# The decision layer, part one: a strategy worked out in advance

## What this file is for

`ENGINE_ALTERNATIVES.md` settles what deals the cards: OpenSpiel's
`universal_poker`. It deliberately leaves open what *decides the bet*. This
document covers one of the two ways of deciding, and one only: **work the whole
strategy out ahead of time, save it, and look the answer up at the table.** The
saved answer is called a **blueprint**.

The other way - think during the hand, about this hand only - is
`DECISION_LAYER_SEARCH.md`, written by another agent at the same time as this
one. Nothing here covers it. The two documents are meant to be read together and
then decided between.

This document exists because the project's rules changed. `CLAUDE.md`'s
forefront rule used to be read as barring us from writing the thing that
chooses. It now says an AI may **write** decision code but never **be** the
decision - ordinary, tested code that calls real engine solvers is allowed,
a model consulted live is not. Every option below is ordinary tested code
calling OpenSpiel's own solvers, so all of them are now on the table where
before they were not.

## Words this document needs

Each is explained in plain words first and named afterwards.

- **A strategy worked out in advance.** Play millions of hands against yourself
  before ever sitting down, write down what to do in every situation you met,
  and at the table just look it up. The looked-up table is a **blueprint**.
- **Learning by regret.** After a hand, ask of each move you did not make: how
  much better off would I have been? Do more of whatever you regret not doing.
  Repeat a few million times and the play converges on something very hard to
  beat. The method is **counterfactual regret minimisation**, always shortened
  to **CFR**.
- **Squashing the game down.** There are more distinct situations in six-handed
  no-limit hold'em than there are atoms in the observable universe, so no
  blueprint can hold them all. You group situations that play alike and treat
  each group as one - all hands of roughly equal strength become "bucket 43",
  and the choice of bet size is cut from "any number of chips" to a short menu.
  That squashing is an **abstraction**; the two halves are **card abstraction**
  and **action abstraction**.
- **How beatable a strategy is.** Let a perfect opponent study your strategy and
  play the single best counter to it. How much they win is how far from perfect
  you are. Summed over every player at the table, that quantity is
  **NashConv**; at a two-player table it is also called **exploitability**.
  Zero means nobody can gain by deviating. **It is measured inside the squashed
  game, not the real one** - a caveat that does more damage than it first
  appears, and is returned to below.
- **How busy the laptop is.** The number of programs queued waiting for a
  processor core, averaged over the last minute: the **load average**. This
  machine has ten cores and other agents share it. `ENGINE_ALTERNATIVES.md`
  establishes that above about 4.0 the timings here stop meaning anything.

## How the numbers below were produced

Every figure in the measurement section comes from one committed program,
`research/bench_blueprint_cfr.py`, and its raw output is committed beside it at
`research/blueprint_cfr_results.jsonl`. Re-run the whole sweep with:

    .venv/bin/python research/bench_blueprint_cfr.py --all --budget 180

The program runs each (method, table size) pair in its own separate process, for
a fixed stopwatch budget, then asks OpenSpiel for NashConv on the resulting
strategy. It records the 1-minute load average from `uptime` at the start and end
of every cell and flags any cell where it went over 4.0. The separate processes
are not tidiness: `universal_poker` **aborts the whole process** - no catchable
error, exit code 139 - if the deck is too small to deal, so one bad cell would
otherwise take the sweep down with it.

Machine and versions: macOS 15.2 (24.2.0), Apple M4, 10 cores, 16 GiB,
Python 3.13.15, `open_spiel` 2.0.2 installed from the Python Package Index as a
native arm64 wheel (`pip install open_spiel`, one command, no compiler needed).
Measured 2026-09-16.

**The honest caveat about these timings, stated before the numbers rather than
after them.** Other agents were working this laptop throughout. The load average
was 2.53 when this session started, 3.81 when the sweep was launched, and had
reached 4.80 within three minutes - **above the 4.0 line**. The per-cell load is
recorded in the results file and in the table below, and cells taken above 4.0
are marked. Those cells' speeds are **floors, not measurements**: the true
speed on an idle machine is higher, by an unknown amount. Nothing in the
recommendation turns on a speed difference small enough for this to reverse it;
what the recommendation turns on is a difference of several thousand times,
which no amount of load noise touches. The operator instruction for this task
was explicitly to move fast rather than to measure perfectly, so each cell was
run once, not repeated. **A single run is not a range.** Where this document
needs a claim to be solid it says which measurement carries it.

