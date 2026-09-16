"""River policy evaluation in hypothetical worlds built from public inputs.

This is a fixed-continuation rollout estimator, not equilibrium search. Uniform
hidden holdings and a shared response model are deliberate initial limitations.
No live Hand, simulator deck, opponent private observation or host seed enters.
"""
from copy import deepcopy
from dataclasses import asdict, dataclass
import random
from statistics import mean, stdev

from .baseline_v1 import FrozenEquityV1
from .engine import Decision, Hand, RANKS, SUITS, card_id
from .policies import Control, menu


def reconstruct(obs, holdings):
    """Replay public history with caller-supplied *hypothetical* hole cards."""
    if obs.street != 3 or len(obs.board) != 5:
        raise ValueError("River search requires a complete public board")
    if len(holdings) != len(obs.players) or tuple(holdings[obs.actor]) != obs.hole_cards:
        raise ValueError("Hypothetical holdings must preserve hero's cards")
    if any(len(hole) != 2 for hole in holdings):
        raise ValueError("Every hypothetical seat needs two cards")
    prefix = [card_id(c) for hole in holdings for c in hole] + [card_id(c) for c in obs.board]
    if len(set(prefix)) != len(prefix):
        raise ValueError("Hypothetical cards overlap")
    deck = prefix + [i for i in range(52) if i not in prefix]
    hand = Hand([p.name for p in obs.players], [p.starting_stack for p in obs.players], deck=deck)
    for event in obs.history:
        if hand.terminal:
            raise ValueError("Public history continues after settlement")
        current = hand.observation()
        if current.players[current.actor].name != event.name or current.street != event.street:
            raise ValueError("Public action order cannot be reconstructed")
        action = (0 if event.kind == "fold" else
                  current.players[current.actor].contribution + event.amount if event.kind == "raise" else 1)
        hand.apply(Decision(action, {}))
        if hand.events[-1] != event:
            raise ValueError("Public action amounts cannot be reconstructed")
    if hand.terminal or hand.observation() != obs:
        raise ValueError("Reconstructed state disagrees with the public observation")
    return hand


def hypothetical_holdings(obs, rng):
    known = obs.hole_cards + obs.board
    if len(set(known)) != len(known):
        raise ValueError("Duplicate visible card")
    available = [r + s for r in RANKS for s in SUITS if r + s not in known]
    drawn = iter(rng.sample(available, 2 * (len(obs.players) - 1)))
    return tuple(obs.hole_cards if p.seat == obs.actor else (next(drawn), next(drawn))
                 for p in obs.players)


def rollout(world, action, hero, response, continuation, seed):
    """Settle a root action with stateless, public-observation continuations."""
    hand = deepcopy(world)
    sunk = hand.observation().players[hero].contribution
    hand.apply(Decision(action, {}))
    rng = random.Random(seed)
    for _ in range(1000):
        if hand.terminal:
            # Value is in chips relative to hero's current remaining stack;
            # earlier committed chips are sunk and common to all root actions.
            return hand.returns()[hero] + sunk
        obs = hand.observation()
        policy = continuation if obs.actor == hero else response
        result = policy.decide(obs, {}, rng)
        hand.apply(result)
    raise RuntimeError("River continuation exceeded its decision bound")


def evaluate_actions(obs, actions, response, continuation, rng, samples):
    if type(samples) is not int or samples < 2:
        raise ValueError("At least two hypothetical worlds are required")
    actions = tuple(actions)
    if not actions or len(set(actions)) != len(actions) or any(not obs.legal.contains(a) for a in actions):
        raise ValueError("Root actions must be distinct legal moves")
    values = {a: [] for a in actions}
    for _ in range(samples):
        world = reconstruct(obs, hypothetical_holdings(obs, rng))
        response_seed = rng.getrandbits(64)
        for action in actions:
            value = rollout(world, action, obs.actor, response, continuation, response_seed)
            values[action].append(value / 100)
    return values


@dataclass(frozen=True)
class RiverConfig:
    worlds: int = 16
    response_model: str = "equity"
    se_penalty: float = 1.96
    min_gain_bb: float = .25

    def __post_init__(self):
        if type(self.worlds) is not int or self.worlds < 2:
            raise ValueError("Need at least two rollout worlds")
        if self.response_model not in ("equity", "caller", "named"):
            raise ValueError("Unknown river response model")
        if not 0 <= self.se_penalty <= 10 or not 0 <= self.min_gain_bb <= 100:
            raise ValueError("Invalid action-selection regularization")


class RiverPolicy:
    def __init__(self, config=None):
        self.config = config or RiverConfig()
        self.baseline = FrozenEquityV1()
        self.response = FrozenEquityV1() if self.config.response_model == "equity" else Control("caller")

    def decide(self, obs, profiles, rng):
        original = self.baseline.decide(obs, {}, rng)
        if obs.street != 3 or len(menu(obs)) == 1:
            return original
        # Include the actual baseline action even when it differs from rounded
        # menu amounts. Never silently compare against a surrogate baseline.
        actions = sorted(set(menu(obs) + [original.action]))
        cfg = self.config
        response = self.response
        if cfg.response_model == "named":
            from .responses import NamedResponse
            response = NamedResponse(profiles)
        values = evaluate_actions(obs, actions, response, self.baseline, rng, cfg.worlds)
        estimates = {}
        selected, best_score = original.action, cfg.min_gain_bb
        for action in actions:
            gains = [a - b for a, b in zip(values[action], values[original.action])]
            se = stdev(gains) / cfg.worlds ** .5
            gain = mean(gains)
            # A noise penalty, not a simultaneous CI or proof that a move wins.
            score = gain - cfg.se_penalty * se
            estimates[str(action)] = {"value_bb": mean(values[action]),
                                      "gain_over_baseline_bb": gain, "paired_se_bb": se}
            if score > best_score:
                selected, best_score = action, score
        return Decision(selected, {"river_search": True, "baseline_action": original.action,
                                   "changed": selected != original.action, "config": asdict(cfg),
                                   "action_values": estimates,
                                   "worlds": cfg.worlds, "root_actions": len(actions),
                                   "hidden_card_model": "uniform; no action conditioning"})
