#!/usr/bin/env python3
"""
H531 - Breadth-Capacity Intersection Test

Test the intersection of two strong signals:
- tight_capacity (H474): order count percentile ≤ 0.2 → IC=0.184, lift +0.065
- low_breadth (H529): bottom 25% dates by active count → IC=0.1542, lift +0.0266

Hypothesis: The intersection of hidden demand (tight capacity) + regime amplifier 
(low breadth) captures stronger alpha than either alone.

Decision rule:
- PASS: tight_capacity × low_breadth beats best single (> +0.01 IC lift)
- MIXED: lift but < +0.01
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
    """Load S1 panel with C16 and order stats."""
    panel = load_s1_decision_panel(
        data_path("features/xs_barrier_vol_1d_hose_full.parquet"),
        start_year=2015,
        end_year=2025,
    )
    
    c16_path = data_path("features/xs_order_pressure_daily.parquet")
    c16_df = pd.read_parquet(c16_path, columns=["time", "ticker", "order_volume_ratio_rank"])
    c16_df = normalize_time_ticker(c16_df, source="C16 panel")
    c16_df = restrict_years(c16_df, start_year=2015, end_year=2025, source="C16 panel")
    
    order_stats_path = data_path("order_stats/cafef/order_stats_daily.parquet")
    os_df = pd.read_parquet(order_stats_path, columns=["date", "ticker", "buy_order_count", "sell_order_count"])
    os_df = os_df.rename(columns={"date": "time"})
    os_df["time"] = pd.to_datetime(os_df["time"]).dt.normalize()
    os_df = normalize_time_ticker(os_df, source="order_stats")
    os_df = restrict_years(os_df, start_year=2015, end_year=2025, source="order_stats")
    
    merged = panel.merge(c16_df, on=["time", "ticker"], how="inner")
    merged = merged.merge(os_df, on=["time", "ticker"], how="inner")
    print(f"Merged panel: {len(merged)} rows, years {merged['time'].dt.year.min()}-{merged['time'].dt.year.max()}")
    return merged


def compute_breadth(df: pd.DataFrame) -> pd.DataFrame:
    """Compute date-level breadth (active stock count)."""
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


def compute_capacity(df: pd.DataFrame) -> pd.DataFrame:
    """Compute ticker-level capacity (order count percentile)."""
    df = df.copy()
    df["total_order_count"] = df["buy_order_count"].fillna(0) + df["sell_order_count"].fillna(0)
    
    cap_rank = df.groupby("time", sort=False)["total_order_count"].rank(method="average", pct=True)
    df["tight_capacity"] = (cap_rank <= 0.2).astype(int)
    df["mid_capacity"] = ((cap_rank > 0.3) & (cap_rank < 0.7)).astype(int)
    df["loose_capacity"] = (cap_rank >= 0.8).astype(int)
    
    print(f"Capacity stats:")
    print(f"  Tight capacity (Q1): {df['tight_capacity'].sum()} rows")
    print(f"  Mid capacity: {df['mid_capacity'].sum()} rows")
    print(f"  Loose capacity (Q5): {df['loose_capacity'].sum()} rows")
    
    return df


def compute_intersection_states(df: pd.DataFrame) -> pd.DataFrame:
    """Compute intersection states."""
    result = df.copy()
    
    result["tight_lowbreadth"] = ((result["tight_capacity"] == 1) & (result["is_low_breadth"] == 1)).astype(int)
    result["tight_highbreadth"] = ((result["tight_capacity"] == 1) & (result["is_high_breadth"] == 1)).astype(int)
    result["loose_lowbreadth"] = ((result["loose_capacity"] == 1) & (result["is_low_breadth"] == 1)).astype(int)
    result["loose_highbreadth"] = ((result["loose_capacity"] == 1) & (result["is_high_breadth"] == 1)).astype(int)
    
    print(f"\nIntersection stats:")
    print(f"  tight + low_breadth: {result['tight_lowbreadth'].sum()} rows")
    print(f"  tight + high_breadth: {result['tight_highbreadth'].sum()} rows")
    print(f"  loose + low_breadth: {result['loose_lowbreadth'].sum()} rows")
    print(f"  loose + high_breadth: {result['loose_highbreadth'].sum()} rows")
    
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
    print("H531 - Breadth-Capacity Intersection Test")
    print("=" * 70)
    
    df = load_data()
    df = compute_breadth(df)
    df = compute_capacity(df)
    df = compute_intersection_states(df)
    
    score_col = "s1_xs_proba"
    target_col = "s1_barrier_hit_1d"
    
    baseline = safe_spearman(df, score_col, target_col, min_rows=100)
    baseline_ic = baseline["ic"]
    print(f"\nBaseline (all rows): IC = {baseline_ic:.4f}, n = {len(df)}")
    
    results = {}
    
    test_configs = {
        "all_rows": ("All S1 rows (baseline)", df["time"].notna()),
        "tight_capacity": ("H474: tight capacity Q1", df["tight_capacity"] == 1),
        "low_breadth": ("H529: low-breadth dates", df["is_low_breadth"] == 1),
        "tight_lowbreadth": ("INTERSECTION: tight + low_breadth", df["tight_lowbreadth"] == 1),
        "tight_highbreadth": ("tight + high_breadth (control)", df["tight_highbreadth"] == 1),
        "loose_lowbreadth": ("loose + low_breadth (control)", df["loose_lowbreadth"] == 1),
        "loose_highbreadth": ("loose + high_breadth (control)", df["loose_highbreadth"] == 1),
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
    
    tight_ic = results["tight_capacity"]["ic"] or 0
    lowbreadth_ic = results["low_breadth"]["ic"] or 0
    intersection_ic = results["tight_lowbreadth"]["ic"] or 0
    
    best_single = max(tight_ic, lowbreadth_ic)
    lift_vs_best = intersection_ic - best_single
    lift_vs_baseline = intersection_ic - baseline_ic
    
    print("\n" + "=" * 70)
    print("ANALYSIS:")
    print("=" * 70)
    print(f"  Baseline (all rows): IC = {baseline_ic:.4f}")
    print(f"  tight_capacity (H474): IC = {tight_ic:.4f}")
    print(f"  low_breadth (H529): IC = {lowbreadth_ic:.4f}")
    print(f"  INTERSECTION (tight + low_breadth): IC = {intersection_ic:.4f}")
    print(f"  Lift vs best single: {lift_vs_best:+.4f}")
    print(f"  Lift vs baseline: {lift_vs_baseline:+.4f}")
    
    if lift_vs_best > 0.01:
        verdict = "PASSED"
        print(f"\nVerdict: {verdict} - intersection beats best single by > +0.01")
    elif lift_vs_best > 0:
        verdict = "MIXED"
        print(f"\nVerdict: {verdict} - intersection lifts but < +0.01 vs best single")
    else:
        verdict = "FAILED"
        print(f"\nVerdict: {verdict} - no meaningful lift vs best single")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    artifact = {
        "experiment": "h531_breadth_capacity_intersection",
        "timestamp": timestamp,
        "verdict": verdict,
        "baseline_ic": float(baseline_ic),
        "results": {k: {**v, "lift_vs_baseline": float((v["ic"] or 0) - baseline_ic)} for k, v in results.items()},
        "analysis": {
            "tight_capacity_ic": float(tight_ic),
            "low_breadth_ic": float(lowbreadth_ic),
            "intersection_ic": float(intersection_ic),
            "lift_vs_best_single": float(lift_vs_best),
            "lift_vs_baseline": float(lift_vs_baseline),
        }
    }
    
    out_path = artifact_path(f"run_summaries/{timestamp}_breadth_capacity_intersection_research_branch.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(artifact, f, indent=2, default=str)
    
    print(f"\nSaved: {out_path}")
    return verdict, artifact


if __name__ == "__main__":
    verdict, artifact = main()
    sys.exit(0 if verdict in ["PASSED", "MIXED"] else 1)