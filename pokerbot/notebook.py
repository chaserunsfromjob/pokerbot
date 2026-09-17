"""The notebook: what the bot writes down while it watches, and nothing else.

This is `OPPONENT_MODEL_DESIGN.md` Tier 0 (section 4.5), the tier that "cannot
lose a single chip". It reads a stream of `HandRecord`s, counts an opportunity
and an event for every stat in section 4.2, shrinks each rate towards a
baseline measured from the same stream, and hands the result to `profile.py`
to print. **It decides nothing and ranks no hand.** Nothing here looks at a
hole card or a board card -- `blind_view` strips both before a single counter
is touched, so card-blindness is a property of the code rather than of a test.

Where every rule in here comes from:

* the stat definitions, literally: `OPPONENT_MODEL_DESIGN.md` section 4.2;
* `rate = (BASELINE*s + k)/(s + n)` and `confidence = n/(n + s)`, with `s` the
  stat's `PRIOR_STRENGTH`: section 4.3;
* buckets, splits, hysteresis and the exploit flags: section 4.4;
* the awkward hands: section 4.7;
* the identifier is the player's name, never the seat: section 7 Q2;
* `BASELINE` is observed, never seeded from an archive: `OPPONENT_BASELINE.md`
  section 5;
* the seat-count band is a `context` value composed into the existing context
  column, the baseline and both splits are per band, `open_raise` is keyed by
  players-to-act-behind rather than EP/MP/LP, `fold_to_steal`'s opportunity is
  "in a blind facing an open from a player with behind <= 1":
  `TABLE_SIZE_AND_SIZING_NOTES.md` R1-R4, and the two sizing rows are R8;
* the counting logic is written here against section 4.2's table rather than
  imported from anybody: `RESOURCES_EXPLOITATION.md` Recommendation item 2.

Every constant below is an unmeasured starting value chosen by the design
documents, gathered into `NotebookConfig` so that tuning changes a config
object and never a line of counting code.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Iterable, Iterator, Mapping, Sequence
from typing import Any

#: The four streets, by the index `HandRecord` stores them under.
STREETS = ("preflop", "flop", "turn", "river")

#: Section 4.3's per-stat prior strength. It is the `s` in both lines, so a
#: stat has exactly one tuning constant; a stat absent from here is not shrunk.
PRIOR_STRENGTH: dict[str, float] = {
    # Tier A
    "vpip": 50.0,
    "pfr": 50.0,
    "limp": 50.0,
    # Tier B
    "three_bet": 25.0,
    "fold_to_three_bet": 25.0,
    "fold_to_steal": 25.0,
    "cbet": 25.0,
    "fold_to_cbet": 25.0,
    "afq": 25.0,
    "check_raise": 25.0,
    "open_raise": 25.0,
    # Tier C
    "wtsd": 15.0,
    "wsd": 15.0,
    "fold_to_river_bet": 15.0,
}

#: Counted, never shrunk. `af_*` are the raw counters behind the reported `AF`
#: diagnostic; `bet_size_dist` is a distribution whose shrinkage is categorical
#: (`TABLE_SIZE_AND_SIZING_NOTES.md` R8) and is not needed at Tier 0, where no
#: bucket and no flag reads it. `fold_to_bet` is R8's binomial sizing row; R9's
#: two flags that would read it are out of this tier's scope.
UNSHRUNK = ("af_bets_raises", "af_calls", "bet_size_dist", "fold_to_bet")

#: Seat-count bands, `TABLE_SIZE_AND_SIZING_NOTES.md` R1. The 4|5 and 6|7 cuts
#: are bookkeeping; `HU` standing alone and 8 and 9 sharing a band are forced.
BANDS = (("HU", 2, 2), ("SHORT", 3, 4), ("MID", 5, 6), ("FULL", 7, 9))


def band_of(seats: int) -> str:
    """Which seat-count band a hand dealt to `seats` players belongs to."""
    for label, low, high in BANDS:
        if low <= seats <= high:
            return label
    raise ValueError(f"{seats} seats is outside every band in {BANDS}")


@dataclasses.dataclass(frozen=True)
class NotebookConfig:
    """Every tuning constant the design documents leave open, in one place.

    All of them are unmeasured starting values, as the sections that introduce
    them say in so many words. Changing one changes a number in a report; none
    of them changes what is counted.
    """

    # section 4.7
    min_stack_bb: float = 5.0
    # section 4.3, applied per band by R2
    min_pool_hands: int = 200
    min_pool_opponents: int = 20
    # section 4.3 step 2. `None` switches decay off, which is what section 4.3
    # asks for inside one session ("high enough that it is effectively off").
    half_life: float | None = None
    # section 4.4
    vpip_split: float = 0.28
    afq_split: float = 0.50
    min_classify_hands: int = 50
    classify_confidence: float = 0.5
    dead_band: float = 0.02
    hold_hands: int = 10
    # section 4.4's flag gates
    flag_margin: float = 0.15
    never_raises_margin: float = 0.05
    flag_confidence: float = 0.6
    never_raises_confidence: float = 0.7
    # R8: two size buckets for one opponent, four for the population, the
    # split at 0.70 of pot, all-in its own bucket. The other three cuts are
    # `OPPONENT_MODEL_DESIGN.md` Table A rows.
    opponent_size_cuts: tuple[float, ...] = (0.70,)
    population_size_cuts: tuple[float, ...] = (0.33, 0.70, 1.00)


CONFIG = NotebookConfig()


# ---------------------------------------------------------------------------
# the card-blind view of a hand
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class BlindEvent:
    """One recorded event with the cards taken out of it."""

    index: int
    kind: str
    street: int
    seat: int | None
    action: str | None
    amount: float | None


@dataclasses.dataclass(frozen=True)
class BlindRecord:
    """One hand as the notebook is allowed to see it: no cards, anywhere.

    There is no `hole_cards` field and no `board` field, and `BlindEvent` has
    no `cards` field, so no stat can read a card even by accident. A board
    event survives as "the flop was dealt on street 1" -- a street marker, not
    a card.
    """

    seats: int
    button: int
    small_blind: float
    big_blind: float
    stacks: tuple[float, ...]
    events: tuple[BlindEvent, ...]
    contributions: tuple[float, ...]
    payouts: tuple[float, ...]
    net: tuple[float, ...]
    folded: tuple[bool, ...]
    pot: float
    finished: bool


class UnusableHand(Exception):
    """Section 4.7: a hand that cannot be parsed is rejected whole.

    Never partially applied. The caller may count it as rejected and move on.
    """


def blind_view(record: Any) -> BlindRecord:
    """Copy a `HandRecord` without ever reading a card field.

    This function names every field it takes, and `hole_cards`, `board` and
    `Event.cards` are not among them. That is the whole mechanism: a record
    whose card attributes explode on access passes through here untouched.
    """
    try:
        events = tuple(
            BlindEvent(
                index=int(event.index),
                kind=str(event.kind),
                street=int(event.street),
                seat=None if event.seat is None else int(event.seat),
                action=None if event.action is None else str(event.action),
                amount=None if event.amount is None else float(event.amount),
            )
            for event in record.events
        )
        view = BlindRecord(
            seats=int(record.seats),
            button=int(record.button),
            small_blind=float(record.small_blind),
            big_blind=float(record.big_blind),
            stacks=tuple(float(s) for s in record.stacks),
            events=events,
            contributions=tuple(float(c) for c in record.contributions),
            payouts=tuple(float(p) for p in record.payouts),
            net=tuple(float(n) for n in record.net),
            folded=tuple(bool(f) for f in record.folded),
            pot=float(record.pot),
            finished=bool(record.finished),
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise UnusableHand(f"this hand will not parse, so none of it is counted: {exc}") from exc
    if not view.finished:
        raise UnusableHand("the hand did not finish, so none of it is counted")
    if len(view.net) != view.seats or len(view.stacks) != view.seats:
        raise UnusableHand(
            f"the hand says {view.seats} seats but carries {len(view.net)} results"
        )
    return view


def blind_view_from_dict(payload: Mapping[str, Any]) -> BlindRecord:
    """The same, from the JSON a records file holds, one hand per line."""
    try:
        events = tuple(
            BlindEvent(
                index=int(e["index"]),
                kind=str(e["kind"]),
                street=int(e["street"]),
                seat=None if e.get("seat") is None else int(e["seat"]),
                action=None if e.get("action") is None else str(e["action"]),
                amount=None if e.get("amount") is None else float(e["amount"]),
            )
            for e in payload["events"]
        )
        return BlindRecord(
            seats=int(payload["seats"]),
            button=int(payload["button"]),
            small_blind=float(payload["small_blind"]),
            big_blind=float(payload["big_blind"]),
            stacks=tuple(float(s) for s in payload["stacks"]),
            events=events,
            contributions=tuple(float(c) for c in payload["contributions"]),
            payouts=tuple(float(p) for p in payload["payouts"]),
            net=tuple(float(n) for n in payload["net"]),
            folded=tuple(bool(f) for f in payload["folded"]),
            pot=float(payload["pot"]),
            finished=bool(payload["finished"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise UnusableHand(f"this hand will not parse, so none of it is counted: {exc}") from exc


# ---------------------------------------------------------------------------
# one hand, read move by move
# ---------------------------------------------------------------------------

FOLD, CHECK, CALL, BET, RAISE = "fold", "check", "call", "bet", "raise"


@dataclasses.dataclass(frozen=True)
class Move:
    """One seat's move, with the state it faced when it made it."""

    street: int
    order: int
    seat: int
    kind: str
    amount: float
    all_in: bool
    to_call: float
    pot_before: float
    aggressions_before: int
    first_on_street: bool
    behind: int


