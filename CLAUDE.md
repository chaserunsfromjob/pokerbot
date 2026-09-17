# pokerbot

A multiway no-limit hold'em poker bot for a class project. Goal: consistently
beat real human players at a table of 3 or more, not chase a theoretical
optimum that does not exist at that table size.

The engine road is OpenSpiel's `universal_poker`: real, tested game code we call
rather than hand-roll. `fedden/poker_ai` stays vendored in `vendor/poker_ai` as
a reference only, not as this project's basis; its fixed-limit short deck is the
wrong shape to convert. `dickreuter/Poker` is the reference for table-state
capture.

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
- Treat who chooses the action on top of the engine as open and the operator's to settle; the exception to this rule is not granted, so every bullet above holds until the operator grants it.

## Plan

1. Superseded; the engine road is OpenSpiel `universal_poker`. What replaces this
   stage is settled by the reconciliation of the four survey documents, which is
   still to come.
2. Layer in opponent modeling: track each player's tendencies and adjust
   against them specifically. This is the part that actually beats humans.
3. Only if time remains: refine with a trained model on top of stage 2.

## Compute budget

- Keep every computation reachable in hours on one laptop; reject any approach that needs multi-day compute to reach a playable bot.

## GitHub

- Treat `github.com/chaserunsfromjob/pokerbot` as the single source of truth; a change that is not on GitHub does not exist.
- Run `git fetch origin` and read the open pull requests (`gh pr list`) before starting anything; that list is the live board of who is working on what.
- Push the task's branch (`git push -u origin <branch>`) before doing the work.
- Open a draft pull request titled with the task (`gh pr create --draft`) as soon as the branch is pushed, so the other agents see it.
- Push the branch as the work goes, not once at the end.
- Mark the pull request ready (`gh pr ready`) when the work is done, and land the change through it.
- Push `main` the moment a merge lands on it.

## Licence

- Keep pokerbot public at `github.com/chaserunsfromjob/pokerbot` so classmates can collaborate on it.
- License pokerbot under the GNU General Public License version 3 — GPL-3.0 — whose full text is `LICENSE` at the root, because the vendored engine is GPL-3.0 and publishing is distribution.
- Keep every derived work under GPL-3.0 with its source published; the vendored engine's terms bind whatever is built on or combined with its code, not a separate program that merely ships beside it.
- Take any move to close the repository, or to a different licence, to the operator first.

Rules in `~/.claude/CLAUDE.md` (deployed machine-wide from the `heater` fleet
repository) apply on top of this file.
