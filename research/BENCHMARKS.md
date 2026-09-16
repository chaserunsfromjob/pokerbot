# Fixed benchmarks and continuing research

The operator wants continued research, including after a benchmark passes.
There is no morning cutoff. A pass is a milestone: retain that exact result
and add a harder stage. Do not rewrite a failed test until it appears to pass.

## First milestone: validated improvement in simulation

Current protocol: **first-milestone-v2-reopening**. The isolated PokerKit
reopening repair changes the action tree, so older engine results are historical,
not evidence for the current referee. The frozen policy, opponent pools, +5
target, sample minimum and shared repeated-attempt ledger are unchanged. No
real v1 confirmation attempt was allocated. A future engine change must remain
explicitly versioned, with fresh evaluation rather than reusing old returns.

This is a project acceptance target, not an industry-standard certificate of
poker strength, a GTO claim, or evidence that the bot beats classmates.

1. **Correctness gate.** Independent payout/hand-ranking fixtures, side pots,
   folded-player eligibility, exact bet amounts, short all-ins, 2–9-player
   mechanics, secret-free observations, legal actions and reproducible replay.
   No known correctness failure may be waived for promotion. Corrected PokerKit
   passes single and cumulative short all-ins, limps facing short all-ins,
   each caller's individual reopening threshold, and checks facing short
   opening bets. Unpatched PokerKit 0.7.5 fails the last three gates and is
   retained only for historical replay. Keep these regressions mandatory.
2. **Frozen baseline.** Original equity policy v0.1: 32 samples, .02 call
   margin, .12 raise margin, half-pot sizing, learning off. Freeze its code
   and parameters before candidate tuning. Changing its behavior requires a
   newly named benchmark; it must never be weakened to secure a pass.
3. **Paired evaluation.** Candidate and baseline use the same deals and seat
   rotation against identical opponent configurations. They play separate
   tables so one arm cannot learn from or affect the other. Reset stacks to
   100bb each hand, no rake, and preserve learning only within each session.
   Betting uses integer chip units and tied payouts split fractionally, matching
   the original OpenSpiel benchmark. The PokerKit adapter explicitly overrides
   its default leftover-chip convention. Class-app integer chip allocation has
   not been validated and is a separate rules profile.
4. **Confirmation size.** At least 30 independent sessions per table size,
   504 hands per session, at 6, 7, 8 and 9 seats. This is 120,960 hands across
   both arms at the minimum size. 504 permits balanced rotation for all four
   sizes. This minimum is not a guarantee of adequate statistical power.
5. **Pass criterion.** At each required table size, the paired mean gain is
   at least **+5 bb/100**, and the adjusted confidence interval's lower end is
   above zero. Student-t intervals use independent session means, not hands.
   They are approximate; inspect heavy tails and increase a predeclared sample
   size in a new attempt if uncertainty remains too large.
6. **No repeated-peeking pass.** Finish the frozen sample before judging it.
   Confirmation attempt k spends alpha = .05 / (k * (k+1)); divide that alpha
   across four table sizes. This bounds the total nominal error budget across
   repeated attempts, assuming the per-attempt intervals are calibrated.
   Every attempt uses fresh deals. Keep the global attempt ledger.

Development seeds and table configurations are for tuning only. The four
confirmation mixes in `pokerbot/benchmark.py` must remain held out from tuning.
They include the equity baseline and distinct caller/tight/aggressive mixtures.
These controls are limited and mostly card-independent; random-player wins
alone cannot pass. No trained opponent is currently integrated. Consequently a
first-stage pass only establishes improvement against this restricted pool.

Confirmation now accepts a versioned strategy specification for `equity`,
`river` and `turn` policies. Named-response search can explicitly choose learning
off or learned; oracle input is prohibited in confirmation. Policy identity,
parameters and learning mode round-trip together. Unsupported types, extra
fields and inconsistent settings fail before allocating an attempt. All policy
types use the same existing ledger and alpha schedule; no fresh error budget is
created for a new strategy family.

Legacy flat equity configuration files and manifest formats remain readable.
Source/runtime hashes are still strict: format compatibility is not permission
to resume an old experiment with changed code. Use its frozen revision and
environment. The baseline parameters and source hashes are unchanged. External
policies, range policies and trained checkpoints are not yet supported by this
confirmation entry point; do not represent missing adapters/artifacts as models.
`research/example-search-candidate.json` illustrates the format and is not a
validated candidate or an instruction to consume a confirmation attempt.

Before confirmation, run the full test suites and record results. A known
failure remains a blocker even if pytest calls it an expected failure.
`check-gates` checks the active referee. A test also verifies that substituting
the defective historical OpenSpiel adapter still blocks confirmation.

## Later stages, specified before execution

| Stage | What becomes harder | Evidence required |
| --- | --- | --- |
| Stronger opponents | Frozen trained policies and separately authored card-aware opponents | Fresh paired confirmation; report unsupported seat counts explicitly |
| Opponent learning | Same candidate with no model, known control model, learned model | Positive learned-minus-off effect; oracle is a diagnostic ceiling, not deployment input |
| Robust adaptation | Sparse, deliberately wrong, unseen and changing opponent histories | Prespecified loss/regression tolerances and confidence intervals in each stress cell |
| Stack/generalization | Unequal 20/50/100/200bb stacks and new opponent mixtures | Correct side pots plus held-out performance without retuning on final deals |
| Decision search | Restricted move menus and hidden-information continuations | Strength improvement, measured latency/memory, no leaked actual opponent holdings |
| Class-app readiness | Observations and legal actions captured from the class app | Shadow/replay agreement first, then separately authorized live integration |

Preserve each passed stage as a regression suite. A new stage needs its own
frozen hypothesis, target and sample plan; do not count the initial +5 target as
evidence for all later stages. Pause an invalid experiment on crashes, hidden
information exposure or accounting failures; save the failure and repair it.
If access/resources block all useful work, report the blocker without claiming
success. Do not acquire paid compute or change repository permissions.

## Commands

```
.venv/bin/python -m pokerbot check-gates
.venv/bin/python -m pokerbot tournament --out runs/screen-001 --seats 6 7 8 9 --hands 72
.venv/bin/python -m pokerbot replay runs/screen-001/n6-seed11.jsonl
.venv/bin/python -m pokerbot confirm --out runs/confirm-001 --candidate research/example-candidate.json
.venv/bin/python -m pokerbot resume runs/confirm-001
```

The referee replacement clears the demonstrated correctness blocker. No
strength confirmation has passed. Confirmation freezes versions and parameters,
logs full simulated histories separately
from public profiles, saves each completed session, and resumes only with the
same source hashes and runtime versions. Partial sessions restart with empty learning state. Do not
edit strategy source while a run is in progress. Confirmations use file locks
to prevent overlapping copies; a scheduled agent must inspect existing jobs
before starting anything else.
