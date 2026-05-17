"""
H526 - Exit Timing Discovery

Hypothesis: All research focuses on entry states. Test if holding-duration
(time-since-entry into active state) or exit conditions (C24 trigger, momentum
decay) matter for realized returns. This is the unexplored half of the trade.

Approach:
1. Compute "days since entering active state" (C23 = vol_expansion)
2. Compare IC for fresh entries vs sustained positions
3. Test exit triggers: entering C24, exiting C23
4. Compare different holding periods

Pass criteria:
- Fresh entry (day 1-2 in C23) vs sustained (day 3+) shows meaningful IC difference
- Exit triggers show predictive power
- Best duration bucket beats uniform holding

Reference: live_state.md queue item 8
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


BRANCH_NAME = "exit_timing_discovery"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Test if holding-duration (time-since-entry into active state C23) "
        "or exit conditions (C24 trigger) predict different realized returns. "
        "Entry states are well-tested; exit/timing is the unexplored half."
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
        description="H526 Exit Timing Discovery: test holding duration effects"
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

    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)

    panel["prev_c23"] = panel.groupby("ticker")["c23_active"].shift(1).fillna(False).astype(bool)
    panel["days_in_c23"] = panel.groupby("ticker")["c23_active"].cumsum()
    panel.loc[~panel["c23_active"], "days_in_c23"] = 0

    fresh_entry = (panel["c23_active"]) & (~panel["prev_c23"])
    panel["fresh_entry"] = fresh_entry.astype(bool)

    sustained = panel["c23_active"] & panel["prev_c23"]
    panel["sustained_c23"] = sustained.astype(bool)

    panel["first_c23_exit"] = ((~panel["c23_active"]) & (panel["prev_c23"])).astype(bool)

    c24_path = ROOT / "data" / "features" / "xs_order_pressure_daily.parquet"
    c24_df = pd.read_parquet(c24_path)
    if "ceiling_2_of_3" in c24_df.columns:
        panel = panel.merge(
            c24_df[["time", "ticker", "ceiling_2_of_3"]],
            on=["time", "ticker"],
            how="left",
        )
        panel["c24_entry"] = (panel["ceiling_2_of_3"] == True) & (
            panel.groupby("ticker")["ceiling_2_of_3"].shift(1).fillna(False) == False
        )
    else:
        panel["c24_entry"] = False

    panel["day1_only"] = panel["days_in_c23"] == 1
    panel["day2_3"] = (panel["days_in_c23"] >= 2) & (panel["days_in_c23"] <= 3)
    panel["day4_plus"] = panel["days_in_c23"] >= 4

    panel["c24_entry"] = panel["c24_entry"].fillna(False).astype(bool)

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
            "fresh_entry",
            "First day in C23 (vol_expansion) - day 1 entry",
            family="timing",
            baseline="all_rows",
        ),
        StateSpec(
            "sustained_c23",
            "Day 2+ in C23 (sustained active state)",
            family="timing",
            baseline="all_rows",
        ),
        StateSpec(
            "first_c23_exit",
            "First day exiting C23 (exiting active state)",
            family="timing",
            baseline="all_rows",
        ),
        StateSpec(
            "c24_entry",
            "Entering C24 (ceiling trigger) - exit signal",
            family="timing",
            baseline="all_rows",
        ),
        StateSpec(
            "day1_only",
            "Exactly day 1 in C23",
            family="duration",
            baseline="all_rows",
        ),
        StateSpec(
            "day2_3",
            "Day 2-3 in C23",
            family="duration",
            baseline="all_rows",
        ),
        StateSpec(
            "day4_plus",
            "Day 4+ in C23",
            family="duration",
            baseline="all_rows",
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

    baseline_ic = results[results["name"] == "all_rows"]["avg_ic"].values[0]

    fresh_entry_ic = results[results["name"] == "fresh_entry"]["avg_ic"].values[0]
    sustained_ic = results[results["name"] == "sustained_c23"]["avg_ic"].values[0]
    fresh_vs_sustained = fresh_entry_ic - sustained_ic

    day1_ic = results[results["name"] == "day1_only"]["avg_ic"].values[0]
    day2_3_ic = results[results["name"] == "day2_3"]["avg_ic"].values[0]
    day4_plus_ic = results[results["name"] == "day4_plus"]["avg_ic"].values[0]

    best_duration = max(
        [("day1_only", day1_ic), ("day2_3", day2_3_ic), ("day4_plus", day4_plus_ic)],
        key=lambda x: x[1],
    )

    decision_map = {
        "PASSED": abs(fresh_vs_sustained) >= 0.010,
        "MIXED": abs(fresh_vs_sustained) >= 0.005,
        "FAILED": True,
    }

    decision = "FAILED"
    for k, v in decision_map.items():
        if v:
            decision = k
            break

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "fresh_entry_ic": float(fresh_entry_ic),
            "sustained_ic": float(sustained_ic),
            "fresh_vs_sustained_lift": float(fresh_vs_sustained),
            "day1_ic": float(day1_ic),
            "day2_3_ic": float(day2_3_ic),
            "day4_plus_ic": float(day4_plus_ic),
            "best_duration_bucket": best_duration[0],
            "best_duration_ic": float(best_duration[1]),
            "exit_timing_effect": abs(fresh_vs_sustained) >= 0.005,
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
    print(f"Fresh vs sustained lift: {fresh_vs_sustained:.4f}")
    print(f"Best duration bucket: {best_duration[0]} (IC={best_duration[1]:.4f})")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()