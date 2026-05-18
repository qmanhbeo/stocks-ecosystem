"""
H615 - Signal Concentration × Breadth Interaction

Hypothesis:
Breadth and concentration may interact for composite_2plus quality.

Test:
- composite_2plus within 4 regimes:
  - low breadth × high concentration
  - low breadth × low concentration
  - high breadth × high concentration
  - high breadth × low concentration

Decision:
- PASSED: best low-breadth regime beats best high-breadth regime by > +0.01 IC
- MIXED: best low-breadth regime > best high-breadth regime
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


BRANCH_NAME = "h615_signal_concentration_breadth_interaction"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Test 4-way interaction on composite_2plus: breadth (low/high) × "
        "signal concentration (high/low)."
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
    StateSpec("c2_low_breadth_high_conc", "2+ × low breadth × high concentration", family="interaction"),
    StateSpec("c2_low_breadth_low_conc", "2+ × low breadth × low concentration", family="interaction"),
    StateSpec("c2_high_breadth_high_conc", "2+ × high breadth × high concentration", family="interaction"),
    StateSpec("c2_high_breadth_low_conc", "2+ × high breadth × low concentration", family="interaction"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H615: concentration × breadth interaction")
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
    panel["c23_illiq_expansion"] = panel["high_illiq"] & panel["vol_expansion"]
    panel["c24_ceiling_expansion"] = (panel["pct_change"] >= 5.0) & panel["vol_expansion"]
    panel["c25_vwap_expansion"] = (panel["pct_change"] <= -2.0) & panel["vol_expansion"]
    panel["c26_buy_heavy_illiq_exp"] = panel["buy_heavy"] & panel["high_illiq"] & panel["vol_expansion"]
    panel["signal_count"] = (
        panel["c23_illiq_expansion"].astype(int)
        + panel["c24_ceiling_expansion"].astype(int)
        + panel["c25_vwap_expansion"].astype(int)
        + panel["c26_buy_heavy_illiq_exp"].astype(int)
    )
    panel["composite_2plus"] = panel["signal_count"] >= 2

    day_breadth = panel.groupby("time")["signal_count"].apply(lambda x: (x >= 1).sum()).rename("active_names").reset_index()
    day_total = panel.groupby("time")["ticker"].nunique().rename("total_names").reset_index()
    day_stats = day_breadth.merge(day_total, on="time", how="inner")
    day_stats["breadth_fraction"] = day_stats["active_names"] / day_stats["total_names"].clip(lower=1)
    low_thr = day_stats["breadth_fraction"].quantile(0.20)
    high_thr = day_stats["breadth_fraction"].quantile(0.80)
    day_stats["low_breadth"] = day_stats["breadth_fraction"] <= low_thr
    day_stats["high_breadth"] = day_stats["breadth_fraction"] >= high_thr

    conc = panel.groupby("time")[S1_SCORE_COL].agg(total="sum").reset_index()
    top5 = (
        panel.sort_values(["time", S1_SCORE_COL], ascending=[True, False])
        .groupby("time")
        .head(5)
        .groupby("time")[S1_SCORE_COL]
        .sum()
        .rename("top5_sum")
        .reset_index()
    )
    conc = conc.merge(top5, on="time", how="left")
    conc["top5_sum"] = conc["top5_sum"].fillna(0.0)
    conc["conc_ratio"] = conc["top5_sum"] / conc["total"].replace(0, np.nan)
    conc["conc_rank"] = conc["conc_ratio"].rank(method="average", pct=True)
    conc["high_conc"] = conc["conc_rank"] >= 0.80
    conc["low_conc"] = conc["conc_rank"] <= 0.20

    day_stats = day_stats.merge(conc[["time", "high_conc", "low_conc"]], on="time", how="left")
    panel = panel.merge(day_stats[["time", "low_breadth", "high_breadth", "high_conc", "low_conc"]], on="time", how="left")

    panel["c2_low_breadth_high_conc"] = panel["composite_2plus"] & panel["low_breadth"] & panel["high_conc"]
    panel["c2_low_breadth_low_conc"] = panel["composite_2plus"] & panel["low_breadth"] & panel["low_conc"]
    panel["c2_high_breadth_high_conc"] = panel["composite_2plus"] & panel["high_breadth"] & panel["high_conc"]
    panel["c2_high_breadth_low_conc"] = panel["composite_2plus"] & panel["high_breadth"] & panel["low_conc"]
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

    low_a = _ic("c2_low_breadth_high_conc")
    low_b = _ic("c2_low_breadth_low_conc")
    high_a = _ic("c2_high_breadth_high_conc")
    high_b = _ic("c2_high_breadth_low_conc")
    best_low = np.nanmax([low_a, low_b])
    best_high = np.nanmax([high_a, high_b])
    lift_best_low_vs_best_high = best_low - best_high if pd.notna(best_low) and pd.notna(best_high) else np.nan

    def _row(name: str) -> pd.Series:
        sub = results[results["name"] == name]
        return sub.iloc[0] if not sub.empty else pd.Series(dtype=object)

    low_name = "c2_low_breadth_high_conc" if pd.notna(low_a) and (not pd.notna(low_b) or low_a >= low_b) else "c2_low_breadth_low_conc"
    high_name = "c2_high_breadth_high_conc" if pd.notna(high_a) and (not pd.notna(high_b) or high_a >= high_b) else "c2_high_breadth_low_conc"
    low_row = _row(low_name)
    high_row = _row(high_name)
    low_years = int(low_row.get("years", 0)) if not low_row.empty else 0
    high_years = int(high_row.get("years", 0)) if not high_row.empty else 0
    low_conf_rows = int(low_row.get("confirmation_rows", 0)) if not low_row.empty else 0
    high_conf_rows = int(high_row.get("confirmation_rows", 0)) if not high_row.empty else 0
    robust_support = (
        low_years >= 8
        and high_years >= 8
        and low_conf_rows >= 100
        and high_conf_rows >= 100
    )

    if pd.isna(lift_best_low_vs_best_high):
        decision = "FAILED"
    elif lift_best_low_vs_best_high > 0.01 and robust_support:
        decision = "PASSED"
    elif lift_best_low_vs_best_high > 0:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "c2_low_breadth_high_conc_ic": low_a,
            "c2_low_breadth_low_conc_ic": low_b,
            "c2_high_breadth_high_conc_ic": high_a,
            "c2_high_breadth_low_conc_ic": high_b,
            "best_low_ic": best_low,
            "best_high_ic": best_high,
            "lift_best_low_vs_best_high": lift_best_low_vs_best_high,
            "best_low_state": low_name,
            "best_high_state": high_name,
            "low_years": low_years,
            "high_years": high_years,
            "low_confirmation_rows": low_conf_rows,
            "high_confirmation_rows": high_conf_rows,
            "robust_support": robust_support,
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
