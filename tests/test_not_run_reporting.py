"""A seat count that will not deal must print NOT RUN, with a reason.

`EVALUATION_STRATEGY.md` section 4.5 is strict about this: a seat count the
engine cannot deal is recorded **NOT RUN**, never as passed. Two halves have to
work for that to hold, and this file tests each of them rather than trusting
that the reporting looks right on the day.

The first half is noticing: `deal_check` has to come back with a reason, not
just a no. The second half is the reporting in `conftest.py`, which has to put
that invariant down as NOT RUN and not as a pass. Only the second half is
proved by the live run today, where I3 at two seats is the single NOT RUN row,
so the first half gets its own test here.

Not one of the seven invariants, so no marker and no row in the seat table.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys

from pokerbot import MAX_SEATS, MIN_SEATS, deal_check, dealable_seat_counts

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_every_seat_count_two_to_nine_gets_a_yes_or_a_reason():
    verdicts = dealable_seat_counts()
    assert sorted(verdicts) == list(range(MIN_SEATS, MAX_SEATS + 1))
    for seats, (ok, reason) in verdicts.items():
        assert ok or reason, f"{seats} seats will not deal and gave no reason"


def test_a_seat_count_that_cannot_deal_says_why():
    """The reason is what gets printed, so a blank one is a failure."""
    for seats in (MIN_SEATS - 1, MAX_SEATS + 1):
        ok, reason = deal_check(seats)
        assert not ok, f"{seats} seats should not be dealable"
        assert reason.strip(), f"{seats} seats refused without saying why"
        assert str(seats) in reason


def test_a_skipped_invariant_is_tallied_not_run_and_never_passed(tmp_path):
    """Run the real conftest over a fake invariant that skips, and read it.

    The tally lives in `conftest.py` and only shows itself in the printed
    summary, so the honest way to test it is to run pytest and read what it
    printed.
    """
    shutil.copy(REPO_ROOT / "tests" / "conftest.py", tmp_path / "conftest.py")
    (tmp_path / "test_fake_invariant.py").write_text(
        "import pytest\n"
        "\n"
        "@pytest.mark.invariant('IX')\n"
        "@pytest.mark.parametrize('seats', [2, 3])\n"
        "def test_fake(seats):\n"
        "    if seats == 2:\n"
        "        pytest.skip('NOT RUN: the engine will not deal 2 seats -- made up for this test')\n"
        "    assert True\n",
        encoding="utf-8",
    )
    env = dict(os.environ, PYTHONPATH=str(REPO_ROOT))
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", str(tmp_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    out = done.stdout
    rows = [line for line in out.splitlines() if line.strip().startswith(("2 ", "3 "))]
    two = next(line for line in rows if line.split()[0] == "2")
    three = next(line for line in rows if line.split()[0] == "3")
    assert "NOT RUN" in two, f"the skipped seat count was not printed NOT RUN: {two!r}"
    assert "PASS" not in two, f"the skipped seat count was counted as passed: {two!r}"
    assert "PASS" in three, f"the seat count that ran was not printed PASS: {three!r}"
    assert "made up for this test" in out, "the NOT RUN reason was not printed"
