"""The league: paired deals, bootstrap intervals, and the decision rule.

What this module is for, in one sentence: to sit a bot down against each of the
personas at each table size, on exactly the same deals as the version it is
being compared with, and to say -- by a rule written down before the first hand
-- whether the new version is an improvement.

It implements `EVALUATION_STRATEGY.md` section 3.7's Tier 1 (the persona league
with intervals) and Tier 2 (paired deals and the pre-registered decision rule),
and section 3.5 is the rule it implements, in that document's own order:

1. **Pre-register.** Everything that decides an accept is in
   `league_config.toml` before a hand is played, and the report reprints it.
2. **Pair everything.** Both arms play identical deals, identical persona
   parameters and identical seat assignments. That is free, and it is what makes
   the two arms' results move together, which is what makes the difference
   between them measurable in far fewer hands.
3. **Do not look at the running total.** There is no early stopping here. The
   number of hands is fixed before the run and the run plays all of them.
4. **Test afterwards.** A percentile bootstrap interval on the paired per-hand
   difference, because per-hand poker results are too heavy-tailed for the
   ordinary textbook interval; a t-interval is printed beside it as a
   cross-check, and the two disagreeing means the data is wrong, not the test.
   A persona with memory -- `tilter` -- gets a block bootstrap, because
   resampling single hands would break the dependence between its hands and
   understate the variance.
5. **Accept only if** the interval for the weighted headline lies entirely above
   zero **and** no single persona's interval lies entirely below zero. Winning
   overall by beating one persona harder while losing to another is the
   signature of over-fitting to an opponent, and it blocks.

**What a bot is, here.** Any callable `bot(hand, seat) -> Action`: the adapter's
own view of a decision. Every persona is one, and so is anything else with that
signature -- T2's search bot plugs in by being registered under a name.
"""

from __future__ import annotations

import dataclasses
import math
import random
import statistics
import time
import tomllib
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

from .personas import (
    ALL_PERSONAS,
    Agent,
    Persona,
    build_persona,
    stable_seed,
)
from .table import Action, Hand, Table, TableConfig, deal_check

CONFIG_PATH = Path(__file__).with_name("league_config.toml")

#: Bots the scoreboard can be pointed at that are not personas. A factory takes
#: the session seed and returns an `Agent`. T2's search bot joins the league by
#: calling `register_bot("search", factory)`; nothing else has to change.
_BOT_FACTORIES: dict[str, Callable[[int], Agent]] = {}


def register_bot(name: str, factory: Callable[[int], Agent]) -> None:
    """Make a bot available to `--bot` and `--compare` under this name."""
    _BOT_FACTORIES[name] = factory


class HeldBackPersonaError(RuntimeError):
    """Tuning asked for a persona that is held back for accept/reject only.

    Section 3.2's second design rule, enforced rather than written down and
    hoped for: counter-strategies in the literature overfit badly to the
    opponent they were built against, so half the set never sees a tuning run.
    """


# --------------------------------------------------------------------------
# The pre-registered configuration
# --------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Config:
    """`league_config.toml`, read once and reprinted in the report."""

    path: Path
    raw: Mapping[str, object]

    @property
    def weights(self) -> Mapping[str, object]:
        return self.raw["weights"]

    @property
    def run(self) -> Mapping[str, object]:
        return self.raw["run"]

    @property
    def bootstrap(self) -> Mapping[str, object]:
        return self.raw["bootstrap"]

    @property
    def decision(self) -> Mapping[str, object]:
        return self.raw["decision"]

    @property
    def split(self) -> Mapping[str, object]:
        return self.raw["split"]

    @property
    def development(self) -> tuple[str, ...]:
        return tuple(self.split["development"])

    @property
    def held_back(self) -> tuple[str, ...]:
        """The evaluation half: accept/reject only, never tuning."""
        return tuple(self.split["evaluation"])

    @property
    def calibration(self) -> tuple[str, ...]:
        return tuple(self.split["calibration"])

    @property
    def overrides(self) -> tuple[Mapping[str, object], ...]:
        return tuple(self.decision.get("overrides", ()))


def load_config(path: Path | str = CONFIG_PATH) -> Config:
    path = Path(path)
    with path.open("rb") as handle:
        raw = tomllib.load(handle)
    missing = {"weights", "run", "bootstrap", "decision", "split"} - set(raw)
    if missing:
        raise ValueError(f"{path} is missing section(s) {sorted(missing)}")
    covered = set(raw["split"]["development"]) | set(raw["split"]["evaluation"])
    if covered != set(ALL_PERSONAS) - set(raw["split"]["calibration"]):
        raise ValueError(
            f"{path}'s split does not cover exactly the nine behavioural "
            f"personas: {sorted(covered)}"
        )
    return Config(path=path, raw=raw)


