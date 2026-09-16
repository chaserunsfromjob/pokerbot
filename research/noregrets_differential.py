"""Host-only differential mechanics test; zero policy-evaluation hands.

Imports pinned NoRegrets Rust modules directly. The source may contain an
isolated engine patch; its exact bytes are frozen with the input cases. PokerKit
supplies legal action sequences; treys independently checks terminal rankings.
Fractional PokerKit and integer native payouts are tested against separate
explicit conventions. A passing finite probe is not proof of all rules.
"""
import argparse
from collections import Counter
import fcntl
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import random
import resource
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pokerbot.engine import Decision, Hand, card_id
from treys import Card, Evaluator

COMMIT = "757f7692738069522195d2b486eec60a8b010c0c"
WRAPPER = ROOT / "research/native/noregrets_differential.rs"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2) + "\n")
    temp.replace(path)


def snapshot(hand):
    if hand.terminal:
        commits = [50, 100] + [0] * (len(hand.names)-2)
        for event in hand.events:
            commits[hand.names.index(event.name)] += event.amount
        return {"terminal": True, "returns": hand.returns(), "commits": commits}
    obs = hand.observation()
    return {"terminal": False, "actor": obs.actor, "street": obs.street,
            "board": [card_id(c) for c in obs.board], "pot": obs.pot,
            "commits": [p.contribution for p in obs.players],
            "stacks": [p.starting_stack-p.contribution for p in obs.players],
            "folded": [p.folded for p in obs.players],
            "all_in": [p.all_in for p in obs.players],
            "call": obs.legal.call_cost, "fold": obs.legal.fold,
            "min": obs.legal.min_raise_to, "max": obs.legal.max_raise_to}


def oracle(hand, commits, integer):
    """Layered pots using independent treys ranks, with no native evaluator."""
    n = len(commits)
    live = [i for i in range(n) if i not in hand.folded]
    values = [-c for c in commits]
    if len(live) == 1:
        values[live[0]] += sum(commits)
        return values
    evaluator = Evaluator()
    board = [Card.new(hand._card(c)) for c in hand.deck[2*n:2*n+5]]
    ranks = {p: evaluator.evaluate(board, [Card.new(hand._card(c)) for c in hand.deck[2*p:2*p+2]]) for p in live}
    previous = 0
    for level in sorted(set(commits) - {0}):
        eligible = [p for p in live if commits[p] >= level]
        if not eligible:
            raise AssertionError("No live seat covers the pot layer")
        winners = [p for p in eligible if ranks[p] == min(ranks[q] for q in eligible)]
        pot = sum(min(c, level)-min(c, previous) for c in commits)
        share, remainder = divmod(pot, len(winners)) if integer else (pot/len(winners), 0)
        for index, p in enumerate(winners):
            values[p] += share + (index < remainder)
        previous = level
    return values


def make_case(name, stacks, seed, prefix=(), mode="calls", deck=None):
    hand = Hand([f"p{i}" for i in range(len(stacks))], stacks, deck=deck, seed=seed)
    rng = random.Random(seed+90000)
    actions, states = [], [snapshot(hand)]
    while not hand.terminal:
        legal = hand.observation().legal
        if len(actions) < len(prefix):
            action = prefix[len(actions)]
        elif mode == "allin":
            action = legal.max_raise_to or 1
        elif mode == "calls":
            action = 1
        else:
            options = [1] * (7 if mode == "passive" else 3)
            if legal.fold:
                options.append(0)
            if legal.min_raise_to is not None:
                options.extend([legal.min_raise_to, legal.max_raise_to,
                                rng.randint(legal.min_raise_to, legal.max_raise_to)])
            action = rng.choice(options)
        hand.apply(Decision(action, {}))
        actions.append(action)
        states.append(snapshot(hand))
        if len(actions) > 250:
            raise AssertionError("Nonterminating reference hand")
    if len(actions) < len(prefix):
        raise AssertionError("Reference ended before targeted sequence")
    fractional = oracle(hand, states[-1]["commits"], False)
    if any(abs(a-b)>1e-7 for a,b in zip(hand.returns(), fractional)):
        raise AssertionError("Reference payout disagrees with independent oracle")
    return {"name": name, "stacks": stacks, "deck": hand.deck, "actions": actions,
            "states": states, "native_expected_returns": oracle(hand, states[-1]["commits"], True)}


