"""The scoreboard: the accounting, the pairing, the guard, and the rule.

These tests cover `pokerbot/league.py` and `pokerbot/scoreboard.py`. They carry
no invariant marker -- they are not one of `EVALUATION_STRATEGY.md` section
4.5's seven statements about a dealt hand -- so they do not appear in the
seat-count table.

The load-bearing one is `test_always_fold_matches_the_closed_form_blinds_figure`:
it is the only number in the whole harness with a right answer worked out on
paper, and it is what says the chips are being counted correctly.
"""

from __future__ import annotations

import io

import pytest

from pokerbot import Action, Table, TableConfig, deal_check
from pokerbot import league, personas, scoreboard
from pokerbot.league import (
    Cell,
    HeldBackPersonaError,
    bootstrap_interval,
    block_length,
    decide,
    load_config,
    resolve_bot,
    run_cell,
    table_size_weights,
    tuning_opponents,
)

CONFIG = load_config()


# --------------------------------------------------------------------------
# The accounting: the one closed-form answer in the harness
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "seats,expected",
    [(2, -75.0), (6, -25.0), (8, -18.75), (9, -150.0 / 9.0)],
)
def test_always_fold_matches_the_closed_form_blinds_figure(seats, expected):
    """`always_fold` can only ever lose the blinds it posts. Worked out:

    The seat under measurement folds whenever folding is legal and never puts a
    chip in voluntarily. Its opponents are `always_raise`, so there is always a
    bet in front of it, folding is always legal, and nobody ever folds around to
    it and hands it a pot. Therefore:

    * When it is the small blind it posts 50 chips = 0.5 big blinds and folds.
    * When it is the big blind it posts 100 chips = 1.0 big blinds and folds.
    * In every other seat it posts nothing and folds, losing 0.

    The button moves one seat per hand, so in a cycle of `n` hands it is the
    small blind exactly once and the big blind exactly once:

        loss per cycle   = 0.5 + 1.0 = 1.5 big blinds over n hands
        loss per hand    = 1.5 / n
        big blinds / 100 = -100 * 1.5 / n = -150 / n

    n=2 -> -75.00,  n=6 -> -25.00,  n=8 -> -18.75,  n=9 -> -16.666...

    There is no sampling error in this figure: every hand loses exactly the
    blind posted, so any deviation at all is a fault in the accounting, not
    noise. The hand count is a whole number of button cycles.
    """
    bot = resolve_bot("always_fold", 1, CONFIG)
    cell = run_cell(
        bot, "always_fold", "always_raise", seats, hands=2 * seats, run_seed=1, config=CONFIG
    )
    assert cell.hands == 2 * seats
    assert cell.bb_per_100 == pytest.approx(expected, abs=1e-9)


def test_the_closed_form_holds_at_a_different_stack_depth_and_seed():
    """The figure is the blinds and nothing else, so nothing else may move it."""
    bot = resolve_bot("always_fold", 9, CONFIG)
    cell = run_cell(
        bot, "always_fold", "always_raise", 6, hands=30, run_seed=9, config=CONFIG
    )
    assert cell.bb_per_100 == pytest.approx(-25.0, abs=1e-9)


# --------------------------------------------------------------------------
# Paired deals
# --------------------------------------------------------------------------


def _recording_bot(inner):
    """`inner`, wrapped so it writes down the cards it was dealt each hand."""
    seen: list[tuple[str, ...]] = []

    def play(hand, seat):
        cards = tuple(hand.record.hole_cards[seat])
        if not seen or seen[-1] != cards:
            seen.append(cards)
        return inner(hand, seat)

    return play, seen


def test_both_arms_of_a_comparison_are_dealt_exactly_the_same_cards():
    """Section 3.5's "pair everything": the deals cannot depend on the bot."""
    folding, folded_cards = _recording_bot(resolve_bot("always_fold", 3, CONFIG))
    calling, called_cards = _recording_bot(resolve_bot("always_call", 3, CONFIG))
    for bot, name in ((folding, "always_fold"), (calling, "always_call")):
        run_cell(bot, name, "always_call", 6, hands=10, run_seed=3, config=CONFIG)
    assert folded_cards == called_cards
    assert len(folded_cards) == 10


# --------------------------------------------------------------------------
# The held-back half
# --------------------------------------------------------------------------


def test_the_split_is_half_and_half_and_covers_the_nine():
    assert set(CONFIG.development) | set(CONFIG.held_back) == set(
        personas.BEHAVIOURAL_PERSONAS
    )
    assert not set(CONFIG.development) & set(CONFIG.held_back)
    assert abs(len(CONFIG.development) - len(CONFIG.held_back)) <= 1


