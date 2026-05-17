"""
H573: Capacity-Breadth-Signal Triple Amplifier

Hypothesis: 
- H565 found tight+low_breadth = 0.2062 (+0.041 vs tight alone)
- H543 found composite×low_breadth = 0.2364 (+0.107 vs baseline)

Test: Adding tight_capacity to composite×low_breadth creates triple intersection:
tight × low_breadth × signal. The three amplifiers together may exceed any pair.

Pass criterion: triple beats best pair by > +0.01 IC
"""

from __future__ import annotations

import argparse
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
    normalize_time_ticker,
    restrict_years,
)
from src.repo_paths import data_path


BRANCH_NAME = "capacity_breadth_signal_triple"
MODE = "research_branch"


def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="H573: Capacity-Breadth-Signal Triple Test")
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    return parser.parse_args()


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    panel = load_s1_decision_panel(
        S1_DEFAULT_PATH,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )

    order_stats_path = data_path("order_stats/cafef/order_stats_daily.parquet")
    order_df = pd.read_parquet(order_stats_path)
    order_df = order_df.rename(columns={"date": "time"})
    order_df = normalize_time_ticker(order_df, source="order_stats")
    order_df = restrict_years(order_df, start_year=spec.start_year, end_year=spec.end_year, source="order_stats")

    order_df["order_count"] = order_df["buy_order_count"] + order_df["sell_order_count"]
    order_df["order_volume"] = order_df["buy_order_volume"] + order_df["sell_order_volume"]

    panel = panel.merge(order_df[["time", "ticker", "order_count", "order_volume"]], 
                       on=["time", "ticker"], how="left")

    date_breadth = panel.groupby("time")["ticker"].nunique().reset_index()
    date_breadth.columns = ["time", "active_count"]
    breadth_20 = date_breadth["active_count"].quantile(0.20)
    date_breadth["low_breadth"] = date_breadth["active_count"] <= breadth_20
    panel = panel.merge(date_breadth[["time", "low_breadth"]], on="time", how="left")

    if "order_count" in panel.columns and panel["order_count"].notna().any():
        panel["order_count_rank"] = panel.groupby("time", sort=False)["order_count"].rank(pct=True, na_option="keep")
        panel["tight_capacity"] = panel["order_count_rank"] <= 0.2
    elif "order_volume_ratio_rank" in panel.columns:
        panel["tight_capacity"] = panel["order_volume_ratio_rank"] <= 0.2
    else:
        panel["tight_capacity"] = False

    ohlcv_path = data_path("stock/")
    ohlcv_files = sorted(Path(ohlcv_path).glob("gia_lich_su_*_1D.parquet"))[:200]

    dfs = []
    for f in ohlcv_files:
        ticker = f.stem.split("_")[-2]
        df = pd.read_parquet(f)
        df["ticker"] = ticker
        dfs.append(df)

    if dfs:
        ohlcv = pd.concat(dfs, ignore_index=True)
        ohlcv = normalize_time_ticker(ohlcv, source="OHLCV")
        ohlcv = restrict_years(ohlcv, start_year=spec.start_year, end_year=spec.end_year, source="OHLCV")

        ohlcv["daily_return"] = ohlcv.groupby("ticker")["close"].pct_change()
        ohlcv["daily_return_abs"] = ohlcv["daily_return"].abs()
        ohlcv["turnover"] = ohlcv["close"] * ohlcv["volume"] / 1e9
        ohlcv["amihud"] = ohlcv["daily_return_abs"] / (ohlcv["turnover"] + 1e-9)

        amihud_20d = ohlcv.groupby("ticker")["amihud"].transform(lambda x: x.rolling(20, min_periods=10).mean())
        ohlcv["amihud_20d_avg"] = amihud_20d
        ohlcv["amihud_rank"] = ohlcv.groupby("time", sort=False)["amihud_20d_avg"].rank(pct=True, na_option="keep")
        ohlcv["high_illiq"] = ohlcv["amihud_rank"] >= 0.80

        ohlcv["volume_5d_change"] = ohlcv.groupby("ticker")["volume"].pct_change(5)
        ohlcv["vol_change_rank"] = ohlcv.groupby("time", sort=False)["volume_5d_change"].rank(pct=True, na_option="keep")
        ohlcv["vol_expansion"] = ohlcv["vol_change_rank"] >= 0.80

        panel = panel.merge(
            ohlcv[["time", "ticker", "high_illiq", "vol_expansion"]],
            on=["time", "ticker"],
            how="left"
        )
    else:
        panel["high_illiq"] = False
        panel["vol_expansion"] = False

    panel["c23_signal"] = panel["high_illiq"] & panel["vol_expansion"]

    if "order_count" in panel.columns and panel["order_count"].notna().any():
        panel["tight_capacity"] = panel["order_count_rank"] <= 0.2
    else:
        panel["tight_capacity"] = panel["order_volume_ratio_rank"] <= 0.2

    panel["tight_low_breadth"] = panel["tight_capacity"] & panel["low_breadth"]
    panel["signal_low_breadth"] = panel["c23_signal"] & panel["low_breadth"]
    panel["triple"] = panel["tight_capacity"] & panel["low_breadth"] & panel["c23_signal"]

    print(f"Panel rows: {len(panel)}")
    print(f"Tight capacity rows: {panel['tight_capacity'].sum()}")
    print(f"Low breadth dates: {panel['low_breadth'].sum()}")
    print(f"C23 signal rows: {panel['c23_signal'].sum()}")
    print(f"Triple intersection: {panel['triple'].sum()}")

    return panel


