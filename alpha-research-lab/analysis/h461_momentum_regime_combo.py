"""
H461: momentum_regime_combo

Hypothesis: C21 sells/buys are the strongest because they capture DECELERATION/ACCELERATION
in vol expansion. Can we improve by adding MOMENTUM (high/low return) to the mix?

First test: momentum × imbalance_delta × vol_expansion vs forward IC.
Compare with: C21 buy_heavy_accel_expansion and sell_heavy_decel_expansion baselines.

Data: Uses order_stats and OHLCV.
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


BRANCH_NAME = "momentum_regime_combo"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "C21 sells/buys are strongest because they capture deceleration/acceleration in vol expansion. "
        "Can momentum (high/low return) improve the combo? Test momentum × imbalance_delta × vol_expansion."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H461 momentum_regime_combo test")
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
    order_stats["buy_sell_volume_imbalance"] = (
        (order_stats["buy_order_volume"] - order_stats["sell_order_volume"]) /
        (order_stats["buy_order_volume"] + order_stats["sell_order_volume"] + 1)
    )

    panel = panel.merge(
        order_stats[["time", "ticker", "pct_change", "total_volume", "buy_sell_volume_imbalance"]],
        on=["time", "ticker"],
        how="left",
    )

    panel["all_rows"] = True

    panel = panel.dropna(subset=["pct_change", "total_volume", "buy_sell_volume_imbalance"])
    panel = panel[panel["total_volume"] > 0]

    panel = panel.sort_values(["ticker", "time"])

    # Volatility regime (H446)
    panel["pct_change_vol"] = panel.groupby("ticker")["pct_change"].transform(
        lambda x: x.rolling(window=5, min_periods=3).std()
    )
    panel["vol_change"] = panel.groupby("ticker")["pct_change_vol"].transform(
        lambda x: x.diff()
    )

    # Imbalance delta (H453)
    panel["imbalance_lag1"] = panel.groupby("ticker")["buy_sell_volume_imbalance"].shift(1)
    panel["imbalance_delta"] = panel["buy_sell_volume_imbalance"] - panel["imbalance_lag1"]

    panel = panel.dropna(subset=["vol_change", "imbalance_delta"])

    # Vol regime
    vol_change_rank = panel.groupby("time", sort=False)["vol_change"].rank(method="average", pct=True)
    panel["vol_expansion"] = vol_change_rank >= 0.8

    # Imbalance level and delta ranks
    imbalance_rank = panel.groupby("time", sort=False)["buy_sell_volume_imbalance"].rank(method="average", pct=True)
    panel["buy_heavy"] = imbalance_rank >= 0.8
    panel["sell_heavy"] = imbalance_rank <= 0.2

    imbalance_delta_rank = panel.groupby("time", sort=False)["imbalance_delta"].rank(method="average", pct=True)
    panel["imbalance_accelerating"] = imbalance_delta_rank >= 0.8
    panel["imbalance_decelerating"] = imbalance_delta_rank <= 0.2

    # Momentum (return) rank
    return_rank = panel.groupby("time", sort=False)["pct_change"].rank(method="average", pct=True)
    panel["high_return"] = return_rank >= 0.7
    panel["low_return"] = return_rank <= 0.3

    # C21 baselines (H453)
    panel["buy_heavy_accel_expansion"] = panel["buy_heavy"] & panel["imbalance_accelerating"] & panel["vol_expansion"]
    panel["sell_heavy_decel_expansion"] = panel["sell_heavy"] & panel["imbalance_decelerating"] & panel["vol_expansion"]

    # Momentum × C21 combos (primary test)
    panel["buy_heavy_accel_expansion_high_return"] = panel["buy_heavy"] & panel["imbalance_accelerating"] & panel["vol_expansion"] & panel["high_return"]
    panel["buy_heavy_accel_expansion_low_return"] = panel["buy_heavy"] & panel["imbalance_accelerating"] & panel["vol_expansion"] & panel["low_return"]
    panel["sell_heavy_decel_expansion_high_return"] = panel["sell_heavy"] & panel["imbalance_decelerating"] & panel["vol_expansion"] & panel["high_return"]
    panel["sell_heavy_decel_expansion_low_return"] = panel["sell_heavy"] & panel["imbalance_decelerating"] & panel["vol_expansion"] & panel["low_return"]

    # Momentum alone with vol expansion
    panel["high_return_expansion"] = panel["high_return"] & panel["vol_expansion"]
    panel["low_return_expansion"] = panel["low_return"] & panel["vol_expansion"]

    # Momentum × imbalance with vol expansion (without level)
    panel["accel_expansion_high_return"] = panel["imbalance_accelerating"] & panel["vol_expansion"] & panel["high_return"]
    panel["accel_expansion_low_return"] = panel["imbalance_accelerating"] & panel["vol_expansion"] & panel["low_return"]
    panel["decel_expansion_high_return"] = panel["imbalance_decelerating"] & panel["vol_expansion"] & panel["high_return"]
    panel["decel_expansion_low_return"] = panel["imbalance_decelerating"] & panel["vol_expansion"] & panel["low_return"]

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    # Vol regime alone
    StateSpec("vol_expansion", "Vol expansion (top 20%)", family="vol_regime"),
    # Momentum alone
    StateSpec("high_return_expansion", "High return + Vol expansion", family="momentum"),
    StateSpec("low_return_expansion", "Low return + Vol expansion", family="momentum"),
    # C21 baselines
    StateSpec("buy_heavy_accel_expansion", "C21: Buy-heavy + Accel + Vol expansion", family="c21_baseline"),
    StateSpec("sell_heavy_decel_expansion", "C21: Sell-heavy + Decel + Vol expansion", family="c21_baseline"),
    # Momentum × C21 (primary test)
    StateSpec("buy_heavy_accel_expansion_high_return", "Buy-heavy + Accel + Vol + High return", family="momentum_c21", primary=True),
    StateSpec("buy_heavy_accel_expansion_low_return", "Buy-heavy + Accel + Vol + Low return", family="momentum_c21"),
    StateSpec("sell_heavy_decel_expansion_high_return", "Sell-heavy + Decel + Vol + High return", family="momentum_c21"),
    StateSpec("sell_heavy_decel_expansion_low_return", "Sell-heavy + Decel + Vol + Low return", family="momentum_c21"),
    # Momentum × imbalance delta (no level)
    StateSpec("accel_expansion_high_return", "Accel + Vol + High return", family="momentum_delta"),
    StateSpec("accel_expansion_low_return", "Accel + Vol + Low return", family="momentum_delta"),
    StateSpec("decel_expansion_high_return", "Decel + Vol + High return", family="momentum_delta"),
    StateSpec("decel_expansion_low_return", "Decel + Vol + Low return", family="momentum_delta"),
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

    # C21 baselines
    buy_accel_ic = results[results["name"] == "buy_heavy_accel_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    sell_decel_ic = results[results["name"] == "sell_heavy_decel_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    buy_accel_lift = buy_accel_ic - baseline_ic
    sell_decel_lift = sell_decel_ic - baseline_ic

    # Momentum × C21
    buy_accel_high_ic = results[results["name"] == "buy_heavy_accel_expansion_high_return"]["avg_ic"].iloc[0] if not results.empty else 0
    buy_accel_low_ic = results[results["name"] == "buy_heavy_accel_expansion_low_return"]["avg_ic"].iloc[0] if not results.empty else 0
    sell_decel_high_ic = results[results["name"] == "sell_heavy_decel_expansion_high_return"]["avg_ic"].iloc[0] if not results.empty else 0
    sell_decel_low_ic = results[results["name"] == "sell_heavy_decel_expansion_low_return"]["avg_ic"].iloc[0] if not results.empty else 0

    buy_accel_high_lift = buy_accel_high_ic - baseline_ic
    buy_accel_low_lift = buy_accel_low_ic - baseline_ic
    sell_decel_high_lift = sell_decel_high_ic - baseline_ic
    sell_decel_low_lift = sell_decel_low_ic - baseline_ic

    # Momentum × delta (no level)
    accel_high_ic = results[results["name"] == "accel_expansion_high_return"]["avg_ic"].iloc[0] if not results.empty else 0
    accel_low_ic = results[results["name"] == "accel_expansion_low_return"]["avg_ic"].iloc[0] if not results.empty else 0
    decel_high_ic = results[results["name"] == "decel_expansion_high_return"]["avg_ic"].iloc[0] if not results.empty else 0
    decel_low_ic = results[results["name"] == "decel_expansion_low_return"]["avg_ic"].iloc[0] if not results.empty else 0

    # Comparisons
    buy_accel_high_vs_baseline = buy_accel_high_lift - buy_accel_lift
    sell_decel_high_vs_baseline = sell_decel_high_lift - sell_decel_lift

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    # Hypothesis: momentum improves C21 combos
    if buy_accel_high_lift > buy_accel_lift + 0.005 or sell_decel_high_lift > sell_decel_lift + 0.005:
        decision = "PASSED"
    elif buy_accel_low_lift > buy_accel_lift + 0.005 or sell_decel_low_lift > sell_decel_lift + 0.005:
        decision = "MIXED"
    else:
        decision = "MIXED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            # C21 baselines
            "buy_heavy_accel_expansion_ic": float(buy_accel_ic),
            "sell_heavy_decel_expansion_ic": float(sell_decel_ic),
            "buy_heavy_accel_expansion_lift": float(buy_accel_lift),
            "sell_heavy_decel_expansion_lift": float(sell_decel_lift),
            # Momentum × C21
            "buy_heavy_accel_expansion_high_return_ic": float(buy_accel_high_ic),
            "buy_heavy_accel_expansion_low_return_ic": float(buy_accel_low_ic),
            "sell_heavy_decel_expansion_high_return_ic": float(sell_decel_high_ic),
            "sell_heavy_decel_expansion_low_return_ic": float(sell_decel_low_ic),
            "buy_heavy_accel_expansion_high_return_lift": float(buy_accel_high_lift),
            "buy_heavy_accel_expansion_low_return_lift": float(buy_accel_low_lift),
            "sell_heavy_decel_expansion_high_return_lift": float(sell_decel_high_lift),
            "sell_heavy_decel_expansion_low_return_lift": float(sell_decel_low_lift),
            # Comparisons
            "buy_accel_high_vs_c21_baseline": float(buy_accel_high_vs_baseline),
            "sell_decel_high_vs_c21_baseline": float(sell_decel_high_vs_baseline),
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
    print(f"\nC21 Baselines:")
    print(f"  buy_heavy_accel_expansion: {buy_accel_ic:.4f} (lift: {buy_accel_lift:+.4f})")
    print(f"  sell_heavy_decel_expansion: {sell_decel_ic:.4f} (lift: {sell_decel_lift:+.4f})")
    print(f"\nMomentum × C21:")
    print(f"  buy_heavy_accel_expansion_high_return: {buy_accel_high_ic:.4f} (lift: {buy_accel_high_lift:+.4f})")
    print(f"  buy_heavy_accel_expansion_low_return: {buy_accel_low_ic:.4f} (lift: {buy_accel_low_lift:+.4f})")
    print(f"  sell_heavy_decel_expansion_high_return: {sell_decel_high_ic:.4f} (lift: {sell_decel_high_lift:+.4f})")
    print(f"  sell_heavy_decel_expansion_low_return: {sell_decel_low_ic:.4f} (lift: {sell_decel_low_lift:+.4f})")
    print(f"\nMomentum improvement vs C21:")
    print(f"  buy_accel_high vs C21 baseline: {buy_accel_high_vs_baseline:+.4f}")
    print(f"  sell_decel_high vs C21 baseline: {sell_decel_high_vs_baseline:+.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()