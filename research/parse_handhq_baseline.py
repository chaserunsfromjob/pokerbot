"""Population baseline statistics, per table size, from HandHQ .phhs hand histories.

What this does, in plain words: it reads a pile of recorded poker hands, works
out for every player how often they played a hand, how often they raised, how
aggressive they were, how often they folded when the preflop raiser bet again,
and how often they stayed to the end -- and then reports what the *typical*
player looks like at a two-handed table, a three-handed table, and so on up to
nine-handed. Those typical values are what `OPPONENT_MODEL_DESIGN.md` calls
`BASELINE`: the average opponent that a real opponent's own numbers are pulled
toward while the bot has seen too few hands to trust them.

The corpus is the HandHQ no-limit hold'em cash logs inside the Poker Hand
Histories dataset (uoftcprg/phh-dataset, MIT; Zenodo record CC BY 4.0), scraped
1-23 July 2009. **The corpus is never committed to this repository.** Download a
sample into a scratch directory and point this script at it:

    python3 research/parse_handhq_baseline.py --corpus /path/to/files \
        --out research/handhq_baseline_output.txt

Stat definitions are taken literally from `OPPONENT_MODEL_DESIGN.md` section 4.2
("A coding task must implement these definitions literally"):

  vpip          numerator: voluntarily put chips in preflop (call or raise; a
                posted blind alone does not count).  denominator: dealt in.
  pfr           numerator: raised preflop.  denominator: dealt in.
  af            af_bets_raises / af_calls, postflop streets only -- the
                unbounded ratio the poker literature uses, reported and never
                acted on (design section 2.2).
  fold_to_cbet  numerator: folded facing a flop continuation bet.  denominator:
                faced one, before any raise over it.  Flop only here.
  wtsd          numerator: reached showdown.  denominator: saw a flop.

Table size is the number of players *dealt in* (`len(players)`), which is the
fallback `RESOURCES_EXPLOITATION.md` section 3.1 establishes: four of the six
networks never record `seat_count` at all, and the two that do leave it off some
hands. A nine-chair table with six people sitting therefore reads as six.

Needs nothing installed: standard library only, Python 3.13.
"""

from __future__ import annotations

import argparse
import collections
import os
import re
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor

# Counter slots per (player, table size).
(HANDS, VPIP, PFR, AF_BR, AF_CALL, FTCB_OPP, FTCB_FOLD, WTSD_OPP, WTSD,
 SHOWN) = range(10)
NSLOTS = 10

ACTION_RE = re.compile(r"'([^']*)'")
PLAYER_RE = re.compile(r"'([^']*)'")


def parse_file(path):
    """Yield one dict per hand: players, blinds, actions."""
    hand = {}
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("["):
                if hand.get("players") and "actions" in hand:
                    yield hand
                hand = {}
            elif line.startswith("actions = "):
                hand["actions"] = ACTION_RE.findall(line)
            elif line.startswith("players = "):
                hand["players"] = PLAYER_RE.findall(line)
            elif line.startswith("blinds_or_straddles = "):
                hand["blinds"] = [float(x) for x in
                                  line.split("=", 1)[1].strip(" []\n").split(",")]
            elif line.startswith("seat_count = "):
                hand["seat_count"] = int(line.split("=", 1)[1])
    if hand.get("players") and "actions" in hand:
        yield hand


