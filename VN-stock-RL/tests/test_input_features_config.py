"""
Tests for centralized input feature configuration.
"""

import os
import tempfile
import numpy as np
import pandas as pd

from vn_stock_rl.env import TradingEnv
from test_utils import TestEnv


def _make_base_df(length: int, price_start: float = 100.0, price_step: float = 1.0) -> pd.DataFrame:
    prices = price_start + (np.arange(length, dtype=float) * price_step)
    return pd.DataFrame(
        {
            "time": np.arange(length, dtype=int),
            "open": prices,
            "high": prices + 1.0,
            "low": prices - 1.0,
            "close": prices,
            "volume": np.linspace(1000.0, 1000.0 + length - 1, length),
        }
    )


def test_input_features_subset_and_ma_layout_raw():
    print("\n" + "=" * 80)
    print("TEST: Input Features Subset + MA Layout (RAW)")
    print("=" * 80)

    df = _make_base_df(length=30, price_start=100.0, price_step=2.0)
    lookback = 4
    ohlcv_fields = ["open", "close", "volume"]
    ma_windows = [2, 3]

    env = TestEnv(
        df=df,
        start_idx=lookback + 1,
        end_idx=len(df) - 2,
        mode="train",
        lookback_window=lookback,
        source_mode="raw",
        ohlcv=ohlcv_fields,
        ma_windows=ma_windows,
        include_can_exit=False,
        min_hold_days=1,
        stop_loss=None,
    )

    obs, _ = env.reset()

    expected_n_features = lookback * (len(ohlcv_fields) + len(ma_windows))
    expected_obs_dim = expected_n_features + 2  # pos, hold_count
    assert env.observation_space.shape[0] == expected_obs_dim, (
        f"Expected observation dim {expected_obs_dim}, got {env.observation_space.shape[0]}"
    )

    end_idx = env.current_step
    start_idx = end_idx - lookback + 1
    base_expected = df.iloc[start_idx : end_idx + 1][ohlcv_fields].to_numpy(dtype=np.float64).reshape(-1)

    close_series = df["close"].to_numpy(dtype=np.float64)
    ma_matrix = np.empty((lookback, len(ma_windows)), dtype=np.float64)
    for col_idx, window in enumerate(ma_windows):
        ma = pd.Series(close_series).rolling(window=window, min_periods=1).mean().to_numpy(dtype=np.float64)
        ma_matrix[:, col_idx] = ma[start_idx : end_idx + 1]
    ma_expected_flat = ma_matrix.reshape(-1)

    expected_obs = np.concatenate(
        [
            base_expected,
            ma_expected_flat,
            np.array([0.0, 0.0], dtype=np.float64),  # position, hold_count at reset
        ]
    ).astype(np.float32)

    assert np.allclose(obs, expected_obs, atol=1e-6), "Raw observation content does not match expected layout"


def test_input_features_return_mode_values():
    print("\n" + "=" * 80)
    print("TEST: Input Features Return Mode Values")
    print("=" * 80)

    length = 24
    prices = np.array([100.0 * (1.01 ** i) for i in range(length)], dtype=float)
    volumes = np.array([1000.0 * (1.02 ** i) for i in range(length)], dtype=float)
    df = pd.DataFrame(
        {
            "time": np.arange(length, dtype=int),
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "volume": volumes,
        }
    )

    lookback = 5
    ohlcv_fields = ["open", "volume"]
    env = TestEnv(
        df=df,
        start_idx=lookback + 2,
        end_idx=len(df) - 2,
        mode="train",
        lookback_window=lookback,
        source_mode="return",
        ohlcv=ohlcv_fields,
        ma_windows=[],
        include_can_exit=False,
        min_hold_days=1,
        stop_loss=None,
    )

    obs, _ = env.reset()
    end_idx = env.current_step
    start_idx = end_idx - lookback + 1

    expected_rows = []
    for t in range(start_idx, end_idx + 1):
        prev_close = prices[t - 1]
        open_ret = (prices[t] / prev_close) - 1.0
        vol_ret = (volumes[t] / volumes[t - 1]) - 1.0
        expected_rows.append([open_ret, vol_ret])
    expected_base = np.asarray(expected_rows, dtype=np.float32).reshape(-1)
    expected_obs = np.concatenate([expected_base, np.array([0.0, 0.0], dtype=np.float32)])

    assert np.allclose(obs, expected_obs, atol=1e-6), "Return-mode observation values do not match expected returns"


