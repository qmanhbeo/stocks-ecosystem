"""
H544: duration_weighted_signal_strength

Hypothesis: H534 found that longer duration in active state predicts STRONGER signal 
(duration_8pl IC=0.1832 vs baseline 0.1302). Now test using this as a continuous
weight modifier instead of just a binary filter.

- Instead of filtering: active state (C16 <= 0.2)
- Use as weight: S1_score × log(1 + consecutive_days_in_active_state)
- Compare against baseline, binary filter, and H534's bucket approach

Prior results:
- H534: duration_8pl IC=0.1832 (+0.0530), duration is a positive predictor
- H534: duration_4_7d IC=0.1812 (+0.0510), duration_2_3d IC=0.1722 (+0.0420)
- H526: exit timing (fresh vs sustained) made NO difference
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
from src.repo_paths import data_path


BRANCH_NAME = "duration_weighted_signal_strength"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "H534 found longer active-state duration predicts STRONGER signal. "
        "Now test using duration as continuous weight modifier for S1 instead of binary filter."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H544 duration_weighted_signal_strength test")
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

    # Load order_stats to get C16 (order_volume_ratio_rank)
    order_stats = pd.read_parquet(args.order_stats_path)
    order_stats = order_stats.rename(columns={"date": "time"})
    order_stats["time"] = pd.to_datetime(order_stats["time"])
    order_stats = order_stats[order_stats["time"].dt.year <= 2025]

    # Need order_volume_ratio for C16 computation
    order_stats["total_volume"] = order_stats["buy_order_volume"] + order_stats["sell_order_volume"]
    order_stats = order_stats[order_stats["total_volume"] > 0]
    order_stats["order_volume_ratio"] = order_stats["buy_order_volume"] / order_stats["total_volume"]

    # Compute C16 rank (order_volume_ratio_rank)
    c16_rank = order_stats.groupby("time")["order_volume_ratio"].rank(method="average", pct=True)
    order_stats["c16_rank"] = c16_rank
    order_stats["c16_active"] = order_stats["c16_rank"] <= 0.2  # Active state (low pressure)

    panel = panel.merge(
        order_stats[["time", "ticker", "c16_rank", "c16_active"]],
        on=["time", "ticker"],
        how="left",
    )

    # Fill NaN for c16_active (no order stats = not active)
    panel["c16_active"] = panel["c16_active"].fillna(False)
    panel["c16_rank"] = panel["c16_rank"].fillna(0.5)

    # Compute consecutive days in active state (C16 <= 0.2)
    # Sort and compute run-length encoding
    panel = panel.sort_values(["ticker", "time"])
    panel["c16_active_lag"] = panel.groupby("ticker")["c16_active"].shift(1)
    panel["c16_active_lag"] = panel["c16_active_lag"].fillna(False)

    # Start of a new active streak = was not active yesterday but is active today
    panel["new_active_streak"] = (panel["c16_active"]) & (~panel["c16_active_lag"])

    # Compute streak ID
    panel["streak_id"] = panel.groupby("ticker")["new_active_streak"].cumsum()
    panel.loc[~panel["c16_active"], "streak_id"] = 0

    # Compute days since start of active streak
    panel["days_in_active"] = panel.groupby(["ticker", "streak_id"]).cumcount() + 1
    panel.loc[~panel["c16_active"], "days_in_active"] = 0

    # Duration weight: log(1 + days_in_active)
    panel["duration_weight"] = np.log1p(panel["days_in_active"])
    panel["duration_weight"] = panel["duration_weight"].fillna(0)

    # Also compute bucket filters for comparison with H534
    panel["duration_2_3d"] = (panel["days_in_active"] >= 2) & (panel["days_in_active"] <= 3)
    panel["duration_4_7d"] = (panel["days_in_active"] >= 4) & (panel["days_in_active"] <= 7)
    panel["duration_8pl"] = panel["days_in_active"] >= 8
    panel["duration_any"] = panel["days_in_active"] >= 1  # Any active state

    # Weighted S1: S1 × duration_weight (only for active states)
    panel["s1_duration_weighted"] = panel[S1_SCORE_COL] * panel["duration_weight"]
    panel["s1_duration_weighted"] = panel["s1_duration_weighted"].fillna(0)

    # Also test: S1 × log(1+days) capped at reasonable max
    panel["s1_duration_capped"] = panel[S1_SCORE_COL] * panel["duration_weight"].clip(upper=3.0)

    # Rank-based version for IC calculation
    panel["weighted_rank"] = panel.groupby("time", sort=False)["s1_duration_weighted"].rank(method="average", pct=True)
    panel["weighted_rank_capped"] = panel.groupby("time", sort=False)["s1_duration_capped"].rank(method="average", pct=True)

    panel["all_rows"] = True

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    # Binary filters (from H534)
    StateSpec("duration_any", "Any active state (C16 <= 0.2)", family="duration_filter"),
    StateSpec("duration_2_3d", "Active 2-3 days", family="duration_filter"),
    StateSpec("duration_4_7d", "Active 4-7 days", family="duration_filter"),
    StateSpec("duration_8pl", "Active 8+ days (H534 best)", family="duration_filter", primary=True),
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

    # Evaluate binary filters
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
    duration_8pl_ic = results[results["name"] == "duration_8pl"]["avg_ic"].iloc[0] if not results.empty else 0
    duration_any_ic = results[results["name"] == "duration_any"]["avg_ic"].iloc[0] if not results.empty else 0

    duration_8pl_lift = duration_8pl_ic - baseline_ic
    duration_any_lift = duration_any_ic - baseline_ic

    # Now test weighted versions: compute IC of weighted scores directly
    # Weighted: S1 × duration_weight (for active states only)
    panel_active = panel[panel["c16_active"]].copy()
    if len(panel_active) > 0:
        # IC of raw S1 on active state (should match duration_any)
        active_raw_ic = panel_active[S1_SCORE_COL].corr(panel_active[S1_TARGET_COL], method="spearman")

        # IC of duration-weighted S1
        weighted_ic = panel_active["s1_duration_weighted"].corr(panel_active[S1_TARGET_COL], method="spearman")

        # IC of capped-weighted S1
        capped_ic = panel_active["s1_duration_capped"].corr(panel_active[S1_TARGET_COL], method="spearman")

        # IC using rank of weighted score
        weighted_rank_ic = panel_active["weighted_rank"].corr(panel_active[S1_TARGET_COL], method="spearman")
        capped_rank_ic = panel_active["weighted_rank_capped"].corr(panel_active[S1_TARGET_COL], method="spearman")
    else:
        active_raw_ic = weighted_ic = capped_ic = weighted_rank_ic = capped_rank_ic = 0

    # Compare weighted vs binary
    best_weighted = max(weighted_ic, capped_ic, weighted_rank_ic, capped_rank_ic)
    best_binary = max(duration_8pl_ic, duration_any_ic)

    # Decision: Does weighting beat binary filter?
    if best_weighted > best_binary + 0.01:
        decision = "PASSED"
    elif best_weighted > baseline_ic + 0.01:
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
            "baseline_ic": float(baseline_ic),
            # Binary filters (H534-style)
            "duration_any_ic": float(duration_any_ic),
            "duration_any_lift": float(duration_any_lift),
            "duration_8pl_ic": float(duration_8pl_ic),
            "duration_8pl_lift": float(duration_8pl_lift),
            # Weighted versions
            "active_raw_ic": float(active_raw_ic),
            "weighted_ic": float(weighted_ic),
            "capped_ic": float(capped_ic),
            "weighted_rank_ic": float(weighted_rank_ic),
            "capped_rank_ic": float(capped_rank_ic),
            "best_weighted_ic": float(best_weighted),
            "best_binary_ic": float(best_binary),
            "best_state_by_avg_year_ic": best_row.get("name"),
            "best_avg_year_ic": best_row.get("avg_ic"),
            "best_positive_years": best_row.get("positive_years"),
            "best_years": best_row.get("years"),
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
    print(f"\nBinary filters (H534-style):")
    print(f"  duration_any: {duration_any_ic:.4f} (lift: {duration_any_lift:+.4f})")
    print(f"  duration_8pl: {duration_8pl_ic:.4f} (lift: {duration_8pl_lift:+.4f})")
    print(f"\nWeighted versions (new):")
    print(f"  active_raw (S1 in active): {active_raw_ic:.4f}")
    print(f"  weighted (S1 × log(1+days)): {weighted_ic:.4f}")
    print(f"  capped (S1 × capped): {capped_ic:.4f}")
    print(f"  weighted_rank: {weighted_rank_ic:.4f}")
    print(f"  capped_rank: {capped_rank_ic:.4f}")
    print(f"\nBest weighted: {best_weighted:.4f}, Best binary: {best_binary:.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()