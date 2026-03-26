"""
Tests for engineered feature pack configuration and values.
"""

import os
import tempfile
import numpy as np
import pandas as pd

from vn_stock_rl.env import TradingEnv
from test_utils import TestEnv


def _make_df(length: int, close_start: float = 100.0, close_step: float = 1.0) -> pd.DataFrame:
    close = close_start + (np.arange(length, dtype=float) * close_step)
    return pd.DataFrame(
        {
            "time": np.arange(length, dtype=int),
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": np.linspace(1000.0, 1000.0 + length - 1, length),
        }
    )


def _expected_engineered_matrix(
    df: pd.DataFrame,
    feature_names,
    medium_window: int,
    long_window: int,
    market_close: np.ndarray | None = None,
) -> np.ndarray:
    close = df["close"].to_numpy(dtype=np.float64)
    volume = df["volume"].to_numpy(dtype=np.float64)
    n = len(df)

    close_ret = np.zeros(n, dtype=np.float64)
    if n > 1:
        prev = close[:-1].copy()
        prev[prev == 0] = 1.0
        close_ret[1:] = (close[1:] / prev) - 1.0

    ma_m = pd.Series(close).rolling(window=medium_window, min_periods=1).mean().to_numpy(dtype=np.float64)
    ma_l = pd.Series(close).rolling(window=long_window, min_periods=1).mean().to_numpy(dtype=np.float64)
    ma_m_safe = ma_m.copy()
    ma_l_safe = ma_l.copy()
    ma_m_safe[ma_m_safe == 0] = 1.0
    ma_l_safe[ma_l_safe == 0] = 1.0

    mom_m = np.zeros(n, dtype=np.float64)
    mom_l = np.zeros(n, dtype=np.float64)
    if n > medium_window:
        prev = close[:-medium_window].copy()
        prev[prev == 0] = 1.0
        mom_m[medium_window:] = (close[medium_window:] / prev) - 1.0
    if n > long_window:
        prev = close[:-long_window].copy()
        prev[prev == 0] = 1.0
        mom_l[long_window:] = (close[long_window:] / prev) - 1.0

    vol_ma_m = pd.Series(volume).rolling(window=medium_window, min_periods=1).mean().to_numpy(dtype=np.float64)
    vol_ma_m[vol_ma_m == 0] = 1.0

    rolling_max = pd.Series(close).rolling(window=long_window, min_periods=1).max().to_numpy(dtype=np.float64)
    rolling_max[rolling_max == 0] = 1.0

    feature_map = {
        "vol_medium": pd.Series(close_ret).rolling(window=medium_window, min_periods=1).std().fillna(0.0).to_numpy(dtype=np.float64),
        "vol_long": pd.Series(close_ret).rolling(window=long_window, min_periods=1).std().fillna(0.0).to_numpy(dtype=np.float64),
        "dist_ma_medium": (close / ma_m_safe) - 1.0,
        "dist_ma_long": (close / ma_l_safe) - 1.0,
        "slope_ma_medium": np.diff(ma_m, prepend=ma_m[0]),
        "slope_ma_long": np.diff(ma_l, prepend=ma_l[0]),
        "mom_medium": mom_m,
        "mom_long": mom_l,
        "vol_ratio_medium": volume / vol_ma_m,
        "dd_long": (close / rolling_max) - 1.0,
    }

    if market_close is not None:
        market_close = market_close.astype(np.float64, copy=False)
        market_mom_m = np.zeros(n, dtype=np.float64)
        market_mom_l = np.zeros(n, dtype=np.float64)
        if n > medium_window:
            prev = market_close[:-medium_window].copy()
            prev[prev == 0] = 1.0
            market_mom_m[medium_window:] = (market_close[medium_window:] / prev) - 1.0
        if n > long_window:
            prev = market_close[:-long_window].copy()
            prev[prev == 0] = 1.0
            market_mom_l[long_window:] = (market_close[long_window:] / prev) - 1.0
        feature_map["rs_medium"] = mom_m - market_mom_m
        feature_map["rs_long"] = mom_l - market_mom_l

    cols = [feature_map[name] for name in feature_names]
    return np.column_stack(cols).astype(np.float64, copy=False)


