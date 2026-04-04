from __future__ import annotations

import pandas as pd


UPWARD_W_SIGNAL_FORMULAS: dict[str, str] = {
    "xs_upward_w_base_12d": "rank(drawdown_12d * rebound_12d * higher_low_margin_12d * breakout_margin_12d)",
    "xs_upward_w_moderate_12d": "rank(band(drawdown,0.15,0.20) * band(higher_low,0.02,0.04) * band(breakout,0.01,0.03) * band(distance_below_pre_peak,0.04,0.10))",
    "xs_upward_w_reclaim_12d": "rank(band(drawdown,0.12,0.18) * band(higher_low,0.02,0.05) * band(reclaim_ratio,0.85,0.35) * band(breakout,0.005,0.025))",
    "xs_upward_w_reclaim_15d": "rank(band(drawdown,0.12,0.18) * band(higher_low,0.02,0.05) * band(reclaim_ratio,0.85,0.35) * band(breakout,0.005,0.025)) on 15d shape window",
}


def _rank_frame(frame: pd.DataFrame, *, ascending: bool = True) -> pd.DataFrame:
    return frame.rank(axis=1, method="average", ascending=ascending, pct=True)


def triangular_band_score(frame: pd.DataFrame, *, center: float, width: float) -> pd.DataFrame:
    if width <= 0.0:
        raise ValueError("width must be positive")
    numeric = frame.astype(float)
    return (1.0 - ((numeric - float(center)).abs() / float(width))).clip(lower=0.0)


def _upward_w_components(
    close: pd.DataFrame,
    *,
    pre_window: int,
    first_bottom_window: int,
    rebound_window: int,
    second_bottom_window: int,
) -> dict[str, pd.DataFrame]:
    total_pattern_window = int(first_bottom_window) + int(rebound_window) + int(second_bottom_window)
    pre_peak = close.shift(total_pattern_window).rolling(
        int(pre_window),
        min_periods=max(3, int(pre_window) // 2),
    ).max()
    first_low = close.shift(int(rebound_window) + int(second_bottom_window)).rolling(
        int(first_bottom_window),
        min_periods=max(2, int(first_bottom_window) // 2),
    ).min()
    mid_high = close.shift(int(second_bottom_window)).rolling(
        int(rebound_window),
        min_periods=max(2, int(rebound_window) // 2),
    ).max()
    second_low_window = max(2, int(second_bottom_window) - 1)
    second_low = close.shift(1).rolling(
        second_low_window,
        min_periods=max(2, second_low_window // 2),
    ).min()
    drawdown = (pre_peak / first_low - 1.0).clip(lower=0.0)
    rebound = (mid_high / first_low - 1.0).clip(lower=0.0)
    higher_low_margin = (second_low / first_low - 1.0).clip(lower=0.0)
    breakout_margin = (close / mid_high - 1.0).clip(lower=0.0)
    reclaim_ratio = ((close - second_low) / (mid_high - first_low).replace(0.0, float("nan"))).clip(lower=0.0, upper=2.0)
    distance_below_pre_peak = (pre_peak / close - 1.0).clip(lower=0.0)
    return {
        "drawdown": drawdown,
        "rebound": rebound,
        "higher_low_margin": higher_low_margin,
        "breakout_margin": breakout_margin,
        "reclaim_ratio": reclaim_ratio,
        "distance_below_pre_peak": distance_below_pre_peak,
    }


def _compose_base_signal(components: dict[str, pd.DataFrame]) -> pd.DataFrame:
    score = (
        _rank_frame(components["drawdown"])
        * _rank_frame(components["rebound"])
        * _rank_frame(components["higher_low_margin"])
        * _rank_frame(components["breakout_margin"])
    )
    return _rank_frame(score)


def _compose_moderate_signal(components: dict[str, pd.DataFrame]) -> pd.DataFrame:
    score = (
        _rank_frame(triangular_band_score(components["drawdown"], center=0.15, width=0.20))
        * _rank_frame(triangular_band_score(components["higher_low_margin"], center=0.02, width=0.04))
        * _rank_frame(triangular_band_score(components["breakout_margin"], center=0.01, width=0.03))
        * _rank_frame(triangular_band_score(components["distance_below_pre_peak"], center=0.04, width=0.10))
    )
    return _rank_frame(score)


def _compose_reclaim_signal(components: dict[str, pd.DataFrame]) -> pd.DataFrame:
    score = (
        _rank_frame(triangular_band_score(components["drawdown"], center=0.12, width=0.18))
        * _rank_frame(triangular_band_score(components["higher_low_margin"], center=0.02, width=0.05))
        * _rank_frame(triangular_band_score(components["reclaim_ratio"], center=0.85, width=0.35))
        * _rank_frame(triangular_band_score(components["breakout_margin"], center=0.005, width=0.025))
    )
    return _rank_frame(score)


def build_upward_w_shape_features(close: pd.DataFrame) -> dict[str, pd.DataFrame]:
    close = close.sort_index().astype(float)

    components_12d = _upward_w_components(
        close,
        pre_window=12,
        first_bottom_window=4,
        rebound_window=4,
        second_bottom_window=4,
    )
    components_15d = _upward_w_components(
        close,
        pre_window=10,
        first_bottom_window=5,
        rebound_window=5,
        second_bottom_window=5,
    )

    return {
        "xs_upward_w_base_12d": _compose_base_signal(components_12d),
        "xs_upward_w_moderate_12d": _compose_moderate_signal(components_12d),
        "xs_upward_w_reclaim_12d": _compose_reclaim_signal(components_12d),
        "xs_upward_w_reclaim_15d": _compose_reclaim_signal(components_15d),
    }