def hand_stats(hand):
    """Return {player_index: [slot increments]} for one hand, plus table size."""
    players = hand["players"]
    n = len(players)
    blinds = hand.get("blinds") or [0.0] * n
    if len(blinds) < n:
        blinds = blinds + [0.0] * (n - len(blinds))

    committed = [blinds[i] for i in range(n)]
    level = max(committed) if committed else 0.0
    street = 0                      # 0 preflop, 1 flop, 2 turn, 3 river
    folded = [False] * n
    saw_flop = [False] * n
    vpip = [False] * n
    pfr = [False] * n
    af_br = [0] * n
    af_call = [0] * n
    last_pf_raiser = None
    shown = False

    # Flop continuation-bet bookkeeping.
    cbet_open = False               # a c-bet is live and unraised
    ftcb_opp = [False] * n
    ftcb_fold = [False] * n

    for act in hand["actions"]:
        parts = act.split()
        if parts[0] == "d":
            if parts[1] == "db":
                street += 1
                if street == 1:
                    for i in range(n):
                        if not folded[i]:
                            saw_flop[i] = True
                committed = [0.0] * n
                level = 0.0
                cbet_open = False
            continue
        who = parts[0]
        if not who.startswith("p"):
            continue
        try:
            i = int(who[1:]) - 1
        except ValueError:
            continue
        if not 0 <= i < n:
            continue
        verb = parts[1]

        if verb == "sm":
            shown = True
            continue
        if verb in ("f", "cc", "cbr"):
            facing = committed[i] < level - 1e-9
            if street == 1 and cbet_open and not ftcb_opp[i] and facing:
                ftcb_opp[i] = True
                if verb == "f":
                    ftcb_fold[i] = True
                if verb == "cbr":
                    cbet_open = False       # raised: later players face a raise
            if verb == "f":
                folded[i] = True
            elif verb == "cc":
                if facing:
                    committed[i] = level
                    if street == 0:
                        vpip[i] = True
                    else:
                        af_call[i] += 1
            elif verb == "cbr":
                amount = float(parts[2]) if len(parts) > 2 else level
                committed[i] = amount
                level = max(level, amount)
                if street == 0:
                    vpip[i] = True
                    pfr[i] = True
                    last_pf_raiser = i
                else:
                    af_br[i] += 1
                    if street == 1 and not cbet_open and i == last_pf_raiser:
                        cbet_open = True

    live = [i for i in range(n) if not folded[i]]
    showdown = len(live) >= 2

    out = {}
    for i in range(n):
        row = [0] * NSLOTS
        row[HANDS] = 1
        row[VPIP] = 1 if vpip[i] else 0
        row[PFR] = 1 if pfr[i] else 0
        row[AF_BR] = af_br[i]
        row[AF_CALL] = af_call[i]
        row[FTCB_OPP] = 1 if ftcb_opp[i] else 0
        row[FTCB_FOLD] = 1 if ftcb_fold[i] else 0
        if saw_flop[i]:
            row[WTSD_OPP] = 1
            if showdown and not folded[i]:
                row[WTSD] = 1
                row[SHOWN] = 1 if shown else 0
        out[players[i]] = row
    return out, n


def worker(paths):
    counts = {}
    hands = 0
    sizes = collections.Counter()
    seat_declared = 0
    for path in paths:
        for hand in parse_file(path):
            rows, n = hand_stats(hand)
            hands += 1
            sizes[n] += 1
            if "seat_count" in hand:
                seat_declared += 1
            for name, row in rows.items():
                key = (name, n)
                cur = counts.get(key)
                if cur is None:
                    counts[key] = list(row)
                else:
                    for s in range(NSLOTS):
                        cur[s] += row[s]
    return counts, hands, sizes, seat_declared


def chunks(items, k):
    out = [[] for _ in range(k)]
    for idx, item in enumerate(items):
        out[idx % k].append(item)
    return [c for c in out if c]


