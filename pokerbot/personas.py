"""The league's opponents: four calibration agents and nine behavioural personas.

What this module is for, in one sentence: to provide the sparring partners the
scoreboard measures a bot against -- caricatures of one human mistake each,
whose parameters are drawn afresh at the start of every session and written into
the report.

`EVALUATION_STRATEGY.md` section 3.2 defines both groups and this file follows
it name for name.

**Group A, the calibration agents.** `always_fold`, `always_call`,
`always_raise`, `call_raise_50_50`. Their job is to prove the harness works, not
to challenge the bot. None of them looks at a card. `always_fold` is the one
with a closed-form answer -- it can only ever lose the blinds it posts -- and
that is what checks the accounting.

**Group B, the nine behavioural personas.** `calling_station`, `nit`, `maniac`,
`never_bluffs`, `fit_or_fold`, `tag`, `lag`, `tilter`, `sizing_tell`. Each is
defined by a rule and then parameterised, and section 3.2's first design rule is
that the parameters are **drawn from a distribution at the start of a session,
never fixed at a point**: a bot tuned against one exact parameter point looks
better than it is. Every drawn value is in `Persona.params` and every one of
them is printed in the report.

**Where a hand's strength comes from.** `CLAUDE.md`'s forefront rule reserves
ranking or valuing a hand to the engine, so no persona in this file ranks a hand
and there is no transcribed strength table anywhere in it. When a persona's rule
needs to know how good its hand is, it asks `showdown_equity`, which deals the
rest of the hand out on the engine's own `universal_poker` game and reads the
engine's own showdown: how often these two cards beat one random other hand on
this board. Same for "the top X% of starting hands", which `preflop_top_fraction`
answers by ranking all 169 starting-hand classes by that same engine-computed
equity. We do the card bookkeeping -- the 169 classes, the combination counts --
which is what the forefront rule hands us; the engine does every comparison of
one hand against another.

**Every agent acts through the adapter's menu and nothing else.** It asks the
`Hand` what is legal and returns one of `{fold, call, half pot, pot, all-in}`.
The choice of bet size stays inside the engine.

**The signature.** An agent is any callable `agent(hand, seat) -> Action`. That
is the adapter's own view of a decision -- the hand as it stands and whose turn
it is -- so a search bot with the same signature plugs into the scoreboard
without either side changing.
"""

from __future__ import annotations

import dataclasses
import functools
import hashlib
import itertools
import random
from typing import Callable, Iterable, Sequence

from .table import (
    Action,
    Hand,
    TableConfig,
    _deck_names,
    _game_string,
    _load_game,
)

#: An agent: given the hand as it stands and whose turn it is, one of the five
#: moves. Every persona here, and any bot the scoreboard measures, is one of
#: these.
Agent = Callable[[Hand, int], Action]

RANKS = "23456789TJQKA"

#: How many of the 1326 two-card combinations each of the 169 starting-hand
#: classes accounts for. Ours to count: `CLAUDE.md` hands us the enumeration of
#: the 169 preflop classes and the deck combinatorics, and keeps only the
#: *ranking* of a hand with the engine.
COMBOS_PAIR = 6
COMBOS_SUITED = 4
COMBOS_OFFSUIT = 12
TOTAL_COMBOS = 1326


# --------------------------------------------------------------------------
# Hand strength, asked of the engine
# --------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def _showdown_game():
    """A two-seat game used for nothing but running a hand out to a showdown.

    It is built from the adapter's own game definition (`table._game_string`)
    rather than a second copy written here: the engine's configuration is the
    adapter's business, and a persona that configured the engine differently
    would be measuring a different game from the one the bot plays.
    """
    config = TableConfig(seats=2)
    stacks = (config.stacks[0], config.stacks[1])
    return _load_game(_game_string(config, stacks))


@functools.lru_cache(maxsize=1)
def _card_indices() -> dict[str, int]:
    return {name: i for i, name in enumerate(_deck_names())}


