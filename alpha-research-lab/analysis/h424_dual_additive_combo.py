"""
H424: Dual-Additive Combinations
Test if multiple additive scores combined improve.
Based on B49: combine different weight ratios.
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
BRANCH_NAME = "dual_additive_combination"
MODE = "research_branch"
MAX_YEAR = 2025


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H424 Dual-additive test")
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

    # Build ranks
    panel["vol_rank"] = panel.groupby("time")["order_volume_ratio"].rank(
        method="average", pct=True
    )
    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)

    print(f"\nPanel rows: {len(panel):,}")

    # Multiple additive scores
    panel["score_010"] = 0.10 * panel["vol_rank"] + 0.90 * panel[S1_SCORE_COL]  # H413
    panel["score_015"] = 0.15 * panel["vol_rank"] + 0.85 * panel[S1_SCORE_COL]
    panel["score_020"] = 0.20 * panel["vol_rank"] + 0.80 * panel[S1_SCORE_COL]
    panel["score_025"] = 0.25 * panel["vol_rank"] + 0.75 * panel[S1_SCORE_COL]

    # ICs for each
    ic_010 = compute_ic(panel, "score_010", S1_TARGET_COL)
    ic_015 = compute_ic(panel, "score_015", S1_TARGET_COL)
    ic_020 = compute_ic(panel, "score_020", S1_TARGET_COL)
    ic_025 = compute_ic(panel, "score_025", S1_TARGET_COL)

    # Combine two additives
    panel["score_comb1"] = 0.5 * panel["score_010"] + 0.5 * panel["score_015"]
    panel["score_comb2"] = 0.5 * panel["score_010"] + 0.5 * panel["score_025"]
    panel["score_avg_all"] = (
        panel["score_010"] + panel["score_015"] + panel["score_020"] + panel["score_025"]
    ) / 4

    ic_comb1 = compute_ic(panel, "score_comb1", S1_TARGET_COL)
    ic_comb2 = compute_ic(panel, "score_comb2", S1_TARGET_COL)
    ic_avg_all = compute_ic(panel, "score_avg_all", S1_TARGET_COL)

    print(f"\n=== H424 Dual-Additive Results ===")
    print(f"Single scores:")
    print(f"  0.10V+0.90S: {ic_010:+.5f}")
    print(f"  0.15V+0.85S: {ic_015:+.5f}")
    print(f"  0.20V+0.80S: {ic_020:+.5f}")
    print(f"  0.25V+0.75S: {ic_025:+.5f}")
    print(f"Combinations:")
    print(f"  50/50 × (010+015): {ic_comb1:+.5f}")
    print(f"  50/50 × (010+025): {ic_comb2:+.5f}")
    print(f"  Avg all 4:       {ic_avg_all:+.5f}")
    print(f"Best single: {max(ic_010, ic_015, ic_020, ic_025):+.5f}")
    print(f"Best combo:   {max(ic_comb1, ic_comb2, ic_avg_all):+.5f}")

    result = {
        "ic_010": float(ic_010),
        "ic_015": float(ic_015),
        "ic_020": float(ic_020),
        "ic_025": float(ic_025),
        "ic_comb1": float(ic_comb1),
        "ic_comb2": float(ic_comb2),
        "ic_avg_all": float(ic_avg_all),
    }

    out_path = ROOT / "artifacts/run_summaries" / f"{BRANCH_NAME}_{MODE}.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nSaved: {out_path}")

    print(f"\n=== VERDICT ===")
    best_single = max(ic_010, ic_015, ic_020, ic_025)
    best_combo = max(ic_comb1, ic_comb2, ic_avg_all)
    if best_combo > best_single + 0.005:
        print("PASSED - combination helps")
    elif best_combo > best_single:
        print("MIXED - marginal")
    else:
        print("FAILED - single best")

    return result


if __name__ == "__main__":
    main()