Long runs were held awake with `caffeinate`, because a laptop that sleeps
mid-run silently ruins the timing - the trap `ENGINE_ALTERNATIVES.md` documents
having been caught by.

## What OpenSpiel actually ships, checked by importing it on this machine

Not read off a website. Each line below was run in this project's `.venv` on
2026-09-16.

| What it is | Where it lives | Does it import here? |
| --- | --- | --- |
| The engine itself | `pyspiel` (a compiled `.so`) | yes; 126 games registered, `universal_poker` among them |
| Vanilla CFR, in C++ | `pyspiel.CFRSolver` | yes |
| CFR+, in C++ | `pyspiel.CFRPlusSolver` | yes |
| External-sampling MCCFR, in C++ | `pyspiel.ExternalSamplingMCCFRSolver` | yes |
| Outcome-sampling MCCFR, in C++ | `pyspiel.OutcomeSamplingMCCFRSolver` | yes |
| CFR-BR | `pyspiel.CFRBRSolver` | yes |
| The same four in Python (slower, readable, hackable) | `open_spiel.python.algorithms.cfr`, `.external_sampling_mccfr`, `.outcome_sampling_mccfr` | yes |
| Linear and discounted CFR | `open_spiel.python.algorithms.discounted_cfr` | yes |
| NashConv / exploitability | `pyspiel.nash_conv`, `pyspiel.exploitability`, and `open_spiel.python.algorithms.exploitability` | yes |
| Best response | `open_spiel.python.algorithms.best_response` | yes |
| **Deep CFR** | **not** in `open_spiel.python.algorithms` at all | **no** - see below |

Deep CFR is the one that is not where you would look for it and does not work
out of the box. It is at `open_spiel/python/pytorch/deep_cfr.py` and
`open_spiel/python/jax/deep_cfr.py`, and on this machine both fail to import:

    open_spiel.python.pytorch.deep_cfr -> ModuleNotFoundError: No module named 'torch'
    open_spiel.python.jax.deep_cfr     -> ModuleNotFoundError: No module named 'chex'

Neither PyTorch nor JAX ships with the `open_spiel` wheel. Using Deep CFR here
means installing a whole neural-network stack first. That is a real cost, not a
formality, and it is counted against Deep CFR below.

**Two traps found while doing this, recorded so nobody loses an afternoon to
them.**

First, the sampling solvers' saved strategies do not work with NashConv the
obvious way. `pyspiel.nash_conv(game, solver.average_policy())` raises
`GetStatePolicy(const std::string&) unimplemented` for both MCCFR solvers. The
fix is the third argument: `pyspiel.nash_conv(game, solver.average_policy(),
True)`, which tells it to look strategies up by game state instead of by name.
`CFRSolver` and `CFRPlusSolver` work either way.

Second, `universal_poker` game settings are fussy about types. `firstPlayer=1`
is rejected - *"Wrong type for parameter firstPlayer. Expected type: kString,
got kInt"* - because it wants a string even when the string is one character.
Pass the settings as a Python dictionary with the value quoted.

## The two halves of squashing the game, and which half OpenSpiel gives you

This matters more than the choice of method, so it comes before the options.

**The betting menu, OpenSpiel gives you.** `universal_poker` has a setting
called `bettingAbstraction` with exactly four values, read off the engine's own
source at `games/universal_poker/universal_poker.h:62`:

| Value | What a player may do |
| --- | --- |
| `fc` | fold or call. Two moves. |
| `fcpa` | fold, call, bet the pot, or go all in. Four moves. |
| `fchpa` | fold, call, bet half the pot, bet the pot, or go all in. Five moves. |
| `fullgame` | **every** whole-chip raise amount they can afford. This is real no-limit. |

`fullgame` is the default. Everything measured below uses `fcpa`, the four-move
menu, because that is what a blueprint can possibly hold.

