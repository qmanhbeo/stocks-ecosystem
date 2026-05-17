"""
H560: Signal Mass Entropy as Regime Detector

Hypothesis: H547 found distributed (0.2604) > concentrated (0.1955) by +0.0648.
Test if ENTROPY of signal mass distribution (not just concentration ratio)
is a hidden regime: high entropy = dispersed alpha, low entropy = crowded.

Honest benchmark: distributed concentration = 0.2604, concentrated = 0.1955
Pass criterion: high_entropy beats low_entropy by > +0.01 IC lift
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


BRANCH_NAME = "signal_mass_entropy_regime"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Test if Shannon entropy of S1 mass distribution per date is a hidden "
        "regime detector. High entropy = dispersed alpha = better IC. "
        "Compare with H547's concentration ratio (top-5 share)."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def compute_entropy(series: pd.Series) -> float:
    """Compute Shannon entropy of a distribution."""
    probs = series / series.sum()
    probs = probs[probs > 0]
    return -(probs * np.log(probs)).sum()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H560: Signal Mass Entropy Regime Test")
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

    date_entropy = (
        panel.groupby("time")[S1_SCORE_COL]
        .apply(compute_entropy)
        .reset_index()
        .rename(columns={S1_SCORE_COL: "s1_entropy"})
    )

    panel = panel.merge(date_entropy, on="time", how="left")

    entropy_rank = panel["s1_entropy"].groupby(panel["time"], sort=False).rank(method="average", pct=True)
    panel["entropy_quintile"] = pd.qcut(panel["s1_entropy"].rank(method="first"), 5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"])

    q1_threshold = panel["s1_entropy"].quantile(0.20)
    q5_threshold = panel["s1_entropy"].quantile(0.80)
    panel["low_entropy"] = panel["s1_entropy"] <= q1_threshold
    panel["high_entropy"] = panel["s1_entropy"] >= q5_threshold

    panel["entropy_q1"] = panel["entropy_quintile"] == "Q1"
    panel["entropy_q5"] = panel["entropy_quintile"] == "Q5"

    date_breadth = panel.groupby("time")["ticker"].nunique().reset_index()
    date_breadth.columns = ["time", "active_count"]
    panel = panel.merge(date_breadth, on="time", how="left")

    breadth_20 = panel["active_count"].quantile(0.20)
    panel["low_breadth"] = panel["active_count"] <= breadth_20
    panel["low_entropy_low_breadth"] = (panel["s1_entropy"] <= q1_threshold) & (panel["active_count"] <= breadth_20)
    panel["high_entropy_low_breadth"] = (panel["s1_entropy"] >= q5_threshold) & (panel["active_count"] <= breadth_20)

    return panel


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(
        SPEC,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        min_year_rows=int(args.min_year_rows),
        min_phase_rows=int(args.min_phase_rows),
    )
    context = build_experiment_context(spec, artifact_subdir="research_branch")

    panel = load_panel(args, spec)

    STATE_SPECS = [
        StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
        StateSpec("low_entropy", "Low entropy dates (Q1, concentrated signal mass)", family="entropy_regime"),
        StateSpec("high_entropy", "High entropy dates (Q5, dispersed signal mass)", family="entropy_regime"),
        StateSpec("entropy_q1", "Bottom entropy quintile (most concentrated)", family="entropy_quintile"),
        StateSpec("entropy_q5", "Top entropy quintile (most dispersed)", family="entropy_quintile"),
        StateSpec("low_breadth", "Low breadth dates (bottom 20%)", family="breadth"),
        StateSpec("low_entropy_low_breadth", "Low entropy + Low breadth (same regime as H547)", family="combo"),
        StateSpec("high_entropy_low_breadth", "High entropy + Low breadth", family="combo"),
    ]

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

    entropy_summary = panel.groupby("entropy_quintile").agg(
        mean_entropy=("s1_entropy", "mean"),
        dates=("time", "nunique"),
        rows=("time", "count"),
    ).reset_index()

    entropy_path = write_dataframe_artifact(entropy_summary, context, f"{BRANCH_NAME}_entropy_summary")

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    baseline = results[results["name"] == "all_rows"]["avg_ic"].iloc[0]
    high_ent = results[results["name"] == "high_entropy"]["avg_ic"].iloc[0]
    low_ent = results[results["name"] == "low_entropy"]["avg_ic"].iloc[0]
    entropy_lift = high_ent - low_ent

    if entropy_lift > 0.01:
        decision = "PASSED"
    elif entropy_lift > 0.005:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": baseline,
            "high_entropy_ic": high_ent,
            "low_entropy_ic": low_ent,
            "entropy_lift": entropy_lift,
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
            "entropy_summary": entropy_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": "entropy as regime detector",
        },
    )

    print("\n=== H560: Signal Mass Entropy Regime Test ===")
    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(f"\nBaseline IC: {baseline:.4f}")
    print(f"High Entropy IC: {high_ent:.4f}")
    print(f"Low Entropy IC: {low_ent:.4f}")
    print(f"Entropy Lift: {entropy_lift:.4f}")
    print(f"\nDecision: {decision}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()