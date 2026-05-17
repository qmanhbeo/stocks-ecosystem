"""
H538: Capacity Expansion Regime

Hypothesis: Test if contracting capacity (fewer orders over time) + S1 beats 
static tight_capacity. Hidden demand growing = stronger signal.

Decision ladder:
- PASS: capacity_expanding IC > tight_capacity_static by +0.01 lift
- MIXED: capacity_expanding beats baseline but not tight_capacity by +0.01
- FAIL: capacity_expanding does not beat tight_capacity
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


BRANCH_NAME = "capacity_expansion_regime"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Test if contracting capacity (fewer orders over time) + S1 beats "
        "static tight_capacity. Hidden demand growing = stronger signal."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H538 capacity expansion regime experiment")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    parser.add_argument("--capacity-quintile", type=float, default=0.20,
                        help="Quintile threshold for capacity (default 0.20 = bottom 20%)")
    return parser.parse_args()


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )

    c16_path = data_path("features/xs_order_pressure_daily.parquet")
    c16_df = pd.read_parquet(c16_path)
    c16_df = c16_df[["time", "ticker", "order_volume_ratio", "order_volume_ratio_rank"]].rename(
        columns={"order_volume_ratio": "c16_raw", "order_volume_ratio_rank": "c16_rank"}
    )
    panel = panel.merge(c16_df, on=["time", "ticker"], how="left")

    capacity_threshold = panel["c16_raw"].groupby(panel["time"]).transform(
        lambda x: x.quantile(args.capacity_quintile)
    )
    panel["tight_capacity"] = panel["c16_raw"] <= capacity_threshold

    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)

    panel["c16_raw_lag5"] = panel.groupby("ticker")["c16_raw"].shift(5)

    panel["capacity_delta"] = panel["c16_raw"] - panel["c16_raw_lag5"]

    panel["capacity_contracting"] = panel["capacity_delta"] < 0
    panel["capacity_expanding"] = panel["capacity_delta"] > 0

    delta_threshold = panel["capacity_delta"].quantile(0.20)
    panel["strongly_contracting"] = panel["capacity_delta"] <= delta_threshold

    panel["tight_contracting"] = panel["tight_capacity"] & panel["capacity_contracting"]
    panel["tight_expanding"] = panel["tight_capacity"] & panel["capacity_expanding"]
    panel["tight_stable"] = panel["tight_capacity"] & ~panel["capacity_contracting"] & ~panel["capacity_expanding"]

    panel["all_rows"] = True

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec(
        "tight_contracting",
        "Tight capacity + contracting (fewer orders over time)",
        family="candidate",
        baseline="all_rows",
    ),
    StateSpec(
        "tight_expanding",
        "Tight capacity + expanding (more orders over time)",
        family="candidate",
        baseline="all_rows",
    ),
    StateSpec(
        "tight_stable",
        "Tight capacity + stable (no change)",
        family="control",
        baseline="all_rows",
    ),
    StateSpec(
        "tight_capacity",
        "Static tight capacity (any change)",
        family="control",
        baseline="all_rows",
    ),
    StateSpec(
        "capacity_contracting",
        "Contracting capacity (any level)",
        family="control",
        baseline="all_rows",
    ),
    StateSpec(
        "strongly_contracting",
        "Strongly contracting capacity",
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
    tight_capacity_ic = results[results["name"] == "tight_capacity"]["avg_ic"].iloc[0]
    tight_contracting_ic = results[results["name"] == "tight_contracting"]["avg_ic"].iloc[0]
    tight_expanding_ic = results[results["name"] == "tight_expanding"]["avg_ic"].iloc[0]
    
    tight_contracting_lift = tight_contracting_ic - baseline_ic
    vs_tight_capacity_lift = tight_contracting_ic - tight_capacity_ic

    if tight_contracting_lift > 0.01 and vs_tight_capacity_lift > 0.01:
        decision = "PASSED"
    elif tight_contracting_lift > 0:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "tight_capacity_ic": float(tight_capacity_ic),
            "tight_contracting_ic": float(tight_contracting_ic),
            "tight_contracting_lift": float(tight_contracting_lift),
            "vs_tight_capacity_lift": float(vs_tight_capacity_lift),
            "tight_expanding_ic": float(tight_expanding_ic),
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
    print(f"baseline_ic: {baseline_ic:.4f}, tight_capacity: {tight_capacity_ic:.4f}")
    print(f"tight_contracting: {tight_contracting_ic:.4f}, lift: {tight_contracting_lift:.4f}, vs_tight: {vs_tight_capacity_lift:.4f}")
    print(f"tight_expanding: {tight_expanding_ic:.4f}")
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()