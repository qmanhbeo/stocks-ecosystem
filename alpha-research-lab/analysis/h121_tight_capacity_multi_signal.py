"""
H121: Tight Capacity × Multi-Signal Amplifier

Hypothesis: 
- F437 found tight+low_breadth = 0.2062
- F447 found composite_2+ × low_breadth = 0.2651
- Triple: tight + multi + low_breadth might exceed both

Test: tight_capacity × composite_2+ × low_breadth vs F447 baseline (0.2651)

Pass criterion: triple beats F447 (0.2651) by +0.01 lift
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


BRANCH_NAME = "h121_tight_capacity_multi_signal"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Tight Capacity × Multi-Signal: F437 found tight+low_breadth=0.2062, "
        "F447 found composite_2+×low_breadth=0.2651. "
        "Test triple: tight + composite_2+ + low_breadth vs F447 baseline"
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=100,
    min_phase_rows=100,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H121: Tight Capacity × Multi-Signal Amplifier")
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

    # Load order_stats for vol regime, signals, and tight capacity
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
    # Compute total order count (buy + sell orders)
    order_stats["total_order_count"] = order_stats["buy_order_count"].fillna(0) + order_stats["sell_order_count"].fillna(0)

    panel = panel.merge(
        order_stats[["time", "ticker", "pct_change", "total_volume", "buy_order_volume", "sell_order_volume", "total_order_count"]],
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

    # Individual signal flags (C23/C24/C25/C26 from F445/F447)
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

    # Compute date-level breadth (how many tickers have signal_count >= 1)
    date_signal_count = panel.groupby("time")["signal_count"].apply(
        lambda x: (x >= 1).sum()
    ).reset_index()
    date_signal_count.columns = ["time", "signal_breadth"]

    # Total tickers per date
    date_total = panel.groupby("time")["ticker"].nunique().reset_index()
    date_total.columns = ["time", "total_tickers"]

    date_stats = date_signal_count.merge(date_total, on="time")
    date_stats["breadth_fraction"] = date_stats["signal_breadth"] / date_stats["total_tickers"]

    panel = panel.merge(date_stats[["time", "breadth_fraction"]], on="time", how="left")

    # Low breadth: bottom 20% of breadth fractions (few signals in market)
    breadth_threshold = panel["breadth_fraction"].quantile(0.20)
    panel["low_breadth"] = panel["breadth_fraction"] <= breadth_threshold

    # Tight capacity (from F437/h565): bottom 20% of order_count
    if "total_order_count" in panel.columns and panel["total_order_count"].notna().any():
        order_count_rank = panel.groupby("time", sort=False)["total_order_count"].rank(method="average", pct=True)
        panel["tight_capacity"] = order_count_rank <= 0.2
    else:
        # Fallback to order_volume_ratio_rank if order_count not available
        if "order_volume_ratio_rank" in panel.columns:
            panel["tight_capacity"] = panel["order_volume_ratio_rank"] <= 0.2
        else:
            panel["tight_capacity"] = False

    # Triple intersection: tight + composite_2+ + low_breadth
    panel["triple_tight_composite_low"] = panel["tight_capacity"] & panel["composite_2plus"] & panel["low_breadth"]

    # Additional baselines for comparison
    panel["tight_low_breadth"] = panel["tight_capacity"] & panel["low_breadth"]
    panel["composite_2plus_low_breadth"] = panel["composite_2plus"] & panel["low_breadth"]

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("composite_2plus", "2+ signals firing (C23/C24/C25/C26)", family="composite"),
    StateSpec("low_breadth", "Low market breadth (bottom 20%)", family="breadth"),
    StateSpec("tight_capacity", "Tight capacity (bottom 20% order_count)", family="capacity"),
    StateSpec("tight_low_breadth", "Tight capacity + Low breadth", family="combo"),
    StateSpec("composite_2plus_low_breadth", "2+ signals + Low breadth (F447)", family="combo"),
    StateSpec("triple_tight_composite_low", "Tight + 2+ signals + Low breadth", family="combo"),
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
    triple_row = results[results["name"] == "triple_tight_composite_low"]
    f447_row = results[results["name"] == "composite_2plus_low_breadth"]
    tight_low_row = results[results["name"] == "tight_low_breadth"]
    composite_row = results[results["name"] == "composite_2plus"]
    tight_row = results[results["name"] == "tight_capacity"]

    triple_ic = triple_row["avg_ic"].iloc[0] if not triple_row.empty else 0
    f447_ic = f447_row["avg_ic"].iloc[0] if not f447_row.empty else 0
    tight_low_ic = tight_low_row["avg_ic"].iloc[0] if not tight_low_row.empty else 0
    composite_ic = composite_row["avg_ic"].iloc[0] if not composite_row.empty else 0
    tight_ic = tight_row["avg_ic"].iloc[0] if not tight_row.empty else 0

    # F447 baseline: composite_2+ × low_breadth = 0.2651
    f447_baseline = 0.2651

    # Pass if triple beats F447 by +0.01
    lift_vs_f447 = triple_ic - f447_baseline
    if lift_vs_f447 > 0.01:
        decision = "PASSED"
    elif lift_vs_f447 > 0:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "triple_ic": float(triple_ic),
            "f447_ic": float(f447_ic),
            "tight_low_breadth_ic": float(tight_low_ic),
            "composite_2plus_ic": float(composite_ic),
            "tight_capacity_ic": float(tight_ic),
            "lift_vs_f447": float(lift_vs_f447),
            "f447_baseline": f447_baseline,
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
    print(f"triple_ic={triple_ic:.4f} vs f447={f447_baseline}, lift={lift_vs_f447:.4f}")
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()