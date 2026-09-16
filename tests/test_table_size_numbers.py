"""The table-size notes' derived numbers must match the constants they come from.

`tools/check_table_size_numbers.py` holds one copy of every constant
`TABLE_SIZE_AND_SIZING_NOTES.md` declares and recomputes every figure the
document derives from them. This test runs it, so a stale number fails the suite
rather than waiting for a reviewer.

The drift tests below are what make a passing run mean something: each mutates
one figure in a scratch copy of the document and asserts the checker exits 1.

No engine, no network, no dependencies: standard library only.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "tools" / "check_table_size_numbers.py"
DOCUMENT = REPO_ROOT / "TABLE_SIZE_AND_SIZING_NOTES.md"


def run_checker(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def mutate(tmp_path: Path, old: str, new: str) -> subprocess.CompletedProcess:
    """Write a copy of the document with one figure changed, and check it."""
    text = DOCUMENT.read_text(encoding="utf-8")
    broken = text.replace(old, new, 1)
    assert broken != text, f"the text this test edits has moved: {old!r}"
    target = tmp_path / DOCUMENT.name
    target.write_text(broken, encoding="utf-8")
    return run_checker(str(target))


def test_script_and_document_exist():
    assert SCRIPT.exists(), f"missing {SCRIPT}"
    assert DOCUMENT.exists(), f"missing {DOCUMENT}"


def test_every_derived_number_matches_its_constants():
    result = run_checker()
    assert result.returncode == 0, (
        "tools/check_table_size_numbers.py found figures in "
        "TABLE_SIZE_AND_SIZING_NOTES.md that no longer match the constants they "
        "derive from:\n" + result.stdout + result.stderr
    )
    assert "all match" in result.stdout


def test_drift_in_table_1(tmp_path):
    result = mutate(tmp_path, "| 7 | 0.286 | 0.143 |", "| 7 | 0.287 | 0.143 |")
    assert result.returncode == 1
    assert "Table 1 n=7 dealt in a blind" in result.stdout


def test_drift_in_table_2(tmp_path):
    result = mutate(
        tmp_path,
        "| **5** | 0.600 | 0.400 | 0.200 | 0.000 |",
        "| **5** | 0.600 | 0.400 | 0.210 | 0.000 |",
    )
    assert result.returncode == 1
    assert "Table 2 TV(5,4)" in result.stdout


def test_drift_in_table_3(tmp_path):
    result = mutate(
        tmp_path,
        "| 9-max vs heads-up | 0.778 | ≤ 0.233 |",
        "| 9-max vs heads-up | 0.778 | ≤ 0.234 |",
    )
    assert result.returncode == 1
    assert "Table 3 9 vs 2 bound at spread 0.3" in result.stdout


def test_drift_in_table_4(tmp_path):
    result = mutate(
        tmp_path,
        "| 640 | 2,560 | 2,560 | 10,240 |",
        "| 640 | 2,560 | 2,560 | 10,204 |",
    )
    assert result.returncode == 1
    assert "Table 4 fold_to_cbet both" in result.stdout


def test_drift_in_table_5(tmp_path):
    result = mutate(
        tmp_path,
        "| 0.60 | 27.3% | +2.3pp |",
        "| 0.60 | 27.3% | +2.4pp |",
    )
    assert result.returncode == 1
    assert "error if treated as 0.5 pot" in result.stdout


def test_drift_in_table_6(tmp_path):
    result = mutate(tmp_path, "| 10 | 10.00 | 1.79 |", "| 10 | 10.00 | 1.78 |")
    assert result.returncode == 1
    assert "Table 6 SPR=10 f in 2 street(s)" in result.stdout


def test_drift_in_the_blind_frequency_ratio(tmp_path):
    """The 4.5x ratio is stated twice; changing either copy must fail."""
    result = mutate(
        tmp_path,
        "which is itself **4.5 times higher heads-up than at 9-max**",
        "which is itself **4.6 times higher heads-up than at 9-max**",
    )
    assert result.returncode == 1
    assert "4.5x blind-frequency ratio" in result.stdout
    assert "1 of 2 occurrences disagree" in result.stdout


def test_drift_in_the_fold_to_steal_multiplier(tmp_path):
    result = mutate(
        tmp_path,
        "stat actually pays is nearer **2.25×**",
        "stat actually pays is nearer **2.5×**",
    )
    assert result.returncode == 1
    assert "2.25x restated in R4" in result.stdout


def test_drift_in_the_solver_run_count(tmp_path):
    result = mutate(tmp_path, "= 32 offline solver runs", "= 30 offline solver runs")
    assert result.returncode == 1
    assert "32 offline solver runs" in result.stdout


def test_a_missing_table_is_reported_not_crashed(tmp_path):
    result = mutate(
        tmp_path,
        "#### Table 6: pot fraction needed to reach all-in in `k` equal bets",
        "#### Table 6: renamed out from under the checker",
    )
    assert result.returncode == 1
    assert "cannot be checked" in result.stdout


def test_missing_document_is_reported():
    result = run_checker("no/such/document.md")
    assert result.returncode == 2
    assert "not found" in result.stderr
