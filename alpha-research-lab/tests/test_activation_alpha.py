from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import activation_alpha
from src.activation_alpha import (
    _validate_benchmark_date_coverage,
    _validate_matrix_signal_coverage,
    compute_cycle_metrics,
    load_or_build_activation_state,
    selector_definitions,
)
from src.deterministic_portfolio import MarketInputs, simulate_strategy


def _market_inputs(score_matrix: np.ndarray) -> MarketInputs:
    dates = pd.date_range("2024-01-01", periods=score_matrix.shape[0], freq="D").to_numpy()
    tickers = tuple(f"T{i:03d}" for i in range(score_matrix.shape[1]))
    return MarketInputs(
        dates=dates,
        tickers=tickers,
        benchmark_open=np.full(score_matrix.shape[0], 100.0, dtype=np.float64),
        open_matrix=np.full(score_matrix.shape, 100.0, dtype=np.float64),
        adv20_matrix=np.full(score_matrix.shape, 1e12, dtype=np.float64),
        can_buy_matrix=np.ones(score_matrix.shape, dtype=bool),
        can_sell_matrix=np.ones(score_matrix.shape, dtype=bool),
        availability_matrix=np.ones(score_matrix.shape, dtype=bool),
        score_matrices={
            "full_library": score_matrix.astype(np.float64),
            "s1_only": score_matrix.astype(np.float64),
        },
        tradability_source="test",
    )


def test_selector_definitions_expose_primary_and_secondary_branches():
    selectors = selector_definitions(["time", "ticker", "actual", "s1_proba", "c4_oc_asym_5d"])
    assert [selector.name for selector in selectors] == ["full_library_k5_r5_eq", "s1_only_k5_r5_eq"]
    assert selectors[0].strategy_name == "full_library"
    assert selectors[1].strategy_name == "s1_only"


def test_simulate_strategy_activation_mask_forces_cash_cycle():
    scores = np.array(
        [
            [0.9, 0.1],
            [0.9, 0.1],
            [0.9, 0.1],
            [0.9, 0.1],
            [0.1, 0.9],
            [0.1, 0.9],
            [0.1, 0.9],
        ],
        dtype=np.float64,
    )
    activation_mask = np.array([True, True, True, False, False, True, True], dtype=bool)
    result = simulate_strategy(
        strategy_name="full_library",
        signal_columns=["mock_signal"],
        market_inputs=_market_inputs(scores),
        top_k=1,
        rebalance_every=1,
        weighting="equal",
        initial_notional_vnd=1.0,
        max_adv_participation=0.0,
        required_holding_age=3,
        buy_fee_rate=0.0,
        sell_fee_rate=0.0,
        capital_gains_tax_rate=0.0,
        activation_mask=activation_mask,
    )

    daily = result.daily
    assert bool(daily.loc[0, "activation_on"]) is True
    assert bool(daily.loc[3, "activation_on"]) is False
    assert daily.loc[3, "num_holdings"] == 0
    assert daily.loc[3, "cash_weight"] == 1.0


def test_simulate_strategy_activation_scale_supports_partial_exposure():
    scores = np.array(
        [
            [0.9, 0.1],
            [0.9, 0.1],
            [0.9, 0.1],
            [0.9, 0.1],
        ],
        dtype=np.float64,
    )
    result = simulate_strategy(
        strategy_name="full_library",
        signal_columns=["mock_signal"],
        market_inputs=_market_inputs(scores),
        top_k=1,
        rebalance_every=1,
        weighting="equal",
        initial_notional_vnd=1.0,
        max_adv_participation=0.0,
        required_holding_age=3,
        buy_fee_rate=0.0,
        sell_fee_rate=0.0,
        capital_gains_tax_rate=0.0,
        activation_scale=np.array([0.5, 0.5, 1.0, 1.0], dtype=np.float64),
    )

    daily = result.daily
    assert bool(daily.loc[0, "activation_on"]) is True
    assert daily.loc[0, "activation_scale"] == 0.5
    assert daily.loc[0, "cash_weight"] == 0.5
    assert daily.loc[2, "activation_scale"] == 1.0


def test_compute_cycle_metrics_summarizes_active_cycles():
    daily = pd.DataFrame(
        {
            "signal_date": pd.to_datetime([
                "2024-01-01",
                "2024-01-02",
                "2024-01-03",
                "2024-01-04",
            ]),
            "portfolio_return": [0.01, 0.02, -0.01, 0.03],
            "rebalance_triggered": [True, False, True, False],
            "activation_on": [True, True, False, False],
        }
    )

    metrics = compute_cycle_metrics(daily)
    assert metrics["cycle_count"] == 2
    assert metrics["active_cycle_count"] == 1
    assert metrics["active_cycle_hit_rate"] == 1.0
    assert metrics["activation_on_rate"] == 0.5
    assert metrics["avg_activation_scale"] == 0.5


def test_load_or_build_activation_state_rebuilds_when_cached_range_is_stale(tmp_path, monkeypatch):
    matrix_path = tmp_path / "matrix.parquet"
    pd.DataFrame({"time": pd.to_datetime(["2025-12-31", "2026-01-02"])}).to_parquet(matrix_path, index=False)

    cached_path = tmp_path / "activation_state.parquet"
    cached = pd.DataFrame(
        {
            "time": pd.to_datetime(["2025-12-31"]),
            "full_top5_mean_clv": [0.5],
            "s1_top5_mean_clv": [0.5],
            "full_top5_prev_overlap_ratio": [0.0],
            "s1_top5_prev_overlap_ratio": [0.0],
            "full_top1_prev_same": [0.0],
            "s1_top1_prev_same": [0.0],
        }
    )
    cached.to_parquet(cached_path, index=False)

    rebuilt = cached.copy()
    rebuilt.loc[:, "time"] = pd.to_datetime(["2026-01-02"])
    calls: list[tuple[int, int]] = []

    def fake_persist_activation_state(**kwargs):
        calls.append((int(kwargs["start_year"]), int(kwargs["end_year"])))
        return rebuilt

    monkeypatch.setattr(activation_alpha, "persist_activation_state", fake_persist_activation_state)

    frame, source = load_or_build_activation_state(
        out_path=cached_path,
        matrix_path=matrix_path,
        tradability_path=tmp_path / "tradability.parquet",
        stock_dir=tmp_path,
        benchmark_path=tmp_path / "benchmark.parquet",
        start_year=2015,
        end_year=2026,
    )

    assert source == "built"
    assert calls == [(2015, 2026)]
    assert pd.Timestamp(frame["time"].max()) == pd.Timestamp("2026-01-02")


def test_validate_matrix_signal_coverage_rejects_latest_date_with_missing_dense_signal():
    matrix = pd.DataFrame(
        {
            "time": pd.to_datetime(["2026-03-30", "2026-03-31"]),
            "c4_oc_asym_5d": [0.2, np.nan],
        }
    )

    with pytest.raises(ValueError, match="2026-03-31"):
        _validate_matrix_signal_coverage(matrix)


def test_validate_benchmark_date_coverage_rejects_lagging_index(tmp_path):
    benchmark_path = tmp_path / "benchmark.parquet"
    pd.DataFrame({"time": pd.to_datetime(["2026-03-27"])}).to_parquet(benchmark_path, index=False)

    with pytest.raises(ValueError, match="2026-03-27"):
        _validate_benchmark_date_coverage(
            benchmark_path=benchmark_path,
            required_end=pd.Timestamp("2026-03-31"),
        )
