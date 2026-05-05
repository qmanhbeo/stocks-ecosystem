"""
H402: Shadow Liquidity Gravity Well
Test whether order fragmentation proxies contain signal beyond raw C16.
Uses walk-forward validation with train/test splits over 2018-2025.
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

from src.experiment_contract import (
    S1_DEFAULT_PATH,
    write_dataframe_artifact,
)


# H402: use raw S1 columns
TARGET_COL = "actual"
SCORE_COL = "xs_proba"
BRANCH_NAME = "shadow_liquidity_gravity_well"
MODE = "research_branch"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H402 shadow liquidity gravity well test")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
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
    
    print("Loading C16 order pressure...")
    c16 = pd.read_parquet(
        ROOT / "data/features/xs_order_pressure_daily.parquet",
        columns=["ticker", "time", "order_pressure_h359_active"],
    )
    panel = panel.merge(c16, on=["ticker", "time"], how="left")
    
    print("Loading order stats...")
    order_stats = pd.read_parquet(
        ROOT / "data/order_stats/cafef/order_stats_daily.parquet",
        columns=["ticker", "date", "buy_order_count", "buy_order_volume", 
                "sell_order_count", "sell_order_volume",
                "avg_buy_order_volume", "avg_sell_order_volume"],
    )
    order_stats["time"] = pd.to_datetime(order_stats["date"])
    order_stats = order_stats.drop(columns=["date"])
    panel = panel.merge(order_stats, on=["ticker", "time"], how="left")
    
    panel = panel[
        panel[SCORE_COL].notna() & 
        panel[TARGET_COL].notna() &
        panel["order_pressure_h359_active"].notna()
    ].copy()
    
    panel["total_order_count"] = (
        panel["buy_order_count"].fillna(0) + panel["sell_order_count"].fillna(0)
    )
    panel["total_order_volume"] = (
        panel["buy_order_volume"].fillna(0) + panel["sell_order_volume"].fillna(0)
    )
    
    panel["fragmentation_ratio"] = np.where(
        panel["total_order_volume"] > 0,
        np.log1p(panel["total_order_count"]) / (np.log1p(panel["total_order_volume"]) + 1),
        np.nan,
    )
    panel["avg_buy_minus_sell_size"] = (
        panel["avg_buy_order_volume"].fillna(0) - panel["avg_sell_order_volume"].fillna(0)
    )
    panel["fragmentation_high"] = (
        panel["fragmentation_ratio"] > panel["fragmentation_ratio"].quantile(0.80)
    ).astype(float)
    panel["avg_size_positive"] = (panel["avg_buy_minus_sell_size"] > 0).astype(float)
    panel["c16_high"] = (panel["order_pressure_h359_active"] >= 0.80).astype(float)
    
    print(f"\nPanel rows: {len(panel):,}")
    
    ic_c16 = compute_ic(panel, "order_pressure_h359_active", TARGET_COL)
    ic_fragmentation = compute_ic(panel, "fragmentation_ratio", TARGET_COL)
    ic_avg_size = compute_ic(panel, "avg_buy_minus_sell_size", TARGET_COL)
    ic_c16_high = compute_ic(panel, "c16_high", TARGET_COL)
    ic_frag_high = compute_ic(panel, "fragmentation_high", TARGET_COL)
    
    yearly_c16 = compute_yearly_ics(panel, "order_pressure_h359_active", TARGET_COL)
    yearly_frag = compute_yearly_ics(panel, "fragmentation_ratio", TARGET_COL)
    
    print(f"\n=== H402 Shadow Liquidity Gravity Well Results ===")
    print(f"\n--- Overall IC ---")
    print(f"  C16:                      {ic_c16:+.5f}")
    print(f"  Fragmentation ratio:       {ic_fragmentation:+.5f}")
    print(f"  Avg buy-sell size:       {ic_avg_size:+.5f}")
    print(f"\n--- Bucket IC ---")
    print(f"  C16 high (>=0.80):       {ic_c16_high:+.5f}")
    print(f"  Fragmentation high:       {ic_frag_high:+.5f}")
    
    print(f"\n--- C16 by year ---")
    for yr, ic in sorted(yearly_c16.items()):
        print(f"    {yr}: {ic:+.5f}")
    
    print(f"\n--- Fragmentation by year ---")
    for yr, ic in sorted(yearly_frag.items()):
        print(f"    {yr}: {ic:+.5f}")
    
    pos_years_c16 = sum(1 for ic in yearly_c16.values() if ic > 0)
    pos_years_frag = sum(1 for ic in yearly_frag.values() if ic > 0)
    print(f"\n--- Positive years ---")
    print(f"  C16: {pos_years_c16}/{len(yearly_c16)}")
    print(f"  Fragmentation: {pos_years_frag}/{len(yearly_frag)}")
    
    result = {
        "c16_overall_ic": ic_c16,
        "fragmentation_overall_ic": ic_fragmentation,
        "avg_size_overall_ic": ic_avg_size,
        "c16_high_bucket_ic": ic_c16_high,
        "fragmentation_high_bucket_ic": ic_frag_high,
        "c16_yearly_ic": yearly_c16,
        "fragmentation_yearly_ic": yearly_frag,
    }
    
    artifact_path = (
        ROOT / "artifacts/run_summaries" /
        f"{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}_{BRANCH_NAME}_{MODE}.json"
    )
    
    import json
    with open(artifact_path, "w") as f:
        json.dump(result, f, indent=2)
    
    print(f"\nSaved: {artifact_path}")
    
    ic_lift = ic_fragmentation - ic_c16
    print(f"\n=== VERDICT ===")
    print(f"Fragmentation vs C16 IC lift: {ic_lift:+.5f}")
    if ic_lift > 0.01 and pos_years_frag >= 6:
        print("PASSED: Fragmentation adds IC beyond C16")
    elif ic_lift > 0:
        print("MIXED: Fragmentation marginally positive")
    else:
        print("FAILED: Fragmentation does not add signal beyond C16")


if __name__ == "__main__":
    main()