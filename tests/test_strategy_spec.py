from dataclasses import asdict
import json
from types import SimpleNamespace

import pytest

from pokerbot import benchmark
from pokerbot.policies import EquityConfig
from pokerbot.river_search import RiverConfig
from pokerbot.runner import provenance, session
from pokerbot.strategy_spec import parse_candidate
from pokerbot.turn_search import TurnConfig


def spec(policy="river", learning="off", **parameters):
    return {"schema":1,"policy":policy,"learning":learning,"parameters":parameters}


@pytest.mark.parametrize("policy,kind", [("equity",EquityConfig),("river",RiverConfig),("turn",TurnConfig)])
def test_roundtrip_preserves_exact_policy_and_parameters(policy,kind):
    raw = spec(policy, **({} if policy == "equity" else {"worlds":2}))
    encoded, config = parse_candidate(raw)
    assert type(config) is kind
    assert parse_candidate(json.loads(json.dumps(encoded))) == (encoded,config)
    if policy == "equity":
        assert parse_candidate(asdict(config)) == (encoded,config)
        assert parse_candidate(config) == (encoded,config)


@pytest.mark.parametrize("bad", [spec("unknown"),spec("process"),spec("river","oracle"),
    spec("river","learned"),spec("equity","learned"),spec("river",checkpoint="missing.pt"),
    {**spec(),"schema":True},{**spec(),"schema":2},{**spec(),"extra":1},None])
def test_unsupported_candidates_fail_before_any_confirmation_side_effect(tmp_path,monkeypatch,bad):
    monkeypatch.setattr(benchmark,"ROOT",tmp_path)
    def forbidden():
        pytest.fail("Invalid candidate reached mechanics checks")
    monkeypatch.setattr(benchmark,"correctness_failures",forbidden)
    with pytest.raises(ValueError):
        benchmark.create_confirmation(tmp_path/"out",bad)
    assert list(tmp_path.iterdir()) == []


def test_all_policy_types_share_attempt_ledger_and_alpha_budget(tmp_path,monkeypatch):
    monkeypatch.setattr(benchmark,"ROOT",tmp_path)
    (tmp_path/"research").mkdir()
    (tmp_path/"research/baseline-v0.1.json").write_text(json.dumps({"source_sha256":{}}))
    monkeypatch.setattr(benchmark,"correctness_failures",lambda: [])
    monkeypatch.setattr(benchmark,"provenance",lambda: {"test_fixture":True})
    monkeypatch.setattr(benchmark.subprocess,"run",lambda *a,**k: SimpleNamespace(returncode=0,stdout="fixture",stderr=""))
    monkeypatch.setattr(benchmark,"run_confirmation",lambda out: json.loads((out/"manifest.json").read_text()))
    first = benchmark.create_confirmation(tmp_path/"first",EquityConfig())
    second = benchmark.create_confirmation(tmp_path/"second",spec("river","learned",response_model="named",response_half_life=64))
    assert (first["attempt"],second["attempt"]) == (1,2)
    assert first["family_alpha"] == .025
    assert second["family_alpha"] == pytest.approx(.05/6)
    assert first["baseline"] == second["baseline"] == asdict(benchmark.BASELINE)
    assert first["pools"] == second["pools"]
    assert second["candidate_spec"]["policy"] == "river" and second["learning"] == "learned"
    assert len(json.loads((tmp_path/"runs/confirmation-ledger.json").read_text())) == 2


@pytest.mark.parametrize("policy,kind",[("river",RiverConfig),("turn",TurnConfig)])
def test_typed_confirmation_resume_dispatches_correct_policy_and_preserves_partial_log(tmp_path,monkeypatch,policy,kind):
    candidate, config = parse_candidate(spec(policy,"learned",response_model="named",response_half_life=64,worlds=2))
    manifest = {"seats":[6,7,8,9],"trials":30,"hands":504,"attempt":1,"pools":[["caller"]],
                "baseline":asdict(benchmark.BASELINE),"candidate":asdict(config),"candidate_spec":candidate,
                "learning":"learned","stack_bb":100,"family_alpha":.025,
                "minimum_improvement_bb_per_100":5,"provenance":provenance()}
    (tmp_path/"manifest.json").write_text(json.dumps(manifest))
    (tmp_path/"6-0-candidate.jsonl").write_text("interrupted fixture")
    calls = []
    def simulated_session(**kwargs):
        calls.append(kwargs)
        if kwargs["frozen_hero"]:
            assert kwargs["hero_policy"] == "equity" and kwargs["learning"] == "off"
            assert kwargs["config"] == benchmark.BASELINE
        else:
            assert kwargs["hero_policy"] == policy and type(kwargs["config"]) is kind
            assert kwargs["learning"] == "learned"
            assert "profile_path" not in kwargs  # Default creates fresh trial memory.
        return {"bb_per_100":0}
    monkeypatch.setattr(benchmark,"session",simulated_session)
    result = benchmark.run_confirmation(tmp_path)
    assert len(calls) == 240
    assert all(calls[i]["seed"] == calls[i+1]["seed"] for i in range(0,240,2))
    assert len(list(tmp_path.glob("6-0-candidate.partial-*"))) == 1
    assert benchmark.run_confirmation(tmp_path) == result and len(calls) == 240
    manifest["provenance"]["source_sha256"]["pokerbot/turn_search.py"] = "changed"
    (tmp_path/"manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError,match="Code changed"):
        benchmark.run_confirmation(tmp_path)


def test_actual_named_turn_sessions_reset_profiles_between_trials():
    _,config = parse_candidate(spec("turn","learned",response_model="named",response_half_life=64,worlds=2))
    args = dict(seats=3,hands=3,seed=31,config=config,pool=["caller","tight"],hero_policy="turn",learning="learned")
    first,second = session(**args),session(**args)
    assert first["response_profiles"] == second["response_profiles"]
    assert first["hero_bb"] == second["hero_bb"]
