"""
H407: Phase Lead Test (Simplified)
Test whether lagged C16 vs price relationship predicts forward.
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
BRANCH_NAME = "phase_lead_simplified"
MODE = "research_branch"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H407 Phase test")
    parser.add_argument("--s1-path", type=str, default=str(ROOT / "data/features/xs_barrier_vol_1d_hose_full.parquet"))
    parser.add_argument("--start-year", type=int, default=2018)
    parser.add_argument("--end-year", type=int, default=2025)
    return parser.parse_args()


def compute_ic(panel, score_col, target_col):
    valid = panel[[score_col, target_col]].dropna()
    if len(valid) < 50:
        return np.nan
    ic, _ = spearmanr(valid[score_col], valid[target_col])
    return ic


def compute_yearly(panel, score_col, target_col):
    panel = panel.copy()
    panel["year"] = pd.to_datetime(panel["time"]).dt.year
    ics = {}
    for year, df in panel.groupby("year"):
        ics[year] = compute_ic(df, score_col, target_col)
    return ics


def main():
    args = parse_args()
    
    print("Loading S1...")
    panel = pd.read_parquet(args.s1_path, columns=["ticker", "time", SCORE_COL, TARGET_COL])
    panel = panel[(panel["time"] >= f"{args.start_year}-01-01") & (panel["time"] <= f"{args.end_year}-12-31")]
    
    print("Loading C16...")
    c16 = pd.read_parquet(ROOT / "data/features/xs_order_pressure_daily.parquet", 
                         columns=["ticker", "time", "order_pressure_h359_active"])
    panel = panel.merge(c16, on=["ticker", "time"], how="left")
    panel = panel[panel[SCORE_COL].notna() & panel[TARGET_COL].notna() & panel["order_pressure_h359_active"].notna()]
    
    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)
    
    panel["price_lag1"] = panel.groupby("ticker")[SCORE_COL].shift(1)
    panel["c16_lag1"] = panel.groupby("ticker")["order_pressure_h359_active"].shift(1)
    panel["price_lag2"] = panel.groupby("ticker")[SCORE_COL].shift(2)
    panel["c16_lag2"] = panel.groupby("ticker")["order_pressure_h359_active"].shift(2)
    
    panel = panel.dropna(subset=["price_lag1", "c16_lag1"])
    
    panel["phase_lag_corr"] = panel["c16_lag1"].fillna(0.5) * panel["price_lag1"].fillna(0.5)
    panel["phase_lag_corr_diff"] = panel["c16_lag1"].fillna(0) - panel["c16_lag2"].fillna(0)
    
    panel["c16_leads_signal"] = panel["c16_lag1"] - panel["c16_lag2"]
    panel["price_leads_signal"] = panel["price_lag1"] - panel["price_lag2"]
    
    print(f"\nPanel rows: {len(panel):,}")
    
    ic_c16 = compute_ic(panel, "order_pressure_h359_active", TARGET_COL)
    ic_phase = compute_ic(panel, "phase_lag_corr", TARGET_COL)
    ic_diff = compute_ic(panel, "phase_lag_corr_diff", TARGET_COL)
    ic_c16_leads = compute_ic(panel, "c16_leads_signal", TARGET_COL)
    ic_price_leads = compute_ic(panel, "price_leads_signal", TARGET_COL)
    
    y_c16 = compute_yearly(panel, "order_pressure_h359_active", TARGET_COL)
    y_phase = compute_yearly(panel, "phase_lag_corr", TARGET_COL)
    
    print(f"\n=== H407 Phase Lead Results ===")
    print(f"C16:          {ic_c16:+.5f}")
    print(f"Phase lag:     {ic_phase:+.5f}")
    print(f"Corr diff:    {ic_diff:+.5f}")
    print(f"C16 leads:     {ic_c16_leads:+.5f}")
    print(f"Price leads:   {ic_price_leads:+.5f}")
    
    print(f"\n--- Positive years ---")
    print(f"C16: {sum(1 for v in y_c16.values() if v > 0)}/{len(y_c16)}")
    print(f"Phase: {sum(1 for v in y_phase.values() if v > 0)}/{len(y_phase)}")
    
    result = {"c16": ic_c16, "phase": ic_phase, "diff": ic_diff}
    
    import json
    with open(ROOT / "artifacts/run_summaries" / f"{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}_{BRANCH_NAME}_{MODE}.json", "w") as f:
        json.dump(result, f)
    
    print(f"\n=== VERDICT ===")
    if abs(ic_phase) > 0.01:
        print("PASSED")
    elif abs(ic_phase) > 0.005:
        print("MIXED")
    else:
        print("FAILED")


if __name__ == "__main__":
    main()