def stable_seed(*parts: object) -> int:
    """A seed that is the same in every process, unlike Python's own `hash`.

    `hash` of a string is salted per process, so a run seeded through it would
    not reproduce tomorrow. Every seed in this file goes through here instead.
    """
    text = "|".join(str(part) for part in parts)
    return int.from_bytes(hashlib.blake2b(text.encode(), digest_size=8).digest(), "big")


def _run_showdown(hole: Sequence[str], villain: Sequence[str], board: Sequence[str]) -> float:
    """Play these exact cards out on the engine and ask who won.

    Both seats check and call all the way, so the hand always reaches a
    showdown and the engine's own `returns` says which hand is better. 1.0 for
    a win, 0.5 for a tie, 0.0 for a loss. Nothing here compares two hands.
    """
    index = _card_indices()
    state = _showdown_game().new_initial_state()
    for card in itertools.chain(hole, villain):
        state.apply_action(index[card])
    remaining = list(board)
    while not state.is_terminal():
        if state.is_chance_node():
            state.apply_action(index[remaining.pop(0)])
            continue
        player = state.current_player()
        call = None
        for action in state.legal_actions():
            if "Call" in state.action_to_string(player, action):
                call = action
                break
        if call is None:  # pragma: no cover - fchpa always offers a call
            call = state.legal_actions()[0]
        state.apply_action(call)
    hero = state.returns()[0]
    if hero > 0:
        return 1.0
    if hero < 0:
        return 0.0
    return 0.5


@functools.lru_cache(maxsize=200_000)
def _equity_cached(hole: tuple[str, ...], board: tuple[str, ...], rollouts: int) -> float:
    deck = [c for c in _deck_names() if c not in hole and c not in board]
    # Deterministic: the same two cards on the same board always return the same
    # number, whoever asks and in whatever order, so two arms of a paired run
    # cannot drift apart through their opponents' hand reading.
    rng = random.Random(stable_seed("equity", hole, board, rollouts))
    won = 0.0
    for _ in range(rollouts):
        sample = rng.sample(deck, 2 + (5 - len(board)))
        villain = sample[:2]
        full_board = list(board) + sample[2:]
        won += _run_showdown(hole, villain, full_board)
    return won / rollouts


def showdown_equity(
    hole: Sequence[str], board: Sequence[str] = (), rollouts: int = 24
) -> float:
    """How often these cards beat one random hand, decided by the engine.

    This is a strength number, not a multiway equity: it asks the engine to
    finish the hand against **one** random opponent many times over and counts
    the showdowns it wins. A persona is a caricature and this is the caricature's
    idea of "how good is my hand"; nothing in the bot's own play uses it.
    """
    return _equity_cached(tuple(sorted(hole)), tuple(sorted(board)), rollouts)


def hand_class(hole: Sequence[str]) -> str:
    """Which of the 169 starting-hand classes these two cards are, e.g. `AKs`.

    Counting and naming the classes is card bookkeeping, which the forefront
    rule leaves to us. It says nothing about which class is better.
    """
    first, second = hole
    high, low = sorted((first[0], second[0]), key=RANKS.index, reverse=True)
    if first[0] == second[0]:
        return f"{high}{low}"
    suited = "s" if first[1] == second[1] else "o"
    return f"{high}{low}{suited}"


def class_combos(name: str) -> int:
    """How many of the 1326 two-card combinations this class accounts for."""
    if len(name) == 2:
        return COMBOS_PAIR
    return COMBOS_SUITED if name.endswith("s") else COMBOS_OFFSUIT


@functools.lru_cache(maxsize=4)
def _preflop_ranking(rollouts: int) -> dict[str, float]:
    """Every starting-hand class in the order the engine's showdowns put them.

    The value is the fraction of all starting hands that are at least this
    strong, counted in combinations: 0.0 is the best hand there is and 1.0 the
    worst. "The top 15% of hands" is then simply "this number is at most 0.15".

    The ordering is not ours. Each class is dealt out against random hands on
    the engine and scored by how often the engine's own showdown says it won.
    """
    equities: dict[str, float] = {}
    for i, high in enumerate(reversed(RANKS)):
        for j, low in enumerate(reversed(RANKS)):
            if j < i:
                continue
            if high == low:
                name, cards = high + low, (high + "s", low + "h")
            else:
                name, cards = f"{high}{low}s", (high + "s", low + "s")
                equities[name] = showdown_equity(cards, (), rollouts)
                name, cards = f"{high}{low}o", (high + "s", low + "h")
            equities[name] = showdown_equity(cards, (), rollouts)
    ordered = sorted(equities, key=lambda n: -equities[n])
    cumulative: dict[str, float] = {}
    seen = 0
    for name in ordered:
        seen += class_combos(name)
        cumulative[name] = seen / TOTAL_COMBOS
    return cumulative


