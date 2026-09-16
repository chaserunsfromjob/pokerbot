"""Position/range ablations; experimental showdown heuristics, not a solver."""
from dataclasses import asdict, dataclass

from .engine import Decision
from .equity import estimate
from .policies import EquityConfig
from .ranges import earliness, preflop_score, range_equity


@dataclass(frozen=True)
class RangeConfig(EquityConfig):
    samples: int = 128
    use_position: bool = False
    use_ranges: bool = False
    conditioning: float = .5
    uniform_mix: float = .25

    def __post_init__(self):
        super().__post_init__()
        if self.adaptive:
            raise ValueError("Named-player adaptation is not implemented for this candidate")
        if not 0 <= self.conditioning <= 1 or not 0 <= self.uniform_mix <= 1:
            raise ValueError("Invalid range parameters")


class RangePolicy:
    def __init__(self, config=None):
        self.config = config or RangeConfig()

    def decide(self, obs, profiles, rng):
        cfg = self.config
        count = len(obs.opponents) + 1
        diagnostics = {}
        if cfg.use_ranges:
            equity, diagnostics = range_equity(obs, cfg.samples, rng,
                conditioning=cfg.conditioning, uniform_mix=cfg.uniform_mix)
        else:
            equity = estimate(obs.hole_cards, obs.board, count, cfg.samples, rng)
        cap = obs.players[obs.actor].contribution + obs.legal.call_cost
        eligible = cap + sum(min(p.contribution, cap) for p in obs.players if p.seat != obs.actor)
        odds = obs.legal.call_cost / eligible if eligible else 0.0
        continuing = equity >= odds + cfg.call_margin
        raising = equity > max(odds, 1 / count) + cfg.raise_margin
        if cfg.use_position and obs.street == 0:
            early = earliness(obs.actor, obs.button, len(obs.players))
            raises = sum(e.kind == "raise" and e.street == 0 for e in obs.history)
            score = preflop_score(obs.hole_cards)
            threshold = .54 + .06 * early + .035 * min(raises, 3)
            continuing = continuing and score >= threshold
            raising = continuing and (raises == 0 or score >= threshold + .08)
            diagnostics.update(preflop_score=score, preflop_threshold=threshold, earliness=early)
        action = 1 if continuing or not obs.legal.call_cost else 0
        if obs.legal.min_raise_to is not None and raising:
            target = cap + max(100, round((obs.pot + obs.legal.call_cost) * cfg.bet_fraction))
            action = max(obs.legal.min_raise_to, min(obs.legal.max_raise_to, target))
        if not obs.legal.contains(action):
            raise ValueError("Range policy produced an illegal action")
        return Decision(action, {**diagnostics, "equity": equity, "pot_odds": odds,
                                 "active_players": count, "config": asdict(cfg)})
