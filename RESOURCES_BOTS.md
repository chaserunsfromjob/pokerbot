# Ready-made poker bots, bot frameworks, and pre-trained strategies

Research survey, September 2026. Companion to `ENGINE_ALTERNATIVES.md` (poker
engines: OpenSpiel, RLCard as an engine, PyPokerEngine, PokerKit, clubs, PokerRL).
This file covers the other side: things that already *play*, already carry a
strategy, or already read a table off a screen.

Every URL below was visited on 2026-09-15. Stars, last-activity dates,
licences and repository file listings come from the GitHub API on that date
unless marked otherwise. Anything I could not confirm is marked **UNVERIFIED**,
and a rating that would have rested on it is marked **?** rather than guessed.

## 1. Summary for a non-programmer

The question was: can we adopt a finished poker bot, or a finished strategy,
instead of building one? The short answer:

- **No single finished thing does what we want.** Nothing open or paid that I
  could verify plays no-limit hold'em at every size from 2 to 9 players, adjusts
  to named opponents, runs on this machine (an Apple M4 laptop with 16 GB of
  memory), and is ready in hours. Each candidate covers two or three of those,
  never all five.
- **The nearest thing to a finished multi-player strategy does not fit this
  laptop's memory.** NoRegrets trains a 2-to-6-player no-limit strategy in
  about an hour — but on a 16-core Apple Silicon machine with **128 GB** of
  memory, and its own published results record training runs holding **36 to
  50 GB** of memory at once, with a finished strategy file of 4.34 GB. This
  laptop has 16 GB in total. Building the software on a Mac is *not* the
  problem: the author's own measurements were taken on one. Memory is. The
  configurations small enough to fit here are the ones the same results file
  says are too under-trained to play multi-player pots.
- **A proven design for "play differently against this named player" exists,
  in software we cannot run.** OpenHoldem looks each opponent's screen name up
  in a hand-history database and exposes their habits as named quantities its
  rule language can branch on. That is the pattern the operator asked for; the
  program itself is Windows-only C++.
- **Every finished table reader is Windows-bound.** The one project advertised
  as Mac-native, poker-gto-rt, **contains no code at all**: its repository is a
  README file and a licence, 4,573 bytes together. It is an advertisement for
  work that was never published.
- **Nothing surveyed plays 7, 8 or 9 seats with real bet sizing.** Everything
  with a trained strategy stops at six. The operator's second priority, 8 and
  9 handed, is an open gap this survey cannot close.
- **This survey does not decide how the bot thinks.** Whether the strategy is
  worked out in advance or worked out during the hand is a question
  `ENGINE_ALTERNATIVES.md` answers differently, and settling it needs those
  documents read together, not a line here. Section 5 below says so at length.
- **The famous bots are not on the table.** Pluribus, Libratus, DeepStack and
  Supremus were never released. The open re-creations either ship no trained
  strategy (DeepHoldem, Deep CFR 6-player), are heads-up only (DecisionHoldem,
  Slumbot), or sell the trained strategy commercially (NoRegrets).
- **Paid products are Windows or Android, not Mac,** and none exposes an
  interface a program can call. PokerSnowie ($29.90/month) is a study tool
  that refuses to run beside a poker client and does not adapt to opponents.
  PokerBotAI (from $700 plus per-hand fees) claims per-opponent profiling on
  mobile poker apps but is closed and runs on Android/Windows.
- **Slumbot is free and live** (I got a hand dealt from its API during this
  survey) but it is a heads-up opponent you play against, not a strategy you
  can ask about your own spots.

Plain-words glossary for terms used below:

- *Blueprint*: a big pre-computed table of "in this kind of spot, do this this
  often". Computing it is the slow part; using it is fast.
- *Screen scraping / table capture*: taking screenshots of the poker app and
  turning the picture into numbers (cards, stacks, bets, whose turn).
- *Heads-up (HU)*: two players only. *6-max*: up to six seats. *Full ring*:
  nine or ten seats.
- *GTO*: a balanced strategy that cannot be beaten long-term but does not
  punish weak opponents as hard as a tailored ("exploitative") one.
- *VPIP / PFR / AF*: standard per-player statistics (how often a player puts
  money in before the flop, how often they raise, how aggressive they are).
  These are what "exploiting a named opponent" is built from.
- *mbb/hand, bb/100*: win-rate units. Positive means winning.

## 2. Rating key

Each resource gets a mark on five criteria:

| Letter | Criterion | ✓ | ~ | ✗ |
| --- | --- | --- | --- | --- |
| a | Plays 2 to 9 players | full range | part of the range | one size only |
| b | True no-limit bet sizing | yes | abstracted / few sizes | limit or not stated |
| c | Exploits a specific opponent by identity | built in, keyed by name | some opponent modelling, not by name | none |
| d | Reachable in hours on **this** laptop (Apple M4, 16 GB memory), Python preferred | yes | possible with real work (other language, VM) | days of compute, more memory than the machine has, or a dead platform |
| e | Fits private use (licence and price) | free and open, or affordable | paid but affordable, or copyleft that is fine for private use | closed with no purchase path |

"Runs on macOS / Python?" is answered literally. GPL/AGPL is fine for us
because the project is never distributed.

Two rules about the marks themselves:

- **A mark rests only on a fact I checked.** Where the fact a criterion turns
  on could not be verified, the criterion gets **?** and says what is missing.
  A ✓ or ~ never stands on a vendor's claim or on a guess.
- **The operator's table sizes are 2 to 9, mostly 6-handed, with 8 and 9 as
  the second priority.** Criterion (a) is scored against that, so "6-max only"
  is a real gap, not a detail.

## 3. Resources, verified

### 3.1 OpenHoldem (original) and openholdem-next (community fork)

- URLs: https://github.com/OpenHoldem/openholdembot and
  https://github.com/openholdem-next/openholdembot