def preflop_top_fraction(hole: Sequence[str], rollouts: int = 120) -> float:
    """Where these two cards sit in the ranking: 0.02 means "top 2% of hands"."""
    return _preflop_ranking(rollouts)[hand_class(hole)]


# --------------------------------------------------------------------------
# What a seat can see when it acts
# --------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class SeatView:
    """Everything a persona is allowed to look at, read off the adapter."""

    seat: int
    seats: int
    street: int            # 0 pre-flop, 1 flop, 2 turn, 3 river
    hole: tuple[str, ...]
    board: tuple[str, ...]
    legal: tuple[Action, ...]
    to_call: float         # chips needed to stay in; 0 means a check is free
    pot: float             # chips in the middle, this seat's own money included
    big_blind: float

    @property
    def facing_bet(self) -> bool:
        return self.to_call > 0

    @property
    def pot_odds(self) -> float:
        """The share of the final pot this call would buy. 0 when nothing to call."""
        if self.to_call <= 0:
            return 0.0
        return self.to_call / (self.pot + self.to_call)


def seat_view(hand: Hand, seat: int) -> SeatView:
    """Build the view. Every field comes out of the adapter, none is computed here."""
    record = hand.record
    contributions = hand.contributions()
    owed = max(contributions) - contributions[seat]
    return SeatView(
        seat=seat,
        seats=hand.config.seats,
        street=hand.street,
        hole=tuple(record.hole_cards[seat]),
        board=tuple(record.board),
        legal=tuple(hand.legal_actions()),
        to_call=owed,
        pot=sum(contributions),
        big_blind=float(hand.config.big_blind),
    )


def _first_legal(view: SeatView, *preferences: Action) -> Action:
    for action in preferences:
        if action in view.legal:
            return action
    return view.legal[0]


def _passive(view: SeatView) -> Action:
    """Check if it is free, call if it is not, and fold only if nothing else is legal."""
    return _first_legal(view, Action.CALL, Action.HALF_POT, Action.FOLD)


def _give_up(view: SeatView) -> Action:
    """Fold if folding is possible; a free check is never worse, so take it if not."""
    if view.facing_bet:
        return _first_legal(view, Action.FOLD, Action.CALL)
    return _first_legal(view, Action.CALL, Action.FOLD)


def _aggress(view: SeatView, size: Action = Action.POT) -> Action:
    """Put money in at the named size, dropping to what the engine will allow."""
    if size is Action.POT:
        return _first_legal(view, Action.POT, Action.HALF_POT, Action.ALL_IN, Action.CALL)
    if size is Action.HALF_POT:
        return _first_legal(view, Action.HALF_POT, Action.POT, Action.ALL_IN, Action.CALL)
    return _first_legal(view, Action.ALL_IN, Action.POT, Action.HALF_POT, Action.CALL)


# --------------------------------------------------------------------------
# The personas themselves
# --------------------------------------------------------------------------


