"""
H293 - Breadth Activation Gate.

Question:
- Does lagged sector breadth predict day-to-day IC variation of S1 on the active book?

Smallest honest test:
- compute daily S1 IC on 2015-2025
- compute lagged daily sector breadth from the sector rotation surface
- measure Spearman correlation between breadth_lag1 and daily_IC

Usage:
    conda run -n stocks python analysis/h293_breadth_activation_gate.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr

from path_utils import data_path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.run_summary import write_run_summary
from src.standalone_signal_utils import daily_ic, load_s1_frame

SECTOR_PATH = data_path("features/xs_sector_rotation_daily.parquet")


def _load_breadth_state() -> pd.DataFrame:
    sector = pd.read_parquet(SECTOR_PATH, columns=["time", "ticker", "xs_sector_breadth_5d"]).copy()
    sector["time"] = pd.to_datetime(sector["time"], errors="coerce").dt.normalize()
    sector = sector.dropna(subset=["time", "xs_sector_breadth_5d"])
    daily = (
        sector.groupby("time", sort=True)["xs_sector_breadth_5d"]
        .median()
        .rename("breadth_level")
        .reset_index()
        .sort_values("time")
        .reset_index(drop=True)
    )
    daily["breadth_lag1"] = daily["breadth_level"].shift(1)
    return daily


def _quintile_summary(panel: pd.DataFrame) -> pd.DataFrame:
    work = panel.dropna(subset=["breadth_lag1", "daily_ic"]).copy()
    if work.empty or work["breadth_lag1"].nunique() < 5:
        return pd.DataFrame()
    work["quintile"] = pd.qcut(work["breadth_lag1"].rank(method="first"), 5, labels=False) + 1
    return (
        work.groupby("quintile", sort=True)
        .agg(
            n=("daily_ic", "size"),
            breadth_mean=("breadth_lag1", "mean"),
            ic_mean=("daily_ic", "mean"),
            ic_median=("daily_ic", "median"),
        )
        .reset_index()
    )


def main() -> None:
    s1 = load_s1_frame()
    s1 = s1[(s1["time"].dt.year >= 2015) & (s1["time"].dt.year <= 2025)].copy()
    daily = daily_ic(s1, "xs_proba", "actual").rename(columns={"ic": "daily_ic"})
    breadth = _load_breadth_state()

    panel = daily.merge(breadth, on="time", how="inner").dropna(subset=["daily_ic", "breadth_lag1"])
    if panel.empty:
        raise ValueError("No overlapping daily S1 IC and sector breadth rows")

    rho, p_value = spearmanr(panel["breadth_lag1"], panel["daily_ic"])
    qtab = _quintile_summary(panel)

    verdict = "PASS" if float(rho) >= 0.10 else "MIXED" if float(rho) >= 0.03 else "FAIL"
    q1_ic = float("nan")
    q5_ic = float("nan")
    q1_q5_gap = float("nan")
    if not qtab.empty:
        q1_ic = float(qtab.loc[qtab["quintile"] == 1, "ic_mean"].iloc[0])
        q5_ic = float(qtab.loc[qtab["quintile"] == 5, "ic_mean"].iloc[0])
        q1_q5_gap = q5_ic - q1_ic

    summary = {
        "verdict": verdict,
        "rho": float(rho),
        "p_value": float(p_value),
        "panel_days": int(len(panel)),
        "panel_start": str(panel["time"].min().date()),
        "panel_end": str(panel["time"].max().date()),
        "daily_ic_mean": float(panel["daily_ic"].mean()),
        "daily_ic_pos_days": int((panel["daily_ic"] > 0).sum()),
        "daily_ic_days": int(len(panel)),
        "quintile_table": qtab.to_dict("records"),
        "q1_ic_mean": q1_ic,
        "q5_ic_mean": q5_ic,
        "q5_minus_q1_ic_mean": q1_q5_gap,
    }

    print("H293 BREADTH ACTIVATION GATE")
    print("=" * 72)
    print(f"panel_days: {summary['panel_days']}")
    print(f"date_range: {summary['panel_start']} -> {summary['panel_end']}")
    print(f"spearman_rho: {summary['rho']:+.4f}")
    print(f"p_value: {summary['p_value']:.4g}")
    print(f"daily_ic_mean: {summary['daily_ic_mean']:+.4f}")
    print(f"daily_ic_pos_days: {summary['daily_ic_pos_days']}/{summary['daily_ic_days']}")
    if not qtab.empty:
        print("\nBreadth quintiles:")
        print(qtab.to_string(index=False))
        print(f"\nq5_minus_q1_ic_mean: {summary['q5_minus_q1_ic_mean']:+.4f}")
    print(f"\nVerdict: {verdict}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    details_path = REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h293_breadth_activation_gate_details.json"
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h293_breadth_activation_gate",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"session": 122, "signal": "H293"},
    )
    print(f"summary: {path}")


if __name__ == "__main__":
    main()
