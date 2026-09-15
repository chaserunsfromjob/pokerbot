# Engine alternatives: what else could we build the bot on?

## What this file is for

We built this project on a borrowed poker engine, `fedden/poker_ai`. Reading it
closely turned up two mismatches with what `CLAUDE.md` says we are building:

- it deals a **20-card deck** (only 10, Jack, Queen, King, Ace), not the normal
  52-card deck; and
- its betting is **fixed-limit** - a raise is always exactly one big blind,
  never an amount the player chooses.

And a third problem, which is the one that actually decides this document:
getting it to 52 cards **the way `poker_ai` itself goes about it** needs about
**18 days of the laptop running flat out**, plus more memory than the laptop
has. There is no budget for that. (That is the measured cost of its own
`clustering/card_combos.py` at 52 cards, not a law about every possible
approach; the distinction is drawn out later.)

This file asks whether some *other* freely available poker engine already does
what we need, inside the time we actually have.

Two words recur and are worth fixing now:

- An **engine** is the code that deals the cards, tracks the chips, decides
  whose turn it is, and pays out the pot. It knows the rules. It does not know
  how to play well.
- A **solver** is the separate piece that learns how to play well, usually by
  playing itself millions of times *in advance*. The best-known family of
  solver methods is called **CFR**, short for **counterfactual regret
  minimisation**. `poker_ai` ships one. Most engines do not.

## The three things every candidate is tested against

1. **Real bet sizing.** A player must be able to bet *any* amount they can
   afford, the way a human does - not pick from a short menu like
   "fold / call / bet the pot". This is what "no-limit" actually means.
2. **A table that changes size.** Anything from 2 players up to 9, chosen when
   the hand starts, without editing the engine's own source.
3. **Fits the compute budget.** A playable bot must be reachable in **hours on
   this one laptop**, not days. This requirement is new, it is firm, and it
   turns out to matter more than the other two.

## How these claims were checked

Everything below was **run**, not read off a website. Each candidate was
downloaded from the Python Package Index (the standard place Python code is
published, "PyPI"), installed into its own clean, separate set of packages, and
driven through real hands. Where a claim could only come from reading the
source, the file and line number is given. Timings are wall-clock on this
machine.

The programs behind every measured number in this file, and the raw output of
the runs quoted, are committed under **`research/engine_alternatives/`**, with
a README saying what each one does and how to re-run it. They are research
artefacts. **They are not the bot**, they are not on the bot's import path, and
whether code of that shape may become the bot at all is the open rule question
set out at the end of this document.

Two conditions decide whether a poker measurement means anything, and both are
stated with every number below. First, the **betting abstraction**: whether the
engine was offering a four-move menu or every whole-chip raise amount. Within
OpenSpiel that alone is about **eleven times** in complete hands per second,
and about **fifty times** in the play-outs the bot gets inside one decision.
Second, for anything measured over hands, **how many hands, and how wide the
uncertainty is**. A poker result without the second is not a weak result; it is
not a result.

Verified on 2026-09-15, macOS 15.2 (24.2.0), Apple M4, 10 cores, 16 GiB,
Python 3.13.15, `open_spiel` 2.0.2, `texasholdem` 0.11.0, PokerKit 0.7.5.
Wall-clock speed on this laptop varies by up to a factor of two between
repeats, so speeds are quoted as the range over six repeats rather than as one
figure, and speed comparisons are taken as ratios within a repeat.

---

# The recommendation, first

**Switch the engine to OpenSpiel's `universal_poker`.** That part is
unconditional: it is the only candidate that gives 52-card no-limit hold'em at
2 to 9 players, with real bet sizing, with no offline training, today.

**Then compute the decision during the hand rather than training a strategy in
advance - subject to two things this document cannot settle by itself:**

1. A **ruling on the forefront rule.** The thing that chooses the action would
   be code we wrote, which is what `CLAUDE.md:13-15` exists to prevent. See
   "Does this contradict the forefront rule?" at the end. Until that is
   recorded, the chooser measured here stays a research artefact.
2. **Comparison against adopting an existing bot** that chooses the action with
   its own code and needs no such ruling - `RESOURCES_BOTS.md` (under review)
   shortlists one that covers 2 to 6 players.

What this document *can* settle, and does: training in advance **without a card
abstraction** does not converge on this laptop, and decision-time computing
needs no abstraction and produces a bot that plays better than random inside
the time budget, measured with an interval. Whether an hours-sized abstraction
exists is untested and is **not** ruled out here.

Keep `fedden/poker_ai` in the repository for reference only. Do not spend
another hour adapting it.

## Why - the measurement that carries the recommendation

A bot was built and run during this survey. Its code is committed, at
`research/engine_alternatives/chooser.py` (about forty lines of decision loop),
so none of what follows has to be taken on trust. It does no training at all.
When it is our turn, it takes a handful of the moves it is allowed to make,
guesses what the opponents are holding, plays the rest of the hand out at
random many times for each, and picks the move with the best average chip
result.

Everything that has to be pinned down for that sentence to mean anything:

