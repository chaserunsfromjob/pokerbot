"""The written account of one hand.

Everything that happened, in the order it happened, in a form that turns into
the same bytes every time: every action, every card that came out, what every
seat put in, what every seat was paid, the shuffle number the hand was dealt
from, and the commit the code was at.

"The same bytes every time" is the whole point. Invariant I6 says the same
seed and the same commit must replay to a byte-identical record, and a record
that serialises its fields in a different order from one run to the next could
not show that even when the hand really was identical. So `to_json` sorts keys
and pins the separators, and `to_bytes` fixes the encoding.
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any

SCHEMA = "pokerbot.hand_record/1"


@dataclasses.dataclass(frozen=True)
class Event:
    """One thing that happened, at one point in the hand."""

    index: int
    kind: str  # blind | hole | action | board | payout
    street: int  # 0 preflop, 1 flop, 2 turn, 3 river
    seat: int | None = None
    cards: tuple[str, ...] = ()
    action: str | None = None
    engine_action: int | None = None
    engine_string: str | None = None
    amount: float | None = None

    def as_dict(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        d["cards"] = list(self.cards)
        return d


@dataclasses.dataclass
class HandRecord:
    """One hand, complete, from deal to payout."""

    schema: str
    commit: str
    seed: int
    seats: int
    button: int
    small_blind: int
    big_blind: int
    stacks: list[int]
    engine: str
    betting_abstraction: str
    game_string: str
    events: list[Event] = dataclasses.field(default_factory=list)
    hole_cards: list[list[str]] = dataclasses.field(default_factory=list)
    board: list[str] = dataclasses.field(default_factory=list)
    contributions: list[float] = dataclasses.field(default_factory=list)
    payouts: list[float] = dataclasses.field(default_factory=list)
    net: list[float] = dataclasses.field(default_factory=list)
    folded: list[bool] = dataclasses.field(default_factory=list)
    pot: float = 0.0
    finished: bool = False

    def as_dict(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        d["events"] = [e.as_dict() for e in self.events]
        return d

    def to_json(self) -> str:
        """The canonical text form: sorted keys, no incidental whitespace."""
        return json.dumps(
            self.as_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )

    def to_bytes(self) -> bytes:
        """The canonical byte form. This is what invariant I6 compares."""
        return (self.to_json() + "\n").encode("utf-8")
