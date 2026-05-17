"""
H564: Breadth Quintile Gate

Current: bottom 20% = low_breadth (binary)
Hypothesis: Test BREADTH QUINTILES as dynamic gate. Q1 (lowest breadth) = high 
participation regime, Q5 (highest) = low participation. Different quintiles may 
need different S1 thresholds or capture different alpha.

Pass criterion: Q1 beats binary low_breadth by > +0.01 IC, or find monotonic pattern
"""

from __future__ import annotations

import argparse
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
    validate_state_columns,
    write_dataframe_artifact,
    normalize_time_ticker,
    restrict_years,
)
from src.repo_paths import data_path


BRANCH_NAME = "breadth_quintile_gate"
MODE = "research_branch"


def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="H564: Breadth Quintile Gate Test")
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    return parser.parse_args()


def load_panel(args: argparse.Namespace) -> pd.DataFrame:
    s1_path = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
    s1_df = pd.read_parquet(s1_path, columns=["time", "ticker", "xs_proba", "actual"])
    s1_df = normalize_time_ticker(s1_df, source="S1 panel")
    s1_df = restrict_years(s1_df, start_year=args.start_year, end_year=args.end_year, source="S1 panel")
    s1_df = s1_df.rename(columns={"xs_proba": "s1_xs_proba", "actual": "s1_barrier_hit_1d"})

    c16_path = data_path("features/xs_order_pressure_daily.parquet")
    c16_df = pd.read_parquet(c16_path)
    c16_df = normalize_time_ticker(c16_df, source="C16 panel")
    c16_df = restrict_years(c16_df, start_year=args.start_year, end_year=args.end_year, source="C16 panel")

    panel = s1_df.merge(c16_df, on=["time", "ticker"], how="inner")
    print(f"Merged panel: {len(panel)} rows")

    date_breadth = panel.groupby("time")["ticker"].nunique().reset_index()
    date_breadth.columns = ["time", "active_count"]

    breadth_20 = date_breadth["active_count"].quantile(0.20)
    date_breadth["low_breadth_binary"] = date_breadth["active_count"] <= breadth_20

    date_breadth["breadth_quintile"] = pd.qcut(date_breadth["active_count"].rank(method="first"), 5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"])

    panel = panel.merge(date_breadth[["time", "low_breadth_binary", "breadth_quintile"]], on="time", how="left")

    panel["breadth_q1"] = panel["breadth_quintile"] == "Q1"
    panel["breadth_q2"] = panel["breadth_quintile"] == "Q2"
    panel["breadth_q3"] = panel["breadth_quintile"] == "Q3"
    panel["breadth_q4"] = panel["breadth_quintile"] == "Q4"
    panel["breadth_q5"] = panel["breadth_quintile"] == "Q5"

    return panel


def run_branch(args: argparse.Namespace) -> str:
    spec = ExperimentSpec(
        name=BRANCH_NAME,
        mode=MODE,
        hypothesis=(
            "Test breadth quintiles (Q1-Q5) vs binary bottom 20%. "
            "Different quintiles may capture different alpha regimes."
        ),
        start_year=2015,
        end_year=2025,
        min_year_rows=500,
        min_phase_rows=500,
        target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
        score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
    )
    context = build_experiment_context(spec, artifact_subdir="research_branch")

    panel = load_panel(args)

    STATE_SPECS = [
        StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
        StateSpec("low_breadth_binary", "Binary low_breadth (bottom 20%)", family="binary"),
        StateSpec("breadth_q1", "Breadth Q1 (lowest 20%)", family="quintile"),
        StateSpec("breadth_q2", "Breadth Q2", family="quintile"),
        StateSpec("breadth_q3", "Breadth Q3", family="quintile"),
        StateSpec("breadth_q4", "Breadth Q4", family="quintile"),
        StateSpec("breadth_q5", "Breadth Q5 (highest 20%)", family="quintile"),
    ]

    available_states = [s.name for s in STATE_SPECS if s.name in panel.columns]
    STATE_SPECS = [s for s in STATE_SPECS if s.name in available_states]

    validate_state_columns(panel, [state.name for state in STATE_SPECS], spec)

    results, yearly = evaluate_state_specs(
        panel,
        STATE_SPECS,
        score_col="s1_xs_proba",
        target_col="s1_barrier_hit_1d",
        spec=spec,
    )

    results_path = write_dataframe_artifact(results, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")

    print("=== H564: Breadth Quintile Gate Test ===")
    print(results[["name", "avg_ic", "positive_years", "years"]].sort_values("avg_ic", ascending=False).to_string(index=False))

    baseline = results[results["name"] == "all_rows"]["avg_ic"].iloc[0] if "all_rows" in results["name"].values else results["avg_ic"].mean()
    binary = results[results["name"] == "low_breadth_binary"]["avg_ic"].iloc[0] if "low_breadth_binary" in results["name"].values else 0.0
    q1 = results[results["name"] == "breadth_q1"]["avg_ic"].iloc[0] if "breadth_q1" in results["name"].values else 0.0

    q1_vs_binary = q1 - binary

    if q1_vs_binary > 0.01:
        decision = "PASSED"
    elif q1_vs_binary > 0.005:
        decision = "MIXED"
    else:
        decision = "FAILED"

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": baseline,
            "binary_low_breadth_ic": binary,
            "q1_ic": q1,
            "q1_vs_binary": q1_vs_binary,
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": "quintiles vs binary",
        },
    )

    print(f"\nBaseline IC: {baseline:.4f}")
    print(f"Binary Low Breadth IC: {binary:.4f}")
    print(f"Q1 (lowest breadth) IC: {q1:.4f}")
    print(f"Q1 vs Binary: {q1_vs_binary:.4f}")
    print(f"\nDecision: {decision}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()