"""Record accepted prohibited raises in legacy PokerKit and their rejection.

Rulebook reference: TDA 2024 rule 47, especially examples 1-A and 3-A.
This test uses both the host interface and the native State legality check.
"""
import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pokerbot.engine import Decision, Hand, LegacyPokerKitHand


def probe():
    cases = [
        ("limp-short-allin", [1000,180,10000], [1,1,180], 280),
        ("later-caller-cumulative", [300,10000,10000,250,10000], [200,250,1,300,1,1], 400),
        ("checked-short-opening", [10000,150,10000], [1,1,1,1,150,1], 250),
    ]
    results = []
    for name, stacks, actions, attempted in cases:
        row = {"name":name,"stacks":stacks,"actions":actions,"prohibited_whole_hand_raise_to":attempted}
        for label, cls in (("unpatched", LegacyPokerKitHand), ("corrected", Hand)):
            hand = cls([str(i) for i in range(len(stacks))], stacks, seed=190916)
            for action in actions:
                hand.apply(Decision(action, {}))
            obs = hand.observation()
            actor = hand.state.actor_index
            prior = obs.players[obs.actor].contribution - hand.state.bets[actor]
            native_legal = hand.state.can_complete_bet_or_raise_to(attempted-prior)
            try:
                hand.apply(Decision(attempted, {}))
                accepted = True
            except ValueError:
                accepted = False
            row[label] = {"engine":hand.engine_id,"actor":obs.actor,"call":obs.legal.call_cost,
                          "min":obs.legal.min_raise_to,"max":obs.legal.max_raise_to,
                          "native_state_accepts":native_legal,"applied":accepted}
            assert accepted == native_legal == (label == "unpatched")
        results.append(row)
    paths = [Path(__file__),ROOT/"pokerbot/engine.py",ROOT/"pokerbot/pokerkit_rules.py",ROOT/"pokerbot/benchmark.py"]
    return {"status":"legacy defects reproduced; corrected engine rejects all three",
        "reference":"https://www.pokertda.com/view-poker-tda-rules/",
        "python":platform.python_version(),"pokerkit":version("pokerkit"),
        "source_sha256":{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        "cases":results,"played_evaluation_hands":0,
        "limitations":"Targeted fixtures only; class-app rules have not been observed"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = probe()
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2)+"\n")
    print(result["status"])