def test_engineered_feature_shape_and_order():
    print("\n" + "=" * 80)
    print("TEST: Engineered Features Shape and Order")
    print("=" * 80)

    df = _make_df(length=80)
    lookback = 6
    env = TestEnv(
        df=df,
        start_idx=lookback + 5,
        end_idx=len(df) - 2,
        mode="train",
        lookback_window=lookback,
        source_mode="raw",
        ohlcv=["open"],
        ma_windows=[],
        returns_windows=[],
        engineered_features=["volatility", "trend", "momentum", "volume_context", "drawdown"],
        window_policy="explicit",
        feature_windows=[2, 3, 4, 6, 8],
        include_can_exit=False,
        min_hold_days=1,
        stop_loss=None,
    )
    obs, _ = env.reset()

    engineered_dim = len(env.engineered_feature_names)
    expected_n_features = lookback * (1 + engineered_dim)
    expected_obs_dim = expected_n_features + 2
    assert obs.shape[0] == expected_obs_dim

    block_start = lookback * 1
    block_end = block_start + lookback * engineered_dim
    engineered_block = obs[block_start:block_end]
    assert engineered_block.shape[0] == lookback * engineered_dim
    assert not np.isnan(engineered_block).any()


def test_engineered_feature_known_values():
    print("\n" + "=" * 80)
    print("TEST: Engineered Features Known Values")
    print("=" * 80)

    df = _make_df(length=90, close_start=100.0, close_step=1.5)
    lookback = 7
    env = TestEnv(
        df=df,
        start_idx=lookback + 10,
        end_idx=len(df) - 2,
        mode="train",
        lookback_window=lookback,
        source_mode="raw",
        ohlcv=["open"],
        ma_windows=[],
        returns_windows=[],
        engineered_features=["volatility", "trend", "momentum", "volume_context", "drawdown"],
        window_policy="explicit",
        feature_windows=[2, 4, 6, 8, 10],
        include_can_exit=False,
        min_hold_days=1,
        stop_loss=None,
    )
    obs, _ = env.reset()

    end_idx = env.current_step
    start_idx = end_idx - lookback + 1
    expected = _expected_engineered_matrix(
        df,
        env.engineered_feature_names,
        env.engineered_medium_window,
        env.engineered_long_window,
    )[start_idx:end_idx + 1].reshape(-1).astype(np.float32)

    block_start = lookback * 1
    block_end = block_start + expected.size
    actual = obs[block_start:block_end]
    assert np.allclose(actual, expected, atol=1e-6), "Engineered feature values do not match expected formulas"


def test_engineered_feature_mode_invariance():
    print("\n" + "=" * 80)
    print("TEST: Engineered Features Mode Invariance")
    print("=" * 80)

    df = _make_df(length=85)
    lookback = 6
    kwargs = dict(
        df=df,
        start_idx=lookback + 9,
        end_idx=len(df) - 2,
        mode="train",
        lookback_window=lookback,
        ohlcv=["open", "close"],
        ma_windows=[3],
        returns_windows=[5],
        engineered_features=["volatility", "trend", "momentum", "volume_context", "drawdown"],
        window_policy="explicit",
        feature_windows=[2, 4, 6, 8, 10],
        include_can_exit=False,
        min_hold_days=1,
        stop_loss=None,
    )
    env_raw = TestEnv(source_mode="raw", **kwargs)
    obs_raw, _ = env_raw.reset()
    env_ret = TestEnv(source_mode="return", **kwargs)
    obs_ret, _ = env_ret.reset()

    base_dim = 2
    ma_dim = 1
    ret_dim = 1
    engineered_dim = len(env_raw.engineered_feature_names)
    start = lookback * (base_dim + ma_dim + ret_dim)
    end = start + lookback * engineered_dim
    assert np.allclose(obs_raw[start:end], obs_ret[start:end], atol=1e-6)


