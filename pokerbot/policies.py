"""Original experimental policies. No claims of equilibrium or human strength."""
from dataclasses import asdict, dataclass

from .engine import Decision
from .equity import estimate


def menu(obs):
    actions = ([0] if obs.legal.fold else []) + ([1] if obs.legal.check_call else [])
    if obs.legal.min_raise_to is not None:
        paid = obs.players[obs.actor].contribution + obs.legal.call_cost
        for amount in (obs.legal.min_raise_to,
                       paid + max(100, (obs.pot + obs.legal.call_cost) // 2),
                       paid + obs.pot + obs.legal.call_cost, obs.legal.max_raise_to):
            actions.append(max(obs.legal.min_raise_to, min(obs.legal.max_raise_to, amount)))
    return sorted(set(actions))


class Control:
    """Card-independent test opponents; not assumptions about classmates."""
    def __init__(self, style):
        if style not in ("random", "caller", "tight", "aggressive"):
            raise ValueError(f"Unknown control {style}")
        self.style = style

    def decide(self, obs, profiles, rng):
        choices = menu(obs)
        raises = [a for a in choices if a >= 2]
        draw = rng.random()
        if self.style == "random":
            action = rng.choice(choices)
        elif self.style == "caller":
            action = 1
        elif self.style == "tight":
            action = 0 if obs.legal.call_cost and draw < .72 else 1
        else:
            action = rng.choice(raises) if raises and draw < .55 else 1
        if not obs.legal.contains(action):
            action = 1 if obs.legal.check_call else choices[0]
        return Decision(action, {"control": self.style})


@dataclass(frozen=True)
class EquityConfig:
    samples: int = 32
    call_margin: float = .02
    raise_margin: float = .12
    bet_fraction: float = .5
    adaptive: bool = False

    def __post_init__(self):
        if self.samples < 1 or not 0 <= self.call_margin <= 1 or not 0 <= self.raise_margin <= 1:
            raise ValueError("Invalid equity parameters")
        if not 0 < self.bet_fraction <= 4:
            raise ValueError("Invalid bet fraction")


class EquityPolicy:
    def __init__(self, config=EquityConfig()):
        self.config = config

    def decide(self, obs, profiles, rng):
        n = len(obs.opponents) + 1  # All-in opponents remain included.
        eq = estimate(obs.hole_cards, obs.board, n, self.config.samples, rng)
        hero = obs.players[obs.actor]
        cap = hero.contribution + obs.legal.call_cost
        # Exclude contributions above what a call can contest. This is still a
        # showdown heuristic, not a side-pot-specific future betting solver.
        eligible = cap + sum(min(p.contribution, cap) for p in obs.players if p.seat != obs.actor)
        odds = obs.legal.call_cost / eligible if eligible else 0.0
        action = 1 if eq >= odds + self.config.call_margin or not obs.legal.call_cost else 0
        adaptation = 0.0
        if self.config.adaptive:
            rates = [profiles[p.name]["fold_rate"] for p in obs.opponents
                     if p.name in profiles and not p.all_in]
            if rates:
                # Bounded exploratory value-threshold adjustment. Does not
                # claim a joint fold probability or a calibrated range model.
                adaptation = max(-.04, min(.04, (sum(rates) / len(rates) - .4) * .1))
        if obs.legal.min_raise_to is not None and eq > max(odds, 1 / n) + self.config.raise_margin - adaptation:
            target = cap + max(100, round((obs.pot + obs.legal.call_cost) * self.config.bet_fraction))
            action = max(obs.legal.min_raise_to, min(obs.legal.max_raise_to, target))
        if not obs.legal.contains(action):
            raise ValueError("Policy produced an illegal action")
        return Decision(action, {"equity": eq, "pot_odds": odds,
                                 "active_players": n, "adaptation": adaptation,
                                 "config": asdict(self.config)})


def make_policy(name, config=None):
    if name.startswith("card_"):
        from .card_controls import CardControl
        return CardControl(name)
    return EquityPolicy(config or EquityConfig()) if name == "equity" else Control(name)
