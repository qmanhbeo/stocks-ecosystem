"""
H452: volume_level_vs_direction_divergence

Hypothesis: H447 showed volume LEVEL + return interaction (contrarian works). What about 
vol DIRECTION (expanding vs contracting) + return interaction? Mechanism: high return + 
vol_expanding = momentum, high return + vol_contracting = exhaustion.

First test: vol_regime × return quintiles vs forward IC.
Compare with: Random baseline.

Data: Uses order_stats and computed vol_change from H446.
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


BRANCH_NAME = "volume_level_vs_direction_divergence"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "H447 showed volume LEVEL + return interaction (low_vol works). What about "
        "vol DIRECTION (expanding vs contracting) + return interaction? "
        "High return + vol_expanding = momentum, high return + vol_contracting = exhaustion. "
        "Test vol_regime × return vs forward IC."
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
    parser = argparse.ArgumentParser(description="H452 volume_level_vs_direction_divergence test")
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
    
    order_stats["pct_change"] = order_stats["price_change_raw"].apply(parse_price_change)
    order_stats["total_volume"] = order_stats["buy_order_volume"] + order_stats["sell_order_volume"]
    
    panel = panel.merge(
        order_stats[["time", "ticker", "pct_change", "total_volume"]],
        on=["time", "ticker"],
        how="left",
    )
    
    panel["all_rows"] = True
    
    panel = panel.dropna(subset=["pct_change", "total_volume"])
    panel = panel[panel["total_volume"] > 0]
    
    # Volume LEVEL (from H447)
    volume_rank = panel.groupby("time", sort=False)["total_volume"].rank(method="average", pct=True)
    panel["high_vol_level"] = volume_rank >= 0.7
    panel["low_vol_level"] = volume_rank <= 0.3
    
    # Return rank
    return_rank = panel.groupby("time", sort=False)["pct_change"].rank(method="average", pct=True)
    panel["high_return"] = return_rank >= 0.7
    panel["low_return"] = return_rank <= 0.3
    
    # Vol DIRECTION (from H446)
    panel = panel.sort_values(["ticker", "time"])
    panel["pct_change_vol"] = panel.groupby("ticker")["pct_change"].transform(
        lambda x: x.rolling(window=5, min_periods=3).std()
    )
    panel["vol_change"] = panel.groupby("ticker")["pct_change_vol"].transform(
        lambda x: x.diff()
    )
    
    panel = panel.dropna(subset=["vol_change"])
    
    vol_change_rank = panel.groupby("time", sort=False)["vol_change"].rank(method="average", pct=True)
    panel["vol_expanding"] = vol_change_rank >= 0.8
    panel["vol_contracting"] = vol_change_rank <= 0.2
    
    # Volume LEVEL × return (H447 pattern)
    panel["high_vol_level_high_return"] = panel["high_vol_level"] & panel["high_return"]
    panel["high_vol_level_low_return"] = panel["high_vol_level"] & panel["low_return"]
    panel["low_vol_level_high_return"] = panel["low_vol_level"] & panel["high_return"]
    panel["low_vol_level_low_return"] = panel["low_vol_level"] & panel["low_return"]
    
    # Volume DIRECTION × return (new test)
    panel["vol_expanding_high_return"] = panel["vol_expanding"] & panel["high_return"]
    panel["vol_expanding_low_return"] = panel["vol_expanding"] & panel["low_return"]
    panel["vol_contracting_high_return"] = panel["vol_contracting"] & panel["high_return"]
    panel["vol_contracting_low_return"] = panel["vol_contracting"] & panel["low_return"]
    
    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    # Volume LEVEL alone
    StateSpec("high_vol_level", "High volume level (top 30%)", family="vol_level"),
    StateSpec("low_vol_level", "Low volume level (bottom 30%)", family="vol_level"),
    # Vol DIRECTION alone
    StateSpec("vol_expanding", "Vol expanding (top 20% 5d change)", family="vol_dir"),
    StateSpec("vol_contracting", "Vol contracting (bottom 20%)", family="vol_dir"),
    # Return alone
    StateSpec("high_return", "High return (top 30%)", family="return"),
    StateSpec("low_return", "Low return (bottom 30%)", family="return"),
    # Volume LEVEL × return (for comparison)
    StateSpec("low_vol_level_low_return", "Low vol level + Low return", family="level_return"),
    StateSpec("high_vol_level_high_return", "High vol level + High return", family="level_return"),
    # Volume DIRECTION × return (primary test)
    StateSpec("vol_expanding_high_return", "Vol expanding + High return (momentum)", family="dir_return", primary=True),
    StateSpec("vol_expanding_low_return", "Vol expanding + Low return (oversold)", family="dir_return"),
    StateSpec("vol_contracting_high_return", "Vol contracting + High return (exhaustion)", family="dir_return"),
    StateSpec("vol_contracting_low_return", "Vol contracting + Low return", family="dir_return"),
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
    
    # Volume level × return
    low_vol_low_ret = results[results["name"] == "low_vol_level_low_return"]["avg_ic"].iloc[0] if not results.empty else 0
    high_vol_high_ret = results[results["name"] == "high_vol_level_high_return"]["avg_ic"].iloc[0] if not results.empty else 0
    
    # Volume direction × return
    exp_high_ret = results[results["name"] == "vol_expanding_high_return"]["avg_ic"].iloc[0] if not results.empty else 0
    exp_low_ret = results[results["name"] == "vol_expanding_low_return"]["avg_ic"].iloc[0] if not results.empty else 0
    cont_high_ret = results[results["name"] == "vol_contracting_high_return"]["avg_ic"].iloc[0] if not results.empty else 0
    cont_low_ret = results[results["name"] == "vol_contracting_low_return"]["avg_ic"].iloc[0] if not results.empty else 0
    
    low_vol_low_ret_lift = low_vol_low_ret - baseline_ic
    high_vol_high_ret_lift = high_vol_high_ret - baseline_ic
    exp_high_ret_lift = exp_high_ret - baseline_ic
    exp_low_ret_lift = exp_low_ret - baseline_ic
    cont_high_ret_lift = cont_high_ret - baseline_ic
    cont_low_ret_lift = cont_low_ret - baseline_ic
    
    # Compare direction vs level for high return
    direction_vs_level_high = exp_high_ret_lift - high_vol_high_ret_lift
    direction_vs_level_low = exp_low_ret_lift - low_vol_low_ret_lift
    
    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}
    
    # Hypothesis: direction × return might work better than level × return
    if direction_vs_level_high > 0.01 and exp_high_ret_lift > 0.01:
        decision = "PASSED"
    elif direction_vs_level_low > 0.01 and exp_low_ret_lift > 0.01:
        decision = "PASSED"
    elif abs(direction_vs_level_high) < 0.005 and abs(direction_vs_level_low) < 0.005:
        decision = "FAILED"
    else:
        decision = "MIXED"
    
    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "low_vol_level_low_return_ic": float(low_vol_low_ret),
            "high_vol_level_high_return_ic": float(high_vol_high_ret),
            "vol_expanding_high_return_ic": float(exp_high_ret),
            "vol_expanding_low_return_ic": float(exp_low_ret),
            "vol_contracting_high_return_ic": float(cont_high_ret),
            "vol_contracting_low_return_ic": float(cont_low_ret),
            "low_vol_level_low_return_lift": float(low_vol_low_ret_lift),
            "high_vol_level_high_return_lift": float(high_vol_high_ret_lift),
            "vol_expanding_high_return_lift": float(exp_high_ret_lift),
            "vol_expanding_low_return_lift": float(exp_low_ret_lift),
            "vol_contracting_high_return_lift": float(cont_high_ret_lift),
            "vol_contracting_low_return_lift": float(cont_low_ret_lift),
            "direction_vs_level_high": float(direction_vs_level_high),
            "direction_vs_level_low": float(direction_vs_level_low),
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
    print(f"Volume LEVEL × return:")
    print(f"  low_vol_level_low_return: {low_vol_low_ret:.4f} (lift: {low_vol_low_ret_lift:+.4f})")
    print(f"  high_vol_level_high_return: {high_vol_high_ret:.4f} (lift: {high_vol_high_ret_lift:+.4f})")
    print(f"Volume DIRECTION × return:")
    print(f"  vol_expanding_high_return: {exp_high_ret:.4f} (lift: {exp_high_ret_lift:+.4f})")
    print(f"  vol_expanding_low_return: {exp_low_ret:.4f} (lift: {exp_low_ret_lift:+.4f})")
    print(f"  vol_contracting_high_return: {cont_high_ret:.4f} (lift: {cont_high_ret_lift:+.4f})")
    print(f"  vol_contracting_low_return: {cont_low_ret:.4f} (lift: {cont_low_ret_lift:+.4f})")
    print(f"Direction vs Level:")
    print(f"  high return: {direction_vs_level_high:+.4f}")
    print(f"  low return: {direction_vs_level_low:+.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()