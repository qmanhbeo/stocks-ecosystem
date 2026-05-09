"""
H481: breadth_threshold_finder

Hypothesis: Find the exact breadth percentage threshold (not quintile) where
signal quality switches from positive to negative. H468 found narrow > broad
at 20% quintile, but what's the exact threshold number?

Decision ladder:
- PASS: Find a clean threshold with >+0.01 IC lift at specific cutoff
- MIXED: Pattern exists but threshold is fuzzy/unstable
- FAIL: No clear threshold, signals work uniformly across all breadth levels

Uses reusable experiment_contract.py scaffold.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiment_contract import (
    S1_DEFAULT_PATH,
    S1_SCORE_COL,
    S1_TARGET_COL,
    ExperimentSpec,
    StateSpec,
    build_experiment_context,
    evaluate_state_specs,
    load_s1_decision_panel,
    validate_state_columns,
    write_dataframe_artifact,
)


BRANCH_NAME = "breadth_threshold_finder"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Find exact breadth percentage threshold where signal quality switches. "
        "H468 found bottom20% breadth positive (+0.0140), top20% negative (-0.0199). "
        "Test thresholds at 10/15/20/25/30/35/40% to find exact cutoff."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def compute_market_breadth(panel: pd.DataFrame) -> pd.DataFrame:
    """Compute daily market breadth: fraction of stocks with positive return.
    
    Uses s1_barrier_hit_1d (binary target: 1 if stock went up) to compute
    the fraction of stocks that were positive each day.
    """
    breadth_daily = (
        panel.groupby("time")
        .agg(
            count_up=(S1_TARGET_COL, "sum"),
            count_total=(S1_TARGET_COL, "count"),
        )
        .reset_index()
    )
    breadth_daily["breadth"] = breadth_daily["count_up"] / breadth_daily["count_total"]
    breadth_daily["breadth_rank"] = breadth_daily["breadth"].rank(pct=True, method="average")
    
    panel = panel.merge(breadth_daily[["time", "breadth", "breadth_rank"]], on="time", how="left")
    return panel


def define_threshold_states() -> list[StateSpec]:
    """Define breadth threshold states at different cutoff percentages."""
    states = [
        StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    ]
    
    thresholds = [10, 15, 20, 25, 30, 35, 40]
    
    for thresh in thresholds:
        states.append(StateSpec(
            f"breadth_top_{thresh}",
            f"Breadth top {thresh}% (broad market)",
            family="breadth_high",
            baseline="all_rows",
        ))
        states.append(StateSpec(
            f"breadth_bottom_{thresh}",
            f"Breadth bottom {thresh}% (narrow market)",
            family="breadth_low",
            baseline="all_rows",
        ))
    
    return states


def apply_state_filters(df: pd.DataFrame, state_name: str) -> pd.DataFrame:
    """Apply state filter based on breadth threshold."""
    if state_name == "all_rows":
        return df
    
    if state_name.startswith("breadth_top_"):
        thresh = int(state_name.split("_")[-1])
        return df[df["breadth"] >= (100 - thresh) / 100]
    
    if state_name.startswith("breadth_bottom_"):
        thresh = int(state_name.split("_")[-1])
        return df[df["breadth"] <= thresh / 100]
    
    return df


def compute_ic(df: pd.DataFrame, score_col: str, target_col: str) -> float:
    """Compute IC for a dataframe."""
    if len(df) < 50:
        return np.nan
    
    valid = df[[score_col, target_col]].dropna()
    if len(valid) < 50:
        return np.nan
    
    return valid[score_col].corr(valid[target_col])


def run_threshold_scan(panel: pd.DataFrame) -> pd.DataFrame:
    """Scan across thresholds and compute IC for each.
    
    Uses breadth_rank (percentile) for thresholding:
    - bottom X% means breadth_rank <= X/100
    - top X% means breadth_rank >= (100-X)/100
    """
    panel = compute_market_breadth(panel)
    
    score_col = S1_SCORE_COL
    target_col = S1_TARGET_COL
    
    results = []
    baseline_ic = compute_ic(panel, score_col, target_col)
    
    thresholds = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
    
    for thresh in thresholds:
        # breadth_rank is percentile (0-1). 
        # Top thresh% means top thresh percentile = rank >= (100-thresh)/100
        # Bottom thresh% means bottom thresh percentile = rank <= thresh/100
        broad_cutoff = (100 - thresh) / 100
        narrow_cutoff = thresh / 100
        
        broad_df = panel[panel["breadth_rank"] >= broad_cutoff]
        narrow_df = panel[panel["breadth_rank"] <= narrow_cutoff]
        
        broad_ic = compute_ic(broad_df, score_col, target_col)
        narrow_ic = compute_ic(narrow_df, score_col, target_col)
        
        broad_lift = broad_ic - baseline_ic if not np.isnan(broad_ic) else np.nan
        narrow_lift = narrow_ic - baseline_ic if not np.isnan(narrow_ic) else np.nan
        
        results.append({
            "threshold_pct": thresh,
            "narrow_ic": narrow_ic,
            "narrow_lift": narrow_lift,
            "narrow_rows": len(narrow_df),
            "broad_ic": broad_ic,
            "broad_lift": broad_lift,
            "broad_rows": len(broad_df),
        })
    
    results_df = pd.DataFrame(results)
    results_df["baseline_ic"] = baseline_ic
    
    return results_df


def decision(results_df: pd.DataFrame, panel: pd.DataFrame) -> str:
    """Decide pass/mixed/fail based on threshold pattern."""
    baseline_ic = results_df["baseline_ic"].iloc[0]
    
    narrow_row = results_df[results_df["threshold_pct"] == 20].iloc[0]
    print(f"\n=== H481 Breadth Threshold Results ===")
    print(f"Baseline S1 IC: {baseline_ic:.4f}")
    print(f"\nNarrow market (bottom 20%): IC={narrow_row['narrow_ic']:.4f}, lift={narrow_row['narrow_lift']:.4f}, rows={narrow_row['narrow_rows']}")
    print(f"Broad market (top 20%): IC={narrow_row['broad_ic']:.4f}, lift={narrow_row['broad_lift']:.4f}, rows={narrow_row['broad_rows']}")
    
    print(f"\n--- Full Threshold Scan ---")
    print(f"{'Thresh%':>8} {'Narrow IC':>10} {'Narrow Lift':>12} {'Broad IC':>10} {'Broad Lift':>12}")
    for _, row in results_df.iterrows():
        print(f"{row['threshold_pct']:>8} {row['narrow_ic']:>10.4f} {row['narrow_lift']:>12.4f} {row['broad_ic']:>10.4f} {row['broad_lift']:>12.4f}")
    
    # Find the best narrow market threshold
    best_narrow = results_df.loc[results_df["narrow_lift"].idxmax()]
    print(f"\nBest narrow threshold: {int(best_narrow['threshold_pct'])}% with lift {best_narrow['narrow_lift']:.4f}")
    
    # Decision: look for clear threshold pattern
    # Pass if: best narrow lift > 0.01 AND enough rows AND multiple thresholds show positive
    if best_narrow["narrow_lift"] > 0.01 and best_narrow["narrow_rows"] > 1000:
        positive_thresholds = results_df[results_df["narrow_lift"] > 0]["threshold_pct"].count()
        if positive_thresholds >= 5:
            return "PASS"
    
    if best_narrow["narrow_lift"] > 0.005:
        return "MIXED"
    
    return "FAIL"


def main():
    parser = argparse.ArgumentParser(description="H481 breadth threshold finder")
    parser.add_argument("--dry-run", action="store_true", help="Dry run only")
    args = parser.parse_args()
    
    panel = load_s1_decision_panel(
        S1_DEFAULT_PATH,
        start_year=SPEC.start_year,
        end_year=SPEC.end_year,
    )
    
    print(f"Loaded panel: {len(panel)} rows")
    
    results_df = run_threshold_scan(panel)
    
    output_path = ROOT / "artifacts" / "run_summaries" / f"h481_breadth_threshold_results.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(output_path, index=False)
    print(f"Results saved to {output_path}")
    
    verdict = decision(results_df, panel)
    print(f"\n=== Verdict: {verdict} ===")
    
    summary = {
        "branch": BRANCH_NAME,
        "verdict": verdict,
        "baseline_ic": results_df["baseline_ic"].iloc[0],
        "narrow_20pct_ic": results_df[results_df["threshold_pct"] == 20]["narrow_ic"].iloc[0],
        "broad_20pct_ic": results_df[results_df["threshold_pct"] == 20]["broad_ic"].iloc[0],
    }
    
    import json
    summary_path = ROOT / "artifacts" / "run_summaries" / f"h481_breadth_threshold_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Summary saved to {summary_path}")


if __name__ == "__main__":
    main()