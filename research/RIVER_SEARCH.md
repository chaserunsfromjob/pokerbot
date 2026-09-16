# River action evaluation v1

## Hypothesis and frozen screen

Explicitly comparing terminal chip values of legal river moves may improve the
original equity-threshold strategy. `research/river_screen.py` compares the
frozen original with two river-only variants: one predicts that opponents use
the frozen equity policy; the other predicts that they always check/call.
The real development opponents remain unchanged, so neither model is an oracle.

The fixed screen uses 6, 7, 8 and 9 seats, two development pools, six independent
sessions per cell and eight full seat rotations per session: **144 sessions,
8,640 played hands**. Seeds use `development-river-screen-v1`. Candidate and
baseline get matched deals and rotations. Source/runtime/configuration are
recorded before execution; complete sessions can resume unchanged. Completed
reports retain their original resource measurements. No confirmation deals
are used and no promotion is made from these exploratory intervals.

## Decision method

Before the river, actions reproduce the frozen original, including its random
stream consumption. At a river decision:

1. Obtain the original policy's action. Form a small menu containing legal fold,
   check/call, minimum raise, half-pot, pot and all-in targets, deduplicated and
   clamped to legal bounds. Include the original action even if its rounding
   differs from the menu.
2. Sample 16 joint hypothetical assignments to all other seats, excluding own
   cards and the five public board cards. Folded seats receive hypothetical
   cards but remain ineligible for any payout. All-in players stay in the game.
3. Create a new PokerKit-backed hand with those cards and the public starting
   stacks. Replay every public action, checking actor, street, amount and the
   entire reconstructed observation. Reject an inconsistency; do not silently
   repair the history or substitute a move.
4. Clone that hypothetical state for each root action. Use the selected fixed
   response model for opponents and the original policy for any later hero
   decisions. Every continuation receives only its own sanitized observation.
   Responses are stateless. No action is selected using a world's omniscient
   hand strength, and no live simulator state is passed into the search.
5. Let PokerKit complete betting and settle every pot. Add hero's already-sunk
   contribution to its terminal net payoff to express value relative to the
   current remaining stack, in big blinds. Compare root actions on the same
   sampled worlds and response random streams.
6. Override the original action only if its estimated improvement minus 1.96
   paired standard errors exceeds .25bb. This is a noise penalty for action
   selection, **not** a confidence certificate after choosing among moves and
   not the tournament benchmark's statistical test. Preserve the baseline on
   ties or insufficient estimated gain.

The estimator does not infer opponent ranges from previous bets and does not
learn player identities. Predicted actions and cards can therefore be wrong.
The current hero continuation is a fixed heuristic; the real policy can search
again at a later river decision. That approximation must remain explicit.
This is limited policy evaluation, not CFR, a best-response proof or equilibrium
search. Do not transfer its result to earlier streets without separate work.

## Validation

Tests verify reconstruction and certain-winner values across 2–9 players,
check/call/fold responses, exact future chip cost, a short all-in winner of the
main pot with hero winning a side pot, folded best-hand ineligibility, split-pot
ties, short-all-in reopening restrictions and mutation isolation between moves.
Changing actual opponents' cards while preserving the public observation leaves
the action and diagnostics unchanged for the same policy RNG. Earlier-street
actions exactly match the original policy.

Recorded diagnostics include root actions, sampled worlds, predicted values,
paired standard errors and whether the action changed. Predicted improvement is
not realized profit. The screen separately records played-hand returns and
session-level uncertainty. Counterfactual branch simulations are reported apart
from played hands; they do not multiply the statistical sample size.

## Follow-up research

Two uncertainties must be addressed separately: hidden holdings and opponents'
response strategies. [Bayes' Bluff](https://arxiv.org/abs/1207.1411) provides a
primary research starting point for maintaining uncertainty over opponent
strategies and responding to that distribution. Our current single-response
rollouts do not implement that method. A concrete next test would compare fixed,
known-control and learned response mixtures using the same evaluator, with
independent trials and deliberately wrong models.

[AIVAT](https://poker.cs.ualberta.ca/publications/aaai18-burch-aivat.pdf) studies
variance reduction in evaluation using value estimates and known strategy
probabilities. This is promising for our noisy comparisons, but our current
interface emits a sampled action rather than an exact action distribution.
Logging a random seed does not by itself supply those probabilities. A pilot
must validate mean-zero corrections independently and retain raw results;
estimated probabilities cannot simply inherit the paper's unbiasedness claim.
Any later adjusted estimator needs its own prespecified protocol. The existing
raw-return confirmation gate remains unchanged.
