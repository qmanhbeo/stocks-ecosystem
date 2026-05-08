"""
H451: buy_sell_imbalance_in_stress

Hypothesis: order_stats has buy_sell_volume_imbalance. Does it work differently in 
vol_expansion vs vol_contraction regimes? Mechanism: imbalance might signal hidden 
depth in stress (expansion), crowd in calm (contraction).

First test: imbalance quintiles × vol_regime vs forward IC.
Compare with: Random baseline.

Data: Uses order_stats buy_sell_volume_imbalance and computed vol_regime.
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


BRANCH_NAME = "buy_sell_imbalance_in_stress"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "order_stats has buy_sell_volume_imbalance. Does it work differently in "
        "vol_expansion vs vol_contraction regimes? Imbalance might signal hidden "
        "depth in stress (expansion), crowd in calm (contraction). "
        "Test imbalance quintiles × vol_regime vs forward IC."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H451 buy_sell_imbalance_in_stress test")
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
    
    # Compute buy_sell_volume_imbalance if not present
    if "buy_sell_volume_imbalance" not in order_stats.columns:
        order_stats["total_buy_volume"] = order_stats.get("buy_order_volume", 0)
        order_stats["total_sell_volume"] = order_stats.get("sell_order_volume", 0)
        order_stats["buy_sell_volume_imbalance"] = (
            (order_stats["total_buy_volume"] - order_stats["total_sell_volume"]) / 
            (order_stats["total_buy_volume"] + order_stats["total_sell_volume"] + 1)
        )
    
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
        order_stats[["time", "ticker", "buy_sell_volume_imbalance", "pct_change"]],
        on=["time", "ticker"],
        how="left",
    )
    
    panel["all_rows"] = True
    
    panel = panel.dropna(subset=["buy_sell_volume_imbalance", "pct_change"])
    
    # Compute volatility regime
    panel = panel.sort_values(["ticker", "time"])
    panel["pct_change_vol"] = panel.groupby("ticker")["pct_change"].transform(
        lambda x: x.rolling(window=5, min_periods=3).std()
    )
    panel["vol_change"] = panel.groupby("ticker")["pct_change_vol"].transform(
        lambda x: x.diff()
    )
    
    panel = panel.dropna(subset=["vol_change"])
    
    vol_change_rank = panel.groupby("time", sort=False)["vol_change"].rank(method="average", pct=True)
    panel["vol_expansion"] = vol_change_rank >= 0.8
    panel["vol_contraction"] = vol_change_rank <= 0.2
    
    # Imbalance quintiles
    imbalance_rank = panel.groupby("time", sort=False)["buy_sell_volume_imbalance"].rank(method="average", pct=True)
    panel["imbalance_buy_heavy"] = imbalance_rank >= 0.8  # Top 20% - buying pressure
    panel["imbalance_sell_heavy"] = imbalance_rank <= 0.2  # Bottom 20% - selling pressure
    panel["imbalance_neutral"] = (imbalance_rank > 0.3) & (imbalance_rank < 0.7)
    
    # Combo: imbalance × vol_regime
    panel["buy_heavy_expansion"] = panel["imbalance_buy_heavy"] & panel["vol_expansion"]
    panel["sell_heavy_expansion"] = panel["imbalance_sell_heavy"] & panel["vol_expansion"]
    panel["buy_heavy_contraction"] = panel["imbalance_buy_heavy"] & panel["vol_contraction"]
    panel["sell_heavy_contraction"] = panel["imbalance_sell_heavy"] & panel["vol_contraction"]
    
    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    # Vol regime alone
    StateSpec("vol_expansion", "Volatility expanding (top 20%)", family="vol_regime"),
    StateSpec("vol_contraction", "Volatility contracting (bottom 20%)", family="vol_regime"),
    # Imbalance alone
    StateSpec("imbalance_buy_heavy", "Buy-heavy imbalance (top 20%)", family="imbalance"),
    StateSpec("imbalance_sell_heavy", "Sell-heavy imbalance (bottom 20%)", family="imbalance"),
    StateSpec("imbalance_neutral", "Neutral imbalance (40-60%)", family="imbalance"),
    # COMBOS - primary test
    StateSpec("buy_heavy_expansion", "Buy-heavy + Vol expansion", family="combo", primary=True),
    StateSpec("sell_heavy_expansion", "Sell-heavy + Vol expansion", family="combo"),
    StateSpec("buy_heavy_contraction", "Buy-heavy + Vol contraction", family="combo"),
    StateSpec("sell_heavy_contraction", "Sell-heavy + Vol contraction", family="combo"),
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
    
    vol_expansion_ic = results[results["name"] == "vol_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    vol_contraction_ic = results[results["name"] == "vol_contraction"]["avg_ic"].iloc[0] if not results.empty else 0
    
    buy_heavy_ic = results[results["name"] == "imbalance_buy_heavy"]["avg_ic"].iloc[0] if not results.empty else 0
    sell_heavy_ic = results[results["name"] == "imbalance_sell_heavy"]["avg_ic"].iloc[0] if not results.empty else 0
    
    buy_exp_ic = results[results["name"] == "buy_heavy_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    sell_exp_ic = results[results["name"] == "sell_heavy_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    buy_cont_ic = results[results["name"] == "buy_heavy_contraction"]["avg_ic"].iloc[0] if not results.empty else 0
    sell_cont_ic = results[results["name"] == "sell_heavy_contraction"]["avg_ic"].iloc[0] if not results.empty else 0
    
    vol_expansion_lift = vol_expansion_ic - baseline_ic
    vol_contraction_lift = vol_contraction_ic - baseline_ic
    buy_heavy_lift = buy_heavy_ic - baseline_ic
    sell_heavy_lift = sell_heavy_ic - baseline_ic
    
    buy_exp_lift = buy_exp_ic - baseline_ic
    sell_exp_lift = sell_exp_ic - baseline_ic
    buy_cont_lift = buy_cont_ic - baseline_ic
    sell_cont_lift = sell_cont_ic - baseline_ic
    
    # Compare expansion vs contraction with same imbalance
    buy_exp_vs_cont = buy_exp_lift - buy_cont_lift
    sell_exp_vs_cont = sell_exp_lift - sell_cont_lift
    
    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}
    
    # Hypothesis: imbalance works differently in expansion vs contraction
    if (buy_exp_lift > buy_heavy_lift + 0.01 and buy_exp_lift > 0.01) or \
       (sell_exp_lift > sell_heavy_lift + 0.01 and sell_exp_lift > 0.01):
        decision = "PASSED"
    elif abs(buy_exp_vs_cont) > 0.02 or abs(sell_exp_vs_cont) > 0.02:
        decision = "PASSED"
    elif vol_expansion_lift > 0.01 and vol_contraction_lift < -0.01:
        decision = "PASSED"
    else:
        decision = "MIXED"
    
    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "vol_expansion_ic": float(vol_expansion_ic),
            "vol_contraction_ic": float(vol_contraction_ic),
            "imbalance_buy_heavy_ic": float(buy_heavy_ic),
            "imbalance_sell_heavy_ic": float(sell_heavy_ic),
            "buy_heavy_expansion_ic": float(buy_exp_ic),
            "sell_heavy_expansion_ic": float(sell_exp_ic),
            "buy_heavy_contraction_ic": float(buy_cont_ic),
            "sell_heavy_contraction_ic": float(sell_cont_ic),
            "vol_expansion_lift": float(vol_expansion_lift),
            "vol_contraction_lift": float(vol_contraction_lift),
            "buy_heavy_lift": float(buy_heavy_lift),
            "sell_heavy_lift": float(sell_heavy_lift),
            "buy_exp_lift": float(buy_exp_lift),
            "sell_exp_lift": float(sell_exp_lift),
            "buy_cont_lift": float(buy_cont_lift),
            "sell_cont_lift": float(sell_cont_lift),
            "buy_exp_vs_cont": float(buy_exp_vs_cont),
            "sell_exp_vs_cont": float(sell_exp_vs_cont),
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
    print(f"Vol regime:")
    print(f"  vol_expansion: {vol_expansion_ic:.4f} (lift: {vol_expansion_lift:+.4f})")
    print(f"  vol_contraction: {vol_contraction_ic:.4f} (lift: {vol_contraction_lift:+.4f})")
    print(f"Imbalance:")
    print(f"  buy_heavy: {buy_heavy_ic:.4f} (lift: {buy_heavy_lift:+.4f})")
    print(f"  sell_heavy: {sell_heavy_ic:.4f} (lift: {sell_heavy_lift:+.4f})")
    print(f"Combos:")
    print(f"  buy_heavy_expansion: {buy_exp_ic:.4f} (lift: {buy_exp_lift:+.4f})")
    print(f"  sell_heavy_expansion: {sell_exp_ic:.4f} (lift: {sell_exp_lift:+.4f})")
    print(f"  buy_heavy_contraction: {buy_cont_ic:.4f} (lift: {buy_cont_lift:+.4f})")
    print(f"  sell_heavy_contraction: {sell_cont_ic:.4f} (lift: {sell_cont_lift:+.4f})")
    print(f"Expansion vs Contraction:")
    print(f"  buy: {buy_exp_vs_cont:+.4f}")
    print(f"  sell: {sell_exp_vs_cont:+.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()