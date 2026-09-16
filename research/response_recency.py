"""Fixed recency prediction pilot; synthetic opportunities, never poker hands."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import random
import resource
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pokerbot.benchmark import write_json
from pokerbot.response_profiles import KINDS, ResponseProfiles
from pokerbot.responses import probabilities
from pokerbot.runner import interval, provenance, seed_for
from research.response_stress import CHECKPOINTS, SCENARIOS, truth_for

NAMESPACE = "response-recency-v1"
TRIALS = 20
OPPORTUNITIES = 1024
HALF_LIFE = 64
ARMS = ("prior", "raw", "discounted")


def stream(scenario, trial):
    seed = seed_for(NAMESPACE, scenario, trial)
    rng = random.Random(seed)
    stores = {"raw": ResponseProfiles(), "discounted": ResponseProfiles(half_life=HALF_LIFE)}
    context = {"name": "opponent", "street": 0, "facing_bet": True, "raise_available": True}
    sums = {arm: 0. for arm in ARMS}
    window = sums.copy()
    checkpoints, actions = [], []
    started = time.perf_counter()
    try:
        if scenario == "mistaken_history":
            for store in stores.values():
                store.record("injected-wrong-history", [{**context, "action": "fold"}] * 800)
        for step in range(OPPORTUNITIES + 1):
            truth = truth_for(scenario, step)
            predictions = {"prior": probabilities(0, True, True)}
            predictions.update({arm: probabilities(0, True, True, store.view().get("opponent"))
                                for arm, store in stores.items()})
            errors = {arm: sum((p-t)**2 for p, t in zip(predictions[arm], truth)) for arm in ARMS}
            if step in CHECKPOINTS:
                checkpoints.append({"observations": step, "truth": truth,
                                    "predictions": predictions, "excess_brier": errors})
            if step == OPPORTUNITIES:
                break
            # Prediction is scored before either learner sees this opportunity.
            for arm in ARMS:
                sums[arm] += errors[arm]
                if 256 <= step < 384:
                    window[arm] += errors[arm]
            draw = rng.random()
            index = 0 if draw < truth[0] else 1 if draw < truth[0] + truth[1] else 2
            actions.append(str(index))
            for store in stores.values():
                store.record(step, [{**context, "action": KINDS[index]}])
        return {"scenario": scenario, "trial": trial, "seed": seed,
                "generated_opportunities": OPPORTUNITIES,
                "injected_wrong_observations": 800 if scenario == "mistaken_history" else 0,
                "mean_excess_brier": {arm: value / OPPORTUNITIES for arm, value in sums.items()},
                "window_256_383_excess_brier": {arm: value / 128 for arm, value in window.items()},
                "checkpoints": checkpoints, "action_indices": "".join(actions),
                "elapsed_seconds": time.perf_counter() - started,
                "process_peak_rss_native_units": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    finally:
        for store in stores.values():
            store.close()


def primary_comparisons(rows):
    """Eight fixed, paired stream-level intervals; lower error is better."""
    comparisons = []
    for scenario in SCENARIOS:
        selected = [r for r in rows if r["scenario"] == scenario]
        if len(selected) != TRIALS or {r["trial"] for r in selected} != set(range(TRIALS)):
            raise ValueError("Complete the fixed independent-stream sample before judging")
        metric = "window_256_383_excess_brier" if scenario == "changing" else "mean_excess_brier"
        references = ("prior", "raw") if scenario in ("changing", "mistaken_history") else ("raw",)
        threshold = 0. if len(references) == 2 else .02
        for reference in references:
            estimate = interval([r[metric]["discounted"] - r[metric][reference] for r in selected], alpha=.05 / 8)
            comparisons.append({"scenario": scenario, "metric": metric,
                                "contrast": f"discounted_minus_{reference}", "adjusted_interval": estimate,
                                "upper_bound_must_be_below": threshold, "passed": estimate["high"] < threshold})
    return comparisons


def run(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "run.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        paths = [Path(__file__), ROOT / "research/response_stress.py", ROOT / "research/RESPONSE_RECENCY_PLAN.md"]
        manifest = {"namespace": NAMESPACE, "trials": TRIALS, "opportunities": OPPORTUNITIES,
                    "half_life": HALF_LIFE, "scenarios": list(SCENARIOS), "alpha_per_comparison": .05 / 8,
                    "files_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                    "provenance": provenance()}
        path = out / "manifest.json"
        if path.exists():
            old = json.loads(path.read_text())
            for key in manifest.keys() - {"provenance"}:
                if old[key] != manifest[key]:
                    raise RuntimeError(f"Changed experiment: {key}")
            for key in ("source_sha256", "python", "open_spiel", "pokerkit", "numpy", "scipy"):
                if old["provenance"][key] != manifest["provenance"][key]:
                    raise RuntimeError(f"Changed runtime: {key}")
            manifest = old
        else:
            write_json(path, manifest)
        if (out / "report.json").exists():
            return json.loads((out / "report.json").read_text())
        rows = []
        for scenario in SCENARIOS:
            for trial in range(TRIALS):
                path = out / f"{scenario}-{trial}.json"
                if not path.exists():
                    write_json(path, stream(scenario, trial))
                row = json.loads(path.read_text())
                rows.append({k: v for k, v in row.items() if k != "action_indices"})
                rows[-1]["stream_file_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
                write_json(out / "progress.json", {"completed_streams": len(rows), "total_streams": TRIALS * len(SCENARIOS)})
        comparisons = primary_comparisons(rows)
        passed = all(c["passed"] for c in comparisons)
        report = {"status": "prediction pilot passed" if passed else "prediction pilot failed",
                  "poker_strength_benchmark_passed": False, "primary_comparisons": comparisons,
                  "generated_opportunities": len(rows) * OPPORTUNITIES, "played_hands": 0,
                  "rows": rows, "experiment_manifest": manifest,
                  "elapsed_seconds": sum(r["elapsed_seconds"] for r in rows),
                  "peak_rss_native_units": max(r["process_peak_rss_native_units"] for r in rows),
                  "rss_unit": "bytes on macOS; KiB on Linux",
                  "limitations": "Single legal context and known categorical processes; no card-dependent decisions, chip returns or human-strength evidence"}
        write_json(out / "report.json", report)
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    result = run(parser.parse_args().out)
    print(json.dumps({k: v for k, v in result.items() if k not in ("rows", "experiment_manifest")}, indent=2))
