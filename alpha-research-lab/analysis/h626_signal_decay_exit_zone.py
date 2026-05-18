"""
H626 - Signal Decay Acceleration / Exit Zone
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

BRANCH_NAME = "h626_signal_decay_exit_zone"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode="research_branch",
    hypothesis="Composite_2plus may decay after long persistence; test run-age buckets 1-7/8-20/21-30/31+.",
    start_year=2015,
    end_year=2025,
    min_year_rows=100,
    min_phase_rows=100,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H626")
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--order-stats-path", type=str, default=str(data_path("order_stats/cafef/order_stats_daily.parquet")))
    return parser.parse_args()


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(SPEC, start_year=int(args.start_year), end_year=int(args.end_year))
    context = build_experiment_context(spec, artifact_subdir="research_branches")
    cache_path = str(ROOT / "artifacts" / "cache" / "h62x_base_panel_2015_2025.parquet")
    panel = build_base_panel(spec.start_year, spec.end_year, args.order_stats_path, cache_path=cache_path)

    panel = panel.sort_values(["ticker", "time"]).copy()
    panel["accum_60d"] = panel.groupby("ticker")["composite_2plus"].transform(
        lambda s: s.astype(int).rolling(window=60, min_periods=1).sum()
    )

    panel["age_1_7"] = panel["composite_2plus"] & panel["accum_60d"].between(1, 7)
    panel["age_8_20"] = panel["composite_2plus"] & panel["accum_60d"].between(8, 20)
    panel["age_21_30"] = panel["composite_2plus"] & panel["accum_60d"].between(21, 30)
    panel["age_31_plus"] = panel["composite_2plus"] & (panel["accum_60d"] >= 31)

    states = ["composite_2plus", "age_1_7", "age_8_20", "age_21_30", "age_31_plus"]
    results, yearly = evaluate_states(panel, states, S1_SCORE_COL, S1_TARGET_COL, min_year_rows=spec.min_year_rows)
    results_path = write_dataframe_artifact(results, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")

    ic_21_30 = float(results.loc[results["name"] == "age_21_30", "avg_ic"].iloc[0])
    ic_31p = float(results.loc[results["name"] == "age_31_plus", "avg_ic"].iloc[0])
    lift = ic_21_30 - ic_31p

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
            "age_21_30_ic": ic_21_30,
            "age_31_plus_ic": ic_31p,
            "lift_21_30_vs_31plus": lift,
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
