"""
H527 - Quiet-State Inverse Alpha

Hypothesis: Are QUIET stocks in active markets contrarian?
- From H524: state_quiet is STRONG (IC=0.1552, 11/11 positive years)
- Test if quiet stocks (NOT in C23) on high-breadth dates (many stocks active)
  have different IC than quiet stocks on low-breadth dates
- If quiet stocks perform better in active markets = contrarian effect

Approach:
1. Compute date-level C23 active coverage (breadth)
2. Split dates into high-breadth (top 20%) vs low-breadth (bottom 20%)
3. For each regime, compute IC of quiet stocks vs all quiet stocks baseline

Pass criteria:
- Quiet stocks in high-breadth dates have meaningfully higher IC than
  quiet stocks in low-breadth dates (+0.01+ lift)
- This would indicate contrarian opportunity when market is crowded
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


BRANCH_NAME = "quiet_state_inverse_alpha"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Test if QUIET stocks (not in C23) in active markets (high date-level C23 coverage) "
        "are contrarian opportunities. From H524, state_quiet alone is STRONG (IC=0.1552). "
        "Does market activity level modulate quiet-stock quality?"
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="H527 Quiet-State Inverse Alpha: test quiet stocks in active markets"
    )
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    return parser.parse_args()


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )

    c16_path = ROOT / "data" / "features" / "xs_order_pressure_daily.parquet"
    c16 = pd.read_parquet(c16_path)
    panel = panel.merge(
        c16[["time", "ticker", "order_volume_ratio_rank", "order_volume_ratio"]],
        on=["time", "ticker"],
        how="left",
    )

    panel["c16_high"] = (panel["order_volume_ratio_rank"] >= 0.80).astype(bool)
    vol_threshold = panel["order_volume_ratio"].quantile(0.80)
    panel["vol_expansion"] = (panel["order_volume_ratio"] >= vol_threshold).astype(bool)
    panel["c23_active"] = (panel["c16_high"] & panel["vol_expansion"]).astype(bool)

    date_breadth = panel.groupby("time")["c23_active"].mean().reset_index()
    date_breadth.columns = ["time", "c23_breadth"]

    panel = panel.merge(date_breadth, on="time", how="left")

    high_thresh = panel["c23_breadth"].quantile(0.80)
    low_thresh = panel["c23_breadth"].quantile(0.20)

    panel["high_breadth_date"] = (panel["c23_breadth"] >= high_thresh).astype(bool)
    panel["low_breadth_date"] = (panel["c23_breadth"] <= low_thresh).astype(bool)

    panel["quiet_state"] = (~panel["c23_active"]).astype(bool)

    panel["quiet_only"] = panel["quiet_state"]
    panel["quiet_in_high_breadth"] = (panel["quiet_state"] & panel["high_breadth_date"]).astype(bool)
    panel["quiet_in_low_breadth"] = (panel["quiet_state"] & panel["low_breadth_date"]).astype(bool)
    panel["active_only"] = panel["c23_active"]
    panel["active_in_high_breadth"] = (panel["c23_active"] & panel["high_breadth_date"]).astype(bool)
    panel["active_in_low_breadth"] = (panel["c23_active"] & panel["low_breadth_date"]).astype(bool)

    return panel


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(
        SPEC,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        min_year_rows=int(args.min_year_rows),
        min_phase_rows=int(args.min_phase_rows),
    )
    context = build_experiment_context(spec, artifact_subdir="research_branch")
    panel = load_panel(args, spec)

    STATE_SPECS = [
        StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
        StateSpec(
            "quiet_only",
            "All quiet stocks (not in C23)",
            family="quiet",
            baseline="all_rows",
        ),
        StateSpec(
            "quiet_in_high_breadth",
            "Quiet stocks on high-breadth dates (top 20% active)",
            family="quiet_regime",
            baseline="quiet_only",
        ),
        StateSpec(
            "quiet_in_low_breadth",
            "Quiet stocks on low-breadth dates (bottom 20% active)",
            family="quiet_regime",
            baseline="quiet_only",
        ),
        StateSpec(
            "active_only",
            "Active stocks (in C23)",
            family="active",
            baseline="all_rows",
        ),
        StateSpec(
            "active_in_high_breadth",
            "Active stocks on high-breadth dates",
            family="active_regime",
            baseline="active_only",
        ),
        StateSpec(
            "active_in_low_breadth",
            "Active stocks on low-breadth dates",
            family="active_regime",
            baseline="active_only",
        ),
    ]

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

    quiet_only_ic = results[results["name"] == "quiet_only"]["avg_ic"].values[0]
    quiet_high_ic = results[results["name"] == "quiet_in_high_breadth"]["avg_ic"].values[0]
    quiet_low_ic = results[results["name"] == "quiet_in_low_breadth"]["avg_ic"].values[0]
    active_only_ic = results[results["name"] == "active_only"]["avg_ic"].values[0]

    quiet_high_vs_low = quiet_high_ic - quiet_low_ic
    quiet_high_vs_baseline = quiet_high_ic - quiet_only_ic

    decision_criteria = abs(quiet_high_vs_low) >= 0.010
    if decision_criteria:
        if quiet_high_ic > quiet_low_ic:
            decision = "PASSED"
        else:
            decision = "MIXED"
    elif abs(quiet_high_vs_low) >= 0.005:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "quiet_only_ic": float(quiet_only_ic),
            "quiet_high_breadth_ic": float(quiet_high_ic),
            "quiet_low_breadth_ic": float(quiet_low_ic),
            "active_only_ic": float(active_only_ic),
            "quiet_high_vs_low_lift": float(quiet_high_vs_low),
            "quiet_high_vs_baseline_lift": float(quiet_high_vs_baseline),
            "contrarian_effect": quiet_high_ic > quiet_low_ic,
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
        },
    )

    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(f"\nDecision: {decision}")
    print(f"Quiet in high breadth IC: {quiet_high_ic:.4f}")
    print(f"Quiet in low breadth IC: {quiet_low_ic:.4f}")
    print(f"Lift (high - low): {quiet_high_vs_low:.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()