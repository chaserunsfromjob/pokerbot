"""Run the four timing programs back to back, several times, in one session.

Why this exists: the play-out counts, the engine speeds and the redraw rates in
`ENGINE_ALTERNATIVES.md` are compared against each other, so a ratio between
two of them only means something if both were measured on the same machine in
the same state. Measured in different sessions they are not comparable - this
laptop is shared, and its throughput moves by a factor of two with the load.

So each repeat runs, back to back and in this order:

    chooser.py fcpa       - play-outs in a 250 ms decision, four-move menu
    chooser.py fullgame   - the same, every whole-chip raise-to amount legal
    bench_speed.py        - complete hands per second, every engine
    resample_opponents.py - opponent hole-card redraws per second
    pypoker_playouts.py   - PyPokerEngine play-outs per second, so that its
                            rejection rests on a figure taken beside the others

Before every one of those, the machine's one-minute load average is read and
recorded beside the figures it produced. If the load is above `MAX_LOAD` the
script waits a minute and looks again, up to `MAX_WAIT_S`, then runs anyway and
says so. A load average is roughly "how many programs were queued for a
processor core"; this machine has 10 cores, and above about 4 the timings stop
meaning anything.

Usage:  python paired_session.py [repeats] [seconds_per_speed_row]

Research artefact. Not the bot, not on the bot's import path.
"""

import os
import re
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable
MAX_LOAD = 4.0
MAX_WAIT_S = 1800
DECISIONS = 20
BUDGET_S = 0.25
PYPOKER_POSITION = "first decision after the deal"


def load_average():
    """The one-minute load average, as the operating system reports it."""
    return os.getloadavg()[0]


def wait_for_quiet():
    """Wait until the machine is idle enough to time on, or give up saying so."""
    waited = 0
    load = load_average()
    while load > MAX_LOAD and waited < MAX_WAIT_S:
        print(f"    [load {load:.2f} > {MAX_LOAD}, waiting 60s "
              f"({waited}s waited so far)]", flush=True)
        time.sleep(60)
        waited += 60
        load = load_average()
    if load > MAX_LOAD:
        print(f"    [load {load:.2f} still above {MAX_LOAD} after {waited}s; "
              f"running anyway, figures are under load]", flush=True)
    return load


def run(args, label):
    """Run one measuring program, with the load average recorded beside it."""
    load = wait_for_quiet()
    print(f"--- {label} [1-minute load average at start: {load:.2f}] ---",
          flush=True)
    out = subprocess.run([PYTHON] + args, cwd=HERE, capture_output=True,
                         text=True)
    sys.stdout.write(out.stdout)
    if out.returncode != 0:
        sys.stdout.write(out.stderr)
        raise SystemExit(f"{label} failed with exit code {out.returncode}")
    print(f"--- end {label} [load at end: {load_average():.2f}] ---",
          flush=True)
    return out.stdout, load


CHOOSER_LINE = re.compile(
    r"rollouts per [\d.]+s decision: n=(\d+) decisions, "
    r"min=(\d+) max=(\d+) mean=(\d+)")
SPEED_LINE = re.compile(r"^(\S.*?)\s{2,}(\d+)\s+([\d.]+)\s+(\d+)$")
RESAMPLE_LINE = re.compile(
    r"resample_opponents, (.+?): n=(\d+) draws in [\d.]+s = (\d+) per second")
PYPOKER_LINE = re.compile(
    r"pypokerengine play-outs, (.+?): n=(\d+) play-outs in [\d.]+s = (\d+) per second")


def parse_chooser(text):
    m = CHOOSER_LINE.search(text)
    return {"n": int(m.group(1)), "min": int(m.group(2)),
            "max": int(m.group(3)), "mean": int(m.group(4))}


def parse_speed(text):
    rates = {}
    for line in text.splitlines():
        m = SPEED_LINE.match(line)
        if m and not line.startswith("engine"):
            rates[m.group(1).strip()] = int(m.group(2))
    return rates


def parse_resample(text):
    return {m.group(1): int(m.group(3)) for m in RESAMPLE_LINE.finditer(text)}


def parse_pypoker(text):
    return {m.group(1): int(m.group(3)) for m in PYPOKER_LINE.finditer(text)}


def spread(xs):
    return f"min={min(xs):8.0f}  median={statistics.median(xs):8.0f}  max={max(xs):8.0f}"


