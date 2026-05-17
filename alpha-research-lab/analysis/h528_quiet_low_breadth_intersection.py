#!/usr/bin/env python3
"""
H528 - Quiet-State × Low-Breadth Intersection Test

Test if intersection of state_quiet (rank >= 0.75) on low_breadth dates 
(active stock count in bottom quartile) captures alpha better than either alone.

Hypothesis from bright-mind idea #13:
- state_quiet is STRONG (IC=0.1552, 11/11 pos yrs) - discovered in H524
- low_breadth dates have BETTER IC (0.1454 vs high breadth 0.1149) - from H525
- Both strong independently; intersection is untested

Decision rule:
- PASS: intersection IC > max(quiet_IC, low_breadth_IC) + 0.01
- MIXED: intersection IC > min(quiet_IC, low_breadth_IC) but not > max + 0.01
- FAIL: intersection IC <= min(quiet_IC, low_breadth_IC)
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
)
from src.repo_paths import artifact_path, data_path


def load_data():
    """Load S1 and C16 signals."""
    s1_path = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
    s1_df = pd.read_parquet(s1_path, columns=["time", "ticker", "xs_proba", "actual"])
    s1_df = normalize_time_ticker(s1_df, source="S1 panel")
    s1_df = restrict_years(s1_df, start_year=2015, end_year=2025, source="S1 panel")
    s1_df = s1_df.rename(columns={"xs_proba": "s1_proba", "actual": "s1_barrier_hit_1d"})
    
    c16_path = data_path("features/xs_order_pressure_daily.parquet")
    c16_cols = ["time", "ticker", "order_volume_ratio_rank"]
    c16_df = pd.read_parquet(c16_path, columns=c16_cols)
    c16_df = normalize_time_ticker(c16_df, source="C16 panel")
    c16_df = restrict_years(c16_df, start_year=2015, end_year=2025, source="C16 panel")
    
    df = s1_df.merge(c16_df, on=["time", "ticker"], how="inner")
    print(f"Merged panel: {len(df)} rows, years {df['time'].dt.year.min()}-{df['time'].dt.year.max()}")
    return df


def compute_date_breadth(df: pd.DataFrame) -> pd.DataFrame:
    """Compute date-level active stock count (breadth)."""
    df["is_active"] = (df["order_volume_ratio_rank"] < 0.2).astype(int)
    
    date_breadth = df.groupby("time")["is_active"].sum().reset_index()
    date_breadth.columns = ["time", "active_count"]
    date_breadth["breadth_percentile"] = date_breadth["active_count"].rank(pct=True)
    date_breadth["is_low_breadth"] = (date_breadth["breadth_percentile"] <= 0.25).astype(int)
    
    print(f"Date breadth: {len(date_breadth)} dates")
    print(f"Low breadth dates: {date_breadth['is_low_breadth'].sum()}")
    print(f"Active count range: {date_breadth['active_count'].min()} - {date_breadth['active_count'].max()}")
    
    return date_breadth


def compute_signal_states(df: pd.DataFrame, date_breadth: pd.DataFrame) -> pd.DataFrame:
    """Compute signal state columns."""
    result = df.merge(date_breadth[["time", "active_count", "breadth_percentile", "is_low_breadth"]], on="time")
    
    # Quiet state: highest pressure (rank >= 0.75)
    result["state_quiet"] = (result["order_volume_ratio_rank"] >= 0.75).astype(int)
    
    # Active state for comparison: lowest pressure (rank < 0.2)
    result["state_active"] = (result["order_volume_ratio_rank"] < 0.2).astype(int)
    
    # Intersections
    result["quiet_low_breadth"] = ((result["state_quiet"] == 1) & (result["is_low_breadth"] == 1)).astype(int)
    result["active_low_breadth"] = ((result["state_active"] == 1) & (result["is_low_breadth"] == 1)).astype(int)
    
    return result


def compute_ic(df: pd.DataFrame, score_col: str, target_col: str = "s1_barrier_hit_1d") -> dict:
    """Compute IC metrics using s1_proba as score."""
    n = int(len(df))
    if n < 30:
        return {"ic": None, "n": n, "pos_years": 0, "yearly": {}}
    
    result = safe_spearman(df, score_col, target_col, min_rows=30)
    ic = result.get("ic")
    
    yearly_list = yearly_ic(df, score_col, target_col, min_year_rows=30)
    yearly = {str(row["year"]): row.get("ic") for row in yearly_list if row.get("ic") is not None}
    pos_years = sum(1 for v in yearly.values() if v is not None and float(v) > 0)
    
    return {
        "ic": float(ic) if ic is not None else None,
        "n": n,
        "pos_years": pos_years,
        "total_years": len(yearly),
        "yearly": yearly
    }


def run_experiment():
    """Run the intersection experiment."""
    print("="*60)
    print("H528 - Quiet-State × Low-Breadth Intersection")
    print("="*60)
    
    df = load_data()
    date_breadth = compute_date_breadth(df)
    result = compute_signal_states(df, date_breadth)
    
    # Compute baseline IC (all rows)
    baseline_result = safe_spearman(result, "s1_proba", "s1_barrier_hit_1d", min_rows=100)
    baseline_ic = baseline_result.get("ic", 0)
    print(f"\nBaseline (all rows): IC = {baseline_ic:.4f}, n = {len(result)}")
    
    # Test signals: compute IC of s1_proba filtered by different conditions
    signals = {
        "state_quiet": ("s1_proba where rank >= 0.75", result[result["state_quiet"] == 1].copy()),
        "is_low_breadth": ("s1_proba on low breadth dates", result[result["is_low_breadth"] == 1].copy()),
        "state_active": ("s1_proba where rank < 0.2", result[result["state_active"] == 1].copy()),
        "quiet_low_breadth": ("s1_proba: quiet + low breadth", result[result["quiet_low_breadth"] == 1].copy()),
        "active_low_breadth": ("s1_proba: active + low breadth", result[result["active_low_breadth"] == 1].copy()),
    }
    
    results = {}
    for sig, (desc, subset) in signals.items():
        metrics = compute_ic(subset, "s1_proba")
        results[sig] = {
            "description": desc,
            "ic": metrics["ic"],
            "n": metrics["n"],
            "pos_years": metrics["pos_years"],
            "total_years": metrics["total_years"],
            "yearly": metrics["yearly"]
        }
        
        lift = (metrics["ic"] - baseline_ic) if metrics["ic"] is not None else 0
        print(f"\n{sig} ({desc}):")
        print(f"  IC = {metrics['ic']:.4f}, lift = {lift:+.4f}" if metrics["ic"] else f"  IC = N/A")
        print(f"  N = {metrics['n']}, pos years = {metrics['pos_years']}/{metrics['total_years']}")
    
    # Determine verdict - compare intersection vs best single
    quiet_ic = results["state_quiet"]["ic"] or 0
    low_breadth_ic = results["is_low_breadth"]["ic"] or 0
    intersection_ic = results["quiet_low_breadth"]["ic"] or 0
    
    max_single = max(quiet_ic, low_breadth_ic)
    min_single = min(quiet_ic, low_breadth_ic)
    
    print("\n" + "="*60)
    print("ANALYSIS:")
    print(f"  state_quiet IC: {quiet_ic:.4f}")
    print(f"  low_breadth IC: {low_breadth_ic:.4f}")
    print(f"  Intersection (quiet + low breadth) IC: {intersection_ic:.4f}")
    print(f"  Max single: {max_single:.4f}")
    print(f"  Min single: {min_single:.4f}")
    
    # Compare active intersection too
    active_int_ic = results["active_low_breadth"]["ic"] or 0
    print(f"  Active + low breadth IC: {active_int_ic:.4f}")
    
    # Check decision rule
    if intersection_ic > max_single + 0.01:
        verdict = "PASSED"
        print(f"  Verdict: {verdict} - intersection beats max single by {intersection_ic - max_single:.4f}")
    elif intersection_ic > min_single:
        verdict = "MIXED"
        print(f"  Verdict: {verdict} - intersection > min single but not > max")
    else:
        verdict = "FAILED"
        print(f"  Verdict: {verdict} - intersection <= min single")
    
    # Also check if active + low breadth beats active alone
    active_ic = results["state_active"]["ic"] or 0
    if active_int_ic > active_ic + 0.01:
        print(f"  Active+low_breadth beats active alone: YES (+{active_int_ic - active_ic:.4f})")
    else:
        print(f"  Active+low_breadth beats active alone: NO ({active_int_ic - active_ic:+.4f})")
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    artifact = {
        "experiment": "h528_quiet_low_breadth_intersection",
        "timestamp": timestamp,
        "verdict": verdict,
        "baseline_ic": float(baseline_ic),
        "signals": {k: {**v, "yearly": {str(yk): float(yv) for yk, yv in v["yearly"].items()}} for k, v in results.items()},
        "analysis": {
            "quiet_ic": float(quiet_ic),
            "low_breadth_ic": float(low_breadth_ic),
            "intersection_ic": float(intersection_ic),
            "active_int_ic": float(active_int_ic),
            "max_single": float(max_single),
            "min_single": float(min_single),
            "intersection_lift_vs_max": float(intersection_ic - max_single),
            "active_ic": float(active_ic)
        }
    }
    
    out_path = artifact_path(f"run_summaries/{timestamp}_quiet_low_breadth_intersection_research_branch.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(artifact, f, indent=2, default=str)
    
    print(f"\nSaved: {out_path}")
    return verdict, artifact


if __name__ == "__main__":
    verdict, artifact = run_experiment()
    sys.exit(0 if verdict in ["PASSED", "MIXED"] else 1)