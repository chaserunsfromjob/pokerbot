# Research checkpoint — September 16, 2026, named response learning

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

Three card-aware development opponents now react to engine-calculated equity,
preflop position and action history. They have distinct tight/loose/pressure
rules and preserve the sanitized observation boundary. The existing frozen
confirmation mixes are unchanged. The controls are not known strong bots and
share the equity evaluator with the original candidate.

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

- **127 root tests passed; no expected failures in the root suite.**
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
Those runs plus the parameter screen account for 7,668 historical evaluation
hands, excluding mechanics fixtures.

## Fresh precision and card-aware screen: 25,920 hands

`runs/precision-screen-001`: original plus five candidate variants, two
opponent pools, four table sizes, six independent sessions per cell and twelve
seat rotations per session. All seeds are in a new development namespace;
held-out confirmation deals were not used.

No candidate had a positive lower confidence bound in any development cell.
Increasing equity samples from 32 to 128 or 256 did not produce consistent
gains; removing the calling margin or changing raise thresholds/sizing also
remained unproven. The 256-sample variant had a negative descriptive interval
in the scripted eight-seat cell. These are unadjusted development intervals
across multiple variants, so that isolated result is not a final hypothesis test.

Paired mean gains against the new card-aware pool (bb/100):

| Variant | 6 seats | 7 seats | 8 seats | 9 seats |
| --- | ---: | ---: | ---: | ---: |
| 128 samples | -18.13 | -115.81 | +58.34 | +36.70 |
| 256 samples | +39.21 | -102.68 | +69.23 | +4.28 |
| 128 samples, no call margin | +1.71 | -112.37 | +58.40 | -9.04 |
| 128 samples, raise margin .20 | -37.04 | -61.80 | +69.90 | +78.08 |
| 128 samples, pot-sized bets | +59.99 | -93.94 | +92.85 | +84.83 |

Every interval in this card-aware table includes zero. No policy was promoted.
The run used approximately **381.3 simulation seconds**, **117 MiB peak RSS**,
and a maximum per-session p95 policy latency of **6.21 ms**. Results, all paired
trial values and provenance are recorded in
`research/results/2026-09-16-precision-screen-001.json`.
Total strategy-evaluation hands: **33,588**, excluding mechanics and toy CFR.

## Existing-bot component: dickreuter equity

Pinned source probe reproduced and repaired the split-pot error. A separate
fixture exposed another bug: with board `2c 2d 2h 3c 3d`, the native evaluator
lets `2s Ac` beat `3h 3s`, wrongly prioritizing the kicker over quads rank.
The tie-only patch does not fix it.

The second patch delegates ranking to PokerKit while preserving upstream
category names. The two-patch component passes eight targeted Monte Carlo
fixtures and 400 random ranking comparisons against `treys` at 2–9 seats.
Both patch files apply in sequence to clean pinned source and reproduce the
tested hash. See `research/patches/README.md` and
`research/results/2026-09-16-dickreuter-equity.json`.

This is a checked component, not an integrated or strength-tested bot. Native
strategy config, conditional ranges, action translation, timeouts and external
consumers of the changed score representation still require validation.

## Training feasibility: toy CFR

`research/train_kuhn.py` ran OpenSpiel external-sampling MCCFR on **two-player,
three-card Kuhn poker**, 20,000 iterations each for seeds 73, 89 and 113.
Exact NashConv decreased from 0.91667 to **0.01385, 0.01897 and 0.00415**.
All three met the predeclared toy threshold of .05. Exporting/reloading each
12-information-set average policy preserved its exact evaluation. Total
training time was about 3.7 seconds.

Policy files are local under `runs/kuhn-cfr-001`; they do not include solver
regrets and are not resumable training states. Recorded results are in
`research/results/2026-09-16-kuhn-cfr-001.json`. This validates training and
policy-export plumbing only. It is not no-limit hold'em, multiway evidence,
or a pass of the project's strength benchmark.

## Position and preflop-action ranges: 28,800 hands

