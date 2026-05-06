"""
H414: Alternative Target Additive Test
Test Vol+S1 additive on different barrier targets (5d, 20d).
Based on H413: additive works on 1d; test generalization.
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
BRANCH_NAME = "alternative_target_additive"
MODE = "research_branch"
MAX_YEAR = 2025


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H414 Alternative target test")
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

    print("Loading 1d barrier (baseline)...")
    s1_1d = pd.read_parquet(
        ROOT / "data/features/xs_barrier_vol_1d_hose_full.parquet",
        columns=["ticker", "time", S1_SCORE_COL, "actual"],
    )
    s1_1d = s1_1d.rename(columns={"actual": "actual_1d"})

    print("Loading 10d (5d ahead) barrier...")
    s1_10d = pd.read_parquet(
        ROOT / "data/features/xs_barrier_10d_label_hose_full.parquet",
        columns=["ticker", "time", "actual"],
    )
    s1_10d = s1_10d.rename(columns={"actual": "actual_10d"})

    print("Loading 20d barrier...")
    s1_20d = pd.read_parquet(
        ROOT / "data/features/xs_barrier_20d_label_hose_full.parquet",
        columns=["ticker", "time", "actual"],
    )
    s1_20d = s1_20d.rename(columns={"actual": "actual_20d"})

    print("Loading Volume...")
    orders = pd.read_parquet(
        ROOT / "data/features/xs_order_pressure_daily.parquet",
        columns=["ticker", "time", "order_volume_ratio"],
    )

    # Merge all
    panel = s1_1d.merge(s1_10d, on=["ticker", "time"], how="inner")
    panel = panel.merge(s1_20d, on=["ticker", "time"], how="inner")
    panel = panel.merge(orders, on=["ticker", "time"], how="inner")

    panel = panel[
        (panel["time"] >= f"{args.start_year}-01-01")
        & (panel["time"] <= f"{args.end_year}-12-31")
    ]
    panel = panel[
        panel[S1_SCORE_COL].notna()
        & panel["order_volume_ratio"].notna()
        & panel["actual_1d"].notna()
        & panel["actual_10d"].notna()
        & panel["actual_20d"].notna()
    ].copy()

    # Build Vol rank
    panel["vol_rank"] = panel.groupby("time")["order_volume_ratio"].rank(method="average", pct=True)

    # Build additive score (H413 best)
    panel["score_h413"] = 0.10 * panel["vol_rank"] + 0.90 * panel[S1_SCORE_COL]

    # Also test on just S1 for comparison
    panel["s1_1d_score"] = panel[S1_SCORE_COL]

    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)

    print(f"\nPanel rows: {len(panel):,}")

    # Test on each target
    print(f"\n=== H414 Alternative Target Additive Results ===")

    # 1d target
    ic_1d_h413 = compute_ic(panel, "score_h413", "actual_1d")
    ic_1d_s1 = compute_ic(panel, "s1_1d_score", "actual_1d")
    y_1d = compute_yearly_ic(panel, "score_h413", "actual_1d")
    pos_1d = sum(1 for v in y_1d.values() if v > 0)

    # 10d target
    ic_10d_h413 = compute_ic(panel, "score_h413", "actual_10d")
    ic_10d_s1 = compute_ic(panel, "s1_1d_score", "actual_10d")
    y_10d = compute_yearly_ic(panel, "score_h413", "actual_10d")
    pos_10d = sum(1 for v in y_10d.values() if v > 0)

    # 20d target
    ic_20d_h413 = compute_ic(panel, "score_h413", "actual_20d")
    ic_20d_s1 = compute_ic(panel, "s1_1d_score", "actual_20d")
    y_20d = compute_yearly_ic(panel, "score_h413", "actual_20d")
    pos_20d = sum(1 for v in y_20d.values() if v > 0)

    print(f"\n1d target (baseline):")
    print(f"  S1 alone:    {ic_1d_s1:+.5f}")
    print(f"  0.1V+0.9S: {ic_1d_h413:+.5f} ({pos_1d}/{len(y_1d)} years)")

    print(f"\n10d target (5d ahead):")
    print(f"  S1 alone:    {ic_10d_s1:+.5f}")
    print(f"  0.1V+0.9S: {ic_10d_h413:+.5f} ({pos_10d}/{len(y_10d)} years)")

    print(f"\n20d target:")
    print(f"  S1 alone:    {ic_20d_s1:+.5f}")
    print(f"  0.1V+0.9S: {ic_20d_h413:+.5f} ({pos_20d}/{len(y_20d)} years)")

    result = {
        "ic_1d_s1": float(ic_1d_s1),
        "ic_1d_h413": float(ic_1d_h413),
        "ic_10d_s1": float(ic_10d_s1),
        "ic_10d_h413": float(ic_10d_h413),
        "ic_20d_s1": float(ic_20d_s1),
        "ic_20d_h413": float(ic_20d_h413),
        "pos_1d": pos_1d,
        "pos_10d": pos_10d,
        "pos_20d": pos_20d,
    }

    out_path = ROOT / "artifacts/run_summaries" / f"{BRANCH_NAME}_{MODE}.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nSaved: {out_path}")

    # Determine verdict based on 10d or 20d beating S1 alone
    print(f"\n=== VERDICT ===")
    if ic_10d_h413 > ic_10d_s1 + 0.01 and pos_10d >= 6:
        print("PASSED - works on 10d")
    elif ic_20d_h413 > ic_20d_s1 + 0.01 and pos_20d >= 6:
        print("PASSED - works on 20d")
    elif ic_10d_h413 > ic_10d_s1 or ic_20d_h413 > ic_20d_s1:
        print("MIXED - some targets benefit")
    else:
        print("FAILED - additive only works on 1d")

    return result


if __name__ == "__main__":
    main()