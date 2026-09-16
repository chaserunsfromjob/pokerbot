"""Isolated upstream equity regression probe; no GUI or service calls.

Loads source from a pinned git object, applies tie-accounting and engine-ranking
patches in memory, and compares known fixtures with treys (test oracle only).
The patch preserves upstream GPL-3.0 provenance; it is not a complete bot port.
"""
import argparse
import difflib
import hashlib
import json
import logging
from pathlib import Path
import random
import subprocess
import sys
import time
import types

from treys import Card, Evaluator

PIN = "cae3a108b6cbf22ed8ef90bc0e70f790346289a4"
SOURCE_PATH = "poker/decisionmaker/montecarlo_python.py"


def patch_source(source):
    start = source.index("            bestHand, winnerCardType = self.eval_best_hand(PlayerFinalCardsWithTableCards)")
    end = source.index("            self.equity = np.round(wins / runs, 3)", start)
    replacement = '''            # Equity is expected pot share; ties divide the win among winners.
            scores = [self.calc_score(hand) for hand in PlayerFinalCardsWithTableCards]
            best_score = max(scores)
            winners = [i for i, score in enumerate(scores) if score == best_score]
            if 0 in winners:
                share = 1.0 / len(winners)
                wins += share
                winnerCardTypeList[best_score[-1]] += share

'''
    return (source[:start] + replacement + source[end:]).replace(
        "        winnerCardTypeList = []", "        winnerCardTypeList = Counter()", 1).replace(
        "        self.winnerCardTypeList = Counter(winnerCardTypeList)",
        "        self.winnerCardTypeList = winnerCardTypeList", 1)


def patch_ranking(source):
    start = source.index("    def calc_score(self, hand):")
    end = source.index("    def create_card_deck(self):", start)
    replacement = '''    def calc_score(self, hand):
        # Use a maintained engine for ranking; preserve existing category keys.
        # Additional dependency: pokerkit==0.7.5.
        from pokerkit import StandardHighHand
        labels = {
            "HIGH_CARD": "HighCard", "ONE_PAIR": "Pair", "TWO_PAIR": "TwoPair",
            "THREE_OF_A_KIND": "ThreeOfAKind", "STRAIGHT": "Straight",
            "FLUSH": "Flush", "FULL_HOUSE": "FullHouse",
            "FOUR_OF_A_KIND": "FoufOfAKind", "STRAIGHT_FLUSH": "StraightFlush",
        }
        cards = "".join(card[0] + card[1].lower() for card in hand)
        evaluated = StandardHighHand.from_game(cards)
        return evaluated.entry.index, (), labels[evaluated.entry.label.name]

'''
    return source[:start] + replacement + source[end:]


def load(source, checkout, name):
    helper = types.ModuleType("poker.tools.helper")
    def get_dir(key):
        if key != "codebase":
            raise ValueError(f"Unsupported path lookup: {key}")
        return str(checkout / "poker")
    helper.get_dir = get_dir
    sys.modules["poker.tools.helper"] = helper
    namespace = {"__name__": name}
    exec(compile(source, str(checkout / SOURCE_PATH), "exec"), namespace)
    return namespace["MonteCarlo"]


def oracle(holdings, board):
    evaluator = Evaluator()
    def convert(cards):
        return [Card.new(c[0] + c[1].lower()) for c in cards]
    ranks = [evaluator.evaluate(convert(board), convert(h)) for h in holdings]
    winners = [i for i, value in enumerate(ranks) if value == min(ranks)]
    return 1 / len(winners) if 0 in winners else 0.0


