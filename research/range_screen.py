"""Fixed-sample development ablation of position and preflop-action ranges."""
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
from pokerbot.range_policy import RangeConfig
from pokerbot.runner import interval, provenance, seed_for, session

VARIANTS = {
    "original": RangeConfig(samples=32),
    "uniform128": RangeConfig(),
    "position128": RangeConfig(use_position=True),
    "ranges128": RangeConfig(use_ranges=True),
    "combined128": RangeConfig(use_position=True, use_ranges=True),
}
POOLS = {
    "scripted": ["caller", "tight", "aggressive", "equity"],
    "card_aware": ["card_tight", "card_loose", "card_pressure", "equity"],
}
CONTRASTS = {
    "position_minus_uniform": ("position128", "uniform128"),
    "ranges_minus_uniform": ("ranges128", "uniform128"),
    "combined_minus_position": ("combined128", "position128"),
    "combined_minus_ranges": ("combined128", "ranges128"),
}


def range_diagnostics(path):
    ess = []
    with path.open() as stream:
        for line in stream:
            hand = json.loads(line)
            for event, decision in zip(hand["events"], hand["decisions"]):
                diag = decision["diagnostics"]
                if event["name"] == "hero" and "effective_samples" in diag:
                    ess.append(diag["effective_samples"])
    return {"decisions": len(ess), "mean_ess": sum(ess) / len(ess) if ess else None,
            "min_ess": min(ess) if ess else None,
            "below_quarter_samples": sum(e < 32 for e in ess)}


def run(out, trials=8, rotations=12):
    if trials < 2 or rotations < 1:
        raise ValueError("Need at least two trials and one complete seat rotation")
    if correctness_failures():
        raise RuntimeError("Mechanics gate failed")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "run.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = {"kind": "development only; range-screen-v1 fresh seeds",
                    "trials": trials, "rotations": rotations, "seats": [6, 7, 8, 9],
                    "variants": {k: asdict(v) for k, v in VARIANTS.items()},
                    "pools": POOLS, "contrasts": CONTRASTS, "provenance": provenance(),
                    "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        # Normalize tuples before comparing a fresh manifest with saved JSON.
        manifest = json.loads(json.dumps(manifest))
        path = out / "manifest.json"
        if path.exists():
            old = json.loads(path.read_text())
            for key in ("trials", "rotations", "seats", "variants", "pools", "contrasts", "script_sha256"):
                if old[key] != manifest[key]:
                    raise RuntimeError(f"Cannot resume changed experiment: {key}")
            for key in ("source_sha256", "python", "open_spiel", "pokerkit", "numpy", "scipy"):
                if old["provenance"][key] != manifest["provenance"][key]:
                    raise RuntimeError(f"Cannot resume changed runtime: {key}")
            manifest = old
        else:
            write_json(path, manifest)
        rows = []
        for pool_name, pool in POOLS.items():
            for seats in manifest["seats"]:
                for trial in range(trials):
                    seed = seed_for("development-range-screen-v1", pool_name, seats, trial)
                    for name, config in VARIANTS.items():
                        path = out / f"{pool_name}-n{seats}-trial{trial}-{name}.json"
                        log = path.with_suffix(".jsonl")
                        if path.exists():
                            result = json.loads(path.read_text())
                        else:
                            if log.exists():
                                digest = hashlib.sha256(log.read_bytes()).hexdigest()[:12]
                                log.rename(log.with_suffix(".partial-" + digest))
                            result = session(seats=seats, hands=seats * rotations, seed=seed,
                                             config=config, pool=pool, log_path=log,
                                             hero_policy="equity" if name == "original" else "range",
                                             frozen_hero=name == "original")
                            result["range_diagnostics"] = range_diagnostics(log)
                            write_json(path, result)
                        if name == "original":
                            baseline = result["bb_per_100"]
                        rows.append({"pool": pool_name, "seats": seats, "trial": trial, "variant": name,
                                     "hands": result["hands"], "bb_per_100": result["bb_per_100"],
                                     "delta": result["bb_per_100"] - baseline,
                                     "elapsed_seconds": result["elapsed_seconds"],
                                     "decision_latency_ms": result["decision_latency_ms"],
                                     "range_diagnostics": result["range_diagnostics"]})
                        write_json(out / "progress.json", {"completed_sessions": len(rows),
                                   "total_sessions": len(POOLS) * 4 * trials * len(VARIANTS),
                                   "hands": sum(r["hands"] for r in rows)})
        summary = {pool: {name: {str(n): interval([r["delta"] for r in rows if
                     r["pool"] == pool and r["variant"] == name and r["seats"] == n])
                     for n in manifest["seats"]} for name in VARIANTS} for pool in POOLS}
        index = {(r["pool"], r["seats"], r["trial"], r["variant"]): r["bb_per_100"] for r in rows}
        contrasts = {pool: {label: {str(n): interval([
            index[pool, n, trial, a] - index[pool, n, trial, b] for trial in range(trials)])
            for n in manifest["seats"]} for label, (a, b) in CONTRASTS.items()} for pool in POOLS}
        report = {"status": "development only; no promotion decision",
                  "hands": sum(r["hands"] for r in rows), "paired_gain_bb_per_100": summary,
                  "feature_contrasts_bb_per_100": contrasts, "rows": rows,
                  "peak_rss_native_units": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  "rss_unit": "bytes on macOS; KiB on Linux", "experiment_manifest": manifest,
                  "hypotheses": ["Position-aware preflop rules improve equal-sample uniform equity play",
                                 "Public preflop actions provide useful holding-range evidence",
                                 "Position and range conditioning combine usefully"],
                  "limitations": "Unadjusted exploratory intervals; heuristic likelihoods; no postflop action inference, learned player models, folded-card model or future betting search; shared equity evaluator; no trained opponent"}
        write_json(out / "report.json", report)
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--trials", type=int, default=8)
    parser.add_argument("--rotations", type=int, default=12)
    args = parser.parse_args()
    report = run(args.out, args.trials, args.rotations)
    print(json.dumps({k: v for k, v in report.items() if k not in ("rows", "experiment_manifest")}, indent=2))
