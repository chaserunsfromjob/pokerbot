"""The bot chooses a legal move, in time, and the same way twice.

`BUILD_PLAN.md` T2's three claims about the search itself, one test each:
a move the engine offered, inside the budget, at two, six and nine seats; the
same move for the same seed; and -- the claim that keeps `CLAUDE.md`'s
forefront rule -- a search that cannot see an opponent's cards, because they
are not in what it is handed.
"""

from __future__ import annotations

import random
import time

import pytest

from pokerbot import Action, Table, TableConfig, deal_check
from pokerbot.search import BUDGET_S, CONTINUATIONS, build_world, decide

SEAT_COUNTS = [2, 6, 9]


def view_at(seats: int, seed: int = 11, button: int = 0, advance: int = 0):
    """A real decision point at this seat count, as the seat to act sees it."""
    hand = Table(TableConfig(seats=seats)).new_hand(seed=seed, button=button)
    for _ in range(advance):
        if hand.is_finished:
            break
        hand.apply_action(Action.CALL)
    return hand


@pytest.mark.parametrize("seats", SEAT_COUNTS, ids=[str(n) for n in SEAT_COUNTS])
def test_search_returns_a_legal_move_inside_the_budget(seats):
    ok, reason = deal_check(seats)
    if not ok:
        pytest.skip(f"NOT RUN: {seats} seats would not deal -- {reason}")
    for offset in range(3):
        hand = view_at(seats, seed=500 + offset, button=offset % seats)
        view = hand.engine_view()
        started = time.monotonic()
        decision = decide(view, seed=97 + offset)
        elapsed = time.monotonic() - started
        assert decision.action in view.menu, (
            f"the search returned {decision.action}, which is not on the menu {view.menu}"
        )
        assert elapsed <= BUDGET_S, f"the decision took {elapsed * 1000:.0f} ms"
        assert decision.playouts > 0
        assert not decision.starved
        # The hand has to accept it, which is the engine's own ruling.
        hand.apply_action(decision.action)


@pytest.mark.parametrize("seats", SEAT_COUNTS, ids=[str(n) for n in SEAT_COUNTS])
def test_the_same_seed_gives_the_same_move(seats):
    ok, reason = deal_check(seats)
    if not ok:
        pytest.skip(f"NOT RUN: {seats} seats would not deal -- {reason}")
    view = view_at(seats, seed=31).engine_view()
    first = decide(view, seed=4242)
    second = decide(view, seed=4242)
    assert first.action is second.action
    assert first.means == second.means, "the same seed weighed the moves differently"
    assert first.counts == second.counts
    assert not first.truncated and not second.truncated, (
        "the clock ended the search, so this run proves nothing about the seed"
    )


def test_a_different_seed_is_allowed_to_differ_but_stays_legal():
    view = view_at(6, seed=31).engine_view()
    for seed in range(20):
        assert decide(view, seed=seed).action in view.menu


def test_the_search_is_never_shown_an_opponents_cards():
    """The view it works from has the other seats' cards blanked out.

    This is the structural half of `CLAUDE.md`'s rule about where knowledge
    comes from: the search cannot cheat by reading an opponent's hand, because
    the hand is not in the object it is given. The worlds it builds for itself
    keep its own two cards and the board and deal everything else afresh.
    """
    hand = view_at(6, seed=77)
    view = hand.engine_view()
    own_slots = (2 * view.player, 2 * view.player + 1)
    for slot in range(view.hole_slots):
        card = view.history[slot]
        if slot in own_slots:
            assert card is not None, "the seat cannot see its own cards"
        else:
            assert card is None, f"slot {slot} leaked an opponent's card"
    rng = random.Random(3)
    real = hand.record.hole_cards
    mine = set(real[view.seat])
    for _ in range(20):
        world = build_world(view, rng)
        json_hands = world.to_json()
        assert all(card in json_hands for card in mine), (
            "the imagined hand changed the searching seat's own cards"
        )


def test_the_four_continuations_are_four_and_add_up():
    """Pluribus's k = 4, and three weights that are a probability each."""
    assert len(CONTINUATIONS) == 4
    assert [c.name for c in CONTINUATIONS] == [
        "fold_biased",
        "call_biased",
        "mixed",
        "raise_biased",
    ]
    for continuation in CONTINUATIONS:
        total = continuation.fold + continuation.call + continuation.raise_
        assert abs(total - 1.0) < 1e-9, f"{continuation.name} weights add to {total}"


def test_a_tiny_budget_still_returns_a_legal_move():
    """The clock can cut the search short; it can never leave it without a move."""
    view = view_at(6, seed=13).engine_view()
    decision = decide(view, seed=5, budget_s=0.0)
    assert decision.action in view.menu
    assert decision.truncated
