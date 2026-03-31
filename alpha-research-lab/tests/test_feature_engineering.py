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
