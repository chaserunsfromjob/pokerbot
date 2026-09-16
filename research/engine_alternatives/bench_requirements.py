"""Re-run the pass/fail checks behind the candidate sections of the survey.

`bench_speed.py`, `bench_cfr.py`, `bench_play.py`, `chooser.py`,
`resample_opponents.py` and `pypoker_playouts.py` produce the *timings* in
`ENGINE_ALTERNATIVES.md`. This program produces the other measured numbers in
it: how many distinct bet sizes each engine really offers, how many seats it
really takes, and whether chips are conserved over a pile of random hands.

Every line it prints is a claim in that document, so a reader who does not
believe one can re-run this and watch it made again. What it checks, engine by
engine:

  OpenSpiel     legal moves at the first decision under `fullgame`; seat counts
                that load; 200 complete random hands at each of 2, 3, 6 and 9
                seats in both betting modes, with chips conserved every hand.
  PokerKit      distinct legal raise-to amounts; an arbitrary non-round raise;
                50 hands at each of 2 to 9 seats; unequal starting stacks;
                whether the package exposes anything that solves.
  texasholdem   distinct legal raise-to amounts; the default seat maximum;
                50 hands at each of 2 to 9 seats.
  RLCard        the size of its action list at 2, 3, 6 and 9 seats, and which
                of its own sub-packages import on this Python.
  PyPokerEngine hands at 2, 3, 6, 9 and 12 seats with chips conserved; the
                raise range it offers; unequal starting stacks.
  clubs         that it does not import at all, and what is underneath once the
                missing standard-library module is faked.

"Chips conserved" means the chips on the table after the hand add up to the
chips before it: nothing was created or destroyed by the payout. It is the
cheapest test that catches an engine getting side pots wrong.

PokerRL is not checked here: it cannot be installed on this machine at all, and
that attempt is recorded in `raw/pokerrl_install.txt` instead.

Usage:  python bench_requirements.py

Research artefact. Not the bot, not on the bot's import path.
"""

import random
import subprocess
import sys
import types

SEED = 20260915
SB, BB = 50, 100
STACK = 20000

OK, BAD = "ok", "MISMATCH"


def say(label, value):
    print(f"  {label:58s} {value}")


def openspiel_game(players, abstraction, stack=STACK):
    import pyspiel

    blind = " ".join([str(SB), str(BB)] + ["0"] * (players - 2))
    stacks = " ".join([str(stack)] * players)
    first = "3 1 1 1" if players > 2 else "2 1 1 1"
    return pyspiel.load_game(
        f"universal_poker(betting=nolimit,numPlayers={players},numRounds=4,"
        f"blind={blind},firstPlayer={first},numSuits=4,numRanks=13,"
        f"numHoleCards=2,numBoardCards=0 3 1 1,stack={stacks},"
        f"bettingAbstraction={abstraction})"
    )


def check_openspiel():
    import pyspiel

    print("OpenSpiel universal_poker")
    game = openspiel_game(6, "fullgame")
    state = game.new_initial_state()
    while state.is_chance_node():
        state.apply_action(state.legal_actions()[0])
    say("legal moves at the first decision, fullgame, 6 seats",
        f"{len(state.legal_actions())} (survey says 19,803)")

    loads = [players for players in range(2, 11)
             if openspiel_game(players, "fcpa").num_players() == players]
    # Asking for 11 seats aborts the whole process rather than raising, so it
    # has to be asked in a separate one.
    probe = subprocess.run([sys.executable, __file__, "--probe-players", "11"],
                           capture_output=True, text=True)
    say("seat counts that load", f"{min(loads)}-{max(loads)} "
        f"(survey says 2-10; universal_poker.cc:114-115)")
    how = (f"killed by signal {-probe.returncode}" if probe.returncode < 0
           else f"exit code {probe.returncode}")
    say("asking for 11 seats in a fresh process",
        f"{how}: "
        f"{(probe.stderr or probe.stdout).strip().splitlines()[-1][:60]}")

    rng = random.Random(SEED)
    total_hands = leaks = 0
    for abstraction in ("fcpa", "fullgame"):
        for players in (2, 3, 6, 9):
            game = openspiel_game(players, abstraction)
            for _ in range(200):
                s = game.new_initial_state()
                while not s.is_terminal():
                    legal = s.legal_actions()
                    s.apply_action(legal[rng.randrange(len(legal))])
                total_hands += 1
                if abs(sum(s.returns())) > 1e-6:
                    leaks += 1
    say("random hands at 2/3/6/9 seats, both betting modes",
        f"{total_hands} hands, {leaks} chip-conservation failures")


