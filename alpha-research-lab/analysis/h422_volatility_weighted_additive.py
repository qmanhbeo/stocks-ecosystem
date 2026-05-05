"""
H422: Volatility-Weighted Additive
Test if high volatility stocks benefit from different Vol/S1 weights.
Based on B52: Volatility regime affects optimal weight.
Uses absolute return rank as volatility proxy.
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
BRANCH_NAME = "volatility_weighted_additive"
MODE = "research_branch"
MAX_YEAR = 2025


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H422 Volatility-weighted test")
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

    print("Loading reversal (as volatility proxy)...")
    reversal = pd.read_parquet(
        ROOT / "data/features/xs_shortterm_reversal.parquet",
        columns=["ticker", "time", "xs_ret_1d_abs_rank"],
    )
    reversal = reversal[
        (reversal["time"] >= f"{args.start_year}-01-01")
        & (reversal["time"] <= f"{args.end_year}-12-31")
    ]

    panel = s1.merge(orders, on=["ticker", "time"], how="inner")
    panel = panel.merge(
        reversal[["ticker", "time", "xs_ret_1d_abs_rank"]],
        on=["ticker", "time"],
        how="inner"
    )
    panel = panel[
        panel[S1_SCORE_COL].notna()
        & panel[S1_TARGET_COL].notna()
        & panel["order_volume_ratio"].notna()
        & panel["xs_ret_1d_abs_rank"].notna()
    ].copy()

    # Build ranks
    panel["vol_rank"] = panel.groupby("time")["order_volume_ratio"].rank(
        method="average", pct=True
    )
    panel["volatility_rank"] = panel["xs_ret_1d_abs_rank"]  # Already a rank
    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)

    print(f"\nPanel rows: {len(panel):,}")

    # H413 baseline
    panel["score_h413"] = 0.10 * panel["vol_rank"] + 0.90 * panel[S1_SCORE_COL]

    # High vol stocks: less Volume weight (they already vol)
    # Low vol stocks: more Volume weight
    panel["score_vol_adjusted"] = np.where(
        panel["volatility_rank"] > 0.5,
        0.05 * panel["vol_rank"] + 0.95 * panel[S1_SCORE_COL],
        0.15 * panel["vol_rank"] + 0.85 * panel[S1_SCORE_COL]
    )

    # Compute ICs
    ic_h413 = compute_ic(panel, "score_h413", S1_TARGET_COL)
    ic_vol_adj = compute_ic(panel, "score_vol_adjusted", S1_TARGET_COL)
    ic_s1 = compute_ic(panel, S1_SCORE_COL, S1_TARGET_COL)

    print(f"\n=== H422 Volatility-Weighted Results ===")
    print(f"S1 alone:           {ic_s1:+.5f}")
    print(f"H413 (uniform):    {ic_h413:+.5f}")
    print(f"Vol-adjusted:    {ic_vol_adj:+.5f}")
    print(f"Delta:            {ic_vol_adj - ic_h413:+.5f}")

    result = {
        "ic_s1": float(ic_s1),
        "ic_h413": float(ic_h413),
        "ic_vol_adjusted": float(ic_vol_adj),
        "delta": float(ic_vol_adj - ic_h413),
    }

    out_path = ROOT / "artifacts/run_summaries" / f"{BRANCH_NAME}_{MODE}.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nSaved: {out_path}")

    print(f"\n=== VERDICT ===")
    delta = ic_vol_adj - ic_h413
    if delta > 0.005:
        print("PASSED - volatility-weighting helps")
    elif delta > 0:
        print("MIXED - marginal")
    else:
        print("FAILED - uniform is best")

    return result


if __name__ == "__main__":
    main()