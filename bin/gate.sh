#!/usr/bin/env bash
# pokerbot's gate. Exit 0 is one of the three things a change needs to land;
# the other two are a fresh independent review pass and a green suite.
#
# Run it from anywhere:  bin/gate.sh
#
# It stands up `.venv` if it is missing, installs the three outside packages the
# tests need if any of them is missing, runs the test suite, and runs the three
# document-arithmetic checkers. A suite that collects no tests is a failure, not
# a pass: an empty run must never be mistaken for a green one.
set -uo pipefail

cd "$(dirname "$0")/.."

VENV=".venv"
PY="$VENV/bin/python"
REQUIREMENTS="requirements-research.txt"

fail=0
failed_steps=""

note() {
    printf '\n== %s\n' "$1"
}

mark_failed() {
    fail=1
    failed_steps="$failed_steps
  - $1"
}

# --- 1. the virtual environment and what the tests need ---------------------

note "dependencies"
if [ ! -x "$PY" ]; then
    echo "no $VENV yet; creating it with python3 -m venv $VENV"
    if ! python3 -m venv "$VENV"; then
        echo "could not create $VENV"
        mark_failed "dependencies"
    fi
fi

if [ -x "$PY" ]; then
    # The import names, not the package names: open_spiel installs as `pyspiel`.
    if "$PY" -c 'import pytest, treys, pyspiel' >/dev/null 2>&1; then
        echo "pytest, treys and open_spiel are already importable; nothing to install"
    elif [ ! -f "$REQUIREMENTS" ]; then
        echo "$REQUIREMENTS is missing, so there is nothing to install from"
        mark_failed "dependencies"
    else
        echo "installing $REQUIREMENTS into $VENV (first run, or one of them is missing)"
        "$PY" -m pip install --quiet --disable-pip-version-check --upgrade pip setuptools wheel
        if ! "$PY" -m pip install --quiet --disable-pip-version-check -r "$REQUIREMENTS"; then
            echo "install failed"
            mark_failed "dependencies"
        elif ! "$PY" -c 'import pytest, treys, pyspiel' >/dev/null 2>&1; then
            echo "installed, but pytest, treys and open_spiel still do not all import"
            mark_failed "dependencies"
        else
            echo "installed"
        fi
    fi
fi

# --- 2. the test suite, which must have collected something -----------------

note "unit tests"
if [ ! -x "$PY" ]; then
    echo "skipped: no $VENV to run them from"
    mark_failed "unit tests"
else
    collected_output=$("$PY" -m pytest tests -q -p no:cacheprovider --collect-only 2>&1)
    collected_status=$?
    collected=$(printf '%s\n' "$collected_output" \
        | grep -Eo '[0-9]+ tests? collected' | tail -1 | grep -Eo '^[0-9]+') || collected=""
    if [ "$collected_status" -ne 0 ]; then
        printf '%s\n' "$collected_output"
        echo "collecting the tests failed"
        mark_failed "unit tests (collection)"
    elif [ -z "$collected" ] || [ "$collected" -eq 0 ]; then
        printf '%s\n' "$collected_output"
        echo "the suite collected no tests; an empty run is not a pass"
        mark_failed "unit tests (collected no tests)"
    else
        echo "collected $collected tests"
        if ! "$PY" -m pytest tests -q -p no:cacheprovider; then
            mark_failed "unit tests"
        fi
    fi
fi

# --- 3. the document-arithmetic checkers ------------------------------------
# Standard library only, so they run on python3 rather than out of the venv.

for checker in check_design_numbers check_table_size_numbers check_evaluation_numbers; do
    note "$checker"
    if ! python3 "tools/$checker.py"; then
        mark_failed "$checker"
    fi
done

# --- the verdict ------------------------------------------------------------

printf '\n'
if [ "$fail" -ne 0 ]; then
    echo "gate: FAILED"
    echo "these steps failed:$failed_steps"
    exit 1
fi
echo "gate: passed"
