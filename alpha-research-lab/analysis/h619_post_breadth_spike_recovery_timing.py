"""
H619 - Post-Breadth-Spike Recovery Timing

Hypothesis:
Composite multi-signal during low-breadth recovery windows after recent
breadth spikes may outperform the base composite_2plus_low_breadth regime.

Definition:
- high_breadth_day: breadth pct rank >= 0.8
- low_breadth_day: breadth pct rank <= 0.2
- post_spike_recovery: low_breadth_day AND any high_breadth_day in prior 5 days

Decision:
- PASSED: combo IC > baseline IC by +0.01
- MIXED: combo IC > baseline IC
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


BRANCH_NAME = "h619_post_breadth_spike_recovery_timing"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Test composite_2plus × low_breadth × post_spike_recovery vs "
        "composite_2plus × low_breadth baseline."
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
    StateSpec("composite_2plus_low_breadth", "2+ signals AND low breadth", family="baseline_combo"),
    StateSpec("composite_2plus_low_breadth_post_spike", "2+ signals AND low breadth AND post-spike recovery", family="combo"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H619: post-breadth-spike recovery timing")
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument(
        "--order-stats-path",
        type=str,
        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")),
    )
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
        S1_DEFAULT_PATH,
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
    panel = panel.merge(ohlcv[["time", "ticker", "amihud_20d_avg"]], on=["time", "ticker"], how="left")

    order_stats = pd.read_parquet(args.order_stats_path)
    order_stats = order_stats.rename(columns={"date": "time"})
    order_stats["time"] = pd.to_datetime(order_stats["time"])
    order_stats = order_stats[order_stats["time"].dt.year <= spec.end_year]
    order_stats["pct_change"] = order_stats["price_change_raw"].apply(_parse_price_change)
    order_stats["total_volume"] = order_stats["buy_order_volume"] + order_stats["sell_order_volume"]
    panel = panel.merge(
        order_stats[["time", "ticker", "pct_change", "total_volume", "buy_order_volume", "sell_order_volume"]],
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
    amihud_rank = panel.groupby("time", sort=False)["amihud_20d_avg"].rank(method="average", pct=True)
    panel["high_illiq"] = amihud_rank >= 0.8
    panel["buy_sell_imbalance"] = (
        (panel["buy_order_volume"] - panel["sell_order_volume"])
        / (panel["buy_order_volume"] + panel["sell_order_volume"] + 1)
    )
    imbalance_rank = panel.groupby("time", sort=False)["buy_sell_imbalance"].rank(method="average", pct=True)
    panel["buy_heavy"] = imbalance_rank >= 0.8
    panel["c23"] = panel["high_illiq"] & panel["vol_expansion"]
    panel["c24"] = (panel["pct_change"] >= 5.0) & panel["vol_expansion"]
    panel["c25"] = (panel["pct_change"] <= -2.0) & panel["vol_expansion"]
    panel["c26"] = panel["buy_heavy"] & panel["high_illiq"] & panel["vol_expansion"]
    panel["signal_count"] = (
        panel["c23"].astype(int) + panel["c24"].astype(int) + panel["c25"].astype(int) + panel["c26"].astype(int)
    )
    panel["composite_2plus"] = panel["signal_count"] >= 2

    day_breadth = panel.groupby("time")["signal_count"].apply(lambda x: (x >= 1).sum()).rename("active_names").reset_index()
    day_total = panel.groupby("time")["ticker"].nunique().rename("total_names").reset_index()
    day_stats = day_breadth.merge(day_total, on="time", how="inner")
    day_stats["breadth_fraction"] = day_stats["active_names"] / day_stats["total_names"].clip(lower=1)
    day_stats["breadth_rank"] = day_stats["breadth_fraction"].rank(method="average", pct=True)
    day_stats["low_breadth"] = day_stats["breadth_rank"] <= 0.20
    day_stats["high_breadth"] = day_stats["breadth_rank"] >= 0.80
    day_stats = day_stats.sort_values("time").copy()
    day_stats["recent_high_spike"] = day_stats["high_breadth"].shift(1).rolling(window=5, min_periods=1).max().fillna(0).astype(bool)
    day_stats["post_spike_recovery"] = day_stats["low_breadth"] & day_stats["recent_high_spike"]

    panel = panel.merge(
        day_stats[["time", "low_breadth", "post_spike_recovery"]],
        on="time",
        how="left",
    )
    panel["composite_2plus_low_breadth"] = panel["composite_2plus"] & panel["low_breadth"]
    panel["composite_2plus_low_breadth_post_spike"] = (
        panel["composite_2plus"] & panel["low_breadth"] & panel["post_spike_recovery"]
    )
    return panel


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(SPEC, start_year=int(args.start_year), end_year=int(args.end_year))
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
        return float(row["avg_ic"].iloc[0]) if not row.empty and pd.notna(row["avg_ic"].iloc[0]) else np.nan

    combo_ic = _ic("composite_2plus_low_breadth_post_spike")
    base_ic = _ic("composite_2plus_low_breadth")
    lift = combo_ic - base_ic if pd.notna(combo_ic) and pd.notna(base_ic) else np.nan

    if pd.isna(lift):
        decision = "FAILED"
    elif lift > 0.01:
        decision = "PASSED"
    elif lift > 0:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "composite_2plus_low_breadth_ic": base_ic,
            "composite_2plus_low_breadth_post_spike_ic": combo_ic,
            "lift_vs_low_breadth": lift,
        },
        artifacts={"results": results_path, "yearly": yearly_path},
        metadata={"state_specs": [state.as_metadata() for state in STATE_SPECS], "hypothesis": SPEC.hypothesis},
    )
    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(f"decision: {decision}")
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()
