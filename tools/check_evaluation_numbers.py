#!/usr/bin/env python3
"""Check every derived number in EVALUATION_STRATEGY.md against its constants.

The evaluation strategy states a handful of constants -- published standard
deviations, a significance and power setting, the grid axes, the table-size
weights, the machine placeholders -- and then derives several hundred figures
from them: the sample-size table, the paired-rho table, the variance-reduction
multipliers, the duplicate factorials, the budget rows, the weighted-headline
arithmetic, and a scattering of figures in the prose. Four review rounds in a
row found a figure that no longer matched the constant it came from.

This script exists so that class of defect is found by a machine instead. Every
constant the document declares is held ONCE, here, in the CONSTANTS section
below. Everything else is recomputed from those constants and compared against
what the document prints. Exit status 0 means every printed figure matches; exit
status 1 prints one line per figure that does not.

Standard library only. Run it from anywhere:

    python3 tools/check_evaluation_numbers.py [path/to/EVALUATION_STRATEGY.md]

Rule for anyone editing the document: change the constant here and the prose
there in the same edit, and let this script say whether the prose is still right.

Second rule, taken from `tools/check_design_numbers.py` on `main`, which pins
`OPPONENT_MODEL_DESIGN.md` the same way: a figure the document states in more
than one place has to be checked in *every* place. `Checker.every_occurrence` is
how that question is asked; `Checker.prose` is only safe for a phrase that
appears once. The standard this file is held to is that mutating any derived
figure in the document, anywhere, makes this script exit 1.

This checker is deliberately standalone: the branch it was written on predates
trunk's checker, so it shares no code with it. Once both have landed the two
should be consolidated -- filed as a finding rather than done here.
"""

from __future__ import annotations

import math
import re
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

# ---------------------------------------------------------------------------
# CONSTANTS -- the single place every constant the document declares is written.
# Nothing below this block may hard-code a figure; it must read it here.
# ---------------------------------------------------------------------------

# -- Statistics -------------------------------------------------------------

# Section 2.5 Step 2: two-sided 5% significance, 80% power. The document prints
# (z_0.975 + z_0.80)^2 as 7.8489 and says the tables are computed at full
# precision, which is this value.
ALPHA = 0.05
BETA = 0.20
Z_SUM_SQ_FULL = 7.848879734
Z_SUM_SQ_DISPLAY = "7.8489"

# Section 3.5: Wald's sequential probability ratio test boundaries.
SPRT_A_DISPLAY = "16.0"
SPRT_B_DISPLAY = "0.2105"

# -- Published figures the derivations start from ---------------------------

# Burch et al. 2018, Table 3: heads-up no-limit per-hand SD in chips, raw and
# after AIVAT, in a game whose big blind is 2 chips (arXiv:1612.06915v2).
AIVAT_SD_RAW_CHIPS = 25.962
AIVAT_SD_AIVAT_CHIPS = 8.095
CHIPS_PER_BIG_BLIND = 2

# Brown 2020 section 6.6: six-player standard errors over 10,000 hands, and
# Pluribus's own edge over elite professionals.
PLURIBUS_HANDS = 10000
PLURIBUS_SE_5H1AI = 25
PLURIBUS_SE_1H5AI = 15
PLURIBUS_EDGE_MBB = 48

# The four per-hand standard deviations section 2.5 Step 1 tabulates, in the
# order it tabulates them, with the label each row carries.
SIGMA_ROWS = [
    ("Heads-up no-limit, raw chip count", "raw_hunl"),
    ("Heads-up no-limit, after AIVAT", "aivat_hunl"),
    ("Six-player no-limit, after AIVAT (5 humans + 1 AI)", "five_h_one_ai"),
    ("Six-player no-limit, after AIVAT (1 human + 5 AI)", "one_h_five_ai"),
]

# The sample-size table's rows (sigma, and the label the document prints) and
# its columns (the effect size Delta each column is computed at).
SAMPLE_SIZE_ROWS = [
    (12981.0, "12,981 (HUNL raw)"),
    (4047.5, "4,047.5 (HUNL, AIVAT)"),
    (2500.0, "2,500 (6-max, AIVAT)"),
    (1500.0, "1,500 (6-max, AIVAT)"),
]
SAMPLE_SIZE_DELTAS = [10, 25, 50, 100, 200]

# The paired-rho table: section 2.5 Step 3, computed at this sigma and Delta.
RHO_SIGMA = 12981.0
RHO_DELTA = 50
RHO_VALUES = [0.0, 0.3, 0.5, 0.7, 0.9]

# The variance-reduction multiplier table: an r% reduction in standard error
# multiplies the hands needed by (1-r)^2.
REDUCTION_ROWS = [
    (0.20, "20% (LBR's duplicate + imaginary observations)"),
    (0.35, "35% (mid-range of baseline at 3 players)"),
    (0.50, "50% (top of baseline's range at 3 players)"),
    (0.68, "68% (AIVAT, counterfactual regret minimisation — CFR — value functions)"),
    (0.85, "85% (AIVAT, DeepStack value functions)"),
]

# -- The game and the engine ------------------------------------------------

SEAT_COUNTS = list(range(2, 10))  # 2 to 9 players inclusive, section 4.1
HOLE_CARDS = 2
BOARD_CARDS = 5
SHORT_DECK_CARDS = 20  # the vendored engine's deck, REFERENCE_NOTES.md on main
FULL_DECK_CARDS = 52

# Lisy & Bowling 2017's bet-size grid: 55 pot fractions plus the all-in bet.
LBR_GRID_BASE = 0.05
LBR_GRID_RATIO = 1.15
LBR_GRID_K_MAX = 54

