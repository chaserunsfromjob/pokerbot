# Engine alternatives: what else could we build the bot on?

## What this file is for

We built this project on a borrowed poker engine, `fedden/poker_ai`. Reading it
closely turned up two mismatches with what `CLAUDE.md` says we are building:

- it deals a **20-card deck** (only 10, Jack, Queen, King, Ace), not the normal
  52-card deck; and
- its betting is **fixed-limit** - a raise is always exactly one big blind,
  never an amount the player chooses.

And a third problem, which is the one that actually decides this document:
getting it to 52 cards needs about **18 days of the laptop running flat out**,
plus more memory than the laptop has. There is no budget for that.

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

Verified on 2026-09-15, macOS 24.2.0 (arm64), Python 3.13.15.

---

# The recommendation, first

**Switch the engine to OpenSpiel's `universal_poker`, and abandon the
train-in-advance approach entirely in favour of computing the decision at the
moment we need it.**

Keep `fedden/poker_ai` in the repository for reference only. Do not spend
another hour adapting it.

## Why - the one measurement that settles it

A bot was built and run during this survey. It does no training at all. When it
is our turn, it takes each move it is allowed to make, plays the rest of the
hand out at random a few thousand times, and picks whichever move ended up with
the most chips. That is the entire idea.

Measured, on this laptop, at a **6-player 52-card no-limit table**:

| | |
| --- | --- |
| Offline training required | **none** |
| Time to first playable decision | **immediate** |
| Time per decision | **250 milliseconds** |
| Hands played out per decision | **16,651** |
| Result over 300 hands vs. random opponents | **+3.87 big blinds per hand** |

Set that against the road we are on: **18 days of computing and more memory
than the machine has, to reach a bot that still cannot choose a bet size.**

## The honest caveat, up front

Beating opponents who move at random is a **very low bar**. That number proves
the machinery works end to end and fits the time budget. It does **not** show
the bot beats people. Only playing it against something that defends itself will
show that, and that test has not been run.

But it establishes the thing the operator asked about: **a playable 52-card
no-limit bot for 2-9 players on one laptop is reachable in hours, and the way to
get there is to compute at decision time rather than train in advance.**

## Why this is a genuine change of direction, not a shortcut

Three measurements say the train-in-advance road is closed on this machine, for
*every* engine here, not just `poker_ai`:

- On the real 6-player 52-card game, the CFR solver ran 18,099 rounds in 45
  seconds and was **still discovering 64 completely new situations every
  round**, with no sign of slowing. It had not seen the game once.
- Shrinking the game did not rescue it. At 6 players it was still finding 31 new
  situations per round on a 24-card deck, and **27 per round on the very 20-card
  deck `poker_ai` uses**. Even `poker_ai`'s own small game does not finish.
- The only variant that showed real convergence was one with the raising
  removed entirely, which is not poker.

Training in advance requires a **card abstraction** first - the compression step
`REFERENCE_NOTES.md` calls clustering, which groups similar situations so the
solver has a finite job. Nobody on this list ships one for 52-card multiway
hold'em, and writing one is the 18-day, 147-gibibyte problem we are trying to
escape. **Decision-time computing skips the requirement altogether**, because it
never needs a strategy for situations it is not currently in.

## Why OpenSpiel specifically, and not the other working engines

Once the architecture is "think during the hand", the engine's job changes: it
has to play out hands *fast*, because speed is directly how good the decision
is. Measured, same 6-player game, one core:

| Engine | Complete hands played per second | Rollouts inside a 250 ms decision |
| --- | --- | --- |
| **OpenSpiel `universal_poker`** (C++) | **56,414** | **~14,100** |
| `texasholdem` (Python) | 6,273 | ~1,570 |
| PokerKit (Python) | 781 | ~195 |

OpenSpiel is **9 times** faster than the next working candidate and **72 times**
faster than PokerKit. Under this architecture that gap is not a detail - it is
the difference between a considered decision and a guess.

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
survey by a wide margin.

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
rewritten in about fifteen lines of our own Python and runs at **47,020 per
second**. The measured bot above uses that workaround and never touches the
broken code.

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

**Requirement 3: no, as the thinking engine.** **781 hands per second** - 72
times slower than OpenSpiel. A 250 ms decision buys about 195 rollouts, which is
not enough to choose between four actions with any confidence. It ships no
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

**Requirement 3: marginal.** **6,273 hands per second** - 9 times slower than
OpenSpiel, about 1,570 rollouts in a 250 ms decision. Workable but meaningfully
worse decisions for the same wait. No pre-trained strategy, no solver; its only
bundled agents are call-only and random.

The easiest code here to read and modify, and the natural fallback if OpenSpiel's
C++ ever becomes a problem to install.

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

