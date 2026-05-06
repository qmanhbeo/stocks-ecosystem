"""
H418: Add Foreign Flow to Additive
Test adding foreign flow signal to confirmed additive pattern.
Based on B56: foreign flow as NEW signal source.
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
BRANCH_NAME = "foreign_additive"
MODE = "research_branch"
MAX_YEAR = 2025


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H418 Foreign flow test")
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

    print("Loading Foreign Flow...")
    foreign = pd.read_parquet(
        ROOT / "data/foreign_flow/cafef/foreign_flow_daily.parquet",
        columns=["ticker", "date", "foreign_net_volume"],
    )
    foreign["time"] = pd.to_datetime(foreign["date"])
    foreign = foreign.drop(columns=["date"])
    foreign["foreign_net"] = foreign["foreign_net_volume"] > 0

    panel = s1.merge(orders, on=["ticker", "time"], how="inner")
    panel = panel.merge(foreign, on=["ticker", "time"], how="left")

    panel = panel[
        panel[S1_SCORE_COL].notna()
        & panel[S1_TARGET_COL].notna()
        & panel["order_volume_ratio"].notna()
    ].copy()

    panel["vol_rank"] = panel.groupby("time")["order_volume_ratio"].rank(
        method="average", pct=True
    )
    panel["foreign_rank"] = panel.groupby("time")["foreign_net_volume"].rank(
        method="average", pct=True, na_option="keep"
    )

    # Fill foreign NaN
    panel["foreign_rank"] = panel["foreign_rank"].fillna(0.5)

    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)

    print(f"\nPanel rows: {len(panel):,}")

    # H413 baseline
    panel["score_h413"] = 0.10 * panel["vol_rank"] + 0.90 * panel[S1_SCORE_COL]

    # Test adding foreign
    panel["score_3way"] = 0.10 * panel["vol_rank"] + 0.80 * panel[S1_SCORE_COL] + 0.10 * panel["foreign_rank"]

    ic_s1 = compute_ic(panel, S1_SCORE_COL, S1_TARGET_COL)
    ic_vol = compute_ic(panel, "vol_rank", S1_TARGET_COL)
    ic_foreign = compute_ic(panel, "foreign_rank", S1_TARGET_COL)
    ic_h413 = compute_ic(panel, "score_h413", S1_TARGET_COL)
    ic_3way = compute_ic(panel, "score_3way", S1_TARGET_COL)

    print(f"\n=== H418 Foreign Flow Add Results ===")
    print(f"S1 alone:        {ic_s1:+.5f}")
    print(f"Volume alone:    {ic_vol:+.5f}")
    print(f"Foreign alone:  {ic_foreign:+.5f}")
    print(f"H413 (0.1V+0.9S): {ic_h413:+.5f}")
    print(f"3-way (+foreign):{ic_3way:+.5f}")

    delta = ic_3way - ic_h413

    result = {
        "ic_s1": float(ic_s1),
        "ic_vol": float(ic_vol),
        "ic_foreign": float(ic_foreign),
        "ic_h413": float(ic_h413),
        "ic_3way": float(ic_3way),
        "delta": float(delta),
    }

    out_path = ROOT / "artifacts/run_summaries" / f"{BRANCH_NAME}_{MODE}.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nSaved: {out_path}")
    print(f"Delta vs H413: {delta:+.5f}")

    print(f"\n=== VERDICT ===")
    if delta > 0.005:
        print("PASSED - foreign adds value")
    elif delta > 0:
        print("MIXED - marginal improvement")
    else:
        print("FAILED - foreign doesn't help")

    return result


if __name__ == "__main__":
    main()