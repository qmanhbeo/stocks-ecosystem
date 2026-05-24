"""
Non-annual profit lens utilities.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


HORIZON_ORDER = ["W", "M", "Q", "6M"]
WEEKLY_FREQ = "W-FRI"
QUARTERLY_FREQ = "QE"
MONTHLY_FREQ = "ME"
SIX_MONTH_TRADING_DAYS = 126


@dataclass(frozen=True)
class HorizonStats:
    horizon: str
    mean_return: float
    median_return: float
    p10_return: float
    positive_period_rate: float
    worst_period_return: float
    n_periods: int


def _to_series(curve: pd.DataFrame) -> pd.Series:
    if curve is None or len(curve) == 0:
        return pd.Series(dtype=float)
    if "date" not in curve.columns or "portfolio_value" not in curve.columns:
        return pd.Series(dtype=float)
    s = curve[["date", "portfolio_value"]].copy()
    s["date"] = pd.to_datetime(s["date"], errors="coerce")
    s = s.dropna(subset=["date", "portfolio_value"]).sort_values("date")
    if len(s) == 0:
        return pd.Series(dtype=float)
    return s.set_index("date")["portfolio_value"].astype(float)


def _summarize_period_returns(horizon: str, period_returns: pd.Series) -> HorizonStats:
    if period_returns is None or len(period_returns) == 0:
        return HorizonStats(
            horizon=horizon,
            mean_return=float("nan"),
            median_return=float("nan"),
            p10_return=float("nan"),
            positive_period_rate=float("nan"),
            worst_period_return=float("nan"),
            n_periods=0,
        )
    r = period_returns.dropna()
    if len(r) == 0:
        return HorizonStats(
            horizon=horizon,
            mean_return=float("nan"),
            median_return=float("nan"),
            p10_return=float("nan"),
            positive_period_rate=float("nan"),
            worst_period_return=float("nan"),
            n_periods=0,
        )
    return HorizonStats(
        horizon=horizon,
        mean_return=float(r.mean()),
        median_return=float(r.median()),
        p10_return=float(np.nanpercentile(r.values, 10)),
        positive_period_rate=float((r > 0).mean()),
        worst_period_return=float(r.min()),
        n_periods=int(len(r)),
    )


def compute_horizon_metrics_from_curve(curve: pd.DataFrame) -> list[HorizonStats]:
    """
    Compute W/M/Q/6M return-lens metrics from a daily equity curve.
    """
    pv = _to_series(curve)
    if len(pv) == 0:
        return [_summarize_period_returns(h, pd.Series(dtype=float)) for h in HORIZON_ORDER]

    weekly = pv.resample(WEEKLY_FREQ).last().pct_change().dropna()
    monthly = pv.resample(MONTHLY_FREQ).last().pct_change().dropna()
    quarterly = pv.resample(QUARTERLY_FREQ).last().pct_change().dropna()
    rolling_6m = (pv / pv.shift(SIX_MONTH_TRADING_DAYS) - 1.0).dropna()

    return [
        _summarize_period_returns("W", weekly),
        _summarize_period_returns("M", monthly),
        _summarize_period_returns("Q", quarterly),
        _summarize_period_returns("6M", rolling_6m),
    ]


def to_records(strategy_name: str, stats: list[HorizonStats]) -> list[dict]:
    out: list[dict] = []
    for s in stats:
        out.append(
            {
                "strategy_name": str(strategy_name),
                "horizon": s.horizon,
                "mean_return": s.mean_return,
                "median_return": s.median_return,
                "p10_return": s.p10_return,
                "positive_period_rate": s.positive_period_rate,
                "worst_period_return": s.worst_period_return,
                "n_periods": s.n_periods,
            }
        )
    return out


def horizon_metrics_to_wide(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert long-form horizon metrics into one row per strategy for easy merges.
    """
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=["strategy_name"])
    rows: list[dict] = []
    for strategy_name, g in df.groupby("strategy_name", dropna=False):
        row: dict[str, float | str | int] = {"strategy_name": str(strategy_name)}
        for _, r in g.iterrows():
            h = str(r["horizon"])
            prefix = f"h_{h.lower()}"
            row[f"{prefix}_mean_return"] = float(r["mean_return"]) if pd.notna(r["mean_return"]) else float("nan")
            row[f"{prefix}_positive_rate"] = float(r["positive_period_rate"]) if pd.notna(r["positive_period_rate"]) else float("nan")
            row[f"{prefix}_worst_return"] = float(r["worst_period_return"]) if pd.notna(r["worst_period_return"]) else float("nan")
            row[f"{prefix}_n_periods"] = int(r["n_periods"]) if pd.notna(r["n_periods"]) else 0
        rows.append(row)
    return pd.DataFrame(rows).sort_values("strategy_name").reset_index(drop=True)
