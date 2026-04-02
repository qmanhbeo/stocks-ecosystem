"""
Build dense date-level earnings/reporting-season calendar features.

Rationale:
- Reporting season timing is known in advance (quarter-end + typical filing windows).
- Features are date-level and dense (100% trading-day coverage).

Output:
- data/features/xs_earnings_calendar_daily.parquet
"""

from pathlib import Path
from path_utils import data_path
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
GRID_SRC = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
OUT_PATH = data_path("features/xs_earnings_calendar_daily.parquet")


def _quarter_end(ts: pd.Timestamp) -> pd.Timestamp:
    q = ((ts.month - 1) // 3) + 1
    m = 3 * q
    return pd.Timestamp(ts.year, m, 1) + pd.offsets.MonthEnd(0)


def _prev_next_q_end(ts: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    curr_q_end = _quarter_end(ts)
    if ts <= curr_q_end:
        prev_q_end = curr_q_end - pd.offsets.QuarterEnd(1)
        next_q_end = curr_q_end
    else:
        prev_q_end = curr_q_end
        next_q_end = curr_q_end + pd.offsets.QuarterEnd(1)
    return pd.Timestamp(prev_q_end), pd.Timestamp(next_q_end)


def main():
    days = pd.read_parquet(GRID_SRC, columns=["time"]).drop_duplicates().sort_values("time")
    days["time"] = pd.to_datetime(days["time"])
    out = days.copy()

    prev_q = []
    next_q = []
    for t in out["time"]:
        p, n = _prev_next_q_end(pd.Timestamp(t))
        prev_q.append(p)
        next_q.append(n)
    out["prev_q_end"] = pd.to_datetime(prev_q)
    out["next_q_end"] = pd.to_datetime(next_q)

    out["days_since_q_end"] = (out["time"] - out["prev_q_end"]).dt.days.clip(lower=0).astype(float)
    out["days_to_next_q_end"] = (out["next_q_end"] - out["time"]).dt.days.clip(lower=0).astype(float)

    # Typical Vietnam filing season proxy windows after quarter end.
    out["in_report_w15_45"] = out["days_since_q_end"].between(15, 45).astype(float)
    out["in_report_w30_60"] = out["days_since_q_end"].between(30, 60).astype(float)
    out["in_report_w20_50"] = out["days_since_q_end"].between(20, 50).astype(float)
    out["pre_q_end_10d"] = (out["days_to_next_q_end"] <= 10).astype(float)
    out["post_q_end_10d"] = (out["days_since_q_end"] <= 10).astype(float)

    # Continuous phase feature within quarter [0,1].
    quarter_len = out["days_since_q_end"] + out["days_to_next_q_end"]
    phase = out["days_since_q_end"] / (quarter_len.replace(0, np.nan))
    phase = phase.fillna(0.0).clip(0, 1)
    out["quarter_phase"] = phase
    out["quarter_phase_sin"] = np.sin(2 * np.pi * phase)
    out["quarter_phase_cos"] = np.cos(2 * np.pi * phase)

    # Discrete quarter-of-year one-hot (seasonality interaction).
    q = out["time"].dt.quarter
    out["q1_flag"] = (q == 1).astype(float)
    out["q2_flag"] = (q == 2).astype(float)
    out["q3_flag"] = (q == 3).astype(float)
    out["q4_flag"] = (q == 4).astype(float)

    keep = [
        "time",
        "days_since_q_end",
        "days_to_next_q_end",
        "in_report_w15_45",
        "in_report_w30_60",
        "in_report_w20_50",
        "pre_q_end_10d",
        "post_q_end_10d",
        "quarter_phase",
        "quarter_phase_sin",
        "quarter_phase_cos",
        "q1_flag",
        "q2_flag",
        "q3_flag",
        "q4_flag",
    ]
    out = out[keep].sort_values("time").reset_index(drop=True)
    for c in keep[1:]:
        out[c] = out[c].replace([np.inf, -np.inf], np.nan).ffill().fillna(0.0)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT_PATH, index=False)
    print(f"saved {len(out):,} rows -> {OUT_PATH}")
    print(f"date range: {out['time'].min().date()} -> {out['time'].max().date()}")
    print(f"nan count: {int(out.drop(columns=['time']).isna().sum().sum())}")


if __name__ == "__main__":
    main()
