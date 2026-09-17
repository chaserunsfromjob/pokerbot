#!/usr/bin/env python3
"""Render the measurement table in DECISION_LAYER_BLUEPRINT.md from the raw results.

Reads research/blueprint_cfr_results.jsonl (written by bench_blueprint_cfr.py) and
prints the markdown table. Keeps every figure in the document traceable to a
recorded run rather than typed by hand.

    .venv/bin/python research/make_blueprint_table.py
"""

import json
import sys

NAMES = {"cfr": "Vanilla CFR", "cfr_plus": "CFR+",
         "es_mccfr": "External-sampling MCCFR", "os_mccfr": "Outcome-sampling MCCFR"}
ORDER = ["cfr", "cfr_plus", "es_mccfr", "os_mccfr"]


def main(path="research/blueprint_cfr_results.jsonl"):
    rows = [json.loads(line) for line in open(path) if line.strip()]
    # Which cells have a recorded solve-only run: only those are known to have
    # solved before the NashConv measurement killed the process.
    solve_only = {(r["algo"], r["players"]) for r in rows
                  if r.get("phase") == "solve_only"}
    # Skip the interim "solve_only" records and the --skip-nashconv runs; this table
    # is the full-budget sweep. The six-handed solve-only figures get their own table.
    rows = [r for r in rows
            if r.get("phase") != "solve_only"
            and r.get("nash_conv_error") != "skipped (--skip-nashconv)"]
    by = {(r["algo"], r["players"]): r for r in rows}

    print("| Method | Seats | Iterations in 180 s | Iterations / second "
          "| NashConv reached | Time to measure NashConv | Peak memory "
          "| Load (start -> end) | Over 4.0? |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for algo in ORDER:
        for players in (2, 3, 6):
            r = by.get((algo, players))
            if r is None:
                continue
            if r.get("crashed_exit_code") is not None:
                code = r["crashed_exit_code"]
                if code != -9:
                    why = "**crashed** (exit %s)" % code
                elif (algo, players) in solve_only:
                    why = "solved, then **killed during the NashConv measurement** (signal 9)"
                else:
                    why = ("killed (signal 9); the solve is known to complete from the "
                           "`--skip-nashconv` run")
                print("| %s | %d | %s | see solve-only table | not measurable here | - | - | - -> %s | %s |" % (
                    NAMES[algo], players, why, r.get("load_1min_end"),
                    "yes" if (r.get("load_1min_end") or 0) > 4.0 else "no"))
                continue
            nc = r.get("nash_conv")
            nc_s = ("%.6g" % nc) if nc is not None else ("error: %s" % r.get("nash_conv_error"))
            print("| %s | %d | %s | %s | %s | %.2f s | %.0f MB | %s -> %s | %s |" % (
                NAMES[algo], players, "{:,}".format(r["iterations"]),
                "{:,.0f}".format(r["iters_per_s"]), nc_s, r["nash_conv_s"],
                r["peak_rss_mb"], r["load_1min_start"], r["load_1min_end"],
                "**yes**" if r["load_over_4"] else "no"))


if __name__ == "__main__":
    main(*sys.argv[1:])
