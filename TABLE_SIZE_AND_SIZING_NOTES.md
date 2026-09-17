# Table size and bet sizing: notes for the opponent model

Research notes on two things the existing opponent-modelling design does not
cover, both now firm requirements from the operator:

1. **The bot must handle every table size from 2 to 9 players.**
2. **The bot must use true no-limit bet sizing** — a continuous raise amount, not
   a fixed increment.

`OPPONENT_MODEL_DESIGN.md` has taken the first requirement into its goal and its
solve budget — it states the 2-to-9 scope in §1 and the 32 solver runs it implies
in §4.5 — but the rest of it, the stat definitions above all, still reads as
though the seat count were fixed; and it says nothing at all about bet sizing as
a source of information. **This document does not edit it.** It is on trunk and
has moved on since, so every cross-reference below is to one fixed revision:
`OPPONENT_MODEL_DESIGN.md` at commit `5aa40b8`, 2026-09-15. What this document
does is work out what those two requirements change,
and end with concrete recommended edits, each naming the exact section of that
document to change, so that a later task can make the edits without re-deciding
anything.

Where this document needs a number it either derives it, or cites it, or labels
it as an illustrative or unmeasured value — the same three categories
`OPPONENT_MODEL_DESIGN.md` uses, and for the same reason. Every number is
accounted for in
[Provenance of every number in this document](#provenance-of-every-number-in-this-document).

---

## In plain words, before the jargon

Two plain facts sit underneath everything below.

**The first.** A poker table can have anywhere from two to nine people at it, and
the *same person playing exactly the same way* produces different-looking numbers
depending on how many people are sitting there. This is not because they changed.
It is because with nine people you are forced to put money in before seeing your
cards only about one hand in five, and with two people you are forced to do it
*every single hand*. A statistic like "how often does this person put money in
voluntarily" is an average over the seats they sat in, and the mix of seats is
decided by the table size, not by the person. So comparing that number across
table sizes compares two different things and calls them the same. The bot's
scorecard has to know which kind of table each observation came from.

**The second.** In this game a bet can be any amount, not one of a few fixed
amounts. That cuts both ways. It means *how much* somebody bets is extra
information about them, on top of *whether* they bet — and that information
arrives on every single bet, which makes it some of the cheapest signal
available. It also means the bot's own bet amounts are information about the
bot. A bot that always bets the same fraction of the pot in the same spot is
readable by any human who pays attention, and once read, is beatable. The fix is
not for the bot's supporting code to invent random amounts — the repository's
forefront rule forbids that code from deciding anything about a poker action.
The fix is to take the varied amounts from the engine, which is allowed to decide
them, and stop throwing that variation away. [§2.3](#23-sizing-as-a-signal-about-us)
is that argument in full, and it turns out to be the most important practical
point in this document.

---

## Contents

1. [Table size](#1-table-size)
2. [Continuous bet sizing](#2-continuous-bet-sizing)
3. [Recommended reconciliation with `OPPONENT_MODEL_DESIGN.md`](#3-recommended-reconciliation-with-opponent_model_designmd)
4. [Questions for the operator](#4-questions-for-the-operator)
5. [Sources](#sources)
6. [Provenance of every number in this document](#provenance-of-every-number-in-this-document)

---

## 1. Table size

### 1.0 The engine this project has today already answers two of these questions, and answers them no

Read this first, because it sets when everything below becomes actionable.

The part of the program that knows the rules of poker and decides what to do is
called the **engine**, and this project did not write one — it borrowed a
published one, `poker_ai`, and surveyed it in `REFERENCE_NOTES.md`. Two
questions this document goes on to ask are already settled for *that* engine,
and settled in the negative; a third bullet below is not a question asked
anywhere in this document but a supporting fact, and it closes the obvious way
out of the two:

- **It seats seven players at most.** It deals from a cut-down deck of 20 cards.
  A hand needs two private cards per player plus five shared ones, so eight
  players need 21 cards out of a deck of 20 and the hand runs out mid-way
  (`REFERENCE_NOTES.md`:485-497). The survey draws the consequence for the
  operator's own priorities in so many words: "the 8/9 band is **impossible on
  the short deck**" (`REFERENCE_NOTES.md`:499-503, and the summary at :12-15).
  Seats 8 and 9 are unreachable there, not merely untested.
- **It has no bet sizes at all.** A raise is always one fixed amount — one big
  blind on top of the call, doubled on the turn and the river — and at most
  three raises are allowed in a round of betting. That is the fixed-stakes form
  of the game (**fixed-limit**), where this project wants the free-stakes form
  (**no-limit**). The survey's words: "there is no bet-sizing dimension anywhere
  in the tree" (`REFERENCE_NOTES.md`:523-542, and the summary at :16-19).
- **Converting it to the ordinary 52-card deck is out**, at least 18.4 days of
  computing and 146.5 GiB of memory reserved in one piece — a floor worked out
  by scaling up a run that did finish, not a stopwatch reading — on a laptop
  that has neither, against a budget of hours (`REFERENCE_NOTES.md`:8-11). So
  the seven-seat ceiling cannot be lifted by converting this engine either.

**What that changes here, and what it does not.** It changes **no
recommendation below** — not one of R1 to R14, and none of the reasoning any of
them rests on. What it changes is each recommendation's stated dependency:

- **Reachable now, on the engine in the repository.** Everything about seat
  counts 2 through 7 that is measurement and bookkeeping rather than betting:
  [R1](#r1--define-the-seat-count-band-as-a-context-value-not-a-new-table-extension-42)
  to [R5](#r5--do-not-add-a-table-size-dimension-to-the-bucket-grid-or-the-archetypes-extension-44-and-45),
  [R7](#r7--cross-tabulate-v5s-bluff-frequency-report-by-seat-count-extension-6),
  [R13](#r13--make-the-deviation-cap-a-function-of-seat-count-extension-52) and
  [R14](#r14--record-the-seat-count-mixture-v4-measured-extension-6). None of
  them needs a bet size or an eighth seat.
- **Waiting on the OpenSpiel move.** Seat counts 8 and 9 wherever they
  appear — the `FULL` band in
  [R1](#r1--define-the-seat-count-band-as-a-context-value-not-a-new-table-extension-42),
  the eight-seat-count solve budget in
  [R6](#r6--the-compute-cap-is-already-in-45-and-e5-what-is-left-is-the-resources_solversmd-pointer-extension-most-of-it-already-applied-45-and-engine-requirements)
  and [Q4](#4-questions-for-the-operator) — and the **whole** of
  [§2](#2-continuous-bet-sizing) with everything resting on it
  ([R8](#r8--add-the-sizing-stats-to-the-stat-table-extension-42-and-23-of-the-design-document),
  [R9](#r9--add-two-sizing-exploit-flags-extension-44),
  [R11](#r11--write-the-sampling-rule-into-the-design-as-a-rule-not-an-assumption-correction-41-and-45),
  [R12](#r12--add-v6-the-bots-own-sizing-distribution-extension-6)). What they
  wait on is the reconciliation of four survey documents —
  `ENGINE_ALTERNATIVES.md`, `RESOURCES_BOTS.md`, `RESOURCES_SOLVERS.md` and
  `RESOURCES_EXPLOITATION.md` — and the move to the engine that reconciliation
  is made against.
  `REFERENCE_NOTES.md` is not one of those four: it is the survey of the engine
  being replaced, already on trunk, and it is where the answers above come from
  rather than an input to the choice. This document is written so that those
  recommendations are ready the day the move is made, not so that they can be
  started before it.

**The engine road is now named, and it is on this project's trunk branch, not
only in the operator's records.** On 2026-09-16 the operator decided to drop
the short-deck engine as the base. The road now runs through a published
collection of ready-made implementations of many different games, of which the
configurable poker one is the piece this project would use — OpenSpiel's
`universal_poker`. The engine the repository already has, called plain
`poker_ai` above and "the vendored `poker_ai`" in the questions at the end,
stays a reference only; it is written `fedden/poker_ai` wherever its author has
to be named, which is how a code-sharing site writes a project, author first and
project second. Written the same way, `dickreuter/Poker` is a third program, and
it is the reference for reading the table, never for play. What stays open is
who chooses the action on top of the engine — the carve-out from the forefront
rule, which the operator has not granted. The engine decision is written into
`CLAUDE.md` on this project's trunk branch: branch `worker/114e5b3f5b1b` landed
there as commit `e67825b` on 2026-09-16, and is pushed. The dated record of the
decision itself is a saved change in the separate `heater` repository where the
operator's decisions are kept — commit `fb353c6`, 2026-09-16. The two places
below that name it do so as that same decision, and no recommendation changes.
It names what the "waiting" above is waiting on.

**One consequence worth stating on its own: E7, E8 and E9 in
[R10](#r10--add-three-engine-requirements-extension-opponent_model_designmd-engine-requirements)
are questions put to a *candidate* engine, not open questions about the vendored
one.** Put to the vendored one they are already answered — no chosen bet size at
all rather than more than one, nothing to translate because there are no sizes
to translate between, and seven seats rather than nine. They belong in the
engine choice as selection criteria.

### 1.1 Three different quantities get called "table size"

They diverge, and the design document currently uses one word for all three.
Separating them is most of the work.

| Name used here | Definition | What it governs |
| --- | --- | --- |
| **Seat count** `n` | Players dealt in at the start of the hand | The positional mix; which seats exist at all; the blind frequency |
| **Field size** `m` | Opponents still live at the moment of a decision | The bluff arithmetic in `OPPONENT_MODEL_DESIGN.md` Table B |
| **Band** | A grouping of seat counts that share a baseline | A bookkeeping choice this document has to make; nothing in poker forces it |

**A note on the letter `n`, because three different quantities are written with
it and only one of them is this document's.** Everywhere in this document `n` is
the seat count in the table above — except where a quoted source uses the same
letter for something else. Two places do: Ganzfried and Sandholm's Equation 1
indexes a public history with `n`, and the design document's confidence formula
`n/(n+s)` counts opportunities with it. Both are flagged where they appear
([§2.2](#22-sizing-as-a-signal-about-the-opponent)); neither is a seat count, and
nothing in this document derives one from the other.

`m ≤ n − 1` always, and the gap is large. A nine-handed table very often plays
three-way after the flop; a three-handed table very often plays heads-up after
the flop. **Seat count determines the *distribution* of field sizes; it does not
determine the field size.** Every consequence below sorts into one of the two.

### 1.2 Why the voluntarily-put-money-in-pot rate (VPIP) is not comparable across seat counts

How often a player puts money in by choice, rather than because a blind forced
them to, is written out **voluntarily put money in pot** and written `VPIP`
everywhere below. The argument here is structural and needs no population data,
which matters because `OPPONENT_MODEL_DESIGN.md` deliberately refuses to cite
table-size-specific population averages for that rate, and this document keeps
that refusal ([Sources](#sources), "Deliberately not cited").

Preflop, action starts to the left of the big blind and ends on the big blind.
So at a table of `n` players, the seats in preflop action order have exactly
`n−1, n−2, …, 1, 0` players still to act behind them — **each value occurs exactly
once**. Over a full orbit a player therefore sits in each of those positional
contexts with probability `1/n`. That single observation drives everything in
this section.

#### Table 1: what seat count mechanically fixes

Derived; `n` is the seat count. Computed and checked by `tools/check_table_size_numbers.py`, 2026-09-15.

| `n` | Dealt in a blind (`2/n`) | On the button (`1/n`) | Neither blind nor button (`max(0, (n−3)/n)`) | Mean players still to act behind (`(n−1)/2`) |
| --- | --- | --- | --- | --- |
| 2 | 1.000 | 0.500 | 0.000 | 0.5 |
| 3 | 0.667 | 0.333 | 0.000 | 1.0 |
| 4 | 0.500 | 0.250 | 0.250 | 1.5 |
| 5 | 0.400 | 0.200 | 0.400 | 2.0 |
| 6 | 0.333 | 0.167 | 0.500 | 2.5 |
| 7 | 0.286 | 0.143 | 0.571 | 3.0 |
| 8 | 0.250 | 0.125 | 0.625 | 3.5 |
| 9 | 0.222 | 0.111 | 0.667 | 4.0 |

At `n = 2` the small blind *is* the button, which is why that row's first two
columns overlap, and why the third column carries a `max(0, ·)`: unclamped,
`(n−3)/n` is `−0.5` at `n = 2`, and no share of hands can be negative. At `n = 2`
and `n = 3` there is genuinely no seat that is neither a blind nor the button, so
`0.000` is the true value in both rows and the clamp is what makes the formula
say so. Heads-up is structurally different and gets
[§1.7](#17-heads-up-is-a-different-game-and-it-inverts-the-designs-founding-argument)
to itself.

That a player should enter more pots as fewer opponents remain behind them is the
oldest position argument in the strategy literature — [Sklansky &
Malmuth](#s-sklanskymalmuth) (**not retrieved during this survey; cited from
memory**) present full-ring starting requirements as a table
indexed by position for exactly this reason, and
`OPPONENT_MODEL_DESIGN.md` already tracks `open_raise_by_seat` on the grounds
that "position-blind opponents are the exploitable ones" (§2.3). What
[Table 1](#table-1-what-seat-count-mechanically-fixes) adds is that **the weights
attached to those positions are set by the seat count, so the aggregate moves
even when the per-position policy is frozen.**

#### Table 2: how far apart two seat counts are, as positional mixtures

Each cell is the share of one table's hands that come from positional contexts
the other table reaches at a different rate. For uniform weights `p` and `q` on
`{0,…,n−1}` and `{0,…,m−1}`, that share is `½·Σ|p−q|`; the name for it is the
**total variation distance** between the two positional-weight vectors, written
`TV` below. Computed and checked by `tools/check_table_size_numbers.py`, 2026-09-15.

| | `n`=2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **2** | 0.000 | 0.333 | 0.500 | 0.600 | 0.667 | 0.714 | 0.750 | 0.778 |
| **3** | 0.333 | 0.000 | 0.250 | 0.400 | 0.500 | 0.571 | 0.625 | 0.667 |
| **4** | 0.500 | 0.250 | 0.000 | 0.200 | 0.333 | 0.429 | 0.500 | 0.556 |
| **5** | 0.600 | 0.400 | 0.200 | 0.000 | 0.167 | 0.286 | 0.375 | 0.444 |
| **6** | 0.667 | 0.500 | 0.333 | 0.167 | 0.000 | 0.143 | 0.250 | 0.333 |
| **7** | 0.714 | 0.571 | 0.429 | 0.286 | 0.143 | 0.000 | 0.125 | 0.222 |
| **8** | 0.750 | 0.625 | 0.500 | 0.375 | 0.250 | 0.125 | 0.000 | 0.111 |
| **9** | 0.778 | 0.667 | 0.556 | 0.444 | 0.333 | 0.222 | 0.111 | 0.000 |

**The bound this gives.** If a player's per-position VPIP is a fixed vector `v`
and the two seat counts impose weight vectors `p` and `q`, the aggregate VPIP
difference is `|Σ(p−q)·v|`, which is bounded above by
`TV(p,q) · (max v − min v)`. That is a standard consequence of the total
variation definition, not a poker claim.

#### Table 3: the swing that costs nothing but a change of seat count

The bound above, evaluated. **The `max v − min v` column is an illustrative
spread, not a measured or cited quantity** — it stands for how much more often a
person plays from the button than from under the gun, which nobody here has
measured. It is on exactly the footing of the illustrative `p̂` anchors in
`OPPONENT_MODEL_DESIGN.md` Table C. The `TV` column is the **total variation
distance** of [Table 2](#table-2-how-far-apart-two-seat-counts-are-as-positional-mixtures),
carried across unchanged.
Computed and checked by `tools/check_table_size_numbers.py`, 2026-09-15.

| Comparison | TV | Spread 0.30 | Spread 0.50 | Spread 0.70 |
| --- | --- | --- | --- | --- |
| 9-max vs 6-max | 0.333 | ≤ 0.100 | ≤ 0.167 | ≤ 0.233 |
| 9-max vs 3-handed | 0.667 | ≤ 0.200 | ≤ 0.333 | ≤ 0.467 |
| 9-max vs heads-up | 0.778 | ≤ 0.233 | ≤ 0.389 | ≤ 0.544 |
| 6-max vs 3-handed | 0.500 | ≤ 0.150 | ≤ 0.250 | ≤ 0.350 |
| 6-max vs heads-up | 0.667 | ≤ 0.200 | ≤ 0.333 | ≤ 0.467 |
| 3-handed vs heads-up | 0.333 | ≤ 0.100 | ≤ 0.167 | ≤ 0.233 |

**The consequence, and the exact weight it can carry.** These are **upper
bounds**. They say how far the aggregate *can* move when only the seat count
changes; they do not say how far it does, and the realised shift is smaller by
however much a real player's per-position VPIP varies less than the illustrative
spread column assumes. An upper bound cannot establish that anything *will*
happen, and this document does not claim it does.

What the bound does establish is that the possibility is not excluded by the
arithmetic. `VPIP_SPLIT` in `OPPONENT_MODEL_DESIGN.md` §4.4 defaults to `0.28`,
and six of the seven flags in the same section fire at a gap of `0.15`, the
seventh — `NEVER_RAISES` — at `0.05` on each of its two legs. A bound of
`0.2`–`0.47` between 9-max and 3-handed is not a rounding error against
thresholds of that size — **it can exceed both, so a shift large enough to move a
player across the tight/loose boundary, or to fire or suppress an exploit flag
with no change in the person at all, is admitted rather than ruled out.** A
single global `BASELINE[vpip]` pooled across every seat count the bot has ever
played **can** therefore misclassify in a systematic direction: reading
short-table players as loose and full-ring players as tight.

**The measurement that would settle it, and it is cheap.** Whether the shift is
real and how large it is are questions for Tier 0's own logged hands, not for
this argument: **compute each opponent's `vpip` separately per seat-count band,
and report, for opponents with enough hands in two or more bands, the
distribution of the same person's band-to-band difference** — alongside the
per-band population median. That distribution is the realised shift the bound
only caps. If its bulk sits well inside `0.15`, banding `BASELINE` is tidiness
and can be dropped; if not, [R2](#r2--make-baseline-and-both-split-thresholds-per-band-correction-43-and-44)
is necessary on measured grounds rather than on an admitted possibility. Until
that number exists, R2 bands the *population* baseline anyway, because the bound
admits a shift larger than the thresholds and banding a pooled baseline is cheap
([§1.6](#16-what-banding-costs)) — a precaution against a possibility, which is
what it should be called.

The same argument applies with different weights to every stat whose rate
depends on the seat and is therefore a mixture over seats — `pfr`, `limp`,
`open_raise`, `three_bet`, `fold_to_steal` — and applies not at all to stats
whose opportunity is defined by a situation rather than by a seat, such as
`fold_to_cbet`, or by an outcome of the whole hand, such as the share of the
hands a player took to a showdown that they won money in —
**won at showdown**, written `wsd`.
[§3](#3-recommended-reconciliation-with-opponent_model_designmd)
turns that split into a per-stat recommendation, because it is what keeps the
fragmentation cost in [§1.6](#16-what-banding-costs) affordable.

### 1.3 Table size versus field size: where the multiway arithmetic actually attaches

`OPPONENT_MODEL_DESIGN.md` Table B computes
the collapse of bluff success as the number of opponents rises, and §2.4 builds
the whole strategic stance on it. Every entry in that table is indexed by **live
opponents**, which is field size `m`, not seat count `n`. The design document is
already correct on this: its §6 gives V5 one extra report, **bluff frequency
broken down by the number of live opponents**, and §2.4 and §4.6's "Multiway
gate" column both read that breakdown as the check on whether the engine's output
carries the multiway discount.

What changes with the 2-to-9 requirement is that **the distribution of `m` is now
something the bot ranges over rather than a fixed property of its table.** Two
recommendations follow, both in [§3](#3-recommended-reconciliation-with-opponent_model_designmd):
V5's existing breakdown should be cross-tabulated by seat count as well as by
field size, and the Tier 1 solve — which §4.5 already requires to be run at "the
seat count of the live game" — is the **32 runs** §4.5 and E5 now both state,
which is a cost question for the operator
([§4](#4-questions-for-the-operator)) and, against the operator's compute cap, a
question about which solver can do it at all. §4.5 also marks that whole solve
plan as conditional on a pending decision: `ENGINE_ALTERNATIVES.md` recommends
computing decisions at play time instead, and if that is accepted the 32 runs do
not happen at all.

### 1.4 Two stat definitions that break outright below six players

These are not adjustments. They are definitions in `OPPONENT_MODEL_DESIGN.md`
§4.2 that produce wrong or empty counters at small seat counts, and a coding task
implementing them literally would silently corrupt the affected stats.

**`open_raise` is keyed on which named group of seats the player is sitting in —
early position, middle position, late position, small blind and big blind,
written `EP`, `MP`, `LP`, `SB` and `BB` here and below.** At `n = 3` the only
non-blind seat is the button, so `EP` and `MP` are empty for every hand and `LP`
absorbs all of it; at `n = 2` there is no non-blind seat at all, because the
small blind is the button. The context key is not defined below about six
players, and worse, it is not *comparable* between six and nine, because "early
position" at 6-max is a seat with three players behind and at 9-max is a seat
with six. **The causally correct key is the number of players still to act behind
the player preflop**, which is defined at every seat count, means the same thing
at every seat count, and — by the `1/n` observation in
[§1.2](#12-why-the-voluntarily-put-money-in-pot-rate-vpip-is-not-comparable-across-seat-counts)
— takes each of its values exactly once per orbit. Keying on it lets
position-dependent stats pool *across* seat counts legitimately instead of
fragmenting, which is the cheapest available answer to
[§1.6](#16-what-banding-costs).

**`fold_to_steal`'s opportunity is "in `SB` or `BB` facing a `LP` open with no
other caller".** At `n = 3` every button open is by construction a late-position
open, so the stat silently becomes "fold to a button open". At `n = 2` the small
blind is the only possible opener and the big blind is the only possible
defender, so the stat becomes "fold to any open" — which is not a steal-defence
statistic at all but the complement of the total defence frequency, a quantity
whose correct value is given by the minimum-defence-frequency column of
`OPPONENT_MODEL_DESIGN.md` Table A rather than by
anything about the opponent's stealing habits. The same stored number would mean
three different things across the range the operator has now required.

### 1.5 The published thresholds are themselves table-size mixtures

This one weakens a threshold `OPPONENT_MODEL_DESIGN.md` currently leans on, and
is worth stating because it changes how much trust the bootstrap deserves.

The aggression half of the threshold quoted below turns on how hard a player
pushes, measured as their bets and raises divided by their calls —
`OPPONENT_MODEL_DESIGN.md` §2.2 calls that ratio the **aggression factor** and
writes it `AF`. The `AF > 1` in the quotation is that ratio;
`AFQ_SPLIT` is the cut-off on a different rate — the design's `afq`,
aggression frequency: bets or raises over *all* voluntary actions, folds
included — which descends from `AF` but is not it.
`VPIP_SPLIT = 0.28` and `AFQ_SPLIT = 0.50` descend from the "folds ≥ 72% of hands
is tight, AF > 1 is aggressive" thresholds that [Teofilo &
Reis 2011](#s-teofilo2011) — which *was* retrieved and read — reports at its §3,
citing two works it took them from: [Billings 2006](#s-billings2006)
(**not retrieved by either survey**) for the numeric classification and
[Sklansky](#s-sklansky) (**also not retrieved**) for the tight/loose,
passive/aggressive taxonomy behind it. That is the attribution
`OPPONENT_MODEL_DESIGN.md` makes at its §2.2 and in its Sources, and this
document follows it. The
design document already flags two problems with them: they are cited at second
hand, and fold rate and VPIP do not sum to 1. There is a third, and it is about
the corpus those thresholds were fitted on.

**Whose corpus that is matters, and it is not the one the design document
describes.** The 51,377,820-game real-money **tournament** corpus that
`OPPONENT_MODEL_DESIGN.md` §2.1 and its [Sources](#sources) entry describe is
**Teofilo and Reis's own**. It is the source of the 4.52% showdown ratio this
document leans on in [§2](#2-continuous-bet-sizing); it is
**not** the source of the 72% / AF > 1 thresholds, which Teofilo and Reis report
from Billings' thesis and Sklansky. The two must not be run together, and an
earlier draft of this section did exactly that.

**So the thresholds' own corpus is unknown to this document.** Neither Billings
2006 nor Sklansky was retrieved by either survey, so nothing here is known about
the corpus behind the numeric thresholds — its size, its
stakes, its era, or — the point of this section — **the seat counts it
contained**. What can still be said is structural and needs no knowledge of the
corpus: a fold rate or an aggression factor averaged over any corpus is
**an average over whatever mixture of seat counts that corpus happened to hold**,
and by [Table 3](#table-3-the-swing-that-costs-nothing-but-a-change-of-seat-count)
two different mixtures can differ by more than the threshold's own distance from
its neighbours. Here the mixture is not merely varying, as it would be within a
tournament; it is **unrecorded**, so the offset it induces cannot be signed, let
alone sized.

The conclusion is not that the threshold is wrong. It is that **it is not known
to be a threshold for any particular seat count**, and so it cannot be corrected
into one by any amount of arithmetic on this side. It is a starting value for the
bootstrap and nothing more — which is what §4.4 already says, for different
reasons, when it specifies that both splits are replaced by the bot's own
population median once enough data exists. This section strengthens that
replacement from "preferable" to "necessary", and adds that **the median must be
taken per band**, not globally. V4 in §6 should record the seat-count mixture of
the population it measured, so that the disagreement it reports can be read
correctly.

### 1.6 What banding costs

Splitting a statistic by seat-count band is not free, and the cost is exactly the
arithmetic already in `OPPONENT_MODEL_DESIGN.md` Table C: the opportunities needed for
a confidence interval of a given half-width depend only on the target width and
the anchor proportion, so **stratifying into `k` bands multiplies the hands
needed by `k`, per band.** Four bands means four times the hands before any band
is as trustworthy as the unstratified stat was.

#### Table 4: the fragmentation multiplier

Applied to two of Table C's rows. **Those row values are illustrative in the
source table and stay illustrative here**; what is real is the multiplier. The
first column's `±5pp` and `±10pp` are interval half-widths measured in
**percentage points** — a gap between two percentages, not a percentage of a
percentage — written `pp` here and everywhere below.
Computed and checked by `tools/check_table_size_numbers.py`, 2026-09-15.

| Stat | Table C hands (illustrative) | × 4 bands | × 4 size buckets ([§2.5](#25-what-sizing-buckets-cost)) | × both |
| --- | --- | --- | --- | --- |
| `vpip` (±5pp) | 323 | 1,292 | n/a | 1,292 |
| `fold_to_cbet` (±10pp) | 640 | 2,560 | 2,560 | 10,240 |

Ten thousand hands against one person is not a quantity this project will have.
**Banding and size-bucketing cannot both be applied to the same stat and still
produce a usable per-opponent number.** That constraint, not elegance, is what
shapes the recommendations in [§3](#3-recommended-reconciliation-with-opponent_model_designmd):
band the *population baseline*, where hands from every opponent pool together and
`MIN_POOL_HANDS` is reachable; do **not** band the per-opponent counters except
where the definition forces it.

There is a second, smaller fragmentation effect that is pure arithmetic from
[Table 1](#table-1-what-seat-count-mechanically-fixes): a stat whose opportunity
requires the player to be in a blind occurs on at most `2/n` of hands. **The
blind frequency itself is 4.5 times higher heads-up than at 9-max** — `1.000`
against `0.222` in Table 1's first column. That ratio is a fact about the blinds
and nothing else; it is not the hands multiplier for any stat gated behind them.

`fold_to_steal` is the affected stat, and its realised multiplier is not 4.5,
because its opportunity is the blind frequency times a conditional rate that is
**not constant in `n`**. [§1.4](#14-two-stat-definitions-that-break-outright-below-six-players)
fixes that rate at one end: at `n = 2` the small blind is the only possible
opener, so only the big blind can ever be the defender and only `1/2` of the
hands in a blind are opportunities at all. Against an unrestricted `2/9` at
9-max that gives **2.25 times as many hands at 9-max as heads-up**, on §1.4's
reasoning. The 9-max conditional rate is below 1 as well — the open must come
from a late-position player with no other caller — and it moves the multiplier
the other way, so 2.25 does not bound it either. The true multiplier is a
measurement, not a derivation. Table C should carry an
opportunities-per-hand column that is band-dependent for this stat and filled
from logged hands.

### 1.7 Heads-up is a different game, and it inverts the design's founding argument

`OPPONENT_MODEL_DESIGN.md` §1 justifies not chasing game-theory-optimal play by
quoting [Brown 2020](#s-brown2020) §6.6: computing a Nash equilibrium for
multiplayer games belongs to a class of problems for which no method that
finishes in reasonable time is known or expected — **PPAD-complete** — and even
a computed equilibrium carries no guarantee, because independently-computed
equilibrium strategies need not form one jointly. That argument is explicitly
about games with **more than two players**. At `n = 2` it does not apply:
heads-up poker is two-player zero-sum, an equilibrium strategy is unbeatable
in expectation regardless of the opponent, and the design document's own §1
says so two sentences earlier in the same paragraph as the one it builds on.

This is not an academic point. It reverses the risk calculus at one end of the
now-required range:

- **At `n = 2`, deviation is the risk and the blueprint is the safe harbour.**
  This is precisely the Libratus position the design document already quotes:
  "trying to exploit the opponent opens oneself to being exploited. Therefore,
  Libratus generally did not do opponent exploitation" ([Brown
  2020](#s-brown2020), §6.4) — and Libratus was a heads-up program.
- **At `n = 9`, the equilibrium guarantee does not exist to be given up**, the
  opponents are the weakest, and exploitation is the whole plan.

The recommendation that follows is a single one, and it is cheap: **the deviation
cap in §5.2 should be a function of seat count**, tightest at `n = 2` and loosest
at large `n`. It reuses machinery already specified — the `Pmax` of the
**data-biased response** of [Johanson & Bowling 2009](#s-johanson2009), who
describe it as setting "a tradeoff between" exploitation and exploitability and
who write it `DBR` — by making one constant into a small table. `DBR` here and
`DBBR` in [§2.2](#22-sizing-as-a-signal-about-the-opponent) are two different
methods by two different sets of authors, not one name spelt two ways: DBBR is
the deviation-based best response of Ganzfried and Sandholm.

Note also that the two solved-poker results sit on opposite sides of this line:
heads-up limit hold'em was solved to a known approximation
([Bowling et al. 2015](#s-bowling2015), **not retrieved for this survey**), and
no comparable result exists or can exist at `n ≥ 3`. Nothing in this design
depends on that; it is context for why the `n = 2` case is different in kind.

---

## 2. Continuous bet sizing

**Nothing in this section is reachable on the engine the repository has.** Its
betting is fixed-limit — one fixed raise amount, at most three raises a street,
"no bet-sizing dimension anywhere in the tree"
(`REFERENCE_NOTES.md`:523-542) — so there are no sizes for the bot to choose, no
sizes for an opponent to choose, and nothing for any of the stats below to
measure. This section waits on the OpenSpiel move: the engine road the
operator's recorded decision names, and the one the reconciliation of the four
survey documents — `ENGINE_ALTERNATIVES.md`, `RESOURCES_BOTS.md`,
`RESOURCES_SOLVERS.md` and `RESOURCES_EXPLOITATION.md` — is made against.
[§1.0](#10-the-engine-this-project-has-today-already-answers-two-of-these-questions-and-answers-them-no)
is where that dependency is set out in full. The argument does not change with
the engine; only the date it can be acted on does.

### 2.1 What "true no-limit" changes

A fixed-increment game has a small action set at every decision. True no-limit
has a continuum: any amount from the minimum raise to the player's stack. Three
consequences, and the design document addresses none of them.

1. **Every bet carries a second channel of information** — not just *that* the
   opponent bet, but *how much*, measured against the pot. This arrives on every
   bet, which makes it far cheaper than the showdown information the design
   document correctly says will starve at a 4.52% showdown ratio
   ([Teofilo & Reis 2011](#s-teofilo2011)).
2. **The bot's own bet amounts are the same channel, pointed the other way.**
3. **The engine's action set is discrete and the game's is not**, so opponents'
   bets will routinely fall outside it and must be mapped onto it. This is a
   named, published problem with a named, published solution, and it is currently
   absent from the design document's Engine requirements.

### 2.2 Sizing as a signal about the opponent

**The quantity to track is the bet as a fraction of the pot, never the bet in big
blinds.** `OPPONENT_MODEL_DESIGN.md`'s entire bluff arithmetic
(`OPPONENT_MODEL_DESIGN.md` Table A) is parameterised by
`s = B/P`, and every threshold in it — break-even fold frequency `s/(1+s)`,
minimum defence frequency `1/(1+s)`, balanced bluff share `s/(1+2s)` — is a
function of that ratio alone. A bet measured in big blinds is not comparable
between a 4bb pot and a 40bb pot; a bet measured in pot fractions is.

Three stats follow, in the design document's own `(numerator, denominator)`
form, all computable from observed actions alone and none requiring a showdown.

**(a) `bet_size_dist[street, role]` — a distribution, not a rate.** For each
street and each role (bettor first-in, raiser, three-bettor), the counts of the
opponent's bets falling in each size bucket. This does not fit the binomial
shrinkage in §4.3, but it fits its source directly: Equation 1 of the
**deviation-based best response** of
[Ganzfried & Sandholm 2011](#s-ganzfried2011) §4.2, written `DBBR`, is already
stated over an action set `a` at a public history, which **the paper** indexes
with `n` — the paper's own letter for its own quantity, and not this document's
seat count. It is a Dirichlet posterior over a categorical outcome. Making
`BASELINE[stat]` a *vector* over size buckets and applying the identical
equation is the natural extension and requires no new mechanism, only a
vector-valued baseline.
`confidence = n/(n+s)` is unchanged, where that `n` is **the design document's
opportunity count** — a third use of the letter again, and again not the seat
count.

**(b) `fold_to_bet[street, size_bucket]` — the directly monetisable one.** How
often this opponent folds conditional on the size they are facing. This is the
stat that turns sizing into money, because
`OPPONENT_MODEL_DESIGN.md` Table A already gives the
break-even fold frequency for each size, and an opponent whose measured fold rate
in a bucket exceeds that row's break-even figure is, in that bucket specifically,
paying for the privilege. It is a plain binomial rate and drops straight into the
existing shrinkage and flag machinery.

**(c) Sizing dispersion, as a cheap early diagnostic.** A player who bets the
same fraction in every spot has a zero-information sizing distribution; a player
whose sizing varies is either balanced or leaking, and telling which requires
outcomes. Dispersion is computable from (a) at no extra cost and converges much
faster than the correlation with strength, because it needs no showdowns. Treat
it as a *diagnostic that selects which opponents are worth measuring further*,
not as an exploit on its own.

**The slow one, named so a later task does not over-promise it.** The genuine
"bet-sizing tell" — a correlation between an opponent's chosen size and their
actual hand strength — needs strength to be observed, which needs a showdown. At
a 4.52% showdown ratio ([Teofilo & Reis 2011](#s-teofilo2011)), and after
splitting by street and by size bucket, this is slower than every Tier C stat in
the design document. It belongs in the stat list as corroboration, on the same
footing as `showdown_holdings`, and no exploit should gate on it.

**Bucket boundaries.** Recommended: `≤ 0.40`, `(0.40, 0.70]`, `(0.70, 1.10]`,
`> 1.10` of pot, with **all-in as its own bucket** regardless of ratio, because
an all-in is bounded by the stack rather than chosen and carries different
information. These four boundaries are **unmeasured design choices**, placed to
straddle the rows of
`OPPONENT_MODEL_DESIGN.md` Table A rather than derived
from anything; they belong in config. Four buckets is chosen against the
fragmentation cost in [§2.5](#25-what-sizing-buckets-cost), not for any other
reason.

### 2.3 Sizing as a signal about us

**This is the most consequential section of this document, because it identifies
a way the bot can be made readable by a single line of ordinary-looking
integration code.**

The engine's strategy is a *mixed* strategy: at a given decision it holds a
probability distribution over actions, and the published work treats that
distribution as the strategy itself — `OPPONENT_MODEL_DESIGN.md` requirement E1
already asks whether the engine can be queried for it rather than only for a
sampled action. Randomisation is not decoration on top of the strategy; it *is*
the strategy. Three failure modes destroy it, in increasing order of how
innocent they look.

**Failure 1: taking the most likely action.** If the integration layer queries
the distribution and plays its argmax, the bot's behaviour at every decision
becomes deterministic. Its bet sizes collapse to a point mass per spot, it never
bluffs in a spot where bluffing is the minority action, and any human who watches
long enough can read it exactly. This is not a poker judgment made by
AI-written code — it is AI-written code *deleting* a poker judgment the engine
already made. **The rule is: sample from the engine's action distribution; never
take its maximum.** A later task should treat an argmax in the action path as a
defect with a reproducing test, not as a style preference.

**Failure 2: an abstraction with one bet size per spot.** If the engine's action
abstraction offers a single size at a decision, no amount of correct sampling
recovers variety, because there is none to recover. The bot is then a point mass
at that size by construction. Nothing outside the engine can fix this without
breaking the forefront rule, because choosing a different amount *is* choosing a
poker action. **This is an engine requirement, and if the engine cannot satisfy
it, the correct response is to report that and stop, exactly as §4.5 already
instructs for Tier 1 and requirement E2** — not to add a randomiser outside the
engine. That instinct will occur to somebody; it must be refused explicitly.

**The engine in the repository already fails this, and fails it at the limit.**
It does not offer one size per spot; it offers no chosen size at all, a raise
being a fixed amount fixed by the rules
(`REFERENCE_NOTES.md`:523-542,
[§1.0](#10-the-engine-this-project-has-today-already-answers-two-of-these-questions-and-answers-them-no)).
So this failure is not a risk to guard against on the current engine — it is
that engine's settled condition, and the requirement stated here is a condition
on its replacement.

**Failure 3: deterministic action translation.** When an opponent bets an amount
not in the engine's abstraction, something must map it onto one that is. A
deterministic map — "anything up to 0.7 of pot is treated as a half-pot bet" —
creates a threshold that an attentive opponent can locate by probing and then sit
just inside, getting a large bet treated as a small one for free.
[Ganzfried & Sandholm 2013](#s-ganzfried2013) (**not retrieved during this
survey**) is the standard treatment: it states axioms an action-translation
mapping should satisfy, shows that the natural deterministic and naive randomised
mappings violate them in ways an opponent can exploit, and proposes the
**pseudo-harmonic mapping**, which maps an observed bet `x` between abstraction
sizes `A < x < B` to `A` with probability

```
f_{A,B}(x) = ((B − x)(1 + A)) / ((B − A)(1 + x))
```

and to `B` otherwise. **The formula is quoted from memory and was not verified
against the primary text; confirm it before implementing.** The behaviour it
produces is not: it is a randomised map, biased toward the nearer endpoint but
never certain, which is what removes the exploitable threshold.

#### Table 5: what mis-reading a bet size costs, exactly

Why translation is worth getting right rather than approximating. Calling a bet
of `B` into a pot of `P` requires pot equity `B/(P + 2B)`; the columns give the
error in required equity if the bot acts on the wrong size. `P = 1`. Computed
and checked by `tools/check_table_size_numbers.py`, 2026-09-15.

| Actual bet (pot fractions) | True required equity | Error if treated as 0.5 pot | Error if treated as 1.0 pot |
| --- | --- | --- | --- |
| 0.33 | 19.9% | −5.1pp | −13.5pp |
| 0.50 | 25.0% | 0.0pp | −8.3pp |
| 0.60 | 27.3% | +2.3pp | −6.1pp |
| 0.75 | 30.0% | +5.0pp | −3.3pp |
| 1.00 | 33.3% | +8.3pp | 0.0pp |
| 1.50 | 37.5% | +12.5pp | +4.2pp |
| 2.00 | 40.0% | +15.0pp | +6.7pp |

A positive error is the bot calling with hands that do not have the equity to
call. **An opponent who finds the threshold can convert the whole error column
into profit by always betting just inside it** — which is exactly the attack the
pseudo-harmonic mapping exists to blunt.

### 2.4 What the strategy literature says about choosing sizes

Held to the same standard the design document sets for §4.6: **descriptive, not
prescriptive.** The engine produces the bot's sizes. This is here so that a
person reviewing the bot's play can tell whether its sizing looks sane, and if
the engine's output disagrees with anything below, the engine is right.

**Size and bluff share are locked together, and the design document already has
the arithmetic.** `OPPONENT_MODEL_DESIGN.md` Table A
gives the balanced bluff share `s/(1+2s)` rising from 19.9% at a third-pot bet to
33.3% at a pot-sized bet. The practical reading: **a bettor cannot choose a size
and a bluff frequency independently.** A strategy that uses large sizes without
carrying proportionally more bluffs is over-valuing, and one that uses small
sizes with a large-size bluff share is over-bluffing. Both are readable and both
are measurable in the bot's own logged output, which is [R12](#r12--add-v6-the-bots-own-sizing-distribution-extension-6) below.

**Why more than one size exists at all.** The standard account — [Chen &
Ankenman](#s-chenankenman) and [Janda](#s-janda), **neither retrieved during this
survey**, both cited from memory — is that the right size depends on the shape of
the betting range: a *polarised* range (very strong hands and bluffs, little in
between) wants large bets, because the strong hands are paid more and the bluffs
are cheaper to make credible; a *merged* or condensed range (many medium hands)
wants small bets, because medium hands cannot profitably charge a large price.
Since the shape of the range differs by spot, a single size for all spots is
leaving expected value behind. **Treat this paragraph as a reviewer's sanity
check, not as a specification**; the claim is one this survey could not verify
directly.

**One sizing result is derivable rather than cited, and is worth having.** If a
bettor intends to get all-in by the river using the same pot fraction `f` on each
of `k` remaining streets, then each bet-and-call multiplies the pot by `(1 + 2f)`,
and, writing the stack-to-pot ratio — the stack behind divided by the pot —
as `SPR`, getting all-in in `k` such bets means `(1 + 2f)^k = 1 + 2·SPR`.

#### Table 6: pot fraction needed to reach all-in in `k` equal bets

Derived from `(1 + 2f)^k = 1 + 2·SPR`. Computed and checked by `tools/check_table_size_numbers.py`, 2026-09-15.

| SPR | `f` in 1 street | `f` in 2 streets | `f` in 3 streets |
| --- | --- | --- | --- |
| 1 | 1.00 | 0.37 | 0.22 |
| 2 | 2.00 | 0.62 | 0.35 |
| 4 | 4.00 | 1.00 | 0.54 |
| 6 | 6.00 | 1.30 | 0.68 |
| 10 | 10.00 | 1.79 | 0.88 |
| 20 | 20.00 | 2.70 | 1.22 |

This has one narrow use here and should not be over-read: **it shows that the
range of sizes a sound no-limit strategy needs is wide** — from roughly a fifth
of the pot to several times it, across ordinary stack depths — which is the
concrete form of the requirement in Failure 2 of
[§2.3](#23-sizing-as-a-signal-about-us). An abstraction offering two sizes cannot
express this. It is **not** a rule for the bot to follow; whether to get all-in
at all is a poker judgment reserved to the engine.

**The relevant caution about enlarging the abstraction.** More sizes is not
automatically better: [Waugh et al. 2009](#s-waugh2009) (**not retrieved during
this survey**) report abstraction pathologies in extensive-form games, where
refining an abstraction can produce a *worse*-performing strategy. The
corroborating data point usually reached for here — that Pluribus used a small
discrete set of bet sizes and beat elite professionals at six-player no-limit —
is **cited from memory and was not retrieved**
([Pluribus's bet-size abstraction](#s-pluribus-sizing)): no web retrieval was
available to this task, and `OPPONENT_MODEL_DESIGN.md`, which did retrieve
[Brown 2020](#s-brown2020), does not state it. **Nothing here rests on it.** The
recommendation — "more than one size per spot, and measure", not "as many sizes
as possible" — stands on
[Table 6](#table-6-pot-fraction-needed-to-reach-all-in-in-k-equal-bets)'s derived
arithmetic for the lower end and on Waugh for the caution at the upper end, and
E7 in [R10](#r10--add-three-engine-requirements-extension-opponent_model_designmd-engine-requirements)
asks the engine for its own count rather than assuming anybody else's.

### 2.5 What sizing buckets cost

The same arithmetic as [§1.6](#16-what-banding-costs): splitting `fold_to_bet`
into four size buckets multiplies the opportunities needed for a given interval
width by four.
[Table 4](#table-4-the-fragmentation-multiplier) puts `fold_to_cbet` at roughly
2,560 hands under a four-way split, against the illustrative 640 unsplit.

Two mitigations, and they are the same shape as the fallback chain already
specified in `OPPONENT_MODEL_DESIGN.md` §4.2:

- **Fall back up the bucket hierarchy.** When `fold_to_bet[street, bucket]` is
  thin, back off to `fold_to_bet[street]` pooled over sizes, then to the
  opponent's `fold_to_cbet`, then to the archetype bucket, then to the
  blueprint. Implement it as an explicit chain, which is what §4.2 already
  requires for the unsized case.
- **Collapse to two buckets for the per-opponent stat and keep four for the
  population baseline.** The population baseline pools across every opponent and
  can afford the resolution; a single opponent cannot. A two-way
  small-versus-large split at 0.70 of pot halves the cost and still separates the
  two ends of `OPPONENT_MODEL_DESIGN.md` Table A, where
  break-even fold frequency differs by **25.2 percentage points** between the
  `0.33` row (24.8%) and the `1.00` row (50.0%).

---

## 3. Recommended reconciliation with `OPPONENT_MODEL_DESIGN.md`

**This document does not make these edits.** Each item names the section to
change and states the change precisely enough to be applied without re-deciding
it. They are ordered so that an earlier item never depends on a later one, and
each is marked as either a **correction** (the current text is wrong at some seat
count) or an **extension** (the current text is right but incomplete).

### R1 — Define the seat-count band as a `context` value, not a new table. *(Extension. §4.2.)*

The `stat` table's schema already carries a `context TEXT NOT NULL DEFAULT ''`
column, introduced for seat buckets and streets. Banding needs no schema change:
encode it in that column, as `band=<label>`, composed with any existing context
key.

Recommended bands: **`HU` = 2, `SHORT` = 3–4, `MID` = 5–6, `FULL` = 7–9.**

**Two things force part of this, and nothing forces the rest.** `n = 2` must
stand alone, because [§1.7](#17-heads-up-is-a-different-game-and-it-inverts-the-designs-founding-argument)
shows heads-up is a different game — two-player zero-sum, the one setting the
design document's founding argument does not reach. And `n = 8` and `n = 9` must
share a band, because the operator's table-size priority, recorded 2026-09-15,
treats them as the same thing ([Q4](#4-questions-for-the-operator)); the same
priority puts the bulk of the hands at `n = 6`, so whichever band holds `6` is
the one that will fill first.

**`FULL` will be partly empty for as long as the current engine is the engine.**
That engine seats seven at most, so of `FULL`'s three seat counts only `7` can
produce a hand on it at all, and `8` and `9` wait on the engine choice
(`REFERENCE_NOTES.md`:499-503,
[§1.0](#10-the-engine-this-project-has-today-already-answers-two-of-these-questions-and-answers-them-no)).
The band definition is unaffected — it is a label on a stored hand, and a band
with no hands in it simply falls back, which is what
[R2](#r2--make-baseline-and-both-split-thresholds-per-band-correction-43-and-44)'s
chain is for — but a coding task should not read an empty `FULL` band as a
defect.

**Everything else — the `4|5` and `6|7` cuts — is an unmeasured bookkeeping
choice, and [Table 2](#table-2-how-far-apart-two-seat-counts-are-as-positional-mixtures)
does not support it.** It cannot: the distance between adjacent seat counts `n`
and `n+1` is exactly `1/(n+1)`, which decreases strictly as `n` grows, so no
interior boundary is a local maximum of that distance and no placement of one can
be justified by it. The table says so directly — the across-band steps `4|5`
(0.200) and `6|7` (0.143) are both *smaller* than the within-band step `3|4`
(0.250). What the choice actually does is hold the number of strata at four,
which is the fragmentation cost [§1.6](#16-what-banding-costs) prices, while
keeping each band's seat counts adjacent. It belongs in config, and it is to be
revisited if V3's calibration is materially better under a different grouping —
which is the only evidence that could settle it.

The `HandRecord` in §4.3 Step 1 already records every player's seat; it must also
record the seat count `n` explicitly, so that band assignment is a property of
the record and not re-derived later.

### R2 — Make `BASELINE` and both split thresholds per band. *(Correction. §4.3 and §4.4.)*

`BASELINE[stat]` becomes `BASELINE[stat, band]`, pooled over stored opponents'
hands *within that band*, with an explicit fallback chain when the band is thin:
**band baseline → global baseline pooled over all bands → the blueprint's own
action frequency at the corresponding decision.** The third step is the
substitution DBBR already makes and §4.3 already specifies; this only adds a
middle rung.

`MIN_POOL_HANDS = 200` and `MIN_POOL_OPPONENTS = 20` must be satisfied **within
the band**, not globally, or the fallback fires. Likewise the population medians
that replace `VPIP_SPLIT` and `AFQ_SPLIT` are taken per band.

This pooling stays on the allowed side of the live-field line in §1 of the design
document, and for the same reason: the band is a property of the *stored hand*,
not of who is sitting at the table now, and an opponent enters the pool by having
played hands in that band, never by being seated. A coding task must not
reinterpret "band" as "the current table", which would restrict the pool to the
live field.

Grounding, and the exact weight it carries:
[Table 3](#table-3-the-swing-that-costs-nothing-but-a-change-of-seat-count) — the
cross-band aggregate shift **bound** exceeds both the `0.28` split and the `0.15`
margin six of the seven §4.4 flags use, so a shift that matters is admitted,
though a bound does not show one occurs
([§1.2](#12-why-the-voluntarily-put-money-in-pot-rate-vpip-is-not-comparable-across-seat-counts)
names the Tier 0 measurement that would) — and
[§1.5](#15-the-published-thresholds-are-themselves-table-size-mixtures), where the
literature threshold turns out to be a mixture over an unknown set of seat counts
and so cannot serve as a per-band value for any band. Banding a **population**
baseline is cheap ([§1.6](#16-what-banding-costs)), which is why this is worth
doing against an admitted possibility rather than a measured effect; banding the
per-opponent counters is not, and R2 does not ask for it.

### R3 — Replace the `EP`/`MP`/`LP`/`SB`/`BB` context key with players-to-act-behind. *(Correction. §4.2.)*

`open_raise`'s context key is undefined at `n ≤ 3` and not comparable between 6
and 9 ([§1.4](#14-two-stat-definitions-that-break-outright-below-six-players)).
Replace it with `behind=<k>` for `k ∈ {0, 1, 2, 3, 4, 5+}` plus a separate
`blind=SB|BB|none` flag, both derived from the recorded seat count.

**This is the single highest-value item in this list**, because it is the one
change that lets position-dependent stats pool *across* bands instead of
fragmenting — a player's button hands are the `behind=2` hands at 3-handed and
also at 9-max — which directly buys back the `k×` cost that
[Table 4](#table-4-the-fragmentation-multiplier) imposes.

### R4 — Redefine `fold_to_steal`'s opportunity, or split it. *(Correction. §4.2.)*

As written the stat means three different things across 2 to 9 players
([§1.4](#14-two-stat-definitions-that-break-outright-below-six-players)).
Recommended: define the opportunity as **"in a blind, facing an open from a
player with `behind ≤ 1`, with no other caller"**, which is well-defined at every
seat count once R3 lands, and record `behind` of the opener in the context so
that the heads-up case is separable rather than silently merged. Add
`fold_to_steal`'s band-dependent opportunity rate to Table C: it is bounded above
by the blind frequency `2/n` ([Table 1](#table-1-what-seat-count-mechanically-fixes)),
which is itself **4.5 times higher heads-up than at 9-max**. The multiplier the
stat actually pays is nearer **2.25×**, because at `n = 2` only the big blind can
defend, and it is a quantity to measure rather than derive
([§1.6](#16-what-banding-costs)).

### R5 — Do **not** add a table-size dimension to the bucket grid or the archetypes. *(Extension. §4.4 and §4.5.)*

This is a recommendation *against* the obvious move, and the reason should be
recorded so it is not re-litigated. The four buckets are defined by comparing an
opponent's shrunk rate to a split threshold. Once R2 makes the threshold
per-band, **the bucket is already band-aware**, because the same person compared
against the right threshold lands in the right box. Adding a band axis to the
grid instead would multiply four buckets into sixteen, and by
`OPPONENT_MODEL_DESIGN.md` §4.5 each bucket implies a
solver-produced counter-strategy — a cost the design document's §3.3 already
rules out at Pluribus scale.

Keep `STATION` / `ROCK` / `TAG` / `MANIAC` / `UNKNOWN` as the global vocabulary.
Move the seat-count knowledge into the thresholds and the baselines, where it is
cheap.

### R6 — The compute cap is already in §4.5 and E5; what is left is the `RESOURCES_SOLVERS.md` pointer. *(Extension, most of it already applied. §4.5 and Engine requirements.)*

**This item asked for a cap that the design document now states itself**, at the
revision this document is written against (`OPPONENT_MODEL_DESIGN.md` at
commit `5aa40b8`). Recorded here rather than dropped, because the reasoning is
what the remaining recommendation rests on. What §4.5 and E5 already carry:

- **The multiplier and the prohibition.** §4.5 requires a counter-strategy to be
  solved at the seat count it will be used at, forbids loading one solved for a
  different size, and states the multiplier in full: **four strategies (`S_BASE`
  plus three counters) × eight seat counts = 32 offline solver runs**.
- **The cap, as a pass/fail on E5.** E5 now asks the cost of one run *and* of 32
  against the operator's cap, recorded 2026-09-15 — **no multi-day computing, and
  a playable bot must be reachable in hours on one laptop** — and records that a
  "days" answer fails outright and an "hours" answer fails at 32.
- **Tier 1 made conditional on that answer.** §4.5 states that Tier 1 as
  specified is conditional on an engine whose single solve against fixed
  opponents finishes in **minutes**, and that a coding task finding otherwise
  must stop and report rather than start a solve that cannot finish.
- **The pending alternative that may remove the solve plan entirely.** §4.5
  records that `ENGINE_ALTERNATIVES.md` is under review and recommends computing
  decisions at play time instead of solving strategies offline at all; if that is
  accepted, the 32 runs do not happen and Tier 1's "select among precomputed
  strategies" structure is what changes, not the stats, shrinkage, buckets or
  flags.
- **The corrected fallback arithmetic.** §4.5 states that dropping one seat count
  from Tier 1 saves **3 runs, not 4** — the dropped seat count still needs its own
  `S_BASE` to play at all — leaving a floor of **8 runs**, one `S_BASE` per seat
  count; cutting a bucket saves 8 runs, one at every seat count.

**Two more of these have been overtaken since the pinned revision, and are named
here so the delta is not read as larger than it is.** `OPPONENT_MODEL_DESIGN.md`
has moved on from `5aa40b8` — it is at commit `5f7a1a8` as this is written — and
commit `72eff27` put into its §4.5 two things this document would otherwise be
recommending: **the operator's solve order** ("Solve 6-handed first; then 8- and
9-handed as one band; then every remaining seat count", §4.5 at :1287-1288 of
that revision), and **the rule that 8 and 9 still need separate solver runs**
even though the operator's priority ranks them together, because a 9-handed
solve faces eight opponents and an 8-handed table presents seven (§4.5 at
:1292-1300). The cross-references elsewhere in this document stay pinned to
`5aa40b8`, which is the revision they were checked against; these two are the
only places where the later revision has already taken the recommendation.

**The genuine delta, and all this item now recommends.** Two points:

- **Point §4.5 at `RESOURCES_SOLVERS.md` as well.** §4.5 names
  `ENGINE_ALTERNATIVES.md`, which is the play-time alternative; the survey of
  which *offline* solvers exist and what one run costs on one laptop is
  `RESOURCES_SOLVERS.md`, and that is the survey E5's pass/fail answer will come
  from if the offline plan survives. `RESOURCES_SOLVERS.md` is on trunk;
  `ENGINE_ALTERNATIVES.md` is still in progress. §4.5's budget should name both.
- **Banding is not the escape.** Solving one representative seat count per band,
  16 runs, contradicts §4.5's own prohibition and must not be adopted silently —
  and it does not rescue the budget anyway, because 16 multi-day runs breach the
  cap exactly as 32 do. The cap binds on the cost of *one* run first.

See [Q4](#4-questions-for-the-operator).

### R7 — Cross-tabulate V5's bluff-frequency report by seat count. *(Extension. §6.)*

**What exists today.** V5 runs two versions side by side and compares them for
exploitation, the arrangement usually written **A/B** — `S_BASE` against the
counter-strategy by hand parity, compared in **big blinds won per 100 hands**,
the standard way of stating a win rate, written `bb/100`. On top of that
comparison §6 gives it **one extra report**: *bluff frequency broken down by the
number of live opponents*. That index is field size `m`, which is the correct one
([§1.3](#13-table-size-versus-field-size-where-the-multiway-arithmetic-actually-attaches)).
The bb/100 comparison is not what this item touches; the extra report is.

**What to add, stated in full so a later task need not infer it.** Make that
report a two-way table rather than a single column. Both axes, explicitly:

| Axis | Values | Where it comes from |
| --- | --- | --- |
| Field size `m` | live opponents at the moment of the bluffing decision, `1 … n−1` | the report's existing index; unchanged |
| Seat count `n` | players dealt in at the start of the hand, `2 … 9`, **and** which strategy was loaded if it was solved for a different `n` | the `HandRecord`'s seat count, which [R1](#r1--define-the-seat-count-band-as-a-context-value-not-a-new-table-extension-42) makes an explicit field |

For each `(n, m)` cell with `m ≤ n − 1`, report **the bot's bluff frequency and
the count of bluffing opportunities behind it**, marking as "insufficient" rather
than as a rate any cell whose opportunity count is too low to read. Keep both
margins: the `m` margin summed over `n` **is** today's report, so nothing is
lost, and the `n` margin is the new one.

**Why both.** The single axis conflates two different findings: "the strategy
bluffs correctly less into larger fields", which is the check §2.4 wants and is a
property of `m`; and "the strategy solved for 9-max behaves differently
three-way than the one solved for 4-max does", which is a property of `n` and is
invisible until the cells are separated. Both are worth knowing, and only the
first is currently visible.

### R8 — Add the sizing stats to the stat table. *(Extension. §4.2 and §2.3 of the design document.)*

Two rows to add, with opportunity definitions in the document's required literal
form. The third sizing signal in
[§2.2](#22-sizing-as-a-signal-about-the-opponent) — sizing dispersion — is
computed from `bet_size_dist` and needs no row of its own.

| `stat_name` | Numerator increments when… | Denominator increments when… | Context key |
| --- | --- | --- | --- |
| `bet_size_dist` | opponent's bet or raise fell in this size bucket | opponent bet or raised on that street | `street` + `role` + `size_bucket` |
| `fold_to_bet` | opponent folded | opponent faced a bet on that street in that size bucket | `street` + `size_bucket` |

Size is measured as **bet divided by the pot before the bet**, never in big
blinds ([§2.2](#22-sizing-as-a-signal-about-the-opponent)). All-in is its own
bucket. `bet_size_dist` is a distribution over buckets, so its baseline is a **vector**
and its shrinkage uses DBBR Equation 1 in its original categorical form
([Ganzfried & Sandholm 2011](#s-ganzfried2011) §4.2) rather than the binomial
special case in §4.3 — the equation is unchanged, only `BASELINE` gains an index.
The `n` in that equation is the paper's public-history index and the `n` in
`confidence = n/(n+s)` is the opportunity count; neither is the seat count this
recommendation bands on
([§1.1](#11-three-different-quantities-get-called-table-size)).

Per-opponent `fold_to_bet` should use **two** buckets (split at 0.70 pot) and the
population baseline **four**, for the reason in
[§2.5](#25-what-sizing-buckets-cost). Add the fallback chain from that section to
§4.2's existing "fall back up the hierarchy" paragraph.

### R9 — Add two sizing exploit flags. *(Extension. §4.4.)*

| Flag | Condition | Confidence gate |
| --- | --- | --- |
| `OVERFOLDS_VS_LARGE` | shrunk `fold_to_bet[large]` exceeds `BASELINE[fold_to_bet[large], band]` by ≥ 0.15 | `confidence ≥ 0.6` |
| `OVERFOLDS_VS_SMALL` | shrunk `fold_to_bet[small]` exceeds `BASELINE[fold_to_bet[small], band]` by ≥ 0.15 | `confidence ≥ 0.6` |

Margins and gates copied from the existing flag table for consistency; like every
value there they are **unmeasured starting values**. Both flags carry the same
multiway gate as `OVERFOLDS_TO_CBET` in §4.6: the discount for field size belongs
to the engine, and no module outside it may multiply live opponents' fold rates
to decide whether to bet.

**Do not add a `SIZE_TELLS` flag yet.** The showdown-conditioned version is
slower than every Tier C stat
([§2.2](#22-sizing-as-a-signal-about-the-opponent)) and a flag gating on it would
fire on noise.

### R10 — Add three engine requirements. *(Extension. `OPPONENT_MODEL_DESIGN.md` Engine requirements.)*

| # | Requirement | Needed by |
| --- | --- | --- |
| E7 | Does the engine's action abstraction contain **more than one bet size** at a given decision, and how many? | The bot's own unpredictability ([§2.3](#23-sizing-as-a-signal-about-us), Failure 2) |
| E8 | Does the engine perform **action translation** for an opponent bet not in its abstraction, and is the mapping randomised? | Not being readable at a size threshold ([§2.3](#23-sizing-as-a-signal-about-us), Failure 3) |
| E9 | Can the engine be run at **every seat count from 2 to 9**, and does the abstraction change with seat count? | The whole 2-to-9 requirement; R6's solve budget |

**All three are asked of a candidate engine, not of the vendored one, whose
answers are already known and are all no.** `REFERENCE_NOTES.md` records them:
the raise amount is fixed by the rules, so E7's count is not "one size" but no
chosen size at all and E8 has nothing to translate between (:523-542); and the
20-card deck seats seven at most, so E9's answer is "2 to 7, not 8 or 9"
(:499-503). Asking them of that engine is therefore closed, and
[§1.0](#10-the-engine-this-project-has-today-already-answers-two-of-these-questions-and-answers-them-no)
sets out what that does and does not change. These three rows are selection
criteria to put to OpenSpiel `universal_poker`, the engine road the operator's
recorded decision names. That is the engine the reconciliation of the four
survey documents — `ENGINE_ALTERNATIVES.md`, `RESOURCES_BOTS.md`,
`RESOURCES_SOLVERS.md` and `RESOURCES_EXPLOITATION.md` — is made against.

E7 and E9 are answerable without writing any code and should be answered before
the Tier 1 solve budget in R6 is committed to. **Each of the three carries its own
"and if the answer is no, then what", because that is the point at which somebody
will otherwise reach for a patch outside the engine.** Each is written for a
candidate engine that has bet sizes to speak of; the bullets below do not
describe a repair to the vendored engine.

- **If E7's answer is "one size": report it and stop**, exactly as §4.5 instructs
  for E2 — not a size randomiser outside the engine, which would be AI-written
  code deciding a poker action.
- **If E8's answer is "no translation" or "a deterministic one": the same shape
  of response, and for the same reason.** Deciding which abstraction size an
  off-abstraction bet *counts as* is reading a poker action, so a translation
  layer written here would be AI-written code making a poker judgment, and
  `CLAUDE.md`'s forefront rule forbids it in the same breath as it forbids the
  randomiser above. The rule's own instruction is what applies: **adapt the
  engine instead.** In order — (1) prefer an engine that already translates
  randomly, which is a point for E9's survey and for `ENGINE_ALTERNATIVES.md` to
  weigh; (2) failing that, implement the pseudo-harmonic mapping
  ([Ganzfried & Sandholm 2013](#s-ganzfried2013), **formula not verified — confirm
  against the primary text first**) *inside the chosen engine's own translation
  code*, as a change to that engine's source covered by its tests, never as a
  wrapper in the integration layer that rewrites the opponent's bet before the
  engine sees it; (3) if neither is possible, **report that and stop**, as for
  E7. **Remedy (2) is not available on the vendored engine and is not proposing
  it**: that engine has no bet sizes and therefore no translation code to put
  the mapping inside of (`REFERENCE_NOTES.md`:523-542). It is a repair to a
  candidate engine that translates badly, not to one that has nothing to
  translate.
- **If E9's answer is "not at every seat count": report it and stop** for the seat
  counts it cannot reach, and fall back to `S_BASE` there, which §4.5 already
  makes the default for anything uncertain. Do not simulate a missing seat count
  by loading a strategy solved for another one; §4.5 forbids exactly that. **For
  the vendored engine this is already the answer, and the seat counts it cannot
  reach are 8 and 9** (`REFERENCE_NOTES.md`:499-503), which is why the operator's
  second priority waits on the engine choice rather than on this design.

### R11 — Write the sampling rule into the design as a rule, not an assumption. *(Correction. §4.1 and §4.5.)*

E1 asks whether the engine's action distribution can be queried. Add the
consequence explicitly, because it is the failure that will otherwise arrive as
a plausible-looking one-liner in the integration layer: **the action path must
sample from the engine's distribution and must never take its most likely
action.** An argmax in the action path is a defect, and R12 is the test that
catches it.

### R12 — Add V6: the bot's own sizing distribution. *(Extension. §6.)*

**V6 — Self-sizing check.** Over logged hands of the bot's own play, report the
bot's realised bet-size distribution per (street, role, size bucket), and its
bluff share per size bucket. Two red flags, both cheap and both offline:

- **A point mass.** If the bot's sizing in a spot is effectively one value, either
  the abstraction has one size (E7) or the action path is taking an argmax (R11).
  Either is a defect with a reproducing test, per the global evidence rules.
- **Bluff share detached from size.** Compare the realised bluff share per bucket
  against the `s/(1+2s)` column of
  `OPPONENT_MODEL_DESIGN.md` Table A. A large gap is a
  red flag against that strategy — a reason to re-examine the archetypes or
  solver settings, **never a licence to correct bluff frequency in code outside
  the engine.** This is the same standing V5 has.

### R13 — Make the deviation cap a function of seat count. *(Extension. §5.2.)*

§5.2's deviation cap is a single global `Pmax`-equivalent. Make it a small table
indexed by band, tightest at `HU` and loosest at `FULL`. The reasoning is in
[§1.7](#17-heads-up-is-a-different-game-and-it-inverts-the-designs-founding-argument):
the equilibrium guarantee that makes deviation costly exists only at two players,
which is the one place the design document's own founding argument does not
reach, and it is the setting Libratus's no-exploitation position was formed in
([Brown 2020](#s-brown2020), §6.4). The values are **unmeasured** and belong in
config.

### R14 — Record the seat-count mixture V4 measured. *(Extension. §6.)*

V4 checks `VPIP_SPLIT` and `AFQ_SPLIT` against the literature thresholds on
logged hands. Those thresholds are attributed by Teofilo and Reis to **Billings'
thesis and Sklansky**, as `OPPONENT_MODEL_DESIGN.md` §2.2 and its Sources record,
and they descend from a corpus this project has never
seen — neither work was retrieved by either survey, so **the seat counts behind
the thresholds are unknown**, and that corpus is *not* the tournament corpus
`OPPONENT_MODEL_DESIGN.md` §2.1 describes, which is Teofilo and Reis's own and
supplies the 4.52% ratio instead
([§1.5](#15-the-published-thresholds-are-themselves-table-size-mixtures)).
Because one side of the comparison has an unknown seat-count mixture, the other
side must have a recorded one: V4 must report the seat-count mixture of the
population **it** measured alongside the disagreement rate. Without it, a gap
between the bot's population and the threshold cannot be told apart from a
difference in the two mixtures, and the disagreement cannot be interpreted at
all. V4 remains
superseded once the per-band population medians replace both splits, as §4.4
already specifies.

---

## 4. Questions for the operator

Recommendation first, as the global rules require. **These are numbered Q4 and
Q5 because `OPPONENT_MODEL_DESIGN.md` §7 already holds Q1, Q2 and Q3; they are
additions to that list, not replacements for it, and keep these numbers when the
two lists are merged.**

**Q4 — How many seat counts should the Tier 1 solve cover, and with which
solver?**
`OPPONENT_MODEL_DESIGN.md` §4.5 forbids loading a counter-strategy solved for a
different seat count, and states the resulting budget: 32 solver runs, four
strategies × eight seat counts. Engine requirement E5 asks what one run costs and
is still unanswered. **The operator's compute cap, recorded 2026-09-15, is what
decides this question: no multi-day computing, and a playable bot must be
reachable in hours on one laptop.** Thirty-two runs are inside that cap only if
one run takes minutes on one laptop, so the question is not only "how many seat
counts" but "with which solver, if any".

**The 32 assumes eight reachable seat counts, and the engine in the repository
reaches seven.** Its 20-card deck seats seven at most, so the seat counts it can
play are 2 through 7, which is **six** of the eight — a budget of **24 runs, not
32** — and the operator's own second priority, 8- and 9-handed play, cannot be
solved or played there at all
(`REFERENCE_NOTES.md`:499-503,
[§1.0](#10-the-engine-this-project-has-today-already-answers-two-of-these-questions-and-answers-them-no)).
The 32 stated here is the budget for an engine that reaches the whole required
range, which is one of the things the engine choice has to buy.

**This question may not need answering at all.** §4.5 marks its own solve plan as
conditional: `ENGINE_ALTERNATIVES.md` is under review and recommends computing
decisions at play time rather than solving strategies offline, and if that
recommendation is accepted there are no precomputed per-seat-count strategies to
budget for and this question lapses. It is asked here because the decision is
pending, not because the offline plan is settled.

*Recommendation:* treat the 32-run budget as **a requirement the engine choice
has to meet, not a plan to execute with the vendored `poker_ai`** (R6). Answer E5
against the cap — minutes per run on one laptop, pass or fail — using the two
surveys, `ENGINE_ALTERNATIVES.md` for the play-time alternative, in progress,
and `RESOURCES_SOLVERS.md` for the offline solvers, on trunk. If something
passes, solve in the order the operator's own table-size priority sets, recorded
2026-09-15: **mostly 6-handed play, then 8 and 9 which the operator treats as the
same thing** — so `n = 6` first, then `n = 8` and `n = 9` together, then the rest
of the 2-to-9 range, which stays a firm requirement rather than becoming
optional. **That order is no longer a recommendation this document is making:
`OPPONENT_MODEL_DESIGN.md` §4.5 states it itself at commit `72eff27`, later than
the `5aa40b8` this document is pinned to, and adds that "treated the same" ranks
8 and 9 in priority without merging their solver runs**
([R6](#r6--the-compute-cap-is-already-in-45-and-e5-what-is-left-is-the-resources_solversmd-pointer-extension-most-of-it-already-applied-45-and-engine-requirements)).
It is repeated here because it is what the answer to this question would be
executed against, not because it is still open. (Solve order, not the stat bands
of
[R1](#r1--define-the-seat-count-band-as-a-context-value-not-a-new-table-extension-42);
the two answer different questions.) Have the bot decline to load a
counter-strategy at an unsolved seat count, falling back to `S_BASE`, which §4.5 already makes the default for
anything uncertain; that keeps the prohibition intact and makes the cost
incremental rather than up-front. If nothing passes, Tier 1 as specified is not
reachable on this hardware, and the honest responses are §4.5's own — narrow the
seat counts Tier 1 covers, at **3 runs saved per seat count dropped and a floor of
8**, or cut buckets at 8 runs each — never a multi-day solve, and never a
strategy loaded at a table size it was not solved for.

*Alternative:* solve one representative seat count per band and accept a known
mismatch. That would require §4.5's prohibition to be relaxed deliberately and in
writing, and it still breaches the cap if a single run takes days.

**Urgency: not blocking for Tier 0** — the whole measurement layer, and
everything in R1 through R4 and R8, needs no solver at all. **Blocking for
Tier 1**, which should not be commissioned before the cap question has an answer,
since the answer may change which engine the project is built on.

**Q5 — Does "2 to 9 players" change the project's stated goal?**
`OPPONENT_MODEL_DESIGN.md` §1 has already been brought to the new requirement: it
now states the goal as beating the humans at the table "at **every table size
from 2 to 9 players**", and notes that two players is the one size where the
equilibrium guarantee exists. `CLAUDE.md` in this repository has not: it still
states the goal as beating humans "at a table of 3 or more". **The two disagree
because `CLAUDE.md` is stale, not because it is right:** its "3 or more" was
written before the operator stated the firm 2-to-9 requirement, and that
requirement governs. `CLAUDE.md` is to be brought to 2 to 9, and a queued task
does exactly that. The design document's
case against pursuing game-theory-optimal play still rests on the multiplayer
result in [Brown 2020](#s-brown2020) §6.6, which is explicitly about tables of
three or more and does not reach two-handed play, where the opposite conclusion
holds
([§1.7](#17-heads-up-is-a-different-game-and-it-inverts-the-designs-founding-argument)).
*Recommendation:* bring `CLAUDE.md`'s scope wording up to 2 to 9, rather than
narrowing the design document back to three or more, and keep the substance —
support two-handed play as a deliberately conservative mode, tight deviation cap
(R13), blueprint-first — rather than rewriting the project's premise around it.
**This document does not edit `CLAUDE.md`**; the change is the operator's and the
stoker's, and is already queued. **Urgency: low, but settle it before Tier 1
solves are commissioned**, because it decides how `n = 2` is treated in the solve
budget in Q4.

---

## Sources

Two categories, kept separate on purpose.

**Retrieved and read 2026-09-15**, by the survey behind `OPPONENT_MODEL_DESIGN.md`;
this document relies on them only for claims that document already establishes.

<a id="s-brown2020"></a>**[Brown 2020]** Noam Brown, *Equilibrium Finding for
Large Adversarial Imperfect-Information Games*, PhD thesis, Carnegie Mellon
University, CMU-CS-20-132.
`http://reports-archive.adm.cs.cmu.edu/anon/2020/CMU-CS-20-132.pdf`
Used here for two claims, and only two, both of which
`OPPONENT_MODEL_DESIGN.md` quotes from the retrieved text: the
multiplayer/two-player boundary in the equilibrium argument (§6.6), and
Libratus's position on exploitation (§6.4). **Anything this document says about
Pluribus's *bet sizing* is not among them** — see
[Pluribus's bet-size abstraction](#s-pluribus-sizing) in the memory-cited list
below.

<a id="s-ganzfried2011"></a>**[Ganzfried & Sandholm 2011]** Sam Ganzfried and
Tuomas Sandholm, "Game Theory-Based Opponent Modeling in Large
Imperfect-Information Games", *AAMAS 2011*.
`https://www.cs.cmu.edu/~sandholm/opponentModeling.aamas11.pdf`
Used here for: Equation 1 in §4.2, whose original form is a Dirichlet posterior
over a categorical action set — which is why the size-bucket distribution in R8
needs no new mechanism.

<a id="s-johanson2009"></a>**[Johanson & Bowling 2009]** Michael Johanson and
Michael Bowling, "Data Biased Robust Counter Strategies", *AISTATS 2009*.
`https://poker.cs.ualberta.ca/publications/AISTATS09.pdf`
Used here for: `Pmax` as an explicit exploitation-versus-exploitability tradeoff,
which R13 turns into a per-band table.

<a id="s-teofilo2011"></a>**[Teofilo & Reis 2011]** Luís Filipe Teófilo and Luís
Paulo Reis, "Identifying Player's Strategies in No Limit Texas Hold'em Poker
through the Analysis of Individual Moves", *EPIA 2011*.
`https://arxiv.org/pdf/1301.5943`
Used here for: the 4.52% showdown ratio, which comes from **their own** corpus of
real-money **tournament** logs (§5, Table 1), as already established in
`OPPONENT_MODEL_DESIGN.md` §2.1 and its source note.
**That corpus is not the source of the 72% / AF > 1 thresholds**, which Teofilo
and Reis report from Billings; the two are separate and
[§1.5](#15-the-published-thresholds-are-themselves-table-size-mixtures) turns on
keeping them apart.

---

**Cited from memory and NOT retrieved during this survey.** No web retrieval was
available to this task. Each of the following is a work — or, in one case, a
claim about a published system — that this survey is confident exists, but no
page, section, or wording was verified, and **a later task must
confirm any of them before an implementation depends on it.** Nothing in
[§3](#3-recommended-reconciliation-with-opponent_model_designmd) depends on one
of these alone — each recommendation is also supported by derived arithmetic or
by a retrieved source.

<a id="s-billings2006"></a>**[Billings 2006]** Darse Billings, *Algorithms and
Assessment in Computer Poker*, PhD thesis, University of Alberta. The origin of
the 72% / AF > 1 thresholds in their numeric form, alongside
[Sklansky](#s-sklansky) for the taxonomy they express. **Cited at third hand** — via
[Teofilo & Reis 2011](#s-teofilo2011), who cite it; the thesis itself was
retrieved by neither survey. **Consequently this document knows nothing about the
corpus those thresholds were fitted on, including the seat counts it contained**,
and [§1.5](#15-the-published-thresholds-are-themselves-table-size-mixtures) rests
on that unknown rather than on any property of Teofilo and Reis's tournament
corpus.

<a id="s-sklansky"></a>**[Sklansky]** David Sklansky, *The Theory of Poker*. The
other work [Teofilo & Reis 2011](#s-teofilo2011) §3 attributes the tight/loose,
passive/aggressive thresholds to, as `OPPONENT_MODEL_DESIGN.md`'s Sources also
record. **Cited at third hand** by the same route as
[Billings 2006](#s-billings2006), and retrieved by neither survey.

<a id="s-pluribus-sizing"></a>**[Pluribus's bet-size abstraction]** The claim that
Pluribus used a small discrete set of bet sizes while beating elite professionals
at six-player no-limit. Presumably in [Brown 2020](#s-brown2020) §6.6 or the
underlying *Science* paper, but **no page was read for it by this task and
`OPPONENT_MODEL_DESIGN.md` does not state it**, so it is recorded here rather
than beside the retrieved uses of that thesis. No count of sizes is asserted, and
nothing in [§3](#3-recommended-reconciliation-with-opponent_model_designmd)
depends on the claim at all — see
[§2.4](#24-what-the-strategy-literature-says-about-choosing-sizes).

<a id="s-ganzfried2013"></a>**[Ganzfried & Sandholm 2013]** Sam Ganzfried and
Tuomas Sandholm, "Action Translation in Extensive-Form Games with Large Action
Spaces: Axioms, Paradoxes, and the Pseudo-Harmonic Mapping", *IJCAI 2013*.
The standard treatment of mapping an off-abstraction bet size onto an
abstraction, and the source of the pseudo-harmonic mapping quoted in
[§2.3](#23-sizing-as-a-signal-about-us). **The formula is quoted from memory.**

<a id="s-waugh2009"></a>**[Waugh et al. 2009]** Kevin Waugh, Dave Schnizlein,
Michael Bowling and Duane Szafron, "Abstraction Pathologies in Extensive Games",
*AAMAS 2009*. The result that refining an abstraction can make the resulting
strategy worse — the caution against simply adding bet sizes in
[§2.4](#24-what-the-strategy-literature-says-about-choosing-sizes).

<a id="s-bowling2015"></a>**[Bowling et al. 2015]** Michael Bowling, Neil Burch,
Michael Johanson and Oskari Tammelin, "Heads-up limit hold'em poker is solved",
*Science* 347(6218). Context only, for
[§1.7](#17-heads-up-is-a-different-game-and-it-inverts-the-designs-founding-argument);
no claim here depends on it.

<a id="s-chenankenman"></a>**[Chen & Ankenman]** Bill Chen and Jerrod Ankenman,
*The Mathematics of Poker*. The analytic treatment of optimal bet sizing in
simplified poker games. Used only for the descriptive
polarised-versus-merged account in
[§2.4](#24-what-the-strategy-literature-says-about-choosing-sizes), which is
explicitly marked as a reviewer's sanity check rather than a specification.

<a id="s-janda"></a>**[Janda]** Matthew Janda, *Applications of No-Limit
Hold'em*. Bet-sizing balance and minimum defence frequency in modern no-limit
strategy. Same use and same caveat as above.

<a id="s-sklanskymalmuth"></a>**[Sklansky & Malmuth]** David Sklansky and Mason
Malmuth, *Hold'em Poker for Advanced Players*. Full-ring starting requirements
presented as a table indexed by position — the strategy-literature grounding for
the position argument in
[§1.2](#12-why-the-voluntarily-put-money-in-pot-rate-vpip-is-not-comparable-across-seat-counts).
The *arithmetic* of [Tables 1–3](#table-1-what-seat-count-mechanically-fixes)
is derived here and does not rest on this citation.

---

**Deliberately not cited.** `OPPONENT_MODEL_DESIGN.md` excludes poker
tracking-software population averages on the grounds that no verifiable source
for them was found, and derives `BASELINE` from the bot's own data instead. **This
document keeps that exclusion and extends it**: the widely-circulated
table-size-specific norms — "full ring VPIP is such-and-such, 6-max is
such-and-such, heads-up is such-and-such" — are exactly the same kind of
unverifiable folklore and **no such figure appears anywhere above**. That is why
[§1.2](#12-why-the-voluntarily-put-money-in-pot-rate-vpip-is-not-comparable-across-seat-counts)
argues from positional weights, which are derivable, rather than from norms,
which are not, and why R2 bands the bot's own measured baseline instead of
hardcoding one per band.

---

## Provenance of every number in this document

**A program checks this table, so it cannot quietly go stale.**
`tools/check_table_size_numbers.py` holds one copy of every constant this
document declares — the seat counts, the illustrative spread column, the
illustrative Table C hand counts, the band and bucket counts, the bet sizes, the
stack-to-pot ratios and the strategy count — and recomputes from them **every
figure in Tables 1 to 6, the `4.5×` and `2.25×` multipliers, and the solver-run
counts**, comparing each against what the prose prints, in *every* place the
prose prints it. It needs nothing but Python itself: no engine, no network, no
installed libraries. `tests/test_table_size_numbers.py` runs it as part of the
test suite, and also mutates one figure at a time in a scratch copy to prove the
check still catches drift. The rule that follows, and it is the same rule
`OPPONENT_MODEL_DESIGN.md` §4.7 states for its own checker,
`tools/check_design_numbers.py`: **a constant is changed in the script and in
the prose together, in one edit, and the script is what says the prose is still
right.**

Two things it deliberately does not check, so the boundary is not guessed at:
figures quoted from `OPPONENT_MODEL_DESIGN.md` or from the
[Sources](#sources) — those are checked against their source by citation, not by
arithmetic — and section numbers, dates and anchors. Every row below that names
the script is checked by it; every row that does not, is not.

**The two checkers should become one.** `OPPONENT_MODEL_DESIGN.md` and its
script are on trunk; this document and its own script are still on a branch, and
only this document's landing is outstanding. What is duplicated between them is
the half-up rounding helpers, the markdown table reader, the `Checker` surface
and the exit-code contract. Merge the two into one script once this document
lands, rather than attempting it from one branch against the other;
`tools/check_table_size_numbers.py` says the same in its own docstring.

| Number | Where it comes from |
| --- | --- |
| [Table 1](#table-1-what-seat-count-mechanically-fixes) — `2/n`, `1/n`, `(n−3)/n`, `(n−1)/2` | Derived; computed and checked by `tools/check_table_size_numbers.py` 2026-09-15. Follows from preflop action order giving each "players behind" value `0…n−1` exactly once per orbit |
| [Table 2](#table-2-how-far-apart-two-seat-counts-are-as-positional-mixtures) — total variation distances | Computed and checked by `tools/check_table_size_numbers.py` 2026-09-15, as `½·Σ|p−q|` over the uniform positional-weight vectors of Table 1. Elementary arithmetic |
| [Table 3](#table-3-the-swing-that-costs-nothing-but-a-change-of-seat-count) — the shift bounds | Computed and checked by `tools/check_table_size_numbers.py` 2026-09-15 as `TV × spread`, the standard total-variation bound. **The spread column (0.30 / 0.50 / 0.70) is illustrative, not measured or cited**, on the same footing as the `p̂` anchors in `OPPONENT_MODEL_DESIGN.md` Table C |
| The `4.5×` blind-frequency ratio between heads-up and 9-max | Derived; `(2/2)/(2/9) = 4.5`, the `2/n` column of Table 1; computed and checked by `tools/check_table_size_numbers.py` 2026-09-15, in the provenance row and at both places in the prose that state it. It is the ratio of blind frequencies, **not** the hands multiplier for any particular stat |
| The `2.25×` hands multiplier for `fold_to_steal`, 9-max versus heads-up ([§1.6](#16-what-banding-costs), [R4](#r4--redefine-fold_to_steals-opportunity-or-split-it-correction-42)) | Derived from §1.4's reasoning: at `n = 2` only the big blind can defend, so half the blind hands are opportunities, `(1/(2/9))/(1/(1/2)) = 2.25`; computed and checked by `tools/check_table_size_numbers.py` 2026-09-15, in the provenance row and at every place in the prose that states it. The 9-max conditional rate is not 1 either, so this is a reasoned figure to be replaced by `denominator / hands_dealt` from logged hands |
| [Table 4](#table-4-the-fragmentation-multiplier) — the `k×` multiplier | Derived: the opportunity count for a fixed interval half-width does not depend on stratification, so `k` strata need `k` times the hands. Computed and checked by `tools/check_table_size_numbers.py` 2026-09-15, in the table and in §2.5's restatement of it. **The 323 and 640 base values are inherited from `OPPONENT_MODEL_DESIGN.md` Table C and are illustrative there; the products inherit that status** |
| 32 solver runs (R6) and 16 under banding | Derived; 8 seat counts × 4 strategies, and 4 bands × 4 strategies. Computed and checked by `tools/check_table_size_numbers.py`, 2026-09-15. `OPPONENT_MODEL_DESIGN.md` §4.5 and E5 now state the same 32 independently |
| 24 runs, the budget the vendored engine could pay for ([Q4](#4-questions-for-the-operator)) | Derived; 6 reachable seat counts × 4 strategies, computed and checked by `tools/check_table_size_numbers.py` 2026-09-15. The 6 is **not derived here**: the vendored engine's 20-card deck seats seven at most, so its seat counts are 2 through 7, taken from `REFERENCE_NOTES.md`:485-497 |
| The vendored engine's seven-seat ceiling, its fixed-limit betting, and the 18.4 days and 146.5 GiB of the 52-card conversion ([§1.0](#10-the-engine-this-project-has-today-already-answers-two-of-these-questions-and-answers-them-no)) | **Not derived here.** Read from `REFERENCE_NOTES.md` on the trunk branch, which measured them: the deck arithmetic at :485-497 and its 8/9 consequence at :499-503, the fixed raise amount and three-raise cap at :523-542, and the conversion cost at :8-11 |
| 3 runs saved per seat count dropped, an 8-run floor, and 8 runs saved per bucket cut (R6, [Q4](#4-questions-for-the-operator)) | **Not derived here.** Taken from `OPPONENT_MODEL_DESIGN.md` §4.5 at commit `5aa40b8`, which states them: a dropped seat count still needs its own `S_BASE`, so only its three counter-strategies are saved, leaving one `S_BASE` per seat count as the floor |
| The compute cap R6 and [Q4](#4-questions-for-the-operator) hold the solve budget to — hours on one laptop, no multi-day computing | **The operator's own requirement, recorded 2026-09-15.** Not derived and not a measurement: it is a constraint stated by the operator, and it is repeated here verbatim in substance rather than paraphrased into a number of hours |
| [Table 5](#table-5-what-mis-reading-a-bet-size-costs-exactly) — required pot equity `B/(P+2B)` and the error columns | Computed and checked by `tools/check_table_size_numbers.py` 2026-09-15. Elementary pot-odds arithmetic, `P = 1` |
| [Table 6](#table-6-pot-fraction-needed-to-reach-all-in-in-k-equal-bets) — `f` from `(1+2f)^k = 1+2·SPR` | Derived; computed and checked by `tools/check_table_size_numbers.py` 2026-09-15. Each bet-and-call multiplies the pot by `(1+2f)`; elementary |
| The 19.9% / 25.0% / 30.0% / 33.3% bluff shares, and the **25.2pp** break-even-fold spread cited in [§2.5](#25-what-sizing-buckets-cost) | Read from `OPPONENT_MODEL_DESIGN.md` Table A, which computes them as `s/(1+2s)` and `s/(1+s)`. Re-derived here and matched. The spread is that table's `1.00` row (50.0%) minus its `0.33` row (24.8%) |
| The pseudo-harmonic formula `((B−x)(1+A))/((B−A)(1+x))` | [Ganzfried & Sandholm 2013](#s-ganzfried2013). **Quoted from memory; NOT retrieved or verified. Confirm against the primary text before implementing** |
| 4.52% showdown ratio | [Teofilo & Reis 2011](#s-teofilo2011), Table 1, as read and reported by `OPPONENT_MODEL_DESIGN.md` |
| Band boundaries `HU`=2, `SHORT`=3–4, `MID`=5–6, `FULL`=7–9 (R1) | **Two constraints and one unmeasured bookkeeping choice.** `n=2` stands alone because [§1.7](#17-heads-up-is-a-different-game-and-it-inverts-the-designs-founding-argument) requires it; `n=8` and `n=9` share a band because the operator's table-size priority, recorded 2026-09-15, treats them as the same. The `4\|5` and `6\|7` cuts are **not** derived from Table 2 and cannot be: adjacent-seat-count distance is `1/(n+1)`, strictly decreasing, so no interior boundary is a local maximum. Belongs in config |
| Size-bucket boundaries 0.40 / 0.70 / 1.10 of pot, and the two-bucket split at 0.70 (R8) | **Unmeasured design choices**, placed to straddle the rows of `OPPONENT_MODEL_DESIGN.md` Table A. Belong in config |
| Flag margins `0.15` and confidence gates `0.6` in R9 | **Unmeasured starting values**, copied from the existing flag table in `OPPONENT_MODEL_DESIGN.md` §4.4 for consistency, and carrying the same status there and here |
| Pluribus's use of a small discrete bet-size abstraction, and the number of sizes in it | **Cited from memory and NOT retrieved; the count is not asserted at all.** `OPPONENT_MODEL_DESIGN.md` does not state the claim and this task had no web access, so it is listed under [Pluribus's bet-size abstraction](#s-pluribus-sizing) in the memory-cited sources. No recommendation here depends on it |
| Any table-size-specific VPIP, PFR or aggression norm | **Not asserted anywhere in this document.** See [Sources](#sources), "Deliberately not cited" |
