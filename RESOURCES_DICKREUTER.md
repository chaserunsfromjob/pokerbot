# dickreuter/Poker: what it is, whether it runs, and what "based on it" could mean

The operator asked, on 2026-09-17: *"the bot should be based off of openspiel or
whatever, but also should be dickreuter. check the dickreuter poker bot to see
if it seems good to base it off of and add that in if you think its good."*
This document is that check. It decides nothing; `CLAUDE.md` is untouched.

Everything below was read or run on **2026-09-17 between 00:47 and 01:11 UTC**,
on the operator's Windows 10 PC (Windows 10 Home 19045, Python 3.13.15). Every
web address carries the code the server gave back and the minute it was read.
Anything that could not be confirmed by visiting or running it is marked
**UNVERIFIED** rather than guessed. The full list of addresses fetched and
commands run is the verification log at the end.

Companion documents by other workers cover engines (`ENGINE_ALTERNATIVES.md`),
solvers (`RESOURCES_SOLVERS.md`), ready-made bots (`RESOURCES_BOTS.md`) and
opponent exploitation (`RESOURCES_EXPLOITATION.md`). This one covers exactly one
project.

---

## In plain words

`dickreuter/Poker` is a real, finished poker bot that has been played for money.
It does three jobs, and they are worth keeping apart, because the answer to the
operator's question is different for each one.

1. **It looks at the poker room's window on screen and works out what is
   happening.** Which two cards are yours, which cards are face up in the
   middle, how much money each person has, whose turn it is, which buttons are
   showing and what numbers are printed on them. It does this by comparing small
   pictures it was taught earlier against the pixels on screen, and by reading
   the printed numbers the way a scanner reads a page. Teaching it a new poker
   room is done by hand, in a window of its own: you take a photograph of the
   screen, drag a box around each thing, and press a button to save it. **This
   part is genuinely good, and it is the part this project cannot easily write
   itself.** It is also the part `CLAUDE.md` already points at.

2. **It decides what to do.** This part is a long list of hand-written rules
   with numbers in them — "if my chance of winning is above 0.62, and nobody has
   raised, and this is the flop, then bet half the pot". The numbers sit in a
   settings sheet a person can edit. There is no solver anywhere in it: nothing
   works out a strategy that cannot be beaten; nothing looks ahead. The author
   calls the thing that adjusts those numbers a *genetic algorithm*, but reading
   the code shows it is nothing of the sort — it is a short list of if-statements
   that nudge eight numbers up or down by fixed amounts after a batch of hands,
   at most two of them per run (`poker/decisionmaker/genetic_algorithm.py`,
   whole file, 160 lines). **This part is the opposite of what `CLAUDE.md`
   demands**, and the rest of this document is mostly about that collision.

3. **It clicks the buttons**, moving the mouse in a wobbly, human-looking way,
   optionally inside a separate pretend computer running on the same machine so
   that it does not fight you for the mouse.

Four things surprised me on reading it, and all four change the answer:

- **There is no opponent modelling at all.** The description and the folklore
  both suggest there is. There is not. The code that would read other players'
  names off the screen is commented out and the function returns immediately
  (`poker/scraper/table_screen_based.py:258-278`). The one place the decision
  maker asks about a specific opponent calls a function
  (`get_flop_frequency_of_player`) **that does not exist anywhere in the
  project** — I searched every file. The call sits inside a `try` that swallows
  the error, so it silently does nothing, every hand, forever
  (`poker/decisionmaker/decisionmaker.py:246-262`). No count of how often anyone
  plays, raises, or folds is kept about anybody. On the criterion the operator
  cares most about — beating a *named* person — this project scores zero.

- **It cannot run without the author's server.** The cards it matches against,
  the co-ordinates of every box on every table, the settings sheets, and the
  trained picture-recogniser are all downloaded from `dickreuter.com:7778` every
  time it starts. None of them are in the public code. I pointed the program at
  a dead address and it crashed outright rather than falling back to anything
  local. The server is alive today and lets a guest account read; that is a
  thread the project would be hanging from.

- **Its "chance of winning" number counts a split pot as a win.** I measured
  this. Asked how often ace-king of one suit beats one unknown hand, it answers
  0.6815. An independent count with `treys`, over the same number of deals, puts
  the true figure at 0.6710 once split pots are halved, and 0.6795 if you count
  every split as a whole win. Its answer matches the second. So every number the
  decision rules are compared against is quietly about one point too high
  heads-up, and more than that on boards where the cards in the middle are the
  best hand.

- **Its own tests do not test the decisions.** All fourteen tests of the
  decision maker are switched off in the source, with the note "Fix access
  issues". What is left and passing is the picture-reading and the draw
  counting.

The recommendation, in one sentence: **take its shape and its eyes, not its
brain.** Details, and the four things "based on dickreuter" could mean, are in
§5 and §7.

---

## How it is rated

Same five criteria and same 0-to-3 scale as `RESOURCES_SOLVERS.md`, so the two
documents can be read side by side. 3 is best.

- **(a) 2 to 9 players** — does it produce decisions for 3+ player spots?
- **(b) true no-limit sizing** — arbitrary bet sizes, not a fixed menu?
- **(c) exploit specific opponents** — can it be biased by an opponent model, or
  does it play the same way against everyone?
- **(d) reachable in hours on one laptop** — no multi-day compute; runs here.
- **(e) licence or price acceptable** — for a **public GPL-3.0** project. Note
  this differs from `RESOURCES_SOLVERS.md`, which was written when pokerbot was
  private; the operator's later decision makes the repository public and
  GPL-3.0, so (e) now means "can we legally publish code derived from it".

The score is in §4, after the evidence.

---

## 1. What it is, part by part

The version read is commit `cae3a108b6cbf22ed8ef90bc0e70f790346289a4`, "fix
config", 2025-06-26, the tip of `master`, cloned at 00:47 UTC on 2026-09-17.
68 Python files, 14,449 lines, of which 5,329 sit in two vendored third-party
folders (`poker/vboxapi` 4,539 lines, `poker/pymouse` 790). So dickreuter's own
code is about **9,100 lines**.

### 1.1 The table-state capture — the good part

Two ways of reading the cards, and the table decides which:

**Picture matching.** `poker/tools/screen_operations.py:33` calls OpenCV's
`cv2.matchTemplate(screenshot, template, cv2.TM_SQDIFF_NORMED)` — it slides a
small stored picture over the screenshot and reports the best-fitting spot and
how good the fit is. Every card face, every button, the dealer button and the
face-down card backs are stored pictures. `poker/scraper/table_scraper.py`
loops over all 13 ranks and 4 suits in two areas of the screen to find your two
cards and the cards in the middle.

**A trained picture recogniser.** If a table is marked for it, cards go through
a small convolutional neural network instead — six convolution layers, then
layers of 2,048 and 1,024, trained for up to 50 passes over pictures generated
by wobbling, shifting and zooming the stored card templates
(`poker/scraper/table_scraper_nn.py:107-185`). Cards are squashed to 15 by 50
pixels first. The point of it is tolerance: a table whose cards slide or fade
defeats exact picture matching. Training needs TensorFlow; *using* a trained one
needs TensorFlow too, because the model is rebuilt from a description the server
sends (`poker/main.py:156-167`).

**Reading the printed numbers.** Pot sizes, stacks and button amounts go through
Tesseract, the standard open-source text-from-pictures program, via `tesserocr`
(`poker/tools/screen_operations.py:11,106,291`). The repository ships 15 MB of
Tesseract language data in `tessdata/`.

