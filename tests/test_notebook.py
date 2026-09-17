"""The notebook, checked against the document that specifies it.

Five things are checked here, and `tests/test_notebook_irc.py` checks the
sixth:

1. the report reproduces `OPPONENT_MODEL_DESIGN.md` section 4.5's worked
   example number for number from its counts, with the arithmetic written out
   in the test's own docstring;
2. every row of section 4.7's edge-case table has a named fixture;
3. no stat reads a hole card or a board card, checked by playing a hand
   through the arena and handing the notebook a record whose card fields
   explode when they are touched;
4. the same records give the same profile bytes;
5. the pieces section 4.3 and section 4.4 are made of -- the two lines, the
   baseline's fallback chain, the splits, the hysteresis -- behave as written.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from pokerbot import notebook
from pokerbot.notebook import (
    Notebook,
    NotebookConfig,
    UnusableHand,
    band_of,
    blind_view,
)
from pokerbot.record import SCHEMA, Event, HandRecord
from pokerbot import profile as profile_module

ROOT = Path(__file__).resolve().parents[1]
WORKED_EXAMPLE = ROOT / "tests" / "data" / "profile_worked_example.json"

#: Section 4.5's block, verbatim, as the document prints it.
WORKED_EXAMPLE_REPORT = """\
  hands       412
  vpip        0.42  (conf 0.89)   raw 0.43
  pfr         0.11  (conf 0.89)   raw 0.10
  gap         0.31
  limp        0.38  (conf 0.83)
  three_bet   0.02  (conf 0.72)
  check_raise 0.01  (conf 0.85)
  afq         0.13  (conf 0.97)
  afq[flop]   0.18  (conf 0.87)
  wtsd        0.42  (conf 0.93)
  bucket      STATION
  flags       NEVER_FOLDS_POSTFLOP, LIMPS, NEVER_RAISES"""


# ---------------------------------------------------------------------------
# building a hand by hand, with no engine in the way
# ---------------------------------------------------------------------------


def make_record(
    seats: int,
    button: int,
    actions,
    *,
    streets_dealt=(),
    stacks=None,
    big_blind: float = 100.0,
    small_blind: float = 50.0,
    extra_blinds=(),
    net=None,
    finished: bool = True,
) -> HandRecord:
    """One hand, written out move by move, the way the arena would record it.

    `actions` is a list of `(street, seat, move, amount)`, in the order they
    happened; `streets_dealt` names the streets whose cards came out, which
    the record marks with a board event. No cards are put in: the notebook
    cannot see them, so a fixture that has to name one would be testing
    something else.
    """
    stacks = list(stacks if stacks is not None else [10_000.0] * seats)
    sb_seat = button if seats == 2 else (button + 1) % seats
    bb_seat = (button + 1) % seats if seats == 2 else (button + 2) % seats
    events: list[Event] = []
    posted = {sb_seat: small_blind, bb_seat: big_blind}
    for seat, amount in extra_blinds:
        posted[seat] = posted.get(seat, 0.0) + amount
    for seat in sorted(posted):
        events.append(
            Event(index=len(events), kind="blind", street=0, seat=seat, amount=posted[seat])
        )
    contributions = [posted.get(s, 0.0) for s in range(seats)]
    folded = [False] * seats
    for street in sorted(streets_dealt):
        events.append(Event(index=len(events), kind="board", street=street))
    for street, seat, move, amount in actions:
        events.append(
            Event(
                index=len(events),
                kind="action",
                street=street,
                seat=seat,
                action=move,
                amount=float(amount),
            )
        )
        contributions[seat] += float(amount)
        if move == "fold":
            folded[seat] = True
    net = list(net if net is not None else [0.0] * seats)
    return HandRecord(
        schema=SCHEMA,
        commit="fixture",
        seed=0,
        seats=seats,
        button=button,
        small_blind=int(small_blind),
        big_blind=int(big_blind),
        stacks=stacks,
        engine="fixture",
        betting_abstraction="fchpa",
        game_string="fixture",
        events=events,
        hole_cards=[[] for _ in range(seats)],
        board=[],
        contributions=contributions,
        payouts=[c + n for c, n in zip(contributions, net)],
        net=net,
        folded=folded,
        pot=sum(contributions),
        finished=finished,
    )


SIX = {seat: f"p{seat}" for seat in range(6)}


def counted(book: Notebook, player: str, key: str) -> tuple[float, float]:
    return book.tally(player, key)


# ---------------------------------------------------------------------------
# 1. the worked example
# ---------------------------------------------------------------------------


def test_worked_example_reproduces_section_4_5_number_for_number():
    """Section 4.5's report, from section 4.5's counts, to the last digit.

    Every line below is `rate = (BASELINE*s + k)/(s + n)` and
    `confidence = n/(n + s)` from section 4.3, with `s` the stat's
    `PRIOR_STRENGTH`, worked out by hand:

      vpip         (0.30*50 + 177)/(50 + 412) = 192/462     = 0.41558 -> 0.42
                   conf 412/462 = 0.89177 -> 0.89 ; raw 177/412 = 0.42961 -> 0.43
      pfr          (0.20*50 + 41)/(50 + 412)  = 51/462      = 0.11039 -> 0.11
                   conf 412/462 = 0.89177 -> 0.89 ; raw 41/412  = 0.09951 -> 0.10
      gap          0.41558 - 0.11039 = 0.30519 -> 0.31
      limp         (0.15*50 + 106)/(50 + 250) = 113.5/300   = 0.37833 -> 0.38
                   conf 250/300 = 0.83333 -> 0.83
      three_bet    (0.07*25 + 0)/(25 + 63)    = 1.75/88     = 0.01989 -> 0.02
                   conf 63/88 = 0.71591 -> 0.72
      check_raise  (0.06*25 + 0)/(25 + 140)   = 1.5/165     = 0.00909 -> 0.01
                   conf 140/165 = 0.84848 -> 0.85
      afq          (0.30*25 + 92)/(25 + 768)  = 99.5/793    = 0.12547 -> 0.13
                   conf 768/793 = 0.96847 -> 0.97
      afq[flop]    (0.30*25 + 27)/(25 + 168)  = 34.5/193    = 0.17876 -> 0.18
                   conf 168/193 = 0.87047 -> 0.87
      wtsd         (0.25*15 + 89)/(15 + 205)  = 92.75/220   = 0.42159 -> 0.42
                   conf 205/220 = 0.93182 -> 0.93

    The bucket is `STATION` because 0.41558 is above `VPIP_SPLIT` 0.28 and
    0.12547 is below `AFQ_SPLIT` 0.50, and the profile clears both gates:
    confidence(vpip) 0.89 >= 0.5 and 412 hands >= MIN_CLASSIFY_HANDS 50.

    The three flags that fire and the four that do not:

      NEVER_FOLDS_POSTFLOP  wtsd        0.42159 - 0.25 = 0.17159 >= 0.15, conf 0.93
      LIMPS                 limp        0.37833 - 0.15 = 0.22833 >= 0.15, conf 0.83
      NEVER_RAISES          three_bet   0.07 - 0.01989 = 0.05011 >= 0.05, conf 0.72
                            check_raise 0.06 - 0.00909 = 0.05091 >= 0.05, conf 0.85
      OVERFOLDS_TO_3BET     blocked: conf(fold_to_three_bet) = 9/34 = 0.26 < 0.6
      NEVER_FOLDS_TO_3BET   blocked by the same 0.26
      OVERFOLDS_TO_CBET     fold_to_cbet[flop] = 26.5/87 = 0.30460, *below* 0.50
      OVERFOLDS_BLINDS      fold_to_steal      = 31.5/80 = 0.39375, *below* 0.50

    They print loudest first -- 0.93, then 0.83, then NEVER_RAISES at its
    weaker leg's 0.72 -- which is the order section 4.5 prints them in.
    """
    payload = json.loads(WORKED_EXAMPLE.read_text())
    profile = profile_module.profile_from_counts(payload)

    assert profile_module.render(profile) == WORKED_EXAMPLE_REPORT

    assert profile.reading("vpip").rate == pytest.approx(192 / 462)
    assert profile.reading("vpip").confidence == pytest.approx(412 / 462)
    assert profile.reading("pfr").rate == pytest.approx(51 / 462)
    assert profile.reading("limp").rate == pytest.approx(113.5 / 300)
    assert profile.reading("three_bet").rate == pytest.approx(1.75 / 88)
    assert profile.reading("check_raise").rate == pytest.approx(1.5 / 165)
    assert profile.reading("afq").rate == pytest.approx(99.5 / 793)
    assert profile.reading("afq[flop]").rate == pytest.approx(34.5 / 193)
    assert profile.reading("wtsd").rate == pytest.approx(92.75 / 220)
    assert profile.reading("fold_to_three_bet").confidence == pytest.approx(9 / 34)
    assert profile.bucket == "STATION"
    assert profile.flags == ("NEVER_FOLDS_POSTFLOP", "LIMPS", "NEVER_RAISES")
    # Section 4.5: this profile is not a near-boundary call on either axis, so
    # the report prints no such mark.
    assert profile.near_boundary == ()


def test_worked_example_through_the_command_line():
    """`python -m pokerbot.profile <name> --counts ...` prints the same block."""
    done = subprocess.run(
        [sys.executable, "-m", "pokerbot.profile", "seat3_alias", "--counts", str(WORKED_EXAMPLE)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert done.stdout.rstrip("\n") == WORKED_EXAMPLE_REPORT


def test_the_worked_examples_margins_are_the_ones_section_4_5_quotes():
    """Section 4.5 quotes 0.172, 0.228, 0.050 and 0.051; here they are."""
    payload = json.loads(WORKED_EXAMPLE.read_text())
    profile = profile_module.profile_from_counts(payload)
    wtsd = profile.reading("wtsd")
    limp = profile.reading("limp")
    three_bet = profile.reading("three_bet")
    check_raise = profile.reading("check_raise")
    assert round(wtsd.rate - wtsd.baseline, 3) == 0.172
    assert round(limp.rate - limp.baseline, 3) == 0.228
    assert round(three_bet.baseline - three_bet.rate, 3) == 0.050
    assert round(check_raise.baseline - check_raise.rate, 3) == 0.051


# ---------------------------------------------------------------------------
# 2. section 4.7's edge cases, one named fixture each
# ---------------------------------------------------------------------------
#
# Section 4.7: "Each of these silently corrupts a counter if not handled. Each
# needs a fixture test." The eleven tests below are those eleven rows, in the
# order the table lists them.


def test_edge_case_posting_the_blind_is_not_vpip():
    """Row 1. A big blind who checks their option has not put money in.

    Six seats, button 0, so the small blind is seat 1 and the big blind seat
    2. Seat 3 limps, everyone else folds, and the big blind checks. The limp
    is voluntary; the blind and the check are not.
    """
    record = make_record(
        6,
        0,
        [
            (0, 3, "call", 100),
            (0, 4, "fold", 0),
            (0, 5, "fold", 0),
            (0, 0, "fold", 0),
            (0, 1, "fold", 0),
            (0, 2, "call", 0),
            (1, 2, "call", 0),
            (1, 3, "call", 0),
            (2, 2, "call", 0),
            (2, 3, "call", 0),
            (3, 2, "call", 0),
            (3, 3, "call", 0),
        ],
        streets_dealt=(1, 2, 3),
        net=[0, -50, 100, -100, 0, 0],
    )
    book = Notebook()
    assert book.observe(record, SIX)
    assert counted(book, "p2", "vpip") == (0.0, 1.0)
    assert counted(book, "p3", "vpip") == (1.0, 1.0)
    assert counted(book, "p3", "limp") == (1.0, 1.0)
    # The big blind cannot limp, so no limp opportunity is recorded for them.
    assert counted(book, "p2", "limp") == (0.0, 0.0)
    # A check is not one of afq's four voluntary actions, so it is not in the
    # denominator either -- section 4.2 lists bet, raise, call and fold.
    assert counted(book, "p2", "afq") == (0.0, 0.0)


def test_edge_case_walk_counts_the_hand_and_nothing_positional():
    """Row 2. Everyone folds to the big blind, who never gets to act.

    `hands_dealt` still increments for everybody, and so does `vpip`'s
    denominator, which section 4.2 and Table C both define as "opponent was
    dealt in" -- one opportunity per hand by definition, which is also what
    section 4.5's worked example counts (177 of 412). What the walk gives
    nobody is a postflop spot, and it gives the big blind no chance to act at
    all: no limp opportunity, no `three_bet` spot, no flop.
    """
    record = make_record(
        6,
        0,
        [
            (0, 3, "fold", 0),
            (0, 4, "fold", 0),
            (0, 5, "fold", 0),
            (0, 0, "fold", 0),
            (0, 1, "fold", 0),
        ],
        net=[0, -50, 50, 0, 0, 0],
    )
    book = Notebook()
    assert book.observe(record, SIX)
    for seat in range(6):
        assert book.hands(f"p{seat}") == 1.0
        assert counted(book, f"p{seat}", "vpip") == (0.0, 1.0)
        assert counted(book, f"p{seat}", "wtsd") == (0.0, 0.0)
    # The big blind never acted, so nothing that needs a decision is recorded.
    assert counted(book, "p2", "limp") == (0.0, 0.0)
    assert counted(book, "p2", "three_bet") == (0.0, 0.0)
    assert counted(book, "p2", "afq") == (0.0, 0.0)


def test_edge_case_player_dealt_out_gets_no_hands_dealt():
    """Row 3. A seat that sat out is not a row in the notebook at all."""
    record = make_record(
        6,
        0,
        [
            (0, 3, "fold", 0),
            (0, 4, "fold", 0),
            (0, 5, "fold", 0),
            (0, 0, "fold", 0),
            (0, 1, "fold", 0),
        ],
        net=[0, -50, 50, 0, 0, 0],
    )
    seated = {seat: name for seat, name in SIX.items() if seat != 4}
    book = Notebook()
    assert book.observe(record, seated)
    assert "p4" not in book.players()
    assert book.hands("p3") == 1.0


def test_edge_case_all_in_for_less_than_a_full_raise_counts_as_a_raise():
    """Row 4. An all-in that clears the bet but not by a full raise is a raise.

    Seat 3 opens to 300. Seat 4 has 520 behind and puts it all in: that is
    above the 300 to call but short of the 500 a full raise would need. It
    counts for `pfr` and for `afq`, which is what section 4.7 requires.
    """
    stacks = [10_000.0] * 6
    stacks[4] = 520.0
    record = make_record(
        6,
        0,
        [
            (0, 3, "pot", 300),
            (0, 4, "all_in", 520),
            (0, 5, "fold", 0),
            (0, 0, "fold", 0),
            (0, 1, "fold", 0),
            (0, 2, "fold", 0),
            (0, 3, "fold", 0),
        ],
        stacks=stacks,
        net=[0, -50, -100, -300, 450, 0],
    )
    book = Notebook()
    assert book.observe(record, SIX)
    assert counted(book, "p4", "pfr") == (1.0, 1.0)
    assert counted(book, "p4", "afq") == (1.0, 1.0)
    assert counted(book, "p4", "vpip") == (1.0, 1.0)
    # It also reopened the action for the opener, who folded to it.
    assert counted(book, "p3", "fold_to_three_bet") == (1.0, 1.0)


def test_edge_case_straddle_is_recorded_and_is_not_voluntary():
    """Row 5. A straddle is a forced post, so it is not `vpip`.

    Section 4.7 calls the shift in the opportunity definitions "a schema
    question, not an afterthought". This fixture pins what is counted today --
    the straddle survives into the record as a blind and buys its poster no
    `vpip` -- so that a later change to the definitions is visible rather than
    silent.
    """
    record = make_record(
        6,
        0,
        [
            (0, 4, "fold", 0),
            (0, 5, "fold", 0),
            (0, 0, "fold", 0),
            (0, 1, "fold", 0),
            (0, 2, "fold", 0),
        ],
        extra_blinds=[(3, 200.0)],
        net=[0, -50, -100, 150, 0, 0],
    )
    view = blind_view(record)
    posts = {e.seat: e.amount for e in view.events if e.kind == "blind"}
    assert posts == {1: 50.0, 2: 100.0, 3: 200.0}
    book = Notebook()
    assert book.observe(record, SIX)
    assert counted(book, "p3", "vpip") == (0.0, 1.0)
    assert counted(book, "p3", "pfr") == (0.0, 1.0)


def test_edge_case_player_leaves_and_returns_keeps_one_row():
    """Row 6. The same name across a gap is the same player, with one row."""
    away = {seat: f"p{seat}" for seat in range(6) if seat != 5}
    book = Notebook()
    for hand_number in range(4):
        record = make_record(
            6,
            0,
            [
                (0, 3, "fold", 0),
                (0, 4, "fold", 0),
                (0, 5, "fold", 0),
                (0, 0, "fold", 0),
                (0, 1, "fold", 0),
            ],
            net=[0, -50, 50, 0, 0, 0],
        )
        book.observe(record, SIX if hand_number in (0, 3) else away)
    assert book.hands("p5") == 2.0
    assert book.hands("p3") == 4.0
    assert book.players().count("p5") == 1


def test_edge_case_alias_reuse_is_undetectable_and_decay_is_the_mitigation():
    """Row 7. One name, two humans: one row, and only decay separates them.

    Section 4.7 says so in as many words -- "undetectable in principle" -- so
    what is tested is the mitigation. With a half-life configured, counts from
    before the gap are worth less than counts after it; with the default
    half-life off, a single stream is a single session and nothing is lost.
    """
    raiser = make_record(
        6,
        0,
        [(0, 3, "pot", 300), (0, 4, "fold", 0), (0, 5, "fold", 0),
         (0, 0, "fold", 0), (0, 1, "fold", 0), (0, 2, "fold", 0)],
        net=[0, -50, -100, 150, 0, 0],
    )
    folder = make_record(
        6,
        0,
        [(0, 3, "fold", 0), (0, 4, "fold", 0), (0, 5, "fold", 0),
         (0, 0, "fold", 0), (0, 1, "fold", 0)],
        net=[0, -50, 50, 0, 0, 0],
    )
    book = Notebook(NotebookConfig(half_life=1.0))
    book.observe(raiser, {3: "reused"})
    for _ in range(10):  # ten hands pass with nobody watched
        book.hands_seen += 1
    book.observe(folder, {3: "reused"})
    k, n = counted(book, "reused", "pfr")
    # Eleven hands elapsed between the two sightings -- the ten that passed
    # and the one being counted -- so at a one-hand half-life the first
    # human's hand is worth 2**-11 of the second's.
    assert k == pytest.approx(2.0 ** -11)
    assert n == pytest.approx(1.0 + 2.0 ** -11)

    plain = Notebook()
    plain.observe(raiser, {3: "reused"})
    plain.observe(folder, {3: "reused"})
    assert counted(plain, "reused", "pfr") == (1.0, 2.0)


def test_edge_case_seat_change_never_changes_the_identity():
    """Row 8. `opponent_id` is the name; the seat is a per-hand field."""
    record = make_record(
        6,
        0,
        [(0, 3, "fold", 0), (0, 4, "fold", 0), (0, 5, "fold", 0),
         (0, 0, "fold", 0), (0, 1, "fold", 0)],
        net=[0, -50, 50, 0, 0, 0],
    )
    book = Notebook()
    book.observe(record, {3: "ada", 4: "grace"})
    book.observe(record, {5: "ada", 0: "grace"})
    assert book.players() == ["ada", "grace"]
    assert book.hands("ada") == 2.0


def test_edge_case_bot_folds_preflop_and_the_hand_is_still_recorded():
    """Row 9. The hands the bot folds are the free observations; keep them."""
    record = make_record(
        6,
        0,
        [
            (0, 3, "pot", 300),
            (0, 4, "fold", 0),
            (0, 5, "fold", 0),
            (0, 0, "fold", 0),  # the bot, out before the flop
            (0, 1, "fold", 0),
            (0, 2, "call", 200),
            (1, 2, "call", 0),
            (1, 3, "pot", 700),
            (1, 2, "fold", 0),
        ],
        streets_dealt=(1,),
        net=[0, -50, -300, 350, 0, 0],
    )
    book = Notebook()
    assert book.observe(record, SIX)
    assert book.hands("p0") == 1.0
    # The hand the bot folded still taught the notebook a continuation bet.
    assert counted(book, "p3", "cbet[flop]") == (1.0, 1.0)
    assert counted(book, "p2", "fold_to_cbet[flop]") == (1.0, 1.0)


def test_edge_case_truncated_hand_is_rejected_whole():
    """Row 10. Never partially applied: a bad hand writes nothing at all."""
    good = make_record(
        6,
        0,
        [(0, 3, "pot", 300), (0, 4, "fold", 0), (0, 5, "fold", 0),
         (0, 0, "fold", 0), (0, 1, "fold", 0), (0, 2, "fold", 0)],
        net=[0, -50, -100, 150, 0, 0],
    )
    book = Notebook()
    book.observe(good, SIX)
    before = {player: dict(rows) for player, rows in book.counts.items()}

    truncated = make_record(
        6,
        0,
        [(0, 3, "pot", 300), (0, 4, "fold", 0)],
        net=[0, -50, -100, 150, 0, 0],
        finished=False,
    )
    assert book.observe(truncated, SIX) is False
    assert book.rejected == 1
    assert {player: dict(rows) for player, rows in book.counts.items()} == before

    ragged = make_record(
        6,
        0,
        [(0, 3, "fold", 0)],
        net=[0, -50, 50, 0, 0, 0],
    )
    ragged.net = [0.0, 0.0]
    assert book.observe(ragged, SIX) is False
    assert book.rejected == 2
    with pytest.raises(UnusableHand):
        blind_view(ragged)


def test_edge_case_short_stack_hand_is_excluded_from_every_counter():
    """Row 11. Under five big blinds is all-in or folding, never choosing."""
    stacks = [10_000.0] * 6
    stacks[4] = 400.0  # four big blinds
    record = make_record(
        6,
        0,
        [
            (0, 3, "pot", 300),
            (0, 4, "all_in", 400),
            (0, 5, "fold", 0),
            (0, 0, "fold", 0),
            (0, 1, "fold", 0),
            (0, 2, "fold", 0),
            (0, 3, "call", 100),
        ],
        stacks=stacks,
        streets_dealt=(1, 2, 3),
        net=[0, -50, -100, -400, 550, 0],
    )
    book = Notebook()
    assert book.observe(record, SIX)
    assert "p4" not in book.players()
    assert book.hands("p3") == 1.0


# ---------------------------------------------------------------------------
# 3. no stat reads a hole card or a board card
# ---------------------------------------------------------------------------

#: Every field on a `HandRecord` or an `Event` that holds cards.
CARD_FIELDS = ("hole_cards", "board", "cards")


class _EventTrap:
    """One recorded event whose `cards` field explodes when it is read."""

    __slots__ = ("_wrapped",)

    def __init__(self, wrapped):
        object.__setattr__(self, "_wrapped", wrapped)

    def __getattr__(self, name):
        if name in CARD_FIELDS:
            raise AssertionError(f"a stat read Event.{name}, which holds cards")
        return getattr(self._wrapped, name)


class _RecordTrap:
    """One hand record whose card fields explode when they are read.

    Handing this to the notebook is the assertion: if any stat so much as
    touches `hole_cards`, `board` or an event's `cards`, the test raises
    instead of counting.
    """

    __slots__ = ("_wrapped",)

    def __init__(self, wrapped):
        object.__setattr__(self, "_wrapped", wrapped)

    def __getattr__(self, name):
        if name in CARD_FIELDS:
            raise AssertionError(f"a stat read HandRecord.{name}, which holds cards")
        value = getattr(self._wrapped, name)
        if name == "events":
            return [_EventTrap(event) for event in value]
        return value


def test_the_card_blind_view_has_no_card_fields_at_all():
    """By construction, not by inspection: the fields simply are not there."""
    fields = {f.name for f in notebook.dataclasses.fields(notebook.BlindRecord)}
    assert fields.isdisjoint(CARD_FIELDS)
    event_fields = {f.name for f in notebook.dataclasses.fields(notebook.BlindEvent)}
    assert event_fields.isdisjoint(CARD_FIELDS)


def test_no_stat_reads_a_hole_card_or_a_board_card():
    """Play a hand through the arena, then count it with the cards booby-trapped.

    The hand is a real one: `pokerbot.arena.play_hand` deals it, the engine
    rules it, and the personas play it out, so the record carries hole cards
    and a board exactly as the arena writes them. The notebook is then handed
    that record through `_RecordTrap`, which raises the moment any card field
    is read. Counting it through to a profile without raising is the proof
    that no stat reads a card.
    """
    from pokerbot import arena, personas
    from pokerbot.table import Table, TableConfig

    seats = 6
    table = Table(TableConfig(seats=seats, small_blind=50, big_blind=100))
    names = {seat: f"seat{seat}" for seat in range(seats)}
    book = Notebook()
    counted_hands = 0
    for index in range(6):
        hand = arena.play_hand(
            table,
            hand_index=index,
            seed=20260917 + index,
            button=index % seats,
            bot_seat=-1,  # every seat is a persona; no search runs here
            opponents={
                seat: personas.build_persona("call_raise_50_50", session_seed=7, stream=seat)
                for seat in range(seats)
            },
            budget_s=0.0,
            playouts_per_candidate=1,
            run_rule=False,
            logs=None,
        )
        record = hand.record
        # The record really does carry cards; that is what makes this a test.
        assert any(cards for cards in record.hole_cards)
        counted_hands += book.observe(_RecordTrap(record), names)
    assert counted_hands == 6
    profile = book.profile("seat0")
    assert profile.hands == 6
    assert profile_module.render(profile)


# ---------------------------------------------------------------------------
# 4. the same records give the same profile bytes
# ---------------------------------------------------------------------------


def _demo_stream(seed: int = 0):
    """A short, fixed stream of hands with three different players in it."""
    hands = []
    for index in range(30):
        button = index % 6
        aggressive = index % 3 == 0
        order = [(button + offset) % 6 for offset in (3, 4, 5, 0, 1, 2)]
        opener, *rest = order
        actions = [(0, opener, "pot" if aggressive else "call", 300 if aggressive else 100)]
        for seat in rest[:-1]:
            actions.append((0, seat, "fold", 0))
        closer = rest[-1]
        actions.append((0, closer, "call", 200 if aggressive else 0))
        actions += [
            (1, closer, "call", 0),
            (1, opener, "pot" if aggressive else "call", 400 if aggressive else 0),
        ]
        if aggressive:
            actions.append((1, closer, "fold", 0))
        else:
            actions += [
                (2, closer, "call", 0),
                (2, opener, "call", 0),
                (3, closer, "call", 0),
                (3, opener, "call", 0),
            ]
        net = [0.0] * 6
        net[opener] = 200.0
        net[closer] = -200.0
        hands.append(
            make_record(
                6,
                button,
                actions,
                streets_dealt=(1,) if aggressive else (1, 2, 3),
                net=net,
            )
        )
    return hands


def test_the_same_records_give_the_same_profile_bytes():
    """Determinism, the same property invariant I6 asks of a hand record."""
    names = {seat: f"p{seat}" for seat in range(6)}
    first = Notebook()
    second = Notebook()
    for record in _demo_stream():
        first.observe(record, names)
    for record in _demo_stream():
        second.observe(record, names)
    for player in first.players():
        one = json.dumps(first.profile(player).as_dict(), sort_keys=True).encode()
        two = json.dumps(second.profile(player).as_dict(), sort_keys=True).encode()
        assert one == two
        assert profile_module.render(first.profile(player)) == profile_module.render(
            second.profile(player)
        )


def test_the_command_line_reads_a_records_file_and_prints_a_profile(tmp_path):
    """The `--records` way in, end to end, as `--records-out` writes them."""
    path = tmp_path / "hands.jsonl"
    with path.open("wb") as handle:
        for record in _demo_stream():
            handle.write(record.to_bytes())
    done = subprocess.run(
        [sys.executable, "-m", "pokerbot.profile", "ada", "--records", str(path),
         "--names", "0=ada,1=grace,2=ida,3=mary,4=edith,5=nina"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    lines = done.stdout.splitlines()
    assert lines[0] == "  hands       30"
    assert lines[-2].startswith("  bucket      ")
    assert lines[-1].startswith("  flags       ")


def test_an_unwatched_name_is_a_clear_refusal_not_an_empty_report(tmp_path):
    path = tmp_path / "hands.jsonl"
    with path.open("wb") as handle:
        for record in _demo_stream():
            handle.write(record.to_bytes())
    done = subprocess.run(
        [sys.executable, "-m", "pokerbot.profile", "nobody", "--records", str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert done.returncode == 2
    assert "nobody" in done.stderr
