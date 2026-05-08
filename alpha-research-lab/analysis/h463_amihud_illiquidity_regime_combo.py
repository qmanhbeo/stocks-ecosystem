"""
H463: amihud_illiquidity_regime_combo

Hypothesis: C10 (Amihud illiquidity, IC +0.0206 standalone) might be a STRONGER signal
in vol_expansion regime. Illiquid stocks (under-followed) might respond more to regime effects.
Test: illiquidity level × vol_expansion vs forward IC.

First test: illiquidity quintiles × vol_expansion vs random baseline.
Compare with: C10 standalone baseline (+0.0206 IC).

Data: Uses OHLCV to compute Amihud illiquidity inline.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys
import glob

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


BRANCH_NAME = "amihud_illiquidity_regime_combo"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "C10 (Amihud illiquidity, IC +0.0206 standalone) might be STRONGER in vol_expansion regime. "
        "Test illiquidity × vol_expansion vs forward IC."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H463 amihud_illiquidity_regime_combo test")
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
    df['turnover'] = df['close'] * df['volume'] / 1e9  # billions VND
    df['amihud'] = df['daily_return_abs'] / (df['turnover'] + 1e-9)
    return df


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )

    # Load OHLCV for Amihud computation - combine all ticker files
    # Filenames: gia_lich_su_AAA_1D.parquet → ticker=AAA
    stock_dir = Path("/home/manh/stocks-ecosystem/data/stock")
    ohlcv_dfs = []
    for f in stock_dir.glob("gia_lich_su_*_1D.parquet"):
        try:
            df = pd.read_parquet(f)
            # Extract ticker from filename: gia_lich_su_AAA_1D.parquet
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

        # Compute 20d rolling average of Amihud
        ohlcv = ohlcv.sort_values(["ticker", "time"])
        ohlcv["amihud_20d_avg"] = ohlcv.groupby("ticker")["amihud"].transform(
            lambda x: x.rolling(window=20, min_periods=10).mean()
        )

        panel = panel.merge(
            ohlcv[["time", "ticker", "amihud_20d_avg", "daily_return"]],
            on=["time", "ticker"],
            how="left",
        )
    else:
        print("Warning: Could not load OHLCV data")
        panel["amihud_20d_avg"] = np.nan

    # Load order_stats for vol regime
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

    # Amihud quintiles (high = illiquid)
    amihud_rank = panel.groupby("time", sort=False)["amihud_20d_avg"].rank(method="average", pct=True)
    panel["high_illiq"] = amihud_rank >= 0.8
    panel["mid_illiq"] = (amihud_rank > 0.3) & (amihud_rank < 0.7)
    panel["low_illiq"] = amihud_rank <= 0.2

    # Imbalance for cross signal
    order_stats2 = pd.read_parquet(args.order_stats_path)
    order_stats2 = order_stats2.rename(columns={"date": "time"})
    order_stats2["time"] = pd.to_datetime(order_stats2["time"])
    order_stats2 = order_stats2[order_stats2["time"].dt.year <= 2025]
    order_stats2["buy_sell_volume_imbalance"] = (
        (order_stats2["buy_order_volume"] - order_stats2["sell_order_volume"]) /
        (order_stats2["buy_order_volume"] + order_stats2["sell_order_volume"] + 1)
    )

    panel = panel.merge(
        order_stats2[["time", "ticker", "buy_sell_volume_imbalance"]],
        on=["time", "ticker"],
        how="left",
    )
    panel = panel.dropna(subset=["buy_sell_volume_imbalance"])

    imbalance_rank = panel.groupby("time", sort=False)["buy_sell_volume_imbalance"].rank(method="average", pct=True)
    panel["buy_heavy"] = imbalance_rank >= 0.8
    panel["buy_heavy_expansion"] = panel["buy_heavy"] & panel["vol_expansion"]

    # Combos: illiq × vol regime
    panel["high_illiq_expansion"] = panel["high_illiq"] & panel["vol_expansion"]
    panel["low_illiq_expansion"] = panel["low_illiq"] & panel["vol_expansion"]
    panel["high_illiq_contraction"] = panel["high_illiq"] & panel["vol_contraction"]

    # Cross: illiq × buy_heavy_expansion
    panel["high_illiq_buy_expansion"] = panel["high_illiq"] & panel["buy_heavy_expansion"]

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    # Vol regime alone
    StateSpec("vol_expansion", "Vol expansion (top 20%)", family="vol_regime"),
    StateSpec("vol_contraction", "Vol contraction (bottom 20%)", family="vol_regime"),
    # Illiq alone
    StateSpec("high_illiq", "High illiquidity (top 20%)", family="illiq"),
    StateSpec("mid_illiq", "Mid illiquidity (40-60%)", family="illiq"),
    StateSpec("low_illiq", "Low illiquidity (bottom 20%)", family="illiq"),
    # Illiq × vol regime
    StateSpec("high_illiq_expansion", "High illiq + Vol expansion", family="illiq_vol", primary=True),
    StateSpec("low_illiq_expansion", "Low illiq + Vol expansion", family="illiq_vol"),
    StateSpec("high_illiq_contraction", "High illiq + Vol contraction", family="illiq_vol"),
    # Cross signals
    StateSpec("buy_heavy_expansion", "H451: Buy-heavy + Vol expansion", family="imbalance"),
    StateSpec("high_illiq_buy_expansion", "High illiq + Buy-heavy + Vol expansion", family="cross"),
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

    # Illiq alone
    high_illiq_ic = results[results["name"] == "high_illiq"]["avg_ic"].iloc[0] if not results.empty else 0
    mid_illiq_ic = results[results["name"] == "mid_illiq"]["avg_ic"].iloc[0] if not results.empty else 0
    low_illiq_ic = results[results["name"] == "low_illiq"]["avg_ic"].iloc[0] if not results.empty else 0
    high_illiq_lift = high_illiq_ic - baseline_ic

    # Illiq × vol
    high_illiq_exp_ic = results[results["name"] == "high_illiq_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    low_illiq_exp_ic = results[results["name"] == "low_illiq_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    high_illiq_cont_ic = results[results["name"] == "high_illiq_contraction"]["avg_ic"].iloc[0] if not results.empty else 0
    high_illiq_exp_lift = high_illiq_exp_ic - baseline_ic

    # Cross
    buy_exp_ic = results[results["name"] == "buy_heavy_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    high_illiq_buy_ic = results[results["name"] == "high_illiq_buy_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    high_illiq_buy_lift = high_illiq_buy_ic - baseline_ic

    # Compare with C10 baseline
    c10_baseline = 0.0206
    high_illiq_vs_c10 = high_illiq_lift - c10_baseline

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    # Hypothesis: illiq works better in vol_expansion
    if high_illiq_exp_lift > high_illiq_lift + 0.005:
        decision = "PASSED"
    elif high_illiq_lift > c10_baseline:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            # Illiq alone
            "high_illiq_ic": float(high_illiq_ic),
            "mid_illiq_ic": float(mid_illiq_ic),
            "low_illiq_ic": float(low_illiq_ic),
            "high_illiq_lift": float(high_illiq_lift),
            # Illiq × vol
            "high_illiq_expansion_ic": float(high_illiq_exp_ic),
            "low_illiq_expansion_ic": float(low_illiq_exp_ic),
            "high_illiq_contraction_ic": float(high_illiq_cont_ic),
            "high_illiq_expansion_lift": float(high_illiq_exp_lift),
            # Cross
            "buy_heavy_expansion_ic": float(buy_exp_ic),
            "high_illiq_buy_expansion_ic": float(high_illiq_buy_ic),
            "high_illiq_buy_expansion_lift": float(high_illiq_buy_lift),
            # Comparison
            "high_illiq_vs_c10_baseline": float(high_illiq_vs_c10),
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
    print(f"\nIlliq alone:")
    print(f"  high_illiq: {high_illiq_ic:.4f} (lift: {high_illiq_lift:+.4f})")
    print(f"  mid_illiq: {mid_illiq_ic:.4f}")
    print(f"  low_illiq: {low_illiq_ic:.4f}")
    print(f"  C10 standalone reference: {c10_baseline:.4f}")
    print(f"\nIlliq × Vol regime:")
    print(f"  high_illiq_expansion: {high_illiq_exp_ic:.4f} (lift: {high_illiq_exp_lift:+.4f})")
    print(f"  low_illiq_expansion: {low_illiq_exp_ic:.4f}")
    print(f"  high_illiq_contraction: {high_illiq_cont_ic:.4f}")
    print(f"\nCross signals:")
    print(f"  buy_heavy_expansion (baseline): {buy_exp_ic:.4f}")
    print(f"  high_illiq_buy_expansion: {high_illiq_buy_ic:.4f}")
    print(f"\nHigh illiq vs C10 baseline: {high_illiq_vs_c10:+.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()