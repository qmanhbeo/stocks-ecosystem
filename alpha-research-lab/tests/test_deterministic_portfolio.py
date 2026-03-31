from __future__ import annotations

import numpy as np
import pandas as pd

from src.deterministic_portfolio import (
    MarketInputs,
    compute_strategy_scores,
    compute_selected_target_weights,
    simulate_strategy,
)


def _market_inputs(
    score_matrix: np.ndarray,
    *,
    can_buy: np.ndarray | None = None,
    can_sell: np.ndarray | None = None,
    adv20: np.ndarray | None = None,
    availability: np.ndarray | None = None,
) -> MarketInputs:
    dates = pd.date_range("2024-01-01", periods=score_matrix.shape[0], freq="D").to_numpy()
    tickers = tuple(f"T{i:03d}" for i in range(score_matrix.shape[1]))
    open_matrix = np.full(score_matrix.shape, 100.0, dtype=np.float64)
    adv20_matrix = np.full(score_matrix.shape, 1e12, dtype=np.float64) if adv20 is None else adv20
    benchmark_open = np.full(score_matrix.shape[0], 100.0, dtype=np.float64)
    availability_matrix = np.ones(score_matrix.shape, dtype=bool) if availability is None else availability
    return MarketInputs(
        dates=dates,
        tickers=tickers,
        benchmark_open=benchmark_open,
        open_matrix=open_matrix,
        adv20_matrix=adv20_matrix,
        can_buy_matrix=np.ones(score_matrix.shape, dtype=bool) if can_buy is None else can_buy,
        can_sell_matrix=np.ones(score_matrix.shape, dtype=bool) if can_sell is None else can_sell,
        availability_matrix=availability_matrix,
        score_matrices={"test": score_matrix.astype(np.float64)},
        tradability_source="test",
    )


def test_simulate_strategy_blocks_sell_until_t_plus_3_close():
    scores = np.array(
        [
            [0.9, 0.1],
            [0.1, 0.9],
            [0.1, 0.9],
            [0.1, 0.9],
            [0.1, 0.9],
            [0.1, 0.9],
        ],
        dtype=np.float64,
    )
    result = simulate_strategy(
        strategy_name="test",
        signal_columns=["mock_signal"],
        market_inputs=_market_inputs(scores),
        top_k=1,
        rebalance_every=1,
        weighting="equal",
        initial_notional_vnd=1.0,
        max_adv_participation=1.0,
        required_holding_age=3,
        buy_fee_rate=0.0,
        sell_fee_rate=0.0,
        capital_gains_tax_rate=0.0,
    )

    daily = result.daily
    assert daily.loc[0, "held_tickers"] == ["T000"]
    assert daily.loc[1, "held_tickers"] == ["T000"]
    assert daily.loc[1, "blocked_sell_count"] == 1
    assert daily.loc[2, "held_tickers"] == ["T000"]
    assert daily.loc[2, "blocked_sell_count"] == 1
    assert daily.loc[3, "held_tickers"] == ["T001"]
    assert daily.loc[3, "blocked_sell_count"] == 0


def test_simulate_strategy_blocks_unbuyable_stock_and_keeps_cash():
    scores = np.array(
        [
            [0.9, 0.1],
            [0.9, 0.1],
            [0.9, 0.1],
            [0.9, 0.1],
        ],
        dtype=np.float64,
    )
    can_buy = np.ones_like(scores, dtype=bool)
    can_buy[0, 0] = False  # Signal-date flag blocks the next open buy for AAA.

    result = simulate_strategy(
        strategy_name="test",
        signal_columns=["mock_signal"],
        market_inputs=_market_inputs(scores, can_buy=can_buy),
        top_k=1,
        rebalance_every=1,
        weighting="equal",
        initial_notional_vnd=1.0,
        max_adv_participation=1.0,
        required_holding_age=3,
        buy_fee_rate=0.0,
        sell_fee_rate=0.0,
        capital_gains_tax_rate=0.0,
    )

    first_day = result.daily.iloc[0]
    assert first_day["num_holdings"] == 0
    assert first_day["cash_weight"] == 1.0
    assert first_day["blocked_buy_count"] == 1


def test_simulate_strategy_uses_signal_date_adv_for_capacity():
    scores = np.array(
        [
            [0.9],
            [0.9],
            [0.9],
        ],
        dtype=np.float64,
    )
    adv20 = np.array(
        [
            [0.2],
            [1_000.0],
            [1_000.0],
        ],
        dtype=np.float64,
    )

    result = simulate_strategy(
        strategy_name="test",
        signal_columns=["mock_signal"],
        market_inputs=_market_inputs(scores, adv20=adv20),
        top_k=1,
        rebalance_every=1,
        weighting="equal",
        initial_notional_vnd=1.0,
        max_adv_participation=0.5,
        required_holding_age=3,
        buy_fee_rate=0.0,
        sell_fee_rate=0.0,
        capital_gains_tax_rate=0.0,
    )

    first_day = result.daily.iloc[0]
    assert first_day["cash_weight"] == 0.9
    assert first_day["capacity_clipped_count"] == 1