def test_input_features_apply_to_helpers():
    print("\n" + "=" * 80)
    print("TEST: Input Features Apply To Helper Tickers")
    print("=" * 80)

    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = os.path.join(tmpdir, "data")
        os.makedirs(data_dir, exist_ok=True)

        base_df = _make_base_df(length=120, price_start=100.0, price_step=0.5)
        helper_df = pd.DataFrame(
            {
                "time": np.arange(120, dtype=int),
                "open": np.full(120, 200.0, dtype=float),
                "high": np.full(120, 200.0, dtype=float),
                "low": np.full(120, 200.0, dtype=float),
                "close": np.full(120, 200.0, dtype=float),
                "volume": np.full(120, 5000.0, dtype=float),
            }
        )

        base_path = os.path.join(data_dir, "gia_lich_su_ACB_1D.parquet")
        helper_path = os.path.join(data_dir, "gia_lich_su_VNINDEX_1D.parquet")
        base_df.to_parquet(base_path, index=False)
        helper_df.to_parquet(helper_path, index=False)

        lookback = 6
        ohlcv_fields = ["open", "close"]
        ma_windows = [3]
        expected_n_features = lookback * (len(ohlcv_fields) + len(ohlcv_fields) + len(ma_windows))
        expected_obs_dim = expected_n_features + 3

        env_raw = TradingEnv(
            data_path=base_path,
            mode="train",
            lookback_window=lookback,
            source_mode="raw",
            ohlcv=ohlcv_fields,
            ma_windows=ma_windows,
            help_tickers=["VNINDEX"],
            market_data_dir=data_dir,
        )
        obs_raw, _ = env_raw.reset()
        assert env_raw.observation_space.shape[0] == expected_obs_dim, (
            f"Expected raw obs dim {expected_obs_dim}, got {env_raw.observation_space.shape[0]}"
        )

        helper_block_start = lookback * len(ohlcv_fields)
        helper_block_end = helper_block_start + lookback * len(ohlcv_fields)
        helper_block_raw = obs_raw[helper_block_start:helper_block_end]
        assert np.allclose(helper_block_raw, 200.0), "Raw helper block should contain constant helper price levels"

        env_return = TradingEnv(
            data_path=base_path,
            mode="train",
            lookback_window=lookback,
            source_mode="return",
            ohlcv=ohlcv_fields,
            ma_windows=ma_windows,
            help_tickers=["VNINDEX"],
            market_data_dir=data_dir,
        )
        obs_return, _ = env_return.reset()
        assert env_return.observation_space.shape[0] == expected_obs_dim, (
            f"Expected return obs dim {expected_obs_dim}, got {env_return.observation_space.shape[0]}"
        )
        helper_block_return = obs_return[helper_block_start:helper_block_end]
        assert np.allclose(helper_block_return, 0.0), (
            "Return helper block should be near zero for constant helper prices"
        )


def test_input_features_helper_ma_same_layout_raw():
    print("\n" + "=" * 80)
    print("TEST: Helper MA Windows 'same' Layout (RAW)")
    print("=" * 80)

    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = os.path.join(tmpdir, "data")
        os.makedirs(data_dir, exist_ok=True)

        length = 140
        base_df = _make_base_df(length=length, price_start=100.0, price_step=1.0)
        helper_close = 200.0 + (np.arange(length, dtype=float) * 2.0)
        helper_df = pd.DataFrame(
            {
                "time": np.arange(length, dtype=int),
                "open": helper_close,
                "high": helper_close + 1.0,
                "low": helper_close - 1.0,
                "close": helper_close,
                "volume": np.linspace(5000.0, 5000.0 + length - 1, length),
            }
        )

        base_path = os.path.join(data_dir, "gia_lich_su_ACB_1D.parquet")
        helper_path = os.path.join(data_dir, "gia_lich_su_VNINDEX_1D.parquet")
        base_df.to_parquet(base_path, index=False)
        helper_df.to_parquet(helper_path, index=False)

        lookback = 5
        env = TradingEnv(
            data_path=base_path,
            mode="train",
            lookback_window=lookback,
            source_mode="raw",
            ohlcv=["open"],
            ma_windows=[2],
            helpers_ma_windows=["same"],
            help_tickers=["VNINDEX"],
            market_data_dir=data_dir,
        )
        obs, _ = env.reset()

        expected_n_features = lookback * (1 + 1 + 1 + 1)
        expected_obs_dim = expected_n_features + 3
        assert env.observation_space.shape[0] == expected_obs_dim
        assert env.helpers_ma_windows == [2]

        end_idx = env.current_step
        start_idx = end_idx - lookback + 1
        helper_ma = (
            pd.Series(helper_close)
            .rolling(window=2, min_periods=1)
            .mean()
            .to_numpy(dtype=np.float64)
        )
        expected_helper_ma_flat = helper_ma[start_idx : end_idx + 1].astype(np.float32)

        helper_ma_block_start = lookback * (1 + 1 + 1)
        helper_ma_block_end = helper_ma_block_start + lookback
        helper_ma_block = obs[helper_ma_block_start:helper_ma_block_end]
        assert np.allclose(helper_ma_block, expected_helper_ma_flat, atol=1e-6), (
            "Helper MA block should match helper rolling MA values when helpers_ma_windows=['same']"
        )


