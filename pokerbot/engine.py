"""Host-only OpenSpiel adapter. Never give a policy a Hand or pyspiel.State."""
from dataclasses import asdict, dataclass
from functools import lru_cache
import random

import pyspiel

RANKS = "23456789TJQKA"
SUITS = "cdhs"


def card_id(card: str) -> int:
    if len(card) != 2:
        raise ValueError(f"Invalid card: {card}")
    return 4 * RANKS.index(card[0]) + SUITS.index(card[1])


def cards(text: str) -> tuple[str, ...]:
    return tuple(text[i:i + 2] for i in range(0, len(text), 2))


@lru_cache(maxsize=32)
def game_for(stacks: tuple[int, ...]):
    n = len(stacks)
    if not 2 <= n <= 9 or any(type(s) is not int or s < 100 for s in stacks):
        raise ValueError("Require 2–9 integer stacks, each at least one big blind")
    return pyspiel.load_game("universal_poker", {
        "betting": "nolimit", "numPlayers": n, "numRounds": 4,
        "blind": " ".join(map(str, [50, 100] + [0] * (n - 2))),
        "firstPlayer": "1 2 2 2" if n == 2 else "3 1 1 1",
        "numSuits": 4, "numRanks": 13, "numHoleCards": 2,
        "numBoardCards": "0 3 1 1", "stack": " ".join(map(str, stacks)),
        "bettingAbstraction": "fullgame",
    })


@dataclass(frozen=True)
class Player:
    name: str
    seat: int
    starting_stack: int
    contribution: int
    folded: bool

    @property
    def all_in(self):
        return not self.folded and self.contribution == self.starting_stack


@dataclass(frozen=True)
class LegalActions:
    fold: bool
    check_call: bool
    call_cost: int
    min_raise_to: int | None
    max_raise_to: int | None

    def contains(self, action: int) -> bool:
        if type(action) is not int:
            return False
        if action == 0:
            return self.fold
        if action == 1:
            return self.check_call
        return self.min_raise_to is not None and self.min_raise_to <= action <= self.max_raise_to


@dataclass(frozen=True)
class Event:
    name: str
    street: int
    kind: str
    amount: int  # Incremental chips.
    facing_bet: bool


@dataclass(frozen=True)
class Observation:
    actor: int
    hole_cards: tuple[str, ...]
    board: tuple[str, ...]
    street: int
    button: int
    players: tuple[Player, ...]
    pot: int
    legal: LegalActions
    history: tuple[Event, ...]

    @property
    def opponents(self):
        return tuple(p for p in self.players if p.seat != self.actor and not p.folded)


@dataclass(frozen=True)
class Decision:
    action: int  # 0 fold, 1 check/call, >=2 total HAND raise-to.
    diagnostics: dict


class Hand:
    def __init__(self, names, stacks=None, deck=None, seed=0):
        if len(set(names)) != len(names):
            raise ValueError("Names must be unique")
        self.names = tuple(names)
        self.stacks = tuple(stacks or [10000] * len(names))
        if len(self.stacks) != len(names):
            raise ValueError("Stack/name length mismatch")
        self.game = game_for(self.stacks)
        self.state = self.game.new_initial_state()
        self.deck = list(range(52)) if deck is None else list(deck)
        if len(self.deck) != 52 or set(self.deck) != set(range(52)):
            raise ValueError("Deck must be a permutation of all 52 cards")
        if deck is None:
            random.Random(seed).shuffle(self.deck)
        self.deck_index = 0
        self.folded = set()
        self.events = []
        self.decisions = []
        self.advance()

    def advance(self):
        while self.state.is_chance_node():
            self.state.apply_action(self.deck[self.deck_index])
            self.deck_index += 1

    @property
    def terminal(self):
        return self.state.is_terminal()

    def observation(self):
        if self.terminal:
            raise ValueError("Terminal hands have no decision observation")
        # This dictionary includes ALL hole cards; sanitize before the boundary.
        raw = self.state.to_dict()
        actor = self.state.current_player()
        contributions = tuple(raw["player_contributions"])
        legal = self.state.legal_actions()
        raises = [a for a in legal if a >= 2]
        call = min(max(contributions) - contributions[actor],
                   self.stacks[actor] - contributions[actor])
        board = cards(raw["board_cards"])
        return Observation(
            actor, cards(raw["player_hands"][actor]), board,
            {0: 0, 3: 1, 4: 2, 5: 3}[len(board)],
            0 if len(self.names) == 2 else len(self.names) - 1,
            tuple(Player(name, i, self.stacks[i], c, i in self.folded)
                  for i, (name, c) in enumerate(zip(self.names, contributions))),
            sum(contributions),  # state.pot_size() instead means a raise target!
            LegalActions(0 in legal, 1 in legal, call,
                         min(raises) if raises else None,
                         max(raises) if raises else None), tuple(self.events))

    def apply(self, decision: Decision):
        obs = self.observation()
        if not obs.legal.contains(decision.action) or decision.action not in self.state.legal_actions():
            raise ValueError(f"Illegal action {decision.action}; {obs.legal}")
        before = obs.players[obs.actor].contribution
        self.state.apply_action(decision.action)
        after = self.state.to_dict()["player_contributions"][obs.actor]
        kind = ("fold" if decision.action == 0 else
                "raise" if decision.action >= 2 else
                "call" if obs.legal.call_cost else "check")
        if kind == "fold":
            self.folded.add(obs.actor)
        self.events.append(Event(self.names[obs.actor], obs.street, kind,
                                 after - before, bool(obs.legal.call_cost)))
        self.decisions.append(asdict(decision))
        self.advance()
        if self.terminal:
            values = self.state.returns()
            if abs(sum(values)) > 1e-7 or any(s + v < -1e-7 for s, v in zip(self.stacks, values)):
                raise AssertionError("Chip conservation or nonnegative-stack failure")

    def record(self):
        if not self.terminal:
            raise ValueError("Can only save completed hands")
        return {"names": self.names, "stacks": self.stacks, "deck": self.deck,
                "decisions": self.decisions, "events": [asdict(e) for e in self.events],
                "returns": self.state.returns()}


def replay(record):
    hand = Hand(record["names"], record["stacks"], record["deck"])
    for decision in record["decisions"]:
        hand.apply(Decision(**decision))
    if not hand.terminal or hand.state.returns() != record["returns"]:
        raise AssertionError("Replay did not reproduce recorded payouts")
    if [asdict(e) for e in hand.events] != record["events"]:
        raise AssertionError("Replay did not reproduce public events")
    return hand
