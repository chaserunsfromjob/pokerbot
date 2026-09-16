from dataclasses import asdict
import json
import random
import sys

import pytest
from treys import Card, Evaluator

from pokerbot.adapters import ProcessPolicy
from pokerbot.engine import Decision, Hand, card_id, replay
from pokerbot.equity import estimate, showdown_share
from pokerbot.policies import EquityConfig, EquityPolicy, menu
from pokerbot.profiles import Profiles
from pokerbot.runner import interval, session


def deck_for(holdings, board):
    prefix = [card_id(c) for h in holdings for c in h] + [card_id(c) for c in board]
    return prefix + [i for i in range(52) if i not in prefix]


def finish_calls(hand):
    while not hand.terminal:
        hand.apply(Decision(1, {}))


@pytest.mark.parametrize("n", range(2, 10))
def test_random_mechanics_and_replay(n):
    rng = random.Random(32 + n)
    for trial in range(12):
        stacks = [10000] * n if trial % 2 else ([100, 250, 1000, 20000] * 3)[:n]
        hand = Hand([f"p{i}" for i in range(n)], stacks, seed=trial)
        while not hand.terminal:
            obs = hand.observation()
            assert obs.pot == sum(p.contribution for p in obs.players)
            assert set(menu(obs)).issubset(hand.state.legal_actions())
            assert set(c for c in obs.hole_cards).isdisjoint(obs.board)
            hand.apply(Decision(rng.choice(menu(obs)), {}))
            assert len(hand.events) < 10000
        replay(json.loads(json.dumps(hand.record())))


@pytest.mark.parametrize("n", range(2, 10))
def test_board_royal_flush_splits_equally(n):
    available = [r + s for r in "23456789TJQKA" for s in "cdh"]
    holdings = [available[i * 2:i * 2 + 2] for i in range(n)]
    board = ["Ts", "Js", "Qs", "Ks", "As"]
    oracle = Evaluator()
    ranks = [oracle.evaluate([Card.new(c) for c in board], [Card.new(c) for c in h]) for h in holdings]
    assert len(set(ranks)) == 1
    assert showdown_share(holdings, board) == pytest.approx([1 / n] * n)


@pytest.mark.parametrize("n", (2, 6, 8, 9))
def test_showdown_winners_match_independent_oracle(n):
    from pokerbot.engine import RANKS, SUITS
    rng = random.Random(400 + n)
    oracle = Evaluator()
    for _ in range(20):
        drawn = rng.sample([r + s for r in RANKS for s in SUITS], 2 * n + 5)
        holdings = [drawn[2 * i:2 * i + 2] for i in range(n)]
        board = drawn[-5:]
        scores = [oracle.evaluate([Card.new(c) for c in board], [Card.new(c) for c in h]) for h in holdings]
        winners = [i for i, s in enumerate(scores) if s == min(scores)]
        expected = [1 / len(winners) if i in winners else 0 for i in range(n)]
        assert showdown_share(holdings, board) == pytest.approx(expected)


def test_side_pots_and_unmatched_return():
    holdings = [["Ac", "Ad"], ["Kc", "Kd"], ["Qc", "Qd"]]
    board = ["2c", "3d", "7h", "8s", "9c"]
    hand = Hand(["aces", "kings", "queens"], [100, 200, 300], deck_for(holdings, board))
    hand.apply(Decision(300, {}))
    finish_calls(hand)
    assert hand.state.returns() == [200, 0, -200]


def test_folded_best_hand_is_ineligible():
    holdings = [["Ac", "Ad"], ["Kc", "Kd"], ["Qc", "Qd"]]
    board = ["2c", "3d", "7h", "8s", "9c"]
    hand = Hand(["aces", "kings", "queens"], [100, 200, 300], deck_for(holdings, board))
    hand.apply(Decision(300, {}))
    hand.apply(Decision(0, {}))
    finish_calls(hand)
    assert hand.state.returns() == [-50, 250, -200]


def test_exact_postflop_increment_and_heads_up_order():
    hu = Hand(["button", "bb"])
    assert hu.observation().actor == 0
    hu.apply(Decision(1, {}))
    hu.apply(Decision(1, {}))
    assert hu.observation().actor == 1
    hand = Hand([str(i) for i in range(8)])
    for _ in range(8):
        hand.apply(Decision(1, {}))
    assert hand.observation().pot == 800
    hand.apply(Decision(237, {}))
    assert hand.observation().pot == 937
    assert hand.events[-1].amount == 137


@pytest.mark.xfail(strict=True, reason="OpenSpiel 2.0.2 reopens action after an insufficient all-in raise; promotion blocker")
def test_short_all_in_does_not_reopen_prior_raiser():
    hand = Hand(["sb", "bb", "button"], [10000, 250, 10000])
    hand.apply(Decision(200, {}))
    hand.apply(Decision(1, {}))
    hand.apply(Decision(250, {}))
    assert hand.observation().actor == 2
    assert hand.observation().legal.call_cost == 50
    assert hand.observation().legal.min_raise_to is None


def test_independent_pokerkit_confirms_short_all_in_rule():
    from pokerkit import Automation, NoLimitTexasHoldem
    state = NoLimitTexasHoldem.create_state(
        (Automation.ANTE_POSTING, Automation.BET_COLLECTION,
         Automation.BLIND_OR_STRADDLE_POSTING),
        True, 0, (50, 100), 100, (10000, 250, 10000), 3)
    for holding in ("AcAd", "KcKd", "QcQd"):
        state.deal_hole(holding)
    state.complete_bet_or_raise_to(200)
    state.check_or_call()
    state.complete_bet_or_raise_to(250)
    assert state.actor_index == 2
    assert not state.can_complete_bet_or_raise_to()
    assert state.min_completion_betting_or_raising_to_amount is None


