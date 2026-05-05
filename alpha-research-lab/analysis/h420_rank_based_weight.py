"""
H420: Rank-Based Weight Adjustment
Test if top-ranked stocks should get different weights than bottom-ranked.
Based on B46: top stocks get more S1 weight, bottom get more Volume.
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
BRANCH_NAME = "rank_based_weight"
MODE = "research_branch"
MAX_YEAR = 2025


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H420 Rank-based weight test")
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

    # Build base ranks
    panel["vol_rank"] = panel.groupby("time")["order_volume_ratio"].rank(
        method="average", pct=True
    )
    panel["s1_rank"] = panel.groupby("time")[S1_SCORE_COL].rank(
        method="average", pct=True
    )

    # H413 baseline
    panel["score_h413"] = 0.10 * panel["vol_rank"] + 0.90 * panel[S1_SCORE_COL]

    # Split into top/bottom by average rank
    panel["avg_rank"] = (panel["vol_rank"] + panel["s1_rank"]) / 2
    panel["is_top"] = panel["avg_rank"] > 0.5

    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)

    print(f"\nPanel rows: {len(panel):,}")
    print(f"Top stocks: {(panel['is_top']).sum():,}")
    print(f"Bottom stocks: {(~panel['is_top']).sum():,}")

    # Test different weighting schemes
    # Top stocks: use more S1; Bottom stocks: use more Volume
    panel["score_top_heavy"] = np.where(
        panel["is_top"],
        0.05 * panel["vol_rank"] + 0.95 * panel[S1_SCORE_COL],
        0.15 * panel["vol_rank"] + 0.85 * panel[S1_SCORE_COL]
    )

    # Reverse: top get more volume
    panel["score_top_light"] = np.where(
        panel["is_top"],
        0.15 * panel["vol_rank"] + 0.85 * panel[S1_SCORE_COL],
        0.05 * panel["vol_rank"] + 0.95 * panel[S1_SCORE_COL]
    )

    # Uniform H413 for comparison
    ic_s1 = compute_ic(panel, S1_SCORE_COL, S1_TARGET_COL)
    ic_h413 = compute_ic(panel, "score_h413", S1_TARGET_COL)
    ic_top_heavy = compute_ic(panel, "score_top_heavy", S1_TARGET_COL)
    ic_top_light = compute_ic(panel, "score_top_light", S1_TARGET_COL)

    print(f"\n=== H420 Rank-Based Weight Results ===")
    print(f"S1 alone:         {ic_s1:+.5f}")
    print(f"H413 (uniform):   {ic_h413:+.5f}")
    print(f"Top-heavy S1:    {ic_top_heavy:+.5f}")
    print(f"Top-light Vol:   {ic_top_light:+.5f}")

    delta_heavy = ic_top_heavy - ic_h413
    delta_light = ic_top_light - ic_h413

    result = {
        "ic_s1": float(ic_s1),
        "ic_h413": float(ic_h413),
        "ic_top_heavy": float(ic_top_heavy),
        "ic_top_light": float(ic_top_light),
        "delta_heavy": float(delta_heavy),
        "delta_light": float(delta_light),
    }

    out_path = ROOT / "artifacts/run_summaries" / f"{BRANCH_NAME}_{MODE}.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nSaved: {out_path}")
    print(f"Delta (top-heavy): {delta_heavy:+.5f}")
    print(f"Delta (top-light): {delta_light:+.5f}")

    print(f"\n=== VERDICT ===")
    if max(delta_heavy, delta_light) > 0.005:
        print("PASSED - rank-based helps")
    elif max(delta_heavy, delta_light) > 0:
        print("MIXED - marginal")
    else:
        print("FAILED - uniform is best")

    return result


if __name__ == "__main__":
    main()