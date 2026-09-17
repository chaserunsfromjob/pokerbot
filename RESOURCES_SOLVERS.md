# Solvers, equity calculators and paid services that could supply the bot's poker judgment

Researched 15 September 2026, revised through 17 September 2026. Machine used
for every timing below: the
operator's Mac laptop (Apple M4, 10 cores, macOS 15, Python 3.13). Everything
marked **measured** was run on this machine on 15 September 2026; everything
marked **quoted** is a number the vendor or author publishes; **UNVERIFIED**
means I could not confirm it by visiting the source.

The engine survey (OpenSpiel, RLCard, PyPokerEngine, PokerKit, clubs, PokerRL)
lives in `ENGINE_ALTERNATIVES.md`; this file does not repeat it.

## Summary for a non-programmer

A **solver** is a program that, given a poker situation (who has what range of
possible hands, the board, the stacks, the allowed bet sizes), computes a
strategy that cannot be beaten in the long run. That unbeatable strategy is
called the **equilibrium**; poker players call playing it **game-theory
optimal**, written **GTO** everywhere below. An **equity calculator** is a
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
  network. This project's own source is already public and licensed GPL-3.0
  (its full text is `LICENSE` at the repository root, and the repository is
  public at `github.com/chaserunsfromjob/pokerbot`), so publishing the changes
  is not the cost; the extra network clause is, and it is a clause GPL-3.0 does
  not carry. The name is **AGPL**, the Affero General Public Licence.

Four findings drive the recommendation:

