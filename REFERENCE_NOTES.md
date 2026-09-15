# Reference notes: the vendored `poker_ai` engine

## The short version, for the operator

**Recommendation: do not try to convert this engine to the normal 52-card
game. Keep it as a worked example to read from and a six-handed test bed.**

1. **The 52-card conversion is out.** Preparing its compressed card groupings
   (**clustering**, explained below) would need at least 18.4 days of computing
   and 146.5 GiB of memory claimed in one piece, on a laptop that does not have
   it, against a budget of hours. Shown at :279 and :411-431.
2. **Its cut-down 20-card deck seats seven players at most**, so the operator's
   second priority - 8- and 9-handed play - cannot be reached on it at all.
   Six-handed, the first priority, works today. Shown at :438-440 and
   :495-503.
3. **The bot cannot choose how much to bet.** A raise is always one fixed
   amount and only three are allowed per round - the fixed-stakes version of
   the game (**fixed-limit**), where this project asks for the free-stakes
   version (**no-limit**). Shown at :523-554.
4. **What it stays good for**: 50 working automated checks of the game rules,
   hand ranking and payouts, usable as a reference (:182-184), and real
   three-or-more-player play up to seven seats (:440-442).

What this file is for: we did not write the poker engine, we borrowed one. This
file records what we borrowed, how to run it, and what we learned by reading it.
It is the input to the next piece of work, so every claim below points at a
specific file and line rather than at a general impression.

Plain-language note first, because two words recur throughout:

- A **deck** here is not always 52 cards. The engine we borrowed plays a
  stripped-down game called **short deck**, which throws away every card from
  2 to 9 and plays with only 10, Jack, Queen, King and Ace - twenty cards in
  total. Our project wants the normal 52-card game.
- **Clustering** (sometimes called **abstraction** or **bucketing**) is a
  compression step. There are too many possible card situations for any
  computer to think about one at a time, so before training the engine groups
  situations that are strategically similar into a few hundred buckets and
  learns one strategy per bucket. The grouping is saved to a file and the
  training step reads it.

## What is vendored, and how

- Source: `https://github.com/fedden/poker_ai`
- Upstream commit: `73fb394b26623c897459ffa3e66d7a5cb47e9962`
  (2020-07-19, "Merge pull request #110 from mervai/patch-1" - the current tip
  of upstream `master`; the project has had no commits since).
- Upstream status: **archived**. `fedden/poker_ai` was made read-only on GitHub
  on 2023-04-03, so it accepts no issues and no pull requests. Nothing we fix
  can ever go upstream, and there will be no upstream fixes to re-apply: every
  patch in `vendor/poker_ai/` is permanently ours to carry.
- Licence: GPL-3.0. The full text is `vendor/poker_ai/LICENSE`, where it sits
  with the code it covers; there is deliberately no `LICENSE` at the repository
  root, because a licence file at the root of a repository conventionally reads
  as a grant of *this* project to whoever holds it, and this project grants
  nothing to anyone. GPL-3.0's obligations - publishing source, licensing
  derived work alike - are triggered by *distributing* the software, not by
  using it. The operator's position, recorded under "Licence" in `CLAUDE.md`, is
  that pokerbot is never distributed, so those obligations do not bite; that
  decision reopens before the code is ever handed to anyone.
- Location in this repo: `vendor/poker_ai/`, as a **plain copy of the source
  tree**, not a git submodule.

Why a copy and not a submodule: stage 1 of the plan in `CLAUDE.md` is to move
this engine off the 20-card deck, which means editing its source. A submodule
turns every such edit into a fork we have to host and track separately, and
makes `git clone` of this repo produce a directory that is empty until someone
remembers a second command. A copy is one clone, one diff, one review. The
cost would normally be that upstream fixes have to be re-applied by hand, and
here there is no such cost at all: the repository is archived, so there will be
no upstream fixes.

### Changes made to the vendored code

Two, and neither is poker logic.

The first is not code at all. Upstream's `.gitignore` excludes `research/` and
`build/`, and a `.gitignore` inside a subdirectory governs that subdirectory in
*our* repository too. Left in place it silently dropped **twelve files that
upstream itself tracks** from our commit (four under `research/`, eight under
`applications/visualisation/frontend/build/`). It is kept for reference as
`vendor/poker_ai/.gitignore.upstream` and no longer applies; this repo's root
`.gitignore` covers what needs covering. Checked with
`git ls-tree -r --name-only HEAD` against upstream: all 142 upstream files are
now present, the only difference being that one rename.

