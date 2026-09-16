"""Frozen original strategy. New candidates belong in policies.py, not here.

Changing this policy or its equity sampler requires a newly named benchmark.
This version deliberately preserves the initial strategy's limitations.
"""
from dataclasses import asdict

from .engine import Decision
from .equity import estimate

PARAMETERS = {"samples": 32, "call_margin": .02, "raise_margin": .12,
              "bet_fraction": .5, "adaptive": False}


class FrozenEquityV1:
    def decide(self, obs, profiles, rng):
        n = len(obs.opponents) + 1
        eq = estimate(obs.hole_cards, obs.board, n, PARAMETERS["samples"], rng)
        hero = obs.players[obs.actor]
        cap = hero.contribution + obs.legal.call_cost
        eligible = cap + sum(min(p.contribution, cap) for p in obs.players if p.seat != obs.actor)
        odds = obs.legal.call_cost / eligible if eligible else 0.0
        action = 1 if eq >= odds + PARAMETERS["call_margin"] or not obs.legal.call_cost else 0
        if obs.legal.min_raise_to is not None and eq > max(odds, 1 / n) + PARAMETERS["raise_margin"]:
            target = cap + max(100, round((obs.pot + obs.legal.call_cost) * PARAMETERS["bet_fraction"]))
            action = max(obs.legal.min_raise_to, min(obs.legal.max_raise_to, target))
        if not obs.legal.contains(action):
            raise ValueError("Frozen policy produced an illegal action")
        return Decision(action, {"equity": eq, "pot_odds": odds, "active_players": n,
                                 "adaptation": 0.0, "config": dict(PARAMETERS)})
