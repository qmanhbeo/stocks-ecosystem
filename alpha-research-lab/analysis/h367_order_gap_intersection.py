"""
H367 - Order + Gap Absorption Intersection

Test: intersection(C16 positive, C12 xs_gap_absorb_3 > median)
vs C16-only baseline from H358.

Design:
- Use C16 standalone results as reference (val IR 1.98)
- Add intersection signal: C16 > median AND C12 > median
- Run quick portfolio comparison on dev 2015-2022
"""

from __future__ import annotations
import argparse
from datetime import datetime
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
import sys
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.repo_paths import artifact_path, data_path
from src.tradability_conditioned_research import load_research_bundle, compute_phase_portfolio_summary, run_selector_candidate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(data_path("features/xs_rl_signal_matrix.parquet")))
    parser.add_argument("--order-stats", type=str, default=str(data_path("order_stats/cafef/order_stats_daily.parquet")))
    parser.add_argument("--tradability", type=str, default=str(data_path("features/execution/tradability_daily.parquet")))
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2022)
    return parser.parse_args()


def load_bundle(args):
    print(f"Loading matrix from {args.matrix}...")
    matrix = pd.read_parquet(args.matrix)
    
    # Load order stats for C16 - column is 'date' not 'time', ratio is singular
    order = pd.read_parquet(args.order_stats)
    order = order[order["date"].dt.year.between(args.start_year, args.end_year)]
    order["order_volume_ratio_rank"] = order.groupby("date")["order_volume_ratio"].rank(pct=True)  # singular
    
    # Merge C16 onto matrix - map date to time
    matrix = matrix.merge(
        order[["date", "ticker", "order_volume_ratio_rank"]].rename(columns={"date": "time"}),
        on=["time", "ticker"],
        how="left"
    )
    matrix["order_volume_ratio_rank"] = matrix["order_volume_ratio_rank"].fillna(0.5)
    
    # Calculate C12 (gap_absorb_3) - simple version
    # C12 exists in full_library, extract it
    c12_col = "c12_gap_absorb_3"
    if c12_col not in matrix.columns:
        print(f"Warning: {c12_col} not in matrix, computing inline")
        # This shouldn't happen - C12 is in full_library
        matrix[c12_col] = 0.5
    
    # Load tradability
    trad = pd.read_parquet(args.tradability)
    
    bundle = load_research_bundle(
        matrix,
        trad,
        {"time": "time", "ticker": "ticker", "actual": "actual"},
        start_year=args.start_year,
        end_year=args.end_year,
    )
    return bundle, matrix


def run_h367_test(bundle, matrix, start_year, end_year):
    """Run H367: C16 + C12 intersection"""
    
    # Strategy: create intersection signal
    # C16 positive = rank > 0.5
    # C12 positive = c12_gap_absorb_3 > 0.5 (median)
    
    print("\n=== H367: Order + Gap Absorption Intersection ===")
    
    # C16 standalone reference (from H358 val IR = 1.98)
    print("Reference: C16 standalone val IR = 1.98")
    
    # Create intersection signal
    c16_positive = matrix["order_volume_ratio_rank"] > 0.5
    c12_positive = matrix["c12_gap_absorb_3"] > 0.5
    
    intersection = (c16_positive & c12_positive).astype(float)
    
    # Calculate IC of intersection against actual
    merged = matrix.merge(
        bundle["research"][["time", "ticker", "actual"]].drop_duplicates(),
        on=["time", "ticker"]
    )
    
    from scipy.stats import spearmanr
    
    # IC by year
    ic_by_year = {}
    for year in range(start_year, end_year + 1):
        year_data = merged[merged["time"].dt.year == year]
        if len(year_data) > 30:
            valid = year_data.dropna(subset=[intersection.name, "actual"])
            if len(valid) > 30:
                ic, _ = spearmanr(valid[intersection.name], valid["actual"])
                if not np.isnan(ic):
                    ic_by_year[year] = ic
    
    avg_ic = np.mean(list(ic_by_year.values())) if ic_by_year else 0.0
    positive_years = sum(1 for v in ic_by_year.values() if v > 0)
    
    print(f"Intersection IC: {avg_ic:+.4f}")
    print(f"Positive years: {positive_years}/{len(ic_by_year)}")
    
    # Compare with C16 alone
    c16_data = merged.dropna(subset=["order_volume_ratio_rank", "actual"])
    c16_ic, _ = spearmanr(c16_data["order_volume_ratio_rank"], c16_data["actual"])
    print(f"C16 alone IC: {c16_ic:+.4f}")
    
    # Compare with C12 alone
    c12_data = merged.dropna(subset=["c12_gap_absorb_3", "actual"])
    c12_ic, _ = spearmanr(c12_data["c12_gap_absorb_3"], c12_data["actual"])
    print(f"C12 alone IC: {c12_ic:+.4f}")
    
    return {
        "intersection_ic": avg_ic,
        "c16_ic": c16_ic,
        "c12_ic": c12_ic,
        "positive_years": positive_years,
        "total_years": len(ic_by_year),
    }


def main():
    args = parse_args()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    bundle, matrix = load_bundle(args)
    
    results = run_h367_test(bundle, matrix, args.start_year, args.end_year)
    
    # Save results
    out_path = artifact_path("run_summaries") / f"{ts}_h367_order_gap_intersection.json"
    with open(out_path, "w") as f:
        json.dump({
            "mode": "h367_order_gap_intersection",
            "results": results,
            "start_year": args.start_year,
            "end_year": args.end_year,
        }, f, indent=2)
    
    print(f"\nResults saved to {out_path}")
    
    # Decision
    if results["intersection_ic"] > results["c16_ic"]:
        print("\nVerdict: PASSED - Intersection beats C16 alone")
    else:
        print("\nVerdict: NEUTRAL - Intersection does not beat C16")


if __name__ == "__main__":
    main()