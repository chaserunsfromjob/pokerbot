"""Synthetic prediction stress; opportunities are not played poker hands."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pokerbot.response_profiles import ResponseProfiles, KINDS
from pokerbot.responses import probabilities
from pokerbot.runner import provenance

SCENARIOS = ("caller", "tight", "aggressive", "unfamiliar", "changing", "mistaken_history")
SEEDS = (17, 29, 43)
CHECKPOINTS = (0, 8, 32, 128, 256, 264, 288, 384, 512, 1024)


def truth_for(scenario, step):
    if scenario == "unfamiliar":
        return (.1, .1, .8)
    style = ("tight" if step < 256 else "caller") if scenario == "changing" else scenario
    if style == "mistaken_history":
        style = "caller"
    return probabilities(0, True, True, {"response_oracle": style})


def run():
    rows = []
    for scenario in SCENARIOS:
        for seed in SEEDS:
            store = ResponseProfiles()
            rng = random.Random(seed)
            row = {"name":"opponent","street":0,"facing_bet":True,"raise_available":True}
            if scenario == "mistaken_history":
                store.record("injected-wrong-history", [{**row,"action":"fold"}]*800)
            checkpoints = []
            prior_error = learned_error = postchange_prior = postchange_learned = 0.
            for step in range(1025):
                truth = truth_for(scenario, step)
                profile = store.view().get("opponent")
                learned = probabilities(0, True, True, profile)
                prior = probabilities(0, True, True)
                a = sum((p-t)**2 for p,t in zip(learned,truth))
                b = sum((p-t)**2 for p,t in zip(prior,truth))
                if step in CHECKPOINTS:
                    checkpoints.append({"observations":step,"truth":truth,"learned":learned,
                                        "learned_excess_brier":a,"prior_excess_brier":b})
                if step == 1024:
                    break
                prior_error += b
                learned_error += a
                if 256 <= step < 384:
                    postchange_prior += b
                    postchange_learned += a
                draw = rng.random()
                index = 0 if draw < truth[0] else 1 if draw < truth[0]+truth[1] else 2
                store.record(step, [{**row,"action":KINDS[index]}])
            rows.append({"scenario":scenario,"seed":seed,"observations":1024,
                         "mean_prior_excess_brier":prior_error/1024,
                         "mean_learned_excess_brier":learned_error/1024,
                         "window_256_383_prior_excess_brier":postchange_prior/128,
                         "window_256_383_learned_excess_brier":postchange_learned/128,
                         "checkpoints":checkpoints})
            store.close()
    return {"status":"synthetic prediction diagnostics; not strategy strength or played hands",
            "seeds":SEEDS,"scenarios":SCENARIOS,"generated_opportunities":len(rows)*1024,
            "injected_wrong_observations_per_mistaken_trial":800,"rows":rows,
            "provenance":provenance(),"script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "limitations":"Known categorical synthetic processes; single legal context; nondecaying counts; no full-game decisions or strength claim"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out",required=True)
    args = parser.parse_args()
    result = run()
    path = Path(args.out)
    if path.exists():
        parser.error("Use a fresh output path")
    path.write_text(json.dumps(result,indent=2)+"\n")
    for scenario in SCENARIOS:
        rows = [r for r in result["rows"] if r["scenario"] == scenario]
        print(scenario, {k:round(sum(r[k] for r in rows)/len(rows),5) for k in (
            "mean_prior_excess_brier","mean_learned_excess_brier",
            "window_256_383_prior_excess_brier","window_256_383_learned_excess_brier")})
