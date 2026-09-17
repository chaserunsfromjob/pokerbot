#!/usr/bin/env python3
"""Measure CFR-family blueprint solving on OpenSpiel universal_poker at 2, 3 and 6 players.

Research instrumentation for DECISION_LAYER_BLUEPRINT.md. Not product code: nothing
here chooses a poker action at runtime. It calls OpenSpiel's own solvers and OpenSpiel's
own NashConv; no hand-rolled poker judgement (see CLAUDE.md, "The forefront rule").

One process per (algorithm, table size) cell so that a C++ abort in one cell cannot
take the whole sweep down. Each cell runs a fixed wall-clock budget, then computes
NashConv once on the average policy.

Every figure is recorded beside the 1-minute load average read from `uptime`, because
other agents share this laptop; a cell whose load exceeded 4.0 is flagged in the output.

Usage:
    .venv/bin/python research/bench_blueprint_cfr.py --all --budget 180
    .venv/bin/python research/bench_blueprint_cfr.py --algo cfr --players 3 --budget 180
"""

import argparse
import json
import os
import re
import resource
import subprocess
import sys
import time

LOAD_ALARM = 4.0

# Small card abstractions. universal_poker needs numRanks*numSuits >= numPlayers*numHoleCards
# + sum(numBoardCards), so a 6-max table with one hole card and one board card needs a
# 7-card deck at minimum. Stacks are in small-blind units; fcpa = fold/call/pot/all-in.
CONFIGS = {
    2: dict(numRanks=4, numSuits=2, stack=6),   # 8-card deck
    3: dict(numRanks=4, numSuits=2, stack=6),   # 8-card deck
    6: dict(numRanks=7, numSuits=1, stack=4),   # 7-card deck, the minimum that deals
}

ALGOS = ("cfr", "cfr_plus", "es_mccfr", "os_mccfr")


def load_avg_1min():
    """The 1-minute load average as `uptime` prints it."""
    out = subprocess.run(["uptime"], capture_output=True, text=True).stdout
    m = re.search(r"load averages?:\s*([\d.]+)", out)
    return float(m.group(1)) if m else float("nan")


def build_game(num_players):
    import pyspiel

    cfg = CONFIGS[num_players]
    blind = " ".join(["1", "2"] + ["0"] * (num_players - 2))
    params = {
        "betting": "nolimit",
        "bettingAbstraction": "fcpa",
        "numPlayers": num_players,
        "numRounds": 2,
        "numRanks": cfg["numRanks"],
        "numSuits": cfg["numSuits"],
        "numHoleCards": 1,
        "numBoardCards": "0 1",
        "stack": " ".join([str(cfg["stack"])] * num_players),
        "blind": blind,
        "firstPlayer": "1 1",
    }
    return pyspiel.load_game("universal_poker", params), params


def run_cell(algo, num_players, budget_s, seed=1):
    import pyspiel

    game, params = build_game(num_players)
    load_start = load_avg_1min()

    if algo == "cfr":
        solver = pyspiel.CFRSolver(game)
        step = solver.evaluate_and_update_policy
    elif algo == "cfr_plus":
        solver = pyspiel.CFRPlusSolver(game)
        step = solver.evaluate_and_update_policy
    elif algo == "es_mccfr":
        solver = pyspiel.ExternalSamplingMCCFRSolver(game, seed=seed)
        step = solver.run_iteration
    elif algo == "os_mccfr":
        solver = pyspiel.OutcomeSamplingMCCFRSolver(game, seed=seed)
        step = solver.run_iteration
    else:
        raise SystemExit("unknown algo %r" % algo)

    iters = 0
    t0 = time.time()
    while time.time() - t0 < budget_s:
        step()
        iters += 1
    solve_s = time.time() - t0
    load_end = load_avg_1min()
    rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6

    # NashConv: the total each player could gain by unilaterally best-responding.
    # Zero means a Nash equilibrium of the abstract game. OpenSpiel computes it by
    # walking the whole tree, so it can cost more than the solve itself.
    nc, nc_s, nc_err = None, None, None
    t1 = time.time()
    try:
        nc = pyspiel.nash_conv(game, solver.average_policy(), True)
        nc_s = time.time() - t1
    except Exception as exc:                      # noqa: BLE001 - recorded, not swallowed
        nc_err = "%s: %s" % (type(exc).__name__, str(exc)[:200])
        nc_s = time.time() - t1

    return {
        "algo": algo,
        "players": num_players,
        "deck": CONFIGS[num_players]["numRanks"] * CONFIGS[num_players]["numSuits"],
        "stack": CONFIGS[num_players]["stack"],
        "params": params,
        "budget_s": budget_s,
        "seed": seed,
        "iterations": iters,
        "solve_s": round(solve_s, 2),
        "iters_per_s": round(iters / solve_s, 3),
        "nash_conv": nc,
        "nash_conv_s": round(nc_s, 2) if nc_s is not None else None,
        "nash_conv_error": nc_err,
        "peak_rss_mb": round(rss_mb, 1),
        "load_1min_start": load_start,
        "load_1min_end": load_end,
        "load_over_4": max(load_start, load_end) > LOAD_ALARM,
        "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--algo", choices=ALGOS)
    ap.add_argument("--players", type=int, choices=sorted(CONFIGS))
    ap.add_argument("--budget", type=float, default=180.0, help="seconds per cell")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--all", action="store_true", help="sweep every algo x table size")
    ap.add_argument("--out", default="research/blueprint_cfr_results.jsonl")
    args = ap.parse_args()

    if args.all:
        # One subprocess per cell: an OpenSpiel C++ abort kills only that cell.
        for algo in ALGOS:
            for players in sorted(CONFIGS):
                cmd = [sys.executable, os.path.abspath(__file__),
                       "--algo", algo, "--players", str(players),
                       "--budget", str(args.budget), "--seed", str(args.seed),
                       "--out", args.out]
                print("=== %s %dp ===" % (algo, players), flush=True)
                rc = subprocess.run(cmd).returncode
                if rc != 0:
                    rec = {"algo": algo, "players": players, "budget_s": args.budget,
                           "crashed_exit_code": rc,
                           "load_1min_end": load_avg_1min(),
                           "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
                    with open(args.out, "a") as fh:
                        fh.write(json.dumps(rec) + "\n")
                    print("CRASHED exit %d" % rc, flush=True)
        return

    if not args.algo or not args.players:
        ap.error("give --algo and --players, or --all")
    rec = run_cell(args.algo, args.players, args.budget, args.seed)
    with open(args.out, "a") as fh:
        fh.write(json.dumps(rec) + "\n")
    print(json.dumps(rec, indent=2), flush=True)


if __name__ == "__main__":
    main()
