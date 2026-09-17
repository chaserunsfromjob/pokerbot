"""Three players that are not trying: the opponents the bot is measured against.

`BUILD_PLAN.md` T2 says that if D1 -- whether to take the classmate's practice
arena -- is still unanswered when T2 starts, "stand up three trivial opponents
-- always-fold, always-call, uniform-random -- and run the same measurement
against those instead". D1 is unanswered, so these are they.

What each of them is, and why it is worth having:

* `always_fold`   gives up the moment it is asked for money. It cannot be beaten
                  by much and it cannot lose much: its score is the blinds it
                  posts, which is a figure that can be worked out on paper, so
                  it is how the arena's accounting gets checked.
* `always_call`   never folds and never raises. Everything it is in goes to a
                  showdown, so it pays off every good hand it meets.
* `uniform_random` picks from the menu the engine is offering with no
                  preference at all. This is the baseline `BUILD_PLAN.md` T2
                  names for the win-rate interval that has to exclude zero.

None of them looks at a card, and none of them is a strategy: they are three
fixed mistakes to measure against. A real league of opponents, each built
around one human mistake, is task T3 (`EVALUATION_STRATEGY.md` section 3.2).

Every one takes the menu the engine offered and returns one move from it, so
none of them can play an illegal move even by accident.
"""

from __future__ import annotations

import random
from typing import Callable, Sequence

from .invariants import require
from .table import Action

#: What each opponent is called on the command line.
OPPONENTS = ("fold", "call", "random")


def always_fold(menu: Sequence[Action], rng: random.Random) -> Action:
    """Fold whenever folding is allowed; check when it is free to."""
    if Action.FOLD in menu:
        return Action.FOLD
    # The engine offers no fold when there is nothing to call: folding a hand
    # that costs nothing is not a move any engine allows.
    return Action.CALL if Action.CALL in menu else menu[0]


def always_call(menu: Sequence[Action], rng: random.Random) -> Action:
    """Call every bet, raise nothing, fold nothing."""
    return Action.CALL if Action.CALL in menu else menu[0]


def uniform_random(menu: Sequence[Action], rng: random.Random) -> Action:
    """Draw from the engine's own menu with every move equally likely."""
    menu = list(menu)
    return menu[rng.randrange(len(menu))]


#: The name-to-player table the arena looks names up in.
BY_NAME: dict[str, Callable[[Sequence[Action], random.Random], Action]] = {
    "fold": always_fold,
    "call": always_call,
    "random": uniform_random,
}


def by_name(name: str):
    """One of the three, by the name the command line uses."""
    require(
        name in BY_NAME,
        "I4",
        f"there is no opponent called {name!r}; the three are {sorted(BY_NAME)}",
    )
    return BY_NAME[name]
