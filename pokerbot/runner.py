"""Seeded independent sessions with rotated seats and privileged replay logs."""
from dataclasses import asdict
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import random
import resource
import subprocess
import time

import numpy as np
from scipy.stats import t

from .baseline_v1 import FrozenEquityV1
from .engine import Hand
from .policies import EquityConfig, make_policy
from .profiles import Profiles

ROOT = Path(__file__).resolve().parents[1]


def seed_for(*parts):
    return int.from_bytes(hashlib.sha256(json.dumps(parts).encode()).digest()[:8], "big")


def provenance():
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted((ROOT / "pokerbot").glob("*.py"))}
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
    return {"git_commit": git("rev-parse", "HEAD"), "git_status": git("status", "--porcelain"),
            "source_sha256": hashes, "python": platform.python_version(),
            "platform": platform.platform(), "open_spiel": version("open-spiel"),
            "rules_engine": "pokerkit", "pokerkit": version("pokerkit"),
            "payout_rule": "fractional",
            "numpy": version("numpy"), "scipy": version("scipy")}


def interval(values, alpha=.05):
    values = np.asarray(values, dtype=float)
    mean = float(values.mean()) if len(values) else None
    if len(values) < 2:
        return {"mean": mean, "low": None, "high": None, "trials": len(values)}
    half = float(t.ppf(1 - alpha / 2, len(values) - 1) * values.std(ddof=1) / len(values) ** .5)
    return {"mean": mean, "low": mean - half, "high": mean + half, "trials": len(values)}


def session(*, seats, hands, seed, config, pool, log_path=None,
            profile_path=":memory:", session_id="trial", learning="off", stack_bb=100,
            frozen_hero=False):
    if not 2 <= seats <= 9 or hands < 1 or not pool or learning not in ("off", "learned", "oracle"):
        raise ValueError("Invalid session configuration")
    if learning == "oracle" and any(style not in ("caller", "tight", "aggressive") for style in pool):
        raise ValueError("Oracle trials support only caller, tight and aggressive controls")
    names = ["hero"] + [f"opponent-{i}" for i in range(seats - 1)]
    styles = {name: pool[i % len(pool)] for i, name in enumerate(names[1:])}
    policies = {"hero": FrozenEquityV1() if frozen_hero else make_policy("equity", config)}
    policies.update({name: FrozenEquityV1() if style == "equity" else make_policy(style)
                     for name, style in styles.items()})
    profiles = Profiles(profile_path, session_id)
    total = 0.0
    latency = []
    hand_log = Path(log_path).open("x") if log_path else None
    started = time.perf_counter()
    try:
        for h in range(hands):
            rotation = h % seats
            seated = names[rotation:] + names[:rotation]
            hand = Hand(seated, stacks=[stack_bb * 100] * seats,
                        seed=seed_for("deal", seed, h))
            while not hand.terminal:
                obs = hand.observation()
                name = seated[obs.actor]
                model = profiles.view() if learning == "learned" else {}
                if learning == "oracle":
                    # Exact conditional facing-bet fold probabilities of our
                    # scripted controls; unavailable for card-dependent equity.
                    model = {k: {"fold_rate": oracle_fold(v, obs), "facing_bet": 1000000}
                             for k, v in styles.items() if v != "equity"}
                rng = random.Random(seed_for("policy", seed, h, name, len(hand.events)))
                begin = time.perf_counter()
                result = policies[name].decide(obs, model if name == "hero" else {}, rng)
                latency.append(time.perf_counter() - begin)
                hand.apply(result)
                if len(hand.events) > 10000:
                    raise RuntimeError("Hand exceeded decision limit")
            total += hand.returns()[seated.index("hero")] / 100
            profiles.record(h, hand.events)
            if hand_log:
                hand_log.write(json.dumps({"hand_id": h, **hand.record()}) + "\n")
                hand_log.flush()
        return {"seed": seed, "seats": seats, "hands": hands, "hero_bb": total,
                "bb_per_100": total * 100 / hands, "pool": styles,
                "elapsed_seconds": time.perf_counter() - started,
                "decision_latency_ms": {"p50": float(np.quantile(latency, .5) * 1000),
                                        "p95": float(np.quantile(latency, .95) * 1000),
                                        "max": max(latency) * 1000},
                "public_profiles": profiles.view()}
    finally:
        profiles.close()
        if hand_log:
            hand_log.close()


def oracle_fold(style, obs):
    # The random control chooses uniformly over its legal menu. Menus depend
    # on each seat's stack; this oracle is for equal-stack control fixtures,
    # not a general hidden model of arbitrary opponents.
    if style == "tight":
        return .72
    if style in ("caller", "aggressive"):
        return 0.0
    if style == "random":
        raise ValueError("Random-menu oracle needs a counterfactual opponent state; omit random from oracle trials")
    raise ValueError("No oracle for this policy")


def tournament(out, *, seats=(6, 8, 9), seeds=(11, 23, 37), hands=36,
               config=EquityConfig(), pool=("caller", "tight", "aggressive", "equity"),
               learning="off", stack_bb=100):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    manifest = {"kind": "screening", "seats": list(seats), "seeds": list(seeds),
                "hands_per_session": hands, "config": asdict(config), "pool": list(pool),
                "learning": learning, "stack_bb": stack_bb, "rake": 0,
                "stack_mode": "reset every hand", "provenance": provenance()}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    results = []
    for n in seats:
        for seed in seeds:
            sid = f"n{n}-seed{seed}"
            result = session(seats=n, hands=hands, seed=seed_for("screen", seed, n),
                             config=config, pool=pool, log_path=out / f"{sid}.jsonl",
                             profile_path=str(out / "profiles.sqlite3"), session_id=sid,
                             learning=learning, stack_bb=stack_bb)
            result["trial_seed"] = seed
            results.append(result)
            (out / "results.json").write_text(json.dumps(results, indent=2))
    summary = {str(n): interval([r["bb_per_100"] for r in results if r["seats"] == n]) for n in seats}
    report = {"status": "screening only; not a promotion result", "by_seats_bb_per_100": summary,
              "peak_rss_native_units": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              "rss_unit": "bytes on macOS; KiB on Linux", "results": results}
    (out / "report.json").write_text(json.dumps(report, indent=2))
    return report