@pytest.mark.parametrize("held_back", load_config().held_back)
def test_tuning_refuses_a_held_back_persona(held_back):
    """Section 3.2's second design rule, enforced rather than hoped for."""
    with pytest.raises(HeldBackPersonaError) as refusal:
        tuning_opponents(CONFIG, [held_back])
    assert held_back in str(refusal.value)


def test_tuning_allows_the_development_half_and_the_calibration_agents():
    allowed = tuning_opponents(CONFIG)
    assert set(allowed) == set(CONFIG.development) | set(CONFIG.calibration)
    assert tuning_opponents(CONFIG, ["nit"]) == ["nit"]


def test_the_command_refuses_a_tuning_run_against_a_held_back_persona():
    out = io.StringIO()
    code = scoreboard.main(
        ["--bot", "always_call", "--mode", "tuning", "--personas", CONFIG.held_back[0],
         "--hands", "4", "--seats", "6"],
        out=out,
    )
    assert code == 2
    assert "refused" in out.getvalue()
    assert CONFIG.held_back[0] in out.getvalue()


def test_an_acceptance_run_may_use_every_persona():
    assert set(league.acceptance_opponents(CONFIG)) == set(personas.ALL_PERSONAS)


# --------------------------------------------------------------------------
# The weights
# --------------------------------------------------------------------------


def test_the_table_size_weights_are_the_ones_section_3_5_fixes():
    """6 at 0.50, 8 and 9 together at 0.30, everything else 0.20 split equally."""
    weights = table_size_weights([2, 6, 8, 9], CONFIG)
    assert weights == pytest.approx({2: 0.20, 6: 0.50, 8: 0.15, 9: 0.15})
    assert sum(weights.values()) == pytest.approx(1.0)


def test_the_config_weights_are_the_same_ones_the_document_checker_holds():
    """One set of weights, not two that can drift apart.

    `tools/check_evaluation_numbers.py` holds EVALUATION_STRATEGY.md's own copy
    of the band weights and recomputes every figure the document derives from
    them. This config is what the harness actually runs on. If the two ever
    disagree, the report is printing numbers the document does not describe.
    """
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "tools" / "check_evaluation_numbers.py"
    spec = importlib.util.spec_from_file_location("check_evaluation_numbers", path)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)

    assert float(CONFIG.weights["primary"]) == checker.WEIGHT_PRIMARY
    assert float(CONFIG.weights["secondary"]) == checker.WEIGHT_SECONDARY
    assert float(CONFIG.weights["other"]) == checker.WEIGHT_REST
    for seats in ([2, 6, 8, 9], [2, 3, 6, 8, 9]):
        assert table_size_weights(seats, CONFIG) == pytest.approx(
            checker.weights_for(list(seats))
        )
    # The one case the document does not cover: a run with no seat count in one
    # of the three bands. The document's weights would then sum to 0.8 and
    # silently shrink the headline by a fifth, so the harness rescales them to
    # sum to 1 and prints a line saying it did. The proportions are untouched.
    rescaled = table_size_weights([6, 8, 9], CONFIG)
    assert sum(rescaled.values()) == pytest.approx(1.0)
    documented = checker.weights_for([6, 8, 9])
    assert rescaled[6] / rescaled[8] == pytest.approx(documented[6] / documented[8])
    assert league.missing_bands([6, 8, 9], CONFIG) == ["everything else"]
    assert league.missing_bands([2, 6, 8, 9], CONFIG) == []


def test_the_last_band_splits_over_whatever_else_ran():
    """The three band weights never move; only the split inside the last one."""
    weights = table_size_weights([2, 3, 6, 8, 9], CONFIG)
    assert weights[6] == pytest.approx(0.50)
    assert weights[8] == weights[9] == pytest.approx(0.15)
    assert weights[2] == weights[3] == pytest.approx(0.10)
    assert sum(weights.values()) == pytest.approx(1.0)


# --------------------------------------------------------------------------
# The intervals
# --------------------------------------------------------------------------


def test_the_interval_covers_a_known_mean_and_is_not_a_point():
    values = [1.0, -1.0, 2.0, -2.0, 0.5, -0.5] * 10
    interval = bootstrap_interval(values, CONFIG, seed=1)
    assert interval.estimate == pytest.approx(0.0, abs=1e-9)
    assert interval.low < 0 < interval.high
    # The t-interval is the cross-check and must agree in this easy case.
    assert interval.t_low < 0 < interval.t_high


