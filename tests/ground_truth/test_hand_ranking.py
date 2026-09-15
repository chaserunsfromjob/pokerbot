"""Ground-truth tests for poker hand ranking.

Why this file exists
--------------------
CLAUDE.md forbids letting an AI model evaluate a hand or read a board. So the
answers here come from two places, and neither of them is a model:

1. The hands themselves are textbook cases whose correct ranking is fixed by
   the published rules of poker (a royal flush beats a full house, a straight
   beats two pair, the higher kicker wins an otherwise identical two pair).
2. The ranking under test is produced by `treys`, a real external MIT-licensed
   hand evaluator (https://github.com/ihendley/treys), whose last release was
   2022-06-21. It descends from Will Drevo's `deuces` through an intermediate
   fork (Drevo's `deuces` -> msaindon's `deuces` -> `treys`). No hand-strength
   logic is written here; this module only feeds cards in and compares the
   numbers that come out.

What this fixture does and does not cover
-----------------------------------------
These cases pin `treys`' own rank scale (1 = best, 7462 = worst) and its own
category names, on a standard 52-card deck. They are not engine-neutral. Aiming
them at another evaluation path -- the vendored `poker_ai` engine or anything
that replaces it -- needs an adapter that maps that engine's rank scale and
category names onto the ones asserted here, and only makes sense once that
engine is actually dealing a full 52-card deck rather than its current default
20-card short deck (see CLAUDE.md).

Running it
----------
    python3 -m venv .venv
    .venv/bin/pip install -r tests/ground_truth/requirements.txt
    .venv/bin/python -m pytest tests/ground_truth -v

Reading treys' numbers
----------------------
`Evaluator.evaluate` returns a rank where LOWER IS STRONGER: 1 is a royal flush
and 7462 is the worst possible five-card hand (7-5-4-3-2 offsuit). Every
comparison below goes through `assert_beats`, so that inversion is stated once
and `test_lower_rank_is_the_stronger_hand` pins it down.
"""

from __future__ import annotations

import pytest
from treys import Card, Evaluator

EVALUATOR = Evaluator()

# treys' own extremes, restated as named constants for the direction test.
BEST_POSSIBLE_RANK = 1
WORST_POSSIBLE_RANK = 7462


def parse(cards: str) -> list[int]:
    """Turn "As Ks" into treys card integers. Rank char + suit char, e.g. Td, 9h."""
    return [Card.new(card) for card in cards.split()]


def evaluate_five_card_rank(hole: str, board: str) -> int:
    """The real evaluator's rank for a hand. Lower is stronger."""
    return EVALUATOR.evaluate(parse(hole), parse(board))


def category_of(hole: str, board: str) -> str:
    """The evaluator's name for the hand's category, e.g. "Full House"."""
    rank = evaluate_five_card_rank(hole, board)
    return EVALUATOR.class_to_string(EVALUATOR.get_rank_class(rank))


def assert_beats(
    winner_hole: str,
    loser_hole: str,
    board: str,
    winner_category: str,
    loser_category: str,
) -> None:
    """Assert the winner's hand outranks the loser's on a shared board.

    Also asserts each side made the category we expect, so a test cannot pass
    for the wrong reason (e.g. a board that accidentally hands someone a flush).
    """
    winner_rank = evaluate_five_card_rank(winner_hole, board)
    loser_rank = evaluate_five_card_rank(loser_hole, board)

    assert category_of(winner_hole, board) == winner_category, (
        f"{winner_hole} on {board} was not a {winner_category}"
    )
    assert category_of(loser_hole, board) == loser_category, (
        f"{loser_hole} on {board} was not a {loser_category}"
    )
    assert winner_rank < loser_rank, (
        f"{winner_hole} ({winner_category}, rank {winner_rank}) should beat "
        f"{loser_hole} ({loser_category}, rank {loser_rank}) on {board}"
    )


def test_lower_rank_is_the_stronger_hand() -> None:
    """Pin the direction of treys' scale, which every other test depends on."""
    royal_flush = evaluate_five_card_rank("As Ks", "Qs Js Ts")
    worst_hand = evaluate_five_card_rank("7c 5d", "4h 3s 2c")

    assert royal_flush == BEST_POSSIBLE_RANK
    assert worst_hand == WORST_POSSIBLE_RANK
    assert royal_flush < worst_hand


def test_royal_flush_beats_full_house() -> None:
    """Board Ts Js Qs 9h 9d: As Ks makes the royal, Qh Qd makes queens full."""
    assert_beats(
        winner_hole="As Ks",
        loser_hole="Qh Qd",
        board="Ts Js Qs 9h 9d",
        winner_category="Royal Flush",
        loser_category="Full House",
    )