def _moves(view: BlindRecord) -> list[Move]:
    """Turn the recorded actions into moves, street by street.

    The engine's five moves are `fold`, `call`, `half_pot`, `pot` and
    `all_in`; "check" and "raise" are not among them and have to be read off
    the money. A `call` that costs nothing is a check. An aggressive move that
    ends above the street's current level is a bet when nothing has been bet
    on that street yet and a raise otherwise -- so the first aggressive move
    before the flop is always a raise, because the blinds already set a level.
    An all-in that does not clear the level is a call, not a raise; one that
    clears it by less than a full raise is a raise, which is section 4.7's
    "all-in for less than a full raise" handling.
    """
    posted: dict[int, float] = {}
    for event in view.events:
        if event.kind == "blind" and event.seat is not None:
            posted[event.seat] = posted.get(event.seat, 0.0) + float(event.amount or 0.0)
    pot = sum(posted.values())

    by_street: dict[int, list[BlindEvent]] = {}
    for event in view.events:
        if event.kind == "action":
            by_street.setdefault(event.street, []).append(event)

    folded: set[int] = set()
    moves: list[Move] = []
    for street in sorted(by_street):
        committed = dict(posted) if street == 0 else {}
        level = max(committed.values(), default=0.0)
        aggressions = 0
        acted: set[int] = set()
        for order, event in enumerate(by_street[street]):
            seat = event.seat
            if seat is None:
                raise UnusableHand("an action was recorded with no seat")
            amount = float(event.amount or 0.0)
            before = committed.get(seat, 0.0)
            after = before + amount
            to_call = max(0.0, level - before)
            if event.action == "fold":
                kind = FOLD
            elif after > level + 1e-9:
                kind = BET if (aggressions == 0 and level <= 1e-9) else RAISE
            elif amount > 1e-9:
                kind = CALL
            else:
                kind = CHECK
            live = [s for s in range(view.seats) if s not in folded]
            behind = len([s for s in live if s != seat and s not in acted])
            moves.append(
                Move(
                    street=street,
                    order=order,
                    seat=seat,
                    kind=kind,
                    amount=amount,
                    all_in=event.action == "all_in",
                    to_call=to_call,
                    pot_before=pot,
                    aggressions_before=aggressions,
                    first_on_street=seat not in acted,
                    behind=behind,
                )
            )
            acted.add(seat)
            committed[seat] = after
            level = max(level, after)
            pot += amount
            if kind == FOLD:
                folded.add(seat)
            if kind in (BET, RAISE):
                aggressions += 1
    return moves


