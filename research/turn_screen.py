"""Prespecified development test isolating turn search from river-only search."""
import argparse
from dataclasses import asdict
import fcntl
import hashlib
import json
from pathlib import Path
import resource
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pokerbot.benchmark import correctness_failures, write_json
from pokerbot.policies import EquityConfig
from pokerbot.river_search import RiverConfig
from pokerbot.runner import interval, provenance, seed_for, session
from pokerbot.turn_search import TurnConfig

VARIANTS = {"original": ("equity",EquityConfig()), "river": ("river",RiverConfig()), "turn": ("turn",TurnConfig())}
POOLS = {"scripted": ["caller","tight","aggressive","equity"],
         "card_aware": ["card_tight","card_loose","card_pressure","equity"]}


def diagnostics(path):
    counts = {street: {"searched_decisions":0,"changed_actions":0,"counterfactual_branches":0,"hands_with_search":0}
              for street in ("turn","river")}
    with path.open() as source:
        for line in source:
            hand = json.loads(line)
            seen = set()
            for event,decision in zip(hand["events"],hand["decisions"]):
                if event["name"] != "hero":
                    continue
                info = decision["diagnostics"]
                for street in counts:
                    if info.get(f"{street}_search"):
                        counts[street]["searched_decisions"] += 1
                        counts[street]["changed_actions"] += info["changed"]
                        counts[street]["counterfactual_branches"] += info["worlds"]*info["root_actions"]
                        seen.add(street)
            for street in seen:
                counts[street]["hands_with_search"] += 1
    return counts


def run(out,trials=6,rotations=8):
    if trials < 2 or rotations < 1:
        raise ValueError("Need independent trials and complete seat rotations")
    if correctness_failures():
        raise RuntimeError("Mechanics gate failed")
    out = Path(out)
    out.mkdir(parents=True,exist_ok=True)
    with (out/"run.lock").open("a+") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        manifest = {"kind":"development-turn-screen-v1; no confirmation data",
            "trials":trials,"rotations":rotations,"seats":[6,7,8,9],"pools":POOLS,"learning":"off",
            "variants":{name:{"policy":policy,"parameters":asdict(config)} for name,(policy,config) in VARIANTS.items()},
            "provenance":provenance(),"script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "plan_sha256":hashlib.sha256((ROOT/"research/TURN_SEARCH_PLAN.md").read_bytes()).hexdigest()}
        path = out/"manifest.json"
        if path.exists():
            old = json.loads(path.read_text())
            for key in manifest.keys()-{"provenance"}:
                if old[key] != manifest[key]:
                    raise RuntimeError(f"Changed experiment: {key}")
            for key in ("source_sha256","python","open_spiel","pokerkit","numpy","scipy"):
                if old["provenance"][key] != manifest["provenance"][key]:
                    raise RuntimeError(f"Changed runtime: {key}")
            manifest = old
        else:
            write_json(path,manifest)
        if (out/"report.json").exists():
            return json.loads((out/"report.json").read_text())
        rows = []
        for pool_name,pool in POOLS.items():
            for seats in manifest["seats"]:
                for trial in range(trials):
                    seed = seed_for("development-turn-screen-v1",pool_name,seats,trial)
                    for name,(policy,config) in VARIANTS.items():
                        path = out/f"{pool_name}-n{seats}-trial{trial}-{name}.json"
                        if path.exists():
                            result = json.loads(path.read_text())
                        else:
                            log = path.with_suffix(".jsonl")
                            if log.exists():
                                log.rename(log.with_suffix(".partial-"+hashlib.sha256(log.read_bytes()).hexdigest()[:12]))
                            result = session(seats=seats,hands=seats*rotations,seed=seed,config=config,
                                pool=pool,log_path=log,hero_policy=policy,frozen_hero=name=="original")
                            result["search_diagnostics"] = diagnostics(log)
                            for street in ("turn","river"):
                                if result["search_diagnostics"][street]["searched_decisions"] != result["search_latency_ms"][street]["count"]:
                                    raise RuntimeError("Search timing and public-log counts disagree")
                            result["process_peak_rss_native_units"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                            write_json(path,result)
                        rows.append({"pool":pool_name,"seats":seats,"trial":trial,"variant":name,
                            **{k:result[k] for k in ("hands","bb_per_100","elapsed_seconds","decision_latency_ms",
                                "search_latency_ms","search_diagnostics","process_peak_rss_native_units")}})
                        write_json(out/"progress.json",{"completed_sessions":len(rows),"total_sessions":len(POOLS)*4*trials*len(VARIANTS),
                            "hands":sum(r["hands"] for r in rows)})
        index = {(r["pool"],r["seats"],r["trial"],r["variant"]):r["bb_per_100"] for r in rows}
        contrasts = {"turn_minus_river":("turn","river"),"turn_minus_original":("turn","original"),"river_minus_original":("river","original")}
        estimates = {pool:{label:{str(n):interval([index[pool,n,t,a]-index[pool,n,t,b] for t in range(trials)])
            for n in manifest["seats"]} for label,(a,b) in contrasts.items()} for pool in POOLS}
        report = {"status":"development only; no promotion decision","hands":sum(r["hands"] for r in rows),
            "paired_comparisons_bb_per_100":estimates,"rows":rows,"experiment_manifest":manifest,
            "peak_rss_native_units":max(r["process_peak_rss_native_units"] for r in rows),
            "rss_unit":"bytes on macOS; KiB on Linux",
            "hypothesis":"Adding turn rollouts improves the same river-only policy",
            "limitations":"Unadjusted exploratory intervals; fixed equity continuations and uniform hidden holdings; no equilibrium guarantee; learned responses disabled; no trained opponents or confirmation deals"}
        write_json(out/"report.json",report)
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out",required=True)
    parser.add_argument("--trials",type=int,default=6)
    parser.add_argument("--rotations",type=int,default=8)
    args = parser.parse_args()
    result = run(args.out,args.trials,args.rotations)
    print(json.dumps({k:v for k,v in result.items() if k not in ("rows","experiment_manifest")},indent=2))
