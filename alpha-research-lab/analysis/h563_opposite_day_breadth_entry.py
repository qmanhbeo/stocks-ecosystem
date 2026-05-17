"""
H563: Opposite-Day Breadth Entry

H525 found low_breadth (bottom 20%) is better than high_breadth.
Hypothesis: Test if the ONSET of low_breadth (first day it becomes low) is 
stronger than sustained low_breadth. The transition from high→low might capture
regime shift alpha that steady state misses.

Honest benchmark: low_breadth IC = ~0.147 (from H525/H529)
Pass criterion: first_day_low_breadth beats sustained_low_breadth by > +0.01 IC
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


BRANCH_NAME = "opposite_day_breadth_entry"
MODE = "research_branch"


def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="H563: Opposite-Day Breadth Entry Test")
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
    date_breadth = date_breadth.sort_values("time")
    date_breadth.columns = ["time", "active_count"]

    breadth_20 = date_breadth["active_count"].quantile(0.20)
    date_breadth["low_breadth"] = date_breadth["active_count"] <= breadth_20
    date_breadth["low_breadth_prev"] = date_breadth["low_breadth"].shift(1).fillna(False)

    date_breadth["first_day_low_breadth"] = date_breadth["low_breadth"] & ~date_breadth["low_breadth_prev"]
    date_breadth["sustained_low_breadth"] = date_breadth["low_breadth"] & date_breadth["low_breadth_prev"]

    panel = panel.merge(date_breadth[["time", "low_breadth", "first_day_low_breadth", "sustained_low_breadth"]], 
                       on="time", how="left")

    return panel


def run_branch(args: argparse.Namespace) -> str:
    spec = ExperimentSpec(
        name=BRANCH_NAME,
        mode=MODE,
        hypothesis=(
            "Test if first day of low_breadth regime is stronger than sustained low_breadth. "
            "The transition from high→low breadth might capture regime shift alpha."
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
        StateSpec("low_breadth", "Low breadth dates (bottom 20%)", family="breadth"),
        StateSpec("first_day_low_breadth", "First day of low_breadth regime (onset)", family="onset"),
        StateSpec("sustained_low_breadth", "Sustained low_breadth (2+ consecutive days)", family="sustained"),
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

    print("=== H563: Opposite-Day Breadth Entry Test ===")
    print(results[["name", "avg_ic", "positive_years", "years"]].sort_values("avg_ic", ascending=False).to_string(index=False))

    baseline = results[results["name"] == "all_rows"]["avg_ic"].iloc[0] if "all_rows" in results["name"].values else results["avg_ic"].mean()
    first_day = results[results["name"] == "first_day_low_breadth"]["avg_ic"].iloc[0] if "first_day_low_breadth" in results["name"].values else 0.0
    sustained = results[results["name"] == "sustained_low_breadth"]["avg_ic"].iloc[0] if "sustained_low_breadth" in results["name"].values else 0.0

    onset_vs_sustained = first_day - sustained

    if onset_vs_sustained > 0.01:
        decision = "PASSED"
    elif onset_vs_sustained > 0.005:
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
            "first_day_ic": first_day,
            "sustained_ic": sustained,
            "onset_vs_sustained": onset_vs_sustained,
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": "first day of low_breadth > sustained",
        },
    )

    print(f"\nBaseline IC: {baseline:.4f}")
    print(f"First Day Low Breadth IC: {first_day:.4f}")
    print(f"Sustained Low Breadth IC: {sustained:.4f}")
    print(f"Onset vs Sustained: {onset_vs_sustained:.4f}")
    print(f"\nDecision: {decision}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()