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

Four findings drive the recommendation:

1. **Nobody sells a fast, scriptable, true multiway (3 to 9 player) postflop
   solver that runs on a Mac.** The only products that solve 3-way postflop
   are GTO Wizard (browser, $229 to $359 a month, 3-way only, no API) and
   Simple 3-way (Windows only, no scripting). Everything that goes to 9
   players is either preflop-only (MonkerSolver, Simple Preflop Holdem, HRC,
   GTOpen's Preflop Lab, GTO Wizard's multiway preflop) or a brand-new
   free beta with no scripting interface (Holdem Solver).
2. **Heads-up postflop solving in under a second on this laptop is solved
   and free.** TexasSolver (C++, ships a macOS binary, text-command driven)
   solved a turn-and-river spot with full 6-max ranges to 0.74%
   exploitability in 0.7 s of solver time (8 s wall including tree build
   and writing the answer to JSON). postflop-solver (Rust library, AGPL)
   solved a comparable turn spot to 0.46% in 0.44 s wall. Both measured on
   this Mac today. A full three-street flop tree with two bet sizes per
   street is a different animal: TexasSolver had not finished one
   iteration of it after 35 minutes, so decision-time use means small trees
   (one size per street, or turn/river only), not full flop solves.
3. **Equity and hand ranking are a non-problem.** OMPEval computed 3-way
   equity at 312 million hands per second on this Mac; phevaluator ranks 2.5
   million 7-card hands per second from plain Python. Any bot logic that needs
   "how good is my hand against what they probably hold" can have that answer
   in under a millisecond.
4. **Only one open-source project explicitly does what the operator wants,
   opponent-specific exploitation across 2 to 9 seats, and it is preflop-only
   for multiway**: GTOpen (Rust, active this week, no licence file). It
   compiled on this Mac in 3 min 20 s and its HTTP server answered on
   `127.0.0.1:3737` with a CPU-only solver, so "Windows/Linux only" in its
   README is just missing documentation. Its author's own experiments report
   40 to 80 big blinds per 100 hands gained by exploiting a correctly
   identified player type, and 194 to 287 bb/100 lost by misidentifying one.
   That is both the promise and the warning.

So the realistic architecture is: precomputed preflop strategy for 2 to 9
players (free charts or a one-time purchase), a fast heads-up postflop solver
called at decision time when the pot is heads-up (most pots are by the turn),
and an equity-driven rule set biased by the opponent model for the multiway
postflop cases no affordable solver handles. Details and the ranked list are
below.

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
    raises, all-ins: did not finish.** After 35 minutes wall (21 CPU-min) it
    had printed only iteration 0. Killed. This is the tree shape study tools
    use; it is not a decision-time solve on a laptop.
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
- macOS / Python: Rust library; **verified to compile and run on this Mac**
  once two things are pinned: Rust 1.85 (the 2026 compiler breaks it) and
  `bincode` and `bincode_derive` at exactly `2.0.0-rc.3` (the 2.0 release
  changed the trait). Build took 22 s after dependencies. Desktop app has an
  Apple-silicon build on the releases page (unsigned). No Python binding;
  you would wrap it with PyO3 or call a small Rust binary from Python.
- Produces a decision for an arbitrary spot? **Heads-up postflop only**
  (the README's "up to six players" refers to *bunching*: it accounts for
  cards removed by up to four folded players, it does not solve 3-way play).
  Arbitrary bet sizes, all-ins, donk bets, merging thresholds.
- Speed, **measured on this Mac**: the bundled `examples/basic` (two full
  ranges of roughly 40% each, board Td9d6h Qc, turn and river, pot 200,
  stack 900, bet sizes 60% / geometric / all-in, raises 2.5x, river donk
  50%, target 0.5% of pot) reached **0.46% exploitability at iteration 100
  in 0.44 s wall** (1.6 s CPU across threads), using 10 MB of memory.
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
  Mac**: `cargo build --release -p server` finished in 3 min 20 s (CPU-only,
  no CUDA), `./target/release/gto-server` started, chose 5 solver threads
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
  same `solve-cli bench_spot.json 100 0.05` run took **110 s** to 1.233% of
  pot (1.35M-node tree, 1.4 GB); see Appendix A.
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

