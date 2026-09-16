"""Diagnostic only: paired off/oracle/learned public fold-profile experiments."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pokerbot.policies import EquityConfig
from pokerbot.runner import interval, provenance, seed_for, session


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--hands", type=int, default=72)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    config = EquityConfig(samples=16, adaptive=True)
    (out / "manifest.json").write_text(json.dumps({
        "purpose": "diagnostic ablation; rules blocker prevents strength claim",
        "config": asdict(config), "hands": args.hands,
        "provenance": provenance(), "seeds": [41, 67, 89],
        "pool": ["tight", "caller", "aggressive"]}, indent=2))
    rows = []
    for seats in (6, 8, 9):
        for seed in (41, 67, 89):
            arms = {}
            for mode in ("off", "oracle", "learned"):
                sid = f"n{seats}-seed{seed}-{mode}"
                arms[mode] = session(seats=seats, hands=args.hands,
                                     seed=seed_for("ablation", seed, seats), config=config,
                                     pool=["tight", "caller", "aggressive"], learning=mode,
                                     profile_path=str(out / "profiles.sqlite3"), session_id=sid,
                                     log_path=out / f"{sid}.jsonl")["bb_per_100"]
            rows.append({"seats": seats, "seed": seed, **arms})
            (out / "results.json").write_text(json.dumps(rows, indent=2))
    report = {str(n): {arm: interval([r[arm] - r["off"] for r in rows if r["seats"] == n])
                      for arm in ("oracle", "learned")} for n in (6, 8, 9)}
    (out / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
