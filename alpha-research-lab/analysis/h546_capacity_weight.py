"""
H546: capacity_direction_as_signal_weight

Hypothesis: H538 found tight_expanding (more orders arriving) beats tight_contracting 
by +0.0144. Now test using capacity direction as continuous weight modifier for S1
instead of binary filter.

Similar to H544 (duration weighting) which FAILED - but test with capacity direction.

Prior results:
- H538: tight_expanding IC=0.1697, tight_contracting IC=0.1553 (+0.0144)
- H544: duration weighting FAILED (0.0972 vs 0.1832 binary)
- H474: tight_capacity (Q1 order count) IC=0.184
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


BRANCH_NAME = "capacity_direction_as_signal_weight"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "H538 found tight_expanding > tight_contracting by +0.0144. "
        "Now test using capacity direction as continuous weight modifier for S1."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H546 capacity_direction_as_signal_weight test")
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

    # Load order_stats
    order_stats = pd.read_parquet(args.order_stats_path)
    order_stats = order_stats.rename(columns={"date": "time"})
    order_stats["time"] = pd.to_datetime(order_stats["time"])
    order_stats = order_stats[order_stats["time"].dt.year <= 2025]

    def parse_price_change(s):
        if pd.isna(s):
            return np.nan
        try:
            match = re.search(r'\(\s*([+-]?[\d,]+)\s*%\)', str(s))
            if match:
                return float(match.group(1).replace(',', '.'))
            return np.nan
        except:
            return np.nan

    order_stats["pct_change"] = order_stats["price_change_raw"].apply(parse_price_change)
    order_stats["total_volume"] = order_stats["buy_order_volume"] + order_stats["sell_order_volume"]
    order_stats = order_stats[order_stats["total_volume"] > 0]

    panel = panel.merge(
        order_stats[["time", "ticker", "total_volume", "pct_change"]],
        on=["time", "ticker"],
        how="left",
    )

    panel = panel.dropna(subset=["total_volume", "pct_change"])
    panel = panel.sort_values(["ticker", "time"])

    # Compute capacity: order count (proxy: total volume as proxy for order activity)
    panel["order_count"] = panel["total_volume"]

    # Compute capacity rank per date (low = tight capacity = fewer orders)
    capacity_rank = panel.groupby("time")["order_count"].rank(method="average", pct=True)
    panel["tight_capacity"] = capacity_rank <= 0.2  # Bottom 20% = tight

    # Compute capacity direction: is capacity expanding or contracting?
    # Use 5d change in order_count
    panel["order_count_change"] = panel.groupby("ticker")["order_count"].transform(
        lambda x: x.pct_change(periods=5)
    )

    # Capacity direction: expanding (positive change) vs contracting (negative change)
    panel["capacity_expanding"] = panel["order_count_change"] > 0
    panel["capacity_contracting"] = panel["order_count_change"] < 0

    # Tight capacity states
    panel["tight_expanding"] = panel["tight_capacity"] & panel["capacity_expanding"]
    panel["tight_contracting"] = panel["tight_capacity"] & panel["capacity_contracting"]

    # Continuous weight: sign of order_count_change (positive = expanding, more weight)
    # Use sign as continuous modifier: S1 × sign(change) or S1 × log(1+change)
    panel["capacity_weight"] = panel["order_count_change"].fillna(0).clip(-1, 1)  # bounded

    # Weighted S1
    panel["s1_capacity_weighted"] = panel[S1_SCORE_COL] * (1 + panel["capacity_weight"])
    panel["s1_capacity_weighted"] = panel["s1_capacity_weighted"].fillna(0)

    # Rank of weighted
    panel["weighted_rank"] = panel.groupby("time", sort=False)["s1_capacity_weighted"].rank(method="average", pct=True)

    panel["all_rows"] = True

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    # Binary filters (from H538 style)
    StateSpec("tight_capacity", "Tight capacity (bottom 20%)", family="capacity"),
    StateSpec("tight_expanding", "Tight + expanding (H538 best)", family="capacity", primary=True),
    StateSpec("tight_contracting", "Tight + contracting", family="capacity"),
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
    tight_capacity_ic = results[results["name"] == "tight_capacity"]["avg_ic"].iloc[0] if not results.empty else 0
    tight_expanding_ic = results[results["name"] == "tight_expanding"]["avg_ic"].iloc[0] if not results.empty else 0
    tight_contracting_ic = results[results["name"] == "tight_contracting"]["avg_ic"].iloc[0] if not results.empty else 0

    tight_capacity_lift = tight_capacity_ic - baseline_ic
    tight_expanding_lift = tight_expanding_ic - baseline_ic
    tight_contracting_lift = tight_contracting_ic - baseline_ic

    # Test weighted versions
    panel_weighted = panel[panel["tight_capacity"]].copy()
    if len(panel_weighted) > 0:
        weighted_ic = panel_weighted[S1_SCORE_COL].corr(panel_weighted[S1_TARGET_COL], method="spearman")
        weighted_rank_ic = panel_weighted["weighted_rank"].corr(panel_weighted[S1_TARGET_COL], method="spearman")
    else:
        weighted_ic = weighted_rank_ic = 0

    # Compare weighted vs binary
    best_weighted = max(weighted_ic, weighted_rank_ic)
    best_binary = max(tight_expanding_ic, tight_contracting_ic)

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
            # Binary filters
            "tight_capacity_ic": float(tight_capacity_ic) if not np.isnan(tight_capacity_ic) else None,
            "tight_capacity_lift": float(tight_capacity_lift),
            "tight_expanding_ic": float(tight_expanding_ic) if not np.isnan(tight_expanding_ic) else None,
            "tight_expanding_lift": float(tight_expanding_lift),
            "tight_contracting_ic": float(tight_contracting_ic) if not np.isnan(tight_contracting_ic) else None,
            "tight_contracting_lift": float(tight_contracting_lift),
            # Weighted
            "weighted_ic": float(weighted_ic),
            "weighted_rank_ic": float(weighted_rank_ic),
            "best_weighted": float(best_weighted),
            "best_binary": float(best_binary),
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
    print(f"\nBinary filters (H538-style):")
    print(f"  tight_capacity: {tight_capacity_ic:.4f} (lift: {tight_capacity_lift:+.4f})")
    print(f"  tight_expanding: {tight_expanding_ic:.4f} (lift: {tight_expanding_lift:+.4f})")
    print(f"  tight_contracting: {tight_contracting_ic:.4f} (lift: {tight_contracting_lift:+.4f})")
    print(f"\nWeighted versions (new):")
    print(f"  weighted (S1 × (1+change)): {weighted_ic:.4f}")
    print(f"  weighted_rank: {weighted_rank_ic:.4f}")
    print(f"\nBest weighted: {best_weighted:.4f}, Best binary: {best_binary:.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()