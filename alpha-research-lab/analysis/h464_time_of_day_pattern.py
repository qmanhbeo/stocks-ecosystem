"""
H464: time_of_day_pattern

Hypothesis: VN market has specific calendar/session patterns driven by:
- T+2 settlement: buy on Monday, settlement Tuesday; sell on Wednesday, settlement Friday
- Monday effect: first trading day of week has distinct patterns
- Month-end: last 3 trading days of month have distinct patterns
- Quarter-start: first 10 trading days of quarter have distinct patterns

First test: calendar pattern states vs random baseline.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import sys
from pathlib import Path

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
from src.repo_paths import data_path


BRANCH_NAME = "time_of_day_pattern"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "VN market has specific calendar patterns: T+2 settlement mechanics, "
        "Monday effect, month-end, quarter-start. Test these calendar states vs random baseline."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H464 time_of_day_pattern test")
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

    dt = panel["time"].dt

    panel["is_monday"] = dt.dayofweek == 0
    panel["is_friday"] = dt.dayofweek == 4
    panel["is_weekstart"] = dt.dayofweek <= 1

    panel["day_of_month"] = dt.day
    panel["is_month_end"] = (dt.day >= 25).astype(bool)
    panel["is_month_start"] = (dt.day <= 5).astype(bool)
    panel["is_month_middle"] = ((dt.day > 5) & (dt.day < 25)).astype(bool)

    panel["month"] = dt.month
    panel["is_january"] = dt.month == 1
    panel["is_tet_month"] = (dt.month == 1) | (dt.month == 2)
    panel["is_quarter_start"] = dt.day <= 10

    panel["week_of_year"] = dt.isocalendar().week.astype(int)
    panel["is_week1_of_month"] = (dt.day <= 7).astype(bool)

    last_trading_day_by_month = panel.groupby(
        [panel["time"].dt.year.rename("year"), panel["time"].dt.month.rename("month")]
    )["time"].transform("max")
    panel["is_last_trading_day"] = (panel["time"] == last_trading_day_by_month).astype(bool)

    last_3_days_mask = panel.groupby(
        [panel["time"].dt.year.rename("year"), panel["time"].dt.month.rename("month")]
    )["time"].transform(lambda x: x >= x.max() - pd.Timedelta(days=3))
    panel["is_last_3d"] = last_3_days_mask.astype(bool)

    panel["all_rows"] = True

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("is_monday", "Monday effect", family="weekday"),
    StateSpec("is_friday", "Friday effect", family="weekday"),
    StateSpec("is_weekstart", "Monday-Tuesday (T+2 settlement window)", family="weekday"),
    StateSpec("is_january", "January effect", family="month"),
    StateSpec("is_tet_month", "Jan-Feb (Tet season)", family="month"),
    StateSpec("is_month_end", "Month end (day >= 25)", family="month"),
    StateSpec("is_month_start", "Month start (day <= 5)", family="month"),
    StateSpec("is_last_3d", "Last 3 trading days of month", family="month"),
    StateSpec("is_quarter_start", "Quarter start (day <= 10)", family="quarter"),
    StateSpec("is_week1_of_month", "Week 1 of month (day <= 7)", family="month"),
]


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

    baseline_ic = results[results["name"] == "all_rows"]["avg_ic"].iloc[0] if not results.empty else 0

    non_baseline = results[results["name"] != "all_rows"].copy()
    best_state = non_baseline.sort_values("avg_ic", ascending=False, na_position="last").iloc[0] if not non_baseline.empty else {}
    best_name = best_state.get("name", "none")
    best_ic = best_state.get("avg_ic", 0)
    best_lift = best_state.get("avg_ic", 0) - baseline_ic

    monday_ic = results[results["name"] == "is_monday"]["avg_ic"].iloc[0] if not results.empty else 0
    friday_ic = results[results["name"] == "is_friday"]["avg_ic"].iloc[0] if not results.empty else 0
    monday_lift = monday_ic - baseline_ic
    friday_lift = friday_ic - baseline_ic

    month_end_ic = results[results["name"] == "is_month_end"]["avg_ic"].iloc[0] if not results.empty else 0
    last_3d_ic = results[results["name"] == "is_last_3d"]["avg_ic"].iloc[0] if not results.empty else 0
    quarter_start_ic = results[results["name"] == "is_quarter_start"]["avg_ic"].iloc[0] if not results.empty else 0

    decision = "FAILED"
    if best_lift > 0.010:
        decision = "PASSED"
    elif best_lift > 0.003:
        decision = "MIXED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "best_state": best_name,
            "best_state_ic": float(best_ic),
            "best_lift": float(best_lift),
            "monday_ic": float(monday_ic),
            "monday_lift": float(monday_lift),
            "friday_ic": float(friday_ic),
            "friday_lift": float(friday_lift),
            "month_end_ic": float(month_end_ic),
            "last_3d_ic": float(last_3d_ic),
            "quarter_start_ic": float(quarter_start_ic),
            "positive_years": int(best_state.get("positive_years", 0)),
            "best_years": int(best_state.get("years", 0)),
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": SPEC.hypothesis,
        },
    )

    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(f"\nDecision: {decision}")
    print(f"Baseline IC: {baseline_ic:.4f}")
    print(f"\nCalendar patterns:")
    print(f"  monday: {monday_ic:.4f} (lift: {monday_lift:+.4f})")
    print(f"  friday: {friday_ic:.4f} (lift: {friday_lift:+.4f})")
    print(f"  month_end: {month_end_ic:.4f}")
    print(f"  last_3d: {last_3d_ic:.4f}")
    print(f"  quarter_start: {quarter_start_ic:.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()