"""The table: a thin adapter over OpenSpiel's `universal_poker`.

What this module is for, in one sentence: to deal a hand of no-limit hold'em
at two to nine seats, say whose turn it is and what that seat may do, carry out
what the seat decides, and write down everything that happened -- while leaving
every judgement about poker to the engine.

What it deliberately does not do. It never ranks a hand, never says which hand
beats which, never decides who won, and never chooses an action. Who is paid
what is read back out of the engine at the end of the hand. That is
`CLAUDE.md`'s forefront rule ("rules and hand evaluation come from the engine
road, OpenSpiel `universal_poker`"), and it is also the only way the invariants
in `EVALUATION_STRATEGY.md` section 4.5 mean anything: a test that checked our
payouts against our own hand evaluator would only be checking us against
ourselves.

The bet menu is `ENGINE_ALTERNATIVES.md`:121 and `ACTION_TRANSLATION.md`
section 7: five moves, `{fold, call, half pot, pot, all-in}`, which is the
engine's own `fchpa` betting abstraction as it ships. The choice of bet size
therefore stays inside the engine, which is where the forefront rule puts it.

Seats and the button. The engine's own seat 0 always posts the small blind, so
this adapter keeps a table of seats of its own and rotates it onto the engine.
Seat numbers in everything this module returns are *table* seats; the button
is a table seat; the mapping onto engine seats is an implementation detail and
the only place a button rotation can go wrong. Heads-up is the exception every
variable-seat engine gets wrong, and it is handled explicitly: with two
players, the button posts the small blind and acts first before the flop, then
acts last on every later street. That is invariant I5.
"""

from __future__ import annotations

import dataclasses
import enum
import functools
import random
import re
from typing import Iterable, Sequence

import pyspiel

from .invariants import InvariantViolation, require
from .provenance import commit_id
from .record import Event, HandRecord, SCHEMA

ENGINE = "open_spiel.universal_poker"
BETTING_ABSTRACTION = "fchpa"
MIN_SEATS = 2
MAX_SEATS = 9

#: The board comes out as (first card, last card, street): the flop is the
#: first three cards and is street 1, the turn is street 2, the river street 3.
BOARD_STREETS = ((0, 3, 1), (3, 4, 2), (4, 5, 3))

_SPENT_RE = re.compile(r"P(\d+):\s*(-?\d+(?:\.\d+)?)")
_SPENT_LINE_RE = re.compile(r"^Spent:\s*\[(.*)\]\s*$", re.MULTILINE)
_ROUND_RE = re.compile(r"^Round:\s*(\d+)\s*$", re.MULTILINE)
_ACPC_RE = re.compile(r"^ACPC State:\s*(\S+)\s*$", re.MULTILINE)
_MOVE_RE = re.compile(r"move=(\S+)")


class Action(enum.Enum):
    """The five moves a seat may make. Nothing else is ever offered."""

    FOLD = "fold"
    CALL = "call"
    HALF_POT = "half_pot"
    POT = "pot"
    ALL_IN = "all_in"


#: The engine's own name for each move, as `action_to_string` writes it.
_ENGINE_MOVE_TO_ACTION = {
    "Fold": Action.FOLD,
    "Call": Action.CALL,
    "HalfPot": Action.HALF_POT,
    "Bet": Action.POT,  # `fchpa`'s plain "Bet" is the pot-sized one
    "AllIn": Action.ALL_IN,
}


class IllegalActionError(InvariantViolation):
    """Invariant I4: a seat tried something the engine does not allow."""

    def __init__(self, message: str, context: object = None):
        super().__init__("I4", message, context)


class SeatCountNotDealable(Exception):
    """This seat count cannot be dealt, with the engine's reason attached."""

    def __init__(self, seats: int, reason: str):
        self.seats = seats
        self.reason = reason
        super().__init__(f"{seats} seats will not deal: {reason}")


@dataclasses.dataclass(frozen=True)
class TableConfig:
    """Everything that is fixed before a hand is dealt.

    `stacks` is one starting stack per table seat. Leave it out and every seat
    starts with 200 big blinds, the depth `ENGINE_ALTERNATIVES.md` measured at.
    """

    seats: int
    small_blind: int = 50
    big_blind: int = 100
    stacks: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not MIN_SEATS <= self.seats <= MAX_SEATS:
            raise ValueError(
                f"seats must be {MIN_SEATS}..{MAX_SEATS}, got {self.seats}"
            )
        if self.small_blind <= 0 or self.big_blind <= 0:
            raise ValueError("blinds must be positive whole chips")
        if self.small_blind > self.big_blind:
            raise ValueError("the small blind cannot exceed the big blind")
        stacks = tuple(self.stacks) or (self.big_blind * 200,) * self.seats
        if len(stacks) != self.seats:
            raise ValueError(
                f"stacks has {len(stacks)} entries for {self.seats} seats"
            )
        if any(s <= 0 for s in stacks):
            raise ValueError("every starting stack must be positive")
        object.__setattr__(self, "stacks", stacks)


