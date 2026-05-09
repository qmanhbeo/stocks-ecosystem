"""
BU2: c17_standalone

Hypothesis: C17 (raw order_volume_ratio without cross-sectional ranking) as standalone
signal may preserve more signal than the ranked C16 (like F414 illiq alone vs C23 combo).
The blending/normalization in C16 may strip away useful information.

Test: raw order_volume_ratio (not ranked) as state vs C16 ranked vs random baseline.
Data: order_stats raw buy/sell volume ratio.

Mechanism: raw ratio captures absolute flow intensity; ranking normalizes away
cross-sectional distribution information that may correlate with regime strength.
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


BRANCH_NAME = "c17_standalone"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "C17 (raw order_volume_ratio without ranking) as standalone signal vs "
        "C16 (ranked). Raw may preserve more signal than blend, like illiq alone "
        "worked better than the combo. Test raw vs ranked vs random baseline."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BU2 c17_standalone test")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--order-stats-path", type=str,
                        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")))
    parser.add_argument("--c16-path", type=str,
                        default=str(data_path("features/xs_order_pressure_daily.parquet")))
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

    order_stats["total_volume"] = order_stats["buy_order_volume"] + order_stats["sell_order_volume"]
    order_stats["buy_volume"] = order_stats["buy_order_volume"]
    order_stats["sell_volume"] = order_stats["sell_order_volume"]
    order_stats["order_volume_ratio_raw"] = (order_stats["buy_volume"] - order_stats["sell_volume"]) / (
        order_stats["buy_volume"] + order_stats["sell_volume"] + 1
    )

    c16 = pd.read_parquet(args.c16_path)
    c16 = c16.rename(columns={"date": "time"})
    c16["time"] = pd.to_datetime(c16["time"])
    c16 = c16[c16["time"].dt.year <= 2025]
    c16 = c16[["time", "ticker", "order_volume_ratio", "order_volume_ratio_rank"]].rename(
        columns={"order_volume_ratio": "c16_raw", "order_volume_ratio_rank": "c16_rank"}
    )

    panel = panel.merge(
        order_stats[["time", "ticker", "total_volume", "order_volume_ratio_raw"]],
        on=["time", "ticker"],
        how="left",
    )
    panel = panel.merge(
        c16,
        on=["time", "ticker"],
        how="left",
    )

    panel["all_rows"] = True
    panel = panel.dropna(subset=["total_volume"])
    panel = panel[panel["total_volume"] > 0]

    panel = panel.dropna(subset=["order_volume_ratio_raw"])

    panel["c17_raw_high"] = False
    panel["c17_raw_low"] = False
    panel["c16_rank_high"] = False
    panel["c16_rank_low"] = False

    if "order_volume_ratio_raw" in panel.columns and panel["order_volume_ratio_raw"].notna().any():
        c17_rank = panel.groupby("time", sort=False)["order_volume_ratio_raw"].rank(method="average", pct=True)
        panel["c17_raw_high"] = c17_rank >= 0.80
        panel["c17_raw_low"] = c17_rank <= 0.20
        panel["c17_raw_mid"] = (c17_rank > 0.20) & (c17_rank < 0.80)

    if "c16_rank" in panel.columns and panel["c16_rank"].notna().any():
        panel["c16_rank_high"] = panel["c16_rank"] >= 0.80
        panel["c16_rank_low"] = panel["c16_rank"] <= 0.20
        panel["c16_rank_mid"] = (panel["c16_rank"] > 0.20) & (panel["c16_rank"] < 0.80)

    panel["c17_raw_top20"] = panel["c17_raw_high"]
    panel["c16_rank_top20"] = panel["c16_rank_high"]
    panel["c17_c16_combo"] = panel["c17_raw_high"] & panel["c16_rank_high"]
    panel["c17_only"] = panel["c17_raw_high"] & ~panel["c16_rank_high"]
    panel["c16_only"] = panel["c16_rank_high"] & ~panel["c17_raw_high"]
    panel["c17_raw_bottom20"] = panel["c17_raw_low"]
    panel["c16_rank_bottom20"] = panel["c16_rank_low"]

    return panel


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

    STATE_SPECS = [
        StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
        StateSpec("c17_raw_top20", "C17 raw (not ranked) top 20%", family="c17_raw"),
        StateSpec("c16_rank_top20", "C16 ranked top 20% (existing)", family="c16_ranked"),
        StateSpec("c17_c16_combo", "Both C17 raw high AND C16 rank high", family="combo"),
        StateSpec("c17_only", "C17 raw high only (not in C16 rank)", family="c17_only"),
        StateSpec("c16_only", "C16 rank high only (not in C17 raw)", family="c16_only"),
        StateSpec("c17_raw_bottom20", "C17 raw bottom 20%", family="c17_raw_bottom"),
        StateSpec("c16_rank_bottom20", "C16 rank bottom 20%", family="c16_ranked_bottom"),
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
    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    c17_raw_ic = results[results["name"] == "c17_raw_top20"]["avg_ic"].values[0]
    c16_rank_ic = results[results["name"] == "c16_rank_top20"]["avg_ic"].values[0]

    lift_vs_baseline = best_row.get("avg_ic", 0) - baseline_ic if best_row else 0
    c17_vs_c16 = c17_raw_ic - c16_rank_ic

    if best_row.get("avg_ic", 0) > baseline_ic + 0.01 and best_row.get("positive_years", 0) >= 6:
        decision = "PASSED"
    elif c17_vs_c16 > 0.01 and best_row.get("positive_years", 0) >= 6:
        decision = "PASSED"
    elif best_row.get("avg_ic", 0) > baseline_ic and best_row.get("positive_years", 0) >= 5:
        decision = "MIXED"
    elif lift_vs_baseline < -0.01:
        decision = "FAILED"
    else:
        decision = "MIXED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
            "lift_vs_baseline": lift_vs_baseline,
            "c17_raw_ic": float(c17_raw_ic),
            "c16_rank_ic": float(c16_rank_ic),
            "c17_vs_c16": c17_vs_c16,
            "best_positive_years": best_row.get("positive_years"),
            "best_years": best_row.get("years"),
            "hypothesis": "C17 raw vs C16 ranked standalone",
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
    )

    print(f"\n=== BU2 c17_standalone ===")
    print(f"Decision: {decision}")
    print(f"Baseline IC: {baseline_ic:.4f}")
    print(f"C17 raw top20%: IC {c17_raw_ic:.4f} (vs baseline {c17_raw_ic - baseline_ic:+.4f})")
    print(f"C16 rank top20%: IC {c16_rank_ic:.4f} (vs baseline {c16_rank_ic - baseline_ic:+.4f})")
    print(f"C17 vs C16: {c17_vs_c16:+.4f}")
    print(f"Best state: {best_row.get('name')}")
    print(f"Best IC: {best_row.get('avg_ic'):.4f}")
    print(f"Positive years: {best_row.get('positive_years')}/{best_row.get('years')}")
    print(f"Summary: {summary_path}")

    return decision


if __name__ == "__main__":
    args = parse_args()
    decision = run_branch(args)
    sys.exit(0 if decision in ["PASSED", "MIXED"] else 1)