# ---------------------------------------------------------------------------
# contexts: R1's `band=` composed with section 4.2's own keys
# ---------------------------------------------------------------------------


def context(**parts: Any) -> str:
    """One `context` column value: `key=value` pairs, sorted, comma-joined.

    R1 asks for the seat-count band to be encoded here rather than given a
    table of its own, "composed with any existing context key". Sorting makes
    the string canonical, so the same context is always the same key.
    """
    return ",".join(f"{k}={v}" for k, v in sorted(parts.items()) if v is not None)


def context_has(ctx: str, key: str, value: str) -> bool:
    """Is `key=value` one of the pairs in this context string?"""
    return f"{key}={value}" in ctx.split(",")


def _size_labels(cuts: Sequence[float]) -> tuple[str, ...]:
    if len(cuts) == 1:
        return ("small", "large")
    if len(cuts) == 3:
        return ("tiny", "small", "medium", "large")
    raise ValueError(f"no bucket names are defined for {len(cuts)} size cuts")


def size_bucket(amount: float, pot_before: float, all_in: bool, cuts: Sequence[float]) -> str:
    """Which size bucket a bet falls in: bet over the pot before it, never bb.

    All-in is its own bucket, as R8 requires, whatever fraction of the pot it
    happened to be.
    """
    if all_in:
        return "allin"
    labels = _size_labels(cuts)
    if pot_before <= 0:
        return labels[-1]
    ratio = amount / pot_before
    for label, cut in zip(labels, cuts):
        if ratio <= cut + 1e-9:
            return label
    return labels[-1]


def size_buckets(cuts: Sequence[float]) -> tuple[str, ...]:
    """Every bucket a bet could land in, all-in included."""
    return _size_labels(cuts) + ("allin",)


# ---------------------------------------------------------------------------
# section 4.2, stat by stat, applied to one hand
# ---------------------------------------------------------------------------

Increment = tuple[int, str, str, float, float]  # seat, stat, context, k, n