def test_simulate_strategy_applies_min_adv20_floor():
    scores = np.array(
        [
            [0.9],
            [0.9],
            [0.9],
        ],
        dtype=np.float64,
    )
    adv20 = np.array(
        [
            [0.4],
            [1_000.0],
            [1_000.0],
        ],
        dtype=np.float64,
    )

    result = simulate_strategy(
        strategy_name="test",
        signal_columns=["mock_signal"],
        market_inputs=_market_inputs(scores, adv20=adv20),
        top_k=1,
        rebalance_every=1,
        weighting="equal",
        initial_notional_vnd=1.0,
        max_adv_participation=1.0,
        required_holding_age=3,
        buy_fee_rate=0.0,
        sell_fee_rate=0.0,
        capital_gains_tax_rate=0.0,
        min_adv20_value_vnd=0.5,
    )

    first_day = result.daily.iloc[0]
    assert first_day["eligible_universe_size"] == 0
    assert first_day["num_holdings"] == 0
    assert first_day["cash_weight"] == 1.0


def test_simulate_strategy_applies_absolute_position_cap():
    scores = np.array(
        [
            [0.9],
            [0.9],
            [0.9],
        ],
        dtype=np.float64,
    )

    result = simulate_strategy(
        strategy_name="test",
        signal_columns=["mock_signal"],
        market_inputs=_market_inputs(scores),
        top_k=1,
        rebalance_every=1,
        weighting="equal",
        initial_notional_vnd=1.0,
        max_adv_participation=1.0,
        required_holding_age=3,
        buy_fee_rate=0.0,
        sell_fee_rate=0.0,
        capital_gains_tax_rate=0.0,
        max_position_vnd=0.25,
    )

    first_day = result.daily.iloc[0]
    assert first_day["cash_weight"] == 0.75
    assert first_day["capacity_clipped_count"] == 1


def test_simulate_strategy_capture_blotter_emits_per_ticker_rows():
    scores = np.array(
        [
            [0.9, 0.1],
            [0.9, 0.1],
            [0.9, 0.1],
        ],
        dtype=np.float64,
    )
    adv20 = np.array(
        [
            [10.0, 10.0],
            [10.0, 10.0],
            [10.0, 10.0],
        ],
        dtype=np.float64,
    )

    result = simulate_strategy(
        strategy_name="test",
        signal_columns=["mock_signal"],
        market_inputs=_market_inputs(scores, adv20=adv20),
        top_k=1,
        rebalance_every=1,
        weighting="equal",
        initial_notional_vnd=1.0,
        max_adv_participation=1.0,
        required_holding_age=3,
        buy_fee_rate=0.0,
        sell_fee_rate=0.0,
        capital_gains_tax_rate=0.0,
        capture_blotter=True,
    )

    assert result.blotter is not None
    assert not result.blotter.empty
    assert {"ticker", "target_notional_vnd", "target_pct_adv20", "buy_blocked"}.issubset(result.blotter.columns)


def test_simulate_strategy_supports_date_varying_incumbent_score_bonus():
    scores = np.array(
        [
            [0.9, 0.1],
            [0.9, 0.1],
            [0.9, 0.1],
            [0.5, 0.55],
            [0.1, 0.9],
            [0.1, 0.9],
        ],
        dtype=np.float64,
    )
    base = simulate_strategy(
        strategy_name="test",
        signal_columns=["mock_signal"],
        market_inputs=_market_inputs(scores),
        top_k=1,
        rebalance_every=1,
        weighting="equal",
        initial_notional_vnd=1.0,
        max_adv_participation=1.0,
        required_holding_age=3,
        buy_fee_rate=0.0,
        sell_fee_rate=0.0,
        capital_gains_tax_rate=0.0,
    )
    scheduled = simulate_strategy(
        strategy_name="test",
        signal_columns=["mock_signal"],
        market_inputs=_market_inputs(scores),
        top_k=1,
        rebalance_every=1,
        weighting="equal",
        initial_notional_vnd=1.0,
        max_adv_participation=1.0,
        required_holding_age=3,
        buy_fee_rate=0.0,
        sell_fee_rate=0.0,
        capital_gains_tax_rate=0.0,
        incumbent_score_bonus=np.array([0.0, 0.0, 0.0, 0.1, 0.0, 0.0], dtype=np.float64),
    )

    assert base.daily.loc[3, "held_tickers"] == ["T001"]
    assert scheduled.daily.loc[3, "held_tickers"] == ["T000"]


