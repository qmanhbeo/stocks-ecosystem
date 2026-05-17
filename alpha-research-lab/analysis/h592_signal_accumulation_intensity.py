"""
H592: Signal Accumulation Intensity

F441 (Session 380): sustained presence in active state = stronger signal.
duration_8pl (8+ days in active) IC=0.1825 (+0.0227 vs active).

Now test: cumulative signal intensity - total days in active state in last 30 days.
A stock that's been active 20/30 days might have stronger alpha than one active today but was quiet 20 days.

Pass criterion: Q4 (highest accumulation) > Q1 (lowest) by > +0.01 IC lift
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
    evaluate_state_specs,
    load_s1_decision_panel,
    validate_state_columns,
    write_dataframe_artifact,
)
from src.repo_paths import data_path


BRANCH_NAME = "signal_accumulation_intensity"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Signal accumulation intensity: cumulative days in active state (last 30d) "
        "predicts stronger alpha. Stocks with sustained presence (20+ days) should "
        "have stronger IC than transient activation (1-2 days)."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H592: Signal Accumulation Intensity")
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

    c16_path = data_path("features/xs_order_pressure_daily.parquet")
    c16_df = pd.read_parquet(c16_path)
    c16_df = c16_df[["time", "ticker", "order_volume_ratio_rank"]].rename(
        columns={"order_volume_ratio_rank": "c16_rank"}
    )

    panel = panel.merge(c16_df, on=["time", "ticker"], how="left")

    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)

    active_threshold = 0.2
    panel["is_active"] = (panel["c16_rank"] <= active_threshold).astype(int)

    panel["active_30d_count"] = (
        panel.groupby("ticker")["is_active"]
        .transform(lambda x: x.rolling(window=30, min_periods=1).sum().shift(1))
    )

    panel["active_30d_intensity"] = panel["active_30d_count"] / 30.0

    panel["accumulation_q1"] = (panel["active_30d_intensity"] <= 0.25).astype(int)
    panel["accumulation_q2"] = ((panel["active_30d_intensity"] > 0.25) & (panel["active_30d_intensity"] <= 0.50)).astype(int)
    panel["accumulation_q3"] = ((panel["active_30d_intensity"] > 0.50) & (panel["active_30d_intensity"] <= 0.75)).astype(int)
    panel["accumulation_q4"] = (panel["active_30d_intensity"] > 0.75).astype(int)
    panel["accumulation_8pl"] = (panel["active_30d_count"] >= 8).astype(int)
    panel["active_only"] = panel["is_active"].astype(int)

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec(
        "active_only",
        "Active state (C16 rank <= 0.2)",
        family="active",
        baseline="all_rows",
    ),
    StateSpec(
        "accumulation_q1",
        "Low accumulation: 0-25th percentile of active_30d_intensity on active rows",
        family="accumulation",
        baseline="active_only",
    ),
    StateSpec(
        "accumulation_q2",
        "Mid-low accumulation: 25-50th percentile",
        family="accumulation",
        baseline="active_only",
    ),
    StateSpec(
        "accumulation_q3",
        "Mid-high accumulation: 50-75th percentile",
        family="accumulation",
        baseline="active_only",
    ),
    StateSpec(
        "accumulation_q4",
        "High accumulation: 75-100th percentile (20+ days in last 30)",
        family="accumulation",
        baseline="active_only",
    ),
    StateSpec(
        "accumulation_8pl",
        "8+ days in active state in last 30 (mimics H534 duration_8pl)",
        family="accumulation",
        baseline="active_only",
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
    print(f"Panel loaded: {len(panel)} rows")

    null_count = panel["active_30d_intensity"].isna().sum()
    print(f"active_30d_intensity nulls: {null_count} (expected for first days per ticker)")

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
    active_only_ic = results[results["name"] == "active_only"]["avg_ic"].iloc[0]
    q1_ic = results[results["name"] == "accumulation_q1"]["avg_ic"].iloc[0]
    q4_ic = results[results["name"] == "accumulation_q4"]["avg_ic"].iloc[0]
    ic_8pl = results[results["name"] == "accumulation_8pl"]["avg_ic"].iloc[0]

    q4_vs_baseline = q4_ic - baseline_ic
    q4_vs_q1 = q4_ic - q1_ic

    print(f"\n=== IC Results ===")
    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(f"\nbaseline_ic: {baseline_ic:.4f}")
    print(f"active_only_ic: {active_only_ic:.4f}")
    print(f"q1_ic: {q1_ic:.4f}")
    print(f"q4_ic: {q4_ic:.4f}")
    print(f"q4 vs baseline: {q4_vs_baseline:+.4f}")
    print(f"q4 vs q1: {q4_vs_q1:+.4f}")

    if q4_vs_baseline > 0.01 and q4_vs_q1 > 0.01:
        decision = "PASSED"
    elif q4_vs_baseline > 0:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "active_only_ic": float(active_only_ic),
            "q1_ic": float(q1_ic),
            "q4_ic": float(q4_ic),
            "q4_vs_baseline": float(q4_vs_baseline),
            "q4_vs_q1": float(q4_vs_q1),
            "accumulation_8pl_ic": float(ic_8pl),
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

    print(f"\ndecision: {decision}")
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()