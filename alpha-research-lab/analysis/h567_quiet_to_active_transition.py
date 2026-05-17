"""
H567: Quiet-to-Active Transition Probability

H548: quiet decay exists but quiet is anti-predictive
Hypothesis: Test TRANSITION PROBABILITY from quiet to active as entry condition.
Catching stocks ABOUT to activate (transitioning from quiet toward active) 
might be the alpha - pre-crowd entry before the mass arrives.

Pass criterion: transitioning_quiet beats steady_quiet by > +0.01 IC
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


BRANCH_NAME = "quiet_to_active_transition_prob"
MODE = "research_branch"


def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="H567: Quiet-to-Active Transition Probability Test")
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

    panel = panel.sort_values(["ticker", "time"])
    panel["c16_level"] = panel["order_volume_ratio_rank"]
    panel["was_quiet"] = panel.groupby("ticker")["c16_level"].transform(lambda x: (x >= 0.75).shift(1)).fillna(False)
    panel["is_quiet"] = panel["c16_level"] >= 0.75

    panel["was_active"] = panel.groupby("ticker")["c16_level"].transform(lambda x: (x <= 0.2).shift(1)).fillna(False)

    panel["quiet_to_active_transition"] = panel["is_quiet"] & ~panel["was_quiet"] & ~panel["was_active"]
    panel["quiet_steady"] = panel["is_quiet"] & panel["was_quiet"]
    panel["active_steady"] = panel["c16_level"] <= 0.2

    return panel


def run_branch(args: argparse.Namespace) -> str:
    spec = ExperimentSpec(
        name=BRANCH_NAME,
        mode=MODE,
        hypothesis=(
            "Test quiet-to-active transition probability. Catching stocks ABOUT to "
            "activate (pre-crowd entry) might be stronger than steady quiet."
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
        StateSpec("is_quiet", "Currently quiet (C16 >= 0.75)", family="quiet"),
        StateSpec("quiet_steady", "Steady quiet (was quiet, is quiet)", family="quiet_state"),
        StateSpec("quiet_to_active_transition", "Quiet→Active transition (was quiet, not active yet)", family="transition"),
    ]

    available_cols = [s.name for s in STATE_SPECS if s.name in panel.columns]
    STATE_SPECS = [s for s in STATE_SPECS if s.name in available_cols]

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

    print("=== H567: Quiet-to-Active Transition Probability Test ===")
    print(results[["name", "avg_ic", "positive_years", "years", "pooled_rows"]].sort_values("avg_ic", ascending=False).to_string(index=False))

    baseline = results[results["name"] == "all_rows"]["avg_ic"].iloc[0] if "all_rows" in results["name"].values else results["avg_ic"].mean()
    quiet_steady = results[results["name"] == "quiet_steady"]["avg_ic"].iloc[0] if "quiet_steady" in results["name"].values else 0.0
    transition = results[results["name"] == "quiet_to_active_transition"]["avg_ic"].iloc[0] if "quiet_to_active_transition" in results["name"].values else 0.0

    transition_vs_steady = transition - quiet_steady

    if transition_vs_steady > 0.01:
        decision = "PASSED"
    elif transition_vs_steady > 0.005:
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
            "quiet_steady_ic": quiet_steady,
            "transition_ic": transition,
            "transition_vs_steady": transition_vs_steady,
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": "quiet-to-active transition probability",
        },
    )

    print(f"\nBaseline IC: {baseline:.4f}")
    print(f"Quiet Steady IC: {quiet_steady:.4f}")
    print(f"Transition (quiet→active) IC: {transition:.4f}")
    print(f"Transition vs Steady: {transition_vs_steady:.4f}")
    print(f"\nDecision: {decision}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()