def hand_counts(
    view: BlindRecord,
    tracked: Iterable[int],
    config: NotebookConfig = CONFIG,
) -> list[Increment]:
    """Every increment section 4.2 asks for, from one hand, for one table.

    `tracked` is the set of seats that were dealt in and are being counted; a
    seat that sat out or was dealt out is simply absent, which is section
    4.7's "no `hands_dealt` increment". A seat that started the hand with
    fewer than `min_stack_bb` big blinds is dropped here too, section 4.7
    again: that short a stack is all-in or folding and never choosing.
    """
    band = band_of(view.seats)
    seats = [
        s
        for s in tracked
        if 0 <= s < view.seats and view.stacks[s] >= config.min_stack_bb * view.big_blind
    ]
    if not seats:
        return []
    moves = _moves(view)
    out: list[Increment] = []

    def add(seat: int, stat: str, k: float, n: float, **parts: Any) -> None:
        if seat in seats:
            out.append((seat, stat, context(band=band, **parts), k, n))

    dealt_streets = {0} | {e.street for e in view.events if e.kind == "board"}
    fold_street: dict[int, int] = {}
    for move in moves:
        if move.kind == FOLD and move.seat not in fold_street:
            fold_street[move.seat] = move.street

    def saw(seat: int, street: int) -> bool:
        return street in dealt_streets and fold_street.get(seat, 99) >= street

    by_street: dict[int, list[Move]] = {}
    for move in moves:
        by_street.setdefault(move.street, []).append(move)
    preflop = by_street.get(0, [])

    sb_seat = view.button if view.seats == 2 else (view.button + 1) % view.seats
    bb_seat = (view.button + 1) % view.seats if view.seats == 2 else (view.button + 2) % view.seats

    def blind_label(seat: int) -> str:
        return "SB" if seat == sb_seat else "BB" if seat == bb_seat else "none"

    for seat in seats:
        add(seat, "hands_dealt", 1.0, 1.0)

    # -- preflop: vpip, pfr, limp, open_raise, three_bet, fold_to_three_bet --
    voluntary = {m.seat for m in preflop if m.kind in (CALL, BET, RAISE)}
    raised = {m.seat for m in preflop if m.kind == RAISE}
    for seat in seats:
        add(seat, "vpip", 1.0 if seat in voluntary else 0.0, 1.0)
        add(seat, "pfr", 1.0 if seat in raised else 0.0, 1.0)

    first_preflop: dict[int, Move] = {}
    money_before_seat: dict[int, bool] = {}
    money_in = False
    for move in preflop:
        if move.seat not in first_preflop:
            first_preflop[move.seat] = move
            money_before_seat[move.seat] = money_in
        if move.kind in (CALL, BET, RAISE):
            money_in = True

    for seat, move in first_preflop.items():
        # limp: the option exists when no raise stands in front of them and
        # they are not the big blind, who cannot call the big blind.
        if move.aggressions_before == 0 and seat != bb_seat:
            add(seat, "limp", 1.0 if move.kind == CALL else 0.0, 1.0)
        # open_raise: first in, nobody having put money in before them.
        if move.aggressions_before == 0 and not money_before_seat[seat]:
            add(
                seat,
                "open_raise",
                1.0 if move.kind == RAISE else 0.0,
                1.0,
                behind=_behind_label(move.behind),
                blind=blind_label(seat),
            )

    open_move = next((m for m in preflop if m.kind == RAISE and m.aggressions_before == 0), None)
    committed_so_far: dict[int, float] = {}
    seen_three_bet_spot: set[int] = set()
    for move in preflop:
        spent = committed_so_far.get(move.seat, 0.0)
        behind_chips = view.stacks[move.seat] - spent - move.to_call
        if move.aggressions_before == 1 and move.seat not in seen_three_bet_spot:
            seen_three_bet_spot.add(move.seat)
            if behind_chips > 0:
                add(move.seat, "three_bet", 1.0 if move.kind == RAISE else 0.0, 1.0)
            # fold_to_steal, R4: in a blind, facing an open made by a player
            # with one or no players behind them, with no other caller.
            if (
                open_move is not None
                and move.seat in (sb_seat, bb_seat)
                and move.seat != open_move.seat
                and open_move.behind <= 1
                and not any(
                    m.kind in (CALL, BET, RAISE)
                    for m in preflop
                    if open_move.order < m.order < move.order
                )
            ):
                add(
                    move.seat,
                    "fold_to_steal",
                    1.0 if move.kind == FOLD else 0.0,
                    1.0,
                    behind=_behind_label(open_move.behind),
                )
        committed_so_far[move.seat] = spent + move.amount

    if open_move is not None:
        reply = next(
            (m for m in preflop if m.seat == open_move.seat and m.aggressions_before >= 2),
            None,
        )
        if reply is not None:
            add(open_move.seat, "fold_to_three_bet", 1.0 if reply.kind == FOLD else 0.0, 1.0)

    # -- per street: cbet, fold_to_cbet, afq, af, check_raise, sizing --------
    last_aggressor: dict[int, int | None] = {}
    for street in range(4):
        aggressive = [m for m in by_street.get(street, []) if m.kind in (BET, RAISE)]
        last_aggressor[street] = aggressive[-1].seat if aggressive else None

    for street, name in enumerate(STREETS):
        street_moves = by_street.get(street, [])
        for move in street_moves:
            if move.kind != CHECK:
                add(
                    move.seat,
                    "afq",
                    1.0 if move.kind in (BET, RAISE) else 0.0,
                    1.0,
                    street=name,
                )
            if move.kind in (BET, RAISE):
                add(move.seat, "af_bets_raises", 1.0, 0.0, street=name)
                bucket = size_bucket(
                    move.amount, move.pot_before, move.all_in, config.opponent_size_cuts
                )
                for candidate in size_buckets(config.opponent_size_cuts):
                    add(
                        move.seat,
                        "bet_size_dist",
                        1.0 if candidate == bucket else 0.0,
                        1.0,
                        street=name,
                        role=move.kind,
                        size=candidate,
                    )
            elif move.kind == CALL:
                add(move.seat, "af_calls", 1.0, 0.0, street=name)

        # check_raise: checked, then a bet landed behind the check.
        checked_at: dict[int, int] = {}
        counted: set[int] = set()
        for move in street_moves:
            if move.kind == CHECK and move.seat not in checked_at:
                checked_at[move.seat] = move.order
            elif move.kind in (BET, RAISE):
                for seat, order in checked_at.items():
                    if order < move.order and seat not in counted and seat != move.seat:
                        reply = next(
                            (m for m in street_moves if m.seat == seat and m.order > move.order),
                            None,
                        )
                        if reply is not None:
                            counted.add(seat)
                            add(
                                seat,
                                "check_raise",
                                1.0 if reply.kind == RAISE else 0.0,
                                1.0,
                                street=name,
                            )

        if street == 0:
            continue

        # cbet and fold_to_cbet.
        aggressor = last_aggressor[street - 1]
        if aggressor is not None and saw(aggressor, street):
            first_bet = next((m for m in street_moves if m.kind == BET), None)
            made_it = first_bet is not None and first_bet.seat == aggressor
            add(aggressor, "cbet", 1.0 if made_it else 0.0, 1.0, street=name)
            if made_it:
                answered: set[int] = set()
                for move in street_moves:
                    if move.order > first_bet.order and move.seat not in answered:
                        answered.add(move.seat)
                        add(
                            move.seat,
                            "fold_to_cbet",
                            1.0 if move.kind == FOLD else 0.0,
                            1.0,
                            street=name,
                        )

        # fold_to_bet, R8: the first answer to a bet, keyed by its size.
        answered_bet: set[int] = set()
        standing: Move | None = None
        for move in street_moves:
            if move.to_call > 0 and standing is not None and move.seat not in answered_bet:
                answered_bet.add(move.seat)
                bucket = size_bucket(
                    standing.amount, standing.pot_before, standing.all_in,
                    config.opponent_size_cuts,
                )
                add(
                    move.seat,
                    "fold_to_bet",
                    1.0 if move.kind == FOLD else 0.0,
                    1.0,
                    street=name,
                    size=bucket,
                )
                if street == 3:
                    add(move.seat, "fold_to_river_bet", 1.0 if move.kind == FOLD else 0.0, 1.0)
            if move.kind in (BET, RAISE):
                standing = move

    # -- showdown: wtsd, wsd ------------------------------------------------
    live_at_end = [s for s in range(view.seats) if not view.folded[s]]
    showdown = 3 in dealt_streets and len(live_at_end) >= 2
    for seat in seats:
        if saw(seat, 1):
            reached = showdown and not view.folded[seat]
            add(seat, "wtsd", 1.0 if reached else 0.0, 1.0)
            if reached:
                add(seat, "wsd", 1.0 if view.net[seat] > 0 else 0.0, 1.0)
    return out


