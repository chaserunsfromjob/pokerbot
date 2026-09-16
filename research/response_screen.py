"""Same river policy with prior, true synthetic and learned named responses."""
import argparse
from dataclasses import asdict
import fcntl
import hashlib
import json
import math
from pathlib import Path
import resource
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pokerbot.benchmark import correctness_failures, write_json
from pokerbot.policies import EquityConfig
from pokerbot.response_profiles import ResponseProfiles, KINDS
from pokerbot.responses import probabilities
from pokerbot.river_search import RiverConfig
from pokerbot.runner import interval, provenance, seed_for, session
from research.river_screen import diagnostics

MODES = {"original": "off", "prior": "off", "oracle": "oracle", "learned": "learned"}
POOLS = {"mixed_controls": ["caller", "tight", "aggressive"],
         "passive_controls": ["caller", "tight", "tight"]}


def prediction_metrics(path, styles, mode):
    counts = ResponseProfiles()
    scores, losses = [], []
    try:
        for line in path.read_text().splitlines():
            hand = json.loads(line)
            rows = hand.get("response_observations", [])
            history = counts.view()
            for row in rows:
                name = row["name"]
                if name == "hero":
                    continue
                context = (row["street"], row["facing_bet"], row["raise_available"])
                truth = probabilities(*context, {"response_oracle": styles[name]})
                profile = ({"response_oracle": styles[name]} if mode == "oracle" else
                           history.get(name) if mode == "learned" else None)
                predicted = probabilities(*context, profile)
                scores.append(sum((a-b)**2 for a,b in zip(predicted, truth)))
                losses.append(-math.log(predicted[KINDS.index(row["action"])]))
            counts.record(hand["hand_id"], rows)
        return {"public_opponent_decisions": len(scores),
                "mean_excess_brier": sum(scores)/len(scores) if scores else None,
                "mean_log_loss": sum(losses)/len(losses) if losses else None}
    finally:
        counts.close()


def run(out, trials=4, rotations=8):
    if trials < 2 or rotations < 1:
        raise ValueError("Need independent trials and complete rotations")
    if correctness_failures():
        raise RuntimeError("Mechanics gate failed")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "run.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        configs = {name: EquityConfig() if name == "original" else RiverConfig(response_model="named") for name in MODES}
        manifest = {"kind": "development only; response-screen-v1 fresh seeds",
                    "trials": trials, "rotations": rotations, "seats": [6,7,8,9],
                    "modes": MODES, "pools": POOLS, "configs": {k:asdict(v) for k,v in configs.items()},
                    "provenance": provenance(), "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    "helper_sha256": hashlib.sha256(Path("research/river_screen.py").read_bytes()).hexdigest()}
        path = out / "manifest.json"
        if path.exists():
            old = json.loads(path.read_text())
            for key in ("trials","rotations","seats","modes","pools","configs","script_sha256","helper_sha256"):
                if old[key] != manifest[key]:
                    raise RuntimeError(f"Changed experiment: {key}")
            for key in ("source_sha256","python","open_spiel","pokerkit","numpy","scipy"):
                if old["provenance"][key] != manifest["provenance"][key]:
                    raise RuntimeError(f"Changed runtime: {key}")
            manifest = old
        else:
            write_json(path, manifest)
        if (out / "report.json").exists():
            return json.loads((out / "report.json").read_text())
        rows = []
        for pool_name, pool in POOLS.items():
            for seats in manifest["seats"]:
                for trial in range(trials):
                    seed = seed_for("development-response-screen-v1", pool_name, seats, trial)
                    for name, mode in MODES.items():
                        path = out / f"{pool_name}-n{seats}-trial{trial}-{name}.json"
                        if path.exists():
                            result = json.loads(path.read_text())
                        else:
                            log = path.with_suffix(".jsonl")
                            if log.exists():
                                log.rename(log.with_suffix(".partial-" + hashlib.sha256(log.read_bytes()).hexdigest()[:12]))
                            result = session(seats=seats, hands=seats*rotations, seed=seed,
                                config=configs[name], pool=pool, log_path=log, learning=mode,
                                frozen_hero=name == "original", hero_policy="equity" if name == "original" else "river")
                            result["search_diagnostics"] = diagnostics(log)
                            result["prediction_metrics"] = prediction_metrics(log, result["pool"], mode)
                            result["process_peak_rss_native_units"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                            write_json(path, result)
                        if name == "original":
                            baseline = result["bb_per_100"]
                        rows.append({"pool":pool_name,"seats":seats,"trial":trial,"variant":name,
                            "hands":result["hands"],"bb_per_100":result["bb_per_100"],
                            "delta":result["bb_per_100"]-baseline,
                            **{k:result[k] for k in ("elapsed_seconds","decision_latency_ms","search_diagnostics","prediction_metrics","process_peak_rss_native_units")}})
                        write_json(out/"progress.json", {"completed_sessions":len(rows),"total_sessions":len(POOLS)*4*trials*len(MODES),"hands":sum(r["hands"] for r in rows)})
        index = {(r["pool"],r["seats"],r["trial"],r["variant"]):r["bb_per_100"] for r in rows}
        comparisons = {"learned_minus_prior":("learned","prior"),"oracle_minus_prior":("oracle","prior"),
                       "learned_minus_original":("learned","original"),"prior_minus_original":("prior","original")}
        estimates = {pool:{label:{str(n):interval([index[pool,n,t,a]-index[pool,n,t,b] for t in range(trials)])
            for n in manifest["seats"]} for label,(a,b) in comparisons.items()} for pool in POOLS}
        report = {"status":"development only; no promotion decision","hands":sum(r["hands"] for r in rows),
                  "paired_comparisons_bb_per_100":estimates,"rows":rows,"experiment_manifest":manifest,
                  "peak_rss_native_units":max(r["process_peak_rss_native_units"] for r in rows),
                  "rss_unit":"bytes on macOS; KiB on Linux",
                  "hypothesis":"Named public action counts improve response prediction and the same river search policy",
                  "limitations":"Few independent sessions; unadjusted exploratory intervals; known card-independent controls only; uniform hidden holdings; no bet-size model or forgetting; oracle is diagnostic, not a human-strength upper bound"}
        write_json(out/"report.json", report)
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out",required=True)
    parser.add_argument("--trials",type=int,default=4)
    parser.add_argument("--rotations",type=int,default=8)
    args = parser.parse_args()
    report = run(args.out,args.trials,args.rotations)
    print(json.dumps({k:v for k,v in report.items() if k not in ("rows","experiment_manifest")},indent=2))
