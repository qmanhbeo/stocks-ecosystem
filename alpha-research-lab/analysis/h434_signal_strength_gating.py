"""
H434: signal_strength_gating

Hypothesis: Signal strength (S1 strength × C18 strength) predicts forward returns.
When both S1 and C18 are strong, IC should be higher than equal-weight blend.

Test: Bucket tickers by (S1 rank * C18 rank) product.
Compare high-strength vs equal-weight vs S1-only.

Comparing against random baseline (not S1 or C16 baseline).
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
    write_dataframe_artifact,
    validate_state_columns,
)


BRANCH_NAME = "h434_signal_strength_gating"
MODE = "research_branch_signal_strength_gating"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Signal strength gating: bucket tickers by (S1 rank * C18 rank) product. "
        "High-strength state should have higher IC than equal-weight blend."
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
        description="H434 signal strength gating test"
    )
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

    # Load C16 (order_volume_ratio_rank) from published feature
    c16_path = Path("/home/manh/stocks-ecosystem/data/features/xs_order_pressure_daily.parquet")
    c16 = pd.read_parquet(c16_path)[["time", "ticker", "order_volume_ratio_rank"]]

    # Ensure time columns are compatible
    if panel["time"].dtype == "object":
        panel["time"] = pd.to_datetime(panel["time"])
    if c16["time"].dtype == "object":
        c16["time"] = pd.to_datetime(c16["time"])

    panel = panel.merge(c16, on=["time", "ticker"], how="left")

    # H413 baseline: 0.1*Vol + 0.9*S1
    panel["score_h413"] = 0.1 * panel["order_volume_ratio_rank"].fillna(0.5) + 0.9 * panel[S1_SCORE_COL]

    # Compute ranks
    panel["s1_rank"] = panel.groupby("time")[S1_SCORE_COL].rank(method="average", pct=True)
    panel["c18_rank"] = panel.groupby("time")["order_volume_ratio_rank"].rank(method="average", pct=True)

    # Signal strength product
    panel["strength_product"] = panel["s1_rank"] * panel["c18_rank"]

    return panel


def evaluate_strength_states(panel: pd.DataFrame, spec: ExperimentSpec) -> pd.DataFrame:
    """Evaluate signal strength gating states."""

    yearly_results = []
    for year, grp in panel.groupby(pd.to_datetime(panel["time"]).dt.year):
        if year < spec.start_year or year > spec.end_year:
            continue

        s1_ic = grp[[S1_SCORE_COL, S1_TARGET_COL]].corr(method="spearman").iloc[0, 1]
        h413_ic = grp[["score_h413", S1_TARGET_COL]].corr(method="spearman").iloc[0, 1]

        # Bucket by strength product quintile
        grp_sorted = grp.dropna(subset=["strength_product"])
        if len(grp_sorted) < 50:
            continue

        q1_ic = grp_sorted[grp_sorted["strength_product"] <= grp_sorted["strength_product"].quantile(0.2)][[S1_SCORE_COL, S1_TARGET_COL]].corr(method="spearman").iloc[0, 1]
        q5_ic = grp_sorted[grp_sorted["strength_product"] >= grp_sorted["strength_product"].quantile(0.8)][[S1_SCORE_COL, S1_TARGET_COL]].corr(method="spearman").iloc[0, 1]

        yearly_results.append({
            "year": year,
            "s1_ic": s1_ic,
            "h413_ic": h413_ic,
            "q1_strength_ic": q1_ic,
            "q5_strength_ic": q5_ic,
            "q5_q1_lift": q5_ic - q1_ic,
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

    panel = load_panel(args, spec)
    validate_state_columns(panel, [], spec)

    yearly = evaluate_strength_states(panel, spec)

    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")

    s1_avg_ic = yearly["s1_ic"].mean()
    h413_avg_ic = yearly["h413_ic"].mean()
    q1_avg_ic = yearly["q1_strength_ic"].mean()
    q5_avg_ic = yearly["q5_strength_ic"].mean()
    q5_q1_lift = (q5_avg_ic - q1_avg_ic)

    print(f"\n=== H434 Signal Strength Gating Results ===")
    print(f"S1 avg IC: {s1_avg_ic:.4f}")
    print(f"H413 avg IC: {h413_avg_ic:.4f}")
    print(f"Low strength (Q1) IC: {q1_avg_ic:.4f}")
    print(f"High strength (Q5) IC: {q5_avg_ic:.4f}")
    print(f"Q5-Q1 lift: {q5_q1_lift:.4f}")
    print(f"\nYearly breakdown:")
    print(yearly.to_string(index=False))

    # Decision: PASS if Q5-Q1 lift > 0.01 and Q5 has more positive years
    pos_years_q5 = (yearly["q5_strength_ic"] > 0).sum()
    total_years = len(yearly)

    if q5_q1_lift > 0.01 and pos_years_q5 >= total_years * 0.7:
        decision = "PASSED"
    elif q5_q1_lift > 0.005 and pos_years_q5 >= total_years * 0.6:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "s1_avg_ic": s1_avg_ic,
            "h413_avg_ic": h413_avg_ic,
            "q1_avg_ic": q1_avg_ic,
            "q5_avg_ic": q5_avg_ic,
            "q5_q1_lift": q5_q1_lift,
            "q5_pos_years": int(pos_years_q5),
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