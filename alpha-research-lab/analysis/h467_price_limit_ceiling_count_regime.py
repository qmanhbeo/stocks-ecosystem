"""
H467: price_limit_ceiling_count_regime

Hypothesis: H454 showed approaching_ceiling (5-7% change) is a strong signal.
But what about multi-day CEILING PRESSURE? Stocks that hit the limit multiple
times in recent days might have different behavior. Also, stocks that are
far below the limit might have different behavior.

Test:
- ceiling_count_3d: how many times in last 3 days the stock hit +7% limit
- far_from_ceiling: far below the limit (e.g., < 2% change)
- ceiling_exhaustion: near limit but yesterday was also near limit (building pressure)

First test: ceiling_count × vol_expansion vs random baseline.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import sys
from pathlib import Path

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


BRANCH_NAME = "price_limit_ceiling_count_regime"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "H454 showed approaching_ceiling (+5-7%) is strong. Test multi-day ceiling pressure: "
        "how many times in last 3d stock hit +7% limit, far-from-ceiling, and ceiling exhaustion."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H467 price_limit_ceiling_count_regime")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--order-stats-path", type=str,
                        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")))
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

    order_stats = pd.read_parquet(args.order_stats_path)
    order_stats = order_stats.rename(columns={"date": "time"})
    order_stats["time"] = pd.to_datetime(order_stats["time"])
    order_stats = order_stats[order_stats["time"].dt.year <= 2025]

    import re
    def parse_price_change(s):
        if pd.isna(s):
            return np.nan
        try:
            match = re.search(r'\(\s*([+-]?[\d,]+)\s*%\)', str(s))
            if match:
                return float(match.group(1).replace(',', '.'))
            return np.nan
        except:
            return np.nan

    order_stats["pct_change"] = order_stats["price_change_raw"].apply(parse_price_change)

    panel = panel.merge(
        order_stats[["time", "ticker", "pct_change"]],
        on=["time", "ticker"],
        how="left",
    )

    panel = panel.sort_values(["ticker", "time"])

    panel["at_limit"] = (panel["pct_change"] >= 6.5).astype(bool)
    panel["near_limit"] = ((panel["pct_change"] >= 5.0) & (panel["pct_change"] < 7.0)).astype(bool)
    panel["far_from_ceiling"] = (panel["pct_change"] < 2.0).astype(bool)
    panel["mid_range"] = ~panel["at_limit"] & ~panel["far_from_ceiling"]

    for w in [3, 5]:
        panel[f"limit_count_{w}d"] = panel.groupby("ticker")["at_limit"].transform(
            lambda x: x.rolling(window=w, min_periods=2).sum()
        )

    panel["near_limit_yesterday"] = panel.groupby("ticker")["near_limit"].shift(1).fillna(False).astype(bool)
    panel["ceiling_exhaustion"] = (panel["near_limit"] & panel["near_limit_yesterday"]).astype(bool)

    panel["limit_1_of_3"] = (panel["limit_count_3d"] == 1).astype(bool)
    panel["limit_2_of_3"] = (panel["limit_count_3d"] >= 2).astype(bool)

    pct_change_vol = panel.groupby("ticker")["pct_change"].transform(
        lambda x: x.rolling(window=5, min_periods=3).std()
    )
    vol_change = pct_change_vol.diff()
    panel["vol_change"] = vol_change
    panel = panel.dropna(subset=["vol_change"])

    vol_rank = panel.groupby("time", sort=False)["vol_change"].rank(method="average", pct=True)
    panel["vol_expansion"] = (vol_rank >= 0.8).astype(bool)

    panel["all_rows"] = True

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("at_limit", "At limit (+6.5%+ change)", family="limit"),
    StateSpec("near_limit", "H454: approaching_ceiling (+5-7%)", family="limit", primary=True),
    StateSpec("far_from_ceiling", "Far from ceiling (<2% change)", family="limit"),
    StateSpec("limit_1_of_3", "Hit limit 1x in last 3 days", family="limit_count"),
    StateSpec("limit_2_of_3", "Hit limit 2+ times in last 3 days", family="limit_count"),
    StateSpec("ceiling_exhaustion", "Near limit TODAY AND yesterday", family="limit"),
    StateSpec("near_limit_expansion", "Near limit × Vol expansion", family="combo", primary=True),
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

    panel["near_limit_expansion"] = (panel["near_limit"] & panel["vol_expansion"]).astype(bool)

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

    baseline_ic = results[results["name"] == "all_rows"]["avg_ic"].iloc[0] if not results.empty else 0

    near_limit_ic = results[results["name"] == "near_limit"]["avg_ic"].iloc[0] if not results.empty else 0
    near_limit_exp_ic = results[results["name"] == "near_limit_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    at_limit_ic = results[results["name"] == "at_limit"]["avg_ic"].iloc[0] if not results.empty else 0
    far_ic = results[results["name"] == "far_from_ceiling"]["avg_ic"].iloc[0] if not results.empty else 0
    limit_1_ic = results[results["name"] == "limit_1_of_3"]["avg_ic"].iloc[0] if not results.empty else 0
    limit_2_ic = results[results["name"] == "limit_2_of_3"]["avg_ic"].iloc[0] if not results.empty else 0
    exhaust_ic = results[results["name"] == "ceiling_exhaustion"]["avg_ic"].iloc[0] if not results.empty else 0

    best = results[results["name"] != "all_rows"].sort_values("avg_ic", ascending=False).iloc[0] if not results.empty else {}
    best_name = best.get("name", "none")
    best_ic = best.get("avg_ic", 0)
    best_lift = best_ic - baseline_ic

    decision = "FAILED"
    if best_lift > 0.010:
        decision = "PASSED"
    elif best_lift > 0.003:
        decision = "MIXED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "near_limit_ic": float(near_limit_ic),
            "near_limit_expansion_ic": float(near_limit_exp_ic),
            "at_limit_ic": float(at_limit_ic),
            "far_from_ceiling_ic": float(far_ic),
            "limit_1_of_3_ic": float(limit_1_ic),
            "limit_2_of_3_ic": float(limit_2_ic),
            "ceiling_exhaustion_ic": float(exhaust_ic),
            "best_state": best_name,
            "best_lift": float(best_lift),
        },
        artifacts={"results": results_path, "yearly": yearly_path},
        metadata={"state_specs": [state.as_metadata() for state in STATE_SPECS], "hypothesis": SPEC.hypothesis},
    )

    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(f"\nDecision: {decision}")
    print(f"Baseline IC: {baseline_ic:.4f}")
    print(f"  near_limit (C22 baseline): {near_limit_ic:.4f}")
    print(f"  near_limit_expansion: {near_limit_exp_ic:.4f} (lift: {near_limit_exp_ic - baseline_ic:+.4f})")
    print(f"  at_limit (+6.5%+): {at_limit_ic:.4f}")
    print(f"  far_from_ceiling (<2%): {far_ic:.4f}")
    print(f"  limit_1_of_3: {limit_1_ic:.4f}")
    print(f"  limit_2_of_3: {limit_2_ic:.4f}")
    print(f"  ceiling_exhaustion: {exhaust_ic:.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()