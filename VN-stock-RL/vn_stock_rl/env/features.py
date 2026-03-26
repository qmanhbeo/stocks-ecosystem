"""Shared environment constants."""

OHLCV_FIELDS = ("open", "high", "low", "close", "volume")
CALENDAR_FEATURES = ("dow", "month", "dom")
ENGINEERED_FEATURE_FAMILIES = (
    "volatility",
    "trend",
    "momentum",
    "volume_context",
    "drawdown",
    "relative_strength",
)
REWARD_BENCHMARKS = ("self_buy_hold",)

__all__ = [
    "OHLCV_FIELDS",
    "CALENDAR_FEATURES",
    "ENGINEERED_FEATURE_FAMILIES",
    "REWARD_BENCHMARKS",
]
