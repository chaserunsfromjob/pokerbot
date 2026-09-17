"""The cheap check that runs beside the bot, and never plays for it.

In plain words: work out how often this hand wins if everyone stays to the end
(its *equity*), compare that with the price the seat is being asked to pay to
stay in (its *pot odds*), and say what a player who only knew those two numbers
would do. Then write both that answer and the bot's own answer down, and play
the bot's.

`BUILD_PLAN.md` T2 and `DECISION_LAYER_SEARCH.md` :637 are explicit about the
"never plays for it" part: the rule is kept "as a logged check rather than as
the decision", because it is the baseline the search has to beat before anyone
trusts the search -- and it cannot size a bet or bluff, so it is not a bot.
Nothing in this module is wired into `search.decide`; `arena.py` calls both and
logs the pair.

Where the equity comes from: the engine. `universal_poker` has its own Monte
Carlo equity calculator, switched on with the `calcOddsNumSims` game parameter
and read back out of the engine's own JSON. No hand is ranked or valued by code
written here, which is `CLAUDE.md`'s forefront rule; `research/decision_layer/
bench_decision_layer.py` (`decide_equity`) is the measured version this is a
port of, and the thresholds below are that file's, unchanged.

One honest limitation, the same one the benchmark has: the engine's calculator
answers "how often does this hand win if every hand still in is played to the
river", which is equity against the hands that were dealt, not against the
hands an opponent would still be holding after betting like that. That is
exactly why this is a check and not the bot.
"""

from __future__ import annotations

import dataclasses
import json
import random
import statistics
import time

from .invariants import require
from .search import build_world
from .table import Action, EngineView

#: How many run-outs of the board the engine simulates per sampled world.
#: `bench_decision_layer.py`'s `--odds-sims` default.
ODDS_SIMS = 200

#: How many worlds -- guesses at what the other seats hold -- are sampled and
#: averaged. The benchmark sampled until its clock ran out; a fixed count is
#: used here for the same reason `search.py` uses one: the same seed has to
#: give the same answer.
WORLDS = 8

#: With nothing to call, bet when the hand wins this often or more.
BET_WHEN_FREE = 0.60

#: With something to call, raise when equity beats the price by this much.
RAISE_MARGIN = 0.25


@dataclasses.dataclass(frozen=True)
class RuleCheck:
    """What the rule would have done, and the arithmetic behind it."""

    action: Action
    equity: float
    pot: float
    to_call: float
    #: The share of the pot the seat is buying: `to_call / (pot + to_call)`.
    #: Zero when there is nothing to call.
    needed: float
    worlds: int
    elapsed_s: float


def with_odds(game_string: str, sims: int = ODDS_SIMS) -> str:
    """The table's own game, with the engine's equity calculator switched on.

    The T1 adapter deals with the calculator off, because the table has no use
    for it and it costs time on every state. This turns it on in a copy of the
    same game definition -- the same seats, blinds, stacks and betting
    abstraction, one setting added.
    """
    if not game_string.endswith(")"):
        raise ValueError(f"the game definition does not look like one: {game_string!r}")
    if "calcOddsNumSims" in game_string:
        raise ValueError("the game definition already sets calcOddsNumSims")
    return f"{game_string[:-1]},calcOddsNumSims={int(sims)})"


def pot_and_call(world, player: int) -> tuple[float, float]:
    """Chips in the middle, and chips this seat must put in to stay.

    Both read out of the engine's own JSON, exactly as
    `bench_decision_layer.py`'s `pot_and_call` does.
    """
    blob = json.loads(world.to_json())
    contributions = blob["player_contributions"]
    return float(blob["pot_size"]), float(max(contributions) - contributions[player])


def rule_action(equity: float, pot: float, to_call: float, menu) -> Action:
    """What a seat that knew only its equity and its price would do.

    The whole rule, and the only place in this module that chooses anything:

    * Nothing to call. Bet the pot when the hand wins at least
      `BET_WHEN_FREE` of the time; otherwise take the free card.
    * Something to call. The price of staying in is the share of the final pot
      being bought, `to_call / (pot + to_call)`. Below that price the hand is
      losing money, so fold; more than `RAISE_MARGIN` above it, raise; in
      between, call.

    `menu` is what the engine is offering, and no move is ever returned that is
    not on it.
    """
    menu = list(menu)
    if to_call <= 0:
        if equity >= BET_WHEN_FREE and Action.POT in menu:
            return Action.POT
        return Action.CALL if Action.CALL in menu else menu[0]
    needed = to_call / (pot + to_call)
    if equity < needed:
        return Action.FOLD if Action.FOLD in menu else Action.CALL
    if equity > needed + RAISE_MARGIN and Action.POT in menu:
        return Action.POT
    return Action.CALL if Action.CALL in menu else menu[0]


def check(
    view: EngineView,
    *,
    seed: int,
    worlds: int = WORLDS,
    sims: int = ODDS_SIMS,
) -> RuleCheck:
    """Run the rule on a position. Its answer is logged, never played."""
    require(bool(view.menu), "I4", f"seat {view.seat} was asked to act with no legal move")
    started = time.monotonic()
    rng = random.Random(seed)
    game_string = with_odds(view.game_string, sims)
    equities = []
    pot = to_call = 0.0
    for _ in range(max(1, worlds)):
        world = build_world(view, rng, game_string=game_string)
        odds = json.loads(world.to_json())["odds"]
        # The engine reports (wins, ties) per seat, in seat order. A tie is
        # counted as half a win, which is `bench_decision_layer.py`'s reading
        # of the same field.
        equities.append(odds[2 * view.player] + 0.5 * odds[2 * view.player + 1])
        pot, to_call = pot_and_call(world, view.player)
    equity = statistics.fmean(equities)
    return RuleCheck(
        action=rule_action(equity, pot, to_call, view.menu),
        equity=equity,
        pot=pot,
        to_call=to_call,
        needed=(to_call / (pot + to_call)) if to_call > 0 else 0.0,
        worlds=len(equities),
        elapsed_s=time.monotonic() - started,
    )
