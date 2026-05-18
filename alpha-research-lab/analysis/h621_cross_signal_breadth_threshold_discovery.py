"""
H621 - Cross-Signal Breadth Threshold Discovery
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

from analysis.h62x_common import build_base_panel, evaluate_states  # noqa: E402
from src.experiment_contract import (  # noqa: E402
    S1_SCORE_COL,
    S1_TARGET_COL,
    ExperimentSpec,
    build_experiment_context,
    write_dataframe_artifact,
)
from src.repo_paths import data_path  # noqa: E402

BRANCH_NAME = "h621_cross_signal_breadth_threshold_discovery"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode="research_branch",
    hypothesis="Per-signal breadth thresholds may differ (10/20/30 percentile) for C23/C24/C25/C26.",
    start_year=2015,
    end_year=2025,
    min_year_rows=100,
    min_phase_rows=100,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H621")
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--order-stats-path", type=str, default=str(data_path("order_stats/cafef/order_stats_daily.parquet")))
    parser.add_argument("--force-rebuild", action="store_true")
    return parser.parse_args()


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(SPEC, start_year=int(args.start_year), end_year=int(args.end_year))
    context = build_experiment_context(spec, artifact_subdir="research_branches")
    cache_path = str(ROOT / "artifacts" / "cache" / "h62x_base_panel_2015_2025.parquet")
    panel = build_base_panel(
        start_year=spec.start_year,
        end_year=spec.end_year,
        order_stats_path=args.order_stats_path,
        cache_path=cache_path,
        force_rebuild=bool(args.force_rebuild),
    )

    date_frame = panel[["time", "market_active_fraction"]].drop_duplicates().sort_values("time")
    date_frame["breadth_pct_rank"] = date_frame["market_active_fraction"].rank(method="average", pct=True)
    panel = panel.merge(date_frame[["time", "breadth_pct_rank"]], on="time", how="left")

    thresholds = [10, 20, 30]
    signal_cols = ["c23", "c24", "c25", "c26"]
    states: list[str] = ["composite_2plus"]
    for thr in thresholds:
        gate = panel["breadth_pct_rank"] <= (thr / 100.0)
        panel[f"breadth_low_{thr}"] = gate
        for signal in signal_cols:
            state = f"{signal}_low_{thr}"
            panel[state] = panel[signal] & gate
            states.append(state)

    results, yearly = evaluate_states(panel, states, S1_SCORE_COL, S1_TARGET_COL, min_year_rows=spec.min_year_rows)
    results_path = write_dataframe_artifact(results, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")

    opt_rows: list[dict[str, object]] = []
    lifts: list[float] = []
    for signal in signal_cols:
        subset = results[results["name"].str.startswith(f"{signal}_low_")].copy()
        subset["thr"] = subset["name"].str.extract(r"low_(\d+)").astype(float)
        subset = subset.sort_values("avg_ic", ascending=False, na_position="last")
        if subset.empty or subset["avg_ic"].isna().all():
            continue
        best = subset.iloc[0]
        mid = subset[subset["thr"] == 20]
        mid_ic = float(mid["avg_ic"].iloc[0]) if not mid.empty and pd.notna(mid["avg_ic"].iloc[0]) else np.nan
        lift = float(best["avg_ic"] - mid_ic) if pd.notna(mid_ic) else np.nan
        if pd.notna(lift):
            lifts.append(lift)
        opt_rows.append(
            {
                "signal": signal,
                "best_state": best["name"],
                "best_threshold": int(best["thr"]),
                "best_ic": float(best["avg_ic"]),
                "ic_at_20": mid_ic,
                "lift_best_vs_20": lift,
            }
        )
    opt_df = pd.DataFrame(opt_rows)
    opt_path = write_dataframe_artifact(opt_df, context, f"{BRANCH_NAME}_optimal_thresholds")

    unique_opt = int(opt_df["best_threshold"].nunique()) if not opt_df.empty else 0
    mean_lift = float(np.nanmean(lifts)) if lifts else np.nan
    if unique_opt >= 2 and pd.notna(mean_lift) and mean_lift > 0.01:
        decision = "PASSED"
    elif unique_opt >= 2 and pd.notna(mean_lift) and mean_lift > 0:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "unique_optimal_thresholds": unique_opt,
            "mean_lift_best_vs_20": mean_lift,
            "composite_2plus_ic": float(results.loc[results["name"] == "composite_2plus", "avg_ic"].iloc[0]),
        },
        artifacts={"results": results_path, "yearly": yearly_path, "optimal_thresholds": opt_path},
        metadata={"hypothesis": SPEC.hypothesis},
    )
    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    if not opt_df.empty:
        print(opt_df.to_string(index=False))
    print(f"decision: {decision}")
    print(f"summary: {summary_path}")
    return summary_path


if __name__ == "__main__":
    run_branch(parse_args())
