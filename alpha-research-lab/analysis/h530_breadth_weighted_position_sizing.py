#!/usr/bin/env python3
"""
H530 - Breadth-Weighted Position Sizing Test

Test if continuous 1/breadth weighting adds value beyond the discrete binary filter.
Make H525/H529's discrete effect continuous.

Key prior findings:
- H529: low_breadth_dates IC=0.1542 vs baseline 0.1277 (+0.0266 lift)
- H529: high_breadth_dates IC=0.1085 vs baseline (-0.0191)
- Binary low vs high breadth gives +0.0457 IC difference

Hypothesis: Continuous 1/breadth weighting captures more signal than binary filter.

Decision rule:
- PASS: weighted_s1 IC > binary_low_breadth IC + 0.01
- MIXED: weighted > baseline but not > binary + 0.01
- FAIL: weighted <= baseline
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
    """Compute date-level active stock count (breadth)."""
    df = df.copy()
    df["is_active"] = (df["order_volume_ratio_rank"] < 0.2).astype(int)
    
    date_stats = df.groupby("time").agg(
        active_count=("is_active", "sum"),
        total_tickers=("ticker", "count")
    ).reset_index()
    
    date_stats["active_fraction"] = date_stats["active_count"] / date_stats["total_tickers"]
    date_stats["inv_breadth_weight"] = 1 / (date_stats["active_fraction"] + 0.01)
    date_stats["inv_breadth_weight"] = date_stats["inv_breadth_weight"] / date_stats["inv_breadth_weight"].mean()
    
    date_stats["breadth_percentile"] = date_stats["active_fraction"].rank(pct=True)
    date_stats["is_low_breadth"] = (date_stats["breadth_percentile"] <= 0.25).astype(int)
    date_stats["is_high_breadth"] = (date_stats["breadth_percentile"] >= 0.75).astype(int)
    
    print(f"Date breadth stats: {len(date_stats)} dates")
    print(f"  Active fraction range: {date_stats['active_fraction'].min():.4f} - {date_stats['active_fraction'].max():.4f}")
    print(f"  Inv-breadth weight range: {date_stats['inv_breadth_weight'].min():.4f} - {date_stats['inv_breadth_weight'].max():.4f}")
    
    return df.merge(date_stats[["time", "active_fraction", "inv_breadth_weight", "is_low_breadth", "is_high_breadth"]], on="time")


def compute_weighted_score_ic(df: pd.DataFrame, weight_col: str, score_col: str, target_col: str, 
                               min_rows: int = 100) -> dict:
    """Compute IC of weighted score (s1 * weight) and compare with weighted rank IC."""
    subset = df.copy()
    
    weighted_score = subset[score_col] * subset[weight_col]
    subset["weighted_score"] = weighted_score
    
    result = safe_spearman(subset, "weighted_score", target_col, min_rows=min_rows)
    
    years = yearly_ic(subset, "weighted_score", target_col, min_year_rows=min_rows)
    summary = summarize_ic_rows(years)
    
    years_series = pd.to_datetime(subset["time"], errors="coerce").dt.year
    dev_mask = years_series.between(2015, 2022)
    val_mask = years_series.isin([2023, 2024])
    conf_mask = years_series == 2025
    
    dev_ic = safe_spearman(subset.loc[dev_mask], "weighted_score", target_col, min_rows=50)["ic"]
    val_ic = safe_spearman(subset.loc[val_mask], "weighted_score", target_col, min_rows=50)["ic"]
    conf_ic = safe_spearman(subset.loc[conf_mask], "weighted_score", target_col, min_rows=50)["ic"]
    
    return {
        "ic": result["ic"],
        "n": len(subset),
        "positive_years": summary["positive_years"],
        "total_years": summary["years"],
        "dev_ic": dev_ic,
        "val_ic": val_ic,
        "conf_ic": conf_ic,
    }


def compute_weighted_rank_ic(df: pd.DataFrame, weight_col: str, score_col: str, target_col: str,
                             min_rows: int = 100) -> dict:
    """Compute IC using rank of weighted score within each date."""
    subset = df.copy()
    
    weighted_score = subset[score_col] * subset[weight_col]
    subset["weighted_score"] = weighted_score
    
    subset["weighted_score_rank"] = subset.groupby("time")["weighted_score"].rank(method="average", pct=True)
    
    result = safe_spearman(subset, "weighted_score_rank", target_col, min_rows=min_rows)
    
    years = yearly_ic(subset, "weighted_score_rank", target_col, min_year_rows=min_rows)
    summary = summarize_ic_rows(years)
    
    return {
        "ic": result["ic"],
        "n": len(subset),
        "positive_years": summary["positive_years"],
        "total_years": summary["years"],
    }


def main():
    print("=" * 70)
    print("H530 - Breadth-Weighted Position Sizing Test")
    print("=" * 70)
    
    df = load_data()
    df = compute_date_breadth(df)
    
    score_col = "s1_xs_proba"
    target_col = "s1_barrier_hit_1d"
    
    baseline = safe_spearman(df, score_col, target_col, min_rows=100)
    baseline_ic = baseline["ic"]
    print(f"\nBaseline (all rows): IC = {baseline_ic:.4f}, n = {len(df)}")
    
    results = {}
    
    print("\n" + "-" * 70)
    print("IC Evaluation:")
    print("-" * 70)
    
    test_configs = {
        "baseline": ("All S1 rows", df, None),
        "low_breadth_dates": ("S1 on low-breadth dates (binary)", df[df["is_low_breadth"] == 1], None),
        "high_breadth_dates": ("S1 on high-breadth dates (binary)", df[df["is_high_breadth"] == 1], None),
    }
    
    for name, (desc, subset, _) in test_configs.items():
        if subset is None:
            subset = df
        if len(subset) < 100:
            continue
        result = safe_spearman(subset, score_col, target_col, min_rows=100)
        years = yearly_ic(subset, score_col, target_col, min_year_rows=100)
        summary = summarize_ic_rows(years)
        results[name] = {
            "description": desc,
            "ic": result["ic"],
            "n": len(subset),
            "positive_years": summary["positive_years"],
            "total_years": summary["years"],
        }
        lift = (result["ic"] - baseline_ic) if result["ic"] else 0
        print(f"\n{name} ({desc}):")
        print(f"  IC = {result['ic']:.4f}, lift = {lift:+.4f}, n = {len(subset)}, pos = {summary['positive_years']}/{summary['years']}")
    
    print("\n--- Weighted Score Tests ---")
    
    weighted_result = compute_weighted_score_ic(df, "inv_breadth_weight", score_col, target_col, min_rows=100)
    results["weighted_score"] = {
        "description": "S1 * inv_breadth_weight (continuous)",
        "ic": weighted_result["ic"],
        "n": weighted_result["n"],
        "positive_years": weighted_result["positive_years"],
        "total_years": weighted_result["total_years"],
        "dev_ic": weighted_result["dev_ic"],
        "val_ic": weighted_result["val_ic"],
        "conf_ic": weighted_result["conf_ic"],
    }
    lift = (weighted_result["ic"] - baseline_ic) if weighted_result["ic"] else 0
    print(f"\nweighted_score (S1 * inv_breadth):")
    print(f"  IC = {weighted_result['ic']:.4f}, lift = {lift:+.4f}, n = {weighted_result['n']}")
    if weighted_result["dev_ic"]:
        print(f"  Phase ICs: dev={weighted_result['dev_ic']:.4f}, val={weighted_result['val_ic']:.4f}, conf={weighted_result['conf_ic']:.4f}")
    
    weighted_rank_result = compute_weighted_rank_ic(df, "inv_breadth_weight", score_col, target_col, min_rows=100)
    results["weighted_rank"] = {
        "description": "Rank(S1 * inv_breadth) within date",
        "ic": weighted_rank_result["ic"],
        "n": weighted_rank_result["n"],
        "positive_years": weighted_rank_result["positive_years"],
        "total_years": weighted_rank_result["total_years"],
    }
    lift_rank = (weighted_rank_result["ic"] - baseline_ic) if weighted_rank_result["ic"] else 0
    print(f"\nweighted_rank (rank of weighted score):")
    print(f"  IC = {weighted_rank_result['ic']:.4f}, lift = {lift_rank:+.4f}, n = {weighted_rank_result['n']}")
    
    baseline_lift = baseline_ic
    binary_low_ic = results["low_breadth_dates"]["ic"] or 0
    weighted_score_ic = results["weighted_score"]["ic"] or 0
    weighted_rank_ic = results["weighted_rank"]["ic"] or 0
    
    print("\n" + "=" * 70)
    print("ANALYSIS:")
    print("=" * 70)
    print(f"  Baseline (all rows): IC = {baseline_lift:.4f}")
    print(f"  Binary low_breadth filter: IC = {binary_low_ic:.4f} (lift = {binary_low_ic - baseline_lift:+.4f})")
    print(f"  Weighted score (continuous): IC = {weighted_score_ic:.4f} (lift = {weighted_score_ic - baseline_lift:+.4f})")
    print(f"  Weighted rank: IC = {weighted_rank_ic:.4f} (lift = {weighted_rank_ic - baseline_lift:+.4f})")
    
    lift_weighted_vs_binary = weighted_score_ic - binary_low_ic
    print(f"\n  Weighted score vs binary low_breadth: {lift_weighted_vs_binary:+.4f}")
    
    if weighted_score_ic > binary_low_ic + 0.01:
        verdict = "PASSED"
        print(f"\nVerdict: {verdict} - continuous weighting beats binary filter by > +0.01")
    elif weighted_score_ic > baseline_lift:
        verdict = "MIXED"
        print(f"\nVerdict: {verdict} - continuous weighting lifts vs baseline but not > binary + 0.01")
    else:
        verdict = "FAILED"
        print(f"\nVerdict: {verdict} - no meaningful lift over baseline")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    artifact = {
        "experiment": "h530_breadth_weighted_position_sizing",
        "timestamp": timestamp,
        "verdict": verdict,
        "baseline_ic": float(baseline_ic),
        "results": {k: {**v, "lift_vs_baseline": float((v["ic"] or 0) - baseline_ic)} for k, v in results.items()},
        "analysis": {
            "binary_low_breadth_ic": float(binary_low_ic),
            "weighted_score_ic": float(weighted_score_ic),
            "weighted_rank_ic": float(weighted_rank_ic),
            "lift_weighted_vs_binary": float(lift_weighted_vs_binary),
        }
    }
    
    out_path = artifact_path(f"run_summaries/{timestamp}_breadth_weighted_position_sizing_research_branch.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(artifact, f, indent=2, default=str)
    
    print(f"\nSaved: {out_path}")
    return verdict, artifact


if __name__ == "__main__":
    verdict, artifact = main()
    sys.exit(0 if verdict in ["PASSED", "MIXED"] else 1)