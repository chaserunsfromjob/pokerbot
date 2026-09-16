"""Rulebook fixtures independent of agreement between two poker engines."""
import json

import pytest

from pokerbot import benchmark
from pokerbot.engine import Decision, Hand, LegacyPokerKitHand, replay
from pokerbot.policies import EquityConfig
from pokerbot.pokerkit_rules import ENGINE_ID


def play(hand, actions):
    for action in actions:
        hand.apply(Decision(action, {}))
    return hand.observation()


@pytest.mark.parametrize("n", range(2, 10))
def test_limp_does_not_reopen_after_short_bb_allin(n):
    stacks = [10000] * n
    stacks[1] = 180
    hand = Hand([str(i) for i in range(n)], stacks)
    obs = play(hand, [1]*(n-1) + [180])
    assert obs.actor == (0 if n == 2 else 2)
    assert obs.legal.call_cost == 80
    assert obs.legal.min_raise_to is None
    assert not hand.is_legal(280)
    with pytest.raises(ValueError, match="Illegal action"):
        hand.apply(Decision(280, {}))
    while not hand.terminal:
        hand.apply(Decision(1, {}))
    assert abs(sum(hand.returns())) < 1e-7
    assert replay(json.loads(json.dumps(hand.record()))).returns() == hand.returns()


@pytest.mark.parametrize("earlier_action,expected_min", [(1,None),(400,500)])
def test_tda_47_example_1_later_caller_has_own_reopening_threshold(earlier_action,expected_min):
    hand = Hand(list("abcde"), [10000,225,10000,300,10000])
    # Flop A bets 100; B all-in 125; C calls; D all-in 200; E calls.
    obs = play(hand, [1]*5+[200,225,1,300,1])
    assert obs.actor == 0 and obs.legal.min_raise_to == 400
    # A can raise, but calling does not reopen C (only 75 more to C).
    obs = play(hand, [earlier_action])
    assert obs.actor == 2
    assert obs.legal.call_cost == (75 if earlier_action == 1 else 175)
    assert obs.legal.min_raise_to == expected_min


def test_checker_cannot_raise_short_opening_but_unacted_player_can():
    hand = Hand(list("abc"), [10000,150,10000])
    obs = play(hand, [1,1,1,1,150])
    assert obs.actor == 2 and obs.legal.min_raise_to == 250
    obs = play(hand, [1])
    assert obs.actor == 0 and obs.legal.call_cost == 50
    assert obs.legal.min_raise_to is None
    with pytest.raises(ValueError, match="Illegal action"):
        hand.apply(Decision(250, {}))


def test_unacted_big_blind_keeps_option_and_full_raise_reopens_limper():
    hand = Hand(list("abcd"), [10000,10000,10000,150])
    obs = play(hand, [1,150,0])
    assert obs.actor == 1 and obs.legal.min_raise_to == 250
    obs = play(hand, [250])
    assert obs.actor == 2 and obs.legal.min_raise_to == 350


def test_covered_opponents_cannot_contest_raise_and_no_forced_terminal_check():
    hand = Hand(list("abc"), [10000,250,250])
    obs = play(hand, [250])
    assert obs.legal.min_raise_to is None  # BB cannot match any extra chips.
    hand = Hand(list("abc"), [10000,300,100])
    hand.apply(Decision(1, {}))
    hand.apply(Decision(0, {}))
    assert hand.terminal  # Only the BB has chips; nothing more is owed.


def test_legacy_histories_keep_original_rule_behavior():
    hand = LegacyPokerKitHand(list("abc"), [1000,180,10000])
    obs = play(hand, [1,1,180])
    assert obs.legal.min_raise_to == 280
    hand.apply(Decision(280, {}))  # Deliberately reproduce the historical defect.
    while not hand.terminal:
        hand.apply(Decision(1, {}))
    record = json.loads(json.dumps(hand.record()))
    restored = replay(record)
    assert type(restored) is LegacyPokerKitHand
    assert restored.record() == hand.record()
    assert Hand(list("abc")).engine_id == ENGINE_ID


def test_confirmation_rejects_unpatched_pokerkit_before_allocating_attempt(tmp_path,monkeypatch):
    assert benchmark.correctness_failures() == []
    monkeypatch.setattr(benchmark, "Hand", LegacyPokerKitHand)
    assert len(benchmark.correctness_failures()) == 3
    monkeypatch.setattr(benchmark, "ROOT", tmp_path)
    with pytest.raises(RuntimeError, match="limp then short all-in"):
        benchmark.create_confirmation(tmp_path/"confirmation", EquityConfig())
    assert not (tmp_path/"confirmation").exists()
    assert not (tmp_path/"runs").exists()
