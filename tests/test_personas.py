"""The league's opponents: do they draw their parameters, and do they behave?

These tests cover `pokerbot/personas.py`. They carry no invariant marker: they
are not one of `EVALUATION_STRATEGY.md` section 4.5's seven statements about a
dealt hand, so they do not appear in the seat-count table.
"""

from __future__ import annotations

import random

import pytest

from pokerbot import Action, Table, TableConfig
from pokerbot import personas
from pokerbot.personas import (
    ALL_PERSONAS,
    BEHAVIOURAL_PERSONAS,
    CALIBRATION_AGENTS,
    DISTRIBUTIONS,
    build_persona,
    draw_session,
    hand_class,
    parameter_log,
    preflop_top_fraction,
    seat_view,
    showdown_equity,
)


def test_the_set_is_exactly_section_3_2s():
    """Four calibration agents and nine behavioural personas, by those names."""
    assert CALIBRATION_AGENTS == (
        "always_fold",
        "always_call",
        "always_raise",
        "call_raise_50_50",
    )
    assert BEHAVIOURAL_PERSONAS == (
        "calling_station",
        "nit",
        "maniac",
        "never_bluffs",
        "fit_or_fold",
        "tag",
        "lag",
        "tilter",
        "sizing_tell",
    )
    assert len(ALL_PERSONAS) == 13


def test_every_persona_draws_its_parameters_and_logs_them():
    """Section 3.2's first design rule: drawn per session, never a fixed point.

    Two sessions with different seeds must give different values, and every
    value drawn must be inside the range the table says it came from, and must
    appear in the line the report prints.
    """
    first = draw_session(session_seed=1)
    second = draw_session(session_seed=2)
    for name in BEHAVIOURAL_PERSONAS:
        spec = DISTRIBUTIONS[name]
        assert spec, f"{name} has no distribution to draw from"
        drawn = first[name].params
        assert set(drawn) == set(spec), f"{name} did not draw every parameter"
        for parameter, (kind, low, high) in spec.items():
            assert low <= drawn[parameter] <= high, (
                f"{name}.{parameter} = {drawn[parameter]} is outside [{low}, {high}]"
            )
        assert drawn != second[name].params, (
            f"{name} drew the same parameters in two different sessions, which is "
            f"a fixed point wearing a disguise"
        )
        logged = first[name].describe()
        for parameter, value in drawn.items():
            assert parameter in logged, f"{parameter} is not in {name}'s logged line"
            assert f"{value:.3f}" in logged

    lines = parameter_log(first.values())
    assert len(lines) == len(ALL_PERSONAS)


def test_the_same_seed_draws_the_same_parameters_in_a_fresh_process():
    """Pairing depends on it: both arms must meet identically built opponents."""
    one = build_persona("tag", session_seed=99)
    two = build_persona("tag", session_seed=99)
    assert one.params == two.params
    # And the seed must not come from Python's per-process string hashing, which
    # would make a run unreproducible tomorrow.
    assert personas.stable_seed("tag", 99) == personas.stable_seed("tag", 99)
    assert personas.stable_seed("tag", 99) != personas.stable_seed("tag", 100)


def test_two_copies_of_one_persona_do_not_flip_the_same_coins():
    """Five maniacs at one table must not raise in lockstep."""
    left = build_persona("maniac", session_seed=5, stream=1)
    right = build_persona("maniac", session_seed=5, stream=2)
    assert left.params == right.params
    assert [left.rng.random() for _ in range(5)] != [right.rng.random() for _ in range(5)]


@pytest.mark.parametrize("name", ALL_PERSONAS)
@pytest.mark.parametrize("seats", [2, 6, 9])
def test_a_persona_only_ever_returns_a_move_the_engine_allows(name, seats):
    """Every agent acts through the adapter's menu and nothing else."""
    persona = build_persona(name, session_seed=11)
    table = Table(TableConfig(seats=seats))
    for hand_index in range(3):
        hand = table.new_hand(seed=1000 + hand_index, button=hand_index % seats)
        while not hand.is_finished:
            seat = hand.current_seat()
            action = persona(hand, seat)
            assert isinstance(action, Action)
            assert action in hand.legal_actions(), (
                f"{name} chose {action} at seat {seat}, which the engine does not allow"
            )
            hand.apply_action(action)


