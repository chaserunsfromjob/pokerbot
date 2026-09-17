"""The runner plays whole hands, checks the table, and says what happened.

A small run of the real thing: the same code path as the thousand-hand run,
with the hand count turned down so the suite stays quick. What is proved here
is that it runs green, that the report it prints has the numbers
`BUILD_PLAN.md` T2 asks for in it, and that the invariant checks it runs would
actually catch a table that had gone wrong -- a check that never fails on a
broken table is not a check.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import subprocess
import sys

import pytest

from pokerbot import Action, InvariantViolation, Table, TableConfig
from pokerbot.arena import (
    bootstrap_interval,
    check_invariants,
    format_report,
    main,
    percentile,
    run,
    seat_opponents,
)
from pokerbot.baselines import OPPONENTS, always_call, always_fold, uniform_random

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SMALL = dict(seats=6, hands=8, seed=4242, replay_check_every=4, resamples=200)


def test_a_small_run_is_green_and_reports_what_t2_asks_for():
    report = run(**SMALL)
    assert report["hands_played"] == SMALL["hands"]
    assert report["invariant_failures"] == 0
    assert report["decisions"] > 0
    assert report["decision_time_max_s"] < 0.25
    assert report["decisions_starved"] == 0
    assert report["rule_decisions"] == report["decisions"], (
        "the equity rule did not run beside every decision"
    )
    assert 0.0 <= report["rule_agreement"] <= 1.0
    assert report["win_rate_ci_low"] <= report["win_rate_bb_per_100"] <= report["win_rate_ci_high"]
    text = format_report(report)
    for wanted in (
        "hands played",
        "invariant failures",
        "decision time",
        "win rate",
        "95% interval",
        "equity rule",
    ):
        assert wanted in text, f"the report never mentions {wanted!r}:\n{text}"


def test_the_same_seed_runs_the_same_hands():
    first = run(**SMALL)
    second = run(**SMALL)
    assert first["records_sha256"] == second["records_sha256"]
    assert first["win_rate_bb_per_100"] == second["win_rate_bb_per_100"]


def test_the_command_line_prints_the_report_and_exits_zero(capsys):
    code = main(
        [
            "--seats", "6",
            "--hands", "6",
            "--seed", "7",
            "--bot", "search",
            "--opponents", "random",
            "--replay-check-every", "3",
            "--resamples", "200",
        ]
    )
    printed = capsys.readouterr().out
    assert code == 0
    assert "pokerbot arena" in printed
    assert "invariant failures 0" in printed
    assert "big blinds per 100 hands" in printed


@pytest.mark.parametrize("opponent", OPPONENTS)
def test_every_trivial_opponent_can_be_played_against(opponent):
    report = run(seats=6, hands=4, seed=11, opponents=[opponent], replay_check_every=0, resamples=100)
    assert report["hands_played"] == 4
    assert report["invariant_failures"] == 0


def test_the_three_opponents_only_ever_play_a_move_on_the_menu():
    import random

    hand = Table(TableConfig(seats=6)).new_hand(seed=63)
    rng = random.Random(0)
    while not hand.is_finished:
        menu = hand.legal_actions()
        for player in (always_fold, always_call, uniform_random):
            assert player(menu, rng) in menu
        hand.apply_action(Action.CALL if Action.CALL in menu else menu[0])


def test_seating_refuses_a_list_that_does_not_fit_the_table():
    # A mistyped command is not a broken table: it raises an ordinary error,
    # not an invariant violation.
    with pytest.raises(ValueError):
        seat_opponents(6, 0, ["random", "call"])
    with pytest.raises(ValueError):
        seat_opponents(6, 0, ["nobody"] * 5)
    seated, names = seat_opponents(6, 0, ["random"])
    assert sorted(seated) == [1, 2, 3, 4, 5]
    assert set(names.values()) == {"random"}


# --------------------------------------------------------------------------
# the invariant checks have to be able to fail
# --------------------------------------------------------------------------


def finished_record():
    table = Table(TableConfig(seats=6))
    hand = table.new_hand(seed=909, button=0)
    while not hand.is_finished:
        menu = hand.legal_actions()
        hand.apply_action(Action.CALL if Action.CALL in menu else menu[0])
    return hand.record


def test_a_doctored_record_is_caught():
    """One broken record per invariant the runner checks on its own."""
    good = finished_record()
    check_invariants(good)  # the untouched one passes

    broken = dataclasses.replace(good, net=[n + 1 for n in good.net])
    with pytest.raises(InvariantViolation) as caught:
        check_invariants(broken)
    assert caught.value.invariant == "I1"

    over = list(good.contributions)
    over[0] = good.stacks[0] + 1
    broken = dataclasses.replace(good, contributions=over)
    with pytest.raises(InvariantViolation) as caught:
        check_invariants(broken)
    assert caught.value.invariant in {"I2", "I7"}

    paid = list(good.payouts)
    paid[0] = sum(good.contributions) + 1
    broken = dataclasses.replace(good, payouts=paid)
    with pytest.raises(InvariantViolation) as caught:
        check_invariants(broken)
    assert caught.value.invariant in {"I3", "I7"}

    broken = dataclasses.replace(good, button=(good.button + 1) % good.seats)
    with pytest.raises(InvariantViolation) as caught:
        check_invariants(broken)
    assert caught.value.invariant == "I5"


def test_the_runner_stops_rather_than_reporting_a_violation(tmp_path):
    """A violated invariant aborts the run; nothing measured is printed."""
    script = (
        "import sys;"
        "import pokerbot.arena as arena;"
        "orig = arena.check_invariants;"
        "arena.check_invariants = lambda record: ("
        "    _ for _ in ()).throw("
        "    __import__('pokerbot').InvariantViolation('I1', 'deliberate'));"
        "sys.exit(arena.main(['--hands', '3', '--seed', '1', '--replay-check-every', '0']))"
    )
    done = subprocess.run(
        [sys.executable, "-c", script], cwd=REPO_ROOT, capture_output=True, check=False
    )
    assert done.returncode == 2, done.stdout.decode()
    assert b"ABORTED" in done.stderr
    assert b"big blinds per 100 hands" not in done.stdout


# --------------------------------------------------------------------------
# the arithmetic the report is made of
# --------------------------------------------------------------------------


def test_the_interval_brackets_the_average_it_is_an_interval_on():
    values = [1.0, -2.0, 5.0, 0.5, -1.5, 3.0, 2.0, -4.0, 1.0, 0.0] * 5
    low, high = bootstrap_interval(values, seed=3, resamples=500)
    average = sum(values) / len(values)
    assert low < average < high


def test_an_interval_on_a_clear_winner_excludes_zero():
    low, high = bootstrap_interval([2.0, 3.0, 2.5, 2.2, 2.8] * 40, seed=5, resamples=500)
    assert low > 0


def test_the_percentile_never_invents_a_number():
    values = [1.0, 2.0, 3.0, 4.0]
    assert percentile(values, 0.99) == 4.0
    assert percentile(values, 0.5) in values


def test_a_hand_record_is_written_for_every_hand(tmp_path):
    out = tmp_path / "hands.jsonl"
    log = tmp_path / "decisions.jsonl"
    report = run(**SMALL, records_out=str(out), log_out=str(log))
    lines = out.read_text().strip().splitlines()
    assert len(lines) == report["hands_played"]
    assert json.loads(lines[0])["schema"] == "pokerbot.hand_record/1"
    entries = [json.loads(line) for line in log.read_text().strip().splitlines()]
    assert len(entries) == report["decisions"]
    assert {"search_action", "rule_action", "agree", "search_s", "rule_s"} <= set(entries[0])


_PROBE = """
import sys
from pokerbot.arena import run
run(seats=6, hands=2, seed=3, replay_check_every=0, resamples=50)
print("|".join(sorted(m for m in sys.modules if m.split(".")[0] in {"treys", "pyspiel"})))
"""


def test_playing_the_arena_never_loads_the_outside_hand_evaluator():
    """`treys` validates tests; it never takes part in play (`CLAUDE.md`)."""
    done = subprocess.run(
        [sys.executable, "-c", _PROBE], cwd=REPO_ROOT, capture_output=True, check=False
    )
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")
    loaded = done.stdout.decode().strip().split("|")
    assert "pyspiel" in loaded
    assert not [m for m in loaded if m.startswith("treys")], (
        f"an arena run loaded a hand evaluator: {loaded}"
    )
