"""
H609 - Triple-Factor Alpha Portfolio

Hypothesis:
Queue item 109: combine three strong components:
- F445: composite_2plus (2+ signals)
- F440: cofire isolation (Q1, C23 breadth context)
- F441: persistence Q4 (sustained active state)

Test:
- triple intersection vs single factors and pairwise intersections

Decision:
- PASSED: triple IC > composite_2plus IC by +0.01
- MIXED: triple IC > composite_2plus IC
- FAILED: otherwise (including sparse/NaN yearly support)
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


BRANCH_NAME = "h609_triple_factor_alpha_portfolio"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Queue 109 triple-factor: composite_2plus × cofire_q1_c23 × persist_q4 "
        "vs singles/pairs with composite_2plus as primary benchmark."
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
    StateSpec("cofire_q1_c23", "C23 cofire Q1 isolation (F440)", family="single"),
    StateSpec("persist_q4", "Active persistence Q4 (F441)", family="single"),
    StateSpec("composite_2plus_cofire_q1", "Composite 2+ AND cofire Q1", family="pair"),
    StateSpec("composite_2plus_persist_q4", "Composite 2+ AND persist Q4", family="pair"),
    StateSpec("cofire_q1_persist_q4", "Cofire Q1 AND persist Q4", family="pair"),
    StateSpec("triple_factor_109", "Composite 2+ AND cofire Q1 AND persist Q4", family="triple"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H609: Triple-Factor Alpha Portfolio")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument(
        "--order-stats-path",
        type=str,
        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")),
    )
    parser.add_argument(
        "--order-pressure-path",
        type=str,
        default=str(data_path("features/xs_order_pressure_daily.parquet")),
    )
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
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

    # F440-style cofire isolation from C23 day-level crowding.
    c23_counts = panel.groupby("time")["c23_illiq_expansion"].sum().rename("c23_day_count")
    panel = panel.merge(c23_counts, on="time", how="left")
    panel["c23_cofire_count"] = np.where(
        panel["c23_illiq_expansion"],
        panel["c23_day_count"] - 1,
        np.nan,
    )
    c23_mask = panel["c23_illiq_expansion"] & panel["c23_cofire_count"].notna()
    cofire_rank = panel.loc[c23_mask, "c23_cofire_count"].rank(method="average", pct=True)
    panel["cofire_q1_c23"] = False
    panel.loc[c23_mask, "cofire_q1_c23"] = cofire_rank <= 0.25

    # F441-style persistence Q4 from C16 order-pressure active state.
    order_pressure = pd.read_parquet(args.order_pressure_path)
    order_pressure = order_pressure.rename(columns={"date": "time"})
    order_pressure["time"] = pd.to_datetime(order_pressure["time"])
    order_pressure = order_pressure[order_pressure["time"].dt.year <= spec.end_year]
    panel = panel.merge(
        order_pressure[["time", "ticker", "order_volume_ratio_rank"]],
        on=["time", "ticker"],
        how="left",
    )
    panel["active_state"] = panel["order_volume_ratio_rank"] <= 0.2
    panel["active_1d_lag"] = panel.groupby("ticker")["active_state"].shift(1)
    panel["active_9d_count"] = panel.groupby("ticker")["active_1d_lag"].transform(
        lambda s: s.rolling(window=9, min_periods=5).sum()
    )
    panel["persistence_ratio"] = panel["active_9d_count"] / 9.0
    persist_rank = panel.groupby("time", sort=False)["persistence_ratio"].rank(
        method="average",
        pct=True,
    )
    panel["persist_q4"] = persist_rank >= 0.75

    panel["composite_2plus_cofire_q1"] = panel["composite_2plus"] & panel["cofire_q1_c23"]
    panel["composite_2plus_persist_q4"] = panel["composite_2plus"] & panel["persist_q4"]
    panel["cofire_q1_persist_q4"] = panel["cofire_q1_c23"] & panel["persist_q4"]
    panel["triple_factor_109"] = (
        panel["composite_2plus"] & panel["cofire_q1_c23"] & panel["persist_q4"]
    )
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

    triple_ic = _ic("triple_factor_109")
    composite_ic = _ic("composite_2plus")
    cofire_ic = _ic("cofire_q1_c23")
    persist_ic = _ic("persist_q4")
    pair_cofire_ic = _ic("composite_2plus_cofire_q1")
    pair_persist_ic = _ic("composite_2plus_persist_q4")
    pair_two_ic = _ic("cofire_q1_persist_q4")
    lift_vs_composite = triple_ic - composite_ic if pd.notna(triple_ic) and pd.notna(composite_ic) else np.nan

    if pd.isna(lift_vs_composite):
        decision = "FAILED"
    elif lift_vs_composite > 0.01:
        decision = "PASSED"
    elif lift_vs_composite > 0:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "composite_2plus_ic": composite_ic,
            "cofire_q1_c23_ic": cofire_ic,
            "persist_q4_ic": persist_ic,
            "composite_2plus_cofire_q1_ic": pair_cofire_ic,
            "composite_2plus_persist_q4_ic": pair_persist_ic,
            "cofire_q1_persist_q4_ic": pair_two_ic,
            "triple_factor_109_ic": triple_ic,
            "lift_vs_composite_2plus": lift_vs_composite,
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
