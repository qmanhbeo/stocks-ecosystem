"""
H644 - Formalized retests for highest-value unresolved hypotheses.

Targets:
- #99  Triple amplification (strict retest)
- #91  Volatility expansion depth conditioner (corrected bins)
- #100 Accumulation x low-breadth (corrected accumulation contract)
- #103 Tight x high-accumulation interaction (corrected accumulation contract)
- BM07 Hierarchical context gating (macro-block gating)
- BM17 Wardrop-style sector pressure equilibrium (sector-dispersion gating)
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
    write_dataframe_artifact,
)
from src.repo_paths import data_path  # noqa: E402

BRANCH_NAME = "h644_formalized_retests"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode="research_branch",
    hypothesis="Strict retests for top-value unresolved hypotheses after backlog closure.",
    start_year=2015,
    end_year=2025,
    min_year_rows=100,
    min_phase_rows=100,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H644 formalized retests")
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument(
        "--order-stats-path",
        type=str,
        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")),
    )
    return parser.parse_args()


def _ic(results: pd.DataFrame, state: str) -> float:
    row = results[results["name"] == state]
    if row.empty:
        return np.nan
    val = row["avg_ic"].iloc[0]
    return float(val) if pd.notna(val) else np.nan


def _rows(results: pd.DataFrame, state: str) -> int:
    row = results[results["name"] == state]
    if row.empty:
        return 0
    return int(row["rows"].iloc[0])


def _decide(lift: float, pass_thr: float = 0.01) -> str:
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
    panel = build_base_panel(spec.start_year, spec.end_year, args.order_stats_path, cache_path=cache_path)

    # Tradability proxy for blocked/liquid context
    trad = pd.read_parquet(data_path("features/execution/tradability_daily.parquet"))
    trad = trad.rename(columns={"date": "time"}) if "date" in trad.columns else trad
    trad["time"] = pd.to_datetime(trad["time"])
    trad = trad[(trad["time"].dt.year >= spec.start_year) & (trad["time"].dt.year <= spec.end_year)].copy()
    panel = panel.merge(
        trad[["time", "ticker", "can_buy_next_open", "can_sell_next_open"]],
        on=["time", "ticker"],
        how="left",
    )

    # order-count derived tight capacity
    order_stats = pd.read_parquet(args.order_stats_path)
    order_stats = order_stats.rename(columns={"date": "time"})
    order_stats["time"] = pd.to_datetime(order_stats["time"])
    order_stats = order_stats[["time", "ticker", "buy_order_count", "sell_order_count"]]
    panel = panel.merge(order_stats, on=["time", "ticker"], how="left")

    panel["total_order_count"] = panel["buy_order_count"].fillna(0) + panel["sell_order_count"].fillna(0)
    panel["order_count_rank"] = panel.groupby("time")["total_order_count"].rank(method="average", pct=True)
    panel["tight_capacity"] = panel["order_count_rank"] <= 0.2

    # isolated cofire proxy: exactly one C23/C24/C25/C26 firing
    panel["cofire_isolated"] = panel["signal_count"] == 1

    # corrected accumulation contract: rolling 30d sum of signal_count (intensity), quantile-based bins
    panel = panel.sort_values(["ticker", "time"]).copy()
    panel["accum_intensity_30d"] = panel.groupby("ticker")["signal_count"].transform(
        lambda s: s.rolling(window=30, min_periods=10).sum()
    )
    hi_cut = panel["accum_intensity_30d"].quantile(0.8)
    lo_cut = panel["accum_intensity_30d"].quantile(0.2)
    panel["high_accum"] = panel["accum_intensity_30d"] >= hi_cut
    panel["low_accum"] = panel["accum_intensity_30d"] <= lo_cut

    # corrected vol-depth bins inside vol-expansion support
    panel["vol_depth_pct"] = panel.groupby("time")["vol_change"].rank(method="average", pct=True)
    panel["vol_deep"] = panel["vol_depth_pct"] >= 0.9
    panel["vol_mild"] = panel["vol_depth_pct"].between(0.8, 0.9, inclusive="left")

    # #99 strict triple vs pairs
    panel["triple_amp"] = panel["tight_capacity"] & panel["low_breadth"] & panel["cofire_isolated"]
    panel["pair_tight_low"] = panel["tight_capacity"] & panel["low_breadth"]
    panel["pair_tight_iso"] = panel["tight_capacity"] & panel["cofire_isolated"]
    panel["pair_low_iso"] = panel["low_breadth"] & panel["cofire_isolated"]

    # #100, #103 corrected states
    panel["high_accum_low_breadth"] = panel["high_accum"] & panel["low_breadth"]
    panel["tight_high_accum"] = panel["tight_capacity"] & panel["high_accum"]
    panel["tight_low_accum"] = panel["tight_capacity"] & panel["low_accum"]

    # BM07 hierarchical context gating: discrete macro blocks from slow observables
    daily = panel.groupby("time", as_index=False).agg(
        breadth=("market_active_fraction", "mean"),
        vol_exp_rate=("vol_expansion", "mean"),
        liq_rank=("amihud_rank", "mean"),
    )
    daily["b_bin"] = pd.qcut(daily["breadth"], q=3, labels=False, duplicates="drop")
    daily["v_bin"] = pd.qcut(daily["vol_exp_rate"], q=3, labels=False, duplicates="drop")
    daily["l_bin"] = pd.qcut(daily["liq_rank"], q=3, labels=False, duplicates="drop")
    daily["macro_score"] = daily[["b_bin", "v_bin", "l_bin"]].sum(axis=1)
    daily["macro_block"] = pd.qcut(daily["macro_score"], q=3, labels=["A", "B", "C"], duplicates="drop")
    panel = panel.merge(daily[["time", "macro_block"]], on="time", how="left")

    panel["router_c23_only"] = panel["c23"] & (~panel["c24"])
    panel["router_c24_only"] = panel["c24"] & (~panel["c23"])
    for block in ["A", "B", "C"]:
        panel[f"c23_only_macro_{block}"] = panel["router_c23_only"] & (panel["macro_block"].astype(str) == block)
        panel[f"c24_only_macro_{block}"] = panel["router_c24_only"] & (panel["macro_block"].astype(str) == block)

    # BM17 Wardrop-style sector pressure dispersion
    sector = pd.read_parquet(data_path("features/sector_classification.parquet"))
    sector = sector.rename(columns={"symbol": "ticker"})
    panel = panel.merge(sector[["ticker", "icb_name2"]], on="ticker", how="left")

    sec_day = panel.groupby(["time", "icb_name2"], as_index=False)["signal_count"].mean().rename(columns={"signal_count": "sector_pressure"})
    sec_disp = sec_day.groupby("time", as_index=False)["sector_pressure"].std().rename(columns={"sector_pressure": "sector_dispersion"})
    q_hi = sec_disp["sector_dispersion"].quantile(0.8)
    q_lo = sec_disp["sector_dispersion"].quantile(0.2)
    sec_disp["high_disp_day"] = sec_disp["sector_dispersion"] >= q_hi
    sec_disp["low_disp_day"] = sec_disp["sector_dispersion"] <= q_lo
    panel = panel.merge(sec_disp[["time", "high_disp_day", "low_disp_day"]], on="time", how="left")
    panel["c23_high_disp"] = panel["c23"] & panel["high_disp_day"]
    panel["c23_low_disp"] = panel["c23"] & panel["low_disp_day"]
    panel["c24_high_disp"] = panel["c24"] & panel["high_disp_day"]
    panel["c24_low_disp"] = panel["c24"] & panel["low_disp_day"]

    states = [
        "triple_amp", "pair_tight_low", "pair_tight_iso", "pair_low_iso",
        "vol_deep", "vol_mild",
        "high_accum_low_breadth", "high_accum",
        "tight_high_accum", "tight_low_accum",
        "router_c23_only", "router_c24_only",
        "c23_only_macro_A", "c23_only_macro_B", "c23_only_macro_C",
        "c24_only_macro_A", "c24_only_macro_B", "c24_only_macro_C",
        "c23_high_disp", "c23_low_disp", "c24_high_disp", "c24_low_disp",
    ]

    results, yearly = evaluate_states(panel, states, S1_SCORE_COL, S1_TARGET_COL, min_year_rows=spec.min_year_rows)

    decisions = []

    # #99
    pair_ics = {k: _ic(results, k) for k in ["pair_tight_low", "pair_tight_iso", "pair_low_iso"]}
    best_pair_state = max(pair_ics, key=lambda k: -999 if pd.isna(pair_ics[k]) else pair_ics[k])
    best_pair_ic = pair_ics[best_pair_state]
    triple_ic = _ic(results, "triple_amp")
    lift99 = triple_ic - best_pair_ic if pd.notna(triple_ic) and pd.notna(best_pair_ic) else np.nan
    decisions.append({
        "item": "99",
        "decision": _decide(lift99),
        "better_state": "triple_amp",
        "base_state": best_pair_state,
        "better_ic": None if pd.isna(triple_ic) else float(triple_ic),
        "base_ic": None if pd.isna(best_pair_ic) else float(best_pair_ic),
        "lift": None if pd.isna(lift99) else float(lift99),
        "better_rows": _rows(results, "triple_amp"),
        "base_rows": _rows(results, best_pair_state),
    })

    # #91
    deep_ic = _ic(results, "vol_deep")
    mild_ic = _ic(results, "vol_mild")
    lift91 = deep_ic - mild_ic if pd.notna(deep_ic) and pd.notna(mild_ic) else np.nan
    decisions.append({
        "item": "91",
        "decision": _decide(lift91),
        "better_state": "vol_deep",
        "base_state": "vol_mild",
        "better_ic": None if pd.isna(deep_ic) else float(deep_ic),
        "base_ic": None if pd.isna(mild_ic) else float(mild_ic),
        "lift": None if pd.isna(lift91) else float(lift91),
        "better_rows": _rows(results, "vol_deep"),
        "base_rows": _rows(results, "vol_mild"),
    })

    # #100
    ha_lb_ic = _ic(results, "high_accum_low_breadth")
    ha_ic = _ic(results, "high_accum")
    lift100 = ha_lb_ic - ha_ic if pd.notna(ha_lb_ic) and pd.notna(ha_ic) else np.nan
    decisions.append({
        "item": "100",
        "decision": _decide(lift100),
        "better_state": "high_accum_low_breadth",
        "base_state": "high_accum",
        "better_ic": None if pd.isna(ha_lb_ic) else float(ha_lb_ic),
        "base_ic": None if pd.isna(ha_ic) else float(ha_ic),
        "lift": None if pd.isna(lift100) else float(lift100),
        "better_rows": _rows(results, "high_accum_low_breadth"),
        "base_rows": _rows(results, "high_accum"),
    })

    # #103
    tha_ic = _ic(results, "tight_high_accum")
    tla_ic = _ic(results, "tight_low_accum")
    lift103 = tha_ic - tla_ic if pd.notna(tha_ic) and pd.notna(tla_ic) else np.nan
    decisions.append({
        "item": "103",
        "decision": _decide(lift103),
        "better_state": "tight_high_accum",
        "base_state": "tight_low_accum",
        "better_ic": None if pd.isna(tha_ic) else float(tha_ic),
        "base_ic": None if pd.isna(tla_ic) else float(tla_ic),
        "lift": None if pd.isna(lift103) else float(lift103),
        "better_rows": _rows(results, "tight_high_accum"),
        "base_rows": _rows(results, "tight_low_accum"),
    })

    # BM07: macro-gating strength for router states
    c23_blocks = [_ic(results, f"c23_only_macro_{b}") for b in ["A", "B", "C"]]
    c24_blocks = [_ic(results, f"c24_only_macro_{b}") for b in ["A", "B", "C"]]
    c23_pooled = _ic(results, "router_c23_only")
    c24_pooled = _ic(results, "router_c24_only")
    c23_range = np.nanmax(c23_blocks) - np.nanmin(c23_blocks) if any(pd.notna(x) for x in c23_blocks) else np.nan
    c24_range = np.nanmax(c24_blocks) - np.nanmin(c24_blocks) if any(pd.notna(x) for x in c24_blocks) else np.nan
    c23_best_lift = np.nanmax(c23_blocks) - c23_pooled if pd.notna(c23_pooled) and any(pd.notna(x) for x in c23_blocks) else np.nan
    c24_best_lift = np.nanmax(c24_blocks) - c24_pooled if pd.notna(c24_pooled) and any(pd.notna(x) for x in c24_blocks) else np.nan
    gate_metric = np.nanmax([c23_best_lift, c24_best_lift])
    range_metric = np.nanmax([c23_range, c24_range])
    bm07_lift = gate_metric if pd.notna(gate_metric) else np.nan
    bm07_dec = "DATA_GATED"
    if pd.notna(gate_metric) and pd.notna(range_metric):
        if gate_metric > 0.01 and range_metric > 0.01:
            bm07_dec = "PASSED"
        elif gate_metric > 0:
            bm07_dec = "MIXED"
        else:
            bm07_dec = "FAILED"
    decisions.append({
        "item": "BM07",
        "decision": bm07_dec,
        "better_state": "best_macro_router_block",
        "base_state": "router_pooled",
        "better_ic": None if pd.isna(gate_metric) else float(gate_metric),
        "base_ic": None,
        "lift": None if pd.isna(bm07_lift) else float(bm07_lift),
        "better_rows": None,
        "base_rows": None,
    })

    # BM17: sector-dispersion gating for C23/C24
    c23_hd = _ic(results, "c23_high_disp")
    c23_ld = _ic(results, "c23_low_disp")
    c24_hd = _ic(results, "c24_high_disp")
    c24_ld = _ic(results, "c24_low_disp")
    c23_lift = c23_hd - c23_ld if pd.notna(c23_hd) and pd.notna(c23_ld) else np.nan
    c24_lift = c24_hd - c24_ld if pd.notna(c24_hd) and pd.notna(c24_ld) else np.nan
    bm17_lift = np.nanmax([c23_lift, c24_lift])
    decisions.append({
        "item": "BM17",
        "decision": _decide(bm17_lift),
        "better_state": "best(high_disp_vs_low_disp for C23/C24)",
        "base_state": "low_disp counterpart",
        "better_ic": None if pd.isna(np.nanmax([c23_hd, c24_hd])) else float(np.nanmax([c23_hd, c24_hd])),
        "base_ic": None if pd.isna(np.nanmax([c23_ld, c24_ld])) else float(np.nanmax([c23_ld, c24_ld])),
        "lift": None if pd.isna(bm17_lift) else float(bm17_lift),
        "better_rows": None,
        "base_rows": None,
    })

    decisions_df = pd.DataFrame(decisions)

    results_path = write_dataframe_artifact(results, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")
    decisions_path = write_dataframe_artifact(decisions_df, context, f"{BRANCH_NAME}_decisions")

    summary_path = context.write_summary(
        summary={
            "decision": "BATCH_COMPLETED",
            "items": int(len(decisions_df)),
            "passed": int((decisions_df["decision"] == "PASSED").sum()),
            "mixed": int((decisions_df["decision"] == "MIXED").sum()),
            "failed": int((decisions_df["decision"] == "FAILED").sum()),
            "data_gated": int((decisions_df["decision"] == "DATA_GATED").sum()),
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
            "decisions": decisions_path,
        },
        metadata={"hypothesis": SPEC.hypothesis},
    )

    print(decisions_df.to_string(index=False))
    print(f"summary: {summary_path}")
    return summary_path


if __name__ == "__main__":
    run_branch(parse_args())