1. **Multiway postflop solvers for a Mac exist; none can be driven by another
   program, and none is fast enough for decision time.** Two products solve
   any street with any number of players on macOS: **MonkerSolver** (EUR 499 one-time, native macOS,
   "any street with any number of players" per its own vendor page) and
   **Holdem Solver** (free beta, macOS Apple Silicon, 2 to 9 players). Both
   are driven by hand, and neither vendor page documents a way for one program
   to ask another for an answer — an **application programming interface**, or
   **API**. MonkerSolver does have a built-in tool for queueing a list of
   boards, but a person starts it by hand and it runs overnight to days
   (entry 16); no outside program controls either solver. That is what keeps
   them off the decision path; the timing is a separate question, and for Holdem Solver it
   is **UNVERIFIED**: what a multiway postflop tree costs in memory and hours
   there has no vendor figure behind it and was not measured here. The
   MonkerSolver vendor page does say that tree size scales with how much
   working memory the machine has — its **random-access memory**, or **RAM** —
   and solving time with how fast its processor is, the **central processing
   unit** or **CPU**. The rest are narrower: 3-way
   postflop in the browser (GTO Wizard, $229 to $359 a month for the tier that
   has it, from the vendor's own patch notes; no API) or on
   Windows (Simple 3-way), and preflop-only multiway (Simple Preflop Holdem,
   HRC, GTOpen's Preflop Lab, GTO Wizard's multiway preflop).
2. **Heads-up postflop solving in under a second on this laptop is solved
   and free.** TexasSolver (C++, ships a macOS binary, text-command driven)
   solved a turn-and-river spot with the full 6-max ranges — 93 and 95 hand
   classes, which expand to 606 card combinations on each side — to 0.74%
   exploitability in 0.56 to 0.71 s of solver time (5.5 s wall measured, the
   earlier run's wall clock noted only as about 8 s, including tree build and
   writing the answer out as text another program can read
   back, in the **JavaScript Object Notation** format, **JSON**).
   postflop-solver (Rust library,
   AGPL) solved a comparable turn spot to 0.46% of the pot in 0.19 to 0.23 s
   wall across five runs. Both measured on this Mac today, each started with
   the machine's 1-minute load average under 4.0 — see Appendix A, which
   records that load beside every figure re-taken this round, because other
   work shares this laptop. A full three-street flop tree
   with two bet sizes per street is a different animal: stopped at seven
   minutes, TexasSolver had printed no iteration past 3 and was still
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
   same loop written in plain Python on phevaluator was never measured here,
   and the arithmetic below rests on an **assumption, not a measurement**:
   that such a loop deals of the order of ten thousand play-outs, a figure no
   measurement in this file supplies and no source here cites.
   `ENGINE_ALTERNATIVES.md` reports two counts and distinguishes them at its
   own :418-428: the engine table's last column, complete hands dealt from
   scratch, and the chooser's play-outs per 250 ms decision, which continue a
   hand already part-played. Neither is this file's ten-thousand figure: both
   play a hand out to the end inside a game engine, where these count deals
   of the remaining cards to settle one hand's equity in a Python loop. On
   that assumption, and counting one hand ranking per play-out, 10,000
   rankings at the measured 2.6 million a second take 10,000 ÷ 2,600,000 =
   **3.8 ms**, and at the measured 0.9 million a second 10,000 ÷ 900,000 =
   **11 ms**: a few milliseconds to about ten, not a sub-millisecond job.
4. **Only one open-source project explicitly does what the operator wants,
   opponent-specific exploitation across 2 to 9 seats, and it is preflop-only
   for multiway**: GTOpen (Rust, pushed 15 Sep 2026, no licence file; read
   2026-09-15). It compiled on this Mac in 1 min 53 s to 3 min 20 s across
   two builds, and its own small web server — it takes requests in the same
   way a web browser makes them, over the **HyperText Transfer Protocol**,
   **HTTP** — answered on `127.0.0.1:3737` with a CPU-only solver, so
   "Windows/Linux only" in its README is just missing documentation. Its
   author's own experiments — results he got from his older fixed opponent
   profiles, which a note on his own page says are not predictions for the app
   he ships today (entry 3) — report 40 to 80 big blinds per 100 hands gained
   by exploiting a correctly identified player type, and, when the read is
   wrong, a loss that runs from 0 to 461 bb/100 depending on which wrong read
   it is (his cross-exploit table, `docs/player_types.md:127-136`: one number
   per counter-strategy-played against table-actually-faced pair; the row for
   the Nit counter-strategy alone spans 126 to 461). That is both the promise
   and the warning. Read the
   build times with one caveat that applies to both Rust projects in this
   file: **this Mac has no Rust toolchain installed**, so every Rust number
   here required installing one first (Appendix B says exactly how, and where
   it was put).

What this survey can settle on its own is which of these tools work, on this
machine, at what speed. What it cannot settle on its own is the architecture,
for two reasons stated plainly here and again in the recommendation:

- The obvious way to cover multiway postflop with the tools listed here is
  **an equity-driven rule set biased by the opponent model**. No engine in
  this survey contains such rules; they would be code we write, and code that
  picks the action. `CLAUDE.md:15-17` forbids exactly that without a recorded
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

Each resource that could supply poker judgment is scored on five criteria, 0
to 3 (3 is best). Two classes of entry are scored differently, and both are
called out where they appear. A **hand evaluator or equity calculator** has no
(a), (b) or (c) to score — it never chooses an action, so those read `n/a` and
only (d) and (e) carry a number. Three entries carry **no score at all**,
because they are listed as dead ends rather than as candidates and a score
would imply they are in the running: **poker-eval / pypoker-eval** (entry 14,
superseded, listed so nobody re-discovers it), **eval7** (entry 15, would not
build here) and **noambrown/poker_solver** (inside entry 9, a river-only
reference implementation, not a product).

- **(a) 2 to 9 players** — does it produce decisions for 3+ player spots?
- **(b) true no-limit sizing** — arbitrary bet sizes, not fixed-limit?
- **(c) exploit specific opponents** — can it be biased by an opponent model
  (nodelocking, profiles, player types) or does it only give equilibrium?
- **(d) reachable in hours on one laptop** — no multi-day compute, runs on
  macOS or callable from a Mac.
- **(e) fits a public GPL-3.0 project** — licence or price acceptable for a
  bot that is itself licensed GPL-3.0 and publishes its source at
  `github.com/chaserunsfromjob/pokerbot` (its full text is `LICENSE` at the
  repository root, and the repository is public).
  GPL-compatible code is fine, because every derived work here is published
  under GPL-3.0 anyway. Paid tools are fine, because the operator buys them
  for their own use and buying a tool is not publishing it. The ones to watch
  are AGPL, which adds a network clause GPL-3.0 does not carry; licences that
  are incompatible with GPL-3.0; code with no licence at all, which may not be
  copied into a published project; and a terms-of-service clause banning
  automated play.

---

## Part 1. Open-source real-time solvers

### 1. TexasSolver (bupticybee)

- URL: https://github.com/bupticybee/TexasSolver
- What: a C++ solver for hold'em and short-deck postflop spots. It learns by
  playing the spot against itself thousands of times and cutting back whatever
  it comes to regret; that method is **counterfactual regret minimisation**,
  written **CFR**, and every open-source solver in this file uses some form of
  it. Ships a point-and-click window — a **graphical user interface**, or
  **GUI** — and a **console binary driven by a text command file**.
- Last activity: last commit 26 Aug 2026; last binary release v0.2.0 on
  4 Nov 2021 (macOS zip included; **2,547 stars**, read from the GitHub API on
  15 Sep 2026).
- Licence: AGPL-3.0 (commercial licence available).
- Price: free.
- macOS / Python: **verified**. I downloaded the v0.2.0 macOS release, ran
  `./console_solver -i <commands.txt>` directly, and it wrote a JSON
  strategy tree that Python can read. Commands are `set_pot`,
  `set_effective_stack`, `set_board`, `set_range_ip/oop`, `set_bet_sizes
  <who>,<street>,<bet|raise|donk|allin>,<pct...>`, `build_tree`,
  `set_accuracy`, `start_solve`, `dump_result`. A Python `TreeBuilder.py`
  ships in `resources/python`.
- Produces a decision for an arbitrary spot? **Heads-up only**: one range for
  the player who acts last on each street (**in position**, **IP**, the `ip`
  in the command names above) and one for the player who has to act first
  (**out of position**, **OOP**). Any street, any board, any bet sizes you
  list, flop through river.
- Speed, **measured on this Mac** (10 threads):
  - **Turn-and-river solve, full ranges** (button 93 vs small blind 95 *hand
    classes* from the bundled 6-max ranges — a hand class such as "AKs" is a
    single line in the range file, and expanding the classes gives **606 card
    combinations** on each side, 551 and 566 after the file's partial weights,
    before the board removes any; board Qs8d7h2c, pot 13, stack 93, one 66%
    bet and 60% raise per street, all-in): **0.74% exploitability at iteration
    51 in 0.56 to 0.71 s solver time; 5.5 to 8 s wall** including tree build
    and a 360 KB JSON strategy dump, over two runs; the fresh one was 0.561 s
    solver time and 5.45 s wall at a 1-minute load of 3.40, and the earlier one
    on a busier machine was 0.706 s solver time — the 0.71 above — with its
    wall clock noted only as about 8 s. Command file and
    raw solver log published at
    `research/solvers/texassolver_turn_full_ranges.txt` and
    `research/solvers/texassolver_turn_run.log`; both runs' timers are written
    out in `research/solvers/texassolver_turn_run_note.txt`, the earlier one
    copied from its log; the command is in Appendix B.
  - The bundled 3-street sample (2-hand vs 2-hand ranges): 0.44%
    exploitability at iteration 71 in 10.5 s solver time, 16.4 s wall.
  - **Full flop tree, same full ranges, three streets, 33%/75% bets, 60%
    raises, all-ins: re-measured today under a hard 7-minute stop.** Command
    file and runner published at
    `research/solvers/texassolver_flop_full_ranges.txt` and
    `research/solvers/run_texassolver_flop.py`, so this number can be checked
    rather than believed. 10 threads, **three runs to the 420-second
    deadline** on this laptop, which other work also shares. The runner's
    stdout for each is published beside the command file, one file per run, so
    the three can be told apart:

    | Run | Wall | CPU | Cores busy | Peak memory | Iterations printed | 1-minute load at the start | Runner stdout |
    | --- | --- | --- | --- | --- | --- | --- | --- |
    | 1 | 423.1 s | 699.8 s | 1.65 | 5.79 GiB | 0, 2, 3 | not recorded | `texassolver_flop_run1_423s.log` |
    | 2 | 421.4 s | 493.4 s | 1.17 | 4.95 GiB | 0, 2 | 3.29, recorded in `texassolver_flop_run2_load_note.txt` | `texassolver_flop_run2_421s.log` |
    | 3 | 422.5 s | 462.2 s | 1.09 | 5.41 GiB | 0, 2, 3 | 3.75 | `texassolver_flop_run3_422s_instrumented.log` |

    All three printed the same two exploitability figures: **226.39% of pot at
    iteration 0 and 221.72% at iteration 2** — against the 1% the command file
    asks for. Run 3 is the instrumented one the page-fault figures below come
    from. Read the spread, not any single run: the wall time is fixed by the
    deadline, and the CPU time moves by a factor of nearly two with what else
    the machine is doing.

    Two shorter probes of the same command file were also run, stopped well
    before the 420-second deadline, and they are **not** part of the three
    above: 181.5 s wall / 302.4 s CPU / 1.67 cores / 3.44 GiB, and 151.6 s
    wall / 343.5 s CPU / 2.27 cores / 4.43 GiB. Both printed iterations 0 and
    2 but only the iteration-0 exploitability, 226.39%, before they were
    stopped; neither recorded its start load. They are why the memory floor
    quoted in an earlier draft was 3.4 GiB — that figure came from the 181 s
    probe, while the three full runs used 4.95 to 5.79 GiB. It is
    the tree shape study tools use; it is not a decision-time solve on a
    laptop, and the gap is more than two orders of magnitude (222% against a
    1% target is a factor of 222), not a near miss.
    An earlier draft of this file said the same run "had printed only
    iteration 0" after 35 minutes for 21 CPU-min. **That did not reproduce
    and is withdrawn**: the print interval was set to 20, so iterations 1 to
    19 were being completed silently, and the 0.6-cores-busy figure it
    implied is not what this machine does either. The conclusion survives the
    correction; the number did not.
  - **Why so few cores are busy is not established here, and an earlier draft
    of this file guessed at it.** That draft said the solve was "waiting on
    memory, not on arithmetic", which would have made a bigger machine the
    fix. No measurement backed that, so the run was instrumented: over the
    422.5 s run the solver process itself took **1,653 major page faults** —
    the kind that have to go to disk — which is about four a second, or
    26 MiB of disk-backed paging in seven minutes. **Whatever the threads are
    waiting for, it is not the solve reading its own pages back off disk**,
    and the guess is withdrawn. What the same run does show is a machine under
    real memory pressure from everything running on it together: swap in use
    went from 4.56 GB to 11.68 GB and macOS grew the swap file from 6 GB to
    12 GB, with 5.27 million pages (80 GiB) written out machine-wide. That
    pressure is not attributable to this solve — other work shares the laptop,
    and the load average sat at 4.4 to 6.9 throughout. The solver also took
    47.4 million minor faults and 4.86 million involuntary context switches,
    both consistent with a contended machine rather than with a memory
    ceiling, but neither isolates a cause. **The honest statement is: 1.1 to
    1.7 cores busy out of 10, and why the other eight are idle is not measured
    here.** Settling it would need the run repeated on a quiet machine with
    per-thread wait accounting, which is not something this survey needs in
    order to reach its conclusion — the conclusion is that the run is 222
    times away from its target after seven minutes, and that holds however the
    cores are spent.
  - **Quoted**: 172 s vs PioSOLVER's 242 s on the same flop tree (author's
    benchmark, with the remaining stack ten times the size of the pot — the
    **stack-to-pot ratio**, **SPR**, is 10 — and a smaller tree than mine).