def run_branch(args: argparse.Namespace) -> str:
    spec = ExperimentSpec(
        name=BRANCH_NAME,
        mode=MODE,
        hypothesis=(
            "Test capacity × breadth × signal triple intersection. "
            "H565 tight+low=0.2062, H543 composite+low=0.2364. "
            "Add tight capacity to composite+low for triple."
        ),
        start_year=2015,
        end_year=2025,
        min_year_rows=500,
        min_phase_rows=500,
        target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
        score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
    )
    context = build_experiment_context(spec, artifact_subdir="research_branch")

    panel = load_panel(args, spec)

    STATE_SPECS = [
        StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
        StateSpec("tight_capacity", "Tight capacity (low order count)", family="capacity"),
        StateSpec("low_breadth", "Low breadth dates", family="breadth"),
        StateSpec("c23_signal", "C23 signal (high_illiq × vol_expansion)", family="signal"),
        StateSpec("tight_low_breadth", "Tight capacity + Low breadth", family="combo"),
        StateSpec("signal_low_breadth", "C23 signal + Low breadth", family="combo"),
        StateSpec("triple", "Tight + Low breadth + C23 signal", family="triple"),
    ]

    available_cols = [s.name for s in STATE_SPECS if s.name in panel.columns]
    STATE_SPECS = [s for s in STATE_SPECS if s.name in available_cols]

    validate_state_columns(panel, [state.name for state in STATE_SPECS], spec)

    results, yearly = evaluate_state_specs(
        panel,
        STATE_SPECS,
        score_col="s1_xs_proba",
        target_col="s1_barrier_hit_1d",
        spec=spec,
    )

    results_path = write_dataframe_artifact(results, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")

    print("=== H573: Capacity-Breadth-Signal Triple Test ===")
    print(results[["name", "avg_ic", "positive_years", "years", "pooled_rows"]].sort_values("avg_ic", ascending=False).to_string(index=False))

    baseline = results[results["name"] == "all_rows"]["avg_ic"].iloc[0] if "all_rows" in results["name"].values else results["avg_ic"].mean()
    tight = results[results["name"] == "tight_capacity"]["avg_ic"].iloc[0] if "tight_capacity" in results["name"].values else 0.0
    signal = results[results["name"] == "c23_signal"]["avg_ic"].iloc[0] if "c23_signal" in results["name"].values else 0.0
    combo_tight_low = results[results["name"] == "tight_low_breadth"]["avg_ic"].iloc[0] if "tight_low_breadth" in results["name"].values else 0.0
    combo_signal_low = results[results["name"] == "signal_low_breadth"]["avg_ic"].iloc[0] if "signal_low_breadth" in results["name"].values else 0.0
    triple = results[results["name"] == "triple"]["avg_ic"].iloc[0] if "triple" in results["name"].values else 0.0

    best_pair = max(combo_tight_low, combo_signal_low)
    triple_vs_best = triple - best_pair

    if triple_vs_best > 0.01:
        decision = "PASSED"
    elif triple_vs_best > 0.005:
        decision = "MIXED"
    else:
        decision = "FAILED"

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": baseline,
            "tight_capacity_ic": tight,
            "c23_signal_ic": signal,
            "tight_low_breadth_ic": combo_tight_low,
            "signal_low_breadth_ic": combo_signal_low,
            "triple_ic": triple,
            "triple_vs_best_pair": triple_vs_best,
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": "capacity × breadth × signal triple",
        },
    )

    print(f"\nBaseline IC: {baseline:.4f}")
    print(f"Tight Capacity IC: {tight:.4f}")
    print(f"C23 Signal IC: {signal:.4f}")
    print(f"Tight + Low Breadth IC: {combo_tight_low:.4f}")
    print(f"Signal + Low Breadth IC: {combo_signal_low:.4f}")
    print(f"Triple (Tight + Low + Signal) IC: {triple:.4f}")
    print(f"Triple vs Best Pair: {triple_vs_best:.4f}")
    print(f"\nDecision: {decision}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()