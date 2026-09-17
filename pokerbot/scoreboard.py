"""The one command: play the league and print the report.

    python -m pokerbot.scoreboard --bot <name> --hands N --seed S

What it does, in one sentence: sits the named bot down against every persona at
every table size the config asks for, sits the comparison bot down on exactly
the same deals, and prints how much each of them won per hundred hands with a
range around every number and the pre-registered rule's verdict at the end.

Every number in the report is a measurement or a decision recorded before the
run. Nothing in it is an impression. `EVALUATION_STRATEGY.md` section 3.5 lays
out what the page contains and this file prints it in that order:

1. What was run and under which config, the table-size weights included --
   an unlabelled average is not a result.
2. The parameters drawn for each persona this session.
3. Big blinds per hundred hands for the bot, one line per persona per table
   size, each with a 95% interval.
4. The same for the paired difference against the comparison bot.
5. The rule's verdict, with every reason it reached it.

A table size the engine will not deal prints NOT RUN with the engine's reason,
never a pass and never a blank.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Sequence, TextIO

from . import league
from .league import Cell, Config, Interval, Verdict
from .personas import ALL_PERSONAS, Persona, build_persona
from .provenance import commit_id
from .table import ENGINE, deal_check

MODES = ("acceptance", "tuning")


def _load_average() -> str:
    one, five, fifteen = os.getloadavg()
    return f"{one:.2f} {five:.2f} {fifteen:.2f}"


def _interval_cell(interval: Interval) -> str:
    if interval.estimate != interval.estimate:  # NaN
        return "NOT RUN: too few hands to put a range around"
    return str(interval)


def print_header(
    out: TextIO,
    bot_name: str,
    compare_name: str,
    mode: str,
    hands: int,
    seats: Sequence[int],
    personas: Sequence[str],
    config: Config,
    weights: dict[int, float],
    load: str,
) -> None:
    write = lambda line="": print(line, file=out)
    write(
        f"scoreboard  bot B={bot_name}  bot A={compare_name}  engine={ENGINE}  "
        f"commit={commit_id()}"
    )
    write(
        f"mode: {mode}   hands: {hands} per cell per arm   "
        f"cells: {len(personas) * len(seats)}   seats: {' '.join(str(n) for n in seats)}"
    )
    write(f"config: {config.path} (pre-registered; reprinted here, not chosen after the run)")
    write(
        "  weights: "
        + "  ".join(f"n{n}={w:.3f}" for n, w in sorted(weights.items()))
    )
    write(
        f"    bands: {config.weights['primary_seats']} at {config.weights['primary']:.2f}, "
        f"{config.weights['secondary_seats']} together at {config.weights['secondary']:.2f}, "
        f"everything else that ran at {config.weights['other']:.2f} split equally"
    )
    write(
        "    (a design choice implementing the operator's stated ordering of table"
    )
    write(
        "     sizes, 2026-09-15 -- mostly six-handed, then eight or nine; the three"
    )
    write(
        "     numbers are EVALUATION_STRATEGY.md section 3.5's, not the operator's)"
    )
    empty = league.missing_bands(seats, config)
    if empty:
        write(
            f"    note: no seat count ran in the band(s) {', '.join(empty)}, so the "
            f"remaining weights were rescaled to sum to 1"
        )
    write(
        f"  bootstrap: {config.bootstrap['resamples']} resamples, "
        f"{float(config.bootstrap['confidence']) * 100:.0f}% percentile interval, "
        f"blocks of {config.bootstrap['block_hands']} hands for a persona with memory"
    )
    write(
        "  decision: accept only if the weighted headline interval lies wholly above"
    )
    write(
        "            zero and no persona's own interval lies wholly below it"
    )
    write(f"  development half (tuning may use these): {', '.join(config.development)}")
    write(f"  held back (accept/reject only):          {', '.join(config.held_back)}")
    write(f"  calibration agents (both modes):         {', '.join(config.calibration)}")
    write(f"machine: load average {load} at the start of the run")


def print_drawn_parameters(out: TextIO, personas: Sequence[Persona], seed: int) -> None:
    print(file=out)
    print(
        f"personas drawn this session (seed {seed}). Section 3.2 draws these afresh "
        f"every session",
        file=out,
    )
    print(
        "rather than fixing them, because a bot tuned against one exact parameter "
        "point looks",
        file=out,
    )
    print("better than it is.", file=out)
    for persona in personas:
        print(f"  {persona.describe()}", file=out)


def print_cells(
    out: TextIO,
    title: str,
    rows: Sequence[tuple[str, int, str, str]],
    last_column: str,
) -> None:
    print(file=out)
    print(title, file=out)
    print(
        f"  {'persona':<17}{'n':>2}  {'bb/100 [95% interval]':<31} {last_column}",
        file=out,
    )
    for persona, seats, cell, extra in rows:
        print(f"  {persona:<17}{seats:>2}  {cell:<31} {extra}", file=out)


def print_verdict(out: TextIO, verdict: Verdict, seats: Sequence[int]) -> None:
    write = lambda line="": print(line, file=out)
    write()
    write(
        f"primary endpoint (weighted pool, paired, B minus A)  "
        f"{verdict.primary} bb/100   {verdict.label}"
    )
    write(
        f"  cross-check, ordinary t-interval: "
        f"[{verdict.primary.t_low:+.1f},{verdict.primary.t_high:+.1f}] bb/100 "
        f"(a material disagreement with the bootstrap means the data is wrong, "
        f"not the test)"
    )
    write(
        f"  by table size, unweighted (Benjamini-Hochberg q=0.05, family size "
        f"{verdict.family_size} cells; * survives the correction)"
    )
    for n in sorted(verdict.by_seats):
        mark = "*" if verdict.by_seats_significant.get(n) else " "
        write(f"    n={n:<2} {verdict.by_seats[n]} bb/100  {mark}")
    write("  by persona (non-inferiority; an interval wholly below zero BLOCKS)")
    for name in sorted(verdict.by_persona):
        interval = verdict.by_persona[name]
        flag = ""
        if interval.below_zero:
            flag = "  <- BLOCK"
        elif interval.low < 0 < interval.high and interval.estimate < 0:
            flag = "  <- watch"
        write(f"    {name:<17} {interval} bb/100{flag}")
    write(f"  overrides in force: {'; '.join(verdict.overrides) or 'none'}")
    write()
    write(f"verdict: {verdict.label}")
    for reason in verdict.reasons:
        write(f"  because {reason}")


def run(
    bot_name: str,
    compare_name: str,
    hands: int,
    seed: int,
    seats: Sequence[int],
    persona_names: Sequence[str],
    mode: str,
    config: Config,
    out: TextIO = sys.stdout,
) -> tuple[list[Cell], list[Cell], Verdict]:
    """Play every cell in both arms and print the report. Returns the results."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
    if mode == "tuning":
        persona_names = league.tuning_opponents(config, persona_names)
    else:
        persona_names = league.acceptance_opponents(config, persona_names)

    started = time.monotonic()
    load_at_start = _load_average()
    weights = league.table_size_weights(seats, config)
    drawn = [
        build_persona(name, seed, rollouts=int(config.run["equity_rollouts"]))
        for name in persona_names
    ]
    print_header(
        out, bot_name, compare_name, mode, hands, seats, persona_names, config, weights,
        load_at_start,
    )
    print_drawn_parameters(out, drawn, seed)

    bot_b = league.resolve_bot(bot_name, seed, config)
    bot_a = league.resolve_bot(compare_name, seed, config)

    cells_b: list[Cell] = []
    cells_a: list[Cell] = []
    rows_b: list[tuple[str, int, str, str]] = []
    rows_diff: list[tuple[str, int, str, str]] = []
    block = int(config.bootstrap["block_hands"])
    for name in persona_names:
        for n in seats:
            dealable, reason = deal_check(n)
            if not dealable:
                rows_b.append((name, n, f"NOT RUN: {reason}"[:25], ""))
                rows_diff.append((name, n, f"NOT RUN: {reason}"[:25], ""))
                continue
            cell_b = league.run_cell(bot_b, bot_name, name, n, hands, seed, config)
            cell_a = league.run_cell(bot_a, compare_name, name, n, hands, seed, config)
            cells_b.append(cell_b)
            cells_a.append(cell_a)
            interval_b = league.bootstrap_interval(
                cell_b.values, config, seed=league.stable_seed(seed, "B", name, n),
                block=block if cell_b.has_memory else 1,
            )
            differences = league.paired_differences(cell_b, cell_a)
            interval_d = league.bootstrap_interval(
                differences, config, seed=league.stable_seed(seed, "D", name, n),
                block=block if cell_b.has_memory else 1,
            )
            seconds = cell_b.seconds + cell_a.seconds
            rows_b.append((name, n, _interval_cell(interval_b), f"{cell_b.hands:>6}  {seconds:>6.1f}"))
            rows_diff.append((name, n, _interval_cell(interval_d), f"{cell_b.hands:>6}"))

    print_cells(
        out,
        f"big blinds per hundred hands for {bot_name}, by persona and table size",
        rows_b,
        f"{'hands':>6}  {'secs':>6}",
    )
    print_cells(
        out,
        f"paired difference, {bot_name} minus {compare_name}, same deals and same seats",
        rows_diff,
        f"{'hands':>6}",
    )
    verdict = league.decide(cells_b, cells_a, config, seed=seed)
    print_verdict(out, verdict, seats)
    elapsed = time.monotonic() - started
    print(file=out)
    print(
        f"elapsed: {elapsed:.1f}s   machine load average {load_at_start} at the start, "
        f"{_load_average()} at the end",
        file=out,
    )
    return cells_b, cells_a, verdict


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m pokerbot.scoreboard",
        description=(
            "Play the persona league and print the scoreboard: big blinds per "
            "hundred hands with a 95% interval for every persona at every table "
            "size, and the pre-registered rule's verdict."
        ),
    )
    parser.add_argument("--bot", required=True, help="the bot being measured (arm B)")
    parser.add_argument(
        "--compare",
        default=None,
        help="the version it is being compared with (arm A); config's reference bot by default",
    )
    parser.add_argument("--hands", type=int, default=None, help="hands per cell per arm")
    parser.add_argument("--seed", type=int, default=0, help="the run's seed")
    parser.add_argument(
        "--seats",
        default=None,
        help="comma-separated table sizes, e.g. 2,6,8,9; config's list by default",
    )
    parser.add_argument(
        "--personas",
        default=None,
        help="comma-separated persona names; all of them by default",
    )
    parser.add_argument(
        "--mode",
        default="acceptance",
        choices=MODES,
        help="tuning refuses the held-back half; acceptance uses every persona",
    )
    parser.add_argument("--config", default=None, help="a different config file")
    parser.add_argument(
        "--list-bots", action="store_true", help="print what --bot accepts and stop"
    )
    return parser


def main(argv: Sequence[str] | None = None, out: TextIO = sys.stdout) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    config = league.load_config(args.config) if args.config else league.load_config()
    if args.list_bots:
        print("  ".join(league.available_bots()), file=out)
        return 0
    seats = (
        [int(n) for n in args.seats.split(",")]
        if args.seats
        else [int(n) for n in config.run["seats"]]
    )
    hands = args.hands if args.hands is not None else int(config.run["hands"])
    personas = args.personas.split(",") if args.personas else None
    compare = args.compare or str(config.decision["reference_bot"])
    try:
        _, _, verdict = run(
            bot_name=args.bot,
            compare_name=compare,
            hands=hands,
            seed=args.seed,
            seats=seats,
            persona_names=personas,
            mode=args.mode,
            config=config,
            out=out,
        )
    except league.HeldBackPersonaError as refusal:
        print(f"refused: {refusal}", file=out)
        return 2
    return 0 if verdict.accepted else 1


if __name__ == "__main__":  # pragma: no cover - the command line entry point
    raise SystemExit(main())
