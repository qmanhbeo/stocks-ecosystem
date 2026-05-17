"""
H107: Signal Order as Hidden State

Hypothesis: Does WHICH signal fires FIRST matter? C23→C24 transition might indicate 
different demand than C24→C23. Source: F445, H507 (onset state).

Test: signal_sequence (first signal detected) vs signal_count (just count)

Pass criterion: First signal matters - any first-signal state beats composite_2+ by +0.01
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys
import re

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


BRANCH_NAME = "h107_signal_order_hidden_state"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Signal Order as Hidden State: Does WHICH signal fires FIRST matter? "
        "C23→C24 vs C24→C23 might indicate different hidden demand. "
        "Test signal_sequence (first signal detected) vs signal_count (just count)."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=100,
    min_phase_rows=100,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H107: Signal Order as Hidden State")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--order-stats-path", type=str,
                        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    return parser.parse_args()


def compute_amihud(df):
    """Compute Amihud illiquidity: |return| / (volume * price) in billions VND."""
    if 'close' not in df.columns or 'volume' not in df.columns:
        return df
    df = df.copy()
    if 'ticker' in df.columns:
        df['daily_return'] = df.groupby('ticker')['close'].pct_change()
    else:
        df['daily_return'] = df['close'].pct_change()
    df['daily_return_abs'] = df['daily_return'].abs()
    df['turnover'] = df['close'] * df['volume'] / 1e9
    df['amihud'] = df['daily_return_abs'] / (df['turnover'] + 1e-9)
    return df


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )

    # Load OHLCV for Amihud (C23)
    stock_dir = Path("/home/manh/stocks-ecosystem/data/stock")
    ohlcv_dfs = []
    for f in stock_dir.glob("gia_lich_su_*_1D.parquet"):
        try:
            df = pd.read_parquet(f)
            ticker = f.stem.replace("gia_lich_su_", "").replace("_1D", "")
            df["ticker"] = ticker
            ohlcv_dfs.append(df)
        except:
            continue

    if ohlcv_dfs:
        ohlcv = pd.concat(ohlcv_dfs, ignore_index=True)
        ohlcv = ohlcv.rename(columns={"date": "time"})
        ohlcv["time"] = pd.to_datetime(ohlcv["time"])
        ohlcv = ohlcv[ohlcv["time"].dt.year <= 2025]
        ohlcv = compute_amihud(ohlcv)

        ohlcv = ohlcv.sort_values(["ticker", "time"])
        ohlcv["amihud_20d_avg"] = ohlcv.groupby("ticker")["amihud"].transform(
            lambda x: x.rolling(window=20, min_periods=10).mean()
        )

        panel = panel.merge(
            ohlcv[["time", "ticker", "amihud_20d_avg"]],
            on=["time", "ticker"],
            how="left",
        )
    else:
        panel["amihud_20d_avg"] = np.nan

    # Load order_stats for vol regime and signals
    order_stats = pd.read_parquet(args.order_stats_path)
    order_stats = order_stats.rename(columns={"date": "time"})
    order_stats["time"] = pd.to_datetime(order_stats["time"])
    order_stats = order_stats[order_stats["time"].dt.year <= 2025]

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

    panel = panel.merge(
        order_stats[["time", "ticker", "pct_change", "total_volume", "buy_order_volume", "sell_order_volume"]],
        on=["time", "ticker"],
        how="left",
    )

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

    # Vol regime (top 20% = expansion)
    vol_change_rank = panel.groupby("time", sort=False)["vol_change"].rank(method="average", pct=True)
    panel["vol_expansion"] = vol_change_rank >= 0.8

    # Amihud quintiles (high = illiquid)
    amihud_rank = panel.groupby("time", sort=False)["amihud_20d_avg"].rank(method="average", pct=True)
    panel["high_illiq"] = amihud_rank >= 0.8

    # Buy-sell imbalance
    panel["buy_sell_imbalance"] = (
        (panel["buy_order_volume"] - panel["sell_order_volume"]) /
        (panel["buy_order_volume"] + panel["sell_order_volume"] + 1)
    )
    panel = panel.dropna(subset=["buy_sell_imbalance"])
    imbalance_rank = panel.groupby("time", sort=False)["buy_sell_imbalance"].rank(method="average", pct=True)
    panel["buy_heavy"] = imbalance_rank >= 0.8

    # Individual signal flags (C23/C24/C25/C26 from F445)
    panel["c23_illiq_expansion"] = panel["high_illiq"] & panel["vol_expansion"]
    panel["c24_ceiling_expansion"] = (panel["pct_change"] >= 5.0) & panel["vol_expansion"]
    panel["c25_vwap_expansion"] = (panel["pct_change"] <= -2.0) & panel["vol_expansion"]
    panel["c26_buy_heavy_illiq_exp"] = panel["buy_heavy"] & panel["high_illiq"] & panel["vol_expansion"]

    # Count signals per ticker-day
    panel["signal_count"] = (
        panel["c23_illiq_expansion"].astype(int) +
        panel["c24_ceiling_expansion"].astype(int) +
        panel["c25_vwap_expansion"].astype(int) +
        panel["c26_buy_heavy_illiq_exp"].astype(int)
    )

    # Composite signal: 2+ signals (AND of F445)
    panel["composite_2plus"] = panel["signal_count"] >= 2

    # For multi-signal stocks, identify which signal fired FIRST (earliest in rolling window)
    # Look back 5 days to find which signal appeared first
    panel = panel.sort_values(["ticker", "time"])
    
    # Create lagged signal indicators
    for sig in ["c23_illiq_expansion", "c24_ceiling_expansion", "c25_vwap_expansion", "c26_buy_heavy_illiq_exp"]:
        for lag in range(1, 6):
            panel[f"{sig}_lag{lag}"] = panel.groupby("ticker")[sig].shift(lag)
    
    # For stocks with 2+ signals, determine which came first
    def get_first_signal(row):
        if row["composite_2plus"]:
            signals = []
            for sig in ["c23_illiq_expansion", "c24_ceiling_expansion", "c25_vwap_expansion", "c26_buy_heavy_illiq_exp"]:
                if row[sig]:
                    signals.append(sig)
            if len(signals) >= 2:
                # Find earliest
                for lag in range(1, 6):
                    for sig in signals:
                        if row.get(f"{sig}_lag{lag}", False):
                            return sig.replace("_illiq_expansion", "").replace("_ceiling_expansion", "").replace("_vwap_expansion", "").replace("_buy_heavy_illiq_exp", "")
        return None
    
    # Apply to composite_2+ rows
    panel["first_signal"] = panel.apply(get_first_signal, axis=1)
    
    # State specs for first signal
    panel["first_c23"] = (panel["first_signal"] == "c23")
    panel["first_c24"] = (panel["first_signal"] == "c24")
    panel["first_c25"] = (panel["first_signal"] == "c25")
    panel["first_c26"] = (panel["first_signal"] == "c26")
    panel["first_any"] = panel["first_signal"].notna()
    
    # Also compute: any signal vs composite_2+ (baseline from F445)
    panel["any_signal"] = panel["signal_count"] >= 1
    
    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("any_signal", "Any signal firing (1+ signals)", family="signal"),
    StateSpec("composite_2plus", "2+ signals firing (F445 baseline)", family="composite"),
    StateSpec("first_any", "First signal detected (2+ signals)", family="sequence"),
    StateSpec("first_c23", "C23 fired first (among multi-signal)", family="sequence"),
    StateSpec("first_c24", "C24 fired first (among multi-signal)", family="sequence"),
    StateSpec("first_c25", "C25 fired first (among multi-signal)", family="sequence"),
    StateSpec("first_c26", "C26 fired first (among multi-signal)", family="sequence"),
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

    # Get IC values
    composite_row = results[results["name"] == "composite_2plus"]
    first_any_row = results[results["name"] == "first_any"]
    first_c23_row = results[results["name"] == "first_c23"]
    first_c24_row = results[results["name"] == "first_c24"]
    first_c25_row = results[results["name"] == "first_c25"]
    first_c26_row = results[results["name"] == "first_c26"]
    any_signal_row = results[results["name"] == "any_signal"]

    composite_ic = composite_row["avg_ic"].iloc[0] if not composite_row.empty else 0
    first_any_ic = first_any_row["avg_ic"].iloc[0] if not first_any_row.empty else 0
    first_c23_ic = first_c23_row["avg_ic"].iloc[0] if not first_c23_row.empty else 0
    first_c24_ic = first_c24_row["avg_ic"].iloc[0] if not first_c24_row.empty else 0
    first_c25_ic = first_c25_row["avg_ic"].iloc[0] if not first_c25_row.empty else 0
    first_c26_ic = first_c26_row["avg_ic"].iloc[0] if not first_c26_row.empty else 0
    any_signal_ic = any_signal_row["avg_ic"].iloc[0] if not any_signal_row.empty else 0

    # F445 baseline: composite_2+ = 0.2445
    f445_baseline = 0.2445

    # Pass if first_any beats composite_2+ by +0.01
    lift_vs_composite = first_any_ic - composite_ic
    best_first = max([first_c23_ic, first_c24_ic, first_c25_ic, first_c26_ic])
    best_lift = best_first - composite_ic if best_first > 0 else 0

    if lift_vs_composite > 0.01 or best_lift > 0.01:
        decision = "PASSED"
    elif lift_vs_composite > 0 or best_lift > 0:
        decision = "MIXED"
    else:
        decision = "FAILED"

    # Check row counts for sparsity
    first_any_rows = first_any_row["pooled_rows"].iloc[0] if not first_any_row.empty else 0
    composite_rows = composite_row["pooled_rows"].iloc[0] if not composite_row.empty else 0

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "composite_2plus_ic": float(composite_ic),
            "any_signal_ic": float(any_signal_ic),
            "first_any_ic": float(first_any_ic),
            "first_c23_ic": float(first_c23_ic),
            "first_c24_ic": float(first_c24_ic),
            "first_c25_ic": float(first_c25_ic),
            "first_c26_ic": float(first_c26_ic),
            "lift_vs_composite": float(lift_vs_composite),
            "best_lift": float(best_lift),
            "f445_baseline": f445_baseline,
            "first_any_rows": int(first_any_rows),
            "composite_rows": int(composite_rows),
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
    print(f"decision: {decision}")
    print(f"first_any_ic={first_any_ic:.4f} vs composite={composite_ic:.4f}, lift={lift_vs_composite:.4f}")
    print(f"best_first={best_lift:.4f}, first_any_rows={first_any_rows}, composite_rows={composite_rows}")
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()