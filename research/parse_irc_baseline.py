"""Population baseline statistics, per table size, from the IRC Poker Database.

The companion to `parse_handhq_baseline.py`. Same five questions, same output
shape, different corpus: Michael Maurer's IRC poker logs, 1995-2001, from
http://poker.cs.ualberta.ca/irc_poker_database.html . The point of running both
is the comparison in `OPPONENT_BASELINE.md` -- whether a 1990s mostly-fixed-limit
corpus produces the same typical player as a no-limit one.

Fold-to-continuation-bet is deliberately **not** computed here. The IRC per-player
record stores each street as one string of that player's own actions, with no
ordering between players, so "faced the preflop raiser's flop bet" cannot be
reconstructed without rebuilding the whole betting sequence from the roster.

A per-player row looks like:

    AAiyAAh   916828992  9  5 r   rc    r     rr        1000  180    0 4c Jd
    name      timestamp  n  pos pre flop  turn  river   bank  bet  won [cards]

Action letters: `-` no action, `B` posted blind, `f` fold, `k` check, `b` bet,
`c` call, `r` raise, `A` all-in, `Q` quit, `K` kicked.

  vpip   preflop string contains a call, bet or raise -- a posted blind (`B`)
         alone does not count, matching OPPONENT_MODEL_DESIGN.md section 4.2.
  pfr    preflop string contains a raise.
  af     (bets + raises) / calls over flop, turn and river.
  wtsd   numerator: the row ends in shown cards, which the logger records at a
         showdown.  denominator: the player saw a flop.  Cards shown is a
         **proxy** for reaching showdown and is marked as one in the report.

Usage -- the corpus is never committed to this repository:

    python3 research/parse_irc_baseline.py --corpus /path/to/IRCdata/holdem \
        --out research/irc_baseline_output.txt

Standard library only, Python 3.13.
"""

from __future__ import annotations

import argparse
import collections
import os
import statistics
import sys
import time

HANDS, VPIP, PFR, AF_BR, AF_CALL, WTSD_OPP, WTSD = range(7)
NSLOTS = 7


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
                    help="a directory holding month directories, each with pdb/")
    ap.add_argument("--out")
    ap.add_argument("--min-hands", type=int, default=100)
    args = ap.parse_args(argv)

    pdb_files = []
    for root, _dirs, files in os.walk(args.corpus):
        if os.path.basename(root) != "pdb":
            continue
        for f in files:
            if f.startswith("pdb."):
                pdb_files.append(os.path.join(root, f))
    if not pdb_files:
        sys.exit(f"no pdb.* files under {args.corpus}")

    load_before = os.getloadavg()
    t0 = time.time()
    counts = {}
    rows_read = 0
    sizes = collections.Counter()
    hands_seen = collections.Counter()
    for path in pdb_files:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) < 11:
                    continue
                name = parts[0]
                try:
                    n = int(parts[2])
                except ValueError:
                    continue
                stamp = parts[1]
                pre, flop, turn, river = parts[4], parts[5], parts[6], parts[7]
                shown = len(parts) >= 13
                rows_read += 1
                sizes[n] += 1
                hands_seen[(stamp, n)] = 1
                key = (name, n)
                row = counts.get(key)
                if row is None:
                    row = counts[key] = [0] * NSLOTS
                row[HANDS] += 1
                voluntary = any(ch in pre for ch in "crbA")
                if voluntary:
                    row[VPIP] += 1
                if "r" in pre:
                    row[PFR] += 1
                post = flop + turn + river
                row[AF_BR] += post.count("b") + post.count("r")
                row[AF_CALL] += post.count("c")
                saw_flop = flop not in ("-", "")
                if saw_flop:
                    row[WTSD_OPP] += 1
                    if shown:
                        row[WTSD] += 1
    elapsed = time.time() - t0
    load_after = os.getloadavg()

    per_player = collections.Counter()
    for (name, _n), row in counts.items():
        per_player[name] += row[HANDS]

    lines = []
    w = lines.append
    w("IRC Poker Database -- population baseline per table size "
      "(fixed-limit hold'em channel)")
    w(f"corpus directory      : {args.corpus}")
    w(f"player files parsed   : {len(pdb_files):,}")
    w(f"player-hand rows      : {rows_read:,}")
    w(f"distinct hands        : {len(hands_seen):,} (timestamp+table size)")
    w(f"distinct player names : {len(per_player):,}")
    w(f"parse wall-clock      : {elapsed:.1f} s, single process")
    w(f"1-minute load average : {load_before[0]:.2f} before, "
      f"{load_after[0]:.2f} after")
    w(f"players with 100+ hands  : "
      f"{sum(1 for v in per_player.values() if v >= 100):,}")
    w(f"players with 1,000+ hands: "
      f"{sum(1 for v in per_player.values() if v >= 1000):,}")
    w("")
    w(f"Distributions over players with >= {args.min_hands} hands at that table "
      "size. WTSD uses shown cards as a proxy for reaching showdown.")
    w("")
    header = ("size  hands      players  qual  VPIP Q1/med/Q3        "
              "PFR Q1/med/Q3         AF Q1/med/Q3         WTSD Q1/med/Q3")
    w(header)
    w("-" * len(header))
    for size in range(2, 11):
        rows = [r for (nm, s), r in counts.items() if s == size]
        if not rows:
            continue
        qual = [r for r in rows if r[HANDS] >= args.min_hands]
        if not qual:
            w(f"{size:>4}  {sizes[size]:>9,}  {len(rows):>7,}     0  "
              "(no player reaches the hand floor)")
            continue

        def dist(num, den, cap=None):
            vals = []
            for r in qual:
                if r[den] > 0:
                    v = r[num] / r[den]
                    vals.append(min(v, cap) if cap else v)
            return quartiles(vals)

        def f3(q, pct=True):
            if pct:
                return "/".join(f"{x * 100:4.1f}" for x in q)
            return "/".join(f"{x:4.2f}" for x in q)

        w(f"{size:>4}  {sizes[size]:>9,}  {len(rows):>7,}  {len(qual):>4}  "
          f"{f3(dist(VPIP, HANDS)):>18}  {f3(dist(PFR, HANDS)):>18}  "
          f"{f3(dist(AF_BR, AF_CALL, 20.0), False):>18}  "
          f"{f3(dist(WTSD, WTSD_OPP)):>18}")

    w("")
    w("Pooled rates over all players at the size (the shape of BASELINE):")
    w("size   pooled VPIP  pooled PFR  pooled AF  pooled WTSD  flops seen/hand")
    for size in range(2, 11):
        rows = [r for (nm, s), r in counts.items() if s == size]
        if not rows:
            continue
        tot = [sum(r[i] for r in rows) for i in range(NSLOTS)]
        w(f"{size:>4}   {tot[VPIP] / tot[HANDS]:>11.3f}  "
          f"{tot[PFR] / tot[HANDS]:>10.3f}  "
          f"{(tot[AF_BR] / tot[AF_CALL] if tot[AF_CALL] else float('nan')):>9.2f}  "
          f"{(tot[WTSD] / tot[WTSD_OPP] if tot[WTSD_OPP] else float('nan')):>11.3f}  "
          f"{tot[WTSD_OPP] / tot[HANDS]:>15.3f}")

    w("")
    w("Players by hand count at a single table size:")
    w("size  >=30 hands  >=100 hands  >=200 hands  >=1,000 hands")
    for size in range(2, 11):
        rows = [r for (nm, s), r in counts.items() if s == size]
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
