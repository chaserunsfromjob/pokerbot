"""Two jobs: stop the run when an invariant fails, and print the seat table.

**Stopping the run.** `EVALUATION_STRATEGY.md` section 4.5 says a failed
invariant aborts the run rather than being reported. So when a test lets a
`pokerbot.InvariantViolation` escape, the whole pytest session stops there and
then: no later test runs, and no number measured after it can be quoted. A
test that *expects* the violation catches it itself and is unaffected.

**The seat table.** The same section says a seat count the engine cannot deal
is recorded NOT RUN with its reason and never counted as passed. Pytest's own
summary would report that as a skip among many, so this file keeps its own
tally and prints one row per invariant per seat count at the end of the run.
"""

from __future__ import annotations

import pytest

from pokerbot.invariants import InvariantViolation

#: (invariant, seats) -> ("PASS" | "FAIL" | "NOT RUN", reason)
_TALLY: dict[tuple[str, int], tuple[str, str]] = {}


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "invariant(name): the EVALUATION_STRATEGY.md section 4.5 invariant this test checks",
    )


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    report = yield
    marker = item.get_closest_marker("invariant")
    if marker is None:
        return report
    seats = None
    if hasattr(item, "callspec"):
        seats = item.callspec.params.get("seats")
    if seats is None:
        return report
    key = (marker.args[0], seats)
    if report.failed:
        _TALLY[key] = ("FAIL", str(report.longrepr).strip().splitlines()[-1] if report.longrepr else "")
    elif report.skipped:
        reason = ""
        if isinstance(report.longrepr, tuple) and len(report.longrepr) == 3:
            reason = report.longrepr[2].removeprefix("Skipped: ")
        _TALLY[key] = ("NOT RUN", reason)
    elif report.when == "call" and report.passed and key not in _TALLY:
        _TALLY[key] = ("PASS", "")
    return report


def pytest_exception_interact(node, call, report):
    """A violated invariant ends the session, not just the test."""
    if call.excinfo is not None and isinstance(call.excinfo.value, InvariantViolation):
        node.session.shouldstop = (
            f"table invariant violated ({call.excinfo.value}); run aborted "
            "-- no measurement taken after this point is usable"
        )


def pytest_terminal_summary(terminalreporter):
    if not _TALLY:
        return
    invariants = sorted({inv for inv, _ in _TALLY})
    seat_counts = sorted({seats for _, seats in _TALLY})
    write = terminalreporter.write_line
    write("")
    write("Table invariants (EVALUATION_STRATEGY.md section 4.5), by seat count")
    header = "  seats  " + "  ".join(f"{inv:^9s}" for inv in invariants)
    write(header)
    for seats in seat_counts:
        cells = []
        for inv in invariants:
            status, _ = _TALLY.get((inv, seats), ("MISSING", ""))
            cells.append(f"{status:^9s}")
        write(f"  {seats:^5d}  " + "  ".join(cells))
    reasons = sorted(
        (inv, seats, status, reason)
        for (inv, seats), (status, reason) in _TALLY.items()
        if status != "PASS"
    )
    for inv, seats, status, reason in reasons:
        write(f"  {inv} at {seats} seats: {status} -- {reason}")
    missing = [
        (inv, seats)
        for inv in invariants
        for seats in seat_counts
        if (inv, seats) not in _TALLY
    ]
    for inv, seats in missing:
        write(f"  {inv} at {seats} seats: MISSING -- no result was recorded")
