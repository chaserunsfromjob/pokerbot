"""Fixed, resumable paired confirmation; no promotion on known rules defects."""
from dataclasses import asdict
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from .engine import Decision, Hand
from .policies import EquityConfig
from .runner import ROOT, interval, provenance, seed_for, session


BASELINE = EquityConfig(samples=32, call_margin=.02, raise_margin=.12,
                        bet_fraction=.5, adaptive=False)
HOLDOUT_POOLS = (
    ("equity", "tight", "caller"),
    ("equity", "aggressive", "tight"),
    ("equity", "equity", "caller", "aggressive"),
    ("tight", "equity", "caller", "tight", "aggressive"),
)


def correctness_failures():
    failures = []
    hand = Hand(["sb", "bb", "button"], [10000, 250, 10000])
    for action in (200, 1, 250):
        hand.apply(Decision(action, {}))
    if hand.observation().legal.min_raise_to is not None:
        failures.append("OpenSpiel short all-in incorrectly reopens the prior raiser")
    return failures


def write_json(path, data):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2))
    temporary.replace(path)


def create_confirmation(out, candidate, *, trials=30, hands=504):
    if trials < 30 or hands < 504 or hands % 504:
        raise ValueError("Confirmation needs >=30 trials and >=504 hands per trial, in multiples of 504")
    failures = correctness_failures()
    if failures:
        raise RuntimeError("Confirmation blocked: " + "; ".join(failures))
    frozen = json.loads((ROOT / "research" / "baseline-v0.1.json").read_text())
    if any(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != digest
           for p, digest in frozen["source_sha256"].items()):
        raise RuntimeError("Frozen baseline changed: create a new named benchmark, do not reuse this target")
    # A saved passing suite is required in addition to the focused known-defect gate.
    checks = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q"],
                            cwd=ROOT, text=True, capture_output=True, timeout=180)
    if checks.returncode:
        raise RuntimeError("Confirmation requires passing tests:\n" + checks.stdout + checks.stderr)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    (out / "correctness-checks.txt").write_text(checks.stdout + checks.stderr)
    (ROOT / "runs").mkdir(exist_ok=True)
    ledger = ROOT / "runs" / "confirmation-ledger.json"
    with (ROOT / "runs" / "confirmation-ledger.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        history = json.loads(ledger.read_text()) if ledger.exists() else []
        attempt = len(history) + 1
        history.append({"attempt": attempt, "path": str(out.resolve()), "candidate": asdict(candidate)})
        write_json(ledger, history)
    spec = {"protocol": "first-milestone-v1", "attempt": attempt,
            "trials": trials, "hands": hands, "seats": [6, 7, 8, 9],
            "pools": HOLDOUT_POOLS, "baseline": asdict(BASELINE), "candidate": asdict(candidate),
            "learning": "learned" if candidate.adaptive else "off",
            "stack_bb": 100, "rake": 0,
            "family_alpha": .05 / (attempt * (attempt + 1)),
            "minimum_improvement_bb_per_100": 5,
            "provenance": provenance()}
    write_json(out / "manifest.json", spec)
    return run_confirmation(out)


def run_confirmation(out):
    out = Path(out)
    # One experiment process at a time; locks release on exit/crash.
    with (out / "run.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _run(out)


def _run(out):
    spec = json.loads((out / "manifest.json").read_text())
    if provenance()["source_sha256"] != spec["provenance"]["source_sha256"]:
        raise RuntimeError("Code changed since freeze; use a new experiment")
    failures = correctness_failures()
    if failures:
        raise RuntimeError("Confirmation blocked: " + "; ".join(failures))
    rows = []
    for n in spec["seats"]:
        for trial in range(spec["trials"]):
            pool = spec["pools"][trial % len(spec["pools"])]
            seed = seed_for("confirm-v1", spec["attempt"], n, trial)
            pair = {}
            for arm in ("baseline", "candidate"):
                stem = f"{n}-{trial}-{arm}"
                result_path = out / f"{stem}.json"
                if result_path.exists():
                    result = json.loads(result_path.read_text())
                else:
                    log = out / f"{stem}.jsonl"
                    if log.exists():
                        # Preserve an interrupted trial; rerun it with empty memory.
                        digest = hashlib.sha256(log.read_bytes()).hexdigest()[:12]
                        log.rename(out / f"{stem}.partial-{digest}")
                    result = session(seats=n, hands=spec["hands"], seed=seed,
                                     config=EquityConfig(**spec[arm]), pool=pool, log_path=log,
                                     learning=spec["learning"] if arm == "candidate" else "off",
                                     stack_bb=spec["stack_bb"], frozen_hero=arm == "baseline")
                    write_json(result_path, result)
                pair[arm] = result["bb_per_100"]
            rows.append({"seats": n, "trial": trial, "delta": pair["candidate"] - pair["baseline"], **pair})
            write_json(out / "progress.json", {"completed_pairs": len(rows), "total_pairs": len(spec["seats"]) * spec["trials"]})
    # Independent sessions, not individual hands, are the statistical units.
    cells = {}
    for n in spec["seats"]:
        ci = interval([r["delta"] for r in rows if r["seats"] == n], alpha=spec["family_alpha"] / 4)
        ci["passed"] = ci["mean"] >= spec["minimum_improvement_bb_per_100"] and ci["low"] > 0
        cells[str(n)] = ci
    passed = all(c["passed"] for c in cells.values())
    report = {"status": "first milestone passed" if passed else "not passed; retain incumbent",
              "paired_improvement_bb_per_100": cells, "rows": rows,
              "limitations": ["Student-t intervals on independent session means are approximate",
                              "Scripted/equity pool is not evidence of strength against trained policies or humans",
                              "100bb reset stacks, no rake; no tournament survival objective"]}
    write_json(out / "report.json", report)
    return report