def _game_string(config: TableConfig, engine_stacks: Sequence[int]) -> str:
    """The ACPC game definition, written the way `universal_poker` reads it.

    Engine seat 0 posts the small blind at every seat count. At two seats the
    acting order is reversed before the flop, which is the heads-up rule and
    the whole of invariant I5's special case.
    """
    n = config.seats
    if n == 2:
        blind = f"{config.small_blind} {config.big_blind}"
        first_player = "1 2 2 2"  # button (seat 0) first pre-flop, last after
    else:
        blind = " ".join(
            [str(config.small_blind), str(config.big_blind)] + ["0"] * (n - 2)
        )
        first_player = "3 1 1 1"  # under the gun first, then the small blind
    stacks = " ".join(str(int(s)) for s in engine_stacks)
    return (
        f"universal_poker(betting=nolimit,numPlayers={n},numRounds=4,"
        f"blind={blind},firstPlayer={first_player},numSuits=4,numRanks=13,"
        f"numHoleCards=2,numBoardCards=0 3 1 1,stack={stacks},"
        f"bettingAbstraction={BETTING_ABSTRACTION})"
    )


@functools.lru_cache(maxsize=256)
def _load_game(game_string: str):
    return pyspiel.load_game(game_string)


@functools.lru_cache(maxsize=1)
def _deck_names() -> tuple[str, ...]:
    """The engine's own name for each card index, asked of the engine."""
    state = _load_game(_game_string(TableConfig(seats=2), (20000, 20000))).new_initial_state()
    names = []
    for card in state.legal_actions():
        text = state.action_to_string(pyspiel.PlayerId.CHANCE, card)
        names.append(text.split()[-1])
    return tuple(names)


def _spent(state) -> list[float]:
    """What each engine seat has put in, read off the engine's own state."""
    text = str(state)
    line = _SPENT_LINE_RE.search(text)
    require(line is not None, "I7", "the engine state has no Spent line", text)
    pairs = _SPENT_RE.findall(line.group(1))
    return [float(amount) for _, amount in pairs]


def _round(state) -> int:
    match = _ROUND_RE.search(str(state))
    require(match is not None, "I7", "the engine state has no Round line", str(state))
    return int(match.group(1))


def _acpc_cards(state, seats: int) -> tuple[list[set[str]], list[str]]:
    """The hole cards and the board, as the engine's own ACPC string spells them."""
    match = _ACPC_RE.search(str(state))
    require(match is not None, "I7", "the engine state has no ACPC State line", str(state))
    fields = match.group(1).split(":")
    cards = fields[-1]
    hole_text, _, board_text = cards.partition("/")
    holes = []
    for chunk in hole_text.split("|"):
        holes.append({chunk[i:i + 2] for i in range(0, len(chunk), 2)})
    require(
        len(holes) == seats,
        "I7",
        f"the engine reported {len(holes)} hands for {seats} seats",
        cards,
    )
    board: list[str] = []
    for street in board_text.split("/"):
        board.extend(street[i:i + 2] for i in range(0, len(street), 2))
    return holes, board


