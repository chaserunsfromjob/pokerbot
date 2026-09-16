# NoRegrets native compatibility probe — September 16, 2026

Pinned source: [`757f7692738069522195d2b486eec60a8b010c0c`](https://github.com/conorarmstrong/noregrets/tree/757f7692738069522195d2b486eec60a8b010c0c).
The unmodified native betting engine fails a targeted short-all-in reopening
probe. Do not train/adopt this revision as a validated rules engine until the
defect is repaired and independent regression checks pass. This source is not
used by the active PokerKit arena, whose checks still pass.

## Reproduced failure

`noregrets_rules_probe.py` compiles a small Rust wrapper importing the pinned
`engine.rs`, `cards.rs` and `eval.rs` directly. It does not translate or rewrite
their rules. Its only crate dependency is the upstream lockfile's rand 0.9.4.

| Sequence | NoRegrets result | PokerKit reference |
| --- | --- | --- |
| Three seats, stacks 10000/250/10000; raise 200, call, short all-in 250 | Prior raiser can raise to 350–10000; applying 350 is accepted | Prior raiser owes 50 and cannot raise |
| Four seats, stacks 300/10000/10000/250; raise 200, short all-ins 250 then 300, call | Prior raiser owes 100 and can raise to 400–10000 | Agrees: cumulative short raises reopen action |

The second case matters: simply forbidding every player who already acted from
raising again would break valid cumulative reopening. The first native case
actually applies the prohibited re-raise, increasing the prior raiser's
contribution to 350. This is not only a mislabeled menu.

Source inspection locates the issue in
[`Hand::raise_bounds`](https://github.com/conorarmstrong/noregrets/blob/757f7692738069522195d2b486eec60a8b010c0c/src/engine.rs#L515):
the returned bounds account for current bet, minimum increment and stack, but
not whether this player's raising rights reopened. The existing short-all-in
test verifies that the earlier bettor must respond; it does not assert that
raising is unavailable.

The recorded probe used Rust 1.98.0 and PokerKit 0.7.5, with source, wrapper,
dependency-lock and runtime hashes in
`results/2026-09-16-noregrets-rules-probe.json`. Compilation plus execution took
about 4.08 seconds. Completed-probe resume preserves the result byte-for-byte.
The first local run was repeated under `noregrets-rules-probe-002` to include
the reference engine/runtime in the provenance guard. Neither run generates
played evaluation hands or establishes native ranking/strategy correctness.

Reproduce from the clean pinned checkout:

```
.venv/bin/python research/noregrets_rules_probe.py --source /path/to/noregrets --out runs/noregrets-rules-probe-002
```

The driver keeps Cargo's registry, compiled objects and wrapper under that
output directory. It does not install anything in the arena's Python environment.

## Other integration requirements verified in source

- The [published source](https://github.com/conorarmstrong/noregrets/blob/757f7692738069522195d2b486eec60a8b010c0c/README.md)
  is MIT licensed, targets 2–6 players and does not distribute pretrained
  blueprints. No native trained model or runnable arena bridge exists here.
- Native `RaiseTo` uses **street commitment**, while our interface uses total
  **whole-hand commitment**. An adapter must translate exactly and reject
  illegal results before application. Native coercion of invalid actions is
  not an acceptable substitute for matching legal actions.
- [`Policy::blueprint_dist`](https://github.com/conorarmstrong/noregrets/blob/757f7692738069522195d2b486eec60a8b010c0c/src/bot.rs#L213)
  exposes a probability vector and counts fallback calls on unseen or
  mismatched information sets. A tiny checkpoint can therefore mostly behave
  like a caller; report fallback coverage rather than calling it strong.
- [`Checkpoint`](https://github.com/conorarmstrong/noregrets/blob/757f7692738069522195d2b486eec60a8b010c0c/src/cfr.rs#L830)
  stores iteration count, abstraction and regret/strategy data, while loading
  receives a fresh training configuration from the caller. Our wrapper must
  freeze and verify seats, stacks, blinds, seeds and training options in a
  sidecar manifest. File existence alone does not ensure compatible resume.
- CLI `--resume ... --iters N` runs **N additional traversals** after loading.
  Preserve that meaning when implementing a bounded continuation loop.

## Next bounded native pilot

First add an isolated MIT-compatible patch for raising rights and test single
and cumulative short all-ins, unopened action, checks before short opening
bets, side pots and postflop amount translation against PokerKit. Preserve this
unpatched failure as evidence; patch success must not erase it.

After rules validation, use three independent training seeds (101, 211, 307),
six seats, 100bb, one worker, four raw-equity buckets and 16 equity rollouts.
Start with 10,000 traversals per seed to test actual artifact creation, then
resume each for 10,000 more with an immutable configuration. Record node counts,
fallback coverage, memory, runtime and hashes; do not call this convergence or
strength. Verify saved/reloaded action distributions and compare with an
uninterrupted matching run where deterministic semantics permit.

Only then add a sanitized native adapter, validate full public state and exact
legal amounts, and run fresh six-seat development matches. This does not satisfy
the project's 6–9-seat benchmark. Keep seven-to-nine-seat use unsupported until
the representation, training and independent validation actually support it.