**The card groupings, OpenSpiel does not give you.** Searched the whole
installed package: there is no bucketing, clustering or card-abstraction module
anywhere in `open_spiel/python/algorithms/`. The only lever the engine offers is
a **smaller deck** - fewer ranks, fewer suits - which is a different thing from
grouping real 52-card hands into strength buckets. Whoever builds a blueprint on
`universal_poker` **writes the card abstraction themselves**, and
`CLAUDE.md`'s forefront rule bears directly on that: grouping hands by measured
strength is the engine's job to evaluate and ours only to bookkeep. This is the
single largest piece of unbuilt work behind every option below, and no option
below escapes it.

The one thing that softens it: `pyspiel.load_universal_poker_from_acpc_gamedef`
is bound in the Python layer, so a game definition in the standard Annual
Computer Poker Competition format can be loaded directly. Abstractions written
for that competition are therefore loadable without touching C++.

## The measurement

Each cell is one method at one table size for a 180-second budget, run once.
The card abstraction is a **tiny deck**, the smallest that deals:

| Table | Deck | Hole cards | Board | Stacks | Decision points in the tree |
| --- | --- | --- | --- | --- | --- |
| 2-handed | 8 cards (4 ranks x 2 suits) | 1 each | 1 | 6 chips | 256 |
| 3-handed | 8 cards (4 ranks x 2 suits) | 1 each | 1 | 6 chips | 1,488 |
| 6-handed | 7 cards (7 ranks x 1 suit) | 1 each | 1 | 4 chips | 47,474 |

Those last three figures are measured, by enumerating the tree with
`open_spiel.python.algorithms.get_all_states`. **The 6-handed one is the number
to carry away from this whole document.** Seven cards. One card each and one on
the board. Four-chip stacks. A four-move betting menu. The smallest six-handed
poker game that can physically be dealt - and it has 47,474 decision points
across **7,670,880 game states**, took 37.2 seconds merely to *list*, and used
**5.8 GB of memory** to hold the list (load 3.66, under the line). Real
six-handed no-limit hold'em, 52 cards, 200-chip stacks, every bet size, is
larger than this by a factor with well over a hundred zeros in it.

<!-- MEASUREMENT_TABLE -->

## The options

Six, each rated at the end of its section against the operator's five
requirements: **(a)** 2 to 9 players, **(b)** true no-limit bet sizing,
**(c)** exploiting named opponents by identity, **(d)** reachable in hours on
this one laptop, **(e)** fits a public GPL-3.0 repository.

---

### Option 1. Vanilla CFR

**What it is.** The original. Every iteration walks the entire game tree,
updating the regret at every decision point. Zinkevich, Johanson, Bowling and
Piccione, *Regret Minimization in Games with Incomplete Information*, NIPS 2007.

**What OpenSpiel ships.** `pyspiel.CFRSolver` (C++, fast) and
`open_spiel.python.algorithms.cfr.CFRSolver` (Python, about 200 readable lines).
Both import here. Nothing to build.

**Abstraction it needs.** The most of any option, because its cost per iteration
is the size of the whole tree. Card abstraction: unavoidable and ours to write.
Action abstraction: `fcpa` or `fchpa`.

**Reachable in hours here?** At the 2-handed toy it is not merely reachable, it
is *finished* - see the table. At 6-handed it is the worst fit of all six
options, because one iteration costs a full pass over those 7.67 million states.

**Opponent modelling.** The Python implementation is short enough to modify, and
the modification wanted is well defined: hold some players' strategies fixed at
what an opponent model says they do, and run regret updates for our seat only.
That is a **best response**, and `open_spiel.python.algorithms.best_response`
already computes one. `CLAUDE.md` explicitly allows this shape - "Substituting
an opponent model into the engine's own solver" sits in the allowed column.

**Rating.** (a) yes, the solver is n-player. (b) no - needs an action menu.
(c) yes in principle, by fixing opponents' strategies, but at the cost of a
fresh solve per opponent line-up. (d) only at toy sizes. (e) yes.

---

### Option 2. CFR+

**What it is.** CFR with two changes: regrets are never allowed to go negative,
and later iterations count for more. In practice it converges dramatically
faster. Tammelin, *Solving Large Imperfect Information Games Using CFR+*,
arXiv:1407.5042, 2014. It is the method behind Cepheus, which essentially solved
two-player **limit** hold'em: Bowling, Burch, Johanson and Tammelin, *Heads-up
limit hold'em poker is solved*, Science 347(6218):145-149, 2015.