class Hand:
    """One hand at one table, from the deal to the payouts.

    Create it with `Table.new_hand(seed)`. Ask `current_seat` whose turn it is
    and `legal_actions` what that seat may do; give it back an `Action` with
    `apply_action`. When `is_finished` is true, `results` reads the payouts out
    of the engine and `record` is the written account of the whole hand.
    """

    def __init__(self, config: TableConfig, seed: int, button: int = 0):
        if not 0 <= button < config.seats:
            raise ValueError(f"button must be a seat 0..{config.seats - 1}")
        self.config = config
        self.seed = int(seed)
        self.button = int(button)
        self._rng = random.Random(self.seed)
        n = config.seats
        # Engine seat 0 always posts the small blind. Heads-up, that is the
        # button itself; otherwise it is the seat to the button's left.
        self._small_blind_seat = button if n == 2 else (button + 1) % n
        self._engine_stacks = [
            config.stacks[self.seat_of(e)] for e in range(n)
        ]
        self.game_string = _game_string(config, self._engine_stacks)
        self._game = _load_game(self.game_string)
        self._state = self._game.new_initial_state()
        self._events: list[Event] = []
        self._hole: list[list[str]] = [[] for _ in range(n)]
        self._board: list[str] = []
        self._deals_seen = 0
        self._folded = [False] * n
        self._record: HandRecord | None = None
        self._advance_chance()
        self._record_blinds()

    # -- seat bookkeeping -------------------------------------------------

    def engine_index(self, seat: int) -> int:
        """Where a table seat sits in the engine's own numbering."""
        return (seat - self._small_blind_seat) % self.config.seats

    def seat_of(self, engine_index: int) -> int:
        """Which table seat an engine seat is."""
        return (engine_index + self._small_blind_seat) % self.config.seats

    @property
    def small_blind_seat(self) -> int:
        return self._small_blind_seat

    @property
    def big_blind_seat(self) -> int:
        return self.seat_of(1)

    # -- dealing ----------------------------------------------------------

    def _advance_chance(self) -> None:
        """Deal every card the engine is waiting on, from this hand's seed."""
        while not self._state.is_terminal() and self._state.is_chance_node():
            legal = self._state.legal_actions()
            card = legal[self._rng.randrange(len(legal))]
            self._state.apply_action(card)
            self._note_card(card)

    def _note_card(self, card: int) -> None:
        name = _deck_names()[card]
        n = self.config.seats
        if self._deals_seen < n * 2:
            engine_index = self._deals_seen // 2
            self._hole[self.seat_of(engine_index)].append(name)
        else:
            self._board.append(name)
        self._deals_seen += 1

    def _flush_deal_events(self) -> None:
        """Write down cards that have become public since the last check.

        The board comes out in three lots -- three cards, then one, then one,
        which is `numBoardCards=0 3 1 1` in the game definition above -- and
        each lot is written down as its own street. Doing it by position
        rather than by asking the engine which round it is in keeps the streets
        right when everybody is already all-in and the engine deals the rest of
        the board in one go without a betting round in between.
        """
        if not self._events and all(self._hole):
            for seat in range(self.config.seats):
                self._append(
                    kind="hole", street=0, seat=seat, cards=tuple(self._hole[seat])
                )
        dealt = sum(len(e.cards) for e in self._events if e.kind == "board")
        for start, end, street in BOARD_STREETS:
            if len(self._board) >= end > dealt:
                self._append(
                    kind="board", street=street, cards=tuple(self._board[start:end])
                )
                dealt = end

    def _record_blinds(self) -> None:
        self._flush_deal_events()
        for engine_index, amount in enumerate(_spent(self._state)):
            if amount:
                self._append(
                    kind="blind",
                    street=0,
                    seat=self.seat_of(engine_index),
                    amount=amount,
                )

    def _append(self, **fields) -> None:
        self._events.append(Event(index=len(self._events), **fields))

    # -- playing ----------------------------------------------------------

    @property
    def is_finished(self) -> bool:
        return self._state.is_terminal()

    @property
    def street(self) -> int:
        """0 before the flop, 1 flop, 2 turn, 3 river."""
        return _round(self._state)

    def current_seat(self) -> int | None:
        """Whose turn it is, or None once the hand is over."""
        if self._state.is_terminal():
            return None
        return self.seat_of(self._state.current_player())

    def _menu(self) -> dict[Action, int]:
        state = self._state
        player = state.current_player()
        menu: dict[Action, int] = {}
        for engine_action in state.legal_actions():
            text = state.action_to_string(player, engine_action)
            move = _MOVE_RE.search(text)
            require(
                move is not None,
                "I4",
                f"the engine described an action as {text!r}",
                text,
            )
            name = move.group(1)
            require(
                name in _ENGINE_MOVE_TO_ACTION,
                "I4",
                f"the engine offered {name!r}, which is not in the fchpa menu",
                text,
            )
            menu[_ENGINE_MOVE_TO_ACTION[name]] = engine_action
        return menu

    def legal_actions(self) -> list[Action]:
        """What the seat to act may do, taken from the engine's own list."""
        if self._state.is_terminal():
            return []
        return [a for a in Action if a in self._menu()]

    def apply_action(self, action: Action) -> None:
        """Carry out one seat's move, refusing anything the engine disallows."""
        if self._state.is_terminal():
            raise IllegalActionError("the hand is already over")
        if not isinstance(action, Action):
            raise IllegalActionError(f"{action!r} is not one of the five moves")
        menu = self._menu()
        if action not in menu:
            raise IllegalActionError(
                f"{action.value} is not legal here; the engine allows "
                f"{sorted(a.value for a in menu)}",
                str(self._state),
            )
        state = self._state
        player = state.current_player()
        seat = self.seat_of(player)
        engine_action = menu[action]
        text = state.action_to_string(player, engine_action)
        before = _spent(state)[player]
        street = _round(state)
        state.apply_action(engine_action)
        after = _spent(state)[player]
        if action is Action.FOLD:
            self._folded[seat] = True
        self._append(
            kind="action",
            street=street,
            seat=seat,
            action=action.value,
            engine_action=engine_action,
            engine_string=text,
            amount=after - before,
        )
        self._advance_chance()
        self._flush_deal_events()

    # -- the result -------------------------------------------------------

    def contributions(self) -> list[float]:
        """What each table seat has put in, read from the engine."""
        spent = _spent(self._state)
        return [spent[self.engine_index(s)] for s in range(self.config.seats)]

    def net(self) -> list[float]:
        """Each seat's win or loss on the hand, read from the engine."""
        require(
            self._state.is_terminal(),
            "I7",
            "the payouts were asked for before the hand ended",
        )
        returns = self._state.returns()
        return [returns[self.engine_index(s)] for s in range(self.config.seats)]

    def payouts(self) -> list[float]:
        """What each seat was handed at the end, read from the engine.

        Gross, not net: money returned to a seat because nobody matched its
        last bet is a payout to that seat, exactly as winning a pot is.
        """
        contributions = self.contributions()
        return [n + c for n, c in zip(self.net(), contributions)]

    def results(self) -> dict[str, object]:
        """The showdown, as the engine reports it. Nothing here is computed."""
        payouts = self.payouts()
        return {
            "net": self.net(),
            "payouts": payouts,
            "contributions": self.contributions(),
            "pot": sum(self.contributions()),
            "paid_seats": [s for s, p in enumerate(payouts) if p > 0],
            "folded": list(self._folded),
        }

    @property
    def record(self) -> HandRecord:
        """The written account of the hand, complete once the hand is over."""
        finished = self._state.is_terminal()
        contributions = self.contributions()
        net = self.net() if finished else []
        payouts = self.payouts() if finished else []
        events = list(self._events)
        if finished and not any(e.kind == "payout" for e in events):
            street = _round(self._state)
            for seat, amount in enumerate(payouts):
                events.append(
                    Event(
                        index=len(events),
                        kind="payout",
                        street=street,
                        seat=seat,
                        amount=amount,
                    )
                )
            self._events = events
        self._check_cards_against_engine()
        return HandRecord(
            schema=SCHEMA,
            commit=commit_id(),
            seed=self.seed,
            seats=self.config.seats,
            button=self.button,
            small_blind=self.config.small_blind,
            big_blind=self.config.big_blind,
            stacks=list(self.config.stacks),
            engine=ENGINE,
            betting_abstraction=BETTING_ABSTRACTION,
            game_string=self.game_string,
            events=events,
            hole_cards=[list(h) for h in self._hole],
            board=list(self._board),
            contributions=contributions,
            payouts=payouts,
            net=net,
            folded=list(self._folded),
            pot=sum(contributions),
            finished=finished,
        )

    def _check_cards_against_engine(self) -> None:
        """Cross-check our reading of the deal against the engine's own text.

        We attribute each dealt card by its position in the deal order; the
        engine also writes the whole deal out in its ACPC state string. If
        those two ever disagree the record is wrong about who held what, so
        the run stops.
        """
        holes, board = _acpc_cards(self._state, self.config.seats)
        for engine_index, engine_hand in enumerate(holes):
            seat = self.seat_of(engine_index)
            ours = set(self._hole[seat])
            require(
                ours == engine_hand,
                "I7",
                f"seat {seat} was recorded with {sorted(ours)} but the engine "
                f"says {sorted(engine_hand)}",
                str(self._state),
            )
        require(
            self._board == board,
            "I7",
            f"the board was recorded as {self._board} but the engine says {board}",
            str(self._state),
        )


