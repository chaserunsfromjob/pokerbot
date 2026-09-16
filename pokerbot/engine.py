"""Host-only rules adapters. Never give a policy a Hand or native engine state.

PokerKit handles live simulation; OpenSpiel remains for frozen equity sampling
and replaying historical records made before the rules defect was identified.
"""
from dataclasses import asdict, dataclass
from functools import lru_cache
import random

import pyspiel
from pokerkit import Automation, NoLimitTexasHoldem
from .pokerkit_rules import ENGINE_ID, ReopeningNoLimitTexasHoldem

RANKS = "23456789TJQKA"
SUITS = "cdhs"


def fractional_split(amount, count):
    """Preserve the benchmark's OpenSpiel fractional-pot convention.

    Bet amounts remain integer chip units; tied payouts may be fractional.
    Integer odd-chip allocation is a separate class-app rules profile.
    """
    return amount / count, 0


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


class OpenSpielHand:
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

    def returns(self):
        return self.state.returns()

    def is_legal(self, action):
        return type(action) is int and action in self.state.legal_actions()

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
        return {"engine": "openspiel-2.0.2", "names": self.names, "stacks": self.stacks, "deck": self.deck,
                "decisions": self.decisions, "events": [asdict(e) for e in self.events],
                "returns": self.state.returns()}


