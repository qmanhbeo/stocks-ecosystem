"""
H403: Capital Reynolds Number
Test whether unified flow-regime states (volume * breadth / volatility) predict C16/S1 variation.
Uses walk-forward validation over 2018-2025.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TARGET_COL = "actual"
SCORE_COL = "xs_proba"
BRANCH_NAME = "capital_reynolds_number"
MODE = "research_branch"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H403 Capital Reynolds Number test")
    parser.add_argument("--s1-path", type=str, default=str(ROOT / "data/features/xs_barrier_vol_1d_hose_full.parquet"))
    parser.add_argument("--start-year", type=int, default=2018)
    parser.add_argument("--end-year", type=int, default=2025)
    return parser.parse_args()


def compute_ic(panel: pd.DataFrame, score_col: str, target_col: str) -> float:
    valid = panel[[score_col, target_col]].dropna()
    if len(valid) < 50:
        return np.nan
    ic, _ = spearmanr(valid[score_col], valid[target_col])
    return ic


def compute_yearly_ics(panel: pd.DataFrame, score_col: str, target_col: str) -> dict[int, float]:
    panel = panel.copy()
    panel["year"] = pd.to_datetime(panel["time"]).dt.year
    ics = {}
    for year, year_df in panel.groupby("year"):
        ic = compute_ic(year_df, score_col, target_col)
        ics[year] = ic
    return ics


def main():
    args = parse_args()
    
    print("Loading S1 panel...")
    panel = pd.read_parquet(
        args.s1_path,
        columns=["ticker", "time", SCORE_COL, TARGET_COL],
    )
    panel = panel[panel["time"] >= f"{args.start_year}-01-01"]
    panel = panel[panel["time"] <= f"{args.end_year}-12-31"]
    
    print("Loading C16...")
    c16 = pd.read_parquet(
        ROOT / "data/features/xs_order_pressure_daily.parquet",
        columns=["ticker", "time", "order_pressure_h359_active"],
    )
    panel = panel.merge(c16, on=["ticker", "time"], how="left")
    
    print("Loading order stats...")
    order_stats = pd.read_parquet(
        ROOT / "data/order_stats/cafef/order_stats_daily.parquet",
        columns=["ticker", "date", "buy_order_volume", "sell_order_volume", "buy_order_count", "sell_order_count"],
    )
    order_stats["time"] = pd.to_datetime(order_stats["date"])
    order_stats = order_stats.drop(columns=["date"])
    panel = panel.merge(order_stats, on=["ticker", "time"], how="left")
    
    print("Loading volume z-score...")
    vol_z = pd.read_parquet(
        ROOT / "data/features/xs_volume_zscore_daily.parquet",
        columns=["ticker", "time", "xs_vol_zscore_5d"],
    )
    panel = panel.merge(vol_z, on=["ticker", "time"], how="left")
    
    panel = panel[
        panel[SCORE_COL].notna() & 
        panel[TARGET_COL].notna() &
        panel["order_pressure_h359_active"].notna()
    ].copy()
    
    panel["total_volume"] = (
        panel["buy_order_volume"].fillna(0) + panel["sell_order_volume"].fillna(0)
    )
    panel["total_count"] = (
        panel["buy_order_count"].fillna(0) + panel["sell_order_count"].fillna(0)
    )
    
    panel["velocity"] = panel["xs_vol_zscore_5d"].fillna(0).abs()
    panel["breadth"] = panel["total_count"] / (panel["total_volume"] + 1)
    panel["viscosity"] = np.abs(panel["total_volume"] / (panel["velocity"] + 0.1))
    
    panel["reynolds_number"] = np.where(
        panel["viscosity"] > 0,
        panel["velocity"] * panel["breadth"] * 1000 / (panel["viscosity"] + 1),
        np.nan,
    )
    
    panel["re_low"] = (panel["reynolds_number"] < panel["reynolds_number"].quantile(0.33)).astype(float)
    panel["re_medium"] = ((panel["reynolds_number"] >= panel["reynolds_number"].quantile(0.33)) & 
                        (panel["reynolds_number"] <= panel["reynolds_number"].quantile(0.67))).astype(float)
    panel["re_high"] = (panel["reynolds_number"] > panel["reynolds_number"].quantile(0.67)).astype(float)
    
    panel["c16_high"] = (panel["order_pressure_h359_active"] >= 0.80).astype(float)
    
    print(f"\nPanel rows: {len(panel):,}")
    print(f"Re mean: {panel['reynolds_number'].mean():.3f}")
    print(f"Re std: {panel['reynolds_number'].std():.3f}")
    
    ic_c16 = compute_ic(panel, "order_pressure_h359_active", TARGET_COL)
    ic_re = compute_ic(panel, "reynolds_number", TARGET_COL)
    ic_re_low = compute_ic(panel, "re_low", TARGET_COL)
    ic_re_high = compute_ic(panel, "re_high", TARGET_COL)
    ic_velocity = compute_ic(panel, "velocity", TARGET_COL)
    ic_breadth = compute_ic(panel, "breadth", TARGET_COL)
    
    yearly_c16 = compute_yearly_ics(panel, "order_pressure_h359_active", TARGET_COL)
    yearly_re = compute_yearly_ics(panel, "reynolds_number", TARGET_COL)
    
    print(f"\n=== H403 Capital Reynolds Number Results ===")
    print(f"\n--- Overall IC ---")
    print(f"  C16:                       {ic_c16:+.5f}")
    print(f"  Reynolds number:          {ic_re:+.5f}")
    print(f"  Velocity (vol_z 5d):     {ic_velocity:+.5f}")
    print(f"  Breadth (count/volume):       {ic_breadth:+.5f}")
    
    print(f"\n--- Bucket IC ---")
    print(f"  Re low (<p33):            {ic_re_low:+.5f}")
    print(f"  Re high (>p67):           {ic_re_high:+.5f}")
    
    print(f"\n--- C16 by year ---")
    for yr, ic in sorted(yearly_c16.items()):
        print(f"    {yr}: {ic:+.5f}")
    
    print(f"\n--- Reynolds by year ---")
    for yr, ic in sorted(yearly_re.items()):
        print(f"    {yr}: {ic:+.5f}")
    
    pos_years_c16 = sum(1 for ic in yearly_c16.values() if ic > 0)
    pos_years_re = sum(1 for ic in yearly_re.values() if ic > 0)
    print(f"\n--- Positive years ---")
    print(f"  C16: {pos_years_c16}/{len(yearly_c16)}")
    print(f"  Reynolds: {pos_years_re}/{len(yearly_re)}")
    
    result = {
        "c16_overall_ic": ic_c16,
        "reynolds_overall_ic": ic_re,
        "velocity_overall_ic": ic_velocity,
        "breadth_overall_ic": ic_breadth,
        "re_low_bucket_ic": ic_re_low,
        "re_high_bucket_ic": ic_re_high,
        "c16_yearly_ic": yearly_c16,
        "reynolds_yearly_ic": yearly_re,
    }
    
    artifact_path = (
        ROOT / "artifacts/run_summaries" /
        f"{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}_{BRANCH_NAME}_{MODE}.json"
    )
    
    import json
    with open(artifact_path, "w") as f:
        json.dump(result, f, indent=2)
    
    print(f"\nSaved: {artifact_path}")
    
    ic_lift = ic_re - ic_c16
    print(f"\n=== VERDICT ===")
    print(f"Reynolds vs C16 IC lift: {ic_lift:+.5f}")
    if ic_lift > 0.01 and pos_years_re >= 6:
        print("PASSED: Reynolds adds IC beyond C16")
    elif ic_re > ic_c16:
        print("MIXED: Reynolds marginally positive")
    else:
        print("FAILED: Reynolds does not add signal beyond C16")


if __name__ == "__main__":
    main()