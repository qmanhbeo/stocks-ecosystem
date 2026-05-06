"""
H410: Volume + S1 Additive Combination Test
Test whether Volume + S1 additive combination beats standalone S1.
Based on H409: Volume alone is +0.077, cross with C16 hurt, try additive with S1.
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
BRANCH_NAME = "volume_s1_additive"
MODE = "research_branch"
MAX_YEAR = 2025


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H410 Volume + S1 additive test")
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

    print("Loading S1...")
    s1 = pd.read_parquet(
        args.s1_path, columns=["ticker", "time", S1_SCORE_COL, S1_TARGET_COL]
    )
    s1 = s1[
        (s1["time"] >= f"{args.start_year}-01-01")
        & (s1["time"] <= f"{args.end_year}-12-31")
    ]

    print("Loading Order Stats (Volume)...")
    orders = pd.read_parquet(
        ROOT / "data/features/xs_order_pressure_daily.parquet",
        columns=["ticker", "time", "order_volume_ratio"],
    )

    panel = s1.merge(orders, on=["ticker", "time"], how="inner")
    print(f"Merged panel rows: {len(panel):,}")

    panel = panel[
        panel[S1_SCORE_COL].notna()
        & panel[S1_TARGET_COL].notna()
        & panel["order_volume_ratio"].notna()
    ].copy()

    panel["vol_zscore"] = panel.groupby("time")["order_volume_ratio"].rank(
        method="average", pct=True
    )

    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)

    print(f"\nPanel rows: {len(panel):,}")

    # Test different combinations
    panel["vol_plus_s1"] = panel["vol_zscore"] + panel[S1_SCORE_COL]
    panel["vol_weight_025_s1"] = 0.25 * panel["vol_zscore"] + 0.75 * panel[S1_SCORE_COL]
    panel["vol_weight_050_s1"] = 0.50 * panel["vol_zscore"] + 0.50 * panel[S1_SCORE_COL]
    panel["vol_weight_075_s1"] = 0.75 * panel["vol_zscore"] + 0.25 * panel[S1_SCORE_COL]

    ic_s1 = compute_ic(panel, S1_SCORE_COL, S1_TARGET_COL)
    ic_vol = compute_ic(panel, "vol_zscore", S1_TARGET_COL)
    ic_add = compute_ic(panel, "vol_plus_s1", S1_TARGET_COL)
    ic_w025 = compute_ic(panel, "vol_weight_025_s1", S1_TARGET_COL)
    ic_w050 = compute_ic(panel, "vol_weight_050_s1", S1_TARGET_COL)
    ic_w075 = compute_ic(panel, "vol_weight_075_s1", S1_TARGET_COL)

    y_s1 = compute_yearly_ic(panel, S1_SCORE_COL, S1_TARGET_COL)
    y_vol = compute_yearly_ic(panel, "vol_zscore", S1_TARGET_COL)
    y_add = compute_yearly_ic(panel, "vol_plus_s1", S1_TARGET_COL)

    pos_s1 = sum(1 for v in y_s1.values() if v > 0)
    pos_vol = sum(1 for v in y_vol.values() if v > 0)
    pos_add = sum(1 for v in y_add.values() if v > 0)

    print(f"\n=== H410 Volume + S1 Additive Results ===")
    print(f"S1 alone:          {ic_s1:+.5f} ({pos_s1}/{len(y_s1)} years)")
    print(f"Vol alone:        {ic_vol:+.5f} ({pos_vol}/{len(y_vol)} years)")
    print(f"Vol+S1 (equal):   {ic_add:+.5f} ({pos_add}/{len(y_add)} years)")
    print(f"0.25V+0.75S:     {ic_w025:+.5f}")
    print(f"0.50V+0.50S:     {ic_w050:+.5f}")
    print(f"0.75V+0.25S:     {ic_w075:+.5f}")

    # Find best weight
    weights = {
        "0.25V+0.75S": ic_w025,
        "0.50V+0.50S": ic_w050,
        "0.75V+0.25S": ic_w075,
    }
    best_weight = max(weights, key=weights.get)
    best_ic = weights[best_weight]

    print(f"\n--- Best: {best_weight} = {best_ic:+.5f}")

    result = {
        "ic_s1": float(ic_s1),
        "ic_vol": float(ic_vol),
        "ic_add": float(ic_add),
        "ic_w025": float(ic_w025),
        "ic_w050": float(ic_w050),
        "ic_w075": float(ic_w075),
        "best_weight": best_weight,
        "best_ic": float(best_ic),
        "pos_s1": pos_s1,
        "pos_vol": pos_vol,
        "pos_add": pos_add,
    }

    out_path = ROOT / "artifacts/run_summaries" / f"{BRANCH_NAME}_{MODE}.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nSaved: {out_path}")

    print(f"\n=== VERDICT ===")
    if best_ic > ic_s1 and pos_add >= 7:
        print("PASSED")
    elif best_ic > ic_s1:
        print("MIXED")
    elif best_ic > 0.10:
        print("MIXED - independent value")
    else:
        print("FAILED")

    return best_ic


if __name__ == "__main__":
    main()