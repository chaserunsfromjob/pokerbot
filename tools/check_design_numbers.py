#!/usr/bin/env python3
"""Check every derived number in OPPONENT_MODEL_DESIGN.md against its constants.

The design document states a handful of constants and then derives a few hundred
figures from them: five tables, a flag margin-versus-interval table, a worked
profile example, and a scattering of figures in the prose. Six review rounds in a
row found a derived figure that no longer matched the constant it came from.

This script exists so that class of defect is found by a machine instead. Every
constant the document declares is held ONCE, here, in the CONSTANTS section
below. Everything else is recomputed from those constants and compared against
what the document prints. Exit status 0 means every printed figure matches; exit
status 1 prints one line per figure that does not.

Standard library only. Run it from anywhere:

    python3 tools/check_design_numbers.py [path/to/OPPONENT_MODEL_DESIGN.md]

Rule for anyone editing the document: change the constant here and the prose
there in the same edit, and let this script say whether the prose is still right.

Second rule, learned the hard way: a figure the document states in more than one
place has to be checked in *every* place. Asking only that some copy is right
lets every other copy go stale unnoticed. `Checker.every_occurrence` is how that
question is asked; `Checker.prose` is only safe for a phrase that appears once.
The standard this file is held to is that mutating any derived figure in the
document, anywhere, makes this script exit 1.
"""

from __future__ import annotations

import math
import re
import sys
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP
from pathlib import Path

# ---------------------------------------------------------------------------
# CONSTANTS -- the single place every constant the document declares is written.
# Nothing below this block may hard-code a design constant; it must read it here.
# ---------------------------------------------------------------------------

# 95% two-sided normal quantile, the only statistical constant in the document.
Z95 = 1.96

# Shrinkage / confidence: rate = (BASELINE*s + k)/(s + n); confidence = n/(n + s).
PRIOR_STRENGTH = {
    # Tier A -- one opportunity per hand dealt.
    "vpip": 50,
    "pfr": 50,
    "limp": 50,
    # Tier B -- a few opportunities per ten hands.
    "three_bet": 25,
    "fold_to_three_bet": 25,
    "fold_to_steal": 25,
    "cbet": 25,
    "fold_to_cbet": 25,
    "afq": 25,
    "check_raise": 25,
    "open_raise": 25,
    # Tier C -- slow but high-value.
    "wtsd": 15,
    "wsd": 15,
    "fold_to_river_bet": 15,
}

# The stat groups the PRIOR_STRENGTH table prints, in the order it prints them.
PRIOR_STRENGTH_GROUPS = [
    ("Tier A", 50, ["vpip", "pfr", "limp"]),
    (
        "Tier B",
        25,
        [
            "three_bet",
            "fold_to_three_bet",
            "fold_to_steal",
            "cbet",
            "fold_to_cbet",
            "afq",
            "check_raise",
            "open_raise",
        ],
    ),
    ("Tier C", 15, ["wtsd", "wsd", "fold_to_river_bet"]),
]

# Stats the document names that deliberately have no PRIOR_STRENGTH, because
# nothing shrinks them. Every stat in the section 4.2 table must be in exactly
# one of this set or PRIOR_STRENGTH.
NO_PRIOR_STRENGTH = {
    "hands_dealt",
    "af_bets_raises",
    "af_calls",
    "vpip_pfr_gap",
    "showdown_holdings",
    "stack_bb",
    "hands_since_last_seen",
    "session_net_bb",
}

# Classification (section 4.4).
VPIP_SPLIT = 0.28
AFQ_SPLIT = 0.50
CLASSIFY_CONF_GATE = 0.5
MIN_CLASSIFY_HANDS = 50
HYSTERESIS_BAND = 0.02
HYSTERESIS_HOLD = 10

# Warm-up and decay (sections 4.3 and 5.2).
WARMUP_HANDS = 200
HALF_LIFE = 2000
HALF_LIFE_BASE = 0.5  # the base the decay halves by, per HALF_LIFE hands

# Pool gates (section 4.3).
MIN_POOL_HANDS = 200
MIN_POOL_OPPONENTS = 20

# Exploit flags (section 4.4). "above"/"below" is the side of BASELINE the
# shrunk rate must sit on by at least `margin`, with `confidence >= gate`.
FLAGS = {
    "OVERFOLDS_TO_3BET": {"stats": ["fold_to_three_bet"], "margin": 0.15, "gate": 0.6, "side": "above"},
    "NEVER_FOLDS_TO_3BET": {"stats": ["fold_to_three_bet"], "margin": 0.15, "gate": 0.6, "side": "below"},
    "OVERFOLDS_TO_CBET": {"stats": ["fold_to_cbet[flop]"], "margin": 0.15, "gate": 0.6, "side": "above"},
    "NEVER_FOLDS_POSTFLOP": {"stats": ["wtsd"], "margin": 0.15, "gate": 0.6, "side": "above"},
    "OVERFOLDS_BLINDS": {"stats": ["fold_to_steal"], "margin": 0.15, "gate": 0.6, "side": "above"},
    "NEVER_RAISES": {"stats": ["three_bet", "check_raise"], "margin": 0.05, "gate": 0.7, "side": "below"},
    "LIMPS": {"stats": ["limp"], "margin": 0.15, "gate": 0.6, "side": "above"},
}

# Table A -- bet sizes as a fraction of the pot.
BET_SIZES = [0.25, 0.33, 0.50, 0.66, 0.75, 1.00, 1.50, 2.00]

# Table B -- per-opponent fold rates and opponent counts.
FOLD_RATES = [0.50, 0.60, 0.70, 0.80, 0.90]
OPPONENT_COUNTS = [1, 2, 3, 4, 5]

# Table C -- illustrative anchors, opportunity rates, and target widths.
# `rate` 1.00 is not a placeholder: it is the bound forced by section 4.2's
# "was dealt in and the hand was not a walk" denominator, which section 4.7
# row 2 fixes on the authority of escalation 241e2f235c94. The rate a real
# population would show is 1.00 less its walk rate, so the table prints 1.00 as
# an upper bound and its last column says so.
# Two rates are measured (below); the rest are placeholders.
PLACEHOLDER_RATES = {0.08, 0.15}
DEALT_IN_STATS = {"vpip", "pfr"}
# Measured per-hand opportunity rates: the nine-handed pooled figures in
# OPPONENT_BASELINE.md section 2's pooled table, whose "FtCB chances per hand"
# and "Flops seen per hand" columns are exactly these two stats' section 4.2
# denominators, over its 70,685 nine-handed hands. Measured on the sample that
# document's section 1 describes (no PartyPoker, leaning high-stakes); adopting
# them is its section 5 recommendation 2. A measured rate is printed to three
# decimals, the precision it was measured to; a placeholder prints to two.
MEASURED_RATES = {"fold_to_cbet": 0.030, "wtsd": 0.187}
# The "Where the rate comes from" cell each kind of rate carries, as the table
# prints it once backticks and bold markers are stripped by `clean_cell`.
RATE_SOURCE_MEASURED = "measured, OPPONENT_BASELINE.md §2, nine-handed"
RATE_SOURCE_PLACEHOLDER = "illustrative placeholder"
RATE_SOURCE_DEALT_IN = "one per hand dealt, less the walk rate: an upper bound (§4.7 row 2)"
# The postflop rows, which section 4.2's `three_bet` sentence claims to be
# nearer than `three_bet` itself.
POSTFLOP_STATS = {"fold_to_cbet", "wtsd"}
# Where the two measured rates are cited from, and how to find them there, so a
# rate re-measured in that document cannot leave a stale copy here.
BASELINE_SOURCE = "OPPONENT_BASELINE.md"
BASELINE_SECTION = "## 2. Corpus A: the 2009 no-limit population, per table size"
BASELINE_POOLED_TABLE = "**The pooled rate**"
BASELINE_SEATS = "9"  # the nine-handed row, the table size this design cites
BASELINE_COLUMNS = {  # Table C stat -> the pooled table's column heading
    "fold_to_cbet": "FtCB chances per hand",
    "wtsd": "Flops seen per hand",
}
BASELINE_NINE_HANDED_HANDS = "70,685"  # quoted beside the rates in section 4.2
TABLE_C_ROWS = [
    # (stat, anchor p-hat, opportunities per hand, target half-width)
    ("vpip", 0.30, 1.00, 0.05),
    ("vpip", 0.30, 1.00, 0.03),
    ("pfr", 0.20, 1.00, 0.05),
    ("three_bet", 0.07, 0.15, 0.02),
    ("fold_to_three_bet", 0.60, 0.08, 0.10),
    ("fold_to_cbet", 0.50, MEASURED_RATES["fold_to_cbet"], 0.10),
    ("wtsd", 0.25, MEASURED_RATES["wtsd"], 0.05),
]
# The anchor each stat is read at wherever an interval is taken for it.
TABLE_C_ANCHORS = {stat: p for stat, p, _rate, _w in TABLE_C_ROWS}
# Stats with no Table C anchor are read at the least favourable p-hat.
LEAST_FAVOURABLE_P = 0.5
# The p-hat range section 4.2 claims the interval width barely moves across, and
# what "barely" is allowed to mean, as a share of the widest interval.
PHAT_FLAT_RANGE = (0.2, 0.8)
PHAT_FLAT_TOLERANCE = 0.25

# Table D -- the confidence-weight illustration.
TABLE_D_N = [1, 2, 5, 10, 25, 50, 100, 250, 500]
TABLE_D_S = [5, 10, 15, 25, 50]

# Table E -- the shrinkage-in-practice illustration.
TABLE_E_ROWS = [
    # (baseline, prior strength, k, n)
    (0.25, 25, 10, 20),
    (0.25, 25, 30, 40),
    (0.60, 25, 18, 20),
    (0.60, 25, 2, 20),
]

# Edge cases and validation (sections 4.7 and 6).
MIN_STACK_BB = 5
V3_HOLDOUT = (70, 30)

# Tier 1 solve plan (section 4.5 and E5).
SEAT_COUNTS = list(range(2, 10))  # 2 to 9 players inclusive
STRATEGIES = ["S_BASE", "S_VS_STATION", "S_VS_MANIAC", "S_VS_ROCK"]
BASE_STRATEGY = "S_BASE"  # the one a dropped seat count still needs
NO_COUNTER_STRATEGY = "S_VS_TAG"  # listed in the table, deliberately never solved
MAJORITY_RULE = "⌈2n/3⌉"  # the share of the live field that must share a bucket

# The two run costs section 4.5 works the cap against, and the day they divide
# into. Neither is a measured figure; they are the two illustrative rates the
# prose names ("ten minutes each", "an hour each").
SOLVE_ILLUSTRATION_MINUTES = 10
SOLVE_ILLUSTRATION_HOURS = 1
HOURS_PER_DAY = 24

# The operator's table-size priority (2026-09-15), quoted where section 4.5 uses
# it. Not a derived figure: it fixes the order of the solve plan, nothing else.
SEAT_PRIORITY_QUOTE = (
    "i will be playing mostly 6 player tables, followed by 8 or 9 player tables "
    "which can honestly be treated the same, they are so close"
)
SEAT_PRIORITY_TASK = "65bba741bf40"
SEAT_PRIORITY_SOURCE = f"recorded as heater task `{SEAT_PRIORITY_TASK}`"
SEAT_PRIORITY_ORDER = [6, 8, 9]  # 6 first, then 8 and 9 as one band, then the rest