### 6. Small or early-stage open solvers (for completeness)

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

### 7. OMPEval (zekyll)

- URL: https://github.com/zekyll/OMPEval
- What: C++ 7-card evaluator plus a range-vs-range equity calculator (Monte
  Carlo or exact enumeration) for **up to 6 players**.
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
  - 3-way Monte-Carlo equity on a flop, 10 threads: **312 million
    hands/s** (623 million samples in 2 s).
  - Heads-up exact enumeration of two real ranges on a flop: **2.8 ms**
    (2.97 million matchups).
- Ratings: (a) 3 (to 6 players) — (b) n/a — (c) n/a (an input to your own
  logic) — (d) 3 — (e) 3.

### 8. PokerHandEvaluator / phevaluator (HenryRLee)

- URL: https://github.com/HenryRLee/PokerHandEvaluator
- What: perfect-hash 5/6/7-card (and Omaha) evaluator in C/C++ with an
  official Python package `phevaluator`.
- Last activity: pushed 14 Sep 2026; 516 stars. Apache-2.0. Free.
- macOS / Python: **verified**; `pip install phevaluator` (0.6.0, arm64
  wheel; on this machine pip needed the wheel downloaded and installed
  explicitly because of a resolver hiccup).
- Speed, **measured**: **2.55 million 7-card hands/s** from Python when cards
  are ints, 0.80 million/s when cards are strings like "Ah". **Quoted** C:
  56 M/s.
- No equity calculator; pair it with your own Monte Carlo loop or OMPEval.
- Ratings: (a) n/a — (b) n/a — (c) n/a — (d) 3 — (e) 3.

### 9. treys (already the project's ground-truth evaluator)

- URL: https://github.com/ihendley/treys — MIT, pure Python, last push
  15 Jul 2023, 179 stars.
- Speed, **measured**: **165,000 7-card hands/s**. Fifteen times slower than
  phevaluator and 370 times slower than OMPEval; fine for tests, too slow for
  Monte-Carlo equity at decision time.

### 10. pokerstove (andrewprock)

- URL: https://github.com/andrewprock/pokerstove
- What: the open-sourced core of the classic PokerStove equity tool: C++
  `peval` library for 14 variants, `ps-eval` CLI, SWIG Python bindings.
- Last activity: 14 Dec 2024; 886 stars. BSD-3-Clause. Free.
- macOS: listed (XCode); needs Boost and CMake. Not built here.
- Speed: not published in the README; historically comparable to poker-eval,
  well below OMPEval.
- Ratings: (d) 2 (build effort) — (e) 3.

### 11. poker-eval / pypoker-eval (PokerSource)

- URL: https://pokersource.sourceforge.net/ , https://github.com/ChazDazzle/pypoker-eval
- What: the old GPL C evaluator with Python bindings; many variants.
- Last activity: essentially dormant (forks only). GPL. Free.
- Verdict: superseded by OMPEval and phevaluator; listed only so nobody
  re-discovers it.

### 12. eval7 (julianandrews/pyeval7)

- URL: https://github.com/julianandrews/pyeval7 — Cython evaluator with
  PokerStove-style range parsing and hand-vs-range equity.
- **Would not build on Python 3.13 on this Mac** (wheel build failed).
  Skip unless the project pins an older Python.

---

## Part 3. Commercial multiway-capable solvers

### 13. MonkerSolver (MonkerWare)

- URL: https://monkerware.com/solver.html
- What: the original multiway solver: "Solve Omaha and Hold'em from any
  street with any number of players", with abstraction to keep trees small.
