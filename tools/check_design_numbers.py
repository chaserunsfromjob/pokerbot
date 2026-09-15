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
"""

from __future__ import annotations

import math
import re
import sys
from decimal import Decimal, ROUND_HALF_UP
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
# `rate` 1.00 is not a placeholder: it is forced by a "was dealt in" denominator
# in section 4.2. Every other rate is one of the three placeholders below.
PLACEHOLDER_RATES = {0.08, 0.15, 0.30}
DEALT_IN_STATS = {"vpip", "pfr"}
TABLE_C_ROWS = [
    # (stat, anchor p-hat, opportunities per hand, target half-width)
    ("vpip", 0.30, 1.00, 0.05),
    ("vpip", 0.30, 1.00, 0.03),
    ("pfr", 0.20, 1.00, 0.05),
    ("three_bet", 0.07, 0.15, 0.02),
    ("fold_to_three_bet", 0.60, 0.08, 0.10),
    ("fold_to_cbet", 0.50, 0.15, 0.10),
    ("wtsd", 0.25, 0.30, 0.05),
]
# The anchor each stat is read at wherever an interval is taken for it.
TABLE_C_ANCHORS = {stat: p for stat, p, _rate, _w in TABLE_C_ROWS}
# Stats with no Table C anchor are read at the least favourable p-hat.
LEAST_FAVOURABLE_P = 0.5

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
    # At most one voluntary action per street: 412 preflop, and 205 on each of
    # the three postflop streets the example's flops can reach.
    (768, "voluntary actions", 412 + 3 * 205),
    (92, "bets or raises", 768),
]

DEFAULT_DOC = Path(__file__).resolve().parent.parent / "OPPONENT_MODEL_DESIGN.md"

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
        rows = self.doc.table_after("#### Table B: the multiway problem")[1:]
        self.equal("Table B row count", len(FOLD_RATES), len(rows))
        for p, row in zip(FOLD_RATES, rows):
            self.equal(f"Table B fold rate label {p}", pct(p, 0), row[0])
            for n, cell in zip(OPPONENT_COUNTS, row[1:]):
                self.equal(f"Table B p={p} n={n}", pct(p ** n), cell)
        self.prose(
            "section 2.4 cube-root reading of Table B",
            f"`0.5^(1/3) ≈ {fmt(0.5 ** (1 / 3), 3)}`",
        )

    # -- Table C ----------------------------------------------------------
    def check_table_c(self) -> None:
        rows = self.doc.table_after("#### Table C: how many hands each stat needs")[1:]
        self.equal("Table C row count", len(TABLE_C_ROWS), len(rows))
        for (stat, p, rate, w), row in zip(TABLE_C_ROWS, rows):
            tag = f"Table C {stat} ±{w}"
            self.equal(f"{tag} stat", stat, row[0])
            self.equal(f"{tag} anchor", fmt(p, 2), row[1])
            self.equal(f"{tag} opportunities per hand", fmt(rate, 2), row[2])
            self.equal(f"{tag} target width", "±" + fmt(w * 100, 0) + "pp", row[3])
            opps = opportunities_needed(p, w)
            self.equal(f"{tag} opportunities needed", fmt(opps, 0, thousands=True), row[4])
            self.equal(f"{tag} hands needed", fmt(opps / rate, 0, thousands=True), row[5])
            # Every rate is either forced by a "dealt in" denominator or a placeholder.
            if stat in DEALT_IN_STATS:
                self.true(f"{tag} rate is one per hand dealt", rate == 1.00, f"rate {rate}")
            else:
                self.true(
                    f"{tag} rate is a placeholder",
                    rate in PLACEHOLDER_RATES,
                    f"rate {rate} is not one of {sorted(PLACEHOLDER_RATES)}",
                )
        three_bet_rate = next(rate for stat, _p, rate, _w in TABLE_C_ROWS if stat == "three_bet")
        three_bet_row = next(row for row in TABLE_C_ROWS if row[0] == "three_bet")
        self.prose(
            "section 4.2 three_bet expectation sentence",
            f"at a placeholder {fmt(three_bet_rate, 2)}\nopportunities per hand a "
            f"±{fmt(three_bet_row[3] * 100, 0)}pp reading of a {fmt(three_bet_row[1] * 100, 0)}% behaviour",
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
            f"{fmt(half_width(LEAST_FAVOURABLE_P, opportunities_at_gate(PRIOR_STRENGTH['limp'], FLAGS['LIMPS']['gate'])), 3)},",
        )
        # The check_raise bound -- only reproducible at PRIOR_STRENGTH 25.
        spec = FLAGS["NEVER_RAISES"]
        s_cr = PRIOR_STRENGTH["check_raise"]
        bound = baseline_bound_for_leg(spec["margin"], spec["gate"], s_cr)
        n_cr = opportunities_at_gate(s_cr, spec["gate"])
        self.prose(
            "section 4.4 check_raise baseline bound",
            f"baseline is below about {fmt(bound, 3)}",
        )
        self.prose(
            "section 4.4 check_raise bound derivation",
            f"the leg's gate is `{fmt(spec['gate'], 1)}`, so\nit admits "
            f"`n = {s_cr}·{fmt(spec['gate'], 1)}/{fmt(1 - spec['gate'], 1)} = {fmt(n_cr, 1)}` "
            f"opportunities at fewest, and {fmt(bound, 3)} is the `p̂`",
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
            self.prose(f"section 4.4 {axis} raw exposure", f"**±{pp(w)}**" if axis == "vpip" else f"±{pp(w)} raw")
            self.prose(f"section 4.4 {axis} shrunk exposure", f"±{pp(shrunk_w)}")
            needed_gate = gate_for_band(split, s, HYSTERESIS_BAND)
            needed_n = opportunities_at_gate(s, needed_gate)
            self.prose(
                f"section 4.4 {axis} gate needed for the band",
                f"`confidence({axis}) ≥ {fmt(needed_gate, 3)}`",
            )
            self.prose(f"section 4.4 {axis} sample needed for the band", fmt(needed_n, 0, thousands=True))
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
        self.prose(
            "section 4.4 dead-band",
            f"dead-band of `{fmt(HYSTERESIS_BAND, 2)}` before",
        )
        self.prose("section 4.5 majority rule", f"`{MAJORITY_RULE}` of the `n` live opponents")
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
        self.equal(
            "example vpip breakdown",
            str(EXAMPLE_COUNTS["vpip"][0]),
            str(106 + 41 + 30),
        )
        self.equal(
            "example three_bet opportunities split into calls and folds",
            str(EXAMPLE_COUNTS["three_bet"][1]),
            str(30 + 33),
        )
        self.equal(
            "example afq denominator is the sum of its streets",
            str(EXAMPLE_COUNTS["afq"][1]),
            str(400 + 168 + 118 + 82),
        )
        self.equal(
            "example afq numerator is the sum of its streets",
            str(EXAMPLE_COUNTS["afq"][0]),
            str(41 + 27 + 15 + 9),
        )
        self.equal(
            "example flop afq denominator matches the history",
            str(EXAMPLE_COUNTS["afq[flop]"][1]),
            "168",
        )
        self.equal(
            "example preflop raises match pfr",
            str(EXAMPLE_COUNTS["pfr"][0]),
            "41",
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
