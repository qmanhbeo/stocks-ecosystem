"""
H574: Implementation Pain as Positive Signal

Hypothesis: Current system treats tradability as veto (filters out illiquid stocks).
Test if "painful to trade" = hidden demand = alpha. Invert the veto.

The idea: illiquid stocks that are hard to trade may have hidden demand that
creates alpha when others can't easily enter.

Pass criterion: illiquid (low tradability) stocks beat liquid stocks by > +0.01 IC
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


BRANCH_NAME = "implementation_pain_positive"
MODE = "research_branch"


def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="H574: Implementation Pain as Positive Signal")
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

    panel["is_illiquid"] = ~panel["has_volume"].fillna(True)
    panel["blocked_buy"] = ~(panel["can_buy_next_open"].fillna(True))
    panel["blocked_sell"] = ~(panel["can_sell_next_open"].fillna(True))
    panel["blocked_either"] = panel["blocked_buy"] | panel["blocked_sell"]
    panel["blocked_both"] = panel["blocked_buy"] & panel["blocked_sell"]

    panel["liquid"] = panel["has_volume"].fillna(True) & panel["can_buy_next_open"].fillna(True)

    print(f"Panel rows: {len(panel)}")
    print(f"Illiquid (no volume): {panel['is_illiquid'].sum()}")
    print(f"Blocked buy: {panel['blocked_buy'].sum()}")
    print(f"Blocked sell: {panel['blocked_sell'].sum()}")
    print(f"Blocked either: {panel['blocked_either'].sum()}")
    print(f"Blocked both: {panel['blocked_both'].sum()}")
    print(f"Liquid (has_volume AND can_buy): {panel['liquid'].sum()}")

    return panel


def run_branch(args: argparse.Namespace) -> str:
    spec = ExperimentSpec(
        name=BRANCH_NAME,
        mode=MODE,
        hypothesis=(
            "Test if 'painful to trade' = hidden demand = alpha. "
            "Invert the tradability veto - test illiquid/blocked stocks vs liquid."
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
        StateSpec("liquid", "Liquid stocks (has_volume=True, can_buy=True)", family="liquid"),
        StateSpec("is_illiquid", "Illiquid stocks (no volume)", family="illiquid"),
        StateSpec("blocked_buy", "Blocked from buying", family="blocked"),
        StateSpec("blocked_sell", "Blocked from selling", family="blocked"),
        StateSpec("blocked_either", "Blocked from buying OR selling", family="blocked"),
        StateSpec("blocked_both", "Blocked from buying AND selling", family="blocked"),
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

    print("=== H574: Implementation Pain as Positive Signal ===")
    print(results[["name", "avg_ic", "positive_years", "years", "pooled_rows"]].sort_values("avg_ic", ascending=False).to_string(index=False))

    baseline = results[results["name"] == "all_rows"]["avg_ic"].iloc[0] if "all_rows" in results["name"].values else results["avg_ic"].mean()
    liquid = results[results["name"] == "liquid"]["avg_ic"].iloc[0] if "liquid" in results["name"].values else 0.0
    illiquid = results[results["name"] == "is_illiquid"]["avg_ic"].iloc[0] if "is_illiquid" in results["name"].values else 0.0
    blocked_buy = results[results["name"] == "blocked_buy"]["avg_ic"].iloc[0] if "blocked_buy" in results["name"].values else 0.0
    blocked_sell = results[results["name"] == "blocked_sell"]["avg_ic"].iloc[0] if "blocked_sell" in results["name"].values else 0.0
    blocked_either = results[results["name"] == "blocked_either"]["avg_ic"].iloc[0] if "blocked_either" in results["name"].values else 0.0

    blocked_vs_liquid = blocked_either - liquid

    if blocked_vs_liquid > 0.01:
        decision = "PASSED"
    elif blocked_vs_liquid > 0.005:
        decision = "MIXED"
    elif blocked_vs_liquid > 0:
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
            "liquid_ic": liquid,
            "illiquid_ic": illiquid,
            "blocked_buy_ic": blocked_buy,
            "blocked_sell_ic": blocked_sell,
            "blocked_either_ic": blocked_either,
            "blocked_vs_liquid": blocked_vs_liquid,
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": "implementation pain as positive signal",
        },
    )

    print(f"\nBaseline IC: {baseline:.4f}")
    print(f"Liquid IC: {liquid:.4f}")
    print(f"Illiquid IC: {illiquid:.4f}")
    print(f"Blocked Buy IC: {blocked_buy:.4f}")
    print(f"Blocked Sell IC: {blocked_sell:.4f}")
    print(f"Blocked Either IC: {blocked_either:.4f}")
    print(f"Blocked vs Liquid: {blocked_vs_liquid:.4f}")
    print(f"\nDecision: {decision}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()