- What: the long-running open-source bot *framework*. It reads a Windows poker
  client's window, exposes everything as symbols, and runs whatever logic you
  write in its OpenPPL rule language. It ships no strategy ("it does not come
  with a strategy, and it never will").
- Last activity: original pushed 2025-04-14, last release 14.0.2 on 2021-12-26;
  fork pushed 2026-09-12 with releases v14.1.0.0 (2026-08-22) and v14.1.1.0
  (2026-09-12). Stars: 255 (original), 1 (fork). Licence: GPLv3.
- Runs on macOS / Python? No. C++, Windows 7+ 32-bit desktop clients only,
  Visual Studio 2017+ to build. Would need a Windows virtual machine on the Mac.
- Plays today? Yes on Windows desktop clients it has a table map for, any
  table size the map covers, limit and no-limit, with OpenPPL profiles.
- Per-opponent adjustment: **yes, by name.** The source contains
  `CSymbolEnginePokerTracker.cpp`, which fills per-chair `pt_` symbols (VPIP,
  PFR and so on) looked up from a PokerTracker database by the player's screen
  name (`pt_name`, `ClearAllStatsOfChangedPlayers`). Profiles then branch on
  those symbols. This is the reference design for what the operator asked for.
- Ratings: a ✓ (checked in the source, not taken on trust:
  `Shared/MagicNumbers/MagicNumbers.h:67-76` sets `kMaxNumberOfPlayers = 10`
  with chairs 0 to 9, so 2 to 9 seats are inside the range it maps) · b ✓
  (`CAutoplayer.cpp:500-518` reads whatever number the `f$betsize` formula
  evaluates to and types it into the bet box; `SwagAdjustment.cpp` clamps it
  with `MinimumBetsizeDueToPreviousRaise` and
  `MaximumPossibleBetsizeBecauseOfBalance`, i.e. an arbitrary amount between
  the legal minimum and maximum) · c ✓ · d ✗ (Windows-only, C++, needs a VM
  and a paid tracker database) · e ✓.

### 3.2 dickreuter/Poker ("DeeperMind pokerbot")

- URL: https://github.com/dickreuter/Poker
- What: a Python bot that plays for real on PokerStars, PartyPoker and GGPoker
  by screenshotting the table (OpenCV template matching, optional neural
  network), computing hand equity by Monte Carlo simulation, and choosing
  actions from a tunable strategy (a "strategy editor" plus a genetic
  algorithm that mutates the parameters).
- Last activity: pushed 2025-06-26. Stars: 2,462. Licence: GPL-3.0.
- Runs on macOS / Python? Python 3.11, but the README states "The current
  version Only works on windows" (Windows 10 x64, 1920x1080, tesserocr Windows
  wheel, poker client in a VM). The decision code is plain Python and portable;
  the scraper and mouse control are Windows-bound.
- Plays today? "Currently the bot only works for tables with 6 players", and
  the README admits the official table maps for PokerStars/PartyPoker have
  drifted. "Any other table can be mapped as well" through its template GUI.
  No-limit: yes.
- Per-opponent adjustment: **no by-name model.** Decisions use equity, pot
  odds, and "behaviour in the previous rounds" of the current hand. No
  persistent per-player statistics.
- Ratings: a ✗ (6 only) · b ~ (**a fixed menu**, the same shape as DeepHoldem's
  in 3.7. `poker/decisionmaker/decisionmaker.py:23` is the whole action set —
  `bet1, bet2, bet3, bet4, bet_bluff = ['Bet','BetPlus','Bet half pot','Bet
  pot','Bet Bluff']` — and `decisionmaker.py:562-572` attaches the amounts:
  the minimum bet; the minimum bet increased by a fixed multiple of itself
  (the `BetPlusInc` setting); half the pot, for both `bet3` and the bluff;
  and the pot.
  `poker/tools/mouse_mover.py:179-214` then executes them by clicking the poker
  client's own half-pot, pot or all-in button, or a counted number of increment
  clicks, so no other amount can be entered. The tunable parameters and the
  genetic algorithm decide *which* of those sizes fires and when, not what the
  sizes are.) · c ✗ · d ~ (Python, but scraper is Windows-only) · e ✓.

### 3.3 Slumbot (live heads-up bot with public API) and slumbot2019 (its solver code)

- URLs: https://www.slumbot.com/ (API documented at
  https://slumbot.com/sample_api.py), https://github.com/ericgjackson/slumbot2019
- What: Eric Jackson's ACPC-champion heads-up no-limit bot, playable for free
  through three HTTP endpoints (`/slumbot/api/login`, `/new_hand`, `/act`).
  Blinds 50/100, 200 big-blind stacks, stacks reset each hand.
- Verified live: a `POST /slumbot/api/new_hand` during this survey returned
  `{"action": "b200", "client_pos": 0, "hole_cards": ["6c","3d"], ...}`.
- What is released: the C++ solver code (CFR+, MCCFR, subgame resolving,
  abstractions; MIT; 177 stars; last push 2023-09-18). **The trained strategy
  files are not released**, and the API does not let you ask "what would you
  do with these cards on this board": the server deals the hand, so you can
  only observe what it does in the spots it deals you.
- Runs on macOS / Python? The API needs only `requests`. The solver is C++
  and would need days of compute to produce a strategy of its own.
- Plays today? Yes, heads-up only, no-limit.
- Per-opponent adjustment: none (it is a fixed near-GTO strategy).
- Ratings: a ✗ (2 only) · b ~ (it is a no-limit game and the API accepts any
  bet size you send, but Slumbot's own sizes come from a betting abstraction —
  a fixed menu — per `slumbot2019`'s documentation) · c ✗ · d ✓ (as a test
  opponent) · e ✓.
- Use: a free, strong yardstick for the 2-player case. Every serious open
  project below benchmarks against it.

### 3.4 NoRegrets (conorarmstrong/noregrets), Pluribus-style, Rust

- URL: https://github.com/conorarmstrong/noregrets
- What: an independent Pluribus-style bot for 2 to 6 player no-limit hold'em.
  It trains a blueprint in advance, then, when it is its turn, re-works the
  current spot on the spot: it re-solves the hand from here forward, looking
  only a street or two ahead instead of to the end, and guesses what each
  opponent could be holding from how they have bet so far. Looking a fixed
  distance ahead and stopping is what the literature calls *depth-limited
  online re-solving*; NoRegrets calls it `play --search`, with a time budget
  per decision (default 2 seconds). "The bot plays any table size from 2 to 6;
  one blueprint covers every seat."
- Last activity: pushed 2026-09-08 (created 2025-06-21). Stars: 19. Licence:
  MIT for the public code, but "it is not the current version" (public release
  lags the private repo by about twelve months) and "Trained blueprints and
  other pretrained artifacts are never published here and are available under a
  commercial licence only" (contact conorarmstrong@gmail.com; price UNVERIFIED).
- Training cost stated in README: "200M iterations ≈ 1 hour on 16 cores";
  400M took 1h56m.
- **macOS is not in doubt; memory is the blocker.** Its `BASELINES.md` names
  the machine every headline number was measured on: "16 cores (Apple Silicon,
  Darwin 25.5.0)" and, later, "16-core Apple Silicon, 128GB". So the project
  already builds and trains on a Mac. What it needs is memory this laptop does
  not have:
  - the published blueprint, `blueprint.bin` from `train --iters 200000000`,
    is **4,343,417,226 bytes** (4.34 GB) on disk, holding 101 million stored
    decisions across 128.5 million distinct situations;
  - `BASELINES.md` records training runs at comparable size holding **36 to
    45 GB** of live memory ("150-210M infosets, 36-45 GB RSS: memory-bound"),
    and one variant at "~50GB RSS" with 142.4M situations. What those runs
    report is how much memory the program is actually holding while it runs,
    as against how big the file it finally writes is; the name for it is
    resident set size, which those quotations shorten to RSS. The machine has
    **16 GB** in total, some of it already spoken for.
  - There is no statement of a memory requirement anywhere in the README, and
    no run in `BASELINES.md` reports a resident set size under ~36 GB, so the
    smallest footprint the published recipe can reach is **unknown**, not
    small.
