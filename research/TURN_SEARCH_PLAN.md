# Next experiment: earlier fixed-policy rollouts

Status: specified September 16, 2026; not implemented or evaluated. Keep the
current recency screen frozen while it runs. This intervention is independent
of the opponent-memory pilot and does not select parameters from its results.

## Research rationale and limits

The existing river screen found few opportunities to change decisions in some
tables. Extending evaluation to the turn could affect more hands. That is our
testable engineering hypothesis, not evidence of stronger play.

[Brown, Sandholm and Amos (2018)](https://proceedings.neurips.cc/paper_files/paper/2018/hash/34306d99c63613fad5b2a140398c0420-Abstract.html)
explain why a single state-value estimate is insufficient for general
imperfect-information depth-limited solving; their method allows multiple
opponent continuation strategies. Its demonstrated poker setting is heads-up.
[Brown and Sandholm (2019)](https://doi.org/10.1126/science.aay2400)
describe six-player Pluribus combining a trained blueprint with real-time search
and a restricted bet menu. Neither result validates our heuristics or nine-seat
play. Our next implementation remains terminal rollouts under specified
continuation policies, with no equilibrium or safe-exploitation guarantee.

## Concrete implementation boundary

1. Preserve `RiverPolicy` behavior and its completed results. Add a separately
   named turn-plus-river policy. Preflop and flop must exactly reproduce the
   frozen original, including random-number consumption.
2. At the turn, accept only the existing sanitized observation. Jointly sample
   two hypothetical cards for every other seat, including folded seats, then
   randomly complete the unseen deck without replacement. Preserve the four
   public board cards and hero's cards. Never copy the host's future river.
   The existing river reconstruction's ascending unused-card suffix is harmless
   on a completed board but must not become the turn's future-card sampler.
3. Replay public actions through PokerKit; compare the complete reconstructed
   observation. Retain actual seats, starting stacks, contributions, folded and
   all-in states, legal actions, and side-pot eligibility.
4. Compare the legal deduplicated menu plus the actual original action over
   16 paired worlds. Each action sees the same sampled future deck and response
   seed. Clone worlds between actions. Use the frozen equity policy for all
   later hero decisions and opponent responses in this first experiment.
5. Keep the current 1.96 paired-standard-error penalty and .25bb action-change
   threshold. These are decision heuristics, not statistical strength gates.
   Do not recursively invoke search inside hypothetical continuations. Real
   later decisions may search again; document that model mismatch.
6. Record turn and river coverage, action changes, sampled worlds, branches,
   predicted gains and decision-time quantiles/max separately from played hands.

## Required correctness checks before matches

- Reconstruct turn states across 2–9 seats, including unequal stacks, short
  all-ins, folded participants and side pots.
- Sample only legal, nonduplicate cards. Deterministic RNG seeds reproduce
  complete hypothetical decks; different seeds can produce different rivers.
- Identical public observations and policy RNG must yield identical decisions
  when actual hidden holdings or the host's future deck differ.
- For fixed hypothetical decks and actions, compare rollout payouts with
  independently exercised PokerKit hands; retain existing independent payout
  and ranking gates. Check sunk-cost accounting and forced all-in runouts.
- Mutating one candidate branch cannot affect another. Earlier-street behavior
  and the existing river-only policy remain unchanged.

## Fixed first development screen

Fresh namespace `development-turn-screen-v1`; 6–9 seats; six independent
sessions per size and pool; eight full seat rotations. Three arms: original,
existing river-only equity-response search, and turn-plus-river equity-response
search. Two existing development pools: caller/tight/aggressive/equity and
card_tight/card_loose/card_pressure/equity. This is 144 sessions / 8,640 hands.

Primary exploratory contrast: turn-plus-river minus river-only. Also report
each against original. Keep opponent learning off to isolate the added turn
intervention. Finish the sample before judging session-level paired intervals.
Greater decision coverage alone does not constitute improvement; inconclusive
returns remain inconclusive. Record actual runtime and memory, not a laptop
compute ceiling. No confirmation data or promotion is involved.

If response-model sensitivity remains the bottleneck, a subsequent independent
experiment can compare several continuation policies or model uncertainty.
That requires its own frozen specification; it is not implemented by this plan.

## Coverage measured before implementation

`street_coverage.py` inspected public events from the already completed
`river-screen-001` original arms, without reading cards or treating this audit
as new played hands. Among 1,440 scripted-pool hands, hero had river decisions
in 46 and turn-or-river decisions in 94. In 1,440 card-aware hands the counts
were 205 and 240. Turn adds 48 and 35 potentially affected hands, respectively.
Thus coverage expands, but its absolute increase is modest: about 3.33 and
2.43 percentage points. Merely moving search one street earlier may still have
limited impact. Decisions counted here can have trivial legal menus, so these
counts are opportunity bounds, not guaranteed action changes or strength gains.

Input log hashes and per-seat counts are preserved in
`results/2026-09-16-street-coverage.json`. The planned experiment above is
unchanged; earlier-street/preflop strategies remain separate research avenues.
