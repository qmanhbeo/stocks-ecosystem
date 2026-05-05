"""
H423: Sector-Adjusted Additive
Test if sector-relative Vol+S1 improves.
Based on B48: subtract sector mean from both before additive.
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
BRANCH_NAME = "sector_adjusted_additive"
MODE = "research_branch"
MAX_YEAR = 2025


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H423 Sector-adjusted test")
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

    print("Loading sector...")
    sector = pd.read_parquet(
        ROOT / "data/features/sector_classification.parquet",
        columns=["symbol", "icb_name2"],
    )
    sector = sector.rename(columns={"symbol": "ticker", "icb_name2": "sector"})

    panel = s1.merge(orders, on=["ticker", "time"], how="inner")
    panel = panel.merge(sector, on="ticker", how="left")
    panel = panel[
        panel[S1_SCORE_COL].notna()
        & panel[S1_TARGET_COL].notna()
        & panel["order_volume_ratio"].notna()
        & panel["sector"].notna()
    ].copy()

    # Sector-relative volume
    panel["sector_vol_mean"] = panel.groupby(["time", "sector"])[
        "order_volume_ratio"
    ].transform("mean")
    panel["vol_sector_adj"] = panel["order_volume_ratio"] - panel["sector_vol_mean"]

    # Similarly for S1
    panel["sector_s1_mean"] = panel.groupby(["time", "sector"])[
        S1_SCORE_COL
    ].transform("mean")
    panel["s1_sector_adj"] = panel[S1_SCORE_COL] - panel["sector_s1_mean"]

    # Build ranks
    panel["vol_rank"] = panel.groupby("time")["order_volume_ratio"].rank(
        method="average", pct=True
    )
    panel["vol_sector_adj_rank"] = panel.groupby("time")["vol_sector_adj"].rank(
        method="average", pct=True
    )
    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)

    print(f"\nPanel rows: {len(panel):,}")
    print(f"Sectors: {panel['sector'].nunique()}")

    # H413 baseline
    panel["score_h413"] = 0.10 * panel["vol_rank"] + 0.90 * panel[S1_SCORE_COL]

    # Sector-adjusted additive
    panel["score_sector_adj"] = (
        0.10 * panel["vol_sector_adj_rank"] + 0.90 * panel[S1_SCORE_COL]
    )

    # Compute ICs
    ic_h413 = compute_ic(panel, "score_h413", S1_TARGET_COL)
    ic_sector_adj = compute_ic(panel, "score_sector_adj", S1_TARGET_COL)
    ic_s1 = compute_ic(panel, S1_SCORE_COL, S1_TARGET_COL)

    print(f"\n=== H423 Sector-Adjusted Results ===")
    print(f"S1 alone:           {ic_s1:+.5f}")
    print(f"H413 (uniform):    {ic_h413:+.5f}")
    print(f"Sector-adjusted: {ic_sector_adj:+.5f}")
    print(f"Delta:            {ic_sector_adj - ic_h413:+.5f}")

    result = {
        "ic_s1": float(ic_s1),
        "ic_h413": float(ic_h413),
        "ic_sector_adj": float(ic_sector_adj),
        "delta": float(ic_sector_adj - ic_h413),
    }

    out_path = ROOT / "artifacts/run_summaries" / f"{BRANCH_NAME}_{MODE}.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nSaved: {out_path}")

    print(f"\n=== VERDICT ===")
    delta = ic_sector_adj - ic_h413
    if delta > 0.005:
        print("PASSED - sector-adjustment helps")
    elif delta > 0:
        print("MIXED - marginal")
    else:
        print("FAILED - uniform is best")

    return result


if __name__ == "__main__":
    main()