"""Verify fixed statistical decisions and deterministic stream generation."""
import json
import pytest

from research.response_recency import SCENARIOS, TRIALS, primary_comparisons, stream
from research.recency_screen import prediction_metrics


def complete_rows():
    return [{"scenario": scenario, "trial": trial,
             "mean_excess_brier": {"prior": .5, "raw": .3, "discounted": .1},
             "window_256_383_excess_brier": {"prior": .5, "raw": .4, "discounted": .2}}
            for scenario in SCENARIOS for trial in range(TRIALS)]


def test_fixed_comparisons_require_complete_sample_and_switch_window():
    rows = complete_rows()
    with pytest.raises(ValueError, match="Complete"):
        primary_comparisons(rows[:-1])
    results = primary_comparisons(rows)
    assert len(results) == 8
    assert all(r["passed"] for r in results)
    for row in rows:
        if row["scenario"] == "changing":
            row["window_256_383_excess_brier"]["discounted"] = .6
    failed = [r for r in primary_comparisons(rows) if not r["passed"]]
    assert len(failed) == 2
    assert all(r["scenario"] == "changing" for r in failed)


def test_stream_is_reproducible_and_scores_before_observation():
    first, second = stream("caller", 99), stream("caller", 99)
    assert first["action_indices"] == second["action_indices"] == "1" * 1024
    assert first["checkpoints"] == second["checkpoints"]
    assert first["mean_excess_brier"] == second["mean_excess_brier"]
    start = first["checkpoints"][0]
    assert len(set(start["predictions"].values())) == 1
    assert start["observations"] == 0
    assert first["mean_excess_brier"]["discounted"] > 0


def test_match_scoring_uses_discounting_and_never_learns_from_the_scored_hand(tmp_path):
    path = tmp_path / "history.jsonl"
    row = {"name": "opponent", "street": 0, "facing_bet": True, "raise_available": True, "action": "fold"}
    first = {"hand_id": 0, "response_observations": [row] * 800}
    path.write_text(json.dumps(first) + "\n")
    prior = prediction_metrics(path, {"opponent": "caller"}, "off", None)
    discounted = prediction_metrics(path, {"opponent": "caller"}, "learned", 64)
    assert discounted["mean_excess_brier"] == prior["mean_excess_brier"]
    second = {"hand_id": 1, "response_observations": [{**row, "action": "passive"}]}
    path.write_text(json.dumps(first) + "\n" + json.dumps(second) + "\n")
    raw = prediction_metrics(path, {"opponent": "caller"}, "learned", None)
    discounted = prediction_metrics(path, {"opponent": "caller"}, "learned", 64)
    assert discounted["mean_excess_brier"] < raw["mean_excess_brier"]
    assert discounted["public_opponent_decisions"] == 801


@pytest.mark.parametrize("scenario", ["changing", "mistaken_history"])
def test_recovery_behavior_regression_on_separate_fixed_test_stream(scenario):
    # Test stream 99 is outside the pilot's 0--19 trials. This is a regression
    # fixture, not another statistical experiment or an additional poker hand.
    result = stream(scenario, 99)
    key = "window_256_383_excess_brier" if scenario == "changing" else "mean_excess_brier"
    errors = result[key]
    assert errors["discounted"] < errors["prior"]
    assert errors["discounted"] < errors["raw"]
