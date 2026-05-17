"""
H523: Cross-Sectional Relative State Encoding

Hypothesis: Relative state encoding (vs market, vs sector) captures info that
absolute state encoding loses.

H510 showed C23 active state is HIGHER in failure years (2017, 2025) than 
success years (2021, 2022). This suggests participation pressure matters.
Relative encoding might capture this better than binary active/quiet.

This branch tests:
- market_percentile: how "active" a ticker is relative to market on each day
- sector_percentile: how "active" a ticker is relative to its sector peers
- relative_active_top20: top 20% market-relative activity
- relative_active_top20_sector: top 20% sector-relative activity
- absolute_vs_relative: compare absolute (binary) vs relative (continuous) encodings

Decision ladder:
- PASS: relative states beat absolute by >+0.01 IC lift
- MIXED: relative shows positive but <+0.01 lift
- FAIL: relative does not beat absolute
"""

from __future__ import annotations

import argparse
import re
from dataclasses import replace
from pathlib import Path
import sys

import numpy as np
import pandas as pd

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


BRANCH_NAME = "cross_sectional_relative_state"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Relative state encoding (vs market, vs sector) captures info that "
        "absolute encoding loses. H510 showed C23 higher in failure years; "
        "relative may capture participation pressure better."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H523 cross-sectional relative state test")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument(
        "--order-stats-path",
        type=str,
        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")),
    )
    parser.add_argument(
        "--c16-path",
        type=str,
        default=str(data_path("features/xs_order_pressure_daily.parquet")),
    )
    parser.add_argument(
        "--sector-path",
        type=str,
        default=str(data_path("features/sector_classification.parquet")),
    )
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    return parser.parse_args()