def check_pokerkit():
    import pokerkit
    from pokerkit import Automation, NoLimitTexasHoldem

    print("PokerKit")
    automations = (
        Automation.ANTE_POSTING, Automation.BET_COLLECTION,
        Automation.BLIND_OR_STRADDLE_POSTING, Automation.CARD_BURNING,
        Automation.HOLE_DEALING, Automation.BOARD_DEALING,
        Automation.HOLE_CARDS_SHOWING_OR_MUCKING, Automation.HAND_KILLING,
        Automation.CHIPS_PUSHING, Automation.CHIPS_PULLING,
    )

    def new_state(players, stacks):
        return NoLimitTexasHoldem.create_state(
            automations, True, 0, (SB, BB), BB, stacks, players)

    state = new_state(6, STACK)
    lo = state.min_completion_betting_or_raising_to_amount
    hi = state.max_completion_betting_or_raising_to_amount
    say("distinct legal raise-to amounts, 6 seats",
        f"{hi - lo + 1} (from {lo} to {hi}; survey says 19,801)")
    state.complete_bet_or_raise_to(377)
    say("an arbitrary non-round raise to 377", "accepted")

    rng = random.Random(SEED)
    total_hands = leaks = 0
    for players in range(2, 10):
        for _ in range(50):
            state = new_state(players, STACK)
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
                    state.complete_bet_or_raise_to(rng.randint(
                        state.min_completion_betting_or_raising_to_amount,
                        state.max_completion_betting_or_raising_to_amount))
            total_hands += 1
            if sum(state.stacks) != players * STACK:
                leaks += 1
    say("random hands at 2-9 seats",
        f"{total_hands} hands, {leaks} chip-conservation failures")

    uneven = new_state(3, (100, 500, STACK))
    say("unequal starting stacks 100 / 500 / 20,000", f"accepted, {uneven.stacks}")

    solvers = [n for n in dir(pokerkit)
               if any(w in n.lower() for w in ("cfr", "solve", "search", "agent"))]
    say("names in the package that solve, search or play",
        solvers if solvers else "none")


def check_texasholdem():
    import inspect

    from texasholdem.game.action_type import ActionType
    from texasholdem.game.game import TexasHoldEm

    print("texasholdem")
    game = TexasHoldEm(buyin=STACK, big_blind=BB, small_blind=SB, max_players=6)
    game.start_hand()
    moves = game.get_available_moves()
    lo, hi = moves.raise_range.start, moves.raise_range.stop - 1
    say("distinct legal raise-to amounts, 6 seats",
        f"{hi - lo + 1} (from {lo} to {hi}; survey says 19,801)")
    default = inspect.signature(TexasHoldEm.__init__).parameters["max_players"].default
    say("max_players default", f"{default} (survey says 9, a constructor argument)")

    rng = random.Random(SEED)
    total_hands = leaks = 0
    for players in range(2, 10):
        game = TexasHoldEm(buyin=STACK, big_blind=BB, small_blind=SB,
                           max_players=players)
        for _ in range(50):
            for p in game.players:
                p.chips = STACK
            game.start_hand()
            while game.is_hand_running():
                moves = game.get_available_moves()
                action = rng.choice(list(moves.action_types))
                total = None
                if action == ActionType.RAISE:
                    total = rng.randint(moves.raise_range.start,
                                        moves.raise_range.stop - 1)
                game.take_action(action, total=total)
            total_hands += 1
            if sum(p.chips for p in game.players) != players * STACK:
                leaks += 1
    say("random hands at 2-9 seats",
        f"{total_hands} hands, {leaks} chip-conservation failures")


def check_rlcard():
    print("RLCard")
    import rlcard

    sizes = {}
    for players in (2, 3, 6, 9):
        env = rlcard.make("no-limit-holdem",
                          config={"game_num_players": players, "seed": SEED})
        sizes[players] = env.num_actions
    say("action-list size at 2 / 3 / 6 / 9 seats", sizes)

    for module in ("rlcard.games.nolimitholdem", "rlcard.agents", "rlcard.models"):
        try:
            __import__(module)
            say(f"import {module}", "succeeds")
        except Exception as exc:
            say(f"import {module}", f"fails: {type(exc).__name__}: {exc}")


