#!/usr/bin/env python3
"""
H525 - Cross-Sectional Breadth as Regime Signal

Test if date-level active-stock density (% of market in C23/C24) predicts forward IC.
When many stocks activate together, it may be a regime signal.

Hypothesis: High breadth (many stocks in active state) = strong regime, different IC than low breadth.
"""

import sys
sys.path.insert(0, "/home/manh/stocks-ecosystem/alpha-research-lab")

import numpy as np
import pandas as pd
from datetime import datetime
from scipy.stats import spearmanr
from pathlib import Path

from src.experiment_contract import (
    safe_spearman,
    yearly_ic,
    summarize_ic_rows,
    normalize_time_ticker,
    restrict_years,
    require_columns,
)
from src.repo_paths import artifact_path, data_path


def load_signals() -> pd.DataFrame:
    """Load S1 and C16 signals."""
    s1_path = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
    s1_df = pd.read_parquet(s1_path, columns=["time", "ticker", "xs_proba", "actual"])
    s1_df = normalize_time_ticker(s1_df, source="S1 panel")
    s1_df = restrict_years(s1_df, start_year=2015, end_year=2025, source="S1 panel")
    s1_df = s1_df.rename(columns={"xs_proba": "s1_xs_proba", "actual": "s1_barrier_hit_1d"})
    
    c16_path = data_path("features/xs_order_pressure_daily.parquet")
    c16_cols = ["time", "ticker", "order_volume_ratio_rank"]
    c16_df = pd.read_parquet(c16_path, columns=c16_cols)
    c16_df = normalize_time_ticker(c16_df, source="C16 panel")
    c16_df = restrict_years(c16_df, start_year=2015, end_year=2025, source="C16 panel")
    
    df = s1_df.merge(c16_df, on=["time", "ticker"], how="inner")
    print(f"Merged panel: {len(df)} rows, years {df['time'].dt.year.min()}-{df['time'].dt.year.max()}")
    return df


def compute_date_breadth(df: pd.DataFrame) -> pd.DataFrame:
    """Compute date-level active-stock density."""
    result = df.copy()
    
    # Create active state flags
    rank = result["order_volume_ratio_rank"]
    result["is_active"] = (rank < 0.25).astype(int)  # Bottom 25% = active states (router, amplified, onset)
    
    # Compute per-date breadth (fraction of tickers in active state)
    date_stats = result.groupby("time").agg(
        total_tickers=("ticker", "count"),
        active_count=("is_active", "sum"),
        active_fraction=("is_active", "mean")
    ).reset_index()
    
    # Merge back to panel
    result = result.merge(date_stats, on="time", how="left")
    
    # Create breadth quintiles
    result["breadth_quintile"] = pd.qcut(
        result["active_fraction"], 
        q=5, 
        labels=[1, 2, 3, 4, 5],
        duplicates="drop"
    ).astype(float)
    
    # Also create high/low binary (top 20% vs bottom 20%)
    threshold_high = result["active_fraction"].quantile(0.8)
    threshold_low = result["active_fraction"].quantile(0.2)
    result["high_breadth"] = (result["active_fraction"] >= threshold_high).astype(int)
    result["low_breadth"] = (result["active_fraction"] <= threshold_low).astype(int)
    
    print(f"Breadth range: {result['active_fraction'].min():.3f} - {result['active_fraction'].max():.3f}")
    print(f"High breadth threshold (P80): {threshold_high:.3f}")
    print(f"Low breadth threshold (P20): {threshold_low:.3f}")
    
    return result


