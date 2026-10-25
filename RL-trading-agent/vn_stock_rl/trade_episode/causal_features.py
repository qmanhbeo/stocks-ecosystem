"""Ticker-local, close-time features with strictly lagged volatility scaling."""

from __future__ import annotations

import numpy as np
import pandas as pd

from vn_stock_rl.trade_episode.market_features import build_causal_market_features

TRAILING_VOLATILITY_WINDOW = 60
DAILY_VOLATILITY_FLOOR = 0.005
CAUSAL_MARKET_FEATURE_NAMES = [
    "market_log_return_1d_scaled",
    "market_log_return_5d_scaled",
    "market_log_return_20d_scaled",
    "market_intraday_log_return_scaled",
    "market_overnight_gap_log_return_scaled",
    "market_high_low_range_log_scaled",
    "market_log_realized_volatility_20d",
    "market_log_lagged_volatility_60d",
    "market_volume_zscore_20d",
]


def build_causal_normalized_market_features(
    bars: pd.DataFrame,
    *,
    volatility_window: int = TRAILING_VOLATILITY_WINDOW,
    volatility_floor: float = DAILY_VOLATILITY_FLOOR,
) -> tuple[pd.DataFrame, pd.Series]:
    """Normalize each row using that ticker's volatility through the prior close.

    Raw close-time returns are observable at decision time ``t``. Their scale is
    the rolling daily-return standard deviation through ``t-1``. The returned
    volatility series is also the entry-time scale used for unrealized returns.
    No fit step or full-series statistic is used.
    """

    if volatility_window < 2 or not np.isfinite(volatility_floor) or volatility_floor <= 0:
        raise ValueError("volatility_window and volatility_floor must be positive")
    raw = build_causal_market_features(bars)
    close = pd.to_numeric(bars["close"], errors="raise").astype(float)
    daily_log_return = np.log(close).diff()
    lagged_volatility = (
        daily_log_return.rolling(volatility_window, min_periods=volatility_window).std().shift(1)
    )
    volatility_scale = lagged_volatility.clip(lower=volatility_floor)

    result = pd.DataFrame(index=bars.index)
    result["market_log_return_1d_scaled"] = raw["market_log_return_1d"] / volatility_scale
    result["market_log_return_5d_scaled"] = raw["market_log_return_5d"] / (
        volatility_scale * np.sqrt(5.0)
    )
    result["market_log_return_20d_scaled"] = raw["market_log_return_20d"] / (
        volatility_scale * np.sqrt(20.0)
    )
    result["market_intraday_log_return_scaled"] = (
        raw["market_intraday_log_return"] / volatility_scale
    )
    result["market_overnight_gap_log_return_scaled"] = (
        raw["market_overnight_gap_log_return"] / volatility_scale
    )
    result["market_high_low_range_log_scaled"] = raw["market_high_low_range_log"] / volatility_scale
    result["market_log_realized_volatility_20d"] = np.log(
        raw["market_realized_volatility_20d"].clip(lower=volatility_floor)
    )
    result["market_log_lagged_volatility_60d"] = np.log(volatility_scale)
    result["market_volume_zscore_20d"] = raw["market_volume_zscore_20d"]
    result = result.loc[:, CAUSAL_MARKET_FEATURE_NAMES]
    if np.isinf(result.to_numpy(dtype=np.float64)).any():
        raise ValueError("Causal market features contain infinite values")
    return result, volatility_scale.rename("lagged_daily_volatility")


def causal_feature_warmup_mask(features: pd.DataFrame, volatility_scale: pd.Series) -> np.ndarray:
    """Keep only dates with every rolling input available and finite."""

    values = features.to_numpy(dtype=np.float64)
    scale = volatility_scale.to_numpy(dtype=np.float64)
    return np.isfinite(values).all(axis=1) & np.isfinite(scale) & (scale > 0)