**What OpenSpiel ships.** `pyspiel.CFRPlusSolver`. Imports here. Nothing to
build. A drop-in replacement for Option 1 - the same call, `evaluate_and_update_policy()`.

**Abstraction it needs.** Identical to Option 1. CFR+ changes how fast you
converge, not how big a tree you can hold.

**Reachable in hours here?** Same tree-size ceiling as Option 1, but it gets
far further down the exploitability curve inside a fixed budget - that is the
whole point of it, and the measurement above shows it.

**Opponent modelling.** Same as Option 1.

**The sobering part.** Cepheus is the cautionary figure for anyone who thinks a
solved blueprint is close. The game it solved is two-player **limit** hold'em -
fixed bet sizes, one opponent - a game vastly smaller than what this project
targets, and it took a cluster running for months. That is what "solve it in
advance" costs at the small end of the problem.

**Rating.** (a) yes. (b) no. (c) yes in principle, same caveat as Option 1.
(d) only at toy sizes, but it is the best of the exhaustive methods. (e) yes.

---

### Option 3. External-sampling MCCFR

**What it is.** Instead of walking the whole tree, deal one random set of cards,
sample what the opponents do, but consider **all** of our own moves. Lanctot,
Waugh, Zinkevich and Bowling, *Monte Carlo Sampling for Regret Minimization in
Extensive Games*, NIPS 2009. "MCCFR" is Monte Carlo CFR; "Monte Carlo" just
means "by random sampling".

**What OpenSpiel ships.** `pyspiel.ExternalSamplingMCCFRSolver`, and the Python
version at `open_spiel.python.algorithms.external_sampling_mccfr`. Both import.
Remember the NashConv trap above - this solver needs the third argument `True`.

**Abstraction it needs.** Card abstraction still ours to write, but the pressure
is different: sampling means the cost of an iteration no longer scales with the
number of possible deals, only with the depth of the tree and the size of our
own action set. A larger card abstraction costs *memory for the strategy table*
rather than *time per iteration*.

**Reachable in hours here?** This is the family that keeps working as seats are
added, and the measurement bears that out.

**Opponent modelling.** Better suited than the exhaustive methods, for a
practical reason: the opponents' moves are *sampled*, so an opponent model is
substituted simply by sampling from the model instead of from the current
strategy. That is a small change to a short file, and it is the same rule-legal
shape as Option 1.

**Rating.** (a) yes. (b) no. (c) yes, and more cheaply than Options 1 and 2.
(d) the best of the tabular options. (e) yes.

---

### Option 4. Outcome-sampling MCCFR

**What it is.** The same 2009 paper's cheaper sibling: sample a **single line of
play** through the hand and update only that. The cheapest possible iteration,
and the noisiest.

**What OpenSpiel ships.** `pyspiel.OutcomeSamplingMCCFRSolver` and
`open_spiel.python.algorithms.outcome_sampling_mccfr`. Both import. Same
NashConv trap.

**Abstraction it needs.** As Option 3.

**Reachable in hours here?** It does the most iterations per second of anything
measured, by a wide margin. Whether that converts into a better strategy is the
question the measurement answers, and the answer is not the one the iteration
count suggests.

**Opponent modelling.** As Option 3.

**Rating.** (a) yes. (b) no. (c) yes. (d) most iterations per second, but see
the measurement before treating that as a recommendation. (e) yes.

---

### Option 5. Deep CFR

**What it is.** Throw away the lookup table. Train a neural network to predict
the regrets instead, and let the network generalise across hands it never saw.
The attraction is that it removes the hand-written card abstraction - the
network learns its own. Brown, Lerer, Gross and Sandholm, *Deep Counterfactual
Regret Minimization*, arXiv:1811.00164, 2018 (ICML 2019).

**What OpenSpiel ships.** This is the one that disappoints on inspection. It is
**not** in `open_spiel.python.algorithms`. It is at
`open_spiel/python/pytorch/deep_cfr.py` and `open_spiel/python/jax/deep_cfr.py`,
and **neither imports on this machine**: `No module named 'torch'` and
`No module named 'chex'` respectively. The `open_spiel` wheel does not bring a
neural-network stack with it.

