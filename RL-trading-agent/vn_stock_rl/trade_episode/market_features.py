from __future__ import annotations

import numpy as np
import pandas as pd

MARKET_FEATURE_NAMES = [
    "market_log_return_1d",
    "market_log_return_5d",
    "market_log_return_20d",
    "market_intraday_log_return",
    "market_overnight_gap_log_return",
    "market_high_low_range_log",
    "market_realized_volatility_20d",
    "market_volume_zscore_20d",
]


def build_causal_market_features(bars: pd.DataFrame) -> pd.DataFrame:
    """Build close-t observable OHLCV features using current and prior bars only."""

    required = {"time", "open", "high", "low", "close", "volume"}
    missing = required.difference(bars.columns)
    if missing:
        raise ValueError(f"bars are missing columns: {sorted(missing)}")
    result = pd.DataFrame(index=bars.index)
    close = pd.to_numeric(bars["close"], errors="coerce").astype(float)
    opening = pd.to_numeric(bars["open"], errors="coerce").astype(float)
    high = pd.to_numeric(bars["high"], errors="coerce").astype(float)
    low = pd.to_numeric(bars["low"], errors="coerce").astype(float)
    volume = pd.to_numeric(bars["volume"], errors="coerce").astype(float)
    if (
        close.isna().any()
        or opening.isna().any()
        or high.isna().any()
        or low.isna().any()
        or (close <= 0).any()
        or (opening <= 0).any()
        or (high <= 0).any()
        or (low <= 0).any()
        or (high < low).any()
    ):
        raise ValueError("OHLC prices must be finite and positive")
    if volume.isna().any() or (volume < 0).any():
        raise ValueError("Volume must be finite and non-negative")

    log_close = np.log(close)
    log_return_1d = log_close.diff()
    result["market_log_return_1d"] = log_return_1d
    result["market_log_return_5d"] = log_close.diff(5)
    result["market_log_return_20d"] = log_close.diff(20)
    result["market_intraday_log_return"] = np.log(close / opening)
    result["market_overnight_gap_log_return"] = np.log(opening / close.shift(1))
    result["market_high_low_range_log"] = np.log(high / low)
    result["market_realized_volatility_20d"] = log_return_1d.rolling(20, min_periods=20).std()

    log_volume = np.log1p(volume)
    prior_volume_mean = log_volume.shift(1).rolling(20, min_periods=20).mean()
    prior_volume_std = log_volume.shift(1).rolling(20, min_periods=20).std()
    prior_volume_std = prior_volume_std.where(prior_volume_std > np.finfo(float).eps, np.nan)
    result["market_volume_zscore_20d"] = (log_volume - prior_volume_mean) / prior_volume_std
    return result.loc[:, MARKET_FEATURE_NAMES]


def market_warmup_mask(features: pd.DataFrame) -> np.ndarray:
    """Return rows with fully available causal rolling features."""

    return np.isfinite(features.to_numpy(dtype=np.float64)).all(axis=1)