def _extract_pct(value: object) -> float:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return np.nan
    text = str(value).replace(",", ".")
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*%", text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return np.nan
    m = re.search(r"(-?\d+(?:\.\d+)?)", text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return np.nan
    return np.nan


def _compute_amihud(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["daily_return"] = frame.groupby("ticker")["close"].pct_change()
    frame["daily_return_abs"] = frame["daily_return"].abs()
    frame["turnover"] = frame["close"] * frame["volume"]
    frame["amihud"] = frame["daily_return_abs"] / (frame["turnover"] + 1e-9)
    return frame


def _load_ohlcv_amihud() -> pd.DataFrame:
    stock_dir = data_path("stock")
    parts: list[pd.DataFrame] = []
    for file in stock_dir.glob("gia_lich_su_*_1D.parquet"):
        try:
            part = pd.read_parquet(file, columns=["time", "close", "volume"])
            part["ticker"] = file.stem.replace("gia_lich_su_", "").replace("_1D", "").upper()
            parts.append(part)
        except Exception:
            continue
    if not parts:
        return pd.DataFrame(columns=["time", "ticker", "amihud"])
    merged = pd.concat(parts, ignore_index=True)
    merged["time"] = pd.to_datetime(merged["time"], errors="coerce").dt.normalize()
    merged = merged.dropna(subset=["time", "ticker", "close", "volume"])
    merged = _compute_amihud(merged)
    return merged[["time", "ticker", "amihud"]]


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    """Load S1 panel with absolute and relative state encodings."""
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )

    c16 = pd.read_parquet(args.c16_path, columns=["time", "ticker", "order_volume_ratio_rank"])
    c16["time"] = pd.to_datetime(c16["time"], errors="coerce").dt.normalize()
    c16["ticker"] = c16["ticker"].astype(str).str.upper()
    panel = panel.merge(c16, on=["time", "ticker"], how="left")

    order_stats = pd.read_parquet(args.order_stats_path)
    order_stats["time"] = pd.to_datetime(order_stats["date"], errors="coerce").dt.normalize()
    order_stats["ticker"] = order_stats["ticker"].astype(str).str.upper()
    order_stats["volume_daily"] = order_stats["buy_order_volume"] + order_stats["sell_order_volume"]
    order_stats["vol_change"] = order_stats.groupby("ticker")["volume_daily"].pct_change()
    order_stats["vol_expansion"] = order_stats.groupby("time")["vol_change"].transform(
        lambda x: (x >= x.quantile(0.8)).astype(int)
    )
    order_stats["order_volume_ratio"] = order_stats["buy_order_volume"] / (
        order_stats["sell_order_volume"] + 1e-9
    )
    order_stats["buy_heavy"] = (order_stats["order_volume_ratio"] > 1.0).astype(int)
    order_stats["price_change_pct"] = order_stats["price_change_raw"].map(_extract_pct)
    order_stats["at_ceiling"] = (order_stats["price_change_pct"] >= 6.5).astype(int)
    order_stats["ceiling_2of3"] = (
        order_stats.groupby("ticker")["at_ceiling"].rolling(3, min_periods=3).sum().reset_index(level=0, drop=True) >= 2
    ).astype(int)
    panel = panel.merge(
        order_stats[
            ["time", "ticker", "vol_expansion", "buy_heavy", "ceiling_2of3"]
        ],
        on=["time", "ticker"],
        how="left",
    )

    amihud = _load_ohlcv_amihud()
    panel = panel.merge(amihud, on=["time", "ticker"], how="left")

    sector = pd.read_parquet(args.sector_path)
    sector["ticker"] = sector["symbol"].astype(str).str.upper()
    panel = panel.merge(sector[["ticker", "icb_name2"]], on="ticker", how="left")

    amihud_p80 = panel["amihud"].quantile(0.8)
    panel["high_illiq"] = (panel["amihud"] >= amihud_p80).astype(int)
    panel["c23"] = ((panel["high_illiq"] == 1) & (panel["vol_expansion"] == 1)).astype(int)
    panel["c24"] = (panel["ceiling_2of3"] == 1).astype(int)
    panel["c26"] = ((panel["buy_heavy"] == 1) & (panel["high_illiq"] == 1) & (panel["vol_expansion"] == 1)).astype(int)
    panel["cofire_count"] = panel[["c23", "c24", "c26"]].sum(axis=1)
    panel["cofire_2"] = (panel["cofire_count"] >= 2).astype(int)
    panel["c16_low"] = (panel["order_volume_ratio_rank"] <= 0.2).astype(int)
    panel["c16_low_c23"] = ((panel["c16_low"] == 1) & (panel["c23"] == 1)).astype(int)

    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)
    panel["c23_prev"] = panel.groupby("ticker")["c23"].shift(1).fillna(0).astype(int)
    panel["c23_fresh"] = ((panel["c23"] == 1) & (panel["c23_prev"] == 0)).astype(int)
    panel["c23_carry"] = ((panel["c23"] == 0) & (panel["c23_prev"] == 1)).astype(int)

    panel["state_quiet"] = (panel["cofire_count"] == 0).astype(int)
    panel["state_onset"] = panel["c23_fresh"]
    panel["state_amplified"] = panel["cofire_2"]
    panel["state_router"] = panel["c16_low_c23"]
    panel["state_carry"] = panel["c23_carry"]

    panel["absolute_active"] = ((panel["state_onset"] == 1) | (panel["state_amplified"] == 1) | 
                                  (panel["state_router"] == 1) | (panel["state_carry"] == 1)).astype(int)

    panel = panel.dropna(subset=[S1_SCORE_COL, S1_TARGET_COL])

    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)

    panel["activity_score"] = panel["high_illiq"].fillna(0) * panel["vol_expansion"].fillna(0)

    panel["market_percentile"] = panel.groupby("time")["high_illiq"].rank(
        method="average", pct=True
    )

    panel["market_percentile_combined"] = panel.groupby("time")["activity_score"].rank(
        method="average", pct=True
    )

    panel["sector_percentile"] = panel.groupby(["time", "icb_name2"])["high_illiq"].rank(
        method="average", pct=True
    )

    panel["sector_percentile_combined"] = panel.groupby(["time", "icb_name2"])["activity_score"].rank(
        method="average", pct=True
    )

    panel["relative_active_market_top20"] = (panel["market_percentile_combined"] >= 0.80).astype(int)
    panel["relative_active_market_top10"] = (panel["market_percentile_combined"] >= 0.90).astype(int)

    panel["relative_active_sector_top20"] = (panel["sector_percentile_combined"] >= 0.80).astype(int)
    panel["relative_active_sector_top10"] = (panel["sector_percentile_combined"] >= 0.90).astype(int)

    panel["high_market_relative_low_absolute"] = (
        (panel["relative_active_market_top20"] == 1) & 
        (panel["absolute_active"] == 0)
    ).astype(int)

    panel["high_sector_relative_low_absolute"] = (
        (panel["relative_active_sector_top20"] == 1) & 
        (panel["absolute_active"] == 0)
    ).astype(int)

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("absolute_active", "Absolute: any active state (onset/amp/router/carry)", family="absolute", primary=True),
    StateSpec("state_onset", "Absolute: onset state", family="absolute"),
    StateSpec("state_amplified", "Absolute: amplified state", family="absolute"),
    StateSpec("state_router", "Absolute: router state", family="absolute"),
    StateSpec("state_carry", "Absolute: carry state", family="absolute"),
    StateSpec("relative_active_market_top20", "Relative: top 20% market activity", family="relative_market", primary=True),
    StateSpec("relative_active_market_top10", "Relative: top 10% market activity", family="relative_market"),
    StateSpec("relative_active_sector_top20", "Relative: top 20% sector activity", family="relative_sector", primary=True),
    StateSpec("relative_active_sector_top10", "Relative: top 10% sector activity", family="relative_sector"),
    StateSpec("high_market_relative_low_absolute", "Relative high + Absolute low: market only", family="cross"),
    StateSpec("high_sector_relative_low_absolute", "Relative high + Absolute low: sector only", family="cross"),
]


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(
        SPEC,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
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

    baseline_row = results[results["name"] == "all_rows"].iloc[0]
    baseline_ic = baseline_row["avg_ic"]

    absolute_states = ["absolute_active", "state_onset", "state_amplified", "state_router", "state_carry"]
    absolute_best = results[results["name"].isin(absolute_states)].nlargest(1, "avg_ic")
    absolute_best_ic = absolute_best.iloc[0]["avg_ic"] if not absolute_best.empty else baseline_ic

    relative_market_states = ["relative_active_market_top20", "relative_active_market_top10"]
    relative_market_best = results[results["name"].isin(relative_market_states)].nlargest(1, "avg_ic")
    relative_market_best_ic = relative_market_best.iloc[0]["avg_ic"] if not relative_market_best.empty else baseline_ic

    relative_sector_states = ["relative_active_sector_top20", "relative_active_sector_top10"]
    relative_sector_best = results[results["name"].isin(relative_sector_states)].nlargest(1, "avg_ic")
    relative_sector_best_ic = relative_sector_best.iloc[0]["avg_ic"] if not relative_sector_best.empty else baseline_ic

    cross_states = ["high_market_relative_low_absolute", "high_sector_relative_low_absolute"]
    cross_best = results[results["name"].isin(cross_states)].nlargest(1, "avg_ic")
    cross_best_ic = cross_best.iloc[0]["avg_ic"] if not cross_best.empty else baseline_ic

    best_relative = max(relative_market_best_ic, relative_sector_best_ic)
    relative_vs_absolute_lift = best_relative - absolute_best_ic if absolute_best_ic > baseline_ic else 0

    if relative_vs_absolute_lift > 0.01:
        decision = "PASSED"
    elif relative_vs_absolute_lift > 0:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "absolute_best_ic": float(absolute_best_ic),
            "relative_market_best_ic": float(relative_market_best_ic),
            "relative_sector_best_ic": float(relative_sector_best_ic),
            "cross_best_ic": float(cross_best_ic),
            "relative_vs_absolute_lift": float(relative_vs_absolute_lift),
            "best_relative_state": relative_market_best.iloc[0]["name"] if relative_market_best_ic > relative_sector_best_ic else relative_sector_best.iloc[0]["name"],
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": "Relative state encoding captures info absolute loses",
        },
    )

    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(f"\nBaseline IC: {baseline_ic:.4f}")
    print(f"Absolute best IC: {absolute_best_ic:.4f}")
    print(f"Relative market best IC: {relative_market_best_ic:.4f}")
    print(f"Relative sector best IC: {relative_sector_best_ic:.4f}")
    print(f"Cross state best IC: {cross_best_ic:.4f}")
    print(f"Relative vs Absolute lift: {relative_vs_absolute_lift:.4f}")
    print(f"decision: {decision}")
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()