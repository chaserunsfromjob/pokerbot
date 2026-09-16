"""Smoothed response distributions; a simple model, not a Bayesian poker solver."""
from copy import deepcopy
import math

from .engine import Decision
from .policies import menu
from .response_profiles import context_key


def probabilities(street, facing_bet, raise_available, profile=None):
    key = context_key(street, facing_bet, raise_available)
    profile = profile or {}
    oracle = profile.get("response_oracle")
    if oracle is not None:
        if oracle not in ("caller", "tight", "aggressive"):
            raise ValueError("No exact response oracle for this policy")
        fold = .72 if oracle == "tight" and facing_bet else 0.
        raise_prob = .55 if oracle == "aggressive" and raise_available else 0.
        return (fold, 1 - fold - raise_prob, raise_prob)
    # Explicit starting assumptions, not empirical population frequencies.
    fold = .35 if facing_bet else 0.
    raise_prob = .20 if raise_available else 0.
    prior = (fold, 1 - fold - raise_prob, raise_prob)
    cells = profile.get("responses", {})
    direct = [0, 0, 0]
    other = [0, 0, 0]
    for cell, raw in cells.items():
        parts = cell.split(":")
        if len(parts) != 3 or parts[0] not in ("0", "1", "2", "3") or any(p not in ("0", "1") for p in parts[1:]):
            raise ValueError("Invalid response context")
        if len(raw) != 3 or any(type(x) is not int or x < 0 for x in raw):
            raise ValueError("Response counts must be nonnegative integers")
        if (parts[1] == "0" and raw[0]) or (parts[2] == "0" and raw[2]):
            raise ValueError("Counts contain an unavailable action")
        if parts[1:] == key.split(":")[1:]:
            target = direct if cell == key else other
            for i, count in enumerate(raw):
                target[i] += count
    # Borrow other streets' evidence in the same legal context; exclude the
    # direct cell from that evidence to avoid counting its observations twice.
    backoff = [(c + 12 * p) / (sum(other) + 12) for c, p in zip(other, prior)]
    result = tuple((c + 8 * p) / (sum(direct) + 8) for c, p in zip(direct, backoff))
    if not all(math.isfinite(p) and p >= 0 for p in result):
        raise ValueError("Invalid response probabilities")
    return result


class NamedResponse:
    """Immutable snapshot shared by counterfactual branches, with no learning."""
    def __init__(self, profiles):
        self.profiles = deepcopy(profiles)

    def decide(self, obs, profiles, rng):
        player = obs.players[obs.actor].name
        probs = probabilities(obs.street, bool(obs.legal.call_cost),
                              obs.legal.min_raise_to is not None, self.profiles.get(player))
        draw = rng.random()
        if draw < probs[0]:
            action = 0
        elif draw < probs[0] + probs[2]:
            action = rng.choice([a for a in menu(obs) if a >= 2])
        else:
            action = 1
        if not obs.legal.contains(action):
            raise ValueError("Response model selected an illegal action")
        return Decision(action, {"response_probabilities": probs})
