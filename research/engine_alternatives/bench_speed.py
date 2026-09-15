"""Measure complete hands per second for each engine, one core, random play.

Every run is a 6-player 52-card no-limit table, 20,000-chip stacks (200 big
blinds), blinds 50/100. Actions are chosen uniformly at random from whatever the
engine itself says is legal, so the numbers include the cost of asking.

OpenSpiel is measured twice, once per betting abstraction:
  fcpa     - fold / call / pot-sized bet / all-in (a four-item menu)
  fullgame - every whole-chip raise-to amount is its own legal action

Usage:  python bench_speed.py [seconds_per_engine]
"""

import random
import sys
import time

SECONDS = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
SEED = 20260915
STACK = 20000
SB, BB = 50, 100
PLAYERS = 6


def openspiel_game(abstraction):
    import pyspiel

    return pyspiel.load_game(
        "universal_poker(betting=nolimit,numPlayers=6,numRounds=4,"
        "blind=50 100 0 0 0 0,firstPlayer=3 1 1 1,numSuits=4,numRanks=13,"
        "numHoleCards=2,numBoardCards=0 3 1 1,"
        "stack=20000 20000 20000 20000 20000 20000,"
        f"bettingAbstraction={abstraction})"
    )


def openspiel_hand(game, rng):
    """Play one complete hand at random. Returns (player actions, payoffs).

    Chance nodes are sampled uniformly from `legal_actions()`; checked against
    `chance_outcomes()`, every undealt card carries the same probability
    (1/52 at the first deal), so this is the fair deal and it avoids building
    the (card, probability) pair list on every deal.
    """
    state = game.new_initial_state()
    acts = 0
    while not state.is_terminal():
        chance = state.is_chance_node()
        legal = state.legal_actions()
        state.apply_action(legal[rng.randrange(len(legal))])
        acts += 0 if chance else 1
    return acts, state.returns()


def bench_openspiel(abstraction, seconds):
    game = openspiel_game(abstraction)
    rng = random.Random(SEED)
    hands = actions = 0
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < seconds:
        a, _ = openspiel_hand(game, rng)
        hands += 1
        actions += a
    dt = time.perf_counter() - t0
    return hands / dt, actions / hands, hands


def bench_texasholdem(seconds, menu=False):
    """menu=False: raise-to drawn from the whole legal range (real sizing).
    menu=True: fold / check-call / pot-sized raise / all-in, the four moves
    OpenSpiel's `fcpa` abstraction offers, so the two engines can be compared
    doing the same amount of work."""
    from texasholdem.game.game import TexasHoldEm
    from texasholdem.game.action_type import ActionType

    rng = random.Random(SEED)
    game = TexasHoldEm(buyin=STACK, big_blind=BB, small_blind=SB, max_players=PLAYERS)
    hands = actions = 0
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < seconds:
        for p in game.players:
            p.chips = STACK
        game.start_hand()
        while game.is_hand_running():
            moves = game.get_available_moves()
            action = rng.choice(list(moves.action_types))
            total = None
            if action == ActionType.RAISE:
                lo = moves.raise_range.start
                hi = moves.raise_range.stop - 1
                if menu:
                    pot = sum(p.get_total_amount() for p in game.pots)
                    total = rng.choice([min(max(pot, lo), hi), hi])
                else:
                    total = rng.randint(lo, hi)
            game.take_action(action, total=total)
            actions += 1
        hands += 1
    dt = time.perf_counter() - t0
    return hands / dt, actions / hands, hands


def bench_pokerkit(seconds, menu=False):
    from pokerkit import Automation, NoLimitTexasHoldem

    rng = random.Random(SEED)
    hands = actions = 0
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < seconds:
        state = NoLimitTexasHoldem.create_state(
            (
                Automation.ANTE_POSTING,
                Automation.BET_COLLECTION,
                Automation.BLIND_OR_STRADDLE_POSTING,
                Automation.CARD_BURNING,
                Automation.HOLE_DEALING,
                Automation.BOARD_DEALING,
                Automation.HOLE_CARDS_SHOWING_OR_MUCKING,
                Automation.HAND_KILLING,
                Automation.CHIPS_PUSHING,
                Automation.CHIPS_PULLING,
            ),
            True,
            0,
            (SB, BB),
            BB,
            STACK,
            PLAYERS,
        )
        while state.status:
            choices = []
            if state.can_fold():
                choices.append("f")
            if state.can_check_or_call():
                choices.append("c")
            if state.can_complete_bet_or_raise_to():
                choices.append("r")
            move = rng.choice(choices)
            if move == "f":
                state.fold()
            elif move == "c":
                state.check_or_call()
            else:
                lo = state.min_completion_betting_or_raising_to_amount
                hi = state.max_completion_betting_or_raising_to_amount
                if menu:
                    pot = state.total_pot_amount
                    state.complete_bet_or_raise_to(
                        rng.choice([min(max(pot, lo), hi), hi])
                    )
                else:
                    state.complete_bet_or_raise_to(rng.randint(lo, hi))
            actions += 1
        hands += 1
    dt = time.perf_counter() - t0
    return hands / dt, actions / hands, hands


def main():
    rows = [
        ("OpenSpiel universal_poker fcpa menu", lambda: bench_openspiel("fcpa", SECONDS)),
        ("OpenSpiel universal_poker fullgame", lambda: bench_openspiel("fullgame", SECONDS)),
        ("texasholdem 0.11.0 menu", lambda: bench_texasholdem(SECONDS, menu=True)),
        ("texasholdem 0.11.0 real sizing", lambda: bench_texasholdem(SECONDS)),
        ("PokerKit 0.7.5 menu", lambda: bench_pokerkit(SECONDS, menu=True)),
        ("PokerKit 0.7.5 real sizing", lambda: bench_pokerkit(SECONDS)),
    ]
    print(f"seed={SEED} seconds per engine={SECONDS} players={PLAYERS} "
          f"stack={STACK} blinds={SB}/{BB}")
    print(f"{'engine':40s} {'hands/s':>10s} {'actions/hand':>13s} {'hands':>8s}")
    for name, fn in rows:
        rate, apa, hands = fn()
        print(f"{name:40s} {rate:10.0f} {apa:13.1f} {hands:8d}")


if __name__ == "__main__":
    main()
