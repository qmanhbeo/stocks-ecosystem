"""
H406: Noether Flow Break (Conservation Law Residual)
Test whether expected price move from flow predicts actual - the residual is the alpha.
Uses regression-residual approach: train model, test residuals.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TARGET_COL = "actual"
SCORE_COL = "xs_proba"
BRANCH_NAME = "noether_flow_break"
MODE = "research_branch"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H406 Noether Flow Break test")
    parser.add_argument("--s1-path", type=str, default=str(ROOT / "data/features/xs_barrier_vol_1d_hose_full.parquet"))
    parser.add_argument("--start-year", type=int, default=2018)
    parser.add_argument("--end-year", type=int, default=2025)
    return parser.parse_args()


def compute_ic(panel: pd.DataFrame, score_col: str, target_col: str) -> float:
    valid = panel[[score_col, target_col]].dropna()
    if len(valid) < 50:
        return np.nan
    ic, _ = spearmanr(valid[score_col], valid[target_col])
    return ic


def compute_yearly_ics(panel: pd.DataFrame, score_col: str, target_col: str) -> dict[int, float]:
    panel = panel.copy()
    panel["year"] = pd.to_datetime(panel["time"]).dt.year
    ics = {}
    for year, year_df in panel.groupby("year"):
        ic = compute_ic(year_df, score_col, target_col)
        ics[year] = ic
    return ics


def main():
    args = parse_args()
    
    print("Loading S1 panel...")
    panel = pd.read_parquet(
        args.s1_path,
        columns=["ticker", "time", SCORE_COL, TARGET_COL],
    )
    panel = panel[panel["time"] >= f"{args.start_year}-01-01"]
    panel = panel[panel["time"] <= f"{args.end_year}-12-31"]
    
    print("Loading order stats...")
    order_stats = pd.read_parquet(
        ROOT / "data/order_stats/cafef/order_stats_daily.parquet",
        columns=["ticker", "date", "buy_order_count", "sell_order_count", 
                "buy_order_volume", "sell_order_volume",
                "avg_buy_order_volume", "avg_sell_order_volume"],
    )
    order_stats["time"] = pd.to_datetime(order_stats["date"])
    order_stats = order_stats.drop(columns=["date"])
    panel = panel.merge(order_stats, on=["ticker", "time"], how="left")
    
    panel = panel[
        panel[SCORE_COL].notna() & 
        panel[TARGET_COL].notna()
    ].copy()
    
    panel["buy_count"] = panel["buy_order_count"].fillna(0)
    panel["sell_count"] = panel["sell_order_count"].fillna(0)
    panel["buy_vol"] = panel["buy_order_volume"].fillna(0)
    panel["sell_vol"] = panel["sell_order_volume"].fillna(0)
    panel["avg_buy"] = panel["avg_buy_order_volume"].fillna(0)
    panel["avg_sell"] = panel["avg_sell_order_volume"].fillna(0)
    
    net_count = panel["buy_count"] - panel["sell_count"]
    net_vol = panel["buy_vol"] - panel["sell_vol"]
    avg_diff = panel["avg_buy"] - panel["avg_sell"]
    
    panel["count_imbalance"] = net_count / (panel["buy_count"] + panel["sell_count"] + 1)
    panel["vol_imbalance"] = net_vol / (panel["buy_vol"] + panel["sell_vol"] + 1)
    panel["avg_size_diff"] = avg_diff
    
    train_panel = panel[panel["time"] < f"{args.end_year-2}-01-01"]
    test_panel = panel[panel["time"] >= f"{args.end_year-2}-01-01"]
    
    from sklearn.linear_model import LinearRegression
    
    features = ["count_imbalance", "vol_imbalance", "avg_size_diff"]
    X_train = train_panel[features].fillna(0)
    y_train = train_panel[TARGET_COL]
    
    model = LinearRegression()
    model.fit(X_train, y_train)
    
    X_test = test_panel[features].fillna(0)
    test_panel["expected_return"] = model.predict(X_test)
    test_panel["residual"] = test_panel[TARGET_COL] - test_panel["expected_return"]
    
    test_panel["forward_target"] = test_panel.groupby("ticker")[TARGET_COL].shift(-1)
    test_panel = test_panel.dropna(subset=["forward_target"])
    
    ic_expected = compute_ic(test_panel, "expected_return", "forward_target")
    ic_residual = compute_ic(test_panel, "residual", "forward_target")
    ic_count = compute_ic(test_panel, "count_imbalance", "forward_target")
    ic_vol = compute_ic(test_panel, "vol_imbalance", "forward_target")
    ic_avg = compute_ic(test_panel, "avg_size_diff", "forward_target")
    
    yearly_expected = compute_yearly_ics(test_panel, "expected_return", "forward_target")
    yearly_residual = compute_yearly_ics(test_panel, "residual", "forward_target")
    
    print(f"\n=== H406 Noether Flow Break Results ===")
    print(f"Test period: {args.end_year-2}-{args.end_year}")
    print(f"\n--- Overall IC ---")
    print(f"  Expected (from flow):  {ic_expected:+.5f}")
    print(f"  Residual (alpha):     {ic_residual:+.5f}")
    print(f"  Count imbalance:      {ic_count:+.5f}")
    print(f"  Vol imbalance:       {ic_vol:+.5f}")
    print(f"  Avg size diff:      {ic_avg:+.5f}")
    
    print(f"\n--- Expected by year ---")
    for yr, ic in sorted(yearly_expected.items()):
        print(f"    {yr}: {ic:+.5f}")
    
    print(f"\n--- Residual by year ---")
    for yr, ic in sorted(yearly_residual.items()):
        print(f"    {yr}: {ic:+.5f}")
    
    pos_expected = sum(1 for ic in yearly_expected.values() if ic > 0)
    pos_residual = sum(1 for ic in yearly_residual.values() if ic > 0)
    print(f"\n--- Positive years ---")
    print(f"  Expected: {pos_expected}/{len(yearly_expected)}")
    print(f"  Residual: {pos_residual}/{len(yearly_residual)}")
    
    result = {
        "expected_ic": ic_expected,
        "residual_ic": ic_residual,
        "count_imbalance_ic": ic_count,
        "vol_imbalance_ic": ic_vol,
        "avg_size_diff_ic": ic_avg,
        "expected_yearly_ic": yearly_expected,
        "residual_yearly_ic": yearly_residual,
    }
    
    artifact_path = (
        ROOT / "artifacts/run_summaries" /
        f"{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}_{BRANCH_NAME}_{MODE}.json"
    )
    
    import json
    with open(artifact_path, "w") as f:
        json.dump(result, f, indent=2)
    
    print(f"\nSaved: {artifact_path}")
    
    print(f"\n=== VERDICT ===")
    if abs(ic_residual) > 0.01 and pos_residual >= 2:
        if ic_residual > ic_expected:
            print("PASSED: Residual > Expected - conservation break is alpha")
        else:
            print("MIXED: Residual exists but not greater than expected")
    else:
        print("FAILED: No conservation break signal")


if __name__ == "__main__":
    main()