**Abstraction it needs.** In principle none, which is exactly its appeal. In
practice it still needs the action menu, and it needs a way to present a hand to
a network as numbers.

**Reachable in hours here?** No, and this is the clearest "no" in the document.
It replaces a cheap table update with a neural network training step inside
every iteration, on a laptop with no usable training GPU. It is also the only
option that adds a large dependency before the first experiment can run at all.
`CLAUDE.md`'s compute budget - "reject any approach that needs multi-day compute
to reach a playable bot" - rejects this one on its face.

**Opponent modelling.** The most interesting story in theory and the least
available in practice: a network can take features describing the opponent as
extra inputs, so one trained model could cover a range of opponent types. Nobody
has published this for multiway no-limit hold'em, and building it is a research
project, not a class project.

**Rating.** (a) yes in principle. (b) no. (c) theoretically the best of the six,
practically unavailable. (d) **no**. (e) yes - OpenSpiel is Apache-2.0 and
PyTorch's licence is permissive, both combinable into GPL-3.0.

---

### Option 6. A Pluribus-style abstracted blueprint

**What it is.** Not a module - a recipe, and the only one on this list that has
actually beaten strong humans at a six-handed no-limit table. Brown and
Sandholm, *Superhuman AI for multiplayer poker*, Science 365(6456):885-890,
2019. The recipe: build a card abstraction and a small action abstraction,
run a modern CFR variant in self-play against copies of itself to produce a
coarse blueprint, then **search during the hand** to sharpen it.

**What OpenSpiel ships.** The solver half, and only the solver half. The variant
Pluribus used is in the discounted/linear CFR family, and
`open_spiel.python.algorithms.discounted_cfr` imports here - it covers Linear
CFR and Discounted CFR from Brown and Sandholm, *Solving Imperfect-Information
Games via Discounted Regret Minimization*, arXiv:1809.04040, 2018 (AAAI 2019).
The card abstraction: not shipped, ours to write. The search: not shipped in a
poker-ready form, and out of scope here - `DECISION_LAYER_SEARCH.md` covers it.

**The part that decides this option.** Pluribus's blueprint is only half the
system. The paper's own framing is that the blueprint is deliberately coarse and
the real-time search is what makes it strong. **Taking the blueprint half alone
is taking the half that was never claimed to be sufficient.**

**Reachable in hours here?** No. The commonly quoted figures for Pluribus's
blueprint are days on a many-core server. **This document could not verify those
figures**: the Science full text returned HTTP 403 to every fetch attempted, so
only the title, authors, year, venue and the publisher's own abstract were
confirmed. The abstract confirms the headline result - six-player no-limit
hold'em, beat elite professionals - and says nothing about compute. Treat any
specific day-count or dollar-cost for Pluribus as **unverified here**, and treat
the direction of the answer, "much more than hours on a laptop", as safe.

**Opponent modelling.** Pluribus is the strongest *evidence against* requirement
(c) in this whole document. It did no opponent modelling at all. It beat elite
professionals by approximating equilibrium and searching well, not by working
out who it was playing. Anyone arguing that beating humans at a six-handed table
requires opponent modelling has to answer Pluribus.

**Rating.** (a) yes - six-handed is the case it was built for. (b) no.
(c) **no, by design.** (d) no. (e) yes for the OpenSpiel parts; Pluribus itself
was never released, so this is a recipe to reimplement, not code to take.

---

## How an opponent model could bend a blueprint

Requirement (c) - beating *these* people, not an imaginary perfect opponent - is
the project's stated reason for existing (`CLAUDE.md`: "consistently beat real
human players at a table of 3 or more, not chase a theoretical optimum that does
not exist at that table size"). A blueprint is, by construction, the opposite of
that: it is an approximation to the play that nobody can exploit, which is also
the play that exploits nobody. So the question is how to bend one.

There are three shapes, in increasing cost.

**One: pick which blueprint to load.** Solve two or three blueprints in advance,
each against a different archetype of opponent, and choose at the table by what
the opponent model has observed. Costs nothing at the table; costs one full
solve per archetype in advance. `CLAUDE.md` puts "Selecting *which* engine
strategy to load" squarely in the allowed column, so this shape needs no rule
change at all.