**What it hands over.** After a successful read (`poker/main.py:171-200` runs
twenty-odd steps in a row and stops at the first failure), the table object
holds: your two cards; the cards in the middle; the stage (PreFlop / Flop /
Turn / River); how many seats; for each other player their seat, whether they
are still in the hand, their money and the chips they have pushed in; where the
dealer button is and how many seats after the first to act you are; your own
money; the pot this round and the pot in total; whether a check button, a call
button, a bet button, an all-in-call button are showing, and the amounts printed
on them. **That is exactly the structure this project needs**, and it is the
list to copy.

**Adding a new poker room.** The README documents it and there is a video link.
In the program, press *Table setup*: give the template a name, press *Blank
new*, press *Take screenshot*, drag a box around the top-left corner of the
poker window and save it (everything else is measured from there), press *Crop*,
then drag a box around each item in turn — the button area, the card areas, the
pot, each seat — pressing the matching save button each time, and separately
teach it every card face and every button picture. Each save is a network call
to the author's server (`poker/scraper/table_setup_actions_and_signals.py`,
`mongo.save_coordinates`, `mongo.update_table_image`, lines 219-438), and the
server refuses if the computer's name is not the table's registered owner
(`get_table_owner`, line 213). **There is no way to store a table locally.**

### 1.2 The decision maker — where the poker decision is actually made

One file, one entry point. `poker/main.py:206-207`:

```
d = Decision(table, history, strategy, self.game_logger)
d.make_decision(table, history, strategy, self.game_logger)
```

`make_decision` is `poker/decisionmaker/decisionmaker.py:582-615`. Everything
below happens inside `Decision`:

1. **`Decision.__init__` (lines 32-277) sets two limits.** The long constructor
   turns the settings sheet plus the table reading into one *maximum amount I am
   willing to call* (`finalCallLimit`) and one *maximum amount I am willing to
   bet* (`finalBetLimit`). Both come out of `Curvefitting`
   (`poker/decisionmaker/curvefitting.py`), which fits the curve
   `y = adj1 * (x + adj2) ** pw` through two points — at the minimum chance of
   winning the answer is one big blind, at certainty it is your whole stack —
   and reads off the amount for the chance of winning just measured. `pw`, the
   curvature, is `FlopCallPower`, `TurnBetPower` and so on from the sheet.
   Before that it applies about a dozen hand-written adjustments: for your seat,
   for whether somebody raised, for whether somebody called, for how big the pot
   is, for the second time round the same betting round, and for how many cards
   would improve your hand.

2. **`calling` (353-363) and `betting` (365-432) compare those limits against
   what the buttons say.** If the call limit is below the price, fold; otherwise
   call. If the bet limit clears a threshold, pick one of four bets.

3. **Or, before the flop, a spreadsheet decides.** If `preflop_override` is on,
   `preflop_table_analyser` (278-340) looks your two cards up in a sheet of
   `preflop.xlsx`, chosen by how many people raised and called ahead of you,
   reads a *call* probability and a *raise* probability off the row, draws a
   random number, and folds, calls or raises accordingly. (The `Default`
   strategy the server hands a guest has `preflop_override: 0`.)

4. **`bluff` (434-471), `check_deception` (473-504) and `bully` (509-528)** may
   override the answer. All three are threshold rules, and `bluff` only fires
   when `isHeadsUp` is true.

5. **`admin` (530-580)** converts the chosen action into an amount and fixes up
   impossible combinations.

**So: the poker decision is made by hand-written if-statements in
`poker/decisionmaker/decisionmaker.py`, using thresholds from a settings sheet,
against a chance-of-winning number from `montecarlo_python.py`.** Nothing
searches, nothing solves, nothing looks ahead.

**The bet sizes are a menu of five**, set in `admin` (557-573): the table's own
minimum bet; minimum plus `BetPlusInc` big blinds; half the pot; the whole pot;
and a bluff of half the pot. Not arbitrary amounts.

**The one opponent-aware branch is dead.** Lines 246-262 try to fetch
`l.get_flop_frequency_of_player(t.PlayerNames[0])` and, on the answer, add or
subtract 2 from both curvature numbers. `t.PlayerNames` is assigned nowhere in
the project (the only three mentions are these lines) and `GameLogger` has no
method of that name (its methods are listed at
`poker/tools/game_logger.py:20-204`). The bare `except` swallows it, the value
becomes "not a number", both comparisons are then false, and the adjustment is
always 0. Searching the whole project for `vpip`, `pfr`, `aggression`,
`fold_rate`, `player_stats` or `opponent_model` returns **nothing**.

### 1.3 The equity Monte Carlo

`poker/decisionmaker/montecarlo_python.py`, 491 lines, pure Python.
`run_montecarlo` (line 238) deals the unknown cards at random up to `max_runs`
times, ranks everybody's seven cards with its own `calc_score`/`eval_best_hand`
(lines 52-159), and counts how often you come out on top.

**Measured on this PC** (5,000 deals each, one core; command and output in the
log):

| Spot | Answer | Wall time | Deals per second |
| --- | --- | --- | --- |
| AKs, 2 players, before the flop | 0.688 | 0.40 s | 12,493 |
| AKs, 3 players, before the flop | 0.508 | 0.49 s | 10,154 |
| AKs, 6 players, before the flop | 0.332 | 0.75 s | 6,643 |
| AKs, 3 players, flop 7h 8h 9c | 0.245 | 0.44 s | 11,323 |
| AKs, 6 players, flop 7h 8h 9c | 0.082 | 0.70 s | 7,142 |

Fast enough to answer inside a second, which is all it needs to be. For scale,
`RESOURCES_SOLVERS.md` measured OMPEval in C++ at 160 to 312 **million** hands a
second; this is about twenty-thousand times slower, and still fast enough.

**It counts split pots as wins.** 200,000 deals of AKs against one unknown hand
gave **0.6815**. An independent 200,000-deal count with `treys` — the outside
hand-ranking library this project already uses to check its tests — gave
win 0.6625, split 0.0170, lose 0.3205: **0.6710** when splits are halved,
**0.6795** when every split counts as a win. dickreuter's answer matches the
second, ten standard errors away from the first. Reading the code confirms why:
`eval_best_hand` sorts by score and takes the first, and Python's sort is
stable, so a tie always resolves in favour of seat 0, which is you.

**It also assigns ranges to opponents.** `get_opponent_allowed_cards_list`
(line 37) reads `preflop_equity.json`, sorts the 169 starting-hand classes by
strength and keeps the strongest slice — `range_utg0` through `range_utg5` and
`range_multiple_players` in the settings sheet decide how big a slice, by the
opponent's seat. That is a hand-written range assumption, not a measured one.

**And it caps how many opponents it simulates.**
`montecarlo_python.py:346-347`: `max_assumed_players = t.total_players - 2`,
then `assumedPlayers` is clamped between 2 and that. On a 6-seat table it never
simulates more than 4 players, whoever is actually in the hand. No comment
explains why.

### 1.4 The "genetic algorithm"

`poker/decisionmaker/genetic_algorithm.py`, 160 lines, read end to end. It is
**not** a genetic algorithm: there is no population, no crossover, no mutation,
no selection. `improve_strategy` runs eight fixed checks — call and bet, for
each of the four betting rounds — each comparing money won against money lost in
the stored log, and each may nudge one minimum-chance-of-winning number by 0.01
to 0.03 and one curvature number by 25 times that, up or down. At most two
changes per run. The result is saved as a new settings sheet on the author's
server. The README says you need 2,000 to 5,000 hands before the numbers mean
anything. It is a manual tuning aid, and honest people should call it that.

