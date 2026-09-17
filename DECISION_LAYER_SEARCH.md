# Choosing the action at the table: search options on top of OpenSpiel

## What this file is for

The engine question is settled: `ENGINE_ALTERNATIVES.md` (branch
`worker/7f09949cb56f`) measured seven candidates and recommends OpenSpiel's
`universal_poker` — 52 cards, real bet sizing, 2 to 9 seats. An engine deals
the cards, tracks the chips and pays out the pot. It does not know how to play.

This file asks the next question: **when it is the bot's turn and a human is
waiting, what code picks the action?** It covers the ways that do the thinking
**during the hand**. The other half — strategies worked out **in advance** and
looked up at the table — is a sibling document, `DECISION_LAYER_BLUEPRINT.md`,
and nothing about training a strategy with counterfactual regret minimisation
is decided here. Solvers and equity products bought or downloaded off the shelf
are `RESOURCES_SOLVERS.md`. Ready-made bots are `RESOURCES_BOTS.md`. Which bet
sizes the bot offers, and what it does when an opponent bets something not on
that list, are settled in `ACTION_TRANSLATION.md` and assumed here.

Four options are covered, and each is rated against the same five things:

- **(a) 2 to 9 players** — the operator's firm requirement.
- **(b) true no-limit sizing** — any amount, not a four-move menu.
- **(c) exploiting specific opponents by identity** — the point of
  `OPPONENT_MODEL_DESIGN.md`.
- **(d) reachable in hours on one laptop** — `CLAUDE.md`'s compute budget.
- **(e) fits a public GPL-3.0 repository** — `CLAUDE.md`'s licence section.

### The rule this document assumes

`CLAUDE.md`'s forefront rule governs everything below. Its two halves, stated
as they stand:

- **"What may be coded"** — an AI assistant may write the poker code: the code
  that picks an action, assigns a range to an opponent, reads the board, and
  combines opponent rates across the observed population. That code has to be
  ordinary and testable — the same inputs and seed give the same answer, tests
  cover it, a reviewer can read it line by line. Card-combinatorics bookkeeping
  is ours; ranking or valuing a hand is the engine's. Any opponent archetype
  fed to a solver has to be derived from measured action frequencies alone,
  never hand-written and never referring to hole cards, board cards or hand
  strength.
- **"What may not be coded"** — no model call anywhere in the live decision
  path, no stored language-model output as the content of a decision, and no
  hand-rolled hand-strength logic in place of the vendored engine.

So every option below is free to assign ranges to opponents and to combine
several opponents' rates; what none of them may do is call a model at the
table, take the content of a decision from stored model output, or rank a hand
with code written here.

---

## The recommendation, first

**Build one decision-time search: depth-limited search over the engine's own
tree, with the hand finished at the depth limit by one of four biased
continuation strategies, and let the opponent model choose those continuation
strategies per seat.** Start it with hand-set continuation biases so it plays
this week, and swap in blueprint-derived ones as
`DECISION_LAYER_BLUEPRINT.md` produces them.

Three measured reasons, all from this laptop, all reproducible from
`research/decision_layer/`:

1. **It is the only one of the four that covers 2 to 9 players and takes an
   opponent model.** OpenSpiel's own Information Set Monte Carlo Tree Search —
   the obvious first choice, and shipped ready to use — **crashes the process
   at three or more players** on `universal_poker`. That is not a slowdown; it
   is a hard stop, and the cause is a single line of OpenSpiel's own source.
2. **Wiring the opponent model in costs nothing measurable at the table.** The
   same search, with every seat's assumed strategy drawn from that seat's
   fold-to-bet rate and aggression, ran at **3,651 play-outs per decision
   against 4,404** at three players in 250 ms, and **2,434-3,447 against
   2,142-2,739** at six — the same, within the spread of the runs. The
   opponent model's cost is offline and in the hand database, not in the
   decision.
3. **The clock is not the binding constraint.** A real table gives the bot
   10-25 seconds. In 10 seconds this search completed **158,779 play-outs at
   three players** and 68,212 at six. What limits it is the
   quality of what happens at the leaves, which is the blueprint's job, not
   the speed.

**Keep the equity-versus-pot-odds rule as well**, but as a floor and a guard
rather than as the bot: it is free to run (over two million simulated run-outs
inside 2 seconds), it uses the engine's own equity calculator so no hand is
evaluated by code written here, and it gives a cheap sanity check on whatever
the search returns. It cannot, on its own, bluff, size a bet, or take money off
a specific person.

**Do not build on OpenSpiel's IS-MCTS** unless someone first replaces its world
sampler. That repair is small and is described below; until it is done, IS-MCTS
is a two-player-only option and even there it managed only **69-85 simulations
in 250 ms**.

---

## In plain words, before the jargon

- A **decision layer** is the code that answers "what do I do now?" when it is
  the bot's turn. It sits on top of the engine.
- A **play-out** (or **simulation**) is one imagined finish of the hand: deal
  out the unknown cards, have everyone act according to some assumption, see
  who wins. Every method below works by doing enormous numbers of these and
  averaging.
- **Equity** is the share of the pot a hand would win on average if the hand
  were played to the end from here. Pocket aces against a random hand, heads
  up, has about 85% equity.
- **Pot odds** are what the call costs against what the pot pays. Calling 100
  into a pot of 300 needs the hand to win 100/400 = 25% of the time to break
  even.
- A **blueprint** is a full strategy worked out in advance, covering every
  situation coarsely. Search improves on it in the situation actually faced.
