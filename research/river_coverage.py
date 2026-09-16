"""Public-event-only coverage audit for a completed river development screen."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def audit(directory):
    directory = Path(directory)
    report_path = directory / "report.json"
    report = json.loads(report_path.read_text())
    counters, hashes = {}, {}
    for row in report["rows"]:
        if row["variant"] != "original":
            continue
        key = f"{row['pool']}-n{row['seats']}"
        counts = counters.setdefault(key, Counter())
        name = f"{key}-trial{row['trial']}-original.jsonl"
        raw = (directory / name).read_bytes()
        hashes[name] = hashlib.sha256(raw).hexdigest()
        for line in raw.splitlines():
            events = json.loads(line)["events"]  # Never inspect cards or deck.
            counts["hands"] += 1
            river_hero = sum(e["name"] == "hero" and e["street"] == 3 for e in events)
            counts["hero_river_decisions"] += river_hero
            counts["hands_with_hero_river_decision"] += river_hero > 0
            counts["hands_with_no_river_betting_decision"] += max(e["street"] for e in events) < 3
            counts[f"last_decision_street_{max(e['street'] for e in events)}"] += 1
    return {"status": "descriptive coverage only; no strategy-strength test",
            "baseline_by_pool_and_seats": counters,
            "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
            "log_sha256": hashes,
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = audit(args.directory)
    Path(args.out).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["baseline_by_pool_and_seats"], indent=2))
