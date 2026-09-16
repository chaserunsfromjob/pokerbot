# Research checkpoint — September 16, 2026, referee replacement

## Current state

The standard 52-card simulation now uses **PokerKit 0.7.5 for betting and
payouts**. OpenSpiel 2.0.2 remains the frozen Monte Carlo equity sampler and
historical replay backend. Original policy and equity sampler hashes are
unchanged. No held-out strength benchmark has passed.

Implemented: sanitized immutable policy observations; original tunable
pot-odds strategy; frozen original opponent/baseline; scripted controls;
seeded matches and seat rotation; SQLite public player profiles isolated by
session; learning off/oracle/learned comparisons; separate privileged replay
logs; source/runtime versions; latency; paired confidence intervals; resumable
confirmation with an error budget across repeated attempts; generic process
policy adapter. Native NoRegrets/dickreuter bridges remain unfinished.

## Rules defect resolved for the active referee

OpenSpiel incorrectly allows the prior raiser to re-raise after a 200/call/250
short-all-in sequence. The native OpenSpiel backend remains defective and is
used only for old replays and equal-contribution showdown equity calculations.
It does not referee new tournaments.

The PokerKit adapter passes that regression plus cumulative short raises that
*do* reopen action, postflop whole-hand raise-to conversion, and heads-up seat
mapping. Betting, payout eligibility and hand ranking stay in existing engines.
A test substitutes the defective OpenSpiel backend and checks that confirmation
still rejects it, so the gate was repaired rather than removed.

The adapter uses PokerKit's supported division callback to retain the original
benchmark's fractional split-pot convention. Native PokerKit instead assigns
leftover chip units to its first eligible winner. A three-way 800-chip split is
now independently tested against the original fractional payout. Integer
class-app odd-chip allocation is a separate, unvalidated rules profile. Current
supported starting stacks are at least one big blind; the benchmark resets
stacks to 100bb each hand. Smaller starting stacks require additional validation.

New records identify backend and payout rule. Unversioned historical logs
select the legacy backend, and old replay verification still passes.

## Validation

- **73 root tests passed; no expected failures in the root suite.**
- **53 vendor tests passed, 2 existing expected failures.** The three historical
  CLI tests still do not assert command success.
- All **680 design arithmetic checks passed**.
- Independent `treys` ranking plus a separate layered-pot calculation matched
  **160 unequal-stack all-in hands across 2–9 seats**.
- Seeded random mechanics and exact replay tests cover another 96 hands across
  2–9 seats. An additional bounded probe completed 160 hands with arbitrary
  legal integer raise amounts.
- `python -m pokerbot check-gates` reports no promotion blockers. This clears
  the demonstrated defects; it is not a proof that every possible state is
  correct or that any strategy is strong.

## Development screen: 5,400 hands

`runs/parameter-screen-001`: five variants × four table sizes × three
independent sessions, each with twelve complete seat rotations. Candidate and
original play matched deals against caller/tight/aggressive/frozen-equity
mixtures. This uses **development deals only**, not held-out confirmation.

| Candidate change | 6 seats gain | 7 seats gain | 8 seats gain | 9 seats gain |
| --- | ---: | ---: | ---: | ---: |
| Raise margin .12 → .20 | +65.86 | +32.99 | -28.21 | +145.29 |
| Call margin .02 → .08 | -455.56 | -575.44 | -382.29 | -68.29 |
| Both margins raised | -434.26 | -581.59 | -239.76 | +70.52 |
| Raise margin .12 → .08 | +74.01 | +65.63 | -0.95 | +108.33 |

Units: paired **bb/100 improvement over the frozen original**. All descriptive
95% intervals include zero. With only three independent sessions per table
size and multiple candidates screened, these numbers do not establish gains.
Calling more conservatively looks unpromising in this pool; varying the raise
threshold merits fresh screening, but neither direction is a confirmed winner.
Do not launch a full confirmation solely because a few point estimates are high.

The screen took approximately 34.6 simulation seconds; the largest session p95
policy-decision latency was 0.984 ms on this Mac. This excludes adapter work
from the policy timer; total session time includes it. Completed-screen resume
was exercised. Summary and all paired trial values are tracked in
`research/results/2026-09-16-parameter-screen-001.json`; full replay logs remain
local under ignored `runs/`.

Run/restart with:

```
.venv/bin/python research/parameter_screen.py --out runs/parameter-screen-001 --trials 3 --rotations 12
```

## Earlier results retained

The original OpenSpiel-refereed run contained 324 screening hands and 1,944
learning-ablation hands. All learning-effect intervals included zero. These
remain historical diagnostics, not strength confirmation. Their recorded
summary is `research/results/2026-09-16-initial.json` and their logs still replay.
Total strategy-evaluation hands so far: **7,668**, excluding mechanics fixtures.

## Next bounded work

1. Add independently authored card-aware control opponents using the same
   observation boundary. Keep the existing confirmation mixes frozen, and
   define any harder benchmark separately.
2. Screen better equity precision, position/preflop logic and raise sizing on
   development deals; retain baseline code and sampler hashes. Use fresh
   development sessions to check that a candidate survives the initial screen.
3. Improve named-player modeling beyond one pooled fold rate. Compare exactly
   the same policy with no model, a known scripted model and a learned model;
   include sparse, deliberately wrong and changing histories.
4. Build a native candidate bridge and reproducible local checkpoint/config.
   NoRegrets supports only 2–6 seats upstream; dickreuter needs its demonstrated
   tie-equity fix and isolated local configuration before use. Research broader
   training and search candidates in parallel with the experiment backlog.
5. Freeze a promising candidate and execute the existing 6–9-seat confirmation
   protocol. No confirmation attempt has yet been allocated. On passage,
   preserve the result and start the next prespecified harder benchmark.

## Continuing task

Codex heartbeat `poker-strategy-research-and-testing` is active every 30 minutes
in the original conversation. There is no morning cutoff, and passing a stage
starts harder research. Inspect running jobs/locks before starting experiments;
never edit their source while they run. Save evidence and notify on meaningful
results or blockers. Local runs require the machine and app to remain running.
