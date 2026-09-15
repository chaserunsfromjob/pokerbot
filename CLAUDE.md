# pokerbot

A multiway no-limit hold'em poker bot for a class project. Goal: consistently
beat real human players at a table of 3 or more, not chase a theoretical
optimum that does not exist at that table size.

Built on `fedden/poker_ai` (vendored into this repo) rather than from scratch,
for speed and because its MCCFR solver is real, tested code no one here would
beat by hand-rolling it in a few weeks.

## The forefront rule

- Never let an AI model decide a poker action, evaluate a hand, or read a board; call real engine code for that.
- Only use AI-written code for integration, tooling, and table-state capture (screen to structured data), never for poker judgment itself.
- Reject a change that adds hand-rolled hand-strength or decision logic in place of the vendored engine; adapt the engine instead.
- Keep opponent-modelling code to the left column of this boundary, and leave every right-column job to the engine.

| Allowed to AI-written opponent-model code | Reserved to the engine |
| --- | --- |
| Counting observed actions | Evaluating hand strength |
| Computing rates from counts | Choosing an action |
| Shrinking a rate toward a baseline | Assigning a range to an opponent |
| Sorting an opponent into a bucket | Reading board texture |
| Selecting *which* engine strategy to load | Producing the strategy itself |
| Substituting an opponent model into the engine's own solver | Solving |

- Derive any opponent archetype fed to the solver from measured action frequencies alone; never hand-write one, and never let it reference hole cards, board cards, or hand strength.

## Plan

1. Vendor `fedden/poker_ai`, get it running, and find out what it takes to move
   it off the default 20-card short deck onto standard 52-card hold'em.
2. Layer in opponent modeling: track each player's tendencies and adjust
   against them specifically. This is the part that actually beats humans.
3. Only if time remains: refine with a trained model on top of stages 1-2.

Rules in `~/.claude/CLAUDE.md` (deployed machine-wide from the `heater` fleet
repository) apply on top of this file.
