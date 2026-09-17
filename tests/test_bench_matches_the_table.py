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
import pathlib

import pyspiel
import pytest

from pokerbot.table import TableConfig, _game_string

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
