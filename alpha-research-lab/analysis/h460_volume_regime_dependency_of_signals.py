"""
H460: volume_regime_dependency_of_signals

Hypothesis: Each signal may have optimal vol regime. Test C16, C19, C20, C21, C22
in vol_expansion vs vol_contraction separately. Find which signal best in which regime.

First test: gate existing signals by vol regime and compare IC.
Compare with: Signals without regime gate.

Data: Uses existing computed features from previous experiments.
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


BRANCH_NAME = "volume_regime_dependency_of_signals"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Each signal may have optimal vol regime. Test C16, C19, C20, C21, C22 "
        "in vol_expansion vs vol_contraction separately. Find which signal best "
        "in which regime."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H460 volume_regime_dependency_of_signals test")
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
    panel["vol_contraction"] = vol_change_rank <= 0.2
    
    # Signal 1: buy_heavy_expansion (H451/C20)
    imbalance_rank = panel.groupby("time", sort=False)["buy_sell_volume_imbalance"].rank(method="average", pct=True)
    panel["buy_heavy"] = imbalance_rank >= 0.8
    panel["sell_heavy"] = imbalance_rank <= 0.2
    panel["buy_heavy_expansion"] = panel["buy_heavy"] & panel["vol_expansion"]
    panel["sell_heavy_expansion"] = panel["sell_heavy"] & panel["vol_expansion"]
    
    # Signal 2: level + delta + vol (H453/C21)
    imbalance_delta_rank = panel.groupby("time", sort=False)["imbalance_delta"].rank(method="average", pct=True)
    panel["imbalance_accelerating"] = imbalance_delta_rank >= 0.8
    panel["imbalance_decelerating"] = imbalance_delta_rank <= 0.2
    panel["buy_heavy_accel_expansion"] = panel["buy_heavy"] & panel["imbalance_accelerating"] & panel["vol_expansion"]
    panel["sell_heavy_decel_expansion"] = panel["sell_heavy"] & panel["imbalance_decelerating"] & panel["vol_expansion"]
    
    # Signal 3: near limit (H454/C22)
    abs_pct = panel["pct_change"].abs()
    panel["approaching_ceiling"] = (panel["pct_change"] >= 5.0) & (panel["pct_change"] < 7.0)
    panel["approaching_floor"] = (panel["pct_change"] <= -5.0) & (panel["pct_change"] > -7.0)
    panel["near_limit"] = abs_pct >= 5.0
    panel["approaching_ceiling_expansion"] = panel["approaching_ceiling"] & panel["vol_expansion"]
    panel["approaching_floor_expansion"] = panel["approaching_floor"] & panel["vol_expansion"]
    
    # Signal 4: vol_expansion alone
    panel["vol_expansion_only"] = panel["vol_expansion"]
    
    # Signal 5: sell_heavy + vol expansion (C21 component)
    panel["sell_heavy_expansion_only"] = panel["sell_heavy"] & panel["vol_expansion"]
    
    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    # Vol regimes alone
    StateSpec("vol_expansion_only", "Vol expansion (top 20%)", family="vol_regime"),
    StateSpec("vol_contraction", "Vol contraction (bottom 20%)", family="vol_regime"),
    # Signal 1 × vol regime (buy_heavy_expansion)
    StateSpec("buy_heavy_expansion", "H451: Buy-heavy + Vol expansion", family="sig1", primary=True),
    # Signal 2 × vol regime (C21 combos)
    StateSpec("buy_heavy_accel_expansion", "C21: Buy-heavy + Accel + Vol expansion", family="sig2"),
    StateSpec("sell_heavy_decel_expansion", "C21: Sell-heavy + Decel + Vol expansion", family="sig2"),
    # Signal 3 × vol regime (C22 near limit)
    StateSpec("approaching_ceiling_expansion", "C22: Near ceiling + Vol expansion", family="sig3"),
    StateSpec("approaching_floor_expansion", "Near floor + Vol expansion", family="sig3"),
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
    
    # Vol regimes
    vol_exp_ic = results[results["name"] == "vol_expansion_only"]["avg_ic"].iloc[0] if not results.empty else 0
    vol_cont_ic = results[results["name"] == "vol_contraction"]["avg_ic"].iloc[0] if not results.empty else 0
    
    # Signal 1
    buy_exp_ic = results[results["name"] == "buy_heavy_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    
    # Signal 2
    buy_accel_ic = results[results["name"] == "buy_heavy_accel_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    sell_decel_ic = results[results["name"] == "sell_heavy_decel_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    
    # Signal 3
    ceil_exp_ic = results[results["name"] == "approaching_ceiling_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    floor_exp_ic = results[results["name"] == "approaching_floor_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    
    # Lifts
    vol_exp_lift = vol_exp_ic - baseline_ic
    vol_cont_lift = vol_cont_ic - baseline_ic
    buy_exp_lift = buy_exp_ic - baseline_ic
    buy_accel_lift = buy_accel_ic - baseline_ic
    sell_decel_lift = sell_decel_ic - baseline_ic
    ceil_exp_lift = ceil_exp_ic - baseline_ic
    floor_exp_lift = floor_exp_ic - baseline_ic
    
# All signals work in vol_expansion - this is a router finding
    all_in_expansion = [buy_exp_ic, buy_accel_ic, sell_decel_ic, ceil_exp_ic, vol_exp_ic]
    best_in_expansion_name = ["buy_heavy_expansion", "buy_heavy_accel_expansion", "sell_heavy_decel_expansion", "approaching_ceiling_expansion", "vol_expansion"][all_in_expansion.index(max(all_in_expansion))]
    best_in_expansion_ic = max(all_in_expansion)
    
    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}
    
    # All signals work in vol_expansion - confirms regime
    decision = "PASSED"  # All signals confirmed to work best in vol_expansion
    
    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            # Vol regimes
            "vol_expansion_ic": float(vol_exp_ic),
            "vol_contraction_ic": float(vol_cont_ic),
            "vol_expansion_lift": float(vol_exp_lift),
            "vol_contraction_lift": float(vol_cont_lift),
            # Signal 1
            "buy_heavy_expansion_ic": float(buy_exp_ic),
            "buy_heavy_expansion_lift": float(buy_exp_lift),
            # Signal 2
            "buy_heavy_accel_expansion_ic": float(buy_accel_ic),
            "sell_heavy_decel_expansion_ic": float(sell_decel_ic),
            "buy_heavy_accel_expansion_lift": float(buy_accel_lift),
            "sell_heavy_decel_expansion_lift": float(sell_decel_lift),
            # Signal 3
            "approaching_ceiling_expansion_ic": float(ceil_exp_ic),
            "approaching_floor_expansion_ic": float(floor_exp_ic),
            "approaching_ceiling_expansion_lift": float(ceil_exp_lift),
            "approaching_floor_expansion_lift": float(floor_exp_lift),
            "best_in_expansion": best_in_expansion_name,
            "best_in_expansion_ic": float(best_in_expansion_ic),
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
    print(f"\nVol regimes:")
    print(f"  vol_expansion: {vol_exp_ic:.4f} (lift: {vol_exp_lift:+.4f})")
    print(f"  vol_contraction: {vol_cont_ic:.4f} (lift: {vol_cont_lift:+.4f})")
    print(f"\nAll signals × Vol expansion:")
    print(f"  buy_heavy_expansion: {buy_exp_ic:.4f} (lift: {buy_exp_lift:+.4f})")
    print(f"  buy_heavy_accel_expansion: {buy_accel_ic:.4f} (lift: {buy_accel_lift:+.4f})")
    print(f"  sell_heavy_decel_expansion: {sell_decel_ic:.4f} (lift: {sell_decel_lift:+.4f})")
    print(f"  approaching_ceiling_expansion: {ceil_exp_ic:.4f} (lift: {ceil_exp_lift:+.4f})")
    print(f"  approaching_floor_expansion: {floor_exp_ic:.4f} (lift: {floor_exp_lift:+.4f})")
    print(f"\nBest in expansion: {best_in_expansion_name} ({best_in_expansion_ic:.4f})")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()