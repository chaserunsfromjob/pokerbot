# Isolated third-party repairs

## NoRegrets betting rights

`noregrets-betting-rights.patch` applies to
https://github.com/conorarmstrong/noregrets at
`757f7692738069522195d2b486eec60a8b010c0c`. It corrects short-all-in reopening,
dry-side-pot raise availability and unnecessary checks after betting ends.
`noregrets-LICENSE` preserves the original MIT notice. The exported patch was
applied to a clean source file and matched the tested file byte-for-byte.
See `../NOREGRETS_COMPATIBILITY.md` for validation and remaining integration work.

```
git apply /path/to/pokerbot/research/patches/noregrets-betting-rights.patch
```

## PokerKit reopening overrides

`pokerbot/pokerkit_rules.py` subclasses PokerKit 0.7.5 with narrow corrections.
It does not edit the installed package or alter historical replay behavior.
Its state-construction forwarding follows upstream `Poker.__call__`; retain
`pokerkit-LICENSE`, the unmodified MIT notice. The private hooks are guarded
against unreviewed version upgrades. See `../REOPENING_REPAIR.md` for fixtures,
limitations and the new engine identity.

## dickreuter/Poker equity repairs

Source: https://github.com/dickreuter/Poker, commit
`cae3a108b6cbf22ed8ef90bc0e70f790346289a4`.
These patches modify upstream GPL-3.0 source. `dickreuter-COPYING` is the
unmodified license file from that checkout; retain upstream provenance and
notices when applying or sharing patched source. No complete upstream app is
vendored here.

Apply in this order to that exact checkout:

```
git apply /path/to/pokerbot/research/patches/dickreuter-tie-share.patch
git apply /path/to/pokerbot/research/patches/dickreuter-pokerkit-ranking.patch
```

The first patch changes equity from a winner flag into expected pot share,
including fractional contributions to the win-type diagnostics. The second
delegates hand ranking to **PokerKit 0.7.5**, an additional runtime dependency,
while preserving upstream category keys (including `FoufOfAKind`). It fixes a
demonstrated case where a kicker wrongly outweighs the rank of four of a kind.

The second patch changes the internal score representation. Its use by
`eval_best_hand` and `run_montecarlo` is checked; other external consumers of
raw `calc_score` tuples must be reviewed before adopting the full application.

Reproduce from a clean pinned checkout without launching the app:

```
.venv/bin/python research/dickreuter_equity_probe.py \
  --source /path/to/pinned-checkout \
  --out /tmp/dickreuter-equity.json \
  --patch-out /tmp/dickreuter-tie-share.patch
```

The probe reads the pinned git object, applies both transformations in memory,
and uses a local path shim instead of importing unrelated app/service helpers.
It exercises the upstream Monte Carlo method on eight fully known fixtures,
and compares rankings against independent `treys` results on 400 random
2–9-player showdowns. Both emitted patches were also applied sequentially to a
temporary clean source file, whose hash matched the tested implementation.

All corrected fixtures passed. This establishes only the checked component
behavior. It does not validate conditional ranges, sampled-equity convergence,
timeouts, live capture, the full decision policy, or playing strength.