- **Depth-limited search** means looking ahead a little way — usually to the
  end of the current betting round — and then stopping and estimating what the
  rest of the hand is worth, rather than playing every branch to the river.
- A **continuation strategy** is one of the ways the hand might be finished
  from that stopping point: give up a lot, call a lot, raise a lot. Pluribus
  used four of them.
- **Determinization** is guessing the hidden cards once, so that the imperfect
  information game becomes an ordinary one for a moment. Do it many times with
  different guesses and average.

---

## How every number here was produced

Two programs, both committed, both runnable with no arguments:

| Program | What it does |
| --- | --- |
| `research/decision_layer/check_openspiel_modules.py` | imports every OpenSpiel piece this document names, records what `universal_poker`'s own equity calculator answers for a known heads-up matchup, and reproduces the crash described below |
| `research/decision_layer/bench_decision_layer.py` | times all four options at 2, 3 and 6 players under a 250 ms, a 2 s and a 10 s budget |

Raw output of every run quoted here is committed beside them under
`research/decision_layer/raw/`. The benchmark now prints its full command line
into that header; the committed raw files predate that line, and the flags
behind them, reconstructed from their own rows, were: `bench_fcpa.txt` the
defaults; `bench_table_budget_10s.txt` `--seats 3 6 --budgets 10 --repeats 1
--decisions 2 --options equity dls`; `bench_fullgame.txt` `--abstraction
fullgame --seats 3 6 --decisions 3 --options dls`. `openspiel_modules.txt`
likewise predates the wording change described under option 1 and still reads
"published" where the script now says "engine's own answer".

Conditions, stated because a poker timing without them means nothing:

| Setting | Value |
| --- | --- |
| Machine | Apple M4, 10 cores, 16 GiB, macOS 15.2 (24.2.0) |
| Software | Python 3.13.15, `open_spiel` 2.0.2 (the version this venv installs) |
| Game | `universal_poker`, 52 cards, no-limit, 4 betting rounds, blinds posted in engine-seat order 100 then 50 — the big blind on engine seat 0, the reverse of the bot's own table, which posts 50 then 100 — and, in the two-seat runs, the heads-up acting order reversed with it (`firstPlayer` 2 1 1 1, against the table's 1 2 2 2, so the small blind, on engine seat 1, acts first before the flop and the big blind first afterwards — the table's own order by blind role, with the two seats' labels exchanged) — 20,000 chips a seat (200 big blinds). See the provenance row below on what that reversal was measured to cost |
| Betting abstraction | `fcpa` (fold / call / pot bet / all-in) unless a row says `fullgame`. The menu `ACTION_TRANSLATION.md` recommends is `fchpa`, which adds a half-pot rung; everything measured here used `fcpa`, so every figure below is one rung short of the recommended menu |
| Offline training | **none**; nothing below has a blueprint behind it |
| Repeats | 2 per configuration at 250 ms and 2 s, 1 at 10 s; ranges quoted are across repeats and across the timed decisions in each run — 5 in the `fcpa` run, which is what `--decisions` defaults to, 3 in the `fullgame` run, 2 in the 10 s run |
| Held awake with | `caffeinate -i`, so a sleeping laptop cannot silently ruin a timing |

**The load warning, and it matters here.** This laptop is shared with other
agents. The count of programs waiting for a core, averaged over the last
minute — the **1-minute load average**, the first number `uptime` prints — is
recorded beside every figure in the raw files, and in every table below. Other
work on this machine pushed it to **4.0-4.7 during most of the run and to
5.6-6.9 during the last third**. `ENGINE_ALTERNATIVES.md` sets the bar at
**below 4.0** for a timing to be trusted, and this run does not clear it.
Everything below is therefore a **lower bound on speed**: an idle laptop would
do more play-outs per decision, not fewer. The comparisons between options
survive it better than the absolute numbers do, because the options were run
in one sitting under the same conditions — but the rows marked with a
dagger (†) were taken at load above 5.5 and should not be compared with the
others without re-running them.

Every latency figure below is a **deadline that was met at the median**: the
median wall-clock time per decision came out at 0.250 s, 2.000 s and 10.001 s
against budgets of 0.25, 2 and 10 s, at every seat count, for every option that
ran at all. The worst single decision did overshoot, because each method checks
the clock before starting another play-out and cannot interrupt the one already
running: the raw maximum column reaches **0.258 s against the 250 ms budget**
and **2.004 s against the 2 s budget**, an overshoot of up to 8 ms. At a table
that is nothing. Latency is therefore not what separates these methods;
**what they get done inside it** is.

---

# Option 1 — Equity versus pot odds, with Monte Carlo equity

## What it is

Work out how often this hand wins from here, compare that with what the call
costs, and act on the comparison: fold when the hand wins less often than the
price demands, call when it is close, raise when it is far ahead. It is the
oldest computer poker recipe there is, and it is one page of code.

## What OpenSpiel already ships

**The equity calculator itself, inside `universal_poker`, and it is multiway.**
This is the find of this survey. The game takes a parameter
`calcOddsNumSims`; set it to a number of simulations and every state answers
`state.to_json()["odds"]` with a win share and a tie share **for each seat**.
The implementation is `CalculateOdds` in `universal_poker.cc` (line 1162 at tag
`v2.0.2`): it takes the seats that have not folded, completes the board with a
fresh shuffle, evaluates the showdown with the engine's own hand ranking, and
counts. Folded seats come back as zero, and the odds move when the flop lands —
both checked.

