#!/usr/bin/env python3
"""
H532 - Breadth-Triggered Entry Decay Detection

Test if signal quality rebounds after high-breadth spike days.
Hypothesis: After a high-breadth day (crowd saturation), the next few days should have
improved signal quality as the crowd disperses.

Key prior findings:
- H525: low_breadth dates have BETTER IC (0.1454 vs high breadth 0.1149)
- H528: active + low_breadth = strongest (0.2013)
- H531: tight + low_breadth = 0.1979

Decision rule:
- PASS: post-high-breadth IC > high-breadth same-day IC by > +0.01
- MIXED: lifts but < +0.01
- FAIL: no meaningful improvement
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
    """Load S1 panel with C16."""
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
    """Compute date-level breadth and add to panel."""
    df = df.copy()
    df["is_active"] = (df["order_volume_ratio_rank"] < 0.2).astype(int)
    
    date_stats = df.groupby("time").agg(
        active_count=("is_active", "sum"),
    ).reset_index()
    
    date_stats["breadth_percentile"] = date_stats["active_count"].rank(pct=True)
    date_stats["is_high_breadth"] = (date_stats["breadth_percentile"] >= 0.75).astype(int)
    date_stats["is_low_breadth"] = (date_stats["breadth_percentile"] <= 0.25).astype(int)
    
    date_stats = date_stats.sort_values("time").reset_index(drop=True)
    
    date_stats["prev_was_high_breadth"] = date_stats["is_high_breadth"].shift(1).fillna(0).astype(int)
    
    hbb = date_stats["is_high_breadth"].values
    any_3d = np.zeros(len(date_stats), dtype=int)
    any_5d = np.zeros(len(date_stats), dtype=int)
    
    for i in range(1, len(date_stats)):
        any_3d[i] = int(any(hbb[max(0, i-3):i]) > 0)
        any_5d[i] = int(any(hbb[max(0, i-5):i]) > 0)
    
    date_stats["any_high_breadth_3d"] = any_3d
    date_stats["any_high_breadth_5d"] = any_5d
    
    df = df.merge(
        date_stats[["time", "active_count", "breadth_percentile", "is_high_breadth", "is_low_breadth",
                    "prev_was_high_breadth", "any_high_breadth_3d", "any_high_breadth_5d"]],
        on="time",
        how="left"
    )
    
    print(f"Date breadth stats: {len(date_stats)} dates")
    print(f"  High breadth dates (P75): {date_stats['is_high_breadth'].sum()}")
    print(f"  Low breadth dates (P25): {date_stats['is_low_breadth'].sum()}")
    print(f"  Days after high-breadth: {date_stats['prev_was_high_breadth'].sum()}")
    
    return df


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
    print("H532 - Breadth-Triggered Entry Decay Detection")
    print("=" * 70)
    
    df = load_data()
    df = compute_date_breadth(df)
    
    score_col = "s1_xs_proba"
    target_col = "s1_barrier_hit_1d"
    
    baseline = safe_spearman(df, score_col, target_col, min_rows=100)
    baseline_ic = baseline["ic"]
    print(f"\nBaseline (all rows): IC = {baseline_ic:.4f}, n = {len(df)}")
    
    results = {}
    
    test_configs = {
        "all_rows": ("All S1 rows (baseline)", df["time"].notna()),
        "high_breadth_same_day": ("Same-day high breadth (crowded)", df["is_high_breadth"] == 1),
        "low_breadth_same_day": ("Same-day low breadth (regime amplifier)", df["is_low_breadth"] == 1),
        "post_highbreadth_1d": ("Day AFTER high-breadth day", (df["prev_was_high_breadth"] == 1) & (df["is_high_breadth"] == 0)),
        "post_highbreadth_3d": ("Within 3d AFTER high-breadth", (df["any_high_breadth_3d"] == 1) & (df["is_high_breadth"] == 0)),
        "post_highbreadth_5d": ("Within 5d AFTER high-breadth", (df["any_high_breadth_5d"] == 1) & (df["is_high_breadth"] == 0)),
        "lowbreadth_post_spike": ("Low breadth + post-spike combo", (df["is_low_breadth"] == 1) & (df["any_high_breadth_3d"] == 1)),
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
    
    highbreadth_ic = results["high_breadth_same_day"]["ic"] or 0
    post1d_ic = results["post_highbreadth_1d"]["ic"] or 0
    post3d_ic = results["post_highbreadth_3d"]["ic"] or 0
    post5d_ic = results["post_highbreadth_5d"]["ic"] or 0
    lowbreadth_ic = results["low_breadth_same_day"]["ic"] or 0
    combo_ic = results["lowbreadth_post_spike"]["ic"] or 0
    
    best_post = max(post1d_ic, post3d_ic, post5d_ic)
    lift_vs_highbreadth = best_post - highbreadth_ic
    lift_vs_baseline = best_post - baseline_ic
    
    print("\n" + "=" * 70)
    print("ANALYSIS:")
    print("=" * 70)
    print(f"  Baseline (all rows): IC = {baseline_ic:.4f}")
    print(f"  Same-day high breadth: IC = {highbreadth_ic:.4f}")
    print(f"  Post-highbreadth 1d: IC = {post1d_ic:.4f}")
    print(f"  Post-highbreadth 3d: IC = {post3d_ic:.4f}")
    print(f"  Post-highbreadth 5d: IC = {post5d_ic:.4f}")
    print(f"  Best post-spike: {best_post:.4f}")
    print(f"  Lift vs same-day high-breadth: {lift_vs_highbreadth:+.4f}")
    print(f"  Lift vs baseline: {lift_vs_baseline:+.4f}")
    print(f"\n  Low breadth (same day): IC = {lowbreadth_ic:.4f}")
    print(f"  Low breadth + post-spike: IC = {combo_ic:.4f}")
    
    if lift_vs_highbreadth > 0.01:
        verdict = "PASSED"
        print(f"\nVerdict: {verdict} - post-spike beats same-day high-breadth by > +0.01")
    elif lift_vs_highbreadth > 0:
        verdict = "MIXED"
        print(f"\nVerdict: {verdict} - post-spike lifts but < +0.01 vs same-day high-breadth")
    else:
        verdict = "FAILED"
        print(f"\nVerdict: {verdict} - no meaningful improvement post-spike")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    artifact = {
        "experiment": "h532_breadth_triggered_decay",
        "timestamp": timestamp,
        "verdict": verdict,
        "baseline_ic": float(baseline_ic),
        "results": {k: {**v, "lift_vs_baseline": float((v["ic"] or 0) - baseline_ic)} for k, v in results.items()},
        "analysis": {
            "high_breadth_same_day_ic": float(highbreadth_ic),
            "post_highbreadth_1d_ic": float(post1d_ic),
            "post_highbreadth_3d_ic": float(post3d_ic),
            "post_highbreadth_5d_ic": float(post5d_ic),
            "best_post_spike_ic": float(best_post),
            "lift_vs_high_breadth": float(lift_vs_highbreadth),
            "lift_vs_baseline": float(lift_vs_baseline),
            "combo_lowbreadth_post_spike_ic": float(combo_ic),
        }
    }
    
    out_path = artifact_path(f"run_summaries/{timestamp}_breadth_triggered_decay_research_branch.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(artifact, f, indent=2, default=str)
    
    print(f"\nSaved: {out_path}")
    return verdict, artifact


if __name__ == "__main__":
    verdict, artifact = main()
    sys.exit(0 if verdict in ["PASSED", "MIXED"] else 1)