class Persona:
    """One sparring partner: a name, the values drawn for it, and how it acts.

    Subclasses implement `act`. `params` is the drawn parameter set and is what
    the report prints; `has_memory` says whether this persona's hands depend on
    each other, which decides whether the bootstrap may resample single hands.
    """

    #: What this persona is a caricature of, printed beside it in the report.
    mistake = ""
    #: True when a hand's play depends on an earlier hand (only `tilter` today).
    has_memory = False
    #: True for the four calibration agents of group A.
    calibration = False

    def __init__(self, name: str, params: dict[str, float], rng: random.Random, rollouts: int = 24):
        self.name = name
        self.params = dict(params)
        self.rng = rng
        self.rollouts = rollouts

    def __call__(self, hand: Hand, seat: int) -> Action:
        return self.act(seat_view(hand, seat))

    def act(self, view: SeatView) -> Action:  # pragma: no cover - abstract
        raise NotImplementedError

    def hand_finished(self, net_bb: float) -> None:
        """Told what this seat won or lost, in big blinds, after each hand."""

    def new_session(self) -> None:
        """Forget anything carried between hands. Called at the start of a cell."""

    def equity(self, view: SeatView) -> float:
        return showdown_equity(view.hole, view.board, self.rollouts)

    def top_fraction(self, view: SeatView) -> float:
        return preflop_top_fraction(view.hole)

    def describe(self) -> str:
        if not self.params:
            return f"{self.name}: no parameters (fixed behaviour)"
        drawn = "  ".join(f"{k}={v:.3f}" for k, v in sorted(self.params.items()))
        return f"{self.name}: {drawn}"


# -- Group A: the four calibration agents ----------------------------------


class AlwaysFold(Persona):
    """Folds whenever folding is legal. Checks when it is free, because the
    engine offers no way to give up a hand nobody has bet into.

    The harness's one closed-form answer: this agent can never put in a chip
    beyond the blinds it is forced to post, so what it loses per hand is exactly
    its share of the blinds. `tests/test_scoreboard.py` works the figure out.
    """

    mistake = "gives up every hand"
    calibration = True

    def act(self, view: SeatView) -> Action:
        return _give_up(view)


class AlwaysCall(Persona):
    """Calls everything and never raises. Checks the bot values hands at all."""

    mistake = "never folds, never raises"
    calibration = True

    def act(self, view: SeatView) -> Action:
        return _passive(view)


class AlwaysRaise(Persona):
    """Raises at every opportunity. Checks the bot does not fold under pressure."""

    mistake = "raises everything"
    calibration = True

    def act(self, view: SeatView) -> Action:
        return _aggress(view, Action.POT)


class CallRaise5050(Persona):
    """Raises half the time and calls the rest, to shake out seed handling."""

    mistake = "a coin flip between calling and raising"
    calibration = True

    def act(self, view: SeatView) -> Action:
        if self.rng.random() < 0.5:
            return _aggress(view, Action.POT)
        return _passive(view)


class UniformRandom(Persona):
    """Draws uniformly from whatever the engine allows.

    Not one of section 3.2's set. It is here as the neutral comparison arm the
    decision rule needs when nothing better is named, and it is the one agent in
    this file that T2's `baselines.py` is also likely to contain.
    """

    mistake = "no strategy at all"
    calibration = True

    def act(self, view: SeatView) -> Action:
        return view.legal[self.rng.randrange(len(view.legal))]


# -- Group B: the nine behavioural personas --------------------------------


class CallingStation(Persona):
    """Calls too much and never folds a hand with anything in it."""

    mistake = "calls too much, never folds a pair"

    def act(self, view: SeatView) -> Action:
        equity = self.equity(view)
        if equity >= self.params["raise_equity"]:
            return _aggress(view, Action.POT)
        if not view.facing_bet:
            return _passive(view)
        if equity >= self.params["stick_equity"]:
            return _passive(view)
        return _give_up(view)


class Nit(Persona):
    """Waits for the top of the range and folds everything else."""

    mistake = "folds far too often, waits for premium hands"

    def act(self, view: SeatView) -> Action:
        if view.street == 0:
            if self.top_fraction(view) <= self.params["tight_fraction"]:
                return _aggress(view, Action.POT)
            return _give_up(view)
        equity = self.equity(view)
        if equity >= self.params["value_equity"]:
            return _aggress(view, Action.POT)
        if view.facing_bet:
            return _give_up(view)
        return _passive(view)


class Maniac(Persona):
    """Bets and raises regardless of what it holds."""

    mistake = "raises regardless of holding"

    def act(self, view: SeatView) -> Action:
        if self.rng.random() < self.params["raise_p"]:
            return _aggress(view, Action.POT)
        return _passive(view)


