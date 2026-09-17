# Engine alternatives: what else could we build the bot on?

## What this file is for

We built this project on a borrowed poker engine, `fedden/poker_ai`. Reading it
closely turned up two mismatches with what `CLAUDE.md` says we are building:

- it deals a **20-card deck** (only 10, Jack, Queen, King, Ace), not the normal
  52-card deck; and
- its betting is **fixed-limit** - a raise is always exactly one big blind,
  never an amount the player chooses.

And a third problem, which is the one that actually decides this document:
getting it to 52 cards **the way `poker_ai` itself goes about it** needs at
least **18 days of the laptop running flat out**, plus more memory than the
laptop has. There is no budget for that.

That 18 days is **not a stopwatch reading and nobody has sat through it**. It is
a **floor worked out by scaling up** a 20-card clustering run that did finish:
the arithmetic, and the reasons it is a floor rather than an estimate, are at
`REFERENCE_NOTES.md:399-430`, which also records that the job dies at its memory
allocation before any of those days could begin. It is the cost of that one
implementation's own `clustering/card_combos.py` at 52 cards, not a law about
every possible approach; the distinction is drawn out later.

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

Everything below was **run**, not read off a website. Every candidate was
downloaded from the Python Package Index (the standard place Python code is
published, "PyPI") into one throwaway set of packages kept well away from the
project's own - `.venv-engines/`, which git ignores - and driven through real
hands there. Where a claim could only come from reading the source, the file and
line number is given. Timings are wall-clock on this machine.

Every **measured** number in this file comes from a program committed under
**`research/engine_alternatives/`**, and the raw output of the run quoted is
committed beside it under `raw/`, with a README saying what each program does
and how to re-run it. That includes the pass/fail checks in the candidate
sections below - how many bet sizes an engine really offers, how many seats it
really takes, whether chips are conserved over a pile of random hands - which
`bench_requirements.py` re-runs in one go.

Three kinds of statement here are **not** measurements and have no program
behind them, and they are marked as such wherever they appear:

- a line quoted from an engine's own source code, given with its file and line
  number so that it can be read rather than believed;
- the star counts and last-push dates taken off each project's GitHub page, read
  by eye (the release dates, which carry more weight, were asked of the Python
  Package Index and the answer is in `raw/release_dates.txt`);
- the claim that PokerRL will not install at all, which is by nature not a
  measurement - the raw output of the attempt is in `raw/pokerrl_install.txt`.

These programs are research artefacts. **They are not the bot**, they are not on
the bot's import path, and whether code of that shape may become the bot at all
is the open rule question set out at the end of this document.

Three conditions decide whether a poker measurement here means anything, and all
three are stated with every number below.

First, the **betting abstraction**: whether the engine was offering a four-move
menu or every whole-chip raise amount. Within OpenSpiel that alone is about
**eleven times** in complete hands per second, and about **fifty times** in the
play-outs the bot gets inside one decision.

Second, for anything measured over hands, **how many hands, and how wide the
uncertainty is**. A poker result without the second is not a weak result; it is
not a result.

Third, and this is new in this draft, **how busy the machine was**. This laptop
is shared with other work. A count of how many programs were queued waiting for
a processor core, averaged over the last minute, is called the **load average**;
this machine has ten cores, and above a load of about 4 its timings stop meaning
anything. Every timing below was taken only once the load was under 4, with the
load written down beside it, and with all the timings that get compared against
each other taken in rotation in a single sitting. There is one more trap, found
the hard way while re-timing: a laptop that goes to sleep part way through a
run - lid closed, idle timer - wrecks the timing without the measuring program
noticing, because the clock the program times itself with stops with the
machine. So every long run was held awake with `caffeinate`, macOS's own tool
for exactly that, and the machine's power log was checked afterwards for any
sleep inside the run's wall-clock window; two head-to-head runs and one whole
paired session that a sleep had split were thrown away and taken again. An
earlier draft of this document did none of this and its speeds were three to
four times too low as a result.

Verified on 2026-09-15 and re-timed on 2026-09-16, macOS 15.2 (24.2.0),
Apple M4, 10 cores, 16 GiB, Python 3.13.15, `open_spiel` 2.0.2, `texasholdem`
0.11.0, PokerKit 0.7.5, PyPokerEngine 1.0.1, RLCard 1.2.0, `clubs` 0.1.4.
Speeds are quoted as the range over six repeats rather than as one figure, and
speed comparisons are taken as ratios within a repeat.

---

# The recommendation, first

**Switch the engine to OpenSpiel's `universal_poker`.** That part is
unconditional. Four of the seven candidates give 52-card no-limit hold'em at 2
to 9 players, with real bet sizing, with no offline training, today - OpenSpiel,
PokerKit, `texasholdem` and PyPokerEngine. Of those four, OpenSpiel is **five
and a half times faster than the next one** at the job this architecture
actually does, and the only one that also ships a solver that works with more
than two players, so it keeps a door open that the others close.