| Setting | What it was |
| --- | --- |
| Engine and game | OpenSpiel `universal_poker`, 52 cards, no-limit, 6 seats, 4 betting rounds |
| Stacks and blinds | 20,000 chips a seat (200 big blinds), blinds 50/100 |
| Betting abstraction | measured under **both**: `fcpa` (a four-move menu) and `fullgame` (19,803 legal moves at the first decision) |
| Offline training | **none** |
| Time to first playable decision | immediate |
| Decision budget | **250 ms**, enforced by a wall-clock deadline checked before every play-out, so it stops at the budget rather than after a fixed count |
| Play-outs per decision, `fcpa` | **13,131** (n = 20 decisions; range 12,451-13,279) |
| Play-outs per decision, `fullgame` | **242** (n = 20 decisions; range 205-267) |
| Candidate moves weighed | 4 of 4 legal under `fcpa`; **8 of 19,803** under `fullgame` |
| Play strength, against five opponents moving at random | **+22.80 big blinds a hand**, 95% confidence interval **+15.07 to +30.53**, over **n = 3,412 hands** (menu mode; see below for what this is and is not worth) |

**How the play-outs relate to the 19,803 legal moves: they cannot cover them,
and the chooser does not try.** No play-out count of this order - and not the
16,651 an earlier draft of this document quoted, which is withdrawn as it was
neither reproducible nor stated with its betting abstraction - comes near
19,803 moves. What the chooser actually samples is a **menu of at most eight
candidates built mechanically from the engine's own legal list**: fold, call,
the smallest legal raise, that raise doubled repeatedly, and all-in. The
250 ms is then split round-robin across those candidates.

That has a consequence worth stating in the same breath as the speed. Under
`fullgame`, 242 play-outs across 8 candidates is about **30 play-outs each**,
and one hand of this game swings by a standard deviation of 223 big blinds
(measured below), so each candidate's average carries a standard error of
roughly **±50 big blinds**. At a quarter of a second, in real-sizing mode, the
ranking the bot produces is **mostly noise**. Under `fcpa`, the same budget
gives about 3,280 play-outs per candidate and a standard error near ±5 big
blinds, which is a real comparison. This is the strongest practical argument in
the document for searching the menu game rather than the real-sizing game, and
it was invisible while the betting abstraction went unstated.

Set that against the road we are on: **18 days of computing and more memory
than the machine has, to reach a bot that still cannot choose a bet size.**

## What the play-strength test says, and what it cannot

First, what a single hand of this game is worth: at 200 big blinds deep,
6-handed, one seat's result for one hand has a **standard deviation of 223 big
blinds** (measured over n = 100,000 random hands;
`bench_play.py variance 100000`). That is the number that governs every claim
about how well anything plays. It means a result measured over 300 hands is
uncertain by about **±25 big blinds a hand**, which is many times larger than
any plausible edge. An earlier draft of this document reported **+3.87 big
blinds a hand over 300 hands**. That figure is **withdrawn**: at that sample
size it was indistinguishable from zero, and quoting it without its interval
made noise look like evidence.

Rerun properly, with the interval:

| | |
| --- | --- |
| Set-up | chooser in seat 0, 250 ms a decision, menu mode (`fcpa`); five opponents choosing uniformly at random from the same menu |
| Hands | **n = 3,412** (3,550 chooser decisions, 900 seconds, seed 20260915) |
| Result | **+22.80 big blinds a hand** |
| 95% confidence interval | **+15.07 to +30.53** big blinds a hand |
| Spread | standard deviation 230.4 big blinds a hand |

The interval stays clear of zero, so this **is** a real result: the machinery
works end to end, inside the time budget, and it beats random play.

**What it is not.** Beating opponents who move at random is a very low bar -
random opponents fold good hands, call anything and never punish a mistake. It
says nothing about whether the bot beats a person, and that test has not been
run. It is also a **menu-mode** result: the real-sizing chooser, at 250 ms and
about 30 play-outs a candidate, was not worth measuring against anything,
because its own candidate rankings are inside their own noise.

**What it costs to answer the real question.** At a spread of 223 big blinds a
hand, bounding a result to ±10 big blinds takes about **1,900 hands** and to
±1 big blind about **190,000**. Against a slow opponent the hands come slower
too. Any future strength claim in this project should carry its hand count and
its interval, or it is not a claim.

What this establishes, and only this: **a playable 52-card no-limit bot for 2 to
9 players on one laptop is reachable in hours by computing at decision time,
and it plays better than random.** Whether that is the right road still depends
on the rule question at the end of this document.

## What the training measurements show, and what they do not

This is the claim to be most careful about, because an earlier draft of this
document over-claimed it. What was run, exactly:

    cd research/engine_alternatives
    ../../.venv-engines/bin/python bench_cfr.py 45     # numpy seed 20260915

OpenSpiel's own external-sampling Monte Carlo CFR, **with no card abstraction
at all**, betting abstraction `fcpa`, 45 seconds per configuration, one core.
Raw output in `research/engine_alternatives/raw/cfr.txt`. "Still-new per round"
is counted over the last quarter of each run, so it is the rate *after* the
easy situations have been seen.

