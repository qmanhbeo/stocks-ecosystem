"""
H575: Foreign Flow Regime as C27 Conditioner

Hypothesis: C27 (blocked stocks = implementation pain) may work differently
in foreign-up vs foreign-down regimes. H443 failed as additive signal (ff_buy
underperforms baseline), but foreign regime was never tested AS A CONDITIONER
on C27.

Mechanism: Foreign investors are informed/large. When they are accumulating
(foreign_up), hidden demand is even stronger. blocked + foreign_up = extreme
pain = extreme alpha. When they are selling (foreign_down), the signal may
be noise or weaker.

Pass criterion: blocked × foreign_up beats blocked × foreign_down by > +0.01 IC,
or blocked beats liquid in foreign_up regime by > +0.01 more than in foreign_down regime.
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


BRANCH_NAME = "foreign_flow_regime_c27_conditioner"
MODE = "research_branch"


def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="H575: Foreign Flow Regime as C27 Conditioner")
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    return parser.parse_args()


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    panel = load_s1_decision_panel(
        S1_DEFAULT_PATH,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )

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
    panel["all_rows"] = True

    ff_path = data_path("foreign_flow/cafef/foreign_flow_daily.parquet")
    ff_df = pd.read_parquet(ff_path)
    ff_df = ff_df.rename(columns={"date": "time"})
    ff_df = normalize_time_ticker(ff_df, source="foreign_flow")
    ff_df = restrict_years(ff_df, start_year=spec.start_year, end_year=spec.end_year, source="foreign_flow")

    ff_df["foreign_up"] = ff_df["foreign_net_volume"] > 0
    ff_df["foreign_down"] = ff_df["foreign_net_volume"] < 0

    date_ff = ff_df.groupby("time").agg(
        foreign_up_count=("foreign_up", "sum"),
        foreign_down_count=("foreign_down", "sum"),
        foreign_net_volume_sum=("foreign_net_volume", "sum"),
    ).reset_index()
    date_ff["foreign_up_regime"] = date_ff["foreign_up_count"] > date_ff["foreign_down_count"]

    panel = panel.merge(
        date_ff[["time", "foreign_up_regime", "foreign_net_volume_sum"]],
        on="time",
        how="left"
    )

    panel["foreign_up_regime"] = panel["foreign_up_regime"].fillna(False)

    panel["blocked_foreign_up"] = panel["blocked_either"] & panel["foreign_up_regime"]
    panel["blocked_foreign_down"] = panel["blocked_either"] & ~panel["foreign_up_regime"]
    panel["liquid_foreign_up"] = panel["liquid"] & panel["foreign_up_regime"]
    panel["liquid_foreign_down"] = panel["liquid"] & ~panel["foreign_up_regime"]

    print(f"Panel rows: {len(panel)}")
    print(f"Foreign up regime days: {panel['foreign_up_regime'].sum()} ({100*panel['foreign_up_regime'].mean():.1f}%)")
    print(f"Foreign down regime days: {(~panel['foreign_up_regime']).sum()}")
    print(f"blocked_either: {panel['blocked_either'].sum()}")
    print(f"blocked_foreign_up: {panel['blocked_foreign_up'].sum()}")
    print(f"blocked_foreign_down: {panel['blocked_foreign_down'].sum()}")
    print(f"liquid: {panel['liquid'].sum()}")
    print(f"liquid_foreign_up: {panel['liquid_foreign_up'].sum()}")
    print(f"liquid_foreign_down: {panel['liquid_foreign_down'].sum()}")

    return panel


def run_branch(args: argparse.Namespace) -> str:
    spec = ExperimentSpec(
        name=BRANCH_NAME,
        mode=MODE,
        hypothesis=(
            "Test if C27 (blocked stocks) works differently in foreign-up vs "
            "foreign-down regimes. H443 failed as additive, now test as conditioner."
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
        StateSpec("foreign_up_regime", "Foreign-up regime days", family="regime"),
        StateSpec("blocked_foreign_up", "C27 × foreign-up", family="c27_regime"),
        StateSpec("blocked_foreign_down", "C27 × foreign-down", family="c27_regime"),
        StateSpec("liquid_foreign_up", "Liquid × foreign-up", family="liq_regime"),
        StateSpec("liquid_foreign_down", "Liquid × foreign-down", family="liq_regime"),
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

    print("\n=== H575: Foreign Flow Regime as C27 Conditioner ===")
    print(results[["name", "avg_ic", "positive_years", "years", "pooled_rows"]].sort_values("avg_ic", ascending=False).to_string(index=False))

    baseline = results[results["name"] == "all_rows"]["avg_ic"].iloc[0]
    blocked_fu = results[results["name"] == "blocked_foreign_up"]["avg_ic"].iloc[0] if "blocked_foreign_up" in results["name"].values else np.nan
    blocked_fd = results[results["name"] == "blocked_foreign_down"]["avg_ic"].iloc[0] if "blocked_foreign_down" in results["name"].values else np.nan
    liquid_fu = results[results["name"] == "liquid_foreign_up"]["avg_ic"].iloc[0] if "liquid_foreign_up" in results["name"].values else np.nan
    liquid_fd = results[results["name"] == "liquid_foreign_down"]["avg_ic"].iloc[0] if "liquid_foreign_down" in results["name"].values else np.nan
    blocked_either = results[results["name"] == "blocked_either"]["avg_ic"].iloc[0] if "blocked_either" in results["name"].values else np.nan
    liquid = results[results["name"] == "liquid"]["avg_ic"].iloc[0] if "liquid" in results["name"].values else np.nan
    foreign_up_regime = results[results["name"] == "foreign_up_regime"]["avg_ic"].iloc[0] if "foreign_up_regime" in results["name"].values else np.nan

    diff_blocked = blocked_fu - blocked_fd if not (np.isnan(blocked_fu) or np.isnan(blocked_fd)) else np.nan
    diff_c27_lift = (blocked_fu - liquid_fu) - (blocked_fd - liquid_fd) if not (np.isnan(blocked_fu) or np.isnan(liquid_fu) or np.isnan(blocked_fd) or np.isnan(liquid_fd)) else np.nan

    print(f"\nBaseline IC: {baseline:.4f}")
    print(f"C27 × foreign-up: {blocked_fu:.4f}")
    print(f"C27 × foreign-down: {blocked_fd:.4f}")
    print(f"C27 × foreign-up vs × foreign-down: {diff_blocked:+.4f}")
    print(f"Liquid × foreign-up: {liquid_fu:.4f}")
    print(f"Liquid × foreign-down: {liquid_fd:.4f}")
    print(f"C27 lift in foreign-up: {blocked_fu - liquid_fu:+.4f}")
    print(f"C27 lift in foreign-down: {blocked_fd - liquid_fd:+.4f}")
    print(f"C27 lift differential: {diff_c27_lift:+.4f}")

    if not np.isnan(diff_blocked):
        if diff_blocked > 0.01:
            decision = "PASSED"
        elif diff_blocked > 0.005:
            decision = "MIXED"
        elif diff_blocked > 0:
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
            "blocked_foreign_up_ic": blocked_fu,
            "blocked_foreign_down_ic": blocked_fd,
            "blocked_diff": diff_blocked,
            "c27_lift_foreign_up": blocked_fu - liquid_fu if not np.isnan(blocked_fu) else np.nan,
            "c27_lift_foreign_down": blocked_fd - liquid_fd if not np.isnan(blocked_fd) else np.nan,
            "c27_lift_differential": diff_c27_lift,
            "liquid_ic": liquid,
            "blocked_either_ic": blocked_either,
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": "foreign flow regime as C27 conditioner",
        },
    )

    print(f"\nDecision: {decision}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()