"""The first bot: depth-limited search over the engine's own tree.

Task T2 of `BUILD_PLAN.md` section 4, built to `DECISION_LAYER_SEARCH.md`
:637 -- "build option 3's search once". In one paragraph, what it does:

    It is the bot's turn. For each move the engine is offering -- fold, call,
    half pot, pot, all-in -- it imagines the hand finishing, over and over.
    Each imagining deals the other seats a hand out of the cards nobody has
    shown, plays the rest of *this* betting round, and then, at that point
    (the *depth limit*), gives every seat one of four fixed ways of playing on
    and lets the engine run the hand to the end. The move whose imaginings
    ended with the most chips on average is the move it makes. It stops when
    it has imagined enough, or when the clock runs out, whichever comes first.

Where every part of it comes from:

* The shape -- look ahead to the end of the betting round, then finish under
  one of four continuation strategies -- is Pluribus's, and is what
  `DECISION_LAYER_SEARCH.md` "Option 3" recommends and measures. It is *not*
  IS-MCTS, which crashes the process above two players (same file, :322).
* The loop is a port of the benchmarked one in
  `research/decision_layer/bench_decision_layer.py` (`decide_dls`,
  `determinize`, `CONTINUATIONS`, `_act`), which is where this document's
  throughput figures were measured. The numbers in `CONTINUATIONS` below are
  that file's, unchanged. Three things differ, each noted at the code:
  the menu is `fchpa`'s five moves rather than `fcpa`'s four; the depth limit
  is spotted by the engine's own next chance node instead of by re-parsing the
  engine's JSON at every node; and the search stops at a fixed number of
  finishes per move as well as at the clock, so that the same seed gives the
  same answer.
* Every rule, every legal move, every card and every payoff comes from
  OpenSpiel `universal_poker`, reached through the T1 adapter's `EngineView`.
  Nothing here ranks a hand or decides who won, and no model is called:
  `CLAUDE.md`'s forefront rule.

What it cannot yet do well, said plainly: the four ways of playing on are
hand-set guesses, not solver output. `DECISION_LAYER_SEARCH.md` "What it needs
precomputed" says so in as many words, and `DECISION_LAYER_BLUEPRINT.md` is
the document that replaces them. The speed is measured; the quality of play is
provisional until it is measured in chips.
"""

from __future__ import annotations

import dataclasses
import functools
import random
import time

import pyspiel

from .invariants import require
from .table import Action, EngineView, engine_menu

#: The clock a real table allows a decision, and `BUILD_PLAN.md`'s bar: no
#: decision over 250 ms. Every caller may pass its own.
BUDGET_S = 0.25

#: How many finished hands each candidate move gets before the search stops.
#: This is the reason the same seed gives the same answer: a search that ran
#: purely until the clock ran out would do more work on a quiet laptop than on
#: a busy one and could pick a different move for the same hand, which makes a
#: result impossible to reproduce. The clock is still there, as the cap that
#: `BUILD_PLAN.md` requires; this number is set low enough that on the machine
#: `DECISION_LAYER_SEARCH.md` measured -- about 2,400 finishes per 250 ms at
#: six seats -- the count is reached first with room to spare. Measured here:
#: five moves x 200 finishes takes about 60 ms at six seats at load 4.2, a
#: quarter of the budget, so the machine has to be four times slower than it
#: was measured on before the clock, rather than the count, ends a search.
PLAYOUTS_PER_CANDIDATE = 200

#: How much of the budget is held back so that the finish already under way
#: cannot overrun it. Raised, as the search runs, to the slowest single finish
#: it has seen, so a slow machine keeps the guarantee rather than losing it.
INITIAL_RESERVE_S = 0.005

#: The raises on the menu, cheapest first. `bench_decision_layer.py` reached
#: for the pot-sized bet before the all-in, i.e. the smallest raise available;
#: `fchpa` adds a smaller rung still (half pot), and it comes first here for
#: the same reason.
RAISE_LADDER = (Action.HALF_POT, Action.POT, Action.ALL_IN)


@dataclasses.dataclass(frozen=True)
class Continuation:
    """One fixed way of playing a hand out from the depth limit.

    Three numbers that add to one: how often this way of playing folds, calls
    and raises when it is asked to act. It reads no cards and knows nothing
    about the hand it is holding -- that is what makes it a placeholder.
    """

    name: str
    fold: float
    call: float
    raise_: float