class NeverBluffs(Persona):
    """Only ever puts money in with a real hand, so its bets are readable."""

    mistake = "bets only with real hands"

    def act(self, view: SeatView) -> Action:
        # Before the flop there is no board to run out, so "how good is this
        # hand" is where it sits in the ranking: the top 2% of hands reads as
        # 0.98, the bottom 2% as 0.02.
        equity = self.equity(view) if view.street else 1.0 - self.top_fraction(view)
        if equity >= self.params["value_threshold"]:
            return _aggress(view, Action.POT)
        if view.facing_bet and equity < self.params["fold_equity"]:
            return _give_up(view)
        return _passive(view)


class FitOrFold(Persona):
    """Gives up the moment the flop misses, whatever the pot is offering."""

    mistake = "folds whenever the flop misses, ignoring pot odds"

    def act(self, view: SeatView) -> Action:
        if view.street == 0:
            if self.top_fraction(view) <= self.params["play_fraction"]:
                return _passive(view)
            return _give_up(view)
        equity = self.equity(view)
        if view.facing_bet:
            # The mistake, spelt out: the pot odds are never consulted.
            return _passive(view) if equity >= self.params["fit_equity"] else _give_up(view)
        if equity >= self.params["bet_equity"]:
            return _aggress(view, Action.HALF_POT)
        return _passive(view)


class Tag(Persona):
    """Tight and aggressive: few hands, played hard. The competent one."""

    mistake = "none, by design: the competent tight-aggressive player"

    def act(self, view: SeatView) -> Action:
        if view.street == 0:
            if self.top_fraction(view) > self.params["tight_fraction"]:
                return _give_up(view)
            if self.rng.random() < self.params["aggression"]:
                return _aggress(view, Action.POT)
            return _passive(view)
        equity = self.equity(view)
        if equity >= self.params["value_equity"] and self.rng.random() < self.params["aggression"]:
            return _aggress(view, Action.POT)
        if view.facing_bet and equity < self.params["fold_equity"]:
            return _give_up(view)
        return _passive(view)


class Lag(Persona):
    """Competent but far too wide: the same aggression over many more hands."""

    mistake = "plays far too many hands aggressively"

    def act(self, view: SeatView) -> Action:
        if view.street == 0:
            if self.top_fraction(view) > self.params["wide_fraction"]:
                return _give_up(view)
            if self.rng.random() < self.params["aggression"]:
                return _aggress(view, Action.POT)
            return _passive(view)
        equity = self.equity(view)
        if equity >= self.params["value_equity"] or self.rng.random() < self.params["bluff_p"]:
            return _aggress(view, Action.HALF_POT)
        if view.facing_bet and equity < self.params["fold_equity"]:
            return _give_up(view)
        return _passive(view)


class Tilter(Persona):
    """Plays well until it loses a big pot, then plays like a maniac for a while.

    Two states and a counter, exactly section 3.2's rule. This is the one
    persona whose hands are not independent of one another, which is why the
    scoreboard resamples blocks of consecutive hands rather than single hands
    when it computes an interval against it.
    """

    mistake = "plays worse after losing a big pot"
    has_memory = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._tilt_hands_left = 0

    def new_session(self) -> None:
        self._tilt_hands_left = 0

    @property
    def tilted(self) -> bool:
        return self._tilt_hands_left > 0

    def hand_finished(self, net_bb: float) -> None:
        if net_bb <= -self.params["tilt_trigger_bb"]:
            self._tilt_hands_left = int(self.params["tilt_duration"])
        elif self._tilt_hands_left:
            self._tilt_hands_left -= 1

    def act(self, view: SeatView) -> Action:
        if self.tilted:
            if self.rng.random() < self.params["tilt_raise_p"]:
                return _aggress(view, Action.POT)
            return _passive(view)
        if view.street == 0:
            if self.top_fraction(view) > self.params["tight_fraction"]:
                return _give_up(view)
            return _aggress(view, Action.POT)
        equity = self.equity(view)
        if equity >= self.params["value_equity"]:
            return _aggress(view, Action.POT)
        if view.facing_bet and equity < self.params["fold_equity"]:
            return _give_up(view)
        return _passive(view)


