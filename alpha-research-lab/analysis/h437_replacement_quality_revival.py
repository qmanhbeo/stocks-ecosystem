"""
H437: replacement_quality_revival

Hypothesis: When tickers cycle out of top-k, the QUALITY of new entrants vs exiting
tickers predicts forward IC. Different from H388 which tested FRESHNESS of returning
tickers - this tests QUALITY (S1 IC, C16 IC) of entering vs exiting tickers.

Mechanism: Track top-10 candidate appearances. Compute quality metrics (S1 IC, C16 IC,
forward returns) for tickers entering top-10 vs tickers exiting top-10.
If entering quality > exiting quality, the cycle creates alpha.

Test: Compare entering tickers vs exiting tickers using quality metrics.
Use random baselines (not S1/C16 direct variations).
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


BRANCH_NAME = "h437_replacement_quality_revival"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Quality (S1 IC, C16 IC, forward returns) of entering tickers vs exiting tickers "
        "predicts forward alpha. Different from H388 which tested freshness - this tests "
        "quality. Entering quality > exiting quality = alpha."
    ),
    start_year=2019,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)

STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("top10_entering", "Top-10 entrant: appeared this date, not in prior 20d top-10", family="replacement"),
    StateSpec("top10_exiting", "Top-10 exiting: was in prior 20d top-10, not this date", family="replacement"),
    StateSpec("top10_stable", "Top-10 stable: in both prior and current top-10", family="replacement"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H437 replacement_quality_revival")
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
    panel["all_rows"] = True

    panel["date"] = pd.to_datetime(panel["time"]).dt.normalize()
    panel = panel.sort_values(["ticker", "date"])

    panel["top10_this_date"] = panel.groupby("date")[S1_SCORE_COL].rank(
        ascending=False, method="first"
    ) <= 10

    panel["was_top10_prior_20d"] = panel.groupby("ticker")["top10_this_date"].transform(
        lambda x: x.shift().rolling(20, min_periods=3).max().astype(bool).fillna(False)
    )

    panel["top10_stable"] = panel["top10_this_date"] & panel["was_top10_prior_20d"]
    panel["top10_entering"] = panel["top10_this_date"] & ~panel["was_top10_prior_20d"]
    panel["prior_top10_stable"] = panel.groupby("ticker")["top10_this_date"].shift().rolling(20, min_periods=3).max().astype(bool).fillna(False)
    panel["top10_exiting"] = (~panel["top10_this_date"]) & panel["prior_top10_stable"]

    panel["s1_rank"] = panel.groupby("date")[S1_SCORE_COL].rank(pct=True)

    return panel


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
    panel_path = write_dataframe_artifact(panel, context, f"{BRANCH_NAME}_panel")

    all_rows_ic = results[results["name"] == "all_rows"]["avg_ic"].values
    all_rows_ic_val = float(all_rows_ic[0]) if len(all_rows_ic) > 0 else None

    enter_ic = results[results["name"] == "top10_entering"]["avg_ic"].values
    enter_val = float(enter_ic[0]) if len(enter_ic) > 0 else None

    exit_ic = results[results["name"] == "top10_exiting"]["avg_ic"].values
    exit_val = float(exit_ic[0]) if len(exit_ic) > 0 else None

    stable_ic = results[results["name"] == "top10_stable"]["avg_ic"].values
    stable_val = float(stable_ic[0]) if len(stable_ic) > 0 else None

    pos_years_enter = int(results[results["name"] == "top10_entering"]["positive_years"].values[0]) if len(enter_ic) > 0 else 0
    total_years_enter = int(results[results["name"] == "top10_entering"]["years"].values[0]) if len(enter_ic) > 0 else 0
    pos_years_exit = int(results[results["name"] == "top10_exiting"]["positive_years"].values[0]) if len(exit_ic) > 0 else 0
    total_years_exit = int(results[results["name"] == "top10_exiting"]["years"].values[0]) if len(exit_ic) > 0 else 0
    pos_years_stable = int(results[results["name"] == "top10_stable"]["positive_years"].values[0]) if len(stable_ic) > 0 else 0
    total_years_stable = int(results[results["name"] == "top10_stable"]["years"].values[0]) if len(stable_ic) > 0 else 0

    enter_vs_exit = (enter_val - exit_val) if enter_val is not None and exit_val is not None else None
    enter_vs_stable = (enter_val - stable_val) if enter_val is not None and stable_val is not None else None

    if enter_vs_exit is not None and enter_vs_exit > 0.01 and pos_years_enter >= total_years_enter * 0.6:
        decision = "PASSED"
    elif enter_vs_exit is not None and enter_vs_exit > 0.005 and pos_years_enter >= total_years_enter * 0.5:
        decision = "MIXED"
    elif enter_vs_exit is not None and enter_vs_exit > 0.002:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "all_rows_avg_ic": all_rows_ic_val,
            "top10_entering_avg_ic": enter_val,
            "top10_entering_pos_years": f"{pos_years_enter}/{total_years_enter}",
            "top10_exiting_avg_ic": exit_val,
            "top10_exiting_pos_years": f"{pos_years_exit}/{total_years_exit}",
            "top10_stable_avg_ic": stable_val,
            "top10_stable_pos_years": f"{pos_years_stable}/{total_years_stable}",
            "enter_vs_exit_lift": enter_vs_exit,
            "enter_vs_stable_lift": enter_vs_stable,
            "best_state": results.sort_values("avg_ic", ascending=False, na_position="last").iloc[0]["name"],
            "best_avg_ic": results.sort_values("avg_ic", ascending=False, na_position="last").iloc[0]["avg_ic"],
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
            "panel": panel_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": SPEC.hypothesis,
        },
    )

    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(f"\nEntering IC: {enter_val} ({pos_years_enter}/{total_years_enter} pos years)")
    print(f"Exiting IC: {exit_val} ({pos_years_exit}/{total_years_exit} pos years)")
    print(f"Stable IC: {stable_val} ({pos_years_stable}/{total_years_stable} pos years)")
    print(f"Enter vs Exit lift: {enter_vs_exit}")
    print(f"Enter vs Stable lift: {enter_vs_stable}")
    print(f"Decision: {decision}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()