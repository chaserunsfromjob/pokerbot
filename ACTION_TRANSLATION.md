# Action translation: a small bet-size menu in a game where any size is legal

No-limit hold'em allows any whole bet up to a player's stack. A bot reasoning
over a short list of sizes has two problems: **which sizes it offers**, and
**what it does when an opponent bets something not on the list**. The second has
a published name, *action translation*, and a settled answer. Both, at 2–9 players.

`TABLE_SIZE_AND_SIZING_NOTES.md` covers, and this note does not repeat: pot
fractions as the unit (§2.2), the equity cost of mis-reading a size (Table 5),
why the menu needs more than one size (§2.3 Failure 2), how wide a sound range
is (Table 6). It flagged the pseudo-harmonic formula, [GS13] and Pluribus's
abstraction as quoted from memory; all three were retrieved here, and **its
formula is correct as quoted.**

## 1. The published methods

The menu holds a size `A` just below the observed bet `x` and a size `B` just
above; the mapping gives the probability `f(x)` of treating the bet as `A`, else
as `B`. Sizes are pot fractions, pot taken as 1 — [GS13] §5's own convention.

| Mapping | `f(x)` or threshold | Used by |
| --- | --- | --- |
| Deterministic arithmetic | threshold `(A+B)/2` | Tartanian1, 2007 |
| Randomized arithmetic | `(B−x)/(B−A)` | AggroBot |
| Deterministic geometric | threshold `√(AB)` | Tartanian2, 2008 |
| Randomized geometric 1 | `A(B−x) / (A(B−x) + x(x−A))` | Sartre, Hyperborean |
| Randomized geometric 2 | `A(B+x)(B−x) / ((B−A)(x²+AB))` | Tartanian4, 2010 |
| **Randomized pseudo-harmonic** | `(B−x)(1+A) / ((B−A)(1+x))` | Tartanian5; Pluribus preflop |

[GS13] §6 derives the last from the clairvoyance game, where the optimal call
frequency against a bet `x` is `1/(1+x)`; it is the only mapping consistent with
that across `[A,B]`. Its median is `x* = (A+B+2AB)/(A+B+2)`.

**What a deterministic threshold costs, in the paper's numbers.** With `A=1`
(pot) and `B=100` (all-in), an honest pot bet with the winning hand pays 1.5;
betting 50, just under the arithmetic threshold and so read as a pot bet, pays
**26**, and against randomized arithmetic betting 50.5 still pays **13.875**
([GS13] §§5.1–5.2) — `TABLE_SIZE_AND_SIZING_NOTES.md` §2.3 Failure 3, priced.
The predecessor mappings are described here **as [GS13] §5 describes them**;
those papers were not retrieved.

## 2. What a coarse menu costs, where measured

- **The mapping itself, on the `fcpa` menu {fold, check, pot, all-in}.** No-limit
  Leduc hold'em, both seats averaged: deterministic arithmetic 0.666, randomized
  geometric 1 0.574, randomized pseudo-harmonic **0.463** ([GS13] Table 6).
  Clairvoyance game at stack 100: 12.37, 1.01, **0.00** (Table 2).
- **One missing rung.** [BS17] built no-limit flop hold'em with {0.5, 0.75, 1.0}
  ×pot and removed the 0.75 rung from one player's menu. Answering that bet by
  pseudo-harmonic translation left them exploitable for **1,465 mbb/hand**;
  solving a fresh subgame containing the actual bet left **119.1**, ~12× lower
  ([BS17] Table 4). One missing size, best published mapping, still an order of
  magnitude worse than not needing the mapping.
- **Finer is not always better.** Kuhn poker's unique equilibrium bet is 0.4 pot,
  yet at stacks of 20 pots and up every mapping was *more* exploitable with
  {fold, check, 0.4 pot, all-in} than with {fold, check, pot, all-in} —
  deterministic arithmetic 0.301 → 3.714 at stack 100 ([GS13] Tables 3–4; at
  stacks of 1 and 3 every mapping improved). Copying human sizes is not a safe
  method.