- The knobs that would shrink it, and what the repo says they cost: `--iters`
  (fewer training passes: a 25M-pass checkpoint holds 60.5M situations against
  121.1M at 200M, so on the order of half the memory; at the ratio those runs
  imply — 36 to 45 GB for 150 to 210M situations — that extrapolates to
  roughly 13 to 15 GB, which is *just* inside 16 GB on an idle machine and is
  an extrapolation rather than a measurement. Meanwhile the same file measures
  the multi-player leak at 25M as nearly three times worse (+2,480 against
  +929 mbb/hand to a best-responder) and warns that "30M-scale multiway
  numbers are... dominated by dilution and should not be used to rank multiway
  play", because such blueprints reach untrained multi-player rivers 32-69% of
  the time and "play a calling station there"); `--buckets` (card grouping,
  12 by default, and **the wrong direction anyway**: their 36-bucket
  run at equal iterations came out *worse* (−1128.2 against −719.0 mbb/hand vs
  Slumbot, `BASELINES.md:303-312`), while the 24-bucket run — bundled with
  OCHS features and a wider bet menu, so not a clean test of buckets — came
  out at best slightly *better* and their own verdict on it is "modernization
  is a SMALL, NON-SIGNIFICANT improvement" (`BASELINES.md:514-530`). More
  important here: 24 buckets pushed that run to **521.7M situations, which
  their own note calls five times the baseline's count** (`BASELINES.md:469`),
  with "heavy visit dilution" as the cost, so raising the bucket count
  costs memory rather than saving it, and lowering it below 12 is untested);
  `--menu pluribus` (the coarse bet menu, already the default,
  "2.5× smaller"); `--bucket-table` (speed, not memory). Nothing here is
  measured in gigabytes by the authors — the memory cost of a reduced
  configuration is ours to measure.
- Plays today? Yes: `play` gives an interactive terminal game, you in seat 0
  against bots. No-limit: yes. No screen capture.
- Strength evidence: against Slumbot heads-up it *lost*, -714.5 ±331.5
  mbb/hand blueprint-only and -1771 ±471.8 with search on, over 10,000 hands.
  The README attributes this to range tracking assuming the opponent plays its
  own blueprint. That is a 2-player result against a top bot, not a result
  against humans; treat the strength as unproven.
- Per-opponent adjustment: partial, and interesting for us because the *engine*
  does the adjusting. `train --rnr-model` and `--rnr-opponent` retrain the
  strategy to punish a described opponent while staying close to safe play —
  the trade-off is a dial, `--rnr-p`, from 0 (play the safe strategy) to 1
  (attack that opponent as hard as possible). Attacking a known opponent while
  keeping a leash on how far you stray from safe play is what the literature
  calls a *restricted Nash response*. `clone` can build the opponent it trains
  against out of a log of hands that opponent played. But the described
  opponent has to be chosen in advance: the README states that the models are
  "pre-specified, pre-trained ... chosen ahead of time" and that "There is no
  online estimation of an unknown live opponent's tendencies from observed
  play" (`README.md:846-850`), and nothing is keyed by name.
- Ratings: a ~ (2 to 6, not 7 to 9) · b ~ (the default bet menu is Pluribus's
  coarse one — half pot, pot, all-in first in, pot or all-in to raise — which
  is abstracted sizing by this document's key, not true no-limit; the wider
  menu is 6-7 sizes and their own tests rate it worse) · c ~ (a bounded
  exploiter of an opponent named in advance; nothing learned at the table) ·
  d ✗ (**the published run needs 36-50 GB; the machine has 16 GB.** A cut-down
  run might just fit by extrapolation, but no measurement exists and the
  repository's own results say runs that small cannot be trusted multi-player)
  · e ✓ (code) /
  ~ (their blueprints are paid).

### 3.5 Deep CFR for 6-player NLHE (dberweger2017)

- URL: https://github.com/dberweger2017/deepcfr-texas-no-limit-holdem-6-players
- What: a Python 3.11 Deep CFR research project for six-handed no-limit, with
  a headless agent API, decision replay, and "identity-owned records" per
  player for opponent modelling across changing line-ups. Four- and five-handed
  are "first-class" configurations. Its contracts promise "exact legal bet
  candidates", but "learn meaningful bet sizes" is listed under work still to
  do, so unrestricted sizing is an intention, not a shipped property.
- Last activity: pushed 2026-09-15 (very active). Stars: 109. Licence: MIT.
  Also on PyPI as `deepcfr-poker`.
- Runs on macOS / Python? Python 3.11 + Rust toolchain (its engine is a pinned
  fork of the Rust `pokers` crate) + Torch 2.x CPU or GPU. Should build on a
  Mac; UNVERIFIED.
- Plays today? Not as a strong player. README: "No current model has
  demonstrated professional-level Hold'em strength", no checkpoints shipped,
  no completed full-game training reported (small-game validation only on
  rented CPU). No GUI or live-table hookup.
- Per-opponent adjustment: designed in (identity-keyed histories) but
  untrained.
- Ratings: a ~ (4 to 6) · b ? (no-limit by contract, but sizing is unlearned
  and untrained, so nothing to judge) · c ~ (designed, not proven) · d ✗ (no
  model; training cost unknown, Deep CFR is typically days) · e ✓.

### 3.6 RLCard no-limit hold'em environment and its model zoo

- URLs: https://github.com/datamllab/rlcard,
  https://github.com/datamllab/rlcard-showdown
- What: the RL toolkit (see `ENGINE_ALTERNATIVES.md` for the engine view).
  Checked here only for *pre-trained* no-limit hold'em players.
- Finding: **there is no pre-trained no-limit hold'em model.** The registry in
  `rlcard/models/__init__.py` lists `leduc-holdem-cfr`, `leduc-holdem-rule-v1/2`,
  `limit-holdem-rule-v1`, plus UNO, Dou Dizhu and Gin Rummy rule models.
  rlcard-showdown's downloadable "pretrained" bundle covers Leduc and Dou Dizhu
  only. DMC on no-limit hold'em is a training *example*, trained "for hours",
  with no published weights.
- The environment itself: `DEFAULT_GAME_CONFIG = {'game_num_players': 2, ...}`
  and the player count is configurable; no-limit with raise amounts in chips.
- Last activity: rlcard pushed 2024-06-26 (3,546 stars, MIT); showdown pushed
  2023-10-10 (413 stars, no licence file).
- Ratings (as a strategy source): a ~ (configurable) · b ~ · c ✗ · d ~ (you
  would train your own DMC agent for hours; strength unknown) · e ✓.

### 3.7 DeepHoldem / DeeperStack / deeper-stacker (open DeepStack re-creations)

- URLs: https://github.com/happypepper/DeepHoldem (222 stars, pushed
  2018-09-25, no licence), https://github.com/godmoves/DeeperStack (26 stars,
  2019-06-16), https://github.com/aikupoker/deeper-stacker (37 stars,
  2020-10-07)
