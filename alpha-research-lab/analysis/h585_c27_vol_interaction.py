"""
H585: C27 × Market Activity Interaction

H574 found blocked_either IC=0.1477 (implementation pain = alpha).
H583 found blocked × high_breadth = 0.2029 (STRONGEST single state this session).
H460: all signals work best in vol_expansion — vol LEVEL matters, not change.
H534: longer in active state = stronger signal (persistent hidden demand).

Since vol data is not directly available in the panel, use market-level order
pressure as proxy. When the market has high aggregate order activity (many orders),
it's a "hot" market regime.

Test: blocked × high market activity vs low market activity.

Pass criterion: blocked × high_activity beats blocked × low_activity by > +0.01 IC
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


BRANCH_NAME = "c27_market_activity_interaction"
MODE = "research_branch"


def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="H585: C27 × Market Activity Interaction")
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
    panel = panel.merge(c16_df[["time", "ticker", "order_volume_ratio_rank", "order_volume_ratio"]], on=["time", "ticker"], how="left")

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

    avg_pressure = panel.groupby("time")["order_volume_ratio"].mean().reset_index()
    avg_pressure.columns = ["time", "avg_pressure"]
    pressure_80 = avg_pressure["avg_pressure"].quantile(0.80)
    pressure_20 = avg_pressure["avg_pressure"].quantile(0.20)
    avg_pressure["high_activity"] = avg_pressure["avg_pressure"] >= pressure_80
    avg_pressure["low_activity"] = avg_pressure["avg_pressure"] <= pressure_20
    panel = panel.merge(avg_pressure[["time", "high_activity", "low_activity"]], on="time", how="left")

    panel["blocked_high_activity"] = panel["blocked_either"] & panel["high_activity"]
    panel["blocked_low_activity"] = panel["blocked_either"] & panel["low_activity"]
    panel["liquid_high_activity"] = panel["liquid"] & panel["high_activity"]
    panel["liquid_low_activity"] = panel["liquid"] & panel["low_activity"]

    panel["blocked_high_breadth"] = panel["blocked_either"] & panel["high_breadth"]
    panel["blocked_low_breadth"] = panel["blocked_either"] & panel["low_breadth"]

    panel["all_rows"] = True

    print(f"Panel rows: {len(panel)}")
    print(f"blocked_either: {panel['blocked_either'].sum()}")
    print(f"high_activity days: {panel['high_activity'].sum()}")
    print(f"low_activity days: {panel['low_activity'].sum()}")
    print(f"blocked_high_activity: {panel['blocked_high_activity'].sum()}")
    print(f"blocked_low_activity: {panel['blocked_low_activity'].sum()}")
    print(f"blocked_high_breadth: {panel['blocked_high_breadth'].sum()}")
    print(f"blocked_low_breadth: {panel['blocked_low_breadth'].sum()}")

    return panel


def run_branch(args: argparse.Namespace) -> str:
    spec = ExperimentSpec(
        name=BRANCH_NAME,
        mode=MODE,
        hypothesis=(
            "Test if C27 (blocked stocks) works differently in high vs low market activity regimes. "
            "Use avg order pressure per day as market activity proxy (proxy for vol regime)."
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
        StateSpec("blocked_either", "Blocked stocks (C27)", family="c27"),
        StateSpec("high_activity", "High market activity days", family="activity"),
        StateSpec("low_activity", "Low market activity days", family="activity"),
        StateSpec("blocked_high_activity", "C27 × high activity", family="c27_act"),
        StateSpec("blocked_low_activity", "C27 × low activity", family="c27_act"),
        StateSpec("liquid_high_activity", "Liquid × high activity", family="liq_act"),
        StateSpec("liquid_low_activity", "Liquid × low activity", family="liq_act"),
        StateSpec("blocked_high_breadth", "C27 × high breadth", family="c27_breadth"),
        StateSpec("blocked_low_breadth", "C27 × low breadth", family="c27_breadth"),
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

    print("\n=== H585: C27 × Market Activity Interaction ===")
    print(results[["name", "avg_ic", "positive_years", "years", "pooled_rows"]].sort_values("avg_ic", ascending=False).to_string(index=False))

    baseline = results[results["name"] == "all_rows"]["avg_ic"].iloc[0] if "all_rows" in results["name"].values else np.nan
    blocked_ha = results[results["name"] == "blocked_high_activity"]["avg_ic"].iloc[0] if "blocked_high_activity" in results["name"].values else np.nan
    blocked_la = results[results["name"] == "blocked_low_activity"]["avg_ic"].iloc[0] if "blocked_low_activity" in results["name"].values else np.nan
    blocked_hb = results[results["name"] == "blocked_high_breadth"]["avg_ic"].iloc[0] if "blocked_high_breadth" in results["name"].values else np.nan
    blocked_lb = results[results["name"] == "blocked_low_breadth"]["avg_ic"].iloc[0] if "blocked_low_breadth" in results["name"].values else np.nan
    blocked_either = results[results["name"] == "blocked_either"]["avg_ic"].iloc[0] if "blocked_either" in results["name"].values else np.nan
    liquid_ha = results[results["name"] == "liquid_high_activity"]["avg_ic"].iloc[0] if "liquid_high_activity" in results["name"].values else np.nan
    liquid_la = results[results["name"] == "liquid_low_activity"]["avg_ic"].iloc[0] if "liquid_low_activity" in results["name"].values else np.nan
    liquid = results[results["name"] == "liquid"]["avg_ic"].iloc[0] if "liquid" in results["name"].values else np.nan
    high_act = results[results["name"] == "high_activity"]["avg_ic"].iloc[0] if "high_activity" in results["name"].values else np.nan
    low_act = results[results["name"] == "low_activity"]["avg_ic"].iloc[0] if "low_activity" in results["name"].values else np.nan

    diff_activity = blocked_ha - blocked_la if not (np.isnan(blocked_ha) or np.isnan(blocked_la)) else np.nan
    c27_lift_ha = blocked_ha - high_act if not (np.isnan(blocked_ha) or np.isnan(high_act)) else np.nan
    c27_lift_la = blocked_la - low_act if not (np.isnan(blocked_la) or np.isnan(low_act)) else np.nan

    print(f"\nBaseline IC: {baseline:.4f}")
    print(f"C27 × high_activity: {blocked_ha:.4f}")
    print(f"C27 × low_activity: {blocked_la:.4f}")
    print(f"C27 × high vs low activity: {diff_activity:+.4f}")
    print(f"High activity alone: {high_act:.4f}")
    print(f"Low activity alone: {low_act:.4f}")
    print(f"C27 × high_breadth: {blocked_hb:.4f}")
    print(f"C27 × low_breadth: {blocked_lb:.4f}")
    print(f"Liquid × high_activity: {liquid_ha:.4f}")
    print(f"Liquid × low_activity: {liquid_la:.4f}")
    print(f"C27 lift in high_activity: {c27_lift_ha:+.4f}")
    print(f"C27 lift in low_activity: {c27_lift_la:+.4f}")

    if not np.isnan(diff_activity):
        if diff_activity > 0.01:
            decision = "PASSED"
        elif diff_activity > 0.005:
            decision = "MIXED"
        elif diff_activity > 0:
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
            "blocked_high_activity_ic": blocked_ha,
            "blocked_low_activity_ic": blocked_la,
            "blocked_either_ic": blocked_either,
            "blocked_high_breadth_ic": blocked_hb,
            "blocked_low_breadth_ic": blocked_lb,
            "liquid_ic": liquid,
            "liquid_high_activity_ic": liquid_ha,
            "liquid_low_activity_ic": liquid_la,
            "high_activity_ic": high_act,
            "low_activity_ic": low_act,
            "diff_activity": diff_activity,
            "c27_lift_high_activity": c27_lift_ha,
            "c27_lift_low_activity": c27_lift_la,
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": "C27 × market activity interaction",
        },
    )

    print(f"\nDecision: {decision}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()