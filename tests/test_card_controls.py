from dataclasses import replace
import random

import pytest

from pokerbot.card_controls import CardControl
from pokerbot.engine import Decision, Hand
from pokerbot.policies import make_policy
from pokerbot.runner import session
from pokerbot.policies import EquityConfig


@pytest.mark.parametrize("style", ["card_tight", "card_loose", "card_pressure"])
def test_controls_react_to_own_cards_and_reject_unseen_information(style):
    obs = Hand(list("abcdef"), seed=9).observation()
    policy = CardControl(style, samples=256)
    strong = replace(obs, hole_cards=("Ac", "Ad"))
    weak = replace(obs, hole_cards=("7c", "2d"))
    a = policy.decide(strong, {}, random.Random(35))
    b = policy.decide(weak, {}, random.Random(35))
    assert a.action >= 2 and b.action == 0
    assert a.diagnostics["preflop_score"] > b.diagnostics["preflop_score"]
    assert policy.decide(strong, {"unknown": {"fold_rate": 1}}, random.Random(35)) == a


@pytest.mark.parametrize("seats", [2, 6, 8, 9])
def test_card_aware_tables_finish_legally_and_reproduce(seats):
    from pokerbot.engine import replay
    policies = {style: make_policy(style) for style in ("card_tight", "card_loose", "card_pressure")}
    for seed in (120, 131):
        hand = Hand([f"p{i}" for i in range(seats)], seed=seed)
        rng = random.Random(seed)
        while not hand.terminal:
            obs = hand.observation()
            policy = list(policies.values())[obs.actor % 3]
            decision = policy.decide(obs, {}, rng)
            assert obs.legal.contains(decision.action)
            hand.apply(decision)
        assert sum(hand.returns()) == pytest.approx(0)
        replay(hand.record())


def test_card_aware_control_keeps_all_in_opponents_in_equity(monkeypatch):
    import pokerbot.card_controls as controls
    hand = Hand(list("abc"), stacks=[10000, 350, 10000])
    for action in (1, 1, 1, 300, 350, 1, 1):
        hand.apply(Decision(action, {}))
    counts = []
    def equity(hole, board, players, samples, rng):
        counts.append(players)
        return .3
    monkeypatch.setattr(controls, "estimate", equity)
    obs = hand.observation()
    assert any(p.all_in for p in obs.opponents)
    decision = CardControl("card_pressure").decide(obs, {}, random.Random(1))
    assert counts == [3]
    assert not decision.diagnostics["bluff"]


def test_no_fake_oracle_for_card_aware_opponents():
    with pytest.raises(ValueError, match="Oracle trials"):
        session(seats=3, hands=1, seed=0, config=EquityConfig(),
                pool=["card_tight"], learning="oracle")