def quartiles(values):
    values = sorted(values)
    if not values:
        return (float("nan"),) * 3
    if len(values) < 4:
        med = statistics.median(values)
        return values[0], med, values[-1]
    qs = statistics.quantiles(values, n=4, method="inclusive")
    return qs[0], qs[1], qs[2]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", required=True,
                    help="directory of .phhs files (never inside this repo)")
    ap.add_argument("--out", help="write the report here as well as to stdout")
    ap.add_argument("--min-hands", type=int, default=100,
                    help="hands at a table size before a player enters that "
                         "size's distribution (default 100)")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--limit", type=int, default=0, help="stop after N files")
    args = ap.parse_args(argv)

    paths = []
    for root, _dirs, files in os.walk(args.corpus):
        for f in files:
            if f.endswith(".phhs"):
                paths.append(os.path.join(root, f))
    paths.sort()
    if args.limit:
        paths = paths[:args.limit]
    if not paths:
        sys.exit(f"no .phhs files under {args.corpus}")

    load_before = os.getloadavg()
    t0 = time.time()
    counts = {}
    hands = 0
    sizes = collections.Counter()
    seat_declared = 0
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for part, h, sz, sd in ex.map(worker, chunks(paths, args.workers * 4)):
            hands += h
            sizes.update(sz)
            seat_declared += sd
            for key, row in part.items():
                cur = counts.get(key)
                if cur is None:
                    counts[key] = row
                else:
                    for s in range(NSLOTS):
                        cur[s] += row[s]
    elapsed = time.time() - t0
    load_after = os.getloadavg()

    # Per-player totals across all table sizes, for the coverage question.
    per_player = collections.Counter()
    for (name, _size), row in counts.items():
        per_player[name] += row[HANDS]
    p100 = sum(1 for v in per_player.values() if v >= 100)
    p1000 = sum(1 for v in per_player.values() if v >= 1000)

    lines = []
    w = lines.append
    w("HandHQ no-limit hold'em cash hands -- population baseline per table size")
    w(f"corpus directory      : {args.corpus}")
    w(f"files parsed          : {len(paths):,}")
    w(f"hands parsed          : {hands:,}")
    w(f"player-hand rows      : {sum(r[HANDS] for r in counts.values()):,}")
    w(f"distinct player codes : {len(per_player):,}")
    w(f"hands declaring seat_count: {seat_declared:,} "
      f"({seat_declared / hands:.1%}); table size is len(players) throughout")
    w(f"parse wall-clock      : {elapsed:.1f} s on {args.workers} workers")
    w(f"1-minute load average : {load_before[0]:.2f} before, "
      f"{load_after[0]:.2f} after (other agents share this laptop)")
    w(f"players with 100+ hands (any table size)  : {p100:,}")
    w(f"players with 1,000+ hands (any table size): {p1000:,}")
    w("")
    w(f"Distributions are over players with >= {args.min_hands} hands AT THAT "
      "table size.")
    w("Q1/median/Q3 are quartiles across those players. 'pooled' is the "
      "sum-of-numerators over sum-of-denominators across every player at that")
    w("table size -- the shape of BASELINE in design section 4.3.")
    w("")

    header = ("size  hands      players  qual  "
              "VPIP Q1/med/Q3        PFR Q1/med/Q3         "
              "AF Q1/med/Q3         FtCB Q1/med/Q3       WTSD Q1/med/Q3")
    w(header)
    w("-" * len(header))

    summary_rows = []
    for size in range(2, 11):
        rows = [(name, r) for (name, s), r in counts.items() if s == size]
        if not rows:
            continue
        qual = [r for _n, r in rows if r[HANDS] >= args.min_hands]
        n_hands = sizes[size]
        if not qual:
            w(f"{size:>4}  {n_hands:>9,}  {len(rows):>7,}  {0:>4}  "
              "(no player reaches the hand floor)")
            continue

        def dist(num, den, cap=None):
            vals = []
            for r in qual:
                if r[den] > 0:
                    v = r[num] / r[den]
                    if cap is not None:
                        v = min(v, cap)
                    vals.append(v)
            return vals, quartiles(vals)

        vpip_v, vpip_q = dist(VPIP, HANDS)
        pfr_v, pfr_q = dist(PFR, HANDS)
        af_v, af_q = dist(AF_BR, AF_CALL, cap=20.0)
        ftcb_v, ftcb_q = dist(FTCB_FOLD, FTCB_OPP)
        wtsd_v, wtsd_q = dist(WTSD, WTSD_OPP)

        def pooled(num, den):
            a = sum(r[num] for _n, r in rows)
            b = sum(r[den] for _n, r in rows)
            return a / b if b else float("nan")

        summary_rows.append({
            "size": size, "hands": n_hands, "players": len(rows),
            "qual": len(qual),
            "vpip": vpip_q, "pfr": pfr_q, "af": af_q, "ftcb": ftcb_q,
            "wtsd": wtsd_q,
            "n_af": len(af_v), "n_ftcb": len(ftcb_v), "n_wtsd": len(wtsd_v),
            "pooled": {
                "vpip": pooled(VPIP, HANDS), "pfr": pooled(PFR, HANDS),
                "af": pooled(AF_BR, AF_CALL),
                "ftcb": pooled(FTCB_FOLD, FTCB_OPP),
                "wtsd": pooled(WTSD, WTSD_OPP),
            },
            "opp_ftcb": (sum(r[FTCB_OPP] for _n, r in rows)
                         / max(1, sum(r[HANDS] for _n, r in rows))),
            "opp_wtsd": (sum(r[WTSD_OPP] for _n, r in rows)
                         / max(1, sum(r[HANDS] for _n, r in rows))),
            "shown": (sum(r[SHOWN] for _n, r in rows)
                      / max(1, sum(r[WTSD] for _n, r in rows))),
        })

        def f3(q, pct=True):
            if pct:
                return "/".join(f"{x * 100:4.1f}" for x in q)
            return "/".join(f"{x:4.2f}" for x in q)

        w(f"{size:>4}  {n_hands:>9,}  {len(rows):>7,}  {len(qual):>4}  "
          f"{f3(vpip_q):>18}  {f3(pfr_q):>18}  {f3(af_q, False):>18}  "
          f"{f3(ftcb_q):>18}  {f3(wtsd_q):>18}")

    w("")
    w("Pooled rates (sum numerators / sum denominators over ALL players at the "
      "size, no hand floor) and opportunity rates per hand dealt:")
    w("size   pooled VPIP  pooled PFR  pooled AF  pooled FtCB  pooled WTSD  "
      "FtCB opps/hand  flops seen/hand  showdowns with cards shown")
    for s in summary_rows:
        p = s["pooled"]
        w(f"{s['size']:>4}   {p['vpip']:>11.3f}  {p['pfr']:>10.3f}  "
          f"{p['af']:>9.2f}  {p['ftcb']:>11.3f}  {p['wtsd']:>11.3f}  "
          f"{s['opp_ftcb']:>14.3f}  {s['opp_wtsd']:>15.3f}  {s['shown']:>25.3f}")

    w("")
    w("Qualifying-player counts behind each distribution column "
      "(a player enters a column only with a non-zero denominator):")
    w("size  players>=floor  AF denom>0  FtCB denom>0  WTSD denom>0")
    for s in summary_rows:
        w(f"{s['size']:>4}  {s['qual']:>14,}  {s['n_af']:>10,}  "
          f"{s['n_ftcb']:>12,}  {s['n_wtsd']:>12,}")

    w("")
    w("Players by hand count at a single table size (the observe-first "
      "question: how much of one opponent does a corpus actually give you):")
    w("size  >=30 hands  >=100 hands  >=200 hands  >=1,000 hands")
    for size in range(2, 11):
        rows = [r for (name, s), r in counts.items() if s == size]
        if not rows:
            continue
        w(f"{size:>4}  {sum(1 for r in rows if r[HANDS] >= 30):>10,}  "
          f"{sum(1 for r in rows if r[HANDS] >= 100):>11,}  "
          f"{sum(1 for r in rows if r[HANDS] >= 200):>11,}  "
          f"{sum(1 for r in rows if r[HANDS] >= 1000):>13,}")

    text = "\n".join(lines)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
