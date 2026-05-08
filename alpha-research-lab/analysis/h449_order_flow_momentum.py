"""
H449: order_flow_momentum experiment.

Test C16 acceleration (delta of delta) vs forward IC. Connection: H443 tested 
foreign flow direction but not momentum in order flow. Accelerating vs 
decelerating order pressure might differ.

Uses walk-forward validation with reusable script.
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


BRANCH_NAME = "h449_order_flow_momentum"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "C16 acceleration (delta of delta) vs forward IC. Accelerating order "
        "pressure vs decelerating may differ. Test C16 2nd difference buckets."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("c16_accel_expanding", "C16 acceleration (2nd diff) >> 0 (expanding momentum)", 
            family="c16_momentum", baseline="all_rows"),
    StateSpec("c16_accel_contracting", "C16 acceleration (2nd diff) << 0 (tightening momentum)", 
            family="c16_momentum", baseline="all_rows"),
    StateSpec("c16_accel_neutral", "C16 acceleration near 0", 
            family="c16_momentum", baseline="all_rows"),
    StateSpec("c16_level_high", "C16 level top 20%", 
            family="c16_level", baseline="all_rows"),
    StateSpec("c16_level_low", "C16 level bottom 20%", 
            family="c16_level", baseline="all_rows"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H449 order_flow_momentum experiment")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    return parser.parse_args()


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )
    
    c16_df = pd.read_parquet("data/features/xs_order_pressure_daily.parquet")
    c16_df = c16_df[["time", "ticker", "order_volume_ratio", "order_volume_ratio_rank"]]
    
    panel = panel.merge(c16_df, on=["time", "ticker"], how="inner")
    
    panel = panel.sort_values(["ticker", "time"])
    
    panel["c16_accel"] = panel.groupby("ticker")["order_volume_ratio_rank"].transform(
        lambda x: x.diff().diff()
    )
    
    panel = panel.dropna(subset=["c16_accel"])
    
    panel["all_rows"] = True
    
    c16_accel_pct = panel["c16_accel"].groupby(panel["time"], sort=False).rank(method="average", pct=True)
    panel["c16_accel_expanding"] = c16_accel_pct >= 0.8
    panel["c16_accel_contracting"] = c16_accel_pct <= 0.2
    panel["c16_accel_neutral"] = (c16_accel_pct > 0.2) & (c16_accel_pct < 0.8)
    
    c16_level_pct = panel["order_volume_ratio_rank"].groupby(panel["time"], sort=False).rank(method="average", pct=True)
    panel["c16_level_high"] = c16_level_pct >= 0.8
    panel["c16_level_low"] = c16_level_pct <= 0.2
    
    return panel


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(
        SPEC,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        min_year_rows=int(args.min_year_rows),
        min_phase_rows=int(args.min_phase_rows),
    )
    context = build_experiment_context(spec, artifact_subdir="research_branches")
    panel = load_panel(args, spec)
    validate_state_columns(panel, [state.name for state in STATE_SPECS], spec)

    results, yearly = evaluate_state_specs(
        panel,
        STATE_SPECS,
        score_col=S1_SCORE_COL,
        target_col=S1_TARGET_COL,
        spec=spec,
    )

    results_path = write_dataframe_artifact(results, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}
    baseline = results[results["name"] == "all_rows"].iloc[0]

    best_lift = best_row.get("avg_ic", 0) - baseline.get("avg_ic", 0) if not best.empty else 0
    
    if best_row.get("avg_ic", 0) > baseline.get("avg_ic", 0) + 0.005 and best_row.get("positive_years", 0) >= 8:
        decision = "PASSED"
    elif best_row.get("avg_ic", 0) > baseline.get("avg_ic", 0) - 0.005:
        decision = "MIXED"
    else:
        decision = "FAILED"
    
    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "best_state_by_avg_year_ic": best_row.get("name"),
            "best_avg_year_ic": best_row.get("avg_ic"),
            "best_positive_years": best_row.get("positive_years"),
            "best_years": best_row.get("years"),
            "baseline_avg_ic": baseline.get("avg_ic"),
            "best_ic_lift": best_lift,
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
    )
    print(f"H449 complete: {decision}")
    print(f"Best state: {best_row.get('name')} IC={best_row.get('avg_ic')}, lift={best_lift:.4f}")
    return summary_path


if __name__ == "__main__":
    run_branch(parse_args())