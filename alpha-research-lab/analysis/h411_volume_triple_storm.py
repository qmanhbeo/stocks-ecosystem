"""
H411: Volume Triple Storm Test
Test Triple Storm conditions on Volume as signal amplifier.
Based on S229: Triple Storm works on C16; H410: additive works; test on Volume.
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
BRANCH_NAME = "volume_triple_storm"
MODE = "research_branch"
MAX_YEAR = 2025


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H411 Volume Triple Storm test")
    parser.add_argument(
        "--s1-path",
        type=str,
        default=str(ROOT / "data/features/xs_barrier_vol_1d_hose_full.parquet"),
    )
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

    print("Loading S1...")
    s1 = pd.read_parquet(
        args.s1_path, columns=["ticker", "time", S1_SCORE_COL, S1_TARGET_COL]
    )
    s1 = s1[
        (s1["time"] >= f"{args.start_year}-01-01")
        & (s1["time"] <= f"{args.end_year}-12-31")
    ]

    print("Loading Order Stats (Volume)...")
    orders = pd.read_parquet(
        ROOT / "data/features/xs_order_pressure_daily.parquet",
        columns=["ticker", "time", "order_volume_ratio"],
    )

    # Load VNINDEX for market state
    vni = pd.read_parquet(
        ROOT / "data/stock/gia_lich_su_VNINDEX_1D.parquet",
        columns=["time", "close"],
    )
    vni["vni_ret"] = vni["close"].pct_change()
    vni["vni_up"] = vni["vni_ret"] > 0

    panel = s1.merge(orders, on=["ticker", "time"], how="inner")
    panel = panel.merge(vni[["time", "vni_up"]], on="time", how="left")

    panel = panel[
        panel[S1_SCORE_COL].notna()
        & panel[S1_TARGET_COL].notna()
        & panel["order_volume_ratio"].notna()
    ].copy()

    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)

    # Build Volume z-score
    panel["vol_zscore"] = panel.groupby("time")["order_volume_ratio"].rank(
        method="average", pct=True
    )

    # Build Triple Storm conditions
    # 1. Liquid: vol std > 80th percentile (rolling 20d)
    panel["vol_std_20d"] = panel.groupby("ticker")["vol_zscore"].transform(
        lambda x: x.rolling(20, min_periods=5).std()
    )
    panel["liquid_80"] = panel.groupby("time")["vol_std_20d"].transform(
        lambda x: x > x.quantile(0.80)
    )

    # 2. Market down: vni_up is False
    panel["market_down"] = ~panel["vni_up"].fillna(False)

    # 3. Divergence: return direction vs volume direction disagreed
    panel["ret_1d"] = panel.groupby("ticker")[S1_SCORE_COL].shift(1)
    panel["ret_dir"] = panel["ret_1d"] > 0
    panel["vol_dir"] = panel["order_volume_ratio"] > 0
    panel["divergence"] = panel["ret_dir"] != panel["vol_dir"]

    # Triple Storm: all 3 conditions
    panel["triple_storm"] = (
        panel["liquid_80"] & panel["market_down"] & panel["divergence"]
    )

    # Single conditions for ablation
    panel["only_liquid"] = panel["liquid_80"]
    panel["only_down"] = panel["market_down"]
    panel["only_divergence"] = panel["divergence"]

    print(f"\nPanel rows: {len(panel):,}")
    print(f"Triple storm rows: {panel['triple_storm'].sum():,}")

    ic_vol = compute_ic(panel, "vol_zscore", S1_TARGET_COL)
    ic_triple = compute_ic(panel[panel["triple_storm"]], "vol_zscore", S1_TARGET_COL)

    y_vol = compute_yearly_ic(panel, "vol_zscore", S1_TARGET_COL)
    y_triple = compute_yearly_ic(
        panel[panel["triple_storm"]], "vol_zscore", S1_TARGET_COL
    )

    pos_vol = sum(1 for v in y_vol.values() if v > 0)
    pos_triple = sum(1 for v in y_triple.values() if v > 0)

    print(f"\n=== H411 Volume Triple Storm Results ===")
    print(f"Volume alone:      {ic_vol:+.5f} ({pos_vol}/{len(y_vol)} years)")
    print(f"Volume+Triple:   {ic_triple:+.5f} ({pos_triple}/{len(y_triple)} years)")

    # Ablation
    ic_only_liquid = compute_ic(panel[panel["only_liquid"]], "vol_zscore", S1_TARGET_COL)
    ic_only_down = compute_ic(panel[panel["only_down"]], "vol_zscore", S1_TARGET_COL)
    ic_only_div = compute_ic(panel[panel["only_divergence"]], "vol_zscore", S1_TARGET_COL)

    print(f"\n--- Ablation ---")
    print(f"Only liquid:    {ic_only_liquid:+.5f}")
    print(f"Only down:     {ic_only_down:+.5f}")
    print(f"Only div:       {ic_only_div:+.5f}")

    result = {
        "ic_vol": float(ic_vol),
        "ic_triple": float(ic_triple),
        "ic_only_liquid": float(ic_only_liquid),
        "ic_only_down": float(ic_only_down),
        "ic_only_div": float(ic_only_div),
        "pos_vol": pos_vol,
        "pos_triple": pos_triple,
        "triple_rows": int(panel["triple_storm"].sum()),
    }

    out_path = ROOT / "artifacts/run_summaries" / f"{BRANCH_NAME}_{MODE}.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nSaved: {out_path}")

    print(f"\n=== VERDICT ===")
    if ic_triple > ic_vol + 0.02 and pos_triple >= 5:
        print("PASSED")
    elif ic_triple > ic_vol and pos_triple >= 4:
        print("MIXED")
    else:
        print("FAILED")

    return ic_triple


if __name__ == "__main__":
    main()