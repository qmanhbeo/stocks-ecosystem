"""
H643 batch: first-pass resolution of Bright-Mind wake/sleep + traffic backlog.
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

BRANCH_NAME = "h643_brightmind_remaining_batch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode="research_branch",
    hypothesis="First-pass tests for remaining Bright-Mind wake/sleep and traffic backlog items.",
    start_year=2015,
    end_year=2025,
    min_year_rows=100,
    min_phase_rows=100,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H643 backlog batch")
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument(
        "--order-stats-path",
        type=str,
        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")),
    )
    return parser.parse_args()


def _ic(results: pd.DataFrame, name: str) -> float:
    row = results[results["name"] == name]
    if row.empty:
        return np.nan
    return float(row["avg_ic"].iloc[0]) if pd.notna(row["avg_ic"].iloc[0]) else np.nan


def _sf(v: float) -> float | None:
    if pd.isna(v):
        return None
    return float(v)


def _decision(lift: float, pass_thr: float = 0.01) -> str:
    if pd.isna(lift):
        return "DATA_GATED"
    if lift > pass_thr:
        return "PASSED"
    if lift > 0:
        return "MIXED"
    return "FAILED"


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(SPEC, start_year=int(args.start_year), end_year=int(args.end_year))
    context = build_experiment_context(spec, artifact_subdir="research_branches")
    cache_path = str(ROOT / "artifacts" / "cache" / "h62x_base_panel_2015_2025.parquet")
    panel = build_base_panel(spec.start_year, spec.end_year, order_stats_path=args.order_stats_path, cache_path=cache_path)

    # shared enrichments
    trad_df = pd.read_parquet(data_path("features/execution/tradability_daily.parquet"))
    trad_df = normalize_time_ticker(trad_df, source="tradability")
    trad_df = restrict_years(trad_df, start_year=spec.start_year, end_year=spec.end_year, source="tradability")
    panel = panel.merge(trad_df[["time", "ticker", "can_buy_next_open", "can_sell_next_open"]], on=["time", "ticker"], how="left")
    panel["liquid"] = panel["can_buy_next_open"].fillna(True) & panel["can_sell_next_open"].fillna(True)

    if "buy_order_count" not in panel.columns or "sell_order_count" not in panel.columns:
        order_stats = pd.read_parquet(args.order_stats_path)
        order_stats = order_stats.rename(columns={"date": "time"})
        order_stats["time"] = pd.to_datetime(order_stats["time"])
        panel = panel.merge(order_stats[["time", "ticker", "buy_order_count", "sell_order_count"]], on=["time", "ticker"], how="left")

    panel["total_order_count"] = panel["buy_order_count"].fillna(0) + panel["sell_order_count"].fillna(0)
    panel["order_count_rank"] = panel.groupby("time")["total_order_count"].rank(method="average", pct=True)
    panel["tight_capacity"] = panel["order_count_rank"] <= 0.2

    panel["cofire_count"] = panel["signal_count"].clip(lower=0)
    panel["cofire_isolated"] = panel["cofire_count"] == 1
    panel["cofire_crowded"] = panel["cofire_count"] >= 3

    panel = panel.sort_values(["ticker", "time"]).copy()
    panel["accum_30d"] = panel.groupby("ticker")["composite_2plus"].transform(lambda s: s.astype(int).rolling(30, min_periods=1).sum())
    panel["long_accum"] = panel["accum_30d"] >= 20

    # date-level frame
    daily = panel.groupby("time", as_index=False).agg(
        breadth=("market_active_fraction", "mean"),
        cofire_mean=("cofire_count", "mean"),
        comp_rate=("composite_2plus", "mean"),
        vol_exp_rate=("vol_expansion", "mean"),
        liquid_rate=("liquid", "mean"),
    )
    daily = daily.sort_values("time")
    daily["breadth_3d_low"] = daily["breadth"].rolling(3, min_periods=3).mean() <= daily["breadth"].quantile(0.2)
    daily["vol_exp_slow"] = daily["vol_exp_rate"] >= daily["vol_exp_rate"].quantile(0.6)
    daily["breadth_10d_var"] = daily["breadth"].rolling(10, min_periods=10).var()
    daily["cofire_10d_var"] = daily["cofire_mean"].rolling(10, min_periods=10).var()
    daily["stability_score"] = -(daily["breadth_10d_var"].fillna(0) + daily["cofire_10d_var"].fillna(0))
    daily["stable_regime"] = daily["stability_score"] >= daily["stability_score"].quantile(0.6)

    # macro blocks (3-state clustering proxy by quantile bins)
    daily["macro_key"] = (
        pd.qcut(daily["breadth"], q=3, labels=False, duplicates="drop").astype(float)
        + pd.qcut(daily["vol_exp_rate"], q=3, labels=False, duplicates="drop").astype(float)
    )
    daily["macro_block"] = pd.qcut(daily["macro_key"], q=3, labels=["A", "B", "C"], duplicates="drop")

    # macro persistence age
    block_change = daily["macro_block"] != daily["macro_block"].shift(1)
    daily["macro_age"] = block_change.cumsum().groupby(block_change.cumsum()).cumcount() + 1
    daily["macro_established"] = daily["macro_age"] >= 5

    # shockwave and fatigue load constructs
    daily["comp_change"] = daily["comp_rate"].diff().abs()
    shock_cut = daily["comp_change"].quantile(0.9)
    daily["shockwave"] = daily["comp_change"] >= shock_cut

    daily["fatigue_10"] = daily["breadth"].rolling(10, min_periods=5).sum()
    daily["fatigue_20"] = daily["breadth"].rolling(20, min_periods=10).sum()
    daily["fatigue_load"] = daily["fatigue_10"] + daily["fatigue_20"]
    daily["fatigue_bin"] = pd.qcut(daily["fatigue_load"], q=3, labels=["low", "mid", "high"], duplicates="drop")

    # phase-lag proxy
    daily["breadth_delta"] = daily["breadth"].diff()
    daily["cofire_delta"] = daily["cofire_mean"].diff()
    daily["phase_lag"] = daily["breadth_delta"] - daily["cofire_delta"]
    daily["phase_q"] = pd.qcut(daily["phase_lag"], q=3, labels=["suppress", "neutral", "allow"], duplicates="drop")

    # mesoscopic shape
    shape = panel.groupby("time").agg(
        top_dec_share=("signal_count", lambda s: s.nlargest(max(1, int(len(s) * 0.1))).sum() / (s.sum() + 1e-9)),
    ).reset_index()
    daily = daily.merge(shape, on="time", how="left")
    daily["shape_high_tail"] = daily["top_dec_share"] >= daily["top_dec_share"].quantile(0.7)

    # spread to panel
    panel = panel.merge(daily, on="time", how="left")

    # build states
    panel["bm_nested_triple"] = panel["breadth_3d_low"] & panel["long_accum"] & panel["vol_exp_slow"]
    panel["bm_nested_pair_fast_med"] = panel["breadth_3d_low"] & panel["long_accum"]
    panel["bm_nested_pair_fast_slow"] = panel["breadth_3d_low"] & panel["vol_exp_slow"]

    panel["arousal"] = panel["composite_2plus"].astype(int) + panel["cofire_isolated"].astype(int) + panel["tight_capacity"].astype(int)
    panel["fatigue"] = (~panel["low_breadth"]).astype(int) + panel["cofire_crowded"].astype(int) + panel["long_accum"].astype(int)
    panel["af_spread"] = panel["arousal"] - panel["fatigue"]
    panel["af_high"] = panel["af_spread"] >= panel["af_spread"].quantile(0.8)
    panel["af_low"] = panel["af_spread"] <= panel["af_spread"].quantile(0.2)

    panel["sigcnt_5d_change"] = panel.groupby("ticker")["signal_count"].transform(lambda s: s - s.shift(5))
    panel["wake_pulse"] = panel["composite_2plus"] & (panel["sigcnt_5d_change"] > 0)
    panel["wake_chronic"] = panel["composite_2plus"] & (panel["sigcnt_5d_change"] <= 0)

    panel["self_hot"] = panel.groupby("ticker")["signal_count_30d_avg"].rank(method="average", pct=True) >= 0.8
    panel["desync_hot_sleepy"] = panel["self_hot"] & panel["low_breadth"]
    panel["sync_hot_hot"] = panel["self_hot"] & (~panel["low_breadth"])

    # cooldown bins after high-breadth spikes
    high_b = daily["breadth"] >= daily["breadth"].quantile(0.8)
    spike_time = daily.loc[high_b, "time"]
    if not spike_time.empty:
        last_spike = daily["time"].where(high_b).ffill()
        daily["days_since_spike"] = (daily["time"] - last_spike).dt.days
    else:
        daily["days_since_spike"] = np.nan
    panel = panel.drop(columns=[c for c in ["days_since_spike"] if c in panel.columns])
    panel = panel.merge(daily[["time", "days_since_spike"]], on="time", how="left")
    panel["cool_1_2"] = panel["composite_2plus"] & panel["days_since_spike"].between(1, 2)
    panel["cool_3_5"] = panel["composite_2plus"] & panel["days_since_spike"].between(3, 5)
    panel["cool_6_10"] = panel["composite_2plus"] & panel["days_since_spike"].between(6, 10)

    panel["stable_lowb"] = panel["composite_2plus"] & panel["low_breadth"] & panel["stable_regime"]
    panel["unstable_lowb"] = panel["composite_2plus"] & panel["low_breadth"] & (~panel["stable_regime"])

    panel["macro_A"] = panel["macro_block"].astype(str) == "A"
    panel["macro_B"] = panel["macro_block"].astype(str) == "B"
    panel["macro_C"] = panel["macro_block"].astype(str) == "C"

    panel["router_c23_only"] = panel["c23"] & (~panel["c24"])
    panel["router_c24_only"] = panel["c24"] & (~panel["c23"])

    panel["fatigue_high"] = panel["fatigue_bin"].astype(str) == "high"
    panel["fatigue_low"] = panel["fatigue_bin"].astype(str) == "low"

    panel["phase_allow"] = panel["phase_q"].astype(str) == "allow"
    panel["phase_suppress"] = panel["phase_q"].astype(str) == "suppress"

    panel["macro_established_state"] = panel["macro_established"]
    panel["macro_new_state"] = ~panel["macro_established"]

    panel["density_mid"] = panel["comp_rate"].between(panel["comp_rate"].quantile(0.4), panel["comp_rate"].quantile(0.6))
    panel["density_low"] = panel["comp_rate"] <= panel["comp_rate"].quantile(0.2)
    panel["density_high"] = panel["comp_rate"] >= panel["comp_rate"].quantile(0.8)

    panel["shock_state"] = panel["shockwave"]
    panel["nonshock_state"] = ~panel["shockwave"]

    panel["relax_gap"] = panel["comp_rate"] - panel["liquid_rate"]
    panel["relax_gap_high"] = panel["relax_gap"] >= panel["relax_gap"].quantile(0.8)
    panel["relax_gap_low"] = panel["relax_gap"] <= panel["relax_gap"].quantile(0.2)

    panel["headway_wide"] = panel["self_hot"] & panel["tight_capacity"]
    panel["headway_tight"] = panel["self_hot"] & (~panel["tight_capacity"])

    panel["shape_tail_high"] = panel["shape_high_tail"]
    panel["shape_tail_low"] = ~panel["shape_high_tail"]

    states = [
        "composite_2plus", "bm_nested_triple", "bm_nested_pair_fast_med", "bm_nested_pair_fast_slow",
        "af_high", "af_low", "wake_pulse", "wake_chronic", "desync_hot_sleepy", "sync_hot_hot",
        "cool_1_2", "cool_3_5", "cool_6_10", "stable_lowb", "unstable_lowb", "router_c23_only", "router_c24_only",
        "fatigue_high", "fatigue_low", "phase_allow", "phase_suppress", "macro_established_state", "macro_new_state",
        "density_mid", "density_low", "density_high", "shock_state", "nonshock_state", "relax_gap_high", "relax_gap_low",
        "headway_wide", "headway_tight", "shape_tail_high", "shape_tail_low",
    ]

    results, yearly = evaluate_states(panel, states, S1_SCORE_COL, S1_TARGET_COL, min_year_rows=spec.min_year_rows)

    decisions = []
    def add(name: str, better: str, base: str, pass_thr: float = 0.01) -> None:
        b = _ic(results, better)
        a = _ic(results, base)
        lift = b - a if pd.notna(b) and pd.notna(a) else np.nan
        decisions.append({"item": name, "decision": _decision(lift, pass_thr), "better": better, "base": base, "better_ic": _sf(b), "base_ic": _sf(a), "lift": _sf(lift)})

    add("BM01_nested_phase_stack", "bm_nested_triple", "bm_nested_pair_fast_med")
    add("BM02_arousal_fatigue", "af_high", "af_low")
    add("BM03_wake_pulse_vs_chronic", "wake_pulse", "wake_chronic")
    add("BM04_local_global_desync", "desync_hot_sleepy", "sync_hot_hot")
    add("BM05_cooldown_halflife", "cool_3_5", "cool_1_2")
    add("BM06_cycle_stability", "stable_lowb", "unstable_lowb")
    add("BM07_hierarchical_context", "macro_A", "macro_C")
    add("BM08_fatigue_threshold", "fatigue_low", "fatigue_high")
    add("BM09_phase_lag_gate", "phase_allow", "phase_suppress")
    add("BM10_router_conditional", "router_c23_only", "router_c24_only")
    add("BM11_macro_persistence", "macro_established_state", "macro_new_state")

    add("BM12_fundamental_diagram", "density_mid", "density_high")
    add("BM13_shockwave", "nonshock_state", "shock_state")
    add("BM14_relaxation_gap", "relax_gap_low", "relax_gap_high")
    add("BM15_headway_safety", "headway_wide", "headway_tight")
    add("BM16_mesoscopic_shape", "shape_tail_low", "shape_tail_high")

    # BM17 sector equilibrium is data gated (no canonical sector map in panel contract).
    decisions.append({"item": "BM17_wardrop_sector_equilibrium", "decision": "DATA_GATED", "better": "n/a", "base": "n/a", "better_ic": None, "base_ic": None, "lift": None})

    decision_df = pd.DataFrame(decisions)

    results_path = write_dataframe_artifact(results, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")
    decision_path = write_dataframe_artifact(decision_df, context, f"{BRANCH_NAME}_decisions")

    summary_path = context.write_summary(
        summary={
            "decision": "BATCH_COMPLETED",
            "items": int(len(decision_df)),
            "passed": int((decision_df["decision"] == "PASSED").sum()),
            "mixed": int((decision_df["decision"] == "MIXED").sum()),
            "failed": int((decision_df["decision"] == "FAILED").sum()),
            "data_gated": int((decision_df["decision"] == "DATA_GATED").sum()),
        },
        artifacts={"results": results_path, "yearly": yearly_path, "decisions": decision_path},
        metadata={"hypothesis": SPEC.hypothesis},
    )

    print(decision_df.to_string(index=False))
    print(f"summary: {summary_path}")
    return summary_path


if __name__ == "__main__":
    run_branch(parse_args())