- Limits: heads-up only; the GPU successor (TexasSolverGPU) is Windows-only,
  NVIDIA-only and closed source, so it is irrelevant on a Mac.
- Ratings: (a) 0 — (b) 3 — (c) 1 (you can hand it a biased range for the
  opponent, but you cannot lock the opponent's actions) — (d) 3 — (e) 2
  (AGPL: GPL-3.0 may take it in, but the network clause rides along).

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
  and re-verified on 2026-09-15, once two things are pinned: the compiler at
  **`rustc 1.85.0 (4d91de4e4 2025-02-17)`** (the 2026 compiler, 1.98.1, breaks
  it) and `bincode` at exactly `2.0.0-rc.3` — one line in `Cargo.toml`
  (line 12, `bincode = { version = "=2.0.0-rc.3", optional = true }`), because
  the 2.0 release changed the trait. Its companion crate `bincode_derive` is
  not named in `Cargo.toml` at all; it comes in as a dependency of `bincode`
  and is held at the same `2.0.0-rc.3` by `Cargo.lock`, so committing the lock
  file is what pins it. **A toolchain has to be
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
  (0.91 chips in a pot of 200) in 0.19 to 0.23 s wall and 1.53 to 1.59 s of
  CPU across threads**, over five consecutive runs re-timed today at a
  1-minute load average of 3.40, using 10 MB of memory. (An earlier round
  reported 0.44 to 0.89 s wall and 2.7 s CPU for the same binary and the same
  example; those runs were taken while the machine was much busier and the
  load was not recorded beside them, so they are superseded by the figures
  here rather than averaged with them.) Either end is well inside a decision
  window.
  **Quoted**: author says it "surpasses PioSOLVER and GTO+"; the WASM
  version solved a full flop tree to 0.1% exploitability in 45.5 s with 16
  threads, and the native version is about 2x faster.
- Limits: heads-up; suspended project; Rust, not Python.
- Ratings: (a) 0 — (b) 3 — (c) 2 (has **node locking** in the library:
  `examples/node_locking.rs` lets you fix the opponent's strategy at chosen
  nodes and re-solve, which is how you turn an opponent read into an
  exploitative strategy) — (d) 3 — (e) 2
  (AGPL: GPL-3.0 may take it in, but the network clause rides along).

### 3. GTOpen (MatthewPDingle)

- URL: https://github.com/MatthewPDingle/GTOpen
- What: an open-source Rust solver with a local web UI and HTTP API:
  heads-up postflop CFR (CPU or CUDA), a **2 to 9 player Preflop Lab** with
  limps and any sizings, and **player profiling with maximum-exploitation
  solves**.
- Last activity: created 13 Jun 2026; pushed **15 Sep 2026** (read
  2026-09-15); 14 stars, one author.
- Licence: **none** (no LICENSE file in the repo). Legally that means all
  rights reserved, and this project publishes its own source under GPL-3.0,
  so none of this code may lawfully be copied into it. Running the published
  binary as a separate tool is a different question and is fine.
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
  iteration 100 in 76.0 s and 79.3 s** on two re-runs today, started at
  1-minute load averages of 3.96 and 3.58 — bit-identical exploitability at
  every printed iteration, so the only thing that moves is the clock. Earlier
  runs of the same command on a much busier machine took 110 s and 179.1 s,
  which is the honest width of a laptop timing: **call it one to three
  minutes, about 76 to 79 s when little else is running.**
  1,346,813-node tree built in 0.04 to 0.06 s; 1.4 GB of arenas. The tree
  header's "hands 257/319" counts **card combinations**, not hand classes —
  two ~35% ranges expand to 257 and 319 individual two-card holdings after
  the Ks7h2d board removes the rest. See Appendix A.
- Opponent modelling: player types defined by two counted rates — how often a
  player puts money in before the flop (**voluntarily put money in pot**,
  **VPIP**) and how often they raise it (**preflop raise**, **PFR**) — in
  bands (Nit, TAG, LAG, Whale, Maniac, station/folder modifiers) with datasets
  from Ignition and CoinPoker at NL10 to NL100; hero solves a max-exploit
  against every other seat playing the measured profile. Author's reported
  results, from the cross-exploit tables in `docs/player_types.md:107-149`:
  **+40 to +80 bb/100** on top of equilibrium play when the type is right
  (section 4.1, eight-max 150bb $2/2 and 200bb $2/5), and, when it is wrong,
  a loss that depends entirely on which wrong read you make. Section 4.2
  gives one number per (counter-strategy played, table actually faced) pair:
  across the whole $2/2 table the cost runs **0 to 461 bb/100**. The two
  figures quoted in earlier drafts of this file, 194 and 287, are two cells of
  a single row — the **Nit counter-strategy** row, played against a TAG table
  and against a Whale table; that row's worst cell is **461 bb/100** against a
  Maniac table, and its range against non-nit tables is 126 to 461. Quote the
  row, not the pair.
- What the author says about his own numbers: the file that holds them opens
  with a warning he added himself, `docs/player_types.md` lines 3-6, read
  2026-09-16 — "September 2026: generated profiles now use separate limp-entry
  defenses and the app defaults to adaptive large-bet responses. Historical
  results below used fixed profiles and should not be read as current
  adaptive-model predictions. See the correction and its limits
  (preflop_modeling_fix.md)." In plain terms: every figure above is something
  that happened in his past experiments, where the imaginary opponents played
  one fixed way; his current program adjusts as the hand goes on, so those
  figures are not a forecast of what it would win or lose now. They are still
  the only numbers anyone has published for this, and they are quoted here as
  history, not as a promise.
- Limits: single-author, brand new, no licence, no Mac instructions,
  multiway is preflop only.
- Ratings: (a) 2 (preflop 2-9, postflop 2) — (b) 3 — (c) 3 — (d) 3
  (builds and serves on this Mac) — (e) 1 (no licence, so nothing of it may
  be copied into a published project; usable only as a separate tool).

### 4. slumbot2019 (Eric Jackson)

- URL: https://github.com/ericgjackson/slumbot2019
- What: the C++ CFR toolkit behind Slumbot, with CFR+, a sampling variant that
  walks a few randomly chosen lines through the tree per pass instead of all of
  them — **Monte-Carlo CFR**, **MCCFR** — card and betting abstractions,
  endgame re-solving and head-to-head evaluation.
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
  retrain) — (e) 2
  (AGPL: GPL-3.0 may take it in, but the network clause rides along).

### 6. amaster97/poker_solver

- URL: https://github.com/amaster97/poker_solver
- What: a heads-up no-limit hold'em solver in two tiers — a readable Python
  reference implementation that acts as the specification, and a Rust core
  (`crates/cfr_core`, exposed to Python as `poker_solver._rust` through PyO3
  and maturin) that does the solving. Tabular Discounted CFR with the
  published Brown-Sandholm 2019 constants, checked tier against tier by
  differential tests. Ships a local browser GUI (NiceGUI), a way to run it by
  typing commands in a terminal — a **command-line interface**, or **CLI** — a
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
  evaluation, abstraction, suit-isomorphism helpers, helpers that make one
  processor instruction work on several cards at once (**single instruction,
  multiple data**, **SIMD**), and vendors
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
- Ratings: (a) n/a — (b) n/a — (c) n/a — (d) 3 (pure Python, installs
  anywhere) — (e) 3 (MIT).

