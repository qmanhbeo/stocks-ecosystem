"""
H453: order_flow_imbalance_momentum

Hypothesis: H451 tested LEVEL × vol_regime. What about CHANGE in imbalance?
Acceleration in buy pressure might signal hidden demand better than level alone.
Test: imbalance_delta × vol_regime vs forward IC.

First test: imbalance delta (acceleration) × vol_regime vs random baseline.
Compare with: H451 buy_heavy_expansion (+0.0508 lift) as reference.

Data: Uses order_stats buy_sell_volume_imbalance and computed vol_change.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

import pandas as pd
import numpy as np
import re

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


BRANCH_NAME = "order_flow_imbalance_momentum"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "H451 tested LEVEL × vol_regime. What about CHANGE in imbalance? "
        "Acceleration in buy pressure might signal hidden demand better than level alone. "
        "Test imbalance_delta × vol_regime vs forward IC."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H453 order_flow_imbalance_momentum test")
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
    
    # Parse price_change_raw
    order_stats["pct_change"] = order_stats["price_change_raw"].apply(parse_price_change)
    
    # Compute buy_sell_volume_imbalance
    order_stats["total_buy_volume"] = order_stats.get("buy_order_volume", 0)
    order_stats["total_sell_volume"] = order_stats.get("sell_order_volume", 0)
    order_stats["buy_sell_volume_imbalance"] = (
        (order_stats["total_buy_volume"] - order_stats["total_sell_volume"]) / 
        (order_stats["total_buy_volume"] + order_stats["total_sell_volume"] + 1)
    )
    
    panel = panel.merge(
        order_stats[["time", "ticker", "buy_sell_volume_imbalance", "pct_change"]],
        on=["time", "ticker"],
        how="left",
    )
    
    panel["all_rows"] = True
    
    panel = panel.dropna(subset=["buy_sell_volume_imbalance", "pct_change"])
    
    # Sort and compute features
    panel = panel.sort_values(["ticker", "time"])
    
    # Volatility regime
    panel["pct_change_vol"] = panel.groupby("ticker")["pct_change"].transform(
        lambda x: x.rolling(window=5, min_periods=3).std()
    )
    panel["vol_change"] = panel.groupby("ticker")["pct_change_vol"].transform(
        lambda x: x.diff()
    )
    
    # Imbalance delta (acceleration) - key new feature
    panel["imbalance_lag1"] = panel.groupby("ticker")["buy_sell_volume_imbalance"].shift(1)
    panel["imbalance_lag2"] = panel.groupby("ticker")["buy_sell_volume_imbalance"].shift(2)
    panel["imbalance_delta"] = panel["buy_sell_volume_imbalance"] - panel["imbalance_lag1"]
    panel["imbalance_accel"] = panel["imbalance_delta"] - (panel["imbalance_lag1"] - panel["imbalance_lag2"])
    
    panel = panel.dropna(subset=["vol_change", "imbalance_delta"])
    
    # Vol regime
    vol_change_rank = panel.groupby("time", sort=False)["vol_change"].rank(method="average", pct=True)
    panel["vol_expansion"] = vol_change_rank >= 0.8
    panel["vol_contraction"] = vol_change_rank <= 0.2
    
    # Imbalance level quintiles
    imbalance_rank = panel.groupby("time", sort=False)["buy_sell_volume_imbalance"].rank(method="average", pct=True)
    panel["imbalance_buy_heavy"] = imbalance_rank >= 0.8
    panel["imbalance_sell_heavy"] = imbalance_rank <= 0.2
    
    # Imbalance delta (acceleration) quintiles
    imbalance_delta_rank = panel.groupby("time", sort=False)["imbalance_delta"].rank(method="average", pct=True)
    panel["imbalance_accelerating"] = imbalance_delta_rank >= 0.8   # buying pressure increasing
    panel["imbalance_decelerating"] = imbalance_delta_rank <= 0.2   # buying pressure decreasing
    panel["imbalance_stable"] = (imbalance_delta_rank > 0.3) & (imbalance_delta_rank < 0.7)
    
    # Imbalance level × vol regime (H451 reference)
    panel["buy_heavy_expansion"] = panel["imbalance_buy_heavy"] & panel["vol_expansion"]
    panel["sell_heavy_expansion"] = panel["imbalance_sell_heavy"] & panel["vol_expansion"]
    
    # Imbalance delta × vol regime (primary test)
    panel["accel_expansion"] = panel["imbalance_accelerating"] & panel["vol_expansion"]
    panel["accel_contraction"] = panel["imbalance_accelerating"] & panel["vol_contraction"]
    panel["decel_expansion"] = panel["imbalance_decelerating"] & panel["vol_expansion"]
    panel["decel_contraction"] = panel["imbalance_decelerating"] & panel["vol_contraction"]
    
    # Level + delta combo (most informative)
    panel["buy_heavy_accel_expansion"] = panel["imbalance_buy_heavy"] & panel["imbalance_accelerating"] & panel["vol_expansion"]
    panel["sell_heavy_decel_expansion"] = panel["imbalance_sell_heavy"] & panel["imbalance_decelerating"] & panel["vol_expansion"]
    
    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    # Vol regime alone
    StateSpec("vol_expansion", "Volatility expanding (top 20%)", family="vol_regime"),
    StateSpec("vol_contraction", "Volatility contracting (bottom 20%)", family="vol_regime"),
    # Imbalance level alone
    StateSpec("imbalance_buy_heavy", "Buy-heavy imbalance level (top 20%)", family="imb_level"),
    StateSpec("imbalance_sell_heavy", "Sell-heavy imbalance level (bottom 20%)", family="imb_level"),
    # Imbalance delta alone
    StateSpec("imbalance_accelerating", "Imbalance accelerating (top 20%)", family="imb_delta"),
    StateSpec("imbalance_decelerating", "Imbalance decelerating (bottom 20%)", family="imb_delta"),
    StateSpec("imbalance_stable", "Imbalance stable (40-60%)", family="imb_delta"),
    # Level × vol (H451 reference)
    StateSpec("buy_heavy_expansion", "H451: Buy-heavy level + Vol expansion", family="level_vol"),
    StateSpec("sell_heavy_expansion", "Sell-heavy level + Vol expansion", family="level_vol"),
    # Delta × vol (primary test)
    StateSpec("accel_expansion", "Imbalance accelerating + Vol expansion", family="delta_vol", primary=True),
    StateSpec("accel_contraction", "Imbalance accelerating + Vol contraction", family="delta_vol"),
    StateSpec("decel_expansion", "Imbalance decelerating + Vol expansion", family="delta_vol"),
    StateSpec("decel_contraction", "Imbalance decelerating + Vol contraction", family="delta_vol"),
    # Level + delta + vol combo
    StateSpec("buy_heavy_accel_expansion", "Buy-heavy + Accelerating + Vol expansion", family="combo"),
    StateSpec("sell_heavy_decel_expansion", "Sell-heavy + Decelerating + Vol expansion", family="combo"),
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

    baseline_ic = results[results["name"] == "all_rows"]["avg_ic"].iloc[0] if not results.empty else 0
    
    # H451 reference
    buy_exp_ic = results[results["name"] == "buy_heavy_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    buy_exp_lift = buy_exp_ic - baseline_ic
    
    # Imbalance delta alone
    accel_ic = results[results["name"] == "imbalance_accelerating"]["avg_ic"].iloc[0] if not results.empty else 0
    decel_ic = results[results["name"] == "imbalance_decelerating"]["avg_ic"].iloc[0] if not results.empty else 0
    stable_ic = results[results["name"] == "imbalance_stable"]["avg_ic"].iloc[0] if not results.empty else 0
    accel_lift = accel_ic - baseline_ic
    decel_lift = decel_ic - baseline_ic
    
    # Delta × vol
    accel_exp_ic = results[results["name"] == "accel_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    accel_cont_ic = results[results["name"] == "accel_contraction"]["avg_ic"].iloc[0] if not results.empty else 0
    decel_exp_ic = results[results["name"] == "decel_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    decel_cont_ic = results[results["name"] == "decel_contraction"]["avg_ic"].iloc[0] if not results.empty else 0
    
    accel_exp_lift = accel_exp_ic - baseline_ic
    accel_cont_lift = accel_cont_ic - baseline_ic
    decel_exp_lift = decel_exp_ic - baseline_ic
    decel_cont_lift = decel_cont_ic - baseline_ic
    
    # Level + delta + vol
    buy_accel_exp_ic = results[results["name"] == "buy_heavy_accel_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    sell_decel_exp_ic = results[results["name"] == "sell_heavy_decel_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    buy_accel_exp_lift = buy_accel_exp_ic - baseline_ic
    sell_decel_exp_lift = sell_decel_exp_ic - baseline_ic
    
    # Compare delta × vol vs level × vol
    accel_vs_level_exp = accel_exp_lift - buy_exp_lift
    
    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}
    
    # Hypothesis: imbalance ACCELERATION × vol regime works better than level × vol
    if accel_exp_lift > buy_exp_lift + 0.005 and accel_exp_lift > 0.01:
        decision = "PASSED"
    elif buy_accel_exp_lift > buy_exp_lift + 0.005 and buy_accel_exp_lift > 0.01:
        decision = "PASSED"
    elif accel_lift > 0.01 or decel_lift > 0.01:
        # Delta alone is informative
        if accel_exp_lift > 0.01 or decel_exp_lift > 0.01:
            decision = "MIXED"
        else:
            decision = "MIXED"
    elif abs(accel_vs_level_exp) < 0.005:
        decision = "FAILED"
    else:
        decision = "MIXED"
    
    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            # H451 reference
            "buy_heavy_expansion_ic": float(buy_exp_ic),
            "buy_heavy_expansion_lift": float(buy_exp_lift),
            # Delta alone
            "imbalance_accelerating_ic": float(accel_ic),
            "imbalance_decelerating_ic": float(decel_ic),
            "imbalance_stable_ic": float(stable_ic),
            "accel_lift": float(accel_lift),
            "decel_lift": float(decel_lift),
            # Delta × vol
            "accel_expansion_ic": float(accel_exp_ic),
            "accel_contraction_ic": float(accel_cont_ic),
            "decel_expansion_ic": float(decel_exp_ic),
            "decel_contraction_ic": float(decel_cont_ic),
            "accel_expansion_lift": float(accel_exp_lift),
            "accel_contraction_lift": float(accel_cont_lift),
            "decel_expansion_lift": float(decel_exp_lift),
            "decel_contraction_lift": float(decel_cont_lift),
            # Level + delta + vol
            "buy_heavy_accel_expansion_ic": float(buy_accel_exp_ic),
            "sell_heavy_decel_expansion_ic": float(sell_decel_exp_ic),
            "buy_heavy_accel_expansion_lift": float(buy_accel_exp_lift),
            "sell_heavy_decel_expansion_lift": float(sell_decel_exp_lift),
            # Comparison
            "accel_vs_level_expansion": float(accel_vs_level_exp),
            "best_state_by_avg_year_ic": best_row.get("name"),
            "best_avg_year_ic": best_row.get("avg_ic"),
            "best_positive_years": best_row.get("positive_years"),
            "best_years": best_row.get("years"),
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
    print(f"\nDecision: {decision}")
    print(f"Baseline IC: {baseline_ic:.4f}")
    print(f"\nH451 reference:")
    print(f"  buy_heavy_expansion: {buy_exp_ic:.4f} (lift: {buy_exp_lift:+.4f})")
    print(f"\nImbalance delta alone:")
    print(f"  accelerating: {accel_ic:.4f} (lift: {accel_lift:+.4f})")
    print(f"  decelerating: {decel_ic:.4f} (lift: {decel_lift:+.4f})")
    print(f"  stable: {stable_ic:.4f}")
    print(f"\nDelta × vol regime:")
    print(f"  accel_expansion: {accel_exp_ic:.4f} (lift: {accel_exp_lift:+.4f})")
    print(f"  accel_contraction: {accel_cont_ic:.4f} (lift: {accel_cont_lift:+.4f})")
    print(f"  decel_expansion: {decel_exp_ic:.4f} (lift: {decel_exp_lift:+.4f})")
    print(f"  decel_contraction: {decel_cont_ic:.4f} (lift: {decel_cont_lift:+.4f})")
    print(f"\nLevel + delta + vol:")
    print(f"  buy_heavy_accel_expansion: {buy_accel_exp_ic:.4f} (lift: {buy_accel_exp_lift:+.4f})")
    print(f"  sell_heavy_decel_expansion: {sell_decel_exp_ic:.4f} (lift: {sell_decel_exp_lift:+.4f})")
    print(f"\nDelta vs Level (expansion): {accel_vs_level_exp:+.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()