- **Against real opponents the order changed.** [GS13] §10, Table 7: Tartanian5
  with only the mapping varied, against every other 2012 ACPC no-limit entry:
  "Det-Arith performed best using the metric of average overall performance,
  despite the fact that it was by far the most exploitable in simplified games.
  Det-psHar, Rand-Arith, and Rand-psHar followed closely behind. The three
  geometric mappings performed significantly worse." The paper's reason: no
  opponent was trying to exploit bet sizing. Rand-psHar stays in the leading
  group and the geometric mappings stay out, so the recommendation holds.

## 3. What the strong bots did

- **Libratus** (heads-up) avoided translation where it could afford to: from the
  third betting round on, and after every later opponent bet, it solved a new
  subgame containing the actual bet rather than mapping it ([BS17] §7, p. 11).
- **Pluribus** (six-player) "only considers a few different bet sizes at any
  given decision point. The exact number of bets it considers varies between one
  and 14 depending on the situation." Off-tree bets get real-time search; only
  preflop bets slightly off the tree are rounded "to a nearby on-tree size (using
  the pseudoharmonic mapping)" ([Pluribus] pp. 2–4). Blueprint: 12,400 CPU
  core-hours, 8 days, 64 cores. It "plays a fixed strategy that does not adapt to
  the observed tendencies of the opponents" (p. 2).
- **OpenSpiel `universal_poker`** exposes `kFC` (fold/call), `kFCPA` (fold, call,
  pot bet, all-in — 4 actions), `kFCHPA` (adds half-pot — 5 actions, and
  `DoApplyAction` also accepts an arbitrary integer bet size), and `kFULLGAME`,
  whose `NumDistinctActions()` is `max_stack_size + 1`: 0 folds, 1 checks or
  calls, every other integer is a raise-to amount. True no-limit is expressible;
  what is unaffordable is *solving* it. `kMaxUniversalPokerPlayers = 10`.

## 4. What changes multiway

1. **Pot share.** `PotSize(multiple)` returns `maxSpent + multiple × (pot +
   amount_to_call)` with `pot` accumulated over *every* player's `spent`, so a
   rung named "pot" is a different chip amount at each seat count and after each
   extra caller. Hence pot fractions, always: `research/action_translation.py`
   pins the trap — pseudo-harmonic on raw chips at ten times scale returns 0.44
   where the pot-fraction answer for the same spot is 0.578947. [GS13] §8 says
   all mappings satisfy scale invariance; that holds only under its §5
   convention that the pot is 1, which is why our code takes pot fractions.
2. **Price against strength.** Calling `s` pot in an `n`-way pot where the other
   `n−1` call needs pot share `s/(1+ns)`: at `s = 0.37`, 21.26% with one caller,
   17.54% with two. The price improves as the pot crowds while the hand needed
   to win it gets stronger, so a translated action is worth less multiway.
3. **Effective stacks.** All-in is not one action multiway: with stacks
   100/60/25 the upper endpoint `B` is 25 against the short stack and 60 against
   the middle, and anything above 25 is partly uncontested. Build the menu per
   *effective* stack, the smallest still contesting, not per hero stack.

**Every exploitability figure in §2 is two-player**, where exploitability means
something; at 3+ players it does not, and [Pluribus] is empirical, not a bound.

## 5. Worked example: 37% pot into a three-way pot, menu {half-pot, pot}

The opponent bets 0.37 pot. The smallest *bet* on the menu is 0.5 pot, so the
neighbours are `A = 0` (check) and `B = 0.5`. From
`python3 research/action_translation.py`:

| Method | Result |
| --- | --- |
| Deterministic arithmetic | threshold 0.25 → **half-pot**, always |
| Randomized arithmetic | check p = 0.2600, half-pot p = 0.7400 |
| Deterministic geometric | threshold `√0` = 0 → **half-pot**, always |
| Randomized geometric 1 and 2 | check p = 0, half-pot p = 1 |
| Deterministic pseudo-harmonic | threshold 0.20 → **half-pot**, always |
| **Randomized pseudo-harmonic** | check p = 0.1898, half-pot p = 0.8102 |

