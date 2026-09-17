"""The decision-layer benchmark times the table the bot actually plays on.

The benchmark in `research/decision_layer/bench_decision_layer.py` backs every
measured figure in `DECISION_LAYER_SEARCH.md`. A stopwatch is only worth
reading if it was held over the right game, so this file pins the benchmark's
game definition to the adapter's own: the same blinds in the same seat order,
the same first seat to act on every street, and the same number of seats.

What the benchmark is allowed to differ on, and does: its own stack depth, its
own betting abstraction (it compares `fcpa` with `fullgame`), and the engine's
equity simulator count, which the table never asks for.
"""

from __future__ import annotations

import importlib.util
import inspect
import pathlib

import pyspiel
import pytest

from pokerbot.equity_rule import with_odds
from pokerbot.table import BETTING_ABSTRACTION, TableConfig, _game_string, game_string

ROOT = pathlib.Path(__file__).resolve().parents[1]
BENCH_PATH = ROOT / "research" / "decision_layer" / "bench_decision_layer.py"

#: The seat counts the claim is made at: heads-up, where the acting order is
#: the special case, and six-handed, the size the evaluation weights most.
SEAT_COUNTS = [2, 6]

#: The three parameters that say who posts what and who acts when.
SHARED_FIELDS = ("numPlayers", "blind", "firstPlayer")

#: The engine's own bet menus, written out here rather than read from the
#: adapter so that this file, not the code under test, says which names are
#: allowed.
ENGINE_BET_MENUS = ("fchpa", "fcpa", "fullgame")

#: A bet menu with a second `blind` and a second `firstPlayer` hidden behind
#: it. `universal_poker` reads the last of a duplicated key, so if this ever
#: reaches the game definition the engine loads the reversed heads-up game --
#: the big blind on engine seat 0 and the acting order turned around -- and
#: says nothing about it.
SMUGGLED_BET_MENU = "fcpa,blind=100 50,firstPlayer=2 1 1 1"


@pytest.fixture(scope="module")
def bench():
    """The benchmark script, imported as a module by its path."""
    spec = importlib.util.spec_from_file_location("bench_decision_layer", BENCH_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def table_parameters(seats: int, stack: int) -> dict:
    """What the adapter's own game definition loads as, at this stack depth."""
    config = TableConfig(seats=seats, stacks=(stack,) * seats)
    return pyspiel.load_game(_game_string(config, config.stacks)).get_parameters()


@pytest.mark.parametrize("seats", SEAT_COUNTS, ids=[str(n) for n in SEAT_COUNTS])
def test_bench_posts_the_blinds_and_acts_in_the_table_s_order(bench, seats):
    measured = bench.build_game(seats).get_parameters()
    expected = table_parameters(seats, bench.BENCH_STACK)
    for field in SHARED_FIELDS:
        assert measured[field] == expected[field], (
            f"the benchmark's {field} at {seats} seats is {measured[field]!r}, "
            f"but the table's is {expected[field]!r}; the benchmark would be "
            "timing a game the bot never plays"
        )


@pytest.mark.parametrize("seats", SEAT_COUNTS, ids=[str(n) for n in SEAT_COUNTS])
def test_bench_keeps_its_own_stacks_abstraction_and_odds_sims(bench, seats):
    measured = bench.build_game(seats, "fullgame", 200).get_parameters()
    assert measured["stack"] == " ".join([str(bench.BENCH_STACK)] * seats)
    assert measured["bettingAbstraction"] == "fullgame"
    assert measured["calcOddsNumSims"] == 200
    expected = table_parameters(seats, bench.BENCH_STACK)
    for field in SHARED_FIELDS:
        assert measured[field] == expected[field]


def test_the_bet_menu_is_the_only_knob_game_string_offers():
    """A signature check, and only that.

    It says the bet menu is the one thing a caller may pass, so no second
    argument can reach the game definition. It says nothing about what a
    caller may pass *as* the bet menu; that is held down below, by
    `test_game_string_refuses_a_bet_menu_that_smuggles_in_parameters` and
    `test_every_accepted_bet_menu_keeps_the_table_s_blinds_and_order`, which
    are the proof, because a signature is not a behaviour.
    """
    keyword_only = [
        name
        for name, parameter in inspect.signature(game_string).parameters.items()
        if parameter.kind is inspect.Parameter.KEYWORD_ONLY
    ]
    assert keyword_only == ["betting_abstraction"], (
        f"game_string takes the keyword-only knobs {keyword_only!r}; only "
        "betting_abstraction may be one, because a second free-form argument "
        "would be another route into the game definition"
    )


def test_the_table_s_own_bet_menu_is_an_accepted_one():
    """Whatever the adapter plays on must be a value `game_string` accepts."""
    assert BETTING_ABSTRACTION in ENGINE_BET_MENUS


def test_game_string_refuses_a_bet_menu_that_smuggles_in_parameters():
    """The one knob cannot be used to move the blinds or the acting order.

    This is the route the signature check cannot see: the value itself, not
    an extra argument. It must be refused before it is written into the game
    definition, because once the engine has loaded it there is nothing left
    to complain about -- the reversed game loads cleanly.
    """
    config = TableConfig(seats=2, stacks=(20000, 20000))
    with pytest.raises(ValueError):
        game_string(config, betting_abstraction=SMUGGLED_BET_MENU)


@pytest.mark.parametrize("abstraction", ENGINE_BET_MENUS)
@pytest.mark.parametrize("seats", SEAT_COUNTS, ids=[str(n) for n in SEAT_COUNTS])
def test_every_accepted_bet_menu_keeps_the_table_s_blinds_and_order(seats, abstraction):
    """Each accepted value changes the menu and nothing else."""
    config = TableConfig(seats=seats, stacks=(20000,) * seats)
    measured = pyspiel.load_game(
        game_string(config, betting_abstraction=abstraction)
    ).get_parameters()
    expected = table_parameters(seats, 20000)
    assert measured["bettingAbstraction"] == abstraction
    for field in SHARED_FIELDS:
        assert measured[field] == expected[field], (
            f"with the bet menu {abstraction!r} at {seats} seats the game's "
            f"{field} is {measured[field]!r}, but the table's is "
            f"{expected[field]!r}; the bet menu must change the menu only"
        )


@pytest.mark.parametrize("seats", SEAT_COUNTS, ids=[str(n) for n in SEAT_COUNTS])
def test_bench_adds_its_odds_sims_through_with_odds(bench, seats):
    """`calcOddsNumSims` reaches the benchmark's game the guarded way.

    The benchmark's game must be the table's own game definition at its own
    stacks and bet menu, with the equity simulator switched on by `with_odds`
    and nothing else touched -- blinds and acting order included.
    """
    config = TableConfig(seats=seats, stacks=(bench.BENCH_STACK,) * seats)
    expected = pyspiel.load_game(
        with_odds(game_string(config, betting_abstraction="fullgame"), 200)
    ).get_parameters()
    measured = bench.build_game(seats, "fullgame", 200).get_parameters()
    assert measured["calcOddsNumSims"] == 200
    for field in SHARED_FIELDS:
        assert measured[field] == expected[field]
    assert measured == expected
