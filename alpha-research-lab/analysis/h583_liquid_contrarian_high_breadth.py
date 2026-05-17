"""
H583: Liquid in Bad Breadth as Contrarian

H574 found blocked_either IC=0.1477 (+0.0211 vs liquid IC=0.1266).
H525 found high breadth = worse signal (crowded regime, IC=0.1149 vs low=0.1454).
H527 found quiet-state contrarian fails (no meaningful lift).

Contrarian angle: When breadth is high, the signal crowd is active everywhere.
Liquid stocks are easily tradable but might be "ignored by the crowd" within
that high-breadth regime — a different mechanism from blocked stocks.

Test: liquid × high_breadth vs liquid × low_breadth. Does liquid beat blocked
specifically in the high-breadth regime?

Pass criterion: liquid × high_breadth beats liquid × low_breadth by > +0.01 IC,
OR liquid × high_breadth beats liquid alone by > +0.01 more than blocked does.
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


BRANCH_NAME = "liquid_contrarian_high_breadth"
MODE = "research_branch"


def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="H583: Liquid in Bad Breadth as Contrarian")
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
    panel["has_volume"] = panel["has_volume"].fillna(True)
    panel["can_buy_next_open"] = panel["can_buy_next_open"].fillna(True)
    panel["can_sell_next_open"] = panel["can_sell_next_open"].fillna(True)

    panel["blocked_buy"] = ~panel["can_buy_next_open"]
    panel["blocked_sell"] = ~panel["can_sell_next_open"]
    panel["blocked_either"] = panel["blocked_buy"] | panel["blocked_sell"]
    panel["liquid"] = panel["has_volume"] & panel["can_buy_next_open"]

    date_breadth = panel.groupby("time")["ticker"].nunique().reset_index()
    date_breadth.columns = ["time", "active_count"]
    breadth_20 = date_breadth["active_count"].quantile(0.20)
    breadth_80 = date_breadth["active_count"].quantile(0.80)
    date_breadth["low_breadth"] = date_breadth["active_count"] <= breadth_20
    date_breadth["high_breadth"] = date_breadth["active_count"] >= breadth_80
    panel = panel.merge(date_breadth[["time", "low_breadth", "high_breadth"]], on="time", how="left")

    panel["liquid_high_breadth"] = panel["liquid"] & panel["high_breadth"]
    panel["liquid_low_breadth"] = panel["liquid"] & panel["low_breadth"]
    panel["blocked_high_breadth"] = panel["blocked_either"] & panel["high_breadth"]
    panel["blocked_low_breadth"] = panel["blocked_either"] & panel["low_breadth"]

    panel["all_rows"] = True

    print(f"Panel rows: {len(panel)}")
    print(f"liquid: {panel['liquid'].sum()}")
    print(f"low_breadth dates: {panel['low_breadth'].sum()}")
    print(f"high_breadth dates: {panel['high_breadth'].sum()}")
    print(f"liquid_high_breadth: {panel['liquid_high_breadth'].sum()}")
    print(f"liquid_low_breadth: {panel['liquid_low_breadth'].sum()}")
    print(f"blocked_high_breadth: {panel['blocked_high_breadth'].sum()}")
    print(f"blocked_low_breadth: {panel['blocked_low_breadth'].sum()}")

    return panel


def run_branch(args: argparse.Namespace) -> str:
    spec = ExperimentSpec(
        name=BRANCH_NAME,
        mode=MODE,
        hypothesis=(
            "Test if liquid stocks (easy to trade) are contrarian in high-breadth "
            "(crowded) regime. Contrarian: liquid ignored by crowd = strong when crowd disperses."
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
        StateSpec("blocked_either", "Blocked stocks (C27)", family="blocked"),
        StateSpec("low_breadth", "Low breadth dates", family="breadth"),
        StateSpec("high_breadth", "High breadth dates", family="breadth"),
        StateSpec("liquid_low_breadth", "Liquid × low breadth", family="liq_breadth"),
        StateSpec("liquid_high_breadth", "Liquid × high breadth", family="liq_breadth"),
        StateSpec("blocked_low_breadth", "Blocked × low breadth", family="blk_breadth"),
        StateSpec("blocked_high_breadth", "Blocked × high breadth", family="blk_breadth"),
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

    print("\n=== H583: Liquid in Bad Breadth as Contrarian ===")
    print(results[["name", "avg_ic", "positive_years", "years", "pooled_rows"]].sort_values("avg_ic", ascending=False).to_string(index=False))

    baseline = results[results["name"] == "all_rows"]["avg_ic"].iloc[0] if "all_rows" in results["name"].values else np.nan
    liquid_hb = results[results["name"] == "liquid_high_breadth"]["avg_ic"].iloc[0] if "liquid_high_breadth" in results["name"].values else np.nan
    liquid_lb = results[results["name"] == "liquid_low_breadth"]["avg_ic"].iloc[0] if "liquid_low_breadth" in results["name"].values else np.nan
    liquid = results[results["name"] == "liquid"]["avg_ic"].iloc[0] if "liquid" in results["name"].values else np.nan
    blocked_hb = results[results["name"] == "blocked_high_breadth"]["avg_ic"].iloc[0] if "blocked_high_breadth" in results["name"].values else np.nan
    blocked_lb = results[results["name"] == "blocked_low_breadth"]["avg_ic"].iloc[0] if "blocked_low_breadth" in results["name"].values else np.nan
    blocked_either = results[results["name"] == "blocked_either"]["avg_ic"].iloc[0] if "blocked_either" in results["name"].values else np.nan
    low_br = results[results["name"] == "low_breadth"]["avg_ic"].iloc[0] if "low_breadth" in results["name"].values else np.nan
    high_br = results[results["name"] == "high_breadth"]["avg_ic"].iloc[0] if "high_breadth" in results["name"].values else np.nan

    diff_liquid_hb_lb = liquid_hb - liquid_lb if not (np.isnan(liquid_hb) or np.isnan(liquid_lb)) else np.nan
    diff_liquid_hb_liq = liquid_hb - liquid if not (np.isnan(liquid_hb) or np.isnan(liquid)) else np.nan
    diff_blocked_hb_liq = blocked_hb - blocked_either if not (np.isnan(blocked_hb) or np.isnan(blocked_either)) else np.nan
    liquid_lift_hb = liquid_hb - high_br if not (np.isnan(liquid_hb) or np.isnan(high_br)) else np.nan
    blocked_lift_hb = blocked_hb - high_br if not (np.isnan(blocked_hb) or np.isnan(high_br)) else np.nan

    print(f"\nBaseline IC: {baseline:.4f}")
    print(f"Liquid × high_breadth: {liquid_hb:.4f}")
    print(f"Liquid × low_breadth: {liquid_lb:.4f}")
    print(f"Liquid alone: {liquid:.4f}")
    print(f"Blocked × high_breadth: {blocked_hb:.4f}")
    print(f"Blocked × low_breadth: {blocked_lb:.4f}")
    print(f"Blocked alone: {blocked_either:.4f}")
    print(f"Liquid × high vs × low breadth: {diff_liquid_hb_lb:+.4f}")
    print(f"Liquid × high vs liquid alone: {diff_liquid_hb_liq:+.4f}")
    print(f"Blocked × high vs blocked alone: {diff_blocked_hb_liq:+.4f}")
    print(f"Liquid lift in high_breadth: {liquid_lift_hb:+.4f}")
    print(f"Blocked lift in high_breadth: {blocked_lift_hb:+.4f}")

    if not np.isnan(diff_liquid_hb_lb):
        if diff_liquid_hb_lb > 0.01:
            decision = "PASSED"
        elif diff_liquid_hb_lb > 0.005:
            decision = "MIXED"
        elif diff_liquid_hb_lb > 0:
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
            "liquid_high_breadth_ic": liquid_hb,
            "liquid_low_breadth_ic": liquid_lb,
            "liquid_ic": liquid,
            "blocked_high_breadth_ic": blocked_hb,
            "blocked_low_breadth_ic": blocked_lb,
            "blocked_either_ic": blocked_either,
            "low_breadth_ic": low_br,
            "high_breadth_ic": high_br,
            "diff_liquid_hb_lb": diff_liquid_hb_lb,
            "diff_liquid_hb_liq": diff_liquid_hb_liq,
            "liquid_lift_high_breadth": liquid_lift_hb,
            "blocked_lift_high_breadth": blocked_lift_hb,
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": "liquid in bad breadth as contrarian",
        },
    )

    print(f"\nDecision: {decision}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()