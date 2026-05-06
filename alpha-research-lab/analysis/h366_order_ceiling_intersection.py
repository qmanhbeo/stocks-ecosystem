"""
H366 - Order + Ceiling Intersection (Simple IC Test)

Quick test: Does C16 + C7 (ceiling count) intersection beat C16 alone?
"""

from __future__ import annotations
from datetime import datetime
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Load data
    print("Loading matrix...")
    matrix = pd.read_parquet(ROOT / "data/features/xs_rl_signal_matrix.parquet")
    
    print("Loading order stats...")
    order = pd.read_parquet(ROOT / "data/order_stats/cafef/order_stats_daily.parquet")
    order["date"] = pd.to_datetime(order["date"])
    order["order_volume_ratio"] = (order["buy_order_volume"] - order["sell_order_volume"]) / (order["buy_order_volume"] + order["sell_order_volume"])
    order["order_volume_ratio_rank"] = order.groupby("date")["order_volume_ratio"].rank(pct=True)
    order = order.rename(columns={"date": "time"})
    
    # Merge C16 onto matrix
    matrix = matrix.merge(
        order[["time", "ticker", "order_volume_ratio_rank"]],
        on=["time", "ticker"],
        how="left"
    )
    matrix["order_volume_ratio_rank"] = matrix["order_volume_ratio_rank"].fillna(0.5)
    
    # Test 2015-2022
    years = list(range(2015, 2023))
    matrix = matrix[matrix["time"].dt.year.isin(years)]
    
    print(f"Matrix rows: {len(matrix):,}")
    
    # Calculate ICs
    def yearly_ic(df, col):
        ics = {}
        for year in years:
            year_data = df[df["time"].dt.year == year].dropna(subset=[col, "actual"])
            if len(year_data) > 30:
                ic, _ = spearmanr(year_data[col], year_data["actual"])
                if not np.isnan(ic):
                    ics[year] = ic
        return ics
    
    # C16 standalone IC
    c16_ics = yearly_ic(matrix, "order_volume_ratio_rank")
    c16_ic = np.mean(list(c16_ics.values()))
    c16_pos = sum(1 for v in c16_ics.values() if v > 0)
    
    print(f"\nC16 standalone (order pressure):")
    print(f"  IC: {c16_ic:+.4f}")
    print(f"  Positive years: {c16_pos}/{len(c16_ics)}")
    
    # C7 standalone IC
    c7_ics = yearly_ic(matrix, "c7_ceiling_count_5d")
    c7_ic = np.mean(list(c7_ics.values()))
    c7_pos = sum(1 for v in c7_ics.values() if v > 0)
    
    print(f"\nC7 standalone (ceiling count):")
    print(f"  IC: {c7_ic:+.4f}")
    print(f"  Positive years: {c7_pos}/{len(c7_ics)}")
    
    # Intersection: C16 > 0.5 AND C7 > 0.5 (has hit ceiling in past 5d)
    matrix["intersection"] = ((matrix["order_volume_ratio_rank"] > 0.5) & (matrix["c7_ceiling_count_5d"] > 0)).astype(float)
    int_ics = yearly_ic(matrix, "intersection")
    int_ic = np.mean(list(int_ics.values()))
    int_pos = sum(1 for v in int_ics.values() if v > 0)
    
    print(f"\nIntersection (C16 > 0.5 AND C7 > 0):")
    print(f"  IC: {int_ic:+.4f}")
    print(f"  Positive years: {int_pos}/{len(int_ics)}")
    
    # Multiplicative: C16 * C7
    matrix["multiply"] = matrix["order_volume_ratio_rank"] * matrix["c7_ceiling_count_5d"]
    mult_ics = yearly_ic(matrix, "multiply")
    mult_ic = np.mean(list(mult_ics.values()))
    mult_pos = sum(1 for v in mult_ics.values() if v > 0)
    
    print(f"\nMultiplicative (C16 * C7):")
    print(f"  IC: {mult_ic:+.4f}")
    print(f"  Positive years: {mult_pos}/{len(mult_ics)}")
    
    # Decision
    result = {
        "c16_standalone": {"ic": c16_ic, "pos_years": c16_pos},
        "c7_standalone": {"ic": c7_ic, "pos_years": c7_pos},
        "intersection_and": {"ic": int_ic, "pos_years": int_pos},
        "multiplicative": {"ic": mult_ic, "pos_years": mult_pos},
    }
    
    best = max(result.items(), key=lambda x: x[1]["ic"])
    print(f"\nBest: {best[0]} with IC {best[1]['ic']:+.4f}")
    
    # Verdict
    if int_ic > c16_ic and mult_ic > c16_ic:
        verdict = "PASSED"
        msg = "Intersection improves C16"
    elif int_ic < c16_ic and mult_ic < c16_ic:
        verdict = "FAILED"
        msg = "Both methods underperform C16 alone"
    else:
        verdict = "MIXED"
        msg = "Mixed results - see details"
    
    print(f"\nVerdict: {verdict} - {msg}")
    
    # Save
    out_path = ROOT / "artifacts/run_summaries" / f"{ts}_h366_order_ceiling_intersection.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"mode": "h366", "results": result, "verdict": verdict, "message": msg}, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
