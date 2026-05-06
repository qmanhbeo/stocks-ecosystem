"""
H417: Hold-Out Validation (2025 Only)
Test additive on completely held-out data to confirm no survivor bias.
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
BRANCH_NAME = "holdout_2025"
MODE = "research_branch"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H417 Hold-out 2025 test")
    parser.add_argument("--target-year", type=int, default=2025)
    return parser.parse_args()


def compute_ic(panel: pd.DataFrame, score_col: str, target_col: str) -> float:
    valid = panel[[score_col, target_col]].dropna()
    if len(valid) < 50:
        return np.nan
    ic, _ = spearmanr(valid[score_col], valid[target_col])
    return ic


def main():
    args = parse_args()

    print(f"Loading S1 target...")
    s1 = pd.read_parquet(
        ROOT / "data/features/xs_barrier_vol_1d_hose_full.parquet",
        columns=["ticker", "time", S1_SCORE_COL, S1_TARGET_COL],
    )
    
    # HOLD OUT 2025 ONLY
    s1 = s1[s1["time"].dt.year == args.target_year].copy()
    print(f"S1 2025 rows: {len(s1):,}")

    print(f"Loading Volume...")
    orders = pd.read_parquet(
        ROOT / "data/features/xs_order_pressure_daily.parquet",
        columns=["ticker", "time", "order_volume_ratio"],
    )
    orders = orders[orders["time"].dt.year == args.target_year]

    panel = s1.merge(orders, on=["ticker", "time"], how="inner")
    panel = panel[
        panel[S1_SCORE_COL].notna()
        & panel[S1_TARGET_COL].notna()
        & panel["order_volume_ratio"].notna()
    ].copy()

    panel["vol_rank"] = panel.groupby("time")["order_volume_ratio"].rank(
        method="average", pct=True
    )
    panel["score_h413"] = 0.10 * panel["vol_rank"] + 0.90 * panel[S1_SCORE_COL]

    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)

    print(f"\n=== H417 Hold-Out 2025 Results ===")
    ic_s1 = compute_ic(panel, S1_SCORE_COL, S1_TARGET_COL)
    ic_h413 = compute_ic(panel, "score_h413", S1_TARGET_COL)
    ic_vol = compute_ic(panel, "vol_rank", S1_TARGET_COL)

    lift = ic_h413 - ic_s1

    print(f"2025 HOLD-OUT:")
    print(f"  S1 alone:          {ic_s1:+.5f}")
    print(f"  Volume alone:     {ic_vol:+.5f}")
    print(f"  0.1V+0.9S:        {ic_h413:+.5f}")
    print(f"  Lift vs S1:       {lift:+.5f}")

    result = {
        "ic_s1": float(ic_s1),
        "ic_vol": float(ic_vol),
        "ic_h413": float(ic_h413),
        "lift": float(lift),
        "year": args.target_year,
        "n_rows": len(panel),
    }

    out_path = ROOT / "artifacts/run_summaries" / f"{BRANCH_NAME}_{MODE}.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nSaved: {out_path}")

    print(f"\n=== VERDICT ===")
    if lift > 0.01:
        print(f"PASSED - holds on 2025 hold-out (+{lift:.5f})")
    elif lift > 0:
        print(f"MIXED - holds marginally (+{lift:.5f})")
    else:
        print(f"FAILED - doesn't hold on 2025")

    return result


if __name__ == "__main__":
    main()