"""
H595: Multi-Signal Co-occurrence Superposition

Hypothesis: C23/C24/C25/C26 fire on different days. When MULTIPLE fire together on same ticker
(co-occurrence), does that indicate stronger hidden demand? "Multiple mechanisms firing
simultaneously = stronger alpha" hypothesis.

Test: count of signal families per ticker-day (1 vs 2 vs 3+). H543 composite OR (any) = IC=0.1988,
what about AND (multiple)?

Pass criterion: Multi-signal co-occurrence (2+ signals) beats single-signal (1) by > +0.01 IC
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


BRANCH_NAME = "multi_signal_cooccurrence"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "C23/C24/C25/C26 fire on different days. When MULTIPLE fire together on same ticker "
        "(co-occurrence), does that indicate stronger hidden demand? Test count of signal families "
        "per ticker-day (1 vs 2 vs 3+)."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=100,
    min_phase_rows=100,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H595: Multi-Signal Co-occurrence Superposition")
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

    # Individual signal flags
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

    # Co-occurrence categories
    panel["signal_0"] = panel["signal_count"] == 0
    panel["signal_1"] = panel["signal_count"] == 1
    panel["signal_2"] = panel["signal_count"] == 2
    panel["signal_3plus"] = panel["signal_count"] >= 3

    # Composite: OR of any (H543 baseline)
    panel["composite_any"] = panel["signal_count"] >= 1

    # Composite AND: 2+ signals (co-occurrence)
    panel["composite_2plus"] = panel["signal_count"] >= 2

    panel["all_rows"] = True

    print(f"Panel rows: {len(panel)}")
    print(f"Signal 0: {panel['signal_0'].sum()}")
    print(f"Signal 1: {panel['signal_1'].sum()}")
    print(f"Signal 2: {panel['signal_2'].sum()}")
    print(f"Signal 3+: {panel['signal_3plus'].sum()}")
    print(f"Composite any: {panel['composite_any'].sum()}")
    print(f"Composite 2+: {panel['composite_2plus'].sum()}")

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("composite_any", "Any C23/C24/C25/C26 firing (OR)", family="composite"),
    StateSpec("signal_1", "Exactly 1 signal", family="cooccurrence"),
    StateSpec("signal_2", "Exactly 2 signals", family="cooccurrence"),
    StateSpec("signal_3plus", "3+ signals", family="cooccurrence"),
    StateSpec("composite_2plus", "2+ signals (AND)", family="composite_and"),
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

    print("=== H595: Multi-Signal Co-occurrence ===")
    print(results[["name", "avg_ic", "positive_years", "years", "pooled_rows"]].sort_values("avg_ic", ascending=False).to_string(index=False))

    baseline_ic = results[results["name"] == "all_rows"]["avg_ic"].iloc[0] if not results.empty else 0
    composite_any_ic = results[results["name"] == "composite_any"]["avg_ic"].iloc[0] if "composite_any" in results["name"].values else 0
    signal_1_ic = results[results["name"] == "signal_1"]["avg_ic"].iloc[0] if "signal_1" in results["name"].values else 0
    signal_2_ic = results[results["name"] == "signal_2"]["avg_ic"].iloc[0] if "signal_2" in results["name"].values else 0
    signal_3plus_ic = results[results["name"] == "signal_3plus"]["avg_ic"].iloc[0] if "signal_3plus" in results["name"].values else 0
    composite_2plus_ic = results[results["name"] == "composite_2plus"]["avg_ic"].iloc[0] if "composite_2plus" in results["name"].values else 0

    # Compare multi-signal vs single-signal
    best_multi = max(signal_2_ic if pd.notna(signal_2_ic) else 0,
                     signal_3plus_ic if pd.notna(signal_3plus_ic) else 0)
    best_vs_single = best_multi - signal_1_ic if pd.notna(signal_1_ic) else 0

    # Compare AND (2+) vs OR (any)
    and_vs_or = composite_2plus_ic - composite_any_ic if pd.notna(composite_2plus_ic) and pd.notna(composite_any_ic) else 0

    # Decision: Does multi-signal beat single-signal?
    if best_vs_single > 0.01:
        decision = "PASSED"
    elif best_vs_single > 0.005:
        decision = "MIXED"
    elif best_vs_single > 0:
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
            "composite_any_ic": float(composite_any_ic),
            "signal_1_ic": float(signal_1_ic),
            "signal_2_ic": float(signal_2_ic),
            "signal_3plus_ic": float(signal_3plus_ic),
            "composite_2plus_ic": float(composite_2plus_ic),
            "best_vs_single": float(best_vs_single),
            "and_vs_or": float(and_vs_or),
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
    print(f"Composite any (OR): {composite_any_ic:.4f}")
    print(f"Signal 1: {signal_1_ic:.4f}")
    print(f"Signal 2: {signal_2_ic:.4f}")
    print(f"Signal 3+: {signal_3plus_ic:.4f}")
    print(f"Composite 2+ (AND): {composite_2plus_ic:.4f}")
    print(f"Best multi vs single: {best_vs_single:.4f}")
    print(f"AND vs OR: {and_vs_or:.4f}")
    print(f"\nDecision: {decision}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()