def _behind_label(behind: int) -> str:
    """R3's `behind=<k>` for k in {0, 1, 2, 3, 4, 5+}."""
    return "5+" if behind >= 5 else str(behind)


# ---------------------------------------------------------------------------
# section 4.3: the two lines, and the baseline they blend towards
# ---------------------------------------------------------------------------


def shrunk_rate(k: float, n: float, baseline: float, s: float) -> float:
    """`rate = (BASELINE*s + k)/(s + n)` -- section 4.3, unchanged."""
    return (baseline * s + k) / (s + n)


def confidence_of(n: float, s: float) -> float:
    """`confidence = n/(n + s)` -- section 4.3, the same `s` as the line above."""
    return n / (n + s)


@dataclasses.dataclass(frozen=True)
class Reading:
    """One stat, counted, shrunk and dated by how much it rests on."""

    key: str
    stat: str
    k: float
    n: float
    baseline: float
    prior_strength: float
    rate: float
    confidence: float
    raw: float | None
    baseline_source: str

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def reading(
    key: str,
    k: float,
    n: float,
    baseline: float,
    *,
    baseline_source: str = "given",
) -> Reading:
    """Build one reading from its counts. The stat's `s` decides the rest."""
    stat, _ = parse_key(key)
    s = PRIOR_STRENGTH.get(stat)
    if s is None:
        raise KeyError(
            f"{stat!r} has no PRIOR_STRENGTH in section 4.3, so it has no shrunk "
            "rate and no confidence; it is counted, not shrunk"
        )
    return Reading(
        key=key,
        stat=stat,
        k=k,
        n=n,
        baseline=baseline,
        prior_strength=s,
        rate=shrunk_rate(k, n, baseline, s),
        confidence=confidence_of(n, s),
        raw=(k / n) if n > 0 else None,
        baseline_source=baseline_source,
    )