def test_hidden_cards_never_enter_observation_or_policy():
    first = Hand([str(i) for i in range(8)])
    changed = list(first.deck)
    changed[6:8], changed[8:10] = changed[8:10], changed[6:8]
    second = Hand(first.names, deck=changed)
    assert first.observation() == second.observation()
    payload = asdict(first.observation())
    assert "deck" not in payload and "player_hands" not in payload
    policy = EquityPolicy(EquityConfig(samples=8))
    assert policy.decide(first.observation(), {}, random.Random(4)) == policy.decide(second.observation(), {}, random.Random(4))


def test_persistent_idempotent_session_profiles(tmp_path):
    hand = Hand(["a", "b", "c"])
    hand.apply(Decision(0, {}))
    finish_calls(hand)
    path = str(tmp_path / "profiles.sqlite3")
    first = Profiles(path, "one")
    first.record("hand", hand.events)
    counts = first.view()
    first.record("hand", hand.events)
    assert first.view() == counts
    first.close()
    second = Profiles(path, "one")
    assert second.view() == counts
    third = Profiles(path, "two")
    assert third.view() == {}
    second.close()
    third.close()


def test_seeded_sessions_reproduce_and_reset_learning():
    kwargs = dict(seats=3, hands=6, seed=3, config=EquityConfig(samples=4, adaptive=True),
                  pool=["tight", "caller"], learning="learned")
    a = session(**kwargs)
    b = session(**kwargs)
    assert a["hero_bb"] == b["hero_bb"]
    assert a["public_profiles"] == b["public_profiles"]


def test_process_adapter_and_illegal_actions():
    hand = Hand(["a", "b", "c"])
    policy = ProcessPolicy([sys.executable, "-c", 'import json,sys; r=json.load(sys.stdin); assert "deck" not in r["observation"]; print(json.dumps({"action":1}))'])
    assert policy.decide(hand.observation(), {}, random.Random(0)).action == 1
    with pytest.raises(ValueError, match="Illegal action"):
        hand.apply(Decision(101, {}))


def test_statistical_units_are_independent_trials():
    assert interval([12])["low"] is None
    assert interval([0, 10, 20])["trials"] == 3
    assert interval([0, 10, 20])["mean"] == 10
    with pytest.raises(ValueError, match="Duplicate"):
        estimate(["Ac", "Ac"], [], 3, 1, random.Random(1))


def test_confirmation_cannot_ignore_known_mechanics_defect(tmp_path):
    from pokerbot.benchmark import create_confirmation
    with pytest.raises(RuntimeError, match="short all-in"):
        create_confirmation(tmp_path / "confirm", EquityConfig())
    assert not (tmp_path / "confirm").exists()


def test_oracle_does_not_invent_equity_opponent_model():
    with pytest.raises(ValueError, match="Oracle trials"):
        session(seats=3, hands=1, seed=1, config=EquityConfig(),
                pool=["equity"], learning="oracle")


def test_frozen_baseline_preserves_original_policy():
    from pokerbot.baseline_v1 import FrozenEquityV1
    hand = Hand(["a", "b", "c"], seed=78)
    original = EquityPolicy()
    frozen = FrozenEquityV1()
    rng = random.Random(5)
    while not hand.terminal:
        obs = hand.observation()
        seed = rng.getrandbits(64)
        assert original.decide(obs, {}, random.Random(seed)) == frozen.decide(obs, {}, random.Random(seed))
        hand.apply(frozen.decide(obs, {}, random.Random(seed)))


@pytest.mark.parametrize("gain,passes", [(0, False), (10, True)])
def test_paired_confirmation_and_resume_without_reusing_trials(tmp_path, monkeypatch, gain, passes):
    from pokerbot import benchmark
    from pokerbot.runner import provenance
    monkeypatch.setattr(benchmark, "correctness_failures", lambda: [])
    calls = []
    def simulated_session(**kwargs):
        calls.append(kwargs["seed"])
        # Deliberately large deal variance cancels only if the arms are paired.
        deal = kwargs["seed"] % 1000
        return {"bb_per_100": deal + (0 if kwargs["frozen_hero"] else gain)}
    monkeypatch.setattr(benchmark, "session", simulated_session)
    spec = {"seats": [6, 7, 8, 9], "trials": 30, "hands": 504,
            "attempt": 1, "pools": [["caller"]],
            "baseline": asdict(EquityConfig()), "candidate": asdict(EquityConfig()),
            "learning": "off", "stack_bb": 100, "family_alpha": .025,
            "minimum_improvement_bb_per_100": 5, "provenance": provenance()}
    (tmp_path / "manifest.json").write_text(json.dumps(spec))
    result = benchmark.run_confirmation(tmp_path)
    assert all(cell["passed"] == passes for cell in result["paired_improvement_bb_per_100"].values())
    assert all(cell["mean"] == gain for cell in result["paired_improvement_bb_per_100"].values())
    assert len(calls) == 240
    assert benchmark.run_confirmation(tmp_path) == result
    assert len(calls) == 240  # Completed independent trials must not run again.