`runs/range-screen-001` completed all 320 sessions: five arms, two development
pools, four table sizes, eight independent sessions per cell, and twelve full
seat rotations per session. The arms isolate position-aware preflop rules,
preflop-action range weighting, both, a uniform 128-sample reference and the
untouched original 32-sample baseline. The new seed namespace is independent of
earlier development screens and does not consume confirmation deals.

No candidate had a positive lower interval against the frozen original in any
cell. Position-only and combined rules had negative descriptive intervals in
the scripted seven-seat cell. Against the card-aware pool, gains versus the
original were:

| Variant | 6 seats | 7 seats | 8 seats | 9 seats |
| --- | ---: | ---: | ---: | ---: |
| Uniform 128 | -81.03 | -21.43 | +91.22 | -70.34 |
| Position only | +131.19 | -70.02 | +75.42 | +92.73 |
| Ranges only | -9.06 | +29.87 | +55.60 | -66.36 |
| Position and ranges | +142.26 | -71.22 | +51.93 | +98.72 |

Units are paired bb/100. Every interval in that table includes zero. Matched
128-sample comparisons did show positive descriptive intervals for position
versus uniform at six seats (+212.22, interval [31.96, 392.48]) and nine seats
(+163.07, [91.64, 234.49]) in the card-aware pool. These are selected,
unadjusted exploratory comparisons; they do not establish broad improvement or
pass the project's benchmark. The ranges-only effect remains inconclusive at
every size and pool.

The estimator uses only public preflop actions and deterministic engine-derived
hand strength ordering. It samples all still-active opponents jointly, including
all-ins, and enforces card blockers. It does not yet infer from postflop actions,
learn named-player tendencies, model folded-card distributions or simulate
future betting. See `research/RANGE_EXPERIMENT.md` for the exact method and limits.

Weighted samples were usually usable but occasionally concentrated: mean
effective sample sizes were 101.09/128 in the scripted pool and 119.64/128 in the
card-aware pool. Respectively 62/7,514 and 18/8,187 range decisions fell below 32;
the minimum was 1.23. This is a sampling limitation to investigate before relying
on individual range estimates, especially in large pots.

The run consumed **383.5 simulation seconds**, **118.38 MiB peak RSS**, with
maximum per-session p95 policy latency **3.82 ms** (across all acting policies,
excluding host adapter work). Exact replay verified an additional 108 completed
nine-seat combined-policy hands. Completed-session resume reproduced every
recorded outcome, comparison and manifest; the resumed process's RSS is a
separate invocation measurement. The tracked report preserves the original
complete run's resource measurement.

All package source hashes match the completed experiment. Frozen original and
equity sampler hashes remain unchanged. Results and paired trial values are in
`research/results/2026-09-16-range-screen-001.json`. Cumulative strategy-evaluation
hands are now **62,388**, excluding mechanics tests and toy CFR. No policy was
promoted and no held-out confirmation attempt was allocated.

## Broader trained-policy research

Source review added another Deep CFR implementation at pinned commit
`e75405928bdcf8f80dc35b463f706b8ef45d1b3b`. Its hold'em encoder is limited to six
seats, its documented models are not included in a fresh checkout, and its
reported initial hold'em training has no demonstrated strength. It remains a
training/component candidate, not an installed opponent. Dependencies and model
execution were not attempted. See `research/TRAINED_CANDIDATES_REVIEW.md` for
primary sources, evidence, PokerRL/Deep CFR and RLCard compatibility findings.

## River action evaluation: 8,640 hands

`pokerbot/river_search.py` now evaluates a small legal river move menu. It samples
16 hypothetical joint hidden-card assignments from public inputs, reconstructs
the betting history, and lets PokerKit settle each continuation, preserving
actual participants and side pots. It never receives the live simulator state.
Opponents use a guessed fixed response policy, and hero uses the original policy
after the root move. Before the river it exactly preserves the original policy.

The two development variants assume either the frozen equity response or an
always-calling response. Both retain uniform hidden cards. A paired-standard-
error penalty makes action changes conservative; it is not a statistical
strength guarantee. Seventeen search tests cover exact chip values, folded-hand
eligibility, unequal-stack side pots, ties, short all-ins, hidden-card invariance,
root mutation isolation and action selection in certain-value situations.

