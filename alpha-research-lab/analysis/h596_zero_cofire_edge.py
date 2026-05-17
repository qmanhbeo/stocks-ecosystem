"""
H596 - Zero-Cofire Edge Test

Hypothesis: F440 showed Q1 cofire (few competitors) is strong (IC=0.2064). But Q1 includes
"1-2 other signals". Maybe "ZERO" (completely isolated, no other signals firing) is even 
stronger than Q1 (1-2 competitors). Zero competition = pure hidden demand.

Test: Using C16 active state as proxy for signal firing. 
- active = order_volume_ratio_rank < 0.2 (bottom 20% = signal firing)
- Count how many stocks are active per day (cofire proxy = breadth)
- Test: isolated (only my stock active that day) vs few (1-2 others) vs many (3+)

Pass criteria: isolated (zero others) IC > Q1 (few competitors) IC by +0.01 lift.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
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
    load_s1_decision_panel,
    validate_state_columns,
    write_dataframe_artifact,
)


BRANCH_NAME = "h596_zero_cofire_edge"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Zero-Cofire Edge: completely isolated stocks (zero competitors) may be stronger "
        "than Q1 (few competitors). Using C16 active state as signal proxy."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H596 Zero-Cofire Edge Test")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    return parser.parse_args()


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    # Load S1 panel
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )

    # For this test, we need C16 (order_volume_ratio_rank)
    # Load it from the standard path
    from src.repo_paths import data_path
    c16_path = data_path("features/xs_order_pressure_daily.parquet")
    c16_cols = ["time", "ticker", "order_volume_ratio_rank"]
    c16_df = pd.read_parquet(c16_path, columns=c16_cols)
    
    # Normalize time format
    c16_df["time"] = pd.to_datetime(c16_df["time"])
    panel["time"] = pd.to_datetime(panel["time"])
    
    # Merge C16 onto panel
    panel = panel.merge(c16_df, on=["time", "ticker"], how="inner")
    print(f"Merged panel: {len(panel)} rows")

    # Define "active" state (signal firing proxy): bottom 20% = high pressure
    # This mirrors C16-based signal detection
    panel["is_active"] = (panel["order_volume_ratio_rank"] < 0.20).astype(int)

    # Compute per-date how many stocks are active (cofire proxy = breadth)
    date_active_count = panel.groupby("time")["is_active"].sum().reset_index()
    date_active_count.columns = ["time", "active_count"]
    panel = panel.merge(date_active_count, on="time", how="left")

    # Total stocks per date for normalization
    date_total = panel.groupby("time")["ticker"].count().reset_index()
    date_total.columns = ["time", "total_stocks"]
    panel = panel.merge(date_total, on="time", how="left")

    # Active fraction (breadth)
    panel["active_fraction"] = panel["active_count"] / panel["total_stocks"]

    # Now define the cofire states:
    # - isolated: my stock is active AND only 0-1 other stocks are active that day
    # - few: my stock is active AND 2-3 other stocks are active that day  
    # - many: my stock is active AND 4+ other stocks are active that day

    # Other active stocks besides me
    panel["others_active"] = panel["active_count"] - panel["is_active"]

    # States for testing
    # Isolated: I'm active + 0-1 others (similar to "zero competitors")
    panel["isolated"] = (panel["is_active"] == 1) & (panel["others_active"] <= 1)
    
    # Few: I'm active + 2-3 others (similar to Q1 "few competitors") 
    panel["few"] = (panel["is_active"] == 1) & (panel["others_active"].between(2, 3))
    
    # Many: I'm active + 4+ others (similar to Q4 "crowded")
    panel["many"] = (panel["is_active"] == 1) & (panel["others_active"] >= 4)

    # Alternative: Use quintiles of others_active for cleaner comparison
    # Q1: 0-1 others (isolated)
    # Q2: 2-3 others (few)
    # Q3: 4-6 others
    # Q4: 7-10 others  
    # Q5: 11+ others (crowded)
    
    # Also test: any active stock vs baseline
    panel["any_active"] = panel["is_active"] == 1

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("any_active", "Any active state (C16 rank < 0.2)", family="signal"),
    StateSpec("isolated", "Active + 0-1 others (zero competitors)", family="isolated"),
    StateSpec("few", "Active + 2-3 others (few competitors)", family="few"),
    StateSpec("many", "Active + 4+ others (crowded)", family="many"),
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

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    # F440 baseline: Q1 (cofire 1-2) = IC 0.2064
    # Pass: isolated IC > few IC by +0.01 (comparing within same methodology)
    
    isolated_row = results[results["name"] == "isolated"]
    few_row = results[results["name"] == "few"]
    many_row = results[results["name"] == "many"]
    any_active_row = results[results["name"] == "any_active"]

    isolated_ic = isolated_row["avg_ic"].iloc[0] if not isolated_row.empty else 0
    few_ic = few_row["avg_ic"].iloc[0] if not few_row.empty else 0
    many_ic = many_row["avg_ic"].iloc[0] if not many_row.empty else 0
    any_active_ic = any_active_row["avg_ic"].iloc[0] if not any_active_row.empty else 0

    # F440 Q1 reference is 0.2064 (but that's from different signal computation)
    # Compare within our methodology: isolated vs few
    # Pass if isolated beats few by +0.01
    if isolated_ic > few_ic + 0.01:
        decision = "PASSED"
    elif isolated_ic > few_ic:
        decision = "MIXED"  # direction correct but below threshold
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "isolated_ic": float(isolated_ic),
            "few_ic": float(few_ic),
            "many_ic": float(many_ic),
            "any_active_ic": float(any_active_ic),
            "isolated_vs_few": float(isolated_ic - few_ic),
            "isolated_vs_many": float(isolated_ic - many_ic),
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
    print(f"decision: {decision}")
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()