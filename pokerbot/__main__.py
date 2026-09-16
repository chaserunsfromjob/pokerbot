import argparse
from dataclasses import asdict
import json
from pathlib import Path

from .adapters import CANDIDATES
from .benchmark import correctness_failures, create_confirmation, run_confirmation
from .engine import replay
from .policies import EquityConfig
from .runner import tournament


def main():
    parser = argparse.ArgumentParser(description="Local play-chip poker research")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("tournament")
    run.add_argument("--out", required=True)
    run.add_argument("--seats", type=int, nargs="+", default=[6, 8, 9])
    run.add_argument("--seeds", type=int, nargs="+", default=[11, 23, 37])
    run.add_argument("--hands", type=int, default=36)
    run.add_argument("--samples", type=int, default=32)
    run.add_argument("--call-margin", type=float, default=.02)
    run.add_argument("--raise-margin", type=float, default=.12)
    run.add_argument("--bet-fraction", type=float, default=.5)
    run.add_argument("--learning", choices=["off", "learned", "oracle"], default="off")
    run.add_argument("--pool", nargs="+", default=["caller", "tight", "aggressive", "equity"])
    run.add_argument("--stack-bb", type=int, default=100)
    play = commands.add_parser("replay")
    play.add_argument("path")
    commands.add_parser("candidates")
    commands.add_parser("check-gates")
    confirm = commands.add_parser("confirm")
    confirm.add_argument("--out", required=True)
    confirm.add_argument("--candidate", required=True, help="JSON file containing EquityConfig parameters")
    confirm.add_argument("--trials", type=int, default=30)
    confirm.add_argument("--hands", type=int, default=504)
    resume = commands.add_parser("resume")
    resume.add_argument("path")
    args = parser.parse_args()
    if args.command == "tournament":
        config = EquityConfig(args.samples, args.call_margin, args.raise_margin,
                              args.bet_fraction, args.learning != "off")
        report = tournament(args.out, seats=args.seats, seeds=args.seeds, hands=args.hands,
                            config=config, pool=args.pool, learning=args.learning, stack_bb=args.stack_bb)
        print(json.dumps({k: v for k, v in report.items() if k != "results"}, indent=2))
    elif args.command == "replay":
        count = 0
        with Path(args.path).open() as stream:
            for row in stream:
                replay(json.loads(row))
                count += 1
        print(f"Replayed {count} hands with identical actions, public events and payouts")
    elif args.command == "check-gates":
        failures = correctness_failures()
        print(json.dumps({"promotion_blockers": failures}, indent=2))
        raise SystemExit(bool(failures))
    elif args.command == "confirm":
        config = EquityConfig(**json.loads(Path(args.candidate).read_text()))
        print(json.dumps(create_confirmation(args.out, config, trials=args.trials, hands=args.hands), indent=2))
    elif args.command == "resume":
        print(json.dumps(run_confirmation(args.path), indent=2))
    else:
        print(json.dumps(CANDIDATES, indent=2))


if __name__ == "__main__":
    main()