def test_a_block_bootstrap_on_a_short_run_still_has_a_width():
    """A block as long as the run would give every resample the same hands."""
    values = [float(i % 7) for i in range(40)]
    assert block_length(values, 20) == 10
    interval = bootstrap_interval(values, CONFIG, seed=2, block=20)
    assert interval.high > interval.low


# --------------------------------------------------------------------------
# The decision rule
# --------------------------------------------------------------------------


def _cell(persona: str, seats: int, values: list[float], memory: bool = False) -> Cell:
    return Cell("B", persona, seats, values, memory)


def test_the_rule_rejects_a_bot_deliberately_made_worse():
    """BUILD_PLAN.md's third "done when" for T3.

    Arm B is `always_fold`, which can only lose its blinds; arm A calls every
    bet. Against opponents who never bet, arm A sees every hand to showdown for
    the price of the blinds and wins its share of them, so it is plainly the
    better of the two. The rule must say so.
    """
    worse = resolve_bot("always_fold", 5, CONFIG)
    better = resolve_bot("always_call", 5, CONFIG)
    cells_b, cells_a = [], []
    for seats in (2, 6):
        cells_b.append(
            run_cell(worse, "always_fold", "always_call", seats, 60, 5, CONFIG)
        )
        cells_a.append(
            run_cell(better, "always_call", "always_call", seats, 60, 5, CONFIG)
        )
    verdict = decide(cells_b, cells_a, CONFIG, seed=5)
    assert not verdict.accepted
    assert verdict.label == "REJECT"
    assert verdict.primary.estimate < 0
    assert any("entirely above zero" in reason for reason in verdict.reasons)


def test_the_rule_rejects_a_bot_with_a_bad_action_injected():
    """The same, by breaking a bot rather than by swapping it for a worse one."""
    good = resolve_bot("always_call", 6, CONFIG)
    broken = personas.handicapped(good, fold_probability=0.6, seed=6)
    cells_b = [run_cell(broken, "broken_call", "always_call", 6, 80, 6, CONFIG)]
    cells_a = [run_cell(good, "always_call", "always_call", 6, 80, 6, CONFIG)]
    verdict = decide(cells_b, cells_a, CONFIG, seed=6)
    assert not verdict.accepted
    assert verdict.primary.estimate < 0


def test_a_change_that_changes_nothing_is_not_an_improvement():
    """The interval has to lie wholly above zero, and zero is not above zero."""
    bot = resolve_bot("always_call", 7, CONFIG)
    cells_b = [run_cell(bot, "same", "calling_station", 6, 20, 7, CONFIG)]
    cells_a = [run_cell(bot, "same", "calling_station", 6, 20, 7, CONFIG)]
    verdict = decide(cells_b, cells_a, CONFIG, seed=7)
    assert not verdict.accepted
    assert verdict.primary.estimate == pytest.approx(0.0)


def test_one_losing_persona_blocks_a_change_that_wins_overall():
    """Section 3.5's non-inferiority rule: the signature of over-fitting blocks.

    The numbers here are made up on purpose -- this is a test of the rule, not
    of any bot. Arm B wins hugely against one persona and loses steadily to
    another, which is exactly the shape the rule exists to catch.
    """
    winning = [3.0, 4.0, 3.5, 4.5] * 10
    losing = [-1.0, -1.2, -0.9, -1.1] * 10
    zeros = [0.0] * 40
    cells_b = [
        _cell("calling_station", 6, winning),
        _cell("never_bluffs", 6, losing),
    ]
    cells_a = [_cell("calling_station", 6, zeros), _cell("never_bluffs", 6, zeros)]
    verdict = decide(cells_b, cells_a, CONFIG, seed=8)
    assert verdict.primary.estimate > 0, "the headline is positive, as designed"
    assert not verdict.accepted, "but one persona's loss must block it"
    assert verdict.blockers and "never_bluffs" in verdict.blockers[0]
    assert any("blocks the change" in reason for reason in verdict.reasons)


def test_a_clean_improvement_is_accepted():
    """The other side of the rule, so a reject is not the only thing it can say."""
    better = [2.0, 2.5, 1.5, 3.0] * 15
    cells_b = [_cell("calling_station", 6, better), _cell("never_bluffs", 6, better)]
    cells_a = [
        _cell("calling_station", 6, [0.0] * 60),
        _cell("never_bluffs", 6, [0.0] * 60),
    ]
    verdict = decide(cells_b, cells_a, CONFIG, seed=9)
    assert verdict.accepted
    assert verdict.primary.low > 0


# --------------------------------------------------------------------------
# The command itself
# --------------------------------------------------------------------------


