"""
H421: Time-Varying Additive
Test if optimal weights changed over years.
Based on B47: weights evolved over time, test year-by-year optimization.
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
BRANCH_NAME = "time_varying_weights"
MODE = "research_branch"
MAX_YEAR = 2025


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H421 Time-varying weights test")
    parser.add_argument("--start-year", type=int, default=2018)
    parser.add_argument("--end-year", type=int, default=MAX_YEAR)
    return parser.parse_args()


def compute_ic(panel: pd.DataFrame, score_col: str, target_col: str) -> float:
    valid = panel[[score_col, target_col]].dropna()
    if len(valid) < 50:
        return np.nan
    ic, _ = spearmanr(valid[score_col], valid[target_col])
    return ic


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

    # Build percentile ranks
    panel["vol_rank"] = panel.groupby("time")["order_volume_ratio"].rank(
        method="average", pct=True
    )
    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)

    panel["year"] = pd.to_datetime(panel["time"]).dt.year

    print(f"\nPanel rows: {len(panel):,}")
    print(f"Years: {panel['year'].unique()}")

    # Test uniform H413
    panel["score_h413"] = 0.10 * panel["vol_rank"] + 0.90 * panel[S1_SCORE_COL]

    # Year-by-year IC with H413
    yearly_results = []
    for year in sorted(panel["year"].unique()):
        yr_panel = panel[panel["year"] == year].copy()
        ic = compute_ic(yr_panel, "score_h413", S1_TARGET_COL)
        yearly_results.append({"year": int(year), "ic_h413": ic})
        print(f"{year}: H413 IC = {ic:+.5f}")

    # Optimize weights per year
    yearly_opt = []
    weights_to_test = [
        (0.05, 0.95),
        (0.10, 0.90),
        (0.15, 0.85),
        (0.20, 0.80),
        (0.25, 0.75),
    ]

    for year in sorted(panel["year"].unique()):
        yr_panel = panel[panel["year"] == year].copy()
        best_ic = -999
        best_w = (0.10, 0.90)
        for w_vol, w_s1 in weights_to_test:
            test_score = w_vol * yr_panel["vol_rank"] + w_s1 * yr_panel[S1_SCORE_COL]
            ic = compute_ic(yr_panel, S1_SCORE_COL, S1_TARGET_COL)
            yr_panel_copy = yr_panel.copy()
            yr_panel_copy["test_score"] = test_score
            ic = compute_ic(yr_panel_copy, "test_score", S1_TARGET_COL)
            if ic > best_ic:
                best_ic = ic
                best_w = (w_vol, w_s1)
        yearly_opt.append({"year": int(year), "best_vol": best_w[0], "best_s1": best_w[1], "ic_opt": best_ic})
        print(f"{year}: OPT = {best_w[0]:.2f}V+{best_w[1]:.2f}S => IC = {best_ic:+.5f}")

    # Compare: optimized per-year vs uniform
    uniform_ic = compute_ic(panel, "score_h413", S1_TARGET_COL)

    # Create year-optimized score
    panel = panel.merge(
        pd.DataFrame(yearly_opt)[["year", "best_vol", "best_s1"]],
        on="year"
    )
    panel["score_opt"] = panel["best_vol"] * panel["vol_rank"] + panel["best_s1"] * panel[S1_SCORE_COL]

    ic_year_opt = compute_ic(panel, "score_opt", S1_TARGET_COL)

    print(f"\n=== H421 Time-Varying Results ===")
    print(f"Uniform (0.1V+0.9S): {uniform_ic:+.5f}")
    print(f"Year-optimized:    {ic_year_opt:+.5f}")
    print(f"Delta:            {ic_year_opt - uniform_ic:+.5f}")

    result = {
        "uniform_ic": float(uniform_ic),
        "ic_year_opt": float(ic_year_opt),
        "delta": float(ic_year_opt - uniform_ic),
        "yearly_opt": yearly_opt,
    }

    out_path = ROOT / "artifacts/run_summaries" / f"{BRANCH_NAME}_{MODE}.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nSaved: {out_path}")

    print(f"\n=== VERDICT ===")
    delta = ic_year_opt - uniform_ic
    if delta > 0.005:
        print("PASSED - time-varying helps")
    elif delta > 0:
        print("MIXED - marginal")
    else:
        print("FAILED - uniform is best")

    return result


if __name__ == "__main__":
    main()