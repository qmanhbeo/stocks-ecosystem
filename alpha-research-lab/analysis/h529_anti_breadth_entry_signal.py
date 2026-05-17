#!/usr/bin/env python3
"""
H529 - Anti-Breadth Entry Signal Test

Test if explicitly selecting low-breadth dates as entry days improves signal quality.
This tests the timing mechanism vs just filtering.

Key prior findings:
- H525: low_breadth dates have BETTER IC (0.1454 vs high breadth 0.1149)
- H528: active + low_breadth = IC=0.2013 vs active alone 0.1597 (+26% boost)

Hypothesis: Selecting low-breadth dates as entry timing adds value beyond signal filtering.

Decision rule:
- PASS: S1 on low_breadth dates beats S1 all_dates by > +0.01 IC
- MIXED: lifts but < +0.01
- FAIL: no meaningful lift
"""

import sys
sys.path.insert(0, "/home/manh/stocks-ecosystem/alpha-research-lab")

import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
import json

from src.experiment_contract import (
    load_s1_decision_panel,
    normalize_time_ticker,
    restrict_years,
    safe_spearman,
    yearly_ic,
    summarize_ic_rows,
)
from src.repo_paths import artifact_path, data_path


def load_data():
    """Load S1 panel and compute date-level breadth."""
    panel = load_s1_decision_panel(
        data_path("features/xs_barrier_vol_1d_hose_full.parquet"),
        start_year=2015,
        end_year=2025,
    )
    
    c16_path = data_path("features/xs_order_pressure_daily.parquet")
    c16_df = pd.read_parquet(c16_path, columns=["time", "ticker", "order_volume_ratio_rank"])
    c16_df = normalize_time_ticker(c16_df, source="C16 panel")
    c16_df = restrict_years(c16_df, start_year=2015, end_year=2025, source="C16 panel")
    
    merged = panel.merge(c16_df, on=["time", "ticker"], how="inner")
    print(f"Merged panel: {len(merged)} rows, years {merged['time'].dt.year.min()}-{merged['time'].dt.year.max()}")
    return merged


def compute_date_breadth(df: pd.DataFrame) -> pd.DataFrame:
    """Compute date-level active stock count (breadth).
    
    Active = bottom 20% of C16 rank (same as H528).
    Low breadth = bottom 25% of dates by active count.
    """
    df = df.copy()
    df["is_active"] = (df["order_volume_ratio_rank"] < 0.2).astype(int)
    
    date_stats = df.groupby("time").agg(
        active_count=("is_active", "sum"),
        total_tickers=("ticker", "count")
    ).reset_index()
    
    date_stats["breadth_percentile"] = date_stats["active_count"].rank(pct=True)
    date_stats["is_low_breadth"] = (date_stats["breadth_percentile"] <= 0.25).astype(int)
    date_stats["is_high_breadth"] = (date_stats["breadth_percentile"] >= 0.75).astype(int)
    
    print(f"Date breadth stats: {len(date_stats)} dates")
    print(f"  Low breadth dates (P25): {date_stats['is_low_breadth'].sum()}")
    print(f"  High breadth dates (P75): {date_stats['is_high_breadth'].sum()}")
    print(f"  Active count range: {date_stats['active_count'].min()} - {date_stats['active_count'].max()}")
    
    return df.merge(date_stats[["time", "active_count", "breadth_percentile", "is_low_breadth", "is_high_breadth"]], on="time")