def test_a_small_run_prints_the_whole_report():
    """One command, a few hands, and every part of the page section 3.5 asks for."""
    out = io.StringIO()
    code = scoreboard.main(
        [
            "--bot", "always_call",
            "--compare", "always_fold",
            "--hands", "8",
            "--seed", "2",
            "--seats", "2,6,8,9",
            "--personas", "calling_station,tilter",
        ],
        out=out,
    )
    report = out.getvalue()
    assert code in (0, 1), "the command must finish and say accept or reject"
    # What was run and under which pre-registered numbers.
    assert "scoreboard  bot B=always_call  bot A=always_fold" in report
    assert "league_config.toml" in report
    assert "weights: n2=0.200  n6=0.500  n8=0.150  n9=0.150" in report
    assert "held back (accept/reject only)" in report
    assert "load average" in report
    # The parameters drawn for this session.
    assert "personas drawn this session (seed 2)" in report
    assert "tilt_trigger_bb=" in report
    # A cell for every persona at every one of the four seat counts.
    for persona in ("calling_station", "tilter"):
        for seats in (2, 6, 8, 9):
            assert any(
                line.strip().startswith(persona) and line.split()[1] == str(seats)
                for line in report.splitlines()
            ), f"no line for {persona} at {seats} seats"
    # The verdict, with its reasons.
    assert "primary endpoint" in report
    assert "by persona (non-inferiority" in report
    assert "verdict:" in report
    assert "because" in report


def test_the_command_can_say_what_bots_it_accepts():
    out = io.StringIO()
    assert scoreboard.main(["--bot", "always_call", "--list-bots"], out=out) == 0
    for name in personas.ALL_PERSONAS:
        assert name in out.getvalue()


def test_a_registered_bot_joins_the_league_under_its_own_name():
    """T2's search bot plugs in here: any callable with the adapter's signature."""

    def factory(seed):
        def bot(hand, seat):
            return Action.CALL if Action.CALL in hand.legal_actions() else Action.FOLD

        return bot

    league.register_bot("test_caller", factory)
    try:
        assert "test_caller" in league.available_bots()
        cell = run_cell(
            league.resolve_bot("test_caller", 1, CONFIG),
            "test_caller",
            "always_call",
            6,
            hands=6,
            run_seed=1,
            config=CONFIG,
        )
        assert cell.hands == 6
    finally:
        league._BOT_FACTORIES.pop("test_caller", None)


# --------------------------------------------------------------------------
# The p-value, the header, and the NOT RUN cell
# --------------------------------------------------------------------------


def test_a_difference_of_exactly_zero_is_not_significant():
    """A run in which nothing changed must not be starred as a discovery.

    Every resampled mean of an all-zero vector is zero, so the honest two-sided
    answer is "as unsurprising as a result can be": p = 1. Counting only the
    resamples on one side of zero gives p = 1/1001 instead, and the
    Benjamini-Hochberg step then stars a difference of nothing at all.
    """
    nothing = bootstrap_interval([0.0] * 60, CONFIG, seed=1)
    assert nothing.p_value == pytest.approx(1.0)
    # And the other side of it: a clear, one-signed difference is still small.
    clearly_better = bootstrap_interval([2.0, 2.5, 1.5, 3.0] * 15, CONFIG, seed=1)
    assert clearly_better.p_value < 0.01


def test_the_report_never_stars_an_interval_that_contains_zero():
    """The star says "this survived the correction". An interval straddling zero
    has not shown a difference in either direction, whatever its p-value."""
    cells_b = [_cell("calling_station", 6, [0.0] * 60)]
    cells_a = [_cell("calling_station", 6, [0.0] * 60)]
    verdict = decide(cells_b, cells_a, CONFIG, seed=3)
    out = io.StringIO()
    scoreboard.print_verdict(out, verdict, [6])
    starred = [
        line for line in out.getvalue().splitlines()
        if line.strip().startswith("n=6") and line.rstrip().endswith("*")
    ]
    assert not starred, f"a zero difference was starred: {starred}"


def test_the_verdict_prints_the_weights_the_headline_actually_used():
    """The header's weights come from the seat counts that were ASKED for; the
    headline is weighted over the seat counts that produced a cell. When a seat
    count produces nothing, those are two different sets of weights, and the one
    the reader needs is the one the number was actually computed with."""
    out = io.StringIO()
    code = scoreboard.main(
        ["--bot", "always_call", "--compare", "always_fold", "--hands", "6",
         "--seed", "3", "--seats", "6,12", "--personas", "always_raise"],
        out=out,
    )
    report = out.getvalue()
    assert code in (0, 1)
    # Asked for 6 and 12; only 6 dealt, so the headline is 100% the six-seat cell.
    assert "weights: n6=0.714  n12=0.286" in report, "the header reports what was asked for"
    assert "n6=1.000" in report.split("primary endpoint")[1], (
        "the verdict must print the weights the headline was computed with"
    )
    assert "12" in report.split("primary endpoint")[1], (
        "the verdict must name the seat count that produced no cell"
    )


