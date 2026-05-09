"""
H478 - zero_liquidity_anomaly

Hypothesis: EXTREME illiquidity (zero volume days) with high C16 = hidden demand 
that couldn't execute. When tickers have zero volume days but high order pressure, 
it indicates hidden demand waiting to be executed - the lack of volume is not lack 
of interest but lack of supply.

Compare with random baselines (not S1/C16 variation).
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


BRANCH_NAME = "zero_liquidity_anomaly"
MODE = "zero_liquidity_test"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "EXTREME illiquidity (zero volume days) with high C16 = hidden demand "
        "that couldn't execute. Zero volume = hidden demand waiting, not lack of interest."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)

STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec(
        "zero_volume_high_c16",
        "Zero volume days + high C16 order pressure",
        family="zero_liquidity",
        baseline="all_rows",
    ),
    StateSpec(
        "zero_volume_any_c16",
        "Zero volume days + any C16 present",
        family="zero_liquidity",
        baseline="all_rows",
    ),
    StateSpec(
        "low_volume_high_c16",
        "Low volume (bottom 20%) + high C16",
        family="low_liquidity",
        baseline="all_rows",
    ),
    StateSpec(
        "high_c16_only",
        "High C16 only (control: same C16 threshold without volume filter)",
        family="c16_control",
        baseline="all_rows",
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="H478 zero_liquidity_anomaly: test zero volume days × C16 pressure"
    )
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    parser.add_argument("--c16-path", type=str, default="/home/manh/stocks-ecosystem/data/features/xs_order_pressure_daily.parquet")
    parser.add_argument("--order-stats-path", type=str, default="/home/manh/stocks-ecosystem/data/order_stats/cafef/order_stats_daily.parquet")
    parser.add_argument("--c16-high-threshold", type=float, default=0.80, help="C16 rank threshold for 'high' (default 0.80)")
    parser.add_argument("--volume-low-threshold", type=float, default=0.20, help="Volume percentile threshold for 'low' (default 0.20)")
    return parser.parse_args()


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )

    order_stats = pd.read_parquet(args.order_stats_path)
    order_stats["time"] = pd.to_datetime(order_stats["date"])
    order_stats["total_volume"] = order_stats["buy_order_volume"] + order_stats["sell_order_volume"]
    order_stats["is_zero_volume"] = order_stats["total_volume"] == 0

    c16 = pd.read_parquet(args.c16_path)
    c16["time"] = pd.to_datetime(c16["time"])
    c16["c16"] = c16["order_volume_ratio"]
    c16["c16_rank"] = c16["order_volume_ratio_rank"]
    c16_high = c16["c16_rank"] >= args.c16_high_threshold

    order_stats_agg = order_stats.groupby(["ticker", "time"]).agg({
        "total_volume": "sum",
        "is_zero_volume": "any",
    }).reset_index()

    panel = panel.merge(
        order_stats_agg[["ticker", "time", "total_volume", "is_zero_volume"]],
        on=["ticker", "time"],
        how="left",
    )

    panel = panel.merge(
        c16[["ticker", "time", "c16", "c16_rank"]],
        on=["ticker", "time"],
        how="left",
    )

    panel["total_volume"] = panel["total_volume"].fillna(0)
    panel["is_zero_volume"] = panel["is_zero_volume"].fillna(False)
    panel["c16"] = panel["c16"].fillna(0)
    panel["c16_rank"] = panel["c16_rank"].fillna(0)

    panel["all_rows"] = True

    c16_high = panel["c16_rank"] >= args.c16_high_threshold
    panel["zero_volume_high_c16"] = (panel["is_zero_volume"]) & (c16_high)

    panel["zero_volume_any_c16"] = (panel["is_zero_volume"]) & (panel["c16"] > 0)

    panel["volume_rank"] = panel["total_volume"].groupby(panel["time"], sort=False).rank(method="average", pct=True)
    volume_low = panel["volume_rank"] <= args.volume_low_threshold
    panel["low_volume_high_c16"] = volume_low & c16_high

    panel["high_c16_only"] = c16_high

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

    baseline = results[results["name"] == "all_rows"].iloc[0]
    baseline_ic = baseline["avg_ic"]

    def compute_lift(row):
        if row["name"] == "all_rows" or pd.isna(row["avg_ic"]):
            return 0.0
        return row["avg_ic"] - baseline_ic

    results["lift_vs_baseline"] = results.apply(compute_lift, axis=1)

    sorted_results = results.sort_values("avg_ic", ascending=False, na_position="last")

    zero_vol_high = results[results["name"] == "zero_volume_high_c16"].iloc[0] if len(results[results["name"] == "zero_volume_high_c16"]) > 0 else None
    high_c16_only = results[results["name"] == "high_c16_only"].iloc[0] if len(results[results["name"] == "high_c16_only"]) > 0 else None

    decision = "FAILED"
    if zero_vol_high is not None and not pd.isna(zero_vol_high["avg_ic"]):
        if zero_vol_high["lift_vs_baseline"] > 0.005 and zero_vol_high["positive_years"] >= 6:
            decision = "PASSED"
        elif zero_vol_high["lift_vs_baseline"] > 0.002:
            decision = "MIXED"

    if high_c16_only is not None and not pd.isna(high_c16_only["avg_ic"]):
        if zero_vol_high is not None and not pd.isna(zero_vol_high["avg_ic"]):
            zero_vs_control = zero_vol_high["avg_ic"] - high_c16_only["avg_ic"]
            if abs(zero_vs_control) < 0.005:
                decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "zero_volume_high_c16_ic": float(zero_vol_high["avg_ic"]) if zero_vol_high is not None and not pd.isna(zero_vol_high["avg_ic"]) else None,
            "zero_volume_high_c16_lift": float(zero_vol_high["lift_vs_baseline"]) if zero_vol_high is not None and not pd.isna(zero_vol_high["lift_vs_baseline"]) else None,
            "zero_volume_high_c16_pos_years": int(zero_vol_high["positive_years"]) if zero_vol_high is not None else None,
            "high_c16_only_ic": float(high_c16_only["avg_ic"]) if high_c16_only is not None and not pd.isna(high_c16_only["avg_ic"]) else None,
            "zero_vs_control_lift": float(zero_vol_high["avg_ic"] - high_c16_only["avg_ic"]) if zero_vol_high is not None and high_c16_only is not None and not pd.isna(zero_vol_high["avg_ic"]) and not pd.isna(high_c16_only["avg_ic"]) else None,
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": SPEC.hypothesis,
        },
    )

    print("\n=== H478 Zero Liquidity Anomaly Results ===")
    print(sorted_results.to_string(index=False))
    print(f"\nBaseline IC: {baseline_ic:.4f}")
    print(f"Decision: {decision}")
    print(f"Summary: {summary_path}")

    row_counts = {}
    for state in STATE_SPECS:
        if state.name in panel.columns:
            cnt = panel[panel[state.name]].shape[0]
            row_counts[state.name] = int(cnt)
        else:
            row_counts[state.name] = 0
    print(f"\nRow counts by state: {row_counts}")

    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()