### 1.5 The GUI

PyQt6. Seven window layouts in `poker/gui/ui/*.ui`: the main window, table
setup, the strategy editor, the strategy analyser, the tuner, the updater and
help. The analyser draws stacked bars of what each action type won and lost at
each stage, so a person can walk backwards from the river tightening numbers.
There is also a small React web front end in `website/` and a tiny local web
service (`poker/restapi_local.py`) that does one thing: hands the browser a
screenshot.

### 1.6 The remote dependency — still there, still required

It is no longer a MongoDB the program talks to directly. `pymongo` is listed in
the requirements but **is imported nowhere in the project** — I grepped. What
exists now is `poker/tools/mongo_manager.py`, which sends web requests to a
single address read from `poker/config.ini`:

```
db = https://dickreuter.com:7778/
login = guest
password = guest
```

Everything comes from there: `get_table` (all card pictures and box
co-ordinates), `get_strategy` and `get_playable_strategy_list` (the settings
sheets), `get_tensorflow_weights` (the trained recogniser),
`get_available_tables`, `save_coordinates`, `update_table_image`,
`save_strategy`, `increment_plays`, `get_rounds`, `get_internal` (which returns
the download link, the current version number, the purchase link, and the
address of the before-the-flop spreadsheet). The server code is **not** in the
repository. `pymongo` is dead weight in the requirements list.

**It is alive today.** At 00:51-00:52 UTC on 2026-09-17, as an anonymous guest:
`get_internal` returned 200 with the current version 6.76;
`get_available_tables` returned 200 and a list of about 70 table templates
including "Official GGPoker 6player", "Official Party Poker" and "PokerStars";
`get_strategy?name=Default&login=guest&password=guest` returned 200 and a full
settings sheet; `get_playable_strategy_list` returned 200 and
`["Official 1","Trial 1","Trial 2","Trial 3"]`. Fetching one whole table
definition, "Official GGPoker 6player", returned 200 and **532,771 bytes** — 103
keys of card pictures and co-ordinates.

**Offline it does not degrade, it stops.** `read_strategy`
(`poker/tools/strategy_handler.py:118-139`) wraps its first request in `try`,
but the fallback inside the `except` is *another* network request, unguarded. I
copied the tree, pointed `db` at a dead port, and called it:

```
read_strategy RAISED: ConnectionError HTTPConnectionPool(host='127.0.0.1',
port=9): Max retries exceeded with url: /get_strategy?name=Default&
login=guest&password=guest
```

There is one local fallback of any kind — a copy of the before-the-flop
spreadsheet at `poker/decisionmaker/preflop.xlsx`, named as
`preflop_url_backup` in `poker/tools/update_checker.py:18`. Nothing else.

**What that means for this project:** if the author turns the server off, or
locks the guest account, or the domain lapses, every table template and every
settings sheet becomes unreachable. Only what has already been downloaded
survives, and the program has no code path to read it back from disk. Anyone
depending on the capture layer should pull the table definitions down and store
them locally as the very first step.

### 1.7 Rooms, and which computers it runs on

**Rooms.** The repository description names PartyPoker, PokerStars and GGPoker,
and the README gives per-room setup: PartyPoker "Fast Forward" tables, PokerStars
"Zoom" tables with the client forced to 4-colour cards and a matching table
style, and a pictured GGPoker layout. The server's table list also shows
community-made templates for ClubGG, PokerNow, ACR, Bet365 and others. The
README's FAQ says plainly: **"Currently the bot only works for tables with 6
players."** The table-setup window offers a seat count of 6 (default), 2, 3, 4,
5, 7 and 8 — **never 9**. The "Official GGPoker 6player" definition carries no
seat-count key at all, so it falls back to 6
(`poker/scraper/table_scraper.py:19`).

**Operating systems.** The README: *"The current version Only works on
windows."* Its own automated tests run on `windows-latest` with Python 3.11.
But the picture is more mixed than that sentence:

- There **is** a `requirements_mac.txt` and a macOS build recipe
  (`.github/workflows/release mac.yml`, Python 3.11, PyInstaller). It is
  manual-trigger only.
- **No macOS build has ever been published.** All five releases carry exactly
  one file, `DeepMindPokerbot_winstaller.exe`.
- The mouse layer genuinely is cross-platform: `poker/pymouse/__init__.py`
  picks `mac.py` (Quartz/AppKit) on macOS, `windows.py` on Windows, `x11.py`
  otherwise. Screenshots use Pillow's `ImageGrab.grab()`, which works on macOS.
- But `poker/tools/screen_operations.py:16` imports `vbox_manager`, which
  imports the `virtualbox` package unconditionally, so even the picture-reading
  module drags in VirtualBox automation on any platform; and
  `poker/pymouse/windows.py` needs `pywin32`, which is **not in either
  requirements file** (I found this the hard way — see §3).

**So can a Mac run any of it?** The reading-and-deciding half, almost certainly
yes with small edits; a Mac build recipe exists and the platform-specific pieces
all have Mac branches — but no one has published a Mac build and I did not test
one, so treat that as **UNVERIFIED**. The *point* of it on a Mac is another
matter: PokerStars, PartyPoker and GGPoker desktop clients are Windows programs,
and the whole design assumes a Windows poker client, ideally inside a Windows
virtual machine. **This PC is Windows 10, which is the supported case.**

---

## 2. The facts

| Fact | Value | How confirmed |
| --- | --- | --- |
| Licence | **GPL-3.0** | GitHub API `license.spdx_id = GPL-3.0`, HTTP 200, 00:52 UTC 2026-09-17; and `license.txt` in the clone is the verbatim 673-line GNU GPL v3 text, no added exceptions |
| Last push | **2025-06-26T21:29:10Z** | GitHub API `pushed_at`, HTTP 200, 00:52 UTC 2026-09-17 |
| Last commit | `cae3a108`, "fix config", 2025-06-26, Nicolas Dickreuter | `git log -1` in the clone |
| Stars | **2,463** | GitHub API, same call |
| Forks / watchers | 589 / 147 | GitHub API, same call |
| Open issues and pull requests | **34** | GitHub API `open_issues_count`; the list call returned 34 items, 25 issues and 9 pull requests |
| Created | 2016-03-29 | GitHub API |
| Repository size | 155,507 KB reported; **92 MB** on disk after a shallow clone | GitHub API; `du -sh` |
| Archived / disabled | No / No | GitHub API |
| Python required | **3.11** | Its own test workflow pins `python-version: 3.11`; the README tells you to install a `cp311` Tesseract wheel; `tensorflow==2.12.0` and `pandas==2.0.3` both publish wheels only for cp38 to cp311 (PyPI API, HTTP 200, 00:56 UTC) |

**Dependencies and weight.** `requirements_win.txt` lists 29 packages;
`requirements_mac.txt` the same, with `tensorflow` unpinned and `tesserocr`
pinned. Nine are pinned on Windows: `pandas==2.0.3`, `matplotlib==3.7.2`,
`pyinstaller==5.13.0`,
`pymongo==4.3.3`, `numexpr==2.8.4`, `fastapi==0.101.1`, `uvicorn==0.23.2`,
`PyJWT==1.7.0`, `tensorflow==2.12.0`, `tesserocr==2.6.1`.

- **TensorFlow: yes, and it is the heavy item.** `tensorflow==2.12.0`. On
  Windows the published `tensorflow` wheel is a 1,916-byte stub that pulls
  `tensorflow-intel`, whose Windows wheel is **272.9 MB**; the Linux wheel is
  **586 MB** and the macOS one 230 MB (PyPI API, HTTP 200, 00:56 UTC). It is
  CPU-only — no CUDA, no GPU stack. It is needed *at runtime* for any table
  marked as using the trained recogniser, not only for training.
