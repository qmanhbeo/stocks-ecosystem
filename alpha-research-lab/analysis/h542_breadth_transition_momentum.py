"""
H542: Breadth Transition Momentum

Hypothesis: Direction of breadth change (contracting vs expanding) may matter 
more than absolute level. Test if breadth_contracting (high→low) has stronger 
IC than steady_low. Mechanism: as crowd disperses, signal quality improves.

Decision ladder:
- PASS: breadth_contracting IC > steady_low by +0.01 lift
- MIXED: breadth_contracting beats baseline but not steady_low by +0.01
- FAIL: breadth_contracting does not beat steady_low
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


BRANCH_NAME = "breadth_transition_momentum"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Direction of breadth change (contracting vs expanding) may matter "
        "more than absolute level. Test if breadth_contracting (high->low) has stronger "
        "IC than steady_low. Mechanism: as crowd disperses, signal quality improves."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H542 breadth transition momentum experiment")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
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
    c16_df = c16_df[["time", "ticker", "order_volume_ratio_rank"]].rename(
        columns={"order_volume_ratio_rank": "c16_rank"}
    )
    panel = panel.merge(c16_df, on=["time", "ticker"], how="left")

    panel["is_active"] = panel["c16_rank"] <= 0.20

    date_active = panel[panel["is_active"]].groupby("time").size().reset_index(name="active_count")
    panel = panel.merge(date_active, on="time", how="left")
    panel["active_count"] = panel["active_count"].fillna(0)

    breadth_threshold = panel["active_count"].quantile(args.breadth_quintile)
    panel["low_breadth"] = panel["active_count"] <= breadth_threshold
    panel["high_breadth"] = panel["active_count"] > panel["active_count"].quantile(0.80)

    date_df = panel.groupby("time")["active_count"].first().reset_index()
    date_df = date_df.sort_values("time")
    date_df["active_count_lag5"] = date_df["active_count"].shift(5)
    date_df["breadth_change"] = date_df["active_count"] - date_df["active_count_lag5"]
    date_df["breadth_contracting"] = date_df["breadth_change"] < -5
    date_df["breadth_expanding"] = date_df["breadth_change"] > 5
    date_df["breadth_stable"] = (date_df["breadth_change"] >= -5) & (date_df["breadth_change"] <= 5)

    panel = panel.merge(date_df[["time", "breadth_contracting", "breadth_expanding", "breadth_stable"]], on="time", how="left")

    panel["steady_low"] = panel["low_breadth"] & panel["breadth_stable"]
    panel["contracting_to_low"] = panel["low_breadth"] & panel["breadth_contracting"]
    panel["expanding_to_high"] = panel["high_breadth"] & panel["breadth_expanding"]

    panel["all_rows"] = True

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec(
        "contracting_to_low",
        "Breadth contracting from high to low",
        family="candidate",
        baseline="all_rows",
    ),
    StateSpec(
        "steady_low",
        "Stable low breadth (steady)",
        family="control",
        baseline="all_rows",
    ),
    StateSpec(
        "low_breadth",
        "Low breadth (any direction)",
        family="control",
        baseline="all_rows",
    ),
    StateSpec(
        "expanding_to_high",
        "Breadth expanding from low to high",
        family="control",
        baseline="all_rows",
    ),
    StateSpec(
        "high_breadth",
        "High breadth (any direction)",
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
    contracting_ic = results[results["name"] == "contracting_to_low"]["avg_ic"].iloc[0]
    steady_low_ic = results[results["name"] == "steady_low"]["avg_ic"].iloc[0]
    low_breadth_ic = results[results["name"] == "low_breadth"]["avg_ic"].iloc[0]
    
    contracting_lift = contracting_ic - baseline_ic
    vs_steady_lift = contracting_ic - steady_low_ic

    if contracting_lift > 0.01 and vs_steady_lift > 0.01:
        decision = "PASSED"
    elif contracting_lift > 0:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "contracting_ic": float(contracting_ic),
            "contracting_lift": float(contracting_lift),
            "steady_low_ic": float(steady_low_ic),
            "vs_steady_lift": float(vs_steady_lift),
            "low_breadth_ic": float(low_breadth_ic),
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
    print(f"baseline_ic: {baseline_ic:.4f}, contracting: {contracting_ic:.4f}, lift: {contracting_lift:.4f}")
    print(f"steady_low: {steady_low_ic:.4f}, vs_steady: {vs_steady_lift:.4f}")
    print(f"low_breadth: {low_breadth_ic:.4f}")
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()