# ENGINE_ALTERNATIVES.md on branch worker/7f09949cb56f at commit 52bd81d:
# median complete hands per second over six repeats, six-handed, one core, by
# betting mode. The superseded figure is the one an earlier draft (54afe67)
# gave; it is held here only so the document cannot quietly go back to it.
ENGINE_SURVEY_BRANCH = "worker/7f09949cb56f"
ENGINE_SURVEY_COMMIT = "52bd81d"
ENGINE_SUPERSEDED_COMMIT = "54afe67"
ENGINE_HANDS_PER_SEC_REAL_SIZING = 4438
ENGINE_HANDS_PER_SEC_MENU = 47564
ENGINE_SUPERSEDED_HANDS_PER_SEC = "56,414"

# -- The grid and the budget ------------------------------------------------

# Section 3.6, the full grid as specified.
FULL_GRID_COMPOSITIONS = 10  # 9 homogeneous + 1 mixed
FULL_GRID_STACK_DEPTHS = 3

# Section 3.6, the reduced grid that actually runs.
NIGHTLY_FIXED_SEATS = [2, 6, 8, 9]
ROTATION_CYCLE = [3, 4, 5, 7]
REDUCED_COMPOSITIONS = 4  # one mixed plus three homogeneous
REDUCED_STACK_DEPTHS = 1  # 100 bb only

# Hands per arm per cell at each run's per-cell power, from the sigma = 1,500
# row of the section 2.5 table. Each is 2*sigma^2*Z/Delta^2 per arm; the
# document's "hands/cell" column is the two arms together.
BUDGET_SIGMA = 1500.0
FULL_GRID_DELTA = 50
NIGHTLY_DELTA = 100
ROUTINE_DELTA = 200

# The wall-clock placeholders, section 3.6. None is measured; they are X7(b),
# X7(c) and X8, and the document says so at the point of use.
SECONDS_PER_DECISION = 0.25
DECISIONS_PER_HAND = 4
PARALLEL_WORKERS = 8
MACHINE_CORES = 10
MACHINE_PERFORMANCE_CORES = 4
MACHINE_EFFICIENCY_CORES = 6
SECONDS_PER_HOUR = 3600
HOURS_PER_DAY = 24

# The two run-length caps, section 3.6. Design choices, not the operator's.
ACCEPTANCE_CAP_HOURS = 10
ROUTINE_CAP_HOURS = 1

# The worker counts section 3.6 works the nightly run against.
WORKER_COUNTS_CHECKED = [4, 3]

# -- The table-size weights, section 3.5 point 2 ----------------------------

WEIGHT_PRIMARY = 0.50  # n = 6
WEIGHT_SECONDARY = 0.30  # n = 8 and n = 9 as one band
WEIGHT_REST = 0.20  # split equally over whichever other seat counts ran
PRIMARY_SEATS = [6]
SECONDARY_SEATS = [8, 9]

# The release gate, stated in these words in five places. The document's own
# claim is that every copy is identical, so the checker holds one copy and
# counts.
GATE_OCCURRENCES = 5
GATE_TEXT = (
    "A release requires every seat count from 2 to 9 to have passed within the "
    "last four nightly acceptance runs. The window counts runs, not bot "
    "versions: an earlier run's pass still counts when the bot SHA has changed "
    "since, and the report prints the date and bot SHA of every last pass "
    "beside it. A seat count whose last pass falls outside that window prints "
    "as NOT GATED and blocks the release exactly as a failure would."
)
GATE_WINDOW_RUNS = 4

DEFAULT_DOC = Path(__file__).resolve().parent.parent / "EVALUATION_STRATEGY.md"


# ---------------------------------------------------------------------------
# Arithmetic the document states inline, written once.
# ---------------------------------------------------------------------------


def hands_per_arm(sigma: float, delta: float, rho: float = 0.0) -> int:
    """Section 2.5: n = 2*sigma^2*(1-rho)*(z_a + z_b)^2 / Delta^2, per arm."""
    return round(2.0 * sigma * sigma * (1.0 - rho) * Z_SUM_SQ_FULL / (delta * delta))


def multiplier(r: float) -> float:
    """Section 2.5 Step 4: an r reduction in SE multiplies hands by (1-r)^2."""
    return (1.0 - r) ** 2


def chips_to_mbb(chips: float) -> float:
    """A per-hand SD in chips becomes mbb/hand at the game's big blind."""
    return chips / CHIPS_PER_BIG_BLIND * 1000.0


def se_to_sd(standard_error: float, n: int) -> float:
    """SD = standard error * sqrt(n), section 2.5's six-player derivation."""
    return standard_error * math.sqrt(n)


def hands_per_hour(workers: int = PARALLEL_WORKERS) -> float:
    """Section 3.6: 3,600 * workers / (seconds per decision * decisions/hand)."""
    return SECONDS_PER_HOUR * workers / (SECONDS_PER_DECISION * DECISIONS_PER_HAND)


def cards_needed(seats: int) -> int:
    """Section on engine requirements: 2 hole cards each plus 5 board cards."""
    return seats * HOLE_CARDS + BOARD_CARDS


def weights_for(seats: list[int]) -> dict[int, float]:
    """Section 3.5 point 2's banding, for whichever seat counts ran."""
    others = [n for n in seats if n not in PRIMARY_SEATS and n not in SECONDARY_SEATS]
    weights = {}
    for n in seats:
        if n in PRIMARY_SEATS:
            weights[n] = WEIGHT_PRIMARY
        elif n in SECONDARY_SEATS:
            weights[n] = WEIGHT_SECONDARY / len(SECONDARY_SEATS)
        else:
            weights[n] = WEIGHT_REST / len(others)
    return weights


