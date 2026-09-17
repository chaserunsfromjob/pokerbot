"""A second opinion on who should be paid what, for the tests only.

The adapter in `pokerbot/` never works out who won -- it reads that out of the
engine. That is the rule, and it is also what makes the invariants worth
running: a check of our payouts against our own hand evaluator would only be
checking us against ourselves.

So the check needs an outside opinion, and this file is it. Hand ranking comes
from `treys`, the external library `CLAUDE.md` names as the ground-truth
evaluator for tests; the division of the pot is worked out here from the
contributions alone.

How the division works, in plain words. When someone runs out of chips in the
middle of a hand, they can only win as much as they put in from each of the
others. So the money is sliced into layers: the first layer is everyone's
first N chips where N is the smallest amount anyone put in, the next layer is
everyone's chips above that up to the next-smallest amount, and so on. Each
layer is won by the best hand among the players who paid into it in full and
did not fold. The layer that only one player paid into is the part of a bet
nobody matched, and it comes straight back to them. The usual name for a layer
above the first is a **side pot**.

Nothing here is on the bot's import path. It is test scaffolding.
"""

from __future__ import annotations

from treys import Card, Evaluator

_EVALUATOR = Evaluator()


def hand_rank(hole: list[str], board: list[str]) -> int:
    """`treys`' rank for a hand: the lower the number, the better the hand."""
    if len(board) != 5:
        raise ValueError(f"a showdown needs five board cards, got {board}")
    if len(hole) != 2:
        raise ValueError(f"a hold'em hand is two cards, got {hole}")
    return _EVALUATOR.evaluate(
        [Card.new(c) for c in board], [Card.new(c) for c in hole]
    )


def expected_payouts(
    contributions: list[float],
    folded: list[bool],
    ranks: list[int | None],
) -> list[float]:
    """What each seat should be handed, worked out from the contributions.

    `ranks` is one `treys` rank per seat, or None for a seat that folded and
    therefore never shows a hand.
    """
    seats = len(contributions)
    payouts = [0.0] * seats
    levels = sorted({c for c in contributions if c > 0})
    previous = 0.0
    for level in levels:
        layer = 0.0
        for seat in range(seats):
            layer += max(0.0, min(contributions[seat], level) - min(contributions[seat], previous))
        eligible = [
            seat
            for seat in range(seats)
            if not folded[seat] and contributions[seat] >= level
        ]
        if not eligible:
            raise AssertionError(
                f"no live seat is eligible for the layer up to {level}: "
                f"contributions={contributions} folded={folded}"
            )
        if len(eligible) == 1:
            winners = eligible
        else:
            best = min(ranks[seat] for seat in eligible)
            winners = [seat for seat in eligible if ranks[seat] == best]
        for seat in winners:
            payouts[seat] += layer / len(winners)
        previous = level
    return payouts


def ranks_for(record) -> list[int | None]:
    """A `treys` rank for every seat that is still live at the showdown."""
    return [
        None if record.folded[seat] else hand_rank(record.hole_cards[seat], record.board)
        for seat in range(record.seats)
    ]
