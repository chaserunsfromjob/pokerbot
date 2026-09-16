"""Fresh paired development screen: sampling precision and card-aware opponents."""
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
from pokerbot.runner import interval, provenance, seed_for, session

VARIANTS = {
    "original": EquityConfig(),
    "precision128": EquityConfig(samples=128),
    "precision256": EquityConfig(samples=256),
    "priced_calls128": EquityConfig(samples=128, call_margin=0),
    "selective_raises128": EquityConfig(samples=128, raise_margin=.20),
    "pot_bets128": EquityConfig(samples=128, bet_fraction=1),
}
POOLS = {
    "scripted": ["caller", "tight", "aggressive", "equity"],
    "card_aware": ["card_tight", "card_loose", "card_pressure", "equity"],
}


def run(out, trials=6, rotations=12):
    if correctness_failures():
        raise RuntimeError("Mechanics gate failed")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "run.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = {"kind": "development only; fresh precision-screen-v1 seeds",
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
        rows = []
        hands = 0
        for pool_name, pool in POOLS.items():
            for seats in manifest["seats"]:
                for trial in range(trials):
                    seed = seed_for("development-precision-screen-v1", pool_name, seats, trial)
                    baseline = None
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
                                             frozen_hero=name == "original")
                            write_json(path, result)
                        if name == "original":
                            baseline = result["bb_per_100"]
                        hands += result["hands"]
                        rows.append({"pool": pool_name, "seats": seats, "trial": trial, "variant": name,
                                     "bb_per_100": result["bb_per_100"], "delta": result["bb_per_100"] - baseline,
                                     "elapsed_seconds": result["elapsed_seconds"],
                                     "decision_latency_ms": result["decision_latency_ms"]})
                        write_json(out / "progress.json", {"completed_sessions": len(rows),
                                   "total_sessions": len(POOLS) * 4 * trials * len(VARIANTS), "hands": hands})
        summary = {pool: {name: {str(n): interval([r["delta"] for r in rows if
                     r["pool"] == pool and r["variant"] == name and r["seats"] == n])
                     for n in manifest["seats"]} for name in VARIANTS} for pool in POOLS}
        report = {"status": "development only; no promotion decision", "hands": hands,
                  "paired_gain_bb_per_100": summary, "rows": rows,
                  "peak_rss_native_units": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  "rss_unit": "bytes on macOS; KiB on Linux", "experiment_manifest": manifest,
                  "hypotheses": ["More equity samples improve decisions over the frozen 32-sample policy",
                                 "Calling nearer pot odds improves on the positive call margin",
                                 "Effects persist when opponents respond to cards and position"],
                  "limitations": "Descriptive intervals on development sessions; multiple variants selected; no trained opponent or conditional range model"}
        write_json(out / "report.json", report)
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--trials", type=int, default=6)
    parser.add_argument("--rotations", type=int, default=12)
    args = parser.parse_args()
    if args.trials < 2 or args.rotations < 1:
        parser.error("Need at least two independent trials and one full seat rotation")
    report = run(args.out, args.trials, args.rotations)
    print(json.dumps({k: v for k, v in report.items() if k not in ("rows", "experiment_manifest")}, indent=2))