class SizingTell(Persona):
    """Its bet size says what it has: big with strong, small with weak.

    The leak `EVALUATION_STRATEGY.md` section 4.3 names -- the bet size carries
    the information, so an opponent who watches sizes gets to see the cards.
    """

    mistake = "bet size leaks hand strength"

    def act(self, view: SeatView) -> Action:
        if view.street == 0:
            if self.top_fraction(view) > self.params["play_fraction"]:
                return _give_up(view)
            strong = self.top_fraction(view) <= self.params["strong_fraction"]
            return _aggress(view, Action.POT if strong else Action.HALF_POT)
        equity = self.equity(view)
        if equity >= self.params["strong_equity"]:
            return _aggress(view, Action.POT)
        if equity >= self.params["weak_equity"]:
            return _aggress(view, Action.HALF_POT)
        if view.facing_bet and equity < self.params["fold_equity"]:
            return _give_up(view)
        return _passive(view)


# --------------------------------------------------------------------------
# Drawing a session's parameters
# --------------------------------------------------------------------------


def _uniform(low: float, high: float):
    return ("uniform", low, high)


def _integer(low: int, high: int):
    return ("integer", low, high)


#: Where each persona's parameters come from. Section 3.2: **every capitalised
#: parameter in that table is a design choice, not a measured or cited value**,
#: and the same is true of every range here. What is grounded is the shape of
#: the set -- one persona per named human mistake, spread across the
#: tight/loose by passive/aggressive square -- not any single number.
#:
#: The ranges are deliberately wide. A narrow range is a fixed point wearing a
#: disguise, and section 3.2's whole reason for drawing rather than fixing is
#: that a bot tuned against one point looks better than it is.
DISTRIBUTIONS: dict[str, dict[str, tuple]] = {
    "always_fold": {},
    "always_call": {},
    "always_raise": {},
    "call_raise_50_50": {},
    "uniform_random": {},
    "calling_station": {
        "stick_equity": _uniform(0.18, 0.34),
        "raise_equity": _uniform(0.78, 0.92),
    },
    "nit": {
        "tight_fraction": _uniform(0.06, 0.16),
        "value_equity": _uniform(0.72, 0.88),
    },
    "maniac": {
        "raise_p": _uniform(0.55, 0.90),
    },
    "never_bluffs": {
        "value_threshold": _uniform(0.62, 0.80),
        "fold_equity": _uniform(0.25, 0.42),
    },
    "fit_or_fold": {
        "play_fraction": _uniform(0.25, 0.45),
        "fit_equity": _uniform(0.45, 0.62),
        "bet_equity": _uniform(0.55, 0.72),
    },
    "tag": {
        "tight_fraction": _uniform(0.14, 0.26),
        "aggression": _uniform(0.60, 0.88),
        "value_equity": _uniform(0.55, 0.72),
        "fold_equity": _uniform(0.30, 0.46),
    },
    "lag": {
        "wide_fraction": _uniform(0.34, 0.58),
        "aggression": _uniform(0.66, 0.92),
        "value_equity": _uniform(0.50, 0.66),
        "bluff_p": _uniform(0.10, 0.30),
        "fold_equity": _uniform(0.22, 0.38),
    },
    "tilter": {
        "tight_fraction": _uniform(0.14, 0.26),
        "value_equity": _uniform(0.55, 0.72),
        "fold_equity": _uniform(0.30, 0.46),
        "tilt_trigger_bb": _uniform(15.0, 45.0),
        "tilt_duration": _integer(5, 25),
        "tilt_raise_p": _uniform(0.60, 0.92),
    },
    "sizing_tell": {
        "play_fraction": _uniform(0.30, 0.55),
        "strong_fraction": _uniform(0.06, 0.14),
        "strong_equity": _uniform(0.62, 0.80),
        "weak_equity": _uniform(0.34, 0.50),
        "fold_equity": _uniform(0.20, 0.34),
    },
}

