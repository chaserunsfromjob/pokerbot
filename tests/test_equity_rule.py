"""The equity rule: the arithmetic is right, and it never plays.

Two things to prove. First that the rule does what pot odds say it should, on
a case worked out by hand here in the test. Second that it stays a check:
`BUILD_PLAN.md` T2 and `DECISION_LAYER_SEARCH.md` :637 both say it is logged,
not played, and the bot's own module must not so much as load it.
"""

from __future__ import annotations

import subprocess
import sys
import pathlib

from pokerbot import Action, Table, TableConfig
from pokerbot.equity_rule import (
    BET_WHEN_FREE,
    RAISE_MARGIN,
    check,
    pot_and_call,
    rule_action,
    with_odds,
)
from pokerbot.search import build_world

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
MENU = (Action.FOLD, Action.CALL, Action.HALF_POT, Action.POT, Action.ALL_IN)


def test_the_rule_matches_pot_odds_worked_out_by_hand():
    """A pot of 300 and 100 to call, done on paper.

    Calling puts 100 into a pot that will then hold 400, so the seat is buying
    a quarter of it: it needs to win more than 100/(300+100) = 0.25 of the time
    to be worth it. So:

      equity 0.20  -- below the price          -> fold
      equity 0.30  -- above the price          -> call
      equity 0.55  -- above it by more than
                      the 0.25 raising margin  -> raise (pot)
      equity 0.50  -- exactly the price plus
                      the margin, not above it -> call
    """
    pot, to_call = 300.0, 100.0
    assert to_call / (pot + to_call) == 0.25
    assert rule_action(0.20, pot, to_call, MENU) is Action.FOLD
    assert rule_action(0.30, pot, to_call, MENU) is Action.CALL
    assert rule_action(0.55, pot, to_call, MENU) is Action.POT
    assert rule_action(0.25 + RAISE_MARGIN, pot, to_call, MENU) is Action.CALL


def test_with_nothing_to_call_it_bets_only_a_hand_that_is_winning():
    assert rule_action(BET_WHEN_FREE, 300.0, 0.0, MENU) is Action.POT
    assert rule_action(BET_WHEN_FREE - 0.01, 300.0, 0.0, MENU) is Action.CALL


def test_it_never_returns_a_move_that_is_not_on_the_menu():
    """With no fold offered, a hopeless hand calls rather than folding."""
    no_fold = (Action.CALL, Action.ALL_IN)
    assert rule_action(0.01, 300.0, 100.0, no_fold) is Action.CALL
    assert rule_action(0.99, 300.0, 100.0, no_fold) is Action.CALL


def test_the_engines_own_numbers_are_the_ones_the_rule_reads():
    """Pot and price come off the engine, and they are the hand-computed ones.

    Six seats, blinds 50 and 100, nobody has acted: 150 chips are in the
    middle and the first seat to act has put in nothing, so it owes 100 and is
    buying 100/(150+100) = 0.4 of the pot.
    """
    hand = Table(TableConfig(seats=6, small_blind=50, big_blind=100)).new_hand(seed=21)
    view = hand.engine_view()
    result = check(view, seed=3)
    assert (result.pot, result.to_call) == (150.0, 100.0)
    assert abs(result.needed - 0.4) < 1e-12
    assert 0.0 <= result.equity <= 1.0
    # And the action it reports is the one its own arithmetic gives.
    assert result.action is rule_action(result.equity, result.pot, result.to_call, view.menu)


def test_the_equity_comes_from_the_engines_calculator_not_from_here():
    """Switching the calculator on is the only change to the game definition."""
    hand = Table(TableConfig(seats=6)).new_hand(seed=8)
    view = hand.engine_view()
    odds_string = with_odds(view.game_string, 200)
    assert odds_string.count("calcOddsNumSims=200") == 1
    assert odds_string.replace(",calcOddsNumSims=200", "") == view.game_string
    import json
    import random

    world = build_world(view, random.Random(1), game_string=odds_string)
    blob = json.loads(world.to_json())
    assert len(blob["odds"]) == 2 * 6, "the engine did not report odds per seat"
    assert pot_and_call(world, view.player) == (150.0, 100.0)


_PROBE = """
import sys
from pokerbot import Table, TableConfig
from pokerbot.search import decide

hand = Table(TableConfig(seats=6)).new_hand(seed=99)
decide(hand.engine_view(), seed=1)
print("|".join(sorted(m for m in sys.modules if m.startswith("pokerbot"))))
"""


def test_the_bot_does_not_even_load_the_rule():
    """The rule is a check beside the decision, never part of it."""
    done = subprocess.run(
        [sys.executable, "-c", _PROBE], cwd=REPO_ROOT, capture_output=True, check=False
    )
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")
    loaded = done.stdout.decode().strip().split("|")
    assert "pokerbot.search" in loaded
    assert "pokerbot.equity_rule" not in loaded, (
        f"deciding a move loaded the equity rule: {loaded}"
    )
