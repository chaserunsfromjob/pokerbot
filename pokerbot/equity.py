"""Sample showdown pot share using OpenSpiel's evaluator, never simulator secrets.

Uniform unknown holdings are an explicit baseline assumption, not inferred
opponent ranges. Equal-contribution showdown equity ignores future betting.
"""
from .engine import card_id, game_for


def showdown_share(holdings, board):
    n = len(holdings)
    if not 2 <= n <= 9 or any(len(h) != 2 for h in holdings) or len(board) != 5:
        raise ValueError("Require 2–9 two-card hands and a five-card board")
    deck = [card_id(c) for h in holdings for c in h] + [card_id(c) for c in board]
    if len(set(deck)) != len(deck):
        raise ValueError("Duplicate card")
    state = game_for((1000,) * n).new_initial_state()
    index = 0
    for _ in range(80):
        if state.is_terminal():
            return tuple((r + 100) / (n * 100) for r in state.returns())
        if state.is_chance_node():
            state.apply_action(deck[index])
            index += 1
        else:
            state.apply_action(1)  # Everyone calls/checks to equal 100 contributions.
    raise RuntimeError("Showdown simulation exceeded the bounded action count")


def estimate(hole, board, players, samples, rng):
    from .engine import RANKS, SUITS
    if len(hole) != 2 or len(board) not in (0, 3, 4, 5):
        raise ValueError("Invalid own cards/board")
    if not 2 <= players <= 9 or samples < 1:
        raise ValueError("Invalid player/sample count")
    known = tuple(hole) + tuple(board)
    for c in known:
        card_id(c)
    if len(set(known)) != len(known):
        raise ValueError("Duplicate known cards")
    available = [r + s for r in RANKS for s in SUITS if r + s not in known]
    value = 0.0
    count = 2 * (players - 1)
    for _ in range(samples):
        drawn = rng.sample(available, count + 5 - len(board))
        holdings = [hole] + [drawn[i:i + 2] for i in range(0, count, 2)]
        value += showdown_share(holdings, list(board) + drawn[count:])[0]
    return value / samples
