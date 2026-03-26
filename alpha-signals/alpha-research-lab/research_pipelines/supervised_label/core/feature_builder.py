"""Leakage-safe feature generation for supervised signal modeling."""

from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd


def resolve_feature_windows(lookback_window: int) -> List[int]:
    windows = [3, 5, 10, 20, lookback_window]
    return sorted({int(window) for window in windows if int(window) > 1})


def build_feature_frame(df: pd.DataFrame, lookback_window: int) -> pd.DataFrame:
    if df.empty:
        raise ValueError("Cannot build features from an empty dataframe")

    frame = df.copy()
    frame["time"] = pd.to_datetime(frame["time"])
    frame = frame.sort_values("time").reset_index(drop=True)
    close = frame["close"].astype(float)
    open_ = frame["open"].astype(float)
    high = frame["high"].astype(float)
    low = frame["low"].astype(float)
    volume = frame["volume"].astype(float)
    close_safe = close.replace(0, np.nan)
    low_safe = low.replace(0, np.nan)
    open_safe = open_.replace(0, np.nan)
    volume_safe = volume.replace(0, np.nan)
    ret_1 = close.pct_change(1)

    feature_frame = pd.DataFrame(
        {
            "time": frame["time"],
            "date": frame["time"].dt.strftime("%Y-%m-%d"),
            "ret_1": ret_1,
            "log_ret_1": np.log(close_safe).diff(1),
            "close_open_ratio": (close / open_safe) - 1.0,
            "high_low_ratio": (high / low_safe) - 1.0,
            "high_close_ratio": (high / close_safe) - 1.0,
            "low_close_ratio": (low / close_safe) - 1.0,
        }
    )

    for window in resolve_feature_windows(lookback_window):
        feature_frame[f"ret_{window}"] = close.pct_change(window)
        feature_frame[f"log_ret_{window}"] = np.log(close_safe).diff(window)
        feature_frame[f"volatility_{window}"] = ret_1.rolling(window=window, min_periods=window).std()
        feature_frame[f"momentum_{window}"] = (close / close.shift(window)) - 1.0
        feature_frame[f"sma_ratio_{window}"] = (close / close.rolling(window=window, min_periods=window).mean()) - 1.0
        rolling_volume_mean = volume_safe.rolling(window=window, min_periods=window).mean()
        feature_frame[f"volume_ratio_{window}"] = (volume / rolling_volume_mean) - 1.0

    if lookback_window > 1:
        feature_frame["history_ready"] = close.shift(lookback_window - 1).notna().astype(int)
    else:
        feature_frame["history_ready"] = 1

    return feature_frame


def get_feature_columns(feature_frame: pd.DataFrame) -> List[str]:
    excluded = {"time", "date", "history_ready", "ticker", "chunk_id", "label", "confidence", "confidence_weight"}
    return [column for column in feature_frame.columns if column not in excluded]
