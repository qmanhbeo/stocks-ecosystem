"""
H594: Blocked-State Transition Timing

Hypothesis: C27 (blocked) is positive (F438) but transient (D079).
First-day blocked might be the purest "pain" signal before market adapts.
Mechanism: initial blockage = fresh hidden demand, prolonged blockage = market already priced in.

Test: blocked_day_1 vs blocked_day_2_3d vs blocked_day_4pl on raw S1 panel.

Pass criterion: best duration state beats blocked_either (0.1477) by > +0.01 IC
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


BRANCH_NAME = "blocked_transition_timing"
MODE = "research_branch"


def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="H594: Blocked-State Transition Timing")
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
        trad_df[["time", "ticker", "can_buy_next_open", "can_sell_next_open"]],
        on=["time", "ticker"],
        how="left"
    )

    panel["blocked_either"] = ~(panel["can_buy_next_open"].fillna(True)) | ~(panel["can_sell_next_open"].fillna(True))

    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)

    panel["was_blocked"] = panel.groupby("ticker")["blocked_either"].shift(1).fillna(False)
    panel["blocked_today"] = panel["blocked_either"]

    panel["episode_id"] = (~panel["blocked_either"]).cumsum()
    panel["blocked_duration"] = panel.groupby(["ticker", "episode_id"]).cumcount() + 1
    panel["blocked_duration"] = panel["blocked_duration"].where(panel["blocked_either"], 0)

    panel["blocked_day_1"] = (panel["blocked_either"] & ~panel["was_blocked"])
    panel["blocked_day_2_3"] = (panel["blocked_either"] & panel["was_blocked"] & (panel["blocked_duration"].isin([2, 3])))
    panel["blocked_day_4pl"] = (panel["blocked_either"] & panel["was_blocked"] & (panel["blocked_duration"] >= 4))

    print(f"Panel rows: {len(panel)}")
    print(f"Blocked either: {panel['blocked_either'].sum()}")
    print(f"blocked_day_1: {panel['blocked_day_1'].sum()}")
    print(f"blocked_day_2_3: {panel['blocked_day_2_3'].sum()}")
    print(f"blocked_day_4pl: {panel['blocked_day_4pl'].sum()}")

    return panel


def run_branch(args: argparse.Namespace) -> str:
    spec = ExperimentSpec(
        name=BRANCH_NAME,
        mode=MODE,
        hypothesis=(
            "C27 (blocked) is positive but transient. First-day blocked may be purest "
            "'pain' signal - initial blockage = fresh hidden demand, prolonged = priced in. "
            "Test blocked_day_1 vs blocked_day_2_3d vs blocked_day_4pl."
        ),
        start_year=2015,
        end_year=2025,
        min_year_rows=100,
        min_phase_rows=100,
        target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
        score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
    )
    context = build_experiment_context(spec, artifact_subdir="research_branch")

    panel = load_panel(args, spec)

    STATE_SPECS = [
        StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
        StateSpec("blocked_either", "Blocked (any duration)", family="blocked"),
        StateSpec("blocked_day_1", "First day blocked", family="blocked_duration"),
        StateSpec("blocked_day_2_3", "2-3 days blocked", family="blocked_duration"),
        StateSpec("blocked_day_4pl", "4+ days blocked", family="blocked_duration"),
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

    print("=== H594: Blocked-State Transition Timing ===")
    print(results[["name", "avg_ic", "positive_years", "years", "pooled_rows"]].sort_values("avg_ic", ascending=False).to_string(index=False))

    baseline = results[results["name"] == "all_rows"]["avg_ic"].iloc[0] if "all_rows" in results["name"].values else results["avg_ic"].mean()
    blocked_either = results[results["name"] == "blocked_either"]["avg_ic"].iloc[0] if "blocked_either" in results["name"].values else 0.0
    blocked_day_1 = results[results["name"] == "blocked_day_1"]["avg_ic"].iloc[0] if "blocked_day_1" in results["name"].values else 0.0
    blocked_day_2_3 = results[results["name"] == "blocked_day_2_3"]["avg_ic"].iloc[0] if "blocked_day_2_3" in results["name"].values else 0.0
    blocked_day_4pl = results[results["name"] == "blocked_day_4pl"]["avg_ic"].iloc[0] if "blocked_day_4pl" in results["name"].values else 0.0

    best_duration = max(
        blocked_day_1 if pd.notna(blocked_day_1) else 0,
        blocked_day_2_3 if pd.notna(blocked_day_2_3) else 0,
        blocked_day_4pl if pd.notna(blocked_day_4pl) else 0
    )
    best_duration_vs_blocked = best_duration - blocked_either if pd.notna(blocked_either) else 0

    if best_duration_vs_blocked > 0.01:
        decision = "PASSED"
    elif best_duration_vs_blocked > 0.005:
        decision = "MIXED"
    elif best_duration_vs_blocked > 0:
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
            "blocked_either_ic": blocked_either,
            "blocked_day_1_ic": blocked_day_1,
            "blocked_day_2_3_ic": blocked_day_2_3,
            "blocked_day_4pl_ic": blocked_day_4pl,
            "best_duration_vs_blocked": best_duration_vs_blocked,
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": "blocked-state transition timing",
        },
    )

    print(f"\nBaseline IC: {baseline:.4f}")
    print(f"Blocked Either IC: {blocked_either:.4f}")
    print(f"blocked_day_1 IC: {blocked_day_1:.4f}")
    print(f"blocked_day_2_3 IC: {blocked_day_2_3:.4f}")
    print(f"blocked_day_4pl IC: {blocked_day_4pl:.4f}")
    print(f"Best duration vs blocked_either: {best_duration_vs_blocked:.4f}")
    print(f"\nDecision: {decision}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()