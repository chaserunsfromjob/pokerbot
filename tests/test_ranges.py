from dataclasses import replace
from itertools import combinations
import math
import random

import pytest

from pokerbot.engine import Decision, Event, Hand, RANKS, SUITS, replay
from pokerbot.equity import estimate, showdown_share
from pokerbot.policies import EquityConfig, EquityPolicy
from pokerbot.range_policy import RangeConfig, RangePolicy
from pokerbot.ranges import (action_contexts, canonical_hole, earliness,
                             log_likelihood, preflop_score, range_equity)
from pokerbot.runner import session


def test_preflop_order_is_suit_invariant_and_uses_engine_strength():
    assert canonical_hole(("Ah", "Kh")) == canonical_hole(("Ks", "As"))
    assert preflop_score(("Ah", "Ad")) == preflop_score(("Ac", "As"))
    assert preflop_score(("Ac", "Ad")) > preflop_score(("7c", "2d"))
    assert canonical_hole(("Ac", "Kd")) != canonical_hole(("Ac", "Kc"))


@pytest.mark.parametrize("seats", range(2, 10))
def test_position_mapping_and_full_hands(seats):
    hand = Hand([f"p{i}" for i in range(seats)], seed=191 + seats)
    obs = hand.observation()
    assert earliness(obs.button, obs.button, seats) == 0
    if seats >= 4:
        assert earliness((obs.button + 3) % seats, obs.button, seats) == 1
    policy = RangePolicy(RangeConfig(samples=24, use_position=True, use_ranges=True))
    while not hand.terminal:
        obs = hand.observation()
        result = policy.decide(obs, {}, random.Random(500 + len(obs.history)))
        assert obs.legal.contains(result.action)
        assert 0 <= result.diagnostics["equity"] <= 1
        assert 1 - 1e-8 <= result.diagnostics["effective_samples"] <= 24 + 1e-8
        hand.apply(result)
    assert sum(hand.returns()) == pytest.approx(0)
    replay(hand.record())


def test_both_features_off_reproduces_original_decisions():
    hand = Hand(list("abcdef"), seed=30)
    while not hand.terminal:
        obs = hand.observation()
        original = EquityPolicy(EquityConfig(samples=128)).decide(obs, {}, random.Random(99))
        candidate = RangePolicy().decide(obs, {}, random.Random(99))
        assert candidate.action == original.action
        assert candidate.diagnostics["equity"] == original.diagnostics["equity"]
        hand.apply(original)


def test_no_evidence_or_zero_conditioning_matches_uniform_estimator():
    obs = Hand(list("abcdef"), seed=100).observation()
    assert not obs.history
    uniform = estimate(obs.hole_cards, obs.board, 6, 128, random.Random(45))
    value, diagnostics = range_equity(obs, 128, random.Random(45))
    assert value == pytest.approx(uniform)
    assert diagnostics["effective_samples"] == pytest.approx(128)
    obs = replace(obs, history=(Event("a", 0, "raise", 1000, True),))
    value, _ = range_equity(obs, 128, random.Random(45), conditioning=0)
    assert value == pytest.approx(uniform)


def test_conditioning_uses_only_opponents_preflop_evidence():
    obs = Hand(list("abc"), seed=1).observation()
    obs = replace(obs, history=(Event("c", 0, "raise", 300, True),
                                Event("a", 0, "call", 250, True),
                                Event("b", 1, "raise", 700, False)))
    assert action_contexts(obs) == {"a": [("call", 1)], "b": []}
    assert log_likelihood(.85, .5, [("raise", 0)]) > log_likelihood(.35, .5, [("raise", 0)])
    assert math.isfinite(log_likelihood(.35, 1, [("raise", 3)] * 100))


def test_exhaustive_river_joint_weights_and_card_blockers():
    # Enumerate every legal opponent holding. The mocked RNG supplies complete
    # uniform proposal coverage, so compare with the finite posterior sum.
    obs = Hand(["hero", "villain"], seed=3).observation()
    obs = replace(obs, hole_cards=("Ac", "Kd"), board=("2c", "4d", "7h", "9s", "Jc"),
                  street=3, history=(Event("villain", 0, "raise", 300, True),))
    known = set(obs.hole_cards + obs.board)
    pairs = list(combinations([r + s for r in RANKS for s in SUITS if r + s not in known], 2))
    class AllPairs:
        def __init__(self):
            self.pairs = iter(pairs)
        def sample(self, available, count):
            assert count == 2 and not known.intersection(available)
            return list(next(self.pairs))
    weighted, mass, uniform = 0., 0., 0.
    for pair in pairs:
        weight = math.exp(.5 * log_likelihood(preflop_score(pair), 1, [("raise", 0)]))
        value = showdown_share([obs.hole_cards, pair], obs.board)[0]
        weighted += weight * value
        mass += weight
        uniform += value
    value, diagnostics = range_equity(obs, len(pairs), AllPairs())
    assert value == pytest.approx(.75 * weighted / mass + .25 * uniform / len(pairs))
    # Conditioning can increase or decrease equity on a particular board;
    # stronger preflop holdings do not always make stronger river hands.
    assert abs(diagnostics["conditioned_equity"] - diagnostics["uniform_equity"]) > .001


def test_all_in_participants_and_public_only_model():
    hand = Hand(list("abc"), stacks=[10000, 350, 10000])
    for action in (1, 1, 1, 300, 350, 1, 1):
        hand.apply(Decision(action, {}))
    obs = hand.observation()
    assert any(p.all_in for p in obs.opponents)
    policy = RangePolicy(RangeConfig(use_ranges=True))
    result = policy.decide(obs, {}, random.Random(10))
    assert result.diagnostics["modeled_opponents"] == 2
    assert policy.decide(obs, {"a": {"fold_rate": 1}}, random.Random(10)) == result


def test_range_factory_runs_through_session_and_keeps_frozen_arm_explicit():
    result = session(seats=3, hands=3, seed=55, config=RangeConfig(samples=24, use_ranges=True),
                     hero_policy="range", pool=["card_tight", "caller"])
    assert result["hands"] == 3
    with pytest.raises(ValueError, match="Frozen hero"):
        session(seats=3, hands=1, seed=0, config=RangeConfig(), hero_policy="range",
                frozen_hero=True, pool=["caller"])
