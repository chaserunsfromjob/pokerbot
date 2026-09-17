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

The second is that most of the tables have three or more players, not two — the
bot has to handle any size from two players up to nine. With one opponent,
bluffing works if that one person folds enough. With four opponents, *all four*
have to fold, and the odds of that collapse fast — the arithmetic is in
[Table B](#table-b-the-multiway-problem). This is why the plan leans on getting
paid with good hands rather than on bluffing.

One rule constrains everything below. `CLAUDE.md` in this repository lets an AI
assistant write the poker code — the code that picks an action, assigns a range
to an opponent, reads the board and combines opponent rates — while keeping
every model call out of the live decision path, refusing to let a decision's
content come from stored model output, and taking the game rules and hand
evaluation from the vendored engine. Nothing in this design breaks that.
Everything the opponent model hands to the bot in play is counted from observed
actions: **numbers describing what an opponent does**, **summaries of those
numbers across the whole observed population** — a baseline to shrink toward, a
threshold to classify against, an archetype for the engine to solve against — and
**a choice of which engine-produced strategy to load**. No model is called while
a hand is live, nothing a model produced is stored and replayed as a decision,
and ranking a hand stays with the engine. `CLAUDE.md` states exactly where the
line falls, in its "What may be coded" and "What may not be coded" lists under
"The forefront rule";
[The forefront rule and this design](#the-forefront-rule-and-this-design) below
points at those lists and this design obeys them.

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
100 hands, at **every table size from 2 to 9 players** — a firm operator
requirement, not a preference, and the scope every part of this document is
sized against ([§4.5](#45-tiers-what-to-build-in-what-order) states what it costs
to cover all eight seat counts, and what changes at 2).

Three or more players is where the hard part sits, and most of what follows is
aimed there, for the reason in the next paragraph: it is the region with no
usable equilibrium guarantee. Two players is in scope all the same, and is the
one size where that guarantee does exist.

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

`CLAUDE.md`, under "The forefront rule", is the authority for what this design
may write, and this document only has to obey it. Three of its bullets govern
everything below, and they are quoted here **verbatim**, so that this summary
can be checked against the authority by inspection rather than trusted:

> Let an AI assistant write the poker code: the code that picks an action, assigns a range to an opponent, reads the board, and combines opponent rates.

> Keep every model call out of the live decision path; when the bot acts it runs ordinary code only, with no language-model inference, no network call to a model, and no prompt.

> Treat the **observed population** as the whole database, seated players' stored rows included, with being seated never the criterion for inclusion, and combine rates across it into a baseline, a classification split, or an archetype.

So an AI assistant may write the opponent-model code in this document, including
the code that picks an action, assigns a range, reads the board, and combines
opponent rates. What that code may never do is call a model while a hand is
live, or take the content of a poker decision from stored model output — a
table, a set of weights, or text a model produced. It is ordinary code: the same
inputs and seed give the same answer, tests cover it, and a reviewer reads it
line by line. The game rules and hand evaluation still come from the engine
road, OpenSpiel `universal_poker`, rather than being hand-rolled, which is why
the non-goals above rule out a hand-strength estimator.

**Live field versus observed population.** This design leans everywhere on a
split between two ways of pooling rates, so it is worth restating in full.
Combining rates across the **live field** — the opponents in the current hand —
into anything that adjusts the bot's own action is left to the engine
throughout, and where a section below declines such a combination that is this
design's own architecture, not a prohibition the rule imposes. Combining
rates across the **observed population** — the whole database, seated players'
stored rows included, with being seated never the criterion for inclusion — into
a baseline, a classification split, or an archetype handed to the engine is
work this document's own code does, exactly as the quoted bullet describes.

"The whole database" is meant literally, and the ambiguity is worth killing
outright, because it is the one that would otherwise be read the wrong way.
Pooling across the observed population does **not** mean the database with the
currently seated players held out. Their stored rows are in the pool like anyone
else's. What makes the pool population-level is that nobody is selected *for*
being at the table: the pool is every opponent meeting the stored-hands
threshold, and seating neither adds an opponent to it nor removes one. Filtering
the pool down to the players in the current hand is the live-field combination
this design leaves to the engine; leaving them in it is not.

**Every rate combination this design puts on the live decision path — anything
computed while a hand is in progress, or loaded into play from something that
was — is on the allowed side, and each one says which side it is on at its own
point of use.** Combinations *across* opponents, all of them population-level and
computed from the stored database rather than from the players in the current
hand: the pooled `BASELINE`
([§4.3](#43-after-each-hand-the-update)) and the population-median split
thresholds ([§4.4](#44-bucketing-an-opponent)), both read while a hand is in
progress; and the pooled archetype fed to the solver
([§4.5](#45-tiers-what-to-build-in-what-order)), which is computed offline but
reaches the table inside a strategy that gets loaded into play.
Combinations *within* one opponent: `AF` ([§4.2](#42-the-stat-table)) and
`vpip_pfr_gap` ([§2.3](#23-the-stat-set)), both of which combine that one
opponent's own counts and are reported as diagnostics without ever being an input
to a poker decision the bot acts on. The only place *on the live decision path*
where the *live field* is looked at collectively is choosing which precomputed
strategy to load ([§4.5](#45-tiers-what-to-build-in-what-order)), which counts
already-assigned buckets rather than combining rates, and whose whole output is a
strategy handle — a choice of which engine strategy to load, not a rate
combination.

**Away from the decision path this design also combines rates offline, over
logged hands, and those combinations are not enumerated above because none of
them is computed at the table.** They are: the pooled rate V3 scores the model
against and V4's mean fold-rate-versus-VPIP gap with its two disagreement rates,
all taken across the whole logged population
([§6](#6-validation-before-it-touches-a-real-table), where V3 and V4 both run
offline on held-out and logged hands); the pooled opportunity rates that replace
the placeholders in [Table C](#table-c-how-many-hands-each-stat-needs), which set
expectations and config values between sessions and are never read during a hand;
the upgrade path's
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
| `open_raise` | Made the first raise preflop, first-in with no prior raiser; split five ways by seat bucket: `EP` / `MP` / `LP` / `SB` / `BB` | Position-blind opponents are the exploitable ones |

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

Bet size `s` is the bet as a fraction of the pot. Computed by `tools/check_design_numbers.py`, 2026-09-15.

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
| 50% | 50.0% | 25.0% | 12.5% | 6.3% | 3.1% |
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
   strategy must exhibit**, and no module in this design multiplies the live
   field's fold rates together at the table and adjusts a bluff frequency by
   the result. `CLAUDE.md`'s forefront rule, under "What may be coded", would
   permit code of ours that did — combining opponent rates is ours to write —
   so this is a design choice about where the multiway discount comes from,
   not a rule forbidding it; see the line summarised in
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
not — "1-Curve" is the source's own name, kept verbatim here, and that it is the
s-Curve above with the constant `s` = 1 is the paper's own statement, not an
inference of this document's: "The s-Curve function returns Pmax × (nI/(s + nI))
for any constant s; in this experiment, we used s = 1" (ibid., §5.2); and the
0-10 Linear counter-strategies "are effective with any quantity of training
data", tested down to 100 observed games (ibid., §6 and Figure 2). That last
point is the licence for this project to exploit on small samples at all — but
only with the shrinkage in place.

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
weight in our model when we have observed the opponent's action 5 times at the
given public history set."

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
| Training a bespoke blueprint per opponent bucket from scratch at Pluribus scale | 12,400 CPU core-hours *per strategy* ([Brown 2020](#s-brown2020), §6.6). Four strategies at each of the eight seat counts from 2 to 9 players is 32 of those ([§4.5](#45-tiers-what-to-build-in-what-order)). |
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
live opponents' rates — a design choice, held to in
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
and 0.8. Computed by `tools/check_design_numbers.py`, 2026-09-15.

The **"Opportunities per hand" column is measured in two rows and an
illustrative estimate in two others.** `fold_to_cbet` at **0.030** and `wtsd` at
**0.187** are the nine-handed pooled rates in
[`OPPONENT_BASELINE.md` §2](OPPONENT_BASELINE.md#2-corpus-a-the-2009-no-limit-population-per-table-size),
whose "FtCB chances per hand" and "Flops seen per hand" columns are exactly the
[§4.2](#42-the-stat-table) denominators of those two stats — "faced a
continuation bet on that street" and "saw a flop" — counted over that
document's 70,685 nine-handed hands of 2009 no-limit play. Carry its caveat with
the number: both were measured on the sample its §1 describes, which lacks
PartyPoker and leans high-stakes, and on a seventeen-year-old archive rather
than on the table this bot will sit at. For the other two rows no published
figure was found for how often a real multiway table hands a given player those
spots, and none is invented here: 0.08 and 0.15 are round order-of-magnitude
placeholders for "rare" and "occasional". Only `vpip` and `pfr` carry a rate of
1.00, and they carry it because their [§4.2](#42-the-stat-table) denominator is
literally "opponent was dealt in" — one opportunity per hand by definition, not
an estimate. **Every row that is neither measured nor forced takes a
placeholder**, because every other denominator in [§4.2](#42-the-stat-table) is
a spot the game has to hand the player: `three_bet`'s is "faced exactly one open
raise with chips behind", `fold_to_three_bet`'s is "had open-raised and then
faced a reraise". The "Hands needed" column inherits whatever its rate is worth
and scales inversely with it — halve an opportunity rate and the hands double.
**Replace every remaining placeholder, and both archive rates, with measurement
as soon as Tier 0 has logged any hands**: each is exactly
`denominator / hands_dealt` for that stat, pooled across the observed population
(not the live field, and not a behaviour rate at all — it is how often the game
hands somebody that spot). What survives the uncertainty is the *ordering* —
Tier A stats need hundreds of hands and postflop stats need thousands — and that
ordering is what the rest of this document leans on.

| Stat | Anchor `p̂` (illustrative) | Opportunities per hand | Target width | Opportunities needed | **Hands needed** | Where the rate comes from |
| --- | --- | --- | --- | --- | --- | --- |
| `vpip` | 0.30 | 1.00 | ±5pp | 323 | **323** | one per hand by definition |
| `vpip` | 0.30 | 1.00 | ±3pp | 896 | **896** | one per hand by definition |
| `pfr` | 0.20 | 1.00 | ±5pp | 246 | **246** | one per hand by definition |
| `three_bet` | 0.07 | 0.15 | ±2pp | 625 | **4,168** | illustrative placeholder |
| `fold_to_three_bet` | 0.60 | 0.08 | ±10pp | 92 | **1,152** | illustrative placeholder |
| `fold_to_cbet` | 0.50 | 0.030 | ±10pp | 96 | **3,201** | measured, `OPPONENT_BASELINE.md` §2, nine-handed |
| `wtsd` | 0.25 | 0.187 | ±5pp | 288 | **1,541** | measured, `OPPONENT_BASELINE.md` §2, nine-handed |

**This table is the honest expectation-setter for the whole project.** VPIP and
PFR are usable inside one long session. Everything postflop needs many sessions
against the same person. A design that promises sharp postflop exploits after
fifty hands is promising noise. `three_bet` is the sharpest illustration: it is
a preflop stat, but its denominator is not "dealt in", and at a placeholder 0.15
opportunities per hand a ±2pp reading of a 7% behaviour is thousands of hands
away — further off than any postflop row here. "Preflop exploits ship first",
the consequence stated just below, therefore means `vpip` and `pfr` first, not
every preflop stat at once.

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

**That Σ is population-level, and that is exactly the baseline the rule
names.** It sums over every qualifying opponent in the database — people not at
the current table, past sessions, and the stored rows of seated players too,
since being seated is never the criterion for inclusion — and its output is a
prior mean that a single opponent's rate is shrunk toward. It adjusts no action
by itself. This is the observed-population baseline named in the forefront
rule's "What may be coded", summarised in
[§1](#the-forefront-rule-and-this-design). A coding task must compute it from
stored history only, and must never restrict the pool to the players currently
seated.

`PRIOR_STRENGTH` per stat — which is also the `s` in the `confidence` line
above — sized to the opportunity rate so that the crossover from "treat as
average" to "treat as themselves" lands at a sensible number of hands:

| Stat group | `PRIOR_STRENGTH` | Prior and data carry equal weight at… |
| --- | --- | --- |
| Tier A (`vpip`, `pfr`, `limp`) | 50 | 50 hands |
| Tier B (`three_bet`, `fold_to_three_bet`, `fold_to_steal`, `cbet`, `fold_to_cbet`, `afq`, `check_raise`, `open_raise`) | 25 | 25 opportunities |
| Tier C (`wtsd`, `wsd`, `fold_to_river_bet`) | 15 | 15 opportunities |

**Every stat this design shrinks is named in exactly one row above, and the rows
are exhaustive on purpose**: a stat with no `PRIOR_STRENGTH` has no shrunk rate
and no confidence, so any gate written against it cannot be evaluated. Two of
them are here for that reason and sit in a group [§2.3](#23-the-stat-set) does
not put them in. `check_raise` is one: [§4.4](#44-bucketing-an-opponent)'s
`NEVER_RAISES` flag reads its shrunk rate and its confidence, and both figures
that section quotes for it are `s` = 25 figures. `open_raise` is the other:
[§2.3](#23-the-stat-set) groups it with Tier A because it is preflop, but its
[§4.2](#42-the-stat-table) denominator is "first-in with no prior raiser" *split
five ways by seat bucket*, so each of its contexts sees a Tier B handful of
opportunities per ten hands and is sized as Tier B. No row above is a wildcard:
`fold_to_river_bet` is Tier C and is **not** covered by the Tier B `fold_to_*`
family it resembles.

The stats named elsewhere in this document that deliberately have **no**
`PRIOR_STRENGTH`, because nothing shrinks them: `hands_dealt` (a count, not a
rate); `af_bets_raises` and `af_calls` (raw counters behind the reported `AF`
diagnostic, and `AF` is unbounded, so neither admits shrinkage — see
[§2.2](#22-the-two-axes-that-have-literature-behind-them)); `vpip_pfr_gap` (a
difference of two already-shrunk rates); `showdown_holdings`; and the Tier D
bookkeeping fields `stack_bb`, `hands_since_last_seen` and `session_net_bb`.

**All three `PRIOR_STRENGTH` values — 50, 25 and 15 — are unmeasured starting
values chosen for this design**, neither measured nor cited. They belong in a
config file and are to be tuned by the validation in
[§6](#6-validation-before-it-touches-a-real-table).

#### Table D: what the confidence weight looks like

`confidence = n / (n + s)`, where `s` is that stat's `PRIOR_STRENGTH`. The three
tier values from the table above are marked; `s`=5 and `s`=10 are included only
to show the shape. Computed by `tools/check_design_numbers.py`, 2026-09-15.

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

What the blend actually does to a loud small sample. Computed by `tools/check_design_numbers.py`, 2026-09-15.

| Baseline | Prior strength | Observed | Raw rate | **Shrunk rate** |
| --- | --- | --- | --- | --- |
| 0.25 | 25 | 10 of 20 | 0.50 | **0.361** |
| 0.25 | 25 | 30 of 40 | 0.75 | **0.558** |
| 0.60 | 25 | 18 of 20 | 0.90 | **0.733** |
| 0.60 | 25 | 2 of 20 | 0.10 | **0.378** |

Row 1 is the case that matters: somebody who has raised half of twenty
*opportunities* — Tier B units, since the prior strength in every row is the
Tier B 25 — is recorded as a 36% raiser, not a 50% one. That is the mechanism
that stops the bot chasing noise. Note also that at 20 observations the
confidence is `20/45 = 0.44`, below every gate in
[§4.4](#44-bucketing-an-opponent): the shrunk rate exists, but nothing fires on
it yet.

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

**That median is population-level, and that is exactly the split the rule
names.** It is taken over every qualifying opponent in the database, including
people not at the current table and the stored rows of seated players, and it
produces a classification split — named in the forefront rule's "What may be
coded" — not an adjustment to any action. It must never be recomputed over just
the opponents in the current hand: that would make being seated the criterion
for inclusion, which the same bullet refuses
([§1](#the-forefront-rule-and-this-design)). Each opponent is then compared to
the threshold **individually**; no opponent's rate is ever
mixed with another live opponent's.

**Hysteresis.** An opponent near a boundary must not flip bucket every hand.
Require the shrunk stat to cross the split by a dead-band of `0.02` before
reclassifying, and require the new classification to hold for `10` consecutive
hands. A bot that changes its whole strategy every third hand is worse than one
that never changes it. The `0.02` dead-band and the `10`-hand hold are
**unmeasured starting values chosen for this design**; V2 measures
reclassification frequency directly and tunes both.

**What the dead-band is not: a noise control. The bucket boundary's own noise
exposure, stated.** The margin-versus-interval discipline further down this
section is applied to flags; the same arithmetic applied here gives a much worse
answer,
and it is stated rather than left for a reader to derive. At the classification
gate — `confidence(vpip) ≥ 0.5`, which with Tier A's `s` = 50 inverts to
`n = 50·0.5/0.5 = 50` hands — the 95% half-width around `VPIP_SPLIT`'s 0.28 is
`w = 1.96·√(0.28·0.72/50)` = **±12.4pp**, which is 6.2 times the `0.02`
dead-band. Shrinkage does not rescue it: the shrunk rate moves only `c` of the
way to the raw rate, so its own half-width at that gate is `c·w` = **±6.2pp**,
still 3.1 times the band. The aggression axis is worse and is not gated at
all — `UNKNOWN` is assigned on `confidence(vpip)`, never on `confidence(afq)` — so
at the matching `afq` confidence of 0.5 (`s` = 25, `n` = 25) the half-width
around `AFQ_SPLIT`'s 0.50 is ±19.6pp raw and ±9.8pp shrunk.

**What that implies, and the choice this document makes.** Of the three
available responses — widen the band, raise the gate, or say why the interval is
the wrong comparator — this design takes the first two as unaffordable and
refuses the third:

- A band wide enough to cover the noise would have to be `0.062` on `vpip` and
  `0.098` on `afq`, an order of magnitude past `0.02`, and a dead-band that wide
  freezes most opponents in whichever bucket they were first given.
- A gate high enough to shrink the noise to the `0.02` band needs
  `confidence(vpip) ≥ 0.973`, i.e. `n = s·c/(1−c)` = **1,835 hands** on one
  opponent, and `confidence(afq) ≥ 0.989`, i.e. **2,351** `afq` opportunities.
  [Table C](#table-c-how-many-hands-each-stat-needs) already says that is out of
  reach, and `MIN_CLASSIFY_HANDS` would stop being a classification gate and
  start being a refusal to classify.
- The interval *is* the right comparator. The question "which side of the split
  is this opponent on" is exactly a question about a rate near a threshold, and
  the interval answers it: at the gate, near the split, it is close to a
  coin-flip.

**So the exposure is accepted, and bounded by what depends on it.** A
misclassification here costs one adjacent bucket's counter-strategy — which is
the thing that does reach play — rather than a fired flag: the flags name a
specific leak rather than act on one, being report-only diagnostics until Tier 2
as the next subsection sets out, and they carry that subsection's margin
discipline and their own higher gates besides. Three consequences a coding task
must keep:

- The `0.02` dead-band controls *flapping between hands*, not sampling error,
  and must never be described or tuned as though it controlled the latter.
- `report.py` must mark a bucket as near-boundary whenever the shrunk rate is
  within `c·w` of its split, so a person reading a profile sees the exposure
  instead of reading the bucket as settled.
- V2 measures reclassification frequency and V3 scores the model's predictions;
  neither validates the bucket label itself, and no result in
  [§6](#6-validation-before-it-touches-a-real-table) should be read as saying a
  near-boundary bucket was right.

**Exploit flags — orthogonal to the bucket.** The four buckets are coarse; the
money is often in one specific leak. Flags are independent booleans, each with
its own confidence gate. A flag fires only when *both* the confidence threshold
and the magnitude threshold are met.

**What a fired flag does, stated plainly: it is a report, not a change of play,
until Tier 2.** Nothing in this design reads a flag to alter what the bot does at
the table. `classify.py` emits flags beside the bucket
([§4.1](#41-architecture-and-module-boundaries)) and `report.py` prints them, but
`select.py` — the only module that reaches the engine — takes buckets and table
context, and [§4.5](#45-tiers-what-to-build-in-what-order)'s load rule reads
bucket labels alone. **Through Tier 0 and Tier 1 the flags are therefore
report-only diagnostics**: they tell a person reading a profile which specific
leak an opponent has, they give the per-flag accounting in
[§5.2](#52-mitigations-each-traceable-to-a-source) and
[§5.3](#53-the-one-risk-the-literature-does-not-cover) something to attribute
profit to, and that is the whole of their effect.
[§4.6](#46-what-each-bucket-means-in-plain-strategic-terms)'s flag table is, by
its own statement, a description of what the engine's output is expected to look
like and not an instruction to any module. **Tier 2** is the first tier at which
the engine receives a per-opponent model at all, so it is the earliest point at
which the rates underlying a flag reach play. Even there no flag-specific
consumer is specified: Tier 2 consumes per-public-history action frequencies,
not flags. Feeding a flag into play any earlier is a mechanism this document
does not contain, and the reconciliation that added it would have to name that
mechanism and show it meets "The forefront rule" in `CLAUDE.md`: reviewable
decision code, no model call on the live decision path, and no decision content
taken from stored model output.

| Flag | Condition | Confidence gate |
| --- | --- | --- |
| `OVERFOLDS_TO_3BET` | shrunk `fold_to_three_bet` exceeds `BASELINE[fold_to_three_bet]` by ≥ 0.15 | `confidence ≥ 0.6` |
| `NEVER_FOLDS_TO_3BET` | shrunk `fold_to_three_bet` below `BASELINE[fold_to_three_bet]` by ≥ 0.15 | `confidence ≥ 0.6` |
| `OVERFOLDS_TO_CBET` | shrunk `fold_to_cbet[flop]` exceeds `BASELINE[fold_to_cbet[flop]]` by ≥ 0.15 | `confidence ≥ 0.6` |
| `NEVER_FOLDS_POSTFLOP` | shrunk `wtsd` exceeds `BASELINE[wtsd]` by ≥ 0.15 | `confidence ≥ 0.6` |
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

**Why a margin is wide enough not to fire on noise, with the arithmetic shown.**
A flag must fire only when the opponent's rate sits further from `BASELINE` than
sampling error alone could have put it. Two steps check that, both from numbers
already in this document, and a reader should be able to reproduce every figure
below from [Table C](#table-c-how-many-hands-each-stat-needs) and the two lines
in [§4.3](#43-after-each-hand-the-update).

*Step 1 — what a shrunk margin asks of the raw data.* Rearranging the shrinkage
line with `c = n/(n+s)` gives
`(BASELINE·s + k)/(s + n) = BASELINE·(1−c) + (k/n)·c`: the shrunk rate is the
baseline and the raw rate blended by the confidence. So the shrunk rate is `m`
away from `BASELINE` only when the **raw** rate is `m / c` away from it. At the
`0.6` gate a 0.15 shrunk margin means a 0.250 raw margin; at the `0.7` gate a
0.05 shrunk margin means a 0.071 raw margin.

*Step 2 — how wide the interval is at the gate.* `confidence = n/(n+s)` inverts
to `n = s·c/(1−c)`, the fewest opportunities the gate admits. Table C's formula
inverts to a half-width `w = 1.96·√(p̂(1−p̂)/n)` at that `n`, read at the same
illustrative anchor `p̂` Table C uses for the stat. The margin is sound only if
the raw margin from step 1 exceeds `w`. Computed by `tools/check_design_numbers.py`,
the same script as Tables A–E, 2026-09-15.

| Flag | Stat, `s`, gate | Fewest opportunities at the gate | Half-width `w` there, at Table C's anchor | Margin | Raw margin it implies | Exceeds `w`? |
| --- | --- | --- | --- | --- | --- | --- |
| `OVERFOLDS_TO_3BET`, `NEVER_FOLDS_TO_3BET` | `fold_to_three_bet`, 25, 0.6 | 37.5 | 0.157 (`p̂` 0.60) | 0.15 | 0.250 | yes |
| `OVERFOLDS_TO_CBET` | `fold_to_cbet`, 25, 0.6 | 37.5 | 0.160 (`p̂` 0.50) | 0.15 | 0.250 | yes |
| `NEVER_FOLDS_POSTFLOP` | `wtsd`, 15, 0.6 | 22.5 | 0.179 (`p̂` 0.25) | 0.15 | 0.250 | yes |
| `NEVER_RAISES`, `three_bet` leg | `three_bet`, 25, 0.7 | 58.3 | 0.065 (`p̂` 0.07) | 0.05 | 0.071 | yes, barely |

**`NEVER_FOLDS_POSTFLOP` carries the same 0.15 margin as the rest because of
that check, and must not be given a narrower one.** A 0.10 margin there implies a
raw margin of 0.167, *inside* the 0.179 interval, so the flag could fire on
sampling error alone — the one thing these margins exist to prevent. `wtsd` is
the slowest stat in the set and its `s` = 15 gate admits
fewer opportunities than any other flag's, so it needs the widest margin, not
the narrowest.

**Three flags cannot be checked this way yet.** Table C anchors no `p̂` for
`fold_to_steal`, `limp` or `check_raise`. Taking the least favourable
`p̂ = 0.5`: `fold_to_steal`'s half-width at its gate is 0.160 and `limp`'s is
0.113, both below the 0.250 raw margin their 0.15 margins imply, so
`OVERFOLDS_BLINDS` and `LIMPS` clear at any anchor. `NEVER_RAISES`'s
`check_raise` leg does not: its 0.071 raw margin clears only while that stat's
baseline is below about 0.085, and fails at `p̂ = 0.5`. `NEVER_RAISES` needs
*both* legs, so it is no sounder than its `check_raise` leg until that baseline
is measured. Both of those figures are `check_raise`'s `PRIOR_STRENGTH` = 25
from [§4.3](#43-after-each-hand-the-update) at work: the leg's gate is `0.7`, so
it admits `n = 25·0.7/0.3 = 58.3` opportunities at fewest, and 0.085 is the `p̂`
at which `1.96·√(p̂(1−p̂)/58.3)` equals the 0.05/0.7 raw margin.

**A coding task must recompute the whole table above from measured `p̂` values
once Tier 0 has logged hands, and raise any margin that stops clearing its
interval.** The margins and gates — 0.15, the tighter 0.05 on `NEVER_RAISES`,
and the `0.6` and `0.7` confidence gates — remain **unmeasured starting values**,
to be tuned by the validation in
[§6](#6-validation-before-it-touches-a-real-table) and recorded in a config file
rather than in code. Tuning may raise a margin freely; it must never lower one
below the interval its gate implies.

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
  vpip        0.42  (conf 0.89)   raw 0.43
  pfr         0.11  (conf 0.89)   raw 0.10
  gap         0.31
  limp        0.38  (conf 0.83)
  three_bet   0.02  (conf 0.72)
  check_raise 0.01  (conf 0.85)
  afq         0.13  (conf 0.97)
  afq[flop]   0.18  (conf 0.87)
  wtsd        0.42  (conf 0.93)
  bucket      STATION
  flags       NEVER_FOLDS_POSTFLOP, LIMPS, NEVER_RAISES
```

Every number in that block is **invented and illustrates the report's format
only**. It is not data and not a claim about any player. It is, however, **one
single coherent hand history** rather than a set of individually plausible
numbers, and it must stay that way: nothing above is chosen, everything above is
*derived* from the counts below by the two lines in
[§4.3](#43-after-each-hand-the-update), `rate = (BASELINE·s + k)/(s + n)` and
`confidence = n/(n + s)`, with `s` each stat's `PRIOR_STRENGTH`. An example whose
counts cannot all come from the same 412 hands, or that fires a flag its own
confidences would have blocked, teaches a coding task the wrong thing.

**The counts the block is computed from.** `BASELINE` is pooled from the bot's
database ([§4.3](#43-after-each-hand-the-update)), so the example has to assume
values for it; where a stat has an anchor in
[Table C](#table-c-how-many-hands-each-stat-needs) the anchor is used, and the
other three are invented like the rest of the example. Rows below the rule are
not printed in the block above — the report prints a selection — and are here
because [§4.4](#44-bucketing-an-opponent)'s flags read them, so leaving them
unstated would leave it unchecked that the flags the example does *not* list are
correctly absent.

| Stat | `k` | `n` | `s` | Assumed `BASELINE` | Shrunk | `confidence` |
| --- | --- | --- | --- | --- | --- | --- |
| `vpip` | 177 | 412 | 50 | 0.30 | 0.42 | 0.89 |
| `pfr` | 41 | 412 | 50 | 0.20 | 0.11 | 0.89 |
| `limp` | 106 | 250 | 50 | 0.15 | 0.38 | 0.83 |
| `three_bet` | 0 | 63 | 25 | 0.07 | 0.02 | 0.72 |
| `check_raise` | 0 | 140 | 25 | 0.06 | 0.01 | 0.85 |
| `afq` | 92 | 768 | 25 | 0.30 | 0.13 | 0.97 |
| `afq[flop]` | 27 | 168 | 25 | 0.30 | 0.18 | 0.87 |
| `wtsd` | 89 | 205 | 15 | 0.25 | 0.42 | 0.93 |
| `fold_to_three_bet` | 5 | 9 | 25 | 0.60 | 0.59 | 0.26 |
| `fold_to_cbet[flop]` | 14 | 62 | 25 | 0.50 | 0.30 | 0.71 |
| `fold_to_steal` | 19 | 55 | 25 | 0.50 | 0.39 | 0.69 |

**The history those counts describe, so that no two of them contradict.** Across
**412** hands dealt, this opponent put money in voluntarily **177** times, and
those 177 break down as **106** limps, **41** preflop raises and **30** calls of
someone else's raise. They had the option to limp — no raise before them — in
**250** of the 412 hands. They faced exactly one open raise with chips behind
**63** times, and reraised none of them: the same 63 spots are the 30 calls plus
33 folds. Having open-raised 41 times, they faced a reraise **9** times. They
saw **205** flops: 155 of the 177 hands they invested in, plus 50 big blinds
that reached a flop unraised. Of those 205 flops they reached showdown **89**
times, faced a continuation bet **62** times, and were in **140** spots across
all three streets where they checked and then faced a bet — check-raising in
none of them. Their voluntary postflop actions number 168 on the flop, 118 on
the turn and 82 on the river, which with 400 preflop actions is the **768** of
the overall `afq`, of which **92** were a bet or a raise (41 preflop, 27 flop, 15
turn, 9 river). Every denominator above is inside the one it is drawn
from — that is the whole point of listing them.

**What the block then has to satisfy, and does.** Each confidence is `n/(n+s)`
for that stat's `PRIOR_STRENGTH` from [§4.3](#43-after-each-hand-the-update).
Every flag listed clears its own gate from
[§4.4](#44-bucketing-an-opponent) — `wtsd` 0.93 and `limp` 0.83 against the `0.6`
gates, `three_bet` 0.72 and `check_raise` 0.85 against the `0.7` gate — and
clears its margin: `wtsd` sits 0.172 above its baseline and `limp` 0.228, both
past 0.15, while `NEVER_RAISES` needs both of its legs 0.05 below theirs and gets
0.050 on `three_bet` and 0.051 on `check_raise` — barely, exactly as
[§4.4](#44-bucketing-an-opponent) warns that leg does. Every flag *not* listed is
correctly absent: `OVERFOLDS_TO_3BET` and `NEVER_FOLDS_TO_3BET` fail the `0.6`
confidence gate at 0.26, and `OVERFOLDS_TO_CBET` and `OVERFOLDS_BLINDS` pass
their gates but sit *below* their baselines rather than 0.15 above. The bucket
clears both the `0.5` `vpip`-confidence gate and `MIN_CLASSIFY_HANDS = 50`, and
is `STATION` because 0.42 is above `VPIP_SPLIT` and 0.13 below `AFQ_SPLIT` — on
both axes by more than the near-boundary width `c·w` of
[§4.4](#44-bucketing-an-opponent), so this profile is not a near-boundary call
and the report prints no such mark. The hands count also clears
`WARMUP_HANDS = 200` from [§5.2](#52-mitigations-each-traceable-to-a-source),
without which the bot would be playing `S_BASE` against them regardless.

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
be loaded at a table of another size.

**The multiplier that follows, stated rather than left to be discovered.** The
bot must work at every table size from 2 to 9 players
([§1](#1-goal-and-non-goals)), which is **eight seat counts**, and each seat
count needs **four strategies** — `S_BASE` plus the three counter-strategies in
the table below, `TAG` having none. **Four strategies × eight seat counts = 32
offline solver runs**, done once. [E5](#engine-requirements) asks the cost of
*one* run; what Tier 1's feasibility actually turns on is that cost times 32.

**The cost bound this has to clear, which is the operator's and not negotiable
here.** No multi-day computing: a playable bot must be reachable in **hours on
one laptop** (operator, 2026-09-15). That is the cap on the *whole* offline
build, not on one run, so with 32 runs in the plan it divides down to a single
run of a few **minutes** — 32 runs at ten minutes each is 5.3 hours already,
and 32 runs at an hour each is 32 hours, which is 1.3 days of continuous laptop
time and breaches the no-multi-day cap on its own. **Tier 1 as specified is
therefore conditional on an engine whose single solve against fixed opponents
finishes in minutes**, and a coding task
that finds otherwise must stop and report it rather than start a solve that
cannot finish inside the cap. [E5](#engine-requirements) is the question that
settles it, and it must be answered for one run *and* for 32 against that cap.

**The decision that may remove the solve plan entirely is pending, and this
section does not pre-empt it.** `ENGINE_ALTERNATIVES.md` is under review and
recommends computing decisions at play time instead of solving strategies
offline at all; its numbers are its own and are deliberately not restated here.
**That document has not landed: it is not on `main` and not in this
repository's trunk.** It exists only on the branch `worker/7f09949cb56f`, and a
reader who cannot find the file beside this one should look there. What this
subsection is conditional on is the pending decision, which stands whether or
not the file has landed; no figure or claim here is drawn from its text.
If that recommendation is accepted, the 32 runs below do not happen and Tier 1's
"select among precomputed strategies" structure is what changes — not the stats,
the shrinkage, the buckets or the flags, which are what
[§4.2](#42-the-stat-table) to [§4.4](#44-bucketing-an-opponent) specify and are
engine-independent. **Read this subsection as conditional on that decision.**

**If 32 runs are unaffordable, what cutting actually saves.** The two honest
responses are to cut buckets or to narrow the seat counts Tier 1 covers, never
to load a strategy at a table size it was not solved for — and the second saves
less than it looks. Because this tier's own rule — "a strategy solved for a
different seat count must not be loaded at a table of another size", stated
where the solve plan is — a seat count dropped from Tier 1 still needs its
own `S_BASE` to play at all; what is dropped is only that seat count's three
counter-strategies. **Dropping one seat count from Tier 1 saves 3 runs, not 4**,
and dropping all of them from Tier 1 leaves a floor of **8 runs** — one `S_BASE`
per seat count — which is the least this design can be built on. Cutting
buckets, by contrast, saves 8 runs per bucket dropped, one at every seat count.

**The order any cut of the seat counts must follow, which is the operator's and
not a judgement call here.** The operator's table-size priority, stated
2026-09-15 and recorded as heater task `65bba741bf40`, verbatim: "i will be
playing mostly 6 player tables, followed by 8 or 9 player tables which can
honestly be treated the same, they are so close". Every size from 2 to 9 is
still required ([§1](#1-goal-and-non-goals)); what this settles is the *order* in
which they are built and the order in which they are given up. **Solve 6-handed
first; then 8- and 9-handed as one band; then every remaining seat count.** A cut
drops seat counts from the bottom of that order upward, never from the top, and
a seat count dropped from Tier 1 still keeps its `S_BASE` by the paragraph above.

**"Treated the same" is a priority, not a shared solve: 8 and 9 still need their
own runs.** The rule at the head of this tier — a strategy solved for one seat
count must not be loaded at a table of another size — is about what the solver
*faced*, not about how alike the two games feel to play. A 9-handed solve seats
eight archetypes against the bot, so its output carries an eight-opponent
multiway discount
([§2.4](#24-why-bluffing-is-the-wrong-primary-exploit-at-a-multiway-table)) and
an eight-opponent `⌈2n/3⌉` field; an 8-handed table presents seven of each. The
operator's words rank those two sizes together in priority; they do not merge the
solver's input, and nothing here reads them as doing so. The one condition that
would let a single 9-handed solve serve both: a measured comparison showing that
strategy loses less at an 8-handed table than dropping that band's three
counter-strategies loses — measurable by
[V5](#6-validation-before-it-touches-a-real-table) once Tier 1 exists, and until
it is measured the answer is two solves.

**At two players the design still applies, with two changes.** Heads-up is the
one case where the equilibrium argument in [§1](#1-goal-and-non-goals) does hold,
so `S_BASE` at that seat count carries the strongest guarantee anything in this
project has, and deviating from it is the plainest downside risk here — the
Libratus position in [§3.1](#31-pluribus-did-not-do-opponent-modelling-at-all)
applies with full force. First change: the multiway discount on bluffing is
simply absent, [Table B](#table-b-the-multiway-problem)'s one-opponent column
being the raw fold rate, so heads-up is the one seat count where a bluffing
exploit is not discounted away. Second: "predominantly" degenerates, because with
`n = 1` live opponent `⌈2n/3⌉ = 1` — the bot loads that opponent's
counter-strategy once they have passed warm-up **and** are classified, and
`S_BASE` while either gate is unmet, which between 50 and 199 stored hands means
while warm-up is unmet even though they are no longer `UNKNOWN`. Everything else
is unchanged: every stat, bucket and flag is keyed on one opponent already.

The archetypes are defined as
*action-frequency perturbations of the blueprint*, in exactly DBBR's sense: take
the blueprint
strategy and shift its action probabilities to match the bucket's measured
profile.

| Strategy | Trained against | The bot loads it when… |
| --- | --- | --- |
| `S_BASE` | self-play (the blueprint) | any opponent has not passed warm-up or is `UNKNOWN`, or the table is mixed |
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
load a counter-strategy only if **every** live opponent has passed warm-up
(`hands_dealt` at or above `WARMUP_HANDS = 200`,
[§5.2](#52-mitigations-each-traceable-to-a-source)) **and** **every** live
opponent is classified (none `UNKNOWN`) **and** at least `⌈2n/3⌉` of the `n` live
opponents share the bucket. Otherwise `S_BASE`. The warm-up conjunct is not
implied by the classification one and has to be written out: `UNKNOWN` clears at
`MIN_CLASSIFY_HANDS = 50` hands while warm-up clears at 200, so an opponent with
between 50 and 199 stored hands is classified and still not warmed up, and it is
the warm-up conjunct that refuses the counter-strategy there.
[§5.2](#52-mitigations-each-traceable-to-a-source) says which of the two binds
where. The `⌈2n/3⌉` fraction is an **unmeasured design choice** encoding "a clear
majority of the live field", to be tuned against
[V5](#6-validation-before-it-touches-a-real-table).

**This is the one place on the live decision path where the live field is looked
at collectively, and it stays inside the rule.** (Offline, two reports read the
live field collectively as well, and neither touches a live decision:
[V5](#6-validation-before-it-touches-a-real-table)'s bluff frequency by number of
live opponents, and the "Multiway gate" column in
[§4.6](#46-what-each-bucket-means-in-plain-strategic-terms).) It counts bucket
labels that were each assigned to one opponent on that opponent's own rates; no
rate is combined with another live opponent's rate, and the output is a
strategy handle. A coding task must not
"improve" this by pooling the live opponents' rates into a baseline or a split
to decide what to load: a pool whose criterion is who is seated is not the
observed population the forefront rule's "What may be coded" names, which is
the whole database with being seated never the criterion for inclusion
([§1](#the-forefront-rule-and-this-design)).

**Where the forefront rule binds hardest, and how it is met.** Defining the
archetype perturbation ("calls up-weighted") is a judgment about poker, and the
rule requires an archetype to be derived rather than hand-written. It is kept
inside the rule by these constraints, which a coding task must not relax:

- The perturbation is **derived from measured statistics**, not chosen by hand:
  the archetype's action frequencies are set to the pooled shrunk rates of real
  opponents in that bucket, from the bot's own database. **That pooling is
  population-level, and that is exactly what the rule names.** It runs offline,
  over every stored opponent in the bucket — the whole database, not a pool cut
  down to the players at any table the bot is sitting at — and what it produces
  is an archetype derived from measured action frequencies alone and handed to
  the engine's solver, which the forefront rule's "What may be coded" permits
  explicitly. Cutting the pool down to the opponents in the current hand would
  make being seated the criterion for inclusion, which that same bullet
  refuses; see [§1](#the-forefront-rule-and-this-design).
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
| Opponent started the hand with fewer than `MIN_STACK_BB = 5` big blinds | Their fold/call frequencies are structurally distorted: a stack that short is all-in or folding, never choosing. Exclude the hand from all counters. The floor of 5 big blinds is an unmeasured starting value |

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
| **Confidence gate on every flag.** No flag is set below its threshold, so nothing thin enough to be noise is ever reported as a leak — and until Tier 2 a set flag is a diagnostic rather than an exploit, per [§4.4](#44-bucketing-an-opponent) | DBR: 1-Step confidence (act after one observation) overfits; 10-Step and 0-10 Linear do not ([Johanson & Bowling 2009](#s-johanson2009), §6) |
| **Warm-up period.** Play `S_BASE` against an opponent until `WARMUP_HANDS = 200` hands have been recorded of *that opponent* — per opponent and lifetime; see below the table | DBBR used `T = 1000` ([Ganzfried & Sandholm 2011](#s-ganzfried2011), §5), also per opponent. 200 is a deliberately shorter warm-up, not a point at which Table C says anything has converged; the arithmetic is below the table. A tuning parameter |
| **Deviation cap.** A global `Pmax`-equivalent limiting how far any counter-strategy may sit from `S_BASE` | DBR's `Pmax` "allows us to set a tradeoff between" exploitation and exploitability |
| **Exploit only where observed.** Where a stat has no observations, the bot must fall back to `S_BASE` for that decision, not to the prior-filled model | Directly from the DBBR river failure above |
| **Win-rate switch.** Track realised bb/100 with exploitation on versus off, per bucket and per flag. Disable any exploit whose measured contribution is not positive over a meaningful sample. Through Tier 1 the only exploit there is to disable is a bucket's counter-strategy; the per-flag figure is a report until Tier 2 gives a flag something to switch off ([§4.4](#44-bucketing-an-opponent)) | "only attempting to exploit the opponent if a win rate above some threshold is attained" (ibid., §5) |
| **Default to the blueprint.** Unknown opponent, mixed table, or any uncertainty: `S_BASE` | Pluribus beat elite humans with no opponent model at all ([Brown 2020](#s-brown2020), §6.6) |

**What `WARMUP_HANDS` counts, and what 200 buys.** The count is the opponent's
stored `hands_dealt` from [§4.2](#42-the-stat-table): **per opponent, and
lifetime** — accumulated across every table and session that opponent has been
seen at, never reset when a session ends. Per opponent because that is what
every other gate in this design counts (`MIN_CLASSIFY_HANDS`, and the
`confidence` gates, which are all counts of evidence about one person) and what
DBBR's `T` counted; lifetime because resetting would throw away evidence the
database already holds, and [§4.3](#43-after-each-hand-the-update)'s decay is
already the mechanism for making old evidence count less. Per *table* it is not:
`opponent_id` is the player name, not the seat or the table
([§7](#7-questions-for-the-operator), Q2).
At a table this reads as `S_BASE` until every live opponent has passed its own
warm-up, and [§4.5](#45-tiers-what-to-build-in-what-order)'s load rule carries
warm-up as a conjunct of its own for exactly that reason. **Warm-up and the
classification gate are two gates, not one, and they clear at different
points — 200 hands against 50 — so which one binds has to be stated rather than
assumed.** `UNKNOWN` clears at `MIN_CLASSIFY_HANDS = 50` hands, and at that same
50 the Tier A `confidence(vpip) ≥ 0.5` threshold is reached too, so the two
halves of the `UNKNOWN` test clear together
([§4.4](#44-bucketing-an-opponent)). Warm-up clears at 200. **Below 50 hands
both gates refuse; from 50 to 199 they disagree and warm-up is the gate that
binds**, because the opponent is classified by then and warm-up alone is what
holds the bot on `S_BASE`; from 200 on, neither of the two holds it back. Warm-up
is therefore the later gate throughout, and the one whose value decides when
exploitation against a given opponent can start at all, for as long as it stays
above `MIN_CLASSIFY_HANDS`. Tuning it moves the gate that actually binds, which
is why it is not a formality.

200 is **not** a convergence point from
[Table C](#table-c-how-many-hands-each-stat-needs). Table C's ±5pp rows need 323
hands for `vpip` and 246 for `pfr`. At
200 hands the same formula, `w = 1.96·√(p̂(1−p̂)/n)`, gives ±6.4pp on `vpip` at
its 0.30 anchor and ±5.5pp on `pfr` at 0.20 — Tier A is inside ±6.4pp and
no tighter. That is the width 200 actually buys; it is chosen as a deliberately
shorter warm-up than DBBR's 1000 hands, and remains a tuning parameter.

### 5.3 The one risk the literature does not cover

**Humans adapt; the bots in these papers did not.** AlwaysRaise, GUS2 and
Tommybot never noticed they were being exploited. A human who works out that the
bot reraises them every time will start trapping. None of the cited results
speak to this.

Required responses, all cheap:

- **Decay** ([§4.3](#43-after-each-hand-the-update) step 2) so that stale
  observations lose weight.
- **Per-exploit profit tracking.** Attribute realised profit to the
  counter-strategy in play and to each flag set on that opponent. If
  `OVERFOLDS_TO_3BET` stops earning against a specific opponent, that has to
  show up — as a report while flags are report-only
  ([§4.4](#44-bucketing-an-opponent)), and as the flag going stale and switching
  off for that opponent once Tier 2 lets a flag reach play. This is the
  counter-adaptation detector, and it costs one extra column.
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
| E5 | What is the cost of one solver run against fixed opponents — minutes, hours, or days? Tier 1 needs **32 of them**: four strategies × eight seat counts, 2 to 9 players ([§4.5](#45-tiers-what-to-build-in-what-order)). Answer for one run and for 32, and answer both against the cap: **hours on one laptop for the whole offline build, no multi-day computing** (operator, 2026-09-15), which at 32 runs means a single run of minutes. A "days" answer fails the cap outright; an "hours" answer fails it at 32 | Tier 1 feasibility |
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
  pooling the rates of the players at the current table would make being seated
  the criterion for inclusion, which the forefront rule's observed-population
  bullet refuses ([§1](#the-forefront-rule-and-this-design)).
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
across data quantities from 100 to 1,000,000 observed games. The name `1-Curve`
is the paper's, for one of the functions it tested; that it is the s-Curve at
`s` = 1 is the paper's own statement rather than an inference here, §5.2 reading
"The s-Curve function returns Pmax × (nI/(s + nI)) for any constant s; in this
experiment, we used s = 1".

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

**`tools/check_design_numbers.py` is the source of truth for every derived
number in this document, and it must exit 0 before any edit to this file
lands.** Run it with `python3 tools/check_design_numbers.py` (standard library
only; `tests/test_design_numbers.py` runs it under the test suite, so a full
`pytest` run covers it too). It holds every constant this document
declares — `PRIOR_STRENGTH` per stat, the confidence and flag gates, the flag
margins, `VPIP_SPLIT`, `AFQ_SPLIT`, the hysteresis band and hold, `WARMUP_HANDS`,
`HALF_LIFE`, the pool and stack gates, the Table C opportunity rates and anchors,
the seat counts, the strategy list and the Tier 0 example's counts — in one
place and recomputes from them, naming any printed value that disagrees:
**every cell of Tables A–E and of the flag tables, every figure in the Tier 0
worked example including its hand history and the flags it does and does not
fire, and every figure quoted in the prose that is computed from a constant or
restates one.** Its scope stops there, and the boundary is worth stating
plainly: it does **not** check figures taken from the
[Sources](#sources) — those are checked against the papers by citation, not by
arithmetic — nor section numbers, dates, or the numbering of tiers, steps and
validation items. The rule that follows from that,
and it is not optional: **a constant is changed in the script and in the prose
together, in one edit, and the script is what says the prose is still right.**
Adding a derived figure to this document without adding its check to the script
is how the six review rounds before this one each found a stale number.

Two conventions the script enforces so that "disagrees" is well defined. Every
figure is rounded **half-up** to the precision the document prints it at — 6.25%
prints as 6.3%, not 6.2% — and every figure is computed from **unrounded**
inputs, never from another figure's printed value.

| Number | Where it comes from |
| --- | --- |
| Tables A, B, C, D, E, the flag margin-versus-interval table in [§4.4](#44-bucketing-an-opponent), and the inline `0.5^(1/3) ≈ 0.794` reading of them | Computed by `tools/check_design_numbers.py`, 2026-09-15, which also re-checks them on every run. Formulas are stated inline beside each table; all are elementary arithmetic (binomial standard error, independent-event products, Beta posterior means) |
| Table C's anchor `p̂` column (0.30, 0.20, 0.07, 0.60, 0.50, 0.25) | **Illustrative anchors, not measured or cited.** Labelled as such beside the table; the interval width barely moves across `p̂` in 0.2–0.8 |
| Table C's opportunities-per-hand column (`three_bet` 0.15, `fold_to_three_bet` 0.08, `fold_to_cbet` 0.030, `wtsd` 0.187) | **Two measured, two illustrative.** `fold_to_cbet` 0.030 and `wtsd` 0.187 are the nine-handed pooled rates in [`OPPONENT_BASELINE.md` §2](OPPONENT_BASELINE.md#2-corpus-a-the-2009-no-limit-population-per-table-size) — its "FtCB chances per hand" and "Flops seen per hand" columns, over 70,685 nine-handed hands — measured on the sample its §1 describes, which lacks PartyPoker and leans high-stakes; adopting them is that document's §5 recommendation 2. `three_bet` 0.15 and `fold_to_three_bet` 0.08 are **illustrative estimates, not measured or cited**, because that measurement does not reach their denominators; no source exists for them, and they are labelled as such beside the table. Each of the four is to be replaced by `denominator / hands_dealt` from the bot's own logged hands. The "Hands needed" column scales inversely with them. Only `vpip` and `pfr` escape the placeholder, at 1.00, and only because their [§4.2](#42-the-stat-table) denominator is "opponent was dealt in" |
| The bucket boundary's noise exposure — ±12.4pp raw and ±6.2pp shrunk on `vpip` at the `0.5` gate, ±19.6pp and ±9.8pp on `afq`, and the 1,835 hands / 2,351 opportunities a `0.02`-tight gate would need ([§4.4](#44-bucketing-an-opponent)) | Computed by `tools/check_design_numbers.py` from `VPIP_SPLIT`, `AFQ_SPLIT`, `PRIOR_STRENGTH`, the `0.5` gate and the `0.02` band, by the same `n = s·c/(1−c)` and `w = 1.96·√(p̂(1−p̂)/n)` used for the flag margins |
| **Hours on one laptop for the whole offline build, no multi-day computing** ([§4.5](#45-tiers-what-to-build-in-what-order), [E5](#engine-requirements)) | **The operator's stated cap, 2026-09-15**, not a derived or negotiable figure. It is what E5's answer has to clear, and what makes Tier 1's 32 runs conditional on a minutes-long single solve |
| The table-size priority — 6-handed first, then 8- and 9-handed as one band, then the rest ([§4.5](#45-tiers-what-to-build-in-what-order)) | **The operator's stated priority, 2026-09-15**, recorded as heater task `65bba741bf40` and quoted verbatim at its point of use. Not derived and not negotiable here; it fixes only the order of the solve plan, never which seat counts are required |
| 32 solver runs, the 3 saved by dropping a seat count, and the 8-run floor ([§4.5](#45-tiers-what-to-build-in-what-order)) | Computed by `tools/check_design_numbers.py` from the four strategies and the eight seat counts (2 to 9 players). The 3 rather than 4 is forced by the same section's rule that a strategy solved for one seat count must not be loaded at another, so a dropped seat count keeps its `S_BASE` |
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
| `HALF_LIFE = 2000`, `PRIOR_STRENGTH` values (50/25/15, which are also the s-Curve `s`), `WARMUP_HANDS = 200`, `MIN_CLASSIFY_HANDS = 50`, all flag margins (0.15/0.05) and flag confidence gates (0.6/0.7), the `confidence < 0.5` `UNKNOWN` gate, `MIN_STACK_BB = 5`, the 70/30 V3 holdout split, and `VPIP_SPLIT` and `AFQ_SPLIT` until the bootstrap in [§4.4](#44-bucketing-an-opponent) replaces them with measured population medians | **Starting values chosen for this design, not measured.** Every one is labelled as such at its point of use as well as here, belongs in a config file, and is to be tuned by the validation in [§6](#6-validation-before-it-touches-a-real-table). `VPIP_SPLIT = 0.28` is the one part-exception: it is the *approximate* complement of the literature's 72% fold threshold — approximate because the two rates do not sum to 1 (see [§2.2](#22-the-two-axes-that-have-literature-behind-them)) — and it stands only until V4 corrects it or the bot's own population replaces it |
| The example `pokerbot profile` output in [Tier 0](#45-tiers-what-to-build-in-what-order) (412 hands, 0.42 vpip, and the rest) | **Invented, and only illustrates the report's format.** Not data, not a claim about any player. What is invented is the count table beside it — one coherent 412-hand history, every denominator inside the one it is drawn from — plus the three assumed `BASELINE` values that Table C has no anchor for. Every rate and every confidence printed is then *computed* from those counts by [§4.3](#43-after-each-hand-the-update)'s two lines, and `tools/check_design_numbers.py` recomputes all of them, the bucket, and every flag's presence or absence |