def cases(seed, hands_per_size):
    targeted = [
        ("single-short", [10000,250,10000], [200,1,250]),
        ("cumulative-short", [300,10000,10000,250], [200,250,300,1,400]),
        ("postflop-short", [10000,350,10000], [1,1,1,300,350,1,1]),
        ("check-short-opening", [10000,150,10000], [1,1,1,1,150,1,1]),
        ("limp-short-allin", [1000,180,10000], [1,1,180,1]),
        ("late-caller-cumulative", [300,10000,10000,250,10000], [200,250,1,300,1,1,1]),
        ("unacted-bb-short", [250,10000,10000], [200,250,350]),
        ("dry-side-pot", [10000,250,250], [250,1,1]),
        ("heads-up-short-bb", [10000,100], [1]),
    ]
    result = [make_case(name, stacks, seed+i, actions) for i,(name,stacks,actions) in enumerate(targeted)]
    # A deliberately tied board and dead money produce a non-integral share.
    front = [card_id(r+s) for r in "23456" for s in "cd"] + [card_id(r+"s") for r in "TJQKA"]
    deck = front + [c for c in range(52) if c not in front]
    result.append(make_case("fractional-three-way-tie", [10000]*5, seed, [1]*5+[200,0,0,1,1], deck=deck))
    for n in range(2,7):
        rng = random.Random(seed+n)
        for i in range(hands_per_size):
            stacks = [rng.choice([100,125,150,180,250,300,777,1000,10000]) for _ in range(n)]
            mode = ("calls", "passive", "arbitrary", "allin")[i % 4]
            result.append(make_case(f"n{n}-{mode}-{i}", stacks, rng.randrange(2**31), mode=mode))
    return result


def compare(case, states):
    issues = []
    if len(states) != len(case["states"]):
        issues.append({"field": "state_count", "reference": len(case["states"]), "native": len(states)})
    for i, (reference, native) in enumerate(zip(case["states"], states)):
        expected = dict(reference)
        if reference["terminal"]:
            expected["returns"] = case["native_expected_returns"]
        state_issues = []
        for field in sorted(set(expected) | set(native)):
            if native.get(field) != expected.get(field):
                state_issues.append({"step": i, "field": field, "reference": expected.get(field), "native": native.get(field)})
        # Preserve the first divergent state. Later actions would no longer
        # represent the same hand, even if they happened to be legal.
        if state_issues:
            issues.extend(state_issues)
            break
    return issues