- What: DeepStack extended from the Leduc example to heads-up no-limit
  hold'em, in Lua/Torch.
- Trained models: DeepHoldem ships only the pre-flop auxiliary network; "the
  counterfactual value networks are not included as part of this release", you
  generate flop/turn/river data yourself (tested on a Tesla P100; thinking
  time 2.7 to 12.4 s per decision on that GPU).
- Runs on macOS / Python? No: Lua 5.2 + Torch, a dead stack, heads-up only.
- Ratings: a ✗ · b ~ (DeepHoldem's own README: "The action abstraction used
  was half pot, pot and all in for first action, pot and all in for second
  action onwards") · c ✗ · d ✗ · e ~ (no licence stated).

### 3.8 DecisionHoldem (AI-Decision)

- URL: https://github.com/AI-Decision/DecisionHoldem
- What: heads-up no-limit AI combining a Linear-CFR blueprint with real-time
  safe depth-limited solving; C++ core with `.so` libraries and Python test
  scripts against Slumbot.
- Trained blueprint: **yes, downloadable**, but only from Baidu Netdisk
  (https://pan.baidu.com/s/157n-H1ECjEryAx0Z03p2_w, size unstated; access from
  outside China is often awkward: UNVERIFIED that the link still serves).
  Trained on a Xeon Gold with 512 GB RAM.
- Last activity: pushed 2024-05-29. Stars: 100. Licence: AGPL-3.0.
- Runs on macOS / Python? Linux `.so` binaries; Mac build UNVERIFIED.
- Ratings: a ✗ (2 only) · b ~ (its README: "hand abstraction technique and
  action abstraction", i.e. a fixed bet menu) · c ✗ · d ? (both the Mac build
  and whether the blueprint download still serves are unverified; the training
  it replaces took 48 cores for 3-4 days) · e ✓.

### 3.9 robopoker (krukah)

- URL: https://github.com/krukah/robopoker
- What: a from-scratch Rust suite aiming at Pluribus parity: abstraction,
  MCCFR blueprint checkpointed to PostgreSQL, real-time re-solve, and a
  Slumbot benchmark client (`spar`).
- Last activity: pushed 2026-09-10. Stars: 221. Licence: MIT.
- Trained blueprint: **not shipped as a download**; you train it (README's
  resource line: 16 vCPU / 120 GB; river abstraction alone is 3.02 GB).
- Strength: "-13.1 bb/100 against live Slumbot over 86K hands" (loses,
  narrowly). Heads-up as evaluated.
- Ratings: a ? (evaluated heads-up; whether it plays multiway at all is not
  stated) · b ~ (its own table: "Action translation: pseudo-harmonic mapping
  over finite lattices" — a fixed menu, with arbitrary opponent bets mapped
  onto it) · c ✗ · d ✗ (120 GB against this laptop's 16 GB) · e ✓.

### 3.10 PokerSnowie (Snowie Games Ltd, Malta)

- URL: https://www.pokersnowie.com/ (pricing at /pricing)
- What: a neural-network trainer you play against and import hands into; it
  grades your decisions against its own near-balanced strategy.
- Price (read from the site's page data): $29.90/month or $16.66/month billed
  annually (about $200/year), 10-day free trial, "PokerSnowie is for personal
  use", professional use by custom offer. Footer copyright 2025; company
  registration C56838, Malta.
- Platforms: Windows, macOS (10.12+), iOS, Android; the phone apps are
  "Optimized for HU and 5-seated". Desktop covers heads-up, 6-max and full
  ring (per the Cardmates review; the site's own feature page did not render
  for me, so full-ring on desktop is second-hand).
- API: none. A reviewer notes it closes itself if a poker client is running.
- Per-opponent adjustment: none by design; it teaches "non-exploitable" play.
- Ratings: a ~ (heads-up and 6-max confirmed on the vendor's own pages; full
  ring is reviewer-sourced only) · b ? (no-limit, but whether it advises from
  a fixed set of sizes is not documented and the software is closed) · c ✗ ·
  d ✗ (cannot be called by a program) · e ~ (affordable, closed).

### 3.11 PokerBotAI (pokerbotai.com)

- URLs: https://pokerbotai.com/, https://github.com/PokerBotAI/poker-bot
  (78 stars, marketing README only), https://sourceforge.net/projects/poker-bot-ai/
  (free demo build, Android and Windows, updated 2025-08-28)
- What: commercial autoplay/advisor bot for 20+ mobile poker apps (GGPoker,
  PPPoker, ClubGG, PokerBros, KKPoker, X-Poker, Pokerrrr 2, and others).
  Claims a neural network trained on 7 billion hands plus "GTO strategy +
  exploiting leaks + opponent profiling" over "hundreds of parameters".
- Price (their own 2026 pricing page): one-time licence "from $700" (the
  home page says about $1,000) plus "fuel", a per-hand charge, first top-up
  from $150; a worked example is "$2,000 one-time + $700/mo". Also a
  managed-farm revenue-share offer. Structured data says the company was
  founded 2021-06-04 and has 51 to 200 staff; the site says "since 2016".
- Platforms: Android phones and emulators, Windows. **Not macOS.** No API.
- Per-opponent adjustment: claimed (per-opponent profiling); **UNVERIFIED**,
  the software is closed and I could not inspect it.
- Ratings: a ? · b ? · c ? — every one of these rests on the vendor's own
  marketing, and the software is closed, so none can be marked · d ✗ (closed,
  Android/Windows, cannot be integrated) · e ~ (buyable, but per-hand fees and
  no way to read its decisions).

### 3.12 Shanky Technologies Holdem Bot (bonusbots.com)

- URLs: https://bonusbots.com/, https://bonusbots.com/pricing.htm
- What: "the original autoplay Texas Holdem Poker Bot since 2007". Version
  12.7.8 posted 2026-08-12. Ships "pre-loaded with 6 good profiles" written in
  PPL (its rule language; OpenPPL was derived from it). Cash, MTT, SNG, HU,
  up to 6 tables at once.
- Price: free demo (stops after 200 hands), $129 for one year, $79 renewal.
- Platforms: Windows desktop clients (licence "can be moved to any PC"). No
  API, no Mac.
- Per-opponent adjustment: PPL profiles can branch on what an opponent has
  done in the current hand. Whether the product tracks players across hands by
  name is not documented.
- Ratings: a **?** — no seat fact could be checked. The site's own wording,
  "Cash Games, MTTs, SNGs, DONs, Speed, HU" and "Multi-table up to 6
  simultaneous tables", is game types and how many tables at once, not how
  many seats; its PPL guide does code for full-ring positions ("StillToAct
  >=7 ... full ring games with 7+ live opponents behind you",
  https://bonusbots.com/PPLguide.pdf p. 22), which implies nine seats, but
  that is the vendor describing closed software nobody here can run, and the
  rule at the top of section 2 says a mark never stands on a vendor's claim ·
  b ✓ (PPL carries the amount in the command: the same guide, p. 15, "Bet 5
  force (bets 5 big blinds)", "Raise 5 force (raises by 5 big blinds, note
  that Raise is always raise by, not raise to)", "Bet 70% force (bets 70% of
  the pot)", "Raise 150% force" — any number of big blinds or any percentage
  of the pot, not a menu) · c ~ (branching on in-hand behaviour only; by-name
  tracking is **?**) · d ✗ (Windows-only, closed) · e ~.

### 3.13 Warbot (warbotpoker.com)

- URL: https://www.warbotpoker.com/ (site is behind a Cloudflare challenge;
  I could only read its forum at https://forum.warbotpoker.com/ via search
  snippets)
- What: an OpenHoldem-derived Windows bot sold with OpenPPL profiles
  (e.g. a free "Snowball 6max cash" profile on the forum).
- Price: about $150/year per third-party guides. **UNVERIFIED** directly.
- Ratings: a ? · b ? · c ? · d ✗ (Windows, closed, by every third-party
  account) · e ?. Nothing beyond its existence could be verified, so nothing
  beyond the platform gets a mark.

### 3.14 aipoker-bot/ppl-interpreter (Python runner for Shanky/OpenPPL profiles)

- URL: https://github.com/aipoker-bot/ppl-interpreter
- What: a Python interpreter for PPL profiles (Shanky dialect, OpenPPL as
  tie-break). `decide_ppl` takes any `GameState` you supply (n players,
  street, board, pot, per-seat hole/stack/bet/position/alive, legal actions)
  and returns the action plus a trace of which rule fired. Claims 100% rule
  coverage on 16 commercial cash profiles.
- Last activity: created and pushed 2026-09-14. Stars: 0. Licence: MIT. The
  GitHub organisation `aipoker-bot` was also created on 2026-09-14 and holds
  only this and `slumbot-adapter` (a Python Slumbot API client, MIT, 0 stars).
  Both are one day old at the time of writing: real code, but unproven.
- Runs on macOS / Python? Yes, pure Python.
- Plays today? Only as a decision function; you supply table state and a
  profile. **Two profiles are included** — `profiles/teaching_tight.txt` and
  `profiles/teaching_loose.txt`, MIT like the rest of the repository — so
  there is a free, complete, runnable profile here and the question of whether
  one exists is settled. What they are *not* is a winning strategy: their own
  header says "a small PPL profile written for ppl-interpreter (not a
  commercial Shanky profile)", each is a couple of dozen rules covering
  tight-aggressive or loose 6-max cash play, and neither has been measured
  against anything. Shanky's six commercial profiles still ship only with its
  $129 Windows product, and OpenHoldem's repository carries an OpenPPL library
  of functions rather than a playable profile; whether a *commercial-grade*
  free profile exists that this parses is still open.
- Per-opponent adjustment: whatever the profile's rules test; PPL has no
  by-name stats unless the host supplies them as symbols.
- Ratings: a ✓ (the caller states the number of seats; nothing in the
  interpreter caps it) · b ✓ (it returns an amount, clamped between the legal
  minimum and maximum raise the caller declares) · c ~ · d ✓ · e ✓. Immature:
  one day old, 0 stars, unproven at the table.

### 3.15 poker-gto-rt (fabienpierret): **no code — an advertisement**

- URL: https://github.com/fabienpierret/poker-gto-rt
- What it claims: a real-time analysis pipeline "optimized for < 400ms latency
  on Apple Silicon" — YOLO table and card detection, SAM2 segmentation,
  calibrated OCR for pot/bets/stacks, CoreML acceleration, then a
  CFR/Monte-Carlo recommendation, advisory only, on an M4 Max with 36 GB.
- **What it contains: two files.** The full repository tree is `README.md`
  (3,503 bytes) and `LICENSE` (1,070 bytes). No source, no models, no tests,
  no packaging; GitHub reports the repository size as 3 KB and detects no
  programming language. Created and last pushed on the same day, 2025-11-25.
  Stars: 11. Licence: MIT — over nothing.
- Every performance figure in that README describes software that was never
  published. Nothing in it can be run, read, copied or measured.
- Ratings: **not rated.** There is no artefact to rate. It is listed here only
  so the next session does not spend an hour rediscovering that, and as a
  reminder that a README is not a project.

### 3.16 PokerScreenBot (Vlad-Boyar) and PokerGPT (HarperJonesGPT): more screen readers

- PokerScreenBot, https://github.com/Vlad-Boyar/PokerScreenBot: YOLOv8 table
  and digit detection, ResNet18/MobileNetV2 card classifiers, FastAPI and
  Telegram front ends, spin-and-go solver database. Pushed 2025-06-28, 0
  stars, no licence, and "trained models and solver databases are excluded
  intentionally". Infrastructure only.
- PokerGPT, https://github.com/HarperJonesGPT/PokerGPT: Windows 11 PokerStars
  6-max bot that reads the table with Tesseract OCR and asks GPT-4 what to do.
  238 stars, MIT, last push 2023-12-26. A language model deciding actions is
  exactly what this project's forefront rule forbids, so it is listed only as
  a screen-reading reference.
- Ratings for both, as capture references only: a ✗/~ · b n/a (neither
  contributes a bet-sizing policy we would keep) · c ✗ · d ~ (PokerScreenBot's
  approach is portable; PokerGPT is Windows) · e ✓ / ~ (no licence on
  PokerScreenBot).
- With poker-gto-rt struck off as an empty repository, PokerScreenBot is the
  most complete *published* capture pipeline on this list — and it too
  withholds its trained models, so what it offers is a worked example of the
  approach, not a component.

### 3.17 PokerBotAgent (gianlucaio): 6-max/9-max screen-scraping agent with per-player stats

- URL: https://github.com/gianlucaio/PokerBotAgent
- What: Python 3.10+ "See → Eval → Act" agent for a private virtual-chip
  platform: screenshots + template matching + OCR + a local vision model,
  equity via `treys`, and "profilazione avversari" that tracks VPIP/PFR/AF per
  player and feeds them into the decision. Explicitly 6-max and 9-max.
  Decisions are made partly by a local LLM through LM Studio.
- Last activity: pushed 2026-09-05. Stars: 1. Licence: MIT. Italian docs.
- Runs on macOS / Python? Python; capture calibrated by an external tool
  (PokerTableScope); macOS UNVERIFIED.
- Per-opponent adjustment: yes, per tracked player statistics, though the
  identity key is UNVERIFIED (seat vs name).
- Ratings: a ~ (6 and 9) · b ~ · c ~ (statistics are tracked per player, but
  whether the key is the seat or the screen name is not documented — and
  "by name" is exactly what criterion (c)'s ✓ requires, so it cannot have
  one) · d ~ · e ✓. The LLM-in-the-loop design conflicts with the forefront
  rule; only its statistics layer is of interest.

### 3.18 Texas Hold'em AI Lab (CathyKernel/Texas-hold-em), in-browser 6-max with shipped models

- URL: https://github.com/CathyKernel/Texas-hold-em
- What: TypeScript single-page app with a full 6-max no-limit engine and five
  agent types (rules, Monte Carlo, tabular CFR, Deep CFR, Q-learning) with
  **trained artifacts committed** in `public/ai/` (an 888,361-iteration MCCFR
  blueprint with 72,741 infosets; a Deep CFR net; an RL policy) and a
  100,000-hand tournament report. Its own result: Deep CFR +144.7 bb/100 and
  the tabular blueprint -170 bb/100 in that tournament, i.e. the blueprint is
  admittedly too coarse.
- Last activity: created 2026-09-14, pushed 2026-09-15. Stars: 0. MIT.
- Runs on macOS / Python? Node 18+/Bun in a browser; not Python.
- Ratings: a ✗ (6) · b ~ (the shipped agents act through an "action & card
  abstraction (info buckets)" module, so the blueprint's sizes come from a
  menu; the engine underneath enforces real no-limit rules) · c ✗ · d ~ ·
  e ✓. Surprising find; strength unproven against humans or Slumbot.

### 3.19 fedden/poker_ai (the vendored engine) and its forks

- URL: https://github.com/fedden/poker_ai (1,585 stars, GPLv3, **archived**;
  the API reports `archived: true` with `archived_at: null`, so GitHub does
  not expose the date it was archived and this survey states none. Its last
  push was 2023-04-03.) keithlee96/pluribus-poker-AI (355 stars, pushed
  2023-10-22) is an earlier snapshot; zanussbaum/pluribus (109 stars, 2020) is
  a separate Python attempt with no trained strategy.
- Strategy shipped: only the 20-card short-deck blueprint pickles referenced
  in its README. Already known from the project's own work: the 52-card path
  is ~18 days and ~147 GiB.
- Ratings: a ~ · b ✗ (fixed-limit as vendored) · c ✗ · d ✗ · e ✓.

### 3.20 whatsdis/pluribus — 242 stars, and it does not run

- URL: https://github.com/whatsdis/pluribus
- What it claims: an implementation of Pluribus for 6-max no-limit, from the
  Science paper's supplementary material, plus a plan for a Bodog.eu Chrome
  extension and depth-limited search on a rented 64-core, 512 GB AWS machine.
- What it is: **one 731-line file, `pluribus.py`, plus a README.** Nothing
  else is in the repository.
- **It is not valid Python.** `python3 -m py_compile pluribus.py` fails at
  line 202 (`SyntaxError: invalid decimal literal`): the file is a half-done
  transliteration of someone else's JavaScript with `//` comments, trailing
  semicolons and `[**list]` spreads left in. It has never been executed.
  Its own README calls the solver, parser and client all "(WIP)", and the
  code's constants set a 20-card deck (`ranks = [6..A]`) and two players.
- Last activity: pushed 2021-08-05. Stars: 242. **No licence file** — meaning
  default copyright: not ours to use, even privately, without permission.
- Ratings: **not rated** — nothing here executes. Recorded because 242 stars
  make it a repeat search hit, and stars are not evidence of code.

### 3.21 rosbo/texas-holdem-poker-ai — explicit opponent modelling, wrong game

- URL: https://github.com/rosbo/texas-holdem-poker-ai
- What: a Java simulator from a Norwegian university course, with three bot
  levels: hand strength only; hand strength plus a pre-flop roll-out
  simulation; and those plus **opponent modelling**. Each level comes in a
  bluffing and a rational variant. Guice for wiring, an embedded H2 database
  holding the pre-flop simulation results and the opponent model — both
  committed (`data/data.h2.db`, `data/data.trace.db`, 4.3 MB together).
- How the opponent model works, which is the reason to read it:
  `OpponentModeler` records, for each player, what they did in a described
  situation (street, number of raises, players left, pot odds) together with
  the hand strength they later showed down, keeping only hands that reached
  showdown; `getEstimatedHandStrength` then answers "when this player bets in
  this kind of spot, how strong are they usually?". That is per-player
  modelling built from evidence, not a hand-written table of reads.
- What it is not: **the betting is fixed-limit.** `BettingRound.applyDecision`
  makes a raise exactly `highestBet + bigBlind` (`BettingRound.java:26-27`),
  and `GameHandController.playRound` converts *any* raise decided after the
  first time round the table into a call — `if (turn >
  numberOfPlayersAtBeginningOfRound && ... RAISE) bettingDecision = CALL;`
  (`GameHandController.java:75-79`), so a betting round can hold at most one
  orbit of raises, whoever makes them. There is no screen capture, no live
  play, and the table is four simulated seats
  (`DemoGameProperties`); players are in-process objects, so "identity" is an
  object reference, not a screen name.
- Last activity: pushed 2023-12-16 (created 2012-08-20). Stars: 146. MIT.
- Ratings: a ✗ (a fixed four-seat simulation) · b ✗ (fixed-limit, one raise
  size) · c ~ (per-player modelling, keyed to a simulated player object) ·
  d ✗ (Java, no live play, and nothing to reuse but the idea) · e ✓.

### 3.22 PokerBotAI/awesome-poker-ai — a vendor's link list, mined

- URL: https://github.com/PokerBotAI/awesome-poker-ai (79 stars, no licence
  file, README only, created 2026-03-01, last push 2026-04-03)