`runs/river-screen-001` completed **144 sessions / 8,640 played hands**, across
two pools, 6–9 seats, six independent trials per cell and eight seat rotations.
The seed namespace is new and no confirmation deals were consumed. The complete
result is inconclusive. Gains against the original in the card-aware pool:

| Response assumption | 6 seats | 7 seats | 8 seats | 9 seats |
| --- | ---: | ---: | ---: | ---: |
| Frozen equity policy | +23.08 | +23.44 | -3.79 | +28.24 |
| Always calls | -13.72 | -5.36 | +5.96 | +107.51 |

Units: paired bb/100; every interval includes zero. No positive lower interval
was obtained in the scripted pool either. Several scripted cells have zero
sampled differences because river changes had no observed effect; their
degenerate [0, 0] sample intervals do not prove population-level equivalence.

The equity-response variant searched 312 decisions and changed 25; the
calling-response variant searched 295 and changed 60. The **46,608 hypothetical
root-action branches are computation, not additional independent played hands**.
Public-event-only coverage analysis of the original-policy logs shows hero had
a river decision in only 2/384 scripted eight-seat hands and 2/432 scripted
nine-seat hands. In the card-aware pool it was 50/288, 56/336, 44/384 and 55/432.
This confines the intervention's impact and motivates work on earlier decisions,
without treating these small samples as precise strength estimates.

Runtime: **207.6 simulation seconds**, **118.38 MiB peak RSS**. Maximum observed
decision latency was **595.24 ms**. Maximum per-session p95 across *all* policies
was 2.98 ms, which hides rare expensive search decisions; the maximum is therefore
also reported. Exact replay verified another 72 nine-seat hands. Completed-run
resume preserved the report byte-for-byte, including original resource records.
All experiment package hashes and frozen baseline hashes remain unchanged.

Results: `research/results/2026-09-16-river-screen-001.json`; coverage and input
hashes: `research/results/2026-09-16-river-coverage.json`. Reproduce coverage with
`research/river_coverage.py`. Cumulative played strategy-evaluation hands are
**71,028**, excluding mechanics, toy CFR and internal hypothetical branches.
No strategy was promoted; no held-out confirmation attempt has been allocated.

See `research/RIVER_SEARCH.md` for assumptions and follow-up primary research on
Bayesian response models and AIVAT variance reduction. Neither paper's method
is implemented by this prototype. Exact policy distributions and independent
unbiasedness checks would be needed before adopting a new evaluation estimator;
the raw-return benchmark remains fixed.

## Named response learning: 7,680 hands and a failed robustness check

`response_profiles.py` now stores named action observations separately from
policies, by street, facing-bet status and legal raise availability. Profiles
persist within a session, survive seat rotation and reset across independent
trials. Completed-hand records are idempotent and replayable from SQLite.
`responses.py` estimates smoothed fold/check-call/raise distributions with
per-player cross-street backoff. The river evaluator uses a copied snapshot;
counterfactual branches cannot update the learned state. No opponent cards,
private policies or actual simulator state enter learned profiles.

Tests verify legal-opportunity denominators, independent copies, persistence,
trial resets, stationary calibration and exact oracle agreement with caller,
tight and aggressive controls. The separate known-policy oracle is synthetic
diagnostic input only; it is not a learned fact about classmates.

`runs/response-screen-001` completed **128 sessions / 7,680 played hands**,
four arms (original, prior-response search, oracle-response search, learned-response
search), two newly specified control pools and all 6–9-seat sizes. Each cell
uses four independent trials and eight full seat rotations. All use fresh
development deals; no confirmation data was consumed.

Probability error against the known control distributions improved substantially:

| Pool | Prior mean excess Brier | Learned mean excess Brier |
| --- | ---: | ---: |
| Mixed caller/tight/aggressive | .27890 | .03648 |
| Passive caller/tight/tight | .16629 | .02170 |

