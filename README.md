# pokerbot

A multiway no-limit hold'em poker bot for a class project. `CLAUDE.md` holds the
goal, the rules this project works under, and the plan.

What the borrowed poker engine is, how to run it, and what it would cost to move
it from its 20-card deck to a normal 52-card one: `REFERENCE_NOTES.md`.

## Setting the project up

The project needs a private area holding the exact set of outside code it
depends on, kept apart from anything else installed on the machine. That area is
called a virtual environment, and this project has exactly one of them, in a
folder named `.venv`. Everything - our own tests and the borrowed engine - runs
out of it.

Python 3.13 is the minimum this project runs on. Check with `python3 --version`
before starting: the exact set of outside code it installs is the set verified
against 3.13, as the opening comment of `requirements-vendor.txt` records, and
nothing older is supported here.

Run these four lines once, from the top of the repository, in order:

    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip setuptools wheel
    .venv/bin/pip install -r requirements-vendor.txt -r tests/ground_truth/requirements.txt
    .venv/bin/pip install --no-deps --no-build-isolation -e vendor/poker_ai

Line by line: the first makes the private area; the second updates the three
tools that do the installing; the third installs the outside code, both what the
borrowed engine needs and what our own tests need; the fourth makes the borrowed
engine in `vendor/poker_ai` importable from that area, without letting it pull
in its own five-year-old package list. `REFERENCE_NOTES.md` explains why those
last two flags are there.

## Running the tests

Two sets of tests, both from the top of the repository:

    .venv/bin/python -m pytest tests/ground_truth -v
    cd vendor/poker_ai && ../../.venv/bin/python -m pytest test -q

The first set checks that a hand of cards is ranked correctly -- that a flush
really does beat a straight, and so on -- by comparing against `treys`, an
outside library that does nothing but rank poker hands. Every case should say
PASSED. The second set is the borrowed engine's own tests, which come with it.

`treys` is used only to check the tests. It never takes part in the bot's own
play -- `CLAUDE.md` states that rule.