def parse_key(key: str) -> tuple[str, dict[str, str]]:
    """`afq[flop]` -> `("afq", {"street": "flop"})`; `afq` -> `("afq", {})`."""
    stat, _, rest = key.partition("[")
    filters: dict[str, str] = {}
    for token in rest.rstrip("]").split(",") if rest else []:
        token = token.strip()
        if not token:
            continue
        if "=" in token:
            name, _, value = token.partition("=")
            filters[name] = value
        elif token in STREETS:
            filters["street"] = token
        else:
            filters["size"] = token
    return stat, filters


# ---------------------------------------------------------------------------
# section 4.4: the grid, the splits, and the flags
# ---------------------------------------------------------------------------

BUCKETS = ("ROCK", "STATION", "TAG", "MANIAC", "UNKNOWN")

#: Each flag: its legs, and the confidence gate every leg must clear. A leg is
#: (key, direction, which margin), where "above"/"below" are relative to that
#: stat's own `BASELINE`. Straight from section 4.4's table.
FLAGS: tuple[tuple[str, tuple[tuple[str, str, str], ...], str], ...] = (
    ("OVERFOLDS_TO_3BET", (("fold_to_three_bet", "above", "flag"),), "flag"),
    ("NEVER_FOLDS_TO_3BET", (("fold_to_three_bet", "below", "flag"),), "flag"),
    ("OVERFOLDS_TO_CBET", (("fold_to_cbet[flop]", "above", "flag"),), "flag"),
    ("NEVER_FOLDS_POSTFLOP", (("wtsd", "above", "flag"),), "flag"),
    ("OVERFOLDS_BLINDS", (("fold_to_steal", "above", "flag"),), "flag"),
    (
        "NEVER_RAISES",
        (("three_bet", "below", "never_raises"), ("check_raise", "below", "never_raises")),
        "never_raises",
    ),
    ("LIMPS", (("limp", "above", "flag"),), "flag"),
)


def near_boundary_width(rate_confidence: float, n: float, split: float) -> float:
    """`c*w`: how close to a split counts as too close to call.

    `w = 1.96*sqrt(split*(1-split)/n)` is the 95% half-width at the split, and
    the shrunk rate moves only `c` of the way to the raw one, so its own
    half-width is `c*w`. Section 4.4 requires a profile to be marked when the
    shrunk rate sits inside it, so that a reader sees the exposure instead of
    reading the bucket as settled.
    """
    if n <= 0:
        return float("inf")
    return rate_confidence * 1.96 * math.sqrt(split * (1.0 - split) / n)


