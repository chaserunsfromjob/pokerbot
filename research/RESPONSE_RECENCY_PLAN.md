# Next response-model experiment: recency weighting

Status: specified before implementation; no result or promotion claimed.

The nondecaying model failed the mistaken-history and immediate behavior-change
diagnostics recorded in `RESPONSE_LEARNING.md`. Test whether exponential
discounting of each named player's older action observations repairs that
weakness without materially degrading stationary prediction.

## Fixed first pilot

- Compare prior-only, existing raw counts and counts with a **64-opportunity
  half-life**. Discount per named player's observed opportunity, not elapsed
  wall time or another player's actions. Keep legal contexts, prior strengths
  and exact-street/backoff structure identical.
- Keep raw public observations as the persistent source; derived effective
  counts may be fractional. Persist model configuration and test reconstruction,
  duplicate-hand idempotence and independent-session resets under discounting.
- Use fresh seed namespace `response-recency-v1`, 20 independent streams per
  scenario, 1,024 generated opportunities per stream. Preserve the six previous
  scenario definitions, including the 256-opportunity switch and 800 deliberately
  wrong initial observations. Retain checkpoints after 8 and 32 observations.
- Feed identical generated actions to each estimator. Score before observing
  each action. Evaluate stream-level mean excess Brier error, plus the first
  128 opportunities after a behavior switch. These are synthetic prediction
  measurements, never additional played poker hands.

## Judge the pilot

For mistaken history and the post-switch window, require the discounted
estimator's mean error to be lower than both prior-only and raw counts, with
the adjusted upper interval for discounted-minus-reference below zero. For
stationary and unfamiliar streams, require the adjusted upper interval for
discounted-minus-raw error to remain below the absolute excess-Brier regression
tolerance of .02. Report sparse checkpoints separately.

Apply a Bonferroni adjustment across all eight primary comparisons: four
improvement comparisons (two stress cases against two references) and four
stationary/unfamiliar noninferiority comparisons. Complete the fixed sample
before judging. A failed cell remains failed; do not replace seeds or tune the
half-life on these final pilot streams. Any revision receives a new experiment
and fresh streams; this pilot does not allocate the poker strength confirmation
ledger or certify performance against people.

Only after the model pilot, compare the same river policy with raw and discounted
learning in fresh played matches. Positive prediction evidence does not waive
the separate learned-minus-off chip-return test. Keep turn-search expansion as
another independent change so its effect remains identifiable.
