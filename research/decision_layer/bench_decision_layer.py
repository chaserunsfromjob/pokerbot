#!/usr/bin/env python3
"""Measure real-time decision layers on OpenSpiel `universal_poker`.

Backs every measured figure in `DECISION_LAYER_SEARCH.md`. Nothing here is the
bot: it is a stopwatch wrapped around four ways of choosing an action at the
table, run at 2, 3 and 6 players.

The four candidates, each under a wall-clock budget:

* `equity`      - Monte Carlo equity against sampled opponent holdings,
                  compared with the pot odds. The equity itself comes from
                  `universal_poker`'s own simulator (the `calcOddsNumSims`
                  game parameter, read out of `state.to_json()["odds"]`), so
                  no hand is evaluated by code written here.
* `ismcts`      - OpenSpiel's shipped Information Set Monte Carlo Tree Search,
                  `pyspiel.ISMCTSBot`, with `pyspiel.RandomRolloutEvaluator`.
* `dls`         - depth-limited search: the candidate action is played, the
                  rest of the current betting round is played out, and at that
                  leaf one of four biased continuation strategies is drawn and
                  played to showdown by the engine (the Pluribus shape).
* `dls_model`   - the same search with the continuation strategies of each
                  seat biased by that seat's fold-to-bet rate and aggression,
                  i.e. the numbers `OPPONENT_MODEL_DESIGN.md` tracks.

What is counted as a play-out:

* `equity`: one simulated run-out of the board inside the engine's simulator.
  One sampled opponent holding costs `--odds-sims` of them.
* `ismcts`: one IS-MCTS simulation (the bot's own unit).
* `dls` / `dls_model`: one continuation played to showdown.

Every figure is printed with the 1-minute load average taken from the same
`uptime` field the operator would read, immediately beside it, because this
laptop is shared. Above a load of about 4 the timings stop meaning anything.

Run from the top of the repository, e.g.:

    .venv/bin/python research/decision_layer/bench_decision_layer.py \
        --seats 2 3 6 --budgets 0.25 2.0 --repeats 2 --decisions 6

`ismcts` is run in a child process on purpose: OpenSpiel 2.0.2 segfaults when
IS-MCTS asks `universal_poker` for a world sample at more than two players, and
a segfault in-process would take the whole benchmark down. The child's exit
status is reported as the measurement.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import random
import resource
import shlex
import statistics
import subprocess
import sys
import time

import pyspiel

# The top of the repository, so that `import pokerbot` works whatever the
# working directory is -- this script is run by its path, and the IS-MCTS
# child process runs from `research/decision_layer/`.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from pokerbot.equity_rule import with_odds  # noqa: E402  (after the path fix)
from pokerbot.table import TableConfig, game_string  # noqa: E402

CARD_SUITS = "cdhs"
CARD_RANKS = "23456789TJQKA"
# fcpa: fold / call / pot-sized bet / all-in, the four-move menu.
FOLD, CALL = 0, 1

#: The benchmark's own stack depth, one per seat: 200 big blinds of the table's
#: 100-chip big blind. The blinds and the acting order are *not* the
#: benchmark's own; they come from the table, below.
BENCH_STACK = 20000


def load_avg() -> float:
    """1-minute load average - the same number `uptime` prints first."""
    return os.getloadavg()[0]


def peak_rss_mib() -> float:
    """Peak resident set size of this process, in MiB (macOS reports bytes)."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)


def build_game(seats: int, abstraction: str = "fcpa", odds_sims: int = 0):
    """The bot's own table, 200 big blinds deep, `seats` players.

    The game definition is asked of `pokerbot.table.game_string`, which is the
    single place the table the bot plays on is written down. That is the
    point: blinds posted in the wrong seat order, or a heads-up acting order
    the other way round, would still deal and still time, and the stopwatch
    would be held over a game the bot never sits in.

    Three things here are the benchmark's own and are passed in: the stack
    depth, the betting abstraction (this benchmark compares `fcpa` with
    `fullgame`, where the table always plays `fchpa`), and the engine's equity
    simulator count, which the table never asks for. The first two are
    arguments to `game_string`; the third is added afterwards by
    `pokerbot.equity_rule.with_odds`, the project's one guarded way to switch
    the engine's equity calculator on, which refuses a game definition that
    already sets `calcOddsNumSims`.
    """
    config = TableConfig(seats=seats, stacks=(BENCH_STACK,) * seats)
    return pyspiel.load_game(
        with_odds(
            game_string(config, betting_abstraction=abstraction),
            odds_sims,
        )
    )


def deal(state, rng: random.Random):
    while state.is_chance_node():
        outcomes = [o for o, _ in state.chance_outcomes()]
        state.apply_action(rng.choice(outcomes))
    return state


