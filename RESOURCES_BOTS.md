# Ready-made poker bots, bot frameworks, and pre-trained strategies

Research survey, September 2026. Companion to `ENGINE_ALTERNATIVES.md` (poker
engines: OpenSpiel, RLCard as an engine, PyPokerEngine, PokerKit, clubs, PokerRL).
This file covers the other side: things that already *play*, already carry a
strategy, or already read a table off a screen.

Every URL below was visited on 2026-09-15. Stars, last-activity dates, and
licences come from the GitHub API on that date unless marked otherwise.
Anything I could not confirm is marked **UNVERIFIED**.

## 1. Summary for a non-programmer

The question was: can we adopt a finished poker bot, or a finished strategy,
instead of building one? The short answer:

- **No single finished thing does what we want.** Nothing open or paid that I
  could verify plays no-limit hold'em at every size from 2 to 9 players, adjusts
  to named opponents, runs on a Mac, and is ready in hours. Each candidate
  covers two or three of those, never all five.
- **Three pieces exist that, combined, get close.** A trainer that builds a
  sound 2-to-6-player no-limit strategy in about an hour on a many-core machine
  (NoRegrets). A proven design for "look up this named player's habits and
  play differently against them" (OpenHoldem's PokerTracker symbols and
  Shanky-style profiles). And working screen-reading pipelines, one of which is
  built for Apple laptops (poker-gto-rt).
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
| d | Reachable in hours on one Mac laptop, Python preferred | yes | possible with real work (other language, VM) | days of compute or dead platform |
| e | Fits private use (licence and price) | free and open, or affordable | paid but affordable, or copyleft that is fine for private use | closed with no purchase path |

"Runs on macOS / Python?" is answered literally. GPL/AGPL is fine for us
because the project is never distributed.

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
- Ratings: a ✓ · b ✓ · c ✓ · d ✗ (Windows-only, C++, needs a VM and a paid
  tracker database) · e ✓.

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
- Ratings: a ✗ (6 only) · b ✓ · c ✗ · d ~ (Python, but scraper is Windows-only)
  · e ✓.

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
- Ratings: a ✗ (2 only) · b ✓ · c ✗ · d ✓ (as a test opponent) · e ✓.
- Use: a free, strong yardstick for the 2-player case. Every serious open
  project below benchmarks against it.

### 3.4 NoRegrets (conorarmstrong/noregrets), Pluribus-style, Rust

- URL: https://github.com/conorarmstrong/noregrets
- What: an independent Pluribus-style bot for 2 to 6 player no-limit hold'em:
  parallel external-sampling Linear MCCFR blueprint plus range-tracked
  depth-limited online re-solving. "The bot plays any table size from 2 to 6;
  one blueprint covers every seat."
- Last activity: pushed 2026-09-08 (created 2025-06-21). Stars: 19. Licence:
  MIT for the public code, but "it is not the current version" (public release
  lags the private repo by about twelve months) and "Trained blueprints and
  other pretrained artifacts are never published here and are available under a
  commercial licence only" (contact conorarmstrong@gmail.com; price UNVERIFIED).
- Training cost stated in README: "200M iterations ≈ 1 hour on 16 cores";
  400M took 1h56m. An 8-to-12-core Mac laptop should land in the low single
  digits of hours. **macOS build UNVERIFIED** (Rust is cross-platform; nothing
  in the README is Windows-specific).
- Plays today? Yes: `play` gives an interactive terminal game, you in seat 0
  against bots. No-limit: yes. No screen capture.
- Strength evidence: against Slumbot heads-up it *lost*, -714.5 ±331.5
  mbb/hand blueprint-only and -1771 ±471.8 with search on, over 10,000 hands.
  The README attributes this to range tracking assuming the opponent plays its
  own blueprint. That is a 2-player result against a top bot, not a result
  against humans; treat the strength as unproven.
- Per-opponent adjustment: partial. It can train a restricted Nash response
  against pre-specified opponent types (random, calling station) but "lacks
  online estimation of an unknown live opponent's tendencies from observed
  play". Nothing keyed by name.
- Ratings: a ~ (2 to 6, not 7 to 9) · b ✓ · c ~ · d ~ (hours, but Rust and
  UNVERIFIED on Mac) · e ✓ (code) / ~ (their blueprints are paid).

### 3.5 Deep CFR for 6-player NLHE (dberweger2017)

