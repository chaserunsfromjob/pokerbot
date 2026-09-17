#!/usr/bin/env python3
"""Check every derived number in TABLE_SIZE_AND_SIZING_NOTES.md against its constants.

That document states a handful of constants -- the seat counts it ranges over,
the illustrative spread column, the illustrative Table C hand counts, the band
count, the bucket count, the bet sizes and the stack-to-pot ratios -- and then
derives six tables and a few multipliers from them. This script holds those
constants ONCE, recomputes every figure the document prints, and compares.

Exit status 0 means every printed figure matches. Exit status 1 prints one line
per figure that does not. Exit status 2 means the document was not found.

Standard library only. Run it from anywhere:

    python3 tools/check_table_size_numbers.py [path/to/TABLE_SIZE_AND_SIZING_NOTES.md]

Rule for anyone editing the document: change the constant here and the prose
there in the same edit, and let this script say whether the prose is still right.
This is the rule `OPPONENT_MODEL_DESIGN.md` §4.7 already states for its own
checker, `tools/check_design_numbers.py`, and the two should be merged into one
script once both documents are on the trunk branch.

A figure the document states in more than one place is checked in *every* place;
`Checker.every_occurrence` is how that question is asked, and `Checker.prose` is
only safe for a phrase that appears once. The standard this file is held to is
that mutating any figure in Tables 1-6, or either of the two multipliers, or
either solver-run count, makes this script exit 1.

Scope, stated plainly so the boundary is not guessed at: this script checks
Tables 1-6, the 4.5x blind-frequency ratio, the 2.25x `fold_to_steal`
multiplier and the 32- and 16-run solver counts. It does **not** check figures
quoted from `OPPONENT_MODEL_DESIGN.md` or from the Sources -- those are checked
by citation, not by arithmetic -- nor section numbers, dates or anchors.
"""

from __future__ import annotations

import re
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

DEFAULT_DOC = Path(__file__).resolve().parent.parent / "TABLE_SIZE_AND_SIZING_NOTES.md"

# ---------------------------------------------------------------------------
# CONSTANTS -- the single place every constant the document declares is written.
# Nothing below this block may hard-code one; it must read it from here.
# ---------------------------------------------------------------------------

# The seat-count range the operator requires, and the whole subject of section 1.
SEAT_COUNTS = [2, 3, 4, 5, 6, 7, 8, 9]

# Table 3 compares these pairs of seat counts, and names them this way.
SEAT_NAMES = {2: "heads-up", 3: "3-handed", 6: "6-max", 9: "9-max"}
COMPARISONS = [(9, 6), (9, 3), (9, 2), (6, 3), (6, 2), (3, 2)]

# Table 3's spread column. ILLUSTRATIVE: not measured and not cited, on the same
# footing as the p-hat anchors in OPPONENT_MODEL_DESIGN.md Table C.
SPREADS = [0.30, 0.50, 0.70]

# Table 4. The band count R1 recommends and the size-bucket count R8 recommends.
BANDS = 4
SIZE_BUCKETS = 4

# Table 4's base hand counts. ILLUSTRATIVE in OPPONENT_MODEL_DESIGN.md Table C,
# and illustrative here: (stat, interval half-width as printed, hands, is the
# stat one that the size buckets also split).
TABLE_C_ROWS = [
    ("vpip", "±5pp", 323, False),
    ("fold_to_cbet", "±10pp", 640, True),
]

# Table 5: the bet sizes, as fractions of the pot, and the two abstraction sizes
# an off-abstraction bet might wrongly be treated as.
BET_SIZES = [0.33, 0.50, 0.60, 0.75, 1.00, 1.50, 2.00]
ASSUMED_SIZES = [0.50, 1.00]
POT = 1.0

# Table 6: the stack-to-pot ratios, and the street counts to get all-in over.
SPRS = [1, 2, 4, 6, 10, 20]
STREET_COUNTS = [1, 2, 3]

# The Tier 1 solve budget in R6 and Q4: one base strategy plus three
# counter-strategies, run at each seat count.
STRATEGIES_PER_SEAT_COUNT = 4

# The seat ceiling of the vendored engine's 20-card deck, cited rather than
# derived: REFERENCE_NOTES.md:485-497. Q4 uses it to size the budget that engine
# could actually pay for.
VENDORED_ENGINE_SEAT_CEILING = 7

# ---------------------------------------------------------------------------
# The arithmetic the document derives, one function per claim.
# ---------------------------------------------------------------------------


