from __future__ import annotations

import numpy as np
import pandas as pd

from vn_stock_rl.env import PortfolioChoiceEnv


def _make_price_df(length: int, base_price: float, volume_level: float) -> pd.DataFrame:
    times = pd.date_range("2020-01-01", periods=length, freq="D")
    close = base_price + np.linspace(0.0, 20.0, length, dtype=np.float64)
    open_ = close * 0.998
    return pd.DataFrame(
        {
            "time": times,
            "open": open_,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.full(length, volume_level, dtype=np.float64),
        }
    )


def _make_signal_df(length: int, offset: float) -> pd.DataFrame:
    times = pd.date_range("2020-01-01", periods=length, freq="D")
    return pd.DataFrame(
        {
            "date": times.strftime("%Y-%m-%d"),
            "s1_proba": np.linspace(0.1 + offset, 0.9 + offset, length, dtype=np.float64),
        }
    )


def _write_ticker_bundle(tmp_path, ticker: str, price_df: pd.DataFrame, signal_df: pd.DataFrame) -> None:
    price_df.to_parquet(tmp_path / f"gia_lich_su_{ticker}_1D.parquet", index=False)
    signal_dir = tmp_path / "signals"
    signal_dir.mkdir(parents=True, exist_ok=True)
    signal_df.to_parquet(signal_dir / f"{ticker}_signal_predictions.parquet", index=False)


def test_portfolio_choice_env_selects_deterministic_liquid_universe(tmp_path):
    length = 400
    _write_ticker_bundle(tmp_path, "ACB", _make_price_df(length, 100.0, 2_000_000.0), _make_signal_df(length, 0.00))
    _write_ticker_bundle(tmp_path, "FPT", _make_price_df(length, 90.0, 1_500_000.0), _make_signal_df(length, 0.05))
    _write_ticker_bundle(tmp_path, "HPG", _make_price_df(length, 80.0, 200_000.0), _make_signal_df(length, 0.10))

    env = PortfolioChoiceEnv(
        data_dir=str(tmp_path),
        mode="train",
        train_episode_sampling_enabled=False,
        signal_feature_columns=["s1_proba"],
        signal_prediction_dir=str(tmp_path / "signals"),
        portfolio_universe_size=2,
        portfolio_top_k=2,
    )

    assert env.universe_tickers == ["ACB", "FPT"]
    assert env.observation_space.shape == (5,)
    env.close()


def test_portfolio_choice_env_delays_execution_and_deduplicates_actions(tmp_path):
    length = 400
    _write_ticker_bundle(tmp_path, "ACB", _make_price_df(length, 100.0, 2_000_000.0), _make_signal_df(length, 0.00))
    _write_ticker_bundle(tmp_path, "FPT", _make_price_df(length, 90.0, 1_500_000.0), _make_signal_df(length, 0.05))

    env = PortfolioChoiceEnv(
        data_dir=str(tmp_path),
        mode="train",
        train_episode_sampling_enabled=False,
        signal_feature_columns=["s1_proba"],
        signal_prediction_dir=str(tmp_path / "signals"),
        portfolio_universe_size=2,
        portfolio_top_k=2,
    )

    weights, indices, tickers = env._decode_action(np.array([0, 0], dtype=np.int64))
    np.testing.assert_allclose(weights, np.array([1.0, 0.0]))
    assert indices == [0]
    assert tickers == ["ACB"]

    obs, info = env.reset(seed=7)
    assert obs.shape == (5,)
    assert info["universe_tickers"] == ["ACB", "FPT"]

    action = np.array([0, 1], dtype=np.int64)
    _obs_1, _reward_1, terminated_1, truncated_1, info_1 = env.step(action)
    assert not terminated_1
    assert not truncated_1
    assert info_1["num_holdings"] == 0
    assert info_1["selected_tickers"] == ["ACB", "FPT"]

    _obs_2, _reward_2, terminated_2, truncated_2, info_2 = env.step(action)
    assert not terminated_2
    assert not truncated_2
    assert info_2["num_holdings"] == 2
    assert info_2["cash_weight"] == 0.0
    np.testing.assert_allclose(env.current_weights, np.array([0.5, 0.5]))
    env.close()
