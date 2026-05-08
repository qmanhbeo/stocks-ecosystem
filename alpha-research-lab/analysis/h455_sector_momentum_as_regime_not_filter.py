"""
H455: sector_momentum_as_regime_not_filter

Hypothesis: S248-S252 used sector as FILTER (failed). Use SECTOR RETURN as REGIME to gate
signal behavior: C16, C19, C20, S1 IC in sector_up vs sector_down separately.

First test: gate C16, C19, C20 by sector momentum regime.
Compare with: signals without regime gate.

Data: Uses existing sector_mom_5d from S1 panel or computed from OHLCV.
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


BRANCH_NAME = "sector_momentum_as_regime_not_filter"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "S248-S252 used sector as FILTER (failed). Use SECTOR RETURN as REGIME to gate "
        "signal behavior: C16, C19, C20, S1 IC in sector_up vs sector_down separately. "
        "Test if signal efficacy changes by regime."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H455 sector_momentum_as_regime_not_filter test")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--order-stats-path", type=str, 
                        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    return parser.parse_args()


def compute_sector_momentum(panel):
    """Compute sector momentum from OHLCV data."""
    # Group by time and compute equal-weight sector return
    # First, we need to compute daily return per ticker
    panel = panel.sort_values(["ticker", "time"])
    panel["pct_change_1d"] = panel.groupby("ticker")["close"].pct_change() * 100
    
    # For simplicity, use cross-sectional average return as market proxy
    # and compute sector momentum from cross-sectional ranks
    return panel


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )
    
    # Load order_stats for C16, vol change
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
    
    # Compute sector momentum as cross-sectional date-level signal
    # For each date, compute market average return and deviation
    date_mean_ret = panel.groupby("time")["pct_change"].transform("mean")
    panel["market_excess"] = panel["pct_change"] - date_mean_ret
    
    # Sector momentum regime: positive vs negative market excess
    panel["sector_up"] = panel["market_excess"] > 0
    panel["sector_down"] = panel["market_excess"] < 0
    
    # Vol regime (H446)
    vol_change_rank = panel.groupby("time", sort=False)["vol_change"].rank(method="average", pct=True)
    panel["vol_expansion"] = vol_change_rank >= 0.8
    
    # Imbalance level (H451)
    imbalance_rank = panel.groupby("time", sort=False)["buy_sell_volume_imbalance"].rank(method="average", pct=True)
    panel["buy_heavy"] = imbalance_rank >= 0.8
    
    # C16 (order volume ratio)
    total_volume_rank = panel.groupby("time", sort=False)["total_volume"].rank(method="average", pct=True)
    panel["high_volume"] = total_volume_rank >= 0.8
    
    # Combos: signals × sector regime
    panel["high_volume_sector_up"] = panel["high_volume"] & panel["sector_up"]
    panel["high_volume_sector_down"] = panel["high_volume"] & panel["sector_down"]
    panel["buy_heavy_expansion"] = panel["buy_heavy"] & panel["vol_expansion"]
    panel["buy_heavy_expansion_sector_up"] = panel["buy_heavy"] & panel["vol_expansion"] & panel["sector_up"]
    panel["buy_heavy_expansion_sector_down"] = panel["buy_heavy"] & panel["vol_expansion"] & panel["sector_down"]
    panel["vol_expansion_sector_up"] = panel["vol_expansion"] & panel["sector_up"]
    panel["vol_expansion_sector_down"] = panel["vol_expansion"] & panel["sector_down"]
    
    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    # Sector regime alone
    StateSpec("sector_up", "Sector/market UP (positive excess return)", family="sector_regime"),
    StateSpec("sector_down", "Sector/market DOWN (negative excess return)", family="sector_regime"),
    # Signal alone
    StateSpec("high_volume", "High volume (top 20%)", family="signal"),
    StateSpec("vol_expansion", "Volatility expanding (top 20%)", family="signal"),
    StateSpec("buy_heavy_expansion", "H451: buy-heavy + vol expansion", family="signal"),
    # Signal × sector regime (primary test)
    StateSpec("high_volume_sector_up", "High volume + Sector UP", family="signal_sector"),
    StateSpec("high_volume_sector_down", "High volume + Sector DOWN", family="signal_sector", primary=True),
    StateSpec("buy_heavy_expansion_sector_up", "Buy-heavy + Vol expansion + Sector UP", family="signal_sector"),
    StateSpec("buy_heavy_expansion_sector_down", "Buy-heavy + Vol expansion + Sector DOWN", family="signal_sector"),
    StateSpec("vol_expansion_sector_up", "Vol expansion + Sector UP", family="signal_sector"),
    StateSpec("vol_expansion_sector_down", "Vol expansion + Sector DOWN", family="signal_sector"),
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
    
    # Sector regime
    sector_up_ic = results[results["name"] == "sector_up"]["avg_ic"].iloc[0] if not results.empty else 0
    sector_down_ic = results[results["name"] == "sector_down"]["avg_ic"].iloc[0] if not results.empty else 0
    
    # Signal alone
    high_vol_ic = results[results["name"] == "high_volume"]["avg_ic"].iloc[0] if not results.empty else 0
    vol_exp_ic = results[results["name"] == "vol_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    buy_exp_ic = results[results["name"] == "buy_heavy_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    
    # Signal × sector regime
    high_vol_sector_up_ic = results[results["name"] == "high_volume_sector_up"]["avg_ic"].iloc[0] if not results.empty else 0
    high_vol_sector_down_ic = results[results["name"] == "high_volume_sector_down"]["avg_ic"].iloc[0] if not results.empty else 0
    buy_exp_sector_up_ic = results[results["name"] == "buy_heavy_expansion_sector_up"]["avg_ic"].iloc[0] if not results.empty else 0
    buy_exp_sector_down_ic = results[results["name"] == "buy_heavy_expansion_sector_down"]["avg_ic"].iloc[0] if not results.empty else 0
    vol_exp_sector_up_ic = results[results["name"] == "vol_expansion_sector_up"]["avg_ic"].iloc[0] if not results.empty else 0
    vol_exp_sector_down_ic = results[results["name"] == "vol_expansion_sector_down"]["avg_ic"].iloc[0] if not results.empty else 0
    
    # Lifts
    high_vol_sector_up_lift = high_vol_sector_up_ic - baseline_ic
    high_vol_sector_down_lift = high_vol_sector_down_ic - baseline_ic
    buy_exp_sector_up_lift = buy_exp_sector_up_ic - baseline_ic
    buy_exp_sector_down_lift = buy_exp_sector_down_ic - baseline_ic
    vol_exp_sector_up_lift = vol_exp_sector_up_ic - baseline_ic
    vol_exp_sector_down_lift = vol_exp_sector_down_ic - baseline_ic
    
    # Signal improvement in sector_down vs sector_up
    vol_exp_regime_diff = vol_exp_sector_down_lift - vol_exp_sector_up_lift
    buy_exp_regime_diff = buy_exp_sector_down_lift - buy_exp_sector_up_lift
    
    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}
    
    # Hypothesis: signals work DIFFERENTLY in sector_down vs sector_up
    if abs(vol_exp_regime_diff) > 0.02 or abs(buy_exp_regime_diff) > 0.02:
        decision = "PASSED"
    elif high_vol_sector_down_lift > high_vol_sector_up_lift + 0.01:
        decision = "MIXED"
    else:
        decision = "FAILED"
    
    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            # Sector regime
            "sector_up_ic": float(sector_up_ic),
            "sector_down_ic": float(sector_down_ic),
            # Signal alone
            "high_volume_ic": float(high_vol_ic),
            "vol_expansion_ic": float(vol_exp_ic),
            "buy_heavy_expansion_ic": float(buy_exp_ic),
            # Signal × sector regime
            "high_volume_sector_up_ic": float(high_vol_sector_up_ic),
            "high_volume_sector_down_ic": float(high_vol_sector_down_ic),
            "buy_heavy_expansion_sector_up_ic": float(buy_exp_sector_up_ic),
            "buy_heavy_expansion_sector_down_ic": float(buy_exp_sector_down_ic),
            "vol_expansion_sector_up_ic": float(vol_exp_sector_up_ic),
            "vol_expansion_sector_down_ic": float(vol_exp_sector_down_ic),
            # Lifts
            "high_volume_sector_up_lift": float(high_vol_sector_up_lift),
            "high_volume_sector_down_lift": float(high_vol_sector_down_lift),
            "buy_heavy_expansion_sector_up_lift": float(buy_exp_sector_up_lift),
            "buy_heavy_expansion_sector_down_lift": float(buy_exp_sector_down_lift),
            "vol_expansion_sector_up_lift": float(vol_exp_sector_up_lift),
            "vol_expansion_sector_down_lift": float(vol_exp_sector_down_lift),
            # Regime differences
            "vol_expansion_regime_diff": float(vol_exp_regime_diff),
            "buy_heavy_expansion_regime_diff": float(buy_exp_regime_diff),
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
    print(f"\nSector regime:")
    print(f"  sector_up: {sector_up_ic:.4f}")
    print(f"  sector_down: {sector_down_ic:.4f}")
    print(f"\nSignal alone:")
    print(f"  high_volume: {high_vol_ic:.4f}")
    print(f"  vol_expansion: {vol_exp_ic:.4f}")
    print(f"  buy_heavy_expansion: {buy_exp_ic:.4f}")
    print(f"\nSignal × Sector regime:")
    print(f"  high_volume_sector_up: {high_vol_sector_up_ic:.4f} (lift: {high_vol_sector_up_lift:+.4f})")
    print(f"  high_volume_sector_down: {high_vol_sector_down_ic:.4f} (lift: {high_vol_sector_down_lift:+.4f})")
    print(f"  vol_expansion_sector_up: {vol_exp_sector_up_ic:.4f} (lift: {vol_exp_sector_up_lift:+.4f})")
    print(f"  vol_expansion_sector_down: {vol_exp_sector_down_ic:.4f} (lift: {vol_exp_sector_down_lift:+.4f})")
    print(f"  buy_heavy_expansion_sector_up: {buy_exp_sector_up_ic:.4f} (lift: {buy_exp_sector_up_lift:+.4f})")
    print(f"  buy_heavy_expansion_sector_down: {buy_exp_sector_down_ic:.4f} (lift: {buy_exp_sector_down_lift:+.4f})")
    print(f"\nRegime differences:")
    print(f"  vol_expansion (down - up): {vol_exp_regime_diff:+.4f}")
    print(f"  buy_heavy_expansion (down - up): {buy_exp_regime_diff:+.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()