def table_size_weights(seats_present: Sequence[int], config: Config) -> dict[int, float]:
    """The section-3.5 band weights, spread over the seat counts that ran.

    Six seats take the primary weight; eight and nine share the secondary one;
    whatever else ran splits the last band equally between them. The three band
    weights never move. Only the split inside the last band does, and the report
    prints whichever split was in force.
    """
    weights_config = config.weights
    primary_seats = [n for n in seats_present if n in weights_config["primary_seats"]]
    secondary_seats = [n for n in seats_present if n in weights_config["secondary_seats"]]
    other_seats = [n for n in seats_present if n not in primary_seats + secondary_seats]
    weights: dict[int, float] = {}
    for band, seats in (
        ("primary", primary_seats),
        ("secondary", secondary_seats),
        ("other", other_seats),
    ):
        if seats:
            share = float(weights_config[band]) / len(seats)
            for n in seats:
                weights[n] = share
    total = sum(weights.values())
    if total <= 0:  # pragma: no cover - a run with no seat counts has no headline
        raise ValueError("no seat count ran, so there is no headline to weight")
    # A band with no seat counts in it -- a run that skipped heads-up, say --
    # would otherwise leave the weights summing to less than one and quietly
    # shrink the headline by that much. They are rescaled to sum to one instead,
    # and `missing_bands` tells the report to say so, because rescaling does
    # move the band weights relative to what the document prints.
    return {n: w / total for n, w in sorted(weights.items())}


def missing_bands(seats_present: Sequence[int], config: Config) -> list[str]:
    """Which of the three bands had no seat count in this run, if any."""
    weights_config = config.weights
    primary = [n for n in seats_present if n in weights_config["primary_seats"]]
    secondary = [n for n in seats_present if n in weights_config["secondary_seats"]]
    others = [
        n for n in seats_present
        if n not in weights_config["primary_seats"]
        and n not in weights_config["secondary_seats"]
    ]
    empty = []
    if not primary:
        empty.append("primary (6 seats)")
    if not secondary:
        empty.append("secondary (8 and 9)")
    if not others:
        empty.append("everything else")
    return empty


def tuning_opponents(config: Config, requested: Iterable[str] | None = None) -> list[str]:
    """The personas a tuning run may use, refusing any that are held back."""
    allowed = set(config.development) | set(config.calibration)
    names = list(requested) if requested is not None else sorted(allowed)
    refused = [n for n in names if n in set(config.held_back)]
    if refused:
        raise HeldBackPersonaError(
            f"{sorted(refused)} are held back for accept/reject only and cannot "
            f"be tuned against; the development half is {sorted(config.development)}"
        )
    unknown = [n for n in names if n not in allowed]
    if unknown:
        raise KeyError(f"no persona called {unknown}; have {sorted(allowed)}")
    return names


def acceptance_opponents(config: Config, requested: Iterable[str] | None = None) -> list[str]:
    """Every persona an accept/reject run may use: both halves and calibration."""
    allowed = set(config.development) | set(config.held_back) | set(config.calibration)
    names = list(requested) if requested is not None else list(ALL_PERSONAS)
    unknown = [n for n in names if n not in allowed]
    if unknown:
        raise KeyError(f"no persona called {unknown}; have {sorted(allowed)}")
    return names


# --------------------------------------------------------------------------
# Playing the hands
# --------------------------------------------------------------------------


def play_hand(agents: Sequence[Agent], table: Table, seed: int, button: int) -> list[float]:
    """One complete hand. Returns each seat's win or loss in big blinds.

    Every action goes through the adapter's menu, and the result is read out of
    the engine; nothing here decides who won.
    """
    hand = table.new_hand(seed=seed, button=button)
    while not hand.is_finished:
        seat = hand.current_seat()
        action = agents[seat](hand, seat)
        if not isinstance(action, Action):
            raise TypeError(
                f"seat {seat}'s agent returned {action!r}, which is not one of "
                f"the five moves the adapter offers"
            )
        hand.apply_action(action)
    big_blind = float(table.config.big_blind)
    return [net / big_blind for net in hand.net()]


