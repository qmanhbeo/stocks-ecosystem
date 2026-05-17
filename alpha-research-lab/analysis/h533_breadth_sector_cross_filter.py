"""
H533: Breadth-Sector Cross-Filter

Hypothesis: Sector-level breadth vs market-level breadth. Low sector + high market 
= sector-specific alpha. H526 tested sector×C23, not sector×breadth.

Decision ladder:
- PASS: low_sector_high_market IC > max(all_rows, high_market_only) by +0.01 lift
- MIXED: low_sector_high_market beats high_market but not by +0.01
- FAIL: low_sector_high_market does not beat high_market baseline
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


BRANCH_NAME = "breadth_sector_cross_filter"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Sector-level breadth vs market-level breadth. Low sector + high market "
        "= sector-specific alpha. H526 tested sector×C23, not sector×breadth."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H533 breadth-sector cross-filter experiment")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    parser.add_argument("--breadth-quintile-cutoff", type=float, default=0.20, 
                        help="Quintile threshold for low/high breadth (default 0.20 = bottom 20%)")
    return parser.parse_args()


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )

    sector_path = data_path("features/sector_classification.parquet")
    sector_df = pd.read_parquet(sector_path)
    sector_df = sector_df.rename(columns={"symbol": "ticker"})
    sector_df = sector_df[["ticker", "icb_name2"]].rename(columns={"icb_name2": "sector"}).dropna()
    panel = panel.merge(sector_df, on="ticker", how="left")

    c16_path = data_path("features/xs_order_pressure_daily.parquet")
    c16_df = pd.read_parquet(c16_path)
    c16_df = c16_df[["time", "ticker", "order_volume_ratio_rank"]].rename(
        columns={"order_volume_ratio_rank": "c16_rank"}
    )
    panel = panel.merge(c16_df, on=["time", "ticker"], how="left")

    panel["is_active"] = panel["c16_rank"] <= 0.20

    date_active = panel[panel["is_active"]].groupby("time").size().reset_index(name="market_active_count")
    panel = panel.merge(date_active, on="time", how="left")
    panel["market_active_count"] = panel["market_active_count"].fillna(0)

    market_breadth_quintile = panel.groupby("time")["market_active_count"].transform(
        lambda x: pd.qcut(x.rank(method="first"), q=5, labels=False, duplicates="drop") / 5
    )
    panel["market_breadth_quintile"] = market_breadth_quintile

    sector_active = panel[panel["is_active"]].groupby(["time", "sector"]).size().reset_index(name="sector_active_count")
    panel = panel.merge(sector_active, on=["time", "sector"], how="left")
    panel["sector_active_count"] = panel["sector_active_count"].fillna(0)

    sector_breadth_quintile = panel.groupby(["time", "sector"])["sector_active_count"].transform(
        lambda x: pd.qcut(x.rank(method="first"), q=5, labels=False, duplicates="drop") / 5
    )
    panel["sector_breadth_quintile"] = sector_breadth_quintile

    panel["low_sector_breadth"] = panel["sector_breadth_quintile"] <= args.breadth_quintile_cutoff
    panel["high_market_breadth"] = panel["market_breadth_quintile"] >= (1 - args.breadth_quintile_cutoff)

    panel["low_sector_high_market"] = panel["low_sector_breadth"] & panel["high_market_breadth"]
    panel["high_sector_high_market"] = ~panel["low_sector_breadth"] & panel["high_market_breadth"]
    panel["low_sector_low_market"] = panel["low_sector_breadth"] & ~panel["high_market_breadth"]
    panel["high_market_breadth_only"] = panel["high_market_breadth"]
    panel["low_sector_breadth_only"] = panel["low_sector_breadth"]

    panel["all_rows"] = True

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec(
        "low_sector_high_market",
        "Low sector breadth + high market breadth",
        family="candidate",
        baseline="all_rows",
    ),
    StateSpec(
        "high_sector_high_market",
        "High sector breadth + high market breadth",
        family="control",
        baseline="all_rows",
    ),
    StateSpec(
        "low_sector_low_market",
        "Low sector breadth + low market breadth",
        family="control",
        baseline="all_rows",
    ),
    StateSpec(
        "high_market_breadth_only",
        "High market breadth (any sector)",
        family="control",
        baseline="all_rows",
    ),
    StateSpec(
        "low_sector_breadth_only",
        "Low sector breadth (any market)",
        family="control",
        baseline="all_rows",
    ),
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

    baseline_ic = results[results["name"] == "all_rows"]["avg_ic"].iloc[0]
    candidate_ic = results[results["name"] == "low_sector_high_market"]["avg_ic"].iloc[0]
    high_market_ic = results[results["name"] == "high_market_breadth_only"]["avg_ic"].iloc[0]

    candidate_lift = candidate_ic - baseline_ic
    vs_high_market_lift = candidate_ic - high_market_ic

    if candidate_lift > 0.01 and vs_high_market_lift > 0.01:
        decision = "PASSED"
    elif candidate_lift > 0 and vs_high_market_lift > 0:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "candidate_ic": float(candidate_ic),
            "candidate_lift": float(candidate_lift),
            "vs_high_market_lift": float(vs_high_market_lift),
            "high_market_ic": float(high_market_ic),
            "breadth_cutoff": args.breadth_quintile_cutoff,
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
    print(f"\ndecision: {decision}")
    print(f"baseline_ic: {baseline_ic:.4f}, candidate_ic: {candidate_ic:.4f}, lift: {candidate_lift:.4f}")
    print(f"vs_high_market_lift: {vs_high_market_lift:.4f}")
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()