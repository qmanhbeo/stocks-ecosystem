"""
H106: Signal Pair Synergy Matrix

Hypothesis: F445 found "2+ signals" works (IC 0.2445), but which SPECIFIC pairs
have strongest synergy? C23+C24 vs C23+C25 vs C24+C25 vs C23+C26 vs C24+C26 vs C25+C26.

Test: Pairwise intersections of C23/C24/C25/C26 signals - which specific combinations are strongest?

Pass criterion: Best pair IC > composite_2plus baseline (0.2445) by > +0.01
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


BRANCH_NAME = "signal_pair_synergy_matrix"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "F445 found '2+ signals' works (IC 0.2445), but which SPECIFIC pairs have "
        "strongest synergy? C23+C24 vs C23+C25 vs C24+C25 etc. Some pairs redundant, "
        "others complementary."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=100,
    min_phase_rows=100,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H106: Signal Pair Synergy Matrix")
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

    # Individual signal flags (C23/C24/C25/C26)
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

    # All signals (any 1+)
    panel["any_signal"] = panel["signal_count"] >= 1

    # Composite 2+ (AND): 2+ signals (F445 baseline)
    panel["composite_2plus"] = panel["signal_count"] >= 2

    # Individual signals
    panel["signal_1_only"] = (panel["signal_count"] == 1) & panel["c23_illiq_expansion"]
    panel["signal_2_only"] = (panel["signal_count"] == 1) & panel["c24_ceiling_expansion"]
    panel["signal_3_only"] = (panel["signal_count"] == 1) & panel["c25_vwap_expansion"]
    panel["signal_4_only"] = (panel["signal_count"] == 1) & panel["c26_buy_heavy_illiq_exp"]

    # Pairwise intersections
    panel["c23_c24"] = panel["c23_illiq_expansion"] & panel["c24_ceiling_expansion"]
    panel["c23_c25"] = panel["c23_illiq_expansion"] & panel["c25_vwap_expansion"]
    panel["c23_c26"] = panel["c23_illiq_expansion"] & panel["c26_buy_heavy_illiq_exp"]
    panel["c24_c25"] = panel["c24_ceiling_expansion"] & panel["c25_vwap_expansion"]
    panel["c24_c26"] = panel["c24_ceiling_expansion"] & panel["c26_buy_heavy_illiq_exp"]
    panel["c25_c26"] = panel["c25_vwap_expansion"] & panel["c26_buy_heavy_illiq_exp"]

    # Triple intersections
    panel["c23_c24_c25"] = panel["c23_illiq_expansion"] & panel["c24_ceiling_expansion"] & panel["c25_vwap_expansion"]
    panel["c23_c24_c26"] = panel["c23_illiq_expansion"] & panel["c24_ceiling_expansion"] & panel["c26_buy_heavy_illiq_exp"]
    panel["c23_c25_c26"] = panel["c23_illiq_expansion"] & panel["c25_vwap_expansion"] & panel["c26_buy_heavy_illiq_exp"]
    panel["c24_c25_c26"] = panel["c24_ceiling_expansion"] & panel["c25_vwap_expansion"] & panel["c26_buy_heavy_illiq_exp"]

    # All 4
    panel["c23_c24_c25_c26"] = panel["c23_illiq_expansion"] & panel["c24_ceiling_expansion"] & panel["c25_vwap_expansion"] & panel["c26_buy_heavy_illiq_exp"]

    panel["all_rows"] = True

    print(f"Panel rows: {len(panel)}")
    print(f"Signal counts: 0={panel[panel['signal_count']==0].shape[0]}, 1={panel[panel['signal_count']==1].shape[0]}, 2={panel[panel['signal_count']==2].shape[0]}, 3+={panel[panel['signal_count']>=3].shape[0]}")

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("any_signal", "Any signal (1+)", family="multi_signal"),
    StateSpec("composite_2plus", "2+ signals (AND) - F445 baseline", family="multi_signal"),
    StateSpec("signal_1_only", "C23 only", family="single_signal"),
    StateSpec("signal_2_only", "C24 only", family="single_signal"),
    StateSpec("signal_3_only", "C25 only", family="single_signal"),
    StateSpec("signal_4_only", "C26 only", family="single_signal"),
    StateSpec("c23_c24", "C23 + C24 pair", family="pair"),
    StateSpec("c23_c25", "C23 + C25 pair", family="pair"),
    StateSpec("c23_c26", "C23 + C26 pair", family="pair"),
    StateSpec("c24_c25", "C24 + C25 pair", family="pair"),
    StateSpec("c24_c26", "C24 + C26 pair", family="pair"),
    StateSpec("c25_c26", "C25 + C26 pair", family="pair"),
    StateSpec("c23_c24_c25", "C23 + C24 + C25 triple", family="triple"),
    StateSpec("c23_c24_c26", "C23 + C24 + C26 triple", family="triple"),
    StateSpec("c23_c25_c26", "C23 + C25 + C26 triple", family="triple"),
    StateSpec("c24_c25_c26", "C24 + C25 + C26 triple", family="triple"),
    StateSpec("c23_c24_c25_c26", "All 4 signals", family="quad"),
]


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(
        SPEC,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        min_year_rows=int(args.min_year_rows),
        min_phase_rows=int(args.min_phase_rows),
    )
    context = build_experiment_context(spec, artifact_subdir="research_branch")
    panel = load_panel(args, spec)

    available_cols = [s.name for s in STATE_SPECS if s.name in panel.columns]
    STATE_SPECS_FILTERED = [s for s in STATE_SPECS if s.name in available_cols]

    validate_state_columns(panel, [state.name for state in STATE_SPECS_FILTERED], spec)

    results, yearly = evaluate_state_specs(
        panel,
        STATE_SPECS_FILTERED,
        score_col=S1_SCORE_COL,
        target_col=S1_TARGET_COL,
        spec=spec,
    )

    results_path = write_dataframe_artifact(results, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")

    print("\n=== H106: Signal Pair Synergy Matrix ===")
    print(results[["name", "avg_ic", "positive_years", "years", "pooled_rows"]].sort_values("avg_ic", ascending=False).to_string(index=False))

    baseline_ic = results[results["name"] == "all_rows"]["avg_ic"].iloc[0] if not results.empty else 0
    composite_2plus_ic = results[results["name"] == "composite_2plus"]["avg_ic"].iloc[0] if "composite_2plus" in results["name"].values else 0

    # Find best pair
    pair_cols = ["c23_c24", "c23_c25", "c23_c26", "c24_c25", "c24_c26", "c25_c26"]
    best_pair_ic = 0
    best_pair_name = ""
    for col in pair_cols:
        if col in results["name"].values:
            ic = results[results["name"] == col]["avg_ic"].iloc[0]
            if pd.notna(ic) and ic > best_pair_ic:
                best_pair_ic = ic
                best_pair_name = col

    lift_vs_composite = best_pair_ic - composite_2plus_ic if composite_2plus_ic > 0 else 0

    # Decision
    if lift_vs_composite > 0.01:
        decision = "PASSED"
    elif lift_vs_composite > 0.005:
        decision = "MIXED"
    elif lift_vs_composite > 0:
        decision = "MIXED (marginal)"
    else:
        decision = "FAILED"

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "composite_2plus_ic": float(composite_2plus_ic),
            "best_pair_name": best_pair_name,
            "best_pair_ic": float(best_pair_ic),
            "lift_vs_composite": float(lift_vs_composite),
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS_FILTERED],
            "hypothesis": SPEC.hypothesis,
        },
    )

    print(f"\nBaseline IC: {baseline_ic:.4f}")
    print(f"Composite 2+ (F445 baseline): {composite_2plus_ic:.4f}")
    print(f"Best pair: {best_pair_name} IC={best_pair_ic:.4f} (lift vs composite: {lift_vs_composite:+.4f})")
    print(f"\nDecision: {decision}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()