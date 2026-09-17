"""The adapter must stay an adapter.

`CLAUDE.md`'s forefront rule says the game rules and hand evaluation come from
OpenSpiel `universal_poker`, and that `treys` validates tests only and never
takes part in play. This file is the guard on that: it checks what the package
actually loads and what it actually offers, rather than trusting a reading of
the source.

It is not one of the seven invariants, so it carries no invariant marker and
does not appear in the seat-count table.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

from pokerbot import Action, Table, TableConfig

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

_PROBE = """
import sys
import pokerbot
from pokerbot.replay import play_scripted_hand

table = pokerbot.Table(pokerbot.TableConfig(seats=6))
hand = play_scripted_hand(table, seed=4242)
assert hand.is_finished
assert hand.results()["pot"] > 0
loaded = sorted(m for m in sys.modules if m.split(".")[0] in {"treys", "pokerbot", "pyspiel"})
print("|".join(loaded))
"""


def test_playing_a_hand_never_loads_a_hand_evaluator():
    """Dealing and finishing a whole hand must not pull `treys` in."""
    done = subprocess.run(
        [sys.executable, "-c", _PROBE], cwd=REPO_ROOT, capture_output=True, check=False
    )
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")
    loaded = done.stdout.decode().strip().split("|")
    assert "pyspiel" in loaded, f"the engine was never loaded: {loaded}"
    assert not [m for m in loaded if m.startswith("treys")], (
        f"playing a hand loaded a hand evaluator: {loaded}"
    )


def test_the_package_offers_the_fchpa_menu_and_nothing_else():
    """Five moves, the ones ACTION_TRANSLATION.md section 7 settles on."""
    assert [a.value for a in Action] == ["fold", "call", "half_pot", "pot", "all_in"]


def test_the_package_never_reports_a_winner_it_worked_out_itself():
    """Everything `results` reports is read back from the engine."""
    table = Table(TableConfig(seats=4))
    hand = table.new_hand(seed=5, button=0)
    while not hand.is_finished:
        hand.apply_action(Action.FOLD if Action.FOLD in hand.legal_actions() else Action.CALL)
    results = hand.results()
    assert set(results) == {"net", "payouts", "contributions", "pot", "paid_seats", "folded"}
    assert abs(sum(results["net"])) < 1e-9
    # `paid_seats` is nothing but "who did the engine hand chips to".
    assert results["paid_seats"] == [
        seat for seat, amount in enumerate(results["payouts"]) if amount > 0
    ]
