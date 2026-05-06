"""
H415: Weight Optimization Grid Search
Systematically search Vol/S1 weight ratios to find optimum.
Based on H413: 0.1V+0.9S found; test if better exists.
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
BRANCH_NAME = "weight_optimization"
MODE = "research_branch"
MAX_YEAR = 2025


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H415 Weight optimization")
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
        ROOT / "data/features/xs_barrier_vol_1d_hose_full.parquet",
        columns=["ticker", "time", S1_SCORE_COL, S1_TARGET_COL],
    )
    s1 = s1[
        (s1["time"] >= f"{args.start_year}-01-01")
        & (s1["time"] <= f"{args.end_year}-12-31")
    ]

    print("Loading Volume...")
    orders = pd.read_parquet(
        ROOT / "data/features/xs_order_pressure_daily.parquet",
        columns=["ticker", "time", "order_volume_ratio"],
    )

    panel = s1.merge(orders, on=["ticker", "time"], how="inner")
    panel = panel[
        panel[S1_SCORE_COL].notna()
        & panel[S1_TARGET_COL].notna()
        & panel["order_volume_ratio"].notna()
    ].copy()

    panel["vol_rank"] = panel.groupby("time")["order_volume_ratio"].rank(
        method="average", pct=True
    )
    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)

    print(f"\nPanel rows: {len(panel):,}")

    # Grid search weights
    weights_to_test = [
        (0.00, 1.00, "S1 only"),
        (0.05, 0.95, "5V+95S"),
        (0.10, 0.90, "10V+90S"),
        (0.15, 0.85, "15V+85S"),
        (0.20, 0.80, "20V+80S"),
        (0.25, 0.75, "25V+75S"),
        (0.30, 0.70, "30V+70S"),
        (0.35, 0.65, "35V+65S"),
        (0.40, 0.60, "40V+60S"),
        (0.50, 0.50, "50V+50S"),
    ]

    results = {}
    print(f"\n=== H415 Weight Optimization Results ===")

    for v_w, s_w, name in weights_to_test:
        col_name = f"w{v_w}_{s_w}"
        panel[col_name] = v_w * panel["vol_rank"] + s_w * panel[S1_SCORE_COL]
        ic = compute_ic(panel, col_name, S1_TARGET_COL)
        y = compute_yearly_ic(panel, col_name, S1_TARGET_COL)
        pos = sum(1 for v in y.values() if v > 0)
        results[name] = {"ic": ic, "pos": pos, "weights": (v_w, s_w)}
        print(f"{name}: {ic:+.5f} ({pos}/{len(y)} years)")

    # Find best
    best_name = max(results, key=lambda k: results[k]["ic"])
    best_ic = results[best_name]["ic"]

    print(f"\n--- Best: {best_name} = {best_ic:+.5f}")
    print(f"--- H413 was 10V+90S = +0.1346, current best = {best_ic - 0.1346:+.5f} delta")

    out_path = ROOT / "artifacts/run_summaries" / f"{BRANCH_NAME}_{MODE}.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved: {out_path}")

    print(f"\n=== VERDICT ===")
    delta = best_ic - 0.1346
    if delta > 0.005:
        print("PASSED - found better weight")
    elif delta > 0:
        print("MIXED - marginal improvement")
    else:
        print("FAILED - 0.1/0.9 remains optimal")

    return results


if __name__ == "__main__":
    main()