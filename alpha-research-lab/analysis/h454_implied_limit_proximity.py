"""
H454: implied_limit_proximity

Hypothesis: price_change_raw strings encode limit proximity. Near-limit + vol expansion
might signal queue exhaustion (many buyers waiting, vol expanding = stress, reversal).

First test: limit_proximity × vol_regime vs forward IC.
Compare with: Random baseline.

Data: Uses order_stats price_change_raw and computed vol_change.
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


BRANCH_NAME = "implied_limit_proximity"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "price_change_raw strings encode limit proximity. Near-limit + vol expansion "
        "might signal queue exhaustion. Test limit_proximity × vol_regime vs forward IC."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_price_change(s):
    """Parse price_change_raw like '+6.8% (+2,400)' to extract pct value."""
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
    parser = argparse.ArgumentParser(description="H454 implied_limit_proximity test")
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
    
    panel = panel.sort_values(["ticker", "time"])
    
    # Volatility regime
    panel["pct_change_vol"] = panel.groupby("ticker")["pct_change"].transform(
        lambda x: x.rolling(window=5, min_periods=3).std()
    )
    panel["vol_change"] = panel.groupby("ticker")["pct_change_vol"].transform(
        lambda x: x.diff()
    )
    
    panel = panel.dropna(subset=["vol_change"])
    
    # Vol regime
    vol_change_rank = panel.groupby("time", sort=False)["vol_change"].rank(method="average", pct=True)
    panel["vol_expansion"] = vol_change_rank >= 0.8
    panel["vol_contraction"] = vol_change_rank <= 0.2
    
    # Limit proximity: VN market has 7% daily limit
    # Near-limit = stocks close to ceiling/floor
    abs_pct = panel["pct_change"].abs()
    panel["near_limit"] = abs_pct >= 5.0   # Within 2% of 7% limit
    panel["mid_range"] = (abs_pct >= 2.0) & (abs_pct < 5.0)
    panel["low_move"] = abs_pct < 2.0
    
    # Direction (up vs down limit)
    panel["approaching_ceiling"] = (panel["pct_change"] >= 5.0) & (panel["pct_change"] < 7.0)
    panel["at_ceiling"] = panel["pct_change"] >= 7.0
    panel["approaching_floor"] = (panel["pct_change"] <= -5.0) & (panel["pct_change"] > -7.0)
    panel["at_floor"] = panel["pct_change"] <= -7.0
    
    # High volume (proxy for queue pressure)
    volume_rank = panel.groupby("time", sort=False)["total_volume"].rank(method="average", pct=True)
    panel["high_volume"] = volume_rank >= 0.8
    
    # Combos
    panel["near_limit_expansion"] = panel["near_limit"] & panel["vol_expansion"]
    panel["approaching_ceiling_expansion"] = panel["approaching_ceiling"] & panel["vol_expansion"]
    panel["approaching_floor_expansion"] = panel["approaching_floor"] & panel["vol_expansion"]
    panel["near_limit_contraction"] = panel["near_limit"] & panel["vol_contraction"]
    panel["at_limit_expansion"] = (panel["at_ceiling"] | panel["at_floor"]) & panel["vol_expansion"]
    
    # High volume + near limit (queue pressure)
    panel["near_limit_high_vol_expansion"] = panel["near_limit"] & panel["high_volume"] & panel["vol_expansion"]
    
    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    # Vol regime alone
    StateSpec("vol_expansion", "Volatility expanding (top 20%)", family="vol_regime"),
    StateSpec("vol_contraction", "Volatility contracting (bottom 20%)", family="vol_regime"),
    # Limit proximity alone
    StateSpec("near_limit", "Near daily limit (|pct| >= 5%)", family="limit_prox"),
    StateSpec("mid_range", "Mid range (2% <= |pct| < 5%)", family="limit_prox"),
    StateSpec("low_move", "Low move (|pct| < 2%)", family="limit_prox"),
    # Limit direction alone
    StateSpec("approaching_ceiling", "Approaching ceiling (+5% to +7%)", family="limit_dir"),
    StateSpec("approaching_floor", "Approaching floor (-5% to -7%)", family="limit_dir"),
    StateSpec("at_ceiling", "At ceiling (+7%)", family="limit_dir"),
    StateSpec("at_floor", "At floor (-7%)", family="limit_dir"),
    # Limit × vol (primary test)
    StateSpec("near_limit_expansion", "Near limit + Vol expansion", family="limit_vol", primary=True),
    StateSpec("approaching_ceiling_expansion", "Approaching ceiling + Vol expansion", family="limit_vol"),
    StateSpec("approaching_floor_expansion", "Approaching floor + Vol expansion", family="limit_vol"),
    StateSpec("near_limit_contraction", "Near limit + Vol contraction", family="limit_vol"),
    StateSpec("at_limit_expansion", "At limit + Vol expansion", family="limit_vol"),
    # Queue pressure combo
    StateSpec("near_limit_high_vol_expansion", "Near limit + High volume + Vol expansion", family="queue"),
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
    
    # Limit proximity alone
    near_limit_ic = results[results["name"] == "near_limit"]["avg_ic"].iloc[0] if not results.empty else 0
    mid_range_ic = results[results["name"] == "mid_range"]["avg_ic"].iloc[0] if not results.empty else 0
    low_move_ic = results[results["name"] == "low_move"]["avg_ic"].iloc[0] if not results.empty else 0
    near_limit_lift = near_limit_ic - baseline_ic
    
    # Limit × vol combos
    near_limit_exp_ic = results[results["name"] == "near_limit_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    near_limit_cont_ic = results[results["name"] == "near_limit_contraction"]["avg_ic"].iloc[0] if not results.empty else 0
    near_limit_exp_lift = near_limit_exp_ic - baseline_ic
    
    near_limit_high_vol_exp_ic = results[results["name"] == "near_limit_high_vol_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    near_limit_high_vol_exp_lift = near_limit_high_vol_exp_ic - baseline_ic
    
    # Direction × vol
    approach_ceil_exp_ic = results[results["name"] == "approaching_ceiling_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    approach_floor_exp_ic = results[results["name"] == "approaching_floor_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    approach_ceil_exp_lift = approach_ceil_exp_ic - baseline_ic
    approach_floor_exp_lift = approach_floor_exp_ic - baseline_ic
    
    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}
    
    # Hypothesis: near_limit × vol_expansion signals queue exhaustion
    if near_limit_exp_lift > 0.01 and near_limit_exp_lift > near_limit_lift:
        decision = "PASSED"
    elif near_limit_high_vol_exp_lift > 0.01:
        decision = "PASSED"
    elif approach_ceil_exp_lift > 0.01 or approach_floor_exp_lift > 0.01:
        decision = "MIXED"
    else:
        decision = "FAILED"
    
    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            # Limit proximity alone
            "near_limit_ic": float(near_limit_ic),
            "mid_range_ic": float(mid_range_ic),
            "low_move_ic": float(low_move_ic),
            "near_limit_lift": float(near_limit_lift),
            # Limit × vol
            "near_limit_expansion_ic": float(near_limit_exp_ic),
            "near_limit_contraction_ic": float(near_limit_cont_ic),
            "near_limit_expansion_lift": float(near_limit_exp_lift),
            "near_limit_high_vol_expansion_ic": float(near_limit_high_vol_exp_ic),
            "near_limit_high_vol_expansion_lift": float(near_limit_high_vol_exp_lift),
            # Direction × vol
            "approaching_ceiling_expansion_ic": float(approach_ceil_exp_ic),
            "approaching_floor_expansion_ic": float(approach_floor_exp_ic),
            "approaching_ceiling_expansion_lift": float(approach_ceil_exp_lift),
            "approaching_floor_expansion_lift": float(approach_floor_exp_lift),
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
    print(f"\nLimit proximity alone:")
    print(f"  near_limit: {near_limit_ic:.4f} (lift: {near_limit_lift:+.4f})")
    print(f"  mid_range: {mid_range_ic:.4f}")
    print(f"  low_move: {low_move_ic:.4f}")
    print(f"\nLimit × vol regime:")
    print(f"  near_limit_expansion: {near_limit_exp_ic:.4f} (lift: {near_limit_exp_lift:+.4f})")
    print(f"  near_limit_contraction: {near_limit_cont_ic:.4f}")
    print(f"  near_limit_high_vol_expansion: {near_limit_high_vol_exp_ic:.4f} (lift: {near_limit_high_vol_exp_lift:+.4f})")
    print(f"\nDirection × vol:")
    print(f"  approaching_ceiling_expansion: {approach_ceil_exp_ic:.4f} (lift: {approach_ceil_exp_lift:+.4f})")
    print(f"  approaching_floor_expansion: {approach_floor_exp_ic:.4f} (lift: {approach_floor_exp_lift:+.4f})")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()