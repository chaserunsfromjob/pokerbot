"""The design document's derived numbers must match the constants they come from.

`tools/check_design_numbers.py` holds every constant `OPPONENT_MODEL_DESIGN.md`
declares and recomputes every figure the document derives from them. This test
runs it, so a stale number fails the suite rather than waiting for a reviewer.

No engine, no network, no dependencies: standard library only.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "tools" / "check_design_numbers.py"
DOCUMENT = REPO_ROOT / "OPPONENT_MODEL_DESIGN.md"


def run_checker(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def test_script_and_document_exist():
    assert SCRIPT.exists(), f"missing {SCRIPT}"
    assert DOCUMENT.exists(), f"missing {DOCUMENT}"


def test_every_derived_number_matches_its_constants():
    result = run_checker()
    assert result.returncode == 0, (
        "tools/check_design_numbers.py found figures in OPPONENT_MODEL_DESIGN.md that "
        "no longer match the constants they derive from:\n" + result.stdout + result.stderr
    )
    assert "all match" in result.stdout


def test_checker_reports_a_mismatch(tmp_path):
    """A changed figure must fail, so a passing run means something."""
    text = DOCUMENT.read_text(encoding="utf-8")
    broken = text.replace("| 0.25 | 20.0% | 80.0% | 16.7% |", "| 0.25 | 21.0% | 80.0% | 16.7% |", 1)
    assert broken != text, "the Table A row this test edits has moved"
    target = tmp_path / "OPPONENT_MODEL_DESIGN.md"
    target.write_text(broken, encoding="utf-8")
    result = run_checker(str(target))
    assert result.returncode == 1
    assert "do not match" in result.stdout
    assert "break-even fold frequency" in result.stdout


def test_checker_reports_a_drifted_forefront_table(tmp_path):
    """§1 claims to reproduce CLAUDE.md's table verbatim; drift must fail."""
    text = DOCUMENT.read_text(encoding="utf-8")
    broken = text.replace(
        "Sorting an opponent into a bucket;",
        "Sorting an opponent into a group;",
        1,
    )
    assert broken != text, "the forefront-rule bullet this test edits has moved"
    target = tmp_path / "OPPONENT_MODEL_DESIGN.md"
    target.write_text(broken, encoding="utf-8")
    result = run_checker(str(target))
    assert result.returncode == 1
    assert "verbatim" in result.stdout


def test_missing_document_is_reported():
    result = run_checker("no/such/document.md")
    assert result.returncode == 2
    assert "not found" in result.stderr