### 13. pokerstove (andrewprock)

- URL: https://github.com/andrewprock/pokerstove
- What: the open-sourced core of the classic PokerStove equity tool: C++
  `peval` library for 14 variants, `ps-eval` CLI, SWIG Python bindings.
- Last activity: 14 Dec 2024; 886 stars. BSD-3-Clause. Free.
- macOS: listed (XCode); needs Boost and CMake. Not built here.
- Speed: not published in the README; historically comparable to poker-eval,
  well below OMPEval.
- Ratings: (a) n/a — (b) n/a — (c) n/a — (d) 2 (build effort: Boost and CMake,
  not built here) — (e) 3 (BSD-3-Clause).

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
  itself on 2026-09-15: "€499", "Solve Omaha and Hold'em from any street with
  any number of players", "Windows 64-bit or Mac OS X with atleast 8 GB RAM".
- Platform: native Windows 64-bit or macOS, 8 GB RAM minimum. The vendor page
  was re-read again on 2026-09-16: it documents a tree builder, a solution
  viewer, a GUI,
  abstraction and the export formats, and **no API and no scripting
  interface** — there is nothing on it that offers a way for one program to
  drive the solver. An earlier draft of this file rested that conclusion on a
  claim that the product's community drives it with AutoHotkey macros; no
  source or date was ever cited for it, the vendor page says nothing about
  AutoHotkey, and the sentence is dropped. The conclusion rests on the vendor
  page alone. Solutions export as .mkr and .txt range files.
- Scripting: the vendor page does not mention it, but a third-party guide
  documents a scripting tool inside the program —
  https://plodalong.com/articles/monkersolver-scripting ("MonkerSolver: Using
  the Scripting Tool to Batch Solve Flops", MonkerSolver Series Part 3,
  PlodAlong, 31 March 2026). What it is: a dialog in the program's own window,
  opened from the **Solve** menu, where you pick one saved `.tree` file with
  its ranges included, give it a comma-separated list of boards, set
  "Volatility" to 2.0 and "Reset avg after iterations" to 7, choose a save
  folder, and click **Start**; it then solves each board in the list in turn
  and writes each answer out to that folder. What it is not: a way for another
  program to use the solver. There is no command line, no API and nothing a
  program can call to start a solve or read one back, and the guide's own
  expectation of the run is that you "leave this running overnight or across
  multiple days".
- Multiway: yes, preflop **and postflop, on any street**, which is what the
  vendor page claims in as many words. It is emphatically **not** a
  preflop-only tool, and an earlier draft of this file said so in its summary;
  that was wrong and is corrected above. The real limits are different ones:
  multiway postflop trees need a lot of RAM and hours of solving, so it is a
  study tool, not a decision-time engine, and there is no external program
  control: its batches are started by hand from the Solve menu and run
  overnight to days (see Scripting above).
- Ratings: (a) 3 (any street, any number of players) — (b) 3 — (c) 1 (no node
  locking documented) — (d) 1 (macOS yes, but by hand and in hours) — (e) 3.

### 17. GTO Wizard (includes the former Ruse AI as "GTO Wizard AI")

- URL: https://gtowizard.com/
- What: a browser library of pre-solved spots plus an on-demand AI solver.
  Every capability line below was re-read off the vendor's own patch notes
  on 2026-09-16 (`blog.gtowizard.com/tag/patch-notes/`) and is quoted, not
  summarised:
  - **Multiway preflop up to 9 players.** Patch note dated **February 03,
    2026**, "Introducing Multiway Preflop Solving": "Today, we're launching
    our biggest solver upgrade yet: custom Multiway Preflop Solving for up to
    9 players!" Same page, on speed: "you can solve multiway preflop spots
    directly in your browser, even on your phone, in seconds". Same page, on
    the structures it supports: "Antes: Per-player antes, total antes, and Big
    Blind ante formats. Straddles: Standard straddles, Double straddles, and
    Mississippi straddles (from any position)" and "Chip EV and Raked Solving".
  - **3-way postflop custom solves.** Same page, listing what the Ultra tier
    includes: "Unlimited Multiway Postflop Solving (up to 3 players)".
  - **3-way postflop solving that prices chips by what they are worth in
    tournament prize money rather than at face value** — the **independent
    chip model**, **ICM**. Announced in the patch note "Now Live: Preflop ICM
    Solving", **dated September 15, 2026**, not August: "We also added 3-way
    postflop ICM solving". An earlier draft of this file dated it to Aug 2026;
    that was wrong and is corrected here.
  - **Beyond 3-way: roadmap, not shipped.** Same Feb 2026 page, under "Ultra
    Roadmap ... We've got major upgrades in development": "Multiway Postflop
    Expansion – Scaling postflop multiway solving up to 9 players."
- Price: **every Ultra figure is vendor-confirmed; the other three tiers are
  not.** The vendor's own pricing page was fetched again on 2026-09-16 and
  returned a
  518-byte page that builds its prices in the browser, so nothing could be
  read from it. The patch notes carry the Ultra prices in plain text instead,
  and all four were read off them on 2026-09-16:
  - The **February 03, 2026** patch note, under "Pricing", gives the
    introductory rate — it calls it an "Early Bird discount" — as "Annual
    Plan: $229/month" and "Monthly Plan: $279/month".
  - The same page gives the rate after it: "After Early Bird, standard Ultra
    pricing will be: Annual: $289/month Monthly: $359/month".
  - The **September 15, 2026** patch note says when the introductory rate
    stops: "Early Bird pricing ends October 15, 2026 at 1:00 PM CEST."
  So $229, $279, $289 and $359 a month for Ultra, and the date the first two
  become the last two, all come from the vendor. What does **not** come from
  the vendor is the rest of the ladder: Starter $49/mo, Premium $99/mo and
  Elite $169/mo are still **UNVERIFIED**, taken from a PokerNews article dated
  31 March 2026 whose Ultra figures the patch notes now confirm. Treat those
  three as a press report that may be stale, and confirm on the site before
  any money is spent. Either way this is a monthly subscription, not a
  purchase, and the multiway and custom-solve features sit in the top tier.
- Opponent modelling: **Profiles** and **Nodelocking 2.0**, both quoted from
  the vendor. Patch note "Custom Profiles Go Live", **November 12, 2025**:
  "you can now model any player type you want. You can create your own from
  scratch, set their specific incentives to guide their behavior", with the
  vendor's own worked example — "Add +5% pot incentive to Bet/Raise, and the
  profile behaves as if every bet were rewarded with an extra 5% pot bonus" —
  and the caveat that "these incentives are virtual. They guide the profile's
  behavior but are ignored in the final expected value calculations". (An
  earlier draft of this file gave the example as "+4% pot to call"; no such
  figure appears on the vendor page, and the vendor's own example is the +5%
  bet/raise one above.) `blog.gtowizard.com` front page on the other feature:
  "Nodelocking 2.0 Model your opponent's leaks and watch the solver build the
  perfect counter-strategy." Both produce an exploitative counter strategy;
  that is the most polished opponent-biasing available anywhere.
- API: **none** for strategy lookup. There is a separate free
  "Researcher API" (https://github.com/gtowizard-ai/researcher-api-client,
  application required) that only lets your bot *play hands against* GTO
  Wizard AI for benchmarking; it does not return strategies. Ranges export by
  hand as text in the format PioSOLVER's command protocol uses — the
  **universal poker interface**, **UPI** — with no bulk download.
