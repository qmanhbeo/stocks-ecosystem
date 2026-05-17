"""
H581: C27 × Breadth Amplifier

H574 found blocked_either IC=0.1477 (+0.0211 vs liquid).
H525/H529 found low_breadth amplifies all signals.
H565 found tight+low_breadth=0.2062 (strong amplification).

Now test: blocked × low_breadth. Different mechanism from tight_capacity,
but breadth filter might amplify C27 too.

Pass criterion: blocked × low_breadth beats raw C27 by > +0.01 IC
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


BRANCH_NAME = "c27_breadth_amplifier"
MODE = "research_branch"


def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="H581: C27 × Breadth Amplifier")
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
    panel = panel.merge(c16_df[["time", "ticker"]], on=["time", "ticker"], how="left")

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

    date_breadth = panel.groupby("time")["ticker"].nunique().reset_index()
    date_breadth.columns = ["time", "active_count"]
    breadth_20 = date_breadth["active_count"].quantile(0.20)
    date_breadth["low_breadth"] = date_breadth["active_count"] <= breadth_20
    panel = panel.merge(date_breadth[["time", "low_breadth"]], on="time", how="left")

    panel["blocked_low_breadth"] = panel["blocked_either"] & panel["low_breadth"]
    panel["blocked_high_breadth"] = panel["blocked_either"] & ~panel["low_breadth"]
    panel["liquid_low_breadth"] = panel["liquid"] & panel["low_breadth"]
    panel["liquid_high_breadth"] = panel["liquid"] & ~panel["low_breadth"]

    panel["all_rows"] = True

    print(f"Panel rows: {len(panel)}")
    print(f"blocked_either: {panel['blocked_either'].sum()}")
    print(f"low_breadth dates: {panel['low_breadth'].sum()}")
    print(f"blocked_low_breadth: {panel['blocked_low_breadth'].sum()}")
    print(f"blocked_high_breadth: {panel['blocked_high_breadth'].sum()}")
    print(f"liquid: {panel['liquid'].sum()}")

    return panel


def run_branch(args: argparse.Namespace) -> str:
    spec = ExperimentSpec(
        name=BRANCH_NAME,
        mode=MODE,
        hypothesis=(
            "Test C27 (blocked stocks) × low_breadth intersection. "
            "Breadth filter amplifies all signals; test if it amplifies C27 too."
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
        StateSpec("low_breadth", "Low breadth dates", family="breadth"),
        StateSpec("blocked_either", "Blocked stocks (C27)", family="c27"),
        StateSpec("blocked_low_breadth", "C27 × low breadth", family="c27_breadth"),
        StateSpec("blocked_high_breadth", "C27 × high breadth", family="c27_breadth"),
        StateSpec("liquid_low_breadth", "Liquid × low breadth", family="liq_breadth"),
        StateSpec("liquid_high_breadth", "Liquid × high breadth", family="liq_breadth"),
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

    print("\n=== H581: C27 × Breadth Amplifier ===")
    print(results[["name", "avg_ic", "positive_years", "years", "pooled_rows"]].sort_values("avg_ic", ascending=False).to_string(index=False))

    baseline = results[results["name"] == "all_rows"]["avg_ic"].iloc[0] if "all_rows" in results["name"].values else np.nan
    blocked_lb = results[results["name"] == "blocked_low_breadth"]["avg_ic"].iloc[0] if "blocked_low_breadth" in results["name"].values else np.nan
    blocked_hb = results[results["name"] == "blocked_high_breadth"]["avg_ic"].iloc[0] if "blocked_high_breadth" in results["name"].values else np.nan
    blocked_either = results[results["name"] == "blocked_either"]["avg_ic"].iloc[0] if "blocked_either" in results["name"].values else np.nan
    low_br = results[results["name"] == "low_breadth"]["avg_ic"].iloc[0] if "low_breadth" in results["name"].values else np.nan
    liquid_lb = results[results["name"] == "liquid_low_breadth"]["avg_ic"].iloc[0] if "liquid_low_breadth" in results["name"].values else np.nan
    liquid_hb = results[results["name"] == "liquid_high_breadth"]["avg_ic"].iloc[0] if "liquid_high_breadth" in results["name"].values else np.nan
    liquid = results[results["name"] == "liquid"]["avg_ic"].iloc[0] if "liquid" in results["name"].values else np.nan

    diff_vs_c27 = blocked_lb - blocked_either if not (np.isnan(blocked_lb) or np.isnan(blocked_either)) else np.nan
    c27_lift_low = blocked_lb - liquid_lb if not (np.isnan(blocked_lb) or np.isnan(liquid_lb)) else np.nan
    c27_lift_high = blocked_hb - liquid_hb if not (np.isnan(blocked_hb) or np.isnan(liquid_hb)) else np.nan

    print(f"\nBaseline IC: {baseline:.4f}")
    print(f"C27 × low_breadth: {blocked_lb:.4f}")
    print(f"C27 × high_breadth: {blocked_hb:.4f}")
    print(f"Raw C27: {blocked_either:.4f}")
    print(f"Low breadth alone: {low_br:.4f}")
    print(f"Liquid × low_breadth: {liquid_lb:.4f}")
    print(f"Liquid × high_breadth: {liquid_hb:.4f}")
    print(f"C27 × low_breadth vs raw C27: {diff_vs_c27:+.4f}")
    print(f"C27 lift in low_breadth: {c27_lift_low:+.4f}")
    print(f"C27 lift in high_breadth: {c27_lift_high:+.4f}")

    if not np.isnan(diff_vs_c27):
        if diff_vs_c27 > 0.01:
            decision = "PASSED"
        elif diff_vs_c27 > 0.005:
            decision = "MIXED"
        elif diff_vs_c27 > 0:
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
            "blocked_low_breadth_ic": blocked_lb,
            "blocked_high_breadth_ic": blocked_hb,
            "blocked_either_ic": blocked_either,
            "low_breadth_ic": low_br,
            "liquid_low_breadth_ic": liquid_lb,
            "liquid_high_breadth_ic": liquid_hb,
            "liquid_ic": liquid,
            "diff_vs_c27": diff_vs_c27,
            "c27_lift_low_breadth": c27_lift_low,
            "c27_lift_high_breadth": c27_lift_high,
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": "C27 × breadth amplifier",
        },
    )

    print(f"\nDecision: {decision}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()