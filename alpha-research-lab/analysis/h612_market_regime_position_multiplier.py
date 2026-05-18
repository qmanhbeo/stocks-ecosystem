"""
H612 - Market Regime Position Multiplier

Hypothesis:
Use breadth regime as an exposure multiplier:
- low breadth dates: 1.5x
- high breadth dates: 0.5x
- middle breadth: 1.0x

Test:
- baseline score: s1_xs_proba
- breadth-multiplied score across all rows

Decision:
- PASSED: multiplied IC > baseline IC by +0.01
- MIXED: multiplied IC > baseline IC
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


BRANCH_NAME = "h612_market_regime_position_multiplier"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Breadth regime exposure multiplier (low=1.5x, high=0.5x, mid=1.0x) "
        "improves baseline S1 IC."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=100,
    min_phase_rows=100,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={
        S1_SCORE_COL: "decision-time S1 probability score",
        "s1_xs_proba_breadth_scaled": "S1 score scaled by breadth regime multipliers",
    },
)

ALL_ROWS_SPEC = [StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H612: Market regime position multiplier")
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

    breadth_by_day = panel.groupby("time")["signal_count"].apply(lambda x: (x >= 1).sum()).reset_index(name="active_names")
    total_by_day = panel.groupby("time")["ticker"].nunique().reset_index(name="total_names")
    day_stats = breadth_by_day.merge(total_by_day, on="time", how="inner")
    day_stats["breadth_fraction"] = day_stats["active_names"] / day_stats["total_names"].clip(lower=1)
    low_threshold = day_stats["breadth_fraction"].quantile(0.20)
    high_threshold = day_stats["breadth_fraction"].quantile(0.80)
    day_stats["low_breadth"] = day_stats["breadth_fraction"] <= low_threshold
    day_stats["high_breadth"] = day_stats["breadth_fraction"] >= high_threshold
    day_stats["breadth_multiplier"] = 1.0
    day_stats.loc[day_stats["low_breadth"], "breadth_multiplier"] = 1.5
    day_stats.loc[day_stats["high_breadth"], "breadth_multiplier"] = 0.5

    panel = panel.merge(day_stats[["time", "breadth_multiplier"]], on="time", how="left")
    panel["breadth_multiplier"] = panel["breadth_multiplier"].fillna(1.0)
    panel["s1_xs_proba_breadth_scaled"] = panel[S1_SCORE_COL] * panel["breadth_multiplier"]
    panel["all_rows"] = True
    return panel


def _extract_single_ic(results: pd.DataFrame) -> tuple[float, int]:
    row = results.iloc[0]
    return float(row["avg_ic"]), int(row["pooled_rows"])


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(SPEC, start_year=int(args.start_year), end_year=int(args.end_year))
    context = build_experiment_context(spec, artifact_subdir="research_branches")
    panel = load_panel(args, spec)
    validate_state_columns(panel, ["all_rows"], spec)

    baseline_results, baseline_yearly = evaluate_state_specs(
        panel,
        ALL_ROWS_SPEC,
        score_col=S1_SCORE_COL,
        target_col=S1_TARGET_COL,
        spec=spec,
    )
    scaled_results, scaled_yearly = evaluate_state_specs(
        panel,
        ALL_ROWS_SPEC,
        score_col="s1_xs_proba_breadth_scaled",
        target_col=S1_TARGET_COL,
        spec=spec,
    )

    baseline_ic, pooled_rows = _extract_single_ic(baseline_results)
    scaled_ic, _ = _extract_single_ic(scaled_results)
    lift = scaled_ic - baseline_ic

    compare = pd.DataFrame(
        [
            {"name": "baseline_score", "avg_ic": baseline_ic, "pooled_rows": pooled_rows, "score_col": S1_SCORE_COL},
            {"name": "breadth_scaled_score", "avg_ic": scaled_ic, "pooled_rows": pooled_rows, "score_col": "s1_xs_proba_breadth_scaled"},
        ]
    )
    key_col = "state" if "state" in baseline_yearly.columns else "name"
    yearly_compare = baseline_yearly.rename(columns={"ic": "baseline_ic"})[[key_col, "year", "baseline_ic", "rows"]]
    scaled_yearly_min = scaled_yearly[[key_col, "year", "ic"]].rename(columns={"ic": "scaled_ic"})
    yearly_compare = yearly_compare.merge(scaled_yearly_min, on=[key_col, "year"], how="left")
    yearly_compare["ic_lift"] = yearly_compare["scaled_ic"] - yearly_compare["baseline_ic"]

    results_path = write_dataframe_artifact(compare, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly_compare, context, f"{BRANCH_NAME}_yearly")

    if lift > 0.01:
        decision = "PASSED"
    elif lift > 0:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "baseline_ic": baseline_ic,
            "breadth_scaled_ic": scaled_ic,
            "lift_vs_baseline": lift,
        },
        artifacts={"results": results_path, "yearly": yearly_path},
        metadata={
            "state_specs": [state.as_metadata() for state in ALL_ROWS_SPEC],
            "hypothesis": SPEC.hypothesis,
        },
    )
    print(compare.to_string(index=False))
    print(f"decision: {decision}")
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()
