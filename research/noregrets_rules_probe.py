"""Compile unmodified pinned NoRegrets engine modules for two betting probes.

No training, bridge, live service, or native policy is used by the poker arena.
Cargo's registry and target files stay inside the requested output directory.
"""
import argparse
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pokerbot.engine import Decision, Hand

COMMIT = "757f7692738069522195d2b486eec60a8b010c0c"


def run(source,out):
    source,out = Path(source).resolve(),Path(out).resolve()
    commit = subprocess.check_output(["git","rev-parse","HEAD"],cwd=source,text=True).strip()
    status = subprocess.check_output(["git","status","--porcelain"],cwd=source,text=True).strip()
    if commit != COMMIT or status:
        raise ValueError("Require the clean, pinned NoRegrets checkout")
    manifest = {"source_commit":commit,"source_url":"https://github.com/conorarmstrong/noregrets",
        "source_sha256":{name:hashlib.sha256((source/name).read_bytes()).hexdigest()
                         for name in ("src/engine.rs","src/cards.rs","src/eval.rs","Cargo.lock")},
        "script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "python":platform.python_version(), "pokerkit":version("pokerkit"),
        "reference_engine_sha256":hashlib.sha256((ROOT/"pokerbot/engine.py").read_bytes()).hexdigest(),
        "rustc":subprocess.check_output(["rustc","--version"],text=True).strip(),
        "rand":"0.9.4"}
    out.mkdir(parents=True,exist_ok=True)
    path = out/"manifest.json"
    if path.exists() and json.loads(path.read_text()) != manifest:
        raise RuntimeError("Cannot resume changed native probe")
    path.write_text(json.dumps(manifest,indent=2)+"\n")
    if (out/"report.json").exists():
        return json.loads((out/"report.json").read_text())
    crate = out/"probe"
    (crate/"src").mkdir(parents=True,exist_ok=True)
    (crate/"Cargo.toml").write_text('[package]\nname="noregrets-rules-probe"\nversion="0.1.0"\nedition="2021"\n[dependencies]\nrand={version="=0.9.4",features=["small_rng"]}\n')
    modules = "\n".join(f'#[path = {json.dumps(str(source/"src"/(name+".rs")))}] mod {name};' for name in ("cards","eval","engine"))
    main = r'''
use engine::{Hand,HandConfig,PlayerAction::{RaiseTo,CheckCall}};
fn main() {
    let cfg=HandConfig {num_players:3,..HandConfig::default()};
    let mut h=Hand::new_with_stacks(&cfg,2,cards::fresh_deck(),&[10000,250,10000]);
    for a in [RaiseTo(200),CheckCall,RaiseTo(250)] {h.apply(a);}
    let b=h.raise_bounds();
    println!("single actor={} call={} min={} max={}",h.to_act(),h.to_call(),b.map_or(0,|x|x.0),b.map_or(0,|x|x.1));
    h.apply(RaiseTo(350));
    println!("after_illegal_reraise contribution={}",h.hand_commit(2));
    let cfg=HandConfig {num_players:4,..HandConfig::default()};
    let mut h=Hand::new_with_stacks(&cfg,3,cards::fresh_deck(),&[300,10000,10000,250]);
    for a in [RaiseTo(200),RaiseTo(250),RaiseTo(300),CheckCall] {h.apply(a);}
    let b=h.raise_bounds();
    println!("cumulative actor={} call={} min={} max={}",h.to_act(),h.to_call(),b.map_or(0,|x|x.0),b.map_or(0,|x|x.1));
}
'''
    (crate/"src/main.rs").write_text('#![allow(dead_code)]\n'+modules+main)
    env = {**os.environ,"CARGO_HOME":str(out/"cargo-home"),"CARGO_TARGET_DIR":str(out/"target")}
    start = time.perf_counter()
    proc = subprocess.run(["cargo","run","--manifest-path",str(crate/"Cargo.toml"),"--quiet"],
                          env=env,text=True,capture_output=True,timeout=180)
    (out/"stdout.txt").write_text(proc.stdout)
    (out/"stderr.txt").write_text(proc.stderr)
    proc.check_returncode()
    native = {}
    for line in proc.stdout.splitlines():
        name,*parts = line.split()
        native[name] = {k:int(v) for k,v in (part.split("=") for part in parts)}
    references = {}
    cases = {"single":([10000,250,10000],[200,1,250]),
             "cumulative":([300,10000,10000,250],[200,250,300,1])}
    for name,(stacks,actions) in cases.items():
        hand = Hand([f"p{i}" for i in range(len(stacks))],stacks)
        for action in actions:
            hand.apply(Decision(action,{}))
        obs = hand.observation()
        references[name] = {"actor":obs.actor,"call":obs.legal.call_cost,
                            "min":obs.legal.min_raise_to or 0,"max":obs.legal.max_raise_to or 0}
    report = {"status":"native mechanics disagreement" if any(native[k]!=v for k,v in references.items()) else "probe agrees",
        "native":native,"pokerkit_reference":references,"manifest":manifest,
        "elapsed_seconds_including_build":time.perf_counter()-start,
        "cargo_lock_sha256":hashlib.sha256((crate/"Cargo.lock").read_bytes()).hexdigest(),
        "wrapper_sha256":hashlib.sha256((crate/"src/main.rs").read_bytes()).hexdigest(),
        "played_evaluation_hands":0,
        "limitations":"Two targeted betting sequences only; no full-engine, ranking, training, policy strength or bridge validation"}
    (out/"report.json").write_text(json.dumps(report,indent=2)+"\n")
    return report


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",required=True)
    parser.add_argument("--out",required=True)
    args=parser.parse_args()
    print(json.dumps(run(args.source,args.out),indent=2))
