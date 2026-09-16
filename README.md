# pokerbot

A multiway no-limit hold'em poker bot for a class project. `CLAUDE.md` holds the
goal, the rules this project works under, and the plan.

## New strategy research environment

The standard-deck no-limit harness lives in `pokerbot/`; the vendored engine
below remains a historical fixed-limit reference. Original coded strategies
and trained models are now in scope. Read `research/PROGRESS.md` for results
and known failures, `research/BENCHMARKS.md` for fixed acceptance criteria,
and `research/BACKLOG.md` for ranked experiments.

After creating the root environment, install and run:

```sh
.venv/bin/python -m pip install -r requirements-research.txt -r tests/ground_truth/requirements.txt
.venv/bin/python -m pokerbot tournament --out runs/my-screen --seats 6 7 8 9 --hands 36
.venv/bin/python -m pokerbot replay runs/my-screen/n6-seed11.jsonl
.venv/bin/python -m pokerbot candidates
.venv/bin/python -m pytest tests -q
```

Use a new output directory for each screening run. Full simulated decks in
replay logs are privileged host data; the policy interface receives only its
own cards and public state. Profiles are stored separately and isolated by
session. Runs record parameters, source hashes, versions, seeds and latency.

PokerKit now referees betting and payouts after independent tests exposed an
OpenSpiel short-all-in reopening defect. OpenSpiel still supplies the frozen
equity sampler and replays old logs. The benchmark retains fractional split-pot
payouts; integer odd-chip allocation requires a separate class-app rules profile.
Run `python -m pokerbot check-gates` for the focused mechanics checks.

**Not yet validated for strength:** mechanics tests pass, but no candidate has
passed the held-out performance benchmark. Generic process adapters are
implemented; native NoRegrets/dickreuter policy bridges and trained artifacts
are not. Run a bounded development sweep with:

```sh
.venv/bin/python research/parameter_screen.py --out runs/my-parameter-screen
```

The sweep resumes completed sessions when rerun with the same source and
configuration. It leaves confirmation deals untouched and makes no promotion
decision.

Card-aware development opponents are available as `card_tight`, `card_loose`
and `card_pressure`. They use engine-calculated equity plus distinct preflop,
position and betting rules; they are test controls, not validated strong bots.
The fixed first-stage confirmation opponents remain unchanged.

```sh
.venv/bin/python research/precision_screen.py --out runs/my-precision-screen
.venv/bin/python research/train_kuhn.py --out runs/my-kuhn-training
```

The first command screens sample counts and decision parameters against both
scripted and card-aware tables on fresh development deals. The second validates
OpenSpiel's existing MCCFR trainer and exported policies on **two-player,
three-card Kuhn poker only**; it does not train the no-limit hold'em bot.
See `research/patches/README.md` for isolated equity/ranking repairs for the
dickreuter candidate. Its complete decision-policy bridge is still unfinished.

Position and preflop-action range candidates have a separate development sweep:

```sh
.venv/bin/python research/range_screen.py --out runs/my-range-screen
```

It compares the frozen original, an equal-sample uniform reference, position
alone, range conditioning alone, and both. The range estimator samples joint
legal card assignments and reports importance-sampling effective sample sizes.
Its action likelihoods are experimental assumptions, not learned player
profiles. It does not yet infer ranges from postflop bets or evaluate future
betting. All-in participants remain in the sampled field. Existing rules,
hand-ranking code and the frozen original strategy are unchanged.

River-only action evaluation is available through a separate development screen:

```sh
.venv/bin/python research/river_screen.py --out runs/my-river-screen
```

It reconstructs hypothetical hands from public observations, compares legal
moves under two fixed response assumptions, and lets PokerKit settle each
continuation. Earlier streets retain the frozen original policy. Uniform hidden
cards, response-model error and noisy move selection remain limitations; this
is not an equilibrium solver. See `research/RIVER_SEARCH.md` for the protocol.

Named public response counts can feed the same river evaluator:

```sh
.venv/bin/python research/response_screen.py --out runs/my-response-screen
.venv/bin/python research/response_stress.py --out runs/my-response-stress.json
```

The first command separates prior-only, known scripted-opponent and learned
models. The second tests prediction under sparse and changing data, including
deliberately mistaken history. The initial model has no forgetting and fails
some robustness diagnostics; it is not validated for exploitation. Read
`research/RESPONSE_LEARNING.md` before interpreting prediction improvements.

Optional per-player recency weighting is now available. Its fixed synthetic
prediction pilot passed the specified average recovery and stationary-tolerance
checks; early predictions after bad history can still be poor. The default
remains raw counts, and prediction passage is not a poker-strength promotion.

```sh
.venv/bin/python research/response_recency.py --out runs/my-response-recency
.venv/bin/python research/recency_screen.py --out runs/my-recency-screen
```

The first command uses the fixed 64-opportunity half-life and 120 complete
streams. The second separately compares original/prior/raw/discounted policies
on fresh played matches. Both save source/configuration hashes and resumable
results. See `research/RESPONSE_RECENCY_RESULTS.md` for the prediction evidence,
and `research/TURN_SEARCH_PLAN.md` for the next, independent search extension.

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
