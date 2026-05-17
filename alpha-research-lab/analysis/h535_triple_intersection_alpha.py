"""
H535: Triple-Intersection Alpha

Hypothesis: Test tight_capacity + low_breadth + active (C16<0.2) three-way intersection.
H531 (tight+low, 0.1979) + H528 (active+low, 0.2013) suggest triple could exceed 0.21.

Decision ladder:
- PASS: triple_intersection IC > best_two_way by +0.01 lift
- MIXED: triple_intersection beats baseline but not best_two_way by +0.01
- FAIL: triple_intersection does not beat best_two_way
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
from src.repo_paths import data_path


BRANCH_NAME = "triple_intersection_alpha"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Test tight_capacity + low_breadth + active (C16<0.2) three-way intersection. "
        "H531 (tight+low, 0.1979) + H528 (active+low, 0.2013) suggest triple could exceed 0.21."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H535 triple intersection alpha experiment")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    parser.add_argument("--capacity-quintile", type=float, default=0.20,
                        help="Quintile threshold for tight capacity (default 0.20 = bottom 20%)")
    parser.add_argument("--breadth-quintile", type=float, default=0.20,
                        help="Quintile threshold for low breadth (default 0.20 = bottom 20%)")
    return parser.parse_args()


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )

    c16_path = data_path("features/xs_order_pressure_daily.parquet")
    c16_df = pd.read_parquet(c16_path)
    c16_df = c16_df[["time", "ticker", "order_volume_ratio_rank", "order_volume_ratio"]].rename(
        columns={"order_volume_ratio_rank": "c16_rank", "order_volume_ratio": "c16_raw"}
    )
    panel = panel.merge(c16_df, on=["time", "ticker"], how="left")

    panel["is_active"] = panel["c16_rank"] <= 0.20

    date_active = panel[panel["is_active"]].groupby("time").size().reset_index(name="active_count")
    panel = panel.merge(date_active, on="time", how="left")
    panel["active_count"] = panel["active_count"].fillna(0)

    breadth_threshold = panel["active_count"].quantile(args.breadth_quintile)
    panel["low_breadth"] = panel["active_count"] <= breadth_threshold

    capacity_threshold = panel["c16_raw"].groupby(panel["time"]).transform(
        lambda x: x.quantile(args.capacity_quintile)
    )
    panel["tight_capacity"] = panel["c16_raw"] <= capacity_threshold

    panel["tight_low_breadth"] = panel["tight_capacity"] & panel["low_breadth"]
    panel["active_low_breadth"] = panel["is_active"] & panel["low_breadth"]
    panel["tight_active"] = panel["tight_capacity"] & panel["is_active"]
    panel["triple_intersection"] = panel["tight_capacity"] & panel["low_breadth"] & panel["is_active"]

    panel["all_rows"] = True

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec(
        "triple_intersection",
        "tight_capacity + low_breadth + active (C16<=0.2)",
        family="candidate",
        baseline="all_rows",
    ),
    StateSpec(
        "tight_low_breadth",
        "tight_capacity + low_breadth (two-way)",
        family="control",
        baseline="all_rows",
    ),
    StateSpec(
        "active_low_breadth",
        "active + low_breadth (two-way)",
        family="control",
        baseline="all_rows",
    ),
    StateSpec(
        "tight_active",
        "tight_capacity + active (two-way)",
        family="control",
        baseline="all_rows",
    ),
    StateSpec(
        "low_breadth",
        "Low breadth dates only",
        family="control",
        baseline="all_rows",
    ),
    StateSpec(
        "tight_capacity",
        "Tight capacity only",
        family="control",
        baseline="all_rows",
    ),
    StateSpec(
        "is_active",
        "Active state (C16<=0.2) only",
        family="control",
        baseline="all_rows",
    ),
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

    baseline_ic = results[results["name"] == "all_rows"]["avg_ic"].iloc[0]
    triple_ic = results[results["name"] == "triple_intersection"]["avg_ic"].iloc[0]
    
    two_way_cols = ["tight_low_breadth", "active_low_breadth", "tight_active"]
    best_two_way_row = results[results["name"].isin(two_way_cols)].sort_values("avg_ic", ascending=False).iloc[0]
    best_two_way_name = best_two_way_row["name"]
    best_two_way_ic = best_two_way_row["avg_ic"]
    
    triple_lift = triple_ic - baseline_ic
    vs_best_two_way_lift = triple_ic - best_two_way_ic

    if triple_lift > 0.01 and vs_best_two_way_lift > 0.01:
        decision = "PASSED"
    elif triple_lift > 0:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "triple_ic": float(triple_ic),
            "triple_lift": float(triple_lift),
            "best_two_way": best_two_way_name,
            "best_two_way_ic": float(best_two_way_ic),
            "vs_best_two_way_lift": float(vs_best_two_way_lift),
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
    print(f"\ndecision: {decision}")
    print(f"baseline_ic: {baseline_ic:.4f}, triple_ic: {triple_ic:.4f}, lift: {triple_lift:.4f}")
    print(f"best_two_way ({best_two_way_name}): {best_two_way_ic:.4f}, vs: {vs_best_two_way_lift:.4f}")
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()