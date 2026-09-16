from dataclasses import replace
import random

import pytest

from pokerbot.baseline_v1 import FrozenEquityV1
from pokerbot.engine import Decision, Hand, RANKS, SUITS, card_id
from pokerbot.river_search import (RiverConfig, RiverPolicy, evaluate_actions,
                                   hypothetical_holdings, reconstruct, rollout)


class Caller:
    def decide(self, obs, profiles, rng):
        return Decision(1, {})


class Folder:
    def decide(self, obs, profiles, rng):
        return Decision(0 if obs.legal.fold else 1, {})


def known_hand(holdings, board, stacks=None):
    prefix = [card_id(c) for h in holdings for c in h] + [card_id(c) for c in board]
    return Hand([f"p{i}" for i in range(len(holdings))], stacks,
                prefix + [c for c in range(52) if c not in prefix])


def to_river(hand):
    while not hand.terminal and hand.observation().street < 3:
        hand.apply(Decision(1, {}))
    assert not hand.terminal
    return hand


@pytest.mark.parametrize("seats", range(2, 10))
def test_public_reconstruction_and_certain_winner_values(seats):
    board = ("As", "Ks", "Qs", "Js", "2d")
    hero = 1 if seats == 2 else 0
    cards = [r + s for r in RANKS for s in SUITS if r + s not in board + ("Ts", "3c")]
    holes = [tuple(cards[i*2:i*2+2]) for i in range(seats)]
    holes[hero] = ("Ts", "3c")
    hand = to_river(known_hand(holes, board))
    obs = hand.observation()
    world = reconstruct(obs, holes)
    assert world.observation() == obs and obs.actor == hero
    original_history = tuple(hand.events)
    for action in (1, 500):
        value = rollout(world, action, hero, Caller(), Caller(), 42)
        expected = obs.pot if action == 1 else obs.pot + (seats - 1) * 400
        assert value == pytest.approx(expected)
    assert tuple(hand.events) == original_history
    assert world.observation() == obs  # Root actions cannot mutate their shared world.
    assert rollout(world, 500, hero, Folder(), Caller(), 42) == pytest.approx(obs.pot)


def test_side_pot_value_keeps_short_all_in_winner():
    holes = [("Kc", "Kd"), ("Ac", "Ad"), ("Qc", "Qd")]
    board = ("2c", "3d", "7h", "8s", "9c")
    hand = known_hand(holes, board, [10000, 300, 1000])
    for action in (1, 1, 1, 300, 1, 1, 1, 1):
        hand.apply(Decision(action, {}))
    obs = hand.observation()
    assert obs.street == 3 and obs.actor == 0 and obs.players[1].all_in
    world = reconstruct(obs, holes)
    assert rollout(world, 1, 0, Caller(), Caller(), 0) == pytest.approx(0)
    # Short aces win the 900 main pot; hero kings win the 600 side pot,
    # of which 300 was newly invested by hero, yielding +300 from this decision.
    assert rollout(world, 600, 0, Caller(), Caller(), 0) == pytest.approx(300)


def test_folded_best_cards_remain_ineligible():
    holes = [("Kc", "Kd"), ("Qc", "Qd"), ("Ac", "Ad")]
    hand = known_hand(holes, ("2c", "3d", "7h", "8s", "9c"))
    for action in (1, 1, 1, 200, 1, 0, 1, 1):
        hand.apply(Decision(action, {}))
    obs = hand.observation()
    assert obs.street == 3 and obs.players[2].folded and obs.pot == 500
    assert rollout(reconstruct(obs, holes), 1, 0, Caller(), Caller(), 0) == 500


def test_short_all_in_reopening_and_exact_call_loss():
    holes = [("Kc", "Kd"), ("Ac", "Ad"), ("Qc", "Qd")]
    hand = to_river(known_hand(holes, ("2c", "3d", "7h", "8s", "9c"), [10000, 350, 10000]))
    for action in (300, 350, 1):
        hand.apply(Decision(action, {}))
    obs = hand.observation()
    assert obs.actor == 0 and obs.legal.min_raise_to is None and obs.legal.call_cost == 50
    world = reconstruct(obs, holes)
    assert rollout(world, 0, 0, Caller(), Caller(), 0) == 0
    assert rollout(world, 1, 0, Caller(), Caller(), 0) == -50
    with pytest.raises(ValueError, match="distinct legal"):
        evaluate_actions(obs, [450], Caller(), Caller(), random.Random(0), 2)


def test_board_tie_has_no_fictitious_value_from_larger_bets():
    holes = [("2c", "3d"), ("4c", "5d"), ("6c", "7d")]
    hand = to_river(known_hand(holes, ("As", "Ks", "Qs", "Js", "Ts")))
    world = reconstruct(hand.observation(), holes)
    for action in (1, 333, 10000):
        assert rollout(world, action, 0, Caller(), Caller(), 0) == pytest.approx(100)


def test_hidden_actual_cards_do_not_change_search_results():
    holes = [("Kc", "Kd"), ("Ac", "Ad"), ("Qc", "Qd")]
    board = ("2c", "3d", "7h", "8s", "9c")
    first = to_river(known_hand(holes, board)).observation()
    other = to_river(known_hand([holes[0], holes[2], holes[1]], board)).observation()
    assert first == other
    policy = RiverPolicy(RiverConfig(worlds=2, response_model="caller"))
    a = policy.decide(first, {}, random.Random(4))
    b = policy.decide(other, {"p1": {"fold_rate": 1}}, random.Random(4))
    assert a == b and first.legal.contains(a.action)
    assert a.diagnostics["river_search"]


def test_reconstruction_rejects_mismatched_public_state_and_duplicate_cards():
    obs = to_river(Hand(list("abc"), seed=4)).observation()
    holes = hypothetical_holdings(obs, random.Random(12))
    with pytest.raises(ValueError, match="public observation"):
        reconstruct(replace(obs, pot=obs.pot + 1), holes)
    duplicate = (holes[0], holes[0], holes[2])
    with pytest.raises(ValueError, match="overlap"):
        reconstruct(obs, duplicate)
    cards = [c for h in holes for c in h] + list(obs.board)
    assert len(cards) == len(set(cards))


def test_earlier_streets_reproduce_frozen_policy():
    hand = Hand(list("abcdef"), seed=93)
    policy = RiverPolicy(RiverConfig(worlds=2))
    while not hand.terminal and hand.observation().street < 3:
        obs = hand.observation()
        expected = FrozenEquityV1().decide(obs, {}, random.Random(22))
        assert policy.decide(obs, {}, random.Random(22)) == expected
        hand.apply(expected)


@pytest.mark.parametrize("tie", [False, True])
def test_policy_selects_certain_value_and_preserves_baseline_on_ties(tie):
    board = ("As", "Ks", "Qs", "Js", "Ts" if tie else "2d")
    holes = [("2c", "3c") if tie else ("Ts", "3c"), ("4c", "5d"), ("6c", "7d")]
    obs = to_river(known_hand(holes, board)).observation()
    result = RiverPolicy(RiverConfig(worlds=2, response_model="caller")).decide(obs, {}, random.Random(13))
    if tie:
        assert result.action == result.diagnostics["baseline_action"] == 1
        assert not result.diagnostics["changed"]
    else:
        assert result.action == obs.legal.max_raise_to
        assert result.diagnostics["changed"]