- What: a curated list of poker-AI papers, frameworks, solvers, bots and
  guides. **Published by PokerBotAI** (3.11), the commercial vendor: its own
  product is the entire "Commercial bots" section, with eight links into its
  own marketing pages, and a "Poker Math & Strategy (by PokerBotAI)" section.
  Read it as a source of links, not as an assessment.
- Mined in full on 2026-09-15. It lists twenty GitHub projects. Every one that
  plays, solves or carries a strategy is already covered here or in
  `ENGINE_ALTERNATIVES.md`: DecisionHoldem, PokerRL, PokerGPT, TexasSolver,
  postflop-solver, RLCard, Deep CFR 6-player, slumbot2019, ReBeL, clubs,
  OpenSpiel, PyPokerEngine, PokerKit, treys, deuces. It adds no bot this
  survey had missed.
- Four remainders, and what they are: `b-inary/desktop-postflop` (349 stars,
  AGPL-3.0, suspended 2023-11) is a desktop front end for postflop-solver,
  already covered; `HenryRLee/PokerHandEvaluator` (516 stars, Apache-2.0,
  active) and `worldveil/deuces` are hand evaluators, and this project already
  has one named in `CLAUDE.md`; `whmmy/poker_LLM` (41 stars, MIT) and
  `superagent-ai/poker-eval` put language models in the seat, which the
  forefront rule forbids.