Why that matters beyond convenience: it means **no hand is ever ranked by code
written here**, which is what `CLAUDE.md`'s forefront rule reserves to the
engine most firmly. What `check_openspiel_modules.py` records is the engine's
own answer, not a comparison with a published table: pocket aces against
seven-deuce offsuit heads-up came back **0.871 win, 0.004 tie over 100,000
simulations**. The script's only assertion is that the win share falls between
0.86 and 0.90 — a sanity band chosen here, with no external source behind it —
so this is a check that the calculator is wired up and answering, not a check
of its accuracy against a published figure.

**What it does not give**, and this is the catch: it computes the odds from the
hole cards *it can see*, which at a real table means the bot's own only. To use
it in play the bot must guess the opponents' cards, and it is our code that
does the guessing — which the forefront rule allows outright, ranges included.
`bench_decision_layer.py` does it the neutral way — deal every unseen card with
equal probability — as a measurement choice, not a rule: these timings are
meant to carry no opponent model at all. Narrowing the guess to a range is
open to this option, and the rule's one condition on it is that the narrowing
come from measured action frequencies rather than a hand-written guess.

## What it needs precomputed

Nothing. It plays the first hand it is switched on for.

## Latency, per table size

Play-outs here are the engine's own simulated run-outs; 200 of them per guessed
opponent holding. "Worlds" is how many different guesses of the opponents'
cards were averaged.

| Seats | Budget | Play-outs per decision (lowest / the run medians / highest) | Worlds | Peak memory | Load |
| --- | --- | --- | --- | --- | --- |
| 2 | 250 ms | 169,200 / 259,600-276,800 / 294,400 | ~1,340 | 34 MiB | 4.02 |
| 2 | 2 s | 1,685,600 / 2,074,000-2,100,400 / 2,219,800 | ~10,400 | 34 MiB | 4.17-4.44 |
| 3 | 250 ms | 248,400 / 257,400-263,600 / 278,200 | ~1,300 | 34 MiB | 4.41 |
| 3 | 2 s | 1,749,800 / 1,977,400-2,005,600 / 2,191,800 | ~9,950 | 35 MiB | 4.47-4.65 |
| 3 | 10 s † | 10,283,000 / 10,550,300 / 10,817,600 | ~52,750 | 37 MiB | 5.67 |
| 6 | 250 ms | 125,200 / 175,800-186,200 / 200,200 | ~900 | 35 MiB | 4.47 |
| 6 | 2 s | 1,611,200 / 1,668,400-1,677,000 / 1,702,800 | ~8,360 | 35 MiB | 4.54 |
| 6 | 10 s † | 6,002,800 / 7,091,200 / 8,179,600 | ~35,460 | 38 MiB | 6.01 |

Decisions per second: 4.0 at the 250 ms budget, 0.50 at 2 s, 0.10 at 10 s — in
every case the budget, not the method, sets the rate. Six seats gets through
about a third fewer run-outs than three — roughly 180,000 against 260,000
inside 250 ms — because more hands have to be dealt and ranked per run-out.

## What it can do in the 10-25 seconds a real table allows

Far more than it needs. The statistical error on an equity estimate from
50,000 guessed worlds is a fraction of a percent; it is already there at
250 ms. **Given ten seconds this method spends nine and a half of them making
an answer it already had.** Its weakness is not speed. It is that a comparison
of two numbers cannot decide *how much* to bet, cannot bluff on purpose, and
assumes the opponents' cards are random when they are not.

## How the opponent model enters

Weakly, and the limit is the method rather than the rule. The routes:

- **Thresholds per opponent bucket.** Call a little wider against a seat whose
  aggression is high, because its bets mean less. This is one seat's own
  measured rate driving the bot's action: `OPPONENT_MODEL_DESIGN.md`'s Tier 1
  in its thinnest possible form.
- **Narrowing the guessed holdings** of a specific opponent is the route that
  would actually pay, and the forefront rule permits it — assigning a range to
  an opponent is named under "What may be coded". It is reachable here only
  through the guessed worlds, since the engine's odds call takes a deal and not
  a weighted range: the narrower range has to be expressed as which worlds get
  dealt, and it has to come from that seat's measured frequencies.
- **Combining several live opponents' fold rates** to gate a bluff is permitted
  too — the rule treats the observed population as one database — but this
  method has nowhere to put the combined number, because comparing equity with
  pot odds does not choose a bet size and cannot bluff on purpose.

Dropping the old prohibition removes one reason this note previously gave for
preferring a search. The recommendation does not rest on it and survives on the
two measured reasons: IS-MCTS dies above two players, and what each method gets
done inside the clock.

## Rating

| Test | Verdict |
| --- | --- |
| (a) 2-9 players | **Yes.** Measured at 2, 3 and 6; the calculator handles any seat count and skips folded seats. |
| (b) true no-limit sizing | **No.** The comparison yields fold/call/raise; the size has to come from somewhere else. Turning an opponent's arbitrary amount into a menu rung is action translation, which `ACTION_TRANSLATION.md` settles: randomised pseudo-harmonic mapping computed in pot fractions, onto the menu it recommends, `fchpa`. |
| (c) exploiting specific opponents | **Partly.** Both routes are open under the rule — threshold nudges and narrowing the guessed worlds — but the output is one comparison of two numbers, so what a model can buy here is bounded: no bet size, no deliberate bluff. |
| (d) hours on one laptop | **Yes, minutes.** No training, 34 MiB, works immediately. |
| (e) public GPL-3.0 | **Yes.** OpenSpiel is Apache-2.0, which GPL-3.0 can absorb; nothing else is needed. |

