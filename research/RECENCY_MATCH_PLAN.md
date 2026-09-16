# Fixed development screen after the recency prediction pilot

Specified before running `recency-screen-001`. The prediction pilot passed its
eight fixed comparisons, but that result does not establish poker strength.

- Fresh namespace: `development-recency-screen-v1`; no confirmation seeds.
- Four arms: untouched original, named-response river search with prior only,
  the identical search with raw learned counts, and with a 64-opportunity
  half-life. All other river parameters stay fixed at their existing defaults.
- Two development pools: caller/tight/aggressive and caller/tight/tight.
  These are stationary synthetic controls, not strong or human-like opponents.
- Six independent trials at each of 6, 7, 8 and 9 seats; eight complete seat
  rotations per trial. All arms receive matched deals and independent profile
  stores. Total: 192 sessions and 11,520 played hands.
- Compare discounted-minus-raw and discounted-minus-prior returns. Preserve
  raw-minus-prior and search-minus-original comparisons as context. Report
  unadjusted session-level paired intervals as exploratory, not promotion.
- Score predictions before learning from each scored hand, replaying the exact
  raw/discounted update schedule. Different arms encounter different contexts;
  pooled prediction scores are not causal strength comparisons.
- Save sessions, privileged replay logs, public opportunities, source/runtime
  hashes, latency and memory. Resume only with unchanged source/configuration.
- Finish the fixed sample before interpreting returns. A positive selected
  interval does not pass the held-out strength benchmark. Any next experiment
  receives a new namespace and frozen plan.

The synthetic pilot tests behavior changes; this played screen tests stationary
returns. Robust chip returns under changing opponents remain a separate future
experiment regardless of either result. Turn search is a separate intervention.