def check_pypokerengine():
    print("PyPokerEngine")
    from pypokerengine.api.emulator import Emulator

    from pypoker_playouts import RandomPlayer, build

    rng = random.Random(SEED)
    _emulator, state = build([100, 500, STACK, STACK, STACK, STACK], rng)
    say("unequal starting stacks 100 / 500 / 20,000",
        f"accepted, {[p.stack for p in state['table'].seats.players]} "
        f"after blinds")
    emulator = Emulator()
    emulator.set_game_rule(player_num=6, max_round=1000,
                           small_blind_amount=SB, ante_amount=0)
    info = {}
    for seat in range(6):
        uuid = f"p{seat}"
        info[uuid] = {"name": uuid, "stack": STACK}
        emulator.register_player(uuid, RandomPlayer(rng))
    fresh, _ = emulator.start_new_round(emulator.generate_initial_game_state(info))
    raise_action = next(a for a in emulator.generate_possible_actions(fresh)
                        if a["action"] == "raise")
    amounts = raise_action["amount"]
    say("raise-to range offered at the first decision, 6 seats",
        f"{amounts['min']} to {amounts['max']} "
        f"({amounts['max'] - amounts['min'] + 1} distinct whole-chip amounts)")

    total_hands = leaks = 0
    for players in (2, 3, 6, 9, 12):
        emulator = Emulator()
        emulator.set_game_rule(player_num=players, max_round=1000,
                               small_blind_amount=SB, ante_amount=0)
        info = {}
        for seat in range(players):
            uuid = f"p{seat}"
            info[uuid] = {"name": uuid, "stack": STACK}
            emulator.register_player(uuid, RandomPlayer(rng))
        for _ in range(50):
            state = emulator.generate_initial_game_state(info)
            state, _ = emulator.start_new_round(state)
            state, _ = emulator.run_until_round_finish(state)
            total_hands += 1
            if sum(p.stack for p in state["table"].seats.players) != players * STACK:
                leaks += 1
    say("random hands at 2 / 3 / 6 / 9 / 12 seats",
        f"{total_hands} hands, {leaks} chip-conservation failures")


def check_clubs():
    print("clubs")
    try:
        __import__("clubs")
        say("import clubs, unpatched", "succeeds")
    except Exception as exc:
        say("import clubs, unpatched", f"fails: {type(exc).__name__}: {exc}")

    # The failed import above left half a package behind; clear it out first.
    for name in [n for n in sys.modules if n == "clubs" or n.startswith("clubs.")]:
        del sys.modules[name]
    shim = types.ModuleType("imp")
    shim.find_module = lambda *a, **k: None
    shim.load_module = lambda *a, **k: None
    sys.modules["imp"] = shim
    import clubs

    for name, players in (("SIX_PLAYER", 6), ("NINE_PLAYER", 9)):
        config = dict(getattr(clubs.configs, f"NO_LIMIT_HOLDEM_{name}"))
        config["blinds"] = [SB, BB] + [0] * (players - 2)
        config["start_stack"] = STACK
        obs = clubs.poker.Dealer(**config).reset()
        say(f"distinct legal raise-to amounts, {players} seats",
            f"{obs['max_raise'] - obs['min_raise'] + 1} "
            f"(from {obs['min_raise']} to {obs['max_raise']})")

    started = []
    for players in (3, 4, 5, 7, 8):
        config = dict(clubs.configs.NO_LIMIT_HOLDEM_SIX_PLAYER)
        config["num_players"] = players
        config["blinds"] = [SB, BB] + [0] * (players - 2)
        config["start_stack"] = STACK
        clubs.poker.Dealer(**config).reset()
        started.append(players)
    say("custom seat counts that start", started)


CHECKS = [
    ("openspiel", check_openspiel),
    ("pokerkit", check_pokerkit),
    ("texasholdem", check_texasholdem),
    ("rlcard", check_rlcard),
    ("pypokerengine", check_pypokerengine),
    ("clubs", check_clubs),
]


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--probe-players":
        openspiel_game(int(sys.argv[2]), "fcpa")
        print("loaded")
        return
    wanted = sys.argv[1:] or [name for name, _ in CHECKS]
    print(f"requirement checks, seed={SEED}, blinds {SB}/{BB}, "
          f"{STACK} chips a seat unless stated, python={sys.version.split()[0]}")
    for name, fn in CHECKS:
        if name not in wanted:
            continue
        try:
            fn()
        except ImportError as exc:
            print(f"{name}: not installed here ({exc})")
        print()


if __name__ == "__main__":
    main()
