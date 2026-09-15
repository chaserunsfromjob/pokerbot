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
