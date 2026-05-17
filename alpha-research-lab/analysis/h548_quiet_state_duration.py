"""
H548: quiet_state_duration_sweet_spot

Hypothesis: H534 found active state (C16<=0.2) has "longer = stronger" (duration_8pl IC=0.1832).
Now test if quiet state (high C16) has the OPPOSITE pattern - longer in quiet = weaker (decay).
- Active state: sustained hidden demand builds over time → stronger
- Quiet state: stale signal → decay over time

Prior results:
- H534: duration_8pl active IC=0.1832 (+0.0530), longer = stronger for active
- H526: fresh_entry vs sustained holding for active state - no difference
- H527: quiet-state inverse alpha - FAILED (no contrarian effect)
- state_quiet is STRONG (IC=0.1552, 11/11 pos years)
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys
import re

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
from src.repo_paths import data_path


BRANCH_NAME = "quiet_state_duration_sweet_spot"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "H534 found active state has longer=stronger. Now test if quiet state (high C16) has "
        "OPPOSITE pattern - longer in quiet = weaker (decay). Active = sustained demand, "
        "quiet = stale signal."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H548 quiet_state_duration_sweet_spot test")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--order-stats-path", type=str,
                        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")))
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

    # Load order_stats for C16 (order_volume_ratio_rank)
    order_stats = pd.read_parquet(args.order_stats_path)
    order_stats = order_stats.rename(columns={"date": "time"})
    order_stats["time"] = pd.to_datetime(order_stats["time"])
    order_stats = order_stats[order_stats["time"].dt.year <= 2025]

    # Use order_volume_ratio_rank as C16
    if "order_volume_ratio_rank" in order_stats.columns:
        panel = panel.merge(
            order_stats[["time", "ticker", "order_volume_ratio_rank"]],
            on=["time", "ticker"],
            how="left",
        )
        # Rename to c16 for clarity
        panel["c16_rank"] = panel["order_volume_ratio_rank"]
    else:
        # Fallback: compute from order volume
        order_stats["total_volume"] = order_stats["buy_order_volume"] + order_stats["sell_order_volume"]
        panel = panel.merge(
            order_stats[["time", "ticker", "total_volume"]],
            on=["time", "ticker"],
            how="left",
        )
        # Create rank
        panel["c16_rank"] = panel.groupby("time")["total_volume"].rank(method="average", pct=True)

    # Define states
    # Active: low C16 (bottom 20%)
    # Quiet: high C16 (top 75%)
    panel["active_state"] = panel["c16_rank"] <= 0.2
    panel["quiet_state"] = panel["c16_rank"] >= 0.75

    # Compute duration in each state
    panel = panel.sort_values(["ticker", "time"])
    
    # Duration in active state: consecutive days with active_state=True
    panel["in_active"] = panel["active_state"].astype(int)
    panel["active_duration"] = panel.groupby("ticker")["in_active"].transform(
        lambda x: x.groupby((x != x.shift()).cumsum()).cumcount() + 1
    )
    
    # Duration in quiet state: consecutive days with quiet_state=True
    panel["in_quiet"] = panel["quiet_state"].astype(int)
    panel["quiet_duration"] = panel.groupby("ticker")["in_quiet"].transform(
        lambda x: x.groupby((x != x.shift()).cumsum()).cumcount() + 1
    )
    
    # Set duration to 0 for non-state days
    panel.loc[~panel["active_state"], "active_duration"] = 0
    panel.loc[~panel["quiet_state"], "quiet_duration"] = 0

    # Duration buckets for active (same as H534)
    panel["duration_2_3d_active"] = (panel["active_duration"] >= 2) & (panel["active_duration"] <= 3)
    panel["duration_4_7d_active"] = (panel["active_duration"] >= 4) & (panel["active_duration"] <= 7)
    panel["duration_8pl_active"] = panel["active_duration"] >= 8

    # Duration buckets for quiet (NEW - testing decay hypothesis)
    panel["duration_1d_quiet"] = (panel["quiet_duration"] >= 1) & (panel["quiet_duration"] <= 1)
    panel["duration_2_3d_quiet"] = (panel["quiet_duration"] >= 2) & (panel["quiet_duration"] <= 3)
    panel["duration_4_7d_quiet"] = (panel["quiet_duration"] >= 4) & (panel["quiet_duration"] <= 7)
    panel["duration_8pl_quiet"] = panel["quiet_duration"] >= 8

    # State combinations
    panel["active_only"] = panel["active_state"] & ~panel["quiet_state"]
    panel["quiet_only"] = panel["quiet_state"] & ~panel["active_state"]

    panel["all_rows"] = True

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    # Active state baseline (H534)
    StateSpec("active_state", "Active state (C16<=0.2)", family="active"),
    StateSpec("duration_2_3d_active", "Active 2-3 days", family="active_duration"),
    StateSpec("duration_4_7d_active", "Active 4-7 days", family="active_duration"),
    StateSpec("duration_8pl_active", "Active 8+ days (H534 winner)", family="active_duration"),
    # Quiet state NEW
    StateSpec("quiet_state", "Quiet state (C16>=0.75)", family="quiet"),
    StateSpec("duration_1d_quiet", "Quiet 1 day (fresh)", family="quiet_duration"),
    StateSpec("duration_2_3d_quiet", "Quiet 2-3 days", family="quiet_duration"),
    StateSpec("duration_4_7d_quiet", "Quiet 4-7 days", family="quiet_duration"),
    StateSpec("duration_8pl_quiet", "Quiet 8+ days (stale?)", family="quiet_duration"),
]


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

    baseline_ic = results[results["name"] == "all_rows"]["avg_ic"].iloc[0] if not results.empty else 0
    
    active_ic = results[results["name"] == "active_state"]["avg_ic"].iloc[0] if not results.empty else 0
    dur_2_3_active = results[results["name"] == "duration_2_3d_active"]["avg_ic"].iloc[0] if not results.empty else 0
    dur_4_7_active = results[results["name"] == "duration_4_7d_active"]["avg_ic"].iloc[0] if not results.empty else 0
    dur_8pl_active = results[results["name"] == "duration_8pl_active"]["avg_ic"].iloc[0] if not results.empty else 0

    quiet_ic = results[results["name"] == "quiet_state"]["avg_ic"].iloc[0] if not results.empty else 0
    dur_1d_quiet = results[results["name"] == "duration_1d_quiet"]["avg_ic"].iloc[0] if not results.empty else 0
    dur_2_3_quiet = results[results["name"] == "duration_2_3d_quiet"]["avg_ic"].iloc[0] if not results.empty else 0
    dur_4_7_quiet = results[results["name"] == "duration_4_7d_quiet"]["avg_ic"].iloc[0] if not results.empty else 0
    dur_8pl_quiet = results[results["name"] == "duration_8pl_quiet"]["avg_ic"].iloc[0] if not results.empty else 0

    baseline_lift = 0
    active_lift = active_ic - baseline_ic
    dur_8pl_active_lift = dur_8pl_active - baseline_ic
    
    quiet_lift = quiet_ic - baseline_ic
    dur_1d_quiet_lift = dur_1d_quiet - baseline_ic
    dur_8pl_quiet_lift = dur_8pl_quiet - baseline_ic

    # Decision: Does quiet state show decay pattern (opposite of active)?
    # H534: active 8+ = 0.1832 (+0.053), so longer = stronger
    # Hypothesis: quiet 8+ should be WEAKER than quiet 1d (if decay exists)
    
    quiet_decay = dur_1d_quiet_lift - dur_8pl_quiet_lift  # positive if decay exists (1d stronger than 8+)
    active_stronger = dur_8pl_active_lift > dur_1d_quiet_lift  # active longer beats quiet longer
    
    if quiet_lift > 0.01 and dur_8pl_quiet_lift < dur_1d_quiet_lift and quiet_decay > 0.01:
        decision = "PASSED"  # Both quiet is strong AND decay exists
    elif quiet_lift > 0.01 and dur_8pl_quiet_lift > 0.01:
        decision = "MIXED"  # Quiet is strong but no clear decay pattern
    elif active_lift > 0.01 and quiet_lift > 0.01:
        decision = "MIXED"  # Both work, but pattern unclear
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "active_state_ic": float(active_ic),
            "active_lift": float(active_lift),
            "duration_8pl_active_ic": float(dur_8pl_active),
            "duration_8pl_active_lift": float(dur_8pl_active_lift),
            "quiet_state_ic": float(quiet_ic),
            "quiet_lift": float(quiet_lift),
            "duration_1d_quiet_ic": float(dur_1d_quiet),
            "duration_1d_quiet_lift": float(dur_1d_quiet_lift),
            "duration_8pl_quiet_ic": float(dur_8pl_quiet),
            "duration_8pl_quiet_lift": float(dur_8pl_quiet_lift),
            "quiet_decay": float(quiet_decay),
            "h534_duration_8pl_active_ic": 0.1832,
            "h534_lift": 0.0530,
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

    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(f"\nDecision: {decision}")
    print(f"Baseline IC: {baseline_ic:.4f}")
    print(f"\nActive state (H534 pattern):")
    print(f"  active_state: {active_ic:.4f} (lift: {active_lift:+.4f})")
    print(f"  duration_8pl_active: {dur_8pl_active:.4f} (lift: {dur_8pl_active_lift:+.4f})")
    print(f"\nQuiet state (testing decay):")
    print(f"  quiet_state: {quiet_ic:.4f} (lift: {quiet_lift:+.4f})")
    print(f"  duration_1d_quiet: {dur_1d_quiet:.4f} (lift: {dur_1d_quiet_lift:+.4f})")
    print(f"  duration_8pl_quiet: {dur_8pl_quiet:.4f} (lift: {dur_8pl_quiet_lift:+.4f})")
    print(f"  decay (1d - 8+): {quiet_decay:+.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()