def test_engineered_relative_strength_proxy_fallback():
    print("\n" + "=" * 80)
    print("TEST: Engineered RS Proxy Fallback (VN30)")
    print("=" * 80)

    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = os.path.join(tmpdir, "data")
        os.makedirs(data_dir, exist_ok=True)

        base_df = _make_df(length=120, close_start=100.0, close_step=1.0)
        vn30_df = _make_df(length=120, close_start=200.0, close_step=0.5)

        base_path = os.path.join(data_dir, "gia_lich_su_ACB_1D.parquet")
        vn30_path = os.path.join(data_dir, "gia_lich_su_VN30_1D.parquet")
        base_df.to_parquet(base_path, index=False)
        vn30_df.to_parquet(vn30_path, index=False)

        lookback = 8
        env = TradingEnv(
            data_path=base_path,
            mode="train",
            lookback_window=lookback,
            source_mode="return",
            ohlcv=["open"],
            ma_windows=[],
            returns_windows=[],
            engineered_features=["relative_strength"],
            window_policy="explicit",
            feature_windows=[2, 4, 6, 8, 10],
            rs_market_proxies=["VNINDEX", "VN30"],
            market_data_dir=data_dir,
        )
        obs, _ = env.reset()

        assert env.engineered_feature_names[0] == "rs_medium"
        end_idx = env.current_step
        start_idx = end_idx - lookback + 1
        expected_matrix = _expected_engineered_matrix(
            base_df,
            env.engineered_feature_names,
            env.engineered_medium_window,
            env.engineered_long_window,
            market_close=vn30_df["close"].to_numpy(dtype=np.float64),
        )
        expected = expected_matrix[start_idx:end_idx + 1].reshape(-1).astype(np.float32)

        block_start = lookback * 1
        block_end = block_start + expected.size
        actual = obs[block_start:block_end]
        assert np.allclose(actual, expected, atol=1e-6), "RS features should use VN30 when VNINDEX is unavailable"


def test_engineered_leakage_safety():
    print("\n" + "=" * 80)
    print("TEST: Engineered Features Leakage Safety")
    print("=" * 80)

    df = _make_df(length=120, close_start=100.0, close_step=1.2)
    lookback = 8
    env = TestEnv(
        df=df,
        start_idx=lookback + 10,
        end_idx=len(df) - 2,
        mode="train",
        lookback_window=lookback,
        source_mode="return",
        ohlcv=["open", "close"],
        ma_windows=[],
        returns_windows=[],
        engineered_features=["volatility", "trend", "momentum", "volume_context", "drawdown"],
        window_policy="explicit",
        feature_windows=[3, 5, 8, 13, 21],
        include_can_exit=False,
        min_hold_days=1,
        stop_loss=None,
    )

    expected_a = env._compute_pretrim_engineered_frame(df)[env.engineered_feature_names].to_numpy(dtype=np.float64)
    mutate_from = 75
    df_mut = df.copy()
    df_mut.loc[mutate_from:, "close"] = df_mut.loc[mutate_from:, "close"] * 3.0
    df_mut.loc[mutate_from:, "volume"] = df_mut.loc[mutate_from:, "volume"] * 5.0
    expected_b = env._compute_pretrim_engineered_frame(df_mut)[env.engineered_feature_names].to_numpy(dtype=np.float64)

    # Future changes (>= mutate_from) must not alter features at <= mutate_from-1.
    assert np.allclose(expected_a[: mutate_from - 1], expected_b[: mutate_from - 1], atol=1e-12)
    # Sanity: changed future should alter later rows.
    assert not np.allclose(expected_a[mutate_from + 1 :], expected_b[mutate_from + 1 :], atol=1e-12)


def test_engineered_backward_compat_disabled_by_default():
    print("\n" + "=" * 80)
    print("TEST: Engineered Features Backward Compatibility (Disabled By Default)")
    print("=" * 80)

    df = _make_df(length=70)
    lookback = 6
    env = TestEnv(
        df=df,
        start_idx=lookback + 5,
        end_idx=len(df) - 2,
        mode="train",
        lookback_window=lookback,
        source_mode="return",
        ohlcv=["open", "high", "low", "close", "volume"],
        ma_windows=[],
        returns_windows=[],
        include_can_exit=False,
        min_hold_days=1,
        stop_loss=None,
    )
    obs, _ = env.reset()
    assert env.engineered_feature_dim == 0
    assert env.input_features["engineered_features"]["enabled"] == []
    assert obs.shape[0] == (lookback * 5) + 2