def blind_frequency(n: int) -> float:
    """Share of hands dealt in a blind at a table of `n`."""
    return 2.0 / n


def button_frequency(n: int) -> float:
    return 1.0 / n


def neither_frequency(n: int) -> float:
    """Clamped at zero: unclamped it is negative at n = 2, and no share can be."""
    return max(0.0, (n - 3.0) / n)


def mean_players_behind(n: int) -> float:
    """Each 'players still to act behind' value 0..n-1 occurs exactly once."""
    return (n - 1) / 2.0


def total_variation(n: int, m: int) -> float:
    """Half the L1 distance between uniform weights on {0..n-1} and {0..m-1}."""
    hi, lo = max(n, m), min(n, m)
    shared = lo * abs(1.0 / hi - 1.0 / lo)
    unshared = (hi - lo) * (1.0 / hi)
    return 0.5 * (shared + unshared)


def required_equity(bet: float, pot: float = POT) -> float:
    """Pot equity needed to call a bet of `bet` into a pot of `pot`."""
    return bet / (pot + 2 * bet)


def all_in_fraction(spr: float, streets: int) -> float:
    """`f` solving (1 + 2f)^k = 1 + 2*SPR."""
    return ((1 + 2 * spr) ** (1.0 / streets) - 1) / 2.0


# ---------------------------------------------------------------------------
# Formatting: half-up to the precision the document prints at.
# ---------------------------------------------------------------------------

MINUS = "−"  # the document prints a real minus sign, not a hyphen.


def fmt(x: float, places: int, thousands: bool = False) -> str:
    quant = Decimal(1).scaleb(-places) if places else Decimal(1)
    d = Decimal(repr(float(x))).quantize(quant, rounding=ROUND_HALF_UP)
    return f"{d:,}" if thousands else str(d)


def pct(x: float, places: int = 1) -> str:
    return fmt(x * 100.0, places) + "%"


def signed_pp(x: float, places: int = 1) -> str:
    """A signed figure in percentage points; zero carries no sign."""
    body = fmt(abs(x) * 100.0, places)
    if Decimal(body) == 0:
        return body + "pp"
    return ("+" if x > 0 else MINUS) + body + "pp"


# ---------------------------------------------------------------------------
# Reading the document.
# ---------------------------------------------------------------------------


def clean_cell(cell: str) -> str:
    return cell.replace("**", "").replace("`", "").strip()


class Document:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.text = path.read_text(encoding="utf-8")
        self.lines = self.text.splitlines()
        self.flat = re.sub(r"\s+", " ", self.text)

    def table_after(self, locator: str) -> list[list[str]]:
        """The first markdown table whose start follows a line containing `locator`."""
        start = None
        for i, line in enumerate(self.lines):
            if locator in line:
                start = i
                break
        if start is None:
            raise LookupError(f"locator not found: {locator!r}")
        i = start
        while i < len(self.lines) and not self.lines[i].lstrip().startswith("|"):
            i += 1
        if i >= len(self.lines):
            raise LookupError(f"no table after locator: {locator!r}")
        rows = []
        while i < len(self.lines) and self.lines[i].lstrip().startswith("|"):
            cells = [c.strip() for c in self.lines[i].strip().strip("|").split("|")]
            if not all(set(c) <= set("- :") and c for c in cells):
                rows.append([clean_cell(c) for c in cells])
            i += 1
        return rows


# ---------------------------------------------------------------------------
# The checker.
# ---------------------------------------------------------------------------


