# pokerbot

A multiway no-limit hold'em poker bot for a class project. `CLAUDE.md` holds the
goal, the rules this project works under, and the plan.

This project is published under the GNU General Public License version 3, whose
full terms are in `LICENSE`, because the borrowed poker engine in
`vendor/poker_ai` carries that licence and publishing this repository counts as
distributing it. The licence's permission cannot be taken back: anyone who has
already taken a copy under this licence keeps those rights permanently, so long
as they keep to the licence's conditions. Making the repository private later,
or putting it under a different licence, would only change what people get from
that point on.

What the borrowed poker engine is, how to run it, and why converting it to a
normal 52-card deck was ruled out: `REFERENCE_NOTES.md`.

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
    .venv/bin/pip install -r requirements-vendor.txt -r requirements-research.txt -r tests/ground_truth/requirements.txt
    .venv/bin/pip install --no-deps --no-build-isolation -e vendor/poker_ai

Line by line: the first makes the private area; the second updates the three
tools that do the installing; the third installs the outside code -- what the
borrowed engine needs, what the engine this project deals its own hands on
needs (that is `requirements-research.txt`, which pins OpenSpiel), and what our
own tests need; the fourth makes the borrowed engine in `vendor/poker_ai`
importable from that area, without letting it pull in its own five-year-old
package list. `REFERENCE_NOTES.md` explains why those last two flags are
there.

## The gate

One command that runs every check this project has and says, in one word,
whether the change is good to go:

    bin/gate.sh

Run it from anywhere in the repository. It does the setting-up itself: if the
private area of outside code (`.venv`, described above) is missing it builds
one, and it installs the three outside packages the tests need -- `pytest`,
`treys` and `open_spiel` -- only when one of them is actually missing, so a
second run takes a couple of seconds.

Then it runs the tests, and the three arithmetic checkers described further
down. It finishes with either `gate: passed`, or `gate: FAILED` followed by the
names of the steps that went wrong.

One thing it deliberately refuses to do is call a run of no tests at all a
success. Before running the suite it counts what the suite found, and treats a
count of zero as a failure, because an empty run looks exactly like a clean one
if nobody counts.

## Running the tests

Two sets of tests come with the borrowed code, both run from the top of the
repository:

    .venv/bin/python -m pytest tests/ground_truth -v
    cd vendor/poker_ai && ../../.venv/bin/python -m pytest test -q

The first set checks that a hand of cards is ranked correctly -- that a flush
really does beat a straight, and so on -- by comparing against `treys`, an
outside library that does nothing but rank poker hands. Every case should say
PASSED. The second set is the borrowed engine's own tests, which come with it.

`treys` is used only to check the tests. It never takes part in the bot's own
play -- `CLAUDE.md` states that rule, in the section called "The forefront
rule", under the heading "What may not be coded".

### The table and its invariants

The `pokerbot` package deals hands on the OpenSpiel engine, and there are seven
statements about a dealt hand that must hold every time -- the chips add up, the
same seed deals the same cards, the engine's own showdown agrees with an outside
hand evaluator, and so on. Those seven are called the invariants, and they are
checked at every table size from two seats to nine. Run them with:

    .venv/bin/python -m pytest -q

At the end it prints a table: one row per table size, one column per invariant,
and in each square either PASS or NOT RUN. NOT RUN means that check was not made
-- because the engine will not deal that many seats, or because the check does
not exist at that table size -- and the reason is printed underneath. A NOT RUN
is never counted as a pass. Nothing should ever say FAIL.

## The scoreboard: how good is a bot?

A poker result over a few hundred hands is mostly luck, so this project never
reports a bare number. One command sits a bot down against a league of
deliberately flawed opponents, plays the same deals twice -- once for the new
version and once for the one it is replacing -- and prints how much each of them
won, with a range around every figure saying how much of it could be luck:

    .venv/bin/python -m pokerbot.scoreboard --bot always_call --hands 200 --seed 1

`--bot` names the version being measured and `--compare` the one it is being
measured against; leave `--compare` out and it uses the reference named in the
config. `--list-bots` prints what the two accept.

**What the opponents are.** Thirteen of them. Four are there to prove the
scoreboard itself is counting correctly -- one folds every hand, one calls
everything, one raises everything, one flips a coin between calling and raising.
The other nine each act out one specific human mistake: the player who calls too
much, the one who waits all night for a premium hand, the one who bets wildly,
the one who only ever bets a real hand so you always know where you are, the one
who gives up the moment the flop misses, two competent ones, the one who plays
badly for a while after losing a big pot, and the one whose bet size tells you
what he has.

**Why the opponents change every night.** Each of those nine is built from a few
settings -- how many hands it plays, how often it raises, how big a loss sets it
off. Those settings are drawn afresh at the start of every run rather than fixed,
because a bot polished against one exact opponent looks better than it is. The
drawn values are printed at the top of the report, so any run can be repeated.

**Why half of them are held back.** The nine are split in two. One half is used
while a bot is being tuned; the other half is never used for anything but the
final accept-or-reject decision. The command enforces it rather than trusting
anyone to remember: ask for a held-back opponent in a tuning run and it refuses
and stops.

**What the report says at the end.** Big blinds won per hundred hands for every
opponent at tables of two, six, eight and nine, each with its range; the same
figures for the difference between the two versions on identical cards; and then
one verdict, ACCEPT or REJECT, by a rule written down before the run and
reprinted at the top of it. The rule is that the overall figure -- weighted
towards six-handed tables, which is what the operator plays most -- has to be
above zero with its whole range above zero, and that no single opponent may be
beating the new version. Winning overall while losing to one opponent is the
signature of a bot that has been polished against the others, and it blocks.

Every number on the page is either a measurement or a decision recorded before
the run. The settings live in `pokerbot/league_config.toml`, which the report
reprints in full, and `EVALUATION_STRATEGY.md` sections 3.2 and 3.5 are what
they implement.

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
