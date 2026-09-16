# Named response learning v1

## Model and information boundary

`ResponseProfiles` stores completed-hand public observations in a separate
SQLite table keyed by session and hand. Each row contains player name, street,
whether a bet was faced, whether raising was legal, and fold/passive/raise.
Cards, private policies, future events and simulator state are not stored.
Player identity survives seat rotation. Repeated hand IDs are idempotent;
different session keys isolate independent trials. Returned snapshots are copies.

For a decision context, the model estimates a three-category distribution.
Starting weights are .35 fold when facing a bet and .20 raise when legal;
remaining mass is check/call. These are explicit initial assumptions, not
measured human frequencies. The same player's other streets, under matching
facing-bet and raise-availability flags, are smoothed with 12 prior observations.
That estimate contributes eight pseudo-observations to the exact street cell.
The direct cell is excluded from the backoff counts, avoiding double use.

These are smoothed frequency estimates, not a full posterior over poker
strategies. No bet-size buckets, card-dependent responses or forgetting are
implemented. Conditional raises are uniform over the existing small legal menu.
No observations from one named player are pooled into another player's model.

River search takes an immutable snapshot at each real decision. Its hypothetical
branches never update the learned model. Learning happens after a completed
real simulated hand; current-hand actions remain public history, but do not yet
change the stored frequencies mid-hand. Earlier-street hero decisions remain the
frozen original. Uniform hidden-card assumptions remain unchanged.

## Separate prior, oracle and learned arms

`research/response_screen.py` uses the exact same named-response river policy in
three modes: empty-history prior, known scripted-control policy, and observed
named histories. The fourth arm is the frozen original with no river search.
The oracle provides only the identities of synthetic caller/tight/aggressive
policies. Their action probabilities match the control implementation exactly,
including when raising is unavailable. This is not information available about
classmates, and it does not reveal sampled or actual cards.

The fixed screen uses two newly specified control pools, 6–9 seats, four
independent sessions per cell and eight complete rotations: **128 sessions /
7,680 played hands**. Every arm gets matched deals and seats in a new development
seed namespace. Models start empty in each trial and persist within that trial.
Report learned-minus-prior separately from learned-minus-original. Oracle results
diagnose response-model error; they are not a guaranteed upper bound on strength.

Prediction diagnostics score probabilities before updating from the scored hand.
The synthetic opponents' known probabilities are used by the host evaluator
only. Mean excess Brier score is the sum of squared probability errors against
that known distribution, averaged over observed opponent contexts. It omits the
irreducible outcome-noise component. Lower is better. Context distributions may
differ across policy arms, so these scores are diagnostic, not a randomized
causal estimate of poker profit. Real chip returns remain the strength measure.

## Stress findings

`research/response_stress.py` generates 1,024 categorical action opportunities
per scenario and seed, with three seeds. These **18,432 opportunities are not
played poker hands**. Cases cover stationary caller/tight/aggressive behavior,
an unfamiliar distribution, a switch from tight to calling after 256 observations,
and 800 deliberately wrong initial fold observations before a calling opponent.
Checkpoints after 8 and 32 observations expose sparse-data behavior.

| Scenario | Prior mean excess Brier | Learned mean excess Brier |
| --- | ---: | ---: |
| Caller | .46500 | .00384 |
| Tight | .20580 | .00292 |
| Aggressive | .24500 | .00391 |
| Unfamiliar categorical distribution | .54500 | .00436 |
| Changing behavior | .40020 | .19350 |
| Deliberately mistaken history | .46500 | .87330 |

The changing model's average conceals a bad transition: during the first 128
opportunities after the switch, learned error is .67067 versus prior .46500.
The mistaken-history case is worse than prior overall. **Robust adaptation has
failed this diagnostic.** Nondecaying evidence can remain misleading; stationary
calibration does not establish robust exploitation or a poker win-rate gain.

Next compare raw counts with explicitly specified recency weighting on fresh
streams, retaining stationary, sparse, unfamiliar, changing and mistaken-history
cells. Fix that demonstrated weakness before claiming robust opponent learning.
Results and source hashes are retained in
`research/results/2026-09-16-response-stress.json`.