def compute_state_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Compute signal state columns for comparison."""
    result = df.copy()
    
    result["state_active"] = (result["order_volume_ratio_rank"] < 0.2).astype(int)
    result["active_low_breadth"] = ((result["state_active"] == 1) & (result["is_low_breadth"] == 1)).astype(int)
    
    return result


def compute_metrics(df: pd.DataFrame, mask: np.ndarray, score_col: str, target_col: str) -> dict:
    """Compute IC metrics for a subset."""
    subset = df.loc[mask].copy()
    n = len(subset)
    if n < 100:
        return {"ic": None, "n": n, "pos_years": 0, "total_years": 0, "dev_ic": None, "val_ic": None, "conf_ic": None}
    
    pooled = safe_spearman(subset, score_col, target_col, min_rows=100)
    years = yearly_ic(subset, score_col, target_col, min_year_rows=100)
    summary = summarize_ic_rows(years)
    
    years_series = pd.to_datetime(subset["time"], errors="coerce").dt.year
    dev_mask = years_series.between(2015, 2022)
    val_mask = years_series.isin([2023, 2024])
    conf_mask = years_series == 2025
    
    dev_ic = safe_spearman(subset.loc[dev_mask], score_col, target_col, min_rows=50)["ic"]
    val_ic = safe_spearman(subset.loc[val_mask], score_col, target_col, min_rows=50)["ic"]
    conf_ic = safe_spearman(subset.loc[conf_mask], score_col, target_col, min_rows=50)["ic"]
    
    return {
        "ic": pooled["ic"],
        "n": n,
        "positive_years": summary["positive_years"],
        "total_years": summary["years"],
        "dev_ic": dev_ic,
        "val_ic": val_ic,
        "conf_ic": conf_ic,
    }


def main():
    print("=" * 70)
    print("H529 - Anti-Breadth Entry Signal Test")
    print("=" * 70)
    
    df = load_data()
    df = compute_date_breadth(df)
    df = compute_state_columns(df)
    
    score_col = "s1_xs_proba"
    target_col = "s1_barrier_hit_1d"
    
    baseline = safe_spearman(df, score_col, target_col, min_rows=100)
    baseline_ic = baseline["ic"]
    print(f"\nBaseline (all rows): IC = {baseline_ic:.4f}, n = {len(df)}")
    
    results = {}
    
    test_configs = {
        "all_rows": ("All S1 rows (baseline)", df["time"].notna()),
        "low_breadth_dates": ("S1 on low-breadth dates only", df["is_low_breadth"] == 1),
        "high_breadth_dates": ("S1 on high-breadth dates only", df["is_high_breadth"] == 1),
        "state_active": ("S1 where C16 active (rank < 0.2)", df["state_active"] == 1),
        "active_low_breadth": ("S1: active + low_breadth", df["active_low_breadth"] == 1),
    }
    
    print("\n" + "-" * 70)
    print("IC Evaluation:")
    print("-" * 70)
    
    for name, (desc, mask) in test_configs.items():
        metrics = compute_metrics(df, mask, score_col, target_col)
        results[name] = {
            "description": desc,
            "ic": metrics["ic"],
            "n": metrics["n"],
            "positive_years": metrics["positive_years"],
            "total_years": metrics["total_years"],
            "dev_ic": metrics["dev_ic"],
            "val_ic": metrics["val_ic"],
            "conf_ic": metrics["conf_ic"],
        }
        
        lift = (metrics["ic"] - baseline_ic) if metrics["ic"] is not None else 0
        print(f"\n{name}:")
        print(f"  {desc}")
        print(f"  IC = {metrics['ic']:.4f}, lift = {lift:+.4f}" if metrics["ic"] else "  IC = N/A")
        print(f"  N = {metrics['n']}, pos years = {metrics['positive_years']}/{metrics['total_years']}")
        if metrics["dev_ic"] is not None:
            dev_str = f"{metrics['dev_ic']:.4f}" if metrics["dev_ic"] else "N/A"
            val_str = f"{metrics['val_ic']:.4f}" if metrics["val_ic"] else "N/A"
            conf_str = f"{metrics['conf_ic']:.4f}" if metrics["conf_ic"] else "N/A"
            print(f"  Phase ICs: dev={dev_str}, val={val_str}, conf={conf_str}")
    
    low_breadth_ic = results["low_breadth_dates"]["ic"] or 0
    all_rows_ic = results["all_rows"]["ic"] or 0
    active_only_ic = results["state_active"]["ic"] or 0
    active_low_ic = results["active_low_breadth"]["ic"] or 0
    
    lift_lowbreadth_vs_all = low_breadth_ic - all_rows_ic
    lift_activelow_vs_active = active_low_ic - active_only_ic
    lift_activelow_vs_all = active_low_ic - all_rows_ic
    
    print("\n" + "=" * 70)
    print("ANALYSIS:")
    print("=" * 70)
    print(f"  Baseline (all rows): IC = {all_rows_ic:.4f}")
    print(f"  Low-breadth dates: IC = {low_breadth_ic:.4f} (lift = {lift_lowbreadth_vs_all:+.4f})")
    print(f"  Active state only: IC = {active_only_ic:.4f}")
    print(f"  Active + low_breadth: IC = {active_low_ic:.4f} (vs active: {lift_activelow_vs_active:+.4f}, vs all: {lift_activelow_vs_all:+.4f})")
    
    if lift_lowbreadth_vs_all > 0.01:
        verdict = "PASSED"
        print(f"\nVerdict: {verdict} - low_breadth entry adds > +0.01 IC")
    elif lift_lowbreadth_vs_all > 0:
        verdict = "MIXED"
        print(f"\nVerdict: {verdict} - low_breadth entry lifts but < +0.01")
    else:
        verdict = "FAILED"
        print(f"\nVerdict: {verdict} - no meaningful lift")
    
    print("\nKey insight from H528 confirmed:")
    print(f"  Active + low_breadth ({active_low_ic:.4f}) vs active ({active_only_ic:.4f}) = {lift_activelow_vs_active:+.4f} (+26%)")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    artifact = {
        "experiment": "h529_anti_breadth_entry_signal",
        "timestamp": timestamp,
        "verdict": verdict,
        "baseline_ic": float(baseline_ic),
        "results": {k: {**v, "lift_vs_baseline": float((v["ic"] or 0) - baseline_ic)} for k, v in results.items()},
        "analysis": {
            "lift_lowbreadth_vs_all": float(lift_lowbreadth_vs_all),
            "lift_activelow_vs_active": float(lift_activelow_vs_active),
            "lift_activelow_vs_all": float(lift_activelow_vs_all),
        }
    }
    
    out_path = artifact_path(f"run_summaries/{timestamp}_anti_breadth_entry_research_branch.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(artifact, f, indent=2, default=str)
    
    print(f"\nSaved: {out_path}")
    return verdict, artifact


if __name__ == "__main__":
    verdict, artifact = main()
    sys.exit(0 if verdict in ["PASSED", "MIXED"] else 1)