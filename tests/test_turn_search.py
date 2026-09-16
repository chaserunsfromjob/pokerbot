from dataclasses import replace
from copy import deepcopy
import random

import pytest

from pokerbot.baseline_v1 import FrozenEquityV1
from pokerbot.engine import Decision, Hand, RANKS, SUITS, card_id
from pokerbot.river_search import RiverConfig, RiverPolicy, rollout
from pokerbot.turn_search import (TurnConfig, TurnPolicy, evaluate_turn_actions,
                                 reconstruct_turn, sample_world)


class Caller:
    def decide(self, obs, profiles, rng):
        return Decision(1, {})


def known_hand(holes, board, stacks=None):
    prefix = [card_id(c) for hole in holes for c in hole] + [card_id(c) for c in board]
    return Hand([f"p{i}" for i in range(len(holes))], stacks,
                prefix + [c for c in range(52) if c not in prefix])


def to_street(hand, street=2):
    while not hand.terminal and hand.observation().street < street:
        hand.apply(Decision(1, {}))
    assert not hand.terminal
    return hand


def world_with_river(obs, holes, river):
    prefix = [card_id(c) for hole in holes for c in hole] + [card_id(c) for c in obs.board]
    future = card_id(river)
    return reconstruct_turn(obs, holes, [future] + [i for i in range(52) if i not in prefix + [future]])


@pytest.mark.parametrize("seats", range(2, 10))
def test_turn_reconstruction_and_exact_values_through_forced_runouts(seats):
    board = ("As", "Ks", "Qs", "Js", "2d")
    hero = 1 if seats == 2 else 0
    available = [r+s for r in RANKS for s in SUITS if r+s not in board + ("Ts", "3c")]
    holes = [tuple(available[2*i:2*i+2]) for i in range(seats)]
    holes[hero] = ("Ts", "3c")
    hand = to_street(known_hand(holes, board))
    obs = hand.observation()
    world = world_with_river(obs, holes, board[-1])
    assert world.observation() == obs
    for action in (1, 500, 10000):
        # Hero's royal flush is already complete; callers pay each root raise.
        expected = obs.pot if action == 1 else obs.pot + (seats-1)*(action-100)
        assert rollout(world, action, hero, Caller(), Caller(), 7) == pytest.approx(expected)
    assert world.observation() == obs
    assert not world.terminal  # Each root branch cloned the shared world.


def test_sampled_decks_are_legal_varied_and_repeatable():
    obs = to_street(Hand(list("abcdefghi"), seed=87)).observation()
    worlds = [sample_world(obs, random.Random(seed)) for seed in range(12)]
    for world in worlds:
        assert world.observation() == obs
        assert len(world.deck) == 52 and set(world.deck) == set(range(52))
    assert worlds[4].deck == sample_world(obs, random.Random(4)).deck
    assert len({world.deck[world.deck_index] for world in worlds}) > 1
    with pytest.raises(ValueError, match="public observation"):
        sample_world(replace(obs, pot=obs.pot+1), random.Random(4))
    with pytest.raises(ValueError, match="distinct legal"):
        evaluate_turn_actions(obs, [1,1], Caller(), Caller(), random.Random(4), 2)


def test_future_river_can_change_value_but_actual_hidden_cards_cannot_change_policy():
    holes = [("Kc", "Kh"), ("Ac", "Ad"), ("Qc", "Qd")]
    board = ("2c", "3d", "7h", "8s")
    a = to_street(known_hand(holes, board+("9c",))).observation()
    b = to_street(known_hand([holes[0],holes[2],holes[1]], board+("Kd",))).observation()
    assert a == b
    policy = TurnPolicy(TurnConfig(worlds=2, response_model="caller"))
    assert policy.decide(a, {}, random.Random(41)) == policy.decide(b, {}, random.Random(41))
    assert rollout(world_with_river(a, holes, "9c"), 1, 0, Caller(), Caller(), 3) == 0
    assert rollout(world_with_river(a, holes, "Kd"), 1, 0, Caller(), Caller(), 3) == 300


def test_turn_preserves_short_all_in_and_side_pot_eligibility():
    holes = [("Kc", "Kd"), ("Ac", "Ad"), ("Qc", "Qd")]
    board = ("2c", "3d", "7h", "8s", "9c")
    hand = known_hand(holes, board, [10000,300,1000])
    for action in (1,1,1,300,1,1):
        hand.apply(Decision(action, {}))
    obs = hand.observation()
    assert obs.street == 2 and obs.players[1].all_in
    world = world_with_river(obs, holes, "9c")
    assert rollout(world, 1, 0, Caller(), Caller(), 3) == 0
    assert rollout(world, 600, 0, Caller(), Caller(), 3) == 300
    short = to_street(known_hand(holes, board, [10000,350,10000]))
    for action in (300,350,1):
        short.apply(Decision(action, {}))
    obs = short.observation()
    assert obs.actor == 0 and obs.legal.call_cost == 50 and obs.legal.min_raise_to is None
    assert rollout(world_with_river(obs,holes,"9c"),1,0,Caller(),Caller(),3) == -50


def test_folded_best_hand_never_wins_a_turn_rollout():
    holes = [("Kc", "Kd"), ("Qc", "Qd"), ("Ac", "Ad")]
    hand = known_hand(holes, ("2c","3d","7h","8s","9c"))
    for action in (1,1,1,200,1,0):
        hand.apply(Decision(action, {}))
    obs = hand.observation()
    assert obs.street == 2 and obs.players[2].folded and obs.pot == 500
    assert rollout(world_with_river(obs,holes,"9c"),1,0,Caller(),Caller(),3) == 500


def test_preflop_flop_and_river_behavior_and_rng_remain_identical():
    policy = TurnPolicy(TurnConfig(worlds=2))
    for street in (0,1,3):
        obs = to_street(Hand(list("abcdef"),seed=93),street).observation()
        reference = RiverPolicy(RiverConfig(worlds=2)) if street == 3 else FrozenEquityV1()
        first, second = random.Random(23), random.Random(23)
        assert policy.decide(obs, {}, first) == reference.decide(obs, {}, second)
        assert first.getstate() == second.getstate()


@pytest.mark.parametrize("action",[1,500,1200])
def test_rollout_matches_independently_completed_fixed_deck_hand(action):
    holes = [("Kc","Kh"),("Ac","Ad"),("Qc","Qd"),("Jc","Jh"),("Tc","Th")]
    hand = to_street(known_hand(holes,("2c","3d","7h","8s","Kd"),[1200,700,2400,900,1700]))
    obs = hand.observation()
    expected = deepcopy(hand)
    expected.apply(Decision(action,{}))
    while not expected.terminal:
        expected.apply(Decision(1,{}))
    value = expected.returns()[obs.actor]+obs.players[obs.actor].contribution
    assert rollout(world_with_river(obs,holes,"Kd"),action,obs.actor,Caller(),Caller(),3) == pytest.approx(value)


def test_certain_winner_can_choose_value_raise_on_turn():
    obs = to_street(known_hand([("Ts","3c"),("4c","5d"),("6c","7d")],
                              ("As","Ks","Qs","Js","2d"))).observation()
    result = TurnPolicy(TurnConfig(worlds=2,response_model="caller")).decide(obs,{},random.Random(17))
    assert result.action == obs.legal.max_raise_to
    assert result.diagnostics["turn_search"] and result.diagnostics["changed"]
