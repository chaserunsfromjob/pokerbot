# Solvers, equity calculators and paid services that could supply the bot's poker judgment

Research date: 15 September 2026. Machine used for every timing below: the
operator's Mac laptop (Apple M4, 10 cores, macOS 15, Python 3.13). Everything
marked **measured** was run on this machine today; everything marked
**quoted** is a number the vendor or author publishes; **UNVERIFIED** means I
could not confirm it by visiting the source.

The engine survey (OpenSpiel, RLCard, PyPokerEngine, PokerKit, clubs, PokerRL)
lives in `ENGINE_ALTERNATIVES.md`; this file does not repeat it.

## Summary for a non-programmer

A **solver** is a program that, given a poker situation (who has what range of
possible hands, the board, the stacks, the allowed bet sizes), computes a
strategy that cannot be beaten in the long run. That unbeatable strategy is
called the **equilibrium** or "GTO" strategy. An **equity calculator** is a
much simpler tool that only answers "how often does this hand win against
those hands" and does it millions of times a second. A **hand evaluator** is
simpler still: it ranks a finished 7-card hand.

Four more words are used throughout and are worth fixing here, before they
appear:

- How far a strategy still is from unbeatable, measured in chips an opponent
  who knew it perfectly could win from it. Smaller is better, and solvers stop
  when it is small enough. The word for it is **exploitability**.
- Pinning one player's play at a chosen point in the hand ("here, this player
  always calls") and re-solving everything else against that assumption. It is
  how a read on a person becomes a strategy aimed at that person. The word is
  **node locking** (written "nodelocking" by some vendors).
- Working out a number by playing the situation out at random thousands of
  times and averaging, instead of counting every possibility exactly. The name
  is **Monte-Carlo**.
- A sharing licence that lets anyone use and change the code but requires
  those changes to be published if the program is offered to others over a
  network. It costs a private bot that is never distributed nothing. The name
  is **AGPL**, the Affero General Public Licence.

Four findings drive the recommendation:

1. **Multiway postflop solvers for a Mac exist; none is scriptable or fast
   enough for decision time.** Two products solve any street with any number
   of players on macOS: **MonkerSolver** (EUR 499 one-time, native macOS,
   "any street with any number of players" per its own vendor page) and
   **Holdem Solver** (free beta, macOS Apple Silicon, 2 to 9 players). Both
   are driven by hand, take RAM and hours on multiway postflop trees, and
   neither documents an API or a scripting interface; MonkerSolver's own
   community drives it with keyboard macros, which is the clearest possible
   sign there is no programmatic route in. The rest are narrower: 3-way
   postflop in the browser (GTO Wizard, price UNVERIFIED, no API) or on
   Windows (Simple 3-way), and preflop-only multiway (Simple Preflop Holdem,
   HRC, GTOpen's Preflop Lab, GTO Wizard's multiway preflop).
2. **Heads-up postflop solving in under a second on this laptop is solved
   and free.** TexasSolver (C++, ships a macOS binary, text-command driven)
   solved a turn-and-river spot with full 6-max ranges to 0.74%
   exploitability in 0.7 s of solver time (8 s wall including tree build
   and writing the answer to JSON). postflop-solver (Rust library, AGPL)
   solved a comparable turn spot to 0.46% of the pot in 0.44 to 0.89 s wall
   across runs. Both measured on this Mac today. A full three-street flop tree
   with two bet sizes per street is a different animal: stopped at seven
   minutes, TexasSolver had completed four iterations of it and was still
   222% of the pot away from the accuracy asked for. So decision-time use
   means small trees (one bet size per street, or turn and river only), never
   full flop solves.
3. **Equity and hand ranking are a non-problem, in C++.** OMPEval computed
   3-way equity at 160 to 312 million hands per second on this Mac (the low
   end measured by a second run while the machine was busy), and it is
   **hard-capped at 6 players** (`omp/Constants.h:6`). phevaluator ranks 0.9
   to 2.6 million 7-card hands per second from Python, same caveat about
   load. A bot asking "how good is my hand against what they probably hold"
   gets a usable Monte-Carlo answer in a millisecond **through OMPEval**; the
   same loop written in plain Python on phevaluator needs of the order of ten
   thousand play-outs and is therefore a tens-of-milliseconds job, not a
   sub-millisecond one.
4. **Only one open-source project explicitly does what the operator wants,
   opponent-specific exploitation across 2 to 9 seats, and it is preflop-only
   for multiway**: GTOpen (Rust, active this week, no licence file). It
   compiled on this Mac in 1 min 53 s to 3 min 20 s across two builds, and its
   HTTP server answered on `127.0.0.1:3737` with a CPU-only solver, so
   "Windows/Linux only" in its README is just missing documentation. Both
   Rust projects in this file need a toolchain installed first; this machine
   ships with none. Its author's own experiments report
   40 to 80 big blinds per 100 hands gained by exploiting a correctly
   identified player type, and 194 to 287 bb/100 lost by misidentifying one.
   That is both the promise and the warning.

What this survey can settle on its own is which of these tools work, on this
machine, at what speed. What it cannot settle on its own is the architecture,
for two reasons stated plainly here and again in the recommendation:

- The obvious way to cover multiway postflop with the tools listed here is
  **an equity-driven rule set biased by the opponent model**. No engine in
  this survey contains such rules; they would be code we write, and code that
  picks the action. `CLAUDE.md:13-15` forbids exactly that without a recorded
  carve-out in the project rules. So it is a rule decision, not a tooling
  decision, and this file does not take it.
- `ENGINE_ALTERNATIVES.md` (under review, not accepted) proposes a different
  answer to the same multiway hole: keep no solver at all for those spots and
  **compute the decision during the hand** by playing the rest of the hand out
  at random inside OpenSpiel's `universal_poker`, measured there at a
  6-player 52-card no-limit decision inside a 250 ms budget. That option needs
  the same carve-out, and it competes with everything recommended below.

Both belong to the reconciliation of the four research sweeps
(`ENGINE_ALTERNATIVES.md`, `RESOURCES_BOTS.md`, `RESOURCES_EXPLOITATION.md`
and this file) against `CLAUDE.md`, which is where the architecture and the
carve-out get decided together. Details and the ranked list are below.

## Rating key

Each resource is scored on five criteria, 0 to 3 (3 is best):

- **(a) 2 to 9 players** — does it produce decisions for 3+ player spots?
- **(b) true no-limit sizing** — arbitrary bet sizes, not fixed-limit?
- **(c) exploit specific opponents** — can it be biased by an opponent model
  (nodelocking, profiles, player types) or does it only give equilibrium?
- **(d) reachable in hours on one laptop** — no multi-day compute, runs on
  macOS or callable from a Mac.
- **(e) fits private use** — licence or price acceptable for a private,
  never-distributed bot. (AGPL and GPL are fine here; a terms-of-service
  clause banning automated play is not.)

---

## Part 1. Open-source real-time solvers

