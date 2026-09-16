from dataclasses import replace
import random

import pytest

from pokerbot.engine import Decision, Hand
from pokerbot.policies import Control
from pokerbot.response_profiles import ResponseProfiles, public_response
from pokerbot.responses import NamedResponse, probabilities
from pokerbot.river_search import RiverConfig
from pokerbot.runner import session


def contexts():
    facing = Hand(list("abc")).observation()
    hand = Hand(list("ab"))
    hand.apply(Decision(1, {}))
    free = hand.observation()
    hand = Hand(list("abc"), stacks=[10000, 250, 10000])
    for action in (200, 1, 250):
        hand.apply(Decision(action, {}))
    short = hand.observation()
    assert short.legal.min_raise_to is None
    return (facing, free, short)


@pytest.mark.parametrize("style", ["caller", "tight", "aggressive"])
def test_oracle_matches_actual_control_actions_in_legal_contexts(style):
    for obs in contexts():
        name = obs.players[obs.actor].name
        policy = NamedResponse({name: {"response_oracle": style}})
        for seed in range(100):
            result = policy.decide(obs, {}, random.Random(seed))
            assert result.action == Control(style).decide(obs, {}, random.Random(seed)).action
            p = result.diagnostics["response_probabilities"]
            assert sum(p) == pytest.approx(1)
            if not obs.legal.fold:
                assert p[0] == 0
            if obs.legal.min_raise_to is None:
                assert p[2] == 0


def test_named_counts_persist_reset_and_ignore_duplicate_hands(tmp_path):
    obs = contexts()[0]
    row = public_response(obs, Decision(1, {}))
    path = str(tmp_path / "profiles.sqlite3")
    profiles = ResponseProfiles(path, "trial-a")
    profiles.record(0, [row])
    profiles.record(0, [row])
    expected = profiles.view()
    assert expected[row["name"]]["responses"]["0:1:1"] == [0, 1, 0]
    copied = profiles.view()
    copied[row["name"]]["responses"]["0:1:1"][1] = 999
    assert profiles.view() == expected
    profiles.close()
    reopened = ResponseProfiles(path, "trial-a")
    assert reopened.view() == expected
    isolated = ResponseProfiles(path, "trial-b")
    assert isolated.view() == {}
    reopened.close()
    isolated.close()


def test_legal_opportunities_and_no_privileged_fields_in_storage():
    store = ResponseProfiles()
    for obs in contexts():
        row = public_response(obs, Decision(1, {}))
        assert set(row) == {"name", "street", "facing_bet", "raise_available", "action"}
        store.record(len(store.view()), [{**row, "opponent_cards": "not retained"}])
    assert "opponent_cards" not in str(store.db.execute("SELECT observations FROM response_hands").fetchall())
    with pytest.raises(ValueError, match="legal context"):
        store.record("bad", [{"name": "p", "street": 0, "facing_bet": False, "raise_available": False, "action": "raise"}])
    assert store.db.execute("SELECT count(*) FROM response_hands WHERE hand='bad'").fetchone() == (0,)
    store.close()


def test_evidence_is_named_and_backs_off_without_double_counting():
    p = {"responses": {"0:1:1": [0, 100, 0]}}
    pre = probabilities(0, True, True, p)
    river = probabilities(3, True, True, p)
    assert pre == pytest.approx((8*.35/108, (100+8*.45)/108, 8*.20/108))
    assert river == pytest.approx((12*.35/112, (100+12*.45)/112, 12*.20/112))
    obs = contexts()[0]
    name = obs.players[obs.actor].name
    policy = NamedResponse({name: p})
    before = policy.decide(obs, {}, random.Random(90))
    p["responses"]["0:1:1"] = [100, 0, 0]
    assert policy.decide(obs, {}, random.Random(90)) == before
    renamed = replace(obs, players=tuple(replace(player, name="unknown") if player.seat == obs.actor else player for player in obs.players))
    assert policy.decide(renamed, {}, random.Random(90)).diagnostics["response_probabilities"] == pytest.approx((.35, .45, .20))


@pytest.mark.parametrize("style", ["caller", "tight", "aggressive"])
def test_learning_improves_response_prediction_for_stationary_controls(style):
    obs = contexts()[0]
    name = obs.players[obs.actor].name
    store = ResponseProfiles()
    rng = random.Random(701)
    for hand in range(500):
        store.record(hand, [public_response(obs, Control(style).decide(obs, {}, rng))])
    truth = probabilities(0, True, True, {"response_oracle": style})
    learned = probabilities(0, True, True, store.view()[name])
    prior = probabilities(0, True, True)
    assert sum((a-b)**2 for a,b in zip(learned,truth)) < .02
    assert sum((a-b)**2 for a,b in zip(learned,truth)) < sum((a-b)**2 for a,b in zip(prior,truth))
    store.close()


@pytest.mark.parametrize("mode", ["off", "oracle", "learned"])
def test_named_response_session_runs_with_trial_scoped_profiles(tmp_path, mode):
    result = session(seats=3, hands=6, seed=107, config=RiverConfig(worlds=2, response_model="named"),
        hero_policy="river", pool=["caller", "tight"], learning=mode,
        profile_path=str(tmp_path / "profiles.sqlite3"), session_id=mode)
    assert result["hands"] == 6 and result["response_profiles"]


def test_invalid_oracle_and_impossible_counts_are_rejected():
    with pytest.raises(ValueError, match="oracle"):
        probabilities(0, True, True, {"response_oracle": "card_tight"})
    with pytest.raises(ValueError, match="unavailable"):
        probabilities(0, False, False, {"responses": {"0:0:0": [1, 0, 0]}})
