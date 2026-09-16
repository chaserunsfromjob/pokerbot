# Research checkpoint — September 16, 2026

## Current state

New `pokerbot/` research package uses OpenSpiel 2.0.2 with a 52-card deck and
exact integer no-limit action amounts for 2–9 seats. It includes:

- Frozen public observations, legal-action bounds and a shared decision API.
- Uniform-hidden-card Monte Carlo pot share through OpenSpiel's evaluator;
  original configurable pot-odds policy, half-pot sizing, optional bounded
  fold-profile adjustment; random/caller/tight/aggressive controls.
- Reproducible independent sessions, seat rotation, fixed stacks per hand,
  mixed opponents, source/dependency hashes, decision diagnostics and latency.
- Separate SQLite public observations with stable names, idempotent completed
  hands, restart persistence and session isolation.
- Saved privileged simulator decks/actions and exact replay. Policies never
  receive those logs; this is API isolation, not a malicious-code sandbox.
- Session-level confidence intervals, a frozen paired confirmation protocol,
  resumable completed trials, repeated-confirmation alpha budget and locks.
- Tested generic local-process candidate interface; upstream native bridges
  remain explicitly unavailable.

## Demonstrated blocker

OpenSpiel 2.0.2 incorrectly reopens betting in this three-player fixture:
stacks `[10000, 250, 10000]`, blinds 50/100; button raises to 200, SB calls,
BB raises all-in to 250. The button should only call or fold, but the native
engine permits another raise. Test `test_short_all_in_does_not_reopen_prior_raiser`
is a strict expected failure. **It is still a promotion blocker.**

Independently reproduced the same sequence in PokerKit 0.7.5, which correctly
forbids another raise. That independent oracle is now a passing test. PokerKit
is installed and pinned, but has not yet replaced the runtime rules adapter.

`python -m pokerbot check-gates` exits nonzero, and `confirm` refuses to start.
Investigate an upstream fix or independently validated PokerKit rules path.
Preserve the fixture, extend to cumulative short all-ins and postflop raises,
and do not workaround it by pretending multiway pots are heads-up.

## First screening run

`runs/initial-screen`: three independent seeds × 36 hands at 6, 8 and 9 seats
= 324 hands. Original policy used 16 equity samples; control pool includes
caller, tight, aggressive and the 32-sample equity policy. Results are diagnostic
only and **not valid strength confirmation while the rules defect is open**.

| Seats | Mean bb/100 | 95% session-level interval |
| --- | ---: | --- |
| 6 | 1139.58 | -1596.10 to 3875.27 |
| 8 | 2018.06 | -1459.84 to 5495.95 |
| 9 | 58.33 | -1063.20 to 1179.87 |

All intervals include zero. The large values reflect small samples, stack-reset
play and weak scripted opposition; they are not believable estimates of human
win rates. Peak process RSS was about 101 MiB on this Mac. Raw logs are ignored
by git; regenerate from the saved command and source revision.

The off/oracle/learned ablation ran another **1,944 hands** (three modes × three
table sizes × three seeds × 72 hands). Learned-minus-off gains were +7.18,
-1.62 and -44.56 bb/100 for 6, 8 and 9 seats respectively; all intervals include
zero. Oracle and learned modes had identical aggregate returns on these small
samples. This does not establish learning benefit or calibration. Run it with
`python research/learning_ablation.py --out runs/ablation-new --hands 72`.

Validation: **59 root tests passed, 1 expected failure** (the promotion blocker);
**53 vendor tests passed, 2 expected failures**; all **680 arithmetic checks**
passed. The vendor suite required permission for its local multiprocessing
socket. Three old vendor CLI tests still do not assert command success.
Recorded summary: `research/results/2026-09-16-initial.json`.

## Next bounded work

1. Fix/referee the short-all-in defect before confirmation; expand independent
   mechanics fixtures. Keep OpenSpiel available for ranking if its payouts are
   independently verified, even if rules need another engine.
2. Add the remaining stress cases: changing and wrong profiles, stack diversity,
   cumulative short all-ins, odd chips, and genuinely card-aware held-out controls.
3. Keep `baseline_v1.py` frozen while changing candidate strategy code. Its
   policy and equity sampler hashes are recorded in `baseline-v0.1.json`, and
   confirmation rejects changes. Equity opponents also use the frozen version.
4. Screen hypotheses; perform paired learning ablations. The oracle currently
   supports caller/tight/aggressive controls only and rejects random-menu or
   learned equity opponents rather than inventing their true fold probability.
5. Build one native candidate bridge and a reproducible local checkpoint/config.
   NoRegrets and dickreuter are candidates, not currently working policies.
6. Run the fixed confirmation when all correctness gates pass. On passage,
   retain results and start a harder prespecified stage per BENCHMARKS.md.

## Continuing task

Codex heartbeat `poker-strategy-research-and-testing` is active in the original
conversation every 30 minutes. The user removed the morning cutoff and asked
for expanded research after benchmark passage. Inspect running processes and
run locks before launching experiments; do not edit a running experiment's
source. Save useful progress and report meaningful results or blockers.
Local scheduled runs require the machine powered on and the app running.
