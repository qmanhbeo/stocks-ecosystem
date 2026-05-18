"""
H624 - Breadth-Time Interaction (Calendar × Breadth)
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.h62x_common import build_base_panel, evaluate_states  # noqa: E402
from src.experiment_contract import S1_SCORE_COL, S1_TARGET_COL, ExperimentSpec, build_experiment_context, write_dataframe_artifact  # noqa: E402
from src.repo_paths import data_path  # noqa: E402

BRANCH_NAME = "h624_calendar_breadth_interaction"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode="research_branch",
    hypothesis="Calendar day may condition low-breadth regime quality (Monday vs Friday vs other).",
    start_year=2015,
    end_year=2025,
    min_year_rows=100,
    min_phase_rows=100,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H624")
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--order-stats-path", type=str, default=str(data_path("order_stats/cafef/order_stats_daily.parquet")))
    return parser.parse_args()


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(SPEC, start_year=int(args.start_year), end_year=int(args.end_year))
    context = build_experiment_context(spec, artifact_subdir="research_branches")
    cache_path = str(ROOT / "artifacts" / "cache" / "h62x_base_panel_2015_2025.parquet")
    panel = build_base_panel(spec.start_year, spec.end_year, args.order_stats_path, cache_path=cache_path)

    panel["dow"] = panel["time"].dt.dayofweek
    panel["low_breadth_composite"] = panel["composite_2plus"] & panel["low_breadth"]
    panel["low_breadth_monday"] = panel["composite_2plus"] & panel["low_breadth"] & (panel["dow"] == 0)
    panel["low_breadth_friday"] = panel["composite_2plus"] & panel["low_breadth"] & (panel["dow"] == 4)
    panel["low_breadth_other"] = panel["composite_2plus"] & panel["low_breadth"] & (~panel["dow"].isin([0, 4]))

    states = ["composite_2plus", "low_breadth_composite", "low_breadth_monday", "low_breadth_friday", "low_breadth_other"]
    results, yearly = evaluate_states(panel, states, S1_SCORE_COL, S1_TARGET_COL, min_year_rows=spec.min_year_rows)
    results_path = write_dataframe_artifact(results, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")

    lb_ic = float(results.loc[results["name"] == "low_breadth_composite", "avg_ic"].iloc[0])
    day_states = results[results["name"].isin(["low_breadth_monday", "low_breadth_friday", "low_breadth_other"])].copy()
    best_day = day_states.sort_values("avg_ic", ascending=False).iloc[0]
    lift = float(best_day["avg_ic"] - lb_ic)

    if lift > 0.01:
        decision = "PASSED"
    elif lift > 0:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "low_breadth_composite_ic": lb_ic,
            "best_day_state": str(best_day["name"]),
            "best_day_ic": float(best_day["avg_ic"]),
            "lift_best_day_vs_low_breadth": lift,
        },
        artifacts={"results": results_path, "yearly": yearly_path},
        metadata={"hypothesis": SPEC.hypothesis},
    )
    print(results.sort_values("avg_ic", ascending=False).to_string(index=False))
    print(f"decision: {decision}")
    print(f"summary: {summary_path}")
    return summary_path


if __name__ == "__main__":
    run_branch(parse_args())
