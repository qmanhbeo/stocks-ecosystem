"""
H465: cross_signal_orthogonality_audit

Hypothesis: The strongest signals (C21, C22, C23, C20) may overlap/redundantly predict.
Test orthogonality: does C21+C22 combo add incremental IC beyond each alone?
Also test C21×C23, C22×C23, and all-three combos.

Signals to test:
- C20: buy_heavy_expansion (IC=0.2105)
- C21: buy_heavy_accel_expansion (IC=0.2320), sell_heavy_decel_expansion (IC=0.2369)
- C22: approaching_ceiling (IC=0.2170)
- C23: high_illiq_expansion (IC=0.2616)

First test: pair-wise combos vs individual baselines.
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


BRANCH_NAME = "cross_signal_orthogonality_audit"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Test orthogonality of top signals (C20/C21/C22/C23). "
        "Does combo add incremental IC beyond each alone?"
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H465 cross_signal_orthogonality_audit")
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
    order_stats["total_volume"] = order_stats["buy_order_volume"] + order_stats["sell_order_volume"]

    panel = panel.merge(
        order_stats[["time", "ticker", "pct_change", "total_volume",
                     "buy_order_volume", "sell_order_volume"]],
        on=["time", "ticker"],
        how="left",
    )

    panel["all_rows"] = True

    panel = panel.dropna(subset=["pct_change", "total_volume"])
    panel = panel[panel["total_volume"] > 0]

    panel = panel.sort_values(["ticker", "time"])

    panel["buy_sell_volume_imbalance"] = (
        (panel["buy_order_volume"] - panel["sell_order_volume"]) /
        (panel["buy_order_volume"] + panel["sell_order_volume"] + 1)
    )

    panel["imbalance_rank"] = panel.groupby("time", sort=False)["buy_sell_volume_imbalance"].rank(method="average", pct=True)

    imbalance_delta = panel.groupby("ticker")["imbalance_rank"].diff()
    panel["imbalance_delta"] = imbalance_delta
    panel["imbalance_delta_rank"] = panel.groupby("time", sort=False)["imbalance_delta"].rank(method="average", pct=True)

    panel["pct_change_vol"] = panel.groupby("ticker")["pct_change"].transform(
        lambda x: x.rolling(window=5, min_periods=3).std()
    )
    panel["vol_change"] = panel.groupby("ticker")["pct_change_vol"].transform(lambda x: x.diff())
    panel = panel.dropna(subset=["vol_change"])

    vol_change_rank = panel.groupby("time", sort=False)["vol_change"].rank(method="average", pct=True)
    panel["vol_expansion"] = (vol_change_rank >= 0.8).astype(bool)
    panel["buy_heavy"] = (panel["imbalance_rank"] >= 0.8).astype(bool)
    panel["sell_heavy"] = (panel["imbalance_rank"] <= 0.2).astype(bool)
    panel["buy_heavy_accel"] = ((panel["imbalance_rank"] >= 0.8) & (panel["imbalance_delta_rank"] >= 0.8)).astype(bool)
    panel["sell_heavy_decel"] = ((panel["imbalance_rank"] <= 0.2) & (panel["imbalance_delta_rank"] <= 0.2)).astype(bool)

    panel["buy_heavy_expansion"] = (panel["buy_heavy"] & panel["vol_expansion"]).astype(bool)
    panel["buy_heavy_accel_expansion"] = (panel["buy_heavy_accel"] & panel["vol_expansion"]).astype(bool)
    panel["sell_heavy_decel_expansion"] = (panel["sell_heavy_decel"] & panel["vol_expansion"]).astype(bool)

    panel["approaching_ceiling"] = ((panel["pct_change"] >= 5.0) & (panel["pct_change"] < 7.0)).astype(bool)

    panel = panel.dropna(subset=["buy_sell_volume_imbalance"])

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("buy_heavy_expansion", "C20: buy_heavy_expansion", family="individual", primary=True),
    StateSpec("buy_heavy_accel_expansion", "C21a: buy_heavy_accel_expansion", family="individual", primary=True),
    StateSpec("sell_heavy_decel_expansion", "C21b: sell_heavy_decel_expansion", family="individual", primary=True),
    StateSpec("approaching_ceiling", "C22: approaching_ceiling", family="individual", primary=True),
    StateSpec("c21a_c22", "C21a × C22 combo", family="combo"),
    StateSpec("c21b_c22", "C21b × C22 combo", family="combo"),
    StateSpec("c20_c22", "C20 × C22 combo", family="combo"),
    StateSpec("c21a_c21b", "C21a × C21b combo", family="combo"),
    StateSpec("c21a_c22_c20", "C21a × C22 × C20 combo", family="combo"),
    StateSpec("c21b_c22_c20", "C21b × C22 × C20 combo", family="combo"),
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
    panel["c21a_c22"] = panel["buy_heavy_accel_expansion"] & panel["approaching_ceiling"]
    panel["c21b_c22"] = panel["sell_heavy_decel_expansion"] & panel["approaching_ceiling"]
    panel["c20_c22"] = panel["buy_heavy_expansion"] & panel["approaching_ceiling"]
    panel["c21a_c21b"] = panel["buy_heavy_accel_expansion"] & panel["sell_heavy_decel_expansion"]
    panel["c21a_c22_c20"] = panel["buy_heavy_accel_expansion"] & panel["approaching_ceiling"] & panel["buy_heavy_expansion"]
    panel["c21b_c22_c20"] = panel["sell_heavy_decel_expansion"] & panel["approaching_ceiling"] & panel["buy_heavy_expansion"]

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

    baseline_ic = results[results["name"] == "all_rows"]["avg_ic"].iloc[0]

    c20_ic = results[results["name"] == "buy_heavy_expansion"]["avg_ic"].iloc[0]
    c21a_ic = results[results["name"] == "buy_heavy_accel_expansion"]["avg_ic"].iloc[0]
    c21b_ic = results[results["name"] == "sell_heavy_decel_expansion"]["avg_ic"].iloc[0]
    c22_ic = results[results["name"] == "approaching_ceiling"]["avg_ic"].iloc[0]

    c21a_c22_ic = results[results["name"] == "c21a_c22"]["avg_ic"].iloc[0]
    c21b_c22_ic = results[results["name"] == "c21b_c22"]["avg_ic"].iloc[0]
    c20_c22_ic = results[results["name"] == "c20_c22"]["avg_ic"].iloc[0]
    c21a_c21b_ic = results[results["name"] == "c21a_c21b"]["avg_ic"].iloc[0]
    c21a_c22_c20_ic = results[results["name"] == "c21a_c22_c20"]["avg_ic"].iloc[0]
    c21b_c22_c20_ic = results[results["name"] == "c21b_c22_c20"]["avg_ic"].iloc[0]

    c21a_c22_lift = c21a_c22_ic - max(c21a_ic, c22_ic)
    c21b_c22_lift = c21b_c22_ic - max(c21b_ic, c22_ic)
    c20_c22_lift = c20_c22_ic - max(c20_ic, c22_ic)
    c21a_c21b_lift = c21a_c21b_ic - max(c21a_ic, c21b_ic)
    c21a_c22_c20_lift = c21a_c22_c20_ic - max(c21a_ic, c20_ic, c22_ic)
    c21b_c22_c20_lift = c21b_c22_c20_ic - max(c21b_ic, c20_ic, c22_ic)

    best_combo = max([
        ("c21a_c22", c21a_c22_ic, c21a_c22_lift),
        ("c21b_c22", c21b_c22_ic, c21b_c22_lift),
        ("c20_c22", c20_c22_ic, c20_c22_lift),
        ("c21a_c21b", c21a_c21b_ic, c21a_c21b_lift),
        ("c21a_c22_c20", c21a_c22_c20_ic, c21a_c22_c20_lift),
        ("c21b_c22_c20", c21b_c22_c20_ic, c21b_c22_c20_lift),
    ], key=lambda x: x[2])

    if any(l > 0.005 for _, _, l in [
        ("c21a_c22", c21a_c22_ic, c21a_c22_lift),
        ("c21b_c22", c21b_c22_ic, c21b_c22_lift),
        ("c20_c22", c20_c22_ic, c20_c22_lift),
    ]):
        decision = "PASSED"
    else:
        decision = "MIXED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "c20_ic": float(c20_ic), "c21a_ic": float(c21a_ic), "c21b_ic": float(c21b_ic), "c22_ic": float(c22_ic),
            "c21a_c22_ic": float(c21a_c22_ic), "c21a_c22_lift": float(c21a_c22_lift),
            "c21b_c22_ic": float(c21b_c22_ic), "c21b_c22_lift": float(c21b_c22_lift),
            "c20_c22_ic": float(c20_c22_ic), "c20_c22_lift": float(c20_c22_lift),
            "c21a_c21b_ic": float(c21a_c21b_ic), "c21a_c21b_lift": float(c21a_c21b_lift),
            "c21a_c22_c20_ic": float(c21a_c22_c20_ic), "c21a_c22_c20_lift": float(c21a_c22_c20_lift),
            "c21b_c22_c20_ic": float(c21b_c22_c20_ic), "c21b_c22_c20_lift": float(c21b_c22_c20_lift),
            "best_combo": best_combo[0], "best_combo_ic": float(best_combo[1]), "best_combo_lift": float(best_combo[2]),
        },
        artifacts={"results": results_path, "yearly": yearly_path},
        metadata={"state_specs": [state.as_metadata() for state in STATE_SPECS], "hypothesis": SPEC.hypothesis},
    )

    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(f"\nDecision: {decision}")
    print(f"Baseline IC: {baseline_ic:.4f}")
    print(f"\nIndividual signals:")
    print(f"  C20 buy_heavy_expansion: {c20_ic:.4f}")
    print(f"  C21a buy_heavy_accel: {c21a_ic:.4f}")
    print(f"  C21b sell_heavy_decel: {c21b_ic:.4f}")
    print(f"  C22 approaching_ceiling: {c22_ic:.4f}")
    print(f"\nCombos:")
    print(f"  C21a×C22: {c21a_c22_ic:.4f} (lift vs max: {c21a_c22_lift:+.4f})")
    print(f"  C21b×C22: {c21b_c22_ic:.4f} (lift vs max: {c21b_c22_lift:+.4f})")
    print(f"  C20×C22: {c20_c22_ic:.4f} (lift vs max: {c20_c22_lift:+.4f})")
    print(f"  C21a×C21b: {c21a_c21b_ic:.4f} (lift vs max: {c21a_c21b_lift:+.4f})")
    print(f"  C21a×C22×C20: {c21a_c22_c20_ic:.4f} (lift vs max: {c21a_c22_c20_lift:+.4f})")
    print(f"  C21b×C22×C20: {c21b_c22_c20_ic:.4f} (lift vs max: {c21b_c22_c20_lift:+.4f})")
    print(f"\nBest combo: {best_combo[0]} (IC={best_combo[1]:.4f}, lift={best_combo[2]:+.4f})")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()