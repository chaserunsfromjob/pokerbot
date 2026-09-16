"""Bounded, resumable DEVELOPMENT sweep. Does not spend confirmation deals."""
import argparse
from dataclasses import asdict
import fcntl
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pokerbot.benchmark import correctness_failures, write_json
from pokerbot.policies import EquityConfig
from pokerbot.runner import interval, provenance, seed_for, session

VARIANTS = {
    "original": EquityConfig(),
    "selective_raises": EquityConfig(raise_margin=.20),
    "selective_calls": EquityConfig(call_margin=.08),
    "selective_both": EquityConfig(call_margin=.08, raise_margin=.20),
    "more_value_raises": EquityConfig(raise_margin=.08),
}


def run(out, trials=3, rotations=12):
    failures = correctness_failures()
    if failures:
        raise RuntimeError("Screen blocked by mechanics: " + "; ".join(failures))
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    source = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with (out / "run.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = {"kind": "development screening only", "trials": trials, "rotations": rotations,
                    "seats": [6, 7, 8, 9], "pool": ["caller", "tight", "aggressive", "equity"],
                    "variants": {name: asdict(config) for name, config in VARIANTS.items()},
                    "provenance": provenance(), "script_sha256": source}
        saved = out / "manifest.json"
        if saved.exists():
            old = json.loads(saved.read_text())
            for key in ("trials", "rotations", "variants", "pool", "seats", "script_sha256"):
                if old[key] != manifest[key]:
                    raise RuntimeError(f"Screen configuration changed: {key}")
            for key in ("source_sha256", "python", "open_spiel", "pokerkit", "numpy", "scipy"):
                if old["provenance"][key] != manifest["provenance"][key]:
                    raise RuntimeError(f"Screen source/runtime changed: {key}")
            manifest = old
        else:
            write_json(saved, manifest)
        rows = []
        total_hands = 0
        for n in manifest["seats"]:
            for trial in range(trials):
                seed = seed_for("development-parameter-sweep-v1", n, trial)
                baseline = None
                for name, config in VARIANTS.items():
                    result_path = out / f"n{n}-trial{trial}-{name}.json"
                    if result_path.exists():
                        result = json.loads(result_path.read_text())
                    else:
                        log = result_path.with_suffix(".jsonl")
                        if log.exists():
                            digest = hashlib.sha256(log.read_bytes()).hexdigest()[:12]
                            log.rename(log.with_suffix(".partial-" + digest))
                        result = session(seats=n, hands=n * rotations, seed=seed,
                                         config=config, pool=manifest["pool"], log_path=log,
                                         frozen_hero=name == "original")
                        write_json(result_path, result)
                    if name == "original":
                        baseline = result["bb_per_100"]
                    rows.append({"seats": n, "trial": trial, "variant": name,
                                 "bb_per_100": result["bb_per_100"],
                                 "delta": result["bb_per_100"] - baseline})
                    total_hands += result["hands"]
                    write_json(out / "progress.json", {"completed_sessions": len(rows), "hands": total_hands})
        by_variant = {name: {str(n): interval([r["delta"] for r in rows if r["seats"] == n and r["variant"] == name])
                            for n in manifest["seats"]} for name in VARIANTS}
        report = {"status": "development screening; no promotion decision", "hands": total_hands,
                  "paired_gain_bb_per_100": by_variant, "rows": rows,
                  "hypothesis": "Larger equity margins reduce unprofitable calls/raises versus the frozen original",
                  "limitations": "Small development sample; weak controls; confidence intervals are descriptive and unadjusted for selecting variants"}
        write_json(out / "report.json", report)
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--rotations", type=int, default=12)
    args = parser.parse_args()
    if args.trials < 2 or args.rotations < 1:
        parser.error("At least two independent trials and one seat rotation are required")
    report = run(args.out, args.trials, args.rotations)
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))
