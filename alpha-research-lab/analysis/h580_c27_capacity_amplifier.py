"""
H580: C27 × Capacity Amplifier

H574 found blocked_either IC=0.1477 (+0.0211 vs liquid). H474 found tight_capacity
IC=0.184 (+0.055 vs baseline). H565 found tight+low_breadth=0.2062.
H575 found C27 is OPPOSITE in foreign regime.

Now test: blocked × tight_capacity. These are two different mechanisms:
- C27: implementation difficulty = hidden demand
- tight: sparse order flow = hidden demand

Pass criterion: blocked × tight beats either single by > +0.01 IC
"""

from __future__ import annotations

import argparse
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
    normalize_time_ticker,
    restrict_years,
)
from src.repo_paths import data_path


BRANCH_NAME = "c27_capacity_amplifier"
MODE = "research_branch"


def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="H580: C27 × Capacity Amplifier")
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    return parser.parse_args()


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    panel = load_s1_decision_panel(
        S1_DEFAULT_PATH,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )

    c16_path = data_path("features/xs_order_pressure_daily.parquet")
    c16_df = pd.read_parquet(c16_path)
    c16_df = normalize_time_ticker(c16_df, source="C16 panel")
    c16_df = restrict_years(c16_df, start_year=spec.start_year, end_year=spec.end_year, source="C16 panel")
    panel = panel.merge(c16_df[["time", "ticker", "order_volume_ratio_rank"]], on=["time", "ticker"], how="left")

    tradability_path = data_path("features/execution/tradability_daily.parquet")
    trad_df = pd.read_parquet(tradability_path)
    trad_df = normalize_time_ticker(trad_df, source="tradability")
    trad_df = restrict_years(trad_df, start_year=spec.start_year, end_year=spec.end_year, source="tradability")

    panel = panel.merge(
        trad_df[["time", "ticker", "has_volume", "can_buy_next_open", "can_sell_next_open"]],
        on=["time", "ticker"],
        how="left"
    )

    panel["blocked_buy"] = ~(panel["can_buy_next_open"].fillna(True))
    panel["blocked_sell"] = ~(panel["can_sell_next_open"].fillna(True))
    panel["blocked_either"] = panel["blocked_buy"] | panel["blocked_sell"]
    panel["liquid"] = panel["has_volume"].fillna(True) & panel["can_buy_next_open"].fillna(True)

    panel["tight_capacity"] = panel["order_volume_ratio_rank"] <= 0.20

    panel["blocked_tight"] = panel["blocked_either"] & panel["tight_capacity"]
    panel["blocked_loose"] = panel["blocked_either"] & ~panel["tight_capacity"]
    panel["liquid_tight"] = panel["liquid"] & panel["tight_capacity"]
    panel["liquid_loose"] = panel["liquid"] & ~panel["tight_capacity"]

    panel["all_rows"] = True

    print(f"Panel rows: {len(panel)}")
    print(f"blocked_either: {panel['blocked_either'].sum()}")
    print(f"tight_capacity: {panel['tight_capacity'].sum()}")
    print(f"blocked_tight: {panel['blocked_tight'].sum()}")
    print(f"blocked_loose: {panel['blocked_loose'].sum()}")
    print(f"liquid: {panel['liquid'].sum()}")
    print(f"liquid_tight: {panel['liquid_tight'].sum()}")

    return panel


