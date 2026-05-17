"""
H534: Active State Duration Sweet Spot

Hypothesis: Test if time-since-entry into active state (duration bucket) predicts 
IC decay differently. H526 tested fresh vs sustained, not duration buckets.
Sweet spot may exist before decay.

Decision ladder:
- PASS: best duration bucket IC > all_rows by +0.01 lift
- MIXED: best duration bucket beats all_rows but by < +0.01
- FAIL: no duration bucket beats all_rows
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


BRANCH_NAME = "active_state_duration_sweet_spot"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Test if time-since-entry into active state (duration bucket) predicts "
        "IC decay differently. H526 tested fresh vs sustained, not duration buckets."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H534 active state duration sweet spot experiment")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    return parser.parse_args()


def compute_consecutive(series):
    result = np.zeros(len(series), dtype=int)
    count = 0
    for i in range(len(series)):
        if series.iloc[i]:
            count += 1
        else:
            count = 0
        result[i] = count
    return result


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

    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)

    panel["consecutive_active"] = panel.groupby("ticker")["is_active"].transform(
        lambda x: compute_consecutive(x)
    )

    panel["duration_1d"] = (panel["is_active"]) & (panel["consecutive_active"] == 1)
    panel["duration_2_3d"] = (panel["is_active"]) & (panel["consecutive_active"].isin([2, 3]))
    panel["duration_4_7d"] = (panel["is_active"]) & (panel["consecutive_active"].isin([4, 5, 6, 7]))
    panel["duration_8pl"] = (panel["is_active"]) & (panel["consecutive_active"] >= 8)

    panel["fresh_entry"] = panel["duration_1d"]
    panel["sustained"] = panel["duration_2_3d"] | panel["duration_4_7d"] | panel["duration_8pl"]
    panel["active_any"] = panel["is_active"]

    panel["all_rows"] = True

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec(
        "duration_1d",
        "Active state duration 1 day (fresh entry)",
        family="candidate",
        baseline="all_rows",
    ),
    StateSpec(
        "duration_2_3d",
        "Active state duration 2-3 days",
        family="candidate",
        baseline="all_rows",
    ),
    StateSpec(
        "duration_4_7d",
        "Active state duration 4-7 days",
        family="candidate",
        baseline="all_rows",
    ),
    StateSpec(
        "duration_8pl",
        "Active state duration 8+ days",
        family="candidate",
        baseline="all_rows",
    ),
    StateSpec(
        "fresh_entry",
        "Fresh entry (duration 1d) - explicit",
        family="control",
        baseline="all_rows",
    ),
    StateSpec(
        "sustained",
        "Sustained position (duration 2d+)",
        family="control",
        baseline="all_rows",
    ),
    StateSpec(
        "active_any",
        "Any active state (C16 <= 0.2)",
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
    
    duration_cols = ["duration_1d", "duration_2_3d", "duration_4_7d", "duration_8pl"]
    best_duration_row = results[results["name"].isin(duration_cols)].sort_values("avg_ic", ascending=False).iloc[0]
    best_duration_name = best_duration_row["name"]
    best_duration_ic = best_duration_row["avg_ic"]
    best_duration_lift = best_duration_ic - baseline_ic
    
    fresh_entry_ic = results[results["name"] == "fresh_entry"]["avg_ic"].iloc[0]
    active_any_ic = results[results["name"] == "active_any"]["avg_ic"].iloc[0]

    if best_duration_lift > 0.01:
        decision = "PASSED"
    elif best_duration_lift > 0:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "best_duration": best_duration_name,
            "best_duration_ic": float(best_duration_ic),
            "best_duration_lift": float(best_duration_lift),
            "fresh_entry_ic": float(fresh_entry_ic),
            "active_any_ic": float(active_any_ic),
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
    print(f"baseline_ic: {baseline_ic:.4f}, best_duration ({best_duration_name}): {best_duration_ic:.4f}, lift: {best_duration_lift:.4f}")
    print(f"fresh_entry_ic: {fresh_entry_ic:.4f}, active_any_ic: {active_any_ic:.4f}")
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()