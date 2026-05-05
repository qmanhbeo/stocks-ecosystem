"""
H409: Volume × C16 Cross-Product Test
Test whether Volume pressure (order_volume_ratio) × C16 cross-product predicts forward.
Based on H407 pattern: cross-products of lagged features work.
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

S1_TARGET_COL = "actual"
BRANCH_NAME = "volume_c16_cross_product"
MODE = "research_branch"
MAX_YEAR = 2025


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H409 Volume × C16 cross-product test")
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
        args.s1_path, columns=["ticker", "time", S1_TARGET_COL]
    )
    s1 = s1[
        (s1["time"] >= f"{args.start_year}-01-01")
        & (s1["time"] <= f"{args.end_year}-12-31")
    ]

    print("Loading Order Stats...")
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

    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)

    panel["c16_lag1"] = panel.groupby("ticker")["order_pressure_h359_active"].shift(1)
    panel["vol_lag1"] = panel.groupby("ticker")["order_volume_ratio"].shift(1)

    panel = panel.dropna(subset=["c16_lag1", "vol_lag1"])

    panel["vol_c16_cross"] = panel["vol_lag1"] * panel["c16_lag1"]
    panel["vol_abs_c16_cross"] = panel["vol_lag1"].abs() * panel["c16_lag1"]

    print(f"\nPanel after lag: {len(panel):,}")

    ic_vol = compute_ic(panel, "order_volume_ratio", S1_TARGET_COL)
    ic_c16 = compute_ic(panel, "order_pressure_h359_active", S1_TARGET_COL)
    ic_cross = compute_ic(panel, "vol_c16_cross", S1_TARGET_COL)
    ic_abs_cross = compute_ic(panel, "vol_abs_c16_cross", S1_TARGET_COL)

    y_vol = compute_yearly_ic(panel, "order_volume_ratio", S1_TARGET_COL)
    y_c16 = compute_yearly_ic(panel, "order_pressure_h359_active", S1_TARGET_COL)
    y_cross = compute_yearly_ic(panel, "vol_c16_cross", S1_TARGET_COL)

    pos_vol = sum(1 for v in y_vol.values() if v > 0)
    pos_c16 = sum(1 for v in y_c16.values() if v > 0)
    pos_cross = sum(1 for v in y_cross.values() if v > 0)

    print(f"\n=== H409 Volume × C16 Cross-Product Results ===")
    print(f"Volume alone:       {ic_vol:+.5f} ({pos_vol}/{len(y_vol)} years)")
    print(f"C16 alone:        {ic_c16:+.5f} ({pos_c16}/{len(y_c16)} years)")
    print(f"Vol×C16 cross:    {ic_cross:+.5f} ({pos_cross}/{len(y_cross)} years)")
    print(f"|Vol|×C16:       {ic_abs_cross:+.5f}")

    result = {
        "ic_vol": ic_vol,
        "ic_c16": ic_c16,
        "ic_cross": ic_cross,
        "ic_abs_cross": ic_abs_cross,
        "pos_vol": pos_vol,
        "pos_c16": pos_c16,
        "pos_cross": pos_cross,
        "years": len(y_vol),
    }

    out_path = ROOT / "artifacts/run_summaries" / f"{BRANCH_NAME}_{MODE}.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nSaved: {out_path}")

    print(f"\n=== VERDICT ===")
    if ic_cross > 0.005 and pos_cross >= 5:
        if ic_cross > 0.01 and pos_cross >= 6:
            print("PASSED")
        else:
            print("MIXED")
    else:
        print("FAILED")

    return ic_cross


if __name__ == "__main__":
    main()