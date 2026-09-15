# Opponent modelling design

How the bot learns what each human at the table does wrong, and changes its own
play to take money off that specific person.

This is a design document, not code. It is written so that a later coding task
can implement it without re-deciding anything. It deliberately makes no
assumptions about the internals of the vendored engine; a separate task is
assessing those. Everywhere the design needs something from the engine, it says
so as a named requirement in [Engine requirements](#engine-requirements).

---

## In plain words, before the jargon

A poker bot that plays the same way against everybody leaves money on the table.
Real people at a real table have habits. One person calls far too often and
never raises. Another raises constantly. Another folds the moment anyone bets
back at them. Each habit has a counter, and the counters are different.

So the bot keeps a small scorecard on every person it plays against. The
scorecard is just counters: how many hands has this person been dealt, how many
did they put money into, how many did they raise, how often did they give up
when bet at. After every hand the bot updates the scorecards. Once a scorecard
has enough hands behind it to be trustworthy, the bot sorts that person into one
of a small number of categories and switches to a playing style built in advance
to beat that category.

Two things make this harder than it sounds.

The first is that a small scorecard lies. If someone has played four hands and
raised two of them, they are not "a 50% raiser" — you have four hands of
evidence, which is nothing. The design handles this by blending every
measurement toward a default until enough evidence accumulates, so the bot
drifts from "treat them as average" to "treat them as themselves" gradually
rather than lurching. The technical name for that blending is *shrinkage toward
a prior*, and the published poker research does exactly this (see
[Sources](#sources)).

The second is that there are three or more players, not two. With one opponent,
bluffing works if that one person folds enough. With four opponents, *all four*
have to fold, and the odds of that collapse fast — the arithmetic is in
[Table B](#table-b-the-multiway-problem). This is why the plan leans on getting
paid with good hands rather than on bluffing.

One rule constrains everything below. `CLAUDE.md` in this repository forbids any
AI-written code from deciding a poker action, evaluating a hand, or reading a
board. Nothing in this design breaks that. Everything the opponent model hands to
the bot in play is one of three things: **numbers describing what an opponent
does**, **summaries of those numbers across the whole observed
population** — a baseline to shrink toward, a
threshold to classify against, an archetype for the engine to solve against — and
**a choice of which engine-produced strategy to load**. It never combines the
numbers of the opponents in the current hand into anything that moves the bot's
own action; that is the engine's job. The engine keeps every piece of poker
judgment. `CLAUDE.md` states exactly where the line falls, in its own two-column
table under "The forefront rule";
[The forefront rule and this design](#the-forefront-rule-and-this-design) below
points at that table and this design obeys it.

---

## Contents

1. [Goal and non-goals](#1-goal-and-non-goals)
2. [Part 1 — What to track per opponent](#2-part-1--what-to-track-per-opponent)
3. [Part 2 — What real bots did, and what is replicable solo](#3-part-2--what-real-bots-did-and-what-is-replicable-solo)
4. [Part 3 — The concrete plan](#4-part-3--the-concrete-plan)
5. [Safety: how this loses money if done carelessly](#5-safety-how-this-loses-money-if-done-carelessly)
6. [Validation before it touches a real table](#6-validation-before-it-touches-a-real-table)
7. [Engine requirements](#engine-requirements)
8. [Questions for the operator](#7-questions-for-the-operator)
9. [Sources](#sources)
10. [Provenance of every number in this document](#provenance-of-every-number-in-this-document)

---

## 1. Goal and non-goals

**Goal.** Beat the specific humans at the table, measured in big blinds won per
100 hands, at a table of three or more players.

**Why not chase game-theory-optimal play.** In two-player zero-sum poker, a Nash
equilibrium strategy is unbeatable in expectation regardless of what the
opponent does; that guarantee is what makes "solve the game" a sensible goal.
That guarantee does not survive the jump to three or more players. Brown's
thesis states the problem directly: for multiplayer games computing a Nash
equilibrium is PPAD-complete, and "even if a Nash equilibrium could be computed
efficiently in a game with more than two players, it is not clear that playing
such an equilibrium strategy would be wise. If each player in such a game
independently computes and plays a Nash equilibrium, the joint strategy that
they play (one strategy per player) may not be a Nash equilibrium and players
might have an incentive to deviate" ([Brown 2020](#s-brown2020), §6.6). The
Pluribus authors resolved this by abandoning the solution concept entirely: "we
took the viewpoint that our goal should not be a specific game-theoretic
solution concept, but rather to create an AI that empirically consistently
defeats human opponents" (ibid.). This project takes the same position, which is
already what `CLAUDE.md` says.

**Non-goals.**

- Not a solver. The blueprint strategy comes from the vendored engine.
- Not a hand-strength estimator. That is the engine's job and the forefront rule
  forbids replacing it.
- Not collusion or multi-account play.
- Not a real-time deep-learning opponent predictor. See
  [what is not replicable](#33-what-is-not-realistic-solo-in-a-few-weeks).

### The forefront rule and this design

`CLAUDE.md` forbids AI-written code from deciding a poker action, evaluating a
hand, or reading a board. **The exact boundary for opponent modelling lives in
`CLAUDE.md`, under "The forefront rule", as a two-column table.** That table is
the authority; this document only has to obey it. Both of its columns are
reproduced here **verbatim**, item for item, so that this summary can be checked
against the authority by inspection rather than trusted:

- **Allowed to AI-written opponent-model code:** Counting observed actions;
  Computing a single rate from its own counts; Shrinking a rate toward a
  baseline; Sorting an opponent into a bucket; Selecting *which* engine strategy
  to load; Substituting an opponent model into the engine's own solver;
  Reporting several rates side by side.
- **Reserved to the engine:** Evaluating hand strength; Choosing an action;
  Assigning a range to an opponent; Reading board texture; Producing the strategy
  itself; Solving; Combining live-field rates into a quantity that drives a poker
  decision — multiplying the fold rates of the opponents in the current hand to
  gate a bluff, for one.

**Live field versus observed population.** That last reserved item turns on a
distinction `CLAUDE.md` states in the two bullets directly beneath its table, and
this design leans on it everywhere, so it is worth restating in full. Combining
rates across the **live field** — the opponents in the current hand — into
anything that adjusts the bot's own action is reserved to the engine. Combining
rates across the **observed population** — the whole database, seated players'
stored rows included, with being seated never the criterion for inclusion — into
a baseline, a classification split, or an archetype handed to the engine is
allowed AI-written work, because the engine still chooses the action.

"The whole database" is meant literally, and the ambiguity is worth killing
outright, because it is the one that would otherwise be read the wrong way.
Pooling across the observed population does **not** mean the database with the
currently seated players held out. Their stored rows are in the pool like anyone
else's. What makes the pool population-level is that nobody is selected *for*
being at the table: the pool is every opponent meeting the stored-hands
threshold, and seating neither adds an opponent to it nor removes one. Filtering
the pool down to the players in the current hand is the reserved live-field
combination; leaving them in it is not.

**Every rate combination this design puts on the live decision path — anything
computed while a hand is in progress, or loaded into play from something that
was — is on the allowed side, and each one says which side it is on at its own
point of use.** Combinations *across* opponents, all of them population-level and
computed from the stored database rather than from the players in the current
hand: the pooled `BASELINE`
([§4.3](#43-after-each-hand-the-update)); the population-median split thresholds
([§4.4](#44-bucketing-an-opponent)); the pooled archetype fed to the solver
([§4.5](#45-tiers-what-to-build-in-what-order)); the pooled opportunity rates
that replace the placeholders in
[Table C](#table-c-how-many-hands-each-stat-needs); and the pooled rate V3 scores
the model against ([§6](#6-validation-before-it-touches-a-real-table)).
Combinations *within* one opponent: `AF` ([§4.2](#42-the-stat-table)) and
`vpip_pfr_gap` ([§2.3](#23-the-stat-set)), both of which combine that one
opponent's own counts and are reported as diagnostics without ever being an input
to a poker decision the bot acts on. The only place *on the live decision path*
where the *live field* is looked at collectively is choosing which precomputed
strategy to load ([§4.5](#45-tiers-what-to-build-in-what-order)), which counts
already-assigned buckets rather than combining rates, and whose whole output is a
strategy handle — the "Selecting *which* engine strategy to load" row above.

**Away from the decision path this design also combines rates offline, over
logged hands, and those combinations are not enumerated above because none of
them is computed at the table.** They are: V4's mean fold-rate-versus-VPIP gap
and its two disagreement rates, both taken across the whole logged population
([§6](#6-validation-before-it-touches-a-real-table)); the upgrade path's
expectation-maximisation clustering over the stored population's profile vectors
([§4.4](#44-bucketing-an-opponent)); and the realised win rate pooled per bucket
and per flag, together with the per-opponent profit tracking, in
[§5.2](#52-mitigations-each-traceable-to-a-source) and
[§5.3](#53-the-one-risk-the-literature-does-not-cover). Two of them also read the
live field collectively, again offline and descriptively: V5's bluff frequency
broken down by the number of live opponents, and the "Multiway gate" column of
[§4.6](#46-what-each-bucket-means-in-plain-strategic-terms), which describes
which field sizes an exploit survives. What any of these can change is a config
value, a switched-off exploit, or a red flag raised between sessions — reviewed
by a person, never a quantity a module computes while a hand is live.

**The test a coding task should apply to any new line of opponent-model code:**
if a quantity is built by reading the rates of more than one of *the opponents in
the current hand* — the live field as such — and anything downstream of it
changes what the bot does, it belongs in the engine, not in this codebase. What
decides the test is how the opponents were selected, not who they turn out to
be: a quantity pooled over the stored database passes even though, after the
first session, some of those stored rows belong to people sitting at the table
right now, because being seated is never what put them in the pool. A quantity
whose inputs were chosen *because* those opponents are in the hand fails. The one
live-field read still allowed on the decision path is the strategy-selection rule
in [§4.5](#45-tiers-what-to-build-in-what-order): it counts bucket labels
assigned to opponents one at a time, performs no arithmetic on rates, and can
only pick among strategies the engine itself produced.

Every counter-strategy in this design is **produced by the engine**, by solving
against a modified opponent, never by a human or an AI writing "against a
calling station, bet more." Tier 1 in [§4.5](#45-tiers-what-to-build-in-what-order)
is the only place that boundary comes under any strain, and it is handled there
explicitly.

---

## 2. Part 1 — What to track per opponent

### 2.1 Design constraints that decide the stat list

**Hole cards are almost never observed.** Teofilo and Reis mined a corpus of
real-money **tournament** logs — 51,377,820 games across 158,035 players —
and report 2,323,538 showdowns, a showdown ratio of 4.52%
([Teofilo & Reis 2011](#s-teofilo2011), Table 1). Showdown frequency can differ
between tournament and cash play, so treat 4.52% as an order of magnitude rather
than a cash-game constant; the conclusion survives either way. Roughly nineteen
hands in twenty end without anyone's cards being revealed. **Consequence: every
primary statistic must be computable from observed *actions* alone.**
Showdown-revealed holdings are a bonus signal, not a foundation. Any design that needs to know
what the opponent held will starve.

**Everything is a pair of counters.** Store `(numerator, denominator)`, never a
rate. The denominator is an *opportunity count* and its definition is the whole
game: "fold to 3-bet" means folds divided by *times faced a 3-bet after opening*,
not divided by hands dealt. Two implementations that disagree about the
opportunity definition produce numbers that cannot be compared. Every stat below
gets an explicit opportunity definition in [§4.2](#42-the-stat-table).

**Cheapness is measured in opportunities per hand, not in CPU.** All of these
are integer increments; none costs anything to compute. What they cost is
*hands*, because a stat with few opportunities per hand takes many hands to
become trustworthy. [Table C](#table-c-how-many-hands-each-stat-needs) quantifies
this, and it is the single most important table for setting expectations.

### 2.2 The two axes that have literature behind them

The classic poker taxonomy splits players on two axes: **tight versus loose**
(how many hands they play) and **passive versus aggressive** (whether they bet
and raise or call and check). This is not folklore invented for this document;
it traces to Sklansky's strategy writing and was formalised numerically in
Billings' PhD thesis, which classifies a player by the percentage of hands they
fold together with an **aggression factor**

```
AF = (number of bets + number of raises) / (number of calls)
```

with the thresholds: **a player who folds 72% or more of hands is tight,
otherwise loose; a player with AF above 1 is aggressive, otherwise passive**
([Teofilo & Reis 2011](#s-teofilo2011), §3, citing
[Billings 2006](#s-billings2006) and [Sklansky](#s-sklansky)). Folding ≥72% of
hands is *approximately* the complement of voluntarily putting money in with
≤28% of them, the quantity the tracking-software world calls VPIP — but the two
rates do **not** sum to exactly 1. Some hands end in neither a fold nor a
voluntary investment; the common case is a big blind who checks their option
when nobody raised, which is not a fold and not a VPIP action either (see
[§4.7](#47-edge-cases-a-coding-task-will-hit)). Under the reading that "folds a
hand" means the player put in no voluntary money and folded, those hands fall
outside both counts, so `fold_rate + vpip < 1` and the VPIP value that truly
corresponds to a 72% fold rate would sit *below* 0.28 by the share of such
hands; using 0.28 anyway would then put the tight/loose split slightly too high
and call some borderline players tight when the literature threshold would call
them loose.

That is one of two readings, not an established fact. The other — the corpus
counting a fold at any street — reverses the sign, because then a player who
calls preflop and folds the flop is counted in *both* rates and the two can sum
above 1. The source does not say which it used, so **the size and even the
direction of the gap are things to measure, not to assume**.
[V4](#6-validation-before-it-touches-a-real-table) measures both on logged hands
before the split is trusted.

Two cautions about AF, both statistical rather than poker-specific:

- **AF is unbounded and undefined at zero calls.** A player who has raised three
  times and never called has AF = ∞. Store the counters and compute an
  *aggression frequency* instead for anything the bot acts on:
  `AFq = (bets + raises) / (bets + raises + calls + folds)`, which is a
  proportion in [0,1] and therefore admits a confidence interval and shrinkage.
  Keep AF as a reported diagnostic because it is what the literature threshold
  is stated in; act on AFq.
- **Aggression is street-dependent.** A player can be aggressive preflop and
  passive on the river. Track AFq per street as well as overall.

### 2.3 The stat set

Grouped by how fast each becomes trustworthy. The "opportunities per hand"
column is what drives that; see [Table C](#table-c-how-many-hands-each-stat-needs).

**Tier A — one opportunity per hand dealt. Usable soonest.**

| Stat | What it measures | Why it is worth tracking |
| --- | --- | --- |
| `hands_dealt` | Denominator for everything | Confidence weight depends on it |
| `vpip` | Voluntarily put money in pot | The tight/loose axis; literature threshold at 28% |
| `pfr` | Preflop raise | Separates aggressive-loose from passive-loose |
| `vpip_pfr_gap` | `vpip − pfr` | Passive callers show a wide gap; the derived "limps a lot" signal. It combines two rates, so — exactly like `AF` in [§4.2](#42-the-stat-table) — it is *reported* as a diagnostic **without ever being used as an input to a poker decision the bot acts on**; it is one opponent's own two rates, never a live-field combination |
| `limp` | Called the big blind unraised, first in | Strongly recreational; Pluribus's self-play discarded limping as suboptimal for everyone but the small blind ([Brown 2020](#s-brown2020), §6.6) |
| `open_raise_by_seat` | PFR split by early / middle / late / blinds | Position-blind opponents are the exploitable ones |

**Tier B — a few opportunities per ten hands. Usable after a session or two.**

| Stat | Opportunity | Why |
| --- | --- | --- |
| `three_bet` | Faced an open raise with the option to reraise | Detects the passive player who never reraises |
| `fold_to_three_bet` | Opened, then faced a reraise | The single most directly exploitable preflop leak |
| `fold_to_steal` | In the blinds facing a late-position open | Blind defence is where recreational players leak most |
| `cbet_flop` | Was the preflop aggressor and saw a flop | Auto-cbet tendency |
| `fold_to_cbet_flop` | Faced a flop continuation bet | Detects both extremes |
| `afq_flop` / `afq_turn` / `afq_river` | Any voluntary postflop action on that street | The aggression axis, per street |
| `check_raise` | Checked, then faced a bet, on any street | Rare; a player who never check-raises can be bet into freely |

**Tier C — slow but high-value. Needs a thousand hands or more.**

| Stat | Opportunity | Why |
| --- | --- | --- |
| `wtsd` | Saw a flop | Went to showdown: the "how sticky are they" number |
| `wsd` | Reached showdown | Won money at showdown: separates sticky-and-bad from sticky-and-strong |
| `fold_to_river_bet` | Faced a river bet | The most directly monetisable overfold when present |
| `showdown_holdings` | Reached showdown | Actual cards, at a ~4.5% rate — corroboration only |

**Tier D — bookkeeping, not behaviour.**

| Field | Use |
| --- | --- |
| `stack_bb` | Short stacks change correct play regardless of tendency |
| `hands_since_last_seen` | Drives the decay in [§4.3](#43-after-each-hand-the-update) |
| `session_net_bb` | Reserved for a tilt signal; **not acted on** — see [§7](#7-questions-for-the-operator) |

### 2.4 Why bluffing is the wrong primary exploit at a multiway table

The arithmetic that governs bluff profitability is the same in every poker book
and is worth deriving rather than citing, because the derivation is three lines
and the conclusion decides the whole strategy.

Bet `B` into a pot of `P`. A bluff with no chance of winning at showdown breaks
even when the opponent folds with probability `B / (P + B)`. So the defender, to
stop a pure bluff from being free money, must continue with at least
`P / (P + B)` of their range — the **minimum defence frequency**. Symmetrically,
for a caller to be indifferent, the bettor's range must contain a bluff fraction
of `B / (P + 2B)`.

#### Table A: bet size, fold frequency, and bluff share

Bet size `s` is the bet as a fraction of the pot. Computed 2026-09-15.

| Bet size `s` | Fold frequency that makes a pure bluff break even | Minimum defence frequency | Bluff share of a balanced betting range |
| --- | --- | --- | --- |
| 0.25 | 20.0% | 80.0% | 16.7% |
| 0.33 | 24.8% | 75.2% | 19.9% |
| 0.50 | 33.3% | 66.7% | 25.0% |
| 0.66 | 39.8% | 60.2% | 28.4% |
| 0.75 | 42.9% | 57.1% | 30.0% |
| 1.00 | 50.0% | 50.0% | 33.3% |
| 1.50 | 60.0% | 40.0% | 37.5% |
| 2.00 | 66.7% | 33.3% | 40.0% |

#### Table B: the multiway problem

A bluff only wins if **every** live opponent folds. If each folds independently
with probability `p`, the bluff succeeds with probability `p^n`. Computed
2026-09-15.

| Per-opponent fold rate | 1 opponent | 2 opponents | 3 opponents | 4 opponents | 5 opponents |
| --- | --- | --- | --- | --- | --- |
| 50% | 50.0% | 25.0% | 12.5% | 6.2% | 3.1% |
| 60% | 60.0% | 36.0% | 21.6% | 13.0% | 7.8% |
| 70% | 70.0% | 49.0% | 34.3% | 24.0% | 16.8% |
| 80% | 80.0% | 64.0% | 51.2% | 41.0% | 32.8% |
| 90% | 90.0% | 81.0% | 72.9% | 65.6% | 59.0% |

Independence is an approximation — the players' ranges are correlated through
the board — but the direction of the effect is not in doubt.

Reading Table A against Table B: a pot-sized bluff needs 50% fold-through. With
three opponents that requires each of them to fold 79% of the time
(`0.5^(1/3) ≈ 0.794`). Against typical opponents that does not happen.

**Three design consequences, and they shape everything in Part 3.**

1. **The primary multiway exploit is value, not bluff.** Against loose-passive
   opponents the money comes from betting good hands more often and larger, not
   from bluffing more.
2. **Bluffing exploits are conditional on the whole live field, never on one
   opponent.** The bucket of the *one* player you want to fold is irrelevant if
   three others are still in. State this carefully, because the forefront rule
   is next to it: the fold-rate product is **a property the engine-produced
   strategy must exhibit, not a calculation for AI-written code to do at the
   table**. No module outside the engine may multiply the live field's fold
   rates together and adjust a bluff frequency by the result; that is deciding a
   poker action, and `CLAUDE.md` forbids it — it is the exact case named in the
   reserved column, and the live-field side of the line summarised in
   [§1](#the-forefront-rule-and-this-design). The multiway discount arrives
   instead through the engine: Tier 1 solves each counter-strategy offline
   against a full table of population-derived archetype opponents
   ([§4.5](#45-tiers-what-to-build-in-what-order)), so the effect is already
   inside its output. What this design owes is a check that it is
   there — see [V5](#6-validation-before-it-touches-a-real-table), which reports
   bluff frequency against the number of live opponents. **This paragraph is
   descriptive, not prescriptive**, on the same footing as
   [§4.6](#46-what-each-bucket-means-in-plain-strategic-terms): if the engine's
   output disagrees with it, the engine is right and this paragraph is wrong.
3. **Preflop is where single-opponent exploits are cleanest,** because preflop
   is where the field is smallest and where `fold_to_three_bet` and
   `fold_to_steal` describe a one-on-one interaction.

---

## 3. Part 2 — What real bots did, and what is replicable solo

### 3.1 Pluribus did not do opponent modelling at all

This is the most important finding for scoping, and it cuts against the
project's instinct.

Pluribus is the only program to have beaten elite human professionals at
six-player no-limit hold'em. It contains **no opponent model**. Brown's thesis
states it flatly: "Pluribus does not adapt its strategy to its opponents and
does not know the identity of its opponents" ([Brown 2020](#s-brown2020), §6.6).
Its architecture is a blueprint strategy trained offline by Linear Monte Carlo
Counterfactual Regret Minimisation from self-play, improved at the table by
depth-limited search. Libratus's self-improvement module — which used the
humans' play to find holes in *its own* strategy rather than in theirs — was not
even used in Pluribus.

The earlier Libratus work makes the reasoning explicit: "The way machine
learning has typically been used in game playing is to try to build an opponent
model, find mistakes in the opponent's strategy, and exploit those mistakes. The
downside is that trying to exploit the opponent opens oneself to being exploited.
Therefore, Libratus generally did not do opponent exploitation" (ibid., §6.4).

Results, for calibration: against five elite professionals over 10,000 hands,
Pluribus won 48 mbb/game with a standard error of 25 mbb/game (p = 0.028). In
the reverse format, one human against five copies of Pluribus over 10,000 hands
total, it won 32 mbb/game, standard error 15 (p = 0.014). The blueprint took 8
days on a 64-core server — 12,400 CPU core-hours, under 512 GB of memory, about
$144 at 2019 cloud spot rates — and real-time search ran on a 28-core CPU with
under 128 GB (ibid.).

**What this means for this project.** Pluribus's opponents were elite
professionals with few exploitable habits. This project's opponents are, by the
stated goal, *real humans* at whatever table the bot sits at — a population with
far larger and more consistent leaks. Opponent modelling is worth far more
against weak opponents than against strong ones, which is exactly what the
opponent-modelling literature finds ([§3.2](#32-the-opponent-modelling-line-and-what-it-actually-showed)).
But two things follow regardless:

- **The blueprint is the load-bearing component; the opponent model is a
  multiplier on it.** A strong blueprint with no opponent model beat
  professionals. A weak blueprint with a clever opponent model beats nobody.
  Budget accordingly: if the blueprint is not yet solid, work on the blueprint.
- **Exploitation is a downside risk, not free money.** Every deviation from the
  blueprint is a deliberate increase in the bot's own exploitability, taken in
  exchange for expected gain. [§5](#5-safety-how-this-loses-money-if-done-carelessly)
  is not optional.

### 3.2 The opponent-modelling line, and what it actually showed

Four published approaches matter here, in increasing order of how well they fit
a solo few-week build.

**Poki / Loki (Alberta, late 1990s–2000s).** The first serious opponent
modelling in poker: per-opponent frequency counts of fold/call/raise in context,
plus a learned predictor of the opponent's next action, feeding a hand-range
estimate. The lineage is acknowledged throughout the later literature
([Billings et al.](#s-billings1998); [Billings 2006](#s-billings2006)). The idea
this project takes from it is the cheapest one: **contextual action frequencies
are the substrate**, and everything else is built on them.

**Bayes' Bluff ([Southey et al. 2005](#s-southey2005)).** A fully Bayesian
treatment: put a prior over opponent strategies, update it to a posterior from
observed play, and play a response to the posterior rather than to a point
estimate. Demonstrated with **Dirichlet priors** on a reduced poker game and a
more informed prior on full Texas hold'em. The idea this project takes:
**represent uncertainty explicitly, and respond to the distribution, not to the
maximum-likelihood guess.** The full machinery is too heavy; the Dirichlet
shrinkage is not, and is adopted directly in [§4.3](#43-after-each-hand-the-update).

**Restricted Nash Response and Data Biased Response (Johanson, Zinkevich &
Bowling; Johanson & Bowling).** RNR computes a counter-strategy that "can take
advantage of a suspected tendency in the decisions of the other agents, while
bounding the worst-case performance when the tendency is not observed"
([Johanson et al. 2007](#s-johanson2007)). DBR fixes RNR's weakness with limited
data ([Johanson & Bowling 2009](#s-johanson2009)). The mechanism is a
**confidence function** `Pconf(I)` at each information set `I`: the modified game
forces the opponent to play the observed model with probability `Pconf(I)` and
lets them play freely with probability `1 − Pconf(I)`. A parameter
`Pmax ∈ [0,1]` caps confidence globally and "allows us to set a tradeoff between"
exploitation and exploitability. Of the four confidence functions they tested,
the useful ones for this project are:

- **0-10 Linear**: `Pconf(I) = Pmax` if `n_I > 10`, else `n_I · Pmax / 10`.
- **s-Curve**: `Pconf(I) = Pmax · n_I / (s + n_I)` for a constant `s`, which
  they note has a Bayesian interpretation.

Their results: the naive **1-Step** function (any confidence after a single
observation) **overfits the model**, while 10-Step, 0-10 Linear and 1-Curve do
not; and the 0-10 Linear counter-strategies "are effective with any quantity of
training data", tested down to 100 observed games (ibid., §6 and Figure 2). That
last point is the licence for this project to exploit on small samples at all —
but only with the shrinkage in place.

**Deviation-Based Best Response, DBBR ([Ganzfried & Sandholm 2011](#s-ganzfried2011)).**
The closest published thing to what this project should build. It "works by
observing the opponent's action frequencies and building an opponent model by
combining information from a precomputed equilibrium strategy with the
observations. It then computes and plays a best response to this opponent
model." The core is one equation. Where `c_{n,a}` is the observed count of the
opponent taking action `a` at public history set `n`, and `p*_{n,a}` is the
probability the baseline strategy `σ*` takes that action:

```
α_{n,a} = (p*_{n,a} · N_prior + c_{n,a}) / (N_prior + Σ_a' c_{n,a'})
```

That is a Dirichlet posterior with the baseline strategy as the prior mean and
`N_prior` as the prior strength. Their reasoning for the parameter is worth
copying verbatim: "we wanted to choose a small number so that our observations
would quickly trump the prior for common public history sets, but so that the
prior would have more weight if we had just one or two observations. Note that
setting `N_prior = 5` means that our prior and our observations will have equal
weight in our model when we have observed the opponent's action 5 times."

Their remaining design choices: play the baseline for the first `T = 1000` hands
before exploiting at all, and rebuild the model every `k = 50` hands. And they
add the operational rule this project should adopt as policy: "Against stronger
opponents one might prefer to always play the precomputed equilibrium rather
than turning on the exploitation. This can be accomplished by periodically
looking at the win rate, and only attempting to exploit the opponent if a win
rate above some threshold is attained."

### 3.3 What is not realistic solo in a few weeks

Named explicitly so a later task does not try.

| Not doing | Why |
| --- | --- |
| Training a bespoke blueprint per opponent bucket from scratch at Pluribus scale | 12,400 CPU core-hours *per strategy* ([Brown 2020](#s-brown2020), §6.6). A four-bucket design would be four of those. |
| Full DBBR with per-information-set best-response computation in real time | Ganzfried and Sandholm could not run it against their own competition-grade abstraction: "GS5 was too large to use as the approximate-equilibrium strategy in our real-time opponent modeling updates", forcing a separate, much coarser abstraction (branching factors 8/12/4/4 instead of 15/40/6/6) purely to make it fast enough. Reproducing that trade-off is a project in itself. |
| RNR/DBR counter-strategies computed by solving a modified game | Requires modifying the solver's game definition. Possible in principle; gated entirely on what the engine exposes. See [Engine requirements](#engine-requirements). |
| A neural opponent-action predictor | No training data until the bot has played. The classic chicken-and-egg. Revisit after the bot has its own hand database. |
| Multiway equilibrium guarantees of any kind | Do not exist. See [§1](#1-goal-and-non-goals). |
| Tilt / emotional-state modelling | No published grounding found. Filed as an open question, [§7](#7-questions-for-the-operator). |

### 3.4 What *is* realistic, and is what Part 3 specifies

1. Counting contextual action frequencies per opponent. Trivial.
2. Dirichlet shrinkage of every rate toward a baseline, with a confidence
   function. Twenty lines of code, and it is the exact published mechanism from
   both DBBR and DBR.
3. Sorting opponents into a handful of buckets on the two literature axes, with
   the boundaries in [§2.2](#22-the-two-axes-that-have-literature-behind-them).
4. Selecting among a **small, fixed set of engine-produced strategies**, one per
   bucket, precomputed offline. This is RNR/DBR's structure with the expensive
   part moved offline and the number of counter-strategies cut to single digits.
5. Tracking realised profit per bucket and per exploit, and switching
   exploitation off when it is not earning.

---

## 4. Part 3 — The concrete plan

### 4.1 Architecture and module boundaries

```
  table state (from the capture layer, existing or planned)
        |
        v
  +----------------------+
  | hand_recorder        |  writes one immutable HandRecord per hand
  +----------------------+
        |
        v
  +----------------------+
  | stat_store           |  SQLite; counters only, no rates
  +----------------------+
        |
        v
  +----------------------+
  | profiler             |  shrinks counters -> rates + confidences
  +----------------------+
        |
        v
  +----------------------+
  | classifier           |  rates -> bucket + exploit flags
  +----------------------+
        |
        v
  +----------------------+
  | strategy_selector    |  bucket(s) -> which engine strategy to load
  +----------------------+
        |
        v
  +----------------------+
  | ENGINE  (vendored)   |  all poker judgment lives here
  +----------------------+
```

Suggested layout under `pokerbot/opponent/`:

| File | Responsibility |
| --- | --- |
| `records.py` | `HandRecord`, `ActionRecord` dataclasses; no logic |
| `store.py` | SQLite schema, open/migrate, read/write counters |
| `counters.py` | The single function that turns a `HandRecord` into counter increments |
| `profile.py` | Shrinkage, confidence, decay; produces an `OpponentProfile` |
| `classify.py` | `OpponentProfile` -> `Bucket` + `ExploitFlags` |
| `select.py` | Bucket(s) + table context -> engine strategy handle |
| `report.py` | Human-readable dump of a profile, for the operator |

`select.py` is the only module that touches the engine. `classify.py` and below
have no engine dependency at all and are therefore unit-testable without it.

Every module down to `classify.py` runs **one opponent at a time**; the only
rates any of them pools across opponents are the population-level ones in
[§4.3](#43-after-each-hand-the-update) and
[§4.4](#44-bucketing-an-opponent), read from stored history. `select.py` is the
only module that looks at the live field as a whole, and it does that by counting
bucket labels ([§4.5](#45-tiers-what-to-build-in-what-order)), never by combining
live opponents' rates — the line drawn in
[§1](#the-forefront-rule-and-this-design).

### 4.2 The stat table

Schema. One row per opponent identity; counters are integers.

```sql
CREATE TABLE opponent (
    opponent_id      TEXT PRIMARY KEY,   -- stable table alias / screen name
    first_seen_utc   TEXT NOT NULL,
    last_seen_utc    TEXT NOT NULL,
    hands_dealt      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE stat (
    opponent_id      TEXT NOT NULL REFERENCES opponent(opponent_id),
    stat_name        TEXT NOT NULL,
    context          TEXT NOT NULL DEFAULT '',  -- e.g. seat bucket, street
    numerator        REAL NOT NULL DEFAULT 0,   -- REAL because decay is fractional
    denominator      REAL NOT NULL DEFAULT 0,
    last_update_hand INTEGER NOT NULL,
    PRIMARY KEY (opponent_id, stat_name, context)
);
```

`numerator` and `denominator` are `REAL` rather than `INTEGER` because the decay
in [§4.3](#43-after-each-hand-the-update) multiplies them by a factor below one.

Every stat, with its exact opportunity definition. **A coding task must
implement these definitions literally; ambiguity here silently corrupts every
downstream number.**

| `stat_name` | Numerator increments when… | Denominator increments when… | Context key |
| --- | --- | --- | --- |
| `vpip` | opponent voluntarily put chips in preflop (call or raise; a posted blind alone does not count) | opponent was dealt in | — |
| `pfr` | opponent raised preflop | opponent was dealt in | — |
| `limp` | opponent called exactly the big blind, first voluntary action, no prior raise | opponent was dealt in and had the option to limp | — |
| `open_raise` | opponent made the first raise preflop | opponent was first-in with no prior raiser | seat bucket: `EP`/`MP`/`LP`/`SB`/`BB` |
| `three_bet` | opponent reraised over an open | opponent faced exactly one open raise with chips behind | — |
| `fold_to_three_bet` | opponent folded | opponent had open-raised and then faced a reraise | — |
| `fold_to_steal` | opponent folded | opponent was in `SB` or `BB` facing a `LP` open with no other caller | — |
| `cbet` | opponent bet first on that street | opponent was last aggressor on the previous street and saw this street | street |
| `fold_to_cbet` | opponent folded | opponent faced a continuation bet on that street | street |
| `afq` | opponent bet or raised | opponent took any voluntary action (bet, raise, call, or fold) on that street | street |
| `af_bets_raises` | opponent bet or raised | *not used as a denominator* — paired with `af_calls` | street |
| `af_calls` | opponent called | *not used as a denominator* | street |
| `check_raise` | opponent checked then raised on that street | opponent checked and then faced a bet on that street | street |
| `wtsd` | opponent reached showdown | opponent saw a flop | — |
| `wsd` | opponent won chips at showdown | opponent reached showdown | — |
| `fold_to_river_bet` | opponent folded on the river | opponent faced a bet on the river | — |

`af_bets_raises` and `af_calls` exist so `AF` can be *reported* in the units the
literature threshold uses, without ever being used as an input to a poker
decision the bot acts on — see the caution in
[§2.2](#22-the-two-axes-that-have-literature-behind-them). The bot acting on
`AFq` instead does not stop `AF` being computed offline on logged hands:
[V4](#6-validation-before-it-touches-a-real-table) computes it on every logged
opponent and moves `AFQ_SPLIT` if the two disagree, which is calibration between
sessions, not a quantity read at the table.

#### Table C: how many hands each stat needs

The number of *opportunities* needed for a 95% confidence interval of half-width
`w` around an observed proportion `p̂` is `(1.96/w)² · p̂(1−p̂)`. Dividing by the
opportunities per hand gives hands. The `p̂` values below are illustrative
anchors chosen to show the shape of the requirement, **not claims about any
real population**; the width of the interval barely moves for `p̂` between 0.2
and 0.8. Computed 2026-09-15.

The **"Opportunities per hand" column is an illustrative estimate on the same
footing as `p̂`, not a sourced fact.** No published figure was found for how
often a real multiway table hands a given player these spots, and none is
invented here: 0.08, 0.15 and 0.30 are round order-of-magnitude placeholders for
"rare", "occasional" and "common". The "Hands needed" column inherits that
uncertainty and scales inversely with them — halve an opportunity rate and the
hands double. **Replace all three with measurement as soon as Tier 0 has logged
any hands**: each is exactly `denominator / hands_dealt` for that stat, pooled
across the observed population (not the live field, and not a behaviour rate at
all — it is how often the game hands somebody that spot). What survives the
uncertainty is the *ordering* — Tier A stats need hundreds of hands and postflop
stats need thousands — and that ordering is what the rest of this document leans
on.

| Stat | Anchor `p̂` (illustrative) | Opportunities per hand (illustrative) | Target width | Opportunities needed | **Hands needed** |
| --- | --- | --- | --- | --- | --- |
| `vpip` | 0.30 | 1.00 | ±5pp | 323 | **323** |
| `vpip` | 0.30 | 1.00 | ±3pp | 896 | **896** |
| `pfr` | 0.20 | 1.00 | ±5pp | 246 | **246** |
| `three_bet` | 0.07 | 1.00 | ±2pp | 625 | **625** |
| `fold_to_three_bet` | 0.60 | 0.08 | ±10pp | 92 | **1,152** |
| `fold_to_cbet` | 0.50 | 0.15 | ±10pp | 96 | **640** |
| `wtsd` | 0.25 | 0.30 | ±5pp | 288 | **960** |

**This table is the honest expectation-setter for the whole project.** VPIP and
PFR are usable inside one long session. Everything postflop needs many sessions
against the same person. A design that promises sharp postflop exploits after
fifty hands is promising noise.

Two consequences:

- **Preflop exploits ship first** and are the ones that will actually fire.
- **Fall back up the hierarchy.** When `fold_to_cbet` has too few observations,
  back off to the opponent's overall `afq`; when that is thin, back off to the
  bucket; when that is thin, play the blueprint. Implement this as an explicit
  chain, not as an accident of missing data.

### 4.3 After each hand: the update

Ordered, and each step is cheap.

**Step 1 — Record.** Write an immutable `HandRecord`: hand id, timestamp, table
id, button position, every player's seat and starting stack, the full ordered
action sequence per street with amounts, the board, and any revealed holdings.
Record the hand even if the bot folded preflop — *especially* then, because
those are the hands where the bot is a pure observer and the data is free.

**Step 2 — Decay.** For each opponent seen this hand, multiply their existing
`numerator` and `denominator` by `d = 0.5 ** (hands_elapsed / HALF_LIFE)`.

Default `HALF_LIFE = 2000` hands. This exists because humans change and the
published bots' opponents did not. Set `HALF_LIFE` high enough that it is
effectively off within one session and only matters across weeks; 2000 is a
starting value to be tuned against logged data, not a claim.

**Step 3 — Increment.** Apply the increments from the table in
[§4.2](#42-the-stat-table). This is a pure function of the `HandRecord`, which
makes it exhaustively testable against hand-history fixtures.

**Step 4 — Recompute profiles.** Not necessarily every hand. DBBR rebuilt every
`k = 50` hands ([Ganzfried & Sandholm 2011](#s-ganzfried2011)); for this design
the computation is a few divisions, so every hand is affordable. Recompute every
hand and keep the constant configurable.

For each stat, with raw counts `k` successes in `n` opportunities:

```python
BASELINE = {...}              # pooled across the observed population, never
                              # across the live field; see below
PRIOR_STRENGTH = {...}        # per-stat; the table below gives every value
s = PRIOR_STRENGTH[stat]      # one constant per stat, used for both lines

rate       = (BASELINE[stat] * s + k) / (s + n)
confidence = n / (n + s)
```

**There is deliberately no separate s-Curve constant.** The s-Curve's `s` *is*
`PRIOR_STRENGTH` for that stat, so a stat has exactly one tuning constant. The
consequence is that the sample size at which the data outweighs the prior and
the sample size at which `confidence` passes 0.5 are the same number by
construction — which is exactly what the "Prior and data carry equal weight at…"
column in the table below reports. A coding task must not introduce a second
constant here.

The `rate` line is DBBR's Equation 1 with `N_prior = PRIOR_STRENGTH[stat]`
([Ganzfried & Sandholm 2011](#s-ganzfried2011), §4.2). The `confidence` line is
DBR's s-Curve confidence function with `Pmax = 1` and `s = PRIOR_STRENGTH[stat]`
([Johanson & Bowling 2009](#s-johanson2009), §5.2). Neither is invented for this
document.

**Where `BASELINE` comes from — and this is a deliberate design choice.** It is
**not** a hardcoded population constant. It is the pooled rate across every
opponent in the bot's own database with at least `MIN_POOL_HANDS = 200` hands:
`BASELINE[stat] = Σ_opponents k / Σ_opponents n`. Rationale: population norms
differ by stake, table size, site, and era, and any constant written into this
document would be exactly the kind of invented number the design must avoid.
Until the pool has at least `MIN_POOL_OPPONENTS = 20` qualifying opponents, fall
back to the blueprint's own action frequency at the corresponding decision — the
same substitution DBBR makes, where the prior mean *is* the baseline strategy's
probability. `MIN_POOL_HANDS = 200` and `MIN_POOL_OPPONENTS = 20` are both
**unmeasured starting values chosen for this design**, belong in a config file,
and are to be raised if the pooled rates prove unstable.

**That Σ is population-level, not live-field, and that is what makes it
allowed.** It sums over every qualifying opponent in the database — people not at
the current table, and past sessions — and its output is a prior mean that a
single opponent's rate is shrunk toward. It is never a combination of the rates
of the opponents in the current hand, and it adjusts no action by itself; the
engine still chooses every action. This is the allowed side of the live-field
versus observed-population line in `CLAUDE.md`, summarised in
[§1](#the-forefront-rule-and-this-design). A coding task must compute it from
stored history only, and must never restrict the pool to the players currently
seated.

`PRIOR_STRENGTH` per stat — which is also the `s` in the `confidence` line
above — sized to the opportunity rate so that the crossover from "treat as
average" to "treat as themselves" lands at a sensible number of hands:

| Stat group | `PRIOR_STRENGTH` | Prior and data carry equal weight at… |
| --- | --- | --- |
| Tier A (`vpip`, `pfr`, `limp`) | 50 | 50 hands |
| Tier B (`three_bet`, `fold_to_*`, `cbet`, `afq`) | 25 | 25 opportunities |
| Tier C (`wtsd`, `wsd`, `fold_to_river_bet`) | 15 | 15 opportunities |

**All three `PRIOR_STRENGTH` values — 50, 25 and 15 — are unmeasured starting
values chosen for this design**, neither measured nor cited. They belong in a
config file and are to be tuned by the validation in
[§6](#6-validation-before-it-touches-a-real-table).

#### Table D: what the confidence weight looks like

`confidence = n / (n + s)`, where `s` is that stat's `PRIOR_STRENGTH`. The three
tier values from the table above are marked; `s`=5 and `s`=10 are included only
to show the shape. Computed 2026-09-15.

| observations `n` | `s`=5 | `s`=10 | `s`=15 (Tier C) | `s`=25 (Tier B) | `s`=50 (Tier A) |
| --- | --- | --- | --- | --- | --- |
| 1 | 0.17 | 0.09 | 0.06 | 0.04 | 0.02 |
| 2 | 0.29 | 0.17 | 0.12 | 0.07 | 0.04 |
| 5 | 0.50 | 0.33 | 0.25 | 0.17 | 0.09 |
| 10 | 0.67 | 0.50 | 0.40 | 0.29 | 0.17 |
| 25 | 0.83 | 0.71 | 0.63 | 0.50 | 0.33 |
| 50 | 0.91 | 0.83 | 0.77 | 0.67 | 0.50 |
| 100 | 0.95 | 0.91 | 0.87 | 0.80 | 0.67 |
| 250 | 0.98 | 0.96 | 0.94 | 0.91 | 0.83 |
| 500 | 0.99 | 0.98 | 0.97 | 0.95 | 0.91 |

#### Table E: shrinkage in practice

What the blend actually does to a loud small sample. Computed 2026-09-15.

| Baseline | Prior strength | Observed | Raw rate | **Shrunk rate** |
| --- | --- | --- | --- | --- |
| 0.25 | 25 | 10 of 20 | 0.50 | **0.361** |
| 0.25 | 25 | 30 of 40 | 0.75 | **0.558** |
| 0.60 | 25 | 18 of 20 | 0.90 | **0.733** |
| 0.60 | 25 | 2 of 20 | 0.10 | **0.378** |

Row 1 is the case that matters: somebody who has raised half of twenty hands is
recorded as a 36% raiser, not a 50% one. That is the mechanism that stops the
bot chasing noise.

### 4.4 Bucketing an opponent

**The grid.** Two axes, from [§2.2](#22-the-two-axes-that-have-literature-behind-them).

- **Looseness**: shrunk `vpip`, split at `VPIP_SPLIT`.
- **Aggression**: shrunk overall `afq`, split at `AFQ_SPLIT`.

| | Tight (`vpip ≤ split`) | Loose (`vpip > split`) |
| --- | --- | --- |
| **Passive** (`afq ≤ split`) | `ROCK` | `STATION` |
| **Aggressive** (`afq > split`) | `TAG` | `MANIAC` |

Plus `UNKNOWN`, assigned whenever `confidence(vpip) < 0.5` **or**
`hands_dealt < MIN_CLASSIFY_HANDS`. `UNKNOWN` always plays the blueprint.
Default `MIN_CLASSIFY_HANDS = 50`, which is the point where Tier A stats reach
equal prior/data weight in the table above. **Both gates — the `0.5` confidence
threshold and `MIN_CLASSIFY_HANDS = 50` — are unmeasured starting values chosen
for this design.** The 50 is anchored to the Tier A crossover above, but that
crossover is itself set by an unmeasured `PRIOR_STRENGTH`, so it inherits the
same status. Both belong in a config file and are to be tuned by
[§6](#6-validation-before-it-touches-a-real-table).

**Where the splits come from.**

- `VPIP_SPLIT` **defaults to 0.28**, the *approximate* complement of the "folds
  72% or more of hands is tight" threshold in [Billings 2006](#s-billings2006)
  as reported by [Teofilo & Reis 2011](#s-teofilo2011). **Approximate**, because
  fold rate and VPIP do not sum to 1: a big blind who checks their option is
  neither a fold nor a VPIP action, as
  [§2.2](#22-the-two-axes-that-have-literature-behind-them) and
  [§4.7](#47-edge-cases-a-coding-task-will-hit) both note. So 0.28 is a biased
  stand-in for the real complement, and borderline players will land on the
  wrong side of it. Treat it as a starting value pending
  [V4](#6-validation-before-it-touches-a-real-table), which measures the
  disagreement on logged hands; move the split by the measured gap.
- `AFQ_SPLIT` **defaults to 0.50**, being the AFq value at which bets-and-raises
  equal calls-and-folds. The literature threshold is stated as `AF > 1`, i.e.
  bets+raises exceed calls; `AFq = 0.5` is the nearest bounded analogue but is
  *not* the same quantity, and the difference must be measured rather than
  assumed. See [§6](#6-validation-before-it-touches-a-real-table).
- **Both splits are then replaced by the median of the bot's own observed
  population** once `MIN_POOL_OPPONENTS` qualifying opponents exist. Same
  rationale as `BASELINE`: a fixed constant would be a guess about a population
  nobody here has measured.

**That median is population-level, not live-field, and that is what makes it
allowed.** It is taken over every qualifying opponent in the database, including
people not at the current table, and it produces a classification threshold — the
"Sorting an opponent into a bucket" row of the `CLAUDE.md` table — not an
adjustment to any action. It must never be recomputed over just the opponents in
the current hand: that would be combining live-field rates, which
[§1](#the-forefront-rule-and-this-design) reserves to the engine. Each opponent
is then compared to the threshold **individually**; no opponent's rate is ever
mixed with another live opponent's.

**Hysteresis.** An opponent near a boundary must not flip bucket every hand.
Require the shrunk stat to cross the split by a dead-band of `0.02` before
reclassifying, and require the new classification to hold for `10` consecutive
hands. A bot that changes its whole strategy every third hand is worse than one
that never changes it. The `0.02` dead-band and the `10`-hand hold are
**unmeasured starting values chosen for this design**; V2 measures
reclassification frequency directly and tunes both.

**Exploit flags — orthogonal to the bucket.** The four buckets are coarse; the
money is often in one specific leak. Flags are independent booleans, each with
its own confidence gate. A flag fires only when *both* the confidence threshold
and the magnitude threshold are met.

| Flag | Condition | Confidence gate |
| --- | --- | --- |
| `OVERFOLDS_TO_3BET` | shrunk `fold_to_three_bet` exceeds `BASELINE[fold_to_three_bet]` by ≥ 0.15 | `confidence ≥ 0.6` |
| `NEVER_FOLDS_TO_3BET` | shrunk `fold_to_three_bet` below `BASELINE[fold_to_three_bet]` by ≥ 0.15 | `confidence ≥ 0.6` |
| `OVERFOLDS_TO_CBET` | shrunk `fold_to_cbet[flop]` exceeds `BASELINE[fold_to_cbet[flop]]` by ≥ 0.15 | `confidence ≥ 0.6` |
| `NEVER_FOLDS_POSTFLOP` | shrunk `wtsd` exceeds `BASELINE[wtsd]` by ≥ 0.10 | `confidence ≥ 0.6` |
| `OVERFOLDS_BLINDS` | shrunk `fold_to_steal` exceeds `BASELINE[fold_to_steal]` by ≥ 0.15 | `confidence ≥ 0.6` |
| `NEVER_RAISES` | shrunk `three_bet` below `BASELINE[three_bet]` **and** shrunk `check_raise` below `BASELINE[check_raise]`, both by ≥ 0.05 | `confidence ≥ 0.7` |
| `LIMPS` | shrunk `limp` exceeds `BASELINE[limp]` by ≥ 0.15 | `confidence ≥ 0.6` |

**`BASELINE` in every row above is the one defined in
[§4.3](#43-after-each-hand-the-update)** — `BASELINE[stat]`, the rate pooled over
every qualifying opponent in the bot's stored database, indexed by the stat named
in the same row. A coding task must not substitute anything else for it: not an
average over the opponents at the current table, which would be the reserved
live-field combination of [§1](#the-forefront-rule-and-this-design); not an
average over the handful of opponents a flag happens to be evaluated against; and
not a constant written into this table.

The 0.15 and 0.10 margins are deliberately larger than the confidence intervals
in [Table C](#table-c-how-many-hands-each-stat-needs) at the gate's
corresponding sample size. Those two margins, the tighter 0.05 margin on
`NEVER_RAISES`, and the `0.6` and `0.7` confidence gates in the table above are
all **unmeasured starting values**, to be tuned by the validation in
[§6](#6-validation-before-it-touches-a-real-table), and should be recorded in a
config file rather than in code.

**The upgrade path, when there is data for it.** The four-box grid is a
deliberate simplification. [Teofilo & Reis 2011](#s-teofilo2011) ran
expectation-maximisation clustering over per-player action-type frequencies
drawn from real-money tournament logs and recovered **7 distinct player types**,
each with at least one characterising tactic. Once this bot has its own hand
database of comparable size, re-derive the buckets the same way — cluster the
profile vectors rather than hand-drawing a grid. Do not do this before the data
exists.

### 4.5 Tiers: what to build, in what order

Each tier is independently shippable and independently valuable. **Do not start
tier N+1 before tier N is validated.**

---

#### Tier 0 — Measure only. No strategy change whatsoever.

Build `records.py`, `store.py`, `counters.py`, `profile.py`, `classify.py`,
`report.py`. The bot plays the blueprint exactly as it would without any of
this. The only visible output is a report command:

```
$ pokerbot profile "seat3_alias"
  hands       412
  vpip        0.41  (conf 0.89)   raw 0.43
  pfr         0.11  (conf 0.89)   raw 0.10
  gap         0.30
  afq[flop]   0.22  (conf 0.61)
  wtsd        0.38  (conf 0.42)
  bucket      STATION
  flags       NEVER_FOLDS_POSTFLOP, LIMPS, NEVER_RAISES
```

Every number in that block is **invented and illustrates the report's format
only**. It is not data and not a claim about any player.

**Why this is a full tier.** It is the whole foundation, it is entirely
engine-independent, it can be built and tested while the engine question is
still open, and it produces the data that every later tier needs. It also cannot
lose a single chip.

**Done when** the counters reproduce correct values on a suite of hand-history
fixtures, including the awkward cases in
[§4.7](#47-edge-cases-a-coding-task-will-hit).

---

#### Tier 1 — Select among precomputed engine strategies.

Precompute, offline, one strategy per bucket. **Each is produced by the engine**,
by running its solver against a *full* table of synthetic archetype opponents
rather than against self-play copies. **Full** means the seat count of the live
game: if the bot will sit at a six-handed table, the solve puts the bot in one
seat and an archetype in each of the other five. That is not a detail —
[§2.4](#24-why-bluffing-is-the-wrong-primary-exploit-at-a-multiway-table) leans
on it, because the multiway discount on bluffing is only in the solver's output
if the solve faced the same number of opponents the bot will. Solve one table per
seat count the bot plays; a strategy solved for a different seat count must not
be loaded at a table of another size. The archetypes are defined as
*action-frequency perturbations of the blueprint*, in exactly DBBR's sense: take
the blueprint
strategy and shift its action probabilities to match the bucket's measured
profile.

| Strategy | Trained against | The bot loads it when… |
| --- | --- | --- |
| `S_BASE` | self-play (the blueprint) | any opponent is `UNKNOWN`, or the table is mixed |
| `S_VS_STATION` | archetype with calls up-weighted, folds and raises down-weighted | the live field is predominantly `STATION` |
| `S_VS_MANIAC` | archetype with raises up-weighted | the live field is predominantly `MANIAC` |
| `S_VS_ROCK` | archetype with folds up-weighted, VPIP down-weighted | the live field is predominantly `ROCK` |
| `S_VS_TAG` | — | never; `TAG` loads `S_BASE` |

`TAG` deliberately has no counter-strategy. Against a competent opponent the
blueprint is the right answer and deviating is pure downside — this is the
Libratus position from [§3.1](#31-pluribus-did-not-do-opponent-modelling-at-all)
and Ganzfried and Sandholm's own advice to fall back to equilibrium against
strong opponents.

**"Predominantly" must be defined, because it is a multiway table.** Selection
is on the *live field*, not on one opponent, for the reason in
[§2.4](#24-why-bluffing-is-the-wrong-primary-exploit-at-a-multiway-table). Rule:
load a counter-strategy only if **every** live opponent is classified (none
`UNKNOWN`) **and** at least `⌈2n/3⌉` of the `n` live opponents share the bucket.
Otherwise `S_BASE`. The `⌈2n/3⌉` fraction is an **unmeasured design choice**
encoding "a clear majority of the live field", to be tuned against
[V5](#6-validation-before-it-touches-a-real-table).

**This is the one place on the live decision path where the live field is looked
at collectively, and it stays inside the rule.** (Offline, two reports read the
live field collectively as well, and neither touches a live decision:
[V5](#6-validation-before-it-touches-a-real-table)'s bluff frequency by number of
live opponents, and the "Multiway gate" column in
[§4.6](#46-what-each-bucket-means-in-plain-strategic-terms).) It counts bucket
labels that were each assigned to one opponent on that opponent's own rates; no
rate is combined with another live
opponent's rate, and the output is a strategy handle — the "Selecting *which*
engine strategy to load" row of the `CLAUDE.md` table, not the reserved
live-field combination described in
[§1](#the-forefront-rule-and-this-design). A coding task must not "improve" this
by averaging or multiplying the live opponents' rates to decide what to load;
that crosses the line.

**Where the forefront rule comes under strain, and how it is handled.** Defining
the archetype perturbation ("calls up-weighted") is a judgment about poker made
outside the engine. It is kept inside the rule by these constraints, which a
coding task must not relax:

- The perturbation is **derived from measured statistics**, not chosen by hand:
  the archetype's action frequencies are set to the pooled shrunk rates of real
  opponents in that bucket, from the bot's own database. **That pooling is
  population-level, not live-field, and that is what makes it allowed.** It runs
  offline, over every stored opponent in the bucket — not over the players at any
  table the bot is sitting at — and what it produces is an archetype handed to
  the engine's solver, which `CLAUDE.md` permits explicitly. Pooling the rates of
  the opponents in the current hand to shape a strategy mid-session would be the
  reserved live-field combination instead; see
  [§1](#the-forefront-rule-and-this-design).
- The perturbation touches **only action probabilities**. It never references
  hole cards, board cards, or hand strength.
- The bot's *own* strategy is then computed **entirely by the engine's solver**
  against that archetype. No hand-written response.

If the engine cannot accept a fixed opponent strategy (see
[Engine requirements](#engine-requirements)), **Tier 1 is not implementable as
specified and the task must stop and report that**, not substitute hand-written
adjustments.

---

#### Tier 2 — Per-opponent model, response computed by the engine.

Full DBBR structure: build `α_{n,a}` per opponent at the public history sets
where observations exist, substitute that as the opponent's strategy, and have
the engine compute the response. This is the highest-value tier and the most
expensive. Attempt only if Tier 1 is validated, the engine supports it, and time
remains.

---

#### Tier 3 — Not in scope.

Learned action predictors, per-opponent solver runs at the table, anything
requiring a trained network. Listed so the boundary is explicit.

### 4.6 What each bucket means in plain strategic terms

This section is **descriptive, not prescriptive**. It states what the
engine-produced counter-strategies are expected to look like, so that a person
reviewing the bot's play can tell whether it is behaving sensibly. **No coding
task should implement this table as rules.** If the engine's output against an
archetype disagrees with this table, the engine is right and this table is
wrong.

| Bucket | The habit | Expected shape of the counter | Multiway caveat |
| --- | --- | --- | --- |
| `STATION` (loose-passive) | Calls far too much, rarely raises, rarely folds | Bet good hands more often and for more; almost never bluff; take thinner value bets to the river | **Best target in the game.** Enter more pots when they are in and few others are |
| `ROCK` (tight-passive) | Plays few hands, folds readily, raises only with strength | Attack their blinds and their opens preflop where the interaction is one-on-one; believe their raises; give up cheaply postflop | Preflop exploits survive multiway; postflop bluffs do not (Table B) |
| `MANIAC` (loose-aggressive) | Raises constantly with a wide range | Call down wider; let them bluff into you; raise for value rather than for protection | Their wide range means they are often the only one who calls, which is exactly what you want |
| `TAG` (tight-aggressive) | Competent | Play the blueprint. Do not deviate | Avoid marginal pots where they are live |
| `UNKNOWN` | Not enough data | Play the blueprint | — |

**Flag-driven adjustments, same caveat.** These are the exploits Table C says
will actually have enough data behind them:

| Flag | Where the money is | Multiway gate |
| --- | --- | --- |
| `OVERFOLDS_TO_3BET` | Reraise them preflop more often | Only when they are the sole opener and nobody else has called |
| `OVERFOLDS_BLINDS` | Open more hands when only they are behind you | Only when they are the sole remaining player to act |
| `NEVER_FOLDS_TO_3BET` | Stop reraising as a bluff; reraise only for value | — |
| `NEVER_FOLDS_POSTFLOP` | Value-bet thinner; never bluff them | Applies regardless of field size — this is the value exploit |
| `OVERFOLDS_TO_CBET` | Continuation-bet more | **The multiway discount belongs to the engine.** Per [Table B](#table-b-the-multiway-problem) the counter-strategy must already bluff less often as the field grows; no module outside the engine may multiply live opponents' fold rates together to gate a bluff. [V5](#6-validation-before-it-touches-a-real-table) checks the engine's output for that fall after the fact |
| `NEVER_RAISES` | Their calls are weak; keep betting | — |
| `LIMPS` | Raise their limps | Only when few players remain to act behind |

### 4.7 Edge cases a coding task will hit

Each of these silently corrupts a counter if not handled. Each needs a fixture
test.

| Case | Required handling |
| --- | --- |
| Posting the blind | Does **not** count toward `vpip`. A player who checks their option in the big blind has not voluntarily put money in |
| Walk (everyone folds to the big blind) | Increments `hands_dealt` only. No `vpip` opportunity for anyone |
| Player sits out or is dealt out | No `hands_dealt` increment |
| All-in for less than a full raise | Counts as a raise for `pfr`/`afq`; the incomplete-raise rule must not reopen action in the state model |
| Straddle / ante structures | Must be recorded; `vpip` opportunity definitions shift. If the target table has straddles, this is a schema question, not an afterthought |
| Player leaves and returns | Same `opponent_id` if the alias is the same; decay handles the gap |
| Alias reuse by a different human | Undetectable in principle. Decay is the only mitigation. Note it and move on |
| Seat change | `opponent_id` is the alias, never the seat. Seat is a per-hand field |
| Bot folds preflop | **Still record the hand.** Free observation |
| Hand history truncated or unparseable | Reject the whole hand. Never partially apply increments |
| Opponent has fewer than 1 big blind | Their fold/call frequencies are structurally distorted. Exclude hands where the opponent started with under `MIN_STACK_BB = 5` (an unmeasured starting value) from all counters |

---

## 5. Safety: how this loses money if done carelessly

### 5.1 The documented failure mode

Ganzfried and Sandholm observed something that should be built for, not hoped
against: when DBBR switched from equilibrium play to exploitation, against two
of their opponents "the win rate **decreases significantly** for the first
several hundred hands before it starts to increase." Their diagnosis: "the
approximate-equilibrium strategy plays some action sequences with very low
probability, leading it to not explore the opponent's full strategy space...
This in turn may cause DBBR to think it can immediately exploit the opponent in
certain ways, which turn out to be unsuccessful."

Their worked example: at hand 1006 against an always-raising opponent, DBBR held
ten-high on the river and, having almost no observations of how that opponent
responded to river raises, fell back on the prior — which said the opponent
would fold weak hands. It raised. The opponent, as always, raised back. "DBBR
lost a significant amount of money."

**The lesson is precise: the danger is not a wrong model, it is a confident
model built in a region of the game the bot has never observed.** The prior
fills the gap with the baseline's behaviour, and the bot then acts as though it
has knowledge it does not have.

### 5.2 Mitigations, each traceable to a source

| Mitigation | Grounding |
| --- | --- |
| **Confidence gate on every flag.** No exploit fires below its threshold | DBR: 1-Step confidence (act after one observation) overfits; 10-Step and 0-10 Linear do not ([Johanson & Bowling 2009](#s-johanson2009), §6) |
| **Warm-up period.** Play `S_BASE` for the first `WARMUP_HANDS = 200` hands at any table | DBBR used `T = 1000` ([Ganzfried & Sandholm 2011](#s-ganzfried2011), §5). 200 is lower because Table C shows Tier A stats converge by then; it is a tuning parameter |
| **Deviation cap.** A global `Pmax`-equivalent limiting how far any counter-strategy may sit from `S_BASE` | DBR's `Pmax` "allows us to set a tradeoff between" exploitation and exploitability |
| **Exploit only where observed.** Where a stat has no observations, the bot must fall back to `S_BASE` for that decision, not to the prior-filled model | Directly from the DBBR river failure above |
| **Win-rate switch.** Track realised bb/100 with exploitation on versus off, per bucket and per flag. Disable any exploit whose measured contribution is not positive over a meaningful sample | "only attempting to exploit the opponent if a win rate above some threshold is attained" (ibid., §5) |
| **Default to the blueprint.** Unknown opponent, mixed table, or any uncertainty: `S_BASE` | Pluribus beat elite humans with no opponent model at all ([Brown 2020](#s-brown2020), §6.6) |

### 5.3 The one risk the literature does not cover

**Humans adapt; the bots in these papers did not.** AlwaysRaise, GUS2 and
Tommybot never noticed they were being exploited. A human who works out that the
bot reraises them every time will start trapping. None of the cited results
speak to this.

Required responses, all cheap:

- **Decay** ([§4.3](#43-after-each-hand-the-update) step 2) so that stale
  observations lose weight.
- **Per-exploit profit tracking.** If `OVERFOLDS_TO_3BET` stops earning against
  a specific opponent, the flag must go stale and switch off for that opponent.
  This is the counter-adaptation detector, and it costs one extra column.
- **Never deviate maximally.** A capped deviation is much harder for a human to
  read than a total one.

---

## 6. Validation before it touches a real table

The global rules require a defect to be reproduced with a failing test before it
is fixed, and require numbers to come from a live query rather than from
assumption. Applied here:

**V1 — Counter correctness.** A fixture suite of hand histories with
hand-checked expected counter values, covering every row of
[§4.7](#47-edge-cases-a-coding-task-will-hit). Pure unit tests, no engine.

**V2 — Classifier stability.** Replay a logged session. Measure how often an
opponent's bucket changes. A classifier that reclassifies the same person more
than a handful of times in a thousand hands has its hysteresis wrong.

**V3 — Predictive calibration. This is the test that says whether the model is
real.** Hold out the last 30% of logged hands per opponent; the 70/30 split is
an unmeasured starting value. From the profile built on the first 70%, predict
each held-out action (fold / call / raise) and score by log-loss against two
baselines: the pooled rate across the observed population (the same
population-level pooling as `BASELINE`, computed offline on logged hands), and
the blueprint's own action frequency. **If the per-opponent model does not beat
both baselines, the opponent model is not adding information and Tier 1 must not
ship.** This is falsifiable, runs offline, and costs nothing.

**V4 — Split-threshold check.** Both splits in
[§4.4](#44-bucketing-an-opponent) are stand-ins for a literature threshold
stated in a different quantity, and both are checked the same way, on the same
logged population, at the same time.

- **Aggression.** `AFQ_SPLIT = 0.50` is asserted as the bounded analogue of the
  literature's `AF > 1`. Compute both on every logged opponent and report the
  disagreement rate. If they disagree often, the split is wrong and must move to
  whatever value reproduces the `AF > 1` partition.
- **Looseness.** `VPIP_SPLIT = 0.28` is asserted as the complement of "folds
  ≥72% of hands", which it is only approximately — checked big-blind options
  belong to neither rate. Measure, per opponent: the fold rate, the VPIP, and
  `1 − fold_rate − vpip`, the gap between them. Report the mean gap, and the
  disagreement rate between "tight by fold rate ≥ 0.72" and "tight by
  `vpip ≤ 0.28`". If the gap is material, move `VPIP_SPLIT` to the VPIP value
  that reproduces the fold-rate partition on this population, and record the
  measured gap beside it.

Both checks are superseded, not repeated, once the population median replaces
each split per [§4.4](#44-bucketing-an-opponent) — at that point the literature
threshold is no longer load-bearing.

**V5 — Exploitation A/B.** Alternate `S_BASE` and the counter-strategy by hand
parity over a long run, and compare bb/100. Note the variance problem: Pluribus
needed 10,000 hands *with the AIVAT variance-reduction technique* to reach
p = 0.028 ([Brown 2020](#s-brown2020), §6.6). Without variance reduction this
measurement needs far more hands than the project will have. **Treat V5 as a
red-flag detector — "is this losing badly?" — not as proof that exploitation
works.** V3 is the real evidence.

V5 carries one extra report, which is cheap and needs no extra hands: **bluff
frequency broken down by the number of live opponents.** The arithmetic in
[§2.4](#24-why-bluffing-is-the-wrong-primary-exploit-at-a-multiway-table) says a
sound strategy bluffs less as the field grows. If the engine's output does not
show that fall, the finding is a red flag against that strategy — a reason to
re-examine the archetypes or the solver settings, never a licence to correct
bluff frequency in code outside the engine.

---

## Engine requirements

What this design needs from the vendored engine. **A separate task is assessing
these; nothing here should be assumed.** Each is stated so it can be answered
yes or no.

| # | Requirement | Needed by |
| --- | --- | --- |
| E1 | Can the engine's trained strategy be queried for an action-probability distribution at a given decision point, rather than only a sampled action? | Tier 1 archetypes, Tier 2, and V3 |
| E2 | Can the solver be run against a **fixed** opponent strategy instead of self-play copies? | Tier 1 |
| E3 | Can more than one trained strategy be held in memory and switched between hands? | Tier 1 |
| E4 | Is there a stable identifier for a decision point (an information set or public history) that the model can key observations on? | Tier 2 |
| E5 | What is the cost of one solver run against fixed opponents — minutes, hours, or days? | Tier 1 feasibility |
| E6 | Does the engine expose the table state the `HandRecorder` needs — seats, stacks, full action sequence with amounts? | Tier 0 |

**E6 is the only requirement Tier 0 has.** If E6 is satisfiable from the capture
layer alone, Tier 0 can be built immediately, in parallel with the engine
assessment. That is the recommended sequencing.

---

## 7. Questions for the operator

Listed with a recommendation first, as the global rules require. Q2 is answered
and kept here as a record of the answer; Q1 and Q3 are still open.

**Q1 — Where does the bot get hands to learn from before it has played any?**
The design needs a pool of observed opponents to set `BASELINE` and the split
thresholds, and it needs logged hands for V2 and V3. *Recommendation:* run Tier
0 in pure observation mode — the bot sits at a table, folds every hand, and
records — for a few hundred hands before anything else. Alternative: use a
public hand-history corpus of the kind
[Teofilo & Reis 2011](#s-teofilo2011) used. Whether that is acceptable for a
class project is the operator's call, and depends on the source's terms.

**Q2 — Is the opponent identifier stable? ANSWERED: yes.** Everything depends on
recognising the same human across hands, so this was load-bearing. The operator
has confirmed directly that the target app shows consistent player names that a
player cannot change, and has asked for a true per-opponent adaptive model to
maximise profit rather than a weaker per-table approximation. **Consequences,
now settled rather than conditional:**

- `opponent_id` is that player name. The schema in
  [§4.2](#42-the-stat-table) already assumes it.
- The per-*table* pooled-profile fallback that this question previously offered
  is **dropped**. It was only ever the answer to "identifiers are unstable",
  and they are not. It is also not to be reintroduced for any other reason:
  pooling the rates of the players at the current table is a live-field
  combination, which [§1](#the-forefront-rule-and-this-design) reserves to the
  engine.
- The rest of this document needs no change: per-opponent tracking was the
  assumption throughout, and every stat, bucket and exploit flag is already
  keyed on `opponent_id`.
- Two edge cases in [§4.7](#47-edge-cases-a-coding-task-will-hit) survive
  unchanged and still need their fixtures: a player who leaves and returns keeps
  the same id, and a name reused by a different human stays undetectable in
  principle, with decay as the only mitigation.

**Q3 — Tilt modelling.** The `session_net_bb` field is reserved but not acted
on. No grounding was found in the surveyed literature for a tilt signal that is
cheap to compute and known to be predictive. *Recommendation:* leave it
recorded and unused; revisit only if V3 shows the existing model has hit a
ceiling.

---

## Sources

All retrieved and read 2026-09-15.

<a id="s-brown2020"></a>**[Brown 2020]** Noam Brown, *Equilibrium Finding for
Large Adversarial Imperfect-Information Games*, PhD thesis, Carnegie Mellon
University, CMU-CS-20-132.
`http://reports-archive.adm.cs.cmu.edu/anon/2020/CMU-CS-20-132.pdf`
Openly available, and the citable source for Pluribus's internals, since the
Science paper itself is paywalled. §6.4 covers Libratus and its position on
opponent exploitation; §6.6 covers Pluribus, including the "does not adapt its
strategy to its opponents" statement, the resource figures, and the multiplayer
game-theory argument.

The underlying publication is Noam Brown and Tuomas Sandholm, "Superhuman AI for
multiplayer poker", *Science* 365(6456):885–890, 2019,
DOI `10.1126/science.aay2400`. Confirmed closed-access via the Unpaywall API on
2026-09-15 (`is_oa: false`, `oa_status: "closed"`), which is why the thesis is
cited in preference.

<a id="s-ganzfried2011"></a>**[Ganzfried & Sandholm 2011]** Sam Ganzfried and
Tuomas Sandholm, "Game Theory-Based Opponent Modeling in Large
Imperfect-Information Games", *AAMAS 2011*.
`https://www.cs.cmu.edu/~sandholm/opponentModeling.aamas11.pdf`
The DBBR algorithm. §4.2 has the Dirichlet posterior equation used in
[§4.3](#43-after-each-hand-the-update); §5 has the parameter choices and the
"only exploit if winning" rule; §5.4 has the exploitation-hurts-at-first failure
analysed in [§5.1](#51-the-documented-failure-mode).

<a id="s-johanson2009"></a>**[Johanson & Bowling 2009]** Michael Johanson and
Michael Bowling, "Data Biased Robust Counter Strategies", *AISTATS 2009*.
`https://poker.cs.ualberta.ca/publications/AISTATS09.pdf`
The confidence-function family, `Pmax`, the overfitting result for single-
observation confidence, and the finding that 0-10 Linear counter-strategies work
across data quantities from 100 to 1,000,000 observed games.

<a id="s-johanson2007"></a>**[Johanson et al. 2007]** Michael Johanson, Martin
Zinkevich and Michael Bowling, "Computing Robust Counter-Strategies",
*NIPS 2007*. `https://poker.cs.ualberta.ca/publications/NIPS07-rnash.pdf`
Restricted Nash Response: exploit a suspected tendency while bounding worst-case
loss.

<a id="s-southey2005"></a>**[Southey et al. 2005]** Finnegan Southey, Michael
Bowling, Bryce Larson, Carmelo Piccione, Neil Burch, Darse Billings and Chris
Rayner, "Bayes' Bluff: Opponent Modelling in Poker", *UAI 2005*.
`https://arxiv.org/pdf/1207.1411`
Bayesian opponent modelling with Dirichlet priors; the source of the
"respond to the posterior, not the point estimate" principle.

<a id="s-teofilo2011"></a>**[Teofilo & Reis 2011]** Luís Filipe Teófilo and Luís
Paulo Reis, "Identifying Player's Strategies in No Limit Texas Hold'em Poker
through the Analysis of Individual Moves", *EPIA 2011*.
`https://arxiv.org/pdf/1301.5943`
§3 states the tight/loose and aggression-factor thresholds and attributes them
to Billings' thesis and Sklansky. §5 Table 1 gives the corpus statistics
(51,377,820 games; 158,035 players; 2,323,538 showdowns; 4.52% showdown ratio).
The corpus is real-money **tournament** play, not cash play — relevant wherever
a rate from it is carried over to a cash table.
§7 reports the 7 recovered player types by EM clustering.

<a id="s-billings2006"></a>**[Billings 2006]** Darse Billings, *Algorithms and
Assessment in Computer Poker*, PhD thesis, University of Alberta. The origin of
the numeric tight/loose and aggression-factor classification, as cited by
Teofilo and Reis. **Cited at second hand** — the thesis itself was not retrieved
in a usable text form during this survey. A coding task relying on the exact
72% threshold should confirm it against the primary text.

<a id="s-billings1998"></a>**[Billings et al.]** Darse Billings, Denis Papp,
Jonathan Schaeffer and Duane Szafron, "Opponent Modeling in Poker",
*AAAI-98*. The Loki/Poki opponent-modelling line. **Cited at second hand**, via
the reference list of [Brown 2020](#s-brown2020) and the related-work section of
[Teofilo & Reis 2011](#s-teofilo2011); the paper was not retrieved directly.
Nothing in this design depends on a specific claim from it.

<a id="s-sklansky"></a>**[Sklansky]** David Sklansky, *The Theory of Poker*.
Cited at second hand via [Teofilo & Reis 2011](#s-teofilo2011) as the origin of
the tight/loose, passive/aggressive taxonomy.

**Deliberately not cited.** Poker tracking-software population averages —
"typical 6-max VPIP is 22–26%" and similar — circulate widely but no
peer-reviewed or otherwise verifiable source for them was found during this
survey. They are **excluded on purpose**, which is why
[§4.3](#43-after-each-hand-the-update) derives `BASELINE` from the bot's own
observed population instead of hardcoding constants. Kyle Siler, "Social and
Psychological Challenges of Poker", *Journal of Gambling Studies* 26(3), 2010,
DOI `10.1007/s10899-009-9168-2`, analyses a large corpus of real online hands
and was considered, but its abstract is publisher-elided and the full text was
not obtainable, so no claim is drawn from it.

---

## Provenance of every number in this document

Per the global evidence rules, so that no figure here has to be taken on trust.

| Number | Where it comes from |
| --- | --- |
| Tables A, B, C, D, E, and the inline `0.5^(1/3) ≈ 0.794` reading of them | Computed by script on 2026-09-15. Formulas are stated inline beside each table; all are elementary arithmetic (binomial standard error, independent-event products, Beta posterior means) |
| Table C's anchor `p̂` column (0.30, 0.20, 0.07, 0.60, 0.50, 0.25) | **Illustrative anchors, not measured or cited.** Labelled as such beside the table; the interval width barely moves across `p̂` in 0.2–0.8 |
| Table C's opportunities-per-hand column (`fold_to_three_bet` 0.08, `fold_to_cbet` 0.15, `wtsd` 0.30) | **Illustrative estimates, not measured or cited.** No source exists for them; labelled as such beside the table. Each is to be replaced by `denominator / hands_dealt` from the bot's own logged hands. The "Hands needed" column scales inversely with them |
| Hysteresis dead-band `0.02` and the `10` consecutive-hand hold ([§4.4](#44-bucketing-an-opponent)) | **Starting values chosen for this design, not measured.** Tuned by V2, which measures reclassification frequency directly |
| The `⌈2n/3⌉` shared-bucket rule for loading a counter-strategy ([§4.5](#45-tiers-what-to-build-in-what-order)) | **A design choice, not a measured or cited threshold.** It encodes "a clear majority of the live field", following the multiway argument in [§2.4](#24-why-bluffing-is-the-wrong-primary-exploit-at-a-multiway-table); tune against V5 |
| `MIN_POOL_HANDS = 200` and `MIN_POOL_OPPONENTS = 20` ([§4.3](#43-after-each-hand-the-update)) | **Starting values chosen for this design, not measured.** They set when the bot's own population is large enough to supply `BASELINE` and the splits; both belong in config and are to be raised if the pooled rates prove unstable |
| 51,377,820 games / 158,035 players / 2,323,538 showdowns / 4.52% showdown ratio | [Teofilo & Reis 2011](#s-teofilo2011), Table 1, read directly. Corpus is real-money **tournament** logs; showdown frequency may differ in cash play |
| 7 player types | [Teofilo & Reis 2011](#s-teofilo2011), §7, read directly |
| Folds ≥72% = tight; AF > 1 = aggressive | [Teofilo & Reis 2011](#s-teofilo2011), §3, citing [Billings 2006](#s-billings2006). **Second-hand** |
| 48 mbb/game ±25, p=0.028; 32 mbb/game ±15, p=0.014; 10,000 hands | [Brown 2020](#s-brown2020), §6.6, read directly |
| 8 days / 64 cores / 12,400 core-hours / <512 GB / ~$144 / 28-core search | [Brown 2020](#s-brown2020), §6.6, read directly |
| "Pluribus does not adapt its strategy to its opponents" | [Brown 2020](#s-brown2020), §6.6, quoted directly |
| `N_prior = 5`, `T = 1000`, `k = 50`; the posterior equation | [Ganzfried & Sandholm 2011](#s-ganzfried2011), §4.2 and §5, read directly |
| Abstraction branching factors 15/40/6/6 and 8/12/4/4 | [Ganzfried & Sandholm 2011](#s-ganzfried2011), §5, read directly |
| The 1006th-hand river failure | [Ganzfried & Sandholm 2011](#s-ganzfried2011), §5.4, read directly |
| s-Curve `Pmax · n/(s+n)`; 0-10 Linear; the 100-to-1m observation range | [Johanson & Bowling 2009](#s-johanson2009), §5.2 and §6, read directly |
| `HALF_LIFE = 2000`, `PRIOR_STRENGTH` values (50/25/15, which are also the s-Curve `s`), `WARMUP_HANDS = 200`, `MIN_CLASSIFY_HANDS = 50`, all flag margins (0.15/0.10/0.05) and flag confidence gates (0.6/0.7), the `confidence < 0.5` `UNKNOWN` gate, `MIN_STACK_BB = 5`, the 70/30 V3 holdout split, and `VPIP_SPLIT` and `AFQ_SPLIT` until the bootstrap in [§4.4](#44-bucketing-an-opponent) replaces them with measured population medians | **Starting values chosen for this design, not measured.** Every one is labelled as such at its point of use as well as here, belongs in a config file, and is to be tuned by the validation in [§6](#6-validation-before-it-touches-a-real-table). `VPIP_SPLIT = 0.28` is the one part-exception: it is the *approximate* complement of the literature's 72% fold threshold — approximate because the two rates do not sum to 1 (see [§2.2](#22-the-two-axes-that-have-literature-behind-them)) — and it stands only until V4 corrects it or the bot's own population replaces it |
| The example `pokerbot profile` output in [Tier 0](#45-tiers-what-to-build-in-what-order) (412 hands, 0.41 vpip, and the rest) | **Invented, and only illustrates the report's format.** Not data, not a claim about any player |
