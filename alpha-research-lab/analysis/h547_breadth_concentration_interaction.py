"""
H547: breadth_concentration_interaction

Hypothesis: H543 found composite×low_breadth is the strongest signal (IC=0.2364).
Now test if signal CONCENTRATION (top-N share of signal mass) adds value on top of breadth.
- When market breadth is low AND signal mass is concentrated among top-5, 
  the signal should be stronger than low-breadth alone.
- H525 showed low breadth = stronger signal.
- H399 partially explored volume concentration, but breadth×concentration untested.

Prior results:
- H543: composite×low_breadth IC=0.2364 (+0.1066 vs baseline) - STRONGEST
- H525: low breadth (0.1454) > high breadth (0.1149)
- H530: continuous weighting FAILED, binary filter works better
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


BRANCH_NAME = "breadth_concentration_interaction"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "H543 found composite×low_breadth is strongest (IC=0.2364). "
        "Now test if signal CONCENTRATION (top-5 share of S1 mass) adds value on top of breadth filter. "
        "Low breadth + concentrated signal should be stronger than low breadth alone."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H547 breadth_concentration_interaction test")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--order-stats-path", type=str,
                        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")))
    parser.add_argument("--ohlcv-path", type=str,
                        default=str(data_path("stock/gia_lich_su_hose_1D.parquet")))
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

    # C23: high_illiq × vol_expansion (Amihud illiquidity regime)
    panel["c23_illiq_expansion"] = panel["high_illiq"] & panel["vol_expansion"]

    # C24: ceiling count (price hitting +7% limit)
    panel["ceiling_proxy"] = panel["pct_change"] >= 5.0
    panel["c24_ceiling_expansion"] = panel["ceiling_proxy"] & panel["vol_expansion"]

    # C25: VWAP deviation proxy
    panel["vwap_below_proxy"] = panel["pct_change"] <= -2.0
    panel["c25_vwap_expansion"] = panel["vwap_below_proxy"] & panel["vol_expansion"]

    # C26: buy_heavy × illiq × vol_expansion
    panel["c26_buy_heavy_illiq_exp"] = panel["buy_heavy"] & panel["high_illiq"] & panel["vol_expansion"]

    # Composite: OR of any C23/C24/C25/C26 (same as H543)
    panel["composite_signal"] = (
        panel["c23_illiq_expansion"] |
        panel["c24_ceiling_expansion"] |
        panel["c25_vwap_expansion"] |
        panel["c26_buy_heavy_illiq_exp"]
    )

    # BREADTH: count of active TICKERS (not rows) per date
    active_tickers_per_date = panel[panel["composite_signal"]].groupby("time")["ticker"].nunique().reset_index()
    active_tickers_per_date.columns = ["time", "active_ticker_count"]

    total_tickers_per_date = panel.groupby("time")["ticker"].nunique().reset_index()
    total_tickers_per_date.columns = ["time", "total_ticker_count"]

    breadth_df = active_tickers_per_date.merge(total_tickers_per_date, on="time", how="outer")
    breadth_df["total_ticker_count"] = breadth_df["total_ticker_count"].fillna(1)
    breadth_df["active_ticker_count"] = breadth_df["active_ticker_count"].fillna(0)
    breadth_df["breadth_fraction"] = breadth_df["active_ticker_count"] / breadth_df["total_ticker_count"]

    panel = panel.merge(breadth_df[["time", "breadth_fraction"]], on="time", how="left")
    panel["breadth_fraction"] = panel["breadth_fraction"].fillna(0)

    # Binary low_breadth filter (bottom 20% - same as H529/H543)
    date_breadth = panel.groupby("time")["breadth_fraction"].first().reset_index()
    date_breadth["breadth_rank"] = date_breadth["breadth_fraction"].rank(method="average", pct=True)
    date_breadth["low_breadth"] = date_breadth["breadth_rank"] <= 0.2

    panel = panel.merge(date_breadth[["time", "low_breadth"]], on="time", how="left", suffixes=("_old", ""))
    if "low_breadth_old" in panel.columns:
        panel["low_breadth"] = panel["low_breadth"].fillna(panel["low_breadth_old"])
        panel = panel.drop(columns=["low_breadth_old"])

    # Composite × low_breadth (H543 winning state)
    panel["composite_low_breadth"] = panel["composite_signal"] & panel["low_breadth"]

    # CONCENTRATION: on low_breadth dates, compute top-5 share of S1 mass
    # Concentration = sum of S1 scores for top-5 / sum of S1 scores for all
    # High concentration = top-5 hold most of the signal mass
    # Split into concentrated (top 5 >= 50% of mass) vs distributed
    
    panel = panel.sort_values(["time", S1_SCORE_COL], ascending=[True, False])
    
    # For each date, compute total S1 mass and top-5 S1 mass
    def compute_concentration(group):
        total_mass = group[S1_SCORE_COL].sum()
        if total_mass == 0:
            return np.nan
        top5_mass = group[S1_SCORE_COL].head(5).sum()
        return top5_mass / total_mass if total_mass > 0 else np.nan
    
    date_concentration = panel.groupby("time").apply(compute_concentration).reset_index()
    date_concentration.columns = ["time", "top5_concentration"]
    
    # Concentration quintiles: Q1=low (distributed), Q5=high (concentrated)
    date_concentration["concentration_rank"] = date_concentration["top5_concentration"].rank(method="average", pct=True)
    date_concentration["high_concentration"] = date_concentration["concentration_rank"] >= 0.6
    date_concentration["low_concentration"] = date_concentration["concentration_rank"] <= 0.4
    
    panel = panel.merge(date_concentration[["time", "top5_concentration", "high_concentration", "low_concentration"]], 
                        on="time", how="left")
    
    # Concentration × breadth interaction states
    panel["concentrated_low_breadth"] = panel["composite_signal"] & panel["low_breadth"] & panel["high_concentration"]
    panel["distributed_low_breadth"] = panel["composite_signal"] & panel["low_breadth"] & panel["low_concentration"]
    
    panel["all_rows"] = True

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    # Baseline: low_breadth filter (H529/H543)
    StateSpec("low_breadth", "Binary low breadth filter (bottom 20%)", family="breadth_filter"),
    StateSpec("composite_low_breadth", "Composite on low breadth dates (H543 winner)", family="breadth_composite"),
    # Concentration on low breadth
    StateSpec("concentrated_low_breadth", "Composite on low breadth + high concentration", family="breadth_concentration"),
    StateSpec("distributed_low_breadth", "Composite on low breadth + low concentration", family="breadth_concentration"),
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
    low_breadth_ic = results[results["name"] == "low_breadth"]["avg_ic"].iloc[0] if not results.empty else 0
    composite_low_breadth_ic = results[results["name"] == "composite_low_breadth"]["avg_ic"].iloc[0] if not results.empty else 0
    concentrated_ic = results[results["name"] == "concentrated_low_breadth"]["avg_ic"].iloc[0] if not results.empty else 0
    distributed_ic = results[results["name"] == "distributed_low_breadth"]["avg_ic"].iloc[0] if not results.empty else 0

    baseline_lift = 0
    low_breadth_lift = low_breadth_ic - baseline_ic
    composite_lift = composite_low_breadth_ic - baseline_ic
    concentrated_lift = concentrated_ic - baseline_ic
    distributed_lift = distributed_ic - baseline_ic

    # Decision: Does concentration add value on top of breadth?
    # H543: composite_low_breadth IC=0.2364 (+0.1066)
    # Test if concentrated beats distributed
    concentration_lift = concentrated_lift - distributed_lift
    
    if concentrated_lift > composite_lift + 0.005:
        decision = "PASSED"
    elif concentrated_lift > 0.01 and concentrated_lift > distributed_lift:
        decision = "MIXED"
    elif concentrated_lift > 0.01:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "low_breadth_ic": float(low_breadth_ic),
            "low_breadth_lift": float(low_breadth_lift),
            "composite_low_breadth_ic": float(composite_low_breadth_ic),
            "composite_low_breadth_lift": float(composite_lift),
            "concentrated_low_breadth_ic": float(concentrated_ic),
            "concentrated_lift": float(concentrated_lift),
            "distributed_low_breadth_ic": float(distributed_ic),
            "distributed_lift": float(distributed_lift),
            "concentration_lift": float(concentration_lift),
            "h543_composite_low_breadth_ic": 0.2364,
            "h543_lift": 0.1066,
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
    print(f"\nBreadth filters:")
    print(f"  low_breadth: {low_breadth_ic:.4f} (lift: {low_breadth_lift:+.4f})")
    print(f"  composite×low_breadth (H543): {composite_low_breadth_ic:.4f} (lift: {composite_lift:+.4f})")
    print(f"\nConcentration on low breadth:")
    print(f"  concentrated: {concentrated_ic:.4f} (lift: {concentrated_lift:+.4f})")
    print(f"  distributed: {distributed_ic:.4f} (lift: {distributed_lift:+.4f})")
    print(f"  concentration lift: {concentration_lift:+.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()