The geometric mappings are degenerate at `A = 0` ([GS13] §8) — and `A = 0` is
the commonest case in poker, since the gap between a check and the smallest menu
bet is where most small bets land. The shortcut of clamping every sub-menu bet
to half-pot is the deterministic answer, which [GS13] footnote 4 names: it
"could be significantly exploited by an opponent who makes extremely small bets
as bluffs". A 0.05-pot stab and a 0.45-pot bet would be answered identically.
`research/action_translation.py --check` reproduces [GS13] Table 1, the Figure 1
medians (0.1, 0.505, 0.3422), the footnote-3 median 1/3 for `A=0, B=1`, and the
1.5 / 26 / 13.875 clairvoyance payoffs; exit 0, or 1 on drift.

## 6. Rating

| Test | Rating |
| --- | --- |
| (a) 2–9 players | **Passes, unmeasured.** Per-decision and seat-count free in pot fractions; the engine seats 10. No published exploitability number covers 3+ players. |
| (b) True no-limit sizing | **Passes on reading, partial on acting.** Every legal opponent size becomes interpretable; the bot's own sizes stay on the menu — the loss `TABLE_SIZE_AND_SIZING_NOTES.md` Table 6 quantifies. |
| (c) Exploiting opponents by identity | **Neutral, and keep it so.** The mapping is opponent-independent by construction; per-opponent reading belongs in the size buckets of `TABLE_SIZE_AND_SIZING_NOTES.md` §2.2. Map for the engine, bucket for the model, never one structure for both. |
| (d) Hours on one laptop | **Passes.** The mapping is a few arithmetic operations; the menu is what costs. Pluribus's 12,400 core-hours is why the menu stays small and search stays out. |
| (e) GPL-3.0 public repository | **Passes.** The script is our own code implementing published formulas; OpenSpiel is Apache-2.0, one-way compatible into a GPL-3.0 work. |

## 7. Recommendation

**Menu, every street: `{fold, call, 0.5 pot, 1.0 pot, all-in}` — OpenSpiel's
`fchpa` as it ships. Translation: randomized pseudo-harmonic, computed in pot
fractions, with `A = 0` (check) below the smallest bet and all-in at the
shortest covering stack as the top endpoint.** `fchpa` is the largest menu the
engine offers without new engine code, so the choice of size stays in the engine
where the forefront rule puts it; the mapping is the lowest-exploitability
published one and the only one not degenerate at `A = 0`; and search, which beat
translation by 12×, needs compute this project has ruled out. First enlargement
to test: a third rung near 0.75 pot on the flop, the rung whose absence [BS17]
measured at 1,465 mbb/hand.

## Sources

All retrieved and read 2026-09-16.

- **[GS13]** Sam Ganzfried, Tuomas Sandholm, "Action Translation in
  Extensive-Form Games with Large Action Spaces: Axioms, Paradoxes, and the
  Pseudo-Harmonic Mapping", IJCAI 2013, pp. 120–128, 9pp.
  `https://www.cs.cmu.edu/~sandholm/reverse%20mapping.ijcai13.pdf` — formula §6,
  desiderata §4, prior mappings §5, exploitability Tables 1–6.
- **[BS17]** Noam Brown, Tuomas Sandholm, "Safe and Nested Subgame Solving for
  Imperfect-Information Games", NeurIPS 2017. `https://arxiv.org/pdf/1705.02955`
  — §7 and Table 4; Libratus p. 11.
- **[Pluribus]** Noam Brown, Tuomas Sandholm, "Superhuman AI for multiplayer
  poker", *Science* 365(6456), 11 July 2019, doi 10.1126/science.aay2400; read
  via NSF public access `https://par.nsf.gov/servlets/purl/10119653` — sizes and
  off-tree handling pp. 2–4; its reference 39 is [GS13].
- **[OpenSpiel]** `universal_poker.h` (line 62 `BettingAbstraction`, line 52
  `kMaxUniversalPokerPlayers`) and `universal_poker.cc` (`PotSize`,
  `NumDistinctActions`), google-deepmind/open_spiel `master`, 2026-09-16, from
  `raw.githubusercontent.com`.
- **Second-hand through [GS13] §5, not retrieved:** Andersson 2006; Gilpin,
  Sandholm & Sørensen 2008; Schnizlein, Bowling & Szafron 2009; Rubin & Watson
  2012; Hawkin et al. 2012.
