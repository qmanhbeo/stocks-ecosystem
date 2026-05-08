"""
H471: order_flow_microstructure_regime

Hypothesis: Order flow imbalance in vol_expansion captures hidden institutional flow.
H451/H453 showed buy/sell imbalance works. H451 tested level, H453 tested delta.
Now test: imbalance RATIO (buy/sell) × vol_expansion × illiquidity as a combined filter.

Data: data/order_stats/cafef/order_stats_daily.parquet
Compare with: C16 baseline, C21a/C21b baselines.

D041 found signals are NOT orthogonal — vol_expansion is shared driver.
This test: check if order flow imbalance adds to vol_expansion independently.
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

BRANCH_NAME = "order_flow_microstructure_regime"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Order flow imbalance × vol_expansion × illiquidity is a combined signal. "
        "D041 found vol_expansion is the universal amplifier — test if imbalance is "
        "independent driver or just echoes vol_expansion."
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
    StateSpec("buy_heavy_exp", "Buy-heavy imbalance + vol expansion", family="of_micro"),
    StateSpec("sell_heavy_exp", "Sell-heavy imbalance + vol expansion", family="of_micro"),
    StateSpec("buy_heavy_no_regime", "Buy-heavy imbalance (any regime)", family="of_micro"),
    StateSpec("sell_heavy_no_regime", "Sell-heavy imbalance (any regime)", family="of_micro"),
    StateSpec("buy_heavy_illiq_exp", "Buy-heavy + illiq + vol expansion", family="of_micro"),
    StateSpec("sell_heavy_illiq_exp", "Sell-heavy + illiq + vol expansion", family="of_micro"),
    StateSpec("large_order_buy_exp", "Large avg buy order + vol expansion", family="of_micro"),
    StateSpec("large_order_sell_exp", "Large avg sell order + vol expansion", family="of_micro"),
    StateSpec("order_count_spike_exp", "High order count + vol expansion", family="of_micro"),
    StateSpec("fragmentation_high_exp", "High fragmentation + vol expansion", family="of_micro"),
    StateSpec("fragmentation_low_exp", "Low fragmentation + vol expansion", family="of_micro"),
    StateSpec("buy_heavy_exp_no_illiq", "Buy-heavy + vol expansion (no illiq)", family="of_micro"),
    StateSpec("sell_heavy_exp_no_illiq", "Sell-heavy + vol expansion (no illiq)", family="of_micro"),
]


def load_order_stats():
    os = pd.read_parquet(data_path("order_stats/cafef/order_stats_daily.parquet"))
    os["date"] = pd.to_datetime(os["date"])
    os["ticker"] = os["ticker"].str.strip()

    os["buy_order_count"] = pd.to_numeric(os["buy_order_count"], errors="coerce").fillna(0)
    os["sell_order_count"] = pd.to_numeric(os["sell_order_count"], errors="coerce").fillna(0)
    os["buy_order_volume"] = pd.to_numeric(os["buy_order_volume"], errors="coerce").fillna(0)
    os["sell_order_volume"] = pd.to_numeric(os["sell_order_volume"], errors="coerce").fillna(0)
    os["avg_buy_order_volume"] = pd.to_numeric(os["avg_buy_order_volume"], errors="coerce").fillna(0)
    os["avg_sell_order_volume"] = pd.to_numeric(os["avg_sell_order_volume"], errors="coerce").fillna(0)

    os["imbalance_level"] = (os["buy_order_volume"] - os["sell_order_volume"]) / (
        os["buy_order_volume"] + os["sell_order_volume"] + 1
    )
    os["buy_heavy"] = os["imbalance_level"] > 0.05
    os["sell_heavy"] = os["imbalance_level"] < -0.05

    os["avg_buy_rank"] = os.groupby("date")["avg_buy_order_volume"].transform(
        lambda x: x.rank(pct=True, na_option="keep")
    )
    os["avg_sell_rank"] = os.groupby("date")["avg_sell_order_volume"].transform(
        lambda x: x.rank(pct=True, na_option="keep")
    )
    os["large_buy_order"] = os["avg_buy_rank"] >= 0.75
    os["large_sell_order"] = os["avg_sell_rank"] >= 0.75

    os["order_count_total"] = os["buy_order_count"] + os["sell_order_count"]
    os["order_count_rank"] = os.groupby("date")["order_count_total"].transform(
        lambda x: x.rank(pct=True, na_option="keep")
    )
    os["order_count_spike"] = os["order_count_rank"] >= 0.80

    volume_total = os["buy_order_volume"] + os["sell_order_volume"]
    count_total = os["buy_order_count"] + os["sell_order_count"]
    os["fragmentation"] = np.log1p(count_total) / (np.log1p(volume_total / 1e6) + 1)
    os["frag_rank"] = os.groupby("date")["fragmentation"].transform(
        lambda x: x.rank(pct=True, na_option="keep")
    )
    os["frag_high"] = os["frag_rank"] >= 0.75
    os["frag_low"] = os["frag_rank"] <= 0.25

    return os[["date", "ticker", "imbalance_level", "buy_heavy", "sell_heavy",
               "large_buy_order", "large_sell_order", "order_count_spike",
               "frag_high", "frag_low", "fragmentation", "avg_buy_order_volume",
               "avg_sell_order_volume"]]


def compute_vol_regime(df):
    df = df.copy()
    if "time" not in df.columns or "ticker" not in df.columns:
        return df
    df = df.sort_values(["ticker", "time"]).copy()
    df["vol_20d"] = df.groupby("ticker")["volume"].transform(
        lambda x: x.rolling(20, min_periods=10).mean()
    )
    df["vol_60d"] = df.groupby("ticker")["volume"].transform(
        lambda x: x.rolling(60, min_periods=20).mean()
    )
    df["vol_expansion"] = (df["vol_20d"] / df["vol_60d"].replace(0, np.nan) - 1).fillna(0)
    return df


def compute_amihud(price_df):
    df = price_df.copy()
    if "time" not in df.columns or "ticker" not in df.columns:
        return df[["ticker", "time"]].assign(illiq_rank=0.5, illiq_high=False)
    ret = df["close"].pct_change(fill_method=None).abs()
    vol = df["volume"] / 1e6
    amihud = (ret / vol.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
    amihud = amihud.fillna(0)
    df["illiq_20d"] = amihud.rolling(20, min_periods=5).mean()
    df["illiq_rank"] = df.groupby("time")["illiq_20d"].transform(
        lambda x: x.rank(pct=True, na_option="keep")
    )
    df["illiq_high"] = df["illiq_rank"] >= 0.70
    return df[["ticker", "time", "illiq_20d", "illiq_rank", "illiq_high"]]


def load_panel(args, spec):
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )

    panel["all_rows"] = True

    os = load_order_stats()
    os_map = os.rename(columns={"date": "time"})
    panel = panel.merge(os_map, on=["time", "ticker"], how="left")

    price_files = sorted(data_path("stock").glob("gia_lich_su_*_1D.parquet"))
    if price_files:
        price_dfs = []
        for f in price_files:
            ticker = f.stem.replace("gia_lich_su_", "").replace("_1D", "")
            df = pd.read_parquet(f)
            if "date" in df.columns and "time" not in df.columns:
                df = df.rename(columns={"date": "time"})
            df["ticker"] = ticker
            price_dfs.append(df[["ticker", "time", "close", "volume"]])
        price_all = pd.concat(price_dfs, ignore_index=True)
        price_all = compute_vol_regime(price_all)
        illiq_df = compute_amihud(price_all[["ticker", "time", "close", "volume"]])
        illiq_df = illiq_df.drop(columns=["close"], errors="ignore")
        price_all = price_all.merge(illiq_df, on=["ticker", "time"], how="left")
        merge_cols = ["ticker", "time", "vol_expansion", "illiq_rank", "illiq_high"]
        merge_cols = [c for c in merge_cols if c in price_all.columns]
        panel = panel.merge(price_all[merge_cols], on=["time", "ticker"], how="left")
    else:
        panel["vol_expansion"] = 0
        panel["illiq_rank"] = 0.5
        panel["illiq_high"] = False

    panel["vol_expansion_q80"] = panel.groupby("time")["vol_expansion"].transform(
        lambda x: x >= x.quantile(0.80)
    )

    missing_cols = ["imbalance_level", "buy_heavy", "sell_heavy", "vol_expansion",
                    "illiq_rank", "illiq_high", "vol_expansion_q80", "large_buy_order",
                    "large_sell_order", "order_count_spike", "frag_high", "frag_low"]
    for c in missing_cols:
        if c not in panel.columns:
            panel[c] = np.nan if panel[c].dtype == object else (False if "bool" in str(panel[c].dtype) else 0)

    panel["buy_heavy_exp"] = panel["buy_heavy"] & panel["vol_expansion_q80"]
    panel["sell_heavy_exp"] = panel["sell_heavy"] & panel["vol_expansion_q80"]
    panel["buy_heavy_no_regime"] = panel["buy_heavy"]
    panel["sell_heavy_no_regime"] = panel["sell_heavy"]
    panel["buy_heavy_illiq_exp"] = panel["buy_heavy"] & panel["illiq_high"] & panel["vol_expansion_q80"]
    panel["sell_heavy_illiq_exp"] = panel["sell_heavy"] & panel["illiq_high"] & panel["vol_expansion_q80"]
    panel["large_order_buy_exp"] = panel["large_buy_order"] & panel["vol_expansion_q80"]
    panel["large_order_sell_exp"] = panel["large_sell_order"] & panel["vol_expansion_q80"]
    panel["order_count_spike_exp"] = panel["order_count_spike"] & panel["vol_expansion_q80"]
    panel["fragmentation_high_exp"] = panel["frag_high"] & panel["vol_expansion_q80"]
    panel["fragmentation_low_exp"] = panel["frag_low"] & panel["vol_expansion_q80"]
    panel["buy_heavy_exp_no_illiq"] = panel["buy_heavy"] & panel["vol_expansion_q80"] & ~panel["illiq_high"]
    panel["sell_heavy_exp_no_illiq"] = panel["sell_heavy"] & panel["vol_expansion_q80"] & ~panel["illiq_high"]

    return panel


def parse_args():
    parser = argparse.ArgumentParser(description="H471: order_flow_microstructure_regime")
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