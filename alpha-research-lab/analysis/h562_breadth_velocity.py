"""
H562: Breadth Velocity (Change Rate)

H550 found C24 benefits from own-breadth filtering, H525 found low_breadth is better.
Now test: NOT how LOW breadth is, but how FAST it's contracting.
Rapid collapse = regime shift = stronger alpha.

Hypothesis: Breadth CHANGE RATE (velocity) is a hidden regime:
- contracting (breadth decreasing) = regime shift = stronger signal
- expanding (breadth increasing) = crowded regime = weaker signal

Pass criterion: contracting beats expanding by > +0.01 IC lift
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


BRANCH_NAME = "breadth_velocity"
MODE = "research_branch"


def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="H562: Breadth Velocity (Change Rate) Test")
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

    date_breadth = panel.groupby("time")["ticker"].nunique().reset_index()
    date_breadth = date_breadth.sort_values("time")
    date_breadth["breadth_lag1"] = date_breadth["ticker"].shift(1)
    date_breadth["breadth_change"] = date_breadth["ticker"] - date_breadth["breadth_lag1"]

    breadth_change_threshold = date_breadth["breadth_change"].quantile([0.2, 0.8])
    date_breadth["breadth_contracting"] = date_breadth["breadth_change"] <= breadth_change_threshold[0.2]
    date_breadth["breadth_expanding"] = date_breadth["breadth_change"] >= breadth_change_threshold[0.8]
    date_breadth["breadth_steady"] = ~(date_breadth["breadth_contracting"] | date_breadth["breadth_expanding"])

    breadth_20 = panel.groupby("time")["ticker"].nunique().quantile(0.20)
    date_breadth["low_breadth"] = date_breadth["ticker"] <= breadth_20

    panel = panel.merge(date_breadth[["time", "breadth_change", "breadth_contracting", 
                                       "breadth_expanding", "breadth_steady", "low_breadth"]], 
                       on="time", how="left")

    return panel


def run_branch(args: argparse.Namespace) -> str:
    spec = ExperimentSpec(
        name=BRANCH_NAME,
        mode=MODE,
        hypothesis=(
            "Test if breadth CHANGE RATE (velocity) is a hidden regime. "
            "Contracting = regime shift = stronger signal. "
            "Expanding = crowded = weaker signal."
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
        StateSpec("low_breadth", "Low breadth dates (bottom 20%)", family="breadth"),
        StateSpec("breadth_contracting", "Breadth decreasing (velocity negative)", family="velocity"),
        StateSpec("breadth_expanding", "Breadth increasing (velocity positive)", family="velocity"),
        StateSpec("breadth_steady", "Breadth stable", family="velocity"),
        StateSpec("breadth_contracting_low_breadth", "Contracting + Low breadth", family="combo"),
        StateSpec("breadth_expanding_low_breadth", "Expanding + Low breadth", family="combo"),
    ]

    available_states = [s.name for s in STATE_SPECS if s.name in panel.columns]
    STATE_SPECS = [s for s in STATE_SPECS if s.name in available_states]

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

    print("=== H562: Breadth Velocity Test ===")
    print(results[["name", "avg_ic", "positive_years", "years"]].sort_values("avg_ic", ascending=False).to_string(index=False))

    baseline = results[results["name"] == "all_rows"]["avg_ic"].iloc[0] if "all_rows" in results["name"].values else results["avg_ic"].mean()
    contracting = results[results["name"] == "breadth_contracting"]["avg_ic"].iloc[0] if "breadth_contracting" in results["name"].values else 0.0
    expanding = results[results["name"] == "breadth_expanding"]["avg_ic"].iloc[0] if "breadth_expanding" in results["name"].values else 0.0

    velocity_lift = contracting - expanding

    if velocity_lift > 0.01:
        decision = "PASSED"
    elif velocity_lift > 0.005:
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
            "contracting_ic": contracting,
            "expanding_ic": expanding,
            "velocity_lift": velocity_lift,
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": "breadth velocity as regime detector",
        },
    )

    print(f"\nBaseline IC: {baseline:.4f}")
    print(f"Contracting IC: {contracting:.4f}")
    print(f"Expanding IC: {expanding:.4f}")
    print(f"Velocity Lift: {velocity_lift:.4f}")
    print(f"\nDecision: {decision}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()