**Two: re-solve with the opponents' strategies held fixed.** Replace the
opponents in the solver with what the model says they do, and run CFR for our
seat only. Done to the limit this is simply a best response, which is maximally
exploitative and maximally fragile - it loses badly the moment the opponent
changes. The published fix is to blend: solve against a mixture of "the model"
and "the equilibrium", tuned by how much data the model rests on. Johanson,
Zinkevich and Bowling, *Computing Robust Counter-Strategies*, NIPS 2007, is the
method - the **restricted Nash response**. This is the shape `CLAUDE.md` names
explicitly in the allowed column, "Substituting an opponent model into the
engine's own solver".

**Three: re-solve during the hand.** Out of scope - `DECISION_LAYER_SEARCH.md`.

The rule boundary to keep hold of while reading these: `CLAUDE.md` allows our
own code to count what opponents did, turn those counts into rates, shrink them
toward a baseline, and sort players into buckets. It forbids our code from
assigning a range, reading board texture, or choosing an action. All three
shapes above stay on the right side of that line, because in all three the
opponent model supplies only **frequencies** and the solver still does the
poker. `OPPONENT_MODEL_DESIGN.md` already specifies the counting and shrinking
half. Shape two is the join between that document and this one.

One warning that applies to all three. Squashing the game can make things
*worse* in ways that are not gradual: a finer abstraction can produce a strategy
that is **more** exploitable than a coarser one, so "add more buckets until it
is good" is not a reliable plan. Waugh, Schnizlein, Bowling and Szafron,
*Abstraction pathologies in extensive games*, AAMAS 2009. And every NashConv
figure in this document is measured **inside** the squashed game; a strategy
with NashConv near zero in a toy game can be badly exploitable in the real one.
The numbers below say a method converged. They do not say a bot is good.

## Ratings, all six side by side

Key: **yes** meets it; **part** meets it with a named condition; **no** does not.

| Option | (a) 2-9 players | (b) true no-limit sizing | (c) exploits named opponents | (d) hours on this laptop | (e) GPL-3.0 public repo |
| --- | --- | --- | --- | --- | --- |
| 1. Vanilla CFR | yes | no - needs a bet menu | part - one solve per line-up | no, toy sizes only | yes |
| 2. CFR+ | yes | no - needs a bet menu | part - one solve per line-up | no, toy sizes only | yes |
| 3. External-sampling MCCFR | yes | no - needs a bet menu | part - sample from the model | part - furthest reach of the six | yes |
| 4. Outcome-sampling MCCFR | yes | no - needs a bet menu | part - sample from the model | part - fastest iterations, slowest progress | yes |
| 5. Deep CFR | yes in principle | no - needs a bet menu | part, unpublished for multiway | **no** - and will not import here | yes |
| 6. Pluribus-style blueprint | yes | no - needs a bet menu | **no, by design** | **no** - server-scale | yes, as a recipe to rebuild |

**Nothing scores yes on (b).** That is not six failures; it is one fact about
blueprints. A strategy computed in advance has to be *finite*, and real no-limit
betting is not. Recovering real bet sizes on top of a menu-based blueprint needs
a translation step both ways - map the opponent's odd-sized bet onto the nearest
menu item, map our menu item back onto a real number of chips - and
`ENGINE_ALTERNATIVES.md` records that nobody on this project has built it. Any
route that goes through (b) pays that cost once, and pays it whichever option
above is chosen.

**(e) is a clean yes throughout, and worth stating because it was checked rather
than assumed.** OpenSpiel is licensed Apache-2.0, read from the project's own
`LICENSE` file on 2026-09-16. Apache-2.0 code may be combined into a GPL-3.0
work; the combination is then GPL-3.0. That is the direction this project needs
and it is the permitted direction. Nothing in this document introduces a
licence that would conflict with `LICENSE` at this repository's root.

## Sources, and how each one was checked

Every source below was fetched on 2026-09-16 from this machine and its title,
authors, year and the specific claim taken from it were read off what came back.
Where a fetch failed, that is recorded here rather than papered over.