- One entry does qualify and was missing here: **dickreuter/neuron_poker**
  (722 stars, MIT, pushed 2025-08-04), the same author as 3.2. It is a
  six-seat no-limit training environment in the OpenAI-gym shape with a
  Monte-Carlo equity helper and several agents, including a deep Q-learning
  one. Its action list is fixed —`FOLD, CHECK, CALL, RAISE_3BB,
  RAISE_HALF_POT, RAISE_POT, RAISE_2POT, ALL_IN` — and it ships no trained
  agent of any strength. Ratings: a ✗ (6 seats) · b ~ (eight fixed actions) ·
  c ✗ · d ~ (Python, Mac-plausible, but you would train it yourself and it has
  never been shown to beat anything) · e ✓. It belongs with RLCard as a place
  to train, not a strategy to take.

### 3.23 Solvers checked in passing (not bots): TexasSolver, postflop-solver, GTO Wizard

- TexasSolver, https://github.com/bupticybee/TexasSolver: 2,547 stars, AGPL-3.0,
  pushed 2026-08-26, C++ with GUI and console, runs on macOS. A post-flop
  solver for a *given* two-player spot (a flop solve took 172 s on 6 threads,
  1.6 GB RAM). Multiway UNVERIFIED (its documented use is heads-up).
- postflop-solver, https://github.com/b-inary/postflop-solver: 369 stars,
  AGPL-3.0, development suspended 2023-10 (author went commercial). Rust,
  heads-up post-flop with a "bunching" correction for folded seats. No Python.
