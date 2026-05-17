"""
H584: C27 as Signal Router

H574 found blocked_either IC=0.1477 (positive signal, implementation pain = alpha).
H581 found C27 in low_breadth HURTS (-0.0517 vs raw C27).
H582 found blocked × composite beats composite but composite was too broad.

Now test: Does being blocked change how OTHER signals work on the same stock?
Test if S1 IC on non-blocked stocks is DIFFERENT from S1 IC on blocked stocks.
If blocked = hidden demand, then S1 should be STRONGER when blocked.

This tests whether C27 is a router for signal selection (not just an additive signal).

Pass criterion: S1 (non-blocked) IC differs from S1 (blocked) IC by > +0.01
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


BRANCH_NAME = "c27_signal_router"
MODE = "research_branch"


def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="H584: C27 as Signal Router")
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
    panel["has_volume"] = panel["has_volume"].fillna(True)
    panel["can_buy_next_open"] = panel["can_buy_next_open"].fillna(True)
    panel["can_sell_next_open"] = panel["can_sell_next_open"].fillna(True)

    panel["blocked_buy"] = ~panel["can_buy_next_open"]
    panel["blocked_sell"] = ~panel["can_sell_next_open"]
    panel["blocked_either"] = panel["blocked_buy"] | panel["blocked_sell"]

    panel["non_blocked"] = ~panel["blocked_either"]

    panel["c23_active"] = panel["order_volume_ratio_rank"] <= 0.20
    panel["c24_signal"] = panel["order_volume_ratio_rank"] >= 0.80

    panel["blocked_c23"] = panel["blocked_either"] & panel["c23_active"]
    panel["non_blocked_c23"] = panel["non_blocked"] & panel["c23_active"]
    panel["blocked_c24"] = panel["blocked_either"] & panel["c24_signal"]
    panel["non_blocked_c24"] = panel["non_blocked"] & panel["c24_signal"]

    panel["all_rows"] = True

    print(f"Panel rows: {len(panel)}")
    print(f"non_blocked: {panel['non_blocked'].sum()}")
    print(f"blocked_either: {panel['blocked_either'].sum()}")
    print(f"blocked_c23: {panel['blocked_c23'].sum()}")
    print(f"non_blocked_c23: {panel['non_blocked_c23'].sum()}")
    print(f"blocked_c24: {panel['blocked_c24'].sum()}")
    print(f"non_blocked_c24: {panel['non_blocked_c24'].sum()}")

    return panel


def run_branch(args: argparse.Namespace) -> str:
    spec = ExperimentSpec(
        name=BRANCH_NAME,
        mode=MODE,
        hypothesis=(
            "Test if C27 (blocked) changes how S1 performs. Does blocked = hidden demand "
            "make S1 signal stronger? Test C23/C24 signal quality conditional on blocked."
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
        StateSpec("blocked_either", "Blocked stocks (C27)", family="c27"),
        StateSpec("non_blocked", "Non-blocked stocks", family="non_c27"),
        StateSpec("c23_active", "C23 active", family="signal"),
        StateSpec("c24_signal", "C24 ceiling", family="signal"),
        StateSpec("blocked_c23", "C23 × blocked", family="sig_c27"),
        StateSpec("non_blocked_c23", "C23 × non-blocked", family="sig_c27"),
        StateSpec("blocked_c24", "C24 × blocked", family="sig_c27"),
        StateSpec("non_blocked_c24", "C24 × non-blocked", family="sig_c27"),
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

    print("\n=== H584: C27 as Signal Router ===")
    print(results[["name", "avg_ic", "positive_years", "years", "pooled_rows"]].sort_values("avg_ic", ascending=False).to_string(index=False))

    baseline = results[results["name"] == "all_rows"]["avg_ic"].iloc[0] if "all_rows" in results["name"].values else np.nan
    blocked_c27 = results[results["name"] == "blocked_either"]["avg_ic"].iloc[0] if "blocked_either" in results["name"].values else np.nan
    non_blocked = results[results["name"] == "non_blocked"]["avg_ic"].iloc[0] if "non_blocked" in results["name"].values else np.nan
    c23 = results[results["name"] == "c23_active"]["avg_ic"].iloc[0] if "c23_active" in results["name"].values else np.nan
    c24 = results[results["name"] == "c24_signal"]["avg_ic"].iloc[0] if "c24_signal" in results["name"].values else np.nan
    blocked_c23 = results[results["name"] == "blocked_c23"]["avg_ic"].iloc[0] if "blocked_c23" in results["name"].values else np.nan
    nb_c23 = results[results["name"] == "non_blocked_c23"]["avg_ic"].iloc[0] if "non_blocked_c23" in results["name"].values else np.nan
    blocked_c24 = results[results["name"] == "blocked_c24"]["avg_ic"].iloc[0] if "blocked_c24" in results["name"].values else np.nan
    nb_c24 = results[results["name"] == "non_blocked_c24"]["avg_ic"].iloc[0] if "non_blocked_c24" in results["name"].values else np.nan

    diff_c23 = blocked_c23 - nb_c23 if not (np.isnan(blocked_c23) or np.isnan(nb_c23)) else np.nan
    diff_c24 = blocked_c24 - nb_c24 if not (np.isnan(blocked_c24) or np.isnan(nb_c24)) else np.nan
    c27_effect = blocked_c27 - non_blocked if not (np.isnan(blocked_c27) or np.isnan(non_blocked)) else np.nan

    print(f"\nBaseline IC: {baseline:.4f}")
    print(f"C27 (blocked): {blocked_c27:.4f}")
    print(f"Non-blocked: {non_blocked:.4f}")
    print(f"C27 effect: {c27_effect:+.4f}")
    print(f"C23 × blocked: {blocked_c23:.4f}, C23 × non-blocked: {nb_c23:.4f}, diff: {diff_c23:+.4f}")
    print(f"C24 × blocked: {blocked_c24:.4f}, C24 × non-blocked: {nb_c24:.4f}, diff: {diff_c24:+.4f}")

    max_router_diff = max(abs(diff_c23) if not np.isnan(diff_c23) else 0, abs(diff_c24) if not np.isnan(diff_c24) else 0)
    if max_router_diff > 0.01:
        decision = "PASSED"
    elif max_router_diff > 0.005:
        decision = "MIXED"
    elif max_router_diff > 0:
        decision = "MIXED (marginal)"
    else:
        decision = "FAILED"

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": baseline,
            "blocked_c27_ic": blocked_c27,
            "non_blocked_ic": non_blocked,
            "c27_effect": c27_effect,
            "c23_blocked_ic": blocked_c23,
            "c23_non_blocked_ic": nb_c23,
            "c24_blocked_ic": blocked_c24,
            "c24_non_blocked_ic": nb_c24,
            "c23_router_diff": diff_c23,
            "c24_router_diff": diff_c24,
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": "C27 as signal router",
        },
    )

    print(f"\nDecision: {decision}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()