def run_branch(args: argparse.Namespace) -> str:
    spec = ExperimentSpec(
        name=BRANCH_NAME,
        mode=MODE,
        hypothesis=(
            "Test C27 (blocked stocks) × tight_capacity intersection. "
            "Two different hidden-demand mechanisms combining."
        ),
        start_year=2015,
        end_year=2025,
        min_year_rows=500,
        min_phase_rows=500,
        target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
        score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
    )
    context = build_experiment_context(spec, artifact_subdir="research_branch")

    panel = load_panel(args, spec)

    STATE_SPECS = [
        StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
        StateSpec("liquid", "Liquid stocks", family="liquid"),
        StateSpec("tight_capacity", "Tight capacity (Q1 order count)", family="capacity"),
        StateSpec("blocked_either", "Blocked stocks (C27)", family="c27"),
        StateSpec("blocked_tight", "C27 × tight capacity", family="c27_cap"),
        StateSpec("blocked_loose", "C27 × loose capacity", family="c27_cap"),
        StateSpec("liquid_tight", "Liquid × tight capacity", family="liq_cap"),
        StateSpec("liquid_loose", "Liquid × loose capacity", family="liq_cap"),
    ]

    available_cols = [s.name for s in STATE_SPECS if s.name in panel.columns]
    STATE_SPECS = [s for s in STATE_SPECS if s.name in available_cols]

    validate_state_columns(panel, [state.name for state in STATE_SPECS], spec)

    results, yearly = evaluate_state_specs(
        panel,
        STATE_SPECS,
        score_col="s1_xs_proba",
        target_col="s1_barrier_hit_1d",
        spec=spec,
    )

    results_path = write_dataframe_artifact(results, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")

    print("\n=== H580: C27 × Capacity Amplifier ===")
    print(results[["name", "avg_ic", "positive_years", "years", "pooled_rows"]].sort_values("avg_ic", ascending=False).to_string(index=False))

    baseline = results[results["name"] == "all_rows"]["avg_ic"].iloc[0] if "all_rows" in results["name"].values else np.nan
    blocked_tight = results[results["name"] == "blocked_tight"]["avg_ic"].iloc[0] if "blocked_tight" in results["name"].values else np.nan
    blocked_either = results[results["name"] == "blocked_either"]["avg_ic"].iloc[0] if "blocked_either" in results["name"].values else np.nan
    tight_cap = results[results["name"] == "tight_capacity"]["avg_ic"].iloc[0] if "tight_capacity" in results["name"].values else np.nan
    liquid_tight = results[results["name"] == "liquid_tight"]["avg_ic"].iloc[0] if "liquid_tight" in results["name"].values else np.nan
    blocked_loose = results[results["name"] == "blocked_loose"]["avg_ic"].iloc[0] if "blocked_loose" in results["name"].values else np.nan
    liquid = results[results["name"] == "liquid"]["avg_ic"].iloc[0] if "liquid" in results["name"].values else np.nan

    diff_vs_blocked = blocked_tight - blocked_either if not np.isnan(blocked_tight) and not np.isnan(blocked_either) else np.nan
    diff_vs_tight = blocked_tight - tight_cap if not np.isnan(blocked_tight) and not np.isnan(tight_cap) else np.nan

    print(f"\nBaseline IC: {baseline:.4f}")
    print(f"C27 × tight: {blocked_tight:.4f}")
    print(f"Raw C27: {blocked_either:.4f}")
    print(f"Raw tight: {tight_cap:.4f}")
    print(f"C27 × loose: {blocked_loose:.4f}")
    print(f"Liquid × tight: {liquid_tight:.4f}")
    print(f"C27 × tight vs raw C27: {diff_vs_blocked:+.4f}")
    print(f"C27 × tight vs raw tight: {diff_vs_tight:+.4f}")

    best_improvement = min(diff_vs_blocked, diff_vs_tight) if not (np.isnan(diff_vs_blocked) or np.isnan(diff_vs_tight)) else np.nan
    if not np.isnan(best_improvement):
        if best_improvement > 0.01:
            decision = "PASSED"
        elif best_improvement > 0.005:
            decision = "MIXED"
        elif best_improvement > 0:
            decision = "MIXED (marginal)"
        else:
            decision = "FAILED"
    else:
        decision = "FAILED (no data)"

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": baseline,
            "blocked_tight_ic": blocked_tight,
            "blocked_either_ic": blocked_either,
            "tight_capacity_ic": tight_cap,
            "liquid_tight_ic": liquid_tight,
            "blocked_loose_ic": blocked_loose,
            "liquid_ic": liquid,
            "diff_vs_blocked": diff_vs_blocked,
            "diff_vs_tight": diff_vs_tight,
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": "C27 × capacity amplifier",
        },
    )

    print(f"\nDecision: {decision}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()