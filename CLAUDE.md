# Poker strategy research

Build a durable standard 52-card no-limit hold'em research environment for a
class competition using play chips. Support 2–9 seats; emphasize 6–9-player
strategy evaluation. Player names are stable identifiers.

## Scope authorized by the operator, September 16, 2026

- Original coded strategies, trained policies, opponent exploitation and
  combinations of them are allowed. The former ban on AI-authored strategy
  code is superseded. Live LLM move selection remains outside the project.
- Existing engines implement poker rules and hand ranking. PokerKit replaced
  OpenSpiel as referee after the short-all-in reopening defect was reproduced.
  OpenSpiel remains the frozen equity sampler and historical replay backend.
  `treys` is an independent test oracle, never the runtime evaluator.
- Treat `vendor/poker_ai` as a historical 20-card fixed-limit reference. Do
  not describe it as an implemented standard-deck no-limit strategy.
- Remove the former hours-on-one-laptop ceiling. Measure latency, memory and
  compute requirements. Paid compute still needs separate authorization.
- Strategy code receives only its own cards, public state, legal actions and
  optional opponent observations. Never pass simulator state or a future deck
  into a policy. Privileged replay records are separate from observations.
- Simplified multiway play reduces candidate decisions/search effort, not the
  number of actual participants or their contributions and pot eligibility.
- Keep named-player data separate from policies. Preserve it within a session
  and reset it between independent experimental trials.

## Research and contribution loop

Use primary papers and runnable code to propose hypotheses; record expected
benefit, readiness, risks, and falsifiable criteria. Screen on development deals,
then confirm on fresh held-out configurations. Keep baseline and candidate
versions frozen during a run. Report uncertainty and inconclusive outcomes.
Passing a benchmark starts a harder stage while preserving earlier results.
See `research/BENCHMARKS.md`, `research/BACKLOG.md`, and `research/PROGRESS.md`.

The class-app connection follows validated simulation. Do not connect to live
tables, publish messages, merge main, change visibility, or acquire paid compute
without separate authorization. Pushing verified work to `codex/tonight` is
authorized. Preserve third-party notices and record source provenance for reused
code; repository visibility is not evidence that licensing has been reviewed.

The old opponent-model design and resource surveys are historical inputs, not
requirements that override this scope. Do not silently treat their constraints
or feasibility exclusions as current decisions.
