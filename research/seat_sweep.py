"""Find the real seat ceiling of the vendored short-deck engine.

Deals whole hands at each requested seat count, choosing every action at
random from the engine's own `legal_actions`, and asserts chips are conserved
(`sum(state.payout.values()) == 0`) at the end of each hand.

Run from the top of the repository:

    .venv/bin/python research/seat_sweep.py 7 8 9

It prints one line per seat count: OK with the hand count, or FAILS with the
exception type and message.
"""
import random
import sys
import traceback


def play_hands(n_players: int, n_hands: int) -> None:
    # Imported inside the function on purpose: importing poker_ai at module
    # scope runs `mp.Manager()` in poker_ai/ai/agent.py:8, which on macOS
    # (spawn) re-imports this file in the child and crashes. See
    # REFERENCE_NOTES.md, "Training with the default --multi_process".
    from poker_ai.games.short_deck.state import ShortDeckPokerState
    from poker_ai.games.short_deck.player import ShortDeckPokerPlayer
    from poker_ai.poker.pot import Pot

    for _ in range(n_hands):
        pot = Pot()
        players = [
            ShortDeckPokerPlayer(player_i=i, pot=pot, initial_chips=10000)
            for i in range(n_players)
        ]
        state = ShortDeckPokerState(players=players, load_card_lut=False)
        while not state.is_terminal:
            state = state.apply_action(random.choice(state.legal_actions))
        assert sum(state.payout.values()) == 0, state.payout


def main(seat_counts, n_hands: int = 50) -> int:
    random.seed(0)
    failures = 0
    for n_players in seat_counts:
        try:
            play_hands(n_players, n_hands)
        except Exception as exc:  # noqa: BLE001 - report, don't stop the sweep
            failures += 1
            print(f"{n_players} players: FAILS - {type(exc).__name__}: {exc}")
            traceback.print_exc(limit=2)
        else:
            print(f"{n_players} players: OK - {n_hands} hands, chips conserved")
    return failures


if __name__ == "__main__":
    seats = [int(a) for a in sys.argv[1:]] or [2, 3, 4, 5, 6, 7, 8, 9]
    sys.exit(1 if main(seats) else 0)