def test_input_features_helper_ma_explicit_windows_shape():
    print("\n" + "=" * 80)
    print("TEST: Helper MA Explicit Windows Shape")
    print("=" * 80)

    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = os.path.join(tmpdir, "data")
        os.makedirs(data_dir, exist_ok=True)

        base_df = _make_base_df(length=120, price_start=100.0, price_step=0.25)
        helper_df = _make_base_df(length=120, price_start=300.0, price_step=0.5)

        base_path = os.path.join(data_dir, "gia_lich_su_ACB_1D.parquet")
        helper_path = os.path.join(data_dir, "gia_lich_su_VNINDEX_1D.parquet")
        base_df.to_parquet(base_path, index=False)
        helper_df.to_parquet(helper_path, index=False)

        lookback = 6
        env = TradingEnv(
            data_path=base_path,
            mode="train",
            lookback_window=lookback,
            source_mode="return",
            ohlcv=["open", "close"],
            ma_windows=[2],
            helpers_ma_windows=[3, 5],
            help_tickers=["VNINDEX"],
            market_data_dir=data_dir,
        )
        obs, _ = env.reset()

        base_dim = 2
        helper_dim = 2
        base_ma_dim = 1
        helper_ma_dim = 2
        expected_n_features = lookback * (base_dim + helper_dim + base_ma_dim + helper_ma_dim)
        expected_obs_dim = expected_n_features + 3
        assert obs.shape[0] == expected_obs_dim
        assert env.helpers_ma_windows == [3, 5]


def test_input_features_returns_windows_values():
    print("\n" + "=" * 80)
    print("TEST: Returns Windows Values")
    print("=" * 80)

    length = 40
    close = np.array([100.0 + i for i in range(length)], dtype=float)
    df = pd.DataFrame(
        {
            "time": np.arange(length, dtype=int),
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": np.linspace(1000.0, 1000.0 + length - 1, length),
        }
    )

    lookback = 5
    returns_windows = [2, 4]
    env = TestEnv(
        df=df,
        start_idx=lookback + 5,
        end_idx=len(df) - 2,
        mode="train",
        lookback_window=lookback,
        source_mode="raw",
        ohlcv=["open"],
        ma_windows=[],
        returns_windows=returns_windows,
        include_can_exit=False,
        min_hold_days=1,
        stop_loss=None,
    )
    obs, _ = env.reset()

    end_idx = env.current_step
    start_idx = end_idx - lookback + 1
    expected_rows = []
    for t in range(start_idx, end_idx + 1):
        expected_rows.append([(close[t] / close[t - w]) - 1.0 for w in returns_windows])
    expected_returns = np.asarray(expected_rows, dtype=np.float32).reshape(-1)

    base_block = lookback * 1
    returns_block = obs[base_block : base_block + lookback * len(returns_windows)]
    assert np.allclose(returns_block, expected_returns, atol=1e-6), (
        "Target returns_windows block values are incorrect"
    )


def test_input_features_helper_returns_windows_same_shape():
    print("\n" + "=" * 80)
    print("TEST: Helper Returns Windows 'same' Shape")
    print("=" * 80)

    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = os.path.join(tmpdir, "data")
        os.makedirs(data_dir, exist_ok=True)

        base_df = _make_base_df(length=120, price_start=100.0, price_step=1.0)
        helper_df = _make_base_df(length=120, price_start=300.0, price_step=2.0)

        base_path = os.path.join(data_dir, "gia_lich_su_ACB_1D.parquet")
        helper_path = os.path.join(data_dir, "gia_lich_su_VNINDEX_1D.parquet")
        base_df.to_parquet(base_path, index=False)
        helper_df.to_parquet(helper_path, index=False)

        lookback = 6
        env = TradingEnv(
            data_path=base_path,
            mode="train",
            lookback_window=lookback,
            source_mode="return",
            ohlcv=["open"],
            ma_windows=[],
            returns_windows=[3],
            helpers_returns_windows=["same"],
            help_tickers=["VNINDEX"],
            market_data_dir=data_dir,
        )
        obs, _ = env.reset()

        assert env.helpers_returns_windows == [3]
        expected_n_features = lookback * (1 + 1 + 1 + 1)
        expected_obs_dim = expected_n_features + 3
        assert obs.shape[0] == expected_obs_dim
