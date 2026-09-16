"""Validate an existing CFR trainer and portable policies on TWO-PLAYER KUHN.

This three-card toy game is not hold'em and cannot satisfy our 6–9-seat target.
Use it to establish training/evaluation/checkpoint plumbing before scaling.
"""
import argparse
from importlib.metadata import version
import json
from pathlib import Path
import random
import time

import numpy as np
import pyspiel
from open_spiel.python import policy
from open_spiel.python.algorithms import external_sampling_mccfr, exploitability


def train(out, iterations=20000, seeds=(73, 89, 113)):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    game = pyspiel.load_game("kuhn_poker", {"players": 2})
    manifest = {"game": "two-player three-card Kuhn poker", "scope": "toy training plumbing only",
                "algorithm": "OpenSpiel external-sampling MCCFR; average strategy",
                "open_spiel": version("open-spiel"), "numpy": version("numpy"),
                "iterations": iterations, "seeds": list(seeds),
                "criterion": "Every final exact NashConv < 0.05 and checkpoint roundtrip preserves it"}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    rows = []
    for seed in seeds:
        np.random.seed(seed)
        random.seed(seed)
        solver = external_sampling_mccfr.ExternalSamplingSolver(game)
        curve = []
        started = time.perf_counter()
        checkpoints = {0, min(100, iterations), min(1000, iterations), min(5000, iterations), iterations}
        for i in range(iterations + 1):
            if i in checkpoints:
                value = float(exploitability.nash_conv(game, solver.average_policy()))
                curve.append({"iteration": i, "nash_conv": value})
            if i < iterations:
                solver.iteration()
        tabular = policy.tabular_policy_from_callable(game, solver.average_policy().action_probabilities)
        checkpoint = {"game": "kuhn_poker(players=2)", "seed": seed, "iterations": iterations,
                      "open_spiel": version("open-spiel"), "kind": "average policy; not a resumable trainer state",
                      "probabilities": {key: tabular.action_probability_array[index].tolist()
                                        for key, index in tabular.state_lookup.items()}}
        path = out / f"seed-{seed}-policy.json"
        path.write_text(json.dumps(checkpoint, indent=2))
        loaded = json.loads(path.read_text())
        restored = policy.TabularPolicy(game)
        for key, index in restored.state_lookup.items():
            restored.action_probability_array[index] = loaded["probabilities"][key]
        restored_value = float(exploitability.nash_conv(game, restored))
        if abs(restored_value - curve[-1]["nash_conv"]) > 1e-12:
            raise AssertionError("Checkpoint roundtrip changed the exact evaluation")
        row = {"seed": seed, "curve": curve, "restored_nash_conv": restored_value,
               "elapsed_seconds": time.perf_counter() - started,
               "passed_toy_criterion": restored_value < .05,
               "information_sets": len(restored.state_lookup)}
        rows.append(row)
        (out / "results.json").write_text(json.dumps(rows, indent=2))
    report = {"status": "toy training criterion passed" if all(r["passed_toy_criterion"] for r in rows) else "toy criterion not met",
              "manifest": manifest, "results": rows,
              "limitations": "Not no-limit hold'em, not multiway, not a strength benchmark result; exported policies do not resume solver regrets"}
    (out / "report.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--iterations", type=int, default=20000)
    parser.add_argument("--seeds", type=int, nargs="+", default=[73, 89, 113])
    args = parser.parse_args()
    if args.iterations < 1 or len(set(args.seeds)) != len(args.seeds):
        parser.error("Use positive iterations and distinct seeds")
    print(json.dumps(train(args.out, args.iterations, args.seeds), indent=2))
