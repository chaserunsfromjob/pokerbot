# Recency prediction pilot — September 16, 2026

The fixed pilot in `RESPONSE_RECENCY_PLAN.md` passed all eight primary
comparisons. This is a synthetic prediction milestone, not a poker-strength
promotion. The failed raw-count stress results remain recorded unchanged.

## Implementation

`ResponseProfiles(half_life=64)` exponentially discounts a named player's prior
effective counts once per new observed action by that same player. Evidence
across that player's legal contexts ages together; other players' actions do
not age it. Raw public rows and model settings remain in SQLite. Reopening
reconstructs identical fractional counts; duplicate hands do not age them.
Changing settings for an existing session is rejected. The default remains
undiscounted, and old raw-count databases reopen with raw semantics.

River search accepts `response_half_life` only for its named response model.
Policies still receive copied public profiles after completed hands. Neither
hidden cards nor hypothetical rollouts update the profiles.

## Fixed evaluation

Twenty independent streams in each of six scenarios generated **122,880 scored
opportunities**, with the same actions supplied to raw and discounted learners.
Predictions were scored before each observation. Each mistaken-history stream
also began with 800 deliberately wrong observations; those injected rows are
separate from scored opportunities. No played poker hands were generated.

| Scenario and scoring window | Prior error | Raw error | Discounted error |
| --- | ---: | ---: | ---: |
| Caller, whole stream | .46500 | .00384 | .00689 |
| Tight, whole stream | .20580 | .00325 | .00593 |
| Aggressive, whole stream | .24500 | .00366 | .00645 |
| Unfamiliar, whole stream | .54500 | .00732 | .01210 |
| Changing, first 128 observations after switch | .46500 | .69464 | .35638 |
| Mistaken history, whole stream | .46500 | .87330 | .09210 |

Error is mean excess Brier score against the known synthetic action
distribution; lower is better. The .05 family error allowance was divided by
eight for the paired stream-level intervals.

- After a behavior switch, discounted-minus-prior was **-.10862**, adjusted
  interval **[-.13061, -.08663]**; discounted-minus-raw was **-.33826**,
  **[-.35701, -.31951]**. Both upper bounds were below zero.
- With mistaken history, differences were **-.37290** versus prior and
  **-.78120** versus raw. Caller and mistaken-history streams are deterministic
  under their specified processes, so repeated seeds yield zero between-stream
  variance. The resulting degenerate intervals do not quantify uncertainty
  about unfamiliar real behavior.
- Stationary/unfamiliar error increased by **.00269–.00478** versus raw counts.
  The largest adjusted upper bound was **.00561**, below the predeclared .02
  tolerance. Passing noninferiority means accepting that bounded degradation;
  it does not mean forgetting is equally accurate on stable players.

Sparse-history checkpoints remain explicit. After eight and 32 new observations
following the wrong history, discounted error was **1.54895** and **.94342**,
both worse than the prior's .46500. This pilot passes an average recovery
criterion, not instant robustness or safety on every decision. All checkpoints
and paired values are in the result JSON.

## Reproduction and limits

```
.venv/bin/python research/response_recency.py --out runs/response-recency-001
.venv/bin/python research/recency_screen.py --out runs/recency-screen-001
```

The prediction run used approximately **2.96 seconds** and **120.84 MiB** peak
RSS on this Mac. Completed-run resume preserved its report byte-for-byte;
source, scenario-helper and prespecified-plan hashes matched. Its tracked
summary is `results/2026-09-16-response-recency-001.json`; raw per-stream actions
remain in the ignored run directory with hashes in the report.

All scenarios use one legal context and categorical controls. The played
screen is separately specified in `RECENCY_MATCH_PLAN.md`; prediction passage
does not waive its chip-return comparison or the held-out strength benchmark.
Future work must test behavior changes across poker contexts and chip returns
under mistaken or changing profiles before claiming robust exploitation.

## Separate played result: do not promote fixed forgetting

The planned `recency-screen-001` completed all 192 sessions / 11,520 hands.
Discounted-minus-prior chip-return intervals all included zero. In the passive
pool, discounted-minus-raw means at 6–9 seats were -93.28, -128.99, -86.91 and
-216.26 bb/100. The eight- and nine-seat unadjusted intervals were entirely
negative; multiple comparisons and six trials per cell limit the inference.
These results do not support replacing raw learning with fixed forgetting.

On these stationary controls, raw prediction error was also lower than
discounted: mixed pool .03467 versus .04219; passive .02061 versus .02595.
The synthetic recovery milestone and the played weakness coexist. Preserve
both. Full paired returns, runtime and limitations are recorded in
`results/2026-09-16-recency-screen-001.json` and `PROGRESS.md`.