def evaluate_regime(df: pd.DataFrame, regime_col: str, score_col: str, target_col: str, 
                   min_rows: int) -> dict:
    """Evaluate IC for a regime."""
    require_columns(df, [regime_col, score_col, target_col], context=f"regime {regime_col}")
    
    subset = df.loc[df[regime_col] == 1].copy()
    if len(subset) < min_rows:
        return {"regime": regime_col, "rows": len(subset), "ic": None}
    
    pooled = safe_spearman(subset, score_col, target_col, min_rows=min_rows)
    years = yearly_ic(subset, score_col, target_col, min_year_rows=min_rows)
    summary = summarize_ic_rows(years)
    
    # Phase IC
    years_series = pd.to_datetime(subset["time"], errors="coerce").dt.year
    dev_subset = subset.loc[years_series.between(2015, 2022)]
    val_subset = subset.loc[years_series.isin([2023, 2024])]
    conf_subset = subset.loc[years_series == 2025]
    
    dev_ic = safe_spearman(dev_subset, score_col, target_col, min_rows=min_rows)["ic"]
    val_ic = safe_spearman(val_subset, score_col, target_col, min_rows=min_rows)["ic"]
    conf_ic = safe_spearman(conf_subset, score_col, target_col, min_rows=min_rows)["ic"]
    
    return {
        "regime": regime_col,
        "pooled_rows": pooled["rows"],
        "pooled_ic": pooled["ic"],
        "positive_years": summary["positive_years"],
        "total_years": summary["years"],
        "dev_ic": dev_ic,
        "validation_ic": val_ic,
        "confirmation_ic": conf_ic,
    }


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = artifact_path("run_summaries")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("Loading signals...")
    df = load_signals()
    
    print("\nComputing date-level breadth...")
    df = compute_date_breadth(df)
    
    score_col = "s1_xs_proba"
    target_col = "s1_barrier_hit_1d"
    min_rows = 500
    
    results = []
    
    # Baseline: all rows
    baseline = safe_spearman(df, score_col, target_col, min_rows=min_rows)
    baseline_years = yearly_ic(df, score_col, target_col, min_year_rows=min_rows)
    baseline_summary = summarize_ic_rows(baseline_years)
    results.append({
        "regime": "all_rows_baseline",
        "pooled_rows": baseline["rows"],
        "pooled_ic": baseline["ic"],
        "positive_years": baseline_summary["positive_years"],
        "total_years": baseline_summary["years"],
    })
    print(f"\nBaseline: IC={baseline['ic']:.4f}, rows={baseline['rows']}")
    
    # Test breadth quintiles
    print("\n--- Breadth Quintiles ---")
    for q in [1, 2, 3, 4, 5]:
        result = evaluate_regime(df, "breadth_quintile", score_col, target_col, min_rows)
        if result["pooled_ic"] is not None:
            results.append(result)
            print(f"Q{q} (low to high breadth): IC={result['pooled_ic']:.4f}, rows={result['pooled_rows']}, pos={result['positive_years']}/{result['total_years']}")
    
    # Test high vs low breadth
    print("\n--- High vs Low Breadth ---")
    high_result = evaluate_regime(df, "high_breadth", score_col, target_col, min_rows)
    low_result = evaluate_regime(df, "low_breadth", score_col, target_col, min_rows)
    
    if high_result["pooled_ic"] is not None:
        results.append(high_result)
        print(f"High breadth: IC={high_result['pooled_ic']:.4f}, rows={high_result['pooled_rows']}, pos={high_result['positive_years']}/{high_result['total_years']}")
    if low_result["pooled_ic"] is not None:
        results.append(low_result)
        print(f"Low breadth: IC={low_result['pooled_ic']:.4f}, rows={low_result['pooled_rows']}, pos={low_result['positive_years']}/{low_result['total_years']}")
    
    # Compute lift: high vs low
    if high_result.get("pooled_ic") and low_result.get("pooled_ic"):
        lift = high_result["pooled_ic"] - low_result["pooled_ic"]
        print(f"Lift (high - low): {lift:+.4f}")
    else:
        lift = None
    
    # Find best quintile
    quintile_results = [r for r in results if "breadth_quintile" in r.get("regime", "")]
    if quintile_results:
        best_q = max(quintile_results, key=lambda x: x.get("pooled_ic") or 0)
        print(f"\nBest quintile: Q{best_q.get('regime', '').split('_')[-1]} with IC={best_q.get('pooled_ic'):.4f}")
    
    # Baseline lift for best regimes
    baseline_ic = baseline["ic"]
    if high_result.get("pooled_ic"):
        high_lift = high_result["pooled_ic"] - baseline_ic
        print(f"Lift vs baseline (high breadth): {high_lift:+.4f}")
        print(f"  Phase ICs: dev={high_result.get('dev_ic', 'N/A'):.4f}, val={high_result.get('validation_ic', 'N/A'):.4f}, conf={high_result.get('confirmation_ic', 'N/A'):.4f}")
    if low_result.get("pooled_ic"):
        low_lift = low_result["pooled_ic"] - baseline_ic
        print(f"Lift vs baseline (low breadth): {low_lift:+.4f}")
    
    # Save results
    results_df = pd.DataFrame(results)
    results_path = output_dir / f"{ts}_breadth_regime_results.parquet"
    results_df.to_parquet(results_path, index=False)
    print(f"\nSaved results to {results_path}")
    
    # Write JSON summary
    import json
    summary = {
        "hypothesis": "Cross-Sectional Breadth as Regime Signal - date-level active-stock density predicts forward IC",
        "baseline_ic": baseline_ic,
        "high_breadth_ic": high_result.get("pooled_ic"),
        "low_breadth_ic": low_result.get("pooled_ic"),
        "lift_high_vs_low": lift,
        "lift_high_vs_baseline": high_lift if high_result.get("pooled_ic") else None,
        "best_quintile": best_q.get("regime") if quintile_results else None,
        "best_quintile_ic": best_q.get("pooled_ic") if quintile_results else None,
    }
    
    if high_result.get("pooled_ic"):
        summary["phase_ic"] = {
            "dev": high_result.get("dev_ic"),
            "validation": high_result.get("validation_ic"),
            "confirmation": high_result.get("confirmation_ic"),
        }
    
    summary_path = output_dir / f"{ts}_cross_sectional_breadth_research_branch.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Saved summary to {summary_path}")
    
    return summary


if __name__ == "__main__":
    main()