def run(source, out, seed, hands_per_size):
    source, out = Path(source).resolve(), Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    with (out/"run.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return locked_run(source, out, seed, hands_per_size)


def locked_run(source, out, seed, hands_per_size):
    commit = subprocess.check_output(["git","rev-parse","HEAD"], cwd=source, text=True).strip()
    if commit != COMMIT:
        raise ValueError("Require pinned NoRegrets revision")
    patch = subprocess.check_output(["git","diff","HEAD","--","src/engine.rs"], cwd=source)
    for name in ("src/cards.rs", "src/eval.rs", "Cargo.lock"):
        if (source/name).read_bytes() != subprocess.check_output(["git","show",f"HEAD:{name}"],cwd=source):
            raise ValueError(f"Unexpected native change: {name}")
    manifest = {"protocol": "native-differential-v1", "source_commit": commit,
        "source_sha256": {name:digest(source/name) for name in ("src/engine.rs","src/cards.rs","src/eval.rs","Cargo.lock")},
        "patch_sha256": hashlib.sha256(patch).hexdigest(), "script_sha256": digest(__file__),
        "wrapper_sha256": digest(WRAPPER), "reference_sha256": digest(ROOT/"pokerbot/engine.py"),
        "reference_patch_sha256": digest(ROOT/"pokerbot/pokerkit_rules.py"), "reference_engine_id": Hand.engine_id,
        "python": platform.python_version(), "pokerkit": version("pokerkit"), "treys": version("treys"),
        "rustc": subprocess.check_output(["rustc","--version"],text=True).strip(),
        "seed": seed, "hands_per_size": hands_per_size, "rand": "0.9.4"}
    if (out/"manifest.json").exists() and json.loads((out/"manifest.json").read_text()) != manifest:
        raise RuntimeError("Cannot resume a changed differential probe")
    save(out/"manifest.json", manifest)
    if (out/"report.json").exists():
        return json.loads((out/"report.json").read_text())
    (out/"engine.patch").write_bytes(patch)
    (out/"driver.py").write_bytes(Path(__file__).read_bytes())
    start = time.perf_counter()
    samples = cases(seed, hands_per_size)
    save(out/"cases.json", samples)
    crate = out/"probe"
    (crate/"src").mkdir(parents=True, exist_ok=True)
    (crate/"Cargo.toml").write_text('[package]\nname="noregrets-differential"\nversion="0.1.0"\nedition="2021"\n[dependencies]\nrand={version="=0.9.4",features=["small_rng"]}\n')
    modules = "\n".join(f'#[path = {json.dumps(str(source/"src"/(name+".rs")))}] mod {name};' for name in ("cards","eval","engine"))
    (crate/"src/main.rs").write_text("#![allow(dead_code)]\n"+modules+"\n"+WRAPPER.read_text())
    env = {**os.environ, "CARGO_HOME":str(out/"cargo-home"), "CARGO_TARGET_DIR":str(out/"target")}
    # Preserve a lockfile once generated, including on an interrupted run.
    if not (crate/"Cargo.lock").exists():
        subprocess.run(["cargo","generate-lockfile","--manifest-path",str(crate/"Cargo.toml")], env=env, check=True, timeout=120)
    for operation in ("test", "build"):
        proc = subprocess.run(["cargo",operation,"--locked","--manifest-path",str(crate/"Cargo.toml"),"--quiet"],
                              env=env,text=True,capture_output=True,timeout=180)
        (out/f"cargo-{operation}.txt").write_text(proc.stdout+proc.stderr)
        proc.check_returncode()
    inputs = "".join(" ".join(map(str,[len(c["stacks"]),*c["stacks"],*c["deck"],*c["actions"]]))+"\n" for c in samples)
    native_start = time.perf_counter()
    proc = subprocess.run([str(out/"target/debug/noregrets-differential")], input=inputs,
                          text=True,capture_output=True,timeout=120)
    native_seconds = time.perf_counter()-native_start
    (out/"native.jsonl").write_text(proc.stdout)
    (out/"native-stderr.txt").write_text(proc.stderr)
    proc.check_returncode()
    lines = proc.stdout.splitlines()
    if len(lines) != len(samples):
        raise RuntimeError("Native wrapper lost cases")
    failures, counts = [], Counter()
    rounding = []
    for case, line in zip(samples, lines):
        states = json.loads(line)
        issues = compare(case, states)
        counts[str(len(case["stacks"]))] += 1
        if issues:
            failures.append({"name":case["name"],"issues":issues,"stacks":case["stacks"],"actions":case["actions"]})
        if any(abs(a-b)>1e-7 for a,b in zip(case["native_expected_returns"],case["states"][-1]["returns"])):
            rounding.append(case["name"])
    report = {"status": "mechanics disagreement" if failures else "finite mechanics probe passed",
        "manifest": manifest, "cases": len(samples), "cases_by_seats":dict(counts),
        "reference_states":sum(len(c["states"]) for c in samples), "failures":failures,
        "declared_integer_fractional_payout_differences":rounding,
        "elapsed_seconds_including_build":time.perf_counter()-start,"native_execution_seconds":native_seconds,
        "driver_peak_rss_bytes":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=="darwin" else 1024),
        "cargo_lock_sha256":digest(crate/"Cargo.lock"), "cases_sha256":digest(out/"cases.json"),
        "native_module_tests_log_sha256":digest(out/"cargo-test.txt"),
        "native_output_sha256":digest(out/"native.jsonl"), "played_evaluation_hands":0,
        "limitations":["2–6 seats only; finite test coverage", "TDA reopening profile; class-app convention unverified",
                       "Native integer odd chips go to lowest seat; arena uses fractional payouts",
                       "No policy adapter, hidden-state isolation, native training or strength validation"]}
    save(out/"report.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--seed", type=int, default=190907)
    parser.add_argument("--hands-per-size", type=int, default=200)
    args = parser.parse_args()
    if args.hands_per_size < 1:
        parser.error("--hands-per-size must be positive")
    report = run(args.source, args.out, args.seed, args.hands_per_size)
    print(json.dumps({k:v for k,v in report.items() if k not in ("manifest","failures")}, indent=2))
    print(f"Failures: {len(report['failures'])}")
    sys.exit(bool(report["failures"]))