---

# Option 2 — Information Set Monte Carlo Tree Search (OpenSpiel ships one)

## What it is

Build a search tree over *information sets* — everything the bot could be
facing given what it has seen — rather than over exact card layouts. Each
simulation guesses the hidden cards afresh, walks down the tree choosing
promising moves, plays the rest out, and feeds the result back up. It is the
standard answer for imperfect-information games and it is Cowling, Powley and
Whitehouse's (2012).

## What OpenSpiel already ships

Both versions, and both import here (`check_openspiel_modules.py`, all OK):

- **`pyspiel.ISMCTSBot`** — the C++ implementation,
  `open_spiel/algorithms/is_mcts.cc`. Takes a seed, a leaf evaluator, an
  exploration constant, a simulation cap, a cap on how many card layouts to
  reuse, and — usefully for a real table — **`max_wall_clock_time`**, so it
  can be told "answer within 250 ms" directly.
- **`open_spiel.python.algorithms.ismcts`** — the same algorithm in Python,
  slower but open to modification.
- **`pyspiel.RandomRolloutEvaluator`** for the leaves, and **`pyspiel.Evaluator`**,
  the base class a blueprint would be plugged in as.

## The blocker, and it is hard

**OpenSpiel's IS-MCTS segfaults on `universal_poker` at three or more
players.** Not an exception — the process dies. It happened in all eight
configurations tried (3 and 6 seats, both budgets, both repeats), and the
benchmark runs it in a child process precisely so the rest of the measurements
survive.

The cause is one line of OpenSpiel's own source. IS-MCTS asks the state for a
consistent guess of the hidden cards, `ResampleFromInfostate`
(`universal_poker.cc:1101`), which calls `GetHistoriesConsistentWithInfostate`,
whose first line is:

    if (acpc_game_->GetNbPlayers() != 2) return {};

That returns an empty handle above two players, and the caller dereferences it
immediately. Reproduced directly, without IS-MCTS in the way, by
`check_openspiel_modules.py`: `CRASHES: exit -11 (SIGSEGV)`.

**The repair is small and is the reason this option is not struck out.** A
guess of the hidden cards is card bookkeeping, which `CLAUDE.md` grants to
AI-written code; `bench_decision_layer.py` already contains one
(`determinize`, about twenty lines: keep the board and our own cards, deal the
other seats out of the unseen deck, replay the betting). It checks itself
against the engine's own account of which seat holds which card. Handing that
to the **Python** IS-MCTS in place of the broken call is a small change; the
C++ one cannot be reached without rebuilding OpenSpiel. The cost of that swap
is the Python implementation's speed, which is the thing already in shortest
supply.

## What it needs precomputed

Nothing to run. To be any good, a blueprint at the leaves — otherwise every
simulation finishes the hand at random, which in a four-round no-limit game is
a very noisy estimate of anything.

## Latency, per table size

| Seats | Budget | Simulations per decision (lowest / the run medians / highest) | Peak memory | Load |
| --- | --- | --- | --- | --- |
| 2 | 250 ms | 69 / 74-82 / 85 | 48-52 MiB | 4.54-4.66 |
| 2 | 2 s | 629 / 681-726 / 732 | 48-49 MiB | 4.53-4.98 |
| 3 | any | **process killed (SIGSEGV), 4 of 4 runs** | — | 4.53 |
| 6 | any | **process killed (SIGSEGV), 4 of 4 runs** | — | 4.53 |

Simulation counts come from a second timed pass with a fixed simulation cap and
no deadline, because the C++ bot does not report how many it ran; the deadline
pass confirms it honours the budget (0.250-0.253 s and 2.000-2.003 s).

Between **280 and 370 simulations a second**, across both budgets. For comparison, the equity option manages
over a million engine run-outs a second on the same machine, and the
depth-limited search below manages 17,000-30,000. IS-MCTS is three orders of
magnitude slower per unit of work because each simulation clones and re-walks
game states rather than just dealing cards.

## What it can do in the 10-25 seconds a real table allows

At two players: roughly **3,300-8,300 simulations**. Spread over four moves and
four betting rounds that is a thin tree, and without a blueprint at the leaves
its estimates are noisy. At three or more players: **nothing at all** until the
sampler is replaced.

## How the opponent model enters

This is where IS-MCTS is genuinely attractive, if it ran. The Python version
keeps a prior over each node's actions and takes a pluggable evaluator, so a
seat's fold-to-bet rate and aggression can bias both which branches get
explored and how the leaves are scored — per seat, by identity, exactly what
`OPPONENT_MODEL_DESIGN.md` Tier 2 asks for. The C++ version exposes the
evaluator but not the per-seat prior.

## Rating

| Test | Verdict |
| --- | --- |
| (a) 2-9 players | **No, as shipped** — crashes above 2. Yes with a replacement sampler that has not been written. |
| (b) true no-limit sizing | **In principle yes** (it searches whatever the engine offers), in practice no: at 19,803 legal moves the root alone cannot be expanded in the budget. |
| (c) exploiting specific opponents | **Yes, structurally** — priors and evaluator are per seat. Unreachable while (a) fails. |
| (d) hours on one laptop | **Yes to run, no to be good**: 330 simulations a second, and it wants a blueprint. |
| (e) public GPL-3.0 | **Yes.** Apache-2.0 upstream, patch would be ours. |

