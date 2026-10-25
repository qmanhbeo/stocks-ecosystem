from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vn_stock_rl.trade_episode.causal_features import (
    CAUSAL_MARKET_FEATURE_NAMES,
    build_causal_normalized_market_features,
    causal_feature_warmup_mask,
)
from vn_stock_rl.trade_episode.data import load_daily_stock_bars
from vn_stock_rl.trade_episode.environment import TradeEpisodeEnv
from vn_stock_rl.trade_episode.multi_stock_environment import MultiStockEpisodeEnv
from vn_stock_rl.trade_episode.phase4a_data import alpha_observation_matrix
from vn_stock_rl.trade_episode.signals import ALPHA_FEATURE_NAMES, load_alpha_signals


def _bars(count: int = 110) -> pd.DataFrame:
    rng = np.random.default_rng(781)
    returns = rng.normal(0.0003, 0.018, count)
    close = 100.0 * np.exp(np.cumsum(returns))
    opening = close * np.exp(rng.normal(0.0, 0.004, count))
    return pd.DataFrame(
        {
            "time": pd.date_range("2014-09-01", periods=count, freq="B"),
            "open": opening,
            "high": np.maximum(opening, close) * 1.01,
            "low": np.minimum(opening, close) * 0.99,
            "close": close,
            "volume": rng.integers(100, 10000, count),
        }
    )


def _env(ticker: str, feature_value: float) -> TradeEpisodeEnv:
    count = 40
    features = np.full((count, 2), feature_value, dtype=np.float32)
    return TradeEpisodeEnv(
        np.full(count, 10.0),
        np.full(count, 10.0),
        price_basis="synthetic",
        market_features=features,
        feature_names=["causal_return", "causal_volatility"],
        dates=pd.date_range("2020-01-01", periods=count, freq="B"),
        ticker=ticker,
        max_episode_steps=20,
        max_wait_steps=20,
        max_holding_intervals=20,
    )


def test_normalizer_uses_lagged_ticker_local_volatility_and_expected_warmup():
    bars = _bars()
    features, volatility = build_causal_normalized_market_features(bars)
    finite = causal_feature_warmup_mask(features, volatility)
    assert features.columns.tolist() == CAUSAL_MARKET_FEATURE_NAMES
    assert np.flatnonzero(finite)[0] == 61
    assert np.isfinite(features.loc[finite].to_numpy()).all()
    assert np.isfinite(volatility.to_numpy()[finite]).all()

    changed = bars.copy()
    changed.loc[75, "close"] *= 1.8
    changed_features, _ = build_causal_normalized_market_features(changed)
    assert (
        changed_features.loc[75, "market_log_lagged_volatility_60d"]
        == features.loc[75, "market_log_lagged_volatility_60d"]
    )
    assert (
        changed_features.loc[75, "market_log_return_1d_scaled"]
        != features.loc[75, "market_log_return_1d_scaled"]
    )


def test_causal_features_do_not_change_when_future_rows_change():
    bars = _bars()
    changed = bars.copy()
    changed.loc[90:, ["open", "high", "low", "close", "volume"]] *= 50.0
    original, _ = build_causal_normalized_market_features(bars)
    altered, _ = build_causal_normalized_market_features(changed)
    np.testing.assert_allclose(
        original.iloc[:90].to_numpy(), altered.iloc[:90].to_numpy(), equal_nan=True
    )


def test_alpha_missingness_uses_neutral_sentinel_and_binary_availability():
    frame = pd.DataFrame(
        {
            "alpha_s1_xs_proba": [np.nan, 0.8],
            "alpha_s1_available": [0.0, 1.0],
            "alpha_c16_order_volume_ratio_rank": [np.nan, 0.2],
            "alpha_c16_available": [0.0, 1.0],
        },
        columns=ALPHA_FEATURE_NAMES,
    )
    values = alpha_observation_matrix(frame)
    np.testing.assert_allclose(values[0], [0.5, 0.0, 0.5, 0.0])
    np.testing.assert_allclose(values[1], [0.8, 1.0, 0.2, 1.0])


