"""
H629-H642 batch: resolve remaining open numbered queue items 85-91 and 96-103.

This script uses lightweight proxy constructions when the exact historical
state definition is unavailable in the current shared contract.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.h62x_common import build_base_panel, evaluate_states  # noqa: E402
from src.experiment_contract import (  # noqa: E402
    S1_SCORE_COL,
    S1_TARGET_COL,
    ExperimentSpec,
    build_experiment_context,
    normalize_time_ticker,
    restrict_years,
    write_dataframe_artifact,
)
from src.repo_paths import data_path  # noqa: E402

BRANCH_NAME = "h629_remaining_queue_85_103_batch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode="research_branch",
    hypothesis="Resolve open queue items 85-91 and 96-103 with smallest valid proxy tests.",
    start_year=2015,
    end_year=2025,
    min_year_rows=100,
    min_phase_rows=100,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H629-H642 batch")
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument(
        "--order-stats-path",
        type=str,
        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")),
    )
    return parser.parse_args()


def _safe_float(v: object) -> float | None:
    try:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return None
        return float(v)
    except Exception:
        return None


def _ic(results: pd.DataFrame, name: str) -> float:
    row = results[results["name"] == name]
    if row.empty:
        return np.nan
    return float(row["avg_ic"].iloc[0]) if pd.notna(row["avg_ic"].iloc[0]) else np.nan


def _rows(results: pd.DataFrame, name: str) -> int:
    row = results[results["name"] == name]
    if row.empty:
        return 0
    return int(row["rows"].iloc[0])


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(SPEC, start_year=int(args.start_year), end_year=int(args.end_year))
    context = build_experiment_context(spec, artifact_subdir="research_branches")

    cache_path = str(ROOT / "artifacts" / "cache" / "h62x_base_panel_2015_2025.parquet")
    panel = build_base_panel(
        spec.start_year,
        spec.end_year,
        order_stats_path=args.order_stats_path,
        cache_path=cache_path,
    )

    # Tradability for blocked-state and liquid states (C27 proxy).
    trad_df = pd.read_parquet(data_path("features/execution/tradability_daily.parquet"))
    trad_df = normalize_time_ticker(trad_df, source="tradability")
    trad_df = restrict_years(trad_df, start_year=spec.start_year, end_year=spec.end_year, source="tradability")
    panel = panel.merge(
        trad_df[["time", "ticker", "can_buy_next_open", "can_sell_next_open"]],
        on=["time", "ticker"],
        how="left",
    )
    panel["blocked_either"] = (~panel["can_buy_next_open"].fillna(True)) | (~panel["can_sell_next_open"].fillna(True))
    panel["liquid_either"] = ~panel["blocked_either"]

    # Tight capacity proxy from daily total order count (bottom quintile per day).
    panel["total_order_count"] = panel["buy_order_volume"] * 0.0
    if "buy_order_count" not in panel.columns or "sell_order_count" not in panel.columns:
        order_stats = pd.read_parquet(args.order_stats_path)
        order_stats = order_stats.rename(columns={"date": "time"})
        order_stats["time"] = pd.to_datetime(order_stats["time"])
        order_stats = order_stats[["time", "ticker", "buy_order_count", "sell_order_count"]]
        panel = panel.merge(order_stats, on=["time", "ticker"], how="left")
    panel["total_order_count"] = panel["buy_order_count"].fillna(0) + panel["sell_order_count"].fillna(0)
    panel["order_count_rank"] = panel.groupby("time")["total_order_count"].rank(method="average", pct=True)
    panel["tight_capacity"] = panel["order_count_rank"] <= 0.2

    # Cofire isolation proxy from signal_count.
    panel["any_signal"] = panel["signal_count"] >= 1
    panel["cofire_zero"] = panel["signal_count"] == 1
    panel["cofire_few"] = panel["signal_count"] == 2
    panel["cofire_many"] = panel["signal_count"] >= 3

    # Quiet/active proxy: quiet=no signal, active=any signal.
    panel["state_quiet_proxy"] = panel["signal_count"] == 0
    panel["state_active_proxy"] = panel["signal_count"] >= 1

    # Volatility depth proxy.
    panel["vol_depth_rank"] = panel.groupby("time")["vol_change"].rank(method="average", pct=True)
    panel["vol_depth_mild"] = panel["vol_depth_rank"].between(0.5, 0.7)
    panel["vol_depth_deep"] = panel["vol_depth_rank"] >= 0.9

    # Accumulation proxy (rolling 30d and 60d counts).
    panel = panel.sort_values(["ticker", "time"]).copy()
    panel["accum_30d"] = panel.groupby("ticker")["composite_2plus"].transform(
        lambda s: s.astype(int).rolling(window=30, min_periods=1).sum()
    )
    panel["high_accum"] = panel["accum_30d"] >= 20
    panel["low_accum"] = panel["accum_30d"] <= 7

    # Consecutive active run for onset/sustained tests.
    panel["active_run"] = panel.groupby("ticker")["state_active_proxy"].transform(
        lambda s: s.astype(int).groupby((~s).cumsum()).cumsum()
    )
    prev1 = panel.groupby("ticker")["state_active_proxy"].shift(1).fillna(False)
    prev5sum = panel.groupby("ticker")["state_active_proxy"].transform(
        lambda s: s.shift(1).rolling(window=5, min_periods=5).sum()
    ).fillna(0)
    panel["first_active_after_quiet"] = panel["state_active_proxy"] & (~prev1) & (prev5sum == 0)
    panel["sustained_active_2pl"] = panel["state_active_proxy"] & (panel["active_run"] >= 2)

    # Breadth persistence split.
    daily = panel[["time", "market_active_fraction"]].drop_duplicates().sort_values("time")
    low_cut = float(daily["market_active_fraction"].quantile(0.2))
    daily["breadth_low_today"] = daily["market_active_fraction"] <= low_cut
    daily["breadth_5d_avg"] = daily["market_active_fraction"].rolling(window=5, min_periods=5).mean()
    daily["breadth_persistent_low"] = daily["breadth_5d_avg"] <= low_cut
    panel = panel.merge(daily[["time", "breadth_low_today", "breadth_persistent_low"]], on="time", how="left")
    panel["breadth_transient_low"] = panel["breadth_low_today"] & (~panel["breadth_persistent_low"].fillna(False))

    # Spread concentration proxy using amihud as daily top-5 concentration ratio.
    date_avg = panel.groupby("time", as_index=False)["amihud_20d_avg"].mean().rename(columns={"amihud_20d_avg": "mean_illiq"})
    top5 = (
        panel.sort_values(["time", "amihud_20d_avg"], ascending=[True, False])
        .groupby("time")
        .head(5)
        .groupby("time", as_index=False)["amihud_20d_avg"]
        .mean()
        .rename(columns={"amihud_20d_avg": "top5_illiq"})
    )
    spread_ratio = date_avg.merge(top5, on="time", how="left")
    spread_ratio["top5_spread_concentration"] = spread_ratio["top5_illiq"] / (spread_ratio["mean_illiq"] + 1e-9)
    spread_ratio["spread_conc_q"] = pd.qcut(spread_ratio["top5_spread_concentration"], q=4, labels=False, duplicates="drop") + 1
    panel = panel.merge(spread_ratio[["time", "spread_conc_q"]], on="time", how="left")

    # Order-arrival intensity proxy (daily order count vs own 20d baseline).
    panel["order_count_20d_avg"] = panel.groupby("ticker")["total_order_count"].transform(
        lambda s: s.rolling(window=20, min_periods=10).mean()
    )
    panel["arrival_intensity"] = panel["total_order_count"] / (panel["order_count_20d_avg"] + 1e-9)
    panel["arrival_high"] = panel.groupby("time")["arrival_intensity"].rank(method="average", pct=True) >= 0.8

    # Capacity transition proxy for item 90 (future 2-day class).
    panel["tight_state"] = np.where(panel["order_count_rank"] <= 0.2, "tight", np.where(panel["order_count_rank"] <= 0.5, "mid", "loose"))
    panel["tight_state_t2"] = panel.groupby("ticker")["tight_state"].shift(-2)
    panel["enter_tight"] = panel["tight_capacity"]
    panel["enter_tight_exit_expanding"] = panel["enter_tight"] & (panel["tight_state_t2"] == "loose")
    panel["enter_tight_exit_tight"] = panel["enter_tight"] & (panel["tight_state_t2"] == "tight")
    panel["enter_tight_exit_mid"] = panel["enter_tight"] & (panel["tight_state_t2"] == "mid")

    # Queue-item state definitions.
    state_map: dict[str, list[str]] = {
        "Q85": [
            "quiet_blocked", "quiet_liquid", "active_blocked", "active_liquid",
        ],
        "Q86": [
            "lb_vol_exp", "lb_vol_contr", "hb_vol_exp", "hb_vol_contr",
        ],
        "Q87": ["first_active_after_quiet", "sustained_active_2pl", "state_active_proxy"],
        "Q88": ["tight_blocked", "tight_liquid", "loose_blocked", "loose_liquid"],
        "Q89": ["spread_q1", "spread_q4"],
        "Q90": ["enter_tight_exit_expanding", "enter_tight_exit_tight", "enter_tight_exit_mid"],
        "Q91": ["vol_expansion", "vol_deep", "vol_mild"],
        "Q96": ["cofire_zero", "cofire_few", "cofire_many"],
        "Q97": ["tight_arrival_high", "tight_capacity"],
        "Q98": [
            "c23_low_bq", "c23_high_bq", "c24_low_bq", "c24_high_bq", "c25_low_bq", "c25_high_bq", "c26_low_bq", "c26_high_bq",
        ],
        "Q99": ["triple_amp", "pair_tight_low", "pair_tight_iso", "pair_low_iso"],
        "Q100": ["high_accum_low_breadth", "high_accum", "low_breadth"],
        "Q101": ["was_active_now_inactive", "never_active"],
        "Q102": ["breadth_persistent_low_state", "breadth_transient_low_state"],
        "Q103": ["tight_high_accum", "tight_low_accum"],
    }

    # build raw states
    panel["quiet_blocked"] = panel["state_quiet_proxy"] & panel["blocked_either"]
    panel["quiet_liquid"] = panel["state_quiet_proxy"] & panel["liquid_either"]
    panel["active_blocked"] = panel["state_active_proxy"] & panel["blocked_either"]
    panel["active_liquid"] = panel["state_active_proxy"] & panel["liquid_either"]

    panel["lb_vol_exp"] = panel["low_breadth"] & panel["vol_expansion"]
    panel["lb_vol_contr"] = panel["low_breadth"] & (~panel["vol_expansion"])
    panel["hb_vol_exp"] = (~panel["low_breadth"]) & panel["vol_expansion"]
    panel["hb_vol_contr"] = (~panel["low_breadth"]) & (~panel["vol_expansion"])

    panel["tight_blocked"] = panel["tight_capacity"] & panel["blocked_either"]
    panel["tight_liquid"] = panel["tight_capacity"] & panel["liquid_either"]
    panel["loose_blocked"] = (~panel["tight_capacity"]) & panel["blocked_either"]
    panel["loose_liquid"] = (~panel["tight_capacity"]) & panel["liquid_either"]

    panel["spread_q1"] = panel["spread_conc_q"] == 1
    panel["spread_q4"] = panel["spread_conc_q"] == 4

    panel["vol_deep"] = panel["vol_expansion"] & panel["vol_depth_deep"]
    panel["vol_mild"] = panel["vol_expansion"] & panel["vol_depth_mild"]

    panel["tight_arrival_high"] = panel["tight_capacity"] & panel["arrival_high"]

    bq = panel[["time", "market_active_fraction"]].drop_duplicates().sort_values("time")
    bq["breadth_quintile"] = pd.qcut(bq["market_active_fraction"], q=5, labels=False, duplicates="drop") + 1
    panel = panel.merge(bq[["time", "breadth_quintile"]], on="time", how="left")
    for s in ["c23", "c24", "c25", "c26"]:
        panel[f"{s}_low_bq"] = panel[s] & (panel["breadth_quintile"] == 1)
        panel[f"{s}_high_bq"] = panel[s] & (panel["breadth_quintile"] == 5)

    panel["triple_amp"] = panel["tight_capacity"] & panel["low_breadth"] & panel["cofire_zero"]
    panel["pair_tight_low"] = panel["tight_capacity"] & panel["low_breadth"]
    panel["pair_tight_iso"] = panel["tight_capacity"] & panel["cofire_zero"]
    panel["pair_low_iso"] = panel["low_breadth"] & panel["cofire_zero"]

    panel["high_accum_low_breadth"] = panel["high_accum"] & panel["low_breadth"]

    panel["was_active_now_inactive"] = (~panel["state_active_proxy"]) & panel.groupby("ticker")["state_active_proxy"].shift(1).fillna(False)
    panel["never_active"] = (~panel["state_active_proxy"]) & (
        panel.groupby("ticker")["state_active_proxy"].transform(lambda s: s.rolling(window=20, min_periods=20).sum().fillna(0) == 0)
    )

    panel["breadth_persistent_low_state"] = panel["breadth_low_today"] & panel["breadth_persistent_low"].fillna(False)
    panel["breadth_transient_low_state"] = panel["breadth_transient_low"]

    panel["tight_high_accum"] = panel["tight_capacity"] & panel["high_accum"]
    panel["tight_low_accum"] = panel["tight_capacity"] & panel["low_accum"]

    # global results table for all states
    all_states = sorted({s for v in state_map.values() for s in v})
    results, yearly = evaluate_states(panel, all_states, S1_SCORE_COL, S1_TARGET_COL, min_year_rows=spec.min_year_rows)

    decisions: list[dict[str, object]] = []

    def decide_lift(item: str, better: str, base: str, pass_thr: float = 0.01) -> None:
        b = _ic(results, better)
        a = _ic(results, base)
        lift = b - a if pd.notna(b) and pd.notna(a) else np.nan
        if pd.isna(lift):
            d = "DATA_GATED"
        elif lift > pass_thr:
            d = "PASSED"
        elif lift > 0:
            d = "MIXED"
        else:
            d = "FAILED"
        decisions.append({"item": item, "decision": d, "better_state": better, "base_state": base, "better_ic": _safe_float(b), "base_ic": _safe_float(a), "lift": _safe_float(lift)})

    # Item-specific decision logic.
    decide_lift("85", "quiet_blocked", "quiet_liquid")
    decide_lift("86", "lb_vol_exp", "hb_vol_contr")
    decide_lift("87", "first_active_after_quiet", "sustained_active_2pl")
    decide_lift("88", "tight_blocked", "tight_liquid")
    decide_lift("89", "spread_q4", "spread_q1")
    decide_lift("90", "enter_tight_exit_expanding", "enter_tight_exit_tight")
    decide_lift("91", "vol_deep", "vol_mild")
    decide_lift("96", "cofire_zero", "cofire_few")
    decide_lift("97", "tight_arrival_high", "tight_capacity")

    # 98: average low-vs-high per signal.
    lows = [_ic(results, f"{s}_low_bq") for s in ["c23", "c24", "c25", "c26"]]
    highs = [_ic(results, f"{s}_high_bq") for s in ["c23", "c24", "c25", "c26"]]
    low_mean = float(np.nanmean(lows)) if any(pd.notna(v) for v in lows) else np.nan
    high_mean = float(np.nanmean(highs)) if any(pd.notna(v) for v in highs) else np.nan
    lift98 = low_mean - high_mean if pd.notna(low_mean) and pd.notna(high_mean) else np.nan
    if pd.isna(lift98):
        d98 = "DATA_GATED"
    elif lift98 > 0.01:
        d98 = "PASSED"
    elif lift98 > 0:
        d98 = "MIXED"
    else:
        d98 = "FAILED"
    decisions.append({"item": "98", "decision": d98, "better_state": "signal_low_breadth_mean", "base_state": "signal_high_breadth_mean", "better_ic": _safe_float(low_mean), "base_ic": _safe_float(high_mean), "lift": _safe_float(lift98)})

    decide_lift("99", "triple_amp", "pair_tight_low")
    decide_lift("100", "high_accum_low_breadth", "high_accum")
    decide_lift("101", "was_active_now_inactive", "never_active")
    decide_lift("102", "breadth_persistent_low_state", "breadth_transient_low_state")
    decide_lift("103", "tight_high_accum", "tight_low_accum")

    decision_df = pd.DataFrame(decisions)

    results_path = write_dataframe_artifact(results, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")
    decision_path = write_dataframe_artifact(decision_df, context, f"{BRANCH_NAME}_decisions")

    pass_n = int((decision_df["decision"] == "PASSED").sum())
    mixed_n = int((decision_df["decision"] == "MIXED").sum())
    fail_n = int((decision_df["decision"] == "FAILED").sum())
    gated_n = int((decision_df["decision"] == "DATA_GATED").sum())

    summary_path = context.write_summary(
        summary={
            "decision": "BATCH_COMPLETED",
            "queue_items_resolved": int(len(decision_df)),
            "passed": pass_n,
            "mixed": mixed_n,
            "failed": fail_n,
            "data_gated": gated_n,
        },
        artifacts={"results": results_path, "yearly": yearly_path, "decisions": decision_path},
        metadata={"hypothesis": SPEC.hypothesis},
    )

    print(decision_df.to_string(index=False))
    print(f"summary: {summary_path}")
    return summary_path


if __name__ == "__main__":
    run_branch(parse_args())
