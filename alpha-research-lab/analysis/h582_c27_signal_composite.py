"""
H582: C27 × Signal Composite

H574 found blocked_either IC=0.1477 (new mechanism).
H573 FAILED: tight+low_breadth × C23 signal = 0.1394 (adding C23 hurts).
H565 found tight+low_breadth = 0.2062.

But H573 tested C23 (latent state signal). C27 is a different mechanism
(implementation pain). Test: blocked × C23/C24/C25/C26 composite.
If C27 captures different hidden demand, it might amplify the composite
even though C23 didn't.

Pass criterion: blocked × composite beats composite alone by > +0.01 IC
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


BRANCH_NAME = "c27_signal_composite"
MODE = "research_branch"


def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="H582: C27 × Signal Composite")
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
    panel = panel.merge(c16_df[["time", "ticker", "order_volume_ratio", "order_volume_ratio_rank"]], on=["time", "ticker"], how="left")

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

    panel["blocked_buy"] = ~(panel["can_buy_next_open"])
    panel["blocked_sell"] = ~(panel["can_sell_next_open"])
    panel["blocked_either"] = panel["blocked_buy"] | panel["blocked_sell"]

    panel["c23_active"] = panel["order_volume_ratio_rank"] <= 0.20
    panel["c24_signal"] = panel["order_volume_ratio_rank"] >= 0.80
    panel["c25_signal"] = panel["order_volume_ratio"] <= 0.15

    panel["composite_signal"] = panel["c23_active"] | panel["c24_signal"] | panel["c25_signal"]
    panel["blocked_composite"] = panel["blocked_either"] & panel["composite_signal"]

    panel["all_rows"] = True

    print(f"Panel rows: {len(panel)}")
    print(f"C23 active: {panel['c23_active'].sum()}")
    print(f"C24 ceiling: {panel['c24_signal'].sum()}")
    print(f"C25 VWAP: {panel['c25_signal'].sum()}")
    print(f"composite_signal: {panel['composite_signal'].sum()}")
    print(f"blocked_either: {panel['blocked_either'].sum()}")
    print(f"blocked_composite: {panel['blocked_composite'].sum()}")

    return panel


def run_branch(args: argparse.Namespace) -> str:
    spec = ExperimentSpec(
        name=BRANCH_NAME,
        mode=MODE,
        hypothesis=(
            "Test C27 (blocked stocks) × composite signal (C23/C24/C25). "
            "H573 failed with C23 added to tight+low, but C27 is different mechanism."
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
        StateSpec("composite_signal", "C23/C24/C25 composite", family="signal"),
        StateSpec("blocked_either", "Blocked stocks (C27)", family="c27"),
        StateSpec("blocked_composite", "C27 × composite signal", family="c27_signal"),
        StateSpec("c23_active", "C23 active", family="signal"),
        StateSpec("c24_signal", "C24 ceiling", family="signal"),
        StateSpec("c25_signal", "C25 VWAP", family="signal"),
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

    print("\n=== H582: C27 × Signal Composite ===")
    print(results[["name", "avg_ic", "positive_years", "years", "pooled_rows"]].sort_values("avg_ic", ascending=False).to_string(index=False))

    baseline = results[results["name"] == "all_rows"]["avg_ic"].iloc[0] if "all_rows" in results["name"].values else np.nan
    blocked_comp = results[results["name"] == "blocked_composite"]["avg_ic"].iloc[0] if "blocked_composite" in results["name"].values else np.nan
    composite = results[results["name"] == "composite_signal"]["avg_ic"].iloc[0] if "composite_signal" in results["name"].values else np.nan
    blocked_either = results[results["name"] == "blocked_either"]["avg_ic"].iloc[0] if "blocked_either" in results["name"].values else np.nan
    c23 = results[results["name"] == "c23_active"]["avg_ic"].iloc[0] if "c23_active" in results["name"].values else np.nan
    c24 = results[results["name"] == "c24_signal"]["avg_ic"].iloc[0] if "c24_signal" in results["name"].values else np.nan
    c25 = results[results["name"] == "c25_signal"]["avg_ic"].iloc[0] if "c25_signal" in results["name"].values else np.nan

    diff_vs_composite = blocked_comp - composite if not (np.isnan(blocked_comp) or np.isnan(composite)) else np.nan
    diff_vs_c27 = blocked_comp - blocked_either if not (np.isnan(blocked_comp) or np.isnan(blocked_either)) else np.nan

    print(f"\nBaseline IC: {baseline:.4f}")
    print(f"C27 × composite: {blocked_comp:.4f}")
    print(f"Raw composite: {composite:.4f}")
    print(f"Raw C27: {blocked_either:.4f}")
    print(f"C23: {c23:.4f}, C24: {c24:.4f}, C25: {c25:.4f}")
    print(f"C27 × composite vs composite alone: {diff_vs_composite:+.4f}")
    print(f"C27 × composite vs raw C27: {diff_vs_c27:+.4f}")

    if not np.isnan(diff_vs_composite):
        if diff_vs_composite > 0.01:
            decision = "PASSED"
        elif diff_vs_composite > 0.005:
            decision = "MIXED"
        elif diff_vs_composite > 0:
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
            "blocked_composite_ic": blocked_comp,
            "composite_ic": composite,
            "blocked_either_ic": blocked_either,
            "c23_ic": c23,
            "c24_ic": c24,
            "c25_ic": c25,
            "diff_vs_composite": diff_vs_composite,
            "diff_vs_c27": diff_vs_c27,
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": "C27 × signal composite",
        },
    )

    print(f"\nDecision: {decision}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()