@dataclasses.dataclass
class Cell:
    """One bot against one persona at one table size: the hands, and the number.

    `values` is the bot's result on each hand in big blinds, in the order the
    hands were played -- the order matters, because a block bootstrap needs it.
    """

    bot: str
    persona: str
    seats: int
    values: list[float]
    has_memory: bool
    seconds: float = 0.0
    not_run: str = ""

    @property
    def hands(self) -> int:
        return len(self.values)

    @property
    def bb_per_100(self) -> float:
        return 100.0 * statistics.fmean(self.values) if self.values else float("nan")


def run_cell(
    bot: Agent,
    bot_name: str,
    persona_name: str,
    seats: int,
    hands: int,
    run_seed: int,
    config: Config,
    session_seed: int | None = None,
) -> Cell:
    """Play one cell: the bot in seat 0, copies of one persona in the rest.

    The deals are a function of `run_seed`, the persona name and the seat count
    alone -- never of which bot is playing -- so two arms of a comparison meet
    the same cards in the same seats. That is section 3.5's "pair everything".

    **The cell starts clean, the bot included.** The opponents are built fresh
    here and told `new_session()`; the bot is handed in already built, so it is
    told the same thing, which winds a persona's coin flips back to where they
    began. That is what makes one cell reproducible on its own: without it, the
    cells before this one in the same run would have drawn from the bot's random
    stream and re-running this cell alone would give a different number from the
    one the report printed. **A bot registered through `register_bot` that
    carries any state of its own -- a random stream, a count of hands, an
    opponent model -- must offer `new_session()` to get the same treatment.** It
    is also told `hand_finished(net)` after every hand, so a bot that adapts
    actually gets to; and if it declares `has_memory`, the cell does, and the
    interval is computed with a block bootstrap rather than by resampling single
    hands.
    """
    dealable, reason = deal_check(seats)
    if not dealable:
        return Cell(bot_name, persona_name, seats, [], False, not_run=reason)

    session_seed = run_seed if session_seed is None else session_seed
    rollouts = int(config.run["equity_rollouts"])
    preflop_rollouts = int(config.run["preflop_rollouts"])
    opponents = [
        build_persona(
            persona_name,
            session_seed,
            rollouts=rollouts,
            preflop_rollouts=preflop_rollouts,
            stream=seat,
        )
        for seat in range(1, seats)
    ]
    for opponent in opponents:
        opponent.new_session()
    _start_session(bot)
    agents: list[Agent] = [bot, *opponents]
    table = Table(
        TableConfig(
            seats=seats,
            small_blind=int(config.run["small_blind"]),
            big_blind=int(config.run["big_blind"]),
            stacks=(int(config.run["big_blind"]) * int(config.run["starting_stack_bb"]),)
            * seats,
        )
    )
    values: list[float] = []
    started = time.monotonic()
    for index in range(hands):
        seed = stable_seed("deal", run_seed, persona_name, seats, index)
        # The button moves one seat every hand, so over a multiple of `seats`
        # hands the bot posts each blind exactly as often as anybody else. The
        # closed-form check on `always_fold` depends on this.
        nets = play_hand(agents, table, seed=seed, button=index % seats)
        values.append(nets[0])
        _report_hand(bot, nets[0])
        for seat, opponent in enumerate(opponents, start=1):
            opponent.hand_finished(nets[seat])
    return Cell(
        bot=bot_name,
        persona=persona_name,
        seats=seats,
        values=values,
        has_memory=bool(getattr(bot, "has_memory", False))
        or any(o.has_memory for o in opponents),
        seconds=time.monotonic() - started,
    )


def _start_session(bot: Agent) -> None:
    """Tell the bot a cell is starting, if it is the sort of bot that cares.

    A bot is any callable with the adapter's signature, so this is asked for
    rather than required. A plain function has nothing to forget.
    """
    start = getattr(bot, "new_session", None)
    if callable(start):
        start()


def _report_hand(bot: Agent, net_bb: float) -> None:
    """Tell the bot what its hand did, if it is the sort of bot that cares."""
    finished = getattr(bot, "hand_finished", None)
    if callable(finished):
        finished(net_bb)


# --------------------------------------------------------------------------
# Intervals
# --------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Interval:
    """A number with a range around it, both in big blinds per hundred hands."""

    estimate: float
    low: float
    high: float
    t_low: float = float("nan")
    t_high: float = float("nan")
    p_value: float = float("nan")

    @property
    def above_zero(self) -> bool:
        return self.low > 0

    @property
    def below_zero(self) -> bool:
        return self.high < 0

    def __str__(self) -> str:
        return f"{self.estimate:+9.1f} [{self.low:+9.1f},{self.high:+9.1f}]"


