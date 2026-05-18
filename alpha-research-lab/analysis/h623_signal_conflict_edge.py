"""
H623 - Anti-Coherence / Signal Conflict Edge
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.h62x_common import build_base_panel, evaluate_states
from src.experiment_contract import S1_SCORE_COL, S1_TARGET_COL, ExperimentSpec, build_experiment_context, write_dataframe_artifact  # noqa: E402
from src.repo_paths import data_path  # noqa: E402

BRANCH_NAME = "h623_signal_conflict_edge"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode="research_branch",
    hypothesis="Conflict states (up signals + down signal together) may outperform coherent multi-signal states.",
    start_year=2015,
    end_year=2025,
    min_year_rows=100,
    min_phase_rows=100,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H623")
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--order-stats-path", type=str, default=str(data_path("order_stats/cafef/order_stats_daily.parquet")))
    return parser.parse_args()


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(SPEC, start_year=int(args.start_year), end_year=int(args.end_year))
    context = build_experiment_context(spec, artifact_subdir="research_branches")
    cache_path = str(ROOT / "artifacts" / "cache" / "h62x_base_panel_2015_2025.parquet")
    panel = build_base_panel(spec.start_year, spec.end_year, args.order_stats_path, cache_path=cache_path)

    panel["up_count"] = panel[["c23", "c24", "c26"]].sum(axis=1)
    panel["down_count"] = panel[["c25"]].sum(axis=1)
    panel["composite_conflict"] = panel["composite_2plus"] & (panel["up_count"] >= 1) & (panel["down_count"] >= 1)
    panel["composite_coherent"] = panel["composite_2plus"] & (~panel["composite_conflict"])

    states = ["composite_2plus", "composite_coherent", "composite_conflict"]
    results, yearly = evaluate_states(panel, states, S1_SCORE_COL, S1_TARGET_COL, min_year_rows=spec.min_year_rows)
    results_path = write_dataframe_artifact(results, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")

    coherent_ic = float(results.loc[results["name"] == "composite_coherent", "avg_ic"].iloc[0])
    conflict_ic = float(results.loc[results["name"] == "composite_conflict", "avg_ic"].iloc[0])
    lift = conflict_ic - coherent_ic

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
            "composite_coherent_ic": coherent_ic,
            "composite_conflict_ic": conflict_ic,
            "lift_conflict_vs_coherent": lift,
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
