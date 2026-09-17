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

### What may be coded

- Let an AI assistant write the poker code: the code that picks an action, assigns a range to an opponent, reads the board, and combines opponent rates.
- Write decision code as ordinary, testable code: the same inputs and seed give the same answer, tests cover it, and a reviewer can read it line by line.
- Treat the **observed population** as the whole database, seated players' stored rows included, with being seated never the criterion for inclusion, and combine rates across it into a baseline, a classification split, or an archetype.
- Write card-combinatorics bookkeeping ourselves - the 169 preflop hand classes, suit isomorphisms, deck enumeration - and leave ranking or valuing a hand to the engine.
- Derive any opponent archetype fed to the solver from measured action frequencies alone; never hand-write one, and never let it reference hole cards, board cards, or hand strength.

### What may not be coded

- Keep every model call out of the live decision path; when the bot acts it runs ordinary code only, with no language-model inference, no network call to a model, and no prompt.
- Take the content of every poker decision from code a reviewer can follow, never from stored language-model output: a table, a set of weights, or text a model produced.
- Take the game rules and hand evaluation from the engine road, OpenSpiel `universal_poker`, rather than hand-rolling them; reject a change that hand-rolls hand-strength logic in place of the vendored engine, and adapt the engine instead.
- Ground-truth hand ranking against a named external evaluator (currently `treys`), the reference for standard 52-card ranking, and keep it out of the bot's decision path; it validates tests only, never runtime play.
- Keep every way language models play poker badly, as named in `LLM_POKER_FAILURE_MODES.md`, out of the decision code, and reject a change that reintroduces one of them.

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
- Push branches without asking, from any session on any machine, the PC included.

## Licence

- Keep pokerbot public at `github.com/chaserunsfromjob/pokerbot` so classmates can collaborate on it.
- License pokerbot under the GNU General Public License version 3 — GPL-3.0 — whose full text is `LICENSE` at the root, because the vendored engine is GPL-3.0 and publishing is distribution.
- Keep every derived work under GPL-3.0 with its source published; the vendored engine's terms bind whatever is built on or combined with its code, not a separate program that merely ships beside it.
- Use third-party code and data now, and wait for the repository to go private, which is the operator's call, before publishing anything whose licence conflicts with GPL-3.0.

Rules in `~/.claude/CLAUDE.md` (deployed machine-wide from the `heater` fleet
repository) apply on top of this file.