---

# Option 3 — Depth-limited search with a blueprint at the leaves (Pluribus-style)

## What it is

Pluribus's structure, and the only one on this list with a published result
against elite humans. Look ahead only to the end of the current betting round.
At that point, rather than guessing a value, let each player choose among
**four continuation strategies** — four different ways of finishing the hand,
from give-up to very aggressive — and play the hand out that way. Brown and
Sandholm's key sentence, verified in the paper: "Each action in that sequence
corresponds to a selection of a continuation strategy for that player for the
remainder of the game", with **k = 4 in Pluribus**. Letting the opponent pick
among several continuations is what stops the search from assuming the
opponent will keep playing one fixed way, which is the classic way this kind of
search fools itself.

## What OpenSpiel already ships

**Not this.** OpenSpiel ships MCTS, IS-MCTS, the CFR family, best-response and
exploitability tools — all import fine here — but no depth-limited
imperfect-information search. What it ships that this can be built *on* is the
part that matters: a tested game, legal moves, chance events, showdown
evaluation, and `pyspiel.Evaluator` as the leaf hook. The search loop is about
sixty lines; `bench_decision_layer.py` contains a working one (`decide_dls`),
and it is what was timed.

## What it needs precomputed

**The four continuation strategies, which is what a blueprint is for.** This is
the honest weakness of the measured version: its four continuations are
hand-set biases (fold-heavy, call-heavy, aggressive, very aggressive), not
solver output. That makes the speed figures real and the *play* provisional.
`DECISION_LAYER_BLUEPRINT.md` is the document that says where real ones come
from. Pluribus's own blueprint cost **12,400 CPU core-hours on a 64-core server
over 8 days**, which `CLAUDE.md`'s compute budget rules out at that scale.

## Latency, per table size

A play-out here is one hand finished from the depth limit under a drawn
continuation strategy, and each one includes a fresh guess of the hidden cards.

| Seats | Budget | Play-outs per decision (lowest / the run medians / highest) | Peak memory | Load |
| --- | --- | --- | --- | --- |
| 2 | 250 ms | 5,669 / 7,066-7,148 / 10,903 | 35 MiB | 4.53 |
| 2 | 2 s | 41,092 / 54,893-57,075 / 86,456 | 35 MiB | 4.31-4.38 |
| 3 | 250 ms | 3,960 / 4,404-4,576 / 4,907 | 35 MiB | 4.37 |
| 3 | 2 s | 32,376 / 34,449-35,705 / 39,257 | 35 MiB | 4.04-4.32 |
| 3 | 10 s † | 156,578 / 158,779 / 160,980 | 38 MiB | 5.62 |
| 6 | 250 ms | 1,851 / 2,142-2,739 / 4,488 | 35 MiB | 4.04 |
| 6 | 2 s | 12,358 / 17,450-28,748 / 33,922 | 35 MiB | 4.02-4.34 |
| 6 | 10 s † | 66,342 / 68,212 / 70,082 | 38 MiB | 5.58 |

Six seats costs roughly half of three, and three roughly two-thirds of two:
more seats means more acting players per play-out and a longer hand.

**With true no-limit sizing (`fullgame`), the same search collapses** — 19,803
legal moves at the first decision, and the cost is in building the state, not
in choosing among them. Measured at load 5.2-5.6 (†), weighing a sample of 8 of
the legal amounts, the same shortcut `ENGINE_ALTERNATIVES.md` took:

| Seats | Budget | Play-outs per decision (lowest / the run medians / highest) | Versus `fcpa` |
| --- | --- | --- | --- |
| 3 | 250 ms | 170 / 189-196 / 268 | about 23× fewer |
| 3 | 2 s | 977 / 1,159-2,036 / 2,122 | 17-30× fewer |
| 6 | 250 ms | 76 / 98-114 / 386 | 19-28× fewer |
| 6 | 2 s | 781 / 875-1,074 / 3,154 | 16-33× fewer |

That is a factor of roughly 20, the same order as the "about fifty times"
`ENGINE_ALTERNATIVES.md`
measured for its own chooser, and it is the single strongest argument for
choosing a small menu of bet sizes rather than the full no-limit tree — a
decision `TABLE_SIZE_AND_SIZING_NOTES.md` owns and `ACTION_TRANSLATION.md` has
now settled: the menu is `fchpa` (fold, call, half-pot, pot, all-in), and an
opponent's off-menu bet is read by randomised pseudo-harmonic mapping in pot
fractions. Every figure above was measured on `fcpa`, one rung short of that
menu. The throughput figures are expected to carry across the extra rung
roughly unchanged — a fifth candidate action costs one more branch to weigh,
not a costlier play-out, which is what the `fullgame` collapse charges for —
but what each candidate action gets is then about a fifth fewer play-outs.
That is an expectation from the shape of the method, not a measurement.

## What it can do in the 10-25 seconds a real table allows

At three players, **about 160,000 play-outs in 10 seconds**, so 300,000-400,000
in the 20-25 seconds a table usually allows. At six, **about 68,000 in 10
seconds**. Spread over four candidate moves that is tens of thousands of
finishes per move — enough for the averages to settle. The clock is not this
method's problem either.

## How the opponent model enters

Directly, and this is the point. Each seat's continuation strategy is drawn per
play-out; `OPPONENT_MODEL_DESIGN.md` Tier 1 is exactly a rule for choosing
which precomputed strategy to load for a named opponent, and the design already
reserves that choice to AI-written code while leaving the strategy itself to
the engine. Option 4 measures the cost of doing it.

