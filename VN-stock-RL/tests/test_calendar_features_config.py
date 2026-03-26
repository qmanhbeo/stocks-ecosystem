"""
Tests for calendar feature configuration and encoding.
"""

import os
import tempfile
import numpy as np
import pandas as pd

from vn_stock_rl.env import TradingEnv
from test_utils import TestEnv


def _make_date_df(start: str, length: int, base_price: float = 100.0) -> pd.DataFrame:
    dates = pd.date_range(start=start, periods=length, freq="D")
    prices = base_price + np.arange(length, dtype=float)
    return pd.DataFrame(
        {
            "time": dates,
            "open": prices,
            "high": prices + 1.0,
            "low": prices - 1.0,
            "close": prices,
            "volume": np.linspace(1000.0, 1000.0 + length - 1, length),
        }
    )


def _calendar_sincos(dates: pd.Series, features) -> np.ndarray:
    out = []
    dt = pd.to_datetime(dates, errors="raise")
    for feature in features:
        if feature == "dow":
            values = dt.dt.dayofweek.to_numpy(dtype=np.float64)
            period = 7.0
        elif feature == "month":
            values = dt.dt.month.to_numpy(dtype=np.float64)
            period = 12.0
        elif feature == "dom":
            values = dt.dt.day.to_numpy(dtype=np.float64)
            period = 31.0
        else:
            raise ValueError(f"Unknown calendar feature: {feature}")
        angles = (2.0 * np.pi * values) / period
        out.append(np.sin(angles))
        out.append(np.cos(angles))
    return np.column_stack(out).astype(np.float64, copy=False)


def test_calendar_feature_shape_and_order():
    print("\n" + "=" * 80)
    print("TEST: Calendar Feature Shape and Order")
    print("=" * 80)

    df = _make_date_df(start="2024-01-01", length=40)
    lookback = 4
    calendar_features = ["dow", "month", "dom"]

    env = TestEnv(
        df=df,
        start_idx=lookback + 1,
        end_idx=len(df) - 2,
        mode="train",
        lookback_window=lookback,
        source_mode="raw",
        ohlcv=["open", "close"],
        ma_windows=[3],
        calendar_features=calendar_features,
        include_can_exit=False,
        min_hold_days=1,
        stop_loss=None,
    )
    obs, _ = env.reset()

    base_dim = len(env.ohlcv_fields)
    ma_dim = len(env.ma_windows)
    cal_dim = 2 * len(calendar_features)
    expected_n_features = lookback * (base_dim + ma_dim + cal_dim)
    expected_obs_dim = expected_n_features + 2
    assert env.observation_space.shape[0] == expected_obs_dim

    end_idx = env.current_step
    start_idx = end_idx - lookback + 1
    expected_calendar = _calendar_sincos(df.iloc[start_idx : end_idx + 1]["time"], calendar_features).reshape(-1)

    calendar_block_start = lookback * (base_dim + ma_dim)
    calendar_block_end = calendar_block_start + lookback * cal_dim
    obs_calendar = obs[calendar_block_start:calendar_block_end]
    assert np.allclose(obs_calendar, expected_calendar.astype(np.float32), atol=1e-6)


def test_calendar_sincos_values_known_dates():
    print("\n" + "=" * 80)
    print("TEST: Calendar Sin/Cos Values for Known Dates")
    print("=" * 80)

    dates = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
    prices = np.array([100.0, 101.0, 102.0, 103.0, 104.0], dtype=float)
    df = pd.DataFrame(
        {
            "time": dates,
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "volume": np.full(len(dates), 1000.0, dtype=float),
        }
    )
    lookback = 3
    calendar_features = ["dow", "month", "dom"]

    env = TestEnv(
        df=df,
        start_idx=lookback + 1,
        end_idx=len(df) - 2,
        mode="train",
        lookback_window=lookback,
        source_mode="raw",
        ohlcv=["open"],
        ma_windows=[],
        calendar_features=calendar_features,
        include_can_exit=False,
        min_hold_days=1,
        stop_loss=None,
    )
    obs, _ = env.reset()

    end_idx = env.current_step
    start_idx = end_idx - lookback + 1
    expected_calendar = _calendar_sincos(df.iloc[start_idx : end_idx + 1]["time"], calendar_features).reshape(-1)

    calendar_block_start = lookback * len(env.ohlcv_fields)
    calendar_block_end = calendar_block_start + lookback * (2 * len(calendar_features))
    obs_calendar = obs[calendar_block_start:calendar_block_end]
    assert np.allclose(obs_calendar, expected_calendar.astype(np.float32), atol=1e-6)