The second is a one-line compatibility fix:

- `vendor/poker_ai/poker_ai/clustering/game_utility.py:33-39` -
  `self.board.astype(np.int)` became `self.board.astype(int)` (same for
  `hand`). `np.int` was removed from NumPy in version 1.24 and it was only ever
  a second name for Python's own built-in `int`, so the swap cannot change a
  result. Without it, **every** clustering run dies immediately with
  `AttributeError: module 'numpy' has no attribute 'int'`. Reproduced before
  fixing by calling `GameUtility.get_winner()` directly.

Nothing else in `vendor/poker_ai/` differs from upstream. `git log -p --
vendor/poker_ai` shows the whole deviation.

## How to run it on this machine

### Setting up

Upstream's own `vendor/poker_ai/requirements.txt` pins 2020-era versions
(`numpy==1.17.4`, `scipy==1.4.1`, `scikit-learn==0.22.1`) that have no
pre-built packages for Python 3.13 and will not compile. Use
`requirements-vendor.txt` in this repo's root instead - those are the versions
actually verified here.

There is **one** environment for this repo, the root `.venv`, and it runs both
test suites: our own `tests/ground_truth` and the vendored `vendor/poker_ai/test`.
That is why both requirements files go into it. `README.md` gives the same
sequence in plain language; keep the two in step.

```bash
cd <repo root>
python3 -m venv .venv
.venv/bin/pip install --upgrade pip setuptools wheel
.venv/bin/pip install -r requirements-vendor.txt -r tests/ground_truth/requirements.txt
.venv/bin/pip install --no-deps --no-build-isolation -e vendor/poker_ai
```

`tests/ground_truth/requirements.txt` carries `treys`, which the vendored
engine does not need and `requirements-vendor.txt` therefore does not list.
Install only `requirements-vendor.txt` and `pytest tests/ground_truth` stops at
collection with `ModuleNotFoundError: No module named 'treys'`. The two files
stay separate because the ground-truth fixture has to be installable on its
own, away from the engine; the single `.venv` is what makes the full suite
runnable in one place.

The two flags on the last line are both needed:

- `--no-build-isolation` because `vendor/poker_ai/setup.py:6` does
  `import poker_ai` while building, which pulls in `rich`; pip's isolated build
  environment does not have `rich`, so the build fails without this flag.
- `--no-deps` so pip does not try to honour the unbuildable pins in
  `vendor/poker_ai/requirements.txt`.

Verified on: macOS 24.2.0 (arm64), Python 3.13.15, NumPy 2.5.3.

### Running the test suites

Two suites, both from that one `.venv`, both from the repo root:

```bash
.venv/bin/python -m pytest tests/ground_truth -q
cd vendor/poker_ai && ../../.venv/bin/python -m pytest test -q
```

Result on 2026-09-15: **`20 passed`** in 0.01s for `tests/ground_truth`, and
**`53 passed, 2 xfailed`** in 21.52s for the vendored suite.

The two `xfail`s are not breakage. They are
`test/functional/test_short_deck.py::test_short_deck_3[0]` and `[1]`, and the
test's own docstring at `test/functional/test_short_deck.py:124` says it
"Check[s] the state fails when the wrong number of players are provided" - a
zero-player and a one-player table are *supposed* to raise. The rejection
happens at `poker_ai/games/short_deck/state.py:84-88`.

**Do not read "53 passed" as "53 things were checked."** Three of those 53 are
`test/functional/test_cli.py::test_train_multiprocess_async`,
`test_train_multiprocess_sync` and `test_train_singleprocess`, and all three
are empty. Each one ends on line 57, 102 and 143 respectively with

```python
result = runner.invoke(cli, cli_args, catch_exceptions=True)
```

and then stops. Nothing is asserted about `result`; `catch_exceptions=True`
swallows any error the command raised, and the only assertion in the file
(`assert result["exit_code"] == 0`, line 176) is commented out. They also point
`--pickle_dir` at `research/blueprint_algo/`
(`test/functional/test_cli.py:12`), which **does not exist**. `research/` itself
does exist and is vendored here - it is the four files counted above under
"Changes made to the vendored code", in `research/size_of_problem/` and
`research/stat_test/`. It is only the `blueprint_algo/` subdirectory that
upstream never committed, and that is where the clustering tables these tests
pass as `--pickle_dir` were meant to be.

