"""pokerbot: the table we trust.

Stage 1 of `BUILD_PLAN.md`, task T1. This package is the adapter over
OpenSpiel's `universal_poker` and nothing else: it deals hands at two to nine
seats, offers each seat the five-move menu `{fold, call, half pot, pot,
all-in}`, writes down everything that happened, and reads the payouts back out
of the engine. It contains no strategy, no search and no opponent model; those
are tasks T2 and T3.

The one thing in it that chooses an action is `replay.play_scripted_hand`,
which draws uniformly from the engine's own menu so that a hand can be walked
to its end for invariant I6's cross-process check. It reads no cards and is not
a baseline to measure a bot against.
"""

from .invariants import InvariantViolation, require
from .provenance import commit_id
from .record import Event, HandRecord, SCHEMA
from .table import (
    Action,
    BETTING_ABSTRACTION,
    ENGINE,
    EngineView,
    Hand,
    IllegalActionError,
    MAX_SEATS,
    MIN_SEATS,
    SeatCountNotDealable,
    Table,
    TableConfig,
    deal_check,
    dealable_seat_counts,
    engine_menu,
)

__all__ = [
    "Action",
    "BETTING_ABSTRACTION",
    "ENGINE",
    "EngineView",
    "Event",
    "Hand",
    "HandRecord",
    "IllegalActionError",
    "InvariantViolation",
    "MAX_SEATS",
    "MIN_SEATS",
    "SCHEMA",
    "SeatCountNotDealable",
    "Table",
    "TableConfig",
    "commit_id",
    "deal_check",
    "dealable_seat_counts",
    "engine_menu",
    "require",
]
