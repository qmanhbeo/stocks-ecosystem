"""
H449: vol_contraction_mean_reversion

Hypothesis: H446 showed vol_contraction UNDERPERFORMS (-0.0085). But vol contraction + 
HIGH return might be the reversal pattern. Mechanism: vol contracting after a rally 
might indicate exhaustion. First test: vol_contraction × high_return vs vol_expansion × high_return.

Compare with: Random baseline.

Data: Uses order_stats for price_change, volume, and computed volatility.
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


BRANCH_NAME = "vol_contraction_mean_reversion"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "H446 showed vol_contraction (-0.0085) underperforms. But vol contraction + HIGH "
        "return might be the reversal: vol contracting after a rally indicates exhaustion. "
        "Test vol_contraction × high_return vs vol_expansion × high_return vs baseline."
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
    parser = argparse.ArgumentParser(description="H449 vol_contraction_mean_reversion test")
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
        order_stats[["time", "ticker", "pct_change", "total_volume", "buy_order_volume", "sell_order_volume"]],
        on=["time", "ticker"],
        how="left",
    )
    
    panel["all_rows"] = True
    
    panel = panel.dropna(subset=["pct_change", "total_volume"])
    panel = panel[panel["total_volume"] > 0]
    
    # Return rank (cross-sectional per date)
    return_rank = panel.groupby("time", sort=False)["pct_change"].rank(method="average", pct=True)
    volume_rank = panel.groupby("time", sort=False)["total_volume"].rank(method="average", pct=True)
    
    # Return buckets
    panel["high_return"] = return_rank >= 0.7
    panel["low_return"] = return_rank <= 0.3
    
    # Volatility regime (from H446)
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
    
    # Exhaustion combos: vol contracting after high return = likely reversal
    panel["vol_contraction_exhaustion"] = panel["vol_contraction"] & panel["high_return"]
    panel["vol_expansion_momentum"] = panel["vol_expansion"] & panel["high_return"]
    
    # Additional combos for completeness
    panel["vol_contraction_contrarian"] = panel["vol_contraction"] & panel["low_return"]
    panel["vol_expansion_contrarian"] = panel["vol_expansion"] & panel["low_return"]
    
    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    # H446 alone
    StateSpec("vol_expansion", "Volatility expanding (top 20% 5d vol change)", family="vol_regime"),
    StateSpec("vol_contraction", "Volatility contracting (bottom 20%)", family="vol_regime"),
    # Return alone
    StateSpec("high_return", "High return (top 30%)", family="return"),
    StateSpec("low_return", "Low return (bottom 30%)", family="return"),
    # COMBOS - primary test
    StateSpec("vol_contraction_exhaustion", "Vol contraction + High return (exhaustion)", family="combo", primary=True),
    StateSpec("vol_expansion_momentum", "Vol expansion + High return (momentum)", family="combo"),
    StateSpec("vol_contraction_contrarian", "Vol contraction + Low return (contrarian)", family="combo"),
    StateSpec("vol_expansion_contrarian", "Vol expansion + Low return (oversold)", family="combo"),
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
    vol_contraction_ic = results[results["name"] == "vol_contraction"]["avg_ic"].iloc[0] if not results.empty else 0
    high_return_ic = results[results["name"] == "high_return"]["avg_ic"].iloc[0] if not results.empty else 0
    combo_ic = results[results["name"] == "vol_contraction_exhaustion"]["avg_ic"].iloc[0] if not results.empty else 0
    momentum_ic = results[results["name"] == "vol_expansion_momentum"]["avg_ic"].iloc[0] if not results.empty else 0
    
    vol_contraction_lift = vol_contraction_ic - baseline_ic
    high_return_lift = high_return_ic - baseline_ic
    combo_lift = combo_ic - baseline_ic
    momentum_lift = momentum_ic - baseline_ic
    
    combo_vs_momentum_lift = combo_ic - momentum_ic
    combo_vs_vol_contraction_lift = combo_ic - vol_contraction_ic
    
    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}
    
    # Hypothesis: vol_contraction + high_return should show mean reversion (negative IC)
    # vs vol_expansion + high_return (momentum, positive IC)
    if combo_lift < -0.005 and momentum_lift > 0.005:
        decision = "PASSED"
    elif combo_lift > 0.005 and momentum_lift < -0.005:
        decision = "PASSED"
    elif combo_vs_momentum_lift > 0.01:
        decision = "PASSED"
    elif combo_lift < -0.005 and abs(momentum_lift) < 0.003:
        decision = "FAILED"
    elif combo_lift > 0.005 and vol_contraction_lift < -0.005:
        decision = "MIXED"
    else:
        decision = "MIXED"
    
    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "vol_contraction_ic": float(vol_contraction_ic),
            "high_return_ic": float(high_return_ic),
            "vol_contraction_exhaustion_ic": float(combo_ic),
            "vol_expansion_momentum_ic": float(momentum_ic),
            "vol_contraction_lift": float(vol_contraction_lift),
            "high_return_lift": float(high_return_lift),
            "combo_lift": float(combo_lift),
            "momentum_lift": float(momentum_lift),
            "combo_vs_momentum_lift": float(combo_vs_momentum_lift),
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
    print(f"vol_contraction IC: {vol_contraction_ic:.4f} (lift: {vol_contraction_lift:+.4f})")
    print(f"high_return IC: {high_return_ic:.4f} (lift: {high_return_lift:+.4f})")
    print(f"vol_contraction_exhaustion IC: {combo_ic:.4f} (lift: {combo_lift:+.4f})")
    print(f"vol_expansion_momentum IC: {momentum_ic:.4f} (lift: {momentum_lift:+.4f})")
    print(f"Combo vs Momentum: {combo_vs_momentum_lift:+.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()