def main():
    repeats = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    speed_seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
    print(f"paired session: {repeats} repeats, each running chooser fcpa, "
          f"chooser fullgame, bench_speed {speed_seconds:.0f}s per row, "
          f"resample_opponents {speed_seconds:.0f}s per position, back to back")
    print(f"load gate: wait while the 1-minute load average is above "
          f"{MAX_LOAD}, up to {MAX_WAIT_S}s")
    print(f"python={PYTHON}")
    rows = []
    for r in range(1, repeats + 1):
        print(f"\n=== repeat {r} ===", flush=True)
        fcpa_out, fcpa_load = run(
            ["chooser.py", "fcpa", str(DECISIONS), str(BUDGET_S)],
            f"repeat {r}: chooser fcpa")
        full_out, full_load = run(
            ["chooser.py", "fullgame", str(DECISIONS), str(BUDGET_S)],
            f"repeat {r}: chooser fullgame")
        speed_out, speed_load = run(
            ["bench_speed.py", str(speed_seconds)],
            f"repeat {r}: bench_speed")
        res_out, res_load = run(
            ["resample_opponents.py", str(speed_seconds)],
            f"repeat {r}: resample_opponents")
        pyp_out, pyp_load = run(
            ["pypoker_playouts.py", str(speed_seconds)],
            f"repeat {r}: pypoker_playouts")
        rows.append({
            "fcpa": parse_chooser(fcpa_out), "fcpa_load": fcpa_load,
            "fullgame": parse_chooser(full_out), "fullgame_load": full_load,
            "speed": parse_speed(speed_out), "speed_load": speed_load,
            "resample": parse_resample(res_out), "resample_load": res_load,
            "pypoker": parse_pypoker(pyp_out), "pypoker_load": pyp_load,
        })

    print("\n=== summary over the repeats above, computed from them ===")
    print(f"{'repeat':>6s} {'load':>5s} {'fcpa play-outs/250ms':>21s} "
          f"{'load':>5s} {'fullgame play-outs/250ms':>25s} "
          f"{'load':>5s} {'OpenSpiel fcpa hands/s':>23s} "
          f"{'fcpa play-outs / hands in 250ms':>32s}")
    ratios = []
    for i, row in enumerate(rows, 1):
        hands_250 = row["speed"]["OpenSpiel universal_poker fcpa menu"] * 0.25
        ratio = row["fcpa"]["mean"] / hands_250
        ratios.append(ratio)
        print(f"{i:6d} {row['fcpa_load']:5.2f} {row['fcpa']['mean']:21d} "
              f"{row['fullgame_load']:5.2f} {row['fullgame']['mean']:25d} "
              f"{row['speed_load']:5.2f} "
              f"{row['speed']['OpenSpiel universal_poker fcpa menu']:23d} "
              f"{ratio:32.2f}")

    print()
    for key, label in (("fcpa", "chooser fcpa play-outs per 250 ms decision"),
                       ("fullgame", "chooser fullgame play-outs per 250 ms")):
        means = [row[key]["mean"] for row in rows]
        lo = min(row[key]["min"] for row in rows)
        hi = max(row[key]["max"] for row in rows)
        print(f"{label:52s} n={len(rows)} repeats x {DECISIONS} decisions  "
              f"{spread(means)}  (single decisions {lo}-{hi})")

    engines = list(rows[0]["speed"])
    for engine in engines:
        print(f"{engine:52s} n={len(rows)} repeats  "
              f"{spread([row['speed'][engine] for row in rows])}")

    for position in rows[0]["resample"]:
        print(f"{('resample_opponents, ' + position):52s} n={len(rows)} repeats  "
              f"{spread([row['resample'][position] for row in rows])}")

    for position in rows[0]["pypoker"]:
        print(f"{('pypokerengine play-outs/s, ' + position):52s} "
              f"n={len(rows)} repeats  "
              f"{spread([row['pypoker'][position] for row in rows])}")

    pairs = [
        ("OpenSpiel fcpa / texasholdem, both menu",
         "OpenSpiel universal_poker fcpa menu", "texasholdem 0.11.0 menu"),
        ("OpenSpiel fullgame / texasholdem, both real sizing",
         "OpenSpiel universal_poker fullgame", "texasholdem 0.11.0 real sizing"),
        ("OpenSpiel fcpa / PokerKit, both menu",
         "OpenSpiel universal_poker fcpa menu", "PokerKit 0.7.5 menu"),
        ("OpenSpiel fullgame / PokerKit, both real sizing",
         "OpenSpiel universal_poker fullgame", "PokerKit 0.7.5 real sizing"),
        ("OpenSpiel fcpa / PyPokerEngine, both menu",
         "OpenSpiel universal_poker fcpa menu", "PyPokerEngine 1.0.1 menu"),
        ("OpenSpiel fullgame / PyPokerEngine, both real sizing",
         "OpenSpiel universal_poker fullgame",
         "PyPokerEngine 1.0.1 real sizing"),
        ("OpenSpiel fcpa / OpenSpiel fullgame",
         "OpenSpiel universal_poker fcpa menu",
         "OpenSpiel universal_poker fullgame"),
    ]
    print()
    for label, a, b in pairs:
        rs = [row["speed"][a] / row["speed"][b] for row in rows]
        print(f"{label:52s} per-repeat ratio min={min(rs):6.2f} "
              f"median={statistics.median(rs):6.2f} max={max(rs):6.2f}")
    print(f"{'chooser fcpa play-outs / complete fcpa hands, same 250 ms':52s} "
          f"per-repeat ratio min={min(ratios):6.2f} "
          f"median={statistics.median(ratios):6.2f} max={max(ratios):6.2f}")
    fr = [row["fcpa"]["mean"] / row["fullgame"]["mean"] for row in rows]
    print(f"{'chooser fcpa / chooser fullgame play-outs':52s} "
          f"per-repeat ratio min={min(fr):6.2f} "
          f"median={statistics.median(fr):6.2f} max={max(fr):6.2f}")
    pp = [row["fcpa"]["mean"] / (row["pypoker"][PYPOKER_POSITION] * BUDGET_S)
          for row in rows]
    print(f"{'chooser fcpa play-outs / PyPokerEngine play-outs':52s} "
          f"per-repeat ratio min={min(pp):6.2f} "
          f"median={statistics.median(pp):6.2f} max={max(pp):6.2f}")


if __name__ == "__main__":
    main()
