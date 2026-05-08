"""
H435: candidate_rank_actual_gap

Hypothesis: The gap between predicted rank (from H413 blend) and actual realized 
rank predicts forward returns. Large gaps = surprising information = alpha.

Test: Compare high-gap vs low-gap states vs random baseline.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

import numpy as np
import pandas as pd

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
    load_s1_decision_panel,
    write_dataframe_artifact,
    validate_state_columns,
)


BRANCH_NAME = "h435_candidate_rank_actual_gap"
MODE = "research_branch_candidate_rank_actual_gap"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Candidate rank actual gap: compute predicted rank minus actual return rank. "
        "Large gaps = surprising information. Test if gap magnitude predicts forward IC."
    ),
    start_year=2018,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H435 candidate rank actual gap test")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    return parser.parse_args()


def compute_predictions_and_actuals(panel: pd.DataFrame) -> pd.DataFrame:
    """Compute predicted rank and actual rank for each date."""
    
    # H413 blend: 0.1*Vol + 0.9*S1
    if "order_volume_ratio_rank" not in panel.columns:
        c16_path = Path("/home/manh/stocks-ecosystem/data/features/xs_order_pressure_daily.parquet")
        c16 = pd.read_parquet(c16_path)[["time", "ticker", "order_volume_ratio_rank"]]
        if panel["time"].dtype == "object":
            panel["time"] = pd.to_datetime(panel["time"])
        if c16["time"].dtype == "object":
            c16["time"] = pd.to_datetime(c16["time"])
        panel = panel.merge(c16, on=["time", "ticker"], how="left")
        panel["order_volume_ratio_rank"] = panel["order_volume_ratio_rank"].fillna(0.5)
    
    # Predicted score
    panel["pred_score"] = 0.1 * panel["order_volume_ratio_rank"] + 0.9 * panel[S1_SCORE_COL]
    
    # Predicted rank (within date)
    panel["pred_rank"] = panel.groupby("time")["pred_score"].rank(method="average", pct=True)
    
    # Actual return rank (using the label as proxy - actually we need next-day return)
    # Use actual barrier hit as a proxy for ranking
    panel["actual_rank"] = panel.groupby("time")[S1_TARGET_COL].rank(method="average", pct=True)
    
    # Gap = predicted - actual (positive means predicted high but actual low = surprise)
    panel["rank_gap"] = panel["pred_rank"] - panel["actual_rank"]
    
    return panel


def evaluate_gap_states(panel: pd.DataFrame, spec: ExperimentSpec) -> pd.DataFrame:
    """Evaluate rank gap quintiles."""
    
    yearly_results = []
    for year, grp in panel.groupby(pd.to_datetime(panel["time"]).dt.year):
        if year < spec.start_year or year > spec.end_year:
            continue

        grp_sorted = grp.dropna(subset=["rank_gap"])
        if len(grp_sorted) < 50:
            continue

        # Baseline: H413 IC
        h413_ic = grp_sorted[["pred_score", S1_TARGET_COL]].corr(method="spearman").iloc[0, 1]

        # Bucket by gap magnitude
        q1_gap_ic = grp_sorted[grp_sorted["rank_gap"] <= grp_sorted["rank_gap"].quantile(0.2)][[S1_SCORE_COL, S1_TARGET_COL]].corr(method="spearman").iloc[0, 1]
        q3_gap_ic = grp_sorted[(grp_sorted["rank_gap"] > grp_sorted["rank_gap"].quantile(0.4)) & (grp_sorted["rank_gap"] <= grp_sorted["rank_gap"].quantile(0.6))][[S1_SCORE_COL, S1_TARGET_COL]].corr(method="spearman").iloc[0, 1]
        q5_gap_ic = grp_sorted[grp_sorted["rank_gap"] >= grp_sorted["rank_gap"].quantile(0.8)][[S1_SCORE_COL, S1_TARGET_COL]].corr(method="spearman").iloc[0, 1]
        
        # High surprise (large |gap|) vs low surprise (small |gap|)
        grp_sorted["abs_gap"] = grp_sorted["rank_gap"].abs()
        q1_abs_gap_ic = grp_sorted[grp_sorted["abs_gap"] <= grp_sorted["abs_gap"].quantile(0.2)][[S1_SCORE_COL, S1_TARGET_COL]].corr(method="spearman").iloc[0, 1]
        q5_abs_gap_ic = grp_sorted[grp_sorted["abs_gap"] >= grp_sorted["abs_gap"].quantile(0.8)][[S1_SCORE_COL, S1_TARGET_COL]].corr(method="spearman").iloc[0, 1]

        yearly_results.append({
            "year": year,
            "h413_ic": h413_ic,
            "q1_gap_ic": q1_gap_ic,
            "q3_gap_ic": q3_gap_ic,
            "q5_gap_ic": q5_gap_ic,
            "q5_q1_gap_lift": q5_gap_ic - q1_gap_ic,
            "q1_abs_gap_ic": q1_abs_gap_ic,
            "q5_abs_gap_ic": q5_abs_gap_ic,
            "q5_abs_q1_abs_lift": q5_abs_gap_ic - q1_abs_gap_ic,
        })

    return pd.DataFrame(yearly_results)


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(
        SPEC,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        min_year_rows=int(args.min_year_rows),
        min_phase_rows=int(args.min_phase_rows),
    )
    context = build_experiment_context(spec, artifact_subdir="research_branch")

    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )
    
    panel = compute_predictions_and_actuals(panel)
    validate_state_columns(panel, [], spec)

    yearly = evaluate_gap_states(panel, spec)
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")

    h413_avg_ic = yearly["h413_ic"].mean()
    q1_gap_ic = yearly["q1_gap_ic"].mean()
    q5_gap_ic = yearly["q5_gap_ic"].mean()
    q5_q1_lift = q5_gap_ic - q1_gap_ic
    q1_abs_ic = yearly["q1_abs_gap_ic"].mean()
    q5_abs_ic = yearly["q5_abs_gap_ic"].mean()
    q5_abs_q1_abs_lift = q5_abs_ic - q1_abs_ic

    print(f"\n=== H435 Candidate Rank Actual Gap Results ===")
    print(f"H413 baseline avg IC: {h413_avg_ic:.4f}")
    print(f"\nPredicted rank gap (positive = overpredicted):")
    print(f"  Q1 (low predicted vs actual) IC: {q1_gap_ic:.4f}")
    print(f"  Q5 (high predicted vs actual) IC: {q5_gap_ic:.4f}")
    print(f"  Q5-Q1 lift: {q5_q1_lift:.4f}")
    print(f"\nAbsolute gap (surprise magnitude):")
    print(f"  Q1 (small |gap|) IC: {q1_abs_ic:.4f}")
    print(f"  Q5 (large |gap|) IC: {q5_abs_ic:.4f}")
    print(f"  Q5-Q1 lift: {q5_abs_q1_abs_lift:.4f}")
    print(f"\nYearly breakdown:")
    print(yearly.to_string(index=False))

    # Decision rules
    q5_q1_pos_years = (yearly["q5_q1_gap_lift"] > 0).sum()
    q5_abs_pos_years = (yearly["q5_abs_q1_abs_lift"] > 0).sum()
    total_years = len(yearly)

    # PASS if either gap metric shows consistent lift
    if q5_abs_q1_abs_lift > 0.01 and q5_abs_pos_years >= total_years * 0.6:
        decision = "PASSED"
    elif q5_q1_lift > 0.01 and q5_q1_pos_years >= total_years * 0.6:
        decision = "MIXED"  
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "h413_avg_ic": h413_avg_ic,
            "q1_gap_ic": q1_gap_ic,
            "q5_gap_ic": q5_gap_ic,
            "q5_q1_lift": q5_q1_lift,
            "q1_abs_ic": q1_abs_ic,
            "q5_abs_ic": q5_abs_ic,
            "q5_abs_q1_abs_lift": q5_abs_q1_abs_lift,
            "q5_q1_pos_years": int(q5_q1_pos_years),
            "q5_abs_pos_years": int(q5_abs_pos_years),
            "total_years": int(total_years),
            "panel_rows": int(len(panel)),
        },
        artifacts={
            "yearly": yearly_path,
        },
        metadata={
            "branch": BRANCH_NAME,
            "hypothesis": SPEC.hypothesis,
        },
    )

    print(f"\nDecision: {decision}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()