# The Tier 0 worked example: one coherent 412-hand history. Everything the
# example prints is derived from these counts.
EXAMPLE_HANDS = 412
EXAMPLE_ALIAS = "seat3_alias"
EXAMPLE_COUNTS = {
    # stat (with context where the document prints one): (k, n, assumed BASELINE)
    "vpip": (177, 412, 0.30),
    "pfr": (41, 412, 0.20),
    "limp": (106, 250, 0.15),
    "three_bet": (0, 63, 0.07),
    "check_raise": (0, 140, 0.06),
    "afq": (92, 768, 0.30),
    "afq[flop]": (27, 168, 0.30),
    "wtsd": (89, 205, 0.25),
    "fold_to_three_bet": (5, 9, 0.60),
    "fold_to_cbet[flop]": (14, 62, 0.50),
    "fold_to_steal": (19, 55, 0.50),
}
# Rows printed in the report block, in order, and whether a raw rate is shown.
EXAMPLE_PRINTED = [
    ("vpip", True),
    ("pfr", True),
    ("limp", False),
    ("three_bet", False),
    ("check_raise", False),
    ("afq", False),
    ("afq[flop]", False),
    ("wtsd", False),
]
EXAMPLE_BUCKET = "STATION"
# How the example's 177 voluntary investments break down, in the order the prose
# states them. Must sum to the vpip numerator.
EXAMPLE_VPIP_BREAKDOWN = [("limps", 106), ("preflop raises", 41), ("calls of a raise", 30)]
# The 63 open raises faced, split the way the prose splits them. Must sum to the
# three_bet denominator, and the calls leg must match the breakdown above.
EXAMPLE_OPEN_RAISE_SPLIT = [("calls", 30), ("folds", 33)]
# Where the 205 flops come from. Must sum to the wtsd denominator.
EXAMPLE_FLOP_SOURCES = [("hands invested in that reached a flop", 155), ("unraised big blinds", 50)]
# The example's voluntary actions and its bets-or-raises, split by street. Each
# list must sum to the matching `afq` count, and the flop entries must match the
# `afq[flop]` count and (preflop) the pfr numerator.
EXAMPLE_STREET_ACTIONS = [("preflop", 400), ("flop", 168), ("turn", 118), ("river", 82)]
EXAMPLE_STREET_AGGRESSION = [("preflop", 41), ("flop", 27), ("turn", 15), ("river", 9)]

# The most voluntary actions the example's hands could contain. A player is not
# limited to one action per street: preflop they act once per hand dealt and
# again whenever a reraise comes back at them (the 9 below), and postflop they
# act once per street reached and again in each spot where they checked and then
# faced a bet (the 140 below, which the prose counts across all three streets).
EXAMPLE_ACTION_CEILING = (412 + 9) + (3 * 205 + 140)

# The example's hand history, as the prose states it. Each entry is
# (count, what it counts, the count it must not exceed).
EXAMPLE_HISTORY = [
    (177, "voluntary investments", 412),
    (106, "limps", 250),
    (41, "preflop raises", 412),
    (30, "calls of a raise", 63),
    (250, "limp opportunities", 412),
    (63, "open raises faced", 412),
    (9, "reraises faced after opening", 41),
    (205, "flops seen", 412),
    (89, "showdowns reached", 205),
    (62, "flop continuation bets faced", 205),
    (140, "checked-then-faced-a-bet spots", 768),
    (768, "voluntary actions", EXAMPLE_ACTION_CEILING),
    (92, "bets or raises", 768),
]
# Per street, the most actions that street could carry: one per hand dealt (or
# per flop seen, since no later street is reached without one) plus the second
# actions above. The 140 checked-then-faced-a-bet spots are a total across the
# three postflop streets, so allowing all 140 to each of them is deliberately
# generous: these are ceilings, and a count that clears them is not contradicted.
EXAMPLE_STREET_CEILING = {
    "preflop": 412 + 9,
    "flop": 205 + 140,
    "turn": 205 + 140,
    "river": 205 + 140,
}

DEFAULT_DOC = Path(__file__).resolve().parent.parent / "OPPONENT_MODEL_DESIGN.md"

# Section 1 quotes this file's forefront-rule bullets verbatim, so every quote is
# compared against the authority rather than trusted.
FOREFRONT_SOURCE = "CLAUDE.md"
FOREFRONT_SECTION = "## The forefront rule"
FOREFRONT_QUOTED_IN = "### The forefront rule and this design"
# Exactly this many bullets are quoted there. A floor lets an added quote
# through without comment, so the count is compared exactly: any change to what
# §1 quotes has to be a deliberate edit here.
FOREFRONT_QUOTE_COUNT = 3

# ---------------------------------------------------------------------------
# Arithmetic the document states inline, written once.
# ---------------------------------------------------------------------------


def shrunk_rate(baseline: float, s: float, k: float, n: float) -> float:
    """Section 4.3: rate = (BASELINE*s + k)/(s + n)."""
    return (baseline * s + k) / (s + n)


def confidence(n: float, s: float) -> float:
    """Section 4.3: confidence = n/(n + s)."""
    return n / (n + s)


def opportunities_at_gate(s: float, c: float) -> float:
    """Section 4.4 step 2: confidence = n/(n+s) inverts to n = s*c/(1-c)."""
    return s * c / (1.0 - c)


def half_width(p: float, n: float) -> float:
    """Table C's formula, inverted: w = 1.96*sqrt(p(1-p)/n)."""
    return Z95 * math.sqrt(p * (1.0 - p) / n)


def opportunities_needed(p: float, w: float) -> float:
    """Table C: (1.96/w)^2 * p(1-p)."""
    return (Z95 / w) ** 2 * p * (1.0 - p)


def raw_margin(margin: float, c: float) -> float:
    """Section 4.4 step 1: a shrunk margin m needs a raw margin m/c."""
    return margin / c


def anchor_for(stat: str) -> float:
    """The p-hat a stat's interval is read at."""
    return TABLE_C_ANCHORS.get(stat, LEAST_FAVOURABLE_P)


def rate_text(stat: str, rate: float) -> str:
    """Table C's opportunity rate as the document prints it.

    A measured rate keeps the three decimals OPPONENT_BASELINE.md measured it
    to; a placeholder and the forced 1.00 print to two.
    """
    return fmt(rate, 3 if stat in MEASURED_RATES else 2)


def hands_needed(stat: str) -> float:
    """The fewest hands any Table C row for `stat` needs."""
    return min(
        opportunities_needed(p, w) / rate
        for st, p, rate, w in TABLE_C_ROWS
        if st == stat
    )


def baseline_bound_for_leg(margin: float, gate: float, s: float) -> float:
    """The largest baseline at which a flag leg's raw margin still exceeds w.

    Solves 1.96*sqrt(p(1-p)/n) = margin/gate for the smaller root p, at the
    fewest opportunities n = s*gate/(1-gate) the gate admits.
    """
    n = opportunities_at_gate(s, gate)
    m = raw_margin(margin, gate)
    # p(1-p) = m^2 * n / z^2
    product = m * m * n / (Z95 * Z95)
    return (1.0 - math.sqrt(1.0 - 4.0 * product)) / 2.0


def gate_for_band(p: float, s: float, band: float) -> float:
    """The confidence gate at which the shrunk half-width falls to `band`.

    The shrunk rate moves c of the way to the raw rate, so its half-width at
    confidence c, where n = s*c/(1-c), is c*w = 1.96*sqrt(p(1-p)*c(1-c)/s).
    """
    product = (band / Z95) ** 2 * s / (p * (1.0 - p))
    return (1.0 + math.sqrt(1.0 - 4.0 * product)) / 2.0


def shrunk_half_width(p: float, s: float, c: float) -> float:
    """c*w at confidence c: the sampling noise left in the shrunk rate."""
    return c * half_width(p, opportunities_at_gate(s, c))


# ---------------------------------------------------------------------------
# Formatting: half-up to the precision the document prints at.
# ---------------------------------------------------------------------------


def fmt(x: float, places: int, thousands: bool = False) -> str:
    quant = Decimal(1).scaleb(-places) if places else Decimal(1)
    d = Decimal(repr(float(x))).quantize(quant, rounding=ROUND_HALF_UP)
    if thousands:
        return f"{d:,}"
    return str(d)


def pct(x: float, places: int = 1) -> str:
    return fmt(x * 100.0, places) + "%"


def pp(x: float, places: int = 1) -> str:
    """A figure the document states in percentage points."""
    return fmt(x * 100.0, places) + "pp"


# ---------------------------------------------------------------------------
# Reading the document.
# ---------------------------------------------------------------------------


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

    def block_after(self, locator: str, fence: str = "```") -> list[str]:
        """The first fenced code block following a line containing `locator`."""
        start = None
        for i, line in enumerate(self.lines):
            if locator in line:
                start = i
                break
        if start is None:
            raise LookupError(f"locator not found: {locator!r}")
        # The locator may sit inside the block, so walk back to its opening
        # fence rather than forward to its closing one.
        i = start
        while i >= 0 and not self.lines[i].startswith(fence):
            i -= 1
        if i < 0:
            raise LookupError(f"no code block around locator: {locator!r}")
        out = []
        i += 1
        while i < len(self.lines) and not self.lines[i].startswith(fence):
            out.append(self.lines[i])
            i += 1
        return out


def clean_cell(cell: str) -> str:
    return cell.replace("**", "").replace("`", "").strip()


def _section_lines(doc: "Document", heading: str) -> list[str]:
    """The lines under `heading`, up to the next heading of the same depth or higher."""
    depth = len(heading) - len(heading.lstrip("#"))
    out: list[str] = []
    inside = False
    for line in doc.lines:
        if line.startswith("#"):
            if line.strip() == heading:
                inside = True
                continue
            if inside and len(line) - len(line.lstrip("#")) <= depth:
                break
        if inside:
            out.append(line)
    return out


def section_bullets(doc: "Document", heading: str) -> list[str]:
    """Every top-level bullet under `heading`, without its marker."""
    return [line[2:].strip() for line in _section_lines(doc, heading) if line.startswith("- ")]


