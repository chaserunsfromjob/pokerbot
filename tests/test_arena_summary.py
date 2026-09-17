"""The thousand-hand run that finishes `BUILD_PLAN.md` T2, kept as evidence.

`tests/data/arena_6seat_1000hands.json` is the summary of one real run of

    python -m pokerbot.arena --seats 6 --hands 1000 --seed 20260917 \\
        --bot search --opponents random

and this file is what makes it evidence rather than a note: it asserts the
three things T2 is done when, against the numbers in that file. If the summary
is ever replaced by a worse run, these fail.

  * zero invariant failures over the thousand hands,
  * no decision over 250 ms,
  * a win rate whose 95% interval excludes zero.

The machine's load is in the file beside the timings, because a timing without
the load it was taken at is not a measurement anyone can repeat.
"""

from __future__ import annotations

import json
import pathlib

from pokerbot.arena import BUDGET_S, run

SUMMARY_PATH = pathlib.Path(__file__).resolve().parent / "data" / "arena_6seat_1000hands.json"
SUMMARY = json.loads(SUMMARY_PATH.read_text())


def test_the_summary_is_small_enough_to_read():
    assert len(SUMMARY_PATH.read_text().splitlines()) < 200


def test_it_is_the_run_t2_asks_for():
    assert SUMMARY["schema"] == "pokerbot.arena_report/1"
    assert SUMMARY["seats"] == 6
    assert SUMMARY["hands_played"] == 1000
    assert SUMMARY["bot"] == "search"
    assert set(SUMMARY["opponents"].values()) == {"random"}
    assert len(SUMMARY["commit"].removesuffix("+dirty")) == 40


def test_no_invariant_failed():
    assert SUMMARY["invariant_failures"] == 0
    assert SUMMARY["invariants_checked"] == ["I1", "I2", "I3", "I4", "I5", "I6", "I7"]
    # And the two that only half ran say so, rather than being counted whole.
    assert set(SUMMARY["invariants_partial"]) == {"I3", "I6", "I7"}


def test_no_decision_took_longer_than_the_budget():
    assert SUMMARY["decisions"] > 0
    assert SUMMARY["decision_time_max_s"] < BUDGET_S
    assert SUMMARY["decision_time_p99_s"] < BUDGET_S
    assert SUMMARY["budget_s"] == BUDGET_S
    # Nothing was cut short, so every decision in the run is one the seed
    # reproduces.
    assert SUMMARY["decisions_truncated"] == 0
    assert SUMMARY["decisions_starved"] == 0


def test_the_win_rate_interval_excludes_zero():
    low, high = SUMMARY["win_rate_ci_low"], SUMMARY["win_rate_ci_high"]
    assert low <= SUMMARY["win_rate_bb_per_100"] <= high
    assert low > 0 or high < 0, f"the 95% interval [{low}, {high}] contains zero"
    assert low > 0, "the interval excludes zero on the losing side"
    assert SUMMARY["bootstrap_resamples"] >= 10_000
    assert SUMMARY["confidence"] == 0.95


def test_the_timings_carry_the_machine_load_they_were_taken_at():
    for field in ("load_at_start", "load_at_end"):
        assert len(SUMMARY[field]) == 3, f"{field} is not a 1, 5 and 15 minute average"
        assert all(value >= 0 for value in SUMMARY[field])


def test_the_summary_still_matches_what_the_runner_produces():
    """A field renamed in `arena.py` must not leave this evidence stale."""
    fresh = run(seats=6, hands=2, seed=1, replay_check_every=0, resamples=50)
    assert set(fresh) == set(SUMMARY), (
        "the report's fields have changed since the thousand-hand run was "
        "recorded; re-run it rather than editing the file"
    )