- Price: **EUR 499 one-time**; free version limited to turn and river.
- Platform: native Windows 64-bit or macOS, 8 GB RAM minimum. No scripting
  or API documented; the community drives it with AutoHotkey macros, which
  is a sign there is no programmatic interface. Solutions export as .mkr and
  .txt range files.
- Multiway: yes, preflop and postflop, but multiway postflop trees need a
  lot of RAM and hours; it is a study tool, not a decision-time engine.
- Ratings: (a) 3 — (b) 3 — (c) 1 (no nodelocking documented) — (d) 1 —
  (e) 3.

### 14. GTO Wizard (includes the former Ruse AI as "GTO Wizard AI")

- URL: https://gtowizard.com/ ; pricing per PokerNews, 31 Mar 2026.
- What: a browser library of pre-solved spots plus an on-demand AI solver.
  **Multiway preflop up to 9 players** (launched 3 Feb 2026, custom antes,
  straddles, rake, "in seconds"); **3-way postflop** custom solves and, since
  Aug 2026, 3-way ICM postflop; 4-way and beyond "in development".
- Price: Starter $49/mo, Premium $99/mo, Elite $169/mo, **Ultra $279/mo
  ($229/mo annual; $359/$289 after early-bird)** for multiway and custom
  trees.
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

### 15. Simple Postflop / Simple 3-way / Simple Preflop Holdem (Simple Poker)

- URLs: https://simplepoker.com/en/Solutions/Simple_3-way ,
  https://shop.gipsyteam.com/simple-preflop-holdem
- What: a family of Windows solvers. Simple 3-way solves **3-player
  postflop**; Simple Preflop Holdem solves **2 to 10 player preflop** with
  postflop abstraction, ICM and rake.
- Price: Simple 3-way $249/year; Simple Preflop Holdem $250/year; Simple
  Postflop $299 standalone.
- Platform: **Windows only**, 16 GB RAM. No API or scripting documented.
- Ratings: (a) 2 — (b) 3 — (c) 1 — (d) 0 on a Mac — (e) 2.

### 16. PioSOLVER, GTO+, Jesolver (heads-up scriptable solvers, Windows)

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

### 17. Holdem Solver (holdemsolver.com) — new, free beta

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

### 18. HoldemResources Calculator (HRC)

- URL: https://www.holdemresources.net/ (pricing at /hrc/pricing)
- What: the standard tournament preflop/ICM solver, Java, Windows/macOS/Linux
  (macOS 64-bit; Apple-silicon support UNVERIFIED, forum posts from 2021 said
  x64 only). Pro tier adds postflop modelling and **scripted tree building in
  JavaScript** (Graal engine) with a Javadoc API.
- Price: Classic $9.99 to $16.66/mo; **Pro $29.99 to $49.99/mo**.
- Multiway: yes for preflop (Monte Carlo engine for 3+ active players).
- Ratings: (a) 3 (preflop) — (b) 2 — (c) 0 — (d) 2 — (e) 2.

### 19. Deepsolver (cloud, has a real HTTP API)

- URL: https://deepsolver.com/api
- What: GPU cloud solver with `POST /task/treebuilder`,
  `POST /task/cfr/schedule`, `GET /task/cfr/result/{id}`; JSON in, per-hand
  EV/strategy out (NumPy-friendly). Custom 1326-weight ranges, arbitrary bet
  grids, 2 to 20 s per solve.
- Price: consumer plans $10/$76/$209 per month (no API); **API plans start at
  $1,875/month plus a $2,000 setup fee**, or $0.025 per calculation on demand.
- Multiway: **not supported** ("multi-way is not supported").
- Ratings: (a) 0 — (b) 3 — (c) 1 — (d) 3 — (e) 0 (price).

### 20. Pokerai API (pokerai.bet)

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

### 21. Spinwize

- URL: https://www.spinwize.net/ — 3-handed Spin&Go database (all 1,755
  flops up to 36bb) with a "Solver API" to fetch from its 60 TB of solutions.
  EUR 53 to 89/month. 3-player only, short stacks only; API details behind the
  paywall (UNVERIFIED). Ratings: (a) 1 — (b) 2 — (c) 0 — (d) 3 — (e) 2.

