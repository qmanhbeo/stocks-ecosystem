"""
BR8: liquidity_depth_combo

Hypothesis: C23 uses Amihud illiq, C25 uses VWAP deviation. BOTH measure under-followed
from different angles. H463 found illiq × vol_exp (C23) IC=0.2616. H470 found
vwap_below × vol_exp (C25) IC=0.1733. Test if combining illiq + vwap deviation +
vol expansion creates a stronger triple filter. D041 killed C21/C22 combos but
multi-dimensional liquidity combo was never tested.

First test: high_illiq × vwap_below_10 × vol_expansion triple vs C23 baseline.
Compare with C23, C25, and illiq alone.
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


BRANCH_NAME = "liquidity_depth_combo"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "C23 uses Amihud illiq, C25 uses VWAP deviation. H470 showed vwap_below × exp "
        "IC=0.1733. Test if illiq + vwap deviation + vol expansion triple beats C23 "
        "(IC=0.2616). D041 killed C21/C22 combos but multi-dimensional liquidity combo "
        "was never tested."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BR8 liquidity_depth_combo test")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--order-stats-path", type=str,
                        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    return parser.parse_args()


def compute_amihud_and_vwap(df):
    required = ["high", "low", "close", "volume"]
    if not all(c in df.columns for c in required):
        return df
    df = df.copy()
    if "ticker" in df.columns:
        df = df.sort_values(["ticker", "time"])
        df["daily_return"] = df.groupby("ticker")["close"].pct_change()
    else:
        df = df.sort_values("time")
        df["daily_return"] = df["close"].pct_change()
    df["daily_return_abs"] = df["daily_return"].abs()
    df["turnover"] = df["close"] * df["volume"] / 1e9
    df["amihud"] = df["daily_return_abs"] / (df["turnover"] + 1e-9)
    typical = (df["high"] + df["low"] + df["close"]) / 3
    pv = typical * df["volume"]
    df["pv_cumsum"] = pv.groupby(df["ticker"] if "ticker" in df.columns else df.index).cumsum()
    df["vol_cumsum"] = df.groupby(df["ticker"] if "ticker" in df.columns else df.index)["volume"].cumsum()
    df["vwap"] = df["pv_cumsum"] / df["vol_cumsum"].replace(0, np.nan)
    df["vwap_deviation"] = (df["close"] - df["vwap"]) / df["vwap"].replace(0, np.nan)
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
        ohlcv = compute_amihud_and_vwap(ohlcv)
        ohlcv = ohlcv.sort_values(["ticker", "time"])
        ohlcv["amihud_20d_avg"] = ohlcv.groupby("ticker")["amihud"].transform(
            lambda x: x.rolling(window=20, min_periods=10).mean()
        )
        panel = panel.merge(
            ohlcv[["time", "ticker", "amihud_20d_avg", "vwap_deviation"]],
            on=["time", "ticker"],
            how="left",
        )
    else:
        panel["amihud_20d_avg"] = np.nan
        panel["vwap_deviation"] = np.nan

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
    order_stats["buy_volume"] = order_stats["buy_order_volume"]
    order_stats["sell_volume"] = order_stats["sell_order_volume"]
    order_stats["buy_sell_volume_imbalance"] = (
        (order_stats["buy_volume"] - order_stats["sell_volume"]) /
        (order_stats["buy_volume"] + order_stats["sell_volume"] + 1)
    )

    panel = panel.merge(
        order_stats[["time", "ticker", "pct_change", "total_volume", "buy_sell_volume_imbalance"]],
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

    vol_change_rank = panel.groupby("time", sort=False)["vol_change"].rank(method="average", pct=True)
    panel["vol_expansion"] = vol_change_rank >= 0.8

    imbalance_rank = panel.groupby("time", sort=False)["buy_sell_volume_imbalance"].rank(method="average", pct=True)
    panel["buy_heavy"] = imbalance_rank >= 0.8
    panel["buy_heavy_expansion"] = panel["buy_heavy"] & panel["vol_expansion"]

    if "amihud_20d_avg" in panel.columns and panel["amihud_20d_avg"].notna().any():
        amihud_rank = panel.groupby("time", sort=False)["amihud_20d_avg"].rank(method="average", pct=True)
        panel["high_illiq"] = amihud_rank >= 0.8
    else:
        panel["high_illiq"] = False

    panel["high_illiq_expansion"] = panel["high_illiq"] & panel["vol_expansion"]

    if "vwap_deviation" in panel.columns and panel["vwap_deviation"].notna().any():
        vwap_rank = panel.groupby("time", sort=False)["vwap_deviation"].rank(method="average", pct=True)
        panel["vwap_below_20"] = vwap_rank <= 0.20
        panel["vwap_below_10"] = vwap_rank <= 0.10
        panel["vwap_above_80"] = vwap_rank >= 0.80
    else:
        panel["vwap_below_20"] = False
        panel["vwap_below_10"] = False
        panel["vwap_above_80"] = False

    panel["vwap_below_20_expansion"] = panel["vwap_below_20"] & panel["vol_expansion"]
    panel["vwap_below_10_expansion"] = panel["vwap_below_10"] & panel["vol_expansion"]
    panel["high_illiq_vwap_20_expansion"] = panel["high_illiq"] & panel["vwap_below_20"] & panel["vol_expansion"]
    panel["high_illiq_vwap_10_expansion"] = panel["high_illiq"] & panel["vwap_below_10"] & panel["vol_expansion"]
    panel["high_illiq_expansion_vwap_10"] = panel["high_illiq"] & panel["vol_expansion"] & panel["vwap_below_10"]

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("high_illiq_expansion", "C23: illiq × vol expansion", family="component", primary=True),
    StateSpec("vwap_below_20_expansion", "C25: vwap below 20% × exp", family="component"),
    StateSpec("vwap_below_10_expansion", "C25 tight: vwap below 10% × exp", family="component"),
    StateSpec("high_illiq_vwap_20_expansion", "Double: illiq + vwap_20 + exp", family="combo", primary=True),
    StateSpec("high_illiq_vwap_10_expansion", "Double tight: illiq + vwap_10 + exp", family="combo"),
    StateSpec("high_illiq_expansion_vwap_10", "Triple-like: illiq_exp + vwap_10", family="combo"),
    StateSpec("high_illiq", "High illiquidity alone", family="illiq"),
    StateSpec("vwap_below_20", "VWAP below alone", family="vwap"),
    StateSpec("vwap_below_10", "VWAP extreme below alone", family="vwap"),
    StateSpec("buy_heavy_expansion", "C20: buy_heavy × vol expansion", family="signal"),
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

    c23_ic = results[results["name"] == "high_illiq_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    c23_lift = c23_ic - baseline_ic

    c25_ic = results[results["name"] == "vwap_below_20_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    c25_tight_ic = results[results["name"] == "vwap_below_10_expansion"]["avg_ic"].iloc[0] if not results.empty else 0

    double_ic = results[results["name"] == "high_illiq_vwap_20_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    double_lift = double_ic - baseline_ic
    double_incr = double_lift - c23_lift

    double_tight_ic = results[results["name"] == "high_illiq_vwap_10_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    double_tight_lift = double_tight_ic - baseline_ic
    double_tight_incr = double_tight_lift - c23_lift

    triple_ic = results[results["name"] == "high_illiq_expansion_vwap_10"]["avg_ic"].iloc[0] if not results.empty else 0
    triple_lift = triple_ic - baseline_ic
    triple_incr = triple_lift - c23_lift

    c20_ic = results[results["name"] == "buy_heavy_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    c20_lift = c20_ic - baseline_ic

    illiq_alone_ic = results[results["name"] == "high_illiq"]["avg_ic"].iloc[0] if not results.empty else 0
    illiq_alone_lift = illiq_alone_ic - baseline_ic

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    if double_incr > 0.01 and double_lift > 0.10:
        decision = "PASSED"
    elif double_incr > 0.005:
        decision = "MIXED"
    elif triple_incr > 0.01:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "c23_ic": float(c23_ic),
            "c23_lift": float(c23_lift),
            "c25_ic": float(c25_ic),
            "c25_tight_ic": float(c25_tight_ic),
            "double_20_ic": float(double_ic),
            "double_20_lift": float(double_lift),
            "double_20_incr_vs_c23": float(double_incr),
            "double_10_ic": float(double_tight_ic),
            "double_10_lift": float(double_tight_lift),
            "double_10_incr_vs_c23": float(double_tight_incr),
            "triple_ic": float(triple_ic),
            "triple_lift": float(triple_lift),
            "triple_incr_vs_c23": float(triple_incr),
            "illiq_alone_ic": float(illiq_alone_ic),
            "illiq_alone_lift": float(illiq_alone_lift),
            "c20_ic": float(c20_ic),
            "c20_lift": float(c20_lift),
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
        },
        artifacts={
            "results": str(results_path),
            "yearly": str(yearly_path),
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": SPEC.hypothesis,
        },
    )

    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(f"\nDecision: {decision}")
    print(f"Baseline IC: {baseline_ic:.4f}")
    print(f"C23 (illiq × exp): IC={c23_ic:.4f}, lift={c23_lift:+.4f}")
    print(f"C25 (vwap_20 × exp): IC={c25_ic:.4f}")
    print(f"C25 tight (vwap_10 × exp): IC={c25_tight_ic:.4f}")
    print(f"\nCombo states:")
    print(f"  illiq+vwap_20+exp: IC={double_ic:.4f}, lift={double_lift:+.4f}, incr_vs_c23={double_incr:+.4f}")
    print(f"  illiq+vwap_10+exp: IC={double_tight_ic:.4f}, lift={double_tight_lift:+.4f}, incr_vs_c23={double_tight_incr:+.4f}")
    print(f"  illiq_exp+vwap_10: IC={triple_ic:.4f}, lift={triple_lift:+.4f}, incr_vs_c23={triple_incr:+.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()
