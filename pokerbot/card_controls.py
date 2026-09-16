"""Separately coded, card-aware test opponents; no strength claims.

These share the engine-backed equity evaluator but not the original policy's
decision thresholds. They are development controls, not held-out champions.
"""
from dataclasses import asdict, dataclass

from .engine import Decision
from .equity import estimate


@dataclass(frozen=True)
class Style:
    opening_equity: float
    call_margin: float
    value_margin: float
    bet_fraction: float
    bluff_probability: float


STYLES = {
    "card_tight": Style(.62, .04, .16, .65, .00),
    "card_loose": Style(.49, -.02, .12, .45, .00),
    "card_pressure": Style(.54, .00, .08, .90, .12),
}


class CardControl:
    def __init__(self, style, samples=64):
        if style not in STYLES or samples < 1:
            raise ValueError("Unknown card-aware style or invalid sample count")
        self.name = style
        self.style = STYLES[style]
        self.samples = samples

    def decide(self, obs, profiles, rng):
        style = self.style
        n = len(obs.opponents) + 1
        share = estimate(obs.hole_cards, obs.board, n, self.samples, rng)
        cap = obs.players[obs.actor].contribution + obs.legal.call_cost
        eligible = cap + sum(min(p.contribution, cap) for p in obs.players if p.seat != obs.actor)
        odds = obs.legal.call_cost / eligible if eligible else 0.0
        first = (obs.button + (3 if obs.street == 0 and len(obs.players) > 2 else 1)) % len(obs.players)
        if obs.street == 0 and len(obs.players) == 2:
            first = obs.button
        position = ((obs.actor - first) % len(obs.players)) / (len(obs.players) - 1)
        preflop_score = None
        raises = sum(e.kind == "raise" and e.street == obs.street for e in obs.history)
        continue_hand = share >= odds + style.call_margin
        raise_hand = share > max(odds, 1 / n) + style.value_margin
        if obs.street == 0:
            # Heads-up equity supplies a preflop ordering without inventing a
            # hand-ranking evaluator. Multiway pot odds still use all players.
            preflop_score = estimate(obs.hole_cards, (), 2, self.samples, rng)
            threshold = style.opening_equity - .04 * position + .035 * min(raises, 3)
            continue_hand = continue_hand and preflop_score >= threshold
            raise_hand = continue_hand and (raises == 0 or preflop_score >= threshold + .10)
        action = 1 if continue_hand or not obs.legal.call_cost else 0
        bluff = (obs.street > 0 and not obs.legal.call_cost and len(obs.opponents) <= 2
                 and not any(p.all_in for p in obs.opponents)
                 and rng.random() < style.bluff_probability)
        if obs.legal.min_raise_to is not None and (raise_hand or bluff):
            target = cap + max(100, round((obs.pot + obs.legal.call_cost) * style.bet_fraction))
            action = min(obs.legal.max_raise_to, max(obs.legal.min_raise_to, target))
        if not obs.legal.contains(action):
            raise ValueError("Card-aware control produced an illegal action")
        return Decision(action, {"control": self.name, "equity": share,
                                 "preflop_score": preflop_score, "pot_odds": odds,
                                 "position": position, "bluff": bluff,
                                 "samples": self.samples, "style": asdict(style)})
