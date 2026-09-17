"""A seat count that will not deal must print NOT RUN, with a reason.

`EVALUATION_STRATEGY.md` section 4.5 is strict about this: a seat count the
engine cannot deal is recorded **NOT RUN**, never as passed. Two halves have to
work for that to hold, and this file tests each of them rather than trusting
that the reporting looks right on the day.

The live run proves that a skip prints NOT RUN, because I3 at two seats is
one. It does not prove that `deal_check` gives a reason, and it does not prove
the tally refuses to call a skip a pass, so both get their own test here.

Not one of the seven invariants, so no marker and no row in the seat table.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys

import pytest

from pokerbot import MAX_SEATS, MIN_SEATS, deal_check, dealable_seat_counts
from pokerbot import table as table_module

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


def test_an_adapter_bug_is_not_reported_as_an_undealable_seat_count(monkeypatch):
    """A `KeyError` in the adapter is our mistake, not the engine's refusal.

    `deal_check`'s whole job is to say why a seat count will not deal, and it
    is believed when it says so. If it swallowed every exception, a broken
    `Hand.__init__` would be printed as "6 seats would not deal" and
    the bug would be hidden behind a NOT RUN row. So only the engine's own
    refusal is caught; anything else comes straight back out.
    """

    def exploding_init(self, *args, **kwargs):
        raise KeyError("button")

    monkeypatch.setattr(table_module.Hand, "__init__", exploding_init)
    with pytest.raises(KeyError):
        deal_check(6)


def test_a_violated_invariant_stops_the_run_and_nothing_later_is_measured(tmp_path):
    """The abort in `conftest.py` is the other half of section 4.5's rule.

    A violated invariant is not a failing test among others: the run stops
    there, so that no number measured after it can be quoted. That is only
    provable by running pytest and reading what did and did not happen, so
    this runs the real `conftest.py` over a fake invariant that violates at
    the first of two seat counts, with a second test file that must never be
    reached.
    """
    shutil.copy(REPO_ROOT / "tests" / "conftest.py", tmp_path / "conftest.py")
    (tmp_path / "test_a_violating_invariant.py").write_text(
        "import pytest\n"
        "\n"
        "from pokerbot.invariants import InvariantViolation\n"
        "\n"
        "@pytest.mark.invariant('IX')\n"
        "@pytest.mark.parametrize('seats', [2, 3])\n"
        "def test_fake(seats):\n"
        "    if seats == 2:\n"
        "        raise InvariantViolation('IX', 'made up for this test')\n"
        "    assert True\n",
        encoding="utf-8",
    )
    (tmp_path / "test_z_later.py").write_text(
        "def test_must_not_run():\n"
        "    assert True\n",
        encoding="utf-8",
    )
    env = dict(os.environ, PYTHONPATH=str(REPO_ROOT))
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-v", str(tmp_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    out = done.stdout + done.stderr
    assert done.returncode != 0, out
    assert "Interrupted" in out, f"the session was not interrupted: {out}"
    assert "run aborted" in out, f"the abort was not explained: {out}"

    three = [line for line in out.splitlines() if line.strip().startswith("3 ")]
    assert all("PASS" not in line for line in three), (
        f"a seat count after the violation was counted as passed: {three!r}"
    )
    later = [line for line in out.splitlines() if "test_must_not_run" in line]
    assert all("PASSED" not in line for line in later), (
        f"a test after the violation ran and was counted: {later!r}"
    )