| Game (all `fcpa`, no card abstraction) | Rounds in 45 s | Situations stored | Still-new per round |
| --- | --- | --- | --- |
| 6 players, 52 cards, 200bb | 7,950 | 778,582 | 84.8 |
| 6 players, 52 cards, 20bb | 5,401 | 445,154 | 69.2 |
| 6 players, 52 cards, 10bb | 7,870 | 490,456 | 49.2 |
| 6 players, 24 cards, 10bb | 17,160 | 493,221 | 19.4 |
| 6 players, **20 cards** (`poker_ai`'s deck), 10bb | 16,913 | 418,540 | 16.5 |
| 3 players, 52 cards, 10bb | 37,478 | 606,670 | 14.2 |
| 6 players, 52 cards, 10bb, **pre-flop only** | 31,936 | 911,510 | 17.4 |

Read the last column, not the middle one: a configuration that runs faster gets
more rounds in its 45 seconds and therefore piles up more situations, which is
why pre-flop-only shows the largest total. What matters is whether the flow of
*new* situations is drying up, and in none of these is it.

Shrinking the deck does not rescue it: `poker_ai`'s own 20-card deck is still
turning up 16.5 new situations per round after 16,913 rounds. Cutting the hand
back to pre-flop only gives the lowest rate of any 6-player row here (17.4,
against 84.8 for the full 200bb game), but it has not converged either - it is
the most promising of these, not a finished one. Only the 3-player row is
lower, and a 3-player strategy is not what this project is aiming at.

**What that establishes:** *unabstracted* CFR does not converge on this machine
inside this budget, on any of these games. That is a real result and it is why
the train-in-advance road cannot simply be started.

**What it does not establish, and the earlier draft wrongly claimed:**

- It does not show that *no* abstraction fits in hours. A **card abstraction** -
  the compression step `REFERENCE_NOTES.md` calls clustering, which groups
  similar situations so the solver has a finite job - is exactly the step that
  makes training tractable, and **no abstraction sized to a few hours was
  attempted here**. This survey did not try one.
- The **18-day, 147-gibibyte** figure is a measurement of `poker_ai`'s own
  `clustering/card_combos.py` at 52 cards - that one implementation, which
  builds every hole-cards-plus-board combination in memory at once. It is the
  cost of *that* approach, **not a lower bound on every possible abstraction**.
- `RESOURCES_BOTS.md` (under review, not accepted) reports that **NoRegrets**'
  README claims a blueprint for 2 to 6 players from 200 million iterations in
  about an hour on 16 cores (400 million in 1 h 56 m). That is an **unverified claim under
  review** - not built, not run, not timed on this machine, and its macOS build
  is unverified too. But it is a live claim that training in advance can fit in
  hours, and it is enough to rule out saying that road is closed for every
  engine.

So the honest scope: decision-time computing **needs no abstraction**, because
it never needs a strategy for a situation it is not currently in, and that is
its genuine advantage. Whether an hours-sized abstraction or an existing
blueprint trainer also fits is **open**, and the NoRegrets verification is what
would settle it.

## Why OpenSpiel specifically, and not the other working engines

Once the architecture is "think during the hand", the engine's job changes: it
has to play out hands *fast*, because speed is directly how good the decision
is. But a hands-per-second figure means nothing without saying **what the
engine was allowed to bet**, and an earlier draft of this document left that
out. Offering a four-move menu and offering every whole-chip raise amount are
different jobs, and within OpenSpiel alone they differ by about **eleven
times**. Every row below therefore states its betting mode, and engines are
compared only against engines doing the same job:

- **menu** - fold, call, a pot-sized bet, all-in. Four moves. OpenSpiel's
  `bettingAbstraction=fcpa`; for the Python engines, the same four moves picked
  out of what they offer.
- **real sizing** - any legal whole-chip raise-to amount, drawn uniformly.
  OpenSpiel's `bettingAbstraction=fullgame` (19,803 legal moves at the first
  decision of this game); for the Python engines, a uniform draw across their
  legal raise range.

Same 6-player 52-card game throughout, 200 big blinds deep, blinds 50/100, one
core, every move drawn at random from what the engine itself says is legal, one
Python call per node. Six repeats of ten seconds per row, `bench_speed.py`,
raw output in `research/engine_alternatives/raw/speed.txt`:

| Engine and betting mode | Complete hands per second (min - median - max over 6 repeats) | Play-outs in a 250 ms decision, at the median |
| --- | --- | --- |
| **OpenSpiel `universal_poker`, menu (`fcpa`)** | **9,273 - 12,824 - 21,274** | **~3,200** |
| `texasholdem` 0.11.0, menu | 1,633 - 2,062 - 3,485 | ~520 |
| PokerKit 0.7.5, menu | 110 - 208 - 356 | ~50 |
| OpenSpiel `universal_poker`, real sizing (`fullgame`) | 972 - 1,218 - 2,159 | ~300 |
| `texasholdem` 0.11.0, real sizing | 1,153 - 2,324 - 3,515 | ~580 |
| PokerKit 0.7.5, real sizing | 67 - 177 - 273 | ~44 |

The last column is a *complete* hand dealt from scratch, which is why it is
lower than the 13,131 play-outs the chooser managed in the same quarter-second
on the menu: a play-out starts from the middle of a hand already dealt, so it
is cheaper than a whole one. The two numbers measure different things and both
are stated rather than blended.