### 1. TexasSolver (bupticybee)

- URL: https://github.com/bupticybee/TexasSolver
- What: a C++ CFR solver for hold'em and short-deck postflop spots, with a
  GUI and a **console binary driven by a text command file**.
- Last activity: last commit 26 Aug 2026; last binary release v0.2.0 on
  4 Nov 2021 (macOS zip included; 2.3k+ stars).
- Licence: AGPL-3.0 (commercial licence available).
- Price: free.
- macOS / Python: **verified**. I downloaded the v0.2.0 macOS release, ran
  `./console_solver -i <commands.txt>` directly, and it wrote a JSON
  strategy tree that Python can read. Commands are `set_pot`,
  `set_effective_stack`, `set_board`, `set_range_ip/oop`, `set_bet_sizes
  <who>,<street>,<bet|raise|donk|allin>,<pct...>`, `build_tree`,
  `set_accuracy`, `start_solve`, `dump_result`. A Python `TreeBuilder.py`
  ships in `resources/python`.
- Produces a decision for an arbitrary spot? **Heads-up only** (one IP, one
  OOP range). Any street, any board, any bet sizes you list, flop through
  river.
- Speed, **measured on this Mac** (10 threads):
  - **Turn-and-river solve, full ranges** (BTN 93 combos vs SB 95 combos
    from the bundled 6-max ranges, board Qs8d7h2c, pot 13, stack 93, one
    66% bet and 60% raise per street, all-in): **0.74% exploitability at
    iteration 51 in 0.71 s solver time; 8 s wall** including tree build and
    a 360 KB JSON strategy dump.
  - The bundled 3-street sample (2-hand vs 2-hand ranges): 0.44%
    exploitability at iteration 71 in 10.5 s solver time, 16.4 s wall.
  - **Full flop tree, same full ranges, three streets, 33%/75% bets, 60%
    raises, all-ins: re-measured today under a hard 7-minute stop.** Command
    file and runner published at
    `research/solvers/texassolver_flop_full_ranges.txt` and
    `research/solvers/run_texassolver_flop.py`, so this number can be checked
    rather than believed. 10 threads, nothing else heavy running:
    **423.1 s wall, 699.8 s CPU (1.65 cores busy on average), 5.79 GiB peak
    memory, iterations 0 to 3 completed, exploitability still 222% of pot
    when it was stopped** — against the 1% the command file asks for. It is
    the tree shape study tools use; it is not a decision-time solve on a
    laptop, and the gap is three orders of magnitude, not a near miss.
    An earlier draft of this file said the same run "had printed only
    iteration 0" after 35 minutes for 21 CPU-min. **That did not reproduce
    and is withdrawn**: the print interval was set to 20, so iterations 1 to
    19 were being completed silently, and the 0.6-cores-busy figure it
    implied is not what this machine does either. The conclusion survives the
    correction; the number did not.
  - Why so few cores are busy is itself the answer to "could a bigger machine
    fix it": at 5.8 GiB peak on a 16 GiB laptop the solve is waiting on
    memory, not on arithmetic, so the fix would be RAM and a smaller tree
    rather than threads.
  - **Quoted**: 172 s vs PioSOLVER's 242 s on the same flop tree
    (author's benchmark, SPR 10, a smaller tree than mine).
- Limits: heads-up only; the GPU successor (TexasSolverGPU) is Windows-only,
  NVIDIA-only and closed source, so it is irrelevant on a Mac.
- Ratings: (a) 0 — (b) 3 — (c) 1 (you can hand it a biased range for the
  opponent, but you cannot lock the opponent's actions) — (d) 3 — (e) 3.

Practical note: at decision time keep the tree small (one bet size per
street, start from the current street), which is exactly what the author's
`riversolver.sh` helper does. That is the shape that solved in under a
second above.

### 2. postflop-solver / Desktop Postflop / WASM Postflop (b-inary)

- URLs: https://github.com/b-inary/postflop-solver (library),
  https://github.com/b-inary/desktop-postflop (app),
  https://wasm-postflop.pages.dev/ (browser app)
- What: a Rust library implementing Discounted CFR for hold'em postflop
  spots, with a desktop app and a browser app built on it.
- Last activity: 1 Oct 2023; the author states development is suspended
  because they moved to building a commercial solver. 349 stars on the app.
- Licence: AGPL-3.0.
- Price: free.
- macOS / Python: Rust library; **verified to compile and run on this Mac**,
  and re-verified today, once two things are pinned: the compiler at
  **`rustc 1.85.0 (4d91de4e4 2025-02-17)`** (the 2026 compiler, 1.98.1, breaks
  it) and `bincode` and `bincode_derive` at exactly `2.0.0-rc.3` in
  `Cargo.toml` (the 2.0 release changed the trait). **A toolchain has to be
  installed first: this Mac has no `cargo`, `rustc`, `rustup` or Homebrew on
  the command path**, and every Rust timing in this file was produced with a
  private toolchain installed under a scratch directory
  (`RUSTUP_HOME`/`CARGO_HOME` pointed at it) rather than into the operator's
  home. Anyone re-running these numbers must do that first; nothing here works
  out of the box. Exact commands in Appendix B. Build: `cargo +1.85.0 build
  --release --example basic`, **19.1 s** with dependencies already fetched.
  Desktop app has an Apple-silicon build on the releases page (unsigned). No
  Python binding; you would wrap it with PyO3 or call a small Rust binary from
  Python.
- Produces a decision for an arbitrary spot? **Heads-up postflop only**
  (the README's "up to six players" refers to *bunching*: it accounts for
  cards removed by up to four folded players, it does not solve 3-way play).
  Arbitrary bet sizes, all-ins, donk bets, merging thresholds.
- Speed, **measured on this Mac**: the bundled `examples/basic` (two full
  ranges of roughly 40% each, board Td9d6h Qc, turn and river, pot 200,
  stack 900, bet sizes 60% / geometric / all-in, raises 2.5x, river donk
  50%, target 0.5% of pot) reached **0.46% of the pot at iteration 100
  (0.91 chips in a pot of 200) in 0.44 to 0.89 s wall** across four runs
  today and earlier (2.7 s CPU across threads), using 10 MB of memory. The
  spread between repeats is the machine, not the solver; either end is well
  inside a decision window.
  **Quoted**: author says it "surpasses PioSOLVER and GTO+"; the WASM
  version solved a full flop tree to 0.1% exploitability in 45.5 s with 16
  threads, and the native version is about 2x faster.
- Limits: heads-up; suspended project; Rust, not Python.
- Ratings: (a) 0 — (b) 3 — (c) 2 (has **node locking** in the library:
  `examples/node_locking.rs` lets you fix the opponent's strategy at chosen
  nodes and re-solve, which is how you turn an opponent read into an
  exploitative strategy) — (d) 3 — (e) 3.

### 3. GTOpen (MatthewPDingle)

- URL: https://github.com/MatthewPDingle/GTOpen
- What: an open-source Rust solver with a local web UI and HTTP API:
  heads-up postflop CFR (CPU or CUDA), a **2 to 9 player Preflop Lab** with
  limps and any sizings, and **player profiling with maximum-exploitation
  solves**.
- Last activity: created 13 Jun 2026; pushed **15 Sep 2026** (today);
  14 stars, one author.
- Licence: **none** (no LICENSE file in the repo). Legally that means all
  rights reserved; for a private, never-distributed bot this is a practical
  non-issue but it is not open source in the formal sense.
- Price: free.
- macOS / Python: Rust workspace (`crates/solver`, `crates/server`). README
  documents Windows, Linux and WSL only, but **it builds and runs on this
  Mac** — with the same caveat as entry 2: a Rust toolchain has to be
  installed first, and this machine has none on the command path. Re-built
  today from a clean target directory with the stable toolchain
  **`rustc 1.98.1 (48a229cea 2026-09-01)`**: `cargo build --release -p server`
  finished in **1 min 53 s** (261 s CPU, 2.4 cores busy), against 3 min 20 s
  on the first build; take the range, and note dependencies were already
  fetched both times. CPU-only, no CUDA. `./target/release/gto-server` started,
  chose 5 solver threads
  and answered `GET /api/status` with JSON. Driven over HTTP from any
  language: `POST /api/spot`, `/api/solve`, `/api/node {path}`,
  `/api/exploit {path, exploiter}`, `/api/lock`,
  `/api/preflop/spot|solve|node|export`. Caution: the API's spot JSON is
  flat (tree fields at top level, bet sizes as strings) and differs from the
  `bench_spot.json` used by its `solve-cli`; the docs do not spell this out.
- Produces a decision for an arbitrary spot? Preflop: yes, 2 to 9 players,
  custom open/3-bet/4-bet multiples per position, optional player models per
  seat. Postflop: **heads-up only**.
- Speed, **quoted** (author's `bench/` logs): the bundled `bench_spot.json`
  (Ks7h2d, two ~35% ranges, three streets, 33/75% bets, 60% raises, stack
  970 on pot 60) reached 1.125% of pot exploitability at 100 iterations in
  60.8 s on a 12-thread CPU; on an RTX 3090 GPU 1.35M-node flop trees run
  31 to 52 ms per iteration. Preflop lab uses Monte-Carlo equity samples
  (20,000 per hand class pair by default). **Measured on this Mac**: the
  same `solve-cli bench_spot.json 100 0.05` run reached **1.233% of pot at
  iteration 100 in 110 to 179 s** — two runs, identical exploitability to
  four decimal places, wall time 63% apart, which is as clean a demonstration
  as this file contains that a laptop timing is a range and not a number.
  1,346,813-node tree built in 0.06 s, 257 vs 319 hands, 1.4 GB of arenas;
  see Appendix A.
- Opponent modelling: player types defined by VPIP/PFR bands (Nit, TAG, LAG,
  Whale, Maniac, station/folder modifiers) with datasets from Ignition and
  CoinPoker at NL10 to NL100; hero solves a max-exploit against every other
  seat playing the measured profile. Author's reported results: +40 to +80
  bb/100 when the type is right, -194 to -287 bb/100 when wrong.
- Limits: single-author, brand new, no licence, no Mac instructions,
  multiway is preflop only.
- Ratings: (a) 2 (preflop 2-9, postflop 2) — (b) 3 — (c) 3 — (d) 3
  (builds and serves on this Mac) — (e) 2 (no licence).

### 4. slumbot2019 (Eric Jackson)

- URL: https://github.com/ericgjackson/slumbot2019
- What: the C++ CFR toolkit behind Slumbot, with CFR+, MCCFR, card and
  betting abstractions, endgame re-solving and head-to-head evaluation.
- Last activity: 18 Sep 2023; 177 stars. MIT licence. Free.
- macOS / Python: C++17, gcc 7.3+; no Python. Builds on a Mac in principle;
  not tested here.
- Multiway: "multiplayer is only supported by MCCFR and not by CFR+". This is
  the same family of approach as the vendored `poker_ai`, so the same
  multi-day blueprint cost applies for a full 52-card game.
- Speed: not published; designed for offline blueprint solving.
- Ratings: (a) 2 — (b) 3 — (c) 0 — (d) 0 (offline blueprint) — (e) 3.

### 5. DecisionHoldem (AI-Decision)

- URL: https://github.com/AI-Decision/DecisionHoldem
- What: a heads-up no-limit bot (blueprint CFR plus real-time search) that
  beat Slumbot by about 730 mbb/hand; weights downloadable from Baidu Netdisk.
- Last activity: 29 May 2024; 100 stars. AGPL-3.0. Free.
- Requirements: C++11, blueprint trained 3 to 4 days on a 48-core, 512 GB
  workstation. Heads-up only.
- Ratings: (a) 0 — (b) 3 — (c) 0 — (d) 1 (download the blueprint, do not
  retrain) — (e) 3.

### 6. amaster97/poker_solver

- URL: https://github.com/amaster97/poker_solver
- What: a heads-up no-limit hold'em solver in two tiers — a readable Python
  reference implementation that acts as the specification, and a Rust core
  (`crates/cfr_core`, exposed to Python as `poker_solver._rust` through PyO3
  and maturin) that does the solving. Tabular Discounted CFR with the
  published Brown-Sandholm 2019 constants, checked tier against tier by
  differential tests. Ships a local browser GUI (NiceGUI), a CLI, a
  Pio-style range parser, exact and Monte-Carlo equity, a precomputed
  preflop blueprint, and a node-lock editor in the tree browser.
- Last activity: created 20 May 2026, pushed 18 Jun 2026; 4 stars, one author.
- Licence: MIT. Price: free.
- macOS / Python: README names macOS Apple Silicon as the primary platform,
  Python 3.9+, `pip install -e .`, and a stable Rust toolchain to build the
  extension. **Not built or run here** — UNVERIFIED on this machine.
- Produces a decision for an arbitrary spot? **Heads-up only.** Bet sizes are
  per-street pot-fraction menus with an always-available all-in and a
  per-street raise cap.
- Speed: none published as a number. Its own README states the honest limit:
  river and turn subgames and shallow-to-medium flop spots are practical
  interactively, while "deep-stack (e.g. 100BB) full-range flop solves are
  compute-intensive — expect minutes, not instant results". That matches what
  was measured here for TexasSolver and GTOpen.
- Ratings: (a) 0 — (b) 3 — (c) 2 (node-lock editor documented; not exercised
  here) — (d) 2 (Python-callable by design, but a Rust build and no timings of
  its own) — (e) 3.

### 7. ArtemIyX/TexasSolverLib

- URL: https://github.com/ArtemIyX/TexasSolverLib
- What: despite the name, **not** a port of bupticybee's TexasSolver (entry 1).
  Its README says it is a C++17 port of the Rust implementation in
  `amaster97/poker_solver` above, repackaged as an installable CMake library
  (target `TexasSolver::texas`). Contains Kuhn and Leduc solvers, hold'em game
  state, heads-up preflop and postflop solving, exploitability and game-value
  evaluation, abstraction, suit-isomorphism and SIMD helpers, and vendors
  `pokerHandEvaluator` (entry 11's C++ core) as a submodule.
- Last activity: created 26 Jun 2026, pushed 1 Sep 2026; 1 star, one author.
- Licence: MIT. Price: free.
- macOS / Python: CMake 3.20+ and any C++17 compiler; the README names Visual
  Studio on Windows and "a normal CMake generator" elsewhere, with no macOS
  instructions and no Python binding. **Not built here** — UNVERIFIED on this
  machine.
- Produces a decision for an arbitrary spot? **Heads-up only**, inheriting the
  capability of the project it ports.
- Speed: none published; not measured here.
- Ratings: (a) 0 — (b) 3 (per-street sizing menus, inherited) — (c) 1 (nothing
  about node locking in the library's own documentation) — (d) 1 (a C++
  library with no macOS notes, no binding and no timings: an integration job
  of unmeasured size) — (e) 3.

### 8. masterai-top/cfr-poker-ai-masterai

- URL: https://github.com/masterai-top/cfr-poker-ai-masterai
- What: a heads-up no-limit research system, not a solver you call: C++ CFR
  and game-tree code under `csrc/`, counterfactual-value modules, self-play
  and supervised-strategy training in Python, opponent bots, and service
  plumbing (Protobuf, Redis, inter-process communication). Documentation is
  Chinese with English and traditional-Chinese translations.
- Last activity: created 22 Sep 2021, pushed 14 Sep 2026; 49 stars.
- Licence: **ambiguous, and that is a real defect.** GitHub reports "Other";
  the repository's `LICENSE` file is two bytes long, effectively empty, while
  a second file `License.md` holds MIT text. Its own README tells the reader
  to "confirm the applicable license terms with the maintainer".
- macOS / Python: building it needs a C++ toolchain, CMake, PyTorch and Redis;
  the README's own recommended sequence starts by creating an isolated
  **Linux** test environment. **Not built here** — UNVERIFIED on this machine.
- Produces a decision for an arbitrary spot? No: it is a training system for
  heads-up play, and no trained weights ship with it beyond two small regret
  files at the repository root.
- Speed and strength: the README carries a win-rate table (85% against a
  random bot, 72% against a rule-based AI, 58% against a CFR baseline) and
  then disowns it in the same section as project-reported figures that were
  not independently reproduced and that lack hand counts, stakes, hardware and
  confidence intervals. Treat as UNVERIFIED and unusable as evidence.
- Ratings: (a) 0 — (b) 1 (abstraction-based; sizing scheme not stated) —
  (c) 0 — (d) 0 (a multi-day training system on Linux, no weights) — (e) 1
  (licence ambiguous).

### 9. Small or early-stage open solvers (for completeness)

- **frla18cz/poker-solver** (https://github.com/frla18cz/poker-solver): pure
  Python, MIT, pushed 24 Aug 2026, 0 stars. Monte-Carlo equity vs weighted
  ranges, 825 precomputed preflop spots, all-in-or-fold CFR and a "multiway
  postflop CFR" that abstracts to one bet size and one re-raise per street.
  Needs Python 3.14. Ratings: (a) 2 — (b) 1 — (c) 0 — (d) 3 — (e) 3.
- **Spin_and_Go_Solver** (https://github.com/jamdickin11/Spin_and_Go_Solver):
  C++ MCCFR for 3-player 15bb spin-and-gos with k-means card abstraction; MIT;
  pushed 27 Aug 2025; 0 stars. 3-player only, blueprint style.
  Ratings: (a) 1 — (b) 2 — (c) 0 — (d) 1 — (e) 3.
- **noambrown/poker_solver** (https://github.com/noambrown/poker_solver):
  river-only subgame solver, Python reference plus C++, MIT, 2 commits. Useful
  as a reference implementation of CFR/DCFR, not as a product.

---

## Part 2. Hand evaluators and equity calculators

### 10. OMPEval (zekyll)

- URL: https://github.com/zekyll/OMPEval
- What: C++ 7-card evaluator plus a range-vs-range equity calculator (Monte
  Carlo or exact enumeration) for **up to 6 players, and 6 is a hard cap in
  the source**: `omp/Constants.h:6` reads `static const unsigned MAX_PLAYERS
  = 6`, and `omp/EquityCalculator.cpp:17` rejects any call with more ranges
  than that. It is not a build flag — the number sizes fixed arrays and a
  `1 << MAX_PLAYERS` win-mask table throughout, so raising it means editing
  and re-testing the library. A 7, 8 or 9-handed pot therefore cannot be
  evaluated in one call; it has to be reduced to at most six live ranges
  first, and who gets dropped is a judgment the bot would be making.
- Last activity: 21 Aug 2016 (finished, not abandoned; it still builds).
- Licence: ISC. Free.
- macOS: **verified**. Needs one two-line patch (`min()`/`max()` in
  `omp/Random.h` must be `constexpr` for current clang) and `-std=c++17`.
- Python: third-party pybind11 wrapper
  https://github.com/Tylder/OMPEval_py_wrapper (4 stars, Jan 2023, exposes
  `CardRange`, `EquityCalculator`), and a Rust port with Python bindings
  `pyrust-poker` on PyPI (MIT, Dec 2024, up to 6 ranges) whose source tarball
  is missing a submodule and would not build here; a Linux-only wheel is
  published. Expect to compile a wrapper yourself.
- Speed, **measured on this Mac**:
  - 7-card evaluation: **61.5 million hands/s** single-thread (including
    building the hand from seven card indices).
  - 3-way Monte-Carlo equity on a flop, 10 threads: **160 to 312 million
    hands/s**. The high figure is the first run (623 million samples in 2 s);
    an independent re-run on the same machine while it was doing other work
    got 160 to 177 million. Read the range, not either end: wall-clock speed
    on a laptop moves by a factor of two with what else is running, and the
    conclusion (equity is free at this scale) survives either number.
  - Heads-up exact enumeration of two real ranges on a flop: **2.8 ms**
    (2.97 million matchups).
- Ratings: (a) 2 (3 to 6 players, never 7 to 9) — (b) n/a — (c) n/a (an input
  to your own logic) — (d) 3 — (e) 3.

### 11. PokerHandEvaluator / phevaluator (HenryRLee)

- URL: https://github.com/HenryRLee/PokerHandEvaluator
- What: perfect-hash 5/6/7-card (and Omaha) evaluator in C/C++ with an
  official Python package `phevaluator`.
- Last activity: pushed 14 Sep 2026; 516 stars. Apache-2.0. Free.
- macOS / Python: **verified**; plain `pip install phevaluator` works and
  installs the 0.6.0 arm64 wheel on Python 3.13 with no flags and no manual
  download. (An earlier draft of this file said pip needed the wheel fetched
  by hand because of a resolver hiccup. Re-tested in a clean virtual
  environment: it does not. The claim was wrong and is withdrawn.)
- Speed, **measured**: **0.9 to 2.6 million 7-card hands/s** from Python when
  cards are ints — 2.55 M/s on an idle machine, 0.89 to 1.44 M/s on an
  independent re-run under load — and 0.80 M/s when cards are strings like
  "Ah". Quote the range, not the peak, when sizing a Monte-Carlo loop.
  **Quoted** C: 56 M/s.
- No equity calculator; pair it with your own Monte Carlo loop or OMPEval.
- Ratings: (a) n/a — (b) n/a — (c) n/a — (d) 3 — (e) 3.

### 12. treys (already the project's ground-truth evaluator)

- URL: https://github.com/ihendley/treys — MIT, pure Python, last push
  15 Jul 2023, 179 stars.
- Speed, **measured**: **165,000 7-card hands/s**. Five to fifteen times
  slower than phevaluator and 370 times slower than OMPEval; fine for tests,
  too slow for Monte-Carlo equity at decision time.

### 13. pokerstove (andrewprock)

- URL: https://github.com/andrewprock/pokerstove
- What: the open-sourced core of the classic PokerStove equity tool: C++
  `peval` library for 14 variants, `ps-eval` CLI, SWIG Python bindings.
- Last activity: 14 Dec 2024; 886 stars. BSD-3-Clause. Free.
- macOS: listed (XCode); needs Boost and CMake. Not built here.
- Speed: not published in the README; historically comparable to poker-eval,
  well below OMPEval.
- Ratings: (d) 2 (build effort) — (e) 3.

### 14. poker-eval / pypoker-eval (PokerSource)

- URL: https://pokersource.sourceforge.net/ , https://github.com/ChazDazzle/pypoker-eval
- What: the old GPL C evaluator with Python bindings; many variants.
- Last activity: essentially dormant (forks only). GPL. Free.
- Verdict: superseded by OMPEval and phevaluator; listed only so nobody
  re-discovers it.

### 15. eval7 (julianandrews/pyeval7)

- URL: https://github.com/julianandrews/pyeval7 — Cython evaluator with
  PokerStove-style range parsing and hand-vs-range equity.
- **Would not build on Python 3.13 on this Mac** (wheel build failed).
  Skip unless the project pins an older Python.

---

## Part 3. Commercial multiway-capable solvers

### 16. MonkerSolver (MonkerWare)

- URL: https://monkerware.com/solver.html
- What: the original multiway solver: "Solve Omaha and Hold'em from any
  street with any number of players", with abstraction to keep trees small.
- Price: **EUR 499 one-time**; free version limited to turn and river.
  Price, platform and the multiway claim were re-read off the vendor page
  itself today: "€499", "Solve Omaha and Hold'em from any street with any
  number of players", "Windows 64-bit or Mac OS X with atleast 8 GB RAM".
- Platform: native Windows 64-bit or macOS, 8 GB RAM minimum. No scripting
  or API documented; the community drives it with AutoHotkey macros, which
  is a sign there is no programmatic interface. Solutions export as .mkr and
  .txt range files.
- Multiway: yes, preflop **and postflop, on any street**, which is what the
  vendor page claims in as many words. It is emphatically **not** a
  preflop-only tool, and an earlier draft of this file said so in its summary;
  that was wrong and is corrected above. The real limits are different ones:
  multiway postflop trees need a lot of RAM and hours of solving, so it is a
  study tool, not a decision-time engine, and there is no way to drive it from
  a program.
- Ratings: (a) 3 (any street, any number of players) — (b) 3 — (c) 1 (no node
  locking documented) — (d) 1 (macOS yes, but by hand and in hours) — (e) 3.

### 17. GTO Wizard (includes the former Ruse AI as "GTO Wizard AI")

- URL: https://gtowizard.com/
- What: a browser library of pre-solved spots plus an on-demand AI solver.
  **Multiway preflop up to 9 players** (launched 3 Feb 2026, custom antes,
  straddles, rake, "in seconds"); **3-way postflop** custom solves and, since
  Aug 2026, 3-way ICM postflop; 4-way and beyond "in development".
- Price: **UNVERIFIED — quoted from the press, not from the vendor.** The
  figures previously carried here (Starter $49/mo, Premium $99/mo, Elite
  $169/mo, Ultra $279/mo, $229/mo annual, $359/$289 after early-bird) come
  from a PokerNews article dated 31 March 2026, not from GTO Wizard. The
  vendor's own pricing page was fetched again today and returns a 518-byte
  page that builds its prices in the browser, so no price could be read from
  the source. Treat every number in this line as a press report that may be
  stale, and confirm on the site before any money is spent. What is safe to
  say without the numbers: the multiway and custom-solve features sit in the
  top tier and this is a monthly subscription, not a purchase.
- Opponent modelling: **Profiles** (action incentives such as "+4% pot to
  call") and **Nodelocking 2.0**; both produce an exploitative counter
  strategy. That is the most polished opponent-biasing available anywhere.
- API: **none** for strategy lookup. There is a separate free
  "Researcher API" (https://github.com/gtowizard-ai/researcher-api-client,
  application required) that only lets your bot *play hands against* GTO
  Wizard AI for benchmarking; it does not return strategies. Ranges export
  as UPI text by hand, no bulk download.
- Ratings: (a) 2 (9 preflop, 3 postflop) — (b) 3 — (c) 3 — (d) 1 (browser
  only, cannot be called from a script) — (e) 1 (expensive, and not
  automatable).

### 18. Simple Postflop / Simple 3-way / Simple Preflop Holdem (Simple Poker)

- URLs: https://simplepoker.com/en/Solutions/Simple_3-way ,
  https://shop.gipsyteam.com/simple-preflop-holdem
- What: a family of Windows solvers. Simple 3-way solves **3-player
  postflop**; Simple Preflop Holdem solves **2 to 10 player preflop** with
  postflop abstraction, ICM and rake.
- Price: Simple 3-way $249/year; Simple Preflop Holdem $250/year; Simple
  Postflop $299 standalone.
- Platform: **Windows only**, 16 GB RAM. No API or scripting documented.
- Ratings: (a) 2 — (b) 3 — (c) 1 — (d) 0 on a Mac — (e) 2.

### 19. PioSOLVER, GTO+, Jesolver (heads-up scriptable solvers, Windows)

- PioSOLVER (https://piosolver.com/): Pro $249, Edge $475 one-time; Windows
  only (Mac users run Parallels). **UPI** text protocol lets a script drive
  it (https://piosolver.com/docs/upi/); nodelocking supported. Heads-up
  postflop; Edge adds a heads-up-style preflop solver.
- GTO+ (https://gtoplus.com/): $75 to $375 one-time, Windows, heads-up,
  scripting for batch databases.
- Jesolver (https://jesolver.com/cmdref.html): $200, a UPI-compatible engine
  that replaces Pio's, several times faster and lower memory; Windows.
- Ratings for all three: (a) 0 — (b) 3 — (c) 2 (nodelocking) — (d) 1
  (Windows VM on a Mac) — (e) 2. TexasSolver and postflop-solver give the
  same capability free and natively on macOS, so none of these are worth
  buying for this project.

### 20. Holdem Solver (holdemsolver.com) — new, free beta

- URL: https://holdemsolver.com/
- What: a desktop solver for **2 to 9 players on any street**, chip-EV or
  ICM/PKO, "no sampling and no card abstraction" heads-up, sampled MCCFR
  multiway, running on your own hardware with results stored locally.
- Price: **free during open beta (v0.79), pricing TBA**.
- Platform: **Windows x64 and macOS Apple Silicon**.
- Speed, **quoted**: a 63-entry PKO multiway spot converged after 20 million
  iterations in 9 min 05 s (hardware unstated).
- API/scripting: none mentioned. Licence: unstated. Vendor and origin:
  UNVERIFIED beyond the site itself.
- Ratings: (a) 3 — (b) 3 — (c) 0 (nothing documented) — (d) 2 (runs on this
  Mac, but only by hand) — (e) 2 (free now, terms unknown).

### 21. HoldemResources Calculator (HRC)

- URL: https://www.holdemresources.net/ (pricing at /hrc/pricing)
- What: the standard tournament preflop/ICM solver, Java, Windows/macOS/Linux
  (macOS 64-bit; Apple-silicon support UNVERIFIED, forum posts from 2021 said
  x64 only). Pro tier adds postflop modelling and **scripted tree building in
  JavaScript** (Graal engine) with a Javadoc API.
- Price: Classic $9.99 to $16.66/mo; **Pro $29.99 to $49.99/mo**.
- Multiway: yes for preflop (Monte Carlo engine for 3+ active players).
- Ratings: (a) 3 (preflop) — (b) 2 — (c) 0 — (d) 2 — (e) 2.

### 22. Deepsolver (cloud, has a real HTTP API)

- URL: https://deepsolver.com/api
- What: GPU cloud solver with `POST /task/treebuilder`,
  `POST /task/cfr/schedule`, `GET /task/cfr/result/{id}`; JSON in, per-hand
  EV/strategy out (NumPy-friendly). Custom 1326-weight ranges, arbitrary bet
  grids, 2 to 20 s per solve.
- Price: consumer plans $10/$76/$209 per month (no API); **API plans start at
  $1,875/month plus a $2,000 setup fee**, or $0.025 per calculation on demand.
- Multiway: **not supported** ("multi-way is not supported").
- Ratings: (a) 0 — (b) 3 — (c) 1 — (d) 3 — (e) 0 (price).

### 23. Pokerai API (pokerai.bet)

- URLs: https://pokerai.bet/ , https://pokerai.bet/reference , /terms
- What: the only self-serve "what should I do here" HTTP API found.
  Pre-solved 6-max preflop and flop lookups (`/v1/gto/preflop`,
  `/v1/gto/flop/node`), queued real-time turn/river solves
  (`/v1/gto/solver`), custom OOP/IP ranges, 100bb and 40bb, Python and
  JavaScript SDKs, Bearer-token auth. Solver is "MelaSolver GPU"; the vendor
  quotes a flop solve in 27.75 s on an Apple M4.
- Price: free tier 1,000 lookups + 25 solves per month; Builder $29/mo;
  Pro $99/mo; Scale from $299/mo.
- Limits: **6-max NLHE only**; postflop is heads-up (OOP vs IP); and the
  terms say: "You must not use the Services, directly or indirectly, to
  advise or automate decisions during live real-money play." Fine for
  building and testing the bot, and for play-money or home games; not for a
  real-money bot.
- Ratings: (a) 1 (6-max preflop, HU postflop) — (b) 2 (their tree) —
  (c) 0 — (d) 3 — (e) 1 (terms).

### 24. Spinwize

- URL: https://www.spinwize.net/ — 3-handed Spin&Go database (all 1,755
  flops up to 36bb) with a "Solver API" to fetch from its 60 TB of solutions.
  EUR 53 to 89/month. 3-player only, short stacks only; API details behind the
  paywall (UNVERIFIED). Ratings: (a) 1 — (b) 2 — (c) 0 — (d) 3 — (e) 2.

### 25. Odin Poker, now "GTO Strategy"

- URL: https://gtostrategy.com/ — browser library built on the Odin solver:
  pre-solved cash and MTT spots for 4-max to 9-max, **multiway postflop
  solutions** in the Elite tier ($79/mo), live turn/river solving. No API or
  export. Ratings: (a) 3 — (b) 2 — (c) 0 — (d) 1 — (e) 2.

### 26. GTOBase

- URL: https://gtobase.com/ — browser viewer; 6-max cash 40 to 200bb, 8/9-max
  MTT 15 to 100bb, HU cash free. $75 to $150/month. No API, no export.
  Ratings: (a) 2 — (b) 2 — (c) 0 — (d) 1 — (e) 2.

---

## Part 4. Free or cheap precomputed preflop ranges, 2 to 9 handed

Preflop for 9 players is the one multiway problem that is genuinely solved
and cheap. Sources checked today:

| Source | Coverage | Format | Price |
| --- | --- | --- | --- |
| Preflop Wizard blog https://www.preflopwizard.app/blog/9-max-preflop-chart | 9-max and 6-max RFI and BB defence at 100bb, 2.5x open; updated Jul 2026 | web page / printable PDF | free |
| preflopranges.app https://preflopranges.app/ | "15,000+ charts": 9-max MTT 10 to 200bb, 6-max cash, 3-max spins, with per-hand frequencies; open beta, no account | web only, no export found | free |
| PokerCoaching https://pokercoaching.com/preflop-charts/ | 6-max and full-ring cash, MTT 15/75bb, push-fold; GTO **and exploitative** versions | PDF, email required | free |
| MonkerGuy https://www.monkerguy.com/ | 6-max and 9-max NLHE 20 to 200bb, 8-max MTT packs; MonkerSolver output | .mkr, MonkerViewer, **.txt ranges (Pio/PPT compatible)** | $69 (6-max 100bb) to $499 |
| GTO Sims https://gtosims.com/ | Spin&Go, 6-max, MTT from Simple Preflop Holdem | Simple Preflop files, Pio charts, PNG | per solution, price not shown |
| TexasSolver release bundle | 6-max 100bb ranges (BTN/CO/MP/SB/UTG opens, 3-bet, call trees) as plain text | text, already on this Mac | free |
| GTO Wizard | 9-max multiway preflop, custom antes/straddles | copy as UPI text by hand | top tier, monthly; price UNVERIFIED (see entry 17) |

A gumroad pack of 576 tournament ranges in .txt (mkosmis) came up in search
but the page returned 404: UNVERIFIED.

None of the free chart sites offer bulk download or an API; the practical
route is to buy a MonkerGuy text pack (or hand-copy the free 9-max charts
into the repo's own text format once) and never solve preflop ourselves.

---

## Part 5. Ranked shortlist (best first)

Ranked on one question: **how much working poker judgment does this put in the
bot's hands today, on this machine, for what effort?** Everything above slot 6
was run here; everything below it was read about.

1. **TexasSolver** — free, ships a macOS binary, text-command driven, nothing
   to build. Solved a full-range turn-and-river spot in 0.7 s of solving here
   (8 s wall including the JSON dump); the same binary needs more than seven
   minutes to get nowhere on a full flop tree, so the rule is "prune the tree
   and start from the current street". The obvious heads-up postflop engine to
   call at decision time, callable from Python by writing a command file.
2. **phevaluator** — plain `pip install phevaluator`, 0.9 to 2.6 M 7-card
   hands/s from Python, no build step and no cap on the number of players.
   Promoted above OMPEval because it is the only thing on this list that is
   working five seconds after the install finishes; it replaces `treys` on any
   runtime path (`treys` stays the test oracle).
3. **OMPEval** — 160 to 312 M hands/s of multiway Monte-Carlo equity, which is
   free speed compared with anything in Python, but **hard-capped at six
   players** (`omp/Constants.h:6`) and it needs a C++ patch and a wrapper you
   compile yourself. At 7 to 9 seats it cannot be handed every live range at
   once, which is exactly the table size this project is aiming at.
4. **postflop-solver** — 0.46% of pot on a turn spot in 0.44 to 0.89 s here,
   and the only free tool in this file with **node locking built in**, which
   is the mechanism that turns a read on a person into a strategy. Promoted
   above GTOpen because that mechanism is what stage 2 of the plan needs.
   Costs: a pinned Rust 1.85 toolchain (this Mac has none installed), a pinned
   dependency, a wrapper, and a project its author has suspended.
5. **GTOpen** — the only open project combining 2 to 9 player preflop with
   explicit player-type exploitation behind an HTTP API; builds and serves on
   this Mac (1 min 53 s to 3 min 20 s) once a toolchain exists. Two blockers,
   not one: **no licence file at all**, and its multiway is preflop only. Its
   player-type definitions are worth borrowing for `OPPONENT_MODEL_DESIGN.md`
   whatever else is decided.
6. **MonkerGuy .txt ranges** ($69 to $499 one-time) or the free 9-max charts
   — precomputed preflop for every table size, no solving needed.
7. **MonkerSolver** (EUR 499 one-time, macOS) — solves **any street with any
   number of players**, which nothing else here does natively on a Mac at a
   one-time price. Not on the decision path: no scripting interface, and
   multiway postflop trees take RAM and hours. Buy it only for offline study.
8. **Holdem Solver** (free beta, macOS, 2 to 9 players) — the other Mac tool
   that solves multiway postflop, and free while the beta lasts, but the
   vendor, licence and terms are all UNVERIFIED and there is no scripting.
   Offline study of specific multiway spots, not decision time.
9. **Pokerai API** — instant 6-max GTO answers over HTTP with a free tier;
   good for testing the bot's judgment against a reference, barred from live
   real-money use by its terms.
10. **GTO Wizard** top tier — best opponent modelling anywhere (Profiles,
    Nodelocking 2.0) and 9-player preflop, but a monthly subscription (price
    UNVERIFIED, see entry 17) with no API; a study tool only.
11. **HRC Pro** — tournament preflop/ICM with JavaScript tree scripting, if
    the bot ever plays tournaments.

The three 2026 heads-up projects added this round (**amaster97/poker_solver**,
**ArtemIyX/TexasSolverLib**, **masterai-top/cfr-poker-ai-masterai**) are not
shortlisted. All three are heads-up only, none was built here, and the first
two duplicate what TexasSolver and postflop-solver already do on this machine
today. Keep `amaster97/poker_solver` in view only: it is MIT, targets Apple
Silicon first, and is the only one of the three that is Python-callable by
design.

Not recommended: Deepsolver API (heads-up only, $1,875/month), PioSOLVER,
GTO+, Jesolver, Simple Poker (Windows, heads-up or no scripting),
slumbot2019 and DecisionHoldem (multi-day blueprints, heads-up).

## Recommendation: input to the reconciliation, not a decision

This is a tool survey. It can say which tools work and how fast; it cannot
choose the bot's architecture, because two of the three pieces below turn on a
rule question and on a competing proposal in another document. So what follows
is written as **input to the reconciliation of the four research sweeps
against `CLAUDE.md`**, with the settled parts marked as settled and the open
parts left open.

**Settled by measurement, and safe to adopt now.**

- **Heads-up postflop: TexasSolver**, called at decision time. Build a small
  command file from the live spot (board, pot, stacks, the opponent's
  estimated range, one or two bet sizes) and read the strategy back from its
  JSON. The measured 0.7 s full-range turn solve is what says a pruned tree
  fits inside a live decision; the measured flop solve (Appendix A) is what
  says the tree must be pruned. Nothing here is our own poker judgment: the
  strategy comes out of a borrowed solver.
- **Hand ranking and equity: phevaluator now, OMPEval when the loop is hot.**
  phevaluator replaces `treys` on any runtime path (`treys` stays the test
  oracle, as `CLAUDE.md` requires). OMPEval is the one to call for Monte-Carlo
  equity, with its 6-player cap recorded: at 7, 8 or 9 seats it cannot be
  handed every live range at once.
- **Preflop: buy or transcribe ranges** for 2 to 9 seats rather than solving
  preflop at all. This is the cheapest well-covered part of the problem.

**Open, and for the reconciliation to decide — not for this file.**

- **What plays multiway postflop.** The obvious fit with the tools above is an
  equity-driven rule set biased by the opponent model. Say plainly what that
  is: **code we would write that picks the action**, with the opponent model
  as its input. `CLAUDE.md:13-15` forbids hand-rolled decision logic in place
  of engine code, so it cannot be adopted on a survey's say-so; it needs a
  recorded carve-out in the project rules, and the reconciliation is where
  that is written or refused.
- **Whether a multiway decision-time option already exists.** An earlier draft
  of this file asserted that none does. That was true only of the solver
  market surveyed here, and it is the wrong place to look.
  `ENGINE_ALTERNATIVES.md` (under review, not accepted) reports a measured
  alternative: OpenSpiel's `universal_poker` playing the rest of the hand out
  at random during the hand, producing a 6-player 52-card no-limit decision
  inside a 250 ms budget on this same machine, with no solver and no training.
  Its own document is candid that the quality of that decision depends on the
  betting abstraction — about 13,000 play-outs per decision against a
  four-move menu, but only about 242 with full bet sizing, which it calls
  mostly noise — and that it needs the same rule carve-out as the rule set
  above, because the code that compares the play-outs is also code that picks
  the action. So the honest statement is: **a multiway decision-time option
  exists and is measured; what does not exist is an affordable, scriptable
  multiway postflop *solver* on a Mac.** Which of the two covers multiway is
  exactly what the reconciliation has to settle, and they are not alternatives
  within this document's authority.
- **GTOpen's player types.** Its promise (+40 to +80 bb/100 when the read is
  right) and its warning (-194 to -287 bb/100 when it is wrong) are the
  author's own numbers, not ours. Its definitions are worth borrowing for
  `OPPONENT_MODEL_DESIGN.md`; adopting its exploit solves is a licence
  question (it has no licence file) as well as a rule question.

The settled part costs nothing but an optional $69 range pack and uses only
AGPL, ISC and Apache code that private use permits.

---

## Appendix A. Measured timings on this Mac (Apple M4, 10 cores)

Wall-clock speed on a laptop moves by tens of percent, and sometimes by a
factor of two, with whatever else the machine is doing. Where a measurement
was repeated the range is given, and the range is the honest figure.

| Tool | Spot | Result | Time |
| --- | --- | --- | --- |
| TexasSolver 0.2.0 | turn+river, 93 vs 95 combos, one 66% bet, 60% raise, all-in | 0.74% exploitability, iter 51 | 0.71 s solve, 8 s wall |
| TexasSolver 0.2.0 | bundled 3-street sample, 2 vs 2 hands | 0.44%, iter 71 | 10.5 s solve, 16.4 s wall |
| TexasSolver 0.2.0 | flop+turn+river, same full ranges, 33/75% bets, 10 threads | iterations 0-3 only; 222% of pot, still falling | stopped at 423.1 s wall / 699.8 s CPU / 5.79 GiB |
| postflop-solver | turn+river, ~40% vs ~40% ranges, 60%/geo/all-in, 2.5x raises | 0.46% of pot (0.91 chips of 200), iter 100 | 0.44 to 0.89 s wall, 2.7 s CPU |
| GTOpen solve-cli | `bench_spot.json` flop, 3 streets, 1.35M nodes, CPU-only | 1.233% of pot, iter 100 | 110 to 179 s wall, 1.4 GB |
| GTOpen | `cargo build --release -p server`, clean target dir | binary | 1 min 53 s to 3 min 20 s |
| OMPEval | 3-way Monte-Carlo equity on a flop, 10 threads | 160 to 312 M hands/s | 2 s budget |
| OMPEval | heads-up exact enumeration, two real ranges, flop | 2.97 M matchups | 2.8 ms |
| OMPEval | 7-card evaluation, single thread | 61.5 M hands/s | |
| phevaluator 0.6.0 | 7-card evaluation from Python, int cards | 0.9 to 2.6 M hands/s | |
| treys 0.1.8 | 7-card evaluation from Python | 165 k hands/s | |

**The flop solve, in full**, because it is the number the recommendation leans
on hardest. Command file `research/solvers/texassolver_flop_full_ranges.txt`,
runner `research/solvers/run_texassolver_flop.py`, `set_thread_num 10`,
`set_accuracy 1.0` (that is, stop at 1% of pot), stopped by the runner at
420 s. Reached: **423.1 s wall, 699.8 s CPU — 1.65 cores busy out of 10 —
5.79 GiB peak memory, four iterations (0 to 3), exploitability 226.4% of pot
at iteration 0 and 221.7% at iteration 2.** A solve that needs 1% and is at
222% after seven minutes is not slow, it is not started. The low core count is
the memory ceiling, not idle threads: 5.79 GiB on a 16 GiB laptop.

GTOpen `solve-cli bench_spot.json 100 0.05` on this Mac, CPU-only: tree of
1,346,813 nodes built in 0.06 s, 257 vs 319 hands, 1,386 MB of solver arenas
(compressed), **1.233% of pot exploitability at 100 iterations in 110 s on
the first run and 179.1 s on the re-run** — bit-identical result, very
different clock (the author's 12-thread desktop did the same in 61 s). That is
a full three-street flop tree with two IP flop sizes: **two to three minutes
for a study-grade flop solve**, which confirms the pattern above. Full flop
trees are minutes at best and unreachable at worst; turn and river trees are
under a second.

## Appendix B. What I ran

```
# evaluators (clean venv, Python 3.13.15)
pip install phevaluator                  # plain install, 0.6.0 arm64 wheel, no flags
pip install treys                        # eval7 and pyrust-poker failed to build
python bench_treys.py                    # 165,275 hands/s
python bench_phe.py                      # 2,550,203 hands/s idle, 0.89-1.44 M/s under
                                         # load (ints); 800,485 (strings)

# OMPEval (clang 16, needs constexpr patch in omp/Random.h)
make CXXFLAGS="-O3 -std=c++17 -Wall -pthread"
./evbench   # 61.5 M evals/s
./eqbench   # 3-way MC 311.7 M hands/s idle, 160-177 M/s under load (10 threads);
            # HU exact flop 2.8 ms.  Player cap: omp/Constants.h:6 MAX_PLAYERS = 6

# TexasSolver v0.2.0 macOS release (unzipped from the GitHub release)
./console_solver -i resources/text/commandline_sample_input.txt   # 16.4 s wall
./console_solver -i turn_input.txt                                # 8 s wall
python3 research/solvers/run_texassolver_flop.py <release-dir> 420
    # 423.1 s wall, 699.8 s CPU, 5.79 GiB, iterations 0-3, 222% of pot

# Rust toolchain: NOT installed on this Mac.  No cargo, rustc, rustup or
# Homebrew is on the command path.  Both Rust projects below were built with a
# private toolchain unpacked into a scratch directory and reached only through
# these three variables, so nothing was written to the operator's home:
export RUSTUP_HOME=<scratch>/rustup CARGO_HOME=<scratch>/cargo
export PATH=<scratch>/cargo/bin:$PATH
rustup toolchain list    # stable (1.98.1) default, plus 1.75.0 and 1.85.0

# postflop-solver: rustc 1.85.0 (4d91de4e4 2025-02-17),
#                  bincode + bincode_derive pinned =2.0.0-rc.3 in Cargo.toml
cargo +1.85.0 build --release --example basic    # 19.1 s, dependencies cached
./target/release/examples/basic                  # 0.72-0.89 s wall, 2.7 s CPU,
                                                 # exploitability 0.91 of pot 200

# GTOpen: rustc 1.98.1 (48a229cea 2026-09-01), CPU-only
CARGO_TARGET_DIR=<scratch>/GTOpen/target_clean cargo build --release -p server
    # 1 min 53 s wall, 261 s CPU (first build, earlier: 3 min 20 s)
./target/release/gto-server & curl 127.0.0.1:3737/api/status   # {"state":"idle","gpu":false,...}
./target/release/solve-cli bench_spot.json 100 0.05
    # 1.233% of pot at iteration 100 in 179.1 s (earlier run: 110 s)
```