def sum_of_squared_weights(seats: list[int]) -> float:
    return sum(w * w for w in weights_for(seats).values())


def detectable_delta(n_eff: float, sigma: float = BUDGET_SIGMA) -> float:
    """Invert the sample-size formula: Delta = sqrt(2*sigma^2*Z/n)."""
    return math.sqrt(2.0 * sigma * sigma * Z_SUM_SQ_FULL / n_eff)


# ---------------------------------------------------------------------------
# Formatting: half-up to the precision the document prints at.
# ---------------------------------------------------------------------------


def fmt(x: float, places: int = 0, thousands: bool = False) -> str:
    quant = Decimal(1).scaleb(-places) if places else Decimal(1)
    d = Decimal(repr(float(x))).quantize(quant, rounding=ROUND_HALF_UP)
    if thousands:
        return f"{d:,}"
    return str(d)


def grouped(n: float) -> str:
    return fmt(n, 0, thousands=True)


def pct(x: float, places: int = 0) -> str:
    return fmt(x * 100.0, places) + "%"


# ---------------------------------------------------------------------------
# Reading the document.
# ---------------------------------------------------------------------------


class Document:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.text = path.read_text(encoding="utf-8")
        self.lines = self.text.splitlines()
        self.flat = re.sub(r"\s+", " ", self.text)
        # The release gate is quoted as a markdown blockquote in four of its five
        # places, so "> " has to come off before the copies can be compared.
        unquoted = "\n".join(re.sub(r"^\s*>\s?", "", line) for line in self.lines)
        self.flat_unquoted = re.sub(r"\s+", " ", unquoted)

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

    def absent(self, what: str, phrase: str) -> None:
        """Assert a superseded figure has not come back."""
        self.checked += 1
        flat_phrase = re.sub(r"\s+", " ", phrase)
        if flat_phrase in self.doc.flat:
            self.failures.append(f"{what}: document still contains {flat_phrase!r}")

    def occurrences(self, what: str, phrase: str, expected: int) -> None:
        """Assert a phrase appears exactly `expected` times, blockquotes included."""
        self.checked += 1
        flat_phrase = re.sub(r"\s+", " ", phrase)
        found = self.doc.flat_unquoted.count(flat_phrase)
        if found != expected:
            self.failures.append(
                f"{what}: document states it {found} times, constants give {expected}"
            )

    def every_occurrence(self, what: str, pattern: str, *expected: str) -> None:
        """Assert *every* place the document states this figure states it the same."""
        self.checked += 1
        found = [
            tuple(g for g in m.groups() if g is not None)
            for m in re.finditer(pattern, self.doc.flat)
        ]
        if not found:
            self.failures.append(f"{what}: document states it nowhere (pattern {pattern!r})")
            return
        if len(expected) == 1:
            wrong = [g for g in found if any(v != expected[0] for v in g)]
        else:
            wrong = [g for g in found if g != tuple(expected)]
        if wrong:
            self.failures.append(
                f"{what}: {len(wrong)} of {len(found)} occurrences disagree — "
                f"document says {wrong!r}, constants give {tuple(expected)!r}"
            )

    # -- Section 2.5 Step 1: the four standard deviations -----------------
    def check_sigma_table(self) -> None:
        rows = self.doc.table_after("**Step 1: how noisy is one hand?**")[1:]
        self.equal("Step 1 row count", len(SIGMA_ROWS), len(rows))
        derived = {
            "raw_hunl": chips_to_mbb(AIVAT_SD_RAW_CHIPS),
            "aivat_hunl": chips_to_mbb(AIVAT_SD_AIVAT_CHIPS),
            "five_h_one_ai": se_to_sd(PLURIBUS_SE_5H1AI, PLURIBUS_HANDS),
            "one_h_five_ai": se_to_sd(PLURIBUS_SE_1H5AI, PLURIBUS_HANDS),
        }
        for (label, key), row in zip(SIGMA_ROWS, rows):
            self.equal(f"Step 1 label {key}", label, row[0])
            value = derived[key]
            places = 1 if abs(value - round(value)) > 1e-9 else 0
            self.equal(
                f"Step 1 sigma {key}",
                f"≈ {fmt(value, places, thousands=True)} mbb",
                row[1],
            )

    def check_sigma_prose(self) -> None:
        raw = chips_to_mbb(AIVAT_SD_RAW_CHIPS)
        aivat = chips_to_mbb(AIVAT_SD_AIVAT_CHIPS)
        six = se_to_sd(PLURIBUS_SE_5H1AI, PLURIBUS_HANDS)
        self.prose(
            "the AIVAT reduction stated exactly",
            f"**{fmt(1 - AIVAT_SD_AIVAT_CHIPS / AIVAT_SD_RAW_CHIPS, 3)[2:4]}."
            f"{fmt(1 - AIVAT_SD_AIVAT_CHIPS / AIVAT_SD_RAW_CHIPS, 3)[4]}%**",
        )
        self.prose(
            "the like-for-like ratio in Step 1",
            f"**{grouped(six)} against {PLURIBUS_EDGE_MBB}, "
            f"a ratio of about {fmt(six / PLURIBUS_EDGE_MBB)}**",
        )
        self.prose(
            "the heads-up ratio in Step 1",
            f"The raw heads-up row is {grouped(raw)}, which is "
            f"{fmt(raw / PLURIBUS_EDGE_MBB)} times that same {PLURIBUS_EDGE_MBB}",
        )
        self.prose("the raw HUNL sigma derivation", f"= {grouped(raw)} mbb")
        self.prose("the AIVAT HUNL sigma derivation", f"= {fmt(aivat, 1, thousands=True)} mbb")

    # -- Section 2.5 Step 2: the sample-size table ------------------------
    def check_sample_size_table(self) -> None:
        all_rows = self.doc.table_after("| σ (mbb/hand) | Δ=10")
        header, rows = all_rows[0], all_rows[1:]
        for delta, cell in zip(SAMPLE_SIZE_DELTAS, header[1:]):
            self.equal(f"sample-size header Δ={delta}", f"Δ={delta}", cell)
        self.equal("sample-size row count", len(SAMPLE_SIZE_ROWS), len(rows))
        for (sigma, label), row in zip(SAMPLE_SIZE_ROWS, rows):
            self.equal(f"sample-size row label σ={sigma}", label, row[0])
            for delta, cell in zip(SAMPLE_SIZE_DELTAS, row[1:]):
                self.equal(
                    f"sample-size σ={sigma} Δ={delta}",
                    grouped(hands_per_arm(sigma, delta)),
                    cell,
                )

    def check_z_constant(self) -> None:
        self.prose(
            "the displayed (z+z)^2",
            f"`(z₀.₉₇₅ + z₀.₈₀)² = {Z_SUM_SQ_DISPLAY}`",
        )
        self.prose("the full-precision (z+z)^2", f"({Z_SUM_SQ_FULL}…)")
        self.prose(
            "the top-left cell restated in words",
            f"takes about {round(hands_per_arm(SAMPLE_SIZE_ROWS[0][0], 10) / 1e6)} "
            "million hands per arm",
        )

    # -- Section 2.5 Step 3: the paired-rho table -------------------------
    def check_rho_table(self) -> None:
        rows = self.doc.table_after("| ρ | Hands per arm |")[1:]
        self.equal("rho row count", len(RHO_VALUES), len(rows))
        for rho, row in zip(RHO_VALUES, rows):
            self.equal(f"rho label {rho}", fmt(rho, 1), row[0])
            self.equal(
                f"rho={rho} hands per arm",
                grouped(hands_per_arm(RHO_SIGMA, RHO_DELTA, rho)),
                row[1],
            )
        self.prose(
            "the sigma and Delta the rho table is computed at",
            f"At σ = {grouped(RHO_SIGMA)} and Δ = {RHO_DELTA} mbb/hand",
        )

    # -- Section 2.5 Step 4: the variance-reduction multipliers -----------
    def check_reduction_table(self) -> None:
        rows = self.doc.table_after("| r | Hands needed × |")[1:]
        self.equal("multiplier row count", len(REDUCTION_ROWS), len(rows))
        for (r, label), row in zip(REDUCTION_ROWS, rows):
            self.equal(f"multiplier label r={r}", label, row[0])
            self.equal(f"multiplier r={r}", fmt(multiplier(r), 3), row[1])

    # -- Section 4.2: duplicate's factorial -------------------------------
    def check_factorial_table(self) -> None:
        rows = self.doc.table_after("| n | Replays per deal (n!) |")[1:]
        self.equal("factorial row count", len(SEAT_COUNTS), len(rows))
        for n, row in zip(SEAT_COUNTS, rows):
            self.equal(f"factorial seat label {n}", str(n), row[0])
            self.equal(f"factorial n={n}", grouped(math.factorial(n)), row[1])
        self.prose(
            "the nine-seat factorial restated",
            f"At nine seats, full duplicate costs {grouped(math.factorial(9))} "
            "replays per deal",
        )

    # -- Section 4.3: the LBR bet-size grid -------------------------------
    def check_lbr_grid(self) -> None:
        points = [LBR_GRID_BASE * LBR_GRID_RATIO**k for k in range(LBR_GRID_K_MAX + 1)]
        at_or_below_pot = sum(1 for p in points if p <= 1.0)
        self.prose(
            "the LBR grid formula",
            f"pot fractions `{LBR_GRID_BASE} × {LBR_GRID_RATIO}^k` for "
            f"`k = 0…{LBR_GRID_K_MAX}`",
        )
        self.prose(
            "the LBR grid's top of range",
            f"which runs from {LBR_GRID_BASE}× pot to about {fmt(points[-1], 1)}× pot",
        )
        self.prose(
            "the LBR grid's points at or below one pot",
            f"with {at_or_below_pot} of the {len(points)} points at or below one pot",
        )
        self.prose(
            "the LBR grid's 55-plus-all-in count",
            f"**That is {len(points)} pot fractions plus the all-in bet, which is "
            f"why the paper calls it {len(points) + 1} bets",
        )

    # -- Section 3.5: the release gate and the weights --------------------
    def check_release_gate(self) -> None:
        self.occurrences("the release gate stated identically", GATE_TEXT, GATE_OCCURRENCES)
        self.prose(
            "the rotation cycle",
            " → ".join(str(n) for n in ROTATION_CYCLE) + " cycle",
        )
        self.every_occurrence(
            "the window length in the gate's own words, everywhere it is stated",
            r"within the last (\w+) nightly acceptance runs",
            spell(GATE_WINDOW_RUNS),
        )
        self.every_occurrence(
            "the window length wherever the report block restates it",
            r"passed within the last (\d+) nightly runs",
            str(GATE_WINDOW_RUNS),
        )

    def check_weights(self) -> None:
        rows = self.doc.table_after("| Band | Seat counts | Headline weight |")[1:]
        self.equal("weight band count", 3, len(rows))
        self.equal("primary band weight", fmt(WEIGHT_PRIMARY, 2), rows[0][2])
        self.equal(
            "secondary band weight",
            f"{fmt(WEIGHT_SECONDARY, 2)} ({fmt(WEIGHT_SECONDARY / 2, 2)} each)",
            rows[1][2],
        )
        self.equal("remaining band weight", f"{fmt(WEIGHT_REST, 2)}, split equally", rows[2][2])
        nightly_others = len(NIGHTLY_FIXED_SEATS) - len(PRIMARY_SEATS) - len(SECONDARY_SEATS) + 1
        self.prose(
            "the nightly split of the last band",
            f"each takes {fmt(WEIGHT_REST, 2)} ÷ {nightly_others} = "
            f"**{fmt(WEIGHT_REST / nightly_others, 2)}**",
        )
        full_others = len([n for n in SEAT_COUNTS if n not in PRIMARY_SEATS + SECONDARY_SEATS])
        self.prose(
            "the full-grid split of the last band",
            f"each takes {fmt(WEIGHT_REST, 2)} ÷ {full_others} = "
            f"**{fmt(WEIGHT_REST / full_others, 2)}**",
        )
        self.prose(
            "the share of the headline the operator's own bands carry",
            f"carry {fmt(WEIGHT_PRIMARY + WEIGHT_SECONDARY, 2)} of the headline",
        )

    # -- Section 3.6: the grid, the hands and the hours -------------------
    def check_full_grid(self) -> None:
        cells = len(SEAT_COUNTS) * FULL_GRID_COMPOSITIONS * FULL_GRID_STACK_DEPTHS
        per_cell = 2 * hands_per_arm(BUDGET_SIGMA, FULL_GRID_DELTA)
        hands = cells * per_cell
        hours = hands / hands_per_hour()
        rows = self.doc.table_after("| Axis | Count | From |")[1:]
        self.equal("full-grid axis row count", 4, len(rows))
        self.equal("full-grid seat count axis", str(len(SEAT_COUNTS)), rows[0][1])
        self.equal("full-grid composition axis", str(FULL_GRID_COMPOSITIONS), rows[1][1])
        self.equal("full-grid stack-depth axis", str(FULL_GRID_STACK_DEPTHS), rows[2][1])
        self.equal("full-grid cell count", grouped(cells), rows[3][1])
        self.prose(
            "the full grid's per-cell cost",
            f"a cell costs {grouped(hands_per_arm(BUDGET_SIGMA, FULL_GRID_DELTA))} "
            f"hands per arm, {grouped(per_cell)} hands in total",
        )
        self.prose(
            "the full grid's total hands",
            f"**{grouped(cells)} cells × {grouped(per_cell)} hands = {grouped(hands)} hands.**",
        )
        self.prose(
            "the full grid against the cap",
            f"{grouped(hands)} hands ÷ {grouped(hands_per_hour())} per hour = "
            f"**{grouped(hours)} hours ≈ {fmt(hours / HOURS_PER_DAY, 1)} days on one laptop.**",
        )
        self.prose(
            "the full grid as a multiple of the cap",
            f"**{fmt(float(grouped(hours).replace(',', '')) / ACCEPTANCE_CAP_HOURS, 1)} times** "
            "the 10-hour cap",
        )

    def check_placeholders(self) -> None:
        rows = self.doc.table_after("| Quantity | Value used here | Status |")[1:]
        self.equal("placeholder row count", 6, len(rows))
        self.equal("seconds per bot decision", fmt(SECONDS_PER_DECISION, 2), rows[1][1])
        self.equal("bot decisions per hand", str(DECISIONS_PER_HAND), rows[2][1])
        self.equal(
            "bot-seconds per hand",
            fmt(SECONDS_PER_DECISION * DECISIONS_PER_HAND, 1),
            rows[3][1],
        )
        self.equal("parallel workers", str(PARALLEL_WORKERS), rows[4][1])
        self.equal("hands per hour", grouped(hands_per_hour()), rows[5][1])
        self.prose(
            "the hands-per-hour arithmetic",
            f"{grouped(SECONDS_PER_HOUR)} × {PARALLEL_WORKERS} ÷ "
            f"{fmt(SECONDS_PER_DECISION * DECISIONS_PER_HAND, 1)}",
        )
        self.every_occurrence(
            "the machine's core count and split, spelled out",
            r"(\d+) cores \((\d+) performance, (\d+) efficiency\)",
            str(MACHINE_CORES),
            str(MACHINE_PERFORMANCE_CORES),
            str(MACHINE_EFFICIENCY_CORES),
        )
        self.every_occurrence(
            "the machine's core split wherever it is abbreviated",
            r"\((\d+)P \+ (\d+)E\)|\((\d+) performance \+ (\d+) efficiency\)",
            str(MACHINE_PERFORMANCE_CORES),
            str(MACHINE_EFFICIENCY_CORES),
        )
        self.prose(
            "the cores left free for everything else",
            f"{PARALLEL_WORKERS} of the {MACHINE_CORES} cores",
        )

    def check_budget_table(self) -> None:
        nightly_seats = len(NIGHTLY_FIXED_SEATS) + 1
        routine_seats = len(NIGHTLY_FIXED_SEATS)
        nightly_cells = nightly_seats * REDUCED_COMPOSITIONS * REDUCED_STACK_DEPTHS
        routine_cells = routine_seats * REDUCED_COMPOSITIONS * REDUCED_STACK_DEPTHS
        full_cells = len(SEAT_COUNTS) * FULL_GRID_COMPOSITIONS * FULL_GRID_STACK_DEPTHS
        nightly_per_cell = 2 * hands_per_arm(BUDGET_SIGMA, NIGHTLY_DELTA)
        routine_per_cell = 2 * hands_per_arm(BUDGET_SIGMA, ROUTINE_DELTA)
        full_per_cell = 2 * hands_per_arm(BUDGET_SIGMA, FULL_GRID_DELTA)

        self.prose("the nightly cell arithmetic", f"**{nightly_seats} × {REDUCED_COMPOSITIONS} × "
                   f"{REDUCED_STACK_DEPTHS} = {nightly_cells} cells**")

        rows = self.doc.table_after("| Run | Seat counts | Cells | Hands/cell |")[1:]
        self.equal("budget row count", 3, len(rows))
        expected = [
            ("Routine check", routine_cells, routine_per_cell, ROUTINE_DELTA),
            ("Nightly acceptance", nightly_cells, nightly_per_cell, NIGHTLY_DELTA),
            ("Full grid (aspirational)", full_cells, full_per_cell, FULL_GRID_DELTA),
        ]
        for (name, cells, per_cell, delta), row in zip(expected, rows):
            hands = cells * per_cell
            hours = hands / hands_per_hour()
            self.equal(f"{name} cells", grouped(cells), row[2])
            self.equal(f"{name} hands per cell", grouped(per_cell), row[3])
            self.equal(f"{name} total hands", grouped(hands), row[4])
            places = 0 if hours >= 100 else (1 if hours >= 1 else 2)
            self.equal(f"{name} wall clock", f"{fmt(hours, places, thousands=True)} h", row[5])
            self.equal(f"{name} detects per cell", f"{delta} mbb/hand", row[6])

        nightly_hands = nightly_cells * nightly_per_cell
        routine_hands = routine_cells * routine_per_cell
        self.prose(
            "the nightly hands restated below the table",
            f"Nightly: {nightly_cells} × {grouped(nightly_per_cell)} = "
            f"{grouped(nightly_hands)} hands; {grouped(nightly_hands)} ÷ "
            f"{grouped(hands_per_hour())} per hour = "
            f"**{fmt(nightly_hands / hands_per_hour(), 3)} h**",
        )
        self.prose(
            "the routine hands restated below the table",
            f"Routine: {routine_cells} × {grouped(routine_per_cell)} = "
            f"{grouped(routine_hands)}; ÷ {grouped(hands_per_hour())} = "
            f"**{fmt(routine_hands / hands_per_hour(), 3)} h**",
        )
        rotated_routine = nightly_cells * routine_per_cell
        self.prose(
            "the routine check with a rotating seat, which is why it has none",
            f"it would be {nightly_cells} × {grouped(routine_per_cell)} = "
            f"{grouped(rotated_routine)} hands = "
            f"**{fmt(rotated_routine / hands_per_hour(), 2)} h**",
        )
        self.prose(
            "the nightly run's headroom under the cap",
            f"**{fmt(ACCEPTANCE_CAP_HOURS - round(nightly_hands / hands_per_hour(), 1), 1)} "
            f"hours of headroom** ({ACCEPTANCE_CAP_HOURS} − "
            f"{fmt(nightly_hands / hands_per_hour(), 1)})",
        )

    def check_worker_breakeven(self) -> None:
        nightly_seats = len(NIGHTLY_FIXED_SEATS) + 1
        nightly_cells = nightly_seats * REDUCED_COMPOSITIONS * REDUCED_STACK_DEPTHS
        nightly_hands = nightly_cells * 2 * hands_per_arm(BUDGET_SIGMA, NIGHTLY_DELTA)
        per_worker_hour = SECONDS_PER_HOUR / (SECONDS_PER_DECISION * DECISIONS_PER_HAND)
        breakeven = nightly_hands / (per_worker_hour * ACCEPTANCE_CAP_HOURS)
        self.prose(
            "the worker breakeven",
            f"{grouped(nightly_hands)} ÷ ({grouped(per_worker_hour)} × "
            f"{ACCEPTANCE_CAP_HOURS}) = **{fmt(breakeven, 2)} — call it "
            f"{math.ceil(breakeven)}**",
        )
        for k in WORKER_COUNTS_CHECKED:
            hours = nightly_hands / (per_worker_hour * k)
            if k == WORKER_COUNTS_CHECKED[0]:
                self.prose(
                    f"the nightly run at {k} workers",
                    f"At {k} workers the run takes {grouped(nightly_hands)} ÷ "
                    f"({grouped(per_worker_hour)} × {k}) = **{fmt(hours, 1)} hours**",
                )
            else:
                self.prose(
                    f"the nightly run at {k} workers",
                    f"at {k} it takes {fmt(hours, 1)} hours",
                )
        self.prose(
            "the breakeven restated in the homogeneity paragraph",
            f"the breakeven is {fmt(breakeven, 2)}",
        )
        self.prose(
            "the breakeven restated as performance-core equivalents",
            f"below {fmt(breakeven, 2)} performance-core equivalents",
        )

    def check_rotation_nights(self) -> None:
        nightly_seats = len(NIGHTLY_FIXED_SEATS) + 1
        nightly_cells = nightly_seats * REDUCED_COMPOSITIONS * REDUCED_STACK_DEPTHS
        nightly_hands = nightly_cells * 2 * hands_per_arm(BUDGET_SIGMA, NIGHTLY_DELTA)
        per_seat_per_arm = nightly_hands / 2 / nightly_seats
        rows = self.doc.table_after("| Rotation night | Seat counts and weights |")[1:]
        self.equal("rotation night count", len(ROTATION_CYCLE), len(rows))
        for i, (rotating, row) in enumerate(zip(ROTATION_CYCLE, rows), start=1):
            seats = NIGHTLY_FIXED_SEATS + [rotating]
            sw2 = sum_of_squared_weights(seats)
            n_eff = per_seat_per_arm / sw2
            self.equal(f"rotation night {i} label", str(i), row[0])
            self.equal(f"rotation night {i} Σw²", fmt(sw2, 3), row[2])
            self.equal(f"rotation night {i} n_eff", grouped(n_eff), row[3])
            self.equal(
                f"rotation night {i} Δ",
                f"{fmt(detectable_delta(n_eff), 1)} mbb/hand",
                row[4],
            )
            self.true(
                f"rotation night {i} names the rotating seat",
                f"{rotating} = .10" in row[1],
                f"row says {row[1]!r}",
            )

        five_seat = NIGHTLY_FIXED_SEATS + [ROTATION_CYCLE[0]]
        sw2_five = sum_of_squared_weights(five_seat)
        n_eff_five = per_seat_per_arm / sw2_five
        self.prose(
            "the per-seat sample the nightly run gives",
            f"each gets {grouped(per_seat_per_arm)} per arm",
        )
        self.prose(
            "the Sigma w squared arithmetic",
            f"= **{fmt(sw2_five, 3)}**; n_eff = {grouped(per_seat_per_arm)} ÷ "
            f"{fmt(sw2_five, 3)} = **{grouped(n_eff_five)}** per arm",
        )
        self.prose(
            "the nightly headline Delta",
            f"÷ {grouped(n_eff_five)}) = **{fmt(detectable_delta(n_eff_five), 1)} mbb/hand**",
        )
        # The four-seat comparison in the same paragraph.
        sw2_four = sum_of_squared_weights(NIGHTLY_FIXED_SEATS)
        n_eff_four = per_seat_per_arm / sw2_four
        self.prose(
            "the four-seat comparison's Sigma w squared",
            f"so Σwᵢ² = {fmt(WEIGHT_PRIMARY, 2)}² + {fmt(WEIGHT_SECONDARY / 2, 2)}² + "
            f"{fmt(WEIGHT_SECONDARY / 2, 2)}² + {fmt(WEIGHT_REST, 2)}² = {fmt(sw2_four, 3)}",
        )
        self.prose(
            "the four-seat comparison's n_eff and Delta",
            f"n_eff = {grouped(per_seat_per_arm)} ÷ {fmt(sw2_four, 3)} = "
            f"{grouped(n_eff_four)} per arm and Δ = {fmt(detectable_delta(n_eff_four), 2)}",
        )
        self.prose(
            "the five-seat Delta before rounding",
            f"against Δ = {fmt(detectable_delta(n_eff_five), 2)} on the five-seat night",
        )
        self.prose(
            "the power the fifth seat buys",
            f"buys **{fmt(detectable_delta(n_eff_four) - detectable_delta(n_eff_five), 1)} "
            "mbb/hand**",
        )
        proportional = nightly_hands / 2
        self.prose(
            "the proportional-allocation alternative",
            f"raise the effective size to the full {grouped(proportional)} and the "
            f"headline to Δ = {fmt(detectable_delta(proportional), 1)}",
        )

    # -- The engine requirements section ----------------------------------
    def check_deck_arithmetic(self) -> None:
        self.prose(
            "the short deck's size",
            f"a cut-down deck of **{SHORT_DECK_CARDS} cards**",
        )
        playable = [n for n in SEAT_COUNTS if cards_needed(n) <= SHORT_DECK_CARDS]
        self.prose(
            "the seat ceiling the short deck forces",
            f"physically caps it at **{spell(max(playable))} seats**",
        )
        self.prose(
            "the card arithmetic behind that ceiling",
            f"{spell(max(playable))} players need {max(playable)} × {HOLE_CARDS} + "
            f"{BOARD_CARDS} = {cards_needed(max(playable))} cards and eight need "
            f"{cards_needed(8)}",
        )
        self.true(
            "the short deck really does seat no more than the document says",
            cards_needed(max(playable)) <= SHORT_DECK_CARDS
            and cards_needed(max(playable) + 1) > SHORT_DECK_CARDS,
            f"{cards_needed(max(playable))} and {cards_needed(max(playable) + 1)} "
            f"cards against a {SHORT_DECK_CARDS}-card deck",
        )
        self.true(
            "a full deck would seat all of 2 to 9",
            all(cards_needed(n) <= FULL_DECK_CARDS for n in SEAT_COUNTS),
            f"{cards_needed(max(SEAT_COUNTS))} cards against {FULL_DECK_CARDS}",
        )

    def check_todays_engine_grid(self) -> None:
        playable = [n for n in SEAT_COUNTS if cards_needed(n) <= SHORT_DECK_CARDS]
        cells = len(playable) * REDUCED_COMPOSITIONS * REDUCED_STACK_DEPTHS
        per_cell = 2 * hands_per_arm(BUDGET_SIGMA, NIGHTLY_DELTA)
        hands = cells * per_cell
        hours = hands / hands_per_hour()
        nightly_seats = len(NIGHTLY_FIXED_SEATS) + 1
        nightly_cells = nightly_seats * REDUCED_COMPOSITIONS * REDUCED_STACK_DEPTHS
        nightly_hands = nightly_cells * per_cell

        rows = self.doc.table_after("| Nightly acceptance, as designed | The same run on today's engine |")
        body = rows[1:]
        self.equal("today's-engine grid row count", 8, len(body))
        self.equal(
            "today's-engine seat counts",
            f"{', '.join(str(n) for n in playable)} — {spell(len(playable))}",
            body[0][2].split(";")[0],
        )
        self.equal("today's-engine cell count", str(cells), body[2][2])
        self.equal("today's-engine hands per cell", grouped(per_cell), body[3][2])
        self.equal("today's-engine total hands", grouped(hands), body[4][2])
        self.equal("today's-engine wall clock", f"{fmt(hours, 3)} h", body[5][2])
        self.equal("today's-engine family size", str(cells), body[6][2])
        self.equal("nightly cell count in the same table", str(nightly_cells), body[2][1])
        self.equal("nightly total hands in the same table", grouped(nightly_hands), body[4][1])
        self.equal(
            "nightly wall clock in the same table",
            f"{fmt(nightly_hands / hands_per_hour(), 3)} h",
            body[5][1],
        )
        self.prose(
            "the today's-engine arithmetic",
            f"{cells} × {grouped(per_cell)} = {grouped(hands)} hands; {grouped(hands)} ÷ "
            f"{grouped(hands_per_hour())} = **{fmt(hours, 3)} h**",
        )
        self.prose(
            "the today's-engine family size in words",
            f"**family size for the Benjamini-Hochberg correction is {cells}, not "
            f"{nightly_cells}**",
        )
        self.true(
            "today's-engine grid fits the acceptance cap",
            hours < ACCEPTANCE_CAP_HOURS,
            f"{hours} h against a {ACCEPTANCE_CAP_HOURS} h cap",
        )

    def check_engine_throughput(self) -> None:
        full_cells = len(SEAT_COUNTS) * FULL_GRID_COMPOSITIONS * FULL_GRID_STACK_DEPTHS
        full_hands = full_cells * 2 * hands_per_arm(BUDGET_SIGMA, FULL_GRID_DELTA)
        real_seconds = full_hands / ENGINE_HANDS_PER_SEC_REAL_SIZING
        menu_seconds = full_hands / ENGINE_HANDS_PER_SEC_MENU
        hours = full_hands / hands_per_hour()
        ratio = hours / (real_seconds / SECONDS_PER_HOUR)
        self.prose(
            "the engine survey's commit",
            f"`{ENGINE_SURVEY_BRANCH}` at commit `{ENGINE_SURVEY_COMMIT}`",
        )
        self.prose(
            "the menu-mode throughput",
            f"**{grouped(ENGINE_HANDS_PER_SEC_MENU)} complete hands per",
        )
        self.prose(
            "the real-sizing throughput",
            f"it deals **{grouped(ENGINE_HANDS_PER_SEC_REAL_SIZING)}** "
            "(median of six repeats)",
        )
        self.prose(
            "the full grid at real-sizing throughput",
            f"{grouped(full_hands)} ÷ {grouped(ENGINE_HANDS_PER_SEC_REAL_SIZING)} = "
            f"**{grouped(real_seconds)} seconds, about {fmt(real_seconds / 60)} minutes**",
        )
        self.prose(
            "the full grid at menu-mode throughput",
            f"it would be {grouped(menu_seconds)} seconds",
        )
        self.prose(
            "the ratio between engine time and budgeted time",
            f"**{grouped(round(ratio / 50) * 50)}** — {fmt(real_seconds / 60)} minutes "
            f"against {grouped(hours)} hours",
        )
        self.absent(
            "the superseded throughput figure",
            f"{ENGINE_SUPERSEDED_HANDS_PER_SEC} complete six-player hands",
        )

    # -- The provenance table ---------------------------------------------
    def check_provenance_rows(self) -> None:
        rows = self.doc.table_after("## Provenance of every number in this document")[1:]
        self.true(
            "the provenance table has rows",
            len(rows) > 20,
            f"found {len(rows)} rows",
        )
        required = [
            ENGINE_SURVEY_COMMIT,
            ENGINE_SUPERSEDED_COMMIT,
            "four-run",
            f"{grouped(hands_per_hour())} hands/hour",
        ]
        flat = " ".join(" ".join(r) for r in rows)
        for phrase in required:
            self.true(
                f"provenance table covers {phrase!r}",
                phrase in flat,
                "no row mentions it",
            )

    # -- Everything ------------------------------------------------------
    def run(self) -> None:
        checks = [
            ("Step 1 standard deviations", self.check_sigma_table),
            ("Step 1 prose", self.check_sigma_prose),
            ("sample-size table", self.check_sample_size_table),
            ("the z constant", self.check_z_constant),
            ("paired-rho table", self.check_rho_table),
            ("variance-reduction multipliers", self.check_reduction_table),
            ("duplicate factorials", self.check_factorial_table),
            ("LBR bet-size grid", self.check_lbr_grid),
            ("release gate", self.check_release_gate),
            ("table-size weights", self.check_weights),
            ("full grid", self.check_full_grid),
            ("wall-clock placeholders", self.check_placeholders),
            ("budget table", self.check_budget_table),
            ("worker breakeven", self.check_worker_breakeven),
            ("rotation nights", self.check_rotation_nights),
            ("deck arithmetic", self.check_deck_arithmetic),
            ("today's-engine grid", self.check_todays_engine_grid),
            ("engine throughput", self.check_engine_throughput),
            ("provenance table", self.check_provenance_rows),
        ]
        for name, check in checks:
            try:
                check()
            except LookupError as exc:
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
    # The document is full of Greek letters and arrows, so a failure line can
    # carry characters a Windows console's default code page cannot print.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover - older streams
            pass
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_DOC
    if not path.exists():
        print(f"evaluation document not found: {path}", file=sys.stderr)
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
