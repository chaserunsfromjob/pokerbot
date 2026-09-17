#!/usr/bin/env python3
"""Check which OpenSpiel decision-time pieces exist and import on this laptop.

`DECISION_LAYER_SEARCH.md` claims, for each way of choosing an action, what
OpenSpiel already ships. This program is the check behind those claims: it
imports each named module or class, and for `universal_poker` it also proves
the game's own Monte Carlo equity calculator runs and agrees with a known
figure (pocket aces against seven-deuce offsuit, about 88% heads-up).

    .venv/bin/python research/decision_layer/check_openspiel_modules.py

Prints one line per item: OK or FAILED with the exception.
"""
from __future__ import annotations

import importlib
import importlib.metadata
import json
import os
import subprocess
import sys

MODULES = [
    ("open_spiel.python.algorithms.ismcts", "Information Set MCTS, Python"),
    ("open_spiel.python.algorithms.mcts", "plain MCTS, Python"),
    ("open_spiel.python.algorithms.mcts_agent", "MCTS wrapped as an RL agent"),
    ("open_spiel.python.algorithms.best_response", "best response to a fixed policy"),
    ("open_spiel.python.algorithms.exploitability", "how exploitable a policy is"),
    ("open_spiel.python.algorithms.evaluate_bots", "play bots against each other"),
    ("open_spiel.python.bots.policy", "a fixed policy driven as a bot"),
    ("open_spiel.python.bots.uniform_random", "the random baseline bot"),
    ("open_spiel.python.policy", "the policy container the above take"),
]

ATTRS = [
    ("ISMCTSBot", "Information Set MCTS, C++ (the fast one)"),
    ("MCTSBot", "plain MCTS, C++"),
    ("RandomRolloutEvaluator", "leaf evaluator: play the rest out at random"),
    ("Evaluator", "the leaf-evaluator base class a blueprint would subclass"),
    ("ISMCTSFinalPolicyType", "how IS-MCTS turns visit counts into a move"),
]


def check_import(name: str) -> str:
    try:
        importlib.import_module(name)
        return "OK"
    except Exception as exc:  # noqa: BLE001 - reporting is the point
        return f"FAILED: {type(exc).__name__}: {exc}"


def main() -> int:
    import pyspiel

    print(f"open_spiel {importlib.metadata.version('open_spiel')}, "
          f"python {sys.version.split()[0]}, load1 {os.getloadavg()[0]:.2f}")
    print()
    for name, what in MODULES:
        print(f"{check_import(name):<60} {name}  ({what})")
    for attr, what in ATTRS:
        status = "OK" if hasattr(pyspiel, attr) else "MISSING"
        print(f"{status:<60} pyspiel.{attr}  ({what})")

    # universal_poker's own Monte Carlo equity, and a known answer for it.
    game = pyspiel.load_game(
        "universal_poker",
        {"numPlayers": 2, "numRounds": 4, "blind": "100 50", "firstPlayer": "2 1 1 1",
         "numSuits": 4, "numRanks": 13, "numHoleCards": 2, "numBoardCards": "0 3 1 1",
         "stack": "20000 20000", "bettingAbstraction": "fcpa", "calcOddsNumSims": 100000})
    state = game.new_initial_state()
    for card in (51, 50, 21, 0):    # As Ah to seat 0, 7d 2c to seat 1
        state.apply_action(card)
    odds = json.loads(state.to_json())["odds"]
    # A sanity band, chosen here; no published equity table is cited for it.
    # This says the calculator is wired up and answering, not that it is right
    # to three decimals against an external source.
    ok = 0.86 <= odds[0] <= 0.90
    print(f"{'OK' if ok else 'FAILED':<60} universal_poker calcOddsNumSims: "
          f"AA vs 72o = {odds[0]:.3f} win, {odds[1]:.3f} tie "
          f"(engine's own answer; sanity band 0.86-0.90 win, no published figure cited)")

    # The one thing that does not work: world sampling above two players.
    child = (
        "import pyspiel, random\n"
        "import sys; sys.path.insert(0, %r)\n"
        "from bench_decision_layer import build_game, deal\n"
        "g = build_game(3); s = deal(g.new_initial_state(), random.Random(1))\n"
        "s.resample_from_infostate(s.current_player(), lambda: random.random())\n"
        "print('returned')\n" % os.path.dirname(os.path.abspath(__file__))
    )
    proc = subprocess.run([sys.executable, "-c", child], capture_output=True, text=True)
    verdict = ("OK" if proc.returncode == 0 else
               f"CRASHES: exit {proc.returncode}" + (" (SIGSEGV)" if proc.returncode == -11 else ""))
    print(f"{verdict:<60} universal_poker.resample_from_infostate at 3 players "
          "(IS-MCTS needs it; universal_poker.cc:1111 returns an empty handle above 2 players)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