def decision_points(game, rng: random.Random, wanted: int):
    """Collect real decision points by playing random hands in the engine."""
    points = []
    while len(points) < wanted:
        state = game.new_initial_state()
        deal(state, rng)
        while not state.is_terminal():
            if state.is_chance_node():
                deal(state, rng)
                continue
            points.append(state.clone())
            if len(points) >= wanted:
                break
            legal = state.legal_actions()
            # Bias towards calling so hands reach later streets rather than
            # ending preflop; this only shapes which decision points we time.
            action = CALL if CALL in legal and rng.random() < 0.75 else rng.choice(legal)
            state.apply_action(action)
    return points


def determinize(game, state, player: int, rng: random.Random):
    """A full-information world consistent with `player`'s information set.

    Replays the hand's history, keeping the board and `player`'s own hole
    cards and dealing every other seat a fresh hand out of the unseen deck.
    OpenSpiel's own `resample_from_infostate` does this, but it crashes above
    two players (see the module docstring), so the card bookkeeping is done
    here - which `CLAUDE.md` allows, it being combinatorics and not judgment.
    """
    seats = game.num_players()
    history = state.history()
    hole_slots = 2 * seats
    mine = {i: history[i] for i in range(hole_slots) if _slot_owner(history, state, i, seats) == player}
    seen = set(history[hole_slots:]) | set(mine.values())
    deck = [c for c in range(52) if c not in seen]
    rng.shuffle(deck)
    fresh = iter(deck)
    replay = []
    for i, action in enumerate(history):
        if i < hole_slots and i not in mine:
            replay.append(next(fresh))
        else:
            replay.append(action)
    world = game.new_initial_state()
    for action in replay:
        world.apply_action(action)
    return world


_SLOT_OWNER_CACHE: dict[int, list[int]] = {}


