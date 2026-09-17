"""The decision-time chooser measured in ENGINE_ALTERNATIVES.md.

What it does, in one sentence: for each of a handful of candidate moves, guess
the opponents' cards, play the rest of the hand out at random many times, and
take the move whose average chip result was highest.

Exact conditions it was measured under:

* Game: OpenSpiel `universal_poker`, 52 cards, no-limit, 6 seats, 20,000-chip
  stacks (200 big blinds), blinds 50/100, four betting rounds.
* Betting abstraction: chosen per run. `fullgame` makes every whole-chip
  raise-to amount legal (19,803 of them at the first decision); `fcpa` offers
  fold / call / pot-sized bet / all-in only.
* Candidate moves: never all 19,803. The menu is built mechanically from the
  engine's own legal list - fold, call, the smallest legal raise, then that
  raise doubled repeatedly, then all-in - and is capped at `MAX_CANDIDATES`.
  Nothing poker-specific picks them; they are the legal range's endpoints and
  powers of two in between.
* Rollout policy: every seat, including ours, plays uniformly at random over
  that same mechanically built menu until the hand ends. It is a uniform
  random policy, not a poker strategy.
* Unseen cards: `resample_opponents` redraws the other seats' hole cards once
  per rollout, because OpenSpiel's own routine for that crashes above two
  players.
* Time budget: enforced by a wall-clock deadline checked before every rollout,
  so the chooser stops at the budget rather than after a fixed count.

Reported with each decision: the number of rollouts each candidate got, its
mean chip result, and the standard error of that mean, so a margin between two
candidates can be read against its own noise.

Research artefact. Not the bot, not on the bot's import path.
"""

import math
import random
import statistics
import sys
import time

from resample_opponents import card_positions, hidden_positions, resample_opponents

GAME_6MAX = (
    "universal_poker(betting=nolimit,numPlayers=6,numRounds=4,"
    "blind=50 100 0 0 0 0,firstPlayer=3 1 1 1,numSuits=4,numRanks=13,"
    "numHoleCards=2,numBoardCards=0 3 1 1,"
    "stack=20000 20000 20000 20000 20000 20000,"
    "bettingAbstraction={abstraction})"
)
MAX_CANDIDATES = 8
BIG_BLIND = 100


def candidates(legal):
    """A small menu built from the engine's legal list, mechanically.

    fold and call if legal, the smallest legal raise, that raise doubled until
    it runs past the largest, and the largest (all-in). At `fcpa` the legal
    list is already this short and comes back unchanged.
    """
    if len(legal) <= MAX_CANDIDATES:
        return list(legal)
    small = [a for a in legal if a <= 1]
    raises = [a for a in legal if a > 1]
    lo, hi = raises[0], raises[-1]
    menu, step = [], lo
    while step < hi and len(menu) < MAX_CANDIDATES - len(small) - 1:
        menu.append(step)
        step *= 2
    return small + menu + [hi]


def rollout(state, rng):
    """Play a hand out to the end, every seat uniform over the same menu."""
    while not state.is_terminal():
        if state.is_chance_node():
            legal = state.legal_actions()
            state.apply_action(legal[rng.randrange(len(legal))])
        else:
            menu = candidates(state.legal_actions())
            state.apply_action(menu[rng.randrange(len(menu))])
    return state.returns()


def choose(state, budget_s=0.25, rng=random):
    """Pick a move for the seat to act. Returns (action, per-candidate stats)."""
    player = state.current_player()
    menu = candidates(state.legal_actions())
    hidden = hidden_positions(state, player)
    dealt = card_positions(state)
    results = {a: [] for a in menu}
    deadline = time.perf_counter() + budget_s
    i = 0
    while time.perf_counter() < deadline:
        action = menu[i % len(menu)]
        world = resample_opponents(state, player, hidden, dealt, rng=rng)
        world.apply_action(action)
        results[action].append(rollout(world, rng)[player])
        i += 1
    stats = {}
    for action, xs in results.items():
        mean = sum(xs) / len(xs) if xs else float("-inf")
        sd = statistics.stdev(xs) if len(xs) > 1 else float("nan")
        stats[action] = (len(xs), mean, sd / math.sqrt(len(xs)) if len(xs) > 1 else float("nan"))
    best = max(menu, key=lambda a: stats[a][1])
    return best, stats


def deal_and_bet(game, rng):
    """A fresh hand dealt to the first decision point."""
    state = game.new_initial_state()
    while state.is_chance_node():
        legal = state.legal_actions()
        state.apply_action(legal[rng.randrange(len(legal))])
    return state


def _main():
    import pyspiel

    abstraction = sys.argv[1] if len(sys.argv) > 1 else "fullgame"
    decisions = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    budget = float(sys.argv[3]) if len(sys.argv) > 3 else 0.25
    game = pyspiel.load_game(GAME_6MAX.format(abstraction=abstraction))
    rng = random.Random(20260915)
    print(f"abstraction={abstraction} budget={budget}s decisions={decisions} "
          f"seed=20260915 6 players, 52 cards, 200bb, blinds 50/100")
    totals = []
    for d in range(decisions):
        state = deal_and_bet(game, rng)
        legal = state.legal_actions()
        t0 = time.perf_counter()
        best, stats = choose(state, budget, rng)
        dt = time.perf_counter() - t0
        n = sum(s[0] for s in stats.values())
        totals.append(n)
        print(f"decision {d}: legal={len(legal)} candidates={len(stats)} "
              f"rollouts={n} in {dt:.3f}s chose {state.action_to_string(state.current_player(), best)}")
        for a, (na, mean, sem) in sorted(stats.items()):
            print(f"    {state.action_to_string(state.current_player(), a):>14s} "
                  f"n={na:5d} mean={mean / BIG_BLIND:+8.2f} bb  sem={sem / BIG_BLIND:6.2f} bb")
    print(f"rollouts per {budget}s decision: n={len(totals)} decisions, "
          f"min={min(totals)} max={max(totals)} mean={sum(totals) / len(totals):.0f}")


if __name__ == "__main__":
    _main()
