"""
H566: Time-Since-Active as Hidden State

H522 transitions don't help individually.
Hypothesis: Test "time since last active state" as a continuous hidden variable 
that modulates signal strength REGARDLESS of current state. Even if currently 
quiet, time-since-last-active might capture dormant alpha.

Pass criterion: time_since_active captures IC variation beyond current state
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

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
    validate_state_columns,
    write_dataframe_artifact,
    normalize_time_ticker,
    restrict_years,
)
from src.repo_paths import data_path


BRANCH_NAME = "time_since_active_hidden_state"
MODE = "research_branch"


def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="H566: Time-Since-Active Hidden State Test")
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    return parser.parse_args()


def load_panel(args: argparse.Namespace) -> pd.DataFrame:
    s1_path = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
    s1_df = pd.read_parquet(s1_path, columns=["time", "ticker", "xs_proba", "actual"])
    s1_df = normalize_time_ticker(s1_df, source="S1 panel")
    s1_df = restrict_years(s1_df, start_year=args.start_year, end_year=args.end_year, source="S1 panel")
    s1_df = s1_df.rename(columns={"xs_proba": "s1_xs_proba", "actual": "s1_barrier_hit_1d"})

    c16_path = data_path("features/xs_order_pressure_daily.parquet")
    c16_df = pd.read_parquet(c16_path)
    c16_df = normalize_time_ticker(c16_df, source="C16 panel")
    c16_df = restrict_years(c16_df, start_year=args.start_year, end_year=args.end_year, source="C16 panel")

    panel = s1_df.merge(c16_df, on=["time", "ticker"], how="inner")
    print(f"Merged panel: {len(panel)} rows")

    panel = panel.sort_values(["ticker", "time"])
    panel["c16_low"] = panel["order_volume_ratio_rank"] <= 0.2
    panel["was_active"] = panel.groupby("ticker")["c16_low"].shift(1).fillna(False)
    panel["days_since_active"] = 0
    panel.loc[~panel["was_active"], "days_since_active"] = panel.groupby("ticker")["was_active"].cumsum().shift(1).fillna(0)
    panel.loc[panel["was_active"], "days_since_active"] = 0

    panel["tsa_0d"] = panel["days_since_active"] == 0
    panel["tsa_1_3d"] = (panel["days_since_active"] >= 1) & (panel["days_since_active"] <= 3)
    panel["tsa_4_7d"] = (panel["days_since_active"] >= 4) & (panel["days_since_active"] <= 7)
    panel["tsa_8_14d"] = (panel["days_since_active"] >= 8) & (panel["days_since_active"] <= 14)
    panel["tsa_15plus"] = panel["days_since_active"] >= 15

    return panel


def run_branch(args: argparse.Namespace) -> str:
    spec = ExperimentSpec(
        name=BRANCH_NAME,
        mode=MODE,
        hypothesis=(
            "Test time since last active state (C16 <= 0.2) as continuous hidden variable. "
            "Even if currently quiet, time since last active might capture dormant alpha."
        ),
        start_year=2015,
        end_year=2025,
        min_year_rows=500,
        min_phase_rows=500,
        target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
        score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
    )
    context = build_experiment_context(spec, artifact_subdir="research_branch")

    panel = load_panel(args)

    STATE_SPECS = [
        StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
        StateSpec("c16_low", "Currently active (C16 <= 0.2)", family="current_state"),
        StateSpec("tsa_0d", "Currently active (0 days since)", family="tsa"),
        StateSpec("tsa_1_3d", "1-3 days since active", family="tsa"),
        StateSpec("tsa_4_7d", "4-7 days since active", family="tsa"),
        StateSpec("tsa_8_14d", "8-14 days since active", family="tsa"),
        StateSpec("tsa_15plus", "15+ days since active", family="tsa"),
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

    print("=== H566: Time-Since-Active Hidden State Test ===")
    print(results[["name", "avg_ic", "positive_years", "years", "pooled_rows"]].sort_values("avg_ic", ascending=False).to_string(index=False))

    baseline = results[results["name"] == "all_rows"]["avg_ic"].iloc[0] if "all_rows" in results["name"].values else results["avg_ic"].mean()
    current = results[results["name"] == "c16_low"]["avg_ic"].iloc[0] if "c16_low" in results["name"].values else 0.0

    tsa_states = [s for s in STATE_SPECS if "time_since_active" in s.name]
    tsa_results = results[results["name"].isin([s.name for s in tsa_states])].sort_values("avg_ic", ascending=False)

    best_tsa = tsa_results.iloc[0]["avg_ic"] if not tsa_results.empty else 0.0
    best_tsa_name = tsa_results.iloc[0]["name"] if not tsa_results.empty else "N/A"

    tsa_vs_current = best_tsa - current

    if tsa_vs_current > 0.01:
        decision = "PASSED"
    elif tsa_vs_current > 0.005:
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
            "baseline_ic": baseline,
            "current_active_ic": current,
            "best_tsa_ic": best_tsa,
            "best_tsa_name": best_tsa_name,
            "tsa_vs_current": tsa_vs_current,
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": "time since active as hidden state",
        },
    )

    print(f"\nBaseline IC: {baseline:.4f}")
    print(f"Current Active IC: {current:.4f}")
    print(f"Best TSA ({best_tsa_name}) IC: {best_tsa:.4f}")
    print(f"TSA vs Current: {tsa_vs_current:.4f}")
    print(f"\nDecision: {decision}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()