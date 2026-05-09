"""
H441: replacement_quality_delta

Test if quality CHANGE (delta S1) predicts forward IC, not quality LEVEL.
H437 tested quality LEVEL (entering IC=0.066 weakest) - this tests CHANGE.

Mechanism: Change in quality signals new information arrival.
Entering ticker quality vs prior quality - does the DELTA predict?

Required edits:
1. Rename BRANCH_NAME, MODE, and SPEC.hypothesis.
2. Add decision-time features in `load_panel`.
3. Replace STATE_SPECS with fixed, predeclared states and controls.
4. Replace `decision` with the branch's actual pass/mixed/fail ladder.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

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
    evaluate_state_specs,
    load_s1_decision_panel,
    validate_state_columns,
    write_dataframe_artifact,
)


BRANCH_NAME = "replacement_quality_delta"
MODE = "quality_change"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Quality CHANGE (delta S1) predicts forward IC, not quality LEVEL. "
        "H437 tested entering vs exiting quality LEVEL and found entering weakest. "
        "This tests if the DELTA in quality predicts."
    ),
    start_year=2018,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test if quality delta (change) predicts forward IC"
    )
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    parser.add_argument("--lookback-days", type=int, default=5, help="Days to look back for prior S1")
    return parser.parse_args()


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )

    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)

    panel["prior_s1"] = panel.groupby("ticker")[S1_SCORE_COL].shift(int(args.lookback_days))

    panel["quality_delta"] = panel[S1_SCORE_COL] - panel["prior_s1"]

    panel["all_rows"] = True
    panel["positive_delta"] = panel["quality_delta"] > 0
    panel["negative_delta"] = panel["quality_delta"] < 0
    panel["strong_positive_delta"] = panel["quality_delta"] > 0.05
    panel["strong_negative_delta"] = panel["quality_delta"] < -0.05

    return panel


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(
        SPEC,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        min_year_rows=int(args.min_year_rows),
        min_phase_rows=int(args.min_phase_rows),
    )

    STATE_SPECS = [
        StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
        StateSpec(
            "positive_delta",
            "Quality improving (current S1 > prior S1)",
            family="delta",
            baseline="all_rows",
        ),
        StateSpec(
            "negative_delta",
            "Quality declining (current S1 < prior S1)",
            family="delta",
            baseline="all_rows",
        ),
        StateSpec(
            "strong_positive_delta",
            "Quality strongly improving (delta > 0.05)",
            family="delta",
            baseline="all_rows",
        ),
        StateSpec(
            "strong_negative_delta",
            "Quality strongly declining (delta < -0.05)",
            family="delta",
            baseline="all_rows",
        ),
    ]

    context = build_experiment_context(spec, artifact_subdir="h441_quality_delta")
    panel = load_panel(args, spec)
    panel = panel.dropna(subset=["quality_delta"])

    if len(panel) < spec.min_phase_rows:
        print(f"WARN: insufficient rows after quality_delta filter: {len(panel)}")
        decision = "SKIPPED_INSUFFICIENT_DATA"
        summary_path = context.write_summary(
            summary={
                "decision": decision,
                "panel_rows": int(len(panel)),
                "note": "Insufficient data after quality_delta computation",
            },
            artifacts={},
            metadata={},
        )
        print(f"decision: {decision}")
        return summary_path

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

    baseline = results[results["name"] == "all_rows"].iloc[0] if len(results) > 0 else None
    baseline_avg_ic = baseline["avg_ic"] if baseline is not None else 0

    positive_delta = results[results["name"] == "positive_delta"].iloc[0] if len(results[results["name"] == "positive_delta"]) > 0 else None
    negative_delta = results[results["name"] == "negative_delta"].iloc[0] if len(results[results["name"] == "negative_delta"]) > 0 else None

    if positive_delta is not None and baseline is not None:
        lift = positive_delta["avg_ic"] - baseline_avg_ic
    else:
        lift = 0

    decision = "MIXED"
    if lift > 0.01 and positive_delta is not None and positive_delta.get("positive_years", 0) >= 6:
        decision = "PASSED"
    elif lift < -0.01:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_avg_ic": baseline_avg_ic,
            "positive_delta_ic": positive_delta["avg_ic"] if positive_delta is not None else None,
            "negative_delta_ic": negative_delta["avg_ic"] if negative_delta is not None else None,
            "delta_lift": lift,
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
            "best_positive_years": best_row.get("positive_years"),
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "lookback_days": args.lookback_days,
            "hypothesis": "quality change predicts forward IC",
        },
    )

    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(f"decision: {decision}")
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()