## Rating

| Test | Verdict |
| --- | --- |
| (a) 2-9 players | **Yes.** Measured at 2, 3 and 6; nothing in it assumes a seat count. |
| (b) true no-limit sizing | **Partly.** It runs on `fullgame`, at roughly a twentieth of the throughput, and only by weighing a sample of the legal amounts. |
| (c) exploiting specific opponents | **Yes** — per-seat continuation strategies are the natural hook. |
| (d) hours on one laptop | **Yes to build and run** (35 MiB, works today with hand-set continuations); the blueprint behind the leaves is a separate budget question. |
| (e) public GPL-3.0 | **Yes.** Our code plus Apache-2.0 OpenSpiel. |

---

# Option 4 — The same search, with each opponent's assumed strategy from their own model

## What it is

Option 3, with one change: instead of drawing a seat's continuation strategy at
random from the four, draw it from **that seat's own measured numbers** — how
often they fold when bet at, and how aggressive they are. A seat that folds 62%
of the time when bet at is assumed to fold in the play-outs 62% of the time, so
the search finds that bluffing into them pays, by itself, from the engine's own
payoffs. This is the structure of Ganzfried and Sandholm's deviation-based best
response, with the expensive part moved offline, which is what
`OPPONENT_MODEL_DESIGN.md` §3.4 already recommends.

## What OpenSpiel already ships

The same as option 3 — the game, the payoffs, the legal moves. Additionally
`open_spiel.python.algorithms.best_response` and `...exploitability` (both
import here) compute an exact best response to a fixed opponent policy, which
is the offline check on whether a per-bucket counter-strategy is actually
better, and the answer to requirement **E2** in `OPPONENT_MODEL_DESIGN.md`'s
engine-requirements table.

## What it needs precomputed

A hand database, which the bot builds by sitting at tables. Nothing else: the
stats it consumes — `fold_to_cbet_flop`, `afq_flop/turn/river`, `vpip`, `pfr` —
are Tier A and Tier B of `OPPONENT_MODEL_DESIGN.md` §2.3, and the design's
Table C already says how many hands each needs before it is trustworthy. The
values used in the benchmark are plausible stand-ins, not measured play: what
is measured here is the **cost** of consulting a model, not the profit from it.

## Latency, per table size

| Seats | Budget | Play-outs per decision (lowest / the run medians / highest) | Same, without the model (option 3) | Load |
| --- | --- | --- | --- | --- |
| 2 | 250 ms | 6,415 / 8,252-8,697 / 11,239 | 5,669 / 7,066-7,148 / 10,903 | 4.24 |
| 2 | 2 s | 38,131 / 52,602-68,366 / 93,775 | 41,092 / 54,893-57,075 / 86,456 | 4.61-4.73 |
| 3 | 250 ms | 3,055 / 3,651-3,661 / 4,670 | 3,960 / 4,404-4,576 / 4,907 | 4.73 |
| 3 | 2 s † | 31,333 / 38,575-40,361 / 45,805 | 32,376 / 34,449-35,705 / 39,257 | 6.77-6.90 |
| 6 | 250 ms † | 2,354 / 2,434-3,447 / 4,777 | 1,851 / 2,142-2,739 / 4,488 | 6.38 |
| 6 | 2 s † | 16,792 / 18,178-26,667 / 36,916 | 12,358 / 17,450-28,748 / 33,922 | 5.98-6.33 |

**The model is free at the table.** Every row overlaps the corresponding row
without it; where it looks slower (3 players, 250 ms) the machine was busier,
and where it looks faster (6 players) so was the comparison. The lookup is one
dictionary access per seat per play-out, and it disappears into the cost of
dealing cards.

## What it can do in the 10-25 seconds a real table allows

The same as option 3 — tens to hundreds of thousands of finishes — with every
one of them assuming the opponents play the way those particular humans have
been observed to play.

## The risk this option carries, which the others do not

Assuming an opponent folds 62% of the time and being wrong is how a bot loses
money faster than it would by playing straightforwardly.
`OPPONENT_MODEL_DESIGN.md` §5 is the section that covers this — shrinkage
toward a baseline until the evidence is there, a floor on how far the
assumption may move, and switching exploitation off when it stops earning.
None of that is optional, and none of it is measured here.

## Rating

| Test | Verdict |
| --- | --- |
| (a) 2-9 players | **Yes**, measured at 2, 3 and 6. |
| (b) true no-limit sizing | **Partly**, exactly as option 3. |
| (c) exploiting specific opponents | **Yes, and best of the four** — the assumption is per seat, keyed on the opponent's identity, and the engine still picks the action from its own payoffs. |
| (d) hours on one laptop | **Yes**, at no measurable cost over option 3; the hand database is the real prerequisite. |
| (e) public GPL-3.0 | **Yes.** |

---

# All four, side by side

| | (a) 2-9 players | (b) true no-limit sizing | (c) exploits a named opponent | (d) hours on one laptop | (e) public GPL-3.0 |
| --- | --- | --- | --- | --- | --- |
| 1. Equity versus pot odds | yes | no | partly | yes | yes |
| 2. IS-MCTS as shipped | **no — crashes above 2** | no | yes, if it ran | runs, but 330 sims/s | yes |
| 3. Depth-limited search, biased continuations | yes | partly (about 20× slower) | yes | yes | yes |
| 4. The same, biased by each opponent's model | yes | partly (about 20× slower) | **yes, best** | yes | yes |

