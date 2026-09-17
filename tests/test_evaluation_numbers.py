"""The evaluation strategy's derived numbers must match the constants they come from.

`tools/check_evaluation_numbers.py` holds every constant `EVALUATION_STRATEGY.md`
declares and recomputes every figure the document derives from them. This test
runs it, so a stale number fails the suite rather than waiting for a reviewer.

The same arrangement pins `OPPONENT_MODEL_DESIGN.md` on `main`, through
`tools/check_design_numbers.py` and `tests/test_design_numbers.py`. The two
checkers are deliberately separate for now because this branch was cut before
that one existed; consolidating them is filed as a finding, not done here.

No engine, no network, no dependencies: standard library only.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "tools" / "check_evaluation_numbers.py"
DOCUMENT = REPO_ROOT / "EVALUATION_STRATEGY.md"


def run_checker(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(REPO_ROOT),
    )


def broken_copy(tmp_path, old: str, new: str) -> Path:
    """The document with one figure changed, written where the checker can read it."""
    text = DOCUMENT.read_text(encoding="utf-8")
    broken = text.replace(old, new, 1)
    assert broken != text, f"the passage this test edits has moved: {old!r}"
    target = tmp_path / "EVALUATION_STRATEGY.md"
    target.write_text(broken, encoding="utf-8")
    return target


def test_script_and_document_exist():
    assert SCRIPT.exists(), f"missing {SCRIPT}"
    assert DOCUMENT.exists(), f"missing {DOCUMENT}"


def test_every_derived_number_matches_its_constants():
    result = run_checker()
    assert result.returncode == 0, (
        "tools/check_evaluation_numbers.py found figures in EVALUATION_STRATEGY.md "
        "that no longer match the constants they derive from:\n"
        + result.stdout
        + result.stderr
    )
    assert "all match" in result.stdout


def test_checker_reports_a_stale_sample_size(tmp_path):
    """A changed cell of the sample-size table must fail."""
    target = broken_copy(
        tmp_path,
        "| 1,500 (6-max, AIVAT) | 353,200 | 56,512 | 14,128 | 3,532 | 883 |",
        "| 1,500 (6-max, AIVAT) | 353,200 | 56,512 | 14,129 | 3,532 | 883 |",
    )
    result = run_checker(str(target))
    assert result.returncode == 1
    assert "do not match" in result.stdout
    assert "sample-size" in result.stdout


def test_checker_reports_a_stale_wall_clock(tmp_path):
    """A changed hour in the budget table must fail."""
    target = broken_copy(tmp_path, "| **4.9 h** |", "| **4.8 h** |")
    result = run_checker(str(target))
    assert result.returncode == 1
    assert "wall clock" in result.stdout


def test_checker_reports_a_stale_todays_engine_figure(tmp_path):
    """The today's-engine grid is derived too, and must not drift."""
    target = broken_copy(tmp_path, "169,536", "169,530")
    result = run_checker(str(target))
    assert result.returncode == 1
    assert "today's-engine" in result.stdout


def test_checker_reports_a_drifted_release_gate(tmp_path):
    """The gate is stated in five places and every copy must be identical."""
    target = broken_copy(
        tmp_path,
        "prints as NOT GATED and blocks the release exactly as a failure would.",
        "prints as NOT GATED and blocks the release just as a failure would.",
    )
    result = run_checker(str(target))
    assert result.returncode == 1
    assert "release gate" in result.stdout


def test_checker_reports_a_superseded_engine_figure(tmp_path):
    """The engine survey's withdrawn throughput figure must not come back."""
    target = broken_copy(
        tmp_path,
        "it deals **47,564 complete hands per",
        "it deals **56,414 complete six-player hands per",
    )
    result = run_checker(str(target))
    assert result.returncode == 1
    assert "superseded" in result.stdout


def test_checker_reports_a_stale_weight(tmp_path):
    """The table-size weights drive the headline arithmetic; drift must fail."""
    target = broken_copy(tmp_path, "| Primary | 6 | 0.50 |", "| Primary | 6 | 0.55 |")
    result = run_checker(str(target))
    assert result.returncode == 1
    assert "weight" in result.stdout


def test_missing_document_is_reported():
    result = run_checker("no/such/document.md")
    assert result.returncode == 2
    assert "not found" in result.stderr
