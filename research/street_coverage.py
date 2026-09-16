"""Count decision opportunities from public events in completed original arms."""
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
            events = json.loads(line)["events"]  # Only public events are used.
            streets = [e["street"] for e in events if e["name"] == "hero"]
            counts["hands"] += 1
            for street in range(4):
                counts[f"street_{street}_decisions"] += streets.count(street)
                counts[f"hands_with_street_{street}_decision"] += street in streets
            counts["hands_with_turn_or_river_decision"] += 2 in streets or 3 in streets
            counts["hands_added_by_turn"] += 2 in streets and 3 not in streets
    return {"status": "public decision coverage only; not strength or legal-menu diversity",
            "baseline_by_pool_and_seats": counters,
            "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
            "log_sha256": hashes,
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    path = Path(args.out)
    if path.exists():
        parser.error("Use a fresh output path")
    result = audit(args.directory)
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["baseline_by_pool_and_seats"], indent=2))
