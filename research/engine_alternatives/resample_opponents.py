"""Workaround for the multiway crash in OpenSpiel's `universal_poker`.

`universal_poker.cc:1111` refuses to invent a plausible set of opponent hole
cards whenever there are more than two players, and the caller six lines above
reads from what it returns, so the whole process dies with a segmentation
fault. Any search that has to guess what the opponents hold needs that job done.

This does it in Python instead: replay the hand's own history into a fresh
state, and wherever the history dealt a card to a seat we cannot see, deal
instead a card drawn from the cards still unaccounted for.

Hole cards are dealt first and in seat order - verified by dealing twelve cards
at a 6-player table and reading each seat's private cards back - so seat `p`
holds history positions `p * hole_cards` and `p * hole_cards + 1`. Board cards
are public and are replayed unchanged.

Research artefact. Not the bot, not on the bot's import path.
"""

import random


def card_positions(state):
    """History positions that dealt a card, found by replaying the hand once."""
    replay = state.get_game().new_initial_state()
    positions = []
    for i, action in enumerate(state.history()):
        if replay.is_chance_node():
            positions.append(i)
        replay.apply_action(action)
    return positions


def hidden_positions(state, player, hole_cards=2):
    """History positions holding hole cards `player` cannot see."""
    seats = state.get_game().num_players()
    return {i for i in range(seats * hole_cards) if i // hole_cards != player}


def resample_opponents(state, player, hidden=None, dealt=None, num_cards=52,
                       rng=random):
    """Return a copy of `state` with every other seat's hole cards redrawn.

    Uniformly, from the cards `player` cannot see. Weighting that draw by an
    opponent model is the hole-card-resampling hook described in
    ENGINE_ALTERNATIVES.md; this function is the uniform case of it.
    """
    history = state.history()
    hidden = hidden_positions(state, player) if hidden is None else hidden
    dealt = card_positions(state) if dealt is None else dealt
    seen = {history[i] for i in dealt if i not in hidden}
    deck = [c for c in range(num_cards) if c not in seen]
    rng.shuffle(deck)
    fresh = state.get_game().new_initial_state()
    for i, action in enumerate(history):
        fresh.apply_action(deck.pop() if i in hidden else action)
    return fresh


def _main():
    import sys
    import time

    import pyspiel

    from chooser import GAME_6MAX, deal_and_bet

    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0
    game = pyspiel.load_game(GAME_6MAX.format(abstraction="fcpa"))
    rng = random.Random(20260915)

    def rate(state, label):
        player = state.current_player()
        hidden = hidden_positions(state, player)
        dealt = card_positions(state)
        n = 0
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < seconds:
            resample_opponents(state, player, hidden, dealt, rng=rng)
            n += 1
        dt = time.perf_counter() - t0
        print(f"resample_opponents, {label}: n={n} draws in {dt:.2f}s = "
              f"{n / dt:.0f} per second (history {len(state.history())} long)")

    rate(deal_and_bet(game, rng), "first decision after the deal")

    # A decision as deep as the hand goes: every seat calls until the river.
    deep = deal_and_bet(game, rng)
    while not deep.is_terminal() and len(deep.history()) < 40:
        if deep.is_chance_node():
            legal = deep.legal_actions()
            deep.apply_action(legal[rng.randrange(len(legal))])
        elif deep.legal_actions()[1] == 1:
            deep.apply_action(1)  # call
        else:
            break
    if not deep.is_terminal() and not deep.is_chance_node():
        rate(deep, "a later decision in the same hand")
    print("6 players, 52 cards, fcpa; hidden positions and card positions "
          "computed once per decision, not once per draw; seed=20260915")


if __name__ == "__main__":
    _main()
