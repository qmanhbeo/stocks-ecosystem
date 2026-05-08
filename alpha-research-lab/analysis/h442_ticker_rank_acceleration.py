"""
H442: ticker_rank_acceleration

Hypothesis: Rank acceleration (second derivative of rank) is the edge. Different from
H407 (phase lag cross-product) and H412 (additive levels) and H431 (rank delta first derivative).
H431 passed with C16 rank delta (+0.0114 IC lift). Now test the SECOND derivative of rank.

Mechanism: C16 rank is computed daily. Rank delta = C16_rank(t) - C16_rank(t-1).
Rank acceleration = rank_delta(t) - rank_delta(t-1). Buckets: accelerating, stable, decelerating.
Test whether rank acceleration predicts forward IC differently from rank level or rank delta.

Test: Compute C16 rank from order_volume_ratio, compute 1d and 5d rank delta, then compute
rank acceleration (delta of delta). Buckets. Compare against rank level, rank delta (H431),
and random baselines.
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


BRANCH_NAME = "h442_ticker_rank_acceleration"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Rank acceleration (second derivative of rank) is the edge. Different from H407 "
        "(phase lag cross-product) and H412 (additive levels) and H431 (rank delta first derivative). "
        "H431 passed with C16 rank delta (+0.0114 IC lift). Now test the SECOND derivative: "
        "rank acceleration = delta of delta. Buckets: accelerating, stable, decelerating. "
        "Test whether rank acceleration predicts forward IC differently from rank level or rank delta."
    ),
    start_year=2018,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)

STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("c16_rank_high", "High C16 rank (Q5)", family="rank_level"),
    StateSpec("c16_rank_low", "Low C16 rank (Q1)", family="rank_level"),
    StateSpec("rank_delta_pos", "Rank delta positive (rank increasing)", family="rank_delta"),
    StateSpec("rank_delta_neg", "Rank delta negative (rank decreasing)", family="rank_delta"),
    StateSpec("rank_accel_up", "Rank acceleration positive (delta of delta > 0.05)", family="rank_accel"),
    StateSpec("rank_accel_down", "Rank acceleration negative (delta of delta < -0.05)", family="rank_accel"),
    StateSpec("rank_accel_up_strong_flow", "Rank accel up + strong C16 flow", family="combined"),
    StateSpec("rank_accel_down_strong_flow", "Rank accel down + strong C16 flow", family="combined"),
    StateSpec("rank_delta_pos_strong_flow", "Rank delta positive + strong C16 flow (H431 combo)", family="h431_combo"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H442 ticker_rank_acceleration")
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
    panel["all_rows"] = True

    vol_path = ROOT / "data" / "features" / "xs_order_pressure_daily.parquet"
    vol = pd.read_parquet(vol_path, columns=["time", "ticker", "order_volume_ratio"])
    vol["time"] = pd.to_datetime(vol["time"], errors="coerce").dt.normalize()
    vol["ticker"] = vol["ticker"].astype(str).str.upper()
    vol = vol.dropna(subset=["time", "ticker"])
    vol = vol[vol["time"].dt.year <= 2025]
    vol = vol[vol["time"] >= pd.Timestamp("2018-01-01")]
    panel = panel.merge(vol[["time", "ticker", "order_volume_ratio"]], on=["time", "ticker"], how="left")
    panel["c16"] = panel["order_volume_ratio"].fillna(panel["order_volume_ratio"].median())
    panel = panel.dropna(subset=["c16"])

    panel = panel.sort_values(["ticker", "time"])

    panel["c16_rank"] = panel.groupby("time")["c16"].rank(pct=True)

    panel["c16_rank_delta"] = panel.groupby("ticker")["c16_rank"].diff()
    panel["c16_rank_delta"] = panel["c16_rank_delta"].fillna(0)

    panel["c16_rank_accel"] = panel.groupby("ticker")["c16_rank_delta"].diff()
    panel["c16_rank_accel"] = panel["c16_rank_accel"].fillna(0)

    q5_rank = panel["c16_rank"].groupby(panel["time"]).quantile(0.80)
    panel["c16_rank_high"] = panel["c16_rank"] > panel["time"].map(q5_rank)
    q1_rank = panel["c16_rank"].groupby(panel["time"]).quantile(0.20)
    panel["c16_rank_low"] = panel["c16_rank"] < panel["time"].map(q1_rank)

    panel["rank_delta_pos"] = panel["c16_rank_delta"] > 0.05
    panel["rank_delta_neg"] = panel["c16_rank_delta"] < -0.05

    panel["rank_accel_up"] = panel["c16_rank_accel"] > 0.05
    panel["rank_accel_down"] = panel["c16_rank_accel"] < -0.05

    panel["strong_flow"] = panel["c16"] > panel.groupby("time")["c16"].transform(
        lambda x: x.quantile(0.75)
    )

    panel["rank_accel_up_strong_flow"] = panel["rank_accel_up"] & panel["strong_flow"]
    panel["rank_accel_down_strong_flow"] = panel["rank_accel_down"] & panel["strong_flow"]
    panel["rank_delta_pos_strong_flow"] = panel["rank_delta_pos"] & panel["strong_flow"]

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
    panel_path = write_dataframe_artifact(panel, context, f"{BRANCH_NAME}_panel")

    all_rows_ic = results[results["name"] == "all_rows"]["avg_ic"].values
    all_rows_ic_val = float(all_rows_ic[0]) if len(all_rows_ic) > 0 else None

    accel_up_ic = results[results["name"] == "rank_accel_up"]["avg_ic"].values
    accel_up_val = float(accel_up_ic[0]) if len(accel_up_ic) > 0 else None
    accel_up_rows = int(results[results["name"] == "rank_accel_up"]["pooled_rows"].values[0]) if len(accel_up_ic) > 0 else 0
    accel_up_pos = int(results[results["name"] == "rank_accel_up"]["positive_years"].values[0]) if len(accel_up_ic) > 0 else 0
    accel_up_total = int(results[results["name"] == "rank_accel_up"]["years"].values[0]) if len(accel_up_ic) > 0 else 0

    accel_down_ic = results[results["name"] == "rank_accel_down"]["avg_ic"].values
    accel_down_val = float(accel_down_ic[0]) if len(accel_down_ic) > 0 else None
    accel_down_rows = int(results[results["name"] == "rank_accel_down"]["pooled_rows"].values[0]) if len(accel_down_ic) > 0 else 0

    accel_up_flow_ic = results[results["name"] == "rank_accel_up_strong_flow"]["avg_ic"].values
    accel_up_flow_val = float(accel_up_flow_ic[0]) if len(accel_up_flow_ic) > 0 else None
    accel_down_flow_ic = results[results["name"] == "rank_accel_down_strong_flow"]["avg_ic"].values
    accel_down_flow_val = float(accel_down_flow_ic[0]) if len(accel_down_flow_ic) > 0 else None

    delta_pos_ic = results[results["name"] == "rank_delta_pos"]["avg_ic"].values
    delta_pos_val = float(delta_pos_ic[0]) if len(delta_pos_ic) > 0 else None
    delta_pos_flow_ic = results[results["name"] == "rank_delta_pos_strong_flow"]["avg_ic"].values
    delta_pos_flow_val = float(delta_pos_flow_ic[0]) if len(delta_pos_flow_ic) > 0 else None

    rank_high_ic = results[results["name"] == "c16_rank_high"]["avg_ic"].values
    rank_high_val = float(rank_high_ic[0]) if len(rank_high_ic) > 0 else None

    accel_lift = (accel_up_val - accel_down_val) if accel_up_val is not None and accel_down_val is not None else None
    accel_vs_delta = (accel_up_val - delta_pos_val) if accel_up_val is not None and delta_pos_val is not None else None

    if accel_lift is not None and accel_lift > 0.01 and accel_up_pos >= accel_up_total * 0.6:
        decision = "PASSED"
    elif accel_lift is not None and accel_lift > 0.005 and accel_up_pos >= accel_up_total * 0.5:
        decision = "MIXED"
    elif accel_lift is not None and accel_lift > 0.002:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "all_rows_avg_ic": all_rows_ic_val,
            "rank_accel_up_avg_ic": accel_up_val,
            "rank_accel_up_rows": accel_up_rows,
            "rank_accel_up_pos_years": f"{accel_up_pos}/{accel_up_total}",
            "rank_accel_down_avg_ic": accel_down_val,
            "rank_accel_down_rows": accel_down_rows,
            "accel_up_vs_down_lift": accel_lift,
            "accel_up_vs_delta_pos_lift": accel_vs_delta,
            "rank_accel_up_strong_flow_avg_ic": accel_up_flow_val,
            "rank_accel_down_strong_flow_avg_ic": accel_down_flow_val,
            "rank_delta_pos_avg_ic": delta_pos_val,
            "rank_delta_pos_strong_flow_avg_ic": delta_pos_flow_val,
            "c16_rank_high_avg_ic": rank_high_val,
            "best_state": results.sort_values("avg_ic", ascending=False, na_position="last").iloc[0]["name"],
            "best_avg_ic": results.sort_values("avg_ic", ascending=False, na_position="last").iloc[0]["avg_ic"],
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
            "panel": panel_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": SPEC.hypothesis,
        },
    )

    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(f"\nRank Accel Up IC: {accel_up_val} ({accel_up_pos}/{accel_up_total} pos years, {accel_up_rows} rows)")
    print(f"Rank Accel Down IC: {accel_down_val} ({accel_down_rows} rows)")
    print(f"Accel Up vs Down lift: {accel_lift}")
    print(f"Accel Up vs Delta Pos lift: {accel_vs_delta}")
    print(f"Accel Up+Flow: {accel_up_flow_val}, Accel Down+Flow: {accel_down_flow_val}")
    print(f"Delta Pos IC: {delta_pos_val}, Delta Pos+Flow: {delta_pos_flow_val}")
    print(f"C16 Rank High: {rank_high_val}")
    print(f"Decision: {decision}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()