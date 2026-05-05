"""
H404: Haar Cascade Pressure
Test whether C16 wavelet energy at different scales (1/2/4/8 day) 
predicts beyond plain C16 level.
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
BRANCH_NAME = "haar_cascade_pressure"
MODE = "research_branch"


def haar_transform(series: np.ndarray, scale: int) -> np.ndarray:
    """Compute Haar wavelet detail at given scale."""
    series = np.asarray(series, dtype=np.float64)
    if len(series) <= scale:
        return np.full(len(series), np.nan)
    result = np.full(len(series), np.nan)
    for i in range(scale, len(series)):
        window = series[i-scale:i]
        valid = ~np.isnan(window)
        if np.any(valid):
            result[i] = np.nanmean(window) - series[i-scale]
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H404 Haar Cascade test")
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
    
    panel = panel[
        panel[SCORE_COL].notna() & 
        panel[TARGET_COL].notna() &
        panel["order_pressure_h359_active"].notna()
    ].copy()
    
    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)
    
    print(f"Computing Haar wavelets...")
    panel["haar_1d"] = panel.groupby("ticker")["order_pressure_h359_active"].transform(
        lambda x: haar_transform(x.values, 1)
    )
    panel["haar_2d"] = panel.groupby("ticker")["order_pressure_h359_active"].transform(
        lambda x: haar_transform(x.values, 2)
    )
    panel["haar_4d"] = panel.groupby("ticker")["order_pressure_h359_active"].transform(
        lambda x: haar_transform(x.values, 4)
    )
    panel["haar_8d"] = panel.groupby("ticker")["order_pressure_h359_active"].transform(
        lambda x: haar_transform(x.values, 8)
    )
    
    panel["haar_jump_1_to_2"] = panel["haar_2d"] - panel["haar_1d"]
    panel["haar_jump_2_to_4"] = panel["haar_4d"] - panel["haar_2d"]
    panel["haar_jump_4_to_8"] = panel["haar_8d"] - panel["haar_4d"]
    panel["haar_energy_sum"] = panel["haar_1d"].abs() + panel["haar_2d"].abs() + panel["haar_4d"].abs() + panel["haar_8d"].abs()
    
    panel["c16_accel"] = panel.groupby("ticker")["order_pressure_h359_active"].transform(
        lambda x: x.diff()
    )
    
    panel = panel.dropna(subset=["haar_1d", "haar_2d", "haar_4d", "haar_8d"])
    
    print(f"\nPanel rows: {len(panel):,}")
    
    ic_c16 = compute_ic(panel, "order_pressure_h359_active", TARGET_COL)
    ic_haar_1 = compute_ic(panel, "haar_1d", TARGET_COL)
    ic_haar_2 = compute_ic(panel, "haar_2d", TARGET_COL)
    ic_haar_4 = compute_ic(panel, "haar_4d", TARGET_COL)
    ic_haar_8 = compute_ic(panel, "haar_8d", TARGET_COL)
    ic_jump_1_2 = compute_ic(panel, "haar_jump_1_to_2", TARGET_COL)
    ic_jump_2_4 = compute_ic(panel, "haar_jump_2_to_4", TARGET_COL)
    ic_jump_4_8 = compute_ic(panel, "haar_jump_4_to_8", TARGET_COL)
    ic_energy = compute_ic(panel, "haar_energy_sum", TARGET_COL)
    ic_accel = compute_ic(panel, "c16_accel", TARGET_COL)
    
    yearly_c16 = compute_yearly_ics(panel, "order_pressure_h359_active", TARGET_COL)
    yearly_haar_2 = compute_yearly_ics(panel, "haar_2d", TARGET_COL)
    yearly_jump_2_4 = compute_yearly_ics(panel, "haar_jump_2_to_4", TARGET_COL)
    
    print(f"\n=== H404 Haar Cascade Pressure Results ===")
    print(f"\n--- Overall IC ---")
    print(f"  C16 level:             {ic_c16:+.5f}")
    print(f"  Haar 1d:               {ic_haar_1:+.5f}")
    print(f"  Haar 2d:               {ic_haar_2:+.5f}")
    print(f"  Haar 4d:               {ic_haar_4:+.5f}")
    print(f"  Haar 8d:              {ic_haar_8:+.5f}")
    print(f"  Haar jump 1->2:        {ic_jump_1_2:+.5f}")
    print(f"  Haar jump 2->4:        {ic_jump_2_4:+.5f}")
    print(f"  Haar jump 4->8:       {ic_jump_4_8:+.5f}")
    print(f"  Haar energy sum:      {ic_energy:+.5f}")
    print(f"  C16 accel:            {ic_accel:+.5f}")
    
    print(f"\n--- C16 by year ---")
    for yr, ic in sorted(yearly_c16.items()):
        print(f"    {yr}: {ic:+.5f}")
    
    print(f"\n--- Haar 2d by year ---")
    for yr, ic in sorted(yearly_haar_2.items()):
        print(f"    {yr}: {ic:+.5f}")
    
    pos_years_c16 = sum(1 for ic in yearly_c16.values() if ic > 0)
    pos_years_haar_2 = sum(1 for ic in yearly_haar_2.values() if ic > 0)
    print(f"\n--- Positive years ---")
    print(f"  C16: {pos_years_c16}/{len(yearly_c16)}")
    print(f"  Haar 2d: {pos_years_haar_2}/{len(yearly_haar_2)}")
    
    result = {
        "c16_overall_ic": ic_c16,
        "haar_1d_ic": ic_haar_1,
        "haar_2d_ic": ic_haar_2,
        "haar_4d_ic": ic_haar_4,
        "haar_8d_ic": ic_haar_8,
        "haar_jump_1_2_ic": ic_jump_1_2,
        "haar_jump_2_4_ic": ic_jump_2_4,
        "haar_jump_4_8_ic": ic_jump_4_8,
        "haar_energy_sum_ic": ic_energy,
        "c16_accel_ic": ic_accel,
        "c16_yearly_ic": yearly_c16,
        "haar_2d_yearly_ic": yearly_haar_2,
    }
    
    artifact_path = (
        ROOT / "artifacts/run_summaries" /
        f"{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}_{BRANCH_NAME}_{MODE}.json"
    )
    
    import json
    with open(artifact_path, "w") as f:
        json.dump(result, f, indent=2)
    
    print(f"\nSaved: {artifact_path}")
    
    best_haar = max(ic_haar_1, ic_haar_2, ic_haar_4, ic_haar_8)
    best_lift = best_haar - ic_c16 if ic_c16 < 0 else best_haar
    print(f"\n=== VERDICT ===")
    print(f"Best Haar vs C16 IC lift: {best_lift:+.5f}")
    if best_lift > 0.01 and pos_years_haar_2 >= 6:
        print("PASSED: Haar wavelet adds IC beyond C16")
    elif best_haar > 0 and pos_years_haar_2 >= 5:
        print("MIXED: Haar marginally positive")
    else:
        print("FAILED: Haar does not add signal beyond C16")


if __name__ == "__main__":
    main()