def section_quotes(doc: "Document", heading: str) -> list[str]:
    """Every block-quoted line under `heading`, without its marker."""
    return [line[2:].strip() for line in _section_lines(doc, heading) if line.startswith("> ")]


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
            self.failures.append(f"{what}: document says {actual!r}, constants give {expected!r}")

    def true(self, what: str, ok: bool, detail: str = "") -> None:
        self.checked += 1
        if not ok:
            self.failures.append(f"{what}: {detail}" if detail else what)

    def prose(self, what: str, phrase: str) -> None:
        """Assert an exact phrase, carrying a derived figure, appears in the prose."""
        self.checked += 1
        flat_phrase = re.sub(r"\s+", " ", phrase)
        if flat_phrase not in self.doc.flat:
            self.failures.append(f"{what}: document does not contain {flat_phrase!r}")

    def every_occurrence(self, what: str, pattern: str, *expected: str) -> None:
        """Assert *every* place the document states this figure states it the same.

        `prose` only asks that one occurrence is right, so a figure the document
        repeats can go stale in every copy but one and still pass. This asks the
        question of all of them at once: each match of `pattern` must capture
        exactly `expected`.
        """
        self.checked += 1
        found = [
            tuple(g for g in m.groups() if g is not None)
            for m in re.finditer(pattern, self.doc.flat)
        ]
        if not found:
            self.failures.append(f"{what}: document states it nowhere (pattern {pattern!r})")
            return
        if len(expected) == 1:
            # One value, however many places and groups it is written in.
            wrong = [g for g in found if any(v != expected[0] for v in g)]
        else:
            wrong = [g for g in found if g != tuple(expected)]
        if wrong:
            self.failures.append(
                f"{what}: {len(wrong)} of {len(found)} occurrences disagree — "
                f"document says {wrong!r}, constants give {tuple(expected)!r}"
            )

    # -- Table A ----------------------------------------------------------
    def check_table_a(self) -> None:
        rows = self.doc.table_after("#### Table A: bet size, fold frequency, and bluff share")[1:]
        self.equal("Table A row count", len(BET_SIZES), len(rows))
        for s, row in zip(BET_SIZES, rows):
            tag = f"Table A s={s}"
            self.equal(f"{tag} bet size", fmt(s, 2), row[0])
            self.equal(f"{tag} break-even fold frequency", pct(s / (1 + s)), row[1])
            self.equal(f"{tag} minimum defence frequency", pct(1 / (1 + s)), row[2])
            self.equal(f"{tag} bluff share", pct(s / (1 + 2 * s)), row[3])

    # -- Table B ----------------------------------------------------------
    def check_table_b(self) -> None:
        all_rows = self.doc.table_after("#### Table B: the multiway problem")
        header, rows = all_rows[0], all_rows[1:]
        for n, cell in zip(OPPONENT_COUNTS, header[1:]):
            self.equal(f"Table B header column {n}", f"{n} opponent" + ("" if n == 1 else "s"), cell)
        self.equal("Table B row count", len(FOLD_RATES), len(rows))
        for p, row in zip(FOLD_RATES, rows):
            self.equal(f"Table B fold rate label {p}", pct(p, 0), row[0])
            for n, cell in zip(OPPONENT_COUNTS, row[1:]):
                self.equal(f"Table B p={p} n={n}", pct(p ** n), cell)
        pot_sized = max(BET_SIZES[BET_SIZES.index(1.00)], 1.00)
        self.prose(
            "section 2.4 cube-root reading of Table B",
            f"a pot-sized bluff needs {pct(pot_sized / (1 + pot_sized), 0)} fold-through. With\n"
            f"three opponents that requires each of them to fold "
            f"{pct(0.5 ** (1 / 3), 0)} of the time\n(`0.5^(1/3) ≈ {fmt(0.5 ** (1 / 3), 3)}`)",
        )

    # -- Table C ----------------------------------------------------------
    def check_table_c(self) -> None:
        rows = self.doc.table_after("#### Table C: how many hands each stat needs")[1:]
        self.equal("Table C row count", len(TABLE_C_ROWS), len(rows))
        for (stat, p, rate, w), row in zip(TABLE_C_ROWS, rows):
            tag = f"Table C {stat} ±{w}"
            self.equal(f"{tag} stat", stat, row[0])
            self.equal(f"{tag} anchor", fmt(p, 2), row[1])
            self.equal(f"{tag} opportunities per hand", rate_text(stat, rate), row[2])
            self.equal(f"{tag} target width", "±" + fmt(w * 100, 0) + "pp", row[3])
            opps = opportunities_needed(p, w)
            self.equal(f"{tag} opportunities needed", fmt(opps, 0, thousands=True), row[4])
            self.equal(f"{tag} hands needed", fmt(opps / rate, 0, thousands=True), row[5])
            # Every rate is forced by a "dealt in" denominator, measured, or a
            # placeholder -- and the last column says which, in every row.
            if stat in DEALT_IN_STATS:
                self.true(f"{tag} rate is one per hand dealt", rate == 1.00, f"rate {rate}")
                self.equal(f"{tag} rate source", RATE_SOURCE_DEALT_IN, row[6])
            elif stat in MEASURED_RATES:
                self.equal(f"{tag} measured rate", repr(MEASURED_RATES[stat]), repr(rate))
                self.equal(f"{tag} rate source", RATE_SOURCE_MEASURED, row[6])
            else:
                self.true(
                    f"{tag} rate is a placeholder",
                    rate in PLACEHOLDER_RATES,
                    f"rate {rate} is not one of {sorted(PLACEHOLDER_RATES)}",
                )
                self.equal(f"{tag} rate source", RATE_SOURCE_PLACEHOLDER, row[6])
        three_bet_rate = next(rate for stat, _p, rate, _w in TABLE_C_ROWS if stat == "three_bet")
        three_bet_row = next(row for row in TABLE_C_ROWS if row[0] == "three_bet")
        self.prose(
            "section 4.2 three_bet expectation sentence",
            f"at a placeholder {fmt(three_bet_rate, 2)}\nopportunities per hand a "
            f"±{fmt(three_bet_row[3] * 100, 0)}pp reading of a {fmt(three_bet_row[1] * 100, 0)}% behaviour",
        )
        # The same sentence claims three_bet sits further off than any postflop
        # row. Re-pinning a postflop rate upward is exactly what would break it.
        self.true(
            "section 4.2 three_bet really is further off than every postflop row",
            all(hands_needed("three_bet") > hands_needed(stat) for stat in POSTFLOP_STATS),
            "a postflop row needs more hands than three_bet: "
            + ", ".join(f"{stat} {hands_needed(stat):.0f}" for stat in sorted(POSTFLOP_STATS))
            + f" against three_bet {hands_needed('three_bet'):.0f}",
        )

    # -- Table D ----------------------------------------------------------
    def check_table_d(self) -> None:
        rows = self.doc.table_after("#### Table D: what the confidence weight looks like")
        header, body = rows[0], rows[1:]
        for s, cell in zip(TABLE_D_S, header[1:]):
            self.true(f"Table D header s={s}", f"s={s}" in cell.replace(" ", ""), f"header cell {cell!r}")
        for tier, value, _stats in PRIOR_STRENGTH_GROUPS:
            self.true(
                f"Table D marks {tier}",
                any(tier in cell and f"s={value}" in cell.replace(" ", "") for cell in header[1:]),
                f"no header cell marks {tier} at s={value}",
            )
        self.equal("Table D row count", len(TABLE_D_N), len(body))
        for n, row in zip(TABLE_D_N, body):
            self.equal(f"Table D n label {n}", str(n), row[0])
            for s, cell in zip(TABLE_D_S, row[1:]):
                self.equal(f"Table D n={n} s={s}", fmt(confidence(n, s), 2), cell)

    # -- Table E ----------------------------------------------------------
    def check_table_e(self) -> None:
        rows = self.doc.table_after("#### Table E: shrinkage in practice")[1:]
        self.equal("Table E row count", len(TABLE_E_ROWS), len(rows))
        tier_b = dict((t, v) for t, v, _ in PRIOR_STRENGTH_GROUPS)["Tier B"]
        for (baseline, s, k, n), row in zip(TABLE_E_ROWS, rows):
            tag = f"Table E {k} of {n} toward {baseline}"
            self.equal(f"{tag} baseline", fmt(baseline, 2), row[0])
            self.equal(f"{tag} prior strength", str(s), row[1])
            self.equal(f"{tag} observed", f"{k} of {n}", row[2])
            self.equal(f"{tag} raw rate", fmt(k / n, 2), row[3])
            self.equal(f"{tag} shrunk rate", fmt(shrunk_rate(baseline, s, k, n), 3), row[4])
            self.true(f"{tag} uses the Tier B prior", s == tier_b, f"prior strength {s} is not Tier B's {tier_b}")
        b, s, k, n = TABLE_E_ROWS[0]
        self.prose(
            "section 4.3 Table E row 1 read in the prose",
            f"the prior strength in every row is the Tier B {s} — is recorded as a "
            f"{pct(shrunk_rate(b, s, k, n), 0)} raiser, not a {pct(k / n, 0)} one",
        )
        self.prose(
            "section 4.3 Table E row 1 observation count",
            f"at {n} observations the confidence is",
        )
        self.prose(
            "section 4.3 Table E confidence reading",
            f"the confidence is `{n}/{n + s} = {fmt(confidence(n, s), 2)}`",
        )
        self.true(
            "section 4.3 Table E confidence is below every bucket gate",
            confidence(n, s) < CLASSIFY_CONF_GATE
            and all(confidence(n, s) < f["gate"] for f in FLAGS.values()),
            "the Table E row's confidence does not sit below every gate",
        )

    # -- PRIOR_STRENGTH table and stat coverage ---------------------------
    def check_prior_strength_table(self) -> None:
        rows = self.doc.table_after("`PRIOR_STRENGTH` per stat — which is also the `s` in the")[1:]
        self.equal("PRIOR_STRENGTH row count", len(PRIOR_STRENGTH_GROUPS), len(rows))
        listed: set[str] = set()
        for (tier, value, stats), row in zip(PRIOR_STRENGTH_GROUPS, rows):
            names = re.findall(r"[a-z_]+", row[0].split("(", 1)[1] if "(" in row[0] else "")
            names = [n for n in names if n not in {"tier"}]
            self.true(f"PRIOR_STRENGTH {tier} label", row[0].startswith(tier), f"row label {row[0]!r}")
            self.equal(f"PRIOR_STRENGTH {tier} value", str(value), row[1])
            self.equal(f"PRIOR_STRENGTH {tier} stats", ", ".join(stats), ", ".join(names))
            unit = "hands" if tier == "Tier A" else "opportunities"
            self.equal(f"PRIOR_STRENGTH {tier} crossover", f"{value} {unit}", row[2])
            for stat in stats:
                self.equal(f"PRIOR_STRENGTH[{stat}]", str(PRIOR_STRENGTH[stat]), str(value))
            listed |= set(stats)
        self.equal(
            "PRIOR_STRENGTH table covers every shrunk stat",
            ", ".join(sorted(PRIOR_STRENGTH)),
            ", ".join(sorted(listed)),
        )

    def check_every_stat_has_a_tier(self) -> None:
        rows = self.doc.table_after("| `stat_name` | Numerator increments when")[1:]
        stats = [row[0] for row in rows]
        self.true("section 4.2 stat table parsed", len(stats) > 10, f"only {len(stats)} stats found")
        for stat in stats:
            self.true(
                f"section 4.2 stat {stat} has a tier",
                stat in PRIOR_STRENGTH or stat in NO_PRIOR_STRENGTH,
                f"{stat} appears in the stat table with no PRIOR_STRENGTH and no exemption",
            )
        for stat in PRIOR_STRENGTH:
            self.true(
                f"PRIOR_STRENGTH[{stat}] names a real stat",
                stat in stats,
                f"{stat} has a PRIOR_STRENGTH but no row in the section 4.2 stat table",
            )
        overlap = set(PRIOR_STRENGTH) & NO_PRIOR_STRENGTH
        self.true("no stat is both shrunk and exempt", not overlap, f"{sorted(overlap)}")

    # -- Flag tables ------------------------------------------------------
    def check_flag_conditions(self) -> None:
        rows = self.doc.table_after("| Flag | Condition | Confidence gate |")[1:]
        self.equal("flag condition row count", len(FLAGS), len(rows))
        for row in rows:
            flag = row[0]
            self.true(f"flag {flag} is a known flag", flag in FLAGS, "not in FLAGS")
            if flag not in FLAGS:
                continue
            spec = FLAGS[flag]
            self.true(
                f"flag {flag} margin",
                f"≥ {fmt(spec['margin'], 2)}" in row[1],
                f"condition {row[1]!r} does not state a {fmt(spec['margin'], 2)} margin",
            )
            self.true(
                f"flag {flag} gate",
                f"confidence ≥ {fmt(spec['gate'], 1)}" in row[2],
                f"gate cell {row[2]!r}",
            )
            for stat in spec["stats"]:
                bare = stat.split("[")[0]
                self.true(
                    f"flag {flag} reads {bare}",
                    bare in row[1],
                    f"condition {row[1]!r} does not name {bare}",
                )

    def check_margin_interval_table(self) -> None:
        rows = self.doc.table_after("| Flag | Stat, `s`, gate | Fewest opportunities at the gate |")[1:]
        expected = [
            ("OVERFOLDS_TO_3BET, NEVER_FOLDS_TO_3BET", "fold_to_three_bet", 0.15, 0.6),
            ("OVERFOLDS_TO_CBET", "fold_to_cbet", 0.15, 0.6),
            ("NEVER_FOLDS_POSTFLOP", "wtsd", 0.15, 0.6),
            ("NEVER_RAISES, three_bet leg", "three_bet", 0.05, 0.7),
        ]
        self.equal("margin table row count", len(expected), len(rows))
        for (label, stat, margin, gate), row in zip(expected, rows):
            tag = f"margin table {label}"
            s = PRIOR_STRENGTH[stat]
            n = opportunities_at_gate(s, gate)
            p = anchor_for(stat)
            w = half_width(p, n)
            m_raw = raw_margin(margin, gate)
            self.equal(f"{tag} label", label, row[0])
            self.equal(f"{tag} stat, s, gate", f"{stat}, {s}, {fmt(gate, 1)}", row[1])
            self.equal(f"{tag} fewest opportunities", fmt(n, 1), row[2])
            self.equal(f"{tag} half-width", f"{fmt(w, 3)} (p̂ {fmt(p, 2)})", row[3])
            self.equal(f"{tag} margin", fmt(margin, 2), row[4])
            self.equal(f"{tag} raw margin", fmt(m_raw, 3), row[5])
            self.true(
                f"{tag} exceeds w",
                row[6].startswith("yes") == (m_raw > w),
                f"table says {row[6]!r}, raw margin {m_raw:.4f} vs w {w:.4f}",
            )
            # The flag's own margin and gate must be the ones FLAGS holds.
            owner = label.split(",")[0]
            self.equal(f"{tag} margin matches FLAGS", fmt(FLAGS[owner]["margin"], 2), fmt(margin, 2))
            self.equal(f"{tag} gate matches FLAGS", fmt(FLAGS[owner]["gate"], 1), fmt(gate, 1))

    def check_margin_prose(self) -> None:
        # Step 1's two worked raw margins.
        for margin, gate in ((0.15, 0.6), (0.05, 0.7)):
            self.prose(
                f"section 4.4 step 1 raw margin for {margin} at {gate}",
                f"`{fmt(gate, 1)}` gate a {fmt(margin, 2)} shrunk margin means a "
                f"{fmt(raw_margin(margin, gate), 3)} raw margin",
            )
        # The narrower wtsd margin that would fail.
        s = PRIOR_STRENGTH["wtsd"]
        gate = FLAGS["NEVER_FOLDS_POSTFLOP"]["gate"]
        n = opportunities_at_gate(s, gate)
        w = half_width(anchor_for("wtsd"), n)
        narrower = 0.10
        self.prose(
            "section 4.4 narrower wtsd margin",
            f"A {fmt(narrower, 2)} margin there implies a\nraw margin of "
            f"{fmt(raw_margin(narrower, gate), 3)}, *inside* the {fmt(w, 3)} interval",
        )
        self.true(
            "section 4.4 narrower wtsd margin really would fail",
            raw_margin(narrower, gate) < w,
            "the narrower margin does not in fact fall inside the interval",
        )
        self.true(
            "section 4.4 wtsd gate admits the fewest opportunities",
            all(
                n <= opportunities_at_gate(PRIOR_STRENGTH[st.split("[")[0]], f["gate"])
                for name, f in FLAGS.items()
                for st in f["stats"]
            ),
            "wtsd's gate does not admit the fewest opportunities of any flag",
        )
        # The three flags with no Table C anchor.
        for stat, flag in (("fold_to_steal", "OVERFOLDS_BLINDS"), ("limp", "LIMPS")):
            s = PRIOR_STRENGTH[stat]
            gate = FLAGS[flag]["gate"]
            w = half_width(LEAST_FAVOURABLE_P, opportunities_at_gate(s, gate))
            self.prose(f"section 4.4 unanchored {stat} half-width", f"{fmt(w, 3)}")
            self.true(
                f"section 4.4 {flag} clears at any anchor",
                raw_margin(FLAGS[flag]["margin"], gate) > w,
                f"raw margin does not exceed {w:.3f}",
            )
        self.prose(
            "section 4.4 unanchored half-widths sentence",
            f"`fold_to_steal`'s half-width at its gate is "
            f"{fmt(half_width(LEAST_FAVOURABLE_P, opportunities_at_gate(PRIOR_STRENGTH['fold_to_steal'], FLAGS['OVERFOLDS_BLINDS']['gate'])), 3)} "
            f"and `limp`'s is\n"
            f"{fmt(half_width(LEAST_FAVOURABLE_P, opportunities_at_gate(PRIOR_STRENGTH['limp'], FLAGS['LIMPS']['gate'])), 3)}, "
            f"both below the {fmt(raw_margin(FLAGS['LIMPS']['margin'], FLAGS['LIMPS']['gate']), 3)} "
            f"raw margin their {fmt(FLAGS['LIMPS']['margin'], 2)} margins imply",
        )
        self.prose(
            "section 4.4 why NEVER_FOLDS_POSTFLOP keeps the wide margin",
            f"**`NEVER_FOLDS_POSTFLOP` carries the same "
            f"{fmt(FLAGS['NEVER_FOLDS_POSTFLOP']['margin'], 2)} margin as the rest",
        )
        self.prose(
            "section 4.4 wtsd's prior strength as the reason it sees fewest opportunities",
            f"its `s` = {PRIOR_STRENGTH['wtsd']} gate admits",
        )
        # The check_raise bound -- only reproducible at PRIOR_STRENGTH 25.
        spec = FLAGS["NEVER_RAISES"]
        s_cr = PRIOR_STRENGTH["check_raise"]
        bound = baseline_bound_for_leg(spec["margin"], spec["gate"], s_cr)
        n_cr = opportunities_at_gate(s_cr, spec["gate"])
        self.prose(
            "section 4.4 check_raise leg's raw margin and the baseline bound",
            f"its {fmt(raw_margin(spec['margin'], spec['gate']), 3)} raw margin clears only "
            f"while that stat's\nbaseline is below about {fmt(bound, 3)}",
        )
        self.prose(
            "section 4.4 check_raise bound derivation",
            f"Both of those figures are `check_raise`'s `PRIOR_STRENGTH` = {s_cr}\n"
            f"from [§4.3](#43-after-each-hand-the-update) at work: the leg's gate is "
            f"`{fmt(spec['gate'], 1)}`, so\nit admits "
            f"`n = {s_cr}·{fmt(spec['gate'], 1)}/{fmt(1 - spec['gate'], 1)} = {fmt(n_cr, 1)}` "
            f"opportunities at fewest, and {fmt(bound, 3)} is the `p̂`\n"
            f"at which `{fmt(Z95, 2)}·√(p̂(1−p̂)/{fmt(n_cr, 1)})` equals the "
            f"{fmt(spec['margin'], 2)}/{fmt(spec['gate'], 1)} raw margin",
        )
        self.true(
            "section 4.4 check_raise leg fails at the least favourable anchor",
            raw_margin(spec["margin"], spec["gate"]) < half_width(LEAST_FAVOURABLE_P, n_cr),
            "the check_raise leg would in fact clear at p-hat 0.5",
        )

    # -- The bucket boundary's noise exposure -----------------------------
    def check_boundary_exposure(self) -> None:
        for axis, split, stat in (("vpip", VPIP_SPLIT, "vpip"), ("afq", AFQ_SPLIT, "afq")):
            s = PRIOR_STRENGTH[stat]
            n = opportunities_at_gate(s, CLASSIFY_CONF_GATE)
            w = half_width(split, n)
            shrunk_w = CLASSIFY_CONF_GATE * w
            # Both exposures are stated twice: in §4.4 and in the provenance table.
            if axis == "vpip":
                self.every_occurrence(
                    "section 4.4 vpip raw exposure, wherever it is stated",
                    r"= \*\*±([\d.]+)pp\*\*, which is|±([\d.]+)pp raw and ±[\d.]+pp shrunk on `vpip`",
                    fmt(w * 100.0, 1),
                )
                self.every_occurrence(
                    "section 4.4 vpip shrunk exposure, wherever it is stated",
                    r"`c·w` = \*\*±([\d.]+)pp\*\*|±[\d.]+pp raw and ±([\d.]+)pp shrunk on `vpip`",
                    fmt(shrunk_w * 100.0, 1),
                )
            else:
                self.every_occurrence(
                    "section 4.4 afq exposures, wherever they are stated",
                    r"is ±([\d.]+)pp raw and ±([\d.]+)pp shrunk|±([\d.]+)pp and ±([\d.]+)pp on `afq`",
                    fmt(w * 100.0, 1),
                    fmt(shrunk_w * 100.0, 1),
                )
            needed_gate = gate_for_band(split, s, HYSTERESIS_BAND)
            needed_n = opportunities_at_gate(s, needed_gate)
            self.prose(
                f"section 4.4 {axis} gate needed for the band",
                f"`confidence({axis}) ≥ {fmt(needed_gate, 3)}`",
            )
            self.every_occurrence(
                f"section 4.4 {axis} sample needed for the band, wherever it is stated",
                (
                    r"= \*\*([\d,]+) hands\*\* on one|the ([\d,]+) hands / [\d,]+ opportunities"
                    if axis == "vpip"
                    else r"i\.e\. \*\*([\d,]+)\*\* `afq` opportunities|"
                    r"[\d,]+ hands / ([\d,]+) opportunities"
                ),
                fmt(needed_n, 0, thousands=True),
            )
            self.prose(f"section 4.4 {axis} band needed", f"`{fmt(shrunk_w, 3)}` on `{axis}`")
        s = PRIOR_STRENGTH["vpip"]
        n = opportunities_at_gate(s, CLASSIFY_CONF_GATE)
        w = half_width(VPIP_SPLIT, n)
        self.prose(
            "section 4.4 vpip gate inversion",
            f"`n = {s}·{fmt(CLASSIFY_CONF_GATE, 1)}/{fmt(1 - CLASSIFY_CONF_GATE, 1)} = {fmt(n, 0)}` hands",
        )
        self.prose(
            "section 4.4 vpip half-width formula",
            f"`w = 1.96·√({fmt(VPIP_SPLIT, 2)}·{fmt(1 - VPIP_SPLIT, 2)}/{fmt(n, 0)})`",
        )
        self.prose(
            "section 4.4 raw exposure as a multiple of the band",
            f"which is {fmt(w / HYSTERESIS_BAND, 1)} times the `{fmt(HYSTERESIS_BAND, 2)}`\ndead-band",
        )
        self.prose(
            "section 4.4 shrunk exposure as a multiple of the band",
            f"still {fmt(CLASSIFY_CONF_GATE * w / HYSTERESIS_BAND, 1)} times the band",
        )
        s_afq = PRIOR_STRENGTH["afq"]
        self.prose(
            "section 4.4 afq gate inversion",
            f"(`s` = {s_afq}, `n` = {fmt(opportunities_at_gate(s_afq, CLASSIFY_CONF_GATE), 0)})",
        )
        self.prose("section 4.4 hysteresis hold", f"hold for `{HYSTERESIS_HOLD}` consecutive")
        self.prose("section 4.4 vpip split", f"`VPIP_SPLIT` **defaults to {fmt(VPIP_SPLIT, 2)}**")
        self.prose("section 4.4 afq split", f"`AFQ_SPLIT` **defaults to {fmt(AFQ_SPLIT, 2)}**")
        self.prose(
            "section 4.4 classify gate",
            f"`confidence(vpip) < {fmt(CLASSIFY_CONF_GATE, 1)}` **or**",
        )
        self.prose(
            "section 4.4 minimum hands to classify",
            f"`MIN_CLASSIFY_HANDS = {MIN_CLASSIFY_HANDS}`",
        )

    # -- The Tier 1 solve plan and its cost bound -------------------------
    def check_solve_plan(self) -> None:
        seats = len(SEAT_COUNTS)
        strategies = len(STRATEGIES)
        total = seats * strategies
        self.prose("section 4.5 seat count", f"which is **{spell(seats)} seat counts**")
        self.prose("section 4.5 strategies per seat count", f"needs **{spell(strategies)} strategies**")
        self.prose(
            "section 4.5 total solve runs",
            f"**{spell(strategies).capitalize()} strategies × {spell(seats)} seat counts = {total}\noffline solver runs**",
        )
        self.prose("section 4.5 feasibility multiplier", f"that cost times {total}")
        saved = strategies - 1  # S_BASE still has to be solved at that seat count
        self.prose(
            "section 4.5 saving from dropping a seat count",
            f"**Dropping one seat count from Tier 1 saves {saved} runs, not {strategies}**",
        )
        self.prose(
            "section 4.5 floor",
            f"leaves a floor of **{seats} runs** — one `{BASE_STRATEGY}`\nper seat count",
        )
        self.prose("section 4.5 saving from dropping a bucket", f"saves {seats} runs per bucket dropped")
        self.prose("engine requirement E5 run count", f"Tier 1 needs **{total} of them**")
        self.prose("engine requirement E5 cost cap", "no multi-day computing** (operator, 2026-09-15)")
        self.prose("section 4.5 cost cap", "**hours on one laptop** (operator, 2026-09-15)")
        self.prose("section 4.5 pending engine decision", "`ENGINE_ALTERNATIVES.md` is under review")
        self.true(
            "section 4.5 states the seat range the seat count comes from",
            f"every table size from 2 to {SEAT_COUNTS[-1]} players" in self.doc.flat,
            "the 2-to-9 seat range is not stated",
        )

    # -- The remaining constants, as the document states them -------------
    def check_stated_constants(self) -> None:
        self.prose("section 4.3 half-life", f"Default `HALF_LIFE = {HALF_LIFE}` hands")
        self.prose("section 4.3 pool hands", f"`MIN_POOL_HANDS = {MIN_POOL_HANDS}` hands")
        self.prose("section 4.3 pool opponents", f"`MIN_POOL_OPPONENTS = {MIN_POOL_OPPONENTS}` qualifying")
        self.prose("section 4.7 minimum stack", f"`MIN_STACK_BB = {MIN_STACK_BB}`")
        # The edge-case row states the floor twice: in its label and in the
        # rule's restatement. Both must be the constant, not a stale copy.
        self.prose(
            "section 4.7 short-stack edge-case label",
            f"Opponent started the hand with fewer than `MIN_STACK_BB = {MIN_STACK_BB}` big blinds",
        )
        self.prose(
            "section 4.7 short-stack floor restated",
            f"The floor of {MIN_STACK_BB} big blinds is an unmeasured starting value",
        )
        self.prose(
            "section 4.4 dead-band",
            f"dead-band of `{fmt(HYSTERESIS_BAND, 2)}` before",
        )
        self.prose("section 4.5 majority rule", f"`{MAJORITY_RULE}` of the `n` live opponents")
        self.every_occurrence(
            "the majority rule wherever the document writes it",
            r"(⌈\d+n/\d+⌉)",
            MAJORITY_RULE,
        )
        self.prose(
            "section 4.5 the majority rule read at one live opponent",
            f"`n = 1` live opponent `{MAJORITY_RULE} = {math.ceil(2 * 1 / 3)}`",
        )
        self.prose(
            "section 6 V3 holdout",
            f"last {V3_HOLDOUT[1]}% of logged hands per opponent; the "
            f"{V3_HOLDOUT[0]}/{V3_HOLDOUT[1]} split",
        )
        rows = self.doc.table_after("| Strategy | Trained against | The bot loads it when")[1:]
        self.equal(
            "strategy table",
            ", ".join(STRATEGIES + [NO_COUNTER_STRATEGY]),
            ", ".join(row[0] for row in rows),
        )
        for row in rows:
            if row[0] == NO_COUNTER_STRATEGY:
                self.true(
                    f"{NO_COUNTER_STRATEGY} is never solved",
                    "never" in row[2],
                    f"loads-when cell {row[2]!r}",
                )

    # -- Warm-up widths ---------------------------------------------------
    def check_warmup(self) -> None:
        self.prose("section 5.2 warm-up constant", f"`WARMUP_HANDS = {WARMUP_HANDS}` hands")
        widths = {}
        for stat in ("vpip", "pfr"):
            p = TABLE_C_ANCHORS[stat]
            widths[stat] = half_width(p, WARMUP_HANDS)
            self.prose(
                f"section 5.2 warm-up width for {stat}",
                f"±{pp(widths[stat])} on `{stat}` at",
            )
        self.prose(
            "section 5.2 warm-up width summary",
            f"Tier A is inside ±{pp(max(widths.values()))} and\nno tighter",
        )
        for stat, target, hands in (("vpip", 0.05, 323), ("pfr", 0.05, 246)):
            opps = opportunities_needed(TABLE_C_ANCHORS[stat], target)
            self.equal(
                f"section 5.2 quotes Table C's {stat} row",
                fmt(opps, 0, thousands=True),
                str(hands),
            )
        self.prose(
            "section 5.2 Table C rows quoted",
            f"Table C's ±5pp rows need {fmt(opportunities_needed(TABLE_C_ANCHORS['vpip'], 0.05), 0)}\n"
            f"hands for `vpip` and {fmt(opportunities_needed(TABLE_C_ANCHORS['pfr'], 0.05), 0)} for `pfr`",
        )

    # -- The Tier 0 worked example ----------------------------------------
    def example_profile(self) -> dict[str, dict[str, float]]:
        out = {}
        for stat, (k, n, baseline) in EXAMPLE_COUNTS.items():
            s = PRIOR_STRENGTH[stat.split("[")[0]]
            out[stat] = {
                "k": k,
                "n": n,
                "s": s,
                "baseline": baseline,
                "rate": shrunk_rate(baseline, s, k, n),
                "conf": confidence(n, s),
                "raw": k / n,
            }
        return out

    def example_flags(self, profile) -> set[str]:
        fired = set()
        for flag, spec in FLAGS.items():
            legs = []
            for stat in spec["stats"]:
                p = profile[stat]
                if p["conf"] < spec["gate"]:
                    legs.append(False)
                    continue
                delta = p["rate"] - p["baseline"]
                legs.append(delta >= spec["margin"] if spec["side"] == "above" else -delta >= spec["margin"])
            if all(legs):
                fired.add(flag)
        return fired

    def check_example(self) -> None:
        profile = self.example_profile()
        rows = self.doc.table_after("| Stat | `k` | `n` | `s` | Assumed `BASELINE` | Shrunk | `confidence` |")[1:]
        self.equal("example count table row count", len(EXAMPLE_COUNTS), len(rows))
        for row in rows:
            stat = row[0]
            self.true(f"example row {stat} is a known stat", stat in profile, "not in EXAMPLE_COUNTS")
            if stat not in profile:
                continue
            p = profile[stat]
            tag = f"example {stat}"
            self.equal(f"{tag} k", str(p["k"]), row[1])
            self.equal(f"{tag} n", str(p["n"]), row[2])
            self.equal(f"{tag} s", str(p["s"]), row[3])
            self.equal(f"{tag} baseline", fmt(p["baseline"], 2), row[4])
            self.equal(f"{tag} shrunk rate", fmt(p["rate"], 2), row[5])
            self.equal(f"{tag} confidence", fmt(p["conf"], 2), row[6])
            # A stat with a Table C anchor must assume that anchor as its baseline.
            bare = stat.split("[")[0]
            if bare in TABLE_C_ANCHORS:
                self.equal(
                    f"{tag} baseline is Table C's anchor",
                    fmt(TABLE_C_ANCHORS[bare], 2),
                    fmt(p["baseline"], 2),
                )

        block = [line for line in self.doc.block_after("$ pokerbot profile") if line.strip()]
        self.true("example block found", len(block) > 5, f"{len(block)} lines")
        printed = {}
        for line in block[1:]:
            m = re.match(r"\s*(\S+)\s+([0-9.]+)\s+\(conf ([0-9.]+)\)(?:\s+raw ([0-9.]+))?\s*$", line)
            if m:
                printed[m.group(1)] = (m.group(2), m.group(3), m.group(4))
            else:
                m2 = re.match(r"\s*(\S+)\s+(.*\S)\s*$", line)
                if m2:
                    printed[m2.group(1)] = (m2.group(2), None, None)
        self.equal("example command line", f'$ pokerbot profile "{EXAMPLE_ALIAS}"', block[0].strip())
        self.equal("example hands", str(EXAMPLE_HANDS), printed.get("hands", ("",))[0])
        self.equal(
            "example hands matches the vpip denominator",
            str(EXAMPLE_HANDS),
            str(EXAMPLE_COUNTS["vpip"][1]),
        )
        for stat, shows_raw in EXAMPLE_PRINTED:
            p = profile[stat]
            got = printed.get(stat)
            self.true(f"example block prints {stat}", got is not None, "line missing")
            if got is None:
                continue
            self.equal(f"example block {stat} rate", fmt(p["rate"], 2), got[0])
            self.equal(f"example block {stat} confidence", fmt(p["conf"], 2), got[1])
            if shows_raw:
                self.equal(f"example block {stat} raw rate", fmt(p["raw"], 2), got[2])
            else:
                self.equal(f"example block {stat} prints no raw rate", "None", str(got[2]))
        gap = profile["vpip"]["rate"] - profile["pfr"]["rate"]
        self.equal("example gap", fmt(gap, 2), printed.get("gap", ("",))[0])

        fired = self.example_flags(profile)
        self.equal(
            "example flags",
            ", ".join(sorted(fired)),
            ", ".join(sorted(x.strip() for x in printed.get("flags", ("",))[0].split(","))),
        )
        # Bucket, from the two axes, with the gates the document sets.
        vpip, afq = profile["vpip"], profile["afq"]
        self.true(
            "example clears the classification gates",
            vpip["conf"] >= CLASSIFY_CONF_GATE and EXAMPLE_HANDS >= MIN_CLASSIFY_HANDS,
            "the example would be UNKNOWN",
        )
        loose = vpip["rate"] > VPIP_SPLIT
        aggressive = afq["rate"] > AFQ_SPLIT
        bucket = {
            (False, False): "ROCK",
            (True, False): "STATION",
            (False, True): "TAG",
            (True, True): "MANIAC",
        }[(loose, aggressive)]
        self.equal("example bucket", bucket, printed.get("bucket", ("",))[0])
        self.equal("example bucket constant", EXAMPLE_BUCKET, bucket)
        self.true(
            "example clears WARMUP_HANDS",
            EXAMPLE_HANDS >= WARMUP_HANDS,
            f"{EXAMPLE_HANDS} hands is under WARMUP_HANDS={WARMUP_HANDS}",
        )
        # Not a near-boundary call on either axis, so the report prints no mark.
        for stat, split in (("vpip", VPIP_SPLIT), ("afq", AFQ_SPLIT)):
            p = profile[stat]
            near = p["conf"] * half_width(split, p["n"])
            self.true(
                f"example is not near-boundary on {stat}",
                abs(p["rate"] - split) > near,
                f"|{p['rate']:.4f} - {split}| is inside c*w = {near:.4f}",
            )
        # The history the prose states must be internally consistent.
        for count, what, limit in EXAMPLE_HISTORY:
            self.true(
                f"example history: {what}",
                count <= limit,
                f"{count} {what} exceeds the {limit} it is drawn from",
            )
            self.prose(f"example history states {what}", f"**{count}**")
        self.check_example_history()
        self.check_example_narrative(profile, fired)

    def check_example_narrative(self, profile, fired: set[str]) -> None:
        """The paragraph that says why each flag fires, and by how much."""

        def conf(stat: str) -> str:
            return fmt(profile[stat]["conf"], 2)

        def above(stat: str) -> str:
            return fmt(profile[stat]["rate"] - profile[stat]["baseline"], 3)

        def below(stat: str) -> str:
            return fmt(profile[stat]["baseline"] - profile[stat]["rate"], 3)

        wide_gate = fmt(FLAGS["NEVER_FOLDS_POSTFLOP"]["gate"], 1)
        raise_gate = fmt(FLAGS["NEVER_RAISES"]["gate"], 1)
        wide_margin = fmt(FLAGS["NEVER_FOLDS_POSTFLOP"]["margin"], 2)
        raise_margin = fmt(FLAGS["NEVER_RAISES"]["margin"], 2)
        self.prose(
            "example narrative: the gates each fired flag clears",
            f"`wtsd` {conf('wtsd')} and `limp` {conf('limp')} against the `{wide_gate}` gates, "
            f"`three_bet` {conf('three_bet')} and `check_raise` {conf('check_raise')} "
            f"against the `{raise_gate}` gate",
        )
        self.prose(
            "example narrative: the margins each fired flag clears",
            f"`wtsd` sits {above('wtsd')} above its baseline and `limp` {above('limp')}, both past "
            f"{wide_margin}, while `NEVER_RAISES` needs both of its legs {raise_margin} below "
            f"theirs and gets {below('three_bet')} on `three_bet` and {below('check_raise')} "
            f"on `check_raise`",
        )
        self.prose(
            "example narrative: the flags that fail their gate, and at what confidence",
            f"fail the `{fmt(FLAGS['OVERFOLDS_TO_3BET']['gate'], 1)}` confidence gate at "
            f"{conf('fold_to_three_bet')}",
        )
        self.prose(
            "example narrative: the flags that pass their gate but not their margin",
            f"pass their gates but sit *below* their baselines rather than {wide_margin} above",
        )
        self.prose(
            "example narrative: the two axes the bucket is read off",
            f"is `{EXAMPLE_BUCKET}` because {fmt(profile['vpip']['rate'], 2)} is above "
            f"`VPIP_SPLIT` and {fmt(profile['afq']['rate'], 2)} below `AFQ_SPLIT`",
        )
        self.prose(
            "example narrative: the classification gate and hands floor",
            f"clears both the `{fmt(CLASSIFY_CONF_GATE, 1)}` `vpip`-confidence gate and "
            f"`MIN_CLASSIFY_HANDS = {MIN_CLASSIFY_HANDS}`",
        )
        # The two "correctly absent" claims, checked rather than asserted.
        for flag in ("OVERFOLDS_TO_3BET", "NEVER_FOLDS_TO_3BET"):
            stat = FLAGS[flag]["stats"][0]
            self.true(
                f"example narrative: {flag} is absent because of its gate",
                flag not in fired and profile[stat]["conf"] < FLAGS[flag]["gate"],
                f"{flag} does not fail on confidence",
            )
        for flag in ("OVERFOLDS_TO_CBET", "OVERFOLDS_BLINDS"):
            stat = FLAGS[flag]["stats"][0]
            p = profile[stat]
            self.true(
                f"example narrative: {flag} is absent despite clearing its gate",
                flag not in fired
                and p["conf"] >= FLAGS[flag]["gate"]
                and p["rate"] < p["baseline"],
                f"{flag} does not pass its gate and sit below its baseline",
            )

    def check_example_history(self) -> None:
        """The prose history: every count in it, read from the document."""
        hands = EXAMPLE_HANDS
        vpip_k, _vpip_n, _ = EXAMPLE_COUNTS["vpip"]
        pfr_k = EXAMPLE_COUNTS["pfr"][0]
        limps, limp_n, _ = EXAMPLE_COUNTS["limp"]
        three_bet_n = EXAMPLE_COUNTS["three_bet"][1]
        flops = EXAMPLE_COUNTS["wtsd"][1]
        afq_k, afq_n, _ = EXAMPLE_COUNTS["afq"]
        flop_k, flop_n, _ = EXAMPLE_COUNTS["afq[flop]"]
        breakdown = dict(EXAMPLE_VPIP_BREAKDOWN)
        split = dict(EXAMPLE_OPEN_RAISE_SPLIT)
        sources = dict(EXAMPLE_FLOP_SOURCES)
        actions = dict(EXAMPLE_STREET_ACTIONS)
        aggression = dict(EXAMPLE_STREET_AGGRESSION)

        # The three parts of vpip, as the prose states them.
        self.equal(
            "example vpip breakdown sums to the vpip numerator",
            str(vpip_k),
            str(sum(breakdown.values())),
        )
        self.equal("example limps match the limp numerator", str(limps), str(breakdown["limps"]))
        self.equal("example preflop raises match pfr", str(pfr_k), str(breakdown["preflop raises"]))
        self.prose(
            "example history states the vpip breakdown",
            f"those {vpip_k} break down as **{breakdown['limps']}** limps, "
            f"**{breakdown['preflop raises']}** preflop raises and "
            f"**{breakdown['calls of a raise']}** calls of someone else's raise",
        )
        self.prose(
            "example history states the limp denominator against the hands dealt",
            f"**{limp_n}** of the {hands} hands",
        )

        # The 63 open raises faced, split into calls and folds.
        self.equal(
            "example open raises faced split into calls and folds",
            str(three_bet_n),
            str(sum(split.values())),
        )
        self.equal(
            "example calls of a raise are the same calls in both splits",
            str(breakdown["calls of a raise"]),
            str(split["calls"]),
        )
        self.prose(
            "example history states the calls-plus-folds split",
            f"the same {three_bet_n} spots are the {split['calls']} calls plus {split['folds']} folds",
        )
        self.prose(
            "example history states the reraises faced against the opens made",
            f"Having open-raised {pfr_k} times, they faced a reraise "
            f"**{EXAMPLE_COUNTS['fold_to_three_bet'][1]}** times",
        )

        # Where the flops come from.
        self.equal(
            "example flop sources sum to the flops seen",
            str(flops),
            str(sum(sources.values())),
        )
        self.true(
            "example flops from invested hands cannot exceed the investments",
            sources["hands invested in that reached a flop"] <= vpip_k,
            f"{sources['hands invested in that reached a flop']} of {vpip_k} investments",
        )
        self.prose(
            "example history states where the flops come from",
            f"saw **{flops}** flops: {sources['hands invested in that reached a flop']} of the "
            f"{vpip_k} hands they invested in, plus {sources['unraised big blinds']} big blinds",
        )

        # The afq numerator and denominator, street by street.
        self.equal(
            "example afq denominator is the sum of its streets",
            str(afq_n),
            str(sum(actions.values())),
        )
        self.equal(
            "example afq numerator is the sum of its streets",
            str(afq_k),
            str(sum(aggression.values())),
        )
        self.equal("example flop afq denominator matches the street split", str(flop_n), str(actions["flop"]))
        self.equal("example flop afq numerator matches the street split", str(flop_k), str(aggression["flop"]))
        self.equal(
            "example preflop bets or raises are the pfr numerator",
            str(pfr_k),
            str(aggression["preflop"]),
        )
        for street, count in EXAMPLE_STREET_ACTIONS:
            self.true(
                f"example {street} actions fit the spots that street offers",
                count <= EXAMPLE_STREET_CEILING[street],
                f"{count} {street} actions exceeds the {EXAMPLE_STREET_CEILING[street]} available",
            )
            self.true(
                f"example {street} bets or raises fit that street's actions",
                aggression[street] <= count,
                f"{aggression[street]} of {count}",
            )
        self.prose(
            "example history states the street split of its voluntary actions",
            f"Their voluntary postflop actions number {actions['flop']} on the flop, "
            f"{actions['turn']} on the turn and {actions['river']} on the river, which with "
            f"{actions['preflop']} preflop actions is the **{afq_n}** of the overall `afq`, "
            f"of which **{afq_k}** were a bet or a raise ({aggression['preflop']} preflop, "
            f"{aggression['flop']} flop, {aggression['turn']} turn, {aggression['river']} river)",
        )

    # -- The solve plan's cost arithmetic and the operator's seat priority --
    def check_solve_cost(self) -> None:
        total = len(SEAT_COUNTS) * len(STRATEGIES)
        minutes = total * SOLVE_ILLUSTRATION_MINUTES / 60.0
        hours = float(total * SOLVE_ILLUSTRATION_HOURS)
        days = hours / HOURS_PER_DAY
        self.prose(
            "section 4.5 cost of 32 runs at ten minutes each",
            f"{total} runs at ten minutes each is {fmt(minutes, 1)} hours already",
        )
        self.prose(
            "section 4.5 cost of 32 runs at an hour each",
            f"{total} runs at an hour each is {fmt(hours, 0)} hours, which is {fmt(days, 1)} days",
        )
        self.true(
            "section 4.5 an hour a run really does breach the no-multi-day cap",
            days > 1.0,
            f"{fmt(hours, 0)} hours is {fmt(days, 1)} days, which is not multi-day",
        )
        self.true(
            "section 4.5 ten minutes a run really does stay inside hours",
            minutes < HOURS_PER_DAY,
            f"{fmt(minutes, 1)} hours is not 'hours on one laptop'",
        )
        self.every_occurrence(
            "the total run count, wherever the document states it",
            r"seat counts = (\d+)|cost times (\d+)|with (\d+) runs in the plan|"
            r"(\d+) runs at ten minutes|(\d+) runs at an hour|for (\d+) against that cap|"
            r"the (\d+) runs below|If (\d+) runs are unaffordable|needs \*\*(\d+) of them\*\*|"
            r"Answer for one run and for (\d+)|which at (\d+) runs means|fails it at (\d+)|"
            r"Tier 1's (\d+) runs conditional|\| (\d+) solver runs,",
            str(total),
        )
        self.every_occurrence(
            "the runs saved by dropping one seat count, wherever it is stated",
            r"saves (\d+) runs, not|the (\d+) saved by dropping a seat count",
            str(len(STRATEGIES) - 1),
        )
        self.every_occurrence(
            "the saving against the strategies per seat count",
            r"saves \d+ runs, not (\d+)\*\*|The \d+ rather than (\d+) is forced",
            str(len(STRATEGIES)),
        )
        self.every_occurrence(
            "the provenance table's reading of that saving",
            r"The (\d+) rather than \d+ is forced",
            str(len(STRATEGIES) - 1),
        )
        self.every_occurrence(
            "the S_BASE floor, wherever it is stated",
            r"floor of \*\*(\d+) runs\*\*|saves (\d+) runs per bucket dropped|the (\d+)-run floor",
            str(len(SEAT_COUNTS)),
        )

    def check_seat_priority(self) -> None:
        """§4.5 records the operator's table-size priority and what follows from it."""
        self.prose("section 4.5 operator seat priority, verbatim", f'"{SEAT_PRIORITY_QUOTE}"')
        self.every_occurrence(
            "the heater task the seat priority is recorded as, wherever it is cited",
            r"recorded as heater task `([0-9a-f]+)`",
            SEAT_PRIORITY_TASK,
        )
        self.prose("section 4.5 seat priority is dated and sourced", SEAT_PRIORITY_SOURCE)
        band_lo, band_hi = SEAT_PRIORITY_ORDER[1], SEAT_PRIORITY_ORDER[2]
        self.prose(
            "section 4.5 what a 9-handed solve actually faces",
            f"A {band_hi}-handed solve seats\n{spell(band_hi - 1)} archetypes against the bot, "
            f"so its output carries an {spell(band_hi - 1)}-opponent\nmultiway discount",
        )
        self.prose(
            "section 4.5 what an 8-handed table presents instead",
            f"an {spell(band_hi - 1)}-opponent `{MAJORITY_RULE}` field; an {band_lo}-handed table "
            f"presents {spell(band_lo - 1)} of each",
        )
        self.prose(
            "section 4.5 what dropping the band would cost",
            f"strategy loses less at an {band_lo}-handed table than dropping that band's "
            f"{spell(len(STRATEGIES) - 1)}\ncounter-strategies loses",
        )
        self.prose(
            "section 4.5 the order a cut must follow",
            f"**Solve {SEAT_PRIORITY_ORDER[0]}-handed\nfirst; then {SEAT_PRIORITY_ORDER[1]}- and "
            f"{SEAT_PRIORITY_ORDER[2]}-handed as one band; then every remaining seat count.**",
        )
        self.prose(
            "section 4.5 the 8-versus-9 reconciliation",
            f'**"Treated the same" is a priority, not a shared solve: {SEAT_PRIORITY_ORDER[1]} and '
            f"{SEAT_PRIORITY_ORDER[2]} still need their\nown runs.**",
        )
        self.prose(
            "section 4.5 the condition under which one solve could serve both",
            f"The one condition that would let a single {SEAT_PRIORITY_ORDER[2]}-handed solve "
            f"serve both",
        )
        for seat in SEAT_PRIORITY_ORDER:
            self.true(
                f"section 4.5 priority seat count {seat} is a seat count the design covers",
                seat in SEAT_COUNTS,
                f"{seat} is outside {SEAT_COUNTS}",
            )

    # -- The provenance table, which restates many of the figures above ----
    def check_provenance_rows(self) -> None:
        """Every derived figure the provenance table repeats, checked there too."""
        anchors = []
        for _stat, p, _rate, _w in TABLE_C_ROWS:
            if fmt(p, 2) not in anchors:
                anchors.append(fmt(p, 2))
        self.prose(
            "provenance: Table C's anchor column",
            f"Table C's anchor `p̂` column ({', '.join(anchors)})",
        )
        rates = []
        for stat, _p, rate, _w in TABLE_C_ROWS:
            entry = f"`{stat}` {rate_text(stat, rate)}"
            if stat not in DEALT_IN_STATS and entry not in rates:
                rates.append(entry)
        self.prose(
            "provenance: Table C's opportunities-per-hand column",
            f"Table C's opportunities-per-hand column ({', '.join(rates)})",
        )
        self.prose(
            "provenance: the rate the dealt-in stats escape the placeholder at",
            f"escape the placeholder, at {fmt(1.00, 2)},",
        )
        self.every_occurrence(
            "the cube-root reading of Table B, wherever it is stated",
            r"`0\.5\^\(1/3\) ≈ ([\d.]+)`",
            fmt(0.5 ** (1 / 3), 3),
        )
        self.every_occurrence(
            "the fold-through a pot-sized bluff needs, as that reading writes it",
            r"`([\d.]+)\^\(1/3\) ≈ [\d.]+`",
            fmt(1.00 / (1 + 1.00), 1),
        )
        self.every_occurrence(
            "the p̂ range as the provenance table writes it",
            r"across `p̂` in (\d\.\d)–(\d\.\d)",
            *[fmt(p, 1) for p in PHAT_FLAT_RANGE],
        )
        self.every_occurrence(
            "the classification gate as the noise-exposure row writes it",
            r"on `vpip` at the `(\d\.\d)` gate|`confidence < (\d\.\d)` `UNKNOWN` gate",
            fmt(CLASSIFY_CONF_GATE, 1),
        )
        self.every_occurrence(
            "the hysteresis band as the provenance table writes it",
            r"Hysteresis dead-band `(\d\.\d+)`|gate and the `(\d\.\d+)` band",
            fmt(HYSTERESIS_BAND, 2),
        )
        self.every_occurrence(
            "the hysteresis hold, wherever it is stated",
            r"hold for `(\d+)` consecutive|the `(\d+)`-hand hold|"
            r"the `(\d+)` consecutive-hand hold",
            str(HYSTERESIS_HOLD),
        )
        self.every_occurrence(
            "the flag margins as the provenance table lists them",
            r"all flag margins \((\d\.\d+)/(\d\.\d+)\)",
            fmt(max(f["margin"] for f in FLAGS.values()), 2),
            fmt(min(f["margin"] for f in FLAGS.values()), 2),
        )
        self.every_occurrence(
            "the flag gates as the provenance table lists them",
            r"flag confidence gates \((\d\.\d+)/(\d\.\d+)\)",
            fmt(min(f["gate"] for f in FLAGS.values()), 1),
            fmt(max(f["gate"] for f in FLAGS.values()), 1),
        )
        self.every_occurrence(
            "the V3 holdout as the provenance table lists it",
            r"the (\d+)/(\d+) V3 holdout split",
            str(V3_HOLDOUT[0]),
            str(V3_HOLDOUT[1]),
        )
        self.every_occurrence(
            "the example's hands and vpip as the provenance table lists them",
            r"\((\d+) hands, ([\d.]+) vpip",
            str(EXAMPLE_HANDS),
            fmt(
                shrunk_rate(
                    EXAMPLE_COUNTS["vpip"][2],
                    PRIOR_STRENGTH["vpip"],
                    EXAMPLE_COUNTS["vpip"][0],
                    EXAMPLE_COUNTS["vpip"][1],
                ),
                2,
            ),
        )
        self.every_occurrence(
            "the seat priority order, wherever it is stated",
            r"Solve (\d)-handed first; then (\d)- and (\d)-handed as one band|"
            r"(\d)-handed first, then (\d)- and (\d)-handed as one band",
            *[str(seat) for seat in SEAT_PRIORITY_ORDER],
        )
        # The rounding convention the whole script depends on, worked in the prose.
        example = Decimal("6.25")
        half_up = example.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        half_even = example.quantize(Decimal("0.1"), rounding=ROUND_HALF_EVEN)
        self.prose(
            "provenance: the half-up rounding convention, worked",
            f"{example}%\nprints as {half_up}%, not {half_even}%",
        )
        self.true(
            "the script really does round half-up",
            fmt(float(example), 1) == str(half_up) != str(half_even),
            f"fmt gives {fmt(float(example), 1)}, half-up gives {half_up}",
        )

    # -- The forefront-rule bullets, quoted from CLAUDE.md -----------------
    def check_forefront_quotes(self) -> None:
        """§1 quotes CLAUDE.md's forefront bullets verbatim; drift must fail."""
        source = self.doc.path.parent / FOREFRONT_SOURCE
        if not source.exists():
            source = DEFAULT_DOC.parent / FOREFRONT_SOURCE
        self.true(f"{FOREFRONT_SOURCE} is readable", source.exists(), f"no {source}")
        if not source.exists():
            return
        rule = section_bullets(Document(source), FOREFRONT_SECTION)
        self.true(f"{FOREFRONT_SOURCE} states its forefront rule as bullets", bool(rule), "no bullets")
        quotes = section_quotes(self.doc, FOREFRONT_QUOTED_IN)
        self.equal(
            "the number of forefront-rule bullets §1 quotes",
            FOREFRONT_QUOTE_COUNT,
            len(quotes),
        )
        for quote in quotes:
            opener = " ".join(quote.split()[:4])
            match = next((bullet for bullet in rule if bullet.startswith(opener)), None)
            self.equal(
                f"§1 quotes {FOREFRONT_SOURCE}'s '{opener}...' bullet verbatim",
                match if match is not None else f"no {FOREFRONT_SOURCE} bullet opening '{opener}'",
                quote,
            )

    # -- The measured rates, checked against the document they are cited from
    def check_baseline_citation(self) -> None:
        """Table C's two measured rates must still be what OPPONENT_BASELINE says.

        The design cites them by section; this reads that section and compares,
        so re-measuring there and not here fails the run rather than passing
        quietly with a stale number.
        """
        source = self.doc.path.parent / BASELINE_SOURCE
        if not source.exists():
            source = DEFAULT_DOC.parent / BASELINE_SOURCE
        self.true(f"{BASELINE_SOURCE} is readable", source.exists(), f"no {source}")
        if not source.exists():
            return
        baseline = Document(source)
        self.true(
            f"{BASELINE_SOURCE} still carries the cited section",
            BASELINE_SECTION in baseline.lines,
            f"no heading {BASELINE_SECTION!r}",
        )
        pooled = baseline.table_after(BASELINE_POOLED_TABLE)
        header, body = pooled[0], pooled[1:]
        row = next((r for r in body if r[0] == BASELINE_SEATS), None)
        self.true(
            f"{BASELINE_SOURCE} §2 has a {BASELINE_SEATS}-seat pooled row",
            row is not None,
            f"no row for {BASELINE_SEATS} seats",
        )
        if row is None:
            return
        for stat, column in BASELINE_COLUMNS.items():
            self.true(
                f"{BASELINE_SOURCE} §2 still has a {column!r} column",
                column in header,
                f"columns are {header}",
            )
            if column not in header:
                continue
            cited = row[header.index(column)]
            here = rate_text(stat, MEASURED_RATES[stat])
            self.true(
                f"Table C's measured {stat} rate against {BASELINE_SOURCE} §2",
                cited == here,
                f"{BASELINE_SOURCE} §2 measures {cited!r} in its {column!r} column, "
                f"Table C carries {here!r}",
            )
        per_size = baseline.table_after(BASELINE_SECTION)
        header = per_size[0]
        row = next((r for r in per_size[1:] if r[0] == BASELINE_SEATS), None)
        cited_hands = row[header.index("Hands")] if row is not None else "no nine-seat row"
        self.true(
            f"the {BASELINE_SEATS}-handed hand count §4.2 quotes from {BASELINE_SOURCE} §2",
            cited_hands == BASELINE_NINE_HANDED_HANDS,
            f"{BASELINE_SOURCE} §2 counts {cited_hands!r} nine-handed hands, "
            f"the citation says {BASELINE_NINE_HANDED_HANDS!r}",
        )
        self.prose(
            "section 4.2 quotes the hand count the measured rates rest on",
            f"document's {BASELINE_NINE_HANDED_HANDS} nine-handed hands",
        )
        self.prose(
            "the provenance table quotes the same hand count",
            f"over {BASELINE_NINE_HANDED_HANDS} nine-handed hands",
        )

    # -- Figures the document states in more than one place ----------------
    def check_restated_constants(self) -> None:
        """Constants the prose repeats. Every copy has to say the same thing."""
        tier_values = [str(value) for _t, value, _s in PRIOR_STRENGTH_GROUPS]
        self.every_occurrence("Z95 wherever a half-width is written", r"`?(\d\.\d+)·√", fmt(Z95, 2))
        self.every_occurrence("Z95 in Table C's formula", r"\((\d\.\d+)/w\)²", fmt(Z95, 2))
        self.every_occurrence(
            "the confidence level those intervals are read at",
            r"(\d+)% (?:confidence interval|half-width)",
            "95",
        )
        self.every_occurrence("WARMUP_HANDS", r"WARMUP_HANDS = (\d+)", str(WARMUP_HANDS))
        self.every_occurrence(
            "WARMUP_HANDS wherever §5.2 argues about it without naming it",
            r"what (\d+) buys|(\d+) is \*\*not\*\* a convergence point|"
            r"At (\d+) hands the same formula|the width (\d+) actually buys|"
            r"§5\), also per opponent\. (\d+) is a deliberately shorter|"
            r"from (\d+) on, neither",
            str(WARMUP_HANDS),
        )
        self.every_occurrence(
            "MIN_CLASSIFY_HANDS wherever §5.2 argues about it without naming it",
            r"Below (\d+) hands\s+both gates refuse|at that same\s+(\d+) the Tier A",
            str(MIN_CLASSIFY_HANDS),
        )
        # The two gates clear at different hand counts, and §4.5 and §5.2 both
        # state where each one binds. Those boundaries are MIN_CLASSIFY_HANDS and
        # WARMUP_HANDS read off against each other, so they are derived figures
        # and every copy of them has to move when either constant moves.
        self.every_occurrence(
            "the hand span over which the two gates disagree, wherever it is stated",
            r"between (\d+) and (\d+) stored hands|from (\d+) to (\d+) they disagree",
            str(MIN_CLASSIFY_HANDS),
            str(WARMUP_HANDS - 1),
        )
        self.every_occurrence(
            "the hand count warm-up clears at, wherever the prose states it bare",
            r"[Ww]arm-up clears at (\d+)",
            str(WARMUP_HANDS),
        )
        self.every_occurrence(
            "the two gates' clearing points where §5.2 sets them side by side",
            r"clear at different\s+points — (\d+) hands against (\d+)",
            str(WARMUP_HANDS),
            str(MIN_CLASSIFY_HANDS),
        )
        self.every_occurrence(
            "the Table C anchors §5.2 reads the warm-up widths at",
            r"its (\d\.\d+) anchor and ±[\d.]+pp on `pfr` at (\d\.\d+)",
            fmt(TABLE_C_ANCHORS["vpip"], 2),
            fmt(TABLE_C_ANCHORS["pfr"], 2),
        )
        self.every_occurrence("HALF_LIFE", r"HALF_LIFE = (\d+)", str(HALF_LIFE))
        self.every_occurrence("MIN_POOL_HANDS", r"MIN_POOL_HANDS = (\d+)", str(MIN_POOL_HANDS))
        self.every_occurrence(
            "MIN_POOL_OPPONENTS", r"MIN_POOL_OPPONENTS = (\d+)", str(MIN_POOL_OPPONENTS)
        )
        self.every_occurrence(
            "MIN_CLASSIFY_HANDS", r"MIN_CLASSIFY_HANDS = (\d+)", str(MIN_CLASSIFY_HANDS)
        )
        self.every_occurrence("MIN_STACK_BB", r"MIN_STACK_BB = (\d+)", str(MIN_STACK_BB))
        self.every_occurrence(
            "VPIP_SPLIT wherever the document states its value",
            r"VPIP_SPLIT = (\d\.\d+)|VPIP_SPLIT` \*\*defaults to (\d\.\d+)\*\*|"
            r"VPIP_SPLIT`'s (\d\.\d+)|`vpip ≤ (\d\.\d+)`|So (\d\.\d+) is a biased|"
            r"sit \*below\* (\d\.\d+) by the share|using (\d\.\d+) anyway",
            fmt(VPIP_SPLIT, 2),
        )
        self.every_occurrence(
            "VPIP_SPLIT wherever the document writes it as a percentage",
            r"≤(\d+)% of them|literature threshold at (\d+)%",
            fmt(VPIP_SPLIT * 100, 0),
        )
        self.prose(
            "the plain-words opening's four-hand scorecard",
            f'raised two of them, they are not "a {pct(2 / 4, 0)} raiser"',
        )
        self.every_occurrence(
            "the heads-up seat count §1 points at",
            r"and what changes at (\d)\)",
            str(SEAT_COUNTS[0]),
        )
        self.every_occurrence(
            "AFQ_SPLIT wherever the document states its value",
            r"AFQ_SPLIT = (\d\.\d+)|AFQ_SPLIT` \*\*defaults to (\d\.\d+)\*\*|AFQ_SPLIT`'s (\d\.\d+)",
            fmt(AFQ_SPLIT, 2),
        )
        self.every_occurrence(
            "AFQ_SPLIT where §4.4 writes it as an AFq value",
            r"`AFq = (\d\.\d+)` is the nearest",
            fmt(AFQ_SPLIT, 1),
        )
        self.every_occurrence(
            "the classification confidence gate, wherever it is stated",
            r"`confidence\(vpip\) ≥ (\d\.\d)`|`confidence\(vpip\) < (\d\.\d)`|"
            r"matching `afq` confidence of (\d\.\d+)|Both gates — the `(\d\.\d+)` confidence|"
            r"`PRIOR_STRENGTH`, the `(\d\.\d+)` gate|the `(\d\.\d+)` `vpip`-confidence gate",
            fmt(CLASSIFY_CONF_GATE, 1),
        )
        self.every_occurrence(
            "Tier A's prior strength where §4.4 inverts the gate with it",
            r"with Tier A's `s` = (\d+) inverts",
            str(PRIOR_STRENGTH["vpip"]),
        )
        self.every_occurrence(
            "MIN_CLASSIFY_HANDS where §4.4 anchors it to the Tier A crossover",
            r"The (\d+) is anchored to the Tier A crossover",
            str(MIN_CLASSIFY_HANDS),
        )
        self.every_occurrence(
            "HALF_LIFE where §4.3 calls it a starting value",
            r"only matters across weeks; (\d+) is a",
            str(HALF_LIFE),
        )
        self.every_occurrence(
            "the least favourable p̂ wherever §4.4 reads an unanchored stat at it",
            r"`p̂ = (\d\.\d+)`",
            fmt(LEAST_FAVOURABLE_P, 1),
        )
        self.every_occurrence(
            "the p̂ range Table C claims the interval is flat across",
            r"barely moves for `p̂` between (\d\.\d+) and (\d\.\d+)",
            *[fmt(p, 1) for p in PHAT_FLAT_RANGE],
        )
        lo, hi = (half_width(p, 100) for p in PHAT_FLAT_RANGE)
        widest = half_width(LEAST_FAVOURABLE_P, 100)
        self.true(
            "the interval really is flat across that p̂ range",
            max(abs(widest - lo), abs(widest - hi)) / widest < PHAT_FLAT_TOLERANCE,
            f"the width moves more than {PHAT_FLAT_TOLERANCE:.0%} across {PHAT_FLAT_RANGE}",
        )
        self.every_occurrence(
            "the confidence the equal-weight sample size corresponds to",
            r"`confidence` passes (\d\.\d+)",
            fmt(confidence(1, 1), 1),
        )
        self.true(
            "confidence really does pass that value exactly at n = s",
            all(confidence(s, s) == confidence(1, 1) for s in PRIOR_STRENGTH.values()),
            "confidence(n=s) is not the same number for every prior strength",
        )
        self.every_occurrence(
            "the three PRIOR_STRENGTH values, listed in the prose",
            r"`PRIOR_STRENGTH` values — (\d+), (\d+) and (\d+) —",
            *tier_values,
        )
        self.every_occurrence(
            "the PRIOR_STRENGTH values as the provenance table lists them",
            r"`PRIOR_STRENGTH` values \((\d+)/(\d+)/(\d+)",
            *tier_values,
        )
        self.every_occurrence(
            "check_raise's PRIOR_STRENGTH where §4.3 justifies its tier",
            r"quotes for it are `s` = (\d+) figures",
            str(PRIOR_STRENGTH["check_raise"]),
        )
        self.every_occurrence(
            "the two illustrative `s` values Table D adds to the tiers",
            r"`s`=(\d+) and `s`=(\d+) are included only",
            *[str(s) for s in TABLE_D_S if s not in {v for _t, v, _ in PRIOR_STRENGTH_GROUPS}],
        )
        self.every_occurrence(
            "Table C's remaining placeholder opportunity rates",
            r"invented here: (\d\.\d+) and (\d\.\d+) are round",
            *[fmt(r, 2) for r in sorted(PLACEHOLDER_RATES)],
        )
        self.every_occurrence(
            "the measured opportunity rates wherever §4.2 names them together",
            r"`fold_to_cbet` at \*\*(\d\.\d+)\*\* and `wtsd` at\s+\*\*(\d\.\d+)\*\*",
            *[rate_text(stat, MEASURED_RATES[stat]) for stat in ("fold_to_cbet", "wtsd")],
        )
        self.every_occurrence(
            "the measured opportunity rates where the provenance table names them",
            r"`fold_to_cbet` (\d\.\d+) and `wtsd` (\d\.\d+) are the nine-handed",
            *[rate_text(stat, MEASURED_RATES[stat]) for stat in ("fold_to_cbet", "wtsd")],
        )
        self.every_occurrence(
            "the rate the dealt-in stats are forced to",
            r"carry a rate of (\d\.\d+)",
            fmt(1.00, 2),
        )
        self.every_occurrence(
            "the decay base, which is what HALF_LIFE halves",
            r"`d = (\d\.\d+) \*\* \(hands_elapsed / HALF_LIFE\)`",
            fmt(HALF_LIFE_BASE, 1),
        )
        self.every_occurrence(
            "the flag margins and gates where §4.4 lists them together",
            r"gates — (\d\.\d+), the tighter (\d\.\d+) on `NEVER_RAISES`, and the "
            r"`(\d\.\d+)` and `(\d\.\d+)` confidence gates",
            fmt(max(f["margin"] for f in FLAGS.values()), 2),
            fmt(min(f["margin"] for f in FLAGS.values()), 2),
            fmt(min(f["gate"] for f in FLAGS.values()), 1),
            fmt(max(f["gate"] for f in FLAGS.values()), 1),
        )
        self.every_occurrence(
            "the hysteresis band and hold where §4.4 names them together",
            r"The `(\d\.\d+)` dead-band and the `(\d+)`-hand hold",
            fmt(HYSTERESIS_BAND, 2),
            str(HYSTERESIS_HOLD),
        )
        self.every_occurrence(
            "the hysteresis band wherever §4.4 measures noise against it",
            r"`(\d\.\d+)` dead-band|dead-band of `(\d\.\d+)`|past `(\d\.\d+)`, and a dead-band|"
            r"to the `(\d\.\d+)` band needs|a `(\d\.\d+)`-tight gate",
            fmt(HYSTERESIS_BAND, 2),
        )
        self.every_occurrence(
            "the V3 holdout, held-out share", r"last (\d+)% of logged hands", str(V3_HOLDOUT[1])
        )
        self.every_occurrence(
            "the V3 holdout, training share", r"built on the first (\d+)%", str(V3_HOLDOUT[0])
        )
        self.every_occurrence(
            "the V3 holdout split as a ratio",
            r"the (\d+)/(\d+) split",
            str(V3_HOLDOUT[0]),
            str(V3_HOLDOUT[1]),
        )
        self.every_occurrence(
            "the seat range the design must cover",
            r"every table size from (\d) to (\d) players|Every size from (\d) to (\d) is still "
            r"required|seat counts \((\d) to (\d) players\)|seat counts, (\d) to (\d) players",
            str(SEAT_COUNTS[0]),
            str(SEAT_COUNTS[-1]),
        )
        self.every_occurrence(
            "the example's hand count wherever the prose restates it",
            r"the same (\d+) hands|Across \*\*(\d+)\*\* hands dealt|one coherent (\d+)-hand history",
            str(EXAMPLE_HANDS),
        )
        self.every_occurrence(
            "the example's flops seen wherever the prose restates it",
            r"Of those (\d+) flops",
            str(EXAMPLE_COUNTS["wtsd"][1]),
        )

    # -- Everything ------------------------------------------------------
    def run(self) -> None:
        checks = [
            ("Table A", self.check_table_a),
            ("Table B", self.check_table_b),
            ("Table C", self.check_table_c),
            ("Table D", self.check_table_d),
            ("Table E", self.check_table_e),
            ("PRIOR_STRENGTH table", self.check_prior_strength_table),
            ("stat tier coverage", self.check_every_stat_has_a_tier),
            ("flag conditions", self.check_flag_conditions),
            ("flag margin-versus-interval table", self.check_margin_interval_table),
            ("flag margin prose", self.check_margin_prose),
            ("bucket boundary exposure", self.check_boundary_exposure),
            ("Tier 1 solve plan", self.check_solve_plan),
            ("stated constants", self.check_stated_constants),
            ("warm-up widths", self.check_warmup),
            ("Tier 0 worked example", self.check_example),
            ("Tier 1 solve cost arithmetic", self.check_solve_cost),
            ("operator seat priority", self.check_seat_priority),
            ("provenance table", self.check_provenance_rows),
            ("measured-rate citation", self.check_baseline_citation),
            ("forefront-rule quotes", self.check_forefront_quotes),
            ("restated constants", self.check_restated_constants),
        ]
        for name, check in checks:
            try:
                check()
            except LookupError as exc:
                # A table or block the document is supposed to carry has moved or
                # gone; that is a mismatch too, not a crash.
                self.checked += 1
                self.failures.append(f"{name}: cannot be checked -- {exc}")


def spell(n: int) -> str:
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
    }
    return words.get(n, str(n))


def main(argv: list[str]) -> int:
    # A failing figure named with a character the console cannot encode
    # (the ceiling brackets in the majority rule, on a cp1252 Windows
    # console) must print as a replacement character, not crash the run.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_DOC
    if not path.exists():
        print(f"design document not found: {path}", file=sys.stderr)
        return 2
    checker = Checker(Document(path))
    checker.run()
    if checker.failures:
        print(f"{len(checker.failures)} of {checker.checked} figures in {path.name} do not match:")
        for failure in checker.failures:
            print(f"  - {failure}")
        return 1
    print(f"{checker.checked} figures in {path.name} all match the constants they derive from.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