| Engine | 1. Real sizing | 2. 2-9 players | 3. Playable in hours | Speed (hands/sec) | Solver | Installs on 3.13 |
| --- | --- | --- | --- | --- | --- | --- |
| **OpenSpiel `universal_poker`** | **yes** (19,803) | **yes** (2-10) | **yes** - no training at all | **56,414** | yes, multiway | yes |
| **PokerKit** | yes (19,801) | yes (2-9) | no - 72x too slow | 781 | no | yes |
| `texasholdem` | yes (19,801) | yes (2-9) | marginal - 9x slower | 6,273 | no | yes |
| PyPokerEngine | yes | yes (to 12) | **no** - cannot search | n/a | no | yes |
| RLCard | **no** - 5 fixed actions | yes | no - only a toy model | n/a | toy games only | yes |
| PokerRL | yes | **no** - heads-up CFR | no | n/a | heads-up only | **no** |
| `clubs` | yes | yes | no | n/a | no | **no** |
| `fedden/poker_ai` (current) | **no** - fixed-limit | 2-6 at 20 cards | **no - ~18 days + 147 GiB** | n/a | yes, but limit only | yes |

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
2. The decision-time chooser measured above: **about forty lines, already
   written and run during this survey.** No training.
3. The fifteen-line Python workaround for the multiway crash: **written and
   measured at 47,020 per second.**
4. A translation layer between our table-state capture and OpenSpiel's game
   parameters - a day or two of plumbing with no poker judgment in it, which
   `CLAUDE.md`'s forefront rule permits us to write.

**Total offline computing: zero.** The remaining work is integration, which is
exactly the category `CLAUDE.md` says is ours.

### Is there a pre-trained strategy we could just download?

Checked, because it would be the cheapest road of all. **No.**

- OpenSpiel ships no trained poker strategies. The four files under
  `universal_poker/endgames/` are heads-up test fixtures, not a strategy.
- RLCard's only pre-trained poker model is for **Leduc**, a 6-card toy game.
- PokerRL, PokerKit, `texasholdem`, PyPokerEngine and `clubs` ship none.

No downloadable 52-card multiway no-limit strategy exists in any of these
projects. This is a firm negative, not an unchecked assumption.

### Is there a smaller offline solve that fits in hours?

Partly, and it is worth knowing as a later improvement rather than a starting
point. Measured at 25-40 seconds per configuration:

| Game | Rounds run | Situations found | Still-new per round |
| --- | --- | --- | --- |
| 6 players, 52 cards, 20bb | 10,424 | 759,129 | 72.8 |
| 6 players, 52 cards, 10bb | 11,614 | 640,641 | 55.2 |
| 6 players, 24 cards, 10bb | 13,656 | 417,624 | 30.6 |
| 6 players, **20 cards** (`poker_ai`'s deck), 10bb | 12,957 | 349,870 | 27.0 |
| 3 players, 52 cards, 10bb | 16,573 | 307,825 | 18.6 |

Every one is still finding large numbers of brand-new situations and none is
close to finished. Only a **pre-flop-only** game showed real slowing: situations
found went 31,143 → 66,817 → 80,078 → 81,291 as rounds went 1,000 → 5,000 →
20,000 → 37,000, which is a curve that is flattening. So **a pre-flop-only
strategy for a fixed table size is the largest thing that plausibly finishes in
hours.** That is a genuine future improvement - it would give the bot a solid
opening game to fall back on - but it is not a bot on its own, and it is not
where to start.

There is one more cheap lever worth recording: the smallest action menu is **297
times smaller** than continuous sizing on an identical game (4,678 situations
versus 1,391,608, and 43 times faster in wall-clock). So the practical shape is
**think against a small menu, act with real sizing** - which OpenSpiel supports
directly by loading the same game twice with different settings.

---

## What this means for the plan in `CLAUDE.md`

The plan's stage 1 is "find out what it takes to move `poker_ai` off the 20-card
deck". This survey answers that question from the other direction: **it takes
more than adopting an engine where the problem does not exist, and more time
than we have.**

Stage 2 - opponent modelling - is where `CLAUDE.md` says the real win is, and
this recommendation helps it rather than delaying it. A bot that decides during
the hand has an obvious place to put what we learn about an opponent: instead of
playing the remaining hands out at random, play them out the way *that specific
player* actually behaves. Opponent modelling stops being a layer bolted on after
training and becomes the thing the search is built around. A trained-in-advance
strategy has no comparable hook.

Nothing here contradicts the forefront rule. Poker judgment stays inside
borrowed, tested engine code - OpenSpiel deals, ranks and pays every hand. What
we write is the search loop, the opponent model and the plumbing.

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

- **Whether the recommended bot beats anything that defends itself.** It was
  measured only against opponents moving at random, which is a very low bar. The
  next test should be against a simple rule-following opponent, then a human.
- Whether the OpenSpiel multiway crash has been reported or fixed upstream. It
  was reproduced here against released version 2.0.2; the issue tracker was not
  searched. We do not need it fixed, having worked around it.
- How much decision time is available in real play. Every timing here assumes a
  250 millisecond budget. If the real table allows two seconds, the bot gets
  eight times the thinking; if it allows fifty milliseconds, it gets a fifth.
  That number comes from the table-capture work, not from here.
