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
from pokerbot.search import BUDGET_S, CONTINUATIONS, _deck, build_world, decide
from pokerbot.table import _deck_names

SEAT_COUNTS = [2, 6, 9]

DECK_SIZE = 52


def view_at(seats: int, seed: int = 11, button: int = 0, advance: int = 0):
    """A real decision point at this seat count, as the seat to act sees it."""
    hand = Table(TableConfig(seats=seats)).new_hand(seed=seed, button=button)
    for _ in range(advance):
        if hand.is_finished:
            break
        hand.apply_action(Action.CALL)
    return hand


def hand_past_the_flop(seats: int = 6, seed: int = 11):
    """A decision point with a flop out and a row of calls already behind it.

    The calls are the point. A call is engine action 1 and the deuce of
    diamonds is card 1, so past the hole cards the engine's history holds two
    kinds of small integer that no amount of staring at their values will tell
    apart. This is the position that catches a reader which tries.
    """
    hand = Table(TableConfig(seats=seats)).new_hand(seed=seed, button=0)
    while not hand.is_finished and hand.street < 1:
        menu = hand.legal_actions()
        hand.apply_action(Action.CALL if Action.CALL in menu else menu[0])
    assert not hand.is_finished, "the hand ended before the flop; pick another seed"
    return hand


def index_of(name: str) -> int:
    """The engine's own index for a card the record spells out, e.g. `Ad`."""
    return _deck_names().index(name)


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
    # Where each card sits, not whether its name appears somewhere in the
    # state: the engine's JSON prints every seat's cards, so a substring
    # search there passes whatever the world holds and proves nothing.
    mine = [index_of(name) for name in real[view.seat]]
    theirs = {
        engine_index: [index_of(name) for name in real[hand.seat_of(engine_index)]]
        for engine_index in range(view.seats)
        if engine_index != view.player
    }
    worlds = 200
    leaked = 0
    for _ in range(worlds):
        world = build_world(view, rng)
        history = world.history()
        assert [history[2 * view.player], history[2 * view.player + 1]] == mine, (
            "the imagined hand changed the searching seat's own cards"
        )
        for engine_index, cards in theirs.items():
            for offset, card in enumerate(cards):
                if history[2 * engine_index + offset] == card:
                    leaked += 1
    # The converse, which is the half that can actually fail: an opponent's
    # real card may turn up in its real slot only as often as a shuffle would
    # put it there. Each of the slots below is one draw from the cards the
    # searching seat cannot account for, so the chance of a hit is one in
    # that many; the bound is three times the average, which a fair shuffle
    # passes by a wide margin and a leak fails outright.
    slots = worlds * 2 * (view.seats - 1)
    pool = DECK_SIZE - len(view.seen_cards())
    expected = slots / pool
    assert leaked <= 3 * expected, (
        f"{leaked} of {slots} opponent card slots held the real card, against "
        f"{expected:.1f} expected from a shuffle of {pool} cards"
    )


def test_every_card_nobody_has_shown_can_be_dealt_into_an_imagined_world():
    """The cards the search deals from are all 52 less the ones it has seen.

    A seat can account for exactly its own two cards and the board. If
    anything else is struck out of the deck, the worlds the search imagines
    are drawn from the wrong cards, every average it takes is biased, and the
    bias is invisible in the result. The failure this catches is real: read
    past the hole cards, a call (engine action 1) looks exactly like the
    deuce of diamonds (card 1) and takes it out of play.
    """
    hand = hand_past_the_flop()
    view = hand.engine_view()
    board = hand.record.board
    assert len(board) == 3, f"expected a flop, got {board}"
    deck = set(_deck(view.game_string))
    assert len(deck) == DECK_SIZE
    own = {view.history[2 * view.player], view.history[2 * view.player + 1]}
    assert view.seen_cards() == own | {index_of(name) for name in board}, (
        f"the seat accounts for {sorted(view.seen_cards())}, not its own "
        f"{sorted(own)} and the board {board}"
    )
    pool = deck - view.seen_cards()
    assert len(pool) == DECK_SIZE - (2 + len(board))
    unseen = view.unseen_slots()
    assert len(unseen) == 2 * (view.seats - 1), (
        "the unseen slots should be every other seat's two hole cards"
    )
    rng = random.Random(99)
    dealt = set()
    for _ in range(400):
        history = build_world(view, rng).history()
        dealt.update(history[slot] for slot in unseen)
    assert dealt == pool, (
        f"cards never dealt: {sorted(pool - dealt)}; "
        f"cards dealt that the seat has already seen: {sorted(dealt - pool)}"
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