- **OpenCV: yes**, `opencv-python`, about 44 MB of wheel on Windows.
- **Tesseract: yes**, via `tesserocr`, plus 15 MB of bundled language data.
- **Qt: yes**, PyQt6, about 85 MB of wheel.
- **Missing from the list: `pywin32`.** The mouse code imports `win32api` and
  the requirements never ask for it. Collection of the test suite fails without
  it.
- **Also listed but never imported anywhere in `poker/`:** `pymongo`, `PyJWT`,
  `flask_jwt_extended`, `fastapi_auth`, `jupyter`. Checked by searching every
  Python file for each import. (`xlib` *is* used, by the Linux mouse backend.)
- **The Dockerfile and README both say `pip install -r requirements.txt`, and no
  file of that name exists in the repository.** Only `requirements_win.txt` and
  `requirements_mac.txt`. The Docker build recipe is therefore broken as
  written.

Installing the seventeen packages the code actually needs, **without**
TensorFlow, came to **710 MB** in the private install area on this PC (54
packages once their own dependencies are counted). PyQt6 added a further 229 MB.
With TensorFlow, budget about 1.2 GB. The README asks for 1.6 GB of disk.

**Release binaries.** Five releases, all in January 2024, each carrying one
file, `DeepMindPokerbot_winstaller.exe`. The newest,
`DeepermindPokerbot-10` (2024-01-28), is **445.6 MB** and has been downloaded
**11,429 times**. No source archives, no macOS build. (GitHub API, HTTP 200,
00:52 UTC 2026-09-17.)

**The vendor website.** `http://deepermind-pokerbot.com/` and
`https://deepermind-pokerbot.com/` both return **200** (1,304 bytes, a small
React page). But the address printed in the README and in the repository
description, **`http://www.deepermind-pokerbot.com`, is broken**: it redirects to
`https://www.deepermind-pokerbot.com/`, where the connection fails outright
(curl exit, code reported as `000`). That is almost certainly the cause of open
issue #241. The paid "full version" — the right to create and see all settings
sheets — is sold from that site, or by e-mail, or for Bitcoin to an address
printed in the README.

**Open issues that say whether it works today.** The 34 open items, newest
first, read as an alive-but-thin project:

- **#241 "Can't download from deepermind-pokerbot.com"** (2025-09-17). The
  author replied the same day: *"Just tried it and it seems to work fine. What
  error are you getting?"* The reporter came back with a screenshot and then
  found the installer in the GitHub releases instead. Consistent with the broken
  `www.` address above.
- **#240 "Program won't open because of JSON-Error"** (2025-04-25, 3 comments).
  The error text in `mongo_manager.get_table` names exactly this: a table marked
  as using the trained recogniser when none has been trained.
- **#228 "Detected by pokerstars"** (2024-02-13, 5 comments). A user reports
  being caught. Others ask what happened. **This is the single most important
  open issue for the operator**, and it matches the README's own warning that on
  PokerStars *"you will be blocked and your account will be frozen within
  minutes"* without a virtual machine.
- **#185 "Bot is far too predictable, improvement strategy advices"**
  (2023-05-23, 3 comments). An honest assessment of the decision maker by a
  user.
- **#194, #178, #174** are all picture-reading or number-reading failures on
  particular tables — the ordinary maintenance load of a screen scraper.
- Nine of the 34 are pull requests, the oldest from May 2023, several of them
  automated security bumps that were never merged.

**Is it maintained?** Partly. Last code change **2025-06-26**, about fifteen
months before this reading. Last release January 2024. Several dependency
security bumps left open for over three years. **But the author still answers**:
he replied to issue #241 on 2025-09-17, one day after it was opened. There is a
Discord. The repository is not archived. The automated test workflow exists but
**the GitHub API reports zero recorded workflow runs** (`total_count 0`, HTTP
200, 00:57 UTC) — so nothing has been checked automatically in the window GitHub
still keeps.

Read that as: **a finished project in light custody, not an abandoned one, and
not one under development.**

**Licence compatibility with pokerbot.** pokerbot is going GPL-3.0, so taking
GPL-3.0 code and publishing the result is exactly what the licence contemplates
— keep the notices, keep the source public. Two wrinkles:

1. **`poker/vboxapi/` is not GPL-3.0.** It is Oracle's VirtualBox glue, and its
   header reads *"under the terms of the GNU General Public License (GPL) ... in
   version 2"*, or alternatively the CDDL version 1.0. GPL **version 2 only** is
   *incompatible* with GPL-3.0, and so is the CDDL. That folder is 4,539 lines,
   it is **imported nowhere else in the project**, and it must not be copied
   into pokerbot. `poker/pymouse/` is fine: version 3 "or any later version".
2. **The table templates and settings sheets carry no licence at all.** They are
   not in the repository; they live on the author's server, and they are
   pictures of PokerStars, PartyPoker and GGPoker client windows. Whether they
   may be redistributed is **UNVERIFIED** and would have to be asked.

Also worth saying once: dickreuter's own `.py` files carry **no per-file licence
header**, and the copyright line in the "how to apply this licence" section of
`license.txt` was never filled in. That is untidy but does not change the
repository-level GPL-3.0 declaration.

---

## 3. Does it run on this PC

Short answer: **yes, and its picture-reading half passes its own tests here —
but only after fixing four things the project does not tell you about, and not
on the Python this project uses.**

**The clone.** `git clone --depth 1 https://github.com/dickreuter/Poker`, 86
seconds, 92 MB (41 MB of that the repository history, 28 MB of documentation
pictures, 15 MB of Tesseract data, 5 MB of actual code).

**The install as documented: fails immediately.** A fresh private install area
made with this PC's `Python313\python.exe` (Python 3.13.15), then
`pip install -r requirements_win.txt`. It got as far as the first line and
stopped, 29 seconds in:

```
Collecting pandas==2.0.3 ...
  Downloading pandas-2.0.3.tar.gz (5.3 MB)
  ...
  ModuleNotFoundError: No module named 'pkg_resources'
ERROR: Failed to build 'pandas' when getting requirements to build wheel
```