def block_length(values: Sequence[float], asked: int) -> int:
    """How long a block of consecutive hands to resample, given how many there are.

    A block as long as the run itself would give every resample the same hands
    and an interval of width zero, which is a lie rather than a small number.
    Four blocks is the floor, so the asked-for length is cut back on a short run
    and the report says how many hands each cell actually played.
    """
    if asked <= 1 or len(values) < 8:
        return 1
    return max(1, min(asked, len(values) // 4))


def _blocks(values: Sequence[float], block: int) -> list[list[float]]:
    """Every run of `block` consecutive hands, one starting at each hand.

    Overlapping blocks, which is the moving-block bootstrap of Politis and
    Romano: it keeps far more distinct blocks to draw from than cutting the run
    into non-overlapping pieces would, and a short cell needs every one of them.
    """
    return [list(values[i:i + block]) for i in range(0, len(values) - block + 1)]


def _resample(values: Sequence[float], rng: random.Random, block: int) -> float:
    block = block_length(values, block)
    if block <= 1:
        picked = rng.choices(values, k=len(values))
        return statistics.fmean(picked)
    chunks = _blocks(values, block)
    drawn: list[float] = []
    while len(drawn) < len(values):
        drawn.extend(rng.choice(chunks))
    return statistics.fmean(drawn[:len(values)])


def _bootstrap_p_value(means: Sequence[float], resamples: int) -> float:
    """How surprising this result would be if the true difference were zero.

    Two-sided, and the "two-sided" has to be done by taking the SMALLER of the
    two tails and doubling it, not by counting whichever side the estimate is
    not on. A run in which nothing changed resamples to exactly zero every time:
    every resample is then on both sides at once, the smaller tail is the whole
    distribution, and the answer is 1 -- as unsurprising as a result can be.
    Counting one side gives 1/(resamples+1) instead and stars a difference of
    nothing as a discovery.

    The +1 in each term is the standard correction (Davison and Hinkley): a
    bootstrap p-value of exactly zero claims more than `resamples` draws can
    support, so the observed statistic is counted in on both sides.

    Used only by the Benjamini-Hochberg step on the per-table-size tests.
    """
    at_or_below = sum(1 for m in means if m <= 0)
    at_or_above = sum(1 for m in means if m >= 0)
    smaller_tail = min(at_or_below, at_or_above)
    return min(1.0, (2.0 * smaller_tail + 1.0) / (resamples + 1))


def bootstrap_interval(
    values: Sequence[float],
    config: Config,
    seed: int = 0,
    block: int = 1,
) -> Interval:
    """The percentile bootstrap of section 3.5, in big blinds per hundred hands.

    In plain words: take the hands that were actually played, draw a fresh
    pretend run of the same length from them at random with repeats allowed,
    average it, do that a few thousand times, and read off the middle 95% of
    those averages. The width of that range is how much of the result is luck.

    `block` above 1 draws runs of consecutive hands instead of single hands,
    which is what a persona whose hands depend on each other needs.
    """
    if len(values) < 2:
        nan = float("nan")
        estimate = 100.0 * values[0] if values else nan
        return Interval(estimate, nan, nan)
    rng = random.Random(seed)
    resamples = int(config.bootstrap["resamples"])
    confidence = float(config.bootstrap["confidence"])
    means = sorted(_resample(values, rng, block) for _ in range(resamples))
    tail = (1.0 - confidence) / 2.0
    low = means[max(0, int(math.floor(tail * resamples)) - 1)]
    high = means[min(resamples - 1, int(math.ceil((1.0 - tail) * resamples)) - 1)]
    estimate = statistics.fmean(values)
    p_value = _bootstrap_p_value(means, resamples)
    t_low, t_high = _t_interval(values, confidence)
    return Interval(
        estimate=100.0 * estimate,
        low=100.0 * low,
        high=100.0 * high,
        t_low=100.0 * t_low,
        t_high=100.0 * t_high,
        p_value=p_value,
    )


def _t_interval(values: Sequence[float], confidence: float) -> tuple[float, float]:
    """The ordinary textbook interval, printed only as a cross-check."""
    n = len(values)
    if n < 2:
        return float("nan"), float("nan")
    mean = statistics.fmean(values)
    spread = statistics.stdev(values) / math.sqrt(n)
    # 1.96 is the 95% figure; the run's confidence level is read from config and
    # anything else falls back to the normal approximation for that level.
    z = 1.959963985 if abs(confidence - 0.95) < 1e-9 else _normal_quantile(
        0.5 + confidence / 2.0
    )
    return mean - z * spread, mean + z * spread


def _normal_quantile(p: float) -> float:
    """Inverse normal, Acklam-style rational approximation, good to ~1e-9."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    p_low, p_high = 0.02425, 1 - 0.02425
    if p < p_low:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > p_high:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def benjamini_hochberg(p_values: Sequence[float], q: float, family_size: int) -> list[bool]:
    """Which of these tests survive a false-discovery-rate correction.

    Section 3.5: five table sizes tested at 5% each raise a false alarm about a
    fifth of the time, so the family is corrected as a family -- and the family
    is every cell the run actually bought, not just the ones being looked at.
    Correcting for five when twenty were run is cheating.
    """
    order = sorted(range(len(p_values)), key=lambda i: p_values[i])
    passed = [False] * len(p_values)
    largest = -1
    for rank, index in enumerate(order, start=1):
        if p_values[index] <= q * rank / family_size:
            largest = rank
    for rank, index in enumerate(order, start=1):
        if rank <= largest:
            passed[index] = True
    return passed


# --------------------------------------------------------------------------
# The decision rule
# --------------------------------------------------------------------------


@dataclasses.dataclass
class Verdict:
    """What the rule says, and every reason it says it."""

    accepted: bool
    primary: Interval
    weights: dict[int, float]
    by_seats: dict[int, Interval]
    by_seats_significant: dict[int, bool]
    by_persona: dict[str, Interval]
    blockers: list[str]
    overrides: list[str]
    family_size: int
    reasons: list[str]

    @property
    def label(self) -> str:
        return "ACCEPT" if self.accepted else "REJECT"


def paired_differences(arm_b: Cell, arm_a: Cell) -> list[float]:
    """Hand by hand, how much better arm B did than arm A on the same deal."""
    if arm_b.seats != arm_a.seats or arm_b.persona != arm_a.persona:
        raise ValueError("these two cells are not the same cell of the grid")
    if len(arm_b.values) != len(arm_a.values):
        raise ValueError("the two arms played different numbers of hands")
    return [b - a for b, a in zip(arm_b.values, arm_a.values)]


def decide(
    cells_b: Sequence[Cell],
    cells_a: Sequence[Cell],
    config: Config,
    seed: int = 0,
) -> Verdict:
    """Section 3.5's rule, applied to a finished paired run."""
    paired = {}
    for b in cells_b:
        match = [a for a in cells_a if a.persona == b.persona and a.seats == b.seats]
        if not match or b.not_run or match[0].not_run:
            continue
        paired[(b.persona, b.seats)] = (paired_differences(b, match[0]), b.has_memory)

    if not paired:
        nan = Interval(float("nan"), float("nan"), float("nan"))
        return Verdict(
            False, nan, {}, {}, {}, {}, [], [], 0,
            ["no cell ran in both arms, so there is nothing to compare"],
        )

    block = int(config.bootstrap["block_hands"])
    seats_present = sorted({seats for _, seats in paired})
    weights = table_size_weights(seats_present, config)

    by_seats: dict[int, Interval] = {}
    for seats in seats_present:
        values, memory = _pool(paired, lambda key: key[1] == seats)
        by_seats[seats] = bootstrap_interval(
            values, config, seed=stable_seed(seed, "seats", seats),
            block=block if memory else 1,
        )
    by_persona: dict[str, Interval] = {}
    for persona in sorted({name for name, _ in paired}):
        values, memory = _pool(paired, lambda key: key[0] == persona)
        by_persona[persona] = bootstrap_interval(
            values, config, seed=stable_seed(seed, "persona", persona),
            block=block if memory else 1,
        )

    primary = _weighted_primary(paired, weights, config, seed)

    family_size = len(paired)
    ordered_seats = list(by_seats)
    significance = benjamini_hochberg(
        [by_seats[n].p_value for n in ordered_seats], q=0.05, family_size=family_size
    )
    by_seats_significant = dict(zip(ordered_seats, significance))

    override_text = []
    overridden = set()
    for override in config.overrides:
        overridden.add(str(override.get("persona", "")))
        override_text.append(
            f"{override.get('persona')}: {override.get('regression')} -- "
            f"{override.get('reason')}"
        )
    blockers = [
        f"{name} {by_persona[name]} bb/100, wholly below zero"
        for name in by_persona
        if by_persona[name].below_zero and name not in overridden
    ]

    reasons: list[str] = []
    accepted = True
    if not primary.above_zero:
        accepted = False
        reasons.append(
            f"the headline interval {primary} bb/100 does not lie entirely above zero"
        )
    if blockers:
        accepted = False
        reasons.append(
            "a persona's interval lies wholly below zero, which blocks the change: "
            + "; ".join(blockers)
        )
    if accepted:
        reasons.append(
            f"the headline interval {primary} bb/100 lies entirely above zero and "
            f"no persona's interval lies wholly below it"
        )
    return Verdict(
        accepted=accepted,
        primary=primary,
        weights=weights,
        by_seats=by_seats,
        by_seats_significant=by_seats_significant,
        by_persona=by_persona,
        blockers=blockers,
        overrides=override_text,
        family_size=family_size,
        reasons=reasons,
    )


def _pool(paired, keep) -> tuple[list[float], bool]:
    """Every per-hand difference from the cells `keep` selects, laid end to end.

    **The approximation this makes, stated rather than hidden.** The cells are
    concatenated, so a block the moving-block bootstrap draws near a join spans
    the end of one cell and the start of the next -- hands that are not
    consecutive and, across a cell boundary, not dependent on each other at all.
    Those straddling blocks are a fraction of roughly (block length - 1) divided
    by (cell length) of all blocks drawn, so at the configured 20-hand block and
    1000-hand cells they are under 2% of them, and each one understates rather
    than overstates the dependence, which widens nothing it should narrow. The
    honest fix is to draw blocks within a cell and never across a join; it is
    not done here because the effect is smaller than the bootstrap's own
    resampling error at these sizes.
    """
    values: list[float] = []
    memory = False
    for key, (differences, has_memory) in paired.items():
        if keep(key):
            values.extend(differences)
            memory = memory or has_memory
    return values, memory


def _weighted_primary(paired, weights: Mapping[int, float], config: Config, seed: int) -> Interval:
    """The one number: the paired difference, weighted across table sizes.

    Each table size's hands are resampled inside that table size, and the
    weighted sum is recomputed for every resample, so the interval on the
    headline is an interval on the weighted thing itself and not a splice of
    four separate intervals.
    """
    per_seat: dict[int, tuple[list[float], bool]] = {}
    for seats in weights:
        per_seat[seats] = _pool(paired, lambda key, n=seats: key[1] == n)
    estimate = sum(
        weights[n] * statistics.fmean(values)
        for n, (values, _) in per_seat.items()
        if values
    )
    resamples = int(config.bootstrap["resamples"])
    confidence = float(config.bootstrap["confidence"])
    block = int(config.bootstrap["block_hands"])
    rng = random.Random(stable_seed(seed, "primary"))
    draws = []
    for _ in range(resamples):
        total = 0.0
        for n, (values, memory) in per_seat.items():
            if not values:
                continue
            total += weights[n] * _resample(values, rng, block if memory else 1)
        draws.append(total)
    draws.sort()
    tail = (1.0 - confidence) / 2.0
    low = draws[max(0, int(math.floor(tail * resamples)) - 1)]
    high = draws[min(resamples - 1, int(math.ceil((1.0 - tail) * resamples)) - 1)]
    pooled = [v for values, _ in per_seat.values() for v in values]
    t_low, t_high = _t_interval(pooled, confidence)
    return Interval(
        estimate=100.0 * estimate,
        low=100.0 * low,
        high=100.0 * high,
        t_low=100.0 * t_low,
        t_high=100.0 * t_high,
        p_value=_bootstrap_p_value(draws, resamples),
    )


# --------------------------------------------------------------------------
# Naming a bot on the command line
# --------------------------------------------------------------------------


def available_bots() -> list[str]:
    from .personas import _CLASSES

    return sorted(set(_CLASSES) | set(_BOT_FACTORIES))


def resolve_bot(name: str, session_seed: int, config: Config) -> Agent:
    """Turn a `--bot` name into something that can sit in a seat."""
    if name in _BOT_FACTORIES:
        return _BOT_FACTORIES[name](session_seed)
    from .personas import _CLASSES

    if name in _CLASSES:
        return build_persona(
            name,
            session_seed,
            rollouts=int(config.run["equity_rollouts"]),
            preflop_rollouts=int(config.run["preflop_rollouts"]),
            stream="bot",
        )
    raise KeyError(f"no bot called {name!r}; have {available_bots()}")