#: The four ways of playing on. **Hand-set placeholders, not solver output.**
#: They are `research/decision_layer/bench_decision_layer.py`'s `CONTINUATIONS`
#: to the decimal, renamed to the four names `BUILD_PLAN.md` T2 asks for:
#: its "give-up biased" is fold-biased, "call-down biased" is call-biased,
#: "very aggressive" is raise-biased, and "aggressive" -- a fold, a call and a
#: raise all well represented -- is the mixed one. `k = 4` is Pluribus's own
#: number (`DECISION_LAYER_SEARCH.md` "Option 3", "What it is").
#:
#: Nothing about these numbers is derived, measured or tuned, and no number
#: here was chosen by playing against the opponents these are measured against.
#: `DECISION_LAYER_BLUEPRINT.md` is where real ones come from, and
#: `DECISION_LAYER_SEARCH.md`'s option 4 is where each seat stops drawing from
#: this tuple at random and starts drawing from its own measured behaviour.
CONTINUATIONS = (
    Continuation("fold_biased", fold=0.45, call=0.50, raise_=0.05),
    Continuation("call_biased", fold=0.10, call=0.85, raise_=0.05),
    Continuation("mixed", fold=0.10, call=0.55, raise_=0.35),
    Continuation("raise_biased", fold=0.05, call=0.35, raise_=0.60),
)


@dataclasses.dataclass(frozen=True)
class Decision:
    """What the search decided, and what it did to get there."""

    action: Action
    #: Mean chips won per finished hand, per candidate move. Empty for a
    #: candidate the clock never reached.
    means: dict[Action, float]
    #: How many hands were finished for each candidate move.
    counts: dict[Action, int]
    playouts: int
    elapsed_s: float
    #: True when the clock, not the finish count, ended the search -- so this
    #: decision is not reproducible from its seed alone.
    truncated: bool
    #: True when the clock ran out before a single hand was finished, so the
    #: move below is a fallback and not a search result. Should never happen;
    #: the arena counts it.
    starved: bool


@functools.lru_cache(maxsize=16)
def _game(game_string: str):
    """The searcher's own copy of the same game the table is dealing."""
    return pyspiel.load_game(game_string)


@functools.lru_cache(maxsize=16)
def _deck(game_string: str) -> tuple[int, ...]:
    """Every card in this game's deck, asked of the engine rather than assumed."""
    return tuple(_game(game_string).new_initial_state().legal_actions())


def build_world(view: EngineView, rng: random.Random, game_string: str | None = None):
    """One whole hand consistent with what the seat to act can see.

    The seat's own two cards and the board stay as they are; every card it has
    not been shown is dealt again out of the cards it cannot account for. This
    is `bench_decision_layer.py`'s `determinize`, simplified by the adapter
    having already done the bookkeeping: `EngineView.history` arrives with the
    unseen slots already blank, so there is nothing here to work out about who
    was dealt what -- and nothing here that *could* look at an opponent's real
    cards, because they are not in the view.

    OpenSpiel ships `resample_from_infostate` for this and it crashes above two
    players, which is why the replay is done by hand. Dealing cards out of a
    deck is card bookkeeping, which `CLAUDE.md` puts on our side of the line;
    no hand is ranked or valued here.

    Pass `game_string` to replay the same hand into a differently configured
    copy of the same game -- `equity_rule.py` passes one that has the engine's
    Monte Carlo equity calculator switched on. It must be the view's own game
    string with settings changed, never a different game.
    """
    string = view.game_string if game_string is None else game_string
    seen = view.seen_cards()
    deck = [card for card in _deck(string) if card not in seen]
    rng.shuffle(deck)
    fresh = iter(deck)
    world = _game(string).new_initial_state()
    for card in view.history:
        world.apply_action(next(fresh) if card is None else card)
    return world


