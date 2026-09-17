"""Sit the bot down against the trivial opponents and count what it wins.

    python -m pokerbot.arena --seats 6 --hands 1000 --seed 20260917 \
        --bot search --opponents random

What it does, in plain words. It deals complete hands on the T1 table, with the
bot in one seat and one of `baselines.py`'s three non-players in each of the
others, moving the dealer button one seat every hand so nobody sits in the
blinds more often than anybody else. After every hand it checks the table's
seven invariants -- the statements that have to be true or no score measured
here means anything -- and if one of them fails it stops the run there and then
rather than finishing and reporting a number. At the end it prints how many
hands were played, how long the bot's slowest decision took, and how much it
won, with a range around it.

The range is the important part. Poker is noisy enough that a bare win rate
means nothing, so the score is printed as a 95% interval worked out by
*bootstrapping*: the thousand hands are re-drawn at random, with repeats, a few
thousand times over, and the middle 95% of those re-drawn averages is the
interval. If that interval does not contain zero, the bot beating the opponents
is not something the shuffle could plausibly have produced on its own.
`BUILD_PLAN.md` T2 is done when it excludes zero against uniform-random play.

Which invariants really run here, said exactly, because a check that does not
run must never be reported as one that passed:

  I1  chips are conserved                                   runs
  I2  nobody overspends and no stack goes negative          runs
  I3  nobody is paid more than they matched, seat by seat   runs, in part
  I4  every move made was on the engine's own menu          runs
  I5  the blinds and the acting order follow the button     runs
  I6  the same seed replays byte-identical hands            runs, sampled
  I7  the pot equals what was put in                        runs, in part

I3 and I7 each have a second half that compares the engine's showdown with an
outside hand evaluator (`treys`). That half is not run here and cannot be:
`CLAUDE.md` keeps that evaluator out of live play and allows it in tests only.
It runs over every seat count from two to nine in `tests/test_table_invariants.py`,
which is where it belongs. I6 is sampled rather than run on every hand because
proving it costs playing the hand a second time.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import random
import statistics
import sys
import time

from . import baselines, equity_rule
from .invariants import InvariantViolation, require
from .provenance import commit_id
from .record import HandRecord
from .search import BUDGET_S, PLAYOUTS_PER_CANDIDATE, decide
from .table import Hand, Table, TableConfig

TOLERANCE = 1e-9

#: How many times the hands are re-drawn to put an interval on the win rate.
BOOTSTRAP_RESAMPLES = 10_000

#: The interval printed: the middle 95% of the re-drawn averages.
CONFIDENCE = 0.95

#: One hand in this many is played a second time from its seed and compared
#: byte for byte, which is invariant I6.
REPLAY_CHECK_EVERY = 100

#: What each street is called, in the order the engine numbers them.
STREET_NAMES = ("preflop", "flop", "turn", "river")


# --------------------------------------------------------------------------
# the invariants, checked on a finished hand
# --------------------------------------------------------------------------


def check_invariants(record: HandRecord) -> None:
    """Every invariant that can be checked on a finished hand record.

    Raises `InvariantViolation`, which ends the run. See the module docstring
    for which half of I3 and I7 runs here and which half is the test suite's.
    """
    seats = record.seats
    contributions = record.contributions
    payouts = record.payouts
    net = record.net

    # I1 -- the seats' wins and losses add up to nothing.
    total = sum(net)
    require(abs(total) < TOLERANCE, "I1", f"the hand's wins and losses add up to {total}", record.to_json())

    for seat in range(seats):
        # I2 -- nobody puts in more than they sat down with, and nobody
        # finishes the hand owing money.
        start = record.stacks[seat]
        require(
            contributions[seat] <= start + TOLERANCE,
            "I2",
            f"seat {seat} put in {contributions[seat]} from a stack of {start}",
            record.to_json(),
        )
        require(
            start + net[seat] >= -TOLERANCE,
            "I2",
            f"seat {seat} finished the hand with {start + net[seat]} chips",
            record.to_json(),
        )
        # I3 -- the side-pot ceiling: a seat can win from each opponent only
        # as much as it had matched against that opponent. This is the half of
        # I3 that needs no hand evaluator, so it is the half that can run in
        # live play.
        ceiling = sum(min(contributions[other], contributions[seat]) for other in range(seats))
        require(
            payouts[seat] <= ceiling + TOLERANCE,
            "I3",
            f"seat {seat} was paid {payouts[seat]} but had only {ceiling} "
            f"matched against it, from contributions {contributions}",
            record.to_json(),
        )

    # I7 -- the pot is what was put in, and it is all handed back out.
    pot = sum(contributions)
    require(
        abs(record.pot - pot) < TOLERANCE,
        "I7",
        f"the record says the pot was {record.pot} but the seats put in {pot}",
        record.to_json(),
    )
    require(
        abs(sum(payouts) - pot) < TOLERANCE,
        "I7",
        f"a pot of {pot} paid out {sum(payouts)}",
        record.to_json(),
    )

    # I5 -- the blinds follow the button, and heads-up reverses.
    blinds = [e for e in record.events if e.kind == "blind"]
    require(
        len(blinds) == 2,
        "I5",
        f"{len(blinds)} blinds were posted, not two",
        record.to_json(),
    )
    small, big = sorted(blinds, key=lambda e: e.amount or 0.0)
    expected_small = record.button if seats == 2 else (record.button + 1) % seats
    expected_big = (record.button + 1) % seats if seats == 2 else (record.button + 2) % seats
    require(
        small.seat == expected_small and big.seat == expected_big,
        "I5",
        f"with the button on seat {record.button} at {seats} seats the blinds "
        f"were posted by {small.seat} and {big.seat}, not {expected_small} and {expected_big}",
        record.to_json(),
    )
    first = next((e for e in record.events if e.kind == "action"), None)
    if first is not None:
        expected_first = record.button if seats == 2 else (record.button + 3) % seats
        require(
            first.seat == expected_first,
            "I5",
            f"with the button on seat {record.button} at {seats} seats the first "
            f"seat to act was {first.seat}, not {expected_first}",
            record.to_json(),
        )


# --------------------------------------------------------------------------
# one hand
# --------------------------------------------------------------------------


@dataclasses.dataclass
class DecisionLog:
    """One decision by the bot, with the check that ran beside it.

    `BUILD_PLAN.md` T2 wants the equity rule logged rather than played, so
    every one of these carries both answers and whether they agreed.
    """

    hand: int
    seat: int
    street: int
    search_action: str
    rule_action: str
    agree: bool
    search_s: float
    rule_s: float
    equity: float
    pot: float
    to_call: float
    needed: float
    playouts: int
    truncated: bool
    starved: bool

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


def play_hand(
    table: Table,
    *,
    hand_index: int,
    seed: int,
    button: int,
    bot_seat: int,
    opponents: dict[int, object],
    budget_s: float,
    playouts_per_candidate: int,
    run_rule: bool,
    logs: list[DecisionLog] | None = None,
) -> Hand:
    """Play one complete hand. Every move comes off the engine's own menu.

    Seeding: the hand's cards come from `seed`, each opponent draws from its
    own stream fixed by `seed`, and the bot's search is seeded from `seed` and
    how many times it has been asked to act in this hand. So the same seed
    replays the same hand, move for move, which is invariant I6.
    """
    hand = table.new_hand(seed=seed, button=button)
    opponent_rng = {s: random.Random(seed * 7919 + s) for s in opponents}
    decisions = 0
    while not hand.is_finished:
        seat = hand.current_seat()
        menu = hand.legal_actions()
        require(bool(menu), "I4", f"seat {seat} was asked to act with no legal move")
        if seat == bot_seat:
            view = hand.engine_view()
            street = hand.street
            decision = decide(
                view,
                seed=seed * 104729 + decisions,
                budget_s=budget_s,
                playouts_per_candidate=playouts_per_candidate,
            )
            action = decision.action
            if run_rule and logs is not None:
                rule = equity_rule.check(view, seed=seed * 15485863 + decisions)
                logs.append(
                    DecisionLog(
                        hand=hand_index,
                        seat=seat,
                        street=street,
                        search_action=action.value,
                        rule_action=rule.action.value,
                        agree=action is rule.action,
                        search_s=decision.elapsed_s,
                        rule_s=rule.elapsed_s,
                        equity=rule.equity,
                        pot=rule.pot,
                        to_call=rule.to_call,
                        needed=rule.needed,
                        playouts=decision.playouts,
                        truncated=decision.truncated,
                        starved=decision.starved,
                    )
                )
            elif logs is not None:
                logs.append(
                    DecisionLog(
                        hand=hand_index,
                        seat=seat,
                        street=street,
                        search_action=action.value,
                        rule_action="",
                        agree=False,
                        search_s=decision.elapsed_s,
                        rule_s=0.0,
                        equity=float("nan"),
                        pot=float("nan"),
                        to_call=float("nan"),
                        needed=float("nan"),
                        playouts=decision.playouts,
                        truncated=decision.truncated,
                        starved=decision.starved,
                    )
                )
            decisions += 1
        else:
            action = opponents[seat](menu, opponent_rng[seat])
        # I4 -- nothing is ever applied that the engine did not offer. The
        # adapter refuses an illegal move as well; this is the belt to its
        # braces, and it names the player that tried it.
        require(
            action in menu,
            "I4",
            f"seat {seat} tried {action}, which the engine does not allow here",
            str(sorted(a.value for a in menu)),
        )
        hand.apply_action(action)
    return hand


# --------------------------------------------------------------------------
# the run
# --------------------------------------------------------------------------


def percentile(values: list[float], fraction: float) -> float:
    """The value below which `fraction` of the sorted values fall.

    Nearest-rank, which needs no interpolation and so cannot invent a number
    that was never measured.
    """
    if not values:
        return float("nan")
    ordered = sorted(values)
    rank = max(1, min(len(ordered), int(round(fraction * len(ordered) + 0.5))))
    return ordered[rank - 1]


def bootstrap_interval(
    per_hand: list[float],
    *,
    seed: int,
    resamples: int = BOOTSTRAP_RESAMPLES,
    confidence: float = CONFIDENCE,
) -> tuple[float, float]:
    """A 95% interval on the mean, by re-drawing the hands with repeats.

    The plain version: take the hands that were played, draw that many of them
    again at random allowing the same hand to come up twice, average them, and
    do that thousands of times. The middle 95% of those averages is the
    interval. It assumes nothing about the shape of poker results, which is
    why `EVALUATION_STRATEGY.md` section 3.5 asks for this one -- the
    percentile bootstrap, resampling hands -- rather than a formula: per-hand
    poker results are mostly small folds and occasionally a whole stack, and
    no textbook curve fits that.

    Resampling single hands is right here because the three opponents have no
    memory: nothing about hand 10 depends on hand 9. The same document says an
    opponent that tilts needs blocks of consecutive hands resampled instead,
    and that opponent does not exist until T3.
    """
    if len(per_hand) < 2:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(per_hand)
    means = []
    for _ in range(resamples):
        means.append(statistics.fmean(rng.choices(per_hand, k=n)))
    means.sort()
    low = (1.0 - confidence) / 2.0
    return (percentile(means, low), percentile(means, 1.0 - low))


def seat_opponents(
    seats: int, bot_seat: int, names: list[str]
) -> tuple[dict[int, object], dict[int, str]]:
    """Which non-player sits in each seat that is not the bot's.

    One name fills every other seat with the same opponent; a list of names
    seats them left to right, skipping the bot's seat.
    """
    others = [s for s in range(seats) if s != bot_seat]
    if len(names) == 1:
        names = names * len(others)
    if len(names) != len(others):
        raise ValueError(f"{len(names)} opponents were named for {len(others)} seats")
    seated = {seat: baselines.by_name(name) for seat, name in zip(others, names)}
    return seated, dict(zip(others, names))


def run(
    *,
    seats: int = 6,
    hands: int = 1000,
    seed: int = 20260917,
    bot: str = "search",
    opponents: list[str] | None = None,
    bot_seat: int = 0,
    small_blind: int = 50,
    big_blind: int = 100,
    budget_s: float = BUDGET_S,
    playouts_per_candidate: int = PLAYOUTS_PER_CANDIDATE,
    run_rule: bool = True,
    replay_check_every: int = REPLAY_CHECK_EVERY,
    resamples: int = BOOTSTRAP_RESAMPLES,
    records_out: str | None = None,
    log_out: str | None = None,
) -> dict:
    """Play the hands, check the table after every one, and report."""
    if bot != "search":
        raise ValueError(f"the only bot is 'search', not {bot!r}")
    names = list(opponents or ["random"])
    table = Table(TableConfig(seats=seats, small_blind=small_blind, big_blind=big_blind))
    seated, seated_names = seat_opponents(seats, bot_seat, names)

    load_start = os.getloadavg()
    started_wall = time.time()
    started = time.monotonic()
    per_hand_bb: list[float] = []
    logs: list[DecisionLog] = []
    digest = hashlib.sha256()
    replay_checks = 0
    records_file = open(records_out, "wb") if records_out else None
    try:
        for index in range(hands):
            hand_seed = seed * 1_000_003 + index
            hand = play_hand(
                table,
                hand_index=index,
                seed=hand_seed,
                button=index % seats,
                bot_seat=bot_seat,
                opponents=seated,
                budget_s=budget_s,
                playouts_per_candidate=playouts_per_candidate,
                run_rule=run_rule,
                logs=logs,
            )
            record = hand.record
            check_invariants(record)
            payload = record.to_bytes()
            digest.update(payload)
            if records_file is not None:
                records_file.write(payload)
            per_hand_bb.append(record.net[bot_seat] / big_blind)
            # I6 -- the same seed, on this commit, replays the same bytes.
            if replay_check_every and index % replay_check_every == 0:
                again = play_hand(
                    table,
                    hand_index=index,
                    seed=hand_seed,
                    button=index % seats,
                    bot_seat=bot_seat,
                    opponents=seated,
                    budget_s=budget_s,
                    playouts_per_candidate=playouts_per_candidate,
                    run_rule=False,
                    logs=None,
                )
                # Whose fault a disagreement is. A search the clock cut short
                # is not reproducible from its seed -- `Decision.truncated`
                # says exactly that -- so once one of those has happened the
                # replay may differ for a reason that is nothing to do with
                # the table. The run still stops; it must not stop blaming the
                # adapter for a laptop that was too slow on the day.
                truncated_so_far = sum(1 for log in logs if log.truncated)
                if truncated_so_far:
                    reason = (
                        f"hand {index} replayed from seed {hand_seed} to "
                        f"different bytes, and the clock had already cut "
                        f"{truncated_so_far} of the bot's searches short. A "
                        f"search the clock ends does not depend on its seed "
                        f"alone, so the likeliest cause is that the "
                        f"{budget_s * 1000:.0f} ms budget is too small on this "
                        f"machine rather than that the table replays "
                        f"differently. Rule the clock out first: give it a "
                        f"longer budget or fewer finishes a move and run it "
                        f"again; only then look at the adapter."
                    )
                else:
                    reason = (
                        f"hand {index} replayed from seed {hand_seed} to "
                        f"different bytes"
                    )
                require(
                    again.record.to_bytes() == payload,
                    "I6",
                    reason,
                    payload.decode("utf-8"),
                )
                replay_checks += 1
    finally:
        if records_file is not None:
            records_file.close()

    elapsed = time.monotonic() - started
    load_end = os.getloadavg()
    search_times = [log.search_s for log in logs]
    # Which streets the bot actually got to play. Against opponents who bet at
    # random almost every hand is over before the flop, so a score that does
    # not say this reads as a verdict on the whole bot when it is a verdict on
    # its first decision. Counted here so the caveat travels with the number.
    decisions_by_street = {
        name: sum(1 for log in logs if log.street == street)
        for street, name in enumerate(STREET_NAMES)
    }
    rule_times = [log.rule_s for log in logs if log.rule_action]
    agreed = sum(1 for log in logs if log.rule_action and log.agree)
    rule_decisions = sum(1 for log in logs if log.rule_action)
    # Everything is quoted per hundred hands, the unit BUILD_PLAN.md uses, so
    # the interval is scaled the same way the win rate is. Quoting a win rate
    # per hundred hands beside an interval per hand would be a lie in units.
    win_rate = statistics.fmean(per_hand_bb) * 100 if per_hand_bb else float("nan")
    low, high = (
        bound * 100
        for bound in bootstrap_interval(per_hand_bb, seed=seed + 1, resamples=resamples)
    )

    if log_out:
        with open(log_out, "w", encoding="utf-8") as handle:
            for log in logs:
                handle.write(json.dumps(log.as_dict(), sort_keys=True) + "\n")

    return {
        "schema": "pokerbot.arena_report/1",
        "commit": commit_id(),
        "seats": seats,
        "hands_played": len(per_hand_bb),
        "seed": seed,
        "bot": bot,
        "bot_seat": bot_seat,
        "opponents": {str(seat): name for seat, name in sorted(seated_names.items())},
        "small_blind": small_blind,
        "big_blind": big_blind,
        "budget_s": budget_s,
        "playouts_per_candidate": playouts_per_candidate,
        "invariant_failures": 0,  # a failure raises; reaching here means none
        "invariants_checked": ["I1", "I2", "I3", "I4", "I5", "I6", "I7"],
        "invariants_partial": {
            "I3": "the side-pot ceiling only; the showdown half needs the "
            "outside evaluator, which CLAUDE.md keeps out of live play",
            "I7": "the pot arithmetic only; the showdown half is the test suite's",
            "I6": f"sampled: {replay_checks} of {len(per_hand_bb)} hands replayed",
        },
        "decisions": len(logs),
        "decisions_by_street": decisions_by_street,
        "decision_time_max_s": max(search_times) if search_times else float("nan"),
        "decision_time_p99_s": percentile(search_times, 0.99),
        "decision_time_median_s": percentile(search_times, 0.50),
        "decisions_truncated": sum(1 for log in logs if log.truncated),
        "decisions_starved": sum(1 for log in logs if log.starved),
        "rule_decisions": rule_decisions,
        "rule_agreed": agreed,
        "rule_agreement": (agreed / rule_decisions) if rule_decisions else float("nan"),
        "rule_time_max_s": max(rule_times) if rule_times else float("nan"),
        "win_rate_bb_per_100": win_rate,
        "win_rate_ci_low": low,
        "win_rate_ci_high": high,
        "bootstrap_resamples": resamples,
        "confidence": CONFIDENCE,
        "records_sha256": digest.hexdigest(),
        "wall_clock_s": elapsed,
        "started": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(started_wall)),
        "load_at_start": list(load_start),
        "load_at_end": list(load_end),
    }


def format_report(report: dict) -> str:
    """The run, in words, for someone who was not watching it."""
    interval = f"[{report['win_rate_ci_low']:+.1f}, {report['win_rate_ci_high']:+.1f}]"
    excludes = report["win_rate_ci_low"] > 0 or report["win_rate_ci_high"] < 0
    lines = [
        "pokerbot arena -- BUILD_PLAN.md T2, the first bot",
        f"  started            {report['started']}, commit {report['commit']}",
        f"  machine load       {report['load_at_start'][0]:.2f} at the start, "
        f"{report['load_at_end'][0]:.2f} at the end (1-minute average, what `uptime` prints first)",
        f"  table              {report['seats']} seats, blinds "
        f"{report['small_blind']}/{report['big_blind']}, seed {report['seed']}",
        f"  bot                {report['bot']} in seat {report['bot_seat']}, "
        f"{report['playouts_per_candidate']} finishes a move, "
        f"{report['budget_s'] * 1000:.0f} ms budget",
        f"  opponents          " + ", ".join(
            f"seat {seat}: {name}" for seat, name in sorted(report["opponents"].items())
        ),
        "",
        f"  hands played       {report['hands_played']}",
        f"  invariant failures {report['invariant_failures']}  "
        f"(checked: {' '.join(report['invariants_checked'])}; "
        f"I3 and I7 in part, I6 sampled -- see the module docstring)",
        f"  decisions          {report['decisions']} by the bot",
        f"  by street          " + ", ".join(
            f"{report['decisions_by_street'][name]} {where}"
            for name, where in zip(
                STREET_NAMES,
                ("before the flop", "on the flop", "on the turn", "on the river"),
            )
        ),
        f"  decision time      max {report['decision_time_max_s'] * 1000:.1f} ms, "
        f"p99 {report['decision_time_p99_s'] * 1000:.1f} ms, "
        f"median {report['decision_time_median_s'] * 1000:.1f} ms "
        f"(budget {report['budget_s'] * 1000:.0f} ms)",
        f"  searches cut short {report['decisions_truncated']} by the clock, "
        f"{report['decisions_starved']} with no finish at all",
        f"  equity rule        agreed with the bot on {report['rule_agreed']} of "
        f"{report['rule_decisions']} decisions "
        f"({report['rule_agreement'] * 100:.1f}%), slowest {report['rule_time_max_s'] * 1000:.1f} ms "
        f"-- logged, never played",
        "",
        f"  win rate           {report['win_rate_bb_per_100']:+.1f} big blinds per 100 hands",
        f"  95% interval       {interval} from {report['bootstrap_resamples']} bootstrap resamples"
        f" -- {'excludes' if excludes else 'INCLUDES'} zero",
        "",
        f"  hand records       sha256 {report['records_sha256']}",
        f"  wall clock         {report['wall_clock_s']:.1f} s",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Play the bot against the trivial opponents.")
    parser.add_argument("--seats", type=int, default=6)
    parser.add_argument("--hands", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260917)
    parser.add_argument("--bot", default="search", choices=["search"])
    parser.add_argument(
        "--opponents",
        default="random",
        help="one of fold, call, random -- or a comma-separated seat-by-seat list",
    )
    parser.add_argument("--bot-seat", type=int, default=0)
    parser.add_argument("--small-blind", type=int, default=50)
    parser.add_argument("--big-blind", type=int, default=100)
    parser.add_argument("--budget-ms", type=float, default=BUDGET_S * 1000)
    parser.add_argument("--playouts", type=int, default=PLAYOUTS_PER_CANDIDATE)
    parser.add_argument("--no-rule", action="store_true", help="skip the logged equity check")
    parser.add_argument("--replay-check-every", type=int, default=REPLAY_CHECK_EVERY)
    parser.add_argument("--resamples", type=int, default=BOOTSTRAP_RESAMPLES)
    parser.add_argument("--records-out", default=None, help="write every hand record here")
    parser.add_argument("--log-out", default=None, help="write the per-decision log here")
    parser.add_argument("--summary-out", default=None, help="write the report as JSON here")
    args = parser.parse_args(argv)

    try:
        report = run(
            seats=args.seats,
            hands=args.hands,
            seed=args.seed,
            bot=args.bot,
            opponents=[name.strip() for name in args.opponents.split(",")],
            bot_seat=args.bot_seat,
            small_blind=args.small_blind,
            big_blind=args.big_blind,
            budget_s=args.budget_ms / 1000.0,
            playouts_per_candidate=args.playouts,
            run_rule=not args.no_rule,
            replay_check_every=args.replay_check_every,
            resamples=args.resamples,
            records_out=args.records_out,
            log_out=args.log_out,
        )
    except InvariantViolation as violation:
        # EVALUATION_STRATEGY.md section 4.5: a failed invariant aborts the
        # run. Nothing measured up to here is reported, because it was
        # measured on a table that has just been shown to be wrong.
        print(f"ABORTED: {violation}", file=sys.stderr)
        return 2
    print(format_report(report))
    if args.summary_out:
        with open(args.summary_out, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
