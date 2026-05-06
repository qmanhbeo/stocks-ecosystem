"""
H412: Volume + C16 Additive Combination Test
Test Volume + C16 additive (NOT cross-product - following H410 additive success).
Based on H410: additive beats cross-product. C16 negative alone but may help additive.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

S1_SCORE_COL = "xs_proba"
S1_TARGET_COL = "actual"
BRANCH_NAME = "volume_c16_additive"
MODE = "research_branch"
MAX_YEAR = 2025


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H412 Volume + C16 additive test")
    parser.add_argument(
        "--s1-path",
        type=str,
        default=str(ROOT / "data/features/xs_barrier_vol_1d_hose_full.parquet"),
    )
    parser.add_argument("--start-year", type=int, default=2018)
    parser.add_argument("--end-year", type=int, default=MAX_YEAR)
    return parser.parse_args()


def compute_ic(panel: pd.DataFrame, score_col: str, target_col: str) -> float:
    valid = panel[[score_col, target_col]].dropna()
    if len(valid) < 50:
        return np.nan
    ic, _ = spearmanr(valid[score_col], valid[target_col])
    return ic


def compute_yearly_ic(panel: pd.DataFrame, score_col: str, target_col: str) -> dict:
    panel = panel.copy()
    panel["year"] = pd.to_datetime(panel["time"]).dt.year
    ics = {}
    for year, df in panel.groupby("year"):
        ic = compute_ic(df, score_col, target_col)
        if not np.isnan(ic):
            ics[year] = ic
    return ics


def main():
    args = parse_args()

    print("Loading S1 target...")
    s1 = pd.read_parquet(
        args.s1_path, columns=["ticker", "time", S1_TARGET_COL]
    )
    s1 = s1[
        (s1["time"] >= f"{args.start_year}-01-01")
        & (s1["time"] <= f"{args.end_year}-12-31")
    ]

    print("Loading Order Stats (Volume + C16)...")
    orders = pd.read_parquet(
        ROOT / "data/features/xs_order_pressure_daily.parquet",
        columns=["ticker", "time", "order_volume_ratio", "order_pressure_h359_active"],
    )

    panel = s1.merge(orders, on=["ticker", "time"], how="inner")
    print(f"Merged panel rows: {len(panel):,}")

    panel = panel[
        panel[S1_TARGET_COL].notna()
        & panel["order_volume_ratio"].notna()
        & panel["order_pressure_h359_active"].notna()
    ].copy()

    # Build ranks for additive combination
    panel["vol_rank"] = panel.groupby("time")["order_volume_ratio"].rank(
        method="average", pct=True
    )
    panel["c16_rank"] = panel.groupby("time")["order_pressure_h359_active"].rank(
        method="average", pct=True
    )

    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)

    print(f"\nPanel rows: {len(panel):,}")

    # Test different additive weights (following H410 pattern: small volume weight helps)
    panel["vol_025_c16_075"] = 0.25 * panel["vol_rank"] + 0.75 * panel["c16_rank"]
    panel["vol_050_c16_050"] = 0.50 * panel["vol_rank"] + 0.50 * panel["c16_rank"]
    panel["vol_075_c16_025"] = 0.75 * panel["vol_rank"] + 0.25 * panel["c16_rank"]
    panel["vol_010_c16_090"] = 0.10 * panel["vol_rank"] + 0.90 * panel["c16_rank"]

    ic_vol = compute_ic(panel, "vol_rank", S1_TARGET_COL)
    ic_c16 = compute_ic(panel, "c16_rank", S1_TARGET_COL)
    ic_025_075 = compute_ic(panel, "vol_025_c16_075", S1_TARGET_COL)
    ic_050_050 = compute_ic(panel, "vol_050_c16_050", S1_TARGET_COL)
    ic_075_025 = compute_ic(panel, "vol_075_c16_025", S1_TARGET_COL)
    ic_010_090 = compute_ic(panel, "vol_010_c16_090", S1_TARGET_COL)

    y_vol = compute_yearly_ic(panel, "vol_rank", S1_TARGET_COL)
    y_c16 = compute_yearly_ic(panel, "c16_rank", S1_TARGET_COL)
    y_025_075 = compute_yearly_ic(panel, "vol_025_c16_075", S1_TARGET_COL)

    pos_vol = sum(1 for v in y_vol.values() if v > 0)
    pos_c16 = sum(1 for v in y_c16.values() if v > 0)
    pos_025_075 = sum(1 for v in y_025_075.values() if v > 0)

    print(f"\n=== H412 Volume + C16 Additive Results ===")
    print(f"Volume alone:       {ic_vol:+.5f} ({pos_vol}/{len(y_vol)} years)")
    print(f"C16 alone:        {ic_c16:+.5f} ({pos_c16}/{len(y_c16)} years)")
    print(f"0.25V+0.75C16:   {ic_025_075:+.5f} ({pos_025_075}/{len(y_025_075)} years)")
    print(f"0.10V+0.90C16:   {ic_010_090:+.5f}")
    print(f"0.50V+0.50C16:   {ic_050_050:+.5f}")
    print(f"0.75V+0.25C16:   {ic_075_025:+.5f}")

    # Find best weight
    weights = {
        "0.25V+0.75C16": ic_025_075,
        "0.10V+0.90C16": ic_010_090,
        "0.50V+0.50C16": ic_050_050,
        "0.75V+0.25C16": ic_075_025,
    }
    best_weight = max(weights, key=weights.get)
    best_ic = weights[best_weight]

    print(f"\n--- Best: {best_weight} = {best_ic:+.5f}")

    result = {
        "ic_vol": float(ic_vol),
        "ic_c16": float(ic_c16),
        "ic_025_075": float(ic_025_075),
        "ic_010_090": float(ic_010_090),
        "ic_050_050": float(ic_050_050),
        "ic_075_025": float(ic_075_025),
        "best_weight": best_weight,
        "best_ic": float(best_ic),
        "pos_vol": pos_vol,
        "pos_c16": pos_c16,
        "pos_025_075": pos_025_075,
    }

    out_path = ROOT / "artifacts/run_summaries" / f"{BRANCH_NAME}_{MODE}.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nSaved: {out_path}")

    print(f"\n=== VERDICT ===")
    if best_ic > ic_vol and pos_025_075 >= 6:
        print("PASSED")
    elif best_ic > ic_vol:
        print("MIXED - additive beats volume alone but C16 alone is weak")
    else:
        print("FAILED - additive doesn't beat volume")

    return best_ic


if __name__ == "__main__":
    main()