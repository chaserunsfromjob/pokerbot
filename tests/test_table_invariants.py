"""The seven invariants the table has to satisfy before any score is believed.

They are `EVALUATION_STRATEGY.md` section 4.5, one test each, run at every seat
count from two to nine:

  I1  chips are conserved
  I2  no stack goes negative and nobody puts in more than they had
  I3  side pots are paid correctly when players are all-in for different
      amounts -- the bug that only exists at three seats or more
  I4  every action taken is legal under the engine's own rules
  I5  the button, the blinds and the acting order rotate correctly, including
      the heads-up reversal
  I6  the same seed and the same commit replay byte-identical hand records
  I7  the pot equals what was put in, and the engine's showdown agrees with
      the outside evaluator

A failure raises `pokerbot.InvariantViolation`, and `conftest.py` turns that
into the end of the whole run. A seat count that cannot be dealt is skipped
with the engine's own reason and printed as NOT RUN, never as a pass.
"""

from __future__ import annotations

import functools
import pathlib
import random
import subprocess
import sys

import pytest

from pokerbot import Action, Hand, IllegalActionError, Table, TableConfig, deal_check
from pokerbot.invariants import require
from reference_payouts import expected_payouts, ranks_for

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SEAT_COUNTS = list(range(2, 10))
TOLERANCE = 1e-9
HANDS_PER_SEAT_COUNT = 60
SMALL_BLIND = 50
BIG_BLIND = 100

#: Uniform play folds most hands away before anyone sees a board, so the corpus
#: is played with the fold weighted down. This is a way of walking hands to the
#: end, not a strategy, and nothing in the package depends on it.
ACTION_WEIGHTS = {
    Action.FOLD: 1,
    Action.CALL: 6,
    Action.HALF_POT: 2,
    Action.POT: 1,
    Action.ALL_IN: 1,
}


def seats_param(name: str = "seats"):
    return pytest.mark.parametrize(name, SEAT_COUNTS, ids=[str(n) for n in SEAT_COUNTS])


def require_dealable(seats: int) -> None:
    """Skip with the engine's reason when a seat count will not deal."""
    ok, reason = deal_check(seats)
    if not ok:
        pytest.skip(f"NOT RUN: {seats} seats would not deal -- {reason}")


def uneven_stacks(seats: int) -> tuple[int, ...]:
    """Deliberately unequal stacks, so all-ins land at different amounts."""
    return tuple(BIG_BLIND * depth for depth in (4, 7, 12, 20, 33, 55, 90, 140, 200)[:seats])


def make_table(seats: int, stacks: tuple[int, ...] | None = None) -> Table:
    return Table(
        TableConfig(
            seats=seats,
            small_blind=SMALL_BLIND,
            big_blind=BIG_BLIND,
            stacks=stacks if stacks is not None else (),
        )
    )


def play_out(hand: Hand, rng: random.Random, weights=ACTION_WEIGHTS) -> list[tuple[int, Action]]:
    """Play a hand to the end, checking every move against the engine's list."""
    taken: list[tuple[int, Action]] = []
    while not hand.is_finished:
        seat = hand.current_seat()
        menu = hand.legal_actions()
        require(bool(menu), "I4", f"seat {seat} was asked to act with no legal move")
        choice = rng.choices(menu, weights=[weights[a] for a in menu], k=1)[0]
        require(
            choice in hand.legal_actions(),
            "I4",
            f"seat {seat} was about to take {choice} which the engine does not allow",
        )
        hand.apply_action(choice)
        taken.append((seat, choice))
    return taken


@functools.lru_cache(maxsize=None)
def corpus(seats: int) -> tuple:
    """A fixed set of finished hands at this seat count, played once and reused.

    Stacks are unequal so that all-ins land at different amounts, and the
    button moves every hand so no single seat's arrangement is over-tested.
    """
    table = make_table(seats, uneven_stacks(seats))
    records = []
    for i in range(HANDS_PER_SEAT_COUNT):
        hand = table.new_hand(seed=1_000_000 + i, button=i % seats)
        play_out(hand, random.Random(500_000 + i))
        records.append(hand.record)
    return tuple(records)