- GTO Wizard, https://gtowizard.com: 2026 tiers reported by reviewers as Free /
  $39 / $99 / $129+ / Ultra $229-279 per month, with Ultra adding multiway
  pre-flop up to 9 players and 3-way post-flop. **No developer API found;
  prices UNVERIFIED on the vendor site itself** (reviewer sources only).
- None of these is a per-spot oracle you can call at play speed for 3 to 9
  players; they are study tools or heads-up solvers. Listed so the next
  session does not re-search them.

### 3.24 Not real / not released

- Pluribus, Libratus, DeepStack (full hold'em), Supremus: no public code or
  strategy. Supremus is described only in a 2020 arXiv paper (2007.10442) and
  press; no repository exists.
- Meta's ReBeL repo (https://github.com/facebookresearch/rebel, Apache-2.0)
  is archived and contains Liar's Dice only, not hold'em.

## 4. Ranked shortlist (best fit first)

Ranked by **how useful each one is to this project on this machine**, not by
how impressive it is and **not by its score on the five criteria**. Nothing
here earns a ✓ on all five, and the top two each carry a hard ✗ — Slumbot on
(a), because it is heads-up only, and OpenHoldem on (d), because it is Windows
C++. They rank first anyway: one of them ran on this laptop during the survey,
and the other is the only shipped answer to the question the operator actually
asked. Read the order as "what to do next", and the criteria in section 3 as
"what each one is". Two facts reshuffle the old order: the strongest
multi-player candidate needs more memory than the laptop has, and the one
Mac-native capture project turned out to contain no code.

1. **Slumbot API** (3.3): the only thing in this survey that ran on this
   laptop during the survey itself — free, live, a hand dealt and verified.
   It measures strength; it is not a strategy, and it is heads-up only.
2. **OpenHoldem's PokerTracker design** (3.1): the one verified, shipped
   answer to "play differently against *this named player*" — statistics
   fetched by screen name and exposed to the rule language as ordinary
   quantities. Windows C++, so what crosses over is the design.
3. **aipoker-bot/ppl-interpreter** (3.14): pure Python, installs in minutes
   here, takes any seat count and any table state we hand it, returns an
   action *and an amount*, and now ships two working profiles. Immature: one
   day old, 0 stars, and its profiles are teaching examples, not winners.
   **Unresolved, and it decides whether this entry is usable at all:** a PPL
   profile *is* a hand-written rule for what to do with each holding, so
   running one puts hand-rolled decision logic where `CLAUDE.md`'s forefront
   rule says the vendored engine must be — the same objection this survey
   applies to PokerGPT (3.16) and PokerBotAgent (3.17). The uses that clearly
   survive the rule are the ones where nothing of ours chooses the action:
   a scripted *opponent* to test against, or a baseline to measure against.
   Using it to pick our own action needs a recorded carve-out in `CLAUDE.md`
   first. That call belongs to the section 5 reconciliation, not here.
4. **dickreuter/Poker** (3.2): a real Python bot that has played for money on
   three sites — the only entry here with that record, and its decision layer
   (equity by Monte Carlo, pot odds, a tunable strategy) is portable Python.
   Gaps: 6-max only, Windows-bound capture, no memory of a player between
   hands, and its bet sizing is a five-item fixed menu clicked on the client's
   own buttons, so nothing about *sizing* is worth taking from it.
5. **NoRegrets** (3.4): the best multi-player no-limit strategy source on the
   list, and it does not fit — 36 to 50 GB while training against this
   laptop's 16 GB. Its engine-side exploit dial (`--rnr-*`) is the most useful
   idea here. Revisit only with a measured small-memory configuration.
6. **Texas Hold'em AI Lab** (3.18): the only project that actually *ships*
   trained 6-max artefacts. In-browser TypeScript, and its own tournament
   says the blueprint is too coarse (−170 bb/100).
7. **PokerScreenBot** (3.16): with poker-gto-rt struck off, the most complete
   published capture pipeline — but its models are withheld, so it is a worked
   example to copy, not a component to install.
8. **Deep CFR 6-player** (3.5): the most active Python multiway project, with
   per-player records designed in; no model, no strength, no sizing yet.
9. **DecisionHoldem** (3.8): the only open project offering a downloadable
   blueprint at all; heads-up, AGPL, Baidu-hosted, Linux binaries.
10. **Shanky Holdem Bot** (3.12): $129/year for six finished PPL profiles —
    the cheapest route to a *real* profile for the interpreter at 3, if the
    licence permits extracting them. Windows, closed. **Do not spend the $129
    yet.** It buys hand-written decision rules, which is the same tension as
    at 3: until the section 5 reconciliation says whether a rule profile may
    choose our actions, and `CLAUDE.md` records a carve-out if it may, the
    only purchase that is certainly in bounds is a sparring opponent — and a
    sparring opponent is not worth $129 while the two free profiles at 3.14
    are untested.
11. **rosbo/texas-holdem-poker-ai** (3.21): wrong game (fixed-limit, four
    simulated seats), but the clearest worked example of building an opponent
    model from showdowns rather than from opinion.
12. **PokerSnowie** (3.10): a study reference at $29.90/month; no interface a
    program can call, and no opponent adaptation by design.
13. **RLCard** (3.6), **neuron_poker** (3.22), **robopoker** (3.9),
    **DeepHoldem family** (3.7): places to train, not strategies to take —
    no usable pre-trained no-limit model, or a dead stack, or 120 GB.
14. Unusable or unrated: **poker-gto-rt** (3.15, no code), **whatsdis/pluribus**
    (3.20, does not compile, no licence), **Warbot** (3.13, unverifiable),
    **PokerBotAI** (3.11, closed, Android/Windows, claims only).

**The 7-to-9-seat gap, stated plainly.** No resource in this survey plays 7,
8 or 9 seats with true no-limit sizing. OpenHoldem's source is the one place
the seats are confirmed (ten chairs), and it is a Windows C++ rule framework
that ships no strategy; Shanky's seat range is a vendor claim about closed
software, and it ships no strategy of its own either, only rule profiles;
PokerBotAgent names 9-max but is an unproven one-star project with a language
model in the decision path; PokerSnowie's full-ring support is second-hand and
uncallable; every open trained-strategy project stops at 6. The operator's
second priority — 8 and 9 handed — is an **open gap this survey cannot
close**, and combining a 6-max bot with a per-name memory does not close it
either. It needs its own piece of work.

## 5. Recommendation

**This survey does not choose the strategy road, and must not.** Recommending
that we train a blueprint in advance would contradict `ENGINE_ALTERNATIVES.md`,
which recommends the opposite in as many
words — "abandon the train-in-advance approach entirely in favour of computing
the decision at the moment we need it" — on the strength of a bot it actually
built and measured on this laptop (6-player, 52-card, no-limit, 250 ms per
decision, no training at all). It would also set aside the opening of
`CLAUDE.md`, which names `fedden/poker_ai` as the engine this project is built
on, and its Plan, whose stage 1 is moving that engine to the 52-card game.
Choosing between a strategy trained in advance and one computed while the hand
is being played is a decision for the **reconciliation of `ENGINE_ALTERNATIVES.md`,
`RESOURCES_BOTS.md`, `RESOURCES_SOLVERS.md` and `RESOURCES_EXPLOITATION.md`**,
and whatever it decides needs a recorded carve-out or rule change in
`CLAUDE.md`. Not a line in a survey of other people's bots.

What this survey *does* settle, and hands to that reconciliation:

- **Nothing here is adoptable whole.** The nearest multi-player strategy,
  NoRegrets, needs 36 to 50 GB to train and this laptop has 16 GB; its own
  results file says the configurations small enough to fit are too
  under-trained to play multi-player pots. If anyone wants to keep it alive,
  the spike is not "does it build on a Mac" — the author's own numbers were
  measured on a Mac — it is: **can any reduced configuration (fewer training
  passes, coarser card grouping, the coarse bet menu) train and then play
  inside 16 GB in hours, and does it still beat a weak baseline multiway?**
  The repository publishes no memory figure for any such run, so that is a
  measurement to make, not a fact to look up.
- **Measure against Slumbot from day one.** Free, live, verified, callable
  from Python today. It is heads-up, so it bounds one seat count only.
- **Identity-keyed exploitation has exactly one shipped design** — OpenHoldem's
  per-seat statistics, looked up by screen name and handed to the decision
  code as inputs. Whatever engine road wins, the memory of "who this player
  is" is ours to write, because nobody ships it in a form we can run.
- **Per-opponent adjustment must enter through the engine, never through code
  of ours that picks actions.** `CLAUDE.md` lines 13-15 forbid hand-rolled
  decision logic, and "shift the call, bluff and value thresholds for this
  named player" is precisely that, as is any layer of ours that turns an
  equity number into a bet. Two shapes are legitimate: (i) **a biased strategy
  the engine itself produces** — NoRegrets' `--rnr-model` / `--rnr-opponent`
  with the `--rnr-p` dial, fed an opponent that its own `clone` command builds
  from logged hands; or (ii) **an opponent input to engine-side search** —
  giving the engine a per-player range or behaviour to play the rest of the
  hand out with, which is the hook `ENGINE_ALTERNATIVES.md` argues a
  decision-time bot has and a fixed blueprint does not. Our code supplies the
  observations and picks which input to pass; the engine chooses the action.
  Anything outside those two shapes needs a recorded carve-out in `CLAUDE.md`
  before it is written, not after.
- **A rule profile is hand-written decision logic, and the survey does not
  settle whether we may run one.** PPL and OpenPPL profiles — the shipped
  strategies behind 3.1, 3.12 and 3.14, and the reason two of them rank in the
  top ten — are lists of "with this hand in this spot, do this", written by a
  person. `CLAUDE.md` lines 13-15 reject "hand-rolled ... decision logic in
  place of the vendored engine", and this survey applies exactly that test to
  PokerGPT (3.16) and PokerBotAgent (3.17), so it must apply it to its own
  picks. Two uses are plainly safe because our code does not choose the
  action: a profile driving a *scripted opponent* to develop and test against,
  and a profile as a *baseline to beat*. A profile choosing the bot's own
  action is the contested case, and it needs a recorded carve-out in
  `CLAUDE.md` before anyone writes or buys one. **Route it to the same
  reconciliation as the train-in-advance question above; this survey must not
  settle it either way.**
- **Table capture has to be written here.** Every finished reader is Windows
  bound, and the Mac-native one is an empty repository. PokerScreenBot and
  dickreuter's capture layer are the references; neither is an installable
  dependency.
- **7 to 9 seats is unsolved** by anything surveyed (see the end of section
  4). Do not plan around a combination that does not exist; plan a piece of
  work.
- **Do not buy PokerSnowie or PokerBotAI for this.** Neither can be called by
  our code, neither runs on the Mac, and PokerBotAI's per-opponent claim is
  unverifiable marketing published by the same party as the "awesome" list
  that promotes it.

## 6. What could not be verified

- **Checked and settled, recorded so nobody re-asks:** NoRegrets
  builds and trains on Apple Silicon (its own baselines were measured there);
  ppl-interpreter does ship free, complete, runnable profiles; poker-gto-rt
  ships no code at all; GitHub does not expose the date `fedden/poker_ai` was
  archived.
- The smallest memory footprint NoRegrets can be trained in, and whether any
  configuration that fits 16 GB still plays multi-player pots. The repository
  states no memory requirement anywhere, and every run it reports is 36 GB or
  more. This is the single measurement that decides whether NoRegrets is ever
  usable here.
- Deep CFR 6-player building on macOS; NoRegrets' commercial blueprint price.
- Warbot's price and current state (site blocks automated readers).
- GTO Wizard's prices from the vendor itself, and whether any API exists
  (none found).
- PokerBotAI's per-opponent profiling claim (closed software).
- Whether DecisionHoldem's Baidu blueprint link still serves outside China.
- PokerSnowie desktop full-ring support (reviewer source only) and the exact
  annual price ($16.66/month on the site's data; $229.95/year per reviewer).
- Whether any *commercial-grade* free OpenPPL/Shanky cash profile exists that
  ppl-interpreter can run. (That it runs free profiles at all is settled: two
  ship with it.)
- Whether PokerBotAgent keys its per-player statistics on the seat or on the
  screen name.
- How many seats the Shanky bot actually plays. Its PPL guide codes for
  full-ring positions, so the language reaches nine, but the product is closed
  and the site advertises game types and table counts, never seat counts.
- TexasSolver multiway support.