**Then compute the decision during the hand rather than training a strategy in
advance - subject to two things this document cannot settle by itself:**

1. A **ruling on the forefront rule.** The thing that chooses the action would
   be code we wrote, which is what `CLAUDE.md`'s "The forefront rule" section
   exists to prevent. See "Does this contradict the forefront rule?" at the
   end. Until that is recorded, the chooser measured here stays a research
   artefact.
2. **Comparison against adopting an existing bot** that chooses the action with
   its own code and needs no such ruling - `RESOURCES_BOTS.md` (under review)
   shortlists one that covers 2 to 6 players.

What this document *can* settle, and does: training in advance **without a card
abstraction** does not converge on this laptop, and decision-time computing
needs no abstraction and produces a bot that plays better than random inside
the time budget, measured with an interval - **on a four-move menu. Acting with
real bet sizing needs a translation between the two ways of loading the game,
and nobody has built it.** Whether an hours-sized abstraction exists is untested
and is **not** ruled out here.

Keep `fedden/poker_ai` in the repository for reference only, and spend no more
time adapting it. When an earlier draft of this document said that, it was an
edit to `CLAUDE.md` that this document had no authority to make: that file's
opening paragraph then made `fedden/poker_ai` "this project's basis", and its
"## Plan" stage 1 was "find out what it takes to move it off the default
20-card short deck". **The operator has since made the edit.** `CLAUDE.md`'s
opening paragraph now reads "The engine road is OpenSpiel's `universal_poker`"
with `fedden/poker_ai` "a reference only, not as this project's basis", and
"## Plan" stage 1 now reads "Superseded; the engine road is OpenSpiel
`universal_poker`", with what replaces it left to the reconciliation of
`ENGINE_ALTERNATIVES.md`, `RESOURCES_BOTS.md` and `RESOURCES_SOLVERS.md`.
So this recommendation no longer contradicts `CLAUDE.md`; what that
reconciliation still owes is the replacement stage 1, and the rule question
above.

## Why - the measurement that carries the recommendation

A bot was built and run during this survey. Its code is committed, at
`research/engine_alternatives/chooser.py` (about forty lines of decision loop),
so none of what follows has to be taken on trust. It does no training at all.
When it is our turn, it takes a handful of the moves it is allowed to make,
guesses what the opponents are holding, plays the rest of the hand out at
random many times for each, and picks the move with the best average chip
result.

Four pieces of arithmetic run through the table below and through the rest of
this document. Each is written out in plain words here, before it is used, and
its usual name is given last:

- **How widely the individual results scatter.** Take one hand's chip result,
  and ask how far a typical hand lands from the average of all of them. In
  poker that distance is enormous, which is why nothing below can be skipped.
  Its name is the **standard deviation**.
- **How far the average itself might be wrong.** An average of many tries is
  not the truth; run the whole exercise again and it would come out somewhere
  else. How far it would typically move is a plus-or-minus attached to the
  average, and gets smaller the more tries there are. Its name is the
  **standard error**.
- **A range instead of a single number.** Widen that plus-or-minus until the
  true answer would fall inside the range in about 95 tries out of 100. Its
  name is a **95% confidence interval**.
- **The plus-or-minus itself**, half the width of that range, is called its
  **half-width**.

Everything that has to be pinned down for the paragraph above to mean anything:

| Setting | What it was |
| --- | --- |
| Engine and game | OpenSpiel `universal_poker`, 52 cards, no-limit, 6 seats, 4 betting rounds |
| Stacks and blinds | 20,000 chips a seat (200 big blinds), blinds 50/100 |
| Betting abstraction | measured under **both**: `fcpa` (a four-move menu) and `fullgame` (19,803 legal moves at the first decision) |
| Offline training | **none** |
| Time to first playable decision | immediate |
| Decision budget | **250 ms**, enforced by a wall-clock deadline checked before every play-out, so it stops at the budget rather than after a fixed count |
| Play-outs per decision, `fcpa` | **7,370 - 12,373 - 13,285** (lowest, middle and highest of six repeats of 20 decisions each; individual decisions ranged 4,848-13,414; machine load 3.1-4.0 throughout) |
| Play-outs per decision, `fullgame` | **117 - 244 - 250** (the same six repeats; individual decisions ranged 31-269) |
| Candidate moves weighed | 4 of 4 legal under `fcpa`; **8 of 19,803** under `fullgame` |
| Play strength, against five opponents moving at random | **+21.90 big blinds a hand**, 95% confidence interval **+14.50 to +29.31**, over **n = 3,467 hands** (menu mode; see below for what this is and is not worth) |

**How the play-outs relate to the 19,803 legal moves: they cannot cover them,
and the chooser does not try.** No play-out count of this order - and not the
16,651 an earlier draft of this document quoted, which is withdrawn as it was
neither reproducible nor stated with its betting abstraction - comes near
19,803 moves. What the chooser actually samples is a **menu of at most eight
candidates built mechanically from the engine's own legal list**: fold, call,
the smallest legal raise, that raise doubled repeatedly, and all-in. The
250 ms is then split round-robin across those candidates.

