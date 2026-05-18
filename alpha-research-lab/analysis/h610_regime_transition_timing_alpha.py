"""
H610 - Regime Transition Timing Alpha

Hypothesis:
Low-breadth regime is strong, but the transition moment into low breadth may be
stronger than already-sustained low breadth for composite multi-signal entries.

Test:
- composite_2plus × transition_to_low_breadth
- composite_2plus × sustained_low_breadth
- compare against composite_2plus and composite_2plus_low_breadth

Decision:
- PASSED: transition combo beats sustained combo by > +0.01 IC
- MIXED: transition combo > sustained combo
- FAILED: otherwise
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiment_contract import (  # noqa: E402
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
from src.repo_paths import data_path  # noqa: E402


BRANCH_NAME = "h610_regime_transition_timing_alpha"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Transition moment into low breadth may outperform sustained low breadth "
        "for composite_2plus entries."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=100,
    min_phase_rows=100,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)

STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("composite_2plus", "2+ signals (F445)", family="single"),
    StateSpec("low_breadth", "Low breadth regime", family="breadth"),
    StateSpec("transition_to_low_breadth", "Crossed into low breadth today", family="breadth"),
    StateSpec("sustained_low_breadth", "Already in low breadth (prev day low)", family="breadth"),
    StateSpec("composite_2plus_low_breadth", "2+ signals AND low breadth", family="combo"),
    StateSpec("composite_2plus_transition_low", "2+ signals AND transition-to-low", family="combo"),
    StateSpec("composite_2plus_sustained_low", "2+ signals AND sustained-low", family="combo"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H610: Regime Transition Timing Alpha")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument(
        "--order-stats-path",
        type=str,
        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")),
    )
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    return parser.parse_args()


def _compute_amihud(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["daily_return"] = out.groupby("ticker")["close"].pct_change(fill_method=None)
    out["daily_return_abs"] = out["daily_return"].abs()
    out["turnover_bil"] = (out["close"] * out["volume"]) / 1e9
    out["amihud"] = out["daily_return_abs"] / (out["turnover_bil"] + 1e-9)
    out["amihud_20d_avg"] = out.groupby("ticker")["amihud"].transform(
        lambda s: s.rolling(window=20, min_periods=10).mean()
    )
    return out


def _parse_price_change(value: object) -> float:
    if pd.isna(value):
        return np.nan
    match = re.search(r"\(\s*([+-]?[\d,]+)\s*%\)", str(value))
    if not match:
        return np.nan
    return float(match.group(1).replace(",", "."))


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )

    stock_dir = data_path("stock")
    ohlcv_parts: list[pd.DataFrame] = []
    for parquet_path in Path(stock_dir).glob("gia_lich_su_*_1D.parquet"):
        try:
            one = pd.read_parquet(parquet_path)
            ticker = parquet_path.stem.replace("gia_lich_su_", "").replace("_1D", "")
            one["ticker"] = ticker
            ohlcv_parts.append(one)
        except Exception:
            continue
    if not ohlcv_parts:
        raise RuntimeError("No OHLCV files available under data/stock")

    ohlcv = pd.concat(ohlcv_parts, ignore_index=True)
    ohlcv = ohlcv.rename(columns={"date": "time"})
    ohlcv["time"] = pd.to_datetime(ohlcv["time"])
    ohlcv = ohlcv[ohlcv["time"].dt.year <= spec.end_year]
    ohlcv = _compute_amihud(ohlcv)
    panel = panel.merge(
        ohlcv[["time", "ticker", "amihud_20d_avg"]],
        on=["time", "ticker"],
        how="left",
    )

    order_stats = pd.read_parquet(args.order_stats_path)
    order_stats = order_stats.rename(columns={"date": "time"})
    order_stats["time"] = pd.to_datetime(order_stats["time"])
    order_stats = order_stats[order_stats["time"].dt.year <= spec.end_year]
    order_stats["pct_change"] = order_stats["price_change_raw"].apply(_parse_price_change)
    order_stats["total_volume"] = (
        order_stats["buy_order_volume"] + order_stats["sell_order_volume"]
    )

    panel = panel.merge(
        order_stats[
            ["time", "ticker", "pct_change", "total_volume", "buy_order_volume", "sell_order_volume"]
        ],
        on=["time", "ticker"],
        how="left",
    )
    panel = panel.dropna(subset=["pct_change", "total_volume"]).copy()
    panel = panel[panel["total_volume"] > 0].copy()
    panel = panel.sort_values(["ticker", "time"]).copy()

    panel["pct_change_vol"] = panel.groupby("ticker")["pct_change"].transform(
        lambda s: s.rolling(window=5, min_periods=3).std()
    )
    panel["vol_change"] = panel.groupby("ticker")["pct_change_vol"].transform(lambda s: s.diff())
    panel = panel.dropna(subset=["vol_change"]).copy()
    vol_rank = panel.groupby("time", sort=False)["vol_change"].rank(method="average", pct=True)
    panel["vol_expansion"] = vol_rank >= 0.8

    amihud_rank = panel.groupby("time", sort=False)["amihud_20d_avg"].rank(
        method="average",
        pct=True,
    )
    panel["high_illiq"] = amihud_rank >= 0.8
    panel["buy_sell_imbalance"] = (
        (panel["buy_order_volume"] - panel["sell_order_volume"])
        / (panel["buy_order_volume"] + panel["sell_order_volume"] + 1)
    )
    imbalance_rank = panel.groupby("time", sort=False)["buy_sell_imbalance"].rank(
        method="average",
        pct=True,
    )
    panel["buy_heavy"] = imbalance_rank >= 0.8

    panel["c23_illiq_expansion"] = panel["high_illiq"] & panel["vol_expansion"]
    panel["c24_ceiling_expansion"] = (panel["pct_change"] >= 5.0) & panel["vol_expansion"]
    panel["c25_vwap_expansion"] = (panel["pct_change"] <= -2.0) & panel["vol_expansion"]
    panel["c26_buy_heavy_illiq_exp"] = (
        panel["buy_heavy"] & panel["high_illiq"] & panel["vol_expansion"]
    )
    panel["signal_count"] = (
        panel["c23_illiq_expansion"].astype(int)
        + panel["c24_ceiling_expansion"].astype(int)
        + panel["c25_vwap_expansion"].astype(int)
        + panel["c26_buy_heavy_illiq_exp"].astype(int)
    )
    panel["composite_2plus"] = panel["signal_count"] >= 2

    date_signal_count = panel.groupby("time")["signal_count"].apply(
        lambda x: (x >= 1).sum()
    ).reset_index(name="signal_breadth")
    date_total = panel.groupby("time")["ticker"].nunique().reset_index(name="total_tickers")
    date_stats = date_signal_count.merge(date_total, on="time", how="inner")
    date_stats["breadth_fraction"] = (
        date_stats["signal_breadth"] / date_stats["total_tickers"].clip(lower=1)
    )
    breadth_threshold = date_stats["breadth_fraction"].quantile(0.20)
    date_stats["low_breadth"] = date_stats["breadth_fraction"] <= breadth_threshold
    date_stats = date_stats.sort_values("time")
    date_stats["prev_low_breadth"] = date_stats["low_breadth"].shift(1).fillna(False)
    date_stats["transition_to_low_breadth"] = (
        date_stats["low_breadth"] & (~date_stats["prev_low_breadth"])
    )
    date_stats["sustained_low_breadth"] = (
        date_stats["low_breadth"] & date_stats["prev_low_breadth"]
    )

    panel = panel.merge(
        date_stats[
            [
                "time",
                "low_breadth",
                "transition_to_low_breadth",
                "sustained_low_breadth",
            ]
        ],
        on="time",
        how="left",
    )
    panel["composite_2plus_low_breadth"] = panel["composite_2plus"] & panel["low_breadth"]
    panel["composite_2plus_transition_low"] = (
        panel["composite_2plus"] & panel["transition_to_low_breadth"]
    )
    panel["composite_2plus_sustained_low"] = (
        panel["composite_2plus"] & panel["sustained_low_breadth"]
    )
    return panel


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(
        SPEC,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
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

    def _ic(name: str) -> float:
        row = results[results["name"] == name]
        return (
            float(row["avg_ic"].iloc[0])
            if not row.empty and pd.notna(row["avg_ic"].iloc[0])
            else np.nan
        )

    transition_ic = _ic("composite_2plus_transition_low")
    sustained_ic = _ic("composite_2plus_sustained_low")
    composite_ic = _ic("composite_2plus")
    low_combo_ic = _ic("composite_2plus_low_breadth")
    lift_transition_vs_sustained = (
        transition_ic - sustained_ic
        if pd.notna(transition_ic) and pd.notna(sustained_ic)
        else np.nan
    )

    if pd.isna(lift_transition_vs_sustained):
        decision = "FAILED"
    elif lift_transition_vs_sustained > 0.01:
        decision = "PASSED"
    elif lift_transition_vs_sustained > 0:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "composite_2plus_ic": composite_ic,
            "composite_2plus_low_breadth_ic": low_combo_ic,
            "composite_2plus_transition_low_ic": transition_ic,
            "composite_2plus_sustained_low_ic": sustained_ic,
            "lift_transition_vs_sustained": lift_transition_vs_sustained,
        },
        artifacts={"results": results_path, "yearly": yearly_path},
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": SPEC.hypothesis,
        },
    )
    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(f"decision: {decision}")
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()
