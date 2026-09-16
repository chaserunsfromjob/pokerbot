# Reopening corrections — September 16, 2026

**The active referee is now `pokerkit-0.7.5-reopening-v1`.** Three targeted
fixtures reproduce prohibited raises accepted by unpatched PokerKit 0.7.5 and
rejected by the corrected native State and host action interface. The new gates
block confirmation if the historical engine is substituted.

The independent reference is [TDA 2024 rule 47 and its illustrations](https://www.pokertda.com/view-poker-tda-rules/).
Examples 3-A and 1-A establish that a limper facing a short raise cannot re-raise,
and that cumulative reopening depends on the increase faced by each player.
We apply the full-bet requirement to prior checks facing short opening all-ins
as well. This defines our simulation profile; the class app's conventions have
not been observed. Integer odd-chip allocation remains a separate profile.

| Reproduction (whole-hand amounts) | Unpatched PokerKit | Corrected |
| --- | --- | --- |
| Three seats 1000/180/10000; call, call, all-in 180 | Prior caller may raise to 280 | Owes 80; fold/call only |
| Five seats 300/10000/10000/250/10000; raise 200, all-in 250, call, all-in 300, call, call | Later caller may raise to 400 | That caller faces only 50; fold/call only |
| Three seats 10000/150/10000; three preflop calls, flop check, short all-in 50, call | Prior checker may raise to street 150 | Owes 50; fold/call only |

The probe actually applies each prohibited raise through the historical
interface and verifies its rejection in the current interface. It also checks
PokerKit State legality directly, so this is not just a displayed-action issue.

The upstream implementation begins each betting round with a zero tracked
full-raise increment, allowing the first short wager to reset acted-player
history. Its other reopening check sums consecutive all-ins globally, including
amounts a later caller already matched. The isolated subclass establishes the
street minimum and checks the current actor's amount faced before delegating
to the engine's other checks. It also removes redundant forced checks when
only one player has chips and owes no call. PokerKit still handles all other
betting, pot settlement and ranking; the installed dependency is untouched.

## Verification

- 192 project tests passed, including new 2–9-seat limp/reopening fixtures,
  cumulative reopening for different callers, unacted BB options, short
  opening bets, exact rejection, dry pots and replay identities.
- 53 historical vendor tests passed; two existing expected failures remain.
  These do not prove the historical fixed-limit trainer works.
- 384 real saved hand logs from the prior turn-search screen replayed exactly
  through `LegacyPokerKitHand`. Old records keep `pokerkit-0.7.5`; new records
  use the corrected engine identity. Historical OpenSpiel replay also remains.
- The independently patched NoRegrets engine agreed on all 5,010 fresh complete
  hands / 44,971 states at 2–6 seats. Payout ranks were checked with treys;
  native integer and arena fractional pot conventions were checked separately.
- No held-out attempt was allocated. The frozen original strategy hashes and
  parameters are unchanged. No policy has passed the strength benchmark.

Reproduce the small positive/negative probe:

```
.venv/bin/python research/pokerkit_reopening_probe.py --out runs/pokerkit-reopening.json
.venv/bin/python -m pytest tests/test_reopening_rules.py -q
.venv/bin/python -m pokerbot check-gates
```

Recorded evidence is in `results/2026-09-16-pokerkit-reopening.json` and the
NoRegrets differential result files. Probe inputs, source and runtime are
versioned. Finite tests are not exhaustive proof of every betting sequence.

## Consequences for research

The prior 98,868 played evaluation hands remain historical results under their
original engines. The effect of these defects on each strategy comparison has
not been quantified; rerun any candidate considered for promotion. Synthetic
response-prediction tests and toy Kuhn results are separate claims.

The revised confirmation name is `first-milestone-v2-reopening`. Keep the same
baseline, thresholds, held-out pools, independent-session uncertainty and
shared attempt ledger; this repair does not create a new statistical budget.
Old experiments cannot resume with altered source/runtime hashes. Next comes
the bounded native checkpoint pilot and fresh strategy evaluations.