- URL: https://github.com/dberweger2017/deepcfr-texas-no-limit-holdem-6-players
- What: a Python 3.11 Deep CFR research project for six-handed no-limit,
  with continuous bet sizing, a headless agent API, decision replay, and
  "per-player identity-owned records" for opponent modelling across changing
  line-ups. Four- and five-handed are "first-class" configurations.
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
- Ratings: a ~ (4 to 6) · b ✓ · c ~ (designed, not proven) · d ✗ (no model;
  training cost unknown, Deep CFR is typically days) · e ✓.

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
- Ratings: a ✗ · b ✓ · c ✗ · d ✗ · e ~ (no licence stated).

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
- Ratings: a ✗ (2 only) · b ✓ · c ✗ · d ~ · e ✓.

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
- Ratings: a ✗ (evaluated HU; multiway UNVERIFIED) · b ✓ · c ✗ · d ✗ (120 GB)
  · e ✓.

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
- Ratings: a ✓ (as a study tool) · b ✓ · c ✗ · d ✗ (cannot be called by a
  program) · e ~ (affordable, closed).

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
- Ratings: a ✓ (claimed) · b ✓ · c ~ (claimed, unverifiable) · d ✗ (closed,
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
- Per-opponent adjustment: PPL profiles can branch on in-hand behaviour;
  by-name tracking UNVERIFIED.
- Ratings: a ✓ · b ✓ · c ~ · d ✗ (Windows-only, closed) · e ~.

### 3.13 Warbot (warbotpoker.com)

- URL: https://www.warbotpoker.com/ (site is behind a Cloudflare challenge;
  I could only read its forum at https://forum.warbotpoker.com/ via search
  snippets)
- What: an OpenHoldem-derived Windows bot sold with OpenPPL profiles
  (e.g. a free "Snowball 6max cash" profile on the forum).
- Price: about $150/year per third-party guides. **UNVERIFIED** directly.
- Ratings: a ✓ · b ✓ · c ~ · d ✗ · e ~. Everything here is UNVERIFIED beyond
  existence.

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
  profile. No profiles are included; Shanky's six ship only with its $129
  Windows product, and OpenHoldem's repo carries an OpenPPL library of
  functions, not a full playable profile (UNVERIFIED whether any free complete
  cash profile exists that this parses).
- Per-opponent adjustment: whatever the profile's rules test; PPL has no
  by-name stats unless the host supplies them as symbols.
- Ratings: a ✓ · b ✓ · c ~ · d ✓ · e ✓. Immature.

### 3.15 poker-gto-rt (fabienpierret): Mac-native table capture + solver

- URL: https://github.com/fabienpierret/poker-gto-rt
- What: real-time analysis pipeline "optimized for < 400ms latency on Apple
  Silicon": YOLO for table and card detection, SAM2 segmentation, calibrated
  OCR for pot/bets/stacks, CoreML acceleration, then a CFR/Monte-Carlo
  recommendation. Advisory only (does not click). Target machine M4 Max 36 GB.
- Last activity: pushed 2025-11-25. Stars: 11. Licence: MIT. Python 3.11+.
- Which poker apps: not stated. Table sizes: not stated.
- Ratings (as a capture component): a ~ · b n/a · c ✗ · d ✓ (Mac-first Python)
  · e ✓.

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
- Ratings for both: a ✗/~ · b ✓ · c ✗ · d ~ (PokerScreenBot's approach is
  portable; PokerGPT is Windows) · e ✓ / ~ (no licence on PokerScreenBot).

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
- Ratings: a ~ (6 and 9) · b ~ · c ✓ (design) · d ~ · e ✓. The LLM-in-the-loop
  design conflicts with the forefront rule; only its stats layer is reusable.

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
- Ratings: a ✗ (6) · b ✓ · c ✗ · d ~ · e ✓. Surprising find; strength
  unproven against humans or Slumbot.

### 3.19 fedden/poker_ai (the vendored engine) and its forks

- URL: https://github.com/fedden/poker_ai (1,585 stars, GPLv3, **archived
  2024-07-16**). keithlee96/pluribus-poker-AI (355 stars, pushed 2023-10-22)
  is an earlier snapshot; zanussbaum/pluribus (109 stars, 2020) is a separate
  Python attempt with no trained strategy.
- Strategy shipped: only the 20-card short-deck blueprint pickles referenced
  in its README. Already known from the project's own work: the 52-card path
  is ~18 days and ~147 GiB.
- Ratings: a ~ · b ✗ (fixed-limit as vendored) · c ✗ · d ✗ · e ✓.

### 3.20 Solvers checked in passing (not bots): TexasSolver, postflop-solver, GTO Wizard

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

### 3.21 Not real / not released

