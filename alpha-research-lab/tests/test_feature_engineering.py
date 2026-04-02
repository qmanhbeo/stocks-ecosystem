from __future__ import annotations

import numpy as np
import pandas as pd

from src import feature_engineering


def _flat_ohlcv_df(periods: int = 30) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": pd.date_range("2020-01-01", periods=periods, freq="D"),
            "open": 10.0,
            "high": 10.0,
            "low": 10.0,
            "close": 10.0,
            "volume": 0.0,
        }
    )


def test_bollinger_pct_uses_nan_when_band_collapses() -> None:
    df = feature_engineering._add_bb(_flat_ohlcv_df(), {"bb_period": 20, "bb_std": 2})

    bb_pct = df["bb_pct"].iloc[19:]
    assert not np.isinf(bb_pct.to_numpy(dtype=float)).any()
    assert bb_pct.isna().all()


def test_volume_ratio_uses_nan_when_rolling_volume_is_zero() -> None:
    df = feature_engineering._add_volume_signals(_flat_ohlcv_df(), {"vol_ma_period": 20})

    vol_ratio = df["vol_ratio"].iloc[19:]
    assert not np.isinf(vol_ratio.to_numpy(dtype=float)).any()
    assert vol_ratio.isna().all()


def test_future_dir_target_keeps_unknown_future_rows_as_nan() -> None:
    frame = pd.DataFrame(
        {
            "time": pd.date_range("2020-01-01", periods=3, freq="D"),
            "close": [10.0, 11.0, 9.0],
        }
    )

    targeted = feature_engineering._make_target(frame, "future_dir_1d", {})

    assert targeted["future_dir_1d"].tolist()[:2] == [1.0, 0.0]
    assert np.isnan(float(targeted["future_return_1d"].iloc[-1]))
    assert np.isnan(float(targeted["future_dir_1d"].iloc[-1]))


def test_cross_sectional_feature_columns_include_market_breadth() -> None:
    frame = pd.DataFrame(
        {
            "xs_rank_1d": [0.2],
            "xs_breadth_1d": [0.3],
            "xs_breadth_5d": [0.4],
            "xs_breadth_20d": [0.5],
        }
    )

    cols = feature_engineering.get_feature_columns(
        frame,
        {"features": {"use_cross_sectional": True, "xs_lag_days": [1, 5, 20]}},
    )

    assert "xs_rank_1d" in cols
    assert "xs_breadth_1d" in cols
    assert "xs_breadth_5d" in cols
    assert "xs_breadth_20d" in cols
