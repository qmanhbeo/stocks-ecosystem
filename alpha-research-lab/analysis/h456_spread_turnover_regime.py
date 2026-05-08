"""
H456: spread_turnover_regime

Hypothesis: Spread killed as FILTER (S248-S252). Try as REGIME instead: 
Wide spreads = low liquidity/uncertainty. Test C16, C19, C20, S1 IC in 
wide_spread vs tight_spread separately.

First test: spread proxy × turnover regime vs forward IC.
Compare with: Signals without regime gate.

Data: Uses OHLCV from S1 panel as spread proxy (open-close gap).
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


BRANCH_NAME = "spread_turnover_regime"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Spread killed as FILTER (S248-S252). Try as REGIME: "
        "wide spreads = low liquidity/uncertainty. Test signals in "
        "wide_spread vs tight_spread separately."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H456 spread_turnover_regime test")
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
    
    # Load order_stats for vol change and imbalance
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
    
    # Imbalance (H451)
    panel["imbalance_lag1"] = panel.groupby("ticker")["buy_sell_volume_imbalance"].shift(1)
    panel["imbalance_delta"] = panel["buy_sell_volume_imbalance"] - panel["imbalance_lag1"]
    
    # Spread proxy: absolute open-close gap as spread/opaqueness measure
    panel["open_close_gap"] = panel["pct_change"].abs()
    
    panel = panel.dropna(subset=["vol_change", "imbalance_delta"])
    
    # Spread regime (wide vs tight)
    gap_rank = panel.groupby("time", sort=False)["open_close_gap"].rank(method="average", pct=True)
    panel["wide_spread"] = gap_rank >= 0.8
    panel["tight_spread"] = gap_rank <= 0.2
    
    # Turnover (volume) regime
    vol_rank = panel.groupby("time", sort=False)["total_volume"].rank(method="average", pct=True)
    panel["high_turnover"] = vol_rank >= 0.8
    panel["low_turnover"] = vol_rank <= 0.2
    
    # Vol regime (H446)
    vol_change_rank = panel.groupby("time", sort=False)["vol_change"].rank(method="average", pct=True)
    panel["vol_expansion"] = vol_change_rank >= 0.8

    # Imbalance level (H451)
    imbalance_rank = panel.groupby("time", sort=False)["buy_sell_volume_imbalance"].rank(method="average", pct=True)
    panel["buy_heavy"] = imbalance_rank >= 0.8

    # H451 buy_heavy_expansion combo
    panel["buy_heavy_expansion"] = panel["buy_heavy"] & panel["vol_expansion"]

    # Spread × signal combos
    panel["buy_heavy_wide_spread"] = panel["buy_heavy"] & panel["wide_spread"]
    panel["buy_heavy_tight_spread"] = panel["buy_heavy"] & panel["tight_spread"]
    panel["vol_expansion_wide_spread"] = panel["vol_expansion"] & panel["wide_spread"]
    panel["vol_expansion_tight_spread"] = panel["vol_expansion"] & panel["tight_spread"]
    panel["buy_heavy_expansion_wide"] = panel["buy_heavy"] & panel["vol_expansion"] & panel["wide_spread"]
    panel["buy_heavy_expansion_tight"] = panel["buy_heavy"] & panel["vol_expansion"] & panel["tight_spread"]
    
    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    # Spread regime alone
    StateSpec("wide_spread", "Wide spread/tight liquidity (top 20%)", family="spread_regime"),
    StateSpec("tight_spread", "Tight spread/wide liquidity (bottom 20%)", family="spread_regime"),
    # Turnover regime alone
    StateSpec("high_turnover", "High turnover (top 20%)", family="turnover"),
    StateSpec("low_turnover", "Low turnover (bottom 20%)", family="turnover"),
    # Signal alone
    StateSpec("buy_heavy_expansion", "H451: buy-heavy + vol expansion", family="signal"),
    # Signal × spread regime (primary test)
    StateSpec("buy_heavy_wide_spread", "Buy-heavy + Wide spread", family="signal_spread"),
    StateSpec("buy_heavy_tight_spread", "Buy-heavy + Tight spread", family="signal_spread"),
    StateSpec("vol_expansion_wide_spread", "Vol expansion + Wide spread", family="signal_spread"),
    StateSpec("vol_expansion_tight_spread", "Vol expansion + Tight spread", family="signal_spread"),
    StateSpec("buy_heavy_expansion_wide", "Buy-heavy + Vol expansion + Wide spread", family="signal_spread", primary=True),
    StateSpec("buy_heavy_expansion_tight", "Buy-heavy + Vol expansion + Tight spread", family="signal_spread"),
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
    
    # Spread regime
    wide_spread_ic = results[results["name"] == "wide_spread"]["avg_ic"].iloc[0] if not results.empty else 0
    tight_spread_ic = results[results["name"] == "tight_spread"]["avg_ic"].iloc[0] if not results.empty else 0
    
    # Signal alone
    buy_exp_ic = results[results["name"] == "buy_heavy_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    
    # Signal × spread
    buy_wide_ic = results[results["name"] == "buy_heavy_wide_spread"]["avg_ic"].iloc[0] if not results.empty else 0
    buy_tight_ic = results[results["name"] == "buy_heavy_tight_spread"]["avg_ic"].iloc[0] if not results.empty else 0
    vol_wide_ic = results[results["name"] == "vol_expansion_wide_spread"]["avg_ic"].iloc[0] if not results.empty else 0
    vol_tight_ic = results[results["name"] == "vol_expansion_tight_spread"]["avg_ic"].iloc[0] if not results.empty else 0
    buy_exp_wide_ic = results[results["name"] == "buy_heavy_expansion_wide"]["avg_ic"].iloc[0] if not results.empty else 0
    buy_exp_tight_ic = results[results["name"] == "buy_heavy_expansion_tight"]["avg_ic"].iloc[0] if not results.empty else 0
    
    # Lifts
    wide_spread_lift = wide_spread_ic - baseline_ic
    tight_spread_lift = tight_spread_ic - baseline_ic
    buy_wide_lift = buy_wide_ic - baseline_ic
    buy_tight_lift = buy_tight_ic - baseline_ic
    vol_wide_lift = vol_wide_ic - baseline_ic
    vol_tight_lift = vol_tight_ic - baseline_ic
    buy_exp_wide_lift = buy_exp_wide_ic - baseline_ic
    buy_exp_tight_lift = buy_exp_tight_ic - baseline_ic
    
    # Spread regime differences
    vol_spread_diff = vol_wide_lift - vol_tight_lift
    buy_spread_diff = buy_exp_wide_lift - buy_exp_tight_lift
    
    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}
    
    # Hypothesis: signals work DIFFERENTLY in wide vs tight spread
    if abs(vol_spread_diff) > 0.02 or abs(buy_spread_diff) > 0.02:
        decision = "PASSED"
    elif buy_exp_wide_lift > buy_exp_tight_lift + 0.01:
        decision = "MIXED"
    else:
        decision = "FAILED"
    
    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            # Spread regime
            "wide_spread_ic": float(wide_spread_ic),
            "tight_spread_ic": float(tight_spread_ic),
            "wide_spread_lift": float(wide_spread_lift),
            "tight_spread_lift": float(tight_spread_lift),
            # Signal alone
            "buy_heavy_expansion_ic": float(buy_exp_ic),
            # Signal × spread
            "buy_heavy_wide_spread_ic": float(buy_wide_ic),
            "buy_heavy_tight_spread_ic": float(buy_tight_ic),
            "vol_expansion_wide_spread_ic": float(vol_wide_ic),
            "vol_expansion_tight_spread_ic": float(vol_tight_ic),
            "buy_heavy_expansion_wide_ic": float(buy_exp_wide_ic),
            "buy_heavy_expansion_tight_ic": float(buy_exp_tight_ic),
            # Lifts
            "buy_heavy_wide_spread_lift": float(buy_wide_lift),
            "buy_heavy_tight_spread_lift": float(buy_tight_lift),
            "vol_expansion_wide_spread_lift": float(vol_wide_lift),
            "vol_expansion_tight_spread_lift": float(vol_tight_lift),
            "buy_heavy_expansion_wide_lift": float(buy_exp_wide_lift),
            "buy_heavy_expansion_tight_lift": float(buy_exp_tight_lift),
            # Spread differences
            "vol_expansion_spread_diff": float(vol_spread_diff),
            "buy_heavy_expansion_spread_diff": float(buy_spread_diff),
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
    print(f"\nSpread regime:")
    print(f"  wide_spread: {wide_spread_ic:.4f} (lift: {wide_spread_lift:+.4f})")
    print(f"  tight_spread: {tight_spread_ic:.4f} (lift: {tight_spread_lift:+.4f})")
    print(f"\nSignal × Spread:")
    print(f"  buy_heavy_wide_spread: {buy_wide_ic:.4f} (lift: {buy_wide_lift:+.4f})")
    print(f"  buy_heavy_tight_spread: {buy_tight_ic:.4f} (lift: {buy_tight_lift:+.4f})")
    print(f"  buy_heavy_expansion_wide: {buy_exp_wide_ic:.4f} (lift: {buy_exp_wide_lift:+.4f})")
    print(f"  buy_heavy_expansion_tight: {buy_exp_tight_ic:.4f} (lift: {buy_exp_tight_lift:+.4f})")
    print(f"\nSpread differences:")
    print(f"  vol_expansion (wide - tight): {vol_spread_diff:+.4f}")
    print(f"  buy_heavy_expansion (wide - tight): {buy_spread_diff:+.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()