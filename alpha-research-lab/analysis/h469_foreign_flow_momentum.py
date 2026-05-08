"""
H469: foreign_flow_momentum

Hypothesis: Foreign flow momentum (acceleration/deceleration) is the edge, not direction alone.
H443 killed raw direction variants. Momentum may be different — accelerating vs decelerating
foreign flow in vol_expansion regime.

Data: data/foreign_flow/cafef/foreign_flow_daily.parquet
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

BRANCH_NAME = "foreign_flow_momentum"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Foreign flow MOMENTUM (acceleration/deceleration) is the signal, not direction alone. "
        "Test foreign net flow momentum × vol_expansion vs forward IC."
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
    StateSpec("ff_accel_exp", "Foreign accelerating + vol expansion", family="ff_momentum"),
    StateSpec("ff_decel_exp", "Foreign decelerating + vol expansion", family="ff_momentum"),
    StateSpec("ff_strong_buy_exp", "Strong foreign buy + vol expansion", family="ff_momentum"),
    StateSpec("ff_strong_sell_exp", "Strong foreign sell + vol expansion", family="ff_momentum"),
    StateSpec("ff_accel_any", "Foreign accelerating (any regime)", family="ff_momentum"),
    StateSpec("ff_decel_any", "Foreign decelerating (any regime)", family="ff_momentum"),
    StateSpec("ff_20d_high_exp", "20d avg flow high + vol expansion", family="ff_momentum"),
    StateSpec("ff_20d_low_exp", "20d avg flow low + vol expansion", family="ff_momentum"),
    StateSpec("ff_5d_spike_exp", "5d flow spike + vol expansion", family="ff_momentum"),
    StateSpec("ff_delta_top20_exp", "Flow delta top 20% + vol expansion", family="ff_momentum"),
    StateSpec("ff_net_pos_top20_exp", "Net positive top 20% + vol expansion", family="ff_momentum"),
    StateSpec("ff_net_neg_bot20_exp", "Net negative bottom 20% + vol expansion", family="ff_momentum"),
]


def load_fflow_data():
    ff = pd.read_parquet(data_path("foreign_flow/cafef/foreign_flow_daily.parquet"))
    ff["date"] = pd.to_datetime(ff["date"])
    ff["ticker"] = ff["ticker"].str.strip()
    ff["net_flow"] = ff["foreign_net_value"] / 1e9
    ff["net_flow_20d"] = ff.groupby("ticker")["net_flow"].transform(
        lambda x: x.rolling(20, min_periods=10).mean()
    )
    ff["net_flow_5d"] = ff.groupby("ticker")["net_flow"].transform(
        lambda x: x.rolling(5, min_periods=3).mean()
    )
    ff["net_flow_delta_5d"] = ff.groupby("ticker")["net_flow"].transform(
        lambda x: x - x.shift(5)
    )
    return ff[["date", "ticker", "net_flow", "net_flow_20d", "net_flow_5d", "net_flow_delta_5d"]]


def compute_vol_regime(df):
    df = df.sort_values(["ticker", "time"]).copy()
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

    ff = load_fflow_data()
    ff_date_map = ff.rename(columns={"date": "time"})
    panel = panel.merge(ff_date_map, on=["time", "ticker"], how="left")

    vol_path = data_path("features/xs_vol_expansion_daily.parquet")
    if vol_path.exists():
        vol = pd.read_parquet(str(vol_path))
        panel = panel.merge(vol[["time", "ticker", "vol_expansion", "vol_expansion_q80"]], on=["time", "ticker"], how="left")
    else:
        price_files = sorted(data_path("stock").glob("gia_lich_su_*_1D.parquet"))
        price_dfs = []
        for f in price_files:
            ticker = f.stem.replace("gia_lich_su_", "").replace("_1D", "")
            df = pd.read_parquet(f)
            if "date" in df.columns and "time" not in df.columns:
                df = df.rename(columns={"date": "time"})
            df["ticker"] = ticker
            price_dfs.append(df[["ticker", "time", "volume"]])
        if price_dfs:
            price_all = pd.concat(price_dfs, ignore_index=True)
            price_all = compute_vol_regime(price_all)
            panel = panel.merge(
                price_all[["ticker", "time", "vol_expansion"]],
                on=["time", "ticker"],
                how="left"
            )

    panel["vol_expansion_q80"] = panel.groupby("time")["vol_expansion"].transform(
        lambda x: x >= x.quantile(0.80)
    )

    ff_cols = ["net_flow", "net_flow_20d", "net_flow_5d", "net_flow_delta_5d", "vol_expansion", "vol_expansion_q80"]
    for c in ff_cols:
        if c not in panel.columns:
            panel[c] = np.nan

    panel["ff_accel"] = panel["net_flow_delta_5d"] > panel.groupby("time")["net_flow_delta_5d"].transform(
        lambda x: x.quantile(0.60)
    )
    panel["ff_decel"] = panel["net_flow_delta_5d"] < panel.groupby("time")["net_flow_delta_5d"].transform(
        lambda x: x.quantile(0.40)
    )
    panel["ff_strong_buy"] = panel["net_flow"] > panel.groupby("time")["net_flow"].transform(
        lambda x: x.quantile(0.75)
    )
    panel["ff_strong_sell"] = panel["net_flow"] < panel.groupby("time")["net_flow"].transform(
        lambda x: x.quantile(0.25)
    )
    panel["ff_20d_high"] = panel["net_flow_20d"] > panel.groupby("time")["net_flow_20d"].transform(
        lambda x: x.quantile(0.80)
    )
    panel["ff_20d_low"] = panel["net_flow_20d"] < panel.groupby("time")["net_flow_20d"].transform(
        lambda x: x.quantile(0.20)
    )
    panel["ff_5d_spike"] = panel["net_flow_delta_5d"] > panel.groupby("time")["net_flow_delta_5d"].transform(
        lambda x: x.quantile(0.80)
    )
    panel["ff_delta_top20"] = panel.groupby("time")["net_flow_delta_5d"].transform(
        lambda x: x >= x.quantile(0.80)
    )
    panel["ff_net_pos_top20"] = panel.groupby("time")["net_flow"].transform(
        lambda x: x >= x.quantile(0.80)
    )
    panel["ff_net_neg_bot20"] = panel.groupby("time")["net_flow"].transform(
        lambda x: x <= x.quantile(0.20)
    )

    panel["ff_accel_exp"] = panel["ff_accel"] & panel["vol_expansion_q80"]
    panel["ff_decel_exp"] = panel["ff_decel"] & panel["vol_expansion_q80"]
    panel["ff_strong_buy_exp"] = panel["ff_strong_buy"] & panel["vol_expansion_q80"]
    panel["ff_strong_sell_exp"] = panel["ff_strong_sell"] & panel["vol_expansion_q80"]
    panel["ff_accel_any"] = panel["ff_accel"]
    panel["ff_decel_any"] = panel["ff_decel"]
    panel["ff_20d_high_exp"] = panel["ff_20d_high"] & panel["vol_expansion_q80"]
    panel["ff_20d_low_exp"] = panel["ff_20d_low"] & panel["vol_expansion_q80"]
    panel["ff_5d_spike_exp"] = panel["ff_5d_spike"] & panel["vol_expansion_q80"]
    panel["ff_delta_top20_exp"] = panel["ff_delta_top20"] & panel["vol_expansion_q80"]
    panel["ff_net_pos_top20_exp"] = panel["ff_net_pos_top20"] & panel["vol_expansion_q80"]
    panel["ff_net_neg_bot20_exp"] = panel["ff_net_neg_bot20"] & panel["vol_expansion_q80"]

    return panel


def parse_args():
    parser = argparse.ArgumentParser(description="H469: foreign_flow_momentum")
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
    baseline_lift = 0.0

    print("\n=== State Results ===")
    print(f"{'State':30s} {'Avg IC':>8s} {'Lift':>8s} {'Rows':>8s} {'Pos Yrs':>8s} {'Phase IC':>10s}")
    print("-" * 75)
    for _, row in results.sort_values("avg_ic", ascending=False).iterrows():
        lift = (row["avg_ic"] or 0) - baseline_ic
        phase_ic_val = row.get("dev_ic") or row.get("confirmation_ic") or 0
        print(f"{row['name']:30s} {(row['avg_ic'] or 0):+.4f}  {lift:+.4f}  {row['pooled_rows']:7d}  {row['positive_years']}/{row['years']}  {phase_ic_val:+.4f}")

    best = results.sort_values("avg_ic", ascending=False, na_position="last").iloc[0]

    if best["avg_ic"] and best["positive_years"] / best["years"] >= 0.7 and best["avg_ic"] > 0.15:
        decision = "PASSED"
    elif best["avg_ic"] and best["avg_ic"] > baseline_ic + 0.02:
        decision = "PASSED"
    elif best["avg_ic"] and best["avg_ic"] > baseline_ic + 0.005:
        decision = "MIXED"
    else:
        decision = "FAILED"

    print(f"\n=== Decision: {decision} ===")
    print(f"Best state: {best['name']} (IC={best['avg_ic']}, lift={lift:.4f})")

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