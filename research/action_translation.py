#!/usr/bin/env python3
"""Action-translation mappings, and a check against the published numbers.

Implements the mappings compared in Ganzfried & Sandholm, "Action Translation in
Extensive-Form Games with Large Action Spaces: Axioms, Paradoxes, and the
Pseudo-Harmonic Mapping", IJCAI 2013, pp. 120-128
(https://www.cs.cmu.edu/~sandholm/reverse%20mapping.ijcai13.pdf), and reproduces
the numbers this repository's ACTION_TRANSLATION.md quotes from it.

Every f(A, B, x) returns the probability of mapping an observed size x in [A, B]
onto the lower abstraction size A; 1 - f is the probability of mapping onto B.
All sizes are in pot fractions, the pot taken as 1, which is the paper's own
convention (section 5) and is what makes the mapping table-size independent.

    python3 research/action_translation.py          # print everything
    python3 research/action_translation.py --check  # exit 1 if any check fails

Nothing outside the standard library is needed. This is research code: it does
not choose a poker action and is not on the bot's decision path.
"""
from __future__ import annotations

import argparse
import math

# --- the mappings (GS13 sections 5 and 6) ----------------------------------


def rand_arith(a: float, b: float, x: float) -> float:
    """Randomized arithmetic, GS13 section 5.2: (B - x) / (B - A)."""
    return (b - x) / (b - a)


def rand_geo_1(a: float, b: float, x: float) -> float:
    """Randomized geometric 1, GS13 section 5.4: A(B-x) / (A(B-x) + x(x-A))."""
    num = a * (b - x)
    den = a * (b - x) + x * (x - a)
    return num / den if den else 0.0


def rand_geo_2(a: float, b: float, x: float) -> float:
    """Randomized geometric 2, GS13 section 5.5: A(B+x)(B-x) / ((B-A)(x^2+AB))."""
    return a * (b + x) * (b - x) / ((b - a) * (x * x + a * b))


def rand_pshar(a: float, b: float, x: float) -> float:
    """Randomized pseudo-harmonic, GS13 section 6: (B-x)(1+A) / ((B-A)(1+x))."""
    return (b - x) * (1.0 + a) / ((b - a) * (1.0 + x))


def median_arith(a: float, b: float) -> float:
    return (a + b) / 2.0


def median_geo(a: float, b: float) -> float:
    return math.sqrt(a * b)


def median_pshar(a: float, b: float) -> float:
    """GS13 section 6: x* = (A + B + 2AB) / (A + B + 2)."""
    return (a + b + 2.0 * a * b) / (a + b + 2.0)


def deterministic(median: float, x: float) -> str:
    """Deterministic version of a mapping: below its median go to A, else B."""
    return "A" if x < median else "B"


MAPPINGS = {
    "Rand-Arith": rand_arith,
    "Rand-Geo-1": rand_geo_1,
    "Rand-Geo-2": rand_geo_2,
    "Rand-psHar": rand_pshar,
}

# --- published numbers this script reproduces ------------------------------

# GS13 Table 1: f(x=0.25) with B = 1 fixed and A increasing from 0 to 0.1.
GS13_TABLE_1_A = [0.0, 0.001, 0.01, 0.05, 0.1]
GS13_TABLE_1 = {
    "Rand-Arith": [0.75, 0.751, 0.758, 0.789, 0.833],
    "Rand-Geo-1": [0.0, 0.012, 0.111, 0.429, 0.667],
    "Rand-Geo-2": [0.0, 0.015, 0.131, 0.439, 0.641],
    "Rand-psHar": [0.6, 0.601, 0.612, 0.663, 0.733],
}
# GS13 section 7, Figure 1 (A = 0.01, B = 1): geometric medians 0.1, arithmetic
# "around 0.5", pseudo-harmonic "around 0.34".
GS13_FIG1_MEDIANS = {"geo": 0.1, "arith": 0.505, "pshar": 0.34}
# GS13 footnote 3: for A = 0, B = 1 the pseudo-harmonic median is 1/3.
GS13_ZERO_ONE_MEDIAN = 1.0 / 3.0
# GS13 section 5.1 and 5.2, the clairvoyance-game exploitation arithmetic with
# A = 1 (pot), B = 100 (all-in), the opponent's expected payoff from betting.
GS13_PAYOFF_POT_BET = 1.5      # bet A = 1 with a winning hand
GS13_PAYOFF_DET_ARITH = 26.0   # bet 50, deterministic arithmetic maps it to A
GS13_PAYOFF_RAND_ARITH = 13.875  # bet 50.5 against randomized arithmetic


def clairvoyance_payoffs() -> tuple[float, float, float]:
    """GS13 sections 5.1-5.2. Pot 1, P2 calls a pot bet with prob 1/2 and an
    all-in of 100 with prob 1/101; P1 holds the winning hand."""
    pot_bet = 1.0 * 0.5 + 2.0 * 0.5
    det_arith = 1.0 * 0.5 + 51.0 * 0.5           # bet 50, treated as a pot bet
    p_to_a = rand_arith(1.0, 100.0, 50.5)        # = 1/2
    rand_a = p_to_a * (1.0 * 0.5 + 51.5 * 0.5) + (1.0 - p_to_a) * (
        1.0 * (100.0 / 101.0) + 51.5 * (1.0 / 101.0)
    )
    return pot_bet, det_arith, rand_a


# --- the worked example in ACTION_TRANSLATION.md ---------------------------

EXAMPLE_X = 0.37   # opponent bets 37% of a three-way pot
EXAMPLE_A = 0.0    # nearest menu size below: no bet (check)
EXAMPLE_B = 0.5    # nearest menu size above: the half-pot bet


