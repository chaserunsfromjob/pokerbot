# Evaluation strategy

How we find out whether this bot is any good, without needing thousands of hands
against real humans to do it.

This is a design document, not code. It is written so that a later coding task
can build the harness without re-deciding anything. It makes no assumptions
about the internals of the vendored engine; everywhere it needs something from
the engine, it says so as a named requirement in
[Engine requirements](#engine-requirements).

It does not replace `tests/ground_truth/`. That fixture checks that a flush
really does beat a straight. This document is about the thing that fixture
cannot check: whether the bot *plays* well.

---

## In plain words, before the jargon

There are two completely different questions you can ask about a poker bot, and
the methods for answering them have almost nothing in common.

The first is **"how badly could a perfect enemy beat this bot?"** You answer it
by building the single nastiest possible opponent, aiming it at the bot, and
measuring the damage. This is the question the famous poker-AI papers are
built around. It has a precise answer, and that is its attraction. It is also
the wrong question for this project, for two reasons: computing that answer
exactly takes computing resources this project does not have, and the answer
only *means* anything at a two-player table. Our table has three to nine people
at it.

The second is **"how much money does this bot win from these particular
opponents?"** That is the question this project actually cares about, because
the goal in `CLAUDE.md` is to beat real humans at a table of three or more, not
to be unbeatable. It is an easier question to compute and a much harder
question to *measure*, because poker is so wildly random that a bot can lose
for thousands of hands while playing better than everyone at the table.

That randomness is the whole problem. A single hand of no-limit hold'em can
swing a hundred big blinds. So if you play a new version of the bot for a
thousand hands, see it win, and conclude the change was an improvement, you
have learned essentially nothing — you have measured luck. Published work makes
this concrete: a poker AI that beat five elite professionals by a margin the
authors call "very high" needed ten thousand hands *plus* a variance-reduction
technique to reach a p-value of 0.028. And of the two individual professionals
whose results that work reports separately, only one clears the same bar — a
one-tailed t-test at 95% — at 40 ± 22 mbb/game, p = 0.033; the other, at
25 ± 20 mbb/game, p = 0.107, is not distinguishable from break-even
([Brown 2020](#s-brown2020), §6.6).

So the plan has three parts.

**Part 1** surveys how the research field actually measures playing strength
and what each method costs.

**Part 2** specifies a harness a solo builder can finish in weeks: a set of
rule-based fake opponents that imitate specific human mistakes, a way of
dealing the same cards to two versions of the bot so their scores can be
compared fairly, and a stated arithmetic rule for deciding whether a change
helped — replacing "the win rate looks higher now". It also does the sum that
turns all of that into hours on the laptop, because the version of this harness
that tests everything against everything would take about ten days per change,
and the version that fits in a night is a deliberately smaller one. **Roughly
113,000 hands, about four hours, is the shape of a run that decides whether a
change is kept.**

**Part 3** covers the operator's firm requirement that the bot work at every
table size from two to nine players and with real no-limit bet sizes, and what
that forces the harness to do. Short version: the single biggest measured
weakness in published no-limit bots comes from bet sizes the bot was not built
to expect, so a harness that only ever shows the bot familiar bet sizes will
score it far too kindly.

Two terms used throughout, explained once:

- A **big blind** is the compulsory bet that opens a hand; it is poker's unit of
  money. Win rates are quoted in thousandths of a big blind per hand, written
  **mbb/hand**. Published poker work uses this and one variant of it:
  10 mbb/hand is the same thing as 1 big blind per 100 hands
  ([Burch et al. 2018](#s-aivat), Table 5 caption).
- A **confidence interval** is the honest way of writing a measurement: not "the
  bot wins 30 mbb/hand" but "the bot wins somewhere between 5 and 55 mbb/hand,
  and there is a 1-in-20 chance the truth is outside even that". Every number
  this harness produces carries one. A win rate without an interval beside it
  is not a result.

---

## Contents

1. [Goal and non-goals](#1-goal-and-non-goals)
2. [Part 1 — How the research field measures strength](#2-part-1--how-the-research-field-measures-strength)
   - [2.1 The unit](#21-the-unit)
   - [2.2 Exploitability and exact best response](#22-exploitability-and-exact-best-response)
   - [2.3 Local best response: a cheap lower bound](#23-local-best-response-a-cheap-lower-bound)
   - [2.4 Variance reduction: duplicate, baseline, MIVAT, AIVAT](#24-variance-reduction-duplicate-baseline-mivat-aivat)
   - [2.5 Win rate with honest statistics](#25-win-rate-with-honest-statistics)
   - [2.6 What a head-to-head number does not tell you](#26-what-a-head-to-head-number-does-not-tell-you)
   - [2.7 What is and is not realistic solo](#27-what-is-and-is-not-realistic-solo)
3. [Part 2 — The harness](#3-part-2--the-harness)
   - [3.1 Architecture and module boundaries](#31-architecture-and-module-boundaries)
   - [3.2 The persona set](#32-the-persona-set)
   - [3.3 The forefront rule and the personas](#33-the-forefront-rule-and-the-personas)
   - [3.4 The deal controller](#34-the-deal-controller)
   - [3.5 The decision rule: is this change an improvement?](#35-the-decision-rule-is-this-change-an-improvement)
   - [3.6 The run budget: turning hands into hours](#36-the-run-budget-turning-hands-into-hours)
   - [3.7 Tiers: what to build, in what order](#37-tiers-what-to-build-in-what-order)
4. [Part 3 — Table sizes 2-9 and true no-limit sizing](#4-part-3--table-sizes-2-9-and-true-no-limit-sizing)
   - [4.1 Table size is an axis, not a setting](#41-table-size-is-an-axis-not-a-setting)
   - [4.2 Why duplicate dies past three seats](#42-why-duplicate-dies-past-three-seats)
   - [4.3 True no-limit sizing, and the biggest measured weakness in published bots](#43-true-no-limit-sizing-and-the-biggest-measured-weakness-in-published-bots)
   - [4.4 Stack depth](#44-stack-depth)
   - [4.5 Correctness invariants that come before any strength number](#45-correctness-invariants-that-come-before-any-strength-number)
5. [How this fits the opponent model](#5-how-this-fits-the-opponent-model)
6. [How this harness lies to you](#6-how-this-harness-lies-to-you)
- [Engine requirements](#engine-requirements)
- [Decisions that were open, and where they now live](#decisions-that-were-open-and-where-they-now-live)
- [Sources](#sources)
- [Provenance of every number in this document](#provenance-of-every-number-in-this-document)

---

## 1. Goal and non-goals

**Goal.** A repeatable, automated measurement that answers one question with a
stated error bar: *does version B of this bot make more money than version A,
across table sizes two to nine, against opponents that make the mistakes real
humans make?* And a second, weaker question that is much cheaper to answer:
*is this bot losing badly to something obvious?*

**Non-goals, stated so a later task does not drift into them:**

- **Not** computing the bot's exact exploitability. [§2.2](#22-exploitability-and-exact-best-response)
  shows the cost, and [§2.2](#22-exploitability-and-exact-best-response) also
  shows the concept stops meaning what people think it means above two players.
- **Not** proving the bot beats humans. Only humans can show that. The harness
  is what you run *before* spending human hours, so that the human hours are not
  spent discovering a bug.
- **Not** a leaderboard. The harness exists to accept or reject a change, not to
  produce a score to admire.

**The measurement this project needs is a bankroll measurement, not an
equilibrium measurement.** `CLAUDE.md` is explicit: beat real humans at a table
of three or more, do not chase a theoretical optimum that does not exist at that
table size. The research field has a name for this distinction and has measured
that the two goals genuinely disagree — see
[§2.6](#26-what-a-head-to-head-number-does-not-tell-you).

---

## 2. Part 1 — How the research field measures strength

### 2.1 The unit

Every number below is in **mbb/hand** — thousandths of a big blind won per hand
played. Published work also writes this as mbb/g ("per game") and as bb/100;
10 mbb/hand = 1 bb/100 ([Burch et al. 2018](#s-aivat), Table 5 caption). Some
older limit-hold'em papers use *milli-big-blinds per game* (mb/g) for the same
thing ([Johanson et al. 2011](#s-johanson2011), §6).

Two reference points from the literature, to calibrate what a "big" number is:

- **50 mb/g** is described as a rule of thumb among human professionals for what
  a strong player should aim to win, in heads-up limit hold'em
  ([Johanson et al. 2011](#s-johanson2011), §6). It is a rule of thumb reported
  in a paper, not a measured constant, and it is for *limit* play.
- **48 mbb/game** was Pluribus's measured win rate against five elite
  professionals in six-player no-limit, which the author calls "considered a very
  high win rate" ([Brown 2020](#s-brown2020), §6.6).

So a genuinely strong no-limit bot's edge is of the order of tens of mbb/hand.
Hold that beside [§2.5](#25-win-rate-with-honest-statistics), where the noise in
a single hand turns out to be of the order of *thousands* of mbb.

### 2.2 Exploitability and exact best response

**What it is.** A *best response* to a strategy is the strategy that beats it by
as much as possible. *Exploitability* is how much a worst-case opponent beats
you by, relative to what an unbeatable strategy would concede
([Brown 2020](#s-brown2020), §2.2). It is the field's gold-standard measure,
because it is a worst case: it cannot be flattered by a weak opponent.

**What it costs.** Computing an exact best response was considered intractable
in heads-up *limit* hold'em (9.17 × 10<sup>17</sup> game states) until an
accelerated algorithm brought it down to **76 CPU-days sequentially, or "just
over a day" on 72 processors** ([Johanson et al. 2011](#s-johanson2011), §4).
That is limit hold'em, the *smallest* variant. For heads-up no-limit, exact best
response "is currently not computationally feasible"
([Lisý & Bowling 2017](#s-lbr), abstract). This project plays multiway no-limit,
which is larger again.

**Why the concept also stops meaning what you want above two players.**
Exploitability generalises to more than two players as *NashConv*, the summed
gain each player could make by deviating ([Lanctot et al. 2017](#s-lanctot2017),
as defined in [Brown 2020](#s-brown2020), §2.2). But the property that makes
low exploitability *desirable* is specific to two-player zero-sum games: there,
and only there, a Nash equilibrium strategy is guaranteed not to lose, and two
players independently computing equilibria still jointly form one. With three or
more players, independently-computed equilibrium strategies need not combine
into an equilibrium at all — Brown's worked illustration is the Lemonade Stand
Game ([Zinkevich et al. 2011](#s-lemonade), via
[Brown 2020](#s-brown2020), §2.2). Finding an equilibrium in a zero-sum game
with three or more players is at least as hard as the two-player non-zero-sum
case, which is PPAD-complete ([Brown 2020](#s-brown2020), §2.2).

**Verdict for this project: do not build this.** It is out of reach
computationally and it is not the property we want. Recorded here so nobody
proposes it later without knowing the price.

### 2.3 Local best response: a cheap lower bound

**Local best response (LBR)** is the practical substitute, and it is the one
idea from the exploitability literature this project could actually use.

**What it is.** LBR does not compute a best response. It *plays* a real poker
strategy against the bot, choosing each action greedily: it maintains an exact
probability distribution over the bot's possible hole cards ("the bot's range"),
updates that distribution by Bayes' rule after every action the bot takes, and
picks whichever single action has the highest immediate expected value under the
assumption that everyone checks and calls to showdown afterwards
([Lisý & Bowling 2017](#s-lbr), Figure 1). Because it plays a legal strategy, it
can never win more than a true worst-case opponent would, so its win rate is a
**lower bound on the bot's exploitability** — a floor, never an overestimate.

**What it needs from the bot.** The bot's action-probability distribution, on
demand, for every hand it could be holding at a given public state. That is
engine requirement [X5](#engine-requirements) — the same capability the opponent
model design lists as its E1. If the engine can only sample an action rather
than report a distribution, LBR can still be run by averaging repeated samples
of the strategy at the same state, and this still yields a valid lower bound
([Lisý & Bowling 2017](#s-lbr), "Sampled soft translation").

**What it found.** Running LBR against the strongest publicly available no-limit
bots of the time — including the second- and third-placed entries in the 2016
Annual Computer Poker Competition — showed **every evaluated bot exploitable for
over 3180 mBB/h with 97.5% confidence**, from 2 × 50,000 duplicate hands. The
authors' own summary: folding every hand would have cost those bots at least
four times less money than playing their actual strategy against a worst-case
opponent ([Lisý & Bowling 2017](#s-lbr), §"Experimental evaluation").

**Its honest limits.** LBR's bound can be *uninformative*: against a bot with no
card abstraction, LBR lost 536 mBB/h, i.e. the lower bound was negative, while a
true best response within the same betting abstraction showed that bot was
exploitable for 90 mBB/h ([Lisý & Bowling 2017](#s-lbr), §"Full cards"). And
the algorithm as published is two-player: it tracks one opponent range and one
"amount asked". Extending it to a six-handed pot means tracking a range per live
opponent, which is not something the paper does or evaluates.

**Verdict for this project: Tier 3, heads-up only, as a red-flag detector.** See
[§3.7](#37-tiers-what-to-build-in-what-order).

### 2.4 Variance reduction: duplicate, baseline, MIVAT, AIVAT

These are the techniques that make win-rate measurement affordable. They all do
the same thing — shrink the error bar without changing what is being estimated —
and they differ enormously in what they demand of you. In cost order:

**(a) Common random numbers / duplicate.** Deal the *same* cards to both things
you are comparing. In two-player poker "duplicate" means replaying each deal
with the two players' hole cards swapped, and averaging the pair; the Annual
Computer Poker Competition plays "hundreds of millions of duplicate poker hands"
to separate entrants ([Davidson et al. 2013](#s-baseline), §5.2;
[Bard et al. 2013](#s-acpc)). In three-player it means averaging over all six
ways of assigning three players to three sets of hole cards
([Davidson et al. 2013](#s-baseline), §5.2). Cost: a deterministic dealer and a
replay facility. Nothing else.

**(b) Baseline control variates.** Play a *control agent* against itself on
exactly the same deals, and subtract its self-play result, scaled by the
measured covariance. Because the game is zero-sum and every seating is equally
likely, the control agent's expected self-play value is exactly zero, so
subtracting it cannot bias the answer ([Davidson et al. 2013](#s-baseline),
§4.1). Requirements: a reproducible random seed and *any* computer agent for the
domain. No hand-crafted value function, no knowledge of anyone's strategy.

  This is the one designed for our situation. On the 2011 ACPC three-player limit
  data (180,000 hands), baseline **beat duplicate for all nine competitors**,
  reducing the standard error by between **21.78% and 49.68%**, and never did
  worse than the raw average. Duplicate, by contrast, *increased* the standard
  error in over half the summaries, by as much as 40.41%
  ([Davidson et al. 2013](#s-baseline), Table 1). The authors attribute this to
  the six-way duplicate not being the best way to combine player orderings, and
  note that baseline "eliminates the complexity involved with creating duplicate
  matches" in games with more than two agents.

**(c) MIVAT.** Control variates applied to *chance* events — subtract a value
estimate for the cards that were dealt, so a good hand is not automatically a
good result. Requires an arbitrary heuristic value function defined after chance
events, and stays unbiased regardless of how bad that function is
([Burch et al. 2018](#s-aivat), §"MIVAT and Imaginary Observations").

**(d) AIVAT** — the technique the brief asks us to verify, and the one Pluribus
used.

  **What it actually is.** AIVAT ("action-informed value assessment tool") is a
  provably unbiased, low-variance estimator of an agent's value in an
  imperfect-information game. It combines three things: MIVAT's control-variate
  correction for chance events; *imaginary observations* — using knowledge of a
  player's strategy to evaluate, from one observed hand, all the other hands that
  player could have held on that same line, with the opponent's reach
  probabilities cancelling out; and, the new part, **MIVAT-like correction terms
  for the players' own non-terminal actions**, which neither earlier technique
  addressed ([Burch et al. 2018](#s-aivat), abstract and §"AIVAT"). Unbiasedness
  matters for a reason worth stating: an unbiased estimator is *truthful*, so an
  agent cannot make itself look better by playing to game the measurement
  ([Burch et al. 2018](#s-aivat), §"Background").

  **What it demands.** (i) A heuristic value function for states and actions;
  (ii) the **explicit strategy** of a known subset of the players — chance plus
  at least the agent being evaluated; (iii) a partition of game states that share
  the same public information. In their own heads-up no-limit experiments the
  authors could "only present results for AIVAT analysis using the strategy of
  one agent", because of the branching factor of the chance events
  ([Burch et al. 2018](#s-aivat), §"No-limit Texas Hold'em with Bots").

  **What it delivered.** In heads-up no-limit over 1,000,000 games, raw chip
  counting had a per-hand standard deviation of 25.962 chips; AIVAT with one
  agent's strategy brought that to 8.095 — **a bit more than a 68% reduction**,
  which is the paper's own phrasing, and **68.8%** exactly
  (1 − 8.095 ÷ 25.962 = 0.688, computed 2026-09-15). With the stronger
  value estimates available from DeepStack, the reduction was **85%**
  ([Burch et al. 2018](#s-aivat), Table 3 and
  §"No-limit Texas Hold'em with Humans"). Those two figures are exactly where the
  paper's headline claims come from: a 68% cut in standard deviation means you
  need 0.102× the hands for the same significance (≈10×), and an 85% cut means
  0.023× (≈44×) — the paper states both, as "ten times less data" and "a factor
  of forty" ([Burch et al. 2018](#s-aivat), conclusions).

  **It works at more than two players.** This is the part worth pinning down,
  because the AIVAT paper's own experiments are all heads-up. Pluribus, a
  *six-player* no-limit bot, used AIVAT for its human evaluation: "In all
  experiments, we used the variance-reduction technique AIVAT to reduce the luck
  factor in the game and measured statistical significance at the 95% confidence
  level using a one-tailed t-test" ([Brown 2020](#s-brown2020), §6.6, citing the
  AIVAT paper as reference [32]).

  **What it bought, in human terms.** In DeepStack's evaluation — 33 players from
  17 countries, 44,852 games — the aggregate result was already significant at
  4 sigma from raw chip counts; AIVAT pushed it to **20 sigma**. The
  per-player claim is narrower than "significant for individual players" and is
  worth quoting exactly: AIVAT estimated DeepStack ahead of **all 11 players who
  completed the required 3,000 hands**, and those individual victories were
  2-sigma significant for **all but one of them** — a per-player result that no
  previous man-machine competition, which needed the aggregate, had managed
  ([Burch et al. 2018](#s-aivat), §"Doyle's Game", Table 5). In a freezeout format, AIVAT produced a significant result from **28
  matches**, where the raw 14-wins-14-losses record separated nothing at all
  ([Burch et al. 2018](#s-aivat), Table 6).

**Summary table of what each costs.**

| Technique | Needs | Works at 2-9 players? | Demonstrated reduction |
| --- | --- | --- | --- |
| Common random numbers | Seeded dealer | Yes | Not separately reported |
| Duplicate | Seeded dealer + replay with permuted seats | Degrades — see [§4.2](#42-why-duplicate-dies-past-three-seats) | 3-player: sometimes negative, worst −40.41% ([Davidson 2013](#s-baseline), Table 1) |
| Baseline | Seeded dealer + any control agent | Yes, designed for it | 3-player: 21.78%–49.68% SE reduction ([Davidson 2013](#s-baseline), Table 1) |
| MIVAT | Heuristic value function after chance events | In principle | HUNL: 18% SD ([Burch 2018](#s-aivat), §"No-limit Texas Hold'em with Bots") |
| AIVAT | Value function + explicit strategy of a player subset + public-state partition | Yes — Pluribus used it 6-handed | HUNL: 68%, or 85% with good value functions |

### 2.5 Win rate with honest statistics

The reason all of the above exists is that raw poker win rates are almost
unmeasurable at small sample sizes. Here is the arithmetic, computed from
published standard deviations rather than asserted.

**Step 1: how noisy is one hand?** Four figures derived from published results
(derivations in the [provenance table](#provenance-of-every-number-in-this-document)):

| Setting | Per-hand standard deviation |
| --- | --- |
| Heads-up no-limit, raw chip count | ≈ 12,981 mbb |
| Heads-up no-limit, after AIVAT | ≈ 4,047.5 mbb |
| Six-player no-limit, after AIVAT (5 humans + 1 AI) | ≈ 2,500 mbb |
| Six-player no-limit, after AIVAT (1 human + 5 AI) | ≈ 1,500 mbb |

Compare that with the 48 mbb/hand edge Pluribus had over elite professionals.
**Compare it against the right row.** That 48 is a six-player no-limit,
post-AIVAT number, so the like-for-like row is the third one: **2,500 against 48,
a ratio of about 52**. That is the honest statement of the problem — even in the
best-measured setting published, with the best variance reduction published, one
hand of noise is fifty times the whole edge. The raw heads-up row is 12,981,
which is 270 times that same 48, but it is a *different* setting and the two
numbers should not be divided as though they described one experiment; read it
only as the order of magnitude that applies before any variance reduction, which
is where this project starts.

**Step 2: how many hands does that imply?** For a two-arm comparison at the
conventional two-sided 5% significance and 80% power, the required hands per arm
is `n = 2σ²(z₀.₉₇₅ + z₀.₈₀)² / Δ²`, with `(z₀.₉₇₅ + z₀.₈₀)² = 7.8489` — every
table below is computed at full precision (7.848879734…), which is what the
cells reproduce from. Computed:

| σ (mbb/hand) | Δ=10 | Δ=25 | Δ=50 | Δ=100 | Δ=200 |
| --- | --- | --- | --- | --- | --- |
| 12,981 (HUNL raw) | 26,451,723 | 4,232,276 | 1,058,069 | 264,517 | 66,129 |
| 4,047.5 (HUNL, AIVAT) | 2,571,647 | 411,464 | 102,866 | 25,716 | 6,429 |
| 2,500 (6-max, AIVAT) | 981,110 | 156,978 | 39,244 | 9,811 | 2,453 |
| 1,500 (6-max, AIVAT) | 353,200 | 56,512 | 14,128 | 3,532 | 883 |

**Read the top-left cell.** Detecting a 10 mbb/hand improvement by raw chip
counting in heads-up no-limit takes about 26 million hands per arm. This is the
single most important number in this document, and it is why "I played 500 hands
and it seemed better" is not evidence of anything.

**Step 3: pairing helps, a lot.** If both arms play the *same deals*, the
comparison is paired and the variance that matters is the variance of the
*difference*, which is `2σ²(1−ρ)` where ρ is the correlation between the arms'
results on the same deal. At σ = 12,981 and Δ = 50 mbb/hand:

| ρ | Hands per arm |
| --- | --- |
| 0.0 | 1,058,069 |
| 0.3 | 740,648 |
| 0.5 | 529,034 |
| 0.7 | 317,421 |
| 0.9 | 105,807 |

**ρ is not known and must be measured by the harness, not assumed.** It is
plausibly high when comparing two similar versions of the same bot on the same
deals against the same deterministic personas, and that is precisely the
comparison this harness exists to make. Measuring ρ is the first experiment the
harness should run on itself.

**Step 4: variance reduction multiplies through.** An r% reduction in standard
error multiplies the hands needed by (1−r)²:

| r | Hands needed × |
| --- | --- |
| 20% (LBR's duplicate + imaginary observations) | 0.640 |
| 35% (mid-range of baseline at 3 players) | 0.423 |
| 50% (top of baseline's range at 3 players) | 0.250 |
| 68% (AIVAT, CFR value functions) | 0.102 |
| 85% (AIVAT, DeepStack value functions) | 0.023 |

The 20% row is real, and it is quoted at the figure the paper gives: LBR's own
experiments used duplicate matches plus imaginary observations and reported that
the two together "reduce the size of the confidence intervals by roughly 20% with
the same number of matches" ([Lisý & Bowling 2017](#s-lbr),
§"Variance reduction"). The other four rows are the published reductions cited in
[§2.4](#24-variance-reduction-duplicate-baseline-mivat-aivat), squared the same
way; none is rounded up beyond what its source says.

**Step 5: the consolation.** All of the above is for detecting a *small* edge
between two good strategies. Detecting that the bot beats a deliberately bad
opponent is far cheaper, because Δ is enormous: LBR beat published bots by over
3180 mBB/h ([Lisý & Bowling 2017](#s-lbr)), and always-folding is exploitable
for 750 mb/g in limit hold'em ([Johanson et al. 2011](#s-johanson2011),
Table 1). **So "does the bot beat a calling station?" is answerable in
thousands of hands; "is version B better than version A?" is the expensive
question.** The harness must treat them as different tests with different
budgets.

### 2.6 What a head-to-head number does not tell you

Two findings in the literature are worth stating plainly, because both cut
against the instinct to trust a single scoreboard.

**Low exploitability does not predict head-to-head results.** In the 2010
Annual Computer Poker Competition, five agents looked similar on tournament
results but had exploitabilities ranging from 135.4 to 421.9 mb/g. PULPO — which
deliberately gave up exploitability to play better against weak opponents — won
the 2010 *Bankroll* event, in which agents maximise winnings against the field,
despite being the second-most exploitable agent measured
([Johanson et al. 2011](#s-johanson2011), §6). **This is a published,
measured vindication of `CLAUDE.md`'s position**: if the goal is to take money
off weak opponents, the lowest-exploitability strategy is not the one you want.

**And head-to-head results do not predict exploitability either.** In the LBR
study, the least exploitable bot (Act1) had been *beaten* in one-on-one play by
a more exploitable one (Slumbot), which the authors call confirmation that "even
LBR may not be indicative of actual one on one performance (and vice versa)"
([Lisý & Bowling 2017](#s-lbr), §"Experimental evaluation").

**Consequence for this harness:** the primary endpoint is money won against the
persona pool. LBR, if built at all, is a *separate*, secondary alarm and never a
reason to reject a change that wins more money.

### 2.7 What is and is not realistic solo

**Not realistic in this project's timeframe:**

- Exact best response / exploitability. 76 CPU-days for the *smallest* poker
  variant ([Johanson et al. 2011](#s-johanson2011), §4); infeasible in no-limit.
- Evaluation against strong published bots. They are not available to run
  against, and the LBR authors needed the cooperation of the bots' authors to do
  their own study ([Lisý & Bowling 2017](#s-lbr), §"Experimental evaluation").
- Human evaluation at the scale that produces a significant answer. Pluribus's
  10,000-hand experiment ran over 12 days with a rotating pool of thirteen
  professionals and a $50,000 incentive pool ([Brown 2020](#s-brown2020), §6.6).

**Realistic, and is what [Part 2](#3-part-2--the-harness) specifies:**

- Self-play and persona-play at whatever throughput the engine gives, with
  seeded deals.
- Common random numbers and duplicate at two and three seats; baseline control
  variates at four and above ([Davidson et al. 2013](#s-baseline)).
- A stated, pre-registered statistical decision rule instead of eyeballing.
- LBR heads-up, if and only if [X5](#engine-requirements) is satisfied.
- AIVAT, last, and only if [X5](#engine-requirements) is satisfied *and* a value
  function exists. Everything cheaper should be exhausted first.

---

## 3. Part 2 — The harness

Working name: **`arena`**. One command, `pokerbot arena run <config>`, produces
one signed result file. Nothing about it is interactive and nothing about it
requires judgement to read.

### 3.1 Architecture and module boundaries

```
tests/arena/    # test-only tree; nothing in the bot's import graph imports it
  deal.py       # seeded deal generation; replay; seat permutation
  seats.py      # table construction for n in 2..9; blinds, button rotation
  personas/     # rule-based opponents, one module each; NO import from bot/
    __init__.py # registry: name -> constructor(params, rng)
    base.py     # Persona protocol: act(observation) -> Action
    params.py   # every persona's parameter vector, in one file, as config
    preflop.py  # static 169-class starting-hand ranking; test-only; see §3.3
    draws.py    # draw detection heuristic; test-only; see §3.3
  runner.py     # plays N hands of a configured table; emits HandRecord rows
  estimators.py # raw mean, duplicate, baseline control variate
  stats.py      # bootstrap CIs, paired tests, BH correction, power/sample size
  invariants.py # chip conservation, side pots, legal-action checks
  report.py     # the single result document
```

**Hard boundaries, each with a reason:**

- `personas/` **must not import anything under the bot's decision path**, and a
  test asserts this by inspecting the import graph. A persona that shares code
  with the bot cannot detect a bug in that shared code.
- `runner.py` owns the game rules by delegating to the vendored engine. It does
  not implement betting rules itself. See
  [Engine requirements](#engine-requirements).
- `estimators.py` and `stats.py` never see cards, only per-hand utilities. This
  keeps the statistics testable with synthetic numbers, with no poker involved.
- Every run writes its full configuration — engine commit, bot version, persona
  parameters, seed, table sizes, stack depths — into the result file. A result
  whose configuration is not recorded is not a result.

### 3.2 The persona set

Two groups, with different jobs.

**Group A — calibration agents.** Trivial, literature-attested strategies whose
job is to prove the harness works, not to challenge the bot. Their exploitability
in heads-up *limit* hold'em is published and exact, which makes them the only
opponents in the harness with a known right answer:

| Persona | Exploitability in HULHE | Harness job |
| --- | --- | --- |
| `always_fold` | 750 mb/g | Sanity: the bot must win ≈ the blinds, and this is computable in closed form, so it checks the accounting |
| `always_call` | 1163.48 mb/g | Checks the bot values hands at all |
| `always_raise` | 3697.69 mb/g | Checks the bot does not fold everything under pressure |
| `call_raise_50_50` | 2406.55 mb/g | A stochastic opponent, to shake out seed handling |

(Figures: [Johanson et al. 2011](#s-johanson2011), Table 1. They are for
two-player *limit* hold'em and do not transfer numerically to our multiway
no-limit game; they are quoted to show these agents are standard instruments,
and as the reason for keeping a heads-up limit-like configuration available as a
self-check.) A comparable set of "chump" strategies — always-call, always
half-pot, and a random mixture — was used the same way in the LBR study
([Lisý & Bowling 2017](#s-lbr), Table 2).

**Group B — behavioural personas.** These are the ones that imitate human
mistakes. Each is defined **structurally** — by a rule, not by a magic number —
and then parameterised. The two axes come from the poker-classification
literature the opponent model already uses: **tight/loose** (how many hands a
player pays to see) and **passive/aggressive** (how often they bet and raise
rather than call), attributed to Billings' thesis and to Sklansky by
[Teófilo & Reis 2011](#s-teofilo2011), §3, with the thresholds *folds ≥72% of
hands = tight* and *aggression factor > 1 = aggressive*. Teófilo and Reis
recovered **seven** player types by clustering 51,377,820 real-money games from
158,035 players (§5 Table 1, §7).

| Persona | The human mistake it embodies | Rule |
| --- | --- | --- |
| `calling_station` | Calls too much, never folds a pair | Never folds post-flop with any made hand or draw; raises only with a strong made hand |
| `nit` | Folds far too often, waits for the top of the range | Plays only hands in the top `TIGHT_FRACTION`; folds to any raise without a strong hand |
| `maniac` | Bets and raises regardless of holding | Raises with probability `MANIAC_RAISE_P` at every opportunity |
| `never_bluffs` | Bets only with real hands, so its bets are readable | Bets or raises only with a made hand at or above `VALUE_THRESHOLD`; otherwise checks or calls |
| `fit_or_fold` | Gives up whenever the flop misses | Folds to any bet without a pair or better, regardless of pot odds |
| `tag` | Competent: tight and aggressive | Top `TIGHT_FRACTION` of hands, but bets and raises them |
| `lag` | Competent but wide | Wide range, high aggression |
| `tilter` | Plays worse after losing a big pot | A two-state machine: normal parameters, but after losing a pot larger than `TILT_TRIGGER_BB`, switches to `maniac` parameters for `TILT_DURATION` hands, then reverts |
| `sizing_tell` | Bet size leaks hand strength | Bets a large fraction with strong hands and a small fraction with weak ones — see [§4.3](#43-true-no-limit-sizing-and-the-biggest-measured-weakness-in-published-bots) |

Three of those rules ask for a judgement no hand evaluator makes — `nit` and
`tag` need a *preflop* ranking of two cards, and `calling_station` needs *draw*
detection on an incomplete hand. [§3.3](#33-the-forefront-rule-and-the-personas)
names what answers each, and why neither the engine's evaluator nor `treys` can.

**Every capitalised parameter above is a design choice, not a measured or cited
value.** All of them live in `personas/params.py`, all are logged into the
result file, and none are asserted to describe any real population. What *is*
grounded is the placement: the persona set is constructed to occupy all four
corners of the tight/loose × passive/aggressive square that
[Teófilo & Reis 2011](#s-teofilo2011) attest, plus the specific
mistakes — never bluffing, fit-or-fold, tilting — the opponent model's exploit
flags are designed to punish.

**Two design rules for the set:**

1. **Randomise parameters per session, do not fix them.** Draw each persona's
   parameters from a distribution at the start of a session rather than using a
   single point. A bot tuned against one exact parameter point will look better
   than it is; see [§6](#6-how-this-harness-lies-to-you).
2. **Hold personas back.** Split the set into a *development* half, used while
   tuning, and an *evaluation* half, used only for accept/reject decisions. The
   grounding is direct: counter-strategies in the literature are documented as
   **"sensitive to the choice of training opponent"** and as overfitting to the
   opponent they were built against, performing "very badly against other
   opponents" ([Johanson & Bowling 2009](#s-johanson2009), §4). A harness with
   one fixed opponent set is a training opponent by another name.

### 3.3 The forefront rule and the personas

`CLAUDE.md`'s forefront rule forbids hand-rolled hand-strength or decision logic
*in place of the vendored engine*, and confines the external evaluator to tests.
Personas are decision logic. This needs saying out loud rather than being left
ambiguous:

- **Personas are test-only code, in the same category as
  `tests/ground_truth/`.** The whole `arena` tree lives under `tests/`. **The
  import-graph boundary is the rule, and it runs in one direction only:** `tests/`
  may import the bot and the engine; nothing reachable from the bot's entry point
  may import anything under `tests/`. A test walks the bot's import graph and
  fails if any module under `tests/` appears in it. A persona that shares code
  with the bot cannot detect a bug in that shared code, and a bot that can reach
  persona code has smuggled hand-rolled poker judgement into itself.
- **The forefront rule governs the bot under test, not its sparring partners.**
  `CLAUDE.md` forbids hand-rolled hand-strength or decision logic *in place of the
  vendored engine*, in the bot's decision path, and it already licenses an outside
  evaluator (`treys`) in the test role. A persona is a fixture. The rule that
  applies to a fixture is the one that applies to `tests/ground_truth/`: it is
  named, it is test-only, and it never plays.
- **Three different judgements, three different answers. Do not collapse them
  into "the personas use an evaluator".** A persona asks three questions and only
  the first is what a hand evaluator answers:
  1. **How strong is this made hand?** → **the engine's own evaluator**, the same
     call the bot makes. No second implementation, and a disagreement between the
     engine and `treys` then surfaces in `tests/ground_truth/` rather than being
     silently absorbed by the harness.
  2. **Is this hole-card pair in the top `TIGHT_FRACTION` before the flop?**
     (`nit`, `tag`) → **not hand evaluation at all.** It is a ranking of the 169
     strategically distinct starting hands, and *neither the engine's evaluator
     nor `treys` provides one*: both score a complete five-card hand, and two hole
     cards are not one. Personas use a **static 169-class ranking table
     transcribed from a named published source**, and the source is **the Chen
     formula** ([Chen & Ankenman 2006](#s-chen)), because it assigns every one of
     the 169 classes a score and so gives the total order that "top X%" requires.
     The alternative considered and rejected, [Sklansky &
     Malmuth 1999](#s-sklansky), is the better-known ranking but groups only the
     playable top and leaves the rest unordered, which a "top X%" rule cannot use.
     The table is a constant, checked into `tests/arena/personas/preflop.py`, with
     its source named in the file. **Neither book was retrieved in this survey**
     (see [Sources](#sources)); the transcription must be checked against the
     named edition before the table is used, and a test must assert the table has
     exactly 169 entries and is a strict ranking.
  3. **Am I drawing?** (`calling_station`'s "any made hand or draw") → **also not
     something either evaluator does.** Detecting four to a flush or an
     open-ended straight is a property of an incomplete hand. This is a small,
     explicit, **test-only heuristic** — count suits, count rank gaps across hole
     cards and board — living in `tests/arena/personas/draws.py`, labelled
     test-only in the file, and unit-tested against enumerated examples. It is
     allowed to be crude and it is allowed to be wrong at the margins: a persona
     is a caricature, and a caricature that misreads a gutshot is still a valid
     fixture. It must never be imported by anything but personas.
- **A persona is deliberately bad poker.** That is its function. It is not a
  claim about correct play and must never be promoted into one.

### 3.4 The deal controller

`deal.py` is small and load-bearing. It provides:

- `deal(seed, n_players) -> Deal` — a complete, deterministic specification of
  every card in a hand, independent of how the betting goes.
- `replay(deal, seat_assignment) -> Deal` — the same cards with players permuted
  across seats, for duplicate.
- Guaranteed reproducibility: same seed, same engine commit, same cards. This is
  the precondition for every variance-reduction technique in
  [§2.4](#24-variance-reduction-duplicate-baseline-mivat-aivat)
  ([Davidson et al. 2013](#s-baseline), §4.1: baseline requires "that the random
  events observed in the simulation are reproducible").

This is engine requirement [X3](#engine-requirements) and
[X4](#engine-requirements). If the vendored engine cannot separate dealing from
play, `arena` cannot use any variance reduction at all and the sample sizes in
[§2.5](#25-win-rate-with-honest-statistics) apply at their unreduced values.
**Assess this before anything else in the harness is built.**

### 3.5 The decision rule: is this change an improvement?

The thing that replaces eyeballing a win rate. Written out as a procedure
because a later coding task should implement it literally.

**Before the run — pre-register.** Write into the config, before playing a hand:

1. **The primary endpoint.** One number: mbb/hand for version B minus version A,
   **weighted** across table sizes by the weights below, pooled across the
   persona pool, on paired deals. It is a *weighted* pool, and the weights are
   written into the config and reprinted in the report; an unlabelled average is
   not a result.
2. **The table-size weights.** These are settled, from the operator's own
   statement of what they play (2026-09-15): *"i will be playing mostly 6 player
   tables, followed by 8 or 9 player tables which can honestly be treated the
   same, they are so close."* So:

   | Band | Seat counts | Headline weight |
   | --- | --- | --- |
   | Primary | 6 | 0.50 |
   | Secondary | 8 and 9, treated as one band | 0.30 (0.15 each) |
   | Everything else | whichever other seat counts ran that night | 0.20, split equally |

   The last row is a **rule, not a fixed list**, because not every seat count
   runs every night ([§3.6](#36-the-run-budget-turning-hands-into-hours)). On a
   nightly acceptance run the other seat counts present are **2 and the single
   rotating seat**, so each takes 0.20 ÷ 2 = **0.10**. On the aspirational full
   grid all five of 2, 3, 4, 5 and 7 are present and each takes 0.20 ÷ 5 =
   **0.04**. The three band weights never move; only the split inside the last
   band does, and the report prints whatever split was in force.

   **Every seat count is still evaluated and every seat count still gates a
   release — on a four-night cadence.** The nightly acceptance run always plays
   seats **6, 8, 9 and 2**: the operator's two priority bands, plus heads-up,
   which is not a light seat count but a structurally different game — with two
   players a no-lose strategy exists and with three or more it does not
   ([§2.2](#22-exploitability-and-exact-best-response)). To those four it adds
   **one** of **{3, 4, 5, 7}**, rotating in the fixed cycle 3 → 4 → 5 → 7.
   **Nothing leaves on a rotation night**: the four fixed seats always run and
   the rotating seat is the fifth, which is why the nightly grid is five seat
   counts and not four. **A release requires every seat count from 2 to 9 to
   have passed within the last four nightly runs** — a rolling four-night
   window. So a collapse at three-handed still blocks the change, on the night
   three-handed runs, even though it carries 10% of that night's headline; the
   window, not any single night, is what makes the gate cover all eight seat
   counts. The non-inferiority and per-table-size rules below apply
   unweighted. The weights decide only what the single summary number means.
   The *numbers* 0.50 / 0.30 / 0.20 are a design
   choice implementing the operator's stated ordering, not a quantity the
   operator gave; they live in config and are revisable without touching this
   document.
3. **The sample size**, from the formula in
   [§2.5](#25-win-rate-with-honest-statistics), using a σ and ρ **measured by a
   pilot run**, not guessed — and then checked against the wall-clock budget in
   [§3.6](#36-the-run-budget-turning-hands-into-hours), which is what decides how
   many cells the run can actually afford.
4. **The decision thresholds** (below).

**During the run.**

- **Pair everything.** Both arms play identical deals, identical persona seeds,
  identical seat assignments. This is free and is what makes ρ large.
- **Apply the variance reduction the table size allows** —
  [§4.2](#42-why-duplicate-dies-past-three-seats).
- **Do not look at the running total.** Stopping when a result looks good
  invalidates a fixed-sample test. If early stopping is wanted, it must be a
  sequential test designed for it — see the upgrade below.

**After the run — the test.**

- **Primary.** A **percentile bootstrap confidence interval** on the paired
  per-hand difference ([Efron 1979](#s-efron)), resampling *hands* for
  memoryless personas. Recommendation: bootstrap rather than a t-interval, and
  the reason is specific — per-hand poker results are extremely heavy-tailed
  (most hands are a small fold, a few are a stack), and the bootstrap makes no
  distributional assumption. A paired t-test
  ([Welch 1947](#s-welch) for the unequal-variance case) is reported alongside as
  a cross-check; if the two disagree materially, something is wrong with the
  data, not with the choice of test.
- **Sessions with memory need a block bootstrap.** The `tilter` persona makes
  consecutive hands dependent: its behaviour in hand *k* depends on hand *k−1*.
  Resampling individual hands would destroy that dependence and understate the
  variance. Resample *blocks* of consecutive hands instead
  ([Politis & Romano 1994](#s-politis)). Any future persona with state falls
  under the same rule.
- **Accept the change if** the bootstrap interval for the primary endpoint lies
  entirely above zero, **and** no per-persona interval trips the blocker below.
- **Secondary, per table size.** The same interval computed separately for each
  n in the run, **unweighted** — the weights of point 2 apply to the headline
  only. Five table sizes a night means five tests, and testing five things at
  5% each produces a false alarm about a fifth of the time. Control the false
  discovery rate across the family with the
  Benjamini–Hochberg procedure ([Benjamini & Hochberg 1995](#s-bh)). The number
  of tests in the family is the number of cells the budget in
  [§3.6](#36-the-run-budget-turning-hands-into-hours) actually bought — **20**
  on a nightly run — and the report states it; correcting for five when twenty
  were run is cheating.
- **Non-inferiority, per persona.** Report the interval against each persona
  separately. **A change that wins overall by beating one persona harder while
  losing to another is a red flag, not a pass** — it is the signature of
  over-adapting to one opponent, which is the documented failure mode in
  [Johanson & Bowling 2009](#s-johanson2009), §4.

  **The rule, decided and not open:** any persona whose interval lies entirely
  below zero **blocks the change**. The only way past it is a **written override
  in the run config** that names the persona, quotes the size of the regression,
  and states why it is acceptable; the override text is copied into the result
  file, so a change that was let through on a judgement call can be found later.
  **No numeric tolerance is set**, because setting one now would be inventing a
  number: there is no data yet on how often a genuine improvement trips this.
  Loosening the rule waits on that data — revisit once the harness has run enough
  comparisons to say what the false-alarm rate actually is.

**Upgrade, not first version: sequential testing.** If the fixed sample size
turns out to cost more wall-clock than the project can spend, replace the
fixed-n test with Wald's sequential probability ratio test
([Wald 1945](#s-wald)), which accumulates a likelihood ratio and stops as soon as
it crosses one of two boundaries: accept above `A = (1−β)/α`, reject below
`B = β/(1−α)`. At α = 0.05 and β = 0.20 those are **A = 16.0** and
**B = 0.2105** (log-scale 2.7726 and −1.5581). SPRT is the standard answer to
"can I stop early without cheating". *(It is also, to the best of this survey's
knowledge, what open-source computer-chess projects use to decide whether a patch
is an improvement — a useful precedent for exactly this problem, but **not
verified against a source here**, and nothing in this document depends on it.)*
Do not implement it until the simple version is working and measured.

**What the report says.** One page:

```
arena report  bot A=<sha> B=<sha>  engine=<sha>  seed=<n>  2026-XX-XX
tier: nightly acceptance   cells: 20   budget: 10h   elapsed: 4h51m
seats: 6 8 9 2 fixed + 3 rotating (cycle 3>4>5>7; night 1 of 4)
weights: n6=0.50  n8=0.15 n9=0.15  n2=0.10 n3=0.10   (config, operator 2026-09-15)
window: all 8 seat counts must have passed within the last 4 nightly runs; 5 have
        (2,3,6,8,9); 4,5,7 last passed too long ago -> NOT GATED, RELEASE BLOCKED
        (the per-seat window table, with last-pass date and bot sha, prints in full)
primary  (weighted pool, paired, baseline-adjusted)  +34.2 mbb/hand  [ +11.8, +56.9 ]  ACCEPT
  powered to detect: 28.1 mbb/hand pooled, 100 mbb/hand per cell
  by table size, unweighted (Benjamini-Hochberg, q=0.05, family size 20)
    n=2   +51.1 [ +12.0, +90.6 ]  *
    n=3   +40.7 [  +4.2, +77.1 ]  *
    ...
    n=9    -2.4 [ -39.8, +35.0 ]
  by persona (non-inferiority; interval wholly below zero = BLOCK)
    calling_station  +102.6 [ +71.1, +134.8 ]
    never_bluffs      -18.9 [ -44.2,   +6.3 ]   <- watch
  overrides in force: none
  measured: sigma=<..> mbb/hand   rho=<..>   SE reduction from baseline=<..>%
  hands: <..> per arm    sec/decision: <..>   decisions/hand: <..>
```

Everything in it is a measurement or a decision. Nothing in it is an
impression.

### 3.6 The run budget: turning hands into hours

Everything above this point is sized for **one** comparison. The harness that
[§3.5](#35-the-decision-rule-is-this-change-an-improvement) and
[§4.1](#41-table-size-is-an-axis-not-a-setting) actually ask for is a **grid** of
them, and the grid is where the arithmetic stops being affordable. This section
does the multiplication, converts it to hours, and cuts the grid down to what
fits. **No sample size in this document may be quoted without going through
here first.**

**The hard constraint, from the operator (recorded 2026-09-15).** The operator's
position, and all of it: **no multi-day computing; hours on one laptop.** That
is a limit on what the machine may be occupied with, not a number of hours.
Turning it into arithmetic needs two numbers the operator did not give, so they
are stated here as **design choices implementing that position** — the same
status as the 0.50 / 0.30 / 0.20 table-size weights in
[§3.5](#35-the-decision-rule-is-this-change-an-improvement) point 2. They live
in config and are revisable without touching this document:

| Run | Must finish within | Whose number |
| --- | --- | --- |
| Full acceptance run, before a change is accepted | **one night — at most 10 hours** | Design choice here: 10 hours is what "one night" means on a laptop the operator needs back in the morning |
| Routine check, during the day | **one hour** | Design choice here: short enough to run between edits without stopping work |
| Anything multi-day | **never** | **The operator's own words** |

**What the grid costs as specified.** Take §3.5 and §4.1 literally: every seat
count, a homogeneous table per behavioural persona plus one mixed table, at
several stack depths ([§4.4](#44-stack-depth)).

| Axis | Count | From |
| --- | --- | --- |
| Seat counts, n = 2…9 | 8 | [§4.1](#41-table-size-is-an-axis-not-a-setting) |
| Compositions per seat count: 9 homogeneous + 1 mixed | 10 | [§4.1](#41-table-size-is-an-axis-not-a-setting), [§3.2](#32-the-persona-set) |
| Stack depths: short, 100 bb, deep | 3 | [§4.4](#44-stack-depth) |
| **Cells** | **240** | |

Each cell is its own two-arm comparison, so each needs the per-arm sample size
from [§2.5](#25-win-rate-with-honest-statistics). Using the **most favourable row
in that whole table** — σ = 1,500 mbb/hand — and Δ = 50 mbb/hand, a cell costs
14,128 hands per arm, 28,256 hands in total:

**240 cells × 28,256 hands = 6,781,440 hands.**

**Hands are not hours, and the conversion is the whole problem.** Two figures,
both pending, and what they imply for the same grid differs by four orders of
magnitude:

- **Engine throughput.** `ENGINE_ALTERNATIVES.md` (on a branch under review, not
  on main at the time of writing) measures OpenSpiel `universal_poker` at
  **56,414 complete six-player hands per second on one core**. At that rate the
  full grid takes **120 seconds**.
- **The bot's own thinking time.** The same document's recommended architecture
  is decision-time computing with a **250 ms budget per decision**. That, not the
  engine, is the binding term: the engine is idle while the bot thinks.

**So the budget must be written in seconds per decision, never in engine hands
per second.** Every hour below is an hour on **one specific machine, and it is
named here so that a number measured on a different one is never silently
substituted: an Apple M4 laptop with 16 GB of RAM and 10 cores (4 performance,
6 efficiency)**. The working assumption, and it is a **placeholder to be
measured**, not a result:

| Quantity | Value used here | Status |
| --- | --- | --- |
| The machine | Apple M4, 16 GB RAM, 10 cores (4P + 6E) | **Recorded, not measured for this purpose.** Every hour in this section is an hour on this laptop and on no other |
| Seconds per bot decision | 0.25 | Architecture budget from `ENGINE_ALTERNATIVES.md`, **under review**; not a measurement of this bot |
| Bot decisions per hand | 4 | **Placeholder. Measure it.** Nothing sources this |
| ⇒ bot-seconds per hand | **1.0** | Product of the two |
| Parallel workers on the laptop | 8 | **Placeholder.** 8 of the 10 cores, leaving two for everything else. **Memory per worker is entirely unmeasured** ([X8](#engine-requirements)), and 16 GB is what decides whether 8 workers thrash |
| ⇒ hands per hour | **28,800** | 3,600 × 8 ÷ 1.0 |

These are [X7](#engine-requirements) and [X8](#engine-requirements), restated as
the numbers that actually decide the wall clock. **Until they are measured, every
hour in this section is provisional**, and the report prints the measured
seconds-per-decision and decisions-per-hand beside the elapsed time so that the
first real run replaces these placeholders with facts.

**How much the worker count can be wrong by.** Wall clock is inversely
proportional to the number of workers: halve the workers and the run takes twice
as long. The nightly acceptance run below is **141,280 hands**, so the workers
needed to finish inside the 10-hour ceiling are 141,280 ÷ (3,600 × 10) =
**3.92 — call it 4**. At 4 workers the run takes 141,280 ÷ (3,600 × 4) =
**9.8 hours**, which still fits; at 3 it takes 13.1 hours and does not.
**So the 8-worker placeholder can be wrong by half and the design survives;
wrong by more than half and the nightly run stops fitting in a night.** That is
the sense in which [X8](#engine-requirements) matters, and it is why memory per
worker — the thing that most plausibly forces the count down on a 16 GB
machine — has to be measured before the first real run.

**The full grid against the cap.** 6,781,440 hands ÷ 28,800 per hour =
**235 hours ≈ 9.8 days on one laptop.** That is **23.5 times** the 10-hour cap,
and it is multi-day, which the operator has ruled out. It also *understates* the
cost, because σ = 1,500 is a post-AIVAT six-player figure and this harness has no
AIVAT before Tier 4. **The full grid is not buildable and must not be quietly
assumed.** It becomes affordable only if a bot decision drops from 250 ms to
about **11 ms**, or if AIVAT-grade variance reduction lands. It is kept below as
the aspirational tier so that nobody re-derives it from scratch.

**The reduced cell set, which is what actually runs.**

- **Seat counts: 6, 8, 9 and 2 every night, plus one of 3, 4, 5, 7 —** five, not
  eight. 6, 8 and 9 are the operator's own two bands and carry 0.80 of the
  headline ([§3.5](#35-the-decision-rule-is-this-change-an-improvement)
  point 2); 2 is fixed not because it is weighted heavily but because heads-up
  is a different game ([§2.2](#22-exploitability-and-exact-best-response)) and
  because duplicate variance reduction is available there and cheap
  ([§4.2](#42-why-duplicate-dies-past-three-seats)). The fifth slot rotates
  3 → 4 → 5 → 7, one per night, in that fixed cycle. **Nothing is dropped to make
  room for the rotating seat**; it is an addition, which is what takes the grid
  from four seat counts to five. Over four consecutive nights all eight seat
  counts have run, and a release needs all eight to have passed inside that
  rolling window.
- **Compositions: 4** — one mixed table plus three homogeneous personas drawn
  from the *evaluation* half of the set ([§3.2](#32-the-persona-set)), rotating
  across runs so every persona is seen over a handful of nights.
- **Stack depth: 100 bb only.** It is the depth every cited evaluation used
  ([§4.4](#44-stack-depth)). The short and deep depths move to the aspirational
  tier and to their own dedicated run, not to every run.

**5 × 4 × 1 = 20 cells** on a nightly acceptance run.

| Run | Seat counts | Cells | Hands/cell | Total hands | Wall clock | Detects per cell | Detects pooled |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Routine check** | 2, 6, 8, 9 (no rotating seat) | 16 | 1,766 | 28,256 | **0.98 h** | 200 mbb/hand | — |
| **Nightly acceptance** | 2, 6, 8, 9 + one of 3/4/5/7 | 20 | 7,064 | 141,280 | **4.9 h** | 100 mbb/hand | **28.1 mbb/hand** |
| Full grid (aspirational) | all of 2…9 | 240 | 28,256 | 6,781,440 | 235 h | 50 mbb/hand | — |

Nightly: 20 × 7,064 = 141,280 hands; 141,280 ÷ 28,800 per hour = **4.906 h**.
Routine: 16 × 1,766 = 28,256; ÷ 28,800 = **0.981 h**.

**Why the routine check does not carry the rotating seat.** At 20 cells it would
be 20 × 1,766 = 35,320 hands = **1.23 h**, which breaks the one-hour bound. The
routine check therefore runs the four fixed seat counts only. That costs
nothing that matters: the routine check is a smoke test that detects only a
200 mbb/hand change, and **it does not gate a release** — the four-night window
of §3.5 point 2 is defined over *nightly acceptance* runs, which do rotate.

Both affordable rows fit inside their caps, the nightly one with **5.1 hours of
headroom** (10 − 4.9) for the pilot that measures σ and ρ, for a re-run, and for
the measurements above turning out worse than the placeholders.

**Where the pooled 28.1 comes from, because it is the number the headline rests
on.** The nightly run's 141,280 hands are 70,640 per arm. Split *equally* across
the five seat counts, each gets 14,128 per arm — the same per-seat sample a
four-seat grid would give, which is why per-cell power is 100 mbb/hand either
way and the fifth seat costs an hour of wall clock (3.9 h → 4.9 h) rather than
costing power. The weighted headline
then has an effective sample size of 14,128 ÷ Σwᵢ² per arm, and Σwᵢ² is the same
on every rotation night, because the weights depend on how many other seat
counts ran, not on which:

| Rotation night | Seat counts and weights | Σwᵢ² | n_eff per arm | Δ detectable |
| --- | --- | --- | --- | --- |
| 1 | 6 = .50, 8 = .15, 9 = .15, 2 = .10, **3 = .10** | 0.315 | 44,851 | **28.1 mbb/hand** |
| 2 | 6 = .50, 8 = .15, 9 = .15, 2 = .10, **4 = .10** | 0.315 | 44,851 | **28.1 mbb/hand** |
| 3 | 6 = .50, 8 = .15, 9 = .15, 2 = .10, **5 = .10** | 0.315 | 44,851 | **28.1 mbb/hand** |
| 4 | 6 = .50, 8 = .15, 9 = .15, 2 = .10, **7 = .10** | 0.315 | 44,851 | **28.1 mbb/hand** |

Σwᵢ² = 0.50² + 0.15² + 0.15² + 0.10² + 0.10² = 0.25 + 0.0225 + 0.0225 + 0.01 +
0.01 = **0.315**; n_eff = 14,128 ÷ 0.315 = **44,851** per arm; at σ = 1,500 and
the same (z₀.₉₇₅ + z₀.₈₀)² = 7.8489 that
[§2.5](#25-win-rate-with-honest-statistics) uses, Δ = √(2 × 1,500² × 7.8489 ÷
44,851) = **28.1 mbb/hand**. **The headline is identical on all four nights**,
which is the point of a fixed cycle: the release criterion does not move
depending on which night a change lands on. *(For comparison, a four-seat night —
6 = .50, 9 = .30, and two others at .10 — has Σwᵢ² = 0.36, n_eff = 39,244 and
Δ = 30.0. The fifth seat spreads the weight further, which lowers Σwᵢ² from 0.36
to 0.315, so the extra hour buys 1.9 mbb/hand of headline power as well as a
wider night.)* *(Allocating hands in proportion to the weights
instead of equally would raise the effective size to the full 70,640 and the
headline to Δ = 22.4, at the cost of the light seat counts' per-cell power. That is
a config switch; the default is equal, because a per-cell regression screen that
is blind at the rotating seat is worse than a headline six units coarser.)*

**Two honest corrections, in opposite directions.** σ = 1,500 is the most
favourable published row and this harness has no AIVAT, so the true σ is larger
and these hours are a **floor**. Against that, the budget assumes ρ = 0 and
ignores pairing entirely, while
[§2.5](#25-win-rate-with-honest-statistics) Step 3 shows ρ = 0.5 halves the hands
needed. Neither cancels the other and neither is known. **Re-derive this table
from the pilot's measured σ and ρ before the first real acceptance run**, and
record both in the result file.

**What this buys and what it does not.** The pooled headline is powered to detect
a 28.1 mbb/hand change — comparable to Pluribus's whole edge over professionals
([§2.1](#21-the-unit)). Each individual cell is powered only to 100 mbb/hand, so
**a per-cell interval is a regression screen, not evidence of no effect.** The
report must print "powered to detect" beside every per-cell interval, or a reader
will read a wide interval as a clean bill of health.
[§6](#6-how-this-harness-lies-to-you) carries that as one of the ways this
harness lies.

### 3.7 Tiers: what to build, in what order

**Tier 0 — the harness can run a legal game.** `deal`, `seats`, `runner`,
`invariants`. Every check in
[§4.5](#45-correctness-invariants-that-come-before-any-strength-number) passes at
every n from 2 to 9. No strength measurement at all. **Nothing else in this
document is worth building until Tier 0 is green**, because a strength number
from a harness that mis-awards side pots is a fiction.

**Tier 1 — the persona league.** Group A and Group B personas; raw win rate with
bootstrap confidence intervals; the report. At this point the harness can answer
"is the bot losing badly to something obvious?", which is the cheap question from
[§2.5](#25-win-rate-with-honest-statistics), Step 5.

**Tier 2 — the comparison machinery.** Paired deals, duplicate at n ≤ 3, baseline
control variates at n ≥ 4, measured σ and ρ, the pre-registered decision rule.
This is the tier that makes "is version B better" answerable. **This is the
tier that pays for itself and the one to stop at if time runs out.**

**Tier 3 — LBR probe, heads-up only.** Needs [X5](#engine-requirements). A
number that only goes one way: a large LBR win rate against our bot is evidence
of a real hole. A small one proves little
([§2.3](#23-local-best-response-a-cheap-lower-bound)).

**Tier 4 — AIVAT.** Needs [X5](#engine-requirements), a value function, and a
public-state partition. The payoff is large (68–85% standard-error reduction,
[§2.4](#24-variance-reduction-duplicate-baseline-mivat-aivat)) and so is the
implementation cost. Do not start it before Tier 2 is measured and its
limitations known.

---

## 4. Part 3 — Table sizes 2-9 and true no-limit sizing

The operator's requirement is firm: the bot must work at every table size from
two to nine, with real no-limit bet sizing. That requirement lands on the
evaluation harness harder than it lands on the bot, because a harness that
exercises one fixed scenario will report a number that is true of that scenario
and false of everything else.

### 4.1 Table size is an axis, not a setting

**The rule: `n` is a dimension of every result, never a constant in a config.**
`arena` runs the whole mix in one invocation and the report is broken down by n,
as in [§3.5](#35-the-decision-rule-is-this-change-an-improvement). A run that
covers only one table size is not a valid run.

**But not every table size in every run — that does not fit in a night.**
[§3.6](#36-the-run-budget-turning-hands-into-hours) does the arithmetic: all
eight seat counts, crossed with per-persona compositions and stack depths, is 240
cells and about 9.8 days of laptop time, which the operator has ruled out. The
affordable form of this rule is the one §3.6 settles on: **five seat counts every
nightly acceptance run — 2, 6, 8 and 9 always, plus one of 3, 4, 5, 7 rotating in
the fixed cycle 3 → 4 → 5 → 7** — with a release gated on every seat count from
2 to 9 having passed **within the last four nightly runs**. No seat count goes
unmeasured for longer than four nights, no seat count stops gating, and no single
run is a one-table-size run. Read this section's rule through that budget, not
around it.

**Why this is not paranoia.** Poker changes shape with the number of players in
a way that is not a matter of degree. Two independent pointers:

- The solution concept itself changes at three players. With two players a
  no-lose strategy exists; with three or more it does not, for the reasons in
  [§2.2](#22-exploitability-and-exact-best-response). A measurement approach
  validated heads-up carries no guarantee at six.
- The correct *frequency* of bluffing falls as the number of live opponents
  grows, because every additional player is another chance that someone has a
  hand — the argument is set out in the opponent model design, §2.4. The harness
  can test this directly at no extra cost: **report the bot's bet-without-a-made-
  hand frequency broken down by the number of live opponents.** If it does not
  fall as the field grows, that is a red flag about the strategy, and it is
  visible from data the harness already collects.

**Seat composition matters too, not just seat count.** A six-handed table of six
calling stations and a six-handed table of one calling station and five nits are
different games. The config specifies a *composition* — a multiset of personas
per table — and the report records it. The ideal is, for each n, a homogeneous
table per persona (the clean signal) plus a mixed table drawn from the pool (the
realistic one), reporting both. **That ideal is ten compositions per seat count
and it does not fit either** —
[§3.6](#36-the-run-budget-turning-hands-into-hours) cuts it to **four per seat
count: one mixed table plus three homogeneous personas drawn from the evaluation
half, rotating across runs** so every persona is seen over a handful of nights.
The full cross is the aspirational tier.

### 4.2 Why duplicate dies past three seats

Duplicate requires replaying each deal with every assignment of players to sets
of hole cards. In two players that is 2 replays; in three it is 6
([Davidson et al. 2013](#s-baseline), §5.2). The factorial does the rest:

| n | Replays per deal (n!) |
| --- | --- |
| 2 | 2 |
| 3 | 6 |
| 4 | 24 |
| 5 | 120 |
| 6 | 720 |
| 7 | 5,040 |
| 8 | 40,320 |
| 9 | 362,880 |

At nine seats, full duplicate costs 362,880 replays per deal. That is not a
close call. And it is not only a cost problem: at three players, full six-way
duplicate **increased** the standard error for more than half of the nine agents
measured, by up to 40.41% ([Davidson et al. 2013](#s-baseline), Table 1).

**So the harness's rule is:**

- **n = 2 or 3:** duplicate is available and cheap; use it, and use baseline too,
  and report which did better. The literature says baseline won on all nine
  three-player agents, but that was limit hold'em in 2011 and our game is not
  theirs, so measure rather than assume.
- **n ≥ 4:** **baseline control variates**
  ([Davidson et al. 2013](#s-baseline)). One control agent, playing itself on the
  same seeded deals; subtract the scaled control value. The control agent can be
  the bot's own previous version — it only has to exist and be reproducible. This
  is the technique the authors explicitly designed for "games with more than two
  agents", where duplicate is impractical.

Implementation note from the source: because the control agent is stochastic,
its per-deal value should be the average over several self-play repetitions of
the same deal; the ACPC analysis used fifty
([Davidson et al. 2013](#s-baseline), §5.2). Fifty is *their* number for *their*
throughput; ours is a budget decision and belongs in config.

### 4.3 True no-limit sizing, and the biggest measured weakness in published bots

**This is the most important finding in this document for the operator's
no-limit requirement, and it is not intuitive.**

No-limit means a player may bet any amount from a minimum up to their whole
stack — in Pluribus's own rule statement, "raises can be in any whole-dollar
amount", with the only constraints being a minimum raise and the player's
remaining stack ([Brown 2020](#s-brown2020), §2.4.3). Solvers cannot handle that
continuum, so they solve a game with a handful
of allowed bet sizes (an *abstraction*) and then *translate* real-world bets onto
the nearest allowed one. The published measurement of what that translation
costs is brutal:

- LBR was run against a bot with **no card abstraction at all** — perfect
  knowledge of hand strength — using the sparse "fold, call, pot, all-in"
  betting abstraction. Within its own abstraction, a true best response showed
  that bot exploitable for only **90 mBB/h**. In the real game, with hard
  translation of off-abstraction bets, **LBR won 2403 mBB/h** against it
  ([Lisý & Bowling 2017](#s-lbr), §"Full cards").
- Soft translation helped but did not fix it: sampled soft translation still lost
  1981 ± 224 mBB/h.
- And it does not take an exotic attack: the same bot lost 1849 mBB/h against LBR
  using only *fold, call, min-bet, 2× pot, 4× pot, 8× pot, and all-in*.

**A bot can be near-perfect inside its own betting abstraction and catastrophic
outside it, and an evaluation harness that only ever offers it familiar bet
sizes will never see the difference.**

**What the harness must therefore do:**

1. **Personas bet off-abstraction sizes on purpose.** Not "a pot-sized bet" but
   arbitrary fractions. Use the LBR study's own grid rather than inventing one:
   pot fractions `0.05 × 1.15^k` for `k = 0…54`, which runs from 0.05× pot to
   about 94.8× pot, with 22 of the 55 points at or below one pot
   ([Lisý & Bowling 2017](#s-lbr), §"Experimental evaluation"). **That is 55 pot
   fractions plus the all-in bet, which is why the paper calls it 56 bets and
   why this document does too:** `k = 0…54` is 55 values, the 56th bet is all-in,
   and the two counts are the same grid, not two different grids. Sampling persona
   bet sizes from this grid guarantees that most bets the bot faces are sizes
   nobody chose for it.
2. **Report split by off-tree exposure.** Every hand record carries a flag: did
   any opponent bet a size outside the bot's own abstraction? The report gives
   win rate on off-tree hands and on-tree hands separately. **A large gap between
   those two numbers is the specific failure this section exists to catch.**
3. **Do not delay the off-tree bets to the flop.** LBR's authors found the timing
   matters and in a counter-intuitive direction: using all 56 bet sizes from the
   first betting round exploited bots "almost a full order of magnitude less"
   than checking through the first two rounds and using them later, because
   betting big early pushes the opponent out before they commit money
   ([Lisý & Bowling 2017](#s-lbr), §"Experimental evaluation"). So the harness
   runs **both** schedules — aggressive from round 1, and quiet-then-aggressive
   from round 3 — and reports both, rather than assuming one is the harder test.
4. **Include the structural edge cases as personas, not as unit tests.**
   Min-bets, minimum raises, raises that are all-in for less than a full raise,
   and bets that leave an opponent with an unplayably small stack. These change
   whose action is reopened under the rules, and they are where engine bugs live.
5. **`sizing_tell` from [§3.2](#32-the-persona-set) belongs to this section.** A
   persona whose bet size correlates with its hand strength is both a realistic
   human mistake and a direct test of whether the bot can use a sizing signal at
   all — which it cannot, if its abstraction collapses every size onto three
   buckets before it looks at them.

This is engine requirement [X2](#engine-requirements), and it may be the single
hardest thing to get from the vendored engine.

### 4.4 Stack depth

Bet sizing is meaningless without stack depth, because what a pot-sized bet
*means* depends on how much money is behind it. The literature's conventions:
the ACPC and Pluribus-style "Doyle's game" resets every player to a fixed stack
each hand — 200 chips at a big blind of 2, i.e. 100 big blinds, in the AIVAT
HUNL experiments ([Burch et al. 2018](#s-aivat), §"No-limit Texas Hold'em",
stated in the arXiv:1612.06915v2 preprint of that paper); the
LBR "full cards" bot played 100 BB ([Lisý & Bowling 2017](#s-lbr)); Pluribus's
multiplayer games started every hand at $10,000 with a $100 big blind, i.e. 100
big blinds, and the reason given for the reset is exactly the statistical one —
"by having each hand start with the same number of chips, we are able to treat
each hand as a separate sample when measuring win rate"
([Brown 2020](#s-brown2020), §2.4.3). Freezeout — chips carry over until
someone is out — is the harder format and was handled separately in the AIVAT
work, with a win-probability value estimate rather than chips
([Burch et al. 2018](#s-aivat), §"Freezouts").

**Harness rule: stack depth is a second axis, and it starts reset-per-hand.**
Reset-per-hand ("Doyle's game") is what every cited evaluation used, it is the
published reason those evaluations could treat each hand as an independent
sample — which is what the statistics in
[§2.5](#25-win-rate-with-honest-statistics) assume — and it is simpler. A short,
a standard and a deep stack exercise materially different strategy, so a declared
set of depths is better than one. The specific depths are a design choice and
belong in config; 100 big blinds must be among them, since it is what every cited
evaluation used.

**Depth is the axis the budget cuts first.** Tripling the cell count triples the
hours, and [§3.6](#36-the-run-budget-turning-hands-into-hours) has no room for
it: **every routine and nightly run is 100 bb only**, and the short and deep
depths get their own dedicated run on their own schedule rather than riding on
every comparison. The reason depth is the axis to cut, rather than seat count or
persona, is that seat count is the operator's stated requirement and personas are
what the harness exists to measure against, while depth is the axis with the
weakest published claim to change the answer.

Carry-over stacks are a later tier, and if they are ever
added, the independence assumption behind the sample-size arithmetic goes with
them and the block bootstrap of
[§3.5](#35-the-decision-rule-is-this-change-an-improvement) becomes mandatory
rather than optional.

### 4.5 Correctness invariants that come before any strength number

Cheap, deterministic, and non-negotiable. These run at every n from 2 to 9 on
every run, and a failure aborts the run rather than being reported.

| # | Invariant | Why |
| --- | --- | --- |
| I1 | Chips are conserved: the sum of all seats' stack changes on a hand is exactly zero | Catches the whole class of pot-accounting bugs, which silently inflate or deflate every win rate |
| I2 | No stack goes negative, and nobody puts in more than they had | Catches all-in handling |
| I3 | Side pots are awarded correctly when players are all-in for different amounts | The most common multiway bug, and it *only* appears at n ≥ 3 |
| I4 | Every action taken is legal under the engine's own rules at that state | Catches a persona doing something impossible and quietly winning |
| I5 | The button, blinds and action order rotate correctly for every n in 2..9, including the heads-up special case where the button posts the small blind and acts first pre-flop | Heads-up reverses the usual order; it is the classic off-by-one in a variable-seat-count engine |
| I6 | Same seed + same engine commit + same bot version ⇒ byte-identical hand records | Without this, no variance reduction in [§2.4](#24-variance-reduction-duplicate-baseline-mivat-aivat) works, and no result is reproducible |
| I7 | A hand's recorded pot equals the sum of contributions, and the showdown winner matches the ground-truth evaluator | Ties the harness back to `tests/ground_truth/` |

I1, I3 and I5 are the ones that make table sizes 2–9 a genuine test rather than a
claim.

---

## 5. How this fits the opponent model

`OPPONENT_MODEL_DESIGN.md` (not yet on the main branch at the time of writing)
specifies a per-opponent model and, in its §6, a validation plan. Two points of
contact, stated here so neither document has to be edited to notice them:

- **The harness gives that design's V3 test a ground truth it cannot otherwise
  have.** V3 asks whether the per-opponent model predicts an opponent's next
  action better than a pooled baseline. Against real humans, the true tendencies
  are unknown and the test can only be scored on held-out actions. Against
  personas, **the true parameters are known by construction**, so the classifier
  can be scored against the correct label directly: given N hands of a
  `never_bluffs` persona, how often and how quickly does the model classify it as
  passive and set the right exploit flag? That is a much sharper test, and it is
  free once the harness exists.
- **The engine capability they need is the same one.** That design's E1 (query
  the strategy for an action-probability distribution rather than a sampled
  action) is this document's [X5](#engine-requirements). It gates that design's
  Tier 1 and this document's Tiers 3 and 4. **One assessment answers both**, and
  whoever assesses the engine should be told so.
- **That design's V5 warning is this document's [§2.5](#25-win-rate-with-honest-statistics).**
  It already notes that Pluribus needed 10,000 hands *with AIVAT* to reach
  p = 0.028 and that without variance reduction the measurement needs far more
  hands than the project has. The arithmetic in
  [§2.5](#25-win-rate-with-honest-statistics) is where that warning's numbers
  come from.

---

## 6. How this harness lies to you

Every way a green report here could still be wrong, so that a later session does
not have to rediscover them.

- **Overfitting to the persona set.** A bot tuned until it beats these nine
  personas has been trained on them. The literature's version of this is
  documented: counter-strategies built against one opponent "can perform very
  badly against other opponents" and are "sensitive to the choice of training
  opponent" ([Johanson & Bowling 2009](#s-johanson2009), §4). Mitigations, both
  in [§3.2](#32-the-persona-set): randomise persona parameters per session, and
  keep an evaluation half of the set that is never used while tuning.
- **Personas are not humans.** They are caricatures of tendencies that a
  clustering study found in real play ([Teófilo & Reis 2011](#s-teofilo2011)),
  played by a rule engine that never adapts, never bluffs a bluff-catcher, never
  targets *our bot* specifically. Beating them is necessary and nowhere near
  sufficient. The harness's job is to catch bad changes cheaply, not to certify
  the bot.
- **The persona corpus's own caveat carries through.** The clustering that
  grounds the tight/loose and aggression axes was done on real-money *tournament*
  logs, not cash play ([Teófilo & Reis 2011](#s-teofilo2011), §5 Table 1). Any
  rate carried from it into a cash-table persona inherits that mismatch.
- **Peeking.** Watching the running win rate and stopping when it looks good
  invalidates the fixed-sample test completely. [§3.5](#35-the-decision-rule-is-this-change-an-improvement)
  forbids it and names the legitimate alternative.
- **An underpowered cell reads as a clean cell.** This is the lie the budget
  creates. [§3.6](#36-the-run-budget-turning-hands-into-hours) buys each cell
  enough hands to detect a 100 mbb/hand regression and no more, so a per-cell
  interval straddling zero means *"we could not have seen anything smaller than
  100"*, not *"nothing is wrong here"*. The same trap sits under the per-table-size
  breakdown in the report. Mitigation: the report prints "powered to detect"
  beside every per-cell interval, and a cell is never described as passing — only
  as not tripping the screen.
- **A seat count that did not run tonight reads as a clean seat count.** Only
  five of the eight seat counts play on any one night
  ([§3.6](#36-the-run-budget-turning-hands-into-hours)), so three are absent from
  every nightly report — and an absent row is the easiest thing in the world to
  read as "no problem there". It is not: it is no evidence at all, and the
  evidence it stands on may be three nights old and describe a different bot.
  Mitigation, and it is a requirement on the report, not advice: **the report
  prints all eight seat counts every night, never only the five that ran**, and
  gives each one the date and bot SHA of the run it last *passed* on. A seat
  count whose last pass is older than four nightly runs, or is against a
  different bot SHA than the one under test, prints as **NOT GATED** and
  **blocks the release** exactly as a failure would. The four-night window of
  [§3.5](#35-the-decision-rule-is-this-change-an-improvement) point 2 is a claim
  about the last four runs, so a report that cannot show those four runs cannot
  support it:

  ```
  seat-count window (release needs all eight passed within the last 4 nightly runs)
    n=2  ran tonight   PASS
    n=3  ran tonight   PASS
    n=4  last passed 2026-XX-XX (1 run ago, bot=<sha>)   PASS
    n=5  last passed 2026-XX-XX (2 runs ago, bot=<sha>)  PASS
    n=6  ran tonight   PASS
    n=7  last passed 2026-XX-XX (5 runs ago, bot=<sha>)  NOT GATED  <- blocks
    n=8  ran tonight   PASS
    n=9  ran tonight   PASS
  ```
- **The budget's own inputs are placeholders.** Seconds per bot decision and
  decisions per hand are assumed, not measured ([X7](#engine-requirements)), and
  σ = 1,500 is borrowed from a post-AIVAT six-player experiment this harness
  cannot match before Tier 4. If the real σ is twice that, every run in
  [§3.6](#36-the-run-budget-turning-hands-into-hours) is four times too short and
  reports confident intervals it has not earned. Re-derive from the pilot.
- **A too-small σ from a pilot.** The sample-size formula is only as good as the
  σ fed into it, and σ estimated from a short pilot on heavy-tailed data is
  biased low, which makes the run too short and the test underpowered. Re-estimate
  σ from the full run and report it; if the realised σ exceeds the pilot's, the
  run was underpowered and says less than it appears to.
- **Silent configuration drift.** Two runs that differ in engine commit, persona
  parameters or stack depth are not comparable, and the difference will look like
  a strategy improvement. The result file records everything
  ([§3.1](#31-architecture-and-module-boundaries)) precisely so this is detectable
  after the fact.
- **A green run is not a deployment.** `rules/global.md` is explicit that a green
  suite is never proof an action is safe. This harness measures play against
  fabricated opponents in a simulator. It says nothing about the screen-capture
  layer, about latency, or about a real table.

---

## Engine requirements

What the harness needs from the vendored engine. **A separate task is assessing
the engine; nothing here should be assumed.** Each is stated so it can be
answered yes or no. Note that `CLAUDE.md` records the engine currently defaults
to a 20-card short deck, so every requirement below is gated on the 52-card
conversion landing first.

| # | Requirement | Needed by |
| --- | --- | --- |
| X1 | Can a table be configured with any seat count from 2 to 9, with correct blind posting and action order at each, including the heads-up reversal? | Everything; [§4.1](#41-table-size-is-an-axis-not-a-setting) |
| X2 | Can a player bet an **arbitrary legal amount**, not merely a size from a fixed abstraction grid — and can the bot be given an off-grid bet to respond to? | [§4.3](#43-true-no-limit-sizing-and-the-biggest-measured-weakness-in-published-bots); the operator's no-limit requirement |
| X3 | Can the deal be generated from an explicit seed, separately from play, and reproduced exactly? | All variance reduction; [§3.4](#34-the-deal-controller); I6 |
| X4 | Can one fixed deal be replayed with players permuted across seats? | Duplicate at n ≤ 3; [§4.2](#42-why-duplicate-dies-past-three-seats) |
| X5 | Can the trained strategy be queried for an **action-probability distribution** at a decision point, rather than only a sampled action? *(Identical to the opponent model design's E1.)* | LBR (Tier 3), AIVAT (Tier 4) |
| X6 | Does the engine handle side pots correctly when players are all-in for different amounts at a multiway pot? | I3; any n ≥ 3 result |
| X7 | The three numbers that convert hands into hours, for a table of n players: **(a)** engine-only throughput, complete hands per second per core, with no bot thinking; **(b)** **seconds per bot decision** at the decision-time budget actually shipped; **(c)** **bot decisions per hand**, measured, not assumed. | Every sample size in [§2.5](#25-win-rate-with-honest-statistics) and the whole budget in [§3.6](#36-the-run-budget-turning-hands-into-hours) |
| X8 | How many `arena` workers can this laptop run in parallel without thrashing — cores usable and memory per worker? | The wall-clock column in [§3.6](#36-the-run-budget-turning-hands-into-hours) |

**X7 is a measurement, not a yes/no, and it should be the first thing measured**,
because it converts every hand count in this document into a number of hours and
therefore decides which tiers are affordable. **Its binding term is (b) × (c),
not (a).** The engine is idle while the bot thinks, so engine hands per second —
the headline figure engine surveys report — is the wrong number to budget with
and will understate the cost by orders of magnitude. `ENGINE_ALTERNATIVES.md` (on
a branch under review at the time of writing) measures 56,414 engine hands/second
for OpenSpiel `universal_poker` and a 250 ms decision-time budget for the bot;
between those two, [§3.6](#36-the-run-budget-turning-hands-into-hours) is the
difference between two minutes and ten days for the same grid.

---

## Decisions that were open, and where they now live

This section used to hold four questions. All four are answered. They are
recorded here as decisions, with the section that carries each one, so that a
later session can see what was decided and does not reopen it.

| Was | Question | Decided | Written into |
| --- | --- | --- | --- |
| Q1 | Which hand evaluator may the fake opponents use? | Method call, delegated. Made-hand strength goes to **the engine's own evaluator**; preflop ranking uses a **static 169-class table from a named published source**; draw detection is a **small, explicitly test-only heuristic**. All three live under `tests/`, outside the bot's import graph, labelled test-only. | [§3.3](#33-the-forefront-rule-and-the-personas) |
| Q2 | What mix of table sizes should the headline number weight? | **The operator's own answer**, 2026-09-15: mostly 6-handed, then 8/9 treated as one band. Headline weights 0.50 / 0.30 / 0.20, the last split equally over whichever other seat counts ran. Every seat count still gates a release, on a **rolling four-night window**: nightly runs always play 2, 6, 8, 9 and rotate one of 3/4/5/7. | [§3.5](#35-the-decision-rule-is-this-change-an-improvement), point 2 |
| Q3 | How much may a change lose against one persona while winning overall? | Method call, delegated. The document's own operating rule stands: **any per-persona regression blocks the change** unless a written override names the persona and the reason. **No numeric tolerance**; loosening waits for data. | [§3.5](#35-the-decision-rule-is-this-change-an-improvement), "Non-inferiority, per persona" |
| Q4 | How long may an evaluation run take? | **The operator's position**, recorded 2026-09-15, is *"no multi-day computing; hours on one laptop"* — that, and no numbers. The **10-hour** acceptance ceiling and the **1-hour** routine bound are **design choices made here** to turn that position into arithmetic, on the same footing as the 0.50/0.30/0.20 weights. | [§3.6](#36-the-run-budget-turning-hands-into-hours) |

**Why Q1 and Q3 were not sent to the operator.** Both are method decisions, not
product ones: nothing about them depends on facts only the operator holds, and
`rules/global.md` reserves escalation for design judgement, ambiguous product
calls, and blast radius. Q2 was the opposite — *which table sizes the operator
actually plays* is a fact no amount of analysis could supply — so it went, and
its answer is quoted verbatim in the
[provenance table](#provenance-of-every-number-in-this-document).

**Nothing in this document is now blocked on an answer.** What it is blocked on
is a *measurement*: [X7](#engine-requirements) and [X8](#engine-requirements),
which turn hand counts into hours. Until those exist, every wall-clock figure in
[§3.6](#36-the-run-budget-turning-hands-into-hours) rests on a placeholder that
is marked as one.

---

## Sources

All retrieved and read 2026-09-15 unless marked otherwise.

<a id="s-aivat"></a>**[Burch et al. 2018]** Neil Burch, Martin Schmid, Matej
Moravčík, Dustin Morrill and Michael Bowling, "AIVAT: A New Variance Reduction
Technique for Agent Evaluation in Imperfect Information Games", *AAAI Conference
on Artificial Intelligence (AAAI)*, 2018.
`https://poker.cs.ualberta.ca/publications/aaai18-burch-aivat.pdf`
The primary source for everything this document says about AIVAT: the
construction (MIVAT chance corrections + imaginary observations + new correction
terms for non-terminal actions), the unbiasedness proof and the truthfulness
argument, the Leduc and HUNL experiments, the DeepStack human-evaluation results
(Table 5) and the freezeout results (Table 6), and the 10 mbb/g = 1 bb/100 unit
identity. An earlier four-author preprint of the same work is arXiv:1612.06915v2
(19 January 2017); its HUNL figures are identical, and it does not contain the
human-evaluation sections. Where a figure appears in both, this document cites
the AAAI version.

<a id="s-brown2020"></a>**[Brown 2020]** Noam Brown, *Equilibrium Finding for
Large Adversarial Imperfect-Information Games*, PhD thesis, Carnegie Mellon
University, CMU-CS-20-132.
`http://reports-archive.adm.cs.cmu.edu/anon/2020/CMU-CS-20-132.pdf`
Cited in preference to the Science paper because it is openly available. §2.2
defines exploitability, NashConv, and why Nash equilibrium stops being the right
target above two players (the Lemonade Stand illustration, the PPAD-completeness
results). §6.6 is the Pluribus evaluation: the use of AIVAT in six-player play,
the one-tailed t-test at 95%, 10,000 hands, 48 mbb/game ± 25 with p = 0.028 for
5H+1AI, 32 mbb/game ± 15 with p = 0.014 for 1H+5AI, and the per-player figures
for Elias (40 ± 22, p = 0.033) and Ferguson (25 ± 20, p = 0.107).
The underlying publication is Noam Brown and Tuomas Sandholm, "Superhuman AI for
multiplayer poker", *Science* 365(6456):885–890, 2019, DOI
`10.1126/science.aay2400` (bibliographic record confirmed via the Crossref API,
2026-09-15); it is closed-access.

<a id="s-lbr"></a>**[Lisý & Bowling 2017]** Viliam Lisý and Michael Bowling,
"Equilibrium Approximation Quality of Current No-Limit Poker Bots",
arXiv:1612.07547v2, 8 January 2017. `https://arxiv.org/pdf/1612.07547`
The Local Best Response method: the algorithm (Figure 1), the proof sketch that
it lower-bounds exploitability, the chump-strategy results (Table 2), the ACPC
bot results (Table 3) and the "over 3180 mBB/h with 97.5% confidence" summary,
the 56-bet grid `0.05 × 1.15^k`, the round-scheduling finding, the duplicate +
imaginary-observations 20% confidence-interval reduction, and the full-cards
translation results (90 mBB/h in-abstraction versus 2403 mBB/h in the real game).

<a id="s-johanson2011"></a>**[Johanson et al. 2011]** Michael Johanson, Kevin
Waugh, Michael Bowling and Martin Zinkevich, "Accelerating Best Response
Calculation in Large Extensive Games", *IJCAI 2011*.
`https://poker.cs.ualberta.ca/publications/ijcai2011_accelerated_best_response.pdf`
§4 has the 76 CPU-day / 72-processor cost of one exact best response in heads-up
limit hold'em and the 9.17 × 10<sup>17</sup> state count. §6 has the trivial-agent
exploitabilities (Table 1), the 2010 ACPC agents' exploitabilities (Table 2), the
50 mb/g professional rule of thumb, and the PULPO finding that the bankroll
winner was not the least exploitable agent.

<a id="s-baseline"></a>**[Davidson et al. 2013]** Joshua Davidson, Christopher
Archibald and Michael Bowling, "Baseline: Practical Control Variates for Agent
Evaluation in Zero-Sum Domains", *AAMAS 2013*.
`https://poker.cs.ualberta.ca/publications/AAMAS13-baseline.pdf`
§4.1 is the baseline construction and the zero-expectation argument. §5.2
describes duplicate at two and three players and the ACPC's use of it. §6.1.1 is
Table 1, the 2011 three-player limit results: baseline beating duplicate on all
nine agents, baseline's 21.78%–49.68% standard-error reduction, and duplicate's
negative reductions down to −40.41%.

<a id="s-teofilo2011"></a>**[Teófilo & Reis 2011]** Luís Filipe Teófilo and Luís
Paulo Reis, "Identifying Player's Strategies in No Limit Texas Hold'em Poker
through the Analysis of Individual Moves", *EPIA 2011*. arXiv:1301.5943.
`https://arxiv.org/pdf/1301.5943`
§3 states the tight/loose (folds ≥72%) and aggression-factor (AF > 1) thresholds
and attributes them to Billings' thesis and to Sklansky; §5 Table 1 gives the
corpus statistics (51,377,820 games, 158,035 players); §7 reports the seven
player types recovered by clustering. The corpus is real-money **tournament**
play, not cash play. Read directly in this survey for the facts cited here; the
same paper is a source of `OPPONENT_MODEL_DESIGN.md`.

<a id="s-johanson2009"></a>**[Johanson & Bowling 2009]** Michael Johanson and
Michael Bowling, "Data Biased Robust Counter Strategies", *AISTATS 2009*.
`https://poker.cs.ualberta.ca/publications/AISTATS09.pdf`
§4 is the source of the overfitting argument used in
[§3.2](#32-the-persona-set) and [§6](#6-how-this-harness-lies-to-you): best
responses "perform well against their intended opponent, but they can perform
very badly against other opponents", counter-strategies overfit their opponent
model, and the technique is "sensitive to the choice of training opponent".

<a id="s-chen"></a>**[Chen & Ankenman 2006]** Bill Chen and Jerrod Ankenman, *The
Mathematics of Poker*, ConJelCo, 2006, ISBN 978-1-886070-25-7. The source named
in [§3.3](#33-the-forefront-rule-and-the-personas) for the personas' static
169-class preflop starting-hand ranking (the "Chen formula"), chosen because it
scores all 169 classes and so gives the total order a "top X%" rule needs.
**Not retrieved in this survey**, and neither the formula nor any ranking derived
from it is reproduced in this document. The table must be transcribed from this
edition and the transcription checked against it before use; a test asserts the
table has exactly 169 entries and is a strict ranking.

<a id="s-sklansky"></a>**[Sklansky & Malmuth 1999]** David Sklansky and Mason
Malmuth, *Hold'em Poker for Advanced Players*, 21st Century Edition, Two Plus Two
Publishing, 1999, ISBN 978-1-880685-22-3. The better-known published
starting-hand grouping, listed in [§3.3](#33-the-forefront-rule-and-the-personas)
as the alternative to the Chen formula and rejected only because it groups the
playable top and leaves the remainder unordered, which a "top X%" rule cannot
use. **Not retrieved in this survey**; no group membership is reproduced here.

<a id="s-lanctot2017"></a>**[Lanctot et al. 2017]** Marc Lanctot, Vinicius
Zambaldi, Audrūnas Gruslys, Angeliki Lazaridou, Karl Tuyls, Julien Pérolat, David
Silver and Thore Graepel, "A Unified Game-Theoretic Approach to Multiagent
Reinforcement Learning", *NIPS 2017*, pp. 4190–4203. arXiv:1711.00832.
The origin of NashConv. **Cited at second hand**, via
[Brown 2020](#s-brown2020) §2.2, which states the definition used here; the
arXiv record and title were confirmed directly on 2026-09-15 but the paper was
not read in this survey.

<a id="s-lemonade"></a>**[Zinkevich et al. 2011]** Martin Zinkevich, Michael
Bowling and Michael Wunder, "The Lemonade Stand Game Competition: Solving
Unsolvable Games", *ACM SIGecom Exchanges* 10(1):35–38, 2011.
**Cited at second hand**, via [Brown 2020](#s-brown2020) §2.2, which uses it as
the worked example of equilibrium selection failing above two players. Not
retrieved.

<a id="s-acpc"></a>**[Bard et al. 2013]** Nolan Bard, John Hawkin, Jonathan Rubin
and Martin Zinkevich, "The Annual Computer Poker Competition", *AI Magazine*
34(2):112–114, 2013. DOI `10.1609/aimag.v34i2.2474`.
Cited only for the existence and structure of the competition. Bibliographic
record confirmed via the Crossref API on 2026-09-15; **the article itself was not
retrieved**, and the competition details used in this document
(duplicate matches, bankroll versus one-on-one events) are taken from
[Davidson et al. 2013](#s-baseline) §5.2 and
[Johanson et al. 2011](#s-johanson2011) §6, both read directly.

**Statistical methods.** All four bibliographic records confirmed via the
Crossref API on 2026-09-15.

<a id="s-efron"></a>**[Efron 1979]** Bradley Efron, "Bootstrap Methods: Another
Look at the Jackknife", *The Annals of Statistics* 7(1):1–26, 1979. DOI
`10.1214/aos/1176344552`. The bootstrap, used here for confidence intervals on
heavy-tailed per-hand results.

<a id="s-politis"></a>**[Politis & Romano 1994]** Dimitris N. Politis and Joseph
P. Romano, "The Stationary Bootstrap", *Journal of the American Statistical
Association* 89(428):1303–1313, 1994. DOI `10.1080/01621459.1994.10476870`.
Resampling for dependent data — the correct tool when consecutive hands are not
independent, as with the `tilter` persona.

<a id="s-bh"></a>**[Benjamini & Hochberg 1995]** Yoav Benjamini and Yosef
Hochberg, "Controlling the False Discovery Rate: A Practical and Powerful
Approach to Multiple Testing", *Journal of the Royal Statistical Society Series
B* 57(1):289–300, 1995. DOI `10.1111/j.2517-6161.1995.tb02031.x`. Used for the
eight simultaneous per-table-size tests.

<a id="s-wald"></a>**[Wald 1945]** Abraham Wald, "Sequential Tests of Statistical
Hypotheses", *The Annals of Mathematical Statistics* 16(2):117–186, 1945. DOI
`10.1214/aoms/1177731118`. The sequential probability ratio test and its
`A = (1−β)/α`, `B = β/(1−α)` boundaries.

<a id="s-welch"></a>**[Welch 1947]** B. L. Welch, "The Generalization of
'Student's' Problem when Several Different Population Variances are Involved",
*Biometrika* 34(1/2):28–35, 1947. DOI `10.2307/2332510`. The unequal-variance
t-test used as a cross-check on the bootstrap.

**Deliberately not cited.** Poker tracking-software population statistics —
typical VPIP ranges, "standard" win-rate standard deviations for online cash
games, and similar — circulate widely but no verifiable source for them was found
in this survey, so no persona parameter and no σ in this document rests on one.
Every σ in [§2.5](#25-win-rate-with-honest-statistics) is derived from a figure
printed in a cited paper, and the derivations are in the provenance table below.

---

## Provenance of every number in this document

Per the global evidence rules, so that no figure here has to be taken on trust.

| Number | Where it comes from |
| --- | --- |
| 10 mbb/g = 1 bb/100 | [Burch et al. 2018](#s-aivat), Table 5 caption, read directly |
| 50 mb/g strong-player aim | [Johanson et al. 2011](#s-johanson2011), §6, read directly. Stated there as **a rule of thumb among human professionals**, for heads-up *limit* hold'em; not a measured constant |
| 48 mbb/game ± 25, p = 0.028; 32 mbb/game ± 15, p = 0.014; 40 ± 22, p = 0.033; 25 ± 20, p = 0.107; 10,000 hands; 12 days | [Brown 2020](#s-brown2020), §6.6, read directly |
| 9.17 × 10<sup>17</sup> states; 76 CPU-days; "just over a day" on 72 processors; 12,285 / 24,570 subgames; 4.5 minutes per subgame | [Johanson et al. 2011](#s-johanson2011), §4 and §5, read directly |
| Always-Fold 750, Always-Call 1163.48, Always-Raise 3697.69, 50/50 2406.55 mb/g | [Johanson et al. 2011](#s-johanson2011), Table 1, read directly. **Heads-up limit** hold'em; they do not transfer numerically to multiway no-limit |
| 135.427 / 141.363 / 237.330 / 300.032 / 318.465 / 399.387 / 421.850 mb/g; the PULPO bankroll finding | [Johanson et al. 2011](#s-johanson2011), Table 2 and §6, read directly |
| "over 3180 mBB/h with 97.5% confidence"; 2 × 50,000 duplicate hands | [Lisý & Bowling 2017](#s-lbr), §"Experimental evaluation", read directly |
| 90 mBB/h in-abstraction vs 2403 mBB/h with hard translation; 1981 ± 224 with sampled soft translation; 1849 mBB/h with seven bet sizes; LBR losing 536 mBB/h | [Lisý & Bowling 2017](#s-lbr), §"Full cards" and Table 3, read directly |
| The 56-bet grid: 55 pot fractions `0.05 × 1.15^k`, k = 0…54, **plus all-in** | [Lisý & Bowling 2017](#s-lbr), §"Experimental evaluation" and Table 3 caption, read directly, which says "all in, and 55 pot fractions computed as 0.05 · (1.15)^k for k = 0…54 (56 bets)". The endpoint values (0.05, 0.2023, 0.818, 3.31, 13.4, 94.8 × pot) and the count of 22 points at or below one pot were **computed by script on 2026-09-15** from that formula |
| "roughly 20%" confidence-interval reduction from duplicate + imaginary observations | [Lisý & Bowling 2017](#s-lbr), §"Variance reduction", read directly |
| HUNL SD 25.962 → 8.095 chips (self-play) and 26.308 → 8.301 (dissimilar); 39% for MIVAT+IO; "a bit more than a 68% reduction" for AIVAT; 18% for MIVAT; 1,000,000 games | [Burch et al. 2018](#s-aivat), Tables 3 and 4 and surrounding text, read directly. The exact **68.8%** is **derived 2026-09-15** as 1 − 8.095 ÷ 25.962; the paper rounds it down to "a bit more than 68%", and both [§2.4](#24-variance-reduction-duplicate-baseline-mivat-aivat) and the 0.102× multiplier use the paper's 68% so as to reproduce the paper's own "ten times less data" |
| Big blind = 2 chips, 200-chip (100 big blind) stacks in those HUNL experiments | The **arXiv:1612.06915v2 preprint** of [Burch et al. 2018](#s-aivat), §"No-limit Texas Hold'em", read directly. The AAAI-18 version states the same experiments but not the blind structure; the identical SD figures in both versions are what licenses carrying it across. This is the conversion factor for every chips→mbb derivation below |
| 85% SD reduction with DeepStack value functions; 4 sigma → 20 sigma; 44,852 games; 33 players from 17 countries; 28 freezeout matches; 0.5 ± 0.2 → 0.59 ± 0.018 | [Burch et al. 2018](#s-aivat), §"No-limit Texas Hold'em with Humans" and Tables 5–6, read directly |
| Leduc 99.8% / 99.9% SD reduction; 48%–75% with dissimilar strategies | [Burch et al. 2018](#s-aivat), Tables 1 and 2 and surrounding text, read directly (referenced in passing in [§2.4](#24-variance-reduction-duplicate-baseline-mivat-aivat)) |
| Baseline 21.78%–49.68%; duplicate down to −40.41%; nine agents; 180,000 hands; fifty self-play repetitions per deal; six orderings at three players | [Davidson et al. 2013](#s-baseline), Table 1 and §5.2, read directly |
| 51,377,820 games; 158,035 players; seven player types; folds ≥72% = tight; AF > 1 = aggressive | [Teófilo & Reis 2011](#s-teofilo2011), §3, §5 Table 1, §7. The 72% and AF > 1 thresholds are attributed there to Billings' thesis and are therefore **second-hand** |
| σ ≈ 12,981 mbb/hand (HUNL raw) | **Derived** 2026-09-15: 25.962 chips ÷ 2 chips per big blind × 1000 = 12,981 mbb, from [Burch et al. 2018](#s-aivat) Table 3 |
| σ = 4,047.5 mbb/hand (HUNL after AIVAT) | **Derived** 2026-09-15: 8.095 ÷ 2 × 1000 = 4,047.5 mbb, same table. Quoted at 4,047.5 and not rounded to 4,048, because 4,047.5 is the value the [§2.5](#25-win-rate-with-honest-statistics) sample-size row reproduces from and 4,048 is not |
| σ ≈ 2,500 and ≈ 1,500 mbb/hand (six-player, after AIVAT) | **Derived** 2026-09-15 as SD = standard error × √n = 25 × √10000 and 15 × √10000, from [Brown 2020](#s-brown2020) §6.6. Assumes the reported standard errors were computed from 10,000 hands treated as independent samples, which is what the cited one-tailed t-test implies |
| `(z₀.₉₇₅ + z₀.₈₀)² = 7.8489`; every cell of the sample-size table; the paired-ρ table; the (1−r)² multipliers; n! for 2–9; SPRT boundaries A = 16.0, B = 0.2105 | **Computed by script on 2026-09-15.** Formulas are stated inline beside each table: `n = 2σ²(z_α + z_β)²/Δ²` unpaired, `2σ²(1−ρ)(z_α + z_β)²/Δ²` paired, `A = (1−β)/α`, `B = β/(1−α)`. Standard results, no source needed beyond [Wald 1945](#s-wald) for the SPRT boundaries. **7.8489 is a display rounding**; the tables are computed at 7.848879734…, and reproducing them with 7.8489 exactly gives cells a few units out |
| The ratios 2,500 ÷ 48 ≈ 52 and 12,981 ÷ 48 ≈ 270 in [§2.5](#25-win-rate-with-honest-statistics) Step 1 | **Computed 2026-09-15** from the rows above. 52 is the like-for-like one: both terms are six-player no-limit after AIVAT ([Brown 2020](#s-brown2020), §6.6). 270 divides a *heads-up* σ by a *six-player* edge and is quoted only as an order of magnitude, labelled as such at the point of use |
| The consistency of 68% → 0.102× and 85% → 0.023× with the AIVAT paper's own "ten times" and "factor of forty" | **Derived** 2026-09-15 as (1−r)², and checked against [Burch et al. 2018](#s-aivat)'s conclusions, which state both multipliers |
| 100 big blinds as the standard stack; $10,000 stacks at a $100 big blind in Pluribus; the "treat each hand as a separate sample" justification; "raises can be in any whole-dollar amount" | arXiv:1612.06915v2 preprint of [Burch et al. 2018](#s-aivat), §"No-limit Texas Hold'em"; [Brown 2020](#s-brown2020) §2.4.3, both read directly |
| Every persona parameter (`TIGHT_FRACTION`, `MANIAC_RAISE_P`, `VALUE_THRESHOLD`, `TILT_TRIGGER_BB`, `TILT_DURATION`) | **Design choices, not measured or cited.** No value is asserted in this document; all belong in `personas/params.py` and are to be randomised per session per [§3.2](#32-the-persona-set) |
| ρ, the paired correlation between arms | **Not known.** [§2.5](#25-win-rate-with-honest-statistics) tabulates it across a range precisely because it must be measured by the harness before any sample size is fixed |
| The example `arena report` output in [§3.5](#35-the-decision-rule-is-this-change-an-improvement) | **Invented, and only illustrates the report's format.** Not data, and not a claim about any version of the bot |
| The stack-depth set, the persona-set split, the development/evaluation halves, the choice of bootstrap over t-test as primary | **Design choices made in this document, labelled as such at each point of use** |
| The table-size weighting: 6-handed first, then 8 and 9 as one band | **The operator, 2026-09-15**, verbatim: *"i will be playing mostly 6 player tables, followed by 8 or 9 player tables which can honestly be treated the same, they are so close."* This is a product fact about what the operator plays, which is why it was asked rather than decided |
| The specific weights 0.50 (n=6) / 0.30 (n=8,9) / 0.20 (every other seat count that ran, split equally: 0.10 each on a nightly run, 0.04 each on the full grid) | **A design choice implementing that ordering, not a quantity the operator gave.** The operator stated an order, not proportions. The weights live in config, are reprinted in every report, and are revisable without touching this document |
| "No multi-day computing; hours on one laptop" | **The operator's position, recorded 2026-09-15**, and the whole of it. The operator gave no hour counts |
| The specific run-length limits: **10 hours** for a full acceptance run, **1 hour** for a routine check | **Design choices made here implementing that position, not quantities the operator gave** — the same status as the table-size weights. "Multi-day never" is the operator's. Both limits live in config and are revisable without touching this document |
| The machine the hours are measured on: Apple M4, 16 GB RAM, 10 cores (4P + 6E) | **Recorded 2026-09-15** from the laptop these runs are planned for. Memory per worker is **unmeasured** ([X8](#engine-requirements)); the 8-worker figure assumes 8 of the 10 cores and nothing about RAM |
| 56,414 engine hands/second (OpenSpiel `universal_poker`, 6-player, one core); the 250 ms per-decision budget | `ENGINE_ALTERNATIVES.md`, **on a branch under review and not on main at the time of writing**. Cited as pending: if that document changes or is rejected, every hour in [§3.6](#36-the-run-budget-turning-hands-into-hours) must be recomputed |
| 4 bot decisions per hand; 8 parallel workers; ⇒ 1.0 bot-second per hand and 28,800 hands/hour | **Placeholders, explicitly marked as such at the point of use. Nothing sources them.** They are [X7](#engine-requirements)(c) and [X8](#engine-requirements) and must be measured before any budget in [§3.6](#36-the-run-budget-turning-hands-into-hours) is relied on |
| The budget arithmetic: 240 cells; 6,781,440 hands; 235 h ≈ 9.8 days; 23.5× the cap; ≈11 ms/decision needed to fit; **20 nightly cells; 141,280 hands; 4.9 h**; 16 routine cells; 28,256 hands; 0.98 h (and 1.23 h if the routine check carried the rotating seat, which is why it does not); **Σwᵢ² = 0.315; pooled n_eff 44,851 ⇒ Δ = 28.1 mbb/hand**; the 3.92-worker breakeven against the 10-hour ceiling | **Computed by script on 2026-09-15** from the σ = 1,500 row of [§2.5](#25-win-rate-with-honest-statistics) and the placeholders above. σ = 1,500 is post-AIVAT and this harness has no AIVAT before Tier 4, so every hour is a **floor**; ρ = 0 is assumed, which pushes the other way. Both caveats are stated in [§3.6](#36-the-run-budget-turning-hands-into-hours) |
| The personas' 169-class preflop ranking table | **Not in this document and not reproduced here.** To be transcribed from [Chen & Ankenman 2006](#s-chen), which was **not retrieved in this survey**; the transcription must be checked against that edition before use ([§3.3](#33-the-forefront-rule-and-the-personas)) |
| The personas' draw-detection heuristic | **A design choice, and deliberately crude.** Test-only, outside the bot's import graph, unit-tested against enumerated examples; no source is claimed for it and none is needed, because a persona is a caricature ([§3.3](#33-the-forefront-rule-and-the-personas)) |