class Checker:
    def __init__(self, doc: Document) -> None:
        self.doc = doc
        self.failures: list[str] = []
        self.checked = 0

    def equal(self, what: str, expected, actual) -> None:
        self.checked += 1
        if str(expected) != str(actual):
            self.failures.append(
                f"{what}: document says {actual!r}, constants give {expected!r}"
            )

    def prose(self, what: str, phrase: str) -> None:
        """Assert an exact phrase, carrying a derived figure, appears once in the prose."""
        self.checked += 1
        flat_phrase = re.sub(r"\s+", " ", phrase)
        if flat_phrase not in self.doc.flat:
            self.failures.append(f"{what}: document does not contain {flat_phrase!r}")

    def every_occurrence(self, what: str, pattern: str, expected: str) -> None:
        """Assert *every* place the document states this figure states it the same.

        `prose` only asks that one occurrence is right, so a figure the document
        repeats can go stale in every copy but one and still pass.
        """
        self.checked += 1
        found = [
            tuple(g for g in m.groups() if g is not None)
            for m in re.finditer(pattern, self.doc.flat)
        ]
        if not found:
            self.failures.append(f"{what}: document states it nowhere (pattern {pattern!r})")
            return
        wrong = [g for g in found if any(v != expected for v in g)]
        if wrong:
            self.failures.append(
                f"{what}: {len(wrong)} of {len(found)} occurrences disagree -- "
                f"document says {wrong!r}, constants give {expected!r}"
            )

    # -- Table 1 ----------------------------------------------------------
    def check_table_1(self) -> None:
        rows = self.doc.table_after("#### Table 1: what seat count mechanically fixes")[1:]
        self.equal("Table 1 row count", len(SEAT_COUNTS), len(rows))
        for n, row in zip(SEAT_COUNTS, rows):
            tag = f"Table 1 n={n}"
            self.equal(f"{tag} seat count", str(n), row[0])
            self.equal(f"{tag} dealt in a blind", fmt(blind_frequency(n), 3), row[1])
            self.equal(f"{tag} on the button", fmt(button_frequency(n), 3), row[2])
            self.equal(f"{tag} neither blind nor button", fmt(neither_frequency(n), 3), row[3])
            self.equal(f"{tag} mean players behind", fmt(mean_players_behind(n), 1), row[4])

    # -- Table 2 ----------------------------------------------------------
    def check_table_2(self) -> None:
        table = self.doc.table_after(
            "#### Table 2: how far apart two seat counts are, as positional mixtures"
        )
        header, rows = table[0], table[1:]
        self.equal("Table 2 column count", len(SEAT_COUNTS) + 1, len(header))
        self.equal("Table 2 row count", len(SEAT_COUNTS), len(rows))
        for n, row in zip(SEAT_COUNTS, rows):
            self.equal(f"Table 2 row label {n}", str(n), row[0])
            for m, cell in zip(SEAT_COUNTS, row[1:]):
                self.equal(f"Table 2 TV({n},{m})", fmt(total_variation(n, m), 3), cell)

    def check_adjacent_seat_claim(self) -> None:
        """R1: the distance between adjacent seat counts is exactly 1/(n+1)."""
        ok = all(
            abs(total_variation(n, n + 1) - 1.0 / (n + 1)) < 1e-12
            for n in SEAT_COUNTS[:-1]
        )
        self.checked += 1
        if not ok:
            self.failures.append(
                "R1 adjacent-seat distance: TV(n, n+1) is not 1/(n+1) for every n in range"
            )
        self.prose(
            "R1 across-band step 4|5",
            f"`4|5`\n({fmt(total_variation(4, 5), 3)})",
        )
        self.prose(
            "R1 across-band step 6|7",
            f"`6|7` (0{fmt(total_variation(6, 7), 3)[1:]})",
        )
        self.prose(
            "R1 within-band step 3|4",
            f"within-band step `3|4`\n({fmt(total_variation(3, 4), 3)})",
        )

    # -- Table 3 ----------------------------------------------------------
    def check_table_3(self) -> None:
        rows = self.doc.table_after(
            "#### Table 3: the swing that costs nothing but a change of seat count"
        )
        header, body = rows[0], rows[1:]
        for spread, cell in zip(SPREADS, header[2:]):
            self.equal(f"Table 3 spread header {spread}", f"Spread {fmt(spread, 2)}", cell)
        self.equal("Table 3 row count", len(COMPARISONS), len(body))
        for (n, m), row in zip(COMPARISONS, body):
            tag = f"Table 3 {n} vs {m}"
            self.equal(
                f"{tag} label", f"{SEAT_NAMES[n]} vs {SEAT_NAMES[m]}", row[0]
            )
            tv = total_variation(n, m)
            self.equal(f"{tag} TV", fmt(tv, 3), row[1])
            for spread, cell in zip(SPREADS, row[2:]):
                self.equal(
                    f"{tag} bound at spread {spread}",
                    f"≤ {fmt(tv * spread, 3)}",
                    cell,
                )

    def check_table_3_prose(self) -> None:
        """The 9-max-versus-3-handed bound §1.2 and R2 quote back."""
        tv = total_variation(9, 3)
        lo, hi = fmt(tv * min(SPREADS), 1), fmt(tv * max(SPREADS), 2)
        self.prose(
            "9-max vs 3-handed bound quoted in §1.2",
            f"A bound of\n`{lo}`–`{hi}` between 9-max and 3-handed",
        )

    # -- Table 4 ----------------------------------------------------------
    def check_table_4(self) -> None:
        rows = self.doc.table_after("#### Table 4: the fragmentation multiplier")[1:]
        self.equal("Table 4 row count", len(TABLE_C_ROWS), len(rows))
        for (stat, width, hands, bucketed), row in zip(TABLE_C_ROWS, rows):
            tag = f"Table 4 {stat}"
            self.equal(f"{tag} label", f"{stat} ({width})", row[0])
            self.equal(f"{tag} base hands", fmt(hands, 0, thousands=True), row[1])
            self.equal(
                f"{tag} banded", fmt(hands * BANDS, 0, thousands=True), row[2]
            )
            self.equal(
                f"{tag} size-bucketed",
                fmt(hands * SIZE_BUCKETS, 0, thousands=True) if bucketed else "n/a",
                row[3],
            )
            both = hands * BANDS * SIZE_BUCKETS if bucketed else hands * BANDS
            self.equal(f"{tag} both", fmt(both, 0, thousands=True), row[4])

    def check_table_4_prose(self) -> None:
        """§2.5 restates the fold_to_cbet row; both copies must agree."""
        _, _, hands, _ = TABLE_C_ROWS[1]
        self.prose(
            "§2.5 restatement of Table 4's fold_to_cbet row",
            f"at roughly\n{fmt(hands * SIZE_BUCKETS, 0, thousands=True)} hands under a "
            f"four-way split, against the illustrative {fmt(hands, 0)} unsplit",
        )

    # -- the two multipliers ---------------------------------------------
    def check_multipliers(self) -> None:
        ratio = blind_frequency(2) / blind_frequency(9)
        self.every_occurrence(
            "4.5x blind-frequency ratio",
            r"([\d.]+) times higher heads-up than at 9-max",
            fmt(ratio, 1),
        )
        self.prose(
            "4.5x ratio read off Table 1's first column",
            f"`{fmt(blind_frequency(2), 3)}`\nagainst `{fmt(blind_frequency(9), 3)}` "
            "in Table 1's first column",
        )
        self.prose(
            "4.5x provenance arithmetic",
            f"`(2/2)/(2/9) = {fmt(ratio, 1)}`",
        )
        # At n = 2 only the big blind can defend, so half the blind hands are
        # opportunities; at 9-max the blind frequency is unrestricted.
        heads_up_rate = blind_frequency(2) / 2
        multiplier = (1 / blind_frequency(9)) / (1 / heads_up_rate)
        self.every_occurrence(
            "2.25x fold_to_steal multiplier",
            r"([\d.]+) times as many hands at 9-max as heads-up",
            fmt(multiplier, 2),
        )
        self.prose(
            "2.25x does not bound the multiplier either",
            f"so {fmt(multiplier, 2)} does not bound it either",
        )
        self.prose(
            "2.25x restated in R4",
            f"stat actually pays is nearer **{fmt(multiplier, 2)}×**",
        )
        self.prose(
            "2.25x provenance arithmetic",
            f"`(1/(2/9))/(1/(1/2)) = {fmt(multiplier, 2)}`",
        )

    # -- Table 5 ----------------------------------------------------------
    def check_table_5(self) -> None:
        rows = self.doc.table_after(
            "#### Table 5: what mis-reading a bet size costs, exactly"
        )[1:]
        self.equal("Table 5 row count", len(BET_SIZES), len(rows))
        for bet, row in zip(BET_SIZES, rows):
            tag = f"Table 5 bet={bet}"
            self.equal(f"{tag} bet size", fmt(bet, 2), row[0])
            true_equity = required_equity(bet)
            self.equal(f"{tag} true required equity", pct(true_equity), row[1])
            for assumed, cell in zip(ASSUMED_SIZES, row[2:]):
                self.equal(
                    f"{tag} error if treated as {assumed} pot",
                    signed_pp(true_equity - required_equity(assumed)),
                    cell,
                )

    # -- Table 6 ----------------------------------------------------------
    def check_table_6(self) -> None:
        rows = self.doc.table_after(
            "#### Table 6: pot fraction needed to reach all-in in `k` equal bets"
        )[1:]
        self.equal("Table 6 row count", len(SPRS), len(rows))
        for spr, row in zip(SPRS, rows):
            self.equal(f"Table 6 SPR label {spr}", str(spr), row[0])
            for k, cell in zip(STREET_COUNTS, row[1:]):
                self.equal(
                    f"Table 6 SPR={spr} f in {k} street(s)",
                    fmt(all_in_fraction(spr, k), 2),
                    cell,
                )

    # -- the solver-run counts -------------------------------------------
    def check_solver_runs(self) -> None:
        full = len(SEAT_COUNTS) * STRATEGIES_PER_SEAT_COUNT
        banded = BANDS * STRATEGIES_PER_SEAT_COUNT
        self.every_occurrence(
            "32 offline solver runs",
            r"(\d+) (?:offline )?solver runs",
            str(full),
        )
        self.prose(
            "32-run provenance arithmetic",
            f"{len(SEAT_COUNTS)} seat counts × {STRATEGIES_PER_SEAT_COUNT} strategies, "
            f"and {BANDS} bands × {STRATEGIES_PER_SEAT_COUNT} strategies",
        )
        # Q4 writes the same count in words once. The digit pattern above cannot
        # see that copy, so it would survive a change to the constants silently.
        self.every_occurrence(
            "32 runs spelled out in Q4",
            r"(\w+(?:-\w+)?) runs are inside that cap",
            spell(full).capitalize(),
        )
        self.every_occurrence(
            "16 runs under banding",
            r"one representative seat count per band, (\d+) runs",
            str(banded),
        )
        self.prose(
            "16 versus 32 in R6",
            f"because {banded} multi-day runs breach the cap exactly as {full} do",
        )
        reachable = [n for n in SEAT_COUNTS if n <= VENDORED_ENGINE_SEAT_CEILING]
        self.prose(
            "Q4's budget on the vendored engine's seat ceiling",
            f"are 2 through {VENDORED_ENGINE_SEAT_CEILING}, which is "
            f"**{spell(len(reachable))}** of the {spell(len(SEAT_COUNTS))} — a budget of "
            f"**{len(reachable) * STRATEGIES_PER_SEAT_COUNT} runs, not\n{full}**",
        )

    def run(self) -> None:
        checks = [
            ("Table 1", self.check_table_1),
            ("Table 2", self.check_table_2),
            ("adjacent-seat distance claim", self.check_adjacent_seat_claim),
            ("Table 3", self.check_table_3),
            ("Table 3 prose", self.check_table_3_prose),
            ("Table 4", self.check_table_4),
            ("Table 4 prose", self.check_table_4_prose),
            ("blind-frequency and fold_to_steal multipliers", self.check_multipliers),
            ("Table 5", self.check_table_5),
            ("Table 6", self.check_table_6),
            ("solver-run counts", self.check_solver_runs),
        ]
        for name, check in checks:
            try:
                check()
            except LookupError as exc:
                # A table the document is supposed to carry has moved or gone;
                # that is a mismatch too, not a crash.
                self.checked += 1
                self.failures.append(f"{name}: cannot be checked -- {exc}")


