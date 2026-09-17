#!/usr/bin/env python3
"""Count seat and stack fields in one HandHQ sample file per network.

Backs the per-network measurements in `RESOURCES_EXPLOITATION.md` §3.1. It
fetches one ~1,000-hand `.phhs` file for each of the six networks in
`uoftcprg/phh-dataset` straight from `raw.githubusercontent.com`, then counts,
per file:

* how many hands there are;
* how many carry a `seat_count` field, and its values (chairs at the table);
* how many carry a `seats` field (the seat numbers the dealt-in players hold);
* the distribution of dealt-in player counts (the length of `players`);
* for each dealt-in count, how many of those hands carry `seat_count` — the
  shape of the coverage, not just its total;
* the 8- and 9-handed share of the file;
* how many hands have every entry of `starting_stacks` equal to `inf`.

No poker judgment happens here: it is counting fields in a text file. Run with
no arguments to reproduce `research/phh_network_counts.txt`:

    python3 research/count_phh_networks.py

Files are cached under the directory given by `--cache` so a re-run does not
re-download.
"""

from __future__ import annotations

import argparse
import collections
import datetime
import pathlib
import re
import ssl
import sys
import urllib.parse
import urllib.request

RAW_BASE = "https://raw.githubusercontent.com/uoftcprg/phh-dataset/main/data/handhq"

# One file per network, each the `handhq_1` slice of one stake.
SAMPLES = (
    ("PokerStars", "PS-2009-07-01_2009-07-23_25NLH_OBFU/0.25/ps NLH handhq_1-OBFUSCATED.phhs"),
    ("iPoker", "IPN-2009-07-01_2009-07-23_100NLH_OBFU/1/ipn NLH handhq_1-OBFUSCATED.phhs"),
    ("PartyPoker", "PTY-2009-07-01_2009-07-23_400NLH_OBFU/4/pty NLH handhq_1-OBFUSCATED.phhs"),
    ("Full Tilt", "FTP-2009-07-01_2009-07-23_50NLH_OBFU/0.5/ftp NLH handhq_1-OBFUSCATED.phhs"),
    ("Absolute Poker", "ABS-2009-07-01_2009-07-23_100NLH_OBFU/1/abs NLH handhq_1-OBFUSCATED.phhs"),
    ("Ongame", "ONG-2009-07-01_2009-07-23_400NLH_OBFU/4/ong NLH handhq_1-OBFUSCATED.phhs"),
)

FIELDS = ("seat_count", "seats", "players", "starting_stacks")

HAND_HEADER = re.compile(r"^\[\d+\]$")
FIELD_LINE = re.compile(r"^(\w+) = (.*)$")


def tls_context() -> ssl.SSLContext:
    """Return a verifying TLS context, preferring certifi's trust store.

    A framework Python on macOS often has no certificate bundle of its own.
    """
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def fetch(path: str, cache: pathlib.Path) -> str:
    """Return the text of one `.phhs` file, downloading it once."""
    cache.mkdir(parents=True, exist_ok=True)
    local = cache / path.replace("/", "_")
    if not local.exists():
        url = f"{RAW_BASE}/{urllib.parse.quote(path)}"
        request = urllib.request.Request(url)  # noqa: S310 - fixed https host
        with urllib.request.urlopen(request, context=tls_context()) as response:  # noqa: S310
            local.write_bytes(response.read())
    return local.read_text(encoding="utf-8")


def hands(text: str):
    """Yield one dict of raw field strings per hand in a `.phhs` file."""
    current = None
    for line in text.splitlines():
        if HAND_HEADER.match(line):
            if current is not None:
                yield current
            current = {}
            continue
        if current is None:
            continue
        match = FIELD_LINE.match(line)
        if match and match.group(1) in FIELDS:
            current[match.group(1)] = match.group(2)
    if current is not None:
        yield current


def n_items(raw: str) -> int:
    """Return the number of entries in a TOML-style inline list."""
    inner = raw.strip()[1:-1].strip()
    return 0 if not inner else inner.count(",") + 1


def report(name: str, path: str, cache: pathlib.Path, out) -> None:
    """Print one network's counts."""
    text = fetch(path, cache)
    total = 0
    seat_count_present = 0
    seat_count_values: collections.Counter[str] = collections.Counter()
    seats_present = 0
    seats_max_equals_seat_count = 0
    seats_max_exceeds_seat_count = 0
    dealt_in: collections.Counter[int] = collections.Counter()
    dealt_in_with_seat_count: collections.Counter[int] = collections.Counter()
    stacks_present = 0
    all_inf_stacks = 0

    for hand in hands(text):
        total += 1
        if "seat_count" in hand:
            seat_count_present += 1
            seat_count_values[hand["seat_count"].strip()] += 1
            if "players" in hand:
                dealt_in_with_seat_count[n_items(hand["players"])] += 1
        if "seats" in hand:
            seats_present += 1
        if "seats" in hand and "seat_count" in hand:
            highest = max(int(v) for v in hand["seats"].strip()[1:-1].split(","))
            declared = int(hand["seat_count"])
            seats_max_equals_seat_count += highest == declared
            seats_max_exceeds_seat_count += highest > declared
        if "players" in hand:
            dealt_in[n_items(hand["players"])] += 1
        if "starting_stacks" in hand:
            stacks_present += 1
            values = [v.strip() for v in hand["starting_stacks"].strip()[1:-1].split(",")]
            if values and all(v == "inf" for v in values):
                all_inf_stacks += 1

    eight, nine = dealt_in[8], dealt_in[9]
    both = eight + nine
    print(f"== {name}", file=out)
    print(f"   file: {path}", file=out)
    print(f"   hands: {total}", file=out)
    print(
        f"   seat_count present: {seat_count_present}/{total}"
        f"   values: {dict(sorted(seat_count_values.items()))}",
        file=out,
    )
    print(f"   seats (occupied-seat numbers) present: {seats_present}/{total}", file=out)
    if seat_count_present:
        print(
            f"   max(seats) == seat_count: {seats_max_equals_seat_count}"
            f"/{seat_count_present}   max(seats) > seat_count: {seats_max_exceeds_seat_count}",
            file=out,
        )
    print(f"   dealt-in counts (len(players)): {dict(sorted(dealt_in.items()))}", file=out)
    coverage = {
        size: f"{dealt_in_with_seat_count[size]}/{count}"
        for size, count in sorted(dealt_in.items())
    }
    print(f"   seat_count present by dealt-in count: {coverage}", file=out)
    print(
        f"   8-handed: {eight}   9-handed: {nine}   8+9: {both}/{total}"
        f" = {100.0 * both / total:.1f}%",
        file=out,
    )
    print(f"   starting_stacks all inf: {all_inf_stacks}/{stacks_present}", file=out)
    print(file=out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache",
        default=pathlib.Path.home() / ".cache" / "phh-dataset-samples",
        type=pathlib.Path,
        help="directory to keep the downloaded .phhs files in",
    )
    args = parser.parse_args()

    out = sys.stdout
    print(
        "phh-dataset HandHQ samples, one file per network, counted "
        f"{datetime.date.today().isoformat()} by research/count_phh_networks.py",
        file=out,
    )
    print(f"source: {RAW_BASE}", file=out)
    print(file=out)
    for name, path in SAMPLES:
        report(name, path, args.cache, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
