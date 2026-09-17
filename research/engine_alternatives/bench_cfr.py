"""Does training in advance get anywhere on this machine, unabstracted?

Runs external-sampling Monte Carlo CFR (OpenSpiel's own implementation) on
`universal_poker` for a fixed number of seconds per configuration, and reports
how many distinct situations ("information sets") it has stored and how many
brand-new ones each recent round still turns up. A solver that is converging
stops finding new situations; one that never stops has not seen the game once.

No card abstraction is used: the solver stores every situation it meets. The
betting abstraction is `fcpa` (fold / call / pot / all-in) for every row -
tabular CFR against `fullgame`'s 19,803 raise-to amounts is not attemptable at
all, which is itself worth knowing.

Usage:  python bench_cfr.py [seconds_per_configuration]

Research artefact. Not the bot, not on the bot's import path.
"""

import sys
import time

import numpy as np
import pyspiel
from open_spiel.python.algorithms import external_sampling_mccfr as mccfr

SECONDS = float(sys.argv[1]) if len(sys.argv) > 1 else 45.0
SEED = 20260915

CONFIGS = [
    ("6 players, 52 cards, 200bb", 6, 13, 20000, 4),
    ("6 players, 52 cards, 20bb", 6, 13, 2000, 4),
    ("6 players, 52 cards, 10bb", 6, 13, 1000, 4),
    ("6 players, 24 cards, 10bb", 6, 6, 1000, 4),
    ("6 players, 20 cards, 10bb", 6, 5, 1000, 4),
    ("3 players, 52 cards, 10bb", 3, 13, 1000, 4),
    ("6 players, 52 cards, 10bb, preflop only", 6, 13, 1000, 1),
]


def build(players, ranks, stack, rounds):
    blinds = " ".join(["50", "100"] + ["0"] * (players - 2))
    stacks = " ".join([str(stack)] * players)
    first = ("3 1 1 1" if players > 2 else "2 1 1 1")[: 2 * rounds - 1]
    board = "0 3 1 1"[: 2 * rounds - 1]
    return pyspiel.load_game("universal_poker", {
        "betting": "nolimit",
        "numPlayers": players,
        "numRounds": rounds,
        "blind": blinds,
        "firstPlayer": first,
        "numSuits": 4,
        "numRanks": ranks,
        "numHoleCards": 2,
        "numBoardCards": board,
        "stack": stacks,
        "bettingAbstraction": "fcpa",
    })


def growth(marks, found, rounds, upto=None):
    """New situations per round over the last quarter, at or before `upto`.

    With `upto` set, this reads the run as if it had been stopped at that round
    count, which is what makes two configurations comparable: a configuration
    that runs faster gets more rounds in the same seconds, and more rounds by
    itself means more situations.
    """
    usable = [m for m in marks if upto is None or m[0] <= upto]
    if len(usable) < 2:
        return float("nan"), float("nan"), float("nan")
    end_rounds, end_found = (rounds, found) if upto is None else usable[-1]
    r0, f0 = usable[len(usable) // 4 * 3]
    return (end_found - f0) / max(end_rounds - r0, 1), end_rounds, end_found


def run(label, players, ranks, stack, rounds_cfg, seconds):
    np.random.seed(SEED)
    game = build(players, ranks, stack, rounds_cfg)
    solver = mccfr.ExternalSamplingSolver(game)
    rounds = 0
    marks = []
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < seconds:
        solver.iteration()
        rounds += 1
        if rounds % 100 == 0:
            marks.append((rounds, len(solver._infostates)))
    dt = time.perf_counter() - t0
    found = len(solver._infostates)
    new_per_round, _, _ = growth(marks, found, rounds)
    print(f"{label:40s} rounds={rounds:7d} situations={found:9d} "
          f"still-new per round (last quarter)={new_per_round:6.1f} "
          f"[{dt:.0f}s]")
    return {"label": label, "rounds": rounds, "found": found,
            "new_per_round": new_per_round, "marks": marks}


if __name__ == "__main__":
    print(f"external-sampling MCCFR, no card abstraction, bettingAbstraction=fcpa, "
          f"numpy seed={SEED}, {SECONDS:.0f}s per configuration")
    results = [run(label, players, ranks, stack, rounds_cfg, SECONDS)
               for label, players, ranks, stack, rounds_cfg in CONFIGS]

    matched = min(r["marks"][-1][0] for r in results if r["marks"])
    print()
    print(f"the same table read at a matched round count of {matched:,} rounds "
          f"- the most every configuration above")
    print("reached - so that a configuration is not credited with more "
          "situations merely for running more rounds:")
    for r in results:
        rate, end_rounds, end_found = growth(r["marks"], r["found"],
                                             r["rounds"], upto=matched)
        print(f"{r['label']:40s} rounds={end_rounds:7.0f} "
              f"situations={end_found:9.0f} "
              f"still-new per round (last quarter)={rate:6.1f}")
