"""How big is one hand's swing, and can a result be bounded at all?

Two modes, both at a 6-player 52-card no-limit table, 200 big blinds deep,
blinds 50/100, betting abstraction `fcpa`:

  variance  every seat plays uniformly at random; reports the spread of one
            seat's per-hand chip result, which is what sets how many hands any
            claim about play strength needs.

  headtohead  seat 0 uses chooser.choose with a 250 ms budget, the other five
            play uniformly at random; reports seat 0's average per-hand result
            with a 95% confidence interval.

Usage:  python bench_play.py variance   [hands]
        python bench_play.py headtohead [seconds]

Research artefact. Not the bot, not on the bot's import path.
"""

import math
import random
import statistics
import sys
import time

import pyspiel

from chooser import GAME_6MAX, BIG_BLIND, candidates, choose

SEED = 20260915


def report(label, xs, extra=""):
    n = len(xs)
    mean = statistics.fmean(xs)
    sd = statistics.stdev(xs)
    half = 1.96 * sd / math.sqrt(n)
    print(f"{label}: n={n} hands  mean={mean:+.2f} bb/hand  sd={sd:.1f} bb  "
          f"95% CI = {mean - half:+.2f} .. {mean + half:+.2f} bb/hand "
          f"(half-width {half:.2f}) {extra}")
    need = (1.96 * sd) ** 2
    print(f"    hands needed for a half-width of 1 bb/hand at this spread: {need:,.0f}")


def variance(hands):
    game = pyspiel.load_game(GAME_6MAX.format(abstraction="fcpa"))
    rng = random.Random(SEED)
    xs = []
    t0 = time.perf_counter()
    for _ in range(hands):
        state = game.new_initial_state()
        while not state.is_terminal():
            legal = state.legal_actions()
            if state.is_chance_node():
                state.apply_action(legal[rng.randrange(len(legal))])
            else:
                menu = candidates(legal)
                state.apply_action(menu[rng.randrange(len(menu))])
        xs.append(state.returns()[0] / BIG_BLIND)
    dt = time.perf_counter() - t0
    report("random vs random, seat 0", xs, f"[{dt:.1f}s, seed={SEED}]")


def headtohead(seconds, budget=0.25):
    game = pyspiel.load_game(GAME_6MAX.format(abstraction="fcpa"))
    rng = random.Random(SEED)
    xs, decisions = [], 0
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < seconds:
        state = game.new_initial_state()
        while not state.is_terminal():
            legal = state.legal_actions()
            if state.is_chance_node():
                state.apply_action(legal[rng.randrange(len(legal))])
            elif state.current_player() == 0:
                action, _ = choose(state, budget, rng)
                state.apply_action(action)
                decisions += 1
            else:
                menu = candidates(legal)
                state.apply_action(menu[rng.randrange(len(menu))])
        xs.append(state.returns()[0] / BIG_BLIND)
    dt = time.perf_counter() - t0
    report(f"chooser (seat 0, {budget}s/decision, fcpa) vs 5 random", xs,
           f"[{dt:.0f}s, {decisions} decisions, seed={SEED}]")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "variance"
    arg = float(sys.argv[2]) if len(sys.argv) > 2 else None
    if mode == "variance":
        variance(int(arg or 100000))
    else:
        headtohead(arg or 900.0)
