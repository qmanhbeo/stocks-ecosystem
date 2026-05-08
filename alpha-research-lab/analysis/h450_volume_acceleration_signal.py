"""
H450: volume_acceleration_signal

Hypothesis: H447 tested volume LEVEL + return interaction. What about volume CHANGE 
(acceleration) + return? H446 showed vol CHANGE matters, so volume CHANGE + return 
interaction might work better than volume LEVEL + return.

First test: vol_delta (volume change) × return buckets vs forward IC.
Compare with: Random baseline.

Data: Uses order_stats for volume and computed volume change.
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


BRANCH_NAME = "volume_acceleration_signal"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "H447 tested volume LEVEL + return interaction. What about volume CHANGE "
        "(acceleration) + return? H446 showed vol CHANGE matters, so volume CHANGE "
        "+ return interaction might work better than volume LEVEL + return. "
        "Test vol_delta × return buckets vs forward IC."
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
    parser = argparse.ArgumentParser(description="H450 volume_acceleration_signal test")
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
    
    # Compute volume change (acceleration)
    panel = panel.sort_values(["ticker", "time"])
    panel["volume_ma5"] = panel.groupby("ticker")["total_volume"].transform(
        lambda x: x.rolling(window=5, min_periods=3).mean()
    )
    panel["vol_delta"] = panel["total_volume"] - panel["volume_ma5"]
    panel["vol_delta_pct"] = panel["vol_delta"] / (panel["volume_ma5"] + 1)
    
    panel = panel.dropna(subset=["vol_delta"])
    
    # Return rank
    return_rank = panel.groupby("time", sort=False)["pct_change"].rank(method="average", pct=True)
    vol_delta_rank = panel.groupby("time", sort=False)["vol_delta"].rank(method="average", pct=True)
    
    # Volume change buckets
    panel["vol_accelerating"] = vol_delta_rank >= 0.7
    panel["vol_decelerating"] = vol_delta_rank <= 0.3
    
    # Return buckets
    panel["high_return"] = return_rank >= 0.7
    panel["low_return"] = return_rank <= 0.3
    
    # Volume acceleration × return combos
    panel["vol_accel_high_return"] = panel["vol_accelerating"] & panel["high_return"]
    panel["vol_accel_low_return"] = panel["vol_accelerating"] & panel["low_return"]
    panel["vol_decel_high_return"] = panel["vol_decelerating"] & panel["high_return"]
    panel["vol_decel_low_return"] = panel["vol_decelerating"] & panel["low_return"]
    
    # Compare with volume LEVEL (H447)
    volume_rank = panel.groupby("time", sort=False)["total_volume"].rank(method="average", pct=True)
    panel["high_vol"] = volume_rank >= 0.7
    panel["low_vol"] = volume_rank <= 0.3
    
    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    # Volume change alone
    StateSpec("vol_accelerating", "Volume accelerating (top 30% vol change)", family="vol_accel"),
    StateSpec("vol_decelerating", "Volume decelerating (bottom 30% vol change)", family="vol_accel"),
    # Return alone
    StateSpec("high_return", "High return (top 30%)", family="return"),
    StateSpec("low_return", "Low return (bottom 30%)", family="return"),
    # Volume level (for comparison with H447)
    StateSpec("high_vol", "High volume level (top 30%)", family="vol_level"),
    StateSpec("low_vol", "Low volume level (bottom 30%)", family="vol_level"),
    # COMBOS - primary test
    StateSpec("vol_accel_high_return", "Volume accelerating + High return", family="combo", primary=True),
    StateSpec("vol_accel_low_return", "Volume accelerating + Low return", family="combo"),
    StateSpec("vol_decel_high_return", "Volume decelerating + High return", family="combo"),
    StateSpec("vol_decel_low_return", "Volume decelerating + Low return", family="combo"),
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
    
    vol_accel_ic = results[results["name"] == "vol_accelerating"]["avg_ic"].iloc[0] if not results.empty else 0
    vol_decel_ic = results[results["name"] == "vol_decelerating"]["avg_ic"].iloc[0] if not results.empty else 0
    high_vol_ic = results[results["name"] == "high_vol"]["avg_ic"].iloc[0] if not results.empty else 0
    low_vol_ic = results[results["name"] == "low_vol"]["avg_ic"].iloc[0] if not results.empty else 0
    
    combo_accel_high_ic = results[results["name"] == "vol_accel_high_return"]["avg_ic"].iloc[0] if not results.empty else 0
    combo_accel_low_ic = results[results["name"] == "vol_accel_low_return"]["avg_ic"].iloc[0] if not results.empty else 0
    combo_decel_high_ic = results[results["name"] == "vol_decel_high_return"]["avg_ic"].iloc[0] if not results.empty else 0
    combo_decel_low_ic = results[results["name"] == "vol_decel_low_return"]["avg_ic"].iloc[0] if not results.empty else 0
    
    vol_accel_lift = vol_accel_ic - baseline_ic
    vol_decel_lift = vol_decel_ic - baseline_ic
    high_vol_lift = high_vol_ic - baseline_ic
    low_vol_lift = low_vol_ic - baseline_ic
    
    combo_accel_high_lift = combo_accel_high_ic - baseline_ic
    combo_accel_low_lift = combo_accel_low_ic - baseline_ic
    combo_decel_high_lift = combo_decel_high_ic - baseline_ic
    combo_decel_low_lift = combo_decel_low_ic - baseline_ic
    
    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}
    
    # Compare acceleration combos vs level combos
    accel_vs_level_high = combo_accel_high_lift - high_vol_lift
    accel_vs_level_low = combo_accel_low_lift - low_vol_lift
    
    if combo_accel_high_lift > high_vol_lift + 0.01 and combo_accel_high_lift > 0.01:
        decision = "PASSED"
    elif combo_accel_low_lift > low_vol_lift + 0.01 and combo_accel_low_lift > 0.01:
        decision = "PASSED"
    elif abs(accel_vs_level_high) < 0.005 and abs(accel_vs_level_low) < 0.005:
        decision = "FAILED"
    else:
        decision = "MIXED"
    
    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "vol_accelerating_ic": float(vol_accel_ic),
            "vol_decelerating_ic": float(vol_decel_ic),
            "high_vol_ic": float(high_vol_ic),
            "low_vol_ic": float(low_vol_ic),
            "vol_accel_high_return_ic": float(combo_accel_high_ic),
            "vol_accel_low_return_ic": float(combo_accel_low_ic),
            "vol_decel_high_return_ic": float(combo_decel_high_ic),
            "vol_decel_low_return_ic": float(combo_decel_low_ic),
            "vol_accel_lift": float(vol_accel_lift),
            "vol_decel_lift": float(vol_decel_lift),
            "high_vol_lift": float(high_vol_lift),
            "low_vol_lift": float(low_vol_lift),
            "combo_accel_high_lift": float(combo_accel_high_lift),
            "combo_accel_low_lift": float(combo_accel_low_lift),
            "accel_vs_level_high": float(accel_vs_level_high),
            "accel_vs_level_low": float(accel_vs_level_low),
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
    print(f"Volume acceleration combos:")
    print(f"  vol_accel_high_return: {combo_accel_high_ic:.4f} (lift: {combo_accel_high_lift:+.4f})")
    print(f"  vol_accel_low_return: {combo_accel_low_ic:.4f} (lift: {combo_accel_low_lift:+.4f})")
    print(f"Volume level combos (H447 comparison):")
    print(f"  high_vol: {high_vol_ic:.4f} (lift: {high_vol_lift:+.4f})")
    print(f"  low_vol: {low_vol_ic:.4f} (lift: {low_vol_lift:+.4f})")
    print(f"Accel vs Level (high return): {accel_vs_level_high:+.4f}")
    print(f"Accel vs Level (low return): {accel_vs_level_low:+.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()