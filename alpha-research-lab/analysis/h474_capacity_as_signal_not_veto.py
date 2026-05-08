"""
H474: capacity_as_signal_not_veto

Hypothesis: Tradability/capacity tightness (order count percentile) should be a signal
INPUT, not a binary veto. Stocks with very low order count (tight capacity) may signal
hidden demand that couldn't execute. The current binary release/veto approach failed
(H391), but a continuous capacity signal may capture different dynamics.

Connection to H391 (tradability_release_pulse) which failed with binary release_flag:
H391 tested BLOCKED->RELEASED state (binary). AN tests CONTINUOUS capacity percentile
(low/mid/high) as a ranker input — a fundamentally different signal mechanism.

Test: total_order_count (from CafeF order_stats) percentile buckets vs forward IC.
Compare with: random baseline and H391 failed-release controls.
Expected: Low capacity (tight, sparse orders) = hidden demand signal (positive).
"""

from __future__ import annotations

import argparse
from dataclasses import replace
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
)
from src.repo_paths import data_path


BRANCH_NAME = "capacity_as_signal_not_veto"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Tradability capacity (total order count percentile) should be a SIGNAL INPUT, not a "
        "binary veto. Low capacity (tight) = hidden demand; high capacity = liquid crowd. "
        "Test order-count percentile vs forward IC."
    ),
    start_year=2018,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H474 capacity_as_signal_not_veto test")
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

    os = pd.read_parquet(args.order_stats_path, engine="pyarrow")
    os = os.rename(columns={"date": "time"})
    os["time"] = pd.to_datetime(os["time"]).dt.normalize()
    os = os[os["time"].dt.year.between(spec.start_year, spec.end_year)]

    os["total_order_count"] = os["buy_order_count"].fillna(0) + os["sell_order_count"].fillna(0)
    os["total_volume"] = os["buy_order_volume"].fillna(0) + os["sell_order_volume"].fillna(0)
    os["avg_order_size"] = os["total_volume"] / (os["total_order_count"] + 1)

    panel = panel.merge(
        os[["time", "ticker", "total_order_count", "total_volume", "avg_order_size"]],
        on=["time", "ticker"],
        how="inner",
    )

    panel["all_rows"] = True
    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("tight_capacity", "Tight capacity (Q1: lowest order count)", family="capacity", primary=True),
    StateSpec("mid_capacity", "Mid capacity (Q3)", family="capacity"),
    StateSpec("loose_capacity", "Loose capacity (Q5: highest order count)", family="capacity"),
    StateSpec("tight_has_volume", "Tight capacity + positive volume", family="cap_vol"),
    StateSpec("tight_expansion", "Tight capacity + vol expansion", family="cap_vol"),
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

    print(f"Panel: {len(panel)} rows, order_count>0: {(panel['total_order_count'] > 0).sum()}")

    cap_rank = panel.groupby("time", sort=False)["total_order_count"].rank(method="average", pct=True)
    panel["tight_capacity"] = cap_rank <= 0.2
    panel["mid_capacity"] = (cap_rank > 0.3) & (cap_rank < 0.7)
    panel["loose_capacity"] = cap_rank >= 0.8

    panel["tight_has_volume"] = panel["tight_capacity"] & (panel["total_order_count"] > 0)

    panel["pct_change_vol"] = panel.groupby("ticker")["total_volume"].transform(
        lambda x: x.rolling(window=5, min_periods=3).std()
    )
    panel["vol_change"] = panel.groupby("ticker")["pct_change_vol"].transform(
        lambda x: x.diff()
    )
    panel = panel.dropna(subset=["vol_change"])
    vol_change_rank = panel.groupby("time", sort=False)["vol_change"].rank(method="average", pct=True)
    panel["vol_expansion"] = vol_change_rank >= 0.8
    panel["tight_expansion"] = panel["tight_capacity"] & panel["vol_expansion"]

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

    baseline_row = results[results["name"] == "all_rows"]
    baseline_ic = float(baseline_row["avg_ic"].iloc[0]) if not baseline_row.empty else 0.0

    def get_ic(name):
        row = results[results["name"] == name]
        return float(row["avg_ic"].iloc[0]) if name in results["name"].values else None

    def get_lift(name):
        ic = get_ic(name)
        return (ic - baseline_ic) if ic is not None else None

    tight_ic = get_ic("tight_capacity")
    mid_ic = get_ic("mid_capacity")
    loose_ic = get_ic("loose_capacity")
    tight_vol_ic = get_ic("tight_has_volume")
    tight_exp_ic = get_ic("tight_expansion")

    tight_lift = get_lift("tight_capacity")
    tight_exp_lift = get_lift("tight_expansion")

    h391_ref = -0.033668

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    if tight_lift is not None and tight_lift > 0.005:
        decision = "PASSED"
    elif tight_lift is not None and tight_lift > 0:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "tight_capacity_ic": tight_ic,
            "mid_capacity_ic": mid_ic,
            "loose_capacity_ic": loose_ic,
            "tight_capacity_lift": tight_lift,
            "tight_has_volume_ic": tight_vol_ic,
            "tight_expansion_ic": tight_exp_ic,
            "tight_expansion_lift": tight_exp_lift,
            "h391_failed_ref_lift": h391_ref,
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
            "best_positive_years": best_row.get("positive_years"),
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

    print(results.sort_values("avg_ic", ascending=False, na_position="last")[["name","avg_ic","positive_years","years"]].to_string(index=False))
    print(f"\nDecision: {decision}")
    print(f"Baseline IC: {baseline_ic:.4f}")
    print(f"\nCapacity alone:")
    print(f"  tight_capacity (Q1): {tight_ic:.4f} (lift: {tight_lift:+.4f})")
    print(f"  mid_capacity (Q3): {mid_ic:.4f}")
    print(f"  loose_capacity (Q5): {loose_ic:.4f}")
    print(f"\nCapacity × Vol regime:")
    print(f"  tight_expansion: {tight_exp_ic:.4f} (lift: {tight_exp_lift:+.4f})")
    print(f"  tight_has_volume: {tight_vol_ic:.4f}")
    print(f"\nH391 failed release ref lift: {h391_ref:.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()