Those ranges are wide because wall-clock throughput on this laptop moves by a
factor of two between repeats. Ratios taken **within** each repeat are far
steadier, and they are what the comparison should rest on:

| Like-for-like comparison | Ratio per repeat (min - median - max) |
| --- | --- |
| OpenSpiel vs `texasholdem`, both on the menu | 4.9 - **5.7** - 6.7 times faster |
| OpenSpiel vs PokerKit, both on the menu | 37.7 - **69.6** - 117.1 times faster |
| OpenSpiel vs `texasholdem`, both real sizing | 0.37 - **0.66** - 0.84, i.e. OpenSpiel is **1.5 times slower** |
| OpenSpiel vs PokerKit, both real sizing | 4.5 - **7.5** - 15.2 times faster |
| OpenSpiel menu vs OpenSpiel real sizing | 6.7 - **11.0** - 13.3 times faster |

Read carefully, that says something the earlier "**9 times** faster" claim hid.
**OpenSpiel's advantage is in menu mode, and in real-sizing mode it is actually
slower than `texasholdem`** - because asking it for the legal moves at that
setting means building a list of 19,803 of them at every decision. So the case
for OpenSpiel is not raw speed at any setting; it is that the architecture we
want **searches the menu**, and on the menu OpenSpiel is about six times faster
than the next working candidate and seventy times faster than PokerKit. Under
this architecture that gap is the difference between a considered decision and
a guess. What it does not do is remove the unsolved problem of translating a
position between the two settings.

It is also the only candidate that still has a CFR solver we could use later
(and one that works with more than two players), so choosing it does not close
the door on training something in advance if the schedule ever allows.

## What to do with PokerKit

Adopt it too, but for a different job: **checking our work, not playing.**

PokerKit is the most rules-correct engine in this survey and the only one still
actively released. It is too slow to think with, but it is ideal for replaying a
hand we captured off a screen and confirming the rules were applied exactly
right. That is the same role `treys` already plays for hand ranking under
`CLAUDE.md` - a reference, kept out of the decision path.

---

# The candidates

### 1. OpenSpiel `universal_poker` - **passes all three**

Google DeepMind's game-research library. 5,486 stars, last push 2026-08-31, not
archived, Apache-2.0 licence. `universal_poker` wraps the engine used by the
Annual Computer Poker Competition, so the rules code is what academic poker
research has run against for over a decade.

**The name was tested, not trusted.** One trap: the library's build script turns
`universal_poker` **off** by default (`open_spiel/scripts/global_variables.sh:40`
reads the global default, and line 27 sets that default to `"OFF"`), so anyone
building from source gets a library with no poker in it. **The pre-built package
on PyPI is built with it ON** - verified by installing `open_spiel` 2.0.2 and
loading the game. So `pip install open_spiel` is enough.

**Requirement 1, real bet sizing: yes, genuinely.** A setting called
`bettingAbstraction`, set to `fullgame`, makes every whole-chip amount a
separate legal move. Measured at a 6-player table with 20,000 chips behind and a
100-chip big blind, the first player to act had **19,803 legal moves** - fold,
call, and every raise-to amount from 200 through 20,000.

**Requirement 2, 2 to 9 players: yes.** `universal_poker.cc:114-115` declares a
maximum of 10 and a minimum of 2. Tested by building full 52-card no-limit
hold'em at every seat count from 2 to 9 and playing **200 complete hands at
each** of 2, 3, 6 and 9 players in both betting modes, every move chosen at
random from the engine's own legal list. **1,600 hands, zero chip-conservation
failures** - side pots, all-ins and showdowns all paid out correctly.

**Requirement 3, compute budget: yes - the only unqualified yes here.** Zero
offline training needed; see the measured bot above. Fastest engine in the
survey **on the four-move menu**, by 5.7 times over `texasholdem` and 70 times
over PokerKit (medians over 6 repeats); with real sizing it is about 1.5 times
*slower* than `texasholdem`, for the reason given in the speed section.

**Solver capability: substantial, and it works multiway.** Ships CFR, CFR+,
discounted CFR, two sampled-CFR variants, Deep CFR, plus best-response and
exploitability measurement. Checked these are not secretly heads-up only:
tabular CFR ran 50 rounds on a **3-player** game, and sampled CFR ran 3,000
rounds on a **3-player no-limit** game and returned usable recommendations.

**One real defect found.** The standard look-ahead search method bundled with
OpenSpiel (ISMCTS) **crashes the whole program** - a hard segmentation fault,
exit code 139, not a catchable error - the moment there are more than two
players. Isolated to one line:

```
open_spiel/games/universal_poker/universal_poker.cc:1111
  if (acpc_game_->GetNbPlayers() != 2) return {};
```

That returns nothing at all, and the caller six lines earlier at 1105 reads from
that nothing. Confirmed at 3 players; 2 players is fine.

