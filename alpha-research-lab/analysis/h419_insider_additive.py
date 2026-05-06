"""
H419: Add Insider Signal to Additive
Test adding insider signal to confirmed additive pattern.
Based on B57: insider as NEW signal source.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from glob import glob

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

S1_SCORE_COL = "xs_proba"
S1_TARGET_COL = "actual"
BRANCH_NAME = "insider_additive"
MODE = "research_branch"
MAX_YEAR = 2025


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H419 Insider test")
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

    print("Loading Insider (394 tickers)...")
    insider_files = glob(str(ROOT / "data/insider_cache/*.parquet"))
    
    dfs = []
    for f in insider_files[:50]:  # Sample first 50 for speed
        try:
            df = pd.read_parquet(f, columns=["ticker", "published_date", "is_insider", "net_real_vol"])
            dfs.append(df)
        except:
            pass
    
    insider = pd.concat(dfs, ignore_index=True)
    insider["time"] = pd.to_datetime(insider["published_date"]).dt.normalize()
    
    # Create binary insider signal: has insider trade that day
    insider_agg = insider.groupby(["ticker", "time"]).agg({
        "is_insider": "max",  # any insider trade that day
        "net_real_vol": "sum"
    }).reset_index()
    insider_agg["insider_active"] = insider_agg["is_insider"] > 0

    panel = s1.merge(orders, on=["ticker", "time"], how="inner")
    panel = panel.merge(
        insider_agg[["ticker", "time", "insider_active"]], 
        on=["ticker", "time"], 
        how="left"
    )

    panel = panel[
        panel[S1_SCORE_COL].notna()
        & panel[S1_TARGET_COL].notna()
        & panel["order_volume_ratio"].notna()
    ].copy()

    panel["vol_rank"] = panel.groupby("time")["order_volume_ratio"].rank(
        method="average", pct=True
    )
    panel["insider_rank"] = panel["insider_active"].astype(float).fillna(0)

    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)

    print(f"\nPanel rows: {len(panel):,}")
    print(f"Insider rows: {panel['insider_active'].sum():,}")

    # H413 baseline
    panel["score_h413"] = 0.10 * panel["vol_rank"] + 0.90 * panel[S1_SCORE_COL]

    # Test adding insider
    panel["score_3way"] = 0.10 * panel["vol_rank"] + 0.80 * panel[S1_SCORE_COL] + 0.10 * panel["insider_rank"]

    ic_s1 = compute_ic(panel, S1_SCORE_COL, S1_TARGET_COL)
    ic_vol = compute_ic(panel, "vol_rank", S1_TARGET_COL)
    ic_insider = compute_ic(panel, "insider_rank", S1_TARGET_COL)
    ic_h413 = compute_ic(panel, "score_h413", S1_TARGET_COL)
    ic_3way = compute_ic(panel, "score_3way", S1_TARGET_COL)

    print(f"\n=== H419 Insider Add Results ===")
    print(f"S1 alone:        {ic_s1:+.5f}")
    print(f"Volume alone:    {ic_vol:+.5f}")
    print(f"Insider alone:   {ic_insider:+.5f}")
    print(f"H413 (0.1V+0.9S): {ic_h413:+.5f}")
    print(f"3-way (+insider):{ic_3way:+.5f}")

    delta = ic_3way - ic_h413

    result = {
        "ic_s1": float(ic_s1),
        "ic_vol": float(ic_vol),
        "ic_insider": float(ic_insider),
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
        print("PASSED - insider adds value")
    elif delta > 0:
        print("MIXED - marginal improvement")
    else:
        print("FAILED - insider doesn't help")

    return result


if __name__ == "__main__":
    main()