def showdowns(records) -> list:
    """The hands where two or more seats were still live at the end."""
    return [r for r in records if sum(1 for f in r.folded if not f) >= 2]


# --------------------------------------------------------------------------
# I1 -- chips are conserved
# --------------------------------------------------------------------------


@pytest.mark.invariant("I1")
@seats_param()
def test_i1_chips_are_conserved(seats):
    require_dealable(seats)
    for record in corpus(seats):
        total = sum(record.net)
        require(
            abs(total) < TOLERANCE,
            "I1",
            f"the seats' wins and losses add up to {total}, not zero",
            record.to_json(),
        )


# --------------------------------------------------------------------------
# I2 -- no stack goes negative, nobody puts in more than they had
# --------------------------------------------------------------------------


@pytest.mark.invariant("I2")
@seats_param()
def test_i2_no_seat_overspends_or_goes_negative(seats):
    require_dealable(seats)
    for record in corpus(seats):
        for seat in range(seats):
            start = record.stacks[seat]
            put_in = record.contributions[seat]
            require(
                put_in <= start + TOLERANCE,
                "I2",
                f"seat {seat} put in {put_in} from a stack of {start}",
                record.to_json(),
            )
            finish = start + record.net[seat]
            require(
                finish >= -TOLERANCE,
                "I2",
                f"seat {seat} finished the hand with {finish} chips",
                record.to_json(),
            )


# --------------------------------------------------------------------------
# I3 -- side pots, at three seats and up
# --------------------------------------------------------------------------


@pytest.mark.invariant("I3")
@seats_param()
def test_i3_side_pots_are_paid_correctly(seats):
    require_dealable(seats)
    if seats < 3:
        pytest.skip(
            "NOT RUN: a side pot needs a third player to be all-in against, so "
            "this invariant does not exist at two seats "
            "(EVALUATION_STRATEGY.md section 4.5, I3)"
        )
    table = make_table(seats, uneven_stacks(seats))
    checked = 0
    deepest = 0
    for i in range(seats):
        hand = table.new_hand(seed=4_000_000 + i, button=i)
        while not hand.is_finished:
            menu = hand.legal_actions()
            hand.apply_action(Action.ALL_IN if Action.ALL_IN in menu else Action.CALL)
        record = hand.record

        live = [seat for seat in range(seats) if not record.folded[seat]]
        require(
            len(live) >= 3,
            "I3",
            f"the all-in hand left only {len(live)} seats live, so there is no side pot to check",
            record.to_json(),
        )
        levels = sorted({record.contributions[seat] for seat in live})
        require(
            len(levels) >= 2,
            "I3",
            f"the live seats all put in the same amount {levels}; this hand "
            "builds no unequal all-in and so tests no side pot",
            record.to_json(),
        )
        deepest = max(deepest, len(levels))
        require(
            len(record.board) == 5,
            "I3",
            f"an all-in hand should run the board out, got {record.board}",
            record.to_json(),
        )

        expected = expected_payouts(record.contributions, record.folded, ranks_for(record))
        for seat in range(seats):
            require(
                abs(expected[seat] - record.payouts[seat]) < TOLERANCE,
                "I3",
                f"seat {seat} was paid {record.payouts[seat]} by the engine but "
                f"the side-pot split of contributions {record.contributions} "
                f"pays it {expected[seat]}",
                record.to_json(),
            )
        checked += 1
    require(checked == seats, "I3", f"only {checked} of {seats} button positions were checked")
    require(
        deepest >= 3,
        "I3",
        f"no hand at {seats} seats produced more than {deepest - 1} side pot(s); "
        "the check never saw a pot split three ways by stack depth",
    )


# --------------------------------------------------------------------------
# I4 -- every action legal under the engine's own rules
# --------------------------------------------------------------------------