def test_straight_beats_two_pair() -> None:
    """Two pair LOSES to a straight.

    Board 9c 8d 7h 2s 3c: Th Jd makes J-high straight, 9h 8s makes nines and
    eights. The two pair looks big and is still second best.
    """
    assert_beats(
        winner_hole="Th Jd",
        loser_hole="9h 8s",
        board="9c 8d 7h 2s 3c",
        winner_category="Straight",
        loser_category="Two Pair",
    )


def test_two_pair_with_ace_kicker_beats_same_two_pair_with_queen_kicker() -> None:
    """The close one: identical two pair, decided only by the fifth card.

    Board Kd Ks 7h 7d 3c already is kings and sevens. Both players play those
    four cards; the ace kicker plays over the queen kicker.
    """
    assert_beats(
        winner_hole="Ac 5d",
        loser_hole="Qc 5s",
        board="Kd Ks 7h 7d 3c",
        winner_category="Two Pair",
        loser_category="Two Pair",
    )


def test_higher_two_pair_beats_lower_two_pair() -> None:
    """Board Jh 8c 5d 2s 3h: jacks-and-eights over jacks-and-fives."""
    assert_beats(
        winner_hole="Jc 8d",
        loser_hole="Jd 5s",
        board="Jh 8c 5d 2s 3h",
        winner_category="Two Pair",
        loser_category="Two Pair",
    )


def test_flush_beats_straight() -> None:
    """Board Ah Kh Qd Jh 2h: 4h 3h makes the flush, Tc 9d makes Broadway."""
    assert_beats(
        winner_hole="4h 3h",
        loser_hole="Tc 9d",
        board="Ah Kh Qd Jh 2h",
        winner_category="Flush",
        loser_category="Straight",
    )


def test_four_of_a_kind_beats_full_house() -> None:
    """Board 6c 6d 9h 9s 2c: 6h 6s makes quad sixes, 9c 4d makes nines full."""
    assert_beats(
        winner_hole="6h 6s",
        loser_hole="9c 4d",
        board="6c 6d 9h 9s 2c",
        winner_category="Four of a Kind",
        loser_category="Full House",
    )


def test_wheel_is_the_weakest_straight() -> None:
    """A-2-3-4-5 is a straight, and the lowest one: 6-high beats it.

    Board 3c 4d 5h 9s Jc: Ah 2d makes the wheel, 6h 7s makes a 7-high straight.
    """
    assert_beats(
        winner_hole="6h 7s",
        loser_hole="Ah 2d",
        board="3c 4d 5h 9s Jc",
        winner_category="Straight",
        loser_category="Straight",
    )


def test_identical_hands_tie() -> None:
    """Both players play the board, so the ranks must be exactly equal."""
    board = "As Ks Qs Js Ts"
    assert evaluate_five_card_rank("2c 3d", board) == evaluate_five_card_rank(
        "4h 5s", board
    )


# One exact five-card example of every category, strongest first. Passing two
# hole cards and a three-card board means the hand is exactly these five cards,
# with nothing for the evaluator to choose between.
CATEGORY_LADDER: list[tuple[str, str, str]] = [
    ("Royal Flush", "As Ks", "Qs Js Ts"),
    ("Straight Flush", "9h 8h", "7h 6h 5h"),
    ("Four of a Kind", "5c 5d", "5h 5s 2c"),
    ("Full House", "6c 6d", "6h 9s 9c"),
    ("Flush", "Ad Jd", "8d 5d 3d"),
    ("Straight", "9c 8d", "7h 6s 5c"),
    ("Three of a Kind", "Qc Qd", "Qh 7s 2d"),
    ("Two Pair", "Kc Kd", "4h 4s 9c"),
    ("Pair", "Ac Ad", "9h 6s 2c"),
    ("High Card", "Ac Qd", "9h 6s 2c"),
]


@pytest.mark.parametrize("expected_category, hole, board", CATEGORY_LADDER)
def test_category_is_named_correctly(
    expected_category: str, hole: str, board: str
) -> None:
    assert category_of(hole, board) == expected_category


def test_categories_rank_in_the_textbook_order() -> None:
    """Every category strictly outranks the one below it, top to bottom."""
    ranked = [
        (category, evaluate_five_card_rank(hole, board))
        for category, hole, board in CATEGORY_LADDER
    ]
    for (stronger_name, stronger), (weaker_name, weaker) in zip(ranked, ranked[1:]):
        assert stronger < weaker, (
            f"{stronger_name} (rank {stronger}) should outrank "
            f"{weaker_name} (rank {weaker})"
        )