def worked_example(a: float = EXAMPLE_A, b: float = EXAMPLE_B, x: float = EXAMPLE_X):
    rows = []
    for name, f in MAPPINGS.items():
        rows.append((name, f(a, b, x)))
    dets = [
        ("Det-Arith", median_arith(a, b)),
        ("Det-Geo", median_geo(a, b)),
        ("Det-psHar", median_pshar(a, b)),
    ]
    return rows, dets


def report() -> None:
    print("GS13 Table 1: f(x = 0.25), B = 1, A increasing")
    print("A          " + "".join(f"{a:>8}" for a in GS13_TABLE_1_A))
    for name, f in MAPPINGS.items():
        vals = [f(a, 1.0, 0.25) for a in GS13_TABLE_1_A]
        print(f"{name:<11}" + "".join(f"{v:8.3f}" for v in vals))
    print()
    print("GS13 Figure 1 medians (A = 0.01, B = 1)")
    print(f"  geometric      {median_geo(0.01, 1.0):.4f}  (paper: 0.1)")
    print(f"  arithmetic     {median_arith(0.01, 1.0):.4f}  (paper: around 0.5)")
    print(f"  pseudo-harmonic{median_pshar(0.01, 1.0):8.4f}  (paper: around 0.34)")
    print(f"  pseudo-harmonic median for A=0, B=1: {median_pshar(0.0, 1.0):.4f} "
          "(paper footnote 3: 1/3)")
    print()
    pot_bet, det_arith, rand_a = clairvoyance_payoffs()
    print("GS13 sections 5.1-5.2, clairvoyance game, P1's expected payoff")
    print(f"  honest pot-sized bet of 1          {pot_bet:.3f}  (paper: 1.5)")
    print(f"  bet 50 vs deterministic arithmetic {det_arith:.3f}  (paper: 26)")
    print(f"  bet 50.5 vs randomized arithmetic  {rand_a:.3f}  (paper: 13.875)")
    print()
    rows, dets = worked_example()
    print(f"Worked example: opponent bets {EXAMPLE_X:.2f} pot, menu half-pot and pot,")
    print(f"  so A = {EXAMPLE_A} (check) and B = {EXAMPLE_B} (half-pot bet)")
    for name, p in rows:
        print(f"  {name:<11} check with prob {p:.4f}, half-pot with prob {1 - p:.4f}")
    for name, med in dets:
        print(f"  {name:<11} median {med:.4f} -> maps to "
              f"{'check' if deterministic(med, EXAMPLE_X) == 'A' else 'half-pot'}")


def check() -> int:
    failures = []

    def near(label, got, want, tol):
        if abs(got - want) > tol:
            failures.append(f"{label}: got {got:.6f}, want {want:.6f}")

    for name, wanted in GS13_TABLE_1.items():
        for a, w in zip(GS13_TABLE_1_A, wanted):
            near(f"Table 1 {name} A={a}", MAPPINGS[name](a, 1.0, 0.25), w, 5e-4)
    near("Fig 1 geometric median", median_geo(0.01, 1.0), GS13_FIG1_MEDIANS["geo"], 1e-9)
    near("Fig 1 arithmetic median", median_arith(0.01, 1.0), GS13_FIG1_MEDIANS["arith"], 1e-9)
    near("Fig 1 pseudo-harmonic median", median_pshar(0.01, 1.0),
         GS13_FIG1_MEDIANS["pshar"], 5e-3)
    near("A=0,B=1 pseudo-harmonic median", median_pshar(0.0, 1.0),
         GS13_ZERO_ONE_MEDIAN, 1e-12)
    pot_bet, det_arith, rand_a = clairvoyance_payoffs()
    near("clairvoyance pot bet", pot_bet, GS13_PAYOFF_POT_BET, 1e-12)
    near("clairvoyance Det-Arith", det_arith, GS13_PAYOFF_DET_ARITH, 1e-12)
    near("clairvoyance Rand-Arith", rand_a, GS13_PAYOFF_RAND_ARITH, 1e-12)
    # Boundary constraints, GS13 desideratum 1, for A > 0.
    for name, f in MAPPINGS.items():
        near(f"{name} f(A)=1", f(0.5, 1.0, 0.5), 1.0, 1e-12)
        near(f"{name} f(B)=0", f(0.5, 1.0, 1.0), 0.0, 1e-12)
    # Scale invariance, GS13 desideratum 3. The arithmetic and geometric
    # mappings are invariant under scaling the raw amounts; the pseudo-harmonic
    # one is not, and is invariant only once every size is divided by the pot,
    # which is the convention GS13 section 5 states ("the pot initially has size
    # 1 and all values have been scaled accordingly"). Feeding it chip amounts
    # instead of pot fractions is therefore a live implementation trap, and this
    # check pins the size of the error rather than pretending it is absent.
    for name in ("Rand-Arith", "Rand-Geo-1", "Rand-Geo-2"):
        f = MAPPINGS[name]
        near(f"{name} scale invariance on raw amounts",
             f(0.5, 2.0, 0.9), f(5.0, 20.0, 9.0), 1e-12)
    near("Rand-psHar in pot fractions", rand_pshar(0.5, 2.0, 0.9), 0.578947, 1e-5)
    near("Rand-psHar on raw chips (10x pot), the trap",
         rand_pshar(5.0, 20.0, 9.0), 0.44, 1e-9)
    for line in failures:
        print("FAIL " + line)
    print(f"{'FAILED' if failures else 'OK'}: {len(failures)} mismatches "
          "against the published numbers")
    return 1 if failures else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check", action="store_true",
                   help="compare against the published numbers and exit nonzero on drift")
    args = p.parse_args()
    if args.check:
        raise SystemExit(check())
    report()
    raise SystemExit(check())