@pytest.mark.invariant("I4")
@seats_param()
def test_i4_only_legal_actions_are_ever_taken(seats):
    require_dealable(seats)
    menu = set(Action)
    for record in corpus(seats):
        for event in record.events:
            if event.kind != "action":
                continue
            require(
                event.action in {a.value for a in menu},
                "I4",
                f"a move called {event.action!r} was recorded, which is outside "
                "the fchpa menu {fold, call, half pot, pot, all-in}",
                record.to_json(),
            )

    # And the adapter refuses an illegal move rather than passing it through.
    table = make_table(seats)
    hand = table.new_hand(seed=99, button=0)
    offered = set(hand.legal_actions())
    require(
        Action.CALL in offered,
        "I4",
        f"the first seat to act was not offered a call; menu was {offered}",
    )
    refused = [a for a in Action if a not in offered]
    for action in refused:
        with pytest.raises(IllegalActionError):
            hand.apply_action(action)
    with pytest.raises(IllegalActionError):
        hand.apply_action("call")  # not one of the five moves at all

    # ...and it refuses to act at all once the hand is over.
    play_out(hand, random.Random(99))
    with pytest.raises(IllegalActionError):
        hand.apply_action(Action.CALL)


# --------------------------------------------------------------------------
# I5 -- button, blinds and acting order, including heads-up
# --------------------------------------------------------------------------


def expected_positions(seats: int, button: int) -> tuple[int, int, int, int]:
    """(small blind, big blind, first to act pre-flop, first to act after).

    Heads-up is the special case: the button posts the small blind and acts
    first before the flop, then acts last on every street after it.
    """
    if seats == 2:
        small_blind = button
        big_blind = (button + 1) % seats
        return small_blind, big_blind, small_blind, big_blind
    small_blind = (button + 1) % seats
    big_blind = (button + 2) % seats
    return small_blind, big_blind, (button + 3) % seats, small_blind


@pytest.mark.invariant("I5")
@seats_param()
def test_i5_button_blinds_and_order_rotate(seats):
    require_dealable(seats)
    table = make_table(seats)
    for button in range(seats):
        small_blind, big_blind, first_pre, first_post = expected_positions(seats, button)
        hand = table.new_hand(seed=7_000_000 + button, button=button)

        posted = hand.contributions()
        for seat in range(seats):
            want = SMALL_BLIND if seat == small_blind else BIG_BLIND if seat == big_blind else 0
            require(
                abs(posted[seat] - want) < TOLERANCE,
                "I5",
                f"{seats} seats, button {button}: seat {seat} posted {posted[seat]}, expected {want}",
            )
        require(
            hand.small_blind_seat == small_blind and hand.big_blind_seat == big_blind,
            "I5",
            f"{seats} seats, button {button}: the adapter calls seat "
            f"{hand.small_blind_seat} the small blind and {hand.big_blind_seat} "
            f"the big blind, expected {small_blind} and {big_blind}",
        )

        # Everyone calls, so the pre-flop order is the full ring once round.
        preflop_order = []
        while not hand.is_finished and hand.street == 0:
            preflop_order.append(hand.current_seat())
            hand.apply_action(Action.CALL)
        want_pre = [(first_pre + i) % seats for i in range(seats)]
        require(
            preflop_order == want_pre,
            "I5",
            f"{seats} seats, button {button}: acted pre-flop in order "
            f"{preflop_order}, expected {want_pre}",
        )

        require(
            not hand.is_finished and hand.street == 1,
            "I5",
            f"{seats} seats, button {button}: the hand did not reach the flop after everyone called",
        )
        flop_order = []
        while not hand.is_finished and hand.street == 1:
            flop_order.append(hand.current_seat())
            hand.apply_action(Action.CALL)
        want_post = [(first_post + i) % seats for i in range(seats)]
        require(
            flop_order == want_post,
            "I5",
            f"{seats} seats, button {button}: acted on the flop in order "
            f"{flop_order}, expected {want_post}",
        )