_CLASSES: dict[str, type[Persona]] = {
    "always_fold": AlwaysFold,
    "always_call": AlwaysCall,
    "always_raise": AlwaysRaise,
    "call_raise_50_50": CallRaise5050,
    "uniform_random": UniformRandom,
    "calling_station": CallingStation,
    "nit": Nit,
    "maniac": Maniac,
    "never_bluffs": NeverBluffs,
    "fit_or_fold": FitOrFold,
    "tag": Tag,
    "lag": Lag,
    "tilter": Tilter,
    "sizing_tell": SizingTell,
}

#: Section 3.2 group A, in the order that table lists them.
CALIBRATION_AGENTS = ("always_fold", "always_call", "always_raise", "call_raise_50_50")
#: Section 3.2 group B, in the order that table lists them.
BEHAVIOURAL_PERSONAS = (
    "calling_station",
    "nit",
    "maniac",
    "never_bluffs",
    "fit_or_fold",
    "tag",
    "lag",
    "tilter",
    "sizing_tell",
)
ALL_PERSONAS = CALIBRATION_AGENTS + BEHAVIOURAL_PERSONAS


def draw_parameters(name: str, rng: random.Random) -> dict[str, float]:
    """Draw one persona's parameters for this session from `DISTRIBUTIONS`."""
    if name not in DISTRIBUTIONS:
        raise KeyError(f"no persona called {name!r}; have {sorted(DISTRIBUTIONS)}")
    drawn: dict[str, float] = {}
    for parameter, spec in sorted(DISTRIBUTIONS[name].items()):
        kind, low, high = spec
        if kind == "uniform":
            drawn[parameter] = rng.uniform(low, high)
        elif kind == "integer":
            drawn[parameter] = float(rng.randint(int(low), int(high)))
        else:  # pragma: no cover - the table only has these two kinds
            raise ValueError(f"unknown distribution {kind!r}")
    return drawn


def build_persona(
    name: str, session_seed: int, rollouts: int = 24, stream: object = 0
) -> Persona:
    """One persona with this session's parameters drawn and recorded on it.

    The same session seed draws the same parameters, so the two arms of a paired
    comparison face opponents built identically -- which is the point of pairing.

    `stream` separates the coin flips of two copies of the same persona sitting
    at one table: same drawn parameters, different flips, so five copies of
    `maniac` do not raise in lockstep.
    """
    if name not in _CLASSES:
        raise KeyError(f"no persona called {name!r}; have {sorted(_CLASSES)}")
    # One stream for the draw and a separate one for the persona's own coin
    # flips at the table, so a persona that flips more coins one night does not
    # shift another persona's drawn parameters.
    draw_rng = random.Random(stable_seed(session_seed, name, "draw"))
    play_rng = random.Random(stable_seed(session_seed, name, "play", stream))
    params = draw_parameters(name, draw_rng)
    return _CLASSES[name](name=name, params=params, rng=play_rng, rollouts=rollouts)


def draw_session(
    names: Iterable[str] = ALL_PERSONAS, session_seed: int = 0, rollouts: int = 24
) -> dict[str, Persona]:
    """Every named persona, with its parameters drawn for this session."""
    return {name: build_persona(name, session_seed, rollouts=rollouts) for name in names}


def parameter_log(personas: Iterable[Persona]) -> list[str]:
    """The drawn values, one line each, as the report prints them."""
    return [persona.describe() for persona in personas]


# --------------------------------------------------------------------------
# Deliberately breaking a bot, for the test that the rule rejects one
# --------------------------------------------------------------------------


def handicapped(agent: Agent, fold_probability: float, seed: int = 0) -> Agent:
    """The same agent, except that it throws a hand away now and then.

    Used by `tests/test_scoreboard.py` for the one thing BUILD_PLAN.md's T3
    insists the rule can do: reject a bot that has been made worse on purpose.
    """
    rng = random.Random(seed)

    def play(hand: Hand, seat: int) -> Action:
        if rng.random() < fold_probability:
            view = seat_view(hand, seat)
            return _give_up(view)
        return agent(hand, seat)

    return play