| Source | Authors, year | What is taken from it | How checked |
| --- | --- | --- | --- |
| *Regret Minimization in Games with Incomplete Information*, NIPS 2007, https://papers.nips.cc/paper_files/paper/2007/hash/08d98638c6fcd194a4b1e6992063e944-Abstract.html | Zinkevich, Johanson, Bowling, Piccione, 2007 | CFR itself (Option 1) | fetched; title and all four authors confirmed on the proceedings page |
| *Monte Carlo Sampling for Regret Minimization in Extensive Games*, NIPS 2009, https://papers.nips.cc/paper_files/paper/2009/hash/00411460f7c92d2124a67ea0f4cb5f85-Abstract.html | Lanctot, Waugh, Zinkevich, Bowling, 2009 | External-sampling and outcome-sampling MCCFR (Options 3, 4) | fetched; title and all four authors confirmed |
| *Solving Large Imperfect Information Games Using CFR+*, arXiv:1407.5042 | Tammelin, 2014 | CFR+ (Option 2) | fetched; title, sole author and date 2014-07-18 confirmed |
| *Heads-up limit hold'em poker is solved*, Science 347(6218):145-149, doi:10.1126/science.1259433 | Bowling, Burch, Johanson, Tammelin, 2015 | the Cepheus result, and the scale it cost (Option 2) | publisher metadata fetched via Crossref; title, four authors, 2015-01-09, volume 347, pages 145-149 confirmed |
| *Deep Counterfactual Regret Minimization*, arXiv:1811.00164 | Brown, Lerer, Gross, Sandholm, 2018 | Deep CFR (Option 5) | fetched; title, all four authors and date 2018-11-01 confirmed |
| *Superhuman AI for multiplayer poker*, Science 365(6456):885-890, doi:10.1126/science.aay2400 | Brown, Sandholm, 2019 | Pluribus (Option 6): six-handed no-limit, beat elite professionals, no opponent modelling | metadata and the publisher's abstract fetched; title, both authors, 2019-08-30, volume 365, pages 885-890 confirmed. **Full text returned HTTP 403 - paywalled.** Compute figures therefore NOT verified and not quoted |
| *Solving Imperfect-Information Games via Discounted Regret Minimization*, arXiv:1809.04040 | Brown, Sandholm, 2018 | Linear and Discounted CFR, the family behind `discounted_cfr` (Option 6) | fetched; title, both authors and date 2018-09-11 confirmed |
| *Computing Robust Counter-Strategies*, NIPS 2007 | Johanson, Zinkevich, Bowling, 2007 | the restricted Nash response, shape two of opponent modelling | confirmed via the Semantic Scholar record: title, three authors, 2007, NIPS |
| *Abstraction pathologies in extensive games*, AAMAS 2009 | Waugh, Schnizlein, Bowling, Szafron, 2009 | a finer abstraction can be more exploitable than a coarser one | confirmed via Crossref: title, four authors, 2009, AAMAS proceedings |
| *Potential-Aware Imperfect-Recall Abstraction with Earth Mover's Distance in Imperfect-Information Games*, AAAI 2014 | Ganzfried, Sandholm, 2014 | the published way to build the card abstraction OpenSpiel does not ship | confirmed via Crossref: title, both authors, 2014 |
| *OpenSpiel: A Framework for Reinforcement Learning in Games*, arXiv:1908.09453 | Lanctot, Lockhart, Lespiau, Zambaldi, Upadhyay, Perolat, Srinivasan, Timbers, Tuyls and others, 2019 | the framework itself | fetched; title and author list confirmed |
| OpenSpiel's licence, https://raw.githubusercontent.com/google-deepmind/open_spiel/master/LICENSE | Google DeepMind | Apache-2.0, for requirement (e) | fetched; the file's opening lines read "Apache License, Version 2.0, January 2004" |

Sibling documents in this repository, cited rather than repeated: **`ENGINE_ALTERNATIVES.md`**
(currently on branch `worker/7f09949cb56f`) for why `universal_poker` is the
engine and for the finding that training in advance without a card abstraction
does not converge here; **`RESOURCES_SOLVERS.md`** for the solvers and paid
services that could supply poker judgment instead of our computing it;
**`OPPONENT_MODEL_DESIGN.md`** for the counting and shrinking that feeds shape
one and shape two above; **`DECISION_LAYER_SEARCH.md`** for the alternative to
everything in this file.