# --------------------------------------------------------------------------
# I6 -- the same seed and the same commit replay the same bytes
# --------------------------------------------------------------------------


def replay_bytes(seats: int, seed: int, button: int) -> bytes:
    table = make_table(seats, uneven_stacks(seats))
    hand = table.new_hand(seed=seed, button=button)
    play_out(hand, random.Random(seed))
    return hand.record.to_bytes()


@pytest.mark.invariant("I6")
@seats_param()
def test_i6_same_seed_same_commit_replays_identically(seats):
    require_dealable(seats)
    for seed in (11, 12, 13):
        first = replay_bytes(seats, seed, button=seed % seats)
        second = replay_bytes(seats, seed, button=seed % seats)
        require(
            first == second,
            "I6",
            f"{seats} seats, seed {seed}: two replays of the same hand differ",
            f"{first!r}\n{second!r}",
        )
    different = replay_bytes(seats, 14, button=14 % seats)
    require(
        different != replay_bytes(seats, 11, button=11 % seats),
        "I6",
        f"{seats} seats: two different seeds produced the identical record, "
        "so the seed is not reaching the deal",
    )


@pytest.mark.invariant("I6")
@seats_param()
def test_i6_holds_across_separate_runs_of_the_program(seats):
    """The same seed in two separate runs of the program, byte for byte.

    In-process repetition would not catch a record whose bytes depend on
    something that varies per run, such as the order of a dictionary seeded by
    the process's own hash randomisation.
    """
    require_dealable(seats)
    command = [
        sys.executable,
        "-m",
        "pokerbot.replay",
        "--seats",
        str(seats),
        "--seed",
        "20260916",
        "--button",
        str(seats - 1),
    ]
    runs = []
    for _ in range(2):
        done = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, check=False)
        require(
            done.returncode == 0,
            "I6",
            f"replaying {seats} seats in a separate run exited {done.returncode}",
            done.stderr.decode("utf-8", "replace"),
        )
        runs.append(done.stdout)
    require(
        runs[0] == runs[1],
        "I6",
        f"{seats} seats: two separate runs of the same seed produced different records",
        f"{runs[0]!r}\n{runs[1]!r}",
    )
    require(
        b'"commit":' in runs[0],
        "I6",
        "the hand record does not say which commit produced it",
        runs[0].decode("utf-8", "replace"),
    )


# --------------------------------------------------------------------------
# I7 -- the pot adds up, and the engine's showdown agrees with treys
# --------------------------------------------------------------------------


@pytest.mark.invariant("I7")
@seats_param()
def test_i7_pot_adds_up_and_showdown_matches_ground_truth(seats):
    require_dealable(seats)
    records = corpus(seats)
    for record in records:
        pot = sum(record.contributions)
        require(
            abs(record.pot - pot) < TOLERANCE,
            "I7",
            f"the recorded pot is {record.pot} but the seats put in {pot}",
            record.to_json(),
        )
        paid = sum(record.payouts)
        require(
            abs(paid - pot) < TOLERANCE,
            "I7",
            f"the pot was {pot} but {paid} was paid out",
            record.to_json(),
        )

    contested = showdowns(records)
    require(
        len(contested) >= 5,
        "I7",
        f"only {len(contested)} of {len(records)} hands at {seats} seats reached "
        "a showdown, which is too few to test the showdown against the evaluator",
    )

    compared = 0
    for record in contested:
        if len(record.board) != 5:
            continue
        compared += 1
        expected = expected_payouts(record.contributions, record.folded, ranks_for(record))
        for seat in range(seats):
            require(
                abs(expected[seat] - record.payouts[seat]) < TOLERANCE,
                "I7",
                f"seat {seat} was paid {record.payouts[seat]} by the engine, but "
                f"treys ranks the live hands so that it should be paid {expected[seat]}",
                record.to_json(),
            )
    require(
        compared >= 5,
        "I7",
        f"only {compared} of the {len(contested)} showdowns at {seats} seats had a "
        "five-card board, which is too few to test the showdown against the evaluator",
    )