def test_the_calibration_agents_do_what_their_names_say():
    table = Table(TableConfig(seats=6))
    hand = table.new_hand(seed=7, button=0)
    view = seat_view(hand, hand.current_seat())
    assert view.facing_bet, "the first seat to act pre-flop owes the big blind"
    assert build_persona("always_fold", 0).act(view) is Action.FOLD
    assert build_persona("always_call", 0).act(view) is Action.CALL
    assert build_persona("always_raise", 0).act(view) in {
        Action.POT,
        Action.HALF_POT,
        Action.ALL_IN,
    }


def test_call_raise_50_50_does_both_and_roughly_half_the_time():
    """The stochastic calibration agent, there to shake out seed handling."""
    persona = build_persona("call_raise_50_50", session_seed=4)
    table = Table(TableConfig(seats=6))
    hand = table.new_hand(seed=7, button=0)
    view = seat_view(hand, hand.current_seat())
    choices = [persona.act(view) for _ in range(400)]
    raises = sum(1 for c in choices if c is not Action.CALL)
    assert 150 < raises < 250, f"{raises} raises out of 400 is not a coin flip"


def test_the_tilter_switches_states_on_a_big_loss_and_comes_back():
    """Section 3.2's two-state machine, checked on its own terms."""
    persona = build_persona("tilter", session_seed=8)
    trigger = persona.params["tilt_trigger_bb"]
    duration = int(persona.params["tilt_duration"])
    assert not persona.tilted
    persona.hand_finished(-(trigger + 1))
    assert persona.tilted, "losing a pot bigger than the trigger must start the tilt"
    for _ in range(duration):
        persona.hand_finished(0.0)
    assert not persona.tilted, "the tilt must end after tilt_duration hands"
    assert persona.has_memory, "the tilter's hands depend on each other"
    assert not build_persona("nit", 8).has_memory


def test_hand_strength_comes_from_the_engines_own_showdown():
    """Aces beat seven-deuce, and nothing in this package decided that.

    `showdown_equity` deals the rest of the hand out on the engine's own game
    and counts how often the engine's `returns` says we won. The ordering below
    is not asserted as poker knowledge; it is the engine's answer, and the test
    fails if the wiring to the engine ever stops working.
    """
    aces = showdown_equity(("As", "Ah"), (), rollouts=80)
    rags = showdown_equity(("7d", "2c"), (), rollouts=80)
    assert 0.8 < aces <= 1.0
    assert rags < 0.45
    assert aces > rags


def test_the_preflop_ranking_has_all_169_classes_in_a_strict_order():
    """We count the classes; the engine ranks them."""
    ranking = personas._preflop_ranking(120)
    assert len(ranking) == 169
    assert len(set(ranking.values())) == 169, "two classes share a place in the order"
    # The combination counts have to add up to the whole deck's worth of hands.
    assert sum(personas.class_combos(name) for name in ranking) == personas.TOTAL_COMBOS
    assert hand_class(("As", "Ah")) == "AA"
    assert hand_class(("Ks", "Qs")) == "KQs"
    assert hand_class(("Ks", "Qh")) == "KQo"
    assert preflop_top_fraction(("As", "Ah")) < preflop_top_fraction(("7d", "2c"))
    assert preflop_top_fraction(("As", "Ah")) < 0.02


def test_a_handicapped_bot_gives_up_more_often_than_the_bot_it_wraps():
    """The wrapper the decision-rule test uses to make a bot deliberately worse."""
    table = Table(TableConfig(seats=6))
    hand = table.new_hand(seed=12, button=0)
    seat = hand.current_seat()
    caller = build_persona("always_call", 0)
    broken = personas.handicapped(caller, fold_probability=1.0, seed=1)
    assert caller(hand, seat) is Action.CALL
    assert broken(hand, seat) is Action.FOLD
