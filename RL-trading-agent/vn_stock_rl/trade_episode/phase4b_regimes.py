"""Causal VNINDEX regimes and calendar-block attribution helpers."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np
import pandas as pd


def build_causal_vnindex_regimes(
    index_bars: pd.DataFrame,
    *,
    lookback_sessions: int = 126,
    rising_threshold: float = 0.10,
    falling_threshold: float = -0.10,
    cutoff: str | pd.Timestamp = "2025-12-31",
) -> pd.DataFrame:
    """Classify trailing index returns using data through the decision close."""

    required = {"time", "close"}
    if required.difference(index_bars.columns):
        raise ValueError("index_bars must contain time and close")
    if lookback_sessions < 1 or rising_threshold <= falling_threshold:
        raise ValueError("Invalid regime lookback or thresholds")
    frame = index_bars.loc[:, ["time", "close"]].copy()
    frame["time"] = pd.to_datetime(frame["time"], errors="raise").dt.normalize()
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame = frame.loc[frame["time"] <= pd.Timestamp(cutoff).normalize()]
    frame = frame.sort_values("time", kind="stable").reset_index(drop=True)
    if frame.empty or frame["time"].duplicated().any():
        raise ValueError("VNINDEX dates must be non-empty and unique")
    if frame["close"].isna().any() or (frame["close"] <= 0).any():
        raise ValueError("VNINDEX close values must be finite and positive")

    trailing_return = frame["close"] / frame["close"].shift(lookback_sessions) - 1.0
    regime = np.full(len(frame), "warmup", dtype=object)
    valid = trailing_return.notna().to_numpy()
    values = trailing_return.to_numpy(dtype=np.float64)
    rising = (values > rising_threshold) | np.isclose(
        values, rising_threshold, rtol=0.0, atol=1e-12
    )
    falling = (values < falling_threshold) | np.isclose(
        values, falling_threshold, rtol=0.0, atol=1e-12
    )
    regime[valid & rising] = "rising"
    regime[valid & falling] = "falling"
    regime[valid & ~rising & ~falling] = "sideways"
    frame["trailing_return_126d"] = trailing_return.to_numpy(dtype=np.float64)
    frame["regime"] = regime
    return frame


def regime_asof(regimes: pd.DataFrame, decision_date) -> str | None:
    """Return the most recent regime label known at or before a decision date."""

    requested = pd.Timestamp(decision_date).normalize()
    dates = pd.DatetimeIndex(regimes["time"])
    index = int(dates.searchsorted(requested, side="right") - 1)
    if index < 0:
        return None
    value = str(regimes.iloc[index]["regime"])
    return None if value == "warmup" else value


def compound_interval_returns(values) -> float:
    returns = np.asarray(values, dtype=np.float64)
    if returns.ndim != 1 or not np.isfinite(returns).all() or (returns <= -1.0).any():
        raise ValueError("interval returns must be finite values greater than -100%")
    return float(np.prod(1.0 + returns, dtype=np.float64) - 1.0)


def summarize_regime_path(
    daily_path: list[dict[str, Any]], regimes: pd.DataFrame
) -> list[dict[str, Any]]:
    """Attribute each close-to-close outcome to its causal decision-date regime."""

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in daily_path:
        label = regime_asof(regimes, row["decision_date"])
        if label is not None:
            grouped[label].append(row)

    results = []
    for label in ("rising", "falling", "sideways"):
        rows = grouped.get(label, [])
        if not rows:
            continue
        interval_returns = np.asarray([row["interval_return"] for row in rows], dtype=np.float64)
        conditional_curve = np.cumprod(1.0 + interval_returns)
        drawdown = conditional_curve / np.maximum.accumulate(conditional_curve) - 1.0
        results.append(
            {
                "regime": label,
                "interval_count": int(len(rows)),
                "conditional_compounded_return": compound_interval_returns(interval_returns),
                "conditional_max_drawdown": float(drawdown.min()),
                "exposure_percentage": float(
                    np.mean([bool(row["exposure"]) for row in rows]) * 100.0
                ),
            }
        )
    return results


def summarize_regime_year_blocks(
    daily_path: list[dict[str, Any]], regimes: pd.DataFrame
) -> list[dict[str, Any]]:
    """Create paired year/regime blocks for cluster-aware comparisons."""

    grouped: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in daily_path:
        regime = regime_asof(regimes, row["decision_date"])
        if regime is None:
            continue
        year = pd.Timestamp(row["execution_date"]).year
        grouped[(year, regime)].append(row)
    results = []
    for (year, regime), rows in sorted(grouped.items()):
        interval_returns = [row["interval_return"] for row in rows]
        results.append(
            {
                "year": year,
                "regime": regime,
                "interval_count": len(rows),
                "conditional_compounded_return": compound_interval_returns(interval_returns),
                "exposure_percentage": float(
                    np.mean([bool(row["exposure"]) for row in rows]) * 100.0
                ),
            }
        )
    return results


def summarize_calendar_year_path(
    daily_path: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Summarize contiguous execution-year blocks without splitting trades."""

    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in daily_path:
        year = pd.Timestamp(row["execution_date"]).year
        grouped[year].append(row)
    results = []
    for year, rows in sorted(grouped.items()):
        interval_returns = [row["interval_return"] for row in rows]
        compound = compound_interval_returns(interval_returns)
        count = len(rows)
        results.append(
            {
                "year": int(year),
                "interval_count": count,
                "calendar_return": compound,
                "annualized_return": (
                    float((1.0 + compound) ** (252.0 / count) - 1.0)
                    if 240 <= count <= 260 and compound > -1.0
                    else None
                ),
                "exposure_percentage": float(
                    np.mean([bool(row["exposure"]) for row in rows]) * 100.0
                ),
            }
        )
    return results