class LegacyPokerKitHand:
    """PokerKit rules with the original whole-hand raise-to policy contract.

    Host seat 0 posts SB, seat 1 BB; seat 0 is the button heads-up. PokerKit
    reverses those two seats heads-up, so the adapter maps seats explicitly.
    Hole/board cards follow the saved shuffled deck. Unknown burn placeholders
    preserve the original marginal deal distribution without leaking a card.
    """
    game_class = NoLimitTexasHoldem
    engine_id = "pokerkit-0.7.5"

    def __init__(self, names, stacks=None, deck=None, seed=0):
        n = len(names)
        self.names = tuple(names)
        self.stacks = tuple([10000] * n if stacks is None else stacks)
        if not 2 <= n <= 9 or len(set(names)) != n or len(self.stacks) != n:
            raise ValueError("Require 2–9 unique names and matching stacks")
        if any(type(s) is not int or s < 100 for s in self.stacks):
            raise ValueError("Stacks must be integer amounts of at least one big blind")
        self.deck = list(range(52)) if deck is None else list(deck)
        if len(self.deck) != 52 or any(type(c) is not int for c in self.deck) or set(self.deck) != set(range(52)):
            raise ValueError("Deck must be a permutation of all 52 cards")
        if deck is None:
            random.Random(seed).shuffle(self.deck)
        self._seat_map = (1, 0) if n == 2 else tuple(range(n))
        self._holes = [tuple(self._card(c) for c in self.deck[2*i:2*i+2]) for i in range(n)]
        self._board = []
        self.deck_index = 2 * n
        self.folded = set()
        self.events = []
        self.decisions = []
        automations = (Automation.ANTE_POSTING, Automation.BET_COLLECTION,
                       Automation.BLIND_OR_STRADDLE_POSTING,
                       Automation.HOLE_CARDS_SHOWING_OR_MUCKING, Automation.HAND_KILLING,
                       Automation.CHIPS_PUSHING, Automation.CHIPS_PULLING)
        self.state = self.game_class.create_state(
            automations, True, 0, (50, 100), 100,
            tuple(self.stacks[i] for i in self._seat_map), n, divmod=fractional_split)
        for host_seat in self._seat_map:
            self.state.deal_hole("".join(self._holes[host_seat]))
        self.advance()

    @staticmethod
    def _card(index):
        return RANKS[index // 4] + SUITS[index % 4]

    def _host_order(self, values):
        return [values[i] for i in self._seat_map]  # Mapping is its own inverse.

    @property
    def terminal(self):
        return not self.state.status

    def returns(self):
        if not self.terminal:
            raise ValueError("Payouts are available only for completed hands")
        return self._host_order(self.state.payoffs)

    def advance(self):
        # Explicit card supply makes deals independent of PokerKit's internal RNG.
        for _ in range(12):
            if self.terminal or self.state.actor_index is not None:
                return
            if self.state.can_burn_card("??"):
                self.state.burn_card("??")
            elif self.state.can_deal_board():
                count = self.state.board_dealing_count
                board = [self._card(c) for c in self.deck[self.deck_index:self.deck_index + count]]
                self.state.deal_board("".join(board))
                self.deck_index += count
                self._board.extend(board)
            else:
                raise RuntimeError("PokerKit reached an unsupported automatic transition")
        raise RuntimeError("Automatic transitions exceeded the bounded runout")

    def observation(self):
        if self.terminal:
            raise ValueError("Terminal hands have no decision observation")
        actor = self.state.actor_index
        host_actor = self._seat_map[actor]
        contributions = self._host_order([-p for p in self.state.payoffs])
        prior_streets = contributions[host_actor] - self.state.bets[actor]
        minimum = self.state.min_completion_betting_or_raising_to_amount
        maximum = self.state.max_completion_betting_or_raising_to_amount
        call = self.state.checking_or_calling_amount
        return Observation(
            host_actor, self._holes[host_actor], tuple(self._board),
            {0: 0, 3: 1, 4: 2, 5: 3}[len(self._board)],
            0 if len(self.names) == 2 else len(self.names) - 1,
            tuple(Player(name, i, self.stacks[i], contributions[i], i in self.folded)
                  for i, name in enumerate(self.names)),
            self.state.total_pot_amount,
            LegalActions(bool(call) and self.state.can_fold(), self.state.can_check_or_call(),
                         call, None if minimum is None else minimum + prior_streets,
                         None if maximum is None else maximum + prior_streets), tuple(self.events))

    def is_legal(self, action):
        if type(action) is not int or self.terminal:
            return False
        if action == 0:
            return bool(self.state.checking_or_calling_amount) and self.state.can_fold()
        if action == 1:
            return self.state.can_check_or_call()
        actor = self.state.actor_index
        prior = -self.state.payoffs[actor] - self.state.bets[actor]
        return self.state.can_complete_bet_or_raise_to(action - prior)

    def apply(self, decision: Decision):
        obs = self.observation()
        if not obs.legal.contains(decision.action) or not self.is_legal(decision.action):
            raise ValueError(f"Illegal action {decision.action}; {obs.legal}")
        actor = self.state.actor_index
        before = self.state.bets[actor]
        prior = obs.players[obs.actor].contribution - before
        if decision.action == 0:
            self.state.fold()
            self.folded.add(obs.actor)
            kind, amount = "fold", 0
        elif decision.action == 1:
            operation = self.state.check_or_call()
            kind, amount = ("call" if obs.legal.call_cost else "check"), operation.amount
        else:
            operation = self.state.complete_bet_or_raise_to(decision.action - prior)
            kind, amount = "raise", operation.amount - before
        self.events.append(Event(self.names[obs.actor], obs.street, kind, amount, bool(obs.legal.call_cost)))
        self.decisions.append(asdict(decision))
        self.advance()
        if self.terminal:
            values = self.returns()
            if abs(sum(values)) > 1e-7 or any(s + v < -1e-7 for s, v in zip(self.stacks, values)):
                raise AssertionError("Chip conservation or nonnegative-stack failure")

    def record(self):
        if not self.terminal:
            raise ValueError("Can only save completed hands")
        return {"schema": 2, "engine": self.engine_id, "payout_rule": "fractional",
                "names": self.names,
                "stacks": self.stacks, "deck": self.deck, "decisions": self.decisions,
                "events": [asdict(e) for e in self.events], "returns": self.returns()}


class Hand(LegacyPokerKitHand):
    """Current NLHE referee with isolated, versioned reopening corrections."""
    game_class = ReopeningNoLimitTexasHoldem
    engine_id = ENGINE_ID


def replay(record):
    backend = record.get("engine", "openspiel-2.0.2")
    engines = {"openspiel-2.0.2": OpenSpielHand, "pokerkit-0.7.5": LegacyPokerKitHand,
               ENGINE_ID: Hand}
    if backend not in engines:
        raise ValueError(f"Unknown replay engine: {backend}")
    if backend.startswith("pokerkit-") and record.get("payout_rule") != "fractional":
        raise ValueError("Unsupported PokerKit payout rule")
    hand = engines[backend](record["names"], record["stacks"], record["deck"])
    for decision in record["decisions"]:
        hand.apply(Decision(**decision))
    if not hand.terminal or hand.returns() != record["returns"]:
        raise AssertionError("Replay did not reproduce recorded payouts")
    if [asdict(e) for e in hand.events] != record["events"]:
        raise AssertionError("Replay did not reproduce public events")
    return hand