Speed at a glance, at the 250 ms budget, three players, on this laptop with
other work running:

| Option | Work done inside 250 ms | Unit |
| --- | --- | --- |
| 1. Equity versus pot odds | 248,400-278,200 | simulated run-outs |
| 2. IS-MCTS | — (crashes) | — |
| 3. Depth-limited search | 3,960-4,907 | hands finished from the depth limit |
| 4. With opponent model | 3,055-4,670 | hands finished from the depth limit |

The units are not comparable with each other, which is the point: option 1 does
a cheap thing very many times, options 3 and 4 do an expensive thing often
enough.

---

# Ranked shortlist

**1. Depth-limited search with continuation strategies biased by each
opponent's own model (option 4).** The only one that satisfies (a), (c), (d)
and (e) outright, and the opponent model is free at the table. Its weakness is
everything behind the leaves: with hand-set continuations it is a decent
random-ish opponent, and it becomes strong only as the blueprint does.

**2. The same search with generic continuation strategies (option 3).** Not
really a separate build — it is option 4 with the model switched off — but it
is the thing to ship first, because it plays without a hand database and gives
the opponent model something to switch on into.

**3. Equity versus pot odds with the engine's own Monte Carlo equity (option
1).** Keep it. It is a page of code, it reaches a settled answer long inside 250 ms,
it never evaluates a hand itself, and it is the baseline any search has to beat
before anyone trusts the search. Not the bot: it cannot size a bet or bluff.

**4. OpenSpiel's IS-MCTS (option 2).** Blocked at three or more players by an
upstream crash, and slow where it does run. Worth a day only if someone wants
a second, independent decision layer to check the first against — the Python
implementation plus the twenty-line card sampler already in the benchmark.

---

# The recommendation

**Build option 3's search once, and let option 4's opponent model supply its
continuation strategies as soon as `OPPONENT_MODEL_DESIGN.md`'s Tier 1 buckets
exist. Run the equity rule alongside it as a check. Do not start from
OpenSpiel's IS-MCTS.**

That dependency is conditional, not scheduled: `OPPONENT_MODEL_DESIGN.md` §4.5
makes Tier 1 itself conditional on 32 offline solver runs fitting inside the
compute budget and on an engine that accepts a fixed opponent strategy, and
says the task must stop and report if either fails — so the buckets are not a
dated deliverable, which is why the search is built to run without them.

Why this one rather than the obvious alternative: IS-MCTS is the textbook
answer and OpenSpiel ships it ready to use, which is exactly why it was tried
first. It does not run at this project's table sizes, and the fix costs the
same work as building the depth-limited search — which then also matches the
only published architecture that has beaten elite humans at six-player
no-limit, and which takes the opponent model in the place the design document
already expects it.

What this recommendation does **not** claim: that the measured version plays
well. Nothing here was measured in chips won. Every figure above is a count of
work done inside a deadline, which is a necessary condition and not a
sufficient one. The next task after this one is a head-to-head: this search,
with hand-set continuations, against the equity rule and against a random
baseline, over enough hands to put an interval on the difference — the shape
`ENGINE_ALTERNATIVES.md` used for its four-move chooser.

## What would change this recommendation

- A blueprint arriving that is good enough to be looked up directly at the
  table would move work out of search and into
  `DECISION_LAYER_BLUEPRINT.md`'s column.
- A fix upstream to `universal_poker`'s world sampler would make IS-MCTS worth
  re-timing at 3 and 6 seats, though 330 simulations a second would still hurt.
- A decision to play true no-limit sizing rather than a small menu of bet sizes
  costs a factor of roughly 20 in everything measured here. `ACTION_TRANSLATION.md`
  settles that decision the other way — the `fchpa` menu, with an opponent's
  off-menu bet read by randomised pseudo-harmonic mapping — so reopening it
  would be the change that costs the factor of 20.

---

# Sources, each opened and checked

Everything below was fetched and read during this work on 2026-09-16. Where a
publisher blocked automated access, the author's own copy was used and is the
URL given.

- **Brown, N. and Sandholm, T. (2019), "Superhuman AI for multiplayer poker",
  *Science* 365(6456), 885-890, 30 August 2019.**
  `https://noambrown.github.io/papers/19-Science-Superhuman.pdf` (the
  publisher's own page at `science.org` refused automated access; this is the
  first author's copy, 7 pages, checked to carry the same title, authors and
  page numbers). Used for: four continuation strategies ("In Pluribus, k = 4");
  search takes "between 1 and 33 s" per subgame and averages "20 s per hand",
  running on two Intel Haswell E5-2695 v3 CPUs with under 128 GB; the blueprint
  cost "8 days on a 64-core server for a total of 12,400 CPU core hours"; the
  results of 48 mbb/game (standard error 25) and 32 mbb/game (standard error
  15).
- **Brown, N., Sandholm, T. and Amos, B. (2018), "Depth-Limited Solving for
  Imperfect-Information Games", NeurIPS 2018.**
  `https://arxiv.org/abs/1805.08195` (authors and date 2018-05-21 read off the
  listing page). Used for: the method of giving the opponent a choice among
  continuation strategies at the depth limit.
- **Cowling, P. I., Powley, E. J. and Whitehouse, D. (2012), "Information Set
  Monte Carlo Tree Search", *IEEE Transactions on Computational Intelligence
  and AI in Games*, pp. 120-143, DOI 10.1109/TCIAIG.2012.2200894.**
  `https://eprints.whiterose.ac.uk/75048/1/CowlingPowleyWhitehouse2012.pdf`
  (25-page deposited copy; the IEEE page itself refused automated access).
  Used for: what IS-MCTS is, and as the citation OpenSpiel's own implementation
  gives.