def test_a_seat_count_the_engine_will_not_deal_prints_its_whole_reason():
    """Truncating the engine's refusal to 25 characters cuts it mid-sentence, and
    a reason a reader cannot finish is not a reason. The cell says NOT RUN; the
    reason goes underneath the table in full, as T1's seat-count table does it."""
    _, reason = deal_check(12)
    assert reason and len(reason) > 25, "this test needs a reason long enough to be cut"
    out = io.StringIO()
    code = scoreboard.main(
        ["--bot", "always_call", "--compare", "always_fold", "--hands", "6",
         "--seed", "4", "--seats", "6,12", "--personas", "always_raise"],
        out=out,
    )
    report = out.getvalue()
    assert code in (0, 1)
    assert "NOT RUN" in report
    assert reason in report, f"the engine's reason was cut short; wanted {reason!r}"


def test_the_preflop_rollout_count_in_the_config_is_the_one_that_is_used():
    """A pre-registered number nothing reads is not pre-registered. The config's
    `preflop_rollouts` has to reach the ranking the personas play on, and the
    report has to print it."""
    configured = int(CONFIG.run["preflop_rollouts"])
    nit = league.build_persona(
        "nit", 1,
        rollouts=int(CONFIG.run["equity_rollouts"]),
        preflop_rollouts=configured,
    )
    assert nit.preflop_rollouts == configured
    table = Table(TableConfig(seats=6))
    hand = table.new_hand(seed=21, button=0)
    view = personas.seat_view(hand, hand.current_seat())
    assert nit.top_fraction(view) == personas.preflop_top_fraction(
        view.hole, configured
    )
    out = io.StringIO()
    scoreboard.main(["--bot", "always_call", "--list-bots"], out=out)
    header = io.StringIO()
    scoreboard.main(
        ["--bot", "always_call", "--compare", "always_fold", "--hands", "4",
         "--seed", "5", "--seats", "6", "--personas", "always_raise"],
        out=header,
    )
    assert f"preflop ranking: {configured} engine showdowns" in header.getvalue()


# --------------------------------------------------------------------------
# The bot's own state
# --------------------------------------------------------------------------


class _MemoryBot:
    """A bot that carries something between hands, to prove the harness tells it
    when a cell starts and what each hand did. `tilter` is the real one."""

    has_memory = True

    def __init__(self):
        self.sessions = 0
        self.results: list[float] = []

    def new_session(self) -> None:
        self.sessions += 1
        self.results = []

    def hand_finished(self, net_bb: float) -> None:
        self.results.append(net_bb)

    def __call__(self, hand, seat):
        return Action.CALL if Action.CALL in hand.legal_actions() else Action.FOLD


def test_a_bot_with_a_memory_is_told_when_a_cell_starts_and_how_each_hand_went():
    """`--bot tilter` never tilts unless the harness reports its own results back
    to it, and a stateful bot that is never given `new_session` runs the whole
    grid on one cell's bootstrap."""
    bot = _MemoryBot()
    cell = run_cell(bot, "memory_bot", "always_call", 6, hands=12, run_seed=13, config=CONFIG)
    assert bot.sessions == 1, "the bot was never told the cell had started"
    assert len(bot.results) == 12, "the bot was never told how its hands went"
    assert cell.values == pytest.approx(bot.results)
    assert cell.has_memory, "a cell whose bot carries state needs a block bootstrap"


def test_one_cell_played_alone_is_the_same_cell_played_inside_a_longer_run():
    """A cell has to be reproducible on its own. The bot's own coin flips carry
    across cells unless the harness restarts them, so re-running one cell to
    chase a number down gives a different number from the one in the report."""
    alone = run_cell(
        resolve_bot("call_raise_50_50", 17, CONFIG), "call_raise_50_50",
        "always_call", 6, hands=20, run_seed=17, config=CONFIG,
    )
    shared = resolve_bot("call_raise_50_50", 17, CONFIG)
    run_cell(shared, "call_raise_50_50", "always_raise", 6, hands=20, run_seed=17, config=CONFIG)
    inside = run_cell(
        shared, "call_raise_50_50", "always_call", 6, hands=20, run_seed=17, config=CONFIG,
    )
    assert inside.values == pytest.approx(alone.values), (
        "the cell played differently because the bot's coin flips carried over"
    )
