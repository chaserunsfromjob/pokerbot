"""Turn-plus-river fixed-policy rollouts using only sampled unseen future cards."""
from dataclasses import asdict, dataclass
from statistics import mean, stdev

from .engine import Decision, Hand, card_id
from .policies import menu
from .river_search import RiverConfig, RiverPolicy, hypothetical_holdings, rollout


def reconstruct_turn(obs, holdings, unseen_deck):
    """Reconstruct a public turn state with an explicitly supplied hypothetical suffix."""
    if obs.street != 2 or len(obs.board) != 4:
        raise ValueError("Turn search requires four public board cards")
    if len(holdings) != len(obs.players) or tuple(holdings[obs.actor]) != obs.hole_cards:
        raise ValueError("Hypothetical holdings must preserve hero's cards")
    if any(len(hole) != 2 for hole in holdings):
        raise ValueError("Every hypothetical seat needs two cards")
    prefix = [card_id(c) for hole in holdings for c in hole] + [card_id(c) for c in obs.board]
    deck = prefix + list(unseen_deck)
    # Hand also rejects overlapping, missing and noninteger cards. No implicit
    # ordered suffix is allowed: it would bias the still-unknown river card.
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


def sample_world(obs, rng):
    holdings = hypothetical_holdings(obs, rng)
    known = {card_id(c) for hole in holdings for c in hole} | {card_id(c) for c in obs.board}
    unseen = [i for i in range(52) if i not in known]
    rng.shuffle(unseen)
    return reconstruct_turn(obs, holdings, unseen)


def evaluate_turn_actions(obs, actions, response, continuation, rng, samples):
    if type(samples) is not int or samples < 2:
        raise ValueError("At least two hypothetical worlds are required")
    actions = tuple(actions)
    if not actions or len(set(actions)) != len(actions) or any(not obs.legal.contains(a) for a in actions):
        raise ValueError("Root actions must be distinct legal moves")
    values = {action: [] for action in actions}
    for _ in range(samples):
        world = sample_world(obs, rng)
        response_seed = rng.getrandbits(64)
        for action in actions:
            values[action].append(rollout(world, action, obs.actor, response, continuation, response_seed) / 100)
    return values


@dataclass(frozen=True)
class TurnConfig(RiverConfig):
    """Same fixed budgets as river search; policy identity distinguishes behavior."""


class TurnPolicy(RiverPolicy):
    def __init__(self, config=None):
        super().__init__(config or TurnConfig())

    def decide(self, obs, profiles, rng):
        if obs.street != 2:
            return super().decide(obs, profiles, rng)
        original = self.baseline.decide(obs, {}, rng)
        if len(menu(obs)) == 1:
            return original
        actions = sorted(set(menu(obs) + [original.action]))
        cfg = self.config
        response = self.response
        if cfg.response_model == "named":
            from .responses import NamedResponse
            response = NamedResponse(profiles)
        values = evaluate_turn_actions(obs, actions, response, self.baseline, rng, cfg.worlds)
        estimates = {}
        selected, best_score = original.action, cfg.min_gain_bb
        for action in actions:
            gains = [a - b for a, b in zip(values[action], values[original.action])]
            se, gain = stdev(gains) / cfg.worlds ** .5, mean(gains)
            score = gain - cfg.se_penalty * se
            estimates[str(action)] = {"value_bb": mean(values[action]),
                                      "gain_over_baseline_bb": gain, "paired_se_bb": se}
            if score > best_score:
                selected, best_score = action, score
        return Decision(selected, {"turn_search": True, "baseline_action": original.action,
                                   "changed": selected != original.action, "config": asdict(cfg),
                                   "action_values": estimates, "worlds": cfg.worlds,
                                   "root_actions": len(actions),
                                   "hidden_card_model": "uniform joint holdings and shuffled unseen future deck; no action conditioning"})