Run by hand, that invocation returns `exit_code = 2` with
`SystemExit(2)`. The tests still report "passed". So upstream has **no working
automated coverage of training at all**; the 50 real tests cover the game
engine, the hand evaluator, payouts, card handling and the combination counts,
which is still a useful suite, but training is unproven by it. Training was
therefore checked here by hand instead - see the run log at the end.

### Running the command-line tool

There is a real bug here, and it is a macOS bug, so it will bite anyone who
uses this repo on a Mac.

**The installed `poker_ai` command does not work on macOS.** Running
`.venv/bin/poker_ai --help` dies with `EOFError` out of Python's
`multiprocessing` machinery. Cause: `poker_ai/ai/agent.py:8` starts a
background helper process (`manager = mp.Manager()`) the moment the package is
imported, at the top level of the file rather than inside a function. On Linux
new processes are cloned from the parent, so this is harmless. On macOS, Python
starts new processes from scratch and each one re-imports the program's main
file; the main file here is `vendor/poker_ai/bin/poker_ai`, whose
`from poker_ai.cli.runner import cli` sits *outside* its
`if __name__ == "__main__":` guard, so the child re-imports the package,
starts another helper, and the chain collapses. The same failure hits
`python - <<EOF` heredocs and anything else where the entry point is
re-importable.

Workaround that does work, and the form every command below uses:

```bash
.venv/bin/python -c "from poker_ai.cli.runner import cli; cli()" --help
```

With `-c`, there is no main file for the child process to re-import, so the
chain never starts. Any script of our own that drives this engine must keep its
`import poker_ai` inside an `if __name__ == "__main__":` block for the same
reason.

The three sub-commands, in the order they must be run:

```bash
# 1. Build the bucketing tables. Writes card_info_lut.joblib and
#    centroids.joblib into --save_dir.
.venv/bin/python -c "from poker_ai.cli.runner import cli; cli()" cluster \
    --low_card_rank 10 --high_card_rank 14 \
    --n_river_clusters 5 --n_turn_clusters 5 --n_flop_clusters 5 \
    --n_simulations_river 2 --n_simulations_turn 2 --n_simulations_flop 2 \
    --save_dir .

# 2. Train. --n_players defaults to 3 (poker_ai/ai/runner.py:163).
#    --single_process is NOT optional here; see the warning below.
.venv/bin/python -c "from poker_ai.cli.runner import cli; cli()" train start \
    --n_players 3 --lut_path <dir from step 1> --n_iterations 50 \
    --dump_iteration 10 --strategy_interval 10 --update_threshold 10 \
    --single_process --nickname smoke3

# 3. Play against the trained strategy. Needs a real terminal.
.venv/bin/python -c "from poker_ai.cli.runner import cli; cli()" play \
    --lut_path <dir from step 1> --strategy_path <agent.joblib from step 2>
```

`--lut_path` wants the **directory**, not the file; the code appends
`/card_info_lut.joblib` itself (`poker_ai/games/short_deck/state.py:281`).

**`--multi_process` is the default and it does not work on this machine.**
Omitting `--single_process` fails with `RuntimeError: An attempt has been made
to start a new process before the current process has finished its
bootstrapping phase`. It is the same `poker_ai/ai/agent.py:8` problem as above,
one layer deeper: the worker process that
`poker_ai/ai/multiprocess/server.py` starts re-imports `poker_ai` while it is
still booting, hits the top-level `mp.Manager()`, and tries to start yet
another process from inside an import.

This one **cannot** be worked around from outside the package. A launcher
script with a proper `if __name__ == "__main__":` guard and `freeze_support()`
was written and tried, and fails identically, because the offending call is
inside the package rather than in the entry point. Fixing it means moving
`mp.Manager()` out of module scope in `agent.py` and into `Agent.__init__`,
behind the `use_manager` flag that already exists there (lines 35-40). Until
that is done, **training on macOS runs on one core**, which is a throughput
cost rather than an inconvenience.

Step 1 timing, measured here: see the run log at the end of this file. Step 2
is **not** covered by the test suite (see the warning above) and was run by
hand here against the tables step 1 produced.

**`cluster` only accepts one deck.** Any rank range other than exactly 10
through 14 is rejected outright:

```
ValueError: Preflop lossless abstraction only works for a short deck with ranks
[10, jack, queen, king, ace]. What was specified={13, 14} doesn't equal what is
allowed={10, 11, 12, 13, 14}
```

That is `poker_ai/clustering/preflop.py:57-64`, and it is the first thing that
has to go for question 1 below.

## Question 1: what would moving to a 52-card deck involve?

