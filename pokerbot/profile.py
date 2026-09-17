"""Print what the notebook has on one player.

    python -m pokerbot.profile "seat3_alias" --records hands.jsonl

The layout is `OPPONENT_MODEL_DESIGN.md` section 4.5's Tier 0 block, to the
column: the name in a twelve-wide field, the shrunk rate, the confidence the
count earns it, and the raw rate beside the two stats section 4.5 shows it
for. Nothing here decides anything; a profile is a description of a player,
and Tier 0 changes no play at all.

Two ways in, because the done-when has two halves:

* `--records <file>` reads hand records, one JSON object per line, as
  `pokerbot.arena --records-out` writes them, and counts them. `--names`
  says who sat where; without it the seats are called `seat0`, `seat1`, and
  so on, because a `HandRecord` stores seats and the names live outside it.
* `--counts <file>` reads counts that were taken somewhere else -- the shape
  section 4.5's worked example tabulates -- and prints the report they make.
  This is the path that shows the report format reproduces the worked
  example number for number from its counts.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from typing import Any

from . import notebook
from .notebook import (
    CONFIG,
    Notebook,
    NotebookConfig,
    Profile,
    UnusableHand,
    blind_view_from_dict,
    build_profile,
)

#: The rows section 4.5's block prints, in its order. `gap` is not a counted
#: stat: it is `vpip - pfr`, the difference of two already-shrunk rates, which
#: section 4.3 lists among the quantities nothing shrinks.
REPORT_ROWS: tuple[str, ...] = (
    "vpip",
    "pfr",
    "gap",
    "limp",
    "three_bet",
    "check_raise",
    "afq",
    "afq[flop]",
    "wtsd",
)

#: The two rows that print a raw rate beside the shrunk one.
WITH_RAW: tuple[str, ...] = ("vpip", "pfr")

#: The name column is twelve characters wide, which is what section 4.5's
#: block uses: `check_raise` is eleven and takes one space after it.
_WIDTH = 12


def render(profile: Profile) -> str:
    """Section 4.5's report block, for one profile."""
    lines = [f"  {'hands':<{_WIDTH}}{profile.hands}"]
    for row in REPORT_ROWS:
        if row == "gap":
            vpip = profile.reading("vpip")
            pfr = profile.reading("pfr")
            if vpip is None or pfr is None:
                continue
            lines.append(f"  {'gap':<{_WIDTH}}{vpip.rate - pfr.rate:.2f}")
            continue
        item = profile.reading(row)
        if item is None:
            continue
        text = f"  {row:<{_WIDTH}}{item.rate:.2f}  (conf {item.confidence:.2f})"
        if row in WITH_RAW and item.raw is not None:
            text += f"   raw {item.raw:.2f}"
        lines.append(text)
    bucket = profile.bucket
    if profile.near_boundary:
        # Section 4.4: a reader must see that a bucket is too close to call.
        bucket += f"  (near boundary on {', '.join(profile.near_boundary)})"
    lines.append(f"  {'bucket':<{_WIDTH}}{bucket}")
    # "none" rather than an empty line: a report that trails off is read as
    # broken, and no flag firing is a result in its own right.
    lines.append(f"  {'flags':<{_WIDTH}}{', '.join(profile.flags) or 'none'}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# the two ways in
# ---------------------------------------------------------------------------


def profile_from_counts(payload: Mapping[str, Any], config: NotebookConfig = CONFIG) -> Profile:
    """Build a profile from counts taken elsewhere.

    The file names the player, how many hands were dealt to them, and one
    entry per stat with its `k`, its `n` and the `BASELINE` it is shrunk
    towards -- exactly the columns section 4.5's table of counts carries.
    """
    readings = [
        notebook.reading(
            key,
            float(entry["k"]),
            float(entry["n"]),
            float(entry["baseline"]),
            baseline_source=str(entry.get("baseline_source", "given")),
        )
        for key, entry in sorted(payload["stats"].items())
    ]
    return build_profile(
        str(payload["player"]),
        str(payload.get("band", "all")),
        int(payload["hands"]),
        readings,
        vpip_split=float(payload.get("vpip_split", config.vpip_split)),
        afq_split=float(payload.get("afq_split", config.afq_split)),
        config=config,
    )


def read_records(path: str) -> list[dict[str, Any]]:
    """One hand record per line, as `--records-out` writes them."""
    hands = []
    with open(path, "r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                hands.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise UnusableHand(f"line {number} of {path} is not a hand record: {exc}") from exc
    return hands


def parse_names(text: str | None, seats: int) -> dict[int, str]:
    """`--names 0=ada,1=grace`, or `seat0`..`seatN` when nothing is given.

    Section 7 Q2: the identifier is the player's name. A `HandRecord` records
    seats, so the mapping from seat to name comes from outside it -- from the
    table's own player list. Nothing downstream ever keys on the seat.
    """
    if not text:
        return {seat: f"seat{seat}" for seat in range(seats)}
    names: dict[int, str] = {}
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        seat, _, name = part.partition("=")
        if not name:
            raise ValueError(f"--names wants seat=name pairs; {part!r} is not one")
        names[int(seat)] = name
    return names


def notebook_from_records(
    hands: Sequence[Mapping[str, Any]],
    names_text: str | None = None,
    config: NotebookConfig = CONFIG,
) -> Notebook:
    """Watch a whole file of hands, and hand back the notebook that watched."""
    book = Notebook(config)
    for payload in hands:
        view = blind_view_from_dict(payload)
        book.observe(view, parse_names(names_text, view.seats))
    return book


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pokerbot.profile",
        description="print the notebook's profile of one player",
    )
    parser.add_argument("name", help="the player's name, which is the identifier")
    parser.add_argument("--records", help="hand records, one JSON object per line")
    parser.add_argument("--counts", help="counts taken elsewhere, as one JSON object")
    parser.add_argument("--names", help="who sat where: 0=ada,1=grace")
    parser.add_argument("--band", help="report one seat-count band only: HU, SHORT, MID, FULL")
    parser.add_argument("--json", action="store_true", help="print the whole profile as JSON")
    args = parser.parse_args(argv)

    if bool(args.records) == bool(args.counts):
        parser.error("give exactly one of --records and --counts")

    if args.counts:
        with open(args.counts, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if str(payload.get("player", args.name)) != args.name:
            parser.error(
                f"{args.counts} holds counts for {payload.get('player')!r}, not {args.name!r}"
            )
        payload = dict(payload, player=args.name)
        profile = profile_from_counts(payload)
    else:
        book = notebook_from_records(read_records(args.records), args.names)
        try:
            profile = book.profile(args.name, args.band)
        except KeyError as exc:
            print(str(exc).strip('"'), file=sys.stderr)
            return 2

    if args.json:
        print(json.dumps(profile.as_dict(), sort_keys=True, indent=2))
    else:
        print(render(profile))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
