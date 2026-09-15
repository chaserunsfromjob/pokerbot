# pokerbot

A multiway no-limit hold'em poker bot for a class project. `CLAUDE.md` holds the
goal, the rules this project works under, and the plan.

## Running the ground-truth hand-ranking tests

These tests check that a hand of cards is ranked correctly -- that a flush really
does beat a straight, and so on -- by comparing against `treys`, an outside
library that does nothing but rank poker hands. They need their own private set
of installed packages, kept apart from the rest of the project.

Run all three lines from the top of the repository, in order:

    python3 -m venv .venv
    .venv/bin/pip install -r tests/ground_truth/requirements.txt
    .venv/bin/python -m pytest tests/ground_truth -v

The first line makes that private package area (a "virtual environment"). The
second installs what the tests need into it. The third runs the tests and prints
one line per case. All cases should say PASSED.

`treys` is used only to check the tests. It never takes part in the bot's own
play -- `CLAUDE.md` states that rule.

## Checking the design document's arithmetic

`OPPONENT_MODEL_DESIGN.md` states a small number of settings and then works out
hundreds of figures from them: tables, a worked example, numbers quoted in the
text. When a setting changes, every figure worked out from it has to change too,
and one left behind is a mistake nobody reliably spots by reading.

This command re-does all of that arithmetic and says whether the document still
agrees with itself:

    python3 tools/check_design_numbers.py

It prints one line for each figure that disagrees, and a single count when they
all agree. **Run it before committing any edit to that document.** The test
suite runs it as well, so a stale figure fails the tests:

    python3 -m pytest tests/test_design_numbers.py -q

It needs nothing installed -- no virtual environment, no outside libraries.