Short answer, and the one recommendation: **it is not a flag, and the hard part
is not the poker - it is that the clustering step does not fit in a computer at
52 cards.** The deck size itself is already a parameter. The bucketing step
that consumes the deck is written in a way that cannot scale. Plan the next
task around rewriting `CardCombos`, not around flipping a setting.

Upstream says so itself, in `vendor/poker_ai/README.md:77`: "Currently we only
support a 20 card deck without modification."

Taken piece by piece, cheapest first:

### Already fine, no change needed

- **The deck** - `poker_ai/poker/deck.py:11` already defaults to
  `range(2, 15)`, i.e. all thirteen ranks, and `Deck.__init__` takes
  `include_ranks` as an argument. A 52-card deck is the *default*; short deck
  is what has to be asked for.
- **The hand evaluator** - `poker_ai/poker/evaluation/lookup.py` is the
  standard Cactus-Kev / `deuces` table: 7462 distinct five-card hand values
  built from all thirteen ranks (see the header comment at lines 7-27 and the
  constants at lines 30-38). It is already a full 52-card evaluator and needs
  nothing. Worth noting the flip side: because it is a *standard* evaluator,
  the current short-deck game is scored with standard rankings, so it does not
  use real short-deck rules (where a flush beats a full house). That is an
  upstream fidelity gap that simply disappears when we move to 52 cards.

  One caveat that matters for this repo specifically. `CLAUDE.md:17` treats
  `treys` as an *external* evaluator used to check hand rankings. It is not
  external to this engine in the way that wording suggests: `poker_ai`'s
  evaluator is itself a fork of the same library. Both descend from Cactus
  Kev via Will Drevo's `deuces`, and
  `vendor/poker_ai/poker_ai/poker/evaluation/eval_card.py` still carries the
  identical internals - the same 32-bit card encoding, the same
  `PRIMES = [2, 3, 5, ..., 41]`, and the same verbatim
  `INT_SUIT_TO_CHAR_SUIT = "xshxdxxxc"` (lines 29-41). Checking one against
  the other will catch a transcription slip but cannot catch a bug they
  inherited from their common ancestor. Filed as a finding rather than
  changed here.

- **The solver** - `poker_ai/ai/ai.py` (the MCCFR training loop) never touches
  a card. It only calls `state.legal_actions`, `state.apply_action(...)`,
  `state.info_set` and `state.payout`. Deck size is invisible to it. Same for
  `poker_ai/ai/singleprocess/train.py` and `poker_ai/ai/multiprocess/`.

### Small, mechanical changes

- `poker_ai/games/short_deck/state.py:96` hard-codes
  `include_ranks=[10, 11, 12, 13, 14]` when it builds the table. This is the
  single line that makes the *game* short-deck. It needs to become a parameter
  threaded up through `ShortDeckPokerState.__init__` and `new_game()`
  (`state.py:24-63`) to the two callers in
  `poker_ai/ai/singleprocess/train.py:92` and
  `poker_ai/ai/multiprocess/worker.py:144`. Perhaps thirty lines, no judgment
  calls.

### The genuinely risky change

- `poker_ai/clustering/preflop.py` has to be rewritten. Two problems:
  - `compute_preflop_lossless_abstraction` (lines 51-64) hard-raises unless the
    deck is exactly `{10, 11, 12, 13, 14}`.
  - `make_starting_hand_lossless` (lines 8-48) is a hand-typed chain of 15
    branches (one `if`, then 14 `elif`), which between them return the 25 magic
    numbers 0-24, one per short-deck starting hand class: the five pair branches
    return one number each, and the ten non-pair branches return a suited or an
    unsuited number. A 52-card deck has **169** starting hand classes
    (13 pairs + 78 suited + 78 unsuited). Writing that enumeration ourselves is
    allowed by `CLAUDE.md:16`, the forefront-rule bullet that puts card
    combinatorics - the 169 preflop classes, suit isomorphisms, deck
    enumeration - on our side of the line and leaves ranking, valuing and
    choosing with the engine. Deciding "which of the 169 classes is this hand"
    only sorts hands into named boxes; it never says which box is better. It
    must still be generated and tested against the evaluator, not typed out by
    hand or by a model.

### The blocker

`poker_ai/clustering/card_combos.py` builds, **in memory, all at once**, every
combination of hole cards plus board for each street. `CardCombos.__init__`
(lines 29-41) assigns `self.flop`, `self.turn` and `self.river` as NumPy arrays
of `Card` objects, via `create_info_combos` (lines 58-111), which is a plain
Python double loop over every starting hand crossed with every public card
combination.