- **Long, J., Sturtevant, N. R., Buro, M. and Furtak, T. (2010),
  "Understanding the Success of Perfect Information Monte Carlo Sampling in
  Game Tree Search", AAAI 2010.**
  `https://webdocs.cs.ualberta.ca/~nathanst/papers/pimc.pdf` (7 pages,
  copyright line "2010, Association for the Advancement of Artificial
  Intelligence"). Used for: the two errors that guessing the hidden cards and
  solving the resulting perfect-information game commits — *strategy fusion*
  (pretending a different plan may be used in each guessed world) and
  *non-locality* — and for why the method nonetheless works in practice. This
  is the caution that applies to options 1, 3 and 4 alike, and the reason the
  continuation strategies are drawn per play-out rather than fixed.
- **Ganzfried, S. and Sandholm, T. (2011), "Game theory-based opponent
  modeling in large imperfect-information games", AAMAS 2011**, DOI
  `10.65109/qrfz3633` (title, authors and date 2011-05-02 confirmed through
  Crossref's record on 2026-09-16; the full text was not re-read here because
  `OPPONENT_MODEL_DESIGN.md` §3.2 already surveys it). Used for: the shape of
  option 4 — substitute a model of the opponent's strategy, then let the
  solver answer it.
- **OpenSpiel 2.0.2 source, `google-deepmind/open_spiel`, tag `v2.0.2`.**
  `https://raw.githubusercontent.com/google-deepmind/open_spiel/v2.0.2/open_spiel/games/universal_poker/universal_poker.cc`
  — `calcOddsNumSims` declared at line 194, `CalculateOdds` implemented at line
  1162, `ResampleFromInfostate` at line 1101 and the two-player guard that
  breaks it at line 1111. Also
  `.../v2.0.2/open_spiel/algorithms/is_mcts.cc` for the C++ IS-MCTS. These are
  quotations of source, not measurements.
- **In this repository:** `ENGINE_ALTERNATIVES.md` (branch
  `worker/7f09949cb56f`) for the engine choice, the `fcpa`-versus-`fullgame`
  cost and the measurement conventions this file follows;
  `ACTION_TRANSLATION.md` for the bet-size menu (`fchpa`) and for reading an
  opponent's off-menu bet by randomised pseudo-harmonic mapping in pot
  fractions, which is the translation gap this file no longer records as open;
  `OPPONENT_MODEL_DESIGN.md` for the stat set, the tiers and the safety
  section; `RESOURCES_SOLVERS.md` for off-the-shelf solvers and equity
  calculators; `TABLE_SIZE_AND_SIZING_NOTES.md` for the bet-sizing menu;
  `RESOURCES_BOTS.md` for ready-made bots. `DECISION_LAYER_BLUEPRINT.md`
  (sibling task, in progress) owns everything computed in advance.

---

# Provenance of every number in this document

| Number | Where it comes from |
| --- | --- |
| Every play-out, latency, memory and load figure | `research/decision_layer/bench_decision_layer.py`, raw output in `research/decision_layer/raw/bench_fcpa.txt`, `bench_table_budget_10s.txt`, `bench_fullgame.txt`. These runs were taken with the blinds posted in reverse seat order and, in the two-seat runs, the heads-up acting order reversed with them (at three and six seats the acting order already matched the table's), which changes nothing about their timing and memory claims — measured on 2026-09-17, 3 × 3000 random hands played to the end, median play-outs per second on the old game versus the new one: 2 seats 50,497 versus 50,727 (ratio 1.005), 6 seats 26,076 versus 25,952 (ratio 0.995); and, on the same day, in two clean child processes per case, 3000 random hands played to the end, the largest amount of memory the process ever held at once (its peak resident set size) on the old game versus the new one: 2 seats 22.2 MiB versus 22.1 MiB, 6 seats 22.1 MiB versus 22.1 MiB — but means they were not the bot's exact table; the benchmark now builds its game from `pokerbot.table.game_string` and the figures here have not been re-measured on it. |
| Which OpenSpiel pieces import, and the AA-versus-72o equity | `research/decision_layer/check_openspiel_modules.py`, raw output in `research/decision_layer/raw/openspiel_modules.txt`; the 0.871/0.004 is the engine's own answer and is compared with no published table |
| The IS-MCTS crash | both programs above; exit status -11 (SIGSEGV), 8 of 8 runs at 3 and 6 seats |
| Line numbers in `universal_poker.cc` and `is_mcts.cc` | the OpenSpiel source at tag `v2.0.2`, fetched 2026-09-16; source quotations, not measurements |
| Pluribus's costs, timings and win rates | the paper, cited above; not reproduced here |
| The `fcpa`-versus-`fullgame` factor of about 23 | this document's own fullgame run, which agrees in order with the "about fifty times" in `ENGINE_ALTERNATIVES.md` for a different chooser |
| Opponent stat names and tiers | `OPPONENT_MODEL_DESIGN.md` §2.3 and §4.5; the values fed to the benchmark are stand-ins, and no claim is made about them |

**Not measured here, and worth saying plainly:** chips won. No option above was
played against another for money, in this document. Speed inside a deadline is
what was measured, at 2, 3 and 6 players, on a laptop that was busier than it
should have been.
