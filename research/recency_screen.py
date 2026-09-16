"""Fresh paired poker screen: same river policy, raw versus discounted learning."""
import argparse
from dataclasses import asdict
import fcntl
import hashlib
import json
import math
from pathlib import Path
import resource
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pokerbot.benchmark import correctness_failures, write_json
from pokerbot.policies import EquityConfig
from pokerbot.response_profiles import KINDS, ResponseProfiles
from pokerbot.responses import probabilities
from pokerbot.river_search import RiverConfig
from pokerbot.runner import interval, provenance, seed_for, session
from research.river_screen import diagnostics

MODES = {"original": "off", "prior": "off", "raw": "learned", "discounted": "learned"}
POOLS = {"mixed_controls": ["caller", "tight", "aggressive"],
         "passive_controls": ["caller", "tight", "tight"]}
CONFIGS = {name: EquityConfig() if name == "original" else
           RiverConfig(response_model="named", response_half_life=64 if name == "discounted" else None)
           for name in MODES}


def prediction_metrics(path, styles, mode, half_life):
    """Replay exactly the profile schedule used by the hero, before each hand."""
    counts = ResponseProfiles(half_life=half_life)
    scores, losses = [], []
    try:
        with path.open() as source:
            for line in source:
                hand = json.loads(line)
                rows = hand.get("response_observations", [])
                history = counts.view()
                for row in rows:
                    name = row["name"]
                    if name == "hero":
                        continue
                    context = (row["street"], row["facing_bet"], row["raise_available"])
                    truth = probabilities(*context, {"response_oracle": styles[name]})
                    predicted = probabilities(*context, history.get(name) if mode == "learned" else None)
                    scores.append(sum((a-b)**2 for a,b in zip(predicted, truth)))
                    losses.append(-math.log(predicted[KINDS.index(row["action"])]))
                counts.record(hand["hand_id"], rows)
        return {"half_life": half_life, "public_opponent_decisions": len(scores),
                "mean_excess_brier": sum(scores)/len(scores) if scores else None,
                "mean_log_loss": sum(losses)/len(losses) if losses else None}
    finally:
        counts.close()


def run(out, trials=6, rotations=8):
    if trials < 2 or rotations < 1:
        raise ValueError("Need independent trials and complete rotations")
    if correctness_failures():
        raise RuntimeError("Mechanics gate failed")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "run.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = {"kind": "development only; development-recency-screen-v1 fresh seeds",
                    "trials": trials, "rotations": rotations, "seats": [6,7,8,9],
                    "modes": MODES, "pools": POOLS, "configs": {k:asdict(v) for k,v in CONFIGS.items()},
                    "provenance": provenance(), "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    "plan_sha256": hashlib.sha256((ROOT / "research/RECENCY_MATCH_PLAN.md").read_bytes()).hexdigest(),
                    "helper_sha256": hashlib.sha256((ROOT / "research/river_screen.py").read_bytes()).hexdigest()}
        path = out / "manifest.json"
        if path.exists():
            old = json.loads(path.read_text())
            for key in manifest.keys() - {"provenance"}:
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
                    seed = seed_for("development-recency-screen-v1", pool_name, seats, trial)
                    for name, mode in MODES.items():
                        path = out / f"{pool_name}-n{seats}-trial{trial}-{name}.json"
                        if path.exists():
                            result = json.loads(path.read_text())
                        else:
                            log = path.with_suffix(".jsonl")
                            if log.exists():
                                log.rename(log.with_suffix(".partial-" + hashlib.sha256(log.read_bytes()).hexdigest()[:12]))
                            result = session(seats=seats, hands=seats*rotations, seed=seed,
                                config=CONFIGS[name], pool=pool, log_path=log, learning=mode,
                                frozen_hero=name == "original", hero_policy="equity" if name == "original" else "river")
                            result["search_diagnostics"] = diagnostics(log)
                            result["prediction_metrics"] = prediction_metrics(log, result["pool"], mode,
                                getattr(CONFIGS[name], "response_half_life", None))
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
        comparisons = {"discounted_minus_raw":("discounted","raw"), "discounted_minus_prior":("discounted","prior"),
                       "raw_minus_prior":("raw","prior"), "discounted_minus_original":("discounted","original"),
                       "prior_minus_original":("prior","original")}
        estimates = {pool:{label:{str(n):interval([index[pool,n,t,a]-index[pool,n,t,b] for t in range(trials)])
            for n in manifest["seats"]} for label,(a,b) in comparisons.items()} for pool in POOLS}
        report = {"status":"development only; no promotion decision","hands":sum(r["hands"] for r in rows),
                  "paired_comparisons_bb_per_100":estimates,"rows":rows,"experiment_manifest":manifest,
                  "peak_rss_native_units":max(r["process_peak_rss_native_units"] for r in rows),
                  "rss_unit":"bytes on macOS; KiB on Linux",
                  "hypothesis":"A 64-opportunity half-life improves the same named-response river policy",
                  "limitations":"Six independent sessions per default cell; unadjusted exploratory intervals; stationary card-independent controls; uniform hidden holdings; no bet-size model; prediction scores concern each arm's encountered contexts and do not establish profit"}
        write_json(out/"report.json", report)
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out",required=True)
    parser.add_argument("--trials",type=int,default=6)
    parser.add_argument("--rotations",type=int,default=8)
    args = parser.parse_args()
    report = run(args.out,args.trials,args.rotations)
    print(json.dumps({k:v for k,v in report.items() if k not in ("rows","experiment_manifest")},indent=2))