Measured sizes (computed from the same `comb()` arithmetic the upstream test
`test/functional/test_clustering.py:43-45` asserts against):

| Street | Rows, 20-card deck | Rows, 52-card deck |
| --- | --- | --- |
| flop | 155,040 | 25,989,600 |
| turn | 581,400 | 305,377,800 |
| river | **1,627,920** | **2,809,475,760** |

The river array at 52 cards is 2,809,475,760 rows of seven `Card` objects. A
NumPy array of Python objects holds one 8-byte pointer per element, so the
pointer array alone comes to
2,809,475,760 x 7 x 8 = 157,330,642,560 bytes, i.e. **146.5 GiB** - and that is
before a single `Card` exists behind those pointers, each of which measures 344
bytes here. The `create_info_combos` double loop would also run
3,446,220,960 iterations with a NumPy `isin` call inside each one - that is
every five-card board crossed with every two-card hand, C(52,5) x C(52,2) =
2,598,960 x 1,326 = 3,446,220,960 (the loop enumerates the two independently
and filters out the overlapping pairs inside the body, which is why it is
C(52,5) and not C(50,5) here). None of this is "slow", it is "will not start":
the array is allocated in one piece before any clustering work begins.

There is a second, smaller scaling problem in the same area:
`card_info_lut_builder.py:93-103` (and the turn/flop equivalents at 117-127 and
139-149) hand `self.process_river_ehs` - a **bound method** - to a
`ProcessPoolExecutor`. Pickling a bound method pickles the object it is bound
to, which is the builder, which holds those multi-million-row arrays. So the
entire combination table is serialised and shipped to a worker process once per
chunk. That is why clustering is slow even at 20 cards on this machine.

So the honest scope for a 52-card move is: rewrite the combination generation
to stream and to key on a canonical (suit-isomorphic) form instead of
materialising every combination, rewrite the preflop abstraction for 169
classes, then thread the rank range through the state object. The first of
those is a real piece of engineering against published abstraction techniques,
not a patch.

### Cost of clustering, measured

The 20-card short deck took **1 hour 29 minutes** to cluster here, at settings
deliberately set below anything usable (5 buckets per street, 2 simulations per
decision, against upstream defaults of 50 and 6). Full numbers in the run log
at the end.

The budget these numbers answer to is the compute-budget bullet at
`CLAUDE.md:29` - **no multi-day computing; a playable bot has to be reachable in
hours, on one laptop** - which the operator stated on 2026-09-15. Measure every
cost below against that bullet.

**Conclusion: this engine's 52-card clustering path is out. It fails the budget
on time and it fails it on memory, and either one alone would be enough.**

On time: at best **18.4 days**, against a budget of hours. The working, which
must be quoted with the number, is the most favourable arithmetic available -
scale the river stage by its own row growth, 2,809,475,760 / 1,627,920 = a
factor of about 1,726, so 1,726 x 920.5s = about 1,588,800s, which over 86,400
seconds per day is 18.4 days. It is a floor rather than an estimate, because
cost per row is not constant across stages: the flop stage took 2,338.5s for
155,040 rows, which is 2,338.5 / 155,040 = 0.0151s per row, while the river
stage took 920.5s for 1,627,920 rows, which is 920.5 / 1,627,920 = 0.00057s per
row. The flop is about 27 times more expensive per row than the river, so no
factor taken from one stage carries to another, and the real figure is worse
than 18.4 days rather than better.

On memory: the run never starts at all. The river combination table at 52 cards
needs **146.5 GiB** for its array of pointers alone, before any card object
exists - the arithmetic is under "The blocker" above. That allocation happens
in one piece before any clustering work begins, on a laptop that does not have
it. So the 18.4 days is not even a wait that could be sat through: the job dies
at allocation.

Getting 52-card hold'em inside the budget therefore means rewriting the
abstraction step, not configuring it - streaming and suit-isomorphic canonical
forms, as set out under "The blocker" above.

## Question 2: does it support 3+ players (multiway), or only heads-up?

**Yes, it genuinely supports multiway play, in both the game engine and the
solver - but on its 20-card deck it stops at seven players, measured here.**
Multiway support is the strongest thing the vendored engine has going for it
relative to our goal; the seven-seat ceiling is the sharpest limit on it.

Evidence:

- `ShortDeckPokerState` takes any player list and only rejects fewer than two
  (`poker_ai/games/short_deck/state.py:83-88`). Blinds, button and acting order
  are derived from `n_players`, not hard-coded
  (`state.py:120-133`: pre-flop order is `order[2:] + order[:2]`, i.e. under-
  the-gun first, blinds last).
- Side pots are implemented, which is the part heads-up-only engines skip.
  `poker_ai/poker/engine.py:99-108` (`_compute_payouts`) walks
  `self.table.pot.side_pots` and pays each one to the best-ranked group still
  eligible for it, with odd-chip remainders handed out in seat order
  (`_process_side_pot`, lines 83-97).
- Training exposes `--n_players` and **defaults it to 3**, not 2
  (`poker_ai/ai/runner.py:163`), and it is threaded all the way through both
  the single-process trainer (`ai/singleprocess/train.py:90-93`) and the
  multi-process server and worker (`ai/multiprocess/server.py:99,145,222` and
  `worker.py:145`).
- Upstream's own tests parametrise over `n_players` of 2, 3, 4, 5 and 6 and
  pass (`test/functional/test_short_deck.py:157-159`, `test_pre_flop_pot`).

Checked directly here rather than taken on trust, with `research/seat_sweep.py`
in this repository. At each seat count it deals 50 complete hands and plays
each to a terminal state, choosing every move at random from the engine's own
`legal_actions` list, and asserts after each hand that chips are conserved
(payouts sum to zero). Commands run from the top of the repository in the
project's `.venv`:

```
.venv/bin/python research/seat_sweep.py 2 3 4 5 6
-> 2 players: OK - 50 hands, chips conserved
   3 players: OK - 50 hands, chips conserved
   4 players: OK - 50 hands, chips conserved
   5 players: OK - 50 hands, chips conserved
   6 players: OK - 50 hands, chips conserved

.venv/bin/python research/seat_sweep.py 7 8 9
-> 7 players: OK - 50 hands, chips conserved
   8 players: FAILS - ValueError: Deck is empty - please use Deck.reset()
   9 players: FAILS - ValueError: Deck is empty - please use Deck.reset()
```

**The ceiling on the short deck is seven seats.** Both failures are
`ValueError: Deck is empty - please use Deck.reset()` from
`poker_ai/poker/deck.py:56`, and both are arithmetic, not bugs. The short deck
holds 20 cards; a hand needs two hole cards per player plus five board cards:

- Seven players: 7 x 2 + 5 = 19 cards, which fits in 20. Passes.
- Eight players: 8 x 2 + 5 = 21 cards, which does not fit in 20. Fails - the
  hole cards and flop and turn are dealt, then the river finds an empty deck.
- Nine players: 9 x 2 + 5 = 23 cards. Fails the same way, earlier.

An earlier sweep tested only 2, 3, 4, 5, 6 and 9, so it reported nine as the
only failure; eight fails too. That ceiling disappears on its own once the deck
is 52 cards (9 x 2 + 5 = 23, well inside 52).

What this means against the operator's priorities - mostly 6-handed, then 8-
and 9-handed treated as one band: the 8/9 band is **impossible on the short
deck**, not merely nine-handed. Six-handed, the first priority, works today.
The whole second priority therefore waits on the 52-card move, which is the
work Question 1 above costs out.

### The one place multiway is *not* supported

The built-in terminal game where a human plays the bot is hard-wired to exactly
three seats:

- `poker_ai/terminal/runner.py:51` sets `n_players: int = 3` as a literal.
- `runner.py:62` sets `positions = ["left", "middle", "right"]` and line 63
  names them `{"left": "BOT 1", "middle": "BOT 2", "right": "HUMAN"}`.
- `poker_ai/terminal/render.py:77-85` reads `players["left"]`,
  `players["middle"]` and `players["right"]` by name and zips exactly three
  sets of lines together.

So a six-handed table can be *trained* today, but cannot be *played* through
the bundled interface without rewriting the display. That is display code with
no poker judgment in it, so it is squarely ours to write under the forefront
rule - and since our plan is to read a real table off a screen rather than use
this ASCII interface, it may not be worth writing at all.

## One thing worth flagging that was not asked

The betting is **fixed-limit, not no-limit.** `CLAUDE.md` describes this
project as "a multiway no-limit hold'em poker bot", so this matters for scoping.

In `poker_ai/games/short_deck/state.py:184-193`, a raise is not a chosen amount
- it is always exactly one big blind on top of the call, doubled on the turn
and river:

```python
bet_n_chips = new_state.big_blind
if new_state._betting_stage in {"turn", "river"}:
    bet_n_chips *= 2
```

and `legal_actions` (lines 448-460) caps the number of raises per street at
three, with the code's own comment saying "In limit hold'em we can only
bet/raise if there have been less than three raises in this round of betting".
The action set is therefore `{fold, call, raise}` with a fixed size - there is
no bet-sizing dimension anywhere in the tree.

Upstream's README acknowledges the gap: line 311 lists "Implement a multiplayer
working heads up no limit poker game engine to support the self-play" as
*future* work.

This does not block the current task, but it is a gap that has to be closed,
not a state we can ship from. `CLAUDE.md` asks for no-limit, and a fixed-limit
bot does not meet that: without a bet-sizing dimension it cannot make or read
the sizing decisions that no-limit play turns on. Closing it means enlarging
the action set inside the CFR tree, which multiplies training cost - so it
belongs in the same conversation as the 52-card move rather than being
discovered afterwards.

## Run log

Everything below was run on 2026-09-15 on this machine: macOS 24.2.0 (arm64),
Python 3.13.15, NumPy 2.5.3, inside the single root `.venv` built by the
sequence under "Setting up" above.

### 1. Both test suites, from the one `.venv` - PASS

```
.venv/bin/python -m pytest tests/ground_truth -q
-> 20 passed in 0.01s

cd vendor/poker_ai && ../../.venv/bin/python -m pytest test -q
-> 53 passed, 2 xfailed, 3 warnings in 21.52s
```

(The three warnings are Click 9 deprecation notices about `isolated_filesystem`
in `test/functional/test_cli.py`. See the caveat above about what those three
CLI tests actually check, which is nothing.)

### 2. Clustering, full 20-card short deck - SUCCEEDS, takes 90 minutes

```
.venv/bin/python -c "from poker_ai.cli.runner import cli; cli()" cluster \
    --low_card_rank 10 --high_card_rank 14 \
    --n_river_clusters 5 --n_turn_clusters 5 --n_flop_clusters 5 \
    --n_simulations_river 2 --n_simulations_turn 2 --n_simulations_flop 2 \
    --save_dir .
-> exit 0, real 5369.21s (1h 29m 29s), user 17744.00s
```

Stage by stage, from the tool's own log - `cluster.log`, written into the run's
`--save_dir` alongside the clustering artefacts and, like them, not kept in the
repo, so its timestamps and figures are quoted below rather than pointed at:

| Stage | Rows processed | Time |
| --- | --- | --- |
| pre-flop | 190 | under 1s |
| river | 1,627,920 | 920.5s |
| turn | 581,400 | 2,022.9s |
| flop | 155,040 | 2,338.5s |
| lookup table built and saved after each street | | 59.9s |
| **total** | | **5,341.8s** |

That fifth row is not padding, and it is why the three street figures do not add
up to the total on their own: 920.5 + 2,022.9 + 2,338.5 = 5,281.9s, which is
59.9s short of the 5,341.8s the tool reports. Each street's timer stops before
the work that follows it. The log shows the gaps directly - river clusters
finish at 13:33:32 and the turn starts at 13:33:51 (19s), turn finishes 14:07:33
and flop starts 14:07:55 (22s), flop finishes 14:46:54 and the overall timer
stops at 14:47:14 (20s) - 61s at one-second timestamp resolution, against the
59.9s the two timers differ by. In each gap the builder turns that street's
cluster ids into a dictionary
(`Creating lookup table`, `card_info_lut_builder.py:365`) and writes both
`.joblib` files to disk (`card_info_lut_builder.py:76-85`), all of it outside
the `start`/`end` pair the street times (`card_info_lut_builder.py:92-107`, with
`create_card_lookup` called afterwards on line 111).

Separately, the 5,341.8s the tool reports is less than the 5,369.21s of wall
clock above it by 27.4s. That is the same effect at the outer edge: the overall
timer starts at `card_info_lut_builder.py:66`, after Python has started and
after `CardCombos` has built the flop, turn and river tables (`created flop`
13:17:47, `created turn` 13:17:53, `created river` 13:18:12).

The figures in the table are the log's own, rounded to one decimal. Verbatim,
the log reports `920.4663696289062`, `2022.8680839538574` and
`2338.4650852680206` seconds for river, turn and flop, and
`5341.814363002777` seconds overall. On those raw figures the gap the fifth row
carries is 60.0s rather than 59.9s; the table shows 59.9s so that its own
rounded rows add up to its own rounded total.