def run(checkout, output, patch_output):
    checkout = Path(checkout).resolve()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=checkout, text=True).strip()
    if head != PIN:
        raise ValueError("Use the pinned candidate checkout")
    source = subprocess.check_output(["git", "show", f"{PIN}:{SOURCE_PATH}"], cwd=checkout, text=True)
    patched = patch_source(source)
    engine_ranked = patch_ranking(patched)
    patch = "".join(difflib.unified_diff(source.splitlines(keepends=True), patched.splitlines(keepends=True),
                                       fromfile="a/" + SOURCE_PATH, tofile="b/" + SOURCE_PATH))
    Path(patch_output).parent.mkdir(parents=True, exist_ok=True)
    Path(patch_output).write_text(patch)
    ranking_patch = "".join(difflib.unified_diff(patched.splitlines(keepends=True), engine_ranked.splitlines(keepends=True),
                         fromfile="a/" + SOURCE_PATH, tofile="b/" + SOURCE_PATH))
    ranking_path = Path(patch_output).with_name("dickreuter-pokerkit-ranking.patch")
    ranking_path.write_text(ranking_patch)
    classes = {"upstream": load(source, checkout, "original_candidate"),
               "tie_patch": load(patched, checkout, "patched_candidate"),
               "engine_ranking": load(engine_ranked, checkout, "engine_ranked_candidate")}
    fixtures = []
    available = [r + s for r in "23456789TJQKA" for s in "CDH"]
    for n in (2, 6, 8, 9):
        fixtures.append((f"royal_flush_{n}_way", [available[2*i:2*i+2] for i in range(n)],
                         ["TS", "JS", "QS", "KS", "AS"]))
    fixtures.extend([
        ("partial_tie", [["AC", "QD"], ["AH", "QC"], ["JD", "TS"]], ["KS", "KD", "7H", "4S", "2C"]),
        ("unique_win", [["AC", "AD"], ["KC", "KD"], ["QC", "QD"]], ["2C", "3D", "7H", "8S", "9C"]),
        ("unique_loss", [["QC", "QD"], ["KC", "KD"], ["AC", "AD"]], ["2C", "3D", "7H", "8S", "9C"]),
        ("quads_rank_before_kicker", [["2S", "AC"], ["3H", "3S"]], ["2C", "2D", "2H", "3C", "3D"]),
    ])
    logging.disable(logging.CRITICAL)
    results = []
    for name, holdings, board in fixtures:
        expected = oracle(holdings, board)
        row = {"fixture": name, "holdings": holdings, "board": board, "expected": expected}
        for label, cls in classes.items():
            mc = cls()
            equity, win_types = mc.run_montecarlo(logging.getLogger("probe"), holdings, board,
                len(holdings), None, 20, time.time() + 5, "", opponent_range=1)
            row[label] = {"equity": equity, "matches": abs(equity - expected) < 1e-9,
                          "win_type_share_sum": sum(value for _, value in win_types)}
        results.append(row)
    rng = random.Random(2026091602)
    ranking_checks = []
    for n in range(2, 10):
        mismatches = {label: 0 for label in classes}
        for _ in range(50):
            drawn = rng.sample([r + s for r in "23456789TJQKA" for s in "CDHS"], 2*n + 5)
            holdings = [drawn[2*i:2*i+2] for i in range(n)]
            board = drawn[-5:]
            expected = oracle(holdings, board)
            for label, cls in classes.items():
                mc = cls()
                scores = [mc.calc_score(h + board) for h in holdings]
                winners = [i for i, score in enumerate(scores) if score == max(scores)]
                observed = 1 / len(winners) if 0 in winners else 0
                mismatches[label] += abs(observed - expected) > 1e-9
        ranking_checks.append({"players": n, "fixtures": 50, "mismatches": mismatches})
    failures = [row["fixture"] for row in results if not row["engine_ranking"]["matches"]]
    if any(row["mismatches"]["engine_ranking"] for row in ranking_checks):
        failures.append("randomized ranking comparisons")
    report = {"candidate": "https://github.com/dickreuter/Poker", "commit": PIN,
              "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
              "patched_sha256": hashlib.sha256(patched.encode()).hexdigest(),
              "engine_ranked_sha256": hashlib.sha256(engine_ranked.encode()).hexdigest(),
              "status": "blocked: additional evaluator failures" if failures else "patched equity fixtures pass; full policy not integrated",
              "remaining_failures": failures, "results": results, "randomized_ranking_checks": ranking_checks,
              "native_evaluator_failure": "Quads rank loses priority to the kicker; tie-only patch is insufficient",
              "limitations": "Known-card equity fixtures only; no GUI, remote strategy config, ranges, policy strength or class-app integration"}
    Path(output).write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--patch-out", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.source, args.out, args.patch_out), indent=2))