**This does not block us, and that was verified rather than assumed.** The job
that line fails to do - inventing a plausible set of opponent hole cards - was
rewritten in about fifteen lines of our own Python, committed at
`research/engine_alternatives/resample_opponents.py`. It replays the hand's own
history into a fresh state and redraws the cards dealt to seats we cannot see,
uniformly from the cards still unaccounted for. Measured at a 6-player 52-card
table, `fcpa`, with the bookkeeping done once per decision rather than once per
draw: **71,344 redraws per second at the first decision after the deal**
(n = 713,438 draws in 10 s) and **91,078 per second at a later decision in the
same hand** (n = 910,784 in 10 s). Wall-clock on this laptop moves by tens of
percent between runs, which is the size of the difference between those two, so
read it as "of the order of 70,000 to 90,000 a second" rather than as a
difference between the two positions. The measured bot uses this workaround and
never touches the broken code.

### 2. PokerKit - **passes 1 and 2**, fails 3 for playing, excellent for checking

From the University of Toronto Computer Poker Research Group. 497 stars, last
release 2026-08-22 (the most recently maintained thing here), MIT licence, 2
open issues.

**Requirement 1: yes.** At a 6-player 20,000-chip table it reports a minimum
raise-to of 200 and a maximum of 20,000 - **19,801 distinct legal amounts** -
and accepted an arbitrary non-round raise to 377.

**Requirement 2: yes.** 50 complete hands at every seat count from 2 to 9 -
**400 hands, zero chip-conservation failures**. Also accepts different starting
stacks per seat (tested 100 / 500 / 20,000), which is what forces side pots and
where weaker engines get payouts wrong.

**Requirement 3: no, as the thinking engine.** On the four-move menu, **110 to
356 complete hands a second** (median 208 over 6 repeats of 10 seconds), which
is **37 to 117 times slower than OpenSpiel on the same menu**; with real
sizing, 67 to 273 a second (median 177), 4.5 to 15 times slower than OpenSpiel
there. A 250 ms decision buys of the order of 50 play-outs, which cannot choose
between four actions: at a per-hand spread of 223 big blinds, 50 play-outs
leave each candidate's average uncertain by about ±60 big blinds. It ships no
pre-trained strategy, so it offers no other route to a playable bot.

**Solver capability: none.** Verified by listing everything the package exposes:
no CFR, no search, no agents.

It is the most *correct* engine here - mucking, hand-killing, bring-ins,
straddles, real hand-history formats. Recommended above as our reference
checker.

### 3. `texasholdem` - **passes 1 and 2**, marginal on 3

108 stars, last push 2025-01-08, MIT licence.

**Requirement 1: yes** - **19,801 legal raise-to values** at a 20,000-chip 6-max
table. **Requirement 2: yes** - `max_players` defaults to 9 and is a constructor
argument (`texasholdem/game/game.py:256`); 50 hands at each of 2 through 9, **400
hands, zero chip-conservation failures**.

**Requirement 3: marginal, and better than the earlier draft said.** On the
four-move menu, **1,633 to 3,485 complete hands a second** (median 2,062 over 6
repeats of 10 seconds), **4.9 to 6.7 times slower than OpenSpiel on the same
menu** - about 520 play-outs in a 250 ms decision, against OpenSpiel's ~3,200.
Meaningfully worse decisions for the same wait, but workable.

**With real sizing it is the faster of the two**: 1,153 to 3,515 hands a second
(median 2,324) against OpenSpiel's 972 to 1,218 to 2,159, a per-repeat ratio of
0.37 to 0.84 - OpenSpiel is about **1.5 times slower** there, because listing
19,803 legal raise amounts at every decision costs more than this library's
whole hand. If the architecture ever searches with real sizing rather than a
menu, this is the faster engine, and that is a genuine mark in its favour that
the earlier draft's single "9 times slower" figure concealed.

No pre-trained strategy, no solver; its only bundled agents are call-only and
random. The easiest code here to read and modify, and the natural fallback if
OpenSpiel's C++ ever becomes a problem to install.

### 4. RLCard - **fails requirement 1**

3,546 stars, last push 2024-06-26, MIT licence. Genuinely real and widely used.

**Requirement 1: no, and this is decisive.** Its "no-limit hold'em" has a
hard-coded five-item action list (`rlcard/games/nolimitholdem/round.py:8-18`):

```python
class Action(Enum):
    FOLD = 0
    CHECK_CALL = 1
    RAISE_HALF_POT = 2
    RAISE_POT = 3
    ALL_IN = 4
```

Confirmed by running it: at 2, 3, 6 and 9 players the environment reports
`num_actions = 5` every time. Half-pot, pot, or shove - a **menu**, which is
exactly what requirement 1 excludes. Changing it means replacing the betting
round, the observation format and every bundled agent.

**Requirement 2: yes**, `game_num_players` is configurable; 2/3/6/9 all started
cleanly. **Requirement 3: no.** Its one pre-trained poker model is
`leduc-holdem-cfr` (`rlcard/models/__init__.py:6`) - **Leduc is a 6-card toy
game**, not hold'em. Nothing here shortens the road.

**Solver capability:** a CFR agent exists (`rlcard/agents/cfr_agent.py`), written
generically over player count, but it walks the entire game tree and needs the
engine's rewind feature, so it is usable only on toy games - which is what
RLCard's own documentation demonstrates it on.

### 5. PyPokerEngine - **passes 1 and 2**, wrong shape, fails 3

723 stars, last push 2024-04-10, MIT licence; last actual release 2017.