Output: `card_info_lut.joblib` (74 MB) and `centroids.joblib`.

Note those were the **cheapest settings that still run** - 5 buckets per street
and 2 simulations per decision, against upstream defaults of 50 buckets and 6
simulations. A default-settings run would be far longer, and even at these
settings scikit-learn warned `Number of distinct clusters (3) found smaller
than n_clusters (5)`, meaning the buckets are too coarse to be useful for real
play. This run proves the pipeline works; it does not produce a usable bot.
Treat 90 minutes as a floor, not an estimate.

### 3. Training, 3-handed - SUCCEEDS

```
.venv/bin/python -c "from poker_ai.cli.runner import cli; cli()" train start \
    --n_players 3 --lut_path ../lut --n_iterations 50 --dump_iteration 10 \
    --strategy_interval 10 --update_threshold 10 --single_process --nickname smoke3
-> exit 0, real 27.42s
```

Wrote `smoke3_<timestamp>/agent.joblib`, `config.yaml` and `server.gz`, and
printed a learned strategy per information set, e.g.
`{"cards_cluster":6,"history":[{"pre_flop":["raise","call","raise","call"]}]}`
-> fold 0.00, call 0.00, raise 1.00.

### 4. Training, 6-handed - SUCCEEDS

```
... train start --n_players 6 ... --n_iterations 50 ... --single_process
-> exit 0, real 376.37s
```

Same 50 iterations cost 27s at three players and 376s at six - about fourteen
times more for twice the players. That is the game tree growing, and it is the
number to remember when planning how long a real six-handed training run takes.

### 5. Training with the default `--multi_process` - FAILS

```
... train start --n_players 3 ... --multi_process ...
-> exit 1
RuntimeError: An attempt has been made to start a new process before the
current process has finished its bootstrapping phase.
```

**The cause is importing the package at all, not the `--multi_process` flag.**
`vendor/poker_ai/poker_ai/ai/agent.py:8` runs `manager = mp.Manager()` at
module scope, and `poker_ai/__init__.py` pulls that module in, so starting a
worker process happens the moment anything imports `poker_ai`. On macOS, new
processes are started by re-running the program from scratch rather than
copying the running one (Python calls this the "spawn" start method), so the
child re-imports the importing script, hits `mp.Manager()` again, and dies with
the `RuntimeError` above.

Two consequences follow, and they are different things:

- **Any unguarded script that imports `poker_ai` dies**, even one that never
  trains and never asks for multiple processes. Seen here: `import poker_ai`
  at the top of a plain script fails with the same `RuntimeError` and an
  `EOFError` out of `multiprocessing/managers.py`.
- **A `if __name__ == "__main__":` guard fixes the import, and only the
  import.** Putting the `poker_ai` imports inside a function called from under
  the guard keeps the re-imported child clean, so the manager starts and the
  script runs - that is what `research/seat_sweep.py` does. It does **not**
  make `--multi_process` training work: a guarded launcher around training was
  tried and failed identically, exit 1. Fixing training needs `mp.Manager()`
  moved out of module scope in `agent.py` itself.

pytest is unaffected: the program the child re-runs is pytest's own entry
point, whose work already sits under such a guard, so the vendored suite passes
regardless.

### 6. Multiway engine check, written for this task - PASSES to seven seats

`research/seat_sweep.py` deals 50 hands to a terminal state at each seat count,
every action drawn at random from the engine's own `legal_actions`, asserting
chips are conserved (`sum(state.payout.values()) == 0`) after each hand.

```
.venv/bin/python research/seat_sweep.py 2 3 4 5 6
-> all OK, 50 hands each, chips conserved
.venv/bin/python research/seat_sweep.py 7 8 9
-> 7 players: OK - 50 hands, chips conserved
   8 players: FAILS - ValueError: Deck is empty - please use Deck.reset()
   9 players: FAILS - ValueError: Deck is empty - please use Deck.reset()
```

Seven seats is the ceiling. Both failures are `poker_ai/poker/deck.py:56` and
both are the 20-card deck running out: 7x2 + 5 = 19 fits, 8x2 + 5 = 21 does
not, 9x2 + 5 = 23 does not. The full reading is under Question 2 above.

### 7. Not run

`poker_ai play` was not exercised. It needs an interactive terminal
(`blessed.Terminal` with `term.cbreak()`) and loops forever waiting for
keystrokes, so it cannot be verified non-interactively. Its three-seat
hard-coding is documented above from reading the source.