- Pluribus, Libratus, DeepStack (full hold'em), Supremus: no public code or
  strategy. Supremus is described only in a 2020 arXiv paper (2007.10442) and
  press; no repository exists.
- Meta's ReBeL repo (https://github.com/facebookresearch/rebel, Apache-2.0)
  is archived and contains Liar's Dice only, not hold'em.

## 4. Ranked shortlist (best fit first)

1. **NoRegrets** (3.4): the only open, active, multi-player (2 to 6) no-limit
   blueprint trainer whose own README puts training at about an hour on 16
   cores; MIT code, plays interactively; gaps: Rust, no 7 to 9, no by-name
   exploitation, unproven strength (lost to Slumbot heads-up).
2. **OpenHoldem's PokerTracker symbol design** (3.1): the proven pattern for
   "adjust to this named player" (per-chair `pt_` stats looked up by screen
   name), and OpenPPL for exploit rules; the software itself is Windows/C++,
   so we copy the design, not the binary.
3. **dickreuter/Poker** (3.2): real Python bot that has actually played on
   three sites, Monte Carlo equity + tunable strategy, GPL; gaps: 6-max only,
   Windows-bound scraper, no per-player memory.
4. **Slumbot API** (3.3): free, live, verified; the heads-up yardstick for any
   strategy we build; cannot be queried for arbitrary spots.
5. **aipoker-bot/ppl-interpreter** (3.14): pure-Python n-player rule runner
   that accepts external table state; the cheapest way to run exploit
   profiles; one day old, 0 stars, no profiles included.
6. **poker-gto-rt** (3.15): Mac-native (CoreML, Apple Silicon) YOLO + OCR
   table capture in Python; advisory only; app-agnostic so it needs training
   on the operator's app.
7. **Deep CFR 6-player** (3.5): most active Python multiway project with
   identity-keyed opponent records designed in; ships no model and no strength.
8. **PokerBotAI** (3.11): the only product verified to *claim* per-opponent
   profiling on mobile apps, from $700 + per-hand fees; closed, Android/
   Windows, unusable as a component.
9. **DecisionHoldem** (3.8): only open project with a downloadable heads-up
   blueprint (Baidu), AGPL; heads-up only.
10. **Shanky Holdem Bot** (3.12): $129/year, six PPL profiles, Windows; the
    cheapest source of finished exploit profiles if the interpreter above pans
    out.
11. **PokerSnowie** (3.10): $29.90/month study reference for all sizes; no
    API, no opponent adaptation.
12. **Texas Hold'em AI Lab** (3.18): shipped 6-max models, but in-browser
    TypeScript and self-admittedly coarse.
13. **RLCard** (3.6), **robopoker** (3.9), **DeepHoldem family** (3.7): no
    usable pre-trained no-limit strategy, or dead stack, or 120 GB.

## 5. Recommendation

Adopt **NoRegrets** first as the strategy source for 2 to 6 players: it is the
only verified, living, open project that produces a multi-player no-limit
strategy in hours rather than days, and it replaces the vendored short-deck
fixed-limit trainer that this project has already ruled out. The first job is
a half-day spike to confirm it builds and trains on the operator's Mac (marked
UNVERIFIED above) and to measure its play against Slumbot ourselves. Combine it
with three things: (1) a Python per-opponent memory copied in design from
OpenHoldem's `pt_` symbols, keyed on the stable player names the operator's
app shows, holding VPIP/PFR/aggression/fold-to-bet per name and shifting the
blueprint's call, bluff and value thresholds against each named player, which
is the only part of the operator's requirement no ready-made project supplies;
(2) a Mac-native capture pipeline built the way poker-gto-rt does it (YOLO +
OCR on screenshots of the operator's app), since every finished scraper is
Windows-only; and (3) Slumbot's free API as the standing heads-up benchmark.
For 7 to 9 seats, where no open blueprint exists, fall back to dickreuter's
Monte Carlo equity decision code (Python, GPL) driven by the same per-name
memory, and revisit Deep CFR 6-player only if its authors publish a trained
model. Do not buy PokerSnowie or PokerBotAI for this: neither can be called by
our code, and neither runs on the Mac.

## 6. What could not be verified

- NoRegrets and Deep CFR 6-player building on macOS; NoRegrets' commercial
  blueprint price.
- Warbot's price and current state (site blocks automated readers).
- GTO Wizard's prices from the vendor itself, and whether any API exists
  (none found).
- PokerBotAI's per-opponent profiling claim (closed software).
- Whether DecisionHoldem's Baidu blueprint link still serves outside China.
- PokerSnowie desktop full-ring support (reviewer source only) and the exact
  annual price ($16.66/month on the site's data; $229.95/year per reviewer).
- Whether any complete free OpenPPL/Shanky cash profile exists that
  ppl-interpreter can run.
- TexasSolver multiway support.
