"""
BU1: market_wide_vol_regime

Hypothesis: c16_low works at ticker level as regime conditioner for C23.
Market-level vol expansion is the systemic analog. When the overall market
has high vol expansion (top 20% of days by market-wide vol std), C23 should
work better than in low-vol periods.

Test: market_vol_expansion × C23 vs C23 alone vs random baseline.
Data: computed from order_stats daily market-wide rolling std of pct_change.

Mechanism: systemic vol regime amplifies illiquidity signal the same way
ticker-level vol regime does, but at the market level.
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


BRANCH_NAME = "market_wide_vol_regime"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "c16_low×C23 (IC 0.2838) works at ticker level. Test market-level vol "
        "expansion as systemic analog. When market-wide vol is in top 20%, "
        "C23 should amplify. Compare market_vol_exp×C23 vs C23 alone vs random."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BU1 market_wide_vol_regime test")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--order-stats-path", type=str,
                        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    return parser.parse_args()


def compute_amihud(df):
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
    order_stats["buy_volume"] = order_stats["buy_order_volume"]
    order_stats["sell_volume"] = order_stats["sell_order_volume"]
    order_stats["c16_proxy"] = (order_stats["buy_volume"] - order_stats["sell_volume"]) / (
        order_stats["buy_volume"] + order_stats["sell_volume"] + 1
    )

    panel = panel.merge(
        order_stats[["time", "ticker", "pct_change", "total_volume", "c16_proxy"]],
        on=["time", "ticker"],
        how="left",
    )

    panel["all_rows"] = True
    panel = panel.dropna(subset=["pct_change", "total_volume"])
    panel = panel[panel["total_volume"] > 0]
    panel = panel.sort_values(["ticker", "time"])

    panel["pct_change_vol"] = panel.groupby("ticker")["pct_change"].transform(
        lambda x: x.rolling(window=5, min_periods=3).std()
    )
    panel["vol_change"] = panel.groupby("ticker")["pct_change_vol"].transform(
        lambda x: x.diff()
    )
    panel = panel.dropna(subset=["vol_change"])

    ticker_vol_rank = panel.groupby("time", sort=False)["vol_change"].rank(method="average", pct=True)
    panel["ticker_vol_expansion"] = ticker_vol_rank >= 0.8

    if "amihud_20d_avg" in panel.columns and panel["amihud_20d_avg"].notna().any():
        amihud_rank = panel.groupby("time", sort=False)["amihud_20d_avg"].rank(method="average", pct=True)
        panel["high_illiq"] = amihud_rank >= 0.8
    else:
        panel["high_illiq"] = False

    panel["c23_ticker_level"] = panel["high_illiq"] & panel["ticker_vol_expansion"]

    market_vol = panel.groupby("time").agg(
        market_vol_std=("pct_change", lambda x: x.std()),
        market_vol_mean=("pct_change", lambda x: x.mean()),
        n_tickers=("ticker", "count"),
    ).reset_index()

    market_vol = market_vol.sort_values("time")
    market_vol["market_vol_5d"] = market_vol["market_vol_std"].rolling(window=5, min_periods=3).mean()
    market_vol["market_vol_change"] = market_vol["market_vol_5d"].diff()
    market_vol = market_vol.dropna(subset=["market_vol_change"])

    market_vol_rank = market_vol["market_vol_change"].rank(pct=True)
    market_vol["market_vol_expansion"] = market_vol_rank >= 0.8
    market_vol["market_vol_contraction"] = market_vol_rank <= 0.2

    panel = panel.merge(
        market_vol[["time", "market_vol_change", "market_vol_expansion", "market_vol_contraction"]],
        on="time",
        how="left",
    )

    panel["c23_market_vol_exp"] = panel["high_illiq"] & panel["market_vol_expansion"]
    panel["c23_ticker_vol_exp"] = panel["high_illiq"] & panel["ticker_vol_expansion"]
    panel["c23_both_vol_exp"] = panel["high_illiq"] & panel["ticker_vol_expansion"] & panel["market_vol_expansion"]
    panel["market_vol_exp_alone"] = panel["market_vol_expansion"]
    panel["ticker_vol_exp_alone"] = panel["ticker_vol_expansion"]

    return panel


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

    STATE_SPECS = [
        StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
        StateSpec("c23_ticker_level", "C23 at ticker-level vol expansion (existing)", family="ticker_level"),
        StateSpec("c23_market_vol_exp", "C23 at market-wide vol expansion (BU1)", family="market_level"),
        StateSpec("c23_ticker_vol_exp", "high_illiq + ticker_vol_expansion", family="ticker_vol"),
        StateSpec("c23_both_vol_exp", "C23 with BOTH ticker AND market vol expansion", family="combo"),
        StateSpec("market_vol_exp_alone", "Market vol expansion alone (no illiq)", family="market_vol_only"),
        StateSpec("ticker_vol_exp_alone", "Ticker vol expansion alone (no illiq)", family="ticker_vol_only"),
    ]

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

    baseline_ic = results[results["name"] == "all_rows"]["avg_ic"].values[0]
    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    lift_vs_baseline = best_row.get("avg_ic", 0) - baseline_ic if best_row else 0

    if best_row.get("avg_ic", 0) > baseline_ic + 0.01 and best_row.get("positive_years", 0) >= 6:
        decision = "PASSED"
    elif best_row.get("avg_ic", 0) > baseline_ic and best_row.get("positive_years", 0) >= 5:
        decision = "MIXED"
    elif lift_vs_baseline < -0.01:
        decision = "FAILED"
    else:
        decision = "MIXED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
            "lift_vs_baseline": lift_vs_baseline,
            "best_positive_years": best_row.get("positive_years"),
            "best_years": best_row.get("years"),
            "hypothesis": "market_vol_exp×C23 vs C23 alone",
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
    )

    print(f"\n=== BU1 market_wide_vol_regime ===")
    print(f"Decision: {decision}")
    print(f"Baseline IC: {baseline_ic:.4f}")
    print(f"Best state: {best_row.get('name')}")
    print(f"Best IC: {best_row.get('avg_ic'):.4f}")
    print(f"Lift vs baseline: {lift_vs_baseline:+.4f}")
    print(f"Positive years: {best_row.get('positive_years')}/{best_row.get('years')}")
    print(f"Summary: {summary_path}")

    return decision


if __name__ == "__main__":
    args = parse_args()
    decision = run_branch(args)
    sys.exit(0 if decision in ["PASSED", "MIXED"] else 1)