def test_multi_stock_observations_hide_ticker_and_sample_stocks_and_dates():
    env = MultiStockEpisodeEnv(
        {"AAA": _env("AAA", 1.0), "BBB": _env("BBB", 2.0)},
        eligible_start_indices={
            "AAA": np.arange(2, 12),
            "BBB": np.arange(3, 13),
        },
    )
    assert all("ticker" not in name.lower() for name in env.observation_feature_names)
    assert all("symbol" not in name.lower() for name in env.observation_feature_names)
    assert env.observation_space.shape == (7,)

    tickers = []
    starts = {ticker: set() for ticker in ("AAA", "BBB")}
    for index in range(40):
        observation, info = env.reset(seed=1208 if index == 0 else None)
        ticker = info["sampled_ticker"]
        tickers.append(ticker)
        starts[ticker].add(info["sampled_start_index"])
        assert observation.shape == env.observation_space.shape
        assert np.isfinite(observation).all()
    assert set(tickers) == {"AAA", "BBB"}
    assert len(starts["AAA"]) > 1 and len(starts["BBB"]) > 1
    assert abs(tickers.count("AAA") - tickers.count("BBB")) <= 1
    env.close()


def test_unrealized_return_uses_volatility_known_at_entry():
    env = TradeEpisodeEnv(
        [100, 100, 100, 100, 100, 100],
        [100, 105, 110, 112, 113, 114],
        price_basis="synthetic",
        daily_volatility_scale=[0.02, 0.03, 0.04, 0.05, 0.06, 0.07],
        max_episode_steps=10,
        max_wait_steps=10,
        max_holding_intervals=10,
    )
    observation, _ = env.reset(seed=1)
    assert observation[-5] == 0.0
    observation, *_ = env.step(1)
    expected = np.log(1.05) / 0.02
    assert observation[-3] == pytest.approx(expected)
    env.close()


def test_stock_loader_enforces_cutoff_inside_single_row_group(tmp_path):
    stock_dir = tmp_path / "stock"
    stock_dir.mkdir()
    path = stock_dir / "gia_lich_su_TEST_1D.parquet"
    frame = pd.DataFrame(
        {
            "time": pd.to_datetime(["2025-12-30", "2025-12-31", "2026-01-02"]),
            "open": [10.0, 11.0, 12.0],
            "high": [11.0, 12.0, 13.0],
            "low": [9.0, 10.0, 11.0],
            "close": [10.5, 11.5, 12.5],
            "volume": [100, 200, 300],
        }
    )
    frame.to_parquet(path, index=False, row_group_size=10)
    loaded = load_daily_stock_bars(
        "TEST", data_root=tmp_path, start_date="2025-12-30", end_date="2025-12-31"
    )
    assert loaded["time"].dt.normalize().max() == pd.Timestamp("2025-12-31")
    assert loaded["close"].tolist() == [10.5, 11.5]


def test_alpha_alignment_discards_rows_outside_requested_decision_dates(tmp_path):
    features = tmp_path / "features"
    features.mkdir()
    pd.DataFrame(
        {
            "time": pd.to_datetime(["2025-12-31", "2026-01-02"]),
            "ticker": ["TEST", "TEST"],
            "xs_proba": [0.7, 0.99],
        }
    ).to_parquet(features / "xs_barrier_vol_1d_hose_full.parquet", index=False)
    pd.DataFrame(
        {
            "time": pd.to_datetime(["2025-12-31", "2026-01-02"]),
            "ticker": ["TEST", "TEST"],
            "order_volume_ratio_rank": [0.3, 0.01],
            "order_pressure_available": [True, True],
        }
    ).to_parquet(features / "xs_order_pressure_daily.parquet", index=False)

    aligned = load_alpha_signals("TEST", pd.to_datetime(["2025-12-31"]), data_root=tmp_path)

    assert aligned.index.tolist() == [pd.Timestamp("2025-12-31")]
    assert aligned.iloc[0]["alpha_s1_xs_proba"] == pytest.approx(0.7)
    assert aligned.iloc[0]["alpha_c16_order_volume_ratio_rank"] == pytest.approx(0.3)