**Requirement 1: yes** - raises are offered as a minimum/maximum range and any
amount between is accepted (`pypokerengine/engine/action_checker.py:37-44`).
**Requirement 2: yes**, and then some - 3-round games at 2, 3, 6, 9 and 12
players, chips conserved every time. Side pots implemented
(`pypokerengine/engine/game_evaluator.py:69`).

**Requirement 3: no.** No pre-trained strategy, no solver, and - fatally for a
thinking bot - **it cannot be used for decision-time search at all.** It is a
**tournament runner**: you register player objects, call `start_poker`, and it
calls *you* back on your turn. There is no way to hand it a position and ask
"what now?", no way to clone a position and play it out, and no way to set
different starting stacks per seat. Our architecture needs exactly the opposite.

### 6. PokerRL - **fails requirement 2, and will not install**

541 stars, last push 2023-03-31, MIT licence. By Eric Steinberger, who also wrote
a well-known Deep CFR paper, so the CFR code is real research code.

**It does not install on this machine.** `pip install PokerRL` fails outright: a
dependency, `pycrayon`, cannot be built under Python 3.13.

**Requirement 2: no.** Its CFR is hard-wired to two players -
`PokerRL/cfr/_CFRBase.py:40` is literally `self._n_seats = 2`. The same
assumption is asserted in seven more places, including every evaluation tool
(`PokerRL/eval/rl_br/LocalRLBRMaster.py:22` says so in its own message: *"only
works for 2 players at the moment"*). The game tree its CFR walks refuses
anything else (`PokerRL/game/_/tree/_/ValueFiller.py:27`).

It does have a genuine continuous-sizing `NoLimitHoldem` environment
(`PokerRL/game/games.py:170-178`). That does not save it: a heads-up-only solver
is useless for a project whose goal is a table of three or more.
**Requirement 3: no** - it ships no trained weights, and training it was the
expensive road anyway.

### 7. `clubs` - passes on paper, broken in practice

21 stars, last push 2024-02-06, GPL-3.0. Its preset list literally contains
`NO_LIMIT_HOLDEM_SIX_PLAYER` and `NO_LIMIT_HOLDEM_NINE_PLAYER` with 52 cards and
unlimited raise sizes - our requirements, pre-packaged.

**It does not import on Python 3.12 or later.** `clubs/render/graphic.py:3` does
`import imp`, and the `imp` module was deleted from Python in 3.12. It is not
optional code - the package's main file pulls it in on every import, so nothing
in the library is reachable.

Patched around it (by faking the missing module) purely to check the engine
underneath, which is fine: 19,801 distinct raise-to values at 6 and 9 players,
custom counts of 3, 4, 5, 7 and 8 all start. **Requirement 3: no** - no solver,
no trained strategy. With 21 stars, no maintenance and a library that will not
import, there is no reason to pick it over PokerKit.

---

## Side by side

Speeds are median complete hands per second over 6 repeats of 10 seconds,
6-player 52-card game, 200bb, one core; the two betting modes are listed
separately because they are not comparable to each other.

| Engine | 1. Real sizing | 2. 2-9 players | 3. Playable in hours | Hands/sec, menu mode | Hands/sec, real sizing | Solver | Installs on 3.13 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **OpenSpiel `universal_poker`** | **yes** (19,803) | **yes** (2-10) | **yes** - no training at all | **12,824** | 1,218 | yes, multiway | yes |
| **PokerKit** | yes (19,801) | yes (2-9) | no - 70x slower on the menu | 208 | 177 | no | yes |
| `texasholdem` | yes (19,801) | yes (2-9) | marginal - 5.7x slower on the menu, **faster with real sizing** | 2,062 | 2,324 | no | yes |
| PyPokerEngine | yes | yes (to 12) | **no** - cannot search | n/a | n/a | no | yes |
| RLCard | **no** - 5 fixed actions | yes | no - only a toy model | n/a | n/a | toy games only | yes |
| PokerRL | yes | **no** - heads-up CFR | no | n/a | n/a | heads-up only | **no** |
| `clubs` | yes | yes | no | n/a | n/a | no | **no** |
| `fedden/poker_ai` (current) | **no** - fixed-limit | 2-6 at 20 cards | **no - ~18 days + 147 GiB** | n/a | n/a | yes, but limit only | yes |

`fedden/poker_ai` is **archived** on GitHub as of 2023-04-03. Archived means
frozen read-only - upstream cannot accept a fix even in principle.
`REFERENCE_NOTES.md` records only that it has had no recent commits, which
understates this. Filed as a finding.

---

## What it costs to reach a playable bot, per road

The target: a real 52-card no-limit hand, a table size we choose, and the
ability to ask for a recommended action.

### Staying with `fedden/poker_ai` - **does not fit the budget**

1. Thread the deck size through the game state - about thirty mechanical lines.
2. Rewrite the pre-flop abstraction from 25 hand classes to 169.
3. **Rewrite `clustering/card_combos.py` completely.** It builds every
   hole-cards-plus-board combination in memory at once. At 52 cards that is
   2,809,475,760 rows on the river and **147 gibibytes just for the list of
   pointers**, before a single card object exists. Re-measured clustering cost:
   **about 18 days of continuous computing** - and only if the memory existed,
   which it does not.
4. **Then, still ahead and not yet costed: add bet sizing.** The engine has no
   concept of choosing an amount. Adding one means rebuilding the betting round
   and enlarging the tree the solver searches.

Step 3 alone exceeds the budget by two orders of magnitude. Step 4 is a second
research-grade rewrite after it. **Recommend stopping here.**

### Switching to OpenSpiel with decision-time computing - **fits, with room**

1. `pip install open_spiel`. **Steps 1, 2 and 4 above do not exist** - 52-card
   no-limit hold'em at 2 to 9 players already runs, verified with 1,600 hands.
2. The decision-time chooser measured above: **about forty lines, written and
   run during this survey and committed at
   `research/engine_alternatives/chooser.py`.** No training. It is a research
   artefact, deliberately not on the bot's import path - see the point below
   about what it would take to make it the bot.
3. The fifteen-line Python workaround for the multiway crash, committed at
   `research/engine_alternatives/resample_opponents.py`: **written and measured
   at of the order of 70,000 to 90,000 redraws per second** (conditions in the
   OpenSpiel entry above).
4. A translation layer between our table-state capture and OpenSpiel's game
   parameters - a day or two of plumbing with no poker judgment in it, which
   `CLAUDE.md`'s forefront rule permits us to write.
5. **A ruling on the forefront rule.** Items 2 and 3 are the parts that choose
   the action and guess the cards, and `CLAUDE.md:13-15` is what says whether
   we may write them at all. This is not costed in days because it is not
   coding work; it is a decision, and the section "Does this contradict the
   forefront rule?" below sets out what has to be decided and where. **Until
   it is made, items 2 and 3 stay research artefacts.**

**Total offline computing: zero.** The remaining coding work is integration,
which is exactly the category `CLAUDE.md` says is ours; the chooser is not.

### Is there a pre-trained strategy we could just download?

Checked, because it would be the cheapest road of all. **No.**

- OpenSpiel ships no trained poker strategies. The four files under
  `universal_poker/endgames/` are heads-up test fixtures, not a strategy.
- RLCard's only pre-trained poker model is for **Leduc**, a 6-card toy game.
- PokerRL, PokerKit, `texasholdem`, PyPokerEngine and `clubs` ship none.

No downloadable 52-card multiway no-limit strategy exists in any of these
projects. This is a firm negative, not an unchecked assumption.

### Is there a smaller offline solve that fits in hours?

Unabstracted, no: the single run recorded above
(`research/engine_alternatives/raw/cfr.txt`, 45 s per configuration, seed
20260915) is the whole evidence, and every configuration in it is still finding
brand-new situations when the time runs out. The **pre-flop-only** game grows
most slowly of the 6-player rows - 17.4 new situations per round after 31,936
rounds, against 84.8 for the full 200bb game - so **a pre-flop-only strategy for a
fixed table size is the largest thing here that looks like it might finish in
hours.** That is a possible future improvement, not a bot on its own, and not
where to start. It has not been run to convergence, so "might" is as strong as
this evidence gets.

With an abstraction the question is open and untested; see the scoping above.

There is one cheap lever worth recording, and this survey's own chooser
measurements are what show it. Searching the four-move `fcpa` menu bought
**13,131 play-outs per 250 ms decision** (n = 20 decisions, range
12,451-13,279); searching the real-sizing `fullgame` bought **242** (n = 20,
range 205-267) for the same quarter-second, a factor of 54. So the practical
shape is **think against a small menu, act with real sizing** - two loadings of
the same game with different settings, which OpenSpiel supports directly. The
catch, unsolved here: OpenSpiel's action numbering differs between the two
loadings, so translating a position from one to the other is real work that
nobody has costed.

---

## What this means for the plan in `CLAUDE.md`

The plan's stage 1 is "find out what it takes to move `poker_ai` off the 20-card
deck". This survey answers that question from the other direction: **it takes
more than adopting an engine where the problem does not exist, and more time
than we have.**

Stage 2 - opponent modelling - is where `CLAUDE.md` says the real win is, and
this recommendation helps it rather than delaying it. A bot that decides during
the hand has two distinct places to put what we learn about an opponent, and
they are not the same hook. Naming them apart matters, because they need
different things from `OPPONENT_MODEL_DESIGN.md` (under review, not accepted)
and only one of them is supported by what was built here.

**Hook A - the rollout policy, per seat.** Inside a play-out, each opponent's
sampled actions are drawn from *that opponent's* modelled tendencies instead of
uniformly: a seat measured as folding to most bets folds more often in the
play-out. What it needs from `OPPONENT_MODEL_DESIGN.md`: a per-seat mapping
from the current decision point to probabilities over the moves on the menu.
Its Tier A and Tier B action-frequency stats (`vpip`, `pfr`,
`fold_to_cbet_flop`, `afq_flop`/`afq_turn`/`afq_river`) are the right raw
material, but that
document reports several of them as diagnostics explicitly *not* fed into a
decision, so it would have to say which become policy inputs. **Supported
today**: the rollout policy in `research/engine_alternatives/chooser.py` is one
function that already receives the acting seat; replacing uniform choice with
per-seat weights changes nothing else. Cost: one weighted draw per node, paid
directly out of the rollout count.

**Hook B - hole-card resampling, per seat.** Each opponent's *cards* are drawn
from the range their model says they would still hold, given how they have
acted this hand: a seat that three-bet and kept betting is dealt strong
holdings more often. What it needs from `OPPONENT_MODEL_DESIGN.md` is something
it does not currently contain - a per-seat starting-hand range and a rule for
narrowing it by observed actions. Its stat list is frequencies, not ranges, and
`showdown_holdings` (real cards, seen at about a 4.5% rate) is explicitly
corroboration only. **Supported today only in its uniform form**:
`resample_opponents` draws every hidden hole card uniformly from the unseen
cards. Weighting that draw is where a model would enter, and the weighting is
itself poker judgment, so it meets the same rule question as the chooser below.

Hook A is the cheaper and the better specified, and is the one to build first
if this architecture is adopted. A trained-in-advance blueprint has no
comparable hook: it is a fixed table, and adapting it means re-solving.

## Does this contradict the forefront rule? It needs a ruling, not an assertion

An earlier draft of this document said "nothing here contradicts the forefront
rule". That settled by assertion the one thing that most needs deciding.
`CLAUDE.md:13-15` says never to let an AI model decide a poker action, and to
reject a change that adds hand-rolled decision logic in place of the vendored
engine. **A rollout loop we wrote, taking the highest average chip result, is
logic that chooses the action.** That it was typed by hand rather than produced
by a model does not exempt it: line 15 is about hand-rolled decision logic in
its own right.

Split precisely, for the bot measured here:

| Supplied by the engine (borrowed, tested) | Written by us (the chooser) |
| --- | --- |
| Dealing, and tracking which cards remain | Which candidate moves are considered at all - 8 out of 19,803, by a rule we wrote |
| Which moves are legal, and the legal raise range | The rollout policy: what every seat does inside a play-out |
| Ranking the hands at showdown | How many play-outs to spend, and on which candidates |
| Paying the pot, including side pots and all-ins | **The comparison that picks the move** - highest mean chips |
| Sampling chance events during a play-out | Redrawing the opponents' hole cards, which `universal_poker.cc:1111` refuses to do |

The right-hand column is where the action comes from. The engine never picks.

**So adopting this recommendation requires a recorded carve-out to the
forefront rule.** One possible shape of such a carve-out, given as an
illustration and not as a proposal: *permit a general, published game-search
algorithm that carries no poker-specific heuristics, implemented from its own
paper and validated against a reference implementation.* Worth noting that the
chooser measured here would **not** qualify under that wording: its candidate
menu and its rollout policy were written here from scratch, not taken from a
published algorithm.

**This document does not grant that carve-out and must not be read as granting
one.** Changing a rule in `CLAUDE.md` is the operator's call, recorded with its
reason. The place for it is the reconciliation of `ENGINE_ALTERNATIVES.md`,
`RESOURCES_BOTS.md` and `RESOURCES_SOLVERS.md`, not here.

**There is an alternative that needs no carve-out at all, and it has to be
weighed against this one:** adopt an existing bot whose *own* code chooses the
action. Then poker judgment stays inside borrowed, tested code and what we
write is plumbing and opponent modelling - exactly the split `CLAUDE.md`
describes. `RESOURCES_BOTS.md` (under review, not accepted) shortlists
**NoRegrets** (`conorarmstrong/noregrets`), an open-source Pluribus-style bot
covering 2 to 6 players at no-limit hold'em that plays a hand today; that
document records its training-time claim and its macOS build as unverified.
Which road to take is not decided here either.

---

## Ruled out on contact

Checked and discarded as not-real-code before reaching the table above:

- GitHub results for "poker bot" that are link collections ("awesome-poker"
  style lists) with no engine in them.
- Repositories whose only poker content is a hand evaluator - `treys` and
  `deuces` among them. We already use `treys` for exactly that, as `CLAUDE.md`
  requires. An evaluator is not an engine: it ranks five cards and knows nothing
  about chips, turns or pots.

## Things this survey could not settle

- **Whether the recommended bot beats anything that defends itself.** It has
  only ever been played against opponents moving at random, which is a very low
  bar, and even that result is reported with its interval above. The next test
  should be against a simple rule-following opponent, then a human. Budget it
  from the spread: one hand of this game has a standard deviation of 223 big
  blinds, so pinning a result down to ±1 big blind per hand takes about
  **190,000 hands**, and to ±10 big blinds about **1,900 hands**. Any strength
  claim that does not say how many hands it rests on is not a claim.
- **Whether searching the four-move menu and acting with real sizing can
  actually be joined up.** The two loadings of the game number their moves
  differently and this survey did not build the translation between them.
- Whether the OpenSpiel multiway crash has been reported or fixed upstream. It
  was reproduced here against released version 2.0.2; the issue tracker was not
  searched. We do not need it fixed, having worked around it.
- How much decision time is available in real play. Every timing here assumes a
  250 millisecond budget. If the real table allows two seconds, the bot gets
  eight times the thinking; if it allows fifty milliseconds, it gets a fifth.
  That number comes from the table-capture work, not from here.