@dataclasses.dataclass(frozen=True)
class Profile:
    """One player, as the notebook has them. A description, not a decision."""

    player: str
    band: str
    hands: int
    readings: tuple[Reading, ...]
    bucket: str
    near_boundary: tuple[str, ...]
    flags: tuple[str, ...]
    vpip_split: float
    afq_split: float

    def reading(self, key: str) -> Reading | None:
        for item in self.readings:
            if item.key == key:
                return item
        return None

    def as_dict(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        d["readings"] = [r.as_dict() for r in self.readings]
        return d


def build_profile(
    player: str,
    band: str,
    hands: int,
    readings: Sequence[Reading],
    *,
    vpip_split: float,
    afq_split: float,
    config: NotebookConfig = CONFIG,
) -> Profile:
    """Put a bucket and the exploit flags beside counted, shrunk numbers."""
    index = {r.key: r for r in readings}
    vpip = index.get("vpip")
    afq = index.get("afq")

    if (
        vpip is None
        or vpip.confidence < config.classify_confidence
        or hands < config.min_classify_hands
    ):
        bucket = "UNKNOWN"
    else:
        loose = vpip.rate > vpip_split
        aggressive = afq is not None and afq.rate > afq_split
        bucket = ("STATION" if loose else "ROCK") if not aggressive else (
            "MANIAC" if loose else "TAG"
        )

    near: list[str] = []
    for axis, item, split in (("vpip", vpip, vpip_split), ("afq", afq, afq_split)):
        if bucket != "UNKNOWN" and item is not None:
            if abs(item.rate - split) < near_boundary_width(item.confidence, item.n, split):
                near.append(axis)

    margins = {"flag": config.flag_margin, "never_raises": config.never_raises_margin}
    gates = {"flag": config.flag_confidence, "never_raises": config.never_raises_confidence}
    fired: list[tuple[float, str]] = []
    for name, legs, gate_name in FLAGS:
        gate = gates[gate_name]
        confidences: list[float] = []
        for key, direction, margin_name in legs:
            item = index.get(key)
            margin = margins[margin_name]
            if item is None or item.confidence < gate:
                break
            gap = item.rate - item.baseline if direction == "above" else item.baseline - item.rate
            if gap < margin:
                break
            confidences.append(item.confidence)
        else:
            fired.append((min(confidences), name))
    # Loudest first: the flag resting on the most observations leads, which is
    # the order section 4.5's worked report prints them in.
    fired.sort(key=lambda pair: (-pair[0], pair[1]))

    return Profile(
        player=player,
        band=band,
        hands=hands,
        readings=tuple(readings),
        bucket=bucket,
        near_boundary=tuple(near),
        flags=tuple(name for _, name in fired),
        vpip_split=vpip_split,
        afq_split=afq_split,
    )


# ---------------------------------------------------------------------------
# the notebook itself
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class _BucketRun:
    """Section 4.4's hysteresis: what is showing, and what is trying to."""

    committed: str = "UNKNOWN"
    candidate: str = "UNKNOWN"
    held: int = 0


class Notebook:
    """Counters for every named player seen, and the profiles they make.

    The identifier is the player's **name** (section 7 Q2): a seat is a
    per-hand field and never an identity, so a player who changes seats, or
    leaves and comes back, keeps one row. Nothing in here is seeded from an
    archive -- `BASELINE` is pooled from the hands this notebook has actually
    watched, which is `OPPONENT_BASELINE.md` section 5's "observe first".
    """

    def __init__(self, config: NotebookConfig = CONFIG):
        self.config = config
        self.hands_seen = 0
        self.rejected = 0
        #: player -> (stat, context) -> [k, n]
        self.counts: dict[str, dict[tuple[str, str], list[float]]] = {}
        self._last_seen: dict[str, int] = {}
        self._buckets: dict[str, _BucketRun] = {}

    # -- watching ---------------------------------------------------------

    def observe(self, record: Any, names: Mapping[int, str]) -> bool:
        """Count one hand. `names` says who sat where, by name.

        Returns True if the hand was counted and False if it was rejected.
        Section 4.7: an unparseable hand is rejected whole, never partially
        applied, so nothing is written until every increment is in hand.
        """
        try:
            view = record if isinstance(record, BlindRecord) else blind_view(record)
            increments = hand_counts(view, sorted(names), self.config)
        except UnusableHand:
            self.rejected += 1
            return False
        self.hands_seen += 1
        seen = {names[seat] for seat, _, _, _, _ in increments}
        for player in sorted(seen):
            self._decay(player)
        for seat, stat, ctx, k, n in increments:
            row = self.counts.setdefault(names[seat], {}).setdefault((stat, ctx), [0.0, 0.0])
            row[0] += k
            row[1] += n
        for player in sorted(seen):
            self._reclassify(player)
        return True

    def observe_stream(self, hands: Iterable[tuple[Any, Mapping[int, str]]]) -> int:
        """Count a whole stream of hands. Returns how many were counted."""
        return sum(1 for record, names in hands if self.observe(record, names))

    def _decay(self, player: str) -> None:
        """Section 4.3 step 2, and it is off unless a half-life is configured.

        Section 4.3 asks for a half-life set "high enough that it is
        effectively off within one session"; one stream of records is one
        session, so the default leaves the counts exactly as counted.
        """
        last = self._last_seen.get(player)
        self._last_seen[player] = self.hands_seen
        if self.config.half_life is None or last is None:
            return
        elapsed = self.hands_seen - last
        d = 0.5 ** (elapsed / self.config.half_life)
        for row in self.counts.get(player, {}).values():
            row[0] *= d
            row[1] *= d

    # -- reading ----------------------------------------------------------

    def players(self) -> list[str]:
        """Every name this notebook has counted, in a fixed order."""
        return sorted(self.counts)

    def bands(self, player: str) -> list[str]:
        """Which seat-count bands this player has been counted in."""
        found = {
            pair
            for (stat, ctx) in self.counts.get(player, {})
            if stat == "hands_dealt"
            for pair in [ctx.split("band=")[1].split(",")[0]]
        }
        return sorted(found)

    def tally(self, player: str, key: str, band: str | None = None) -> tuple[float, float]:
        """The counts behind one key, pooled over every context that matches.

        `band=None` pools the player's own counters over every band, which is
        what R2 asks for: the band is banded in the *population* baseline, not
        in one opponent's counters, whose contexts are summed back up here.
        """
        stat, filters = parse_key(key)
        k = n = 0.0
        for (name, ctx), row in self.counts.get(player, {}).items():
            if name != stat:
                continue
            if band is not None and not context_has(ctx, "band", band):
                continue
            if all(context_has(ctx, f, v) for f, v in filters.items()):
                k += row[0]
                n += row[1]
        return k, n

    def hands(self, player: str, band: str | None = None) -> float:
        return self.tally(player, "hands_dealt", band)[1]

    def qualifying(self, band: str | None = None) -> list[str]:
        """Opponents with enough hands to join the pool -- within the band."""
        floor = self.config.min_pool_hands
        return [p for p in self.players() if self.hands(p, band) >= floor]

    def baseline(self, key: str, band: str | None = None) -> tuple[float, str]:
        """`BASELINE[stat, band]`, with R2's fallback chain, and where it came from.

        Band baseline, then the global one pooled over all bands, then the rate
        pooled over everyone observed whether or not they qualify. That last
        rung stands in for section 4.3's "the blueprint's own action frequency",
        which Tier 0 has no blueprint to ask; it is marked as unqualified so a
        reader never mistakes it for a pooled population baseline.
        """
        scopes: list[tuple[str | None, str]] = []
        if band is not None:
            scopes.append((band, f"band={band}"))
        scopes.append((None, "global"))
        for scope, source in scopes:
            pool = self.qualifying(scope)
            if len(pool) >= self.config.min_pool_opponents:
                k = n = 0.0
                for player in pool:
                    pk, pn = self.tally(player, key, scope)
                    k += pk
                    n += pn
                if n > 0:
                    return k / n, source
        k = n = 0.0
        for player in self.players():
            pk, pn = self.tally(player, key, band)
            k += pk
            n += pn
        if n > 0:
            return k / n, "pooled-unqualified"
        return 0.0, "no-observations"

    def split(self, axis: str, band: str | None = None) -> float:
        """`VPIP_SPLIT` / `AFQ_SPLIT`: the design's default, or the pool median.

        Section 4.4 replaces both by the median of the bot's own observed
        population once enough opponents qualify, and R2 takes that median per
        band. Until then the documented default stands.
        """
        key = "vpip" if axis == "vpip" else "afq"
        default = self.config.vpip_split if axis == "vpip" else self.config.afq_split
        pool = self.qualifying(band)
        if len(pool) < self.config.min_pool_opponents:
            return default
        rates = []
        for player in pool:
            k, n = self.tally(player, key, band)
            if n > 0:
                rates.append(k / n)
        if not rates:
            return default
        rates.sort()
        mid = len(rates) // 2
        return rates[mid] if len(rates) % 2 else (rates[mid - 1] + rates[mid]) / 2.0

    def keys(self, player: str) -> list[str]:
        """Every display key this player has counts for, in a fixed order."""
        found: set[str] = set()
        for stat, ctx in self.counts.get(player, {}):
            if stat not in PRIOR_STRENGTH:
                continue
            found.add(stat)
            for street in STREETS:
                if context_has(ctx, "street", street):
                    found.add(f"{stat}[{street}]")
        return sorted(found)

    def profile(self, player: str, band: str | None = None) -> Profile:
        """One player's profile: counted, shrunk, bucketed and flagged."""
        if player not in self.counts:
            raise KeyError(
                f"nobody called {player!r} has been watched; the notebook has "
                f"{self.players()}"
            )
        readings = []
        for key in self.keys(player):
            k, n = self.tally(player, key, band)
            base, source = self.baseline(key, band)
            readings.append(reading(key, k, n, base, baseline_source=source))
        profile = build_profile(
            player,
            band or "all",
            int(round(self.hands(player, band))),
            readings,
            vpip_split=self.split("vpip", band),
            afq_split=self.split("afq", band),
            config=self.config,
        )
        if band is None:
            # Section 4.4's hysteresis applies to the running classification,
            # which is kept per player across hands rather than recomputed.
            run = self._buckets.get(player)
            if run is not None:
                profile = dataclasses.replace(profile, bucket=run.committed)
        return profile

    def classification(self, player: str) -> tuple[str, str, int]:
        """The bucket showing, the one trying to replace it, and how long for.

        Section 4.4's hysteresis in three numbers, so that a caller can see
        *why* a bucket has not changed rather than only that it has not.
        """
        run = self._buckets.get(player, _BucketRun())
        return run.committed, run.candidate, run.held

    def _reclassify(self, player: str) -> None:
        """Section 4.4: cross the split by the dead band, then hold it.

        A bucket changes only when the shrunk rate is past the split by more
        than `dead_band` **and** the new label has held for `hold_hands`
        hands. The dead band controls flapping between hands; section 4.4 is
        explicit that it does not control sampling error and must never be
        tuned as though it did.
        """
        run = self._buckets.setdefault(player, _BucketRun())
        cfg = self.config
        if self.hands(player) < cfg.min_classify_hands:
            run.candidate = run.committed = "UNKNOWN"
            run.held = 0
            return
        band_cfg = cfg.dead_band
        vpip_split = self.split("vpip")
        afq_split = self.split("afq")
        k, n = self.tally(player, "vpip")
        base, _ = self.baseline("vpip")
        vpip = reading("vpip", k, n, base)
        k, n = self.tally(player, "afq")
        base, _ = self.baseline("afq")
        afq = reading("afq", k, n, base)
        hands = self.hands(player)
        if vpip.confidence < cfg.classify_confidence or hands < cfg.min_classify_hands:
            candidate = "UNKNOWN"
        elif (
            abs(vpip.rate - vpip_split) < band_cfg or abs(afq.rate - afq_split) < band_cfg
        ) and run.committed != "UNKNOWN":
            candidate = run.committed
        else:
            loose = vpip.rate > vpip_split
            aggressive = afq.rate > afq_split
            candidate = ("STATION" if loose else "ROCK") if not aggressive else (
                "MANIAC" if loose else "TAG"
            )
        if candidate == run.candidate:
            run.held += 1
        else:
            run.candidate = candidate
            run.held = 1
        if candidate == "UNKNOWN" or run.held >= cfg.hold_hands:
            run.committed = candidate
