# Position and range experiment v1

## Hypotheses and comparisons

Position-aware preflop decisions and public preflop-action conditioning might
improve the original showdown-equity heuristic. Test each separately and their
combination; increased sample count is controlled by a uniform 128-sample arm.
The fifth arm is the untouched frozen 32-sample original.

`research/range_screen.py` fixes eight independent sessions per table size and
pool, twelve complete seat rotations per session, 6–9 seats, two development
pools and five arms: **320 sessions / 28,800 hands**. Each arm uses the same
deals and seat rotation within a paired session. Seeds use the new namespace
`development-range-screen-v1`. Configuration, script/package hashes and runtime
versions are retained before the first session. Interrupted sessions restart;
completed sessions are reused only under identical code and configuration.

This is exploratory screening: report session-level mean differences and
unadjusted 95% intervals both against the frozen original and between matched
feature arms. Do not claim a benchmark pass from a development interval, pool
seat counts to hide a failure, or modify the candidate before the full fixed
sample completes. The separate confirmation protocol remains unchanged.

## Candidate implementation

- Preflop ordering uses existing-engine heads-up equity against uniform cards,
  with 512 deterministic samples per canonical two-card class. Suit relabelings
  share one score. This is an approximate ordering, not a preflop solution.
- Position changes opening/continuation thresholds. UTG and button are distinct;
  blinds do not receive button thresholds just because they act last preflop.
- Still-active opponents' preflop calls, checks and raises contribute smoothed
  action likelihoods. Earlier raises and position affect those likelihoods.
  All constants are uncalibrated hypothesis parameters, not population evidence.
- Sample complete joint opponent holdings and remaining board cards without
  replacement. Weight each sample by the product of the opponents' likelihoods,
  tempered by exponent .5, and normalize the weights. Joint proposals enforce
  card blockers without sequentially truncating independent ranges.
- Blend 75% of that weighted equity with 25% of the same proposals' uniform
  estimate. This is a conservative mixture of two estimates, not a claim of a
  calibrated posterior. Log weights prevent numerical underflow. Record the
  effective sample size of the conditioned component to detect concentrated
  weights; it is not the number of independent tournament observations.
- All-in opponents remain participants. The rules engine still supplies legal
  actions and payouts; the existing engine still supplies hand ranking.

## Validation and limits

Tests enumerate all 990 possible opponent holdings in a heads-up river fixture
and compare the sampler's weighted result with the finite sum. With no evidence
or zero conditioning, the estimator reproduces uniform sampling on identical
random draws. With both new features disabled, actions match the original
128-sample policy. Tests exercise legal full hands and exact replays at 2–9 seats,
all-in participation, canonical suit equivalence and irrelevant-profile isolation.

No inference from postflop actions, bet sizes, reconstructed historical legal
menus, folded players' hidden-card distribution or named-player tendencies is
implemented. The candidate does not simulate future betting or calculate
side-pot-specific action values. Observed preflop strength and final-board
strength need not move together. Stronger inferred preflop holdings can improve
hero's equity on a particular board; do not enforce a universal sign in tests.

Passing mechanics checks permits experiments, not promotion. A useful next
step must be chosen from measured results: likelihood calibration, richer public
features or explicit action-value search, rather than declaring hand-authored
probabilities to be accurate opponent knowledge.
