"""Development screen of river-only fixed-continuation action evaluation."""
import argparse
from dataclasses import asdict
import fcntl
import hashlib
import json
from pathlib import Path
import resource
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pokerbot.benchmark import correctness_failures, write_json
from pokerbot.policies import EquityConfig
from pokerbot.river_search import RiverConfig
from pokerbot.runner import interval, provenance, seed_for, session

VARIANTS = {
    "original": EquityConfig(),
    "search_equity": RiverConfig(),
    "search_caller": RiverConfig(response_model="caller"),
}
POOLS = {
    "scripted": ["caller", "tight", "aggressive", "equity"],
    "card_aware": ["card_tight", "card_loose", "card_pressure", "equity"],
}


def diagnostics(path):
    searched = changed = branches = 0
    estimated_gain = 0.
    with path.open() as stream:
        for line in stream:
            hand = json.loads(line)
            for event, decision in zip(hand["events"], hand["decisions"]):
                data = decision["diagnostics"]
                if event["name"] == "hero" and data.get("river_search"):
                    searched += 1
                    changed += data["changed"]
                    branches += data["worlds"] * data["root_actions"]
                    estimated_gain += data["action_values"][str(decision["action"])]["gain_over_baseline_bb"]
    return {"searched_decisions": searched, "changed_actions": changed,
            "counterfactual_branches": branches,
            "mean_selected_predicted_gain_bb": estimated_gain / searched if searched else None}


def run(out, trials=6, rotations=8):
    if trials < 2 or rotations < 1:
        raise ValueError("Need at least two trials and one full rotation")
    if correctness_failures():
        raise RuntimeError("Mechanics gate failed")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "run.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = {"kind": "development only; river-screen-v1 fresh seeds",
                    "trials": trials, "rotations": rotations, "seats": [6, 7, 8, 9],
                    "variants": {k: asdict(v) for k, v in VARIANTS.items()},
                    "pools": POOLS, "provenance": provenance(),
                    "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        path = out / "manifest.json"
        if path.exists():
            old = json.loads(path.read_text())
            for key in ("trials", "rotations", "seats", "variants", "pools", "script_sha256"):
                if old[key] != manifest[key]:
                    raise RuntimeError(f"Cannot resume changed experiment: {key}")
            for key in ("source_sha256", "python", "open_spiel", "pokerkit", "numpy", "scipy"):
                if old["provenance"][key] != manifest["provenance"][key]:
                    raise RuntimeError(f"Cannot resume changed runtime: {key}")
            manifest = old
        else:
            write_json(path, manifest)
        # A completed run is immutable, including its original resource record.
        # Resume must not replace that record with the lighter read-only invocation.
        report_path = out / "report.json"
        if report_path.exists():
            return json.loads(report_path.read_text())
        rows = []
        for pool_name, pool in POOLS.items():
            for seats in manifest["seats"]:
                for trial in range(trials):
                    seed = seed_for("development-river-screen-v1", pool_name, seats, trial)
                    for name, config in VARIANTS.items():
                        path = out / f"{pool_name}-n{seats}-trial{trial}-{name}.json"
                        if path.exists():
                            result = json.loads(path.read_text())
                        else:
                            log = path.with_suffix(".jsonl")
                            if log.exists():
                                digest = hashlib.sha256(log.read_bytes()).hexdigest()[:12]
                                log.rename(log.with_suffix(".partial-" + digest))
                            result = session(seats=seats, hands=seats * rotations, seed=seed,
                                             config=config, pool=pool, log_path=log,
                                             hero_policy="equity" if name == "original" else "river",
                                             frozen_hero=name == "original")
                            result["search_diagnostics"] = diagnostics(log)
                            result["process_peak_rss_native_units"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                            write_json(path, result)
                        if name == "original":
                            baseline = result["bb_per_100"]
                        rows.append({"pool": pool_name, "seats": seats, "trial": trial, "variant": name,
                                     "hands": result["hands"], "bb_per_100": result["bb_per_100"],
                                     "delta": result["bb_per_100"] - baseline,
                                     "elapsed_seconds": result["elapsed_seconds"],
                                     "decision_latency_ms": result["decision_latency_ms"],
                                     "search_diagnostics": result["search_diagnostics"],
                                     "process_peak_rss_native_units": result["process_peak_rss_native_units"]})
                        write_json(out / "progress.json", {"completed_sessions": len(rows),
                            "total_sessions": len(POOLS) * 4 * trials * len(VARIANTS),
                            "hands": sum(r["hands"] for r in rows)})
        summary = {pool: {name: {str(n): interval([r["delta"] for r in rows if
                     r["pool"] == pool and r["variant"] == name and r["seats"] == n])
                     for n in manifest["seats"]} for name in VARIANTS} for pool in POOLS}
        report = {"status": "development only; no promotion decision",
                  "hands": sum(r["hands"] for r in rows), "paired_gain_bb_per_100": summary,
                  "rows": rows, "experiment_manifest": manifest,
                  "peak_rss_native_units": max(r["process_peak_rss_native_units"] for r in rows),
                  "rss_unit": "bytes on macOS; KiB on Linux",
                  "hypothesis": "River-only action evaluation improves the frozen policy under a usable response model",
                  "limitations": "Small exploratory session sample, unadjusted intervals; uniform hidden cards; shared guessed response policy; fixed hero continuation; local SE penalty is not a strength CI; no equilibrium or exploitation guarantee"}
        write_json(report_path, report)
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--trials", type=int, default=6)
    parser.add_argument("--rotations", type=int, default=8)
    args = parser.parse_args()
    report = run(args.out, args.trials, args.rotations)
    print(json.dumps({k: v for k, v in report.items() if k not in ("rows", "experiment_manifest")}, indent=2))