def _continuation_action(world, continuation: Continuation, rng: random.Random) -> int:
    """One move under a fixed way of playing on, drawn from the three weights.

    `bench_decision_layer.py`'s `_act`, with the menu read through the
    adapter's translation so the five-move `fchpa` menu is used rather than
    `fcpa`'s four.
    """
    menu = engine_menu(world)
    roll = rng.random()
    if roll < continuation.fold and Action.FOLD in menu:
        return menu[Action.FOLD]
    if roll < continuation.fold + continuation.raise_:
        for action in RAISE_LADDER:
            if action in menu:
                return menu[action]
    if Action.CALL in menu:
        return menu[Action.CALL]
    # The engine offers no call only when there is nothing to call and nothing
    # to bet, which `fchpa` does not produce; fall back to its own list rather
    # than assume.
    return rng.choice(sorted(menu.values()))


def _finish_one(view: EngineView, action: Action, rng: random.Random) -> float:
    """Play one imagined hand from one candidate move, and return the chips.

    The depth limit is the end of the current betting round. Past it every
    seat is given a fresh way of playing on, drawn at random from the four,
    exactly as `bench_decision_layer.py` does -- and as
    `DECISION_LAYER_SEARCH.md` "Option 3" requires, because a search that
    assumes each opponent will keep playing one fixed way is the classic way
    this method fools itself.

    Spotting the depth limit: `bench_decision_layer.py` re-read the engine's
    round counter out of its JSON at every node. The round ends exactly when
    the engine stops to deal the next board card, so the first chance node
    after the root is the same instant, and noticing it costs nothing.
    """
    world = build_world(view, rng)
    menu = engine_menu(world)
    require(
        action in menu,
        "I4",
        f"the search weighed {action.value}, which the engine does not offer "
        f"in the position it was given",
    )
    world.apply_action(menu[action])
    past_depth_limit = False
    continuations: dict[int, Continuation] = {}
    while not world.is_terminal():
        if world.is_chance_node():
            past_depth_limit = True  # the engine is dealing: the round ended
            outcomes = world.legal_actions()
            world.apply_action(outcomes[rng.randrange(len(outcomes))])
            continue
        seat = world.current_player()
        if seat not in continuations or past_depth_limit:
            continuations[seat] = CONTINUATIONS[rng.randrange(len(CONTINUATIONS))]
        world.apply_action(_continuation_action(world, continuations[seat], rng))
    return world.returns()[view.player]


def decide(
    view: EngineView,
    *,
    seed: int,
    budget_s: float = BUDGET_S,
    playouts_per_candidate: int = PLAYOUTS_PER_CANDIDATE,
) -> Decision:
    """Choose a move for the seat to act. The whole bot is this function.

    `seed` fixes every card dealt and every way of playing on that the search
    draws, so the same view and the same seed give the same move -- unless the
    clock cuts the search short, which the returned `Decision` says.

    `budget_s` is the wall clock, measured with `time.monotonic` because it is
    the clock that cannot be moved backwards by the machine adjusting its idea
    of the time of day. The search never starts a finish it does not expect to
    complete inside the budget.
    """
    require(bool(view.menu), "I4", f"seat {view.seat} was asked to act with no legal move")
    rng = random.Random(seed)
    candidates = list(view.menu)
    totals = {action: 0.0 for action in candidates}
    counts = {action: 0 for action in candidates}
    started = time.monotonic()
    deadline = started + budget_s
    reserve = INITIAL_RESERVE_S
    truncated = False
    for _ in range(playouts_per_candidate):
        for action in candidates:
            before = time.monotonic()
            if before + reserve > deadline:
                truncated = True
                break
            totals[action] += _finish_one(view, action, rng)
            counts[action] += 1
            reserve = max(reserve, time.monotonic() - before)
        if truncated:
            break
    elapsed = time.monotonic() - started
    playouts = sum(counts.values())
    means = {
        action: totals[action] / counts[action]
        for action in candidates
        if counts[action]
    }
    if means:
        # Ties break towards the earlier move on the menu, which is fixed
        # order (fold, call, half pot, pot, all-in), so a tie is reproducible.
        best = max(candidates, key=lambda a: (means.get(a, float("-inf")), -candidates.index(a)))
        starved = False
    else:
        # The clock ran out before one hand was finished. There is no search
        # result to report, so take the move that neither gives the hand up
        # nor puts more money in, and say loudly that this happened.
        best = Action.CALL if Action.CALL in view.menu else view.menu[0]
        starved = True
    return Decision(
        action=best,
        means=means,
        counts=counts,
        playouts=playouts,
        elapsed_s=elapsed,
        truncated=truncated,
        starved=starved,
    )