- Ratings. The two that carry weight elsewhere in this file, (a) and (c), now
  rest on the vendor quotes above rather than on recollection: (a) 2 (9
  preflop, 3 postflop, both quoted) — (b) 3 — (c) 3 (Profiles and Nodelocking
  2.0, both quoted) — (d) 1 (browser
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

- PioSOLVER: prices read off the vendor's own product page,
  https://piosolver.com/products, on 2026-09-17 and quoted from it —
  "PioSOLVER 3.0 Pro … € 450.00 (+applicable taxes)" and "PioSOLVER 3.0
  Edge … € 800.00 (+applicable taxes)". Both list "1 year of software
  updates" and "Can be used on two computers"; Edge adds "Preflop solver (for
  heads-up spots)" and "Support for up to 64 cores" where Pro has 16. That is
  euros, not dollars, and roughly twice what an earlier draft of this file
  said ("Pro $249, Edge $475 one-time"), which it took from the site root —
  a page that carries no prices at all. Windows
  only (Mac users run Parallels). **UPI** text protocol lets a script drive
  it (https://piosolver.com/docs/upi/); nodelocking supported. Heads-up
  postflop.
- GTO+: prices read off https://gtoplus.com/purchase on 2026-09-17 and quoted
  from it — "Main License: $75  Second License: $40  Upgrade from CREV: $50"
  and "The registration fee is one-time. All future updates are included.
  Taxes may still be added depending on your location."
  The $375 top end an earlier draft gave appears nowhere on that page.
  Windows, heads-up, scripting for batch databases.
- Jesolver (https://jesolver.com/cmdref.html): price **UNVERIFIED**. On
  2026-09-17 the site root and `/index.html` each returned a one-byte page,
  and `/cmdref.html` is a command list that names no price, so the "$200" an
  earlier draft carried has no live source. Treat it the way entry 17's
  unconfirmed GTO Wizard tiers are treated: a figure that may be stale, to be
  confirmed on the site before any money is spent. It is a UPI-compatible
  engine that replaces Pio's, several times faster and lower memory; Windows.
- Ratings for all three: (a) 0 — (b) 3 — (c) 2 (nodelocking) — (d) 1
  (Windows VM on a Mac) — (e) 2. **The corrected prices do not move this
  entry's verdict.** TexasSolver and postflop-solver give the
  same capability free and natively on macOS, so none of these are worth
  buying for this project at any price.

### 20. Holdem Solver (holdemsolver.com) — new, free beta

- URL: https://holdemsolver.com/
- What: a desktop solver for **2 to 9 players on any street**. It can value a
  line either by the average number of chips it wins in the long run — its
  **expected value**, **EV** — or, in tournaments, by prize money: ICM (see
  entry 17), and the bounty variant where knocking a player out pays part of
  their bounty and adds the rest to your own head, **progressive knockout**,
  **PKO**. "No sampling and no card abstraction" heads-up, sampled MCCFR
  multiway, running on your own hardware with results stored locally.
- Price: **free during open beta (v0.79), pricing TBA**.
- Platform: **Windows x64 and macOS Apple Silicon**.
- Speed, **quoted from the vendor's own front page**, re-read on 2026-09-16,
  with the
  caption it carries there. Under a strategy grid the page prints the run's
  own readout, "20,050,063 iterations · 9m 05s  Δ 0.0010 · precision low", and
  captions it "Real solver output": "LJ's opening strategy in a 63-entry PKO,
  53 players left. Full-field ICM with bounties and antes, running locally: 20
  million iterations in and still converging. AKs currently raises 90.8% and
  jams 9.2%." Read what that says: after 9 min 05 s the spot had **not**
  converged, and the vendor says so. An earlier draft of this file reported
  the same figures as a spot that "converged after 20 million iterations in
  9 min 05 s"; that reversed the vendor's own words and is corrected here.
  Hardware unstated.
- Time and memory on a multiway postflop tree: **UNVERIFIED**. The vendor
  publishes no such figure, and nothing was measured here.
- API/scripting: none mentioned. Licence: unstated. Vendor and origin:
  UNVERIFIED beyond the site itself.
- Ratings: (a) 3 — (b) 3 — (c) 0 (nothing documented) — (d) 2 (runs on this
  Mac, but only by hand) — (e) 2 (free now, terms unknown; a closed tool we
  run, not code we copy).

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
- Price: **API plans start at $1,875/month plus a $2,000 setup fee** (Builder,
  50,000 calls included, overage $0.05 a call; Production $2,625 and $0.04;
  Scale $4,875 with 300,000 calls included and **overage $0.025 a call**;
  Enterprise $6,750, unlimited, no overage). The same $0.025 a calculation is
  also sold outright on that page as an On-Demand tier, "Sold in packs of $250
  for 10,000 calculations". The separate consumer plans are on
  https://deepsolver.com/pricing, not on the API page, and on 2026-09-16 that
  page showed two: Pro $69 a month ($41.40 billed yearly) and Essential $49 a
  month ($29.40 billed yearly); neither lists API access among its features.
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
  pre-solved cash-game spots and spots from tournaments played across many
  tables at once — a **multi-table tournament**, **MTT** — for 4-max to
  9-max, **multiway postflop
  solutions** in the Elite tier ($79/mo), live turn/river solving. No API or
  export. Ratings: (a) 3 — (b) 2 — (c) 0 — (d) 1 — (e) 2.

### 26. GTOBase

- URL: https://gtobase.com/ — browser viewer; 6-max cash 40 to 200bb, 8/9-max
  MTT 15 to 100bb, HU cash free. $75 to $150/month. No API, no export.
  Ratings: (a) 2 — (b) 2 — (c) 0 — (d) 1 — (e) 2.

---

## Part 4. Free or cheap precomputed preflop ranges, 2 to 9 handed

Preflop for 9 players is the one multiway problem that is genuinely solved
and cheap. Sources checked 2026-09-15, except where a row carries its own read
date:

| Source | Coverage | Format | Price |
| --- | --- | --- | --- |
| Preflop Wizard blog https://www.preflopwizard.app/blog/9-max-preflop-chart | 9-max and 6-max charts for opening when everyone ahead has folded (**raise first in**, **RFI**) and for defending the big blind, at 100bb, 2.5x open; updated Jul 2026 | web page only (the ranges are tables inside the article); no download and no PDF — the only downloads offered are the vendor's iOS and Android apps, and the article argues against printing charts. Read 2026-09-17 | free |
| preflopranges.app https://preflopranges.app/ | "15,000+ charts": 9-max MTT 10 to 200bb, 6-max cash, 3-max spins, with per-hand frequencies; open beta, no account | web only, no export found | free |
| PokerCoaching https://pokercoaching.com/preflop-charts/ | 6-max and full-ring cash, MTT 15/75bb, push-fold; GTO **and exploitative** versions | PDF, email required | free |
| MonkerGuy https://www.monkerguy.com/ | 6-max and 9-max NLHE 20 to 200bb, 8-max MTT packs; MonkerSolver output | .mkr, MonkerViewer, **.txt ranges (Pio/PPT compatible)** | hold'em products only: **$69** for the cheapest single sim ("6-MAX 100BB 2.5x Open") up to **$319** for the tournament pack ("8max (BB ANTE) MTT Pack"); the 9-handed sim this project would actually want ("9 PLAYERS NLH 100bb - 2.5x Open") is **$199**. The one $499 item on the site is "6-MAX PLO MTT (BB ANTE) Pack", which is Omaha, a different game. Prices read off the page 2026-09-16 |
| GTO Sims https://gtosims.com/ | Spin&Go, 6-max, MTT from Simple Preflop Holdem | Simple Preflop files, Pio charts, PNG | per solution, price not shown |
| TexasSolver release bundle | 6-max 100bb ranges (BTN/CO/MP/SB/UTG opens, 3-bet, call trees) as plain text | text, already on this Mac | free |
| GTO Wizard | 9-max multiway preflop, custom antes/straddles | copy as UPI text by hand | top tier, monthly; $229 to $359 a month, vendor-confirmed (see entry 17) |

A gumroad pack of 576 tournament ranges in .txt (mkosmis) came up in search
but the page returned 404: UNVERIFIED.

None of the free chart sites offer bulk download or an API, so getting a set in
usable form means buying a pack — MonkerGuy's Pio-compatible .txt ranges run
from $69 for one 6-max 100bb hold'em sim to $319 for the 8-max tournament
pack, with the 9-handed 100bb sim at $199 (read off the page 2026-09-16) — or
hand-copying the free 9-max charts into a text format once.
Either way, preflop ranges for 2 to 9 seats are available free or for $69 to
$319, so no preflop solving is needed to obtain them. What is done with them is
a separate question and not this file's to answer; see the recommendation.

---

## Part 5. Ranked shortlist (best first)

Ranked on one question: **how much working poker judgment does this put in the
bot's hands today, on this machine, for what effort?** Everything above slot 6
was run here; everything below it was read about.

1. **TexasSolver** — free, ships a macOS binary, text-command driven, nothing
   to build. Solved a full-range turn-and-river spot in 0.56 to 0.71 s of
   solving here (5.5 s wall measured, an earlier run noted only as about 8 s,
   including the JSON dump); the same binary
   needs more than seven minutes to get nowhere on a full flop tree, so the
   rule is "prune the tree and start from the current street". The fastest
   heads-up postflop candidate measured here, and callable from Python by
   writing a command file — but whether anything is called at decision time is
   not this file's to say; see the recommendation.
2. **phevaluator** — plain `pip install phevaluator`, 0.9 to 2.6 M 7-card
   hands/s from Python, no build step and no cap on the number of players.
   Promoted above OMPEval because it is the only thing on this list that is
   working five seconds after the install finishes. Whether anything ranks
   hands at decision time, and if so what, is not this file's to say; see the
   recommendation. `treys` is not the comparison for that question in any
   case, because `CLAUDE.md:19` already keeps it to tests only.
3. **OMPEval** — 160 to 312 M hands/s of multiway Monte-Carlo equity, which is
   free speed compared with anything in Python, but **hard-capped at six
   players** (`omp/Constants.h:6`) and it needs a C++ patch and a wrapper you
   compile yourself. At 7 to 9 seats it cannot be handed every live range at
   once, which is exactly the table size this project is aiming at.
4. **postflop-solver** — 0.46% of pot on a turn spot in 0.19 to 0.23 s here,
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
6. **MonkerGuy .txt ranges** ($69 one-time for a single 6-max 100bb hold'em
   sim, up to $319 for the 8-max tournament pack) or the free 9-max charts
   — precomputed preflop for every table size, no solving needed.
7. **MonkerSolver** (EUR 499 one-time, macOS) — solves **any street with any
   number of players**, which nothing else here does natively on a Mac at a
   one-time price. Not on the decision path: no external program control — its
   scripting tool batches a board list by hand and overnight (entry 16) — and
   multiway postflop trees take RAM and hours. Buy it only for offline study.
8. **Holdem Solver** (free beta, macOS, 2 to 9 players) — the other Mac tool
   that solves multiway postflop, and free while the beta lasts, but the
   vendor, licence and terms are all UNVERIFIED and there is no scripting.
   That last point is what keeps it off the decision path; how long its
   multiway trees take is UNVERIFIED too, and the one run the vendor shows was
   still converging after 9 min 05 s. Offline study of specific multiway
   spots, not decision time.
9. **Pokerai API** — instant 6-max GTO answers over HTTP with a free tier;
   good for testing the bot's judgment against a reference, barred from live
   real-money use by its terms.
10. **GTO Wizard** top tier — best opponent modelling anywhere (Profiles,
    Nodelocking 2.0) and 9-player preflop, but a monthly subscription
    ($229/month annual or $279/month monthly until 15 October 2026, $289 and
    $359 after it; see entry 17) with no API; a study tool only.
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
choose the bot's architecture, because most of what follows turns on a rule
question and on a competing proposal in another document. Only one piece is
this file's to settle, and it is about speed rather than about what decides a
hand. So what follows is written as **input to the reconciliation of the four
research sweeps against `CLAUDE.md`**, with the settled parts marked as settled
and the open parts left open.

**Settled by measurement: timings only, no tool nominated.**

- **Hand ranking and equity: what the stopwatch says.** Three things were
  timed on this machine, and this is all of it. `phevaluator` ranks 7-card
  hands **5 to 15 times faster than `treys`** from the same Python, and
  installs with one command. OMPEval is faster again once a Monte-Carlo loop
  is hot, and carries a **hard cap of 6 players** (`omp/Constants.h:6`): at 7,
  8 or 9 seats it cannot be handed every live range at once. `CLAUDE.md:19`
  already keeps `treys` off the bot's decision path — it is the ground-truth
  oracle for tests and nothing else — so nothing at runtime is being displaced
  by any of that. These are speeds, not a nomination; which evaluator the bot
  calls when it has to act is in the open list below.

**Open, and for the reconciliation to decide — not for this file.**

- **What plays heads-up postflop.** TexasSolver is the fastest thing measured
  here for it, and that measurement stands: **0.74% of pot on a full-range
  turn-and-river spot in 0.56 to 0.71 s of solving, 5.5 s wall measured and
  the earlier run noted only as about 8 s**, which is
  what says a pruned tree fits inside a live decision, while the flop solve
  (Appendix A) is what says the tree must be pruned. An earlier draft of this
  file called that settled and wrote "Heads-up postflop: TexasSolver, called at
  decision time" into the settled list. **It is not settled, and this file had
  no authority to settle it.** Two reasons:
  - `ENGINE_ALTERNATIVES.md` (under revision) recommends switching the whole
    engine to OpenSpiel's `universal_poker` and computing the decision during
    the hand, which is a different answer to the same question and covers
    heads-up as well as multiway. Naming a heads-up engine here would decide
    part of that switch on a tool survey's say-so.
  - Calling TexasSolver at decision time means building its command file from
    the live spot: board, pot, stacks, one or two bet sizes, **and a range for
    the opponent**. The first four are bookkeeping. The range is not. Nothing
    in this survey produces it: TexasSolver takes a range as input and never
    infers one, and the opponent model can supply counted rates and a bucket
    but `CLAUDE.md:26` reserves **"Assigning a range to an opponent"** to the
    engine, exactly as it reserves choosing an action. So whatever turns "this
    player folds to 62% of continuation bets" into a weighted list of holdings
    would be code we write doing a job the rules give the engine. The earlier
    draft's sentence "Nothing here is our own poker judgment: the strategy
    comes out of a borrowed solver" was true of the strategy and false of its
    input; **it is withdrawn.** Who produces the opponent range, and whether
    writing that code needs a carve-out, goes to the same reconciliation as
    the rule set below.
- **Where the bot's preflop play comes from.** The market fact is in Part 4 and
  is not in doubt: preflop ranges for 2 to 9 seats are available free or for
  $69 to $319, so no preflop solving is needed to obtain them. What that does
  not settle is what the bot plays preflop from when it has to act. That is a
  decision-path choice of the same class as the heads-up engine above —
  `CLAUDE.md:28` reserves **"Producing the strategy itself"** to the engine —
  and nothing measured here bears on it. An earlier draft of this file put
  "buy or transcribe ranges for 2 to 9 seats rather than solving preflop at
  all" in the settled list above. **No measurement stood behind it, and it is
  moved here.**
- **Which evaluator the bot calls at decision time.** Naming one is the same
  class of decision as naming the heads-up engine above: it is a choice about
  what the bot calls when it has to act, and no project file records such a
  choice today. An earlier draft of this file put "where a runtime path needs
  an evaluator, use phevaluator" in the settled list and repeated it in the
  shortlist. **That is a nomination, not a measurement, and this file had no
  authority to make it.** The measurement is in the settled list above and
  stands: phevaluator is 5 to 15 times faster than `treys` from Python, and
  OMPEval is faster than either below 7 seats. What that does not say is
  whether anything ranks hands on the decision path at all, or which thing
  does it. That is for the reconciliation.
- **What plays multiway postflop.** The obvious fit with the tools above is an
  equity-driven rule set biased by the opponent model. Say plainly what that
  is: **code we would write that picks the action**, with the opponent model
  as its input. `CLAUDE.md:15-17` forbids hand-rolled decision logic in place
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
  betting abstraction — cutting the choices down to a four-move menu buys it
  far more play-outs per decision than letting it bet any amount does, and it
  calls the any-amount search mostly noise — and that it needs the same
  rule carve-out as the rule set
  above, because the code that compares the play-outs is also code that picks
  the action. No play-out counts are quoted here on purpose: that document is
  still a draft under review, its own counts have already moved once while
  this file cited them, and its point above does not depend on them. Read the
  figures there, not here. So the honest statement is: **a multiway
  decision-time option
  exists and is measured; what does not exist is an affordable multiway
  postflop *solver* on a Mac that another program can drive.** Which of the
  two covers multiway is
  exactly what the reconciliation has to settle, and they are not alternatives
  within this document's authority.
- **GTOpen's player types.** Its promise (+40 to +80 bb/100 when the read is
  right) and its warning (a loss running from 0 to 461 bb/100 when it is
  wrong, depending on which wrong read it is — see entry 3 for what the table
  actually says) are the author's own numbers, not ours, and they are results
  he recorded with his older fixed opponent profiles rather than predictions
  for the app he ships today (entry 3 quotes the note on his page that says
  so). Its definitions are
  worth borrowing for
  `OPPONENT_MODEL_DESIGN.md`; adopting its exploit solves is a licence
  question (it has no licence file) as well as a rule question.

The settled part is a set of stopwatch readings, so it adopts no code and costs
nothing at all. The code that was timed for it — OMPEval (ISC licence) and
`phevaluator` (Apache-2.0) — is free, and both of those licences are
compatible with this project's own GPL-3.0, so adopting either would also cost
nothing if the reconciliation ever decided to. The open parts
cost at most an optional $69 to $319 range pack
and, if the reconciliation goes the way of the tools measured here, add AGPL
code (TexasSolver, postflop-solver), which GPL-3.0 may take in — but the AGPL
network clause would then ride along with that part, and it would bite if the
bot were ever offered to others over a network.

---

## Appendix A. Measured timings on this Mac (Apple M4, 10 cores)

Wall-clock speed on a laptop moves by tens of percent, and sometimes by a
factor of two, with whatever else the machine is doing. Other work shares this
laptop, so every timing **re-taken this round** — the first, third, fourth and
fifth rows below — was started only once the 1-minute load average was under
4.0, and that load is recorded beside it. One row is the exception to both
halves of that sentence: the sixth, the GTOpen build, was re-taken this round
but its start load was not recorded. The remaining rows without a load beside
them are carried from earlier rounds, when the load was not recorded; read
those as looser. Where a measurement was repeated the range is given, and the
range is the honest figure.

| Tool | Spot | Result | Time (1-minute load at the start) |
| --- | --- | --- | --- |
| TexasSolver 0.2.0 | turn+river, 93 vs 95 hand classes (606 combinations each), one 66% bet, 60% raise, all-in | 0.74% exploitability, iter 51 | 0.56 to 0.71 s solve, 5.5 s wall measured (load 3.40 on the fresh run); the earlier run's wall clock noted only as about 8 s |
| TexasSolver 0.2.0 | bundled 3-street sample, 2 vs 2 hand classes | 0.44%, iter 71 | 10.5 s solve, 16.4 s wall |
| TexasSolver 0.2.0 | flop+turn+river, same full ranges, 33/75% bets, 10 threads | iterations 0 and 2 printed on every run and 3 on two of the three (see the per-run table below); 226.39% of pot at iteration 0 and 221.72% at iteration 2 on all three runs | stopped at 421.4 / 422.5 / 423.1 s wall, 493.4 / 462.2 / 699.8 s CPU, 4.95 / 5.41 / 5.79 GiB over three runs (loads 3.29, 3.75, and not recorded on the third) |
| postflop-solver | turn+river, ~40% vs ~40% ranges, 60%/geo/all-in, 2.5x raises | 0.46% of pot (0.91 chips of 200), iter 100 | 0.19 to 0.23 s wall, 1.53 to 1.59 s CPU over five runs (load 3.40) |
| GTOpen solve-cli | `bench_spot.json` flop, 3 streets, 1.35M nodes, CPU-only | 1.233% of pot, iter 100 | 76.0 and 79.3 s wall, 1.4 GB (load 3.96 and 3.58) |
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
420 s. Three runs went to that deadline, and each one's stdout is published
beside the command file:

| Run | Wall | CPU | Cores busy of 10 | Peak memory | Iterations printed | 1-minute load at the start | Runner stdout |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 423.1 s | 699.8 s | 1.65 | 5.79 GiB | 0, 2, 3 | not recorded | `texassolver_flop_run1_423s.log` |
| 2 | 421.4 s | 493.4 s | 1.17 | 4.95 GiB | 0, 2 | 3.29, recorded in `texassolver_flop_run2_load_note.txt` | `texassolver_flop_run2_421s.log` |
| 3 | 422.5 s | 462.2 s | 1.09 | 5.41 GiB | 0, 2, 3 | 3.75 | `texassolver_flop_run3_422s_instrumented.log` |

All three printed **exploitability 226.39% of pot at iteration 0 and 221.72%
at iteration 2**, and none printed anything past iteration 3. A solve that
needs 1% and is at 222% after seven minutes is not slow, it is not started.

Two shorter probes of the same command file are recorded separately and are
not part of that population: 181.5 s wall / 302.4 s CPU / 1.67 cores /
3.44 GiB, and 151.6 s wall / 343.5 s CPU / 2.27 cores / 4.43 GiB. Each printed
iterations 0 and 2 and the iteration-0 exploitability of 226.39% before being
stopped; neither recorded a start load, so read them as looser still. The
3.4 GiB memory floor an earlier draft of this file quoted across "four runs"
is the 181 s probe's figure, not a full run's; the three full runs used 4.95
to 5.79 GiB. That draft also described the population as three runs of mine
and one independent re-run during review; the run outputs do not record who
started them, so no attribution is claimed here.

Why only one or two cores are busy is **not** answered here, and an earlier
draft of this file answered it anyway, with "the memory ceiling, not idle
threads". Run 3 of the three was instrumented to check that: over
422.5 s the solver process took **1,653 major page faults** (the kind served
from disk), about four a second. It is not stalling on its own pages coming
back off disk, so that explanation is withdrawn rather than restated. The
machine around it was under heavy memory pressure the whole time — swap in use
4.56 GB rising to 11.68 GB, the swap file grown from 6 GB to 12 GB, 5.27
million pages written out machine-wide — but other agents share this laptop
and none of that is attributable to the solve. The figure that survives is the
one that was measured: **1.1 to 1.7 cores busy of 10, cause not established.**

GTOpen `solve-cli bench_spot.json 100 0.05` on this Mac, CPU-only: tree of
1,346,813 nodes built in 0.04 to 0.06 s, 257 vs 319 card combinations,
1,386 MB of solver arenas (compressed), **1.233% of pot exploitability at 100
iterations in 76.0 s and 79.3 s** on two re-runs today (loads 3.96 and 3.58),
bit-identical at every printed iteration. Two earlier runs of the same command
on a far busier machine took 110 s and 179.1 s, and the author's 12-thread
desktop did it in 61 s. That is a full three-street flop tree with two
in-position flop sizes: **one to three minutes for a study-grade flop solve,
about 76 to 79 s when little else is running**, which confirms the pattern
above. Full flop trees are minutes at best and unreachable at worst; turn and
river trees are under a second.

## Appendix B. What I ran

```
# evaluators (clean venv, Python 3.13.15)
pip install phevaluator                  # plain install, 0.6.0 arm64 wheel, no flags
pip install treys                        # eval7 and pyrust-poker failed to build
# Both benchmark scripts are published under research/solvers/.
python research/solvers/bench_treys.py   # 165,275 hands/s
python research/solvers/bench_phe.py     # 2,550,203 hands/s idle, 0.89-1.44 M/s under
                                         # load (ints); 800,485 (strings)

# OMPEval (clang 16, needs constexpr patch in omp/Random.h)
make CXXFLAGS="-O3 -std=c++17 -Wall -pthread"
./evbench   # 61.5 M evals/s
./eqbench   # 3-way MC 311.7 M hands/s idle, 160-177 M/s under load (10 threads);
            # HU exact flop 2.8 ms.  Player cap: omp/Constants.h:6 MAX_PLAYERS = 6

# TexasSolver v0.2.0 macOS release (unzipped from the GitHub release).  Both
# command files below are published under research/solvers/; the solver
# resolves its dump path relative to its working directory, so copy the
# command file in beside console_solver before running it.
./console_solver -i resources/text/commandline_sample_input.txt   # 16.4 s wall
cp research/solvers/texassolver_turn_full_ranges.txt <release-dir>/turn_input.txt
./console_solver -i turn_input.txt   # 5.45 s wall at load 3.40 (earlier: 8 s);
    # 0.74% of pot at iteration 51, 0.561 s solver time.  Raw stdout of this
    # exact run: research/solvers/texassolver_turn_run.log; the wall time and
    # the load, which the solver does not print, are recorded beside it in
    # research/solvers/texassolver_turn_run_note.txt
python3 research/solvers/run_texassolver_flop.py <release-dir> 420
    # Three runs to the deadline; the runner's stdout for each is published,
    # one file per run:
    #   research/solvers/texassolver_flop_run1_423s.log
    #     423.1 s wall, 699.8 s CPU, 1.65 cores, 5.79 GiB, iters 0/2/3, start
    #     load not recorded
    #   research/solvers/texassolver_flop_run2_421s.log
    #     421.4 s wall, 493.4 s CPU, 1.17 cores, 4.95 GiB, iters 0/2, load 3.29
    #     (that load is in research/solvers/texassolver_flop_run2_load_note.txt,
    #     copied from the probe line the solver itself does not print)
    #   research/solvers/texassolver_flop_run3_422s_instrumented.log
    #     422.5 s wall, 462.2 s CPU, 1.09 cores, 5.41 GiB, iters 0/2/3, load
    #     3.75; this is the run carrying the page-fault and swap sampling
    # All three: 226.39% of pot at iteration 0, 221.72% at iteration 2.
    # Two shorter probes of the same command file, not part of that three:
    # 181.5 s / 302.4 s CPU / 1.67 cores / 3.44 GiB and 151.6 s / 343.5 s CPU /
    # 2.27 cores / 4.43 GiB, each printing 226.39% at iteration 0 only, start
    # loads not recorded

# Rust toolchain: NOT installed on this Mac.  No cargo, rustc, rustup or
# Homebrew is on the command path.  Both Rust projects below were built with a
# private toolchain unpacked into a scratch directory and reached only through
# these three variables, so nothing was written to the operator's home:
export RUSTUP_HOME=<scratch>/rustup CARGO_HOME=<scratch>/cargo
export PATH=<scratch>/cargo/bin:$PATH
rustup toolchain list    # stable (1.98.1) default, plus 1.75.0 and 1.85.0

# postflop-solver: rustc 1.85.0 (4d91de4e4 2025-02-17), bincode pinned
#   =2.0.0-rc.3 on Cargo.toml line 12; bincode_derive is not in Cargo.toml at
#   all, it arrives as bincode's own dependency and Cargo.lock holds it at the
#   same 2.0.0-rc.3
cargo +1.85.0 build --release --example basic    # 19.1 s, dependencies cached
./target/release/examples/basic  # 0.19-0.23 s wall, 1.53-1.59 s CPU over five
                                 # runs at load 3.40; exploitability 0.91 of a
                                 # pot of 200 (0.46%) at iteration 100

# GTOpen: rustc 1.98.1 (48a229cea 2026-09-01), CPU-only
CARGO_TARGET_DIR=<scratch>/GTOpen/target_clean cargo build --release -p server
    # 1 min 53 s wall, 261 s CPU (the rebuild, today; the first build took
    # 3 min 20 s)
./target/release/gto-server & curl 127.0.0.1:3737/api/status   # {"state":"idle","gpu":false,...}
./target/release/solve-cli bench_spot.json 100 0.05
    # 1.233% of pot at iteration 100 in 76.0 s and 79.3 s, two re-runs started
    # at 1-minute loads of 3.96 and 3.58, bit-identical at every printed
    # iteration (earlier runs on a far busier machine: 110 s and 179.1 s)

# What the flop solve waits on (one instrumented run of the command above):
#   1,653 major page faults in 422.5 s -- it is not paging off disk.
#   Sampled every 15 s with `vm_stat` and `sysctl -n vm.swapusage`; swap in use
#   rose 4.56 -> 11.68 GB and the swap file 6 -> 12 GB machine-wide, but other
#   agents share this laptop, so none of that is attributable to the solve.

# Vendor pages re-read 2026-09-17.  These are page reads, not timings, and they
# were taken on the operator's PC rather than the Mac; each was fetched with
# curl and a desktop browser user-agent and returned HTTP 200.
#   https://piosolver.com/products   "PioSOLVER 3.0 Pro ... € 450.00
#     (+applicable taxes)", "PioSOLVER 3.0 Edge ... € 800.00 (+applicable
#     taxes)", both "1 year of software updates" and "Can be used on two
#     computers"
#   https://gtoplus.com/purchase   "Main License: $75  Second License: $40
#     Upgrade from CREV: $50" and "The registration fee is one-time. All
#     future updates are included. Taxes may still be added depending on
#     your location."
#   https://jesolver.com/ and https://jesolver.com/index.html   one byte each,
#     no price anywhere; https://jesolver.com/cmdref.html is a command list
#     with no price either
#   https://www.preflopwizard.app/blog/9-max-preflop-chart   no PDF and no
#     chart download; the only downloads offered are its iOS and Android apps
#   https://www.monkerguy.com/   product names carry no commas: "6-MAX 100BB
#     2.5x Open" $69, "9 PLAYERS NLH 100bb - 2.5x Open" $199, "8max (BB ANTE)
#     MTT Pack (10bb-100bb)" $319
```
