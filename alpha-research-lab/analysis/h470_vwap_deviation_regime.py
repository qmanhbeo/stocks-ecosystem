"""
H470: vwap_deviation_regime

Hypothesis: Distance from VWAP captures "expensive vs cheap" vs day's average transaction price.
VWAP deviation × vol_expansion regime is a signal. C23 (illiq_expansion) already showed
under-followed stocks amplify regime effects. VWAP deviation may similarly amplify.

Data: Uses OHLCV to compute VWAP inline from gia_lich_su_*_1D.parquet.
Compare with: C16 baseline, random baseline.
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

BRANCH_NAME = "vwap_deviation_regime"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "VWAP deviation (price far from day's average transaction price) × vol_expansion is signal. "
        "Under-followed stocks amplify regime effects (like C23 illiq_expansion)."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)

STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("vwap_above_80_exp", "VWAP far above + vol expansion", family="vwap_regime"),
    StateSpec("vwap_below_20_exp", "VWAP far below + vol expansion", family="vwap_regime"),
    StateSpec("vwap_above_50_exp", "VWAP above median + vol expansion", family="vwap_regime"),
    StateSpec("vwap_above_80_any", "VWAP far above (any regime)", family="vwap_regime"),
    StateSpec("vwap_below_20_any", "VWAP far below (any regime)", family="vwap_regime"),
    StateSpec("vwap_dev_top20", "VWAP deviation rank top 20%", family="vwap_regime"),
    StateSpec("vwap_dev_bot20", "VWAP deviation rank bottom 20%", family="vwap_regime"),
    StateSpec("vwap_dev_top10", "VWAP deviation rank top 10%", family="vwap_regime"),
    StateSpec("vwap_dev_bot10", "VWAP deviation rank bottom 10%", family="vwap_regime"),
    StateSpec("vwap_mid50_exp", "VWAP mid-50% + vol expansion", family="vwap_regime"),
    StateSpec("vwap_above_90_exp", "VWAP extreme above + vol expansion", family="vwap_regime"),
    StateSpec("vwap_below_10_exp", "VWAP extreme below + vol expansion", family="vwap_regime"),
]


def compute_vwap_and_regime(price_df):
    df = price_df.sort_values(["ticker", "time"]).copy()
    typical = (df["high"] + df["low"] + df["close"]) / 3
    pv = typical * df["volume"]
    df["vwap"] = pv.groupby(df["ticker"]).transform(
        lambda x: x.cumsum() / df.loc[x.index, "volume"].expanding().sum()
    )
    df["vwap_deviation"] = (df["close"] - df["vwap"]) / df["vwap"].replace(0, np.nan)

    df["vol_20d"] = df.groupby("ticker")["volume"].transform(
        lambda x: x.rolling(20, min_periods=10).mean()
    )
    df["vol_60d"] = df.groupby("ticker")["volume"].transform(
        lambda x: x.rolling(60, min_periods=20).mean()
    )
    df["vol_expansion"] = (df["vol_20d"] / df["vol_60d"].replace(0, np.nan) - 1).fillna(0)
    return df


def load_panel(args, spec):
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )

    panel["all_rows"] = True

    price_files = sorted(data_path("stock").glob("gia_lich_su_*_1D.parquet"))
    price_dfs = []
    for f in price_files:
        ticker = f.stem.replace("gia_lich_su_", "").replace("_1D", "")
        df = pd.read_parquet(f)
        if "date" in df.columns and "time" not in df.columns:
            df = df.rename(columns={"date": "time"})
        df["ticker"] = ticker
        price_dfs.append(df[["ticker", "time", "open", "high", "low", "close", "volume"]])

    if price_dfs:
        price_all = pd.concat(price_dfs, ignore_index=True)
        price_all = compute_vwap_and_regime(price_all)
        panel = panel.merge(
            price_all[["ticker", "time", "vwap_deviation", "vol_expansion"]],
            on=["time", "ticker"],
            how="left"
        )

    if "vwap_deviation" in panel.columns:
        panel["vwap_dev_rank"] = panel.groupby("time")["vwap_deviation"].transform(
            lambda x: x.rank(pct=True, na_option="keep")
        )
        panel["vwap_above_50pct"] = panel["vwap_deviation"] > panel.groupby("time")["vwap_deviation"].transform(
            lambda x: x.quantile(0.50)
        )
        panel["vwap_below_50pct"] = panel["vwap_deviation"] < panel.groupby("time")["vwap_deviation"].transform(
            lambda x: x.quantile(0.50)
        )
        panel["vwap_above_80pct"] = panel["vwap_dev_rank"] >= 0.80
        panel["vwap_below_20pct"] = panel["vwap_dev_rank"] <= 0.20
        panel["vwap_above_90pct"] = panel["vwap_dev_rank"] >= 0.90
        panel["vwap_below_10pct"] = panel["vwap_dev_rank"] <= 0.10

    if "vol_expansion" in panel.columns:
        panel["vol_expansion_q80"] = panel.groupby("time")["vol_expansion"].transform(
            lambda x: x >= x.quantile(0.80)
        )
    else:
        panel["vol_expansion_q80"] = False

    panel["vwap_above_80_exp"] = panel["vwap_above_80pct"] & panel["vol_expansion_q80"]
    panel["vwap_below_20_exp"] = panel["vwap_below_20pct"] & panel["vol_expansion_q80"]
    panel["vwap_above_50_exp"] = panel["vwap_above_50pct"] & panel["vol_expansion_q80"]
    panel["vwap_above_80_any"] = panel["vwap_above_80pct"]
    panel["vwap_below_20_any"] = panel["vwap_below_20pct"]
    panel["vwap_dev_top20"] = panel["vwap_dev_rank"] >= 0.80
    panel["vwap_dev_bot20"] = panel["vwap_dev_rank"] <= 0.20
    panel["vwap_dev_top10"] = panel["vwap_dev_rank"] >= 0.90
    panel["vwap_dev_bot10"] = panel["vwap_dev_rank"] <= 0.10
    panel["vwap_mid50_exp"] = panel["vwap_above_50pct"] & ~panel["vwap_above_80pct"] & ~panel["vwap_below_20pct"] & panel["vol_expansion_q80"]
    panel["vwap_above_90_exp"] = panel["vwap_above_90pct"] & panel["vol_expansion_q80"]
    panel["vwap_below_10_exp"] = panel["vwap_below_10pct"] & panel["vol_expansion_q80"]

    return panel


def parse_args():
    parser = argparse.ArgumentParser(description="H470: vwap_deviation_regime")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    return parser.parse_args()


def run_branch(args):
    spec = replace(
        SPEC,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        min_year_rows=int(SPEC.min_year_rows),
        min_phase_rows=int(SPEC.min_phase_rows),
    )
    context = build_experiment_context(spec, artifact_subdir="research_branches")
    panel = load_panel(args, spec)
    print(f"Panel: {panel.shape}, date range: {panel['time'].min()} - {panel['time'].max()}")

    state_names = [s.name for s in STATE_SPECS]
    validate_state_columns(panel, state_names, spec)

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

    print("\n=== State Results ===")
    print(f"{'State':30s} {'Avg IC':>8s} {'Lift':>8s} {'Rows':>8s} {'Pos Yrs':>8s}")
    print("-" * 65)
    for _, row in results.sort_values("avg_ic", ascending=False).iterrows():
        lift = (row["avg_ic"] or 0) - baseline_ic
        print(f"{row['name']:30s} {(row['avg_ic'] or 0):+.4f}  {lift:+.4f}  {row['pooled_rows']:7d}  {row['positive_years']}/{row['years']}")

    best = results.sort_values("avg_ic", ascending=False, na_position="last").iloc[0]
    lift = (best["avg_ic"] or 0) - baseline_ic

    if best["avg_ic"] and best["positive_years"] / best["years"] >= 0.7 and best["avg_ic"] > 0.15:
        decision = "PASSED"
    elif best["avg_ic"] and best["avg_ic"] > baseline_ic + 0.02:
        decision = "PASSED"
    elif best["avg_ic"] and best["avg_ic"] > baseline_ic + 0.005:
        decision = "MIXED"
    else:
        decision = "FAILED"

    print(f"\n=== Decision: {decision} ===")
    print(f"Best: {best['name']} (IC={best['avg_ic']}, lift={lift:.4f})")

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "branch": BRANCH_NAME,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "best_state": best["name"],
            "best_avg_ic": float(best["avg_ic"]) if best["avg_ic"] else None,
            "best_lift": float(lift),
            "baseline_ic": float(baseline_ic) if baseline_ic else None,
        },
        artifacts={
            "results": str(results_path),
            "yearly": str(yearly_path),
        },
        metadata={
            "hypothesis": SPEC.hypothesis,
            "state_specs": [s.as_metadata() for s in STATE_SPECS],
        },
    )
    return summary_path


def main():
    run_branch(parse_args())


if __name__ == "__main__":
    main()