That has a consequence worth stating in the same breath as the speed. Under
`fullgame`, the middle repeat's 244 play-outs across 8 candidates is about
**30 play-outs each** - and in the slowest repeat, 117 across 8, about
**15 each**. A typical single hand of this game lands 223 big blinds away from
the average (measured below), so an average taken over only 30 of them could
easily be out by roughly **±40 big blinds**, and over 15 by **±58** - that
plus-or-minus is the **standard error** described above. At a quarter of a
second, in real-sizing mode, the ranking the bot produces is therefore **mostly
noise**. Under `fcpa`, the same budget gives about 3,100 play-outs per
candidate, and the same plus-or-minus falls to about **±4 big blinds**, which is
a real comparison. This is the strongest practical argument in the document for
searching the menu game rather than the real-sizing game, and it was invisible
while the betting abstraction went unstated.

Set that against the road we are on: **at least 18 days of computing and more
memory than the machine has, to reach a bot that still cannot choose a bet
size.**

## What the play-strength test says, and what it cannot

First, what a single hand of this game is worth: at 200 big blinds deep,
6-handed, one seat's result for one hand scatters enormously. A typical hand
lands about **223 big blinds** away from the average of all of them - that
distance is the **standard deviation** described above - measured over
n = 100,000 random hands, `bench_play.py variance 100000`. That is the number
that governs every claim about how well anything plays. It means a result
measured over 300 hands could easily be wrong by about **±25 big blinds a
hand**, which is many times larger than any plausible edge. An earlier draft
of this document reported **+3.87 big blinds a hand over 300 hands**. That
figure is **withdrawn**: at that sample size it was indistinguishable from
zero, and quoting it without its interval made noise look like evidence.

Rerun properly, with the interval:

| | |
| --- | --- |
| Set-up | chooser in seat 0, 250 ms a decision, menu mode (`fcpa`); five opponents choosing uniformly at random from the same menu the chooser's own play-outs assume they use |
| Hands | **n = 3,467** (3,572 chooser decisions, 900 seconds, seed 20260915; machine load 2.52 at the start and 4.06 at the end, run under `caffeinate` so the machine could not sleep part way, wall clock 23:01:04 to 23:16:04 - `raw/headtohead.txt`) |
| Result | **+21.90 big blinds a hand** |
| The range the true figure is 95-times-in-100 inside (its 95% confidence interval) | **+14.50 to +29.31** big blinds a hand |
| How far a typical single hand landed from that average (its standard deviation) | 222.6 big blinds a hand |

The interval stays clear of zero, so this **is** a real result: the machinery
works end to end, inside the time budget, and it beats random play.

**What it is not.** Beating opponents who move at random is a very low bar -
random opponents fold good hands, call anything and never punish a mistake. It
says nothing about whether the bot beats a person, and that test has not been
run.

**It is also the most favourable case the chooser could have been given, and
that is a separate limitation from the low bar.** Inside every play-out the
chooser assumes the other five seats pick uniformly from the eight-item menu it
builds; in this test they really do pick uniformly from that same menu. Its
picture of its opponents is therefore exactly right, which it never would be
against anyone real. Being wrong about how opponents behave is the single
largest error a bot of this shape can make, and this test is constructed so
that the error is zero. Read **+21.90 big blinds a hand as a best case**, not
as a typical one.

It is also a **menu-mode** result: the real-sizing chooser, at 250 ms and about
30 play-outs a candidate, was not worth measuring against anything, because its
own candidate rankings are inside their own noise.

**What it costs to answer the real question.** With a typical hand landing 223
big blinds from the average, bounding a result to ±10 big blinds takes about
**1,900 hands** and to ±1 big blind about **190,000**. Against a slow
opponent the hands come slower too. Any future strength claim in this project
should carry its hand count and its interval, or it is not a claim.

What this establishes, and only this: **a playable 52-card no-limit bot for 2 to
9 players on one laptop is reachable in hours by computing at decision time,
and it plays better than random on a four-move menu. Acting with real bet
sizing needs a translation between the two ways of loading the game, and nobody
has built it.** Whether that is the right road still depends on the rule
question at the end of this document.

## What the training measurements show, and what they do not

This is the claim to be most careful about, because an earlier draft of this
document over-claimed it. What was run, exactly:

    cd research/engine_alternatives
    ../../.venv-engines/bin/python bench_cfr.py 45     # numpy seed 20260915

OpenSpiel's own external-sampling Monte Carlo CFR, **with no card abstraction
at all**, betting abstraction `fcpa`, 45 seconds per configuration, one core,
machine load 3.52 at the start and 4.81 at the end. Raw output in
`research/engine_alternatives/raw/cfr.txt`. "Still-new per round" is counted
over the last quarter of each run, so it is the rate *after* the easy
situations have been seen.

**The table is given twice, and the second reading is the honest one.** Giving
every configuration the same 45 seconds is not a fair race: a configuration
that runs faster gets more rounds in those seconds, and more rounds by itself
means more situations found and a lower rate of new ones. So the right-hand
pair of columns re-reads the same run as if every configuration had been
stopped at **16,900 rounds**, which is the most that all seven reached. An
earlier draft of this document only had the left-hand reading, and drew a
conclusion from it that the right-hand reading does not support.

| Game (all `fcpa`, no card abstraction) | Rounds in 45 s | Situations stored | Still-new per round | Situations at 16,900 rounds | **Still-new per round, at 16,900 rounds** |
| --- | --- | --- | --- | --- | --- |
| 6 players, 52 cards, 200bb | 16,944 | 1,456,253 | 71.7 | 1,453,100 | **71.7** |
| 6 players, 52 cards, 20bb | 18,008 | 1,153,621 | 50.6 | 1,097,603 | **51.2** |
| 6 players, 52 cards, 10bb | 20,462 | 964,878 | 33.9 | 845,212 | **36.1** |
| 6 players, 24 cards, 10bb | 25,872 | 633,310 | 15.8 | 488,828 | **19.6** |
| 6 players, **20 cards** (`poker_ai`'s deck), 10bb | 26,311 | 555,196 | 14.2 | 418,308 | **16.4** |
| 3 players, 52 cards, 10bb | 56,564 | 882,287 | 14.5 | 311,032 | **14.8** |
| 6 players, 52 cards, 10bb, **pre-flop only** | 31,122 | 898,369 | 17.7 | 627,745 | **24.0** |

Read a "still-new per round" column, not a "situations stored" one. What matters
is whether the flow of *brand-new* situations is drying up, and in none of these
is it: the best of them is still meeting roughly **fifteen situations it has
never seen before, in every single round**, after tens of thousands of rounds.

Shrinking the deck does not rescue it: `poker_ai`'s own 20-card deck is still
turning up 16.4 new situations per round at 16,900 rounds. **And cutting the
hand back to pre-flop only is not the winner an earlier draft made it.** At
matched rounds it sits at 24.0 - above the 20-card row (16.4), above the
24-card row (19.6) and above the 3-player row (14.8), and below only the three
full-length 52-card games. Its apparent advantage came from counting seconds
instead of rounds: it runs nearly twice as many rounds as the 200bb game in the
same 45 seconds, and a faster configuration always looks calmer on a
per-round-at-the-end measure. **The claim that pre-flop-only is the slowest
growing 6-player game here is withdrawn.**

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
  about an hour on 16 cores (400 million in 1 h 56 m). That is an **unverified
  claim under review** - not built, not run, not timed on this machine, and
  its macOS build is unverified too. But it is a live claim that training in
  advance can fit in hours, and it is enough to rule out saying that road is
  closed for every engine.

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
Python call per node. Six repeats of ten seconds per row.

**All of it was measured in one sitting, with the chooser counts above and the
redraw rates below, taken in rotation.** That matters more than it sounds: this
laptop is shared with other work, and figures taken on different evenings are
not comparable at all. Before every single run the machine's **load average**
was read - roughly how many programs were queued waiting for a processor core,
on a machine with ten of them - and the run was held back while it was above 4.
The six repeats below all ran at a load between **3.08 and 3.96**, and the load
is printed beside every figure in the raw output,
`research/engine_alternatives/raw/paired_session.txt`. `paired_session.py` is
what does this; `bench_speed.py` is the part of it that produced this table.

**Checked again a day later, on a busier machine, and it reproduces.** A second
sitting on 2026-09-16 ran the same four programs in the same rotation, two
repeats of eight seconds a row, at loads of **3.39 to 4.66** - this time without
waiting for the load to fall, because the laptop was shared all evening and it
never settled; every figure in that run is recorded with the load it was taken
at, in `research/engine_alternatives/raw/paired_session_2.txt`. The result is
the one to expect: **the ratios held and the absolute speeds came out lower.**
The chooser got 11,535 - 13,108 play-outs per `fcpa` decision and 202 - 245 per
`fullgame` decision; OpenSpiel ran 42,541 - 48,572 complete `fcpa` hands a
second - its slowest repeat is 11 per cent under the quieter sitting's median
of 47,564, and its fastest is above that median. Every ratio this document
argues from was at least as favourable as the figure quoted below: OpenSpiel
over `texasholdem` on the menu 5.7 - 6.8 (quoted 5.5), over PokerKit 71 - 74
(quoted 64.5), over PyPokerEngine 55 - 61 (quoted 51).
**This is why the document argues from ratios within a sitting and not from the
absolute speeds:** the absolute speeds move with whatever else the laptop is
doing, and the ratios do not.

| Engine and betting mode | Complete hands per second (min - median - max over 6 repeats) | Play-outs in a 250 ms decision, at the median |
| --- | --- | --- |
| **OpenSpiel `universal_poker`, menu (`fcpa`)** | **46,745 - 47,564 - 48,410** | **~11,900** |
| `texasholdem` 0.11.0, menu | 6,311 - 8,526 - 9,095 | ~2,100 |
| PokerKit 0.7.5, menu | 354 - 746 - 765 | ~190 |
| PyPokerEngine 1.0.1, menu | 457 - 926 - 959 | ~230 |
| OpenSpiel `universal_poker`, real sizing (`fullgame`) | 4,251 - 4,438 - 4,628 | ~1,100 |
| `texasholdem` 0.11.0, real sizing | 3,986 - 8,336 - 8,394 | ~2,100 |
| PokerKit 0.7.5, real sizing | 404 - 848 - 873 | ~210 |
| PyPokerEngine 1.0.1, real sizing | 429 - 896 - 946 | ~220 |

Every figure in that table is three to four times higher than the one an
earlier draft of this document gave. Nothing about the engines changed; the
earlier numbers were taken while the machine was busy, and nobody had written
down how busy. That is the whole reason for the load gate described above, and
it is why no figure here should be quoted without it.

**A note on the last column, because an earlier draft got the explanation
wrong.** It counts *complete* hands dealt from scratch, whereas the chooser's
play-out starts from a hand already dealt and part-played. The earlier draft
said the second must therefore be much the cheaper of the two, and used that to
explain a four-fold gap. Measured back to back in the same quarter-second, in
the same repeats, the ratio of chooser play-outs to complete hands is
**0.62 - 1.05 - 1.11**: they cost about the same, and the apparent gap was the
machine's load, not the poker. The two are still different things and both are
stated, but **"a play-out is cheaper because the hand is already dealt" is
withdrawn** - what a play-out saves on dealing it spends on rebuilding the
position from the hand's history before it can start.

Ratios taken **within** each repeat are steadier than the raw rates, and they
are what the comparison should rest on:

| Like-for-like comparison | Ratio per repeat (min - median - max) |
| --- | --- |
| OpenSpiel vs `texasholdem`, both on the menu | 5.3 - **5.5** - 7.5 times faster |
| OpenSpiel vs PokerKit, both on the menu | 61.1 - **64.5** - 133.7 times faster |
| OpenSpiel vs PyPokerEngine, both on the menu | 49.7 - **51.1** - 103.6 times faster |
| OpenSpiel vs `texasholdem`, both real sizing | 0.51 - **0.54** - 1.16, i.e. OpenSpiel is about **1.9 times slower** |
| OpenSpiel vs PokerKit, both real sizing | 4.9 - **5.2** - 11.5 times faster |
| OpenSpiel vs PyPokerEngine, both real sizing | 4.5 - **5.0** - 10.8 times faster |
| OpenSpiel menu vs OpenSpiel real sizing | 10.2 - **10.7** - 11.3 times faster |

Read carefully, that says something the earlier "**9 times** faster" claim hid.
**OpenSpiel's advantage is in menu mode, and in real-sizing mode it is actually
slower than `texasholdem`** - by about 1.9 times, because asking it for the
legal moves at that setting means building a list of 19,803 of them at every
decision. So the case for OpenSpiel is not raw speed at any setting; it is that
the architecture we want **searches the menu**, and on the menu OpenSpiel is
about five and a half times faster than the next working candidate and sixty-odd
times faster than either PokerKit or PyPokerEngine. Under this architecture that
gap is the difference between a considered decision and a guess. What it does
not do is remove the unsolved problem of translating a position between the two
settings.

It is also the only candidate that still has a CFR solver we could use later
(and one that works with more than two players), so choosing it does not close
the door on training something in advance if the schedule ever allows.

## What to do with PokerKit

**Proposed, not adopted here:** keep it for a different job - **checking our
work, not playing.**

PokerKit is the most rules-correct engine in this survey, and one of the two
still actively released - an earlier draft said it was the only one, which is
wrong. Asked of the Python Package Index directly
(`research/engine_alternatives/raw/release_dates.txt`): PokerKit 0.7.5 was
published on 2026-08-22 and `open_spiel` 2.0.2 on 2026-08-12, three weeks
apart, and OpenSpiel's repository was last pushed on 2026-08-31. Every other
candidate's newest release is from 2024 or earlier. PokerKit is too
slow to think with, but it is well suited to replaying a hand we captured off a
screen and confirming the rules were applied exactly right.

That is the same role `treys` plays for hand ranking, and what puts `treys`
there is the ground-truth-evaluator bullet of `CLAUDE.md`'s **"The forefront
rule"** section: it names one external evaluator - "currently `treys`" - as the
ground-truth reference and requires that it stay out of the bot's decision
path. Adding a second borrowed engine as a reference is the same kind of
choice, about a different job, and that bullet does not currently record it.
**This document does not make that choice.** It goes to the same reconciliation
of `ENGINE_ALTERNATIVES.md`, `RESOURCES_BOTS.md` and `RESOURCES_SOLVERS.md` as
the rule question at the end, where the operator decides whether to record it
and in which words.

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
survey **on the four-move menu**, by 5.5 times over `texasholdem`, 64 times over
PokerKit and 51 times over PyPokerEngine (medians over 6 repeats); with real
sizing it is about 1.9 times *slower* than `texasholdem`, for the reason given
in the speed section.

**Solver capability: substantial, and it works multiway.** Ships CFR, CFR+,
discounted CFR, two sampled-CFR variants, Deep CFR, plus best-response and
exploitability measurement. Checked these are not secretly heads-up only:
tabular CFR ran 50 rounds on a **3-player** game, and sampled CFR ran 3,000
rounds on a **3-player no-limit** game and returned usable recommendations.

**One real defect found.** OpenSpiel bundles a ready-made way of thinking ahead
in games where you cannot see your opponents' cards: it invents a plausible set
of hidden cards, plays forward from there many times, and spends most of its
effort on the lines that look best. Its name is **information-set Monte Carlo
tree search**, usually shortened to **ISMCTS**. It **crashes the whole
program** - a hard segmentation fault, exit code 139, not a catchable error -
the moment there are more than two players. Isolated to one line:

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
draw, in the same six-repeat sitting as the speeds above and at the same machine
loads: **102,384 - 105,119 - 105,504 redraws per second at the first decision
after the deal**, and **91,486 - 98,074 - 98,916 per second at a later decision
in the same hand** (ten seconds per position per repeat; lowest, middle and
highest of the six). The busier second sitting gave **79,850 - 85,010** and
**74,712 - 84,387** for the same two positions at loads of 3.39 to 4.66, which
is the same story slowed down. So **of the order of 100,000 a second on a quiet
machine and not far under it on a busy one**, and the later
position is now consistently the slower of the two by about 7 per cent, which is
the direction you would expect from a longer history to replay. An earlier draft
had these the other way round and put the difference down to noise; taken in
rotation on a quiet machine, the ranges no longer overlap. The measured bot uses
this workaround and never touches the broken code.

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

**Requirement 3: no, as the thinking engine.** On the four-move menu, **354 to
765 complete hands a second** (median 746 over 6 repeats of 10 seconds), which
is **61 to 134 times slower than OpenSpiel on the same menu**; with real
sizing, 404 to 873 a second (median 848), 4.9 to 11.5 times slower than
OpenSpiel there. A 250 ms decision buys of the order of 190 play-outs, which
cannot choose between four actions: that is about 46 apiece, and with a typical
hand landing 223 big blinds from the average, an average over 46 of them could
easily be out by about ±33 big blinds - that plus-or-minus is its standard
error, against edges that would be worth a fraction of one big blind. It ships
no pre-trained strategy, so it offers no other route to a playable bot.

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
four-move menu, **6,311 to 9,095 complete hands a second** (median 8,526 over 6
repeats of 10 seconds), **5.3 to 7.5 times slower than OpenSpiel on the same
menu** - about 2,100 play-outs in a 250 ms decision, against OpenSpiel's
~11,900. Meaningfully worse decisions for the same wait, but workable.

**With real sizing it is the faster of the two**: 3,986 to 8,394 hands a second
(median 8,336) against OpenSpiel's 4,251 to 4,438 to 4,628, a per-repeat ratio
of 0.51 to 1.16 with a median of 0.54 - OpenSpiel is about **1.9 times slower**
there, because listing 19,803 legal raise amounts at every decision costs more
than this library's whole hand. If the architecture ever searches with real
sizing rather than a menu, this is the faster engine, and that is a genuine mark
in its favour that the earlier draft's single "9 times slower" figure concealed.

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

**Only half of it imports on this Python, and the half that matters is the
broken half.** The game code runs: `import rlcard` and
`import rlcard.games.nolimitholdem` both succeed, which is how the action-list
count above was taken. But `import rlcard.agents` and `import rlcard.models`
both fail outright with `ModuleNotFoundError: No module named 'distutils'`
(`rlcard/agents/__init__.py:3` does `from distutils.version import
LooseVersion`, and `distutils` was deleted from Python in 3.12). Every agent and
every pre-trained model is therefore unreachable here without patching RLCard
first. Re-run by `bench_requirements.py rlcard`; raw output in
`raw/requirements.txt`.

**Solver capability:** a CFR agent exists (`rlcard/agents/cfr_agent.py`), written
generically over player count, but it is behind the failing import above, and in
any case it walks the entire game tree and needs the engine's rewind feature, so
it is usable only on toy games - which is what RLCard's own documentation
demonstrates it on.

### 5. PyPokerEngine - **passes 1 and 2**, fails 3 on speed

723 stars, last push 2024-04-10, MIT licence; last actual release 2017-04-02.

**Requirement 1: yes** - raises are offered as a minimum/maximum range and any
amount between is accepted (`pypokerengine/engine/action_checker.py:37-44`);
measured at a 6-player 20,000-chip table, the range at the first decision runs
from 150 to 20,000, **19,851 distinct whole-chip amounts**.
**Requirement 2: yes**, and then some - 50 hands at each of 2, 3, 6, 9 and 12
players, **250 hands, zero chip-conservation failures**. Side pots implemented
(`pypokerengine/engine/game_evaluator.py:69`).

**An earlier draft of this document rejected it for the wrong reason, and the
correction matters.** That draft said it "cannot be used for decision-time
search at all", on the grounds that it is a tournament runner which calls you
back on your turn. **That is false.** Alongside the tournament runner it ships
`pypokerengine.api.emulator.Emulator`, which does precisely the three things
the draft said were impossible, each checked here and each committed at
`research/engine_alternatives/pypoker_playouts.py`:

- `generate_initial_game_state` takes a **stack per seat**, so seats can start
  with different amounts - tested with 100 / 500 / 20,000, the arrangement that
  forces side pots;
- `generate_possible_actions` answers "what is legal in *this* position?" for a
  position handed to it, with no callback anywhere;
- `deepcopy_game_state` **clones a position** and `run_until_round_finish`
  plays the clone to the end - which is a play-out, the unit a decision-time
  search is built out of.

**Requirement 3: no - but on speed and on the missing solver, not on shape.**
Driven through that `Emulator`, cloning one mid-hand position and playing the
clone out on the same four-move menu the other engines were given, it manages
**895 - 1,053 - 1,136 play-outs per second** (lowest, middle and highest of six
repeats of ten seconds, taken in the same sitting and at the same machine loads
as every other timing here; the busier second sitting gave **878 - 958** at
loads of 3.68 to 4.66, so the rejection does not turn on which evening it was
measured). That is about **260 play-outs in a 250 ms decision**, against the
**12,373** the chooser gets out of OpenSpiel in the same quarter-second on the
same menu - a factor of **29 to 59, median 47**. Split
across eight candidate moves, 260 play-outs is 33 apiece, which as the PokerKit
entry sets out is not enough to tell four actions apart. Complete hands from
scratch tell the same story: 457 - 926 - 959 a second on the menu, 50 to 104
times slower than OpenSpiel there. And it ships **no solver and no pre-trained
strategy**, so there is no second route.

So it is rejected, but for what it is: **too slow to think with, with nothing
trained to fall back on.** It is not the wrong shape.

### 6. PokerRL - **fails requirement 2, and will not install**

541 stars, last push 2023-03-31, MIT licence. By Eric Steinberger, who also wrote
a well-known Deep CFR paper, so the CFR code is real research code.

**It does not install on this machine.** `pip install PokerRL` fails outright,
exit code 1, at a dependency called `pycrayon`, which cannot be built at all:
its build script imports the package it is trying to build, which in turn
imports `requests`, which is not there while a package is being built.
`ERROR: Failed to build 'pycrayon' when getting requirements to build wheel` -
the whole attempt is in `research/engine_alternatives/raw/pokerrl_install.txt`.
Nothing about PokerRL itself was reachable to test.

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

Speeds are median complete hands per second over 6 repeats of 10 seconds, all
taken in one sitting at a machine load between 3.08 and 3.96; 6-player 52-card
game, 200bb, one core. The two betting modes are listed separately because they
are not comparable to each other. "n/a" means the engine was ruled out before
speed could decide anything, not that it was too slow to measure.

| Engine | 1. Real sizing | 2. 2-9 players | 3. Playable in hours | Hands/sec, menu mode | Hands/sec, real sizing | Solver | Installs on 3.13 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **OpenSpiel `universal_poker`** | **yes** (19,803) | **yes** (2-10) | **yes** - no training at all | **47,564** | 4,438 | yes, multiway | yes |
| **PokerKit** | yes (19,801) | yes (2-9) | no - 64x slower on the menu | 746 | 848 | no | yes |
| `texasholdem` | yes (19,801) | yes (2-9) | marginal - 5.5x slower on the menu, **faster with real sizing** | 8,526 | 8,336 | no | yes |
| PyPokerEngine | yes (19,851) | yes (to 12) | **no** - 51x slower on the menu; ~260 play-outs a decision | 926 | 896 | no | yes |
| RLCard | **no** - 5 fixed actions | yes | no - only a toy model, and it will not import here | n/a | n/a | toy games only | game code only - `rlcard.agents` and `rlcard.models` fail |
| PokerRL | yes | **no** - heads-up CFR | no | n/a | n/a | heads-up only | **no** |
| `clubs` | yes (19,801) | yes | no | n/a | n/a | no | **no** |
| `fedden/poker_ai` (current) | **no** - fixed-limit | 2-6 at 20 cards | **no - 18+ days + 147 GiB** | n/a | n/a | yes, but limit only | yes |

### Does the licence fit?

This project is now a **public** repository under the **GNU General Public
License version 3** (*GPL-3.0*, full text in `LICENSE` at the root), so the
question a licence has to answer here is no longer "may we use this privately?"
but **"may we ship it inside a published GPL-3.0 project?"**. A licence permits
that if it asks nothing of us beyond publishing our own source, which we are
doing anyway. `RESOURCES_BOTS.md` section 2 judges its own criterion (e) on
exactly this standard.

Every candidate above passes, and none of them was a close call:

| Engine | Licence | Fits a public GPL-3.0 repository? |
| --- | --- | --- |
| OpenSpiel `universal_poker` | Apache-2.0 | yes - Apache-2.0 code may be combined into a GPL-3.0 work |
| PokerKit | MIT | yes - MIT asks only that its notice travel with the code |
| `texasholdem` | MIT | yes - same |
| PyPokerEngine | MIT | yes - same |
| RLCard | MIT | yes - same |
| PokerRL | MIT | yes - same |
| `clubs` | GPL-3.0 | yes - the same licence this project is under |
| `fedden/poker_ai` (vendored) | GPL-3.0 | yes - the same licence, which is why vendoring it was safe |

So **no engine was rejected on its licence, and none could have been.** The
recommendation would be unchanged if this repository were private. Licences
read from each package's own metadata and from `vendor/poker_ai/LICENSE`.

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
   pointers**, before a single card object exists. Clustering cost, scaled up
   from the 20-card run that did finish and stated as a floor rather than an
   estimate (`REFERENCE_NOTES.md:399-430`): **at least 18 days of continuous
   computing** - and only if the memory existed, which it does not, so the
   18 days has never been run and could not be.
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
   at of the order of 100,000 redraws per second** (conditions in the OpenSpiel
   entry above).
4. A translation layer between our table-state capture and OpenSpiel's game
   parameters - a day or two of plumbing with no poker judgment in it, which
   `CLAUDE.md`'s forefront rule permits us to write.
5. **A ruling on the forefront rule.** Items 2 and 3 are the parts that choose
   the action and guess the cards, and `CLAUDE.md`'s "The forefront rule"
   section is what says whether we may write them at all. This is not costed
   in days because it is not coding work; it is a decision, and the section
   "Does this contradict the forefront rule?" below sets out what has to be
   decided and where. **Until it is made, items 2 and 3 stay research
   artefacts.**

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
brand-new situations when the time runs out.

An earlier draft of this document nominated the **pre-flop-only** game as the
most promising of them, on the strength of its low rate of new situations per
round. **That nomination is withdrawn.** Compared at a matched 16,900 rounds,
which is the only fair comparison, pre-flop-only turns up **24.0** new
situations per round against **16.4** for the 20-card game and **19.6** for the
24-card one. Of the 6-player games measured here the smallest decks grow most
slowly, not the shortest hand; pre-flop-only only looked best because it runs
more rounds per second than the others and was being judged per second.

What is left standing is the negative, and it is a firm one: **none of these
seven has converged or is close to it**, and the smallest-growing of them is
still meeting about fifteen unseen situations every round after tens of
thousands of rounds. Nothing here is a candidate to be run to completion in
hours. Which game would be, if any, is not answered by this run.

With an abstraction the question is open and untested; see the scoping above.

There is one cheap lever worth recording, and this survey's own chooser
measurements are what show it. Searching the four-move `fcpa` menu bought
**7,370 - 12,373 - 13,285 play-outs per 250 ms decision** (lowest, middle and
highest of six repeats of 20 decisions); searching the real-sizing `fullgame`
bought **117 - 244 - 250** for the same quarter-second. Taken repeat by repeat,
that is a factor of **47 to 65, median 54**. So the practical
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
loop that already has the acting seat in hand (`state.current_player()`);
replacing the uniform choice with per-seat weights changes nothing else. Cost:
one weighted draw per node, paid directly out of the rollout count.

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
`CLAUDE.md`'s "The forefront rule" section says never to let an AI model decide
a poker action, and to reject a change that adds hand-rolled decision logic in
place of the vendored engine. **A rollout loop we wrote, taking the highest
average chip result, is logic that chooses the action.** That it was typed by
hand rather than produced by a model does not exempt it: the bullet rejecting
hand-rolled decision logic in place of the vendored engine is about hand-rolled
logic in its own right, whoever or whatever typed it.

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
  bar, and even that result is reported with its interval above. **Worse, those
  random opponents drew from exactly the menu of moves the bot's own play-outs
  assume they draw from, so its picture of them was perfectly accurate - the
  most favourable condition it could be given, and one no real opponent will
  reproduce.** The next test should be against a simple rule-following opponent
  whose behaviour the bot does *not* already assume, then a human. Budget it
  from the scatter: a typical single hand of this game lands 223 big blinds from
  the average, so pinning a result down to ±1 big blind per hand takes about
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
