"""
H625 - Ticker-Specific Breadth (Self-Reference)
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

BRANCH_NAME = "h625_ticker_self_breadth_reference"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode="research_branch",
    hypothesis="Ticker self-referenced breadth may condition composite_2plus better than market-wide breadth.",
    start_year=2015,
    end_year=2025,
    min_year_rows=100,
    min_phase_rows=100,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H625")
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--order-stats-path", type=str, default=str(data_path("order_stats/cafef/order_stats_daily.parquet")))
    return parser.parse_args()


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(SPEC, start_year=int(args.start_year), end_year=int(args.end_year))
    context = build_experiment_context(spec, artifact_subdir="research_branches")
    cache_path = str(ROOT / "artifacts" / "cache" / "h62x_base_panel_2015_2025.parquet")
    panel = build_base_panel(spec.start_year, spec.end_year, args.order_stats_path, cache_path=cache_path)

    panel["self_hist_rank"] = panel.groupby("ticker")["signal_count_30d_avg"].rank(method="average", pct=True)
    panel["self_hist_quiet"] = panel["self_hist_rank"] <= 0.2
    panel["self_hist_hot"] = panel["self_hist_rank"] >= 0.8

    panel["composite_market_low"] = panel["composite_2plus"] & panel["low_breadth"]
    panel["composite_self_hist_quiet"] = panel["composite_2plus"] & panel["self_hist_quiet"]
    panel["composite_self_hist_hot"] = panel["composite_2plus"] & panel["self_hist_hot"]

    states = [
        "composite_2plus",
        "composite_market_low",
        "composite_self_hist_quiet",
        "composite_self_hist_hot",
    ]
    results, yearly = evaluate_states(panel, states, S1_SCORE_COL, S1_TARGET_COL, min_year_rows=spec.min_year_rows)
    results_path = write_dataframe_artifact(results, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")

    market_ic = float(results.loc[results["name"] == "composite_market_low", "avg_ic"].iloc[0])
    quiet_ic = float(results.loc[results["name"] == "composite_self_hist_quiet", "avg_ic"].iloc[0])
    hot_ic = float(results.loc[results["name"] == "composite_self_hist_hot", "avg_ic"].iloc[0])
    best_ic = max(quiet_ic, hot_ic)
    best_name = "composite_self_hist_quiet" if quiet_ic >= hot_ic else "composite_self_hist_hot"
    lift = best_ic - market_ic

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
            "composite_market_low_ic": market_ic,
            "composite_self_hist_quiet_ic": quiet_ic,
            "composite_self_hist_hot_ic": hot_ic,
            "best_self_variant": best_name,
            "lift_best_self_variant_vs_market_low": lift,
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
