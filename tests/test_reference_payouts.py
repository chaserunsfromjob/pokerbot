"""Check the checker.

`reference_payouts.expected_payouts` is what invariants I3 and I7 hold the
engine to. If it were wrong it would either wave a real payout bug through or
fail an honest table, so it gets its own worked examples with the answer
written out by hand.

Not one of the seven invariants, so no marker and no row in the seat table.
"""

from __future__ import annotations

import pytest

from reference_payouts import expected_payouts


def test_worked_example_two_side_pots_and_a_split():
    """Four seats, three different all-in amounts, one folder, one tie.

    Seat 0 is all-in for 100 and has the best hand. Seats 1 and 2 are all-in
    for 400 with hands that tie each other. Seat 3 put in 250 and folded.

    By hand: the first 100 from all four seats makes 400 and seat 0 wins it.
    The next 150 from seats 1, 2 and 3 makes 450, which only seats 1 and 2 can
    win, so they split it 225 each. The last 150 from seats 1 and 2 makes 300,
    split 150 each. Totals: 400, 375, 375, 0 -- and 1,150 was put in.
    """
    payouts = expected_payouts(
        contributions=[100, 400, 400, 250],
        folded=[False, False, False, True],
        ranks=[1, 10, 10, None],
    )
    assert payouts == [400, 375, 375, 0]
    assert sum(payouts) == sum([100, 400, 400, 250])


def test_the_part_of_a_bet_nobody_matched_comes_back():
    """Seat 1 bets 200 into a seat that folded after 50; 150 is unmatched."""
    payouts = expected_payouts(
        contributions=[50, 200],
        folded=[True, False],
        ranks=[None, 5],
    )
    assert payouts == [0, 250]


def test_the_best_hand_takes_it_all_when_everyone_paid_the_same():
    payouts = expected_payouts(
        contributions=[300, 300, 300],
        folded=[False, False, False],
        ranks=[9, 2, 400],
    )
    assert payouts == [0, 900, 0]


def test_a_layer_with_no_live_claimant_is_an_error_not_a_guess():
    with pytest.raises(AssertionError):
        expected_payouts(contributions=[100, 300], folded=[False, True], ranks=[7, None])