`pandas==2.0.3` has no ready-made build for Python 3.13, so pip tried to build
it from source and the build failed. **Its pins top out at Python 3.11**, which
is what its own test workflow uses. This PC has only Python 3.13 installed
(`C:\Users\chase\AppData\Local\Programs\Python\` contains `Python313` and
nothing else; no `py` launcher; no Anaconda). As instructed, I tried anyway, and
then went round it.

**Going round it.** Installing the packages the code actually imports, with the
version numbers **taken off**, on Python 3.13 worked: 49 packages pulled in, no
source builds, nothing touching a GPU. TensorFlow was
left out deliberately — it has no Python 3.13 build at all, and pulling 273 MB
for a code path we would not use was outside the time box. Four further things
were needed that the project's own instructions do not mention:

1. **`tesserocr`** is not on PyPI for Windows. The project's test workflow
   downloads a third-party Windows build for Python 3.11. That third party does
   publish a **Python 3.13** build — `tesserocr-2.10.0-cp313-cp313-win_amd64.whl`
   (GitHub API, HTTP 200, 01:01 UTC) — and it installed cleanly.
2. **`virtualbox`** (the `pyvbox` package, Apache-2.0, 275 KB) is in the
   requirements list, but I had left it out; the picture-reading module imports
   it unconditionally, so it is not optional even if you never use a virtual
   machine.
3. **`pywin32`** is **not in the requirements list at all**, and the mouse code
   needs it. This is a genuine gap in their file.
4. **PyQt6 would not install into the scratch folder** because the path was too
   long for Windows' 260-character limit, which is this PC's setting, not
   dickreuter's fault. Installing it under a shorter path worked.

**Total install time**, everything included, about **4 minutes** of wall time
across the attempts, well inside the ten-minute box. Disk: 710 MB, plus 229 MB
for the second Qt install area.

**The test suite.** The README says to run `pytest` from the repository root,
which is what the project's own workflow does. Result on this PC:

```
SKIPPED [14] poker\tests\test_decision.py: Fix access issues
FAILED poker/tests/test_montecarlo.py::TestMonteCarlo::test_monteCarlo
FAILED poker/tests/test_tensorflow.py::test_save_model
FAILED poker/tests/test_tensorflow.py::test_train_card_neural_network_and_predict
================== 3 failed, 28 passed, 14 skipped in 53.63s ==================
```

45 tests collected. Reading each result:

- **14 skipped**: every test of the decision maker, switched off in the source
  with `@pytest.mark.skip(reason="Fix access issues")`. Two more test files are
  switched off entirely (`test_reverseTables.py`, `test_tableScreenBased.py`),
  so three of the seven test files never run.
- **1 genuine upstream failure**: `test_monteCarlo` calls
  `run_montecarlo(maxRuns=...)` but the function was renamed to `max_runs`.
  `TypeError: MonteCarlo.run_montecarlo() got an unexpected keyword argument
  'maxRuns'. Did you mean 'max_runs'?` A stale test, broken on any Python, on
  any machine.
- **2 failures caused by leaving TensorFlow out**, plus a missing
  `poker/pics/model.json` that is not in the repository anyway, so
  `test_save_model` would fail on a clean clone regardless.
- **28 passed**, and the interesting 24 of them ran cleanly on their own:

```
$ pytest poker/tests/test_table_and_ocr.py poker/tests/test_outs.py
........................
24 passed in 11.17s
```

Those 24 are **the capture layer and the draw counter**: cropping a screenshot,
finding the top-left corner, running the whole table scraper over a stored
screenshot, and reading pot and stack numbers off PartyPoker, PokerStars and
GGPoker screenshots — nine tests — plus fifteen tests of counting the cards that
would improve a hand. **They download the table definitions from the author's
server while they run.** So this is a live end-to-end confirmation that the
capture layer works today, on this machine, on Python 3.13, against the live
server.

**What the tests need that they do not say.** They need the network (the shared
setup code at `poker/tests/__init__.py:39-46` makes two server calls before any
test body runs). They do **not** need a display or a live poker table; every
screen they read is a stored `.png`. Nothing was launched that connects to a
poker site, and no table was played.

---

## 4. The rating

**dickreuter/Poker — Ratings: (a) 2 — (b) 1 — (c) 0 — (d) 2 — (e) 2.**

- **(a) 2 to 9 players — 2.** The decision code does branch on multiway
  (`isHeadsUp` guards the bluff and profile paths; `range_multiple_players`
  governs equity when more than one opponent is live), and the setup window
  offers 2 to 8 seats. But every official table is 6-handed, the README's FAQ
  says "Currently the bot only works for tables with 6 players", **9 is not
  offered at all**, and the equity simulation silently caps itself at
  `total_players - 2` opponents. Multiway in principle, six-handed in practice,
  never nine.
- **(b) true no-limit sizing — 1.** A menu of five: minimum bet; minimum plus
  N big blinds; half pot; pot; bluff of half pot. One of them is
  parameterised, which is why this is 1 and not 0.
- **(c) exploit specific opponents — 0.** No per-person memory of any kind; the
  only branch that would have used one calls a function that does not exist, and
  name reading is commented out. Not partly, not weakly — zero.
- **(d) reachable in hours on one laptop — 2.** No training of any kind is
  needed, and the equity simulation answers in well under a second (measured,
  §1.3), so on compute alone this is a 3. It loses a point because getting it
  running here needed a Python it does not support, four undocumented packages,
  and a live connection to somebody else's server — and because the Mac case,
  which `RESOURCES_SOLVERS.md` scores, has a build recipe but no published
  build and no test here.
- **(e) licence acceptable for a public GPL-3.0 project — 2.** GPL-3.0 and free,
  which is exactly right for a public GPL-3.0 project, and the price of the
  code is nothing. It loses a point for two real snags: the GPL-**2**-only
  `poker/vboxapi/` folder, which must not be copied; and the table templates,
  which are the part actually worth having, are not in the repository, are not
  licensed, and are pictures of commercial poker clients. The paid "full
  version" buys server privileges, not code, so it is not a barrier.

For comparison from `RESOURCES_SOLVERS.md`: OpenSpiel-style entries score (a) 2
to 3 and (b) 3; GTOpen scores (a) 2 — (b) 3 — (c) 3 — (d) 3 — (e) 3. dickreuter
is not in that company **as a source of poker judgment**, and is not trying to
be. As a source of *eyes*, nothing else in any of the four surveys competes.

---

## 5. The forefront rule: which parts sit on which side

`CLAUDE.md` says: *"Never let an AI model decide a poker action, evaluate a
hand, or read a board; call real engine code for that,"* and *"Only use
AI-written code for integration, tooling, table-state capture (screen to
structured data), and card combinatorics, never for poker judgment itself,"* and
*"Reject a change that adds hand-rolled hand-strength or decision logic in place
of the vendored engine; adapt the engine instead."* Its table has a left column
(allowed) and a right column (reserved to the engine).

**One thing has to be said first, because it decides everything after it.**
Nicolas Dickreuter is a person, not a language model, and his code is not
AI-written. So the rule's *first two* bullets, which are about AI-written code,
do not by themselves forbid using it. The *third* bullet does not mention who
wrote it: it rejects **hand-rolled hand-strength or decision logic in place of
the engine**, full stop. And the table's right column reserves those jobs "to
the engine" without saying whose hand wrote the alternative. So the real
question is not "is this AI-written" but **"does this count as engine code?"** —
and that is a judgment for the operator, not for me.

Sorting the files:

### Left column — allowed to us, no exception needed

| Part of dickreuter | Which allowed job |
| --- | --- |
| `poker/scraper/table_scraper.py`, `table_screen_based.py` | table-state capture: screen to structured data |
| `poker/scraper/table_scraper_nn.py` (the trained card reader) | same; it reads *which card*, never *how good* |
| `poker/tools/screen_operations.py` (picture matching, number reading) | same |
| `poker/scraper/table_setup_actions_and_signals.py` + the setup window | tooling |
| `poker/tools/mouse_mover.py`, `poker/pymouse/`, `poker/tools/vbox_manager.py` | integration |
| `poker/gui/`, `poker/tools/logger.py`, `poker/tools/helper.py` | tooling |
| `poker/tools/game_logger.py` | counting observed actions (our own) |
| `MonteCarlo.create_card_deck`, `get_two_short_notation` | card combinatorics — deck enumeration, hand-class naming, both named as ours to write |

### Right column — reserved to the engine

| Part of dickreuter | Which reserved job |
| --- | --- |
| `montecarlo_python.calc_score` / `eval_best_hand` (lines 52-159) | **Evaluating hand strength** — a hand-rolled 7-card ranker |
| `montecarlo_python.run_montecarlo` (the equity number) | **Evaluating hand strength** — it exists only to say how good your hand is, and it is built on the ranker above |
| `MonteCarlo.get_opponent_allowed_cards_list` + `preflop_equity.json` + `range_utg0..5` | **Assigning a range to an opponent** |
| `poker/decisionmaker/outs_calculator.py` (328 lines of flush draws, open-ended straights, gutshots) | **Reading board texture** |
| `decisionmaker.calling`, `betting`, `bluff`, `check_deception`, `bully`, `admin`, `make_decision` | **Choosing an action** |
| `decisionmaker.preflop_table_analyser` + `preflop.xlsx` | **Producing the strategy itself** |
| `poker/decisionmaker/curvefitting.py` | part of choosing an action — it converts a chance of winning into an amount of money |
| `poker/decisionmaker/genetic_algorithm.py` | **Producing the strategy itself** |
| `decisionmaker.py:246-262` (the dead player-profile branch) | **Combining live-field rates into a quantity that drives a poker decision** — it would turn one opponent's flop frequency directly into a curvature change. Dead, but it is the shape the rule names |

The split is clean and it falls exactly along the seam between the two halves of
the program. **Its eyes are entirely in the left column. Its brain is entirely
in the right column.** That is the whole finding in one line.

### What "based on dickreuter" could legitimately mean

**(i) Its capture layer only — what `CLAUDE.md` already records.**
Take the scraper, the setup window, the mouse mover, and the structure of the
table reading. Nothing else.
*Gains:* the hardest, least glamorous, most tedious part of the project,
finished and tested, with its own tests passing on this PC today (§3). A way in
to three named poker rooms and a documented way to teach a fourth.
*Gives up:* nothing.
*Permitted as written?* **Yes.** The rule names table-state capture explicitly.
*Cost to be honest about:* the table templates are on somebody else's server and
must be pulled down and stored locally before anything is built on them; and
`poker/tools/screen_operations.py` imports VirtualBox automation at the top of
the file, which would have to be untangled.

**(ii) Capture plus its equity Monte Carlo.**
Also take `montecarlo_python.py` to answer "how often do I win this hand".
*Gains:* a working chance-of-winning number, measured here at 6,600 to 12,500
deals a second, with ranges per seat already wired in. It saves a week.
*Gives up:* accuracy and trust. Its ranker is hand-rolled Python that counts
split pots as wins (measured, §1.3), its opponent ranges are hand-written
assumptions, and its own test of the simulation has been broken since a rename.
*Permitted as written?* **No.** Evaluating hand strength and assigning a range
to an opponent are both in the right column. It would need the operator's
carve-out — **unless** the ranking is replaced. Swapping `calc_score` for a real
external evaluator is a small, contained change, and it would put the loop back
on the right side of the line while keeping the useful shell. That is worth
saying plainly: **(ii) is one substitution away from being allowed.**

**(iii) Capture plus its whole decision maker, calling that "the engine".**
*Gains:* a bot that plays a real table this month. That is not nothing, and it
is the only option here that produces a playing bot quickly.
*Gives up:* the project. No solver, no looking ahead, five bet sizes instead of
any amount, six seats, and — the part that matters most — **no opponent
modelling at all**, which is stage 2 of the plan and the operator's stated
reason for the whole thing. Its own users say it plays predictably (issue #185).
And the thresholds are tuned by a routine that is called a genetic algorithm and
is not one.
*Permitted as written?* **No, and not close.** It would need the operator to
grant the standing exception in `CLAUDE.md` — *"Treat who chooses the action on
top of the engine as open and the operator's to settle; the exception to this
rule is not granted"* — and to widen it further, because this is not a chooser
sitting on top of an engine; it is a chooser instead of one.

**(iv) Its architecture as a template, with OpenSpiel supplying the decisions.**
Copy the *shape*: screen → one table-state structure → a decision → a mouse
click, with a settings file and a log. Take the capture code with it. Write the
decision side against OpenSpiel `universal_poker`.
*Gains:* everything (i) gains, plus a proven arrangement of the parts, worked
out over nine years against three live poker rooms, including the unglamorous
things a first attempt gets wrong — read the whole table before deciding
anything and abandon the read at the first failure; keep a memory of what you
did last time round this betting round; move the mouse on a wobbly path; keep
the poker client in a separate pretend computer.
*Gives up:* nothing, except that the decision side still has to be built.
*Permitted as written?* **Yes.** Architecture is not poker judgment.

---

## 6. How it would join to OpenSpiel `universal_poker`, concretely

**What dickreuter produces.** After one successful screen read, one object
holding: `mycards` (`['AS','KS']`), `cardsOnTable` (`['7H','8H','9C']`),
`gameStage`, `total_players`, `dealer_position`, `position_utg_plus`,
`myFunds`, `totalPotValue`, `round_pot_value`, `minCall`, `minBet`,
`checkButton` / `allInCallButton` / bet and raise button flags, and for each
other seat a small record: `utg_position`, `status` (still in the hand or not),
`funds`, `pot`.

**What OpenSpiel needs.** `universal_poker` is a wrapper around the rules engine
of the Annual Computer Poker Competition (its header says so at line 40;
fetched HTTP 200, 00:56 UTC 2026-09-17). A game is built from named settings
(`universal_poker.cc:152-212`): `numPlayers`, `numRounds`, `numSuits`,
`numRanks`, `numHoleCards`, `numBoardCards`, `stack` (one whole-chip figure per
player), `blind` (one per player), `firstPlayer`, `betting` (`"nolimit"`), and
`bettingAbstraction`. Setting `bettingAbstraction` to `fullgame`
(`BettingAbstraction::kFULLGAME`, header line 62) makes every whole-chip raise
amount its own legal move — genuine no-limit. The ceiling is **10 players**
(`kMaxUniversalPokerPlayers`, header line 52). Then the position in the hand is
reached by **replaying the actions** from the start: fold, call, bet, all-in
(header lines 56-58).

**The seam, named.** One structure and two converters:

```
TableScraper  --->  TableState  --->  universal_poker game + replayed state
 (dickreuter)      (ours, new)              (OpenSpiel, unchanged)
```

`TableState` is a plain record this project owns: seat count, my seat, the
button's seat, hole cards, board cards, each seat's chips and committed chips,
whose turn it is, and **the list of actions taken so far this hand**. Capture
fills it; a builder turns it into an OpenSpiel game and state. Four mismatches
have to be bridged there, and they are the whole of the work:

1. **A snapshot is not a history.** dickreuter reads the table as it is *now*.
   OpenSpiel needs the sequence of moves from the first card to this moment.
   Nothing in dickreuter accumulates that; its `History` object
   (`poker/decisionmaker/current_hand_memory.py`) remembers only its own last
   decision, and the per-hand round list it does keep comes from the author's
   server (`get_rounds`). **This project has to build the action history itself,
   by differencing consecutive screen reads.** It is the one piece of real new
   work the join demands, and it belongs squarely in the left column: counting
   observed actions.
2. **Money versus chips.** dickreuter reads dollars as floating-point numbers
   through a text scanner. OpenSpiel counts whole chips. Divide by the big blind
   and round, and decide once what a hundredth of a big blind does.
3. **Card spelling.** dickreuter writes `'AS'`, rank then suit, both capitals,
   suits `CDHS`. OpenSpiel's card sets use the usual lower-case suit. A ten-line
   mapping.
4. **Seat numbering.** dickreuter numbers seats anticlockwise from you, with you
   always 0. OpenSpiel numbers players 0 upward with the blinds at fixed
   positions. A rotation, computed from the dealer button.

**Licences fit.** OpenSpiel is Apache-2.0, which may be combined into a GPL-3.0
work; dickreuter is GPL-3.0; pokerbot is GPL-3.0 and public. The combination is
lawful in that direction, provided `poker/vboxapi/` is left behind (§2).

---

## 7. The four meanings, ranked, and one recommendation

**Ranked, best first:**

| Rank | Meaning | Allowed by the rule as written? | What it buys |
| --- | --- | --- | --- |
| **1** | **(iv)** Its architecture as the template, its capture layer as the eyes, OpenSpiel deciding | **Yes** | The finished hard part, plus a proven layout of the whole program |
| 2 | **(i)** Its capture layer only | **Yes** | The finished hard part |
| 3 | **(ii)** Capture plus its equity simulation | **No** — needs a carve-out, *or* one substitution to become yes | A week saved, at the cost of a number that is quietly wrong |
| 4 | **(iii)** Capture plus its whole decision maker as "the engine" | **No** — needs a wide, explicit carve-out | A playing bot soon, and the end of the project's actual goal |

### The recommendation

**Take option (iv): copy how dickreuter's program is put together, take its
screen-reading half, and let OpenSpiel make every poker decision.**

Three reasons, in the order they matter:

1. **The thing dickreuter is genuinely excellent at is the thing this project
   cannot buy anywhere else.** Reading a poker room's window and turning it into
   numbers is nine years of fiddly work against three commercial programs that
   keep changing. It works: on this PC, today, its picture-reading tests passed
   twenty-four out of twenty-four in eleven seconds. No solver, no engine and no
   other project in the four surveys does this job at all.

2. **The thing it is weakest at is the thing this project exists to do.** The
   operator's goal is to beat *specific* human beings by noticing how each of
   them plays. dickreuter keeps no record of any opponent whatsoever — not a
   weak version, not a partial version, none. Adopting its brain would not be a
   shortcut towards the goal; it would be a turn away from it.

3. **It costs nothing to take the shape as well as the eyes, and the shape is
   worth real time.** The arrangement — read everything, stop at the first thing
   you cannot read, decide once, click once, write it down, remember what you
   did last time round — is the part a first attempt gets wrong. Copying it is
   free and forbidden by nothing.

**What saying yes to this would mean, in practice, in order:**
(1) download and store locally every table definition the project needs, before
anything is built on them, because they live on somebody else's computer;
(2) copy the screen-reading, mouse-moving and table-setup code into the project
under GPL-3.0, keeping the notices, **leaving `poker/vboxapi/` behind**;
(3) untangle the VirtualBox import out of the screen-reading module so it is
optional; (4) define the one table-state structure named in §6 and write the
piece that builds the action history by comparing one screen read with the next;
(5) let OpenSpiel make every decision from there.

**What saying no would mean:** nothing is lost today. `CLAUDE.md` already
records dickreuter as the capture reference, and option (i) — which needs no
decision at all — is a subset of this recommendation.

**The one thing to decide separately, and soon:** option (ii). If the operator
wants a chance-of-winning number quickly, dickreuter's simulation is the fastest
route, and it is **one substitution away** from being allowed — replace its
hand-rolled card ranker with a real external evaluator and the loop stops
breaking the rule. That is a smaller question than the four above and can be
settled on its own.

**Not recommended:** option (iii). It would need the operator to grant an
exception `CLAUDE.md` explicitly says is not granted, and what it buys — a bot
that plays predictably, at six seats, with five bet sizes, against everyone the
same way — is not the bot that was asked for.

---

## Appendix A. Verification log

Every address fetched, with the code the server returned and the UTC time. All
fetched with
`curl -sL -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
(KHTML, like Gecko) Chrome/128.0 Safari/537.36" --max-time 40`, on 2026-09-17.
No browser was used.

| Time (UTC) | Address | Code | What it gave |
| --- | --- | --- | --- |
| 00:51:42 | `POST https://dickreuter.com:7778/get_internal` | **200** | version 6.76, installer link, purchase link, `preflop_url` |
| 00:51:59 | `POST https://dickreuter.com:7778/get_available_tables?computer_name=test` | **200** | ~70 table names incl. "Official GGPoker 6player", "Official Party Poker", "PartyPoker", "PokerStarsMesa3" |
| 00:52:08 | `POST https://dickreuter.com:7778/get_strategy?name=Default&login=guest&password=guest` | **200** | full settings sheet; `preflop_override: 0`, `bigBlind: 0.04`, `strategyIterationGames: 1013` |
| 00:52:10 | `POST https://dickreuter.com:7778/get_playable_strategy_list?login=guest&password=guest&computer_name=test` | **200** | `["Official 1","Trial 1","Trial 2","Trial 3"]` |
| 00:52:11 | `http://deepermind-pokerbot.com/preflop.xlsx` | **200** | 180,959 bytes |
| 00:52:32 | `https://api.github.com/repos/dickreuter/Poker` | **200** | GPL-3.0; 2,463 stars; 589 forks; 147 watchers; 34 open; pushed 2025-06-26T21:29:10Z; created 2016-03-29; size 155,507 KB; not archived |
| 00:52:40 | `https://api.github.com/repos/dickreuter/Poker/issues?state=open&per_page=40` | **200** | 34 items (25 issues, 9 pull requests), listed in §2 |
| 00:52:40 | `https://api.github.com/repos/dickreuter/Poker/releases?per_page=10` | **200** | 5 releases, all Jan 2024, one `.exe` each; newest 445.6 MB, 11,429 downloads |
| 00:52:40 | `https://api.github.com/repos/dickreuter/Poker/commits?per_page=10` | **200** | last commit `cae3a108` 2025-06-26 "fix config"; "add licence" 2024-01-18 |
| 00:56:17 | `https://raw.githubusercontent.com/google-deepmind/open_spiel/master/open_spiel/games/universal_poker/universal_poker.h` | **200** | 12,986 bytes; `kMaxUniversalPokerPlayers = 10` (l.52); `BettingAbstraction { kFCPA, kFC, kFULLGAME, kFCHPA }` (l.62); ACPC note (l.40) |
| 00:56:33 | `.../universal_poker/universal_poker.cc` | **200** | 72,804 bytes; game settings at ll.152-212 |
| 00:56:51 | `https://pypi.org/pypi/tensorflow/2.12.0/json` | **200** | builds only for cp38-cp311; Windows wheel 1,916 bytes (a stub) |
| 00:56:51 | `https://pypi.org/pypi/tensorflow/json` | **200** | latest 2.21.0, needs Python >= 3.10 |
| 00:56:51 | `https://pypi.org/pypi/pandas/2.0.3/json` | **200** | builds only for cp38-cp311 |
| 00:56:5x | `https://pypi.org/pypi/tesserocr/json` | **200** | no Windows builds published on PyPI |
| 00:56:5x | `https://pypi.org/pypi/tensorflow-intel/2.12.0/json` | **200** | `tensorflow_intel-2.12.0-cp311-cp311-win_amd64.whl` = **272.9 MB** |
| 00:57:38 | `https://api.github.com/repos/dickreuter/Poker/issues/241/comments` | **200** | author replied 2025-09-17, same day the issue opened |
| 00:57:38 | `https://api.github.com/repos/dickreuter/Poker/issues/228/comments` | **200** | 5 comments about a PokerStars detection |
| 00:57:51 | `https://api.github.com/repos/dickreuter/Poker/actions/workflows/python-tests.yml/runs` | **200** | `total_count 0` |
| 00:57:5x | `https://api.github.com/repos/dickreuter/Poker/actions/runs` | **200** | `total_count 0` |
| 01:01:37 | `https://api.github.com/repos/simonflueckiger/tesserocr-windows_build/releases?per_page=5` | **200** | Windows builds for cp39-cp314 incl. **cp313**; newest 2026-09-12 |
| 01:0x | `POST https://dickreuter.com:7778/get_table?table_name=Official%20GGPoker%206player` | **200** | **532,771 bytes**, 103 keys; `max_players` absent; `use_neural_network: 0` |
| 01:11:09 | `http://www.deepermind-pokerbot.com/` | **301 → fails** | redirects to `https://www.…`, which does not connect (curl reports `000`) |
| 01:11:16 | `https://deepermind-pokerbot.com/` | **200** | 1,304 bytes, "DeeperMind Pokerbot" React page |
| 01:11:16 | `http://deepermind-pokerbot.com/` | **200** | same, after redirect to https |

**UNVERIFIED, and why:**

- **Whether any of it runs on macOS.** A `requirements_mac.txt` and a macOS
  build recipe exist; no macOS build has ever been released; no Mac was
  available to this session.
- **Whether the trained card recogniser works.** TensorFlow has no Python 3.13
  build, so the two tests that use it were not run. Downloading the trained
  weights from the server *did* succeed (`test_load_nn_model` passed).
- **Whether the table templates may be redistributed.** They are not in the
  repository, carry no licence, and are pictures of commercial poker clients.
- **What the paid "full version" actually unlocks beyond creating and viewing
  settings sheets.** The purchase page was not bought from.
- **Whether the decision maker's 14 switched-off tests would pass.** They are
  switched off in the source with "Fix access issues"; I did not re-enable them.
- **How well the capture layer performs against a live table.** Nothing was
  launched that connects to a poker site, per the brief.

## Appendix B. What I ran

Scratch area:
`C:\Users\chase\AppData\Local\Temp\claude\C--Users-chase-heater\9b6e4e4f-09aa-4db9-b21b-ae800089dd8f\scratchpad\dickreuter\`.
Python: `C:\Users\chase\AppData\Local\Programs\Python\Python313\python.exe`,
**3.13.15**. Nothing outside the scratch area and this repository was changed.

**1. Clone.** 00:47:56 → 00:49:22 UTC, 86 s.
```
$ git clone --depth 1 https://github.com/dickreuter/Poker
Cloning into 'Poker'...
$ du -sh Poker
92M     Poker
$ git log -1 --format="%H %ad %an %s" --date=iso-strict
cae3a108b6cbf22ed8ef90bc0e70f790346289a4 2025-06-26T22:29:09+01:00 Nicolas Dickreuter fix config
```
Size breakdown: `.git` 41 M, `doc` 28 M, `tessdata` 15 M, `poker` 5.0 M,
`notebooks` 3.2 M, `website` 2.2 M. 68 Python files, 14,449 lines.

**2. The documented install, on Python 3.13 — failed.** 00:50:23 → 00:50:52.
```
$ python -m venv venv
$ venv/Scripts/python.exe -m pip install -r Poker/requirements_win.txt
Collecting pandas==2.0.3 (from -r Poker/requirements_win.txt (line 1))
  Downloading pandas-2.0.3.tar.gz (5.3 MB)
  Getting requirements to build wheel: finished with status 'error'
  ...
  ModuleNotFoundError: No module named 'pkg_resources'
ERROR: Failed to build 'pandas' when getting requirements to build wheel
EXITCODE=1
```
(`requirements.txt`, the file the README and the Dockerfile both name, does not
exist in the repository; `requirements_win.txt` is the Windows one.)

**3. The unpinned install — worked.** 00:58:10 → 00:59:59, plus three extras.
```
$ venv/Scripts/python.exe -m pip install pandas numpy scipy matplotlib \
    opencv-python pillow pytest requests openpyxl xlrd pyyaml lmfit \
    numexpr tqdm seaborn pymongo fastapi uvicorn
Successfully installed ... 49 packages ...
$ venv/Scripts/python.exe -c "import cv2,numpy,pandas;print(...)"
opencv 5.0.0 numpy 2.5.3 pandas 3.0.5
$ venv/Scripts/python.exe -m pip install \
    https://github.com/simonflueckiger/tesserocr-windows_build/releases/download/\
tesserocr-v2.10.0-tesseract-5.5.2/tesserocr-2.10.0-cp313-cp313-win_amd64.whl
Successfully installed tesserocr-2.10.0
$ venv/Scripts/python.exe -m pip install virtualbox
Successfully installed virtualbox-2.1.1
$ venv/Scripts/python.exe -m pip install pywin32      # not in requirements
Successfully installed pywin32-312
```
PyQt6 was installed separately under a shorter path because of this PC's
260-character path limit. TensorFlow was deliberately omitted: no Python 3.13
build exists and it is 273 MB. Final size: `venv` 710 MB, second area 229 MB.

**4. The test suite.** 01:02:39 → 01:03:53.
```
$ pytest
SKIPPED [14] poker\tests\test_decision.py: Fix access issues
FAILED poker/tests/test_montecarlo.py::TestMonteCarlo::test_monteCarlo
FAILED poker/tests/test_tensorflow.py::test_save_model
FAILED poker/tests/test_tensorflow.py::test_train_card_neural_network_and_predict
================== 3 failed, 28 passed, 14 skipped in 53.63s ==================
```
The three failures, one line each:
```
E TypeError: MonteCarlo.run_montecarlo() got an unexpected keyword argument
  'maxRuns'. Did you mean 'max_runs'?
E FileNotFoundError: [Errno 2] No such file or directory: '...\poker\pics/model.json'
E ModuleNotFoundError: No module named 'tensorflow'
```
45 tests collected in total. The capture and draw-counting tests on their own,
01:05:16 → 01:05:29:
```
$ pytest poker/tests/test_table_and_ocr.py poker/tests/test_outs.py -q
........................
24 passed in 11.17s
```

**5. Equity simulation, measured.** 01:05:46 → 01:05:49. Script
`mc_bench.py`, 5,000 deals per row, one core, ace-king of one suit:
```
players=2 board=preflop        equity=0.688 runs=5000 wall=0.40s -> 12,493 playouts/s
players=3 board=preflop        equity=0.508 runs=5000 wall=0.49s -> 10,154 playouts/s
players=6 board=preflop        equity=0.332 runs=5000 wall=0.75s ->  6,643 playouts/s
players=3 board=['7H','8H','9C'] equity=0.245 runs=5000 wall=0.44s -> 11,323 playouts/s
players=6 board=['7H','8H','9C'] equity=0.082 runs=5000 wall=0.70s ->  7,142 playouts/s
```

**6. The split-pot check.** 01:06:06 → 01:06:46.
```
$ python mc_bench2.py                         # dickreuter's own simulation
AKs heads-up vs random, 200000 playouts: equity=0.6815 in 16.6s
$ python treys_check.py                       # independent, using treys 0.1.8
treys, 200000 deals: win=0.6625 tie=0.0170 lose=0.3205
                     win+tie=0.6795  win+tie/2=0.6710
```
0.6815 matches "every split counts as a win" (0.6795), not "splits halved"
(0.6710).

**7. The offline check.** A copy of the tree with `db` pointed at a dead port:
```
read_strategy RAISED: ConnectionError HTTPConnectionPool(host='127.0.0.1',
port=9): Max retries exceeded with url: /get_strategy?name=Default&
login=guest&password=guest
```

**8. This repository's own suite, before and after writing this file**
(nothing here changes any code, so nothing should move):
```
$ python.exe -m pytest tests -q
.........................                                                [100%]
25 passed in 0.72s
```
