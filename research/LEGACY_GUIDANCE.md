# Historical guidance — superseded September 16, 2026

This is an archival test fixture, not current instructions. It preserves the
source of the arithmetic design document's quoted table. Current guidance is
in the root CLAUDE.md and explicitly permits original coded/trained strategies.

# pokerbot

A multiway no-limit hold'em poker bot for a class project. Goal: consistently
beat real human players at a table of 3 or more, not chase a theoretical
optimum that does not exist at that table size.

Built on `fedden/poker_ai` (vendored into this repo) rather than from scratch,
for speed and because its MCCFR solver is real, tested code no one here would
beat by hand-rolling it in a few weeks.

## The forefront rule

- Never let an AI model decide a poker action, evaluate a hand, or read a board; call real engine code for that.
- Only use AI-written code for integration, tooling, table-state capture (screen to structured data), and card combinatorics, never for poker judgment itself.
- Reject a change that adds hand-rolled hand-strength or decision logic in place of the vendored engine; adapt the engine instead.
- Write card-combinatorics bookkeeping ourselves - enumerating the 169 preflop hand classes, suit isomorphisms, deck enumeration - but leave anything that ranks or values a hand, or chooses an action, to the engine.
- Ground-truth hand ranking against a named external evaluator (currently `treys`), the reference for standard 52-card ranking, and keep it out of the bot's decision path; it validates tests only, never runtime play.
- Keep opponent-modelling code to the left column of this boundary, and leave every right-column job to the engine.

| Allowed to AI-written opponent-model code | Reserved to the engine |
| --- | --- |
| Counting observed actions | Evaluating hand strength |
| Computing a single rate from its own counts | Choosing an action |
| Shrinking a rate toward a baseline | Assigning a range to an opponent |
| Sorting an opponent into a bucket | Reading board texture |
| Selecting *which* engine strategy to load | Producing the strategy itself |
| Substituting an opponent model into the engine's own solver | Solving |
| Reporting several rates side by side | Combining live-field rates into a quantity that drives a poker decision — multiplying the fold rates of the opponents in the current hand to gate a bluff, for one |

- Allow AI-written code to combine rates across the **observed population** — the whole database, seated players' stored rows included, with being seated never the criterion for inclusion — into a baseline, a classification split, or an archetype, and hand that result to the engine, which still chooses the action.
- Derive any opponent archetype fed to the solver from measured action frequencies alone; never hand-write one, and never let it reference hole cards, board cards, or hand strength.

## Plan

1. Vendor `fedden/poker_ai`, get it running, and find out what it takes to move
   it off the default 20-card short deck onto standard 52-card hold'em.
2. Layer in opponent modeling: track each player's tendencies and adjust
   against them specifically. This is the part that actually beats humans.
3. Only if time remains: refine with a trained model on top of stages 1-2.

## Compute budget

- Keep every computation reachable in hours on one laptop; reject any approach that needs multi-day compute to reach a playable bot.

## Licence

- Keep pokerbot private: never publish it, give it to a classmate, or sell it.
- Treat the vendored engine's GPL-3.0 terms as imposing nothing while pokerbot stays private, since they attach only on distribution.
- Reopen this licence decision with the operator before handing the code to anyone.

Rules in `~/.claude/CLAUDE.md` (deployed machine-wide from the `heater` fleet
repository) apply on top of this file.
