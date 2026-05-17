"""
H586: Blocked Duration Sweet Spot

H534 found duration_8pl (8+ days in active state) IC=0.1832 (+0.053 vs baseline).
Longer in active state = STRONGER, not decay. Persistent hidden demand.

H574 found blocked_either IC=0.1477 — C27 is positive.
Now test: is newly blocked vs persistently blocked different?

Pass criterion: persistently_blocked (8d+) beats newly_blocked (1d) by > +0.01 IC
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
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
    normalize_time_ticker,
    restrict_years,
)
from src.repo_paths import data_path


BRANCH_NAME = "blocked_duration_sweet_spot"
MODE = "research_branch"


def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="H586: Blocked Duration Sweet Spot")
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
    panel["has_volume"] = panel["has_volume"].fillna(True)
    panel["can_buy_next_open"] = panel["can_buy_next_open"].fillna(True)
    panel["can_sell_next_open"] = panel["can_sell_next_open"].fillna(True)

    panel["blocked_buy"] = ~panel["can_buy_next_open"]
    panel["blocked_sell"] = ~panel["can_sell_next_open"]
    panel["blocked_either"] = panel["blocked_buy"] | panel["blocked_sell"]

    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)
    blocked = panel["blocked_either"].values
    ticker_arr = panel["ticker"].values
    n = len(panel)
    consec = np.zeros(n, dtype=np.int32)
    cur_ticker = ticker_arr[0] if n > 0 else None
    cur_count = 0
    for i in range(n):
        if ticker_arr[i] != cur_ticker:
            cur_ticker = ticker_arr[i]
            cur_count = 0
        if blocked[i]:
            cur_count += 1
            consec[i] = cur_count
        else:
            cur_count = 0
    panel["consecutive_blocked"] = consec

    panel["duration_1d"] = panel["blocked_either"] & (panel["consecutive_blocked"] == 1)
    panel["duration_2_3d"] = panel["blocked_either"] & (panel["consecutive_blocked"].between(2, 3))
    panel["duration_4_7d"] = panel["blocked_either"] & (panel["consecutive_blocked"].between(4, 7))
    panel["duration_8pl"] = panel["blocked_either"] & (panel["consecutive_blocked"] >= 8)

    panel["all_rows"] = True

    print(f"Panel rows: {len(panel)}")
    print(f"blocked_either: {panel['blocked_either'].sum()}")
    vc = panel.loc[panel["blocked_either"], "consecutive_blocked"].value_counts().head(10)
    print(f"consecutive_blocked top: {vc.to_dict()}")
    print(f"duration_1d: {panel['duration_1d'].sum()}")
    print(f"duration_2_3d: {panel['duration_2_3d'].sum()}")
    print(f"duration_4_7d: {panel['duration_4_7d'].sum()}")
    print(f"duration_8pl: {panel['duration_8pl'].sum()}")

    return panel


def run_branch(args: argparse.Namespace) -> str:
    spec = ExperimentSpec(
        name=BRANCH_NAME,
        mode=MODE,
        hypothesis=(
            "Test if persistence of being blocked modulates C27 quality. "
            "H534 found longer in active = stronger. Test if same for blocked."
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
        StateSpec("blocked_either", "Blocked stocks (C27)", family="c27"),
        StateSpec("duration_1d", "Newly blocked (1d)", family="duration"),
        StateSpec("duration_2_3d", "Blocked 2-3d", family="duration"),
        StateSpec("duration_4_7d", "Blocked 4-7d", family="duration"),
        StateSpec("duration_8pl", "Persistently blocked (8d+)", family="duration"),
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

    print("\n=== H586: Blocked Duration Sweet Spot ===")
    print(results[["name", "avg_ic", "positive_years", "years", "pooled_rows"]].sort_values("avg_ic", ascending=False).to_string(index=False))

    baseline = results[results["name"] == "all_rows"]["avg_ic"].iloc[0] if "all_rows" in results["name"].values else np.nan
    blocked_c27 = results[results["name"] == "blocked_either"]["avg_ic"].iloc[0] if "blocked_either" in results["name"].values else np.nan
    dur_1d = results[results["name"] == "duration_1d"]["avg_ic"].iloc[0] if "duration_1d" in results["name"].values else np.nan
    dur_2_3 = results[results["name"] == "duration_2_3d"]["avg_ic"].iloc[0] if "duration_2_3d" in results["name"].values else np.nan
    dur_4_7 = results[results["name"] == "duration_4_7d"]["avg_ic"].iloc[0] if "duration_4_7d" in results["name"].values else np.nan
    dur_8pl = results[results["name"] == "duration_8pl"]["avg_ic"].iloc[0] if "duration_8pl" in results["name"].values else np.nan

    diff_8pl_1d = dur_8pl - dur_1d if not (np.isnan(dur_8pl) or np.isnan(dur_1d)) else np.nan

    print(f"\nBaseline IC: {baseline:.4f}")
    print(f"Raw C27: {blocked_c27:.4f}")
    print(f"Newly blocked (1d): {dur_1d}")
    print(f"Blocked 2-3d: {dur_2_3:.4f}" if not np.isnan(dur_2_3) else f"Blocked 2-3d: {dur_2_3}")
    print(f"Blocked 4-7d: {dur_4_7}")
    print(f"Persistently blocked (8d+): {dur_8pl}")
    if not np.isnan(diff_8pl_1d):
        print(f"8d+ vs 1d: {diff_8pl_1d:+.4f}")
    else:
        print("8d+ vs 1d: N/A")

    if not np.isnan(diff_8pl_1d):
        if diff_8pl_1d > 0.01:
            decision = "PASSED"
        elif diff_8pl_1d > 0.005:
            decision = "MIXED"
        elif diff_8pl_1d > 0:
            decision = "MIXED (marginal)"
        else:
            decision = "FAILED"
    elif panel["duration_8pl"].sum() < 100 or panel["duration_1d"].sum() < 100:
        decision = "FAILED (sparse)"
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
            "blocked_either_ic": blocked_c27,
            "duration_1d_ic": str(dur_1d),
            "duration_2_3d_ic": dur_2_3,
            "duration_4_7d_ic": str(dur_4_7),
            "duration_8pl_ic": str(dur_8pl),
            "diff_8pl_1d": diff_8pl_1d,
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": "blocked duration sweet spot",
        },
    )

    print(f"\nDecision: {decision}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()