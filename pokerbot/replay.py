"""Replay one hand from a seed and print its record.

This exists so invariant I6 can be proved across separate runs of the program
rather than only inside one: run this twice with the same arguments, on the
same commit, and the two outputs must be the same bytes.

    python -m pokerbot.replay --seats 6 --seed 12345

The seats play by drawing uniformly from the menu the engine offers them,
using a seeded draw of their own. That is not a strategy and is not meant to
be one; it is a way of walking a hand to its end that repeats exactly.
"""

from __future__ import annotations

import argparse
import random
import sys

from .table import Hand, Table, TableConfig


def play_scripted_hand(table: Table, seed: int, button: int = 0, policy_seed: int | None = None) -> Hand:
    """Play one whole hand, every seat drawing uniformly from its own menu."""
    hand = table.new_hand(seed=seed, button=button)
    rng = random.Random(seed if policy_seed is None else policy_seed)
    while not hand.is_finished:
        menu = hand.legal_actions()
        hand.apply_action(menu[rng.randrange(len(menu))])
    return hand


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seats", type=int, default=6)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--button", type=int, default=0)
    parser.add_argument("--small-blind", type=int, default=50)
    parser.add_argument("--big-blind", type=int, default=100)
    parser.add_argument("--stack", type=int, default=None)
    args = parser.parse_args(argv)

    stacks = ()
    if args.stack is not None:
        stacks = (args.stack,) * args.seats
    table = Table(
        TableConfig(
            seats=args.seats,
            small_blind=args.small_blind,
            big_blind=args.big_blind,
            stacks=stacks,
        )
    )
    hand = play_scripted_hand(table, seed=args.seed, button=args.button)
    sys.stdout.buffer.write(hand.record.to_bytes())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
