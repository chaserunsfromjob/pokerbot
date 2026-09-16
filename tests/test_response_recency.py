import json
import math
import sqlite3

import pytest

from pokerbot.response_profiles import ResponseProfiles
from pokerbot.responses import probabilities
from pokerbot.river_search import RiverConfig
from pokerbot.runner import session


def row(name="a", action="passive", street=0):
    return {"name":name,"street":street,"facing_bet":True,"raise_available":True,"action":action}


def test_half_life_is_per_players_opportunities_across_contexts():
    profiles = ResponseProfiles(half_life=64)
    profiles.record(0, [row(action="fold")])
    profiles.record(1, [row(name="b")]*200)
    assert profiles.view()["a"]["responses"]["0:1:1"] == [1,0,0]
    profiles.record(2, [row(street=3)]*64)
    cells = profiles.view()["a"]["responses"]
    assert cells["0:1:1"][0] == pytest.approx(.5)
    decay = 2**(-1/64)
    assert cells["3:1:1"][1] == pytest.approx((1-decay**64)/(1-decay))
    assert sum(probabilities(3,True,True,profiles.view()["a"])) == pytest.approx(1)
    profiles.close()


def test_batching_duplicate_hand_and_reopening_preserve_effective_counts(tmp_path):
    path = str(tmp_path/"recency.sqlite3")
    rows = [row(action="fold" if i%3 == 0 else "passive",street=i%4) for i in range(100)]
    batched = ResponseProfiles(path,"trial",half_life=64)
    batched.record(0,rows)
    expected = batched.view()
    batched.record(0,rows)
    assert batched.view() == expected
    split = ResponseProfiles(half_life=64)
    for i,r in enumerate(rows):
        split.record(i,[r])
    assert split.view() == expected
    batched.close()
    reopened = ResponseProfiles(path,"trial",half_life=64)
    assert reopened.view() == expected
    settings = json.loads(reopened.db.execute("SELECT config FROM response_settings WHERE session='trial'").fetchone()[0])
    assert settings == {"schema":1,"half_life":64}
    isolated = ResponseProfiles(path,"independent",half_life=64)
    assert isolated.view() == {}
    with pytest.raises(ValueError,match="changed"):
        ResponseProfiles(path,"trial",half_life=32)
    with pytest.raises(ValueError,match="changed"):
        ResponseProfiles(path,"trial")
    reopened.close()
    isolated.close()
    split.close()


def test_legacy_raw_data_is_not_silently_reinterpreted(tmp_path):
    path = str(tmp_path/"legacy.sqlite3")
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE response_hands (session TEXT, hand TEXT, observations TEXT, PRIMARY KEY(session,hand))")
    db.execute("INSERT INTO response_hands VALUES ('old','0',?)",(json.dumps([row()]),))
    db.commit()
    db.close()
    with pytest.raises(ValueError,match="Legacy"):
        ResponseProfiles(path,"old",half_life=64)
    raw = ResponseProfiles(path,"old")
    assert raw.view()["a"]["responses"]["0:1:1"] == [0,1,0]
    raw.close()


@pytest.mark.parametrize("value", [0,-1,float("nan"),float("inf"),True])
def test_invalid_half_life_rejected(value):
    with pytest.raises(ValueError,match="Half-life"):
        ResponseProfiles(half_life=value)
    with pytest.raises(ValueError,match="half-life"):
        RiverConfig(response_model="named",response_half_life=value)


def test_fractional_evidence_is_accepted_but_nonfinite_or_boolean_counts_fail():
    p = probabilities(0,True,True,{"responses":{"0:1:1":[.5,2.5,0]}})
    assert p == pytest.approx(((.5+8*.35)/11,(2.5+8*.45)/11,(8*.20)/11))
    for bad in (float("nan"),float("inf"),True,-.5):
        with pytest.raises(ValueError,match="finite nonnegative"):
            probabilities(0,True,True,{"responses":{"0:1:1":[bad,0,0]}})


def test_bad_name_does_not_partially_commit_a_batch():
    profiles = ResponseProfiles(half_life=64)
    with pytest.raises(ValueError,match="name"):
        profiles.record("bad",[row(),row(name=[])])
    assert profiles.view() == {}
    assert profiles.db.execute("SELECT count(*) FROM response_hands").fetchone() == (0,)
    profiles.close()


def test_discounted_profiles_feed_the_existing_policy_without_illegal_actions(tmp_path):
    config = RiverConfig(worlds=2,response_model="named",response_half_life=64)
    result = session(seats=3,hands=8,seed=83,config=config,pool=["caller","tight"],
                     hero_policy="river",learning="learned",profile_path=str(tmp_path/"profiles.sqlite3"))
    assert result["hands"] == 8
    values = [value for p in result["response_profiles"].values() for counts in p["responses"].values() for value in counts]
    assert all(math.isfinite(v) and v >= 0 for v in values)
    assert any(v != int(v) for v in values)
