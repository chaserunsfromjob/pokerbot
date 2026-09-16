"""Experimental preflop-action ranges, using only sanitized public information.

Likelihoods are explicit, uncalibrated hypotheses, not learned opponent models.
Joint uniform deals enforce blockers without biased sequential range sampling.
Postflop actions and folded players' card-removal effects are not modeled yet.
"""
from functools import lru_cache
import hashlib
import math
import random

from .engine import RANKS, SUITS, card_id
from .equity import estimate, showdown_share


def canonical_hole(hole):
    if len(hole) != 2 or hole[0] == hole[1]:
        raise ValueError("Need two distinct hole cards")
    for card in hole:
        card_id(card)
    a, b = sorted(hole, key=lambda c: RANKS.index(c[0]), reverse=True)
    return (a[0] + "c", b[0] + ("c" if a[1] == b[1] else "d"))


@lru_cache(maxsize=169)
def _preflop_score(canonical):
    seed = int.from_bytes(hashlib.sha256(("preflop-order-v1" + "".join(canonical)).encode()).digest()[:8], "big")
    return estimate(canonical, (), 2, 512, random.Random(seed))


def preflop_score(hole):
    """Reproducible heads-up equity ordering; existing engine ranks all hands."""
    return _preflop_score(canonical_hole(hole))


def earliness(seat, button, seats):
    # Nonblind seats: UTG=1, button=0. Blinds act last preflop but play out
    # of position later, so do not give them button opening thresholds.
    if seats == 2:
        return 0.0 if seat == button else 1.0
    first = (button + 3) % seats
    index = (seat - first) % seats
    if index >= seats - 2:
        return .75
    return (seats - 3 - index) / max(1, seats - 3)


def action_contexts(obs):
    """Return observed preflop evidence for each still-active opponent."""
    contexts = {p.name: [] for p in obs.opponents}
    raises = 0
    for event in obs.history:
        if event.street != 0:
            continue
        if event.name in contexts:
            contexts[event.name].append((event.kind, raises))
        raises += event.kind == "raise"
    return contexts


def log_likelihood(score, early, contexts):
    """Smoothed action probabilities under a simple monotone strength model.

    No sizes, legal-menu reconstruction or opponent identity parameters yet.
    The likelihood floor keeps unusual actions possible for every holding.
    """
    result = 0.0
    for kind, raises in contexts:
        pressure = .04 * min(raises, 3)
        continuing = 1 / (1 + math.exp(-18 * (score - (.47 + .04 * early + pressure))))
        raising = 1 / (1 + math.exp(-18 * (score - (.60 + .04 * early + pressure))))
        if kind == "raise":
            probability = .10 / 3 + .90 * raising
        elif kind == "call":
            probability = .10 / 3 + .90 * (continuing - raising)
        elif kind == "check":
            probability = .05 + .90 * (1 - raising)
        elif kind == "fold":
            probability = .10 / 3 + .90 * (1 - continuing)
        else:
            raise ValueError(f"Unknown action kind: {kind}")
        result += math.log(probability)
    return result


def range_equity(obs, samples, rng, *, conditioning=.5, uniform_mix=.25):
    if samples < 1 or not 0 <= conditioning <= 1 or not 0 <= uniform_mix <= 1:
        raise ValueError("Invalid range-estimation configuration")
    if len(obs.hole_cards) != 2 or len(obs.board) not in (0, 3, 4, 5):
        raise ValueError("Invalid hole cards or board")
    known = obs.hole_cards + obs.board
    for card in known:
        card_id(card)
    if len(set(known)) != len(known) or not 1 <= len(obs.opponents) <= 8:
        raise ValueError("Duplicate known card or invalid opponent count")
    available = [r + s for r in RANKS for s in SUITS if r + s not in known]
    contexts = action_contexts(obs)
    early = [earliness(p.seat, obs.button, len(obs.players)) for p in obs.opponents]
    evidence = sum(len(c) for c in contexts.values())
    cache = {}
    values, log_weights = [], []
    count = 2 * len(obs.opponents)
    for _ in range(samples):
        drawn = rng.sample(available, count + 5 - len(obs.board))
        holdings = [drawn[i:i + 2] for i in range(0, count, 2)]
        log_weight = 0.0
        if conditioning and evidence:
            for p, hole, position in zip(obs.opponents, holdings, early):
                if not contexts[p.name]:
                    continue
                key = (p.name, canonical_hole(hole))
                if key not in cache:
                    cache[key] = log_likelihood(preflop_score(hole), position, contexts[p.name])
                log_weight += cache[key] * conditioning
        log_weights.append(log_weight)
        values.append(showdown_share([obs.hole_cards] + holdings, list(obs.board) + drawn[count:])[0])
    peak = max(log_weights)
    weights = [math.exp(w - peak) for w in log_weights]
    total = sum(weights)
    posterior = sum(w * v for w, v in zip(weights, values)) / total
    uniform = sum(values) / samples
    equity = (1 - uniform_mix) * posterior + uniform_mix * uniform
    return equity, {"uniform_equity": uniform, "conditioned_equity": posterior,
                    "effective_samples": total * total / sum(w * w for w in weights),
                    "preflop_evidence_actions": evidence,
                    "modeled_opponents": len(obs.opponents)}