class Table:
    """A table of two to nine seats that deals hands from a seed."""

    def __init__(self, config: TableConfig):
        self.config = config

    @classmethod
    def of(cls, seats: int, **kwargs) -> "Table":
        return cls(TableConfig(seats=seats, **kwargs))

    def new_hand(self, seed: int, button: int = 0) -> Hand:
        """Deal a fresh hand. The same seed and button deal the same cards."""
        return Hand(self.config, seed=seed, button=button)


def deal_check(seats: int) -> tuple[bool, str]:
    """Can this seat count be dealt at all?

    Answers the question `EVALUATION_STRATEGY.md` section 4.5 insists on: a
    seat count the engine cannot deal is recorded NOT RUN with the reason,
    never counted as passed. Returns (True, "") or (False, reason).
    """
    try:
        config = TableConfig(seats=seats)
    except ValueError as exc:
        return False, str(exc)
    try:
        hand = Hand(config, seed=0, button=0)
    except Exception as exc:  # noqa: BLE001 - the reason is the point
        return False, f"{type(exc).__name__}: {exc}"
    if hand.current_seat() is None:
        return False, "the engine deals the hand already finished"
    return True, ""


def dealable_seat_counts(
    candidates: Iterable[int] = range(MIN_SEATS, MAX_SEATS + 1),
) -> dict[int, tuple[bool, str]]:
    """Every seat count asked for, each with a yes or a reason for no."""
    return {n: deal_check(n) for n in candidates}
