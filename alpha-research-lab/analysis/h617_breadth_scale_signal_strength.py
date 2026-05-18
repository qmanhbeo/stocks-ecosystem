"""
H617 - Breadth-Scale Signal Strength Regression

Hypothesis:
The breadth effect on composite_2plus may be continuous rather than purely
binary.

Test:
1) IC by breadth quintile within composite_2plus.
2) Continuous breadth scaling on composite_2plus score vs binary low-breadth
   gate benchmark.

Decision:
- PASSED: continuous-scaled IC beats binary gate by +0.01
- MIXED: quintile trend exists but continuous-scaled IC does not beat binary
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


BRANCH_NAME = "h617_breadth_scale_signal_strength"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Test whether breadth effect is continuous by comparing quintile trend "
        "and continuous scaling vs binary low-breadth gate on composite_2plus."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=100,
    min_phase_rows=100,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={
        S1_SCORE_COL: "decision-time S1 probability score",
        "s1_xs_proba_breadth_continuous": "S1 score scaled by (1 - breadth_pct_rank) on composite_2plus rows",
    },
)

STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("composite_2plus", "2+ signals (F445)", family="single"),
    StateSpec("composite_2plus_low_breadth", "2+ signals AND low breadth (binary gate)", family="binary"),
    StateSpec("composite_2plus_q1", "2+ signals in breadth quintile Q1 (lowest)", family="quintile"),
    StateSpec("composite_2plus_q2", "2+ signals in breadth quintile Q2", family="quintile"),
    StateSpec("composite_2plus_q3", "2+ signals in breadth quintile Q3", family="quintile"),
    StateSpec("composite_2plus_q4", "2+ signals in breadth quintile Q4", family="quintile"),
    StateSpec("composite_2plus_q5", "2+ signals in breadth quintile Q5 (highest)", family="quintile"),
]

COMPOSITE_ONLY_SPEC = [StateSpec("composite_2plus", "2+ signals (F445)", family="single", primary=True)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H617: Breadth-scale signal strength")
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
    day_stats["breadth_pct_rank"] = day_stats["breadth_fraction"].rank(method="average", pct=True)
    day_stats["low_breadth"] = day_stats["breadth_pct_rank"] <= 0.20
    day_stats["breadth_quintile"] = np.ceil(day_stats["breadth_pct_rank"] * 5).astype(int).clip(1, 5)

    panel = panel.merge(day_stats[["time", "breadth_pct_rank", "low_breadth", "breadth_quintile"]], on="time", how="left")
    panel["composite_2plus_low_breadth"] = panel["composite_2plus"] & panel["low_breadth"]
    for q in range(1, 6):
        panel[f"composite_2plus_q{q}"] = panel["composite_2plus"] & (panel["breadth_quintile"] == q)

    panel["s1_xs_proba_breadth_continuous"] = panel[S1_SCORE_COL]
    comp_mask = panel["composite_2plus"]
    panel.loc[comp_mask, "s1_xs_proba_breadth_continuous"] = (
        panel.loc[comp_mask, S1_SCORE_COL] * (1.0 - panel.loc[comp_mask, "breadth_pct_rank"])
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
    cont_results, cont_yearly = evaluate_state_specs(
        panel,
        COMPOSITE_ONLY_SPEC,
        score_col="s1_xs_proba_breadth_continuous",
        target_col=S1_TARGET_COL,
        spec=spec,
    )

    def _ic(df: pd.DataFrame, name: str) -> float:
        row = df[df["name"] == name]
        return float(row["avg_ic"].iloc[0]) if not row.empty and pd.notna(row["avg_ic"].iloc[0]) else np.nan

    q_ics = [_ic(results, f"composite_2plus_q{q}") for q in range(1, 6)]
    valid = [(q, ic) for q, ic in enumerate(q_ics, 1) if pd.notna(ic)]
    if len(valid) >= 3:
        x = np.array([q for q, _ in valid], dtype=float)
        y = np.array([ic for _, ic in valid], dtype=float)
        quintile_corr = float(np.corrcoef(x, y)[0, 1])
    else:
        quintile_corr = np.nan

    binary_ic = _ic(results, "composite_2plus_low_breadth")
    continuous_ic = _ic(cont_results, "composite_2plus")
    lift_cont_vs_binary = continuous_ic - binary_ic if pd.notna(continuous_ic) and pd.notna(binary_ic) else np.nan

    trend_exists = pd.notna(quintile_corr) and (quintile_corr < -0.6)
    if pd.notna(lift_cont_vs_binary) and lift_cont_vs_binary > 0.01:
        decision = "PASSED"
    elif trend_exists:
        decision = "MIXED"
    else:
        decision = "FAILED"

    results_path = write_dataframe_artifact(results, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")
    cont_results_path = write_dataframe_artifact(cont_results, context, f"{BRANCH_NAME}_continuous_results")
    cont_yearly_path = write_dataframe_artifact(cont_yearly, context, f"{BRANCH_NAME}_continuous_yearly")

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "quintile_ics": {f"q{q}": q_ics[q - 1] for q in range(1, 6)},
            "quintile_corr_q_vs_ic": quintile_corr,
            "binary_low_breadth_ic": binary_ic,
            "continuous_scaled_composite_ic": continuous_ic,
            "lift_continuous_vs_binary": lift_cont_vs_binary,
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
            "continuous_results": cont_results_path,
            "continuous_yearly": cont_yearly_path,
        },
        metadata={"state_specs": [state.as_metadata() for state in STATE_SPECS], "hypothesis": SPEC.hypothesis},
    )
    print(results.sort_values("name").to_string(index=False))
    print("continuous:")
    print(cont_results.to_string(index=False))
    print(f"decision: {decision}")
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()