def spell(n: int) -> str:
    """The document writes some counts out in words; this builds the same word.

    Q4 writes the full solver-run count as "Thirty-two", which no digit-matching
    pattern can see, so the phrase has to be built from the constants too.
    """
    words = {
        1: "one",
        2: "two",
        3: "three",
        4: "four",
        5: "five",
        6: "six",
        7: "seven",
        8: "eight",
        9: "nine",
        10: "ten",
        11: "eleven",
        12: "twelve",
        13: "thirteen",
        14: "fourteen",
        15: "fifteen",
        16: "sixteen",
        17: "seventeen",
        18: "eighteen",
        19: "nineteen",
    }
    tens = {
        2: "twenty",
        3: "thirty",
        4: "forty",
        5: "fifty",
        6: "sixty",
        7: "seventy",
        8: "eighty",
        9: "ninety",
    }
    if n in words:
        return words[n]
    if 20 <= n <= 99:
        ten, unit = divmod(n, 10)
        return tens[ten] if unit == 0 else f"{tens[ten]}-{words[unit]}"
    return str(n)


def main(argv: list[str]) -> int:
    # The failure lines quote the document's own characters -- "<=" as the real
    # sign in Table 3, the real minus sign in Table 5 -- and a plain Windows
    # console is cp1252, where `print` raises UnicodeEncodeError and the detail
    # lines are lost while the exit code still reads 1, which disguises the
    # crash as an ordinary mismatch. trunk's tools/check_design_numbers.py has
    # the same shape; carry this line over when the two scripts are merged.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_DOC
    if not path.exists():
        print(f"table-size notes not found: {path}", file=sys.stderr)
        return 2
    checker = Checker(Document(path))
    checker.run()
    if checker.failures:
        print(
            f"{len(checker.failures)} of {checker.checked} figures in {path.name} do not match:"
        )
        for failure in checker.failures:
            print(f"  - {failure}")
        return 1
    print(f"{checker.checked} figures in {path.name} all match the constants they derive from.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