### 22. Odin Poker, now "GTO Strategy"

- URL: https://gtostrategy.com/ — browser library built on the Odin solver:
  pre-solved cash and MTT spots for 4-max to 9-max, **multiway postflop
  solutions** in the Elite tier ($79/mo), live turn/river solving. No API or
  export. Ratings: (a) 3 — (b) 2 — (c) 0 — (d) 1 — (e) 2.

### 23. GTOBase

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
| GTO Wizard | 9-max multiway preflop, custom antes/straddles | copy as UPI text by hand | Ultra $229+/mo |

A gumroad pack of 576 tournament ranges in .txt (mkosmis) came up in search
but the page returned 404: UNVERIFIED.

None of the free chart sites offer bulk download or an API; the practical
route is to buy a MonkerGuy text pack (or hand-copy the free 9-max charts
into the repo's own text format once) and never solve preflop ourselves.

---

## Part 5. Ranked shortlist (best first)

1. **TexasSolver** — free, ships a macOS binary, text-command driven,
   solved a full-range turn-and-river spot in 0.7 s here (8 s wall with
   JSON output); the obvious heads-up postflop engine to call at decision
   time, callable from Python by writing a command file.
2. **OMPEval** (with a thin Python wrapper) — 312 M hands/s multiway equity
   on this Mac; the foundation for any opponent-biased rule in 3+ way pots.
3. **phevaluator** — `pip install`, 2.5 M hands/s from Python; replaces treys
   in the runtime path (treys stays as the test oracle).
4. **GTOpen** — the only open project with 2 to 9 player preflop plus
   explicit player-type exploitation and an HTTP API; builds and serves on
   this Mac; the blocker is the missing licence, which matters little for a
   private bot. Borrow its player-type definitions now.
5. **postflop-solver** — solved a comparable turn spot in 0.44 s here and
   has built-in node locking (turn a read into an exploit); needs Rust with
   a pinned toolchain and a small wrapper, and the project is suspended.
6. **MonkerGuy .txt ranges** ($69 to $499 one-time) or the free 9-max charts
   — precomputed preflop for every table size, no solving needed.
7. **Holdem Solver** (free beta, macOS, 2 to 9 players) — the only Mac tool
   that solves multiway postflop; no scripting, so useful for offline study
   of specific multiway spots, not at decision time.
8. **Pokerai API** — instant 6-max GTO answers over HTTP with a free tier;
   good for testing the bot's judgment against a reference, barred from live
   real-money use by its terms.
9. **GTO Wizard Ultra** — best opponent modelling (Profiles, Nodelocking 2.0)
   and 9-player preflop, but $229+/month with no API; a study tool only.
10. **HRC Pro** — tournament preflop/ICM with JavaScript tree scripting, if
    the bot ever plays tournaments.

Not recommended: Deepsolver API (heads-up only, $1,875/month), PioSOLVER,
GTO+, Jesolver, Simple Poker (Windows, heads-up or no scripting),
slumbot2019 and DecisionHoldem (multi-day blueprints, heads-up).

## Recommendation: what to adopt first

Adopt **TexasSolver as the postflop decision engine for heads-up pots and
OMPEval-plus-phevaluator as the equity layer for everything else**, and buy or
transcribe **precomputed preflop ranges** rather than solving preflop at all.
Concretely: at decision time, if only two players remain, build a small
TexasSolver command file from the live spot (board, pot, stacks, the
opponent's *estimated* range from the opponent model, one or two bet sizes)
and read the strategy from its JSON; the 0.7-second full-range turn solve
measured here says a pruned tree fits within a live decision window, and the
range you feed it is where the opponent model biases the answer. If three or more players
remain, use OMPEval equity against each opponent's modelled range (sub
millisecond) inside rules the engine already has, because no affordable,
scriptable multiway postflop solver exists on a Mac today. Preflop comes from
a range table for 2 to 9 seats, adjusted per opponent by the model. This
reaches a playable bot in hours, costs nothing but an optional $69 range
pack, uses only AGPL/ISC/Apache code that private use permits, and leaves a
clear upgrade path: GTOpen for player-type exploitation once it has a licence
and a Mac build, and Holdem Solver for offline multiway study.

---

## Appendix A. Measured timings on this Mac (Apple M4, 10 cores)

| Tool | Spot | Result | Time |
| --- | --- | --- | --- |
| TexasSolver 0.2.0 | turn+river, 93 vs 95 combos, one 66% bet, 60% raise, all-in | 0.74% exploitability, iter 51 | 0.71 s solve, 8 s wall |
| TexasSolver 0.2.0 | bundled 3-street sample, 2 vs 2 hands | 0.44%, iter 71 | 10.5 s solve, 16.4 s wall |
| TexasSolver 0.2.0 | flop+turn+river, same full ranges, 33/75% bets | not past iter 0 | killed at 35 min |
| postflop-solver | turn+river, ~40% vs ~40% ranges, 60%/geo/all-in, 2.5x raises | 0.46%, iter 100 | 0.44 s wall |
| GTOpen solve-cli | `bench_spot.json` flop, 3 streets, 1.35M nodes, CPU-only | 1.23% of pot, iter 100 | 110 s wall, 1.4 GB |
| OMPEval | 3-way Monte-Carlo equity on a flop, 10 threads | 312 M hands/s | 2 s budget |
| OMPEval | heads-up exact enumeration, two real ranges, flop | 2.97 M matchups | 2.8 ms |
| OMPEval | 7-card evaluation, single thread | 61.5 M hands/s | |
| phevaluator 0.6.0 | 7-card evaluation from Python, int cards | 2.55 M hands/s | |
| treys 0.1.8 | 7-card evaluation from Python | 165 k hands/s | |

GTOpen `solve-cli bench_spot.json 100 0.05` on this Mac, CPU-only, 10
threads: tree of 1,346,813 nodes built in 0.05 s, 257 vs 319 hands, 1.4 GB
of solver memory (compressed), **1.233% of pot exploitability at 100
iterations in 110 s** (the author's 12-thread desktop did the same in 61 s).
That is a full three-street flop tree with two IP flop sizes: two minutes
for a study-grade flop solve, which confirms the pattern above: full flop
trees are minutes, turn/river trees are under a second.

## Appendix B. What I ran

```
# evaluators (scratch venv, Python 3.13)
pip install treys phevaluator            # eval7 and pyrust-poker failed to build
python bench_treys.py                    # 165,275 hands/s
python bench_phe.py                      # 2,550,203 hands/s (ints), 800,485 (strings)

# OMPEval (clang 16, needs constexpr patch in omp/Random.h)
make CXXFLAGS="-O3 -std=c++17 -Wall -pthread"
./evbench   # 61.5 M evals/s
./eqbench   # 3-way MC 311.7 M hands/s (10 threads); HU exact flop 2.8 ms

# TexasSolver v0.2.0 macOS release (unzipped from the GitHub release)
./console_solver -i resources/text/commandline_sample_input.txt   # 16.4 s wall
./console_solver -i turn_input.txt                                # 8 s wall
./console_solver -i realistic_input.txt                           # killed at 35 min

# postflop-solver: rustup 1.85.0, bincode + bincode_derive pinned =2.0.0-rc.3
cargo +1.85.0 build --release --example basic && ./target/release/examples/basic   # 0.44 s

# GTOpen (stable Rust 1.98, CPU-only)
cargo build --release -p server                # 3 min 20 s
./target/release/gto-server & curl 127.0.0.1:3737/api/status   # {"state":"idle","gpu":false,...}
cargo build --release -p solver --bin solve-cli && ./target/release/solve-cli bench_spot.json 100 0.05
```