These host-only scores use predictions made before learning from the scored
hand. They measure probability error on each arm's encountered contexts, not
profit or a causal strength effect. The oracle's probability error is zero by
construction, and must not be counted as a learned result.

Additional chip-return gains from learning versus the identical prior-response
policy remain inconclusive at every size and pool. In the passive pool, means
were +161.99, +63.34, -79.59 and +94.53 bb/100 at 6–9 seats, respectively; all
intervals include zero. Some comparisons of search against the original are
promising: learned search versus original at six seats was +665.29 [153.43,
1177.16] and at seven seats +861.24 [20.08, 1702.40]. Prior-only search also had
positive descriptive intervals in passive six- and eight-seat cells. These
are unadjusted exploratory results on only four sessions per cell, restricted
controls and selected comparisons; they do not establish learning's contribution
or pass the held-out benchmark. Zero sampled differences in some mixed cells
do not prove equivalence.

The three candidate arms searched 970 real decisions, changed 222 actions and
simulated 76,240 hypothetical root-action branches. Branches are not independent
played hands. Runtime was **324.1 simulation seconds**, peak RSS **120.06 MiB**,
and maximum decision latency **662.29 ms**. Replay verified another 72 nine-seat
learned-policy hands; resume preserved the full report byte-for-byte. Package
and original baseline hashes match the experiment. Root suite: 127 pass; vendor:
53 pass and two existing expected failures.

The separate synthetic stress study generated **18,432 action opportunities**
across six scenarios and three seeds; these are not poker hands. Stationary and
unfamiliar action frequencies were learned well. However, immediately after a
tight-to-calling switch, learned excess Brier was .67067 versus prior .46500;
with deliberately wrong initial history, whole-stream error was .87330 versus
prior .46500. **Robust adaptation failed.** The model has no forgetting and can
retain misleading evidence. Preserve those failures; do not present stationary
calibration as a robust exploitative strategy.

Results are in `research/results/2026-09-16-response-screen-001.json` and
`research/results/2026-09-16-response-stress.json`. Method and limitations:
`research/RESPONSE_LEARNING.md`. Cumulative played strategy-evaluation hands:
**78,708**, excluding synthetic opportunities, hypothetical branches, mechanics
tests and toy CFR. No strategy is promoted and no confirmation attempt allocated.

## Next bounded work

1. Repair stale-history sensitivity with per-player recency weighting. Follow
   the already specified `research/RESPONSE_RECENCY_PLAN.md`: a 64-opportunity
   half-life, fresh 20-seed streams, paired adjusted improvement/noninferiority
   checks, and explicit stationary/sparse/changing/mistaken cells. Then test
   raw versus discounted learning in fresh played matches. Prediction success
   must remain separate from chip-return strength.
2. Extend the tested reconstruction/rollout boundary to turn decisions with a
   prespecified action/world budget, then evaluate earlier-decision coverage and
   paired returns. Future community cards must be sampled, never copied from
   a live deck. Preserve public-only continuations and side-pot fixtures.
3. Investigate concentrated range weights and replicate position effects on fresh
   development sessions with more independent trials. Maintain scripted-pool
   regression checks. Consider evaluation variance reduction only after its
   prerequisites and zero-mean corrections are independently validated.
4. Build one native policy/component bridge or a bounded hold'em training pilot
   with real saved artifacts and independent seeds. NoRegrets is limited to
   2–6 seats upstream; dickreuter needs local strategy config and a policy bridge;
   the newly reviewed Deep CFR project needs artifacts and six-seat compatibility
   work. Do not disguise missing models with randomly initialized networks.
5. Freeze a promising candidate and execute the existing 6–9-seat confirmation
   protocol. On passage, preserve the result and specify the next harder stage
   before looking at its results.

## Continuing task

Codex heartbeat `poker-strategy-research-and-testing` is active every 30 minutes
in the original conversation. There is no morning cutoff, and passing a stage
starts harder research. Inspect running jobs/locks before starting experiments;
never edit their source while they run. Save evidence and notify on meaningful
results or blockers. Local runs require the machine and app to remain running.