def test_calendar_mode_invariance():
    print("\n" + "=" * 80)
    print("TEST: Calendar Mode Invariance (RAW vs RETURN)")
    print("=" * 80)

    df = _make_date_df(start="2024-02-01", length=30)
    lookback = 5
    calendar_features = ["dow", "month", "dom"]

    env_raw = TestEnv(
        df=df,
        start_idx=lookback + 1,
        end_idx=len(df) - 2,
        mode="train",
        lookback_window=lookback,
        source_mode="raw",
        ohlcv=["open", "close"],
        ma_windows=[2],
        calendar_features=calendar_features,
        include_can_exit=False,
        min_hold_days=1,
        stop_loss=None,
    )
    obs_raw, _ = env_raw.reset()

    env_return = TestEnv(
        df=df,
        start_idx=lookback + 1,
        end_idx=len(df) - 2,
        mode="train",
        lookback_window=lookback,
        source_mode="return",
        ohlcv=["open", "close"],
        ma_windows=[2],
        calendar_features=calendar_features,
        include_can_exit=False,
        min_hold_days=1,
        stop_loss=None,
    )
    obs_return, _ = env_return.reset()

    base_dim = len(env_raw.ohlcv_fields)
    ma_dim = len(env_raw.ma_windows)
    cal_dim = 2 * len(calendar_features)
    calendar_block_start = lookback * (base_dim + ma_dim)
    calendar_block_end = calendar_block_start + lookback * cal_dim

    assert np.allclose(
        obs_raw[calendar_block_start:calendar_block_end],
        obs_return[calendar_block_start:calendar_block_end],
        atol=1e-6,
    )


def test_calendar_with_helpers_and_ma():
    print("\n" + "=" * 80)
    print("TEST: Calendar + Helpers + MA Combined Shape")
    print("=" * 80)

    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = os.path.join(tmpdir, "data")
        os.makedirs(data_dir, exist_ok=True)

        base_df = _make_date_df(start="2024-01-01", length=120, base_price=100.0)
        helper_df = _make_date_df(start="2024-01-01", length=120, base_price=200.0)

        base_path = os.path.join(data_dir, "gia_lich_su_ACB_1D.parquet")
        helper_path = os.path.join(data_dir, "gia_lich_su_VNINDEX_1D.parquet")
        base_df.to_parquet(base_path, index=False)
        helper_df.to_parquet(helper_path, index=False)

        lookback = 6
        ohlcv_fields = ["open", "close"]
        ma_windows = [3]
        calendar_features = ["dow", "month", "dom"]

        env = TradingEnv(
            data_path=base_path,
            mode="train",
            lookback_window=lookback,
            source_mode="return",
            ohlcv=ohlcv_fields,
            ma_windows=ma_windows,
            calendar_features=calendar_features,
            help_tickers=["VNINDEX"],
            market_data_dir=data_dir,
        )
        obs, _ = env.reset()

        base_dim = len(ohlcv_fields)
        helper_dim = len(ohlcv_fields)
        ma_dim = len(ma_windows)
        cal_dim = 2 * len(calendar_features)
        expected_n_features = lookback * (base_dim + helper_dim + ma_dim + cal_dim)
        expected_obs_dim = expected_n_features + 3  # include_can_exit=True default

        assert env.observation_space.shape[0] == expected_obs_dim, (
            f"Expected obs dim {expected_obs_dim}, got {env.observation_space.shape[0]}"
        )
        assert obs.shape[0] == expected_obs_dim
