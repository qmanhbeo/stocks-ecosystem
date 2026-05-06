"""
H416: Market-State Gated Additive
Test Vol+S1 additive in different market states.
Based on H415: weight insensitive; test regime-specific.
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
BRANCH_NAME = "market_state_gated"
MODE = "research_branch"
MAX_YEAR = 2025


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H416 Market state gated test")
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

    print("Loading VNINDEX...")
    vni = pd.read_parquet(
        ROOT / "data/stock/gia_lich_su_VNINDEX_1D.parquet",
        columns=["time", "close"],
    )
    vni["vni_ret"] = vni["close"].pct_change()
    vni["vni_up"] = vni["vni_ret"] > 0
    vni = vni[["time", "vni_up"]]

    panel = s1.merge(orders, on=["ticker", "time"], how="inner")
    panel = panel.merge(vni, on="time", how="left")

    panel = panel[
        panel[S1_SCORE_COL].notna()
        & panel[S1_TARGET_COL].notna()
        & panel["order_volume_ratio"].notna()
        & panel["vni_up"].notna()
    ].copy()

    panel["vol_rank"] = panel.groupby("time")["order_volume_ratio"].rank(
        method="average", pct=True
    )
    panel["score_h413"] = 0.10 * panel["vol_rank"] + 0.90 * panel[S1_SCORE_COL]

    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)

    print(f"\nPanel rows: {len(panel):,}")

    # Split by market state
    vni_up = panel[panel["vni_up"] == True]
    vni_down = panel[panel["vni_up"] == False]

    print(f"\n=== H416 Market State Gated Results ===")
    print(f"VNI up days: {len(vni_up):,}, VNI down days: {len(vni_down):,}")

    ic_all = compute_ic(panel, "score_h413", S1_TARGET_COL)
    ic_up = compute_ic(vni_up, "score_h413", S1_TARGET_COL)
    ic_down = compute_ic(vni_down, "score_h413", S1_TARGET_COL)

    ic_s1_all = compute_ic(panel, S1_SCORE_COL, S1_TARGET_COL)
    ic_s1_up = compute_ic(vni_up, S1_SCORE_COL, S1_TARGET_COL)
    ic_s1_down = compute_ic(vni_down, S1_SCORE_COL, S1_TARGET_COL)

    print(f"\nAll days:")
    print(f"  S1 alone: {ic_s1_all:+.5f}")
    print(f"  0.1V+0.9S: {ic_all:+.5f} (lift: {ic_all-ic_s1_all:+.5f})")

    print(f"\nVNI up ({len(vni_up)} rows):")
    print(f"  S1 alone: {ic_s1_up:+.5f}")
    print(f"  0.1V+0.9S: {ic_up:+.5f} (lift: {ic_up-ic_s1_up:+.5f})")

    print(f"\nVNI down ({len(vni_down)} rows):")
    print(f"  S1 alone: {ic_s1_down:+.5f}")
    print(f"  0.1V+0.9S: {ic_down:+.5f} (lift: {ic_down-ic_s1_down:+.5f})")

    result = {
        "ic_all": float(ic_all),
        "ic_up": float(ic_up),
        "ic_down": float(ic_down),
        "ic_s1_all": float(ic_s1_all),
        "ic_s1_up": float(ic_s1_up),
        "ic_s1_down": float(ic_s1_down),
        "lift_up": float(ic_up - ic_s1_up),
        "lift_down": float(ic_down - ic_s1_down),
    }

    out_path = ROOT / "artifacts/run_summaries" / f"{BRANCH_NAME}_{MODE}.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nSaved: {out_path}")

    print(f"\n=== VERDICT ===")
    if (ic_up - ic_s1_up) > 0.01 and (ic_down - ic_s1_down) > 0.01:
        print("PASSED - works in both states")
    elif (ic_up - ic_s1_up) > 0 or (ic_down - ic_s1_down) > 0:
        print("MIXED - works in some states")
    else:
        print("FAILED - additive doesn't help")

    return result


if __name__ == "__main__":
    main()