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
from pokerbot.table import TableConfig, _game_string, game_string

ROOT = pathlib.Path(__file__).resolve().parents[1]
BENCH_PATH = ROOT / "research" / "decision_layer" / "bench_decision_layer.py"

#: The seat counts the claim is made at: heads-up, where the acting order is
#: the special case, and six-handed, the size the evaluation weights most.
SEAT_COUNTS = [2, 6]

#: The three parameters that say who posts what and who acts when.
SHARED_FIELDS = ("numPlayers", "blind", "firstPlayer")


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


def test_game_string_has_no_knob_that_can_overwrite_the_table():
    """The bet menu is the only thing a caller may change.

    `universal_poker` reads the last of any duplicated key, so a knob that
    appended free-form parameters could set `blind` or `firstPlayer` a second
    time and load a game the bot never sits at -- the reversal this change
    removes, through the front door. An engine parameter is added instead by
    `equity_rule.with_odds`, which refuses a game definition that already sets
    `calcOddsNumSims`.
    """
    keyword_only = [
        name
        for name, parameter in inspect.signature(game_string).parameters.items()
        if parameter.kind is inspect.Parameter.KEYWORD_ONLY
    ]
    assert keyword_only == ["betting_abstraction"], (
        f"game_string takes the keyword-only knobs {keyword_only!r}; only "
        "betting_abstraction may be one, because any other route into the "
        "game definition can overwrite the table's blinds or acting order"
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
