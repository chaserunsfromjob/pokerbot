"""Can PyPokerEngine be used for decision-time search, and if so how fast?

An earlier draft of `ENGINE_ALTERNATIVES.md` said PyPokerEngine "cannot be used
for decision-time search at all", on the grounds that it is a tournament runner
that calls you back on your turn. That was wrong, and this program is what
shows it wrong. `pypokerengine.api.emulator.Emulator` is a second, documented
entry point that does exactly the three things the claim said were impossible:

  * `generate_initial_game_state(players_info)` takes a **per-seat stack**, so
    seats can start with different amounts (checked below with 100 / 500 /
    20,000, the arrangement that forces side pots);
  * `generate_possible_actions(game_state)` answers "what is legal here?" for a
    position handed to it, without any callback;
  * `deepcopy_game_state(game_state)` clones a position and
    `run_until_round_finish` plays that clone out to the end - which is a
    play-out, the unit a decision-time search is built from.

So the reason to reject PyPokerEngine is not that it cannot search. It is that
it searches far too slowly to matter, and that it ships no solver. This program
measures the first half of that: how many complete play-outs from one mid-hand
position it manages per second, and therefore how many a 250 ms decision buys.

The play-out policy is the same four-move menu `bench_speed.py` gives the other
Python engines - fold, call, a pot-sized raise clamped into the legal range,
all-in - so the figure is comparable with the menu rows there.

Usage:  python pypoker_playouts.py [seconds]

Research artefact. Not the bot, not on the bot's import path.
"""

import random
import sys
import time

from pypokerengine.api.emulator import Emulator
from pypokerengine.players import BasePokerPlayer
from pypokerengine.utils.game_state_utils import deepcopy_game_state

SEED = 20260915
SB, BB = 50, 100
STACK = 20000
PLAYERS = 6
BUDGET_S = 0.25


class RandomPlayer(BasePokerPlayer):
    """Uniform random, with no poker judgment in it at all.

    `menu=True` offers fold / call / pot-sized raise / all-in, the four moves
    `bench_speed.py` gives the other Python engines. `menu=False` offers fold,
    call, and a raise-to amount drawn uniformly across the whole legal range,
    which is that file's real-sizing mode.
    """

    def __init__(self, rng, menu=True):
        self.rng = rng
        self.menu = menu
        self.decisions = 0

    def declare_action(self, valid_actions, hole_card, round_state):
        self.decisions += 1
        by_name = {a["action"]: a for a in valid_actions}
        moves = []
        if "fold" in by_name:
            moves.append(("fold", 0))
        if "call" in by_name:
            moves.append(("call", by_name["call"]["amount"]))
        raise_action = by_name.get("raise")
        if raise_action is not None:
            lo = raise_action["amount"]["min"]
            hi = raise_action["amount"]["max"]
            if lo != -1 and hi != -1:
                if self.menu:
                    pot = round_state["pot"]["main"]["amount"]
                    pot += sum(s["amount"] for s in round_state["pot"].get("side", []))
                    moves.append(("raise", min(max(pot, lo), hi)))
                    moves.append(("raise", hi))
                else:
                    moves.append(("raise", self.rng.randint(lo, hi)))
        if not moves:
            return "fold", 0
        return moves[self.rng.randrange(len(moves))]

    # The emulator calls these on a registered player; nothing here needs them.
    def receive_game_start_message(self, game_info):
        pass

    def receive_round_start_message(self, round_count, hole_card, seats):
        pass

    def receive_street_start_message(self, street, round_state):
        pass

    def receive_game_update_message(self, action, round_state):
        pass

    def receive_round_result_message(self, winners, hand_info, round_state):
        pass


def build(stacks, rng, menu=True):
    """An emulator and a game state dealt to the first decision of a hand."""
    emulator = Emulator()
    emulator.set_game_rule(
        player_num=len(stacks), max_round=1000, small_blind_amount=SB, ante_amount=0
    )
    players_info = {}
    for seat, stack in enumerate(stacks):
        uuid = f"p{seat}"
        players_info[uuid] = {"name": uuid, "stack": stack}
        emulator.register_player(uuid, RandomPlayer(rng, menu=menu))
    state = emulator.generate_initial_game_state(players_info)
    state, _events = emulator.start_new_round(state)
    return emulator, state


def check_per_seat_stacks(rng):
    """The claim that it takes one stack for the whole table, checked."""
    stacks = [100, 500, 20000, 20000, 20000, 20000]
    emulator, state = build(stacks, rng)
    seated = [p.stack for p in state["table"].seats.players]
    actions = emulator.generate_possible_actions(state)
    names = [a["action"] for a in actions]
    raise_action = next((a for a in actions if a["action"] == "raise"), None)
    span = (
        raise_action["amount"]["max"] - raise_action["amount"]["min"] + 1
        if raise_action
        else 0
    )
    print(f"per-seat stacks asked for      : {stacks}")
    print(f"per-seat stacks the table took : {seated}")
    print(f"generate_possible_actions here : {names}, "
          f"raise-to range {raise_action['amount'] if raise_action else 'none'} "
          f"({span} distinct whole-chip amounts)")


def playouts(seconds, rng):
    """Clone one mid-hand position and play the clone out, as often as we can."""
    emulator, state = build([STACK] * PLAYERS, rng)
    actions = emulator.generate_possible_actions(state)
    n = 0
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < seconds:
        emulator.run_until_round_finish(deepcopy_game_state(state))
        n += 1
    dt = time.perf_counter() - t0
    rate = n / dt
    print(f"pypokerengine play-outs, first decision after the deal: "
          f"n={n} play-outs in {dt:.2f}s = {rate:.0f} per second "
          f"({rate * BUDGET_S:.0f} in a {BUDGET_S}s decision); "
          f"{len(actions)} action kinds legal at the position")
    return rate


def main():
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0
    rng = random.Random(SEED)
    print(f"pypokerengine 1.0.1, Emulator API, {PLAYERS} players, 52 cards, "
          f"blinds {SB}/{BB}, {STACK} chips a seat (200bb), seed={SEED}, "
          f"{seconds:.0f}s of play-outs")
    print("play-out policy: uniform over fold / call / pot-sized raise / all-in, "
          "the same four-move menu bench_speed.py gives the other Python engines")
    check_per_seat_stacks(rng)
    playouts(seconds, rng)


if __name__ == "__main__":
    main()