def _slot_owner(history, state, slot: int, seats: int) -> int:
    """Which seat the `slot`-th hole-card deal belongs to.

    Worked out once per seat count by dealing a probe hand and reading each
    seat's private cards back out of the engine, so nothing here assumes a
    dealing order.
    """
    if seats not in _SLOT_OWNER_CACHE:
        game = build_game(seats)
        probe = game.new_initial_state()
        cards = list(range(2 * seats))
        for card in cards:
            probe.apply_action(card)
        owners = []
        privates = [probe.information_state_string(p).split("[Private: ")[1].split("]")[0] for p in range(seats)]
        for card in cards:
            name = CARD_RANKS[card // 4] + CARD_SUITS[card % 4]
            owners.append(next(p for p in range(seats) if name in privates[p]))
        _SLOT_OWNER_CACHE[seats] = owners
    return _SLOT_OWNER_CACHE[seats][slot]


def pot_and_call(state, player: int) -> tuple[float, float]:
    """Chips in the middle, and chips this seat must put in to continue."""
    blob = json.loads(state.to_json())
    contributions = blob["player_contributions"]
    return float(blob["pot_size"]), float(max(contributions) - contributions[player])


# ---------------------------------------------------------------- option 1
def decide_equity(game, state, player, deadline, rng, odds_sims):
    """Monte Carlo equity against sampled holdings, versus the pot odds."""
    equities, playouts = [], 0
    while time.perf_counter() < deadline:
        world = determinize(game, state, player, rng)
        odds = json.loads(world.to_json())["odds"]
        equities.append(odds[2 * player] + 0.5 * odds[2 * player + 1])
        playouts += odds_sims
    equity = statistics.fmean(equities) if equities else 0.0
    pot, to_call = pot_and_call(state, player)
    legal = state.legal_actions()
    if to_call <= 0:
        action = 2 if equity > 0.6 and 2 in legal else CALL
    else:
        needed = to_call / (pot + to_call)
        if equity < needed:
            action = FOLD if FOLD in legal else CALL
        elif equity > needed + 0.25 and 2 in legal:
            action = 2
        else:
            action = CALL
    return action, playouts, len(equities)


# ---------------------------------------------------------------- options 3/4
CONTINUATIONS = (
    {"fold": 0.45, "call": 0.50, "raise": 0.05},   # give-up biased
    {"fold": 0.10, "call": 0.85, "raise": 0.05},   # call-down biased
    {"fold": 0.10, "call": 0.55, "raise": 0.35},   # aggressive
    {"fold": 0.05, "call": 0.35, "raise": 0.60},   # very aggressive
)

# Stand-in opponent model: one (fold-to-bet, aggression) pair per seat, of the
# kind `OPPONENT_MODEL_DESIGN.md` Tier A/B produces. Values are plausible, not
# measured from play; only the *cost* of consulting them is measured here.
def seat_models(seats: int) -> list[dict]:
    presets = [
        {"fold_to_bet": 0.62, "aggression": 0.18},
        {"fold_to_bet": 0.28, "aggression": 0.55},
        {"fold_to_bet": 0.45, "aggression": 0.30},
        {"fold_to_bet": 0.70, "aggression": 0.12},
        {"fold_to_bet": 0.35, "aggression": 0.45},
        {"fold_to_bet": 0.50, "aggression": 0.25},
        {"fold_to_bet": 0.55, "aggression": 0.22},
        {"fold_to_bet": 0.40, "aggression": 0.38},
        {"fold_to_bet": 0.48, "aggression": 0.28},
    ]
    return presets[:seats]


def _profile_for(seat, models, rng):
    if models is None:
        return CONTINUATIONS[rng.randrange(len(CONTINUATIONS))]
    m = models[seat]
    return {"fold": m["fold_to_bet"], "call": max(0.0, 1.0 - m["fold_to_bet"] - m["aggression"]),
            "raise": m["aggression"]}


def _act(state, profile, rng):
    legal = state.legal_actions()
    roll = rng.random()
    if roll < profile["fold"] and FOLD in legal:
        return FOLD
    if roll < profile["fold"] + profile["raise"]:
        for a in (2, 3):
            if a in legal:
                return a
    return CALL if CALL in legal else rng.choice(legal)


def _round_of(state) -> int:
    return int(json.loads(state.to_json())["acpc_state"].count("/"))


MAX_CANDIDATES = 8


def candidates(state, rng):
    """The moves the search weighs.

    Under `fcpa` that is all four. Under `fullgame` - real no-limit sizing,
    tens of thousands of legal raise amounts at the first decision - it is a
    sample of `MAX_CANDIDATES` of them, the same shortcut
    `ENGINE_ALTERNATIVES.md` took, because weighing all of them is hopeless.
    """
    legal = state.legal_actions()
    if len(legal) <= MAX_CANDIDATES:
        return legal
    keep = {legal[0], legal[1], legal[-1]}
    while len(keep) < MAX_CANDIDATES:
        keep.add(rng.choice(legal))
    return sorted(keep)


def decide_dls(game, state, player, deadline, rng, models):
    """Depth-limited search: leaves resolved by biased continuation strategies.

    The depth limit is the end of the current betting round. Past it the hand
    is finished by one of four continuation strategies, drawn per seat, which
    is what a blueprint would supply. Every card, every legal action and every
    payoff comes from the engine.
    """
    legal = candidates(state, rng)
    totals = {a: 0.0 for a in legal}
    counts = {a: 0 for a in legal}
    playouts = 0
    while time.perf_counter() < deadline:
        for action in legal:
            if time.perf_counter() >= deadline:
                break
            world = determinize(game, state, player, rng)
            world.apply_action(action)
            start_round = _round_of(world)
            depth_reached = False
            profiles = {}
            while not world.is_terminal():
                if world.is_chance_node():
                    outcomes = [o for o, _ in world.chance_outcomes()]
                    world.apply_action(rng.choice(outcomes))
                    continue
                seat = world.current_player()
                if not depth_reached and _round_of(world) > start_round:
                    depth_reached = True     # the depth limit: leaf reached
                if seat not in profiles or depth_reached:
                    profiles[seat] = _profile_for(seat, models, rng)
                world.apply_action(_act(world, profiles[seat], rng))
            totals[action] += world.returns()[player]
            counts[action] += 1
            playouts += 1
    best = max(legal, key=lambda a: (totals[a] / counts[a]) if counts[a] else float("-inf"))
    return best, playouts, sum(counts.values())


# ---------------------------------------------------------------- option 2
ISMCTS_CHILD = r"""
import json, os, sys, time, random
sys.path.insert(0, "@REPO@")
import pyspiel
from bench_decision_layer import build_game, decision_points, load_avg, peak_rss_mib
seats, budget, decisions, seed, probe = (int(sys.argv[1]), float(sys.argv[2]),
                                         int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]))
rng = random.Random(seed)
game = build_game(seats)
points = decision_points(game, rng, decisions)
ev = pyspiel.RandomRolloutEvaluator(1, seed)


def bot(max_sims, wall):
    return pyspiel.ISMCTSBot(seed, ev, 2.0, max_sims, -1,
                             pyspiel.ISMCTSFinalPolicyType.MAX_VISIT_COUNT,
                             False, False, wall)


lat = []
for st in points:
    t0 = time.perf_counter(); bot(10**9, budget).step(st); lat.append(time.perf_counter() - t0)
# Second pass with a fixed simulation count and no deadline, so that
# simulations per second - and so play-outs inside a budget - can be stated.
rates = []
for st in points:
    t0 = time.perf_counter(); bot(probe, -1.0).step(st)
    rates.append(probe / (time.perf_counter() - t0))
print(json.dumps({"latencies": lat, "sims_per_s": rates,
                  "load": load_avg(), "rss_mib": peak_rss_mib()}))
"""


def run_ismcts(seats, budget, decisions, seed, repo, probe=400):
    code = ISMCTS_CHILD.replace("@REPO@", repo)
    proc = subprocess.run([sys.executable, "-c", code, str(seats), str(budget),
                           str(decisions), str(seed), str(probe)],
                          capture_output=True, text=True, cwd=repo)
    if proc.returncode != 0:
        return {"failed": True, "returncode": proc.returncode,
                "stderr": proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else ""}
    out = json.loads(proc.stdout.strip().splitlines()[-1])
    out["failed"] = False
    return out


# ---------------------------------------------------------------- harness
def run_option(name, seats, budget, decisions, seed, odds_sims, abstraction):
    rng = random.Random(seed)
    game = build_game(seats, abstraction, odds_sims if name == "equity" else 0)
    points = decision_points(game, rng, decisions)
    latencies, playouts, worlds = [], [], []
    models = seat_models(seats) if name == "dls_model" else None
    for state in points:
        player = state.current_player()
        t0 = time.perf_counter()
        deadline = t0 + budget
        if name == "equity":
            _, po, w = decide_equity(game, state, player, deadline, rng, odds_sims)
        else:
            _, po, w = decide_dls(game, state, player, deadline, rng, models)
        latencies.append(time.perf_counter() - t0)
        playouts.append(po)
        worlds.append(w)
    return {"latencies": latencies, "playouts": playouts, "worlds": worlds,
            "load": load_avg(), "rss_mib": peak_rss_mib(), "failed": False}


def summarise(values):
    return min(values), statistics.median(values), max(values)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seats", type=int, nargs="+", default=[2, 3, 6])
    ap.add_argument("--budgets", type=float, nargs="+", default=[0.25, 2.0])
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--decisions", type=int, default=5)
    ap.add_argument("--odds-sims", type=int, default=200)
    ap.add_argument("--abstraction", default="fcpa", choices=["fcpa", "fullgame"])
    ap.add_argument("--options", nargs="+", default=["equity", "ismcts", "dls", "dls_model"])
    ap.add_argument("--seed", type=int, default=20260916)
    args = ap.parse_args()

    repo = os.path.dirname(os.path.abspath(__file__))
    version = importlib.metadata.version("open_spiel")
    print(f"# bench_decision_layer, open_spiel {version}, python {sys.version.split()[0]}, "
          f"betting={args.abstraction}, odds-sims={args.odds_sims}")
    print(f"# started {time.strftime('%Y-%m-%dT%H:%M:%S%z')}, load1 at start {load_avg():.2f}")
    # The full command line, so a raw file says on its face what produced it.
    print(f"# argv {' '.join(shlex.quote(a) for a in sys.argv)}")
    print()
    header = ("option", "seats", "budget_s", "rep", "load1", "latency_s min/med/max",
              "playouts/decision min/med/max", "worlds/decision med", "dec/s", "peak_rss_MiB")
    print(" | ".join(header))
    for option in args.options:
        for seats in args.seats:
            for budget in args.budgets:
                for rep in range(args.repeats):
                    seed = args.seed + 1000 * rep + seats
                    if option == "ismcts":
                        res = run_ismcts(seats, budget, args.decisions, seed, repo)
                        if res["failed"]:
                            print(f"ismcts | {seats} | {budget} | {rep} | {load_avg():.2f} | "
                                  f"CRASHED rc={res['returncode']} {res['stderr']}")
                            continue
                        lat = res["latencies"]
                        rate = res["sims_per_s"]
                        po = [r * budget for r in rate]
                        print(f"ismcts | {seats} | {budget} | {rep} | {res['load']:.2f} | "
                              f"{min(lat):.3f}/{statistics.median(lat):.3f}/{max(lat):.3f} | "
                              f"{int(min(po))}/{int(statistics.median(po))}/{int(max(po))} | "
                              f"- | {1/statistics.fmean(lat):.2f} | {res['rss_mib']:.0f}")
                        continue
                    res = run_option(option, seats, budget, args.decisions, seed,
                                     args.odds_sims, args.abstraction)
                    lat, po, w = res["latencies"], res["playouts"], res["worlds"]
                    print(f"{option} | {seats} | {budget} | {rep} | {res['load']:.2f} | "
                          f"{min(lat):.3f}/{statistics.median(lat):.3f}/{max(lat):.3f} | "
                          f"{min(po)}/{int(statistics.median(po))}/{max(po)} | "
                          f"{int(statistics.median(w))} | {1/statistics.fmean(lat):.2f} | {res['rss_mib']:.0f}")
                    sys.stdout.flush()
    print()
    print(f"# finished {time.strftime('%Y-%m-%dT%H:%M:%S%z')}, load1 at end {load_avg():.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