def test_entry_filter_only_blocks_new_buys_not_existing_holdings():
    scores = np.array(
        [
            [0.9, 0.1],
            [0.9, 0.1],
            [0.9, 0.1],
            [0.9, 0.1],
        ],
        dtype=np.float64,
    )
    entry_allowed = np.array(
        [
            [True, True],
            [False, True],
            [False, True],
            [False, True],
        ],
        dtype=bool,
    )

    result = simulate_strategy(
        strategy_name="test",
        signal_columns=["mock_signal"],
        market_inputs=_market_inputs(scores),
        top_k=1,
        rebalance_every=1,
        weighting="equal",
        initial_notional_vnd=1.0,
        max_adv_participation=1.0,
        required_holding_age=3,
        buy_fee_rate=0.0,
        sell_fee_rate=0.0,
        capital_gains_tax_rate=0.0,
        entry_allowed_matrix=entry_allowed,
    )

    assert result.daily.loc[0, "held_tickers"] == ["T000"]
    assert result.daily.loc[1, "held_tickers"] == ["T000"]
    assert result.daily.loc[1, "num_holdings"] == 1


def test_entry_slicing_accumulates_between_rebalance_days():
    scores = np.array(
        [
            [0.9],
            [0.9],
            [0.9],
            [0.9],
            [0.9],
            [0.9],
        ],
        dtype=np.float64,
    )
    adv20 = np.array([[0.4], [0.4], [0.4], [0.4], [0.4], [0.4]], dtype=np.float64)

    base = simulate_strategy(
        strategy_name="test",
        signal_columns=["mock_signal"],
        market_inputs=_market_inputs(scores, adv20=adv20),
        top_k=1,
        rebalance_every=5,
        weighting="equal",
        initial_notional_vnd=1.0,
        max_adv_participation=1.0,
        required_holding_age=3,
        buy_fee_rate=0.0,
        sell_fee_rate=0.0,
        capital_gains_tax_rate=0.0,
        entry_slice_days=1,
    )
    sliced = simulate_strategy(
        strategy_name="test",
        signal_columns=["mock_signal"],
        market_inputs=_market_inputs(scores, adv20=adv20),
        top_k=1,
        rebalance_every=5,
        weighting="equal",
        initial_notional_vnd=1.0,
        max_adv_participation=0.0,
        required_holding_age=3,
        buy_fee_rate=0.0,
        sell_fee_rate=0.0,
        capital_gains_tax_rate=0.0,
        entry_slice_days=3,
        daily_buy_adv_participation=1.0,
    )

    assert base.daily.loc[1, "cash_weight"] == 0.6
    assert sliced.daily.loc[1, "cash_weight"] < base.daily.loc[1, "cash_weight"]
    assert sliced.summary["partial_fill_count"] >= 1


def test_min_deployable_weight_filters_small_capacity_names():
    scores = np.array(
        [
            [0.9],
            [0.9],
            [0.9],
        ],
        dtype=np.float64,
    )
    adv20 = np.array([[0.05], [0.05], [0.05]], dtype=np.float64)

    result = simulate_strategy(
        strategy_name="test",
        signal_columns=["mock_signal"],
        market_inputs=_market_inputs(scores, adv20=adv20),
        top_k=1,
        rebalance_every=1,
        weighting="equal",
        initial_notional_vnd=1.0,
        max_adv_participation=1.0,
        required_holding_age=3,
        buy_fee_rate=0.0,
        sell_fee_rate=0.0,
        capital_gains_tax_rate=0.0,
        min_deployable_weight=0.10,
    )

    assert result.daily.loc[0, "eligible_universe_size"] == 0
    assert result.daily.loc[0, "cash_weight"] == 1.0


def test_compute_selected_target_weights_respects_weighting_scheme():
    scores = np.array([0.90, 0.70, 0.55], dtype=np.float64)
    selected = [0, 1, 2]

    equal = compute_selected_target_weights(scores, selected, weighting="equal")
    linear = compute_selected_target_weights(scores, selected, weighting="linear")
    square = compute_selected_target_weights(scores, selected, weighting="square")

    assert np.allclose(equal[selected], np.array([1 / 3, 1 / 3, 1 / 3]))
    assert linear[0] > linear[1] > linear[2] > 0.0
    assert square[0] > linear[0]
    assert np.isclose(linear.sum(), 1.0)
    assert np.isclose(square.sum(), 1.0)


def test_compute_strategy_scores_cross_sectionally_ranks_non_presence_columns():
    matrix = pd.DataFrame(
        {
            "time": pd.to_datetime(["2024-01-01", "2024-01-01", "2024-01-02", "2024-01-02"]),
            "ticker": ["AAA", "BBB", "AAA", "BBB"],
            "actual": [0, 0, 0, 0],
            "raw_signal": [10.0, 1_000_000.0, 5.0, -5.0],
            "flag_present": [1.0, 0.0, 0.0, 1.0],
        }
    )

    scored = compute_strategy_scores(
        matrix,
        {"test_raw": ["raw_signal"], "test_flag": ["flag_present"]},
    )
    day1_raw = scored.loc[scored["time"] == pd.Timestamp("2024-01-01"), "score__test_raw"].tolist()
    day2_raw = scored.loc[scored["time"] == pd.Timestamp("2024-01-02"), "score__test_raw"].tolist()
    day1_flag = scored.loc[scored["time"] == pd.Timestamp("2024-01-01"), "score__test_flag"].tolist()

    assert day1_raw[1] > day1_raw[0]
    assert day2_raw[0] > day2_raw[1]
    assert day1_flag == [1.0, 0.0]
