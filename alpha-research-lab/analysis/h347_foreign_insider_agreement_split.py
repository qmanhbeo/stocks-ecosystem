"""
H347: foreign-flow agreement split for C5.

Question:
    After standalone foreign-flow paths failed, does foreign buy/sell pressure
    work as an interaction state for the positive side of C5 insider
    conviction, and can it add anything on top of the stronger H340
    order-pressure rewrite?

Design:
    - use only 2015-2025 predictive data; 2026 remains monitor-only
    - reuse the existing C5 5d relative-return target contract
    - predeclare foreign-flow gates/scales and H340 stack variants
    - classify as PASSED only if a foreign-conditioned row improves the H340
      benchmark in validation and confirmation; beating raw C5 only is MIXED
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from path_utils import data_path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.h327_cafef_foreign_flow_source_audit import (  # noqa: E402
    PASS_CORR,
    _json_safe,
    load_flow,
    load_stock_panel,
)
from src.research_protocol import ResearchProtocol, phase_mask  # noqa: E402
from src.run_summary import write_run_summary  # noqa: E402


QUALITY_PATH = data_path("features/xs_insider_quality_features.parquet")
ORDER_STATS_PATH = data_path("order_stats/cafef/order_stats_daily.parquet")
S1_PATH = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
FUTURE_REL_5D_PATH = ROOT / "artifacts" / "cache" / "future_rel_return_5d_hose.parquet"
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"

PROTOCOL = ResearchProtocol(
    dev_start_year=2015,
    dev_end_year=2022,
    validation_start_year=2023,
    validation_end_year=2024,
    confirmation_year=2025,
    forward_start_year=2026,
)

MIN_PHASE_ROWS = 100
MIN_YEARLY_ROWS = 20
PASS_MIN_AVG_IC_DELTA_VS_H340 = 0.0
PASS_MIN_VALIDATION_DELTA_VS_H340 = 0.0
PASS_MIN_CONFIRMATION_DELTA_VS_H340 = 0.0
MIXED_MIN_RAW_CONFIRMATION_UPLIFT = 0.0


def _safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _spearman(x: pd.Series, y: pd.Series) -> float | None:
    clean = pd.DataFrame({"x": x, "y": y}).replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < MIN_YEARLY_ROWS or clean["x"].nunique() < 3 or clean["y"].nunique() < 3:
        return None
    stat = spearmanr(clean["x"], clean["y"]).statistic
    return float(np.asarray(stat).flat[0])


def _rolling_sum(grouped: pd.core.groupby.DataFrameGroupBy, column: str, window: int) -> pd.Series:
    return grouped[column].rolling(window, min_periods=max(3, window // 2)).sum().reset_index(level=0, drop=True)


def load_foreign_support_panel() -> pd.DataFrame:
    flow = load_flow()
    stock = load_stock_panel()
    merged = stock[["time", "ticker", "volume"]].merge(
        flow[
            [
                "time",
                "ticker",
                "foreign_buy_volume",
                "foreign_sell_volume",
                "foreign_net_volume",
            ]
        ],
        on=["time", "ticker"],
        how="inner",
    )
    merged = merged.sort_values(["ticker", "time"]).reset_index(drop=True)
    grouped = merged.groupby("ticker", group_keys=False)
    volume_5d = _rolling_sum(grouped, "volume", 5).replace(0, np.nan)
    buy_5d = _rolling_sum(grouped, "foreign_buy_volume", 5)
    sell_5d = _rolling_sum(grouped, "foreign_sell_volume", 5)
    net_5d = _rolling_sum(grouped, "foreign_net_volume", 5)

    merged["ff_net_vol_share_5d"] = net_5d / volume_5d
    merged["ff_buy_vol_share_5d"] = buy_5d / volume_5d
    merged["ff_sell_vol_share_5d"] = sell_5d / volume_5d
    merged["ff_net_vol_share_5d_lag1"] = grouped["ff_net_vol_share_5d"].shift(1)
    return merged[
        [
            "time",
            "ticker",
            "ff_net_vol_share_5d",
            "ff_buy_vol_share_5d",
            "ff_sell_vol_share_5d",
            "ff_net_vol_share_5d_lag1",
        ]
    ].rename(columns={"time": "trading_day"})


def load_base_panel() -> pd.DataFrame:
    quality = pd.read_parquet(
        QUALITY_PATH,
        columns=["trading_day", "ticker", "xs_ins_relative_size_5d"],
    )
    quality["trading_day"] = pd.to_datetime(quality["trading_day"])
    quality["ticker"] = quality["ticker"].astype(str).str.upper()

    order_stats = pd.read_parquet(
        ORDER_STATS_PATH,
        columns=["ticker", "date", "buy_order_volume", "sell_order_volume"],
    ).rename(columns={"date": "trading_day"})
    order_stats["trading_day"] = pd.to_datetime(order_stats["trading_day"])
    order_stats["ticker"] = order_stats["ticker"].astype(str).str.upper()
    buy = pd.to_numeric(order_stats["buy_order_volume"], errors="coerce").fillna(0.0)
    sell = pd.to_numeric(order_stats["sell_order_volume"], errors="coerce").fillna(0.0)
    denom = buy + sell
    order_stats["order_volume_ratio"] = np.where(denom > 0.0, (buy - sell) / denom, 0.0)
    order_stats = order_stats[["trading_day", "ticker", "order_volume_ratio"]]

    future_rel = pd.read_parquet(FUTURE_REL_5D_PATH)
    future_rel["time"] = pd.to_datetime(future_rel["time"])
    future_rel["ticker"] = future_rel["ticker"].astype(str).str.upper()
    future_rel = future_rel.rename(columns={"time": "trading_day"})
    future_rel = future_rel[["trading_day", "ticker", "fwd_rel_5d"]]

    s1 = pd.read_parquet(S1_PATH, columns=["time", "ticker", "xs_proba"])
    s1 = s1.rename(columns={"time": "trading_day"})
    s1["trading_day"] = pd.to_datetime(s1["trading_day"])
    s1["ticker"] = s1["ticker"].astype(str).str.upper()

    foreign = load_foreign_support_panel()
    foreign["trading_day"] = pd.to_datetime(foreign["trading_day"])
    foreign["ticker"] = foreign["ticker"].astype(str).str.upper()

    frame = quality.merge(future_rel, on=["trading_day", "ticker"], how="inner")
    frame = frame.merge(s1, on=["trading_day", "ticker"], how="inner")
    frame = frame.merge(foreign, on=["trading_day", "ticker"], how="left")
    frame = frame.merge(order_stats, on=["trading_day", "ticker"], how="left")
    frame = frame[frame["trading_day"].dt.year.between(2015, 2025)].copy()
    frame["year"] = frame["trading_day"].dt.year

    numeric_cols = [
        "xs_ins_relative_size_5d",
        "fwd_rel_5d",
        "xs_proba",
        "ff_net_vol_share_5d",
        "ff_buy_vol_share_5d",
        "ff_sell_vol_share_5d",
        "ff_net_vol_share_5d_lag1",
        "order_volume_ratio",
    ]
    for column in numeric_cols:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["order_volume_ratio"] = frame["order_volume_ratio"].fillna(0.0)
    return frame.sort_values(["ticker", "trading_day"]).reset_index(drop=True)


def _dev_positive_threshold(frame: pd.DataFrame, column: str, score: pd.Series) -> float:
    values = frame.loc[
        (frame["year"] <= PROTOCOL.dev_end_year)
        & (score > 0.0)
        & (pd.to_numeric(frame[column], errors="coerce") > 0.0),
        column,
    ].dropna()
    if values.empty:
        return 1.0
    threshold = float(values.median())
    return threshold if threshold > 0 else 1.0


def build_candidate_scores(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    work = frame.copy()
    score = work["xs_ins_relative_size_5d"].fillna(0.0)
    ff = work["ff_net_vol_share_5d"].fillna(0.0)
    ff_lag1 = work["ff_net_vol_share_5d_lag1"].fillna(0.0)
    order = work["order_volume_ratio"].fillna(0.0)

    thresholds = {
        "foreign_net_5d_dev_positive_median": _dev_positive_threshold(work, "ff_net_vol_share_5d", score),
        "foreign_net_5d_lag1_dev_positive_median": _dev_positive_threshold(
            work, "ff_net_vol_share_5d_lag1", score
        ),
        "order_volume_dev_positive_median": _dev_positive_threshold(work, "order_volume_ratio", score),
    }

    ff_scale = np.clip(ff / thresholds["foreign_net_5d_dev_positive_median"], 0.0, 1.0)
    ff_lag1_scale = np.clip(
        ff_lag1 / thresholds["foreign_net_5d_lag1_dev_positive_median"],
        0.0,
        1.0,
    )
    order_scale = np.clip(order / thresholds["order_volume_dev_positive_median"], 0.0, 1.0)

    work["c5_raw"] = score
    work["h340_c5_scale_pos_buy_vol_ratio_cap_dev_median"] = np.where(score > 0.0, score * order_scale, score)
    work["c5_gate_pos_ff_net_5d_gt_0"] = score.mask((score > 0.0) & (ff <= 0.0), 0.0)
    work["c5_scale_pos_ff_net_5d_cap_dev_median"] = np.where(score > 0.0, score * ff_scale, score)
    work["c5_gate_pos_ff_net_5d_lag1_gt_0"] = score.mask((score > 0.0) & (ff_lag1 <= 0.0), 0.0)
    work["c5_scale_pos_ff_net_5d_lag1_cap_dev_median"] = np.where(score > 0.0, score * ff_lag1_scale, score)
    work["c5_gate_pos_order_and_ff_net_5d_gt_0"] = score.mask(
        (score > 0.0) & ((order <= 0.0) | (ff <= 0.0)),
        0.0,
    )
    work["c5_scale_pos_order_x_ff_net_5d_min_cap"] = np.where(
        score > 0.0,
        score * np.minimum(order_scale, ff_scale),
        score,
    )
    return work, thresholds


def _phase_ic(frame: pd.DataFrame, signal_col: str, phase: str) -> dict[str, object]:
    scoped = frame.loc[phase_mask(frame.rename(columns={"trading_day": "time"}), phase, protocol=PROTOCOL)]
    clean = scoped[[signal_col, "fwd_rel_5d"]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < MIN_PHASE_ROWS or clean[signal_col].nunique() < 3:
        return {"rows": int(len(clean)), "pooled_ic": None}
    return {"rows": int(len(clean)), "pooled_ic": _spearman(clean[signal_col], clean["fwd_rel_5d"])}


def _yearly_ic(frame: pd.DataFrame, signal_col: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for year, group in frame.groupby("year"):
        clean = group[[signal_col, "fwd_rel_5d"]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(clean) < MIN_YEARLY_ROWS or clean[signal_col].nunique() < 3:
            continue
        rows.append(
            {
                "year": int(year),
                "n": int(len(clean)),
                "ic": _spearman(clean[signal_col], clean["fwd_rel_5d"]),
            }
        )
    return rows


def summarize_candidate(frame: pd.DataFrame, signal_col: str) -> dict[str, object]:
    fire = frame.loc[frame[signal_col].fillna(0.0) != 0.0].copy()
    yearly = _yearly_ic(fire, signal_col)
    avg_ic = float(np.nanmean([row["ic"] for row in yearly])) if yearly else None
    pos_years = int(sum(1 for row in yearly if (row["ic"] or 0.0) > 0.0))
    phase_details = {
        phase: _phase_ic(fire, signal_col, phase)
        for phase in ("dev", "validation", "confirmation")
    }
    corr = _spearman(fire[signal_col], fire["xs_proba"])
    return {
        "signal_name": signal_col,
        "fire_rows": int(len(fire)),
        "coverage_pct": float(100.0 * len(fire) / len(frame)),
        "avg_ic": avg_ic,
        "pos_years": pos_years,
        "years": int(len(yearly)),
        "pct_years_positive": float(pos_years / len(yearly)) if yearly else None,
        "corr_with_s1": corr,
        "dev_pooled_ic": phase_details["dev"]["pooled_ic"],
        "dev_rows": phase_details["dev"]["rows"],
        "validation_pooled_ic": phase_details["validation"]["pooled_ic"],
        "validation_rows": phase_details["validation"]["rows"],
        "confirmation_pooled_ic": phase_details["confirmation"]["pooled_ic"],
        "confirmation_rows": phase_details["confirmation"]["rows"],
        "phase_details": phase_details,
        "yearly": yearly,
    }


def apply_decisions(results: pd.DataFrame) -> pd.DataFrame:
    raw = results.loc[results["signal_name"] == "c5_raw"].iloc[0]
    h340 = results.loc[results["signal_name"] == "h340_c5_scale_pos_buy_vol_ratio_cap_dev_median"].iloc[0]
    raw_avg = _safe_float(raw["avg_ic"]) or 0.0
    raw_val = _safe_float(raw["validation_pooled_ic"]) or 0.0
    raw_conf = _safe_float(raw["confirmation_pooled_ic"]) or 0.0
    h340_avg = _safe_float(h340["avg_ic"]) or 0.0
    h340_val = _safe_float(h340["validation_pooled_ic"]) or 0.0
    h340_conf = _safe_float(h340["confirmation_pooled_ic"]) or 0.0

    rows: list[dict[str, object]] = []
    for _, row in results.iterrows():
        item = row.to_dict()
        name = str(item["signal_name"])
        avg_ic = _safe_float(item["avg_ic"]) or 0.0
        val_ic = _safe_float(item["validation_pooled_ic"]) or 0.0
        conf_ic = _safe_float(item["confirmation_pooled_ic"]) or 0.0
        corr = abs(_safe_float(item["corr_with_s1"]) or 0.0)
        val_rows = int(item["validation_rows"])
        conf_rows = int(item["confirmation_rows"])

        item["avg_ic_delta_vs_raw_c5"] = avg_ic - raw_avg
        item["validation_ic_delta_vs_raw_c5"] = val_ic - raw_val
        item["confirmation_ic_delta_vs_raw_c5"] = conf_ic - raw_conf
        item["avg_ic_delta_vs_h340"] = avg_ic - h340_avg
        item["validation_ic_delta_vs_h340"] = val_ic - h340_val
        item["confirmation_ic_delta_vs_h340"] = conf_ic - h340_conf

        if name == "c5_raw":
            item["candidate_decision"] = "BASELINE"
        elif name == "h340_c5_scale_pos_buy_vol_ratio_cap_dev_median":
            item["candidate_decision"] = "H340_BENCHMARK"
        else:
            pass_condition = bool(
                item["avg_ic_delta_vs_h340"] > PASS_MIN_AVG_IC_DELTA_VS_H340
                and item["validation_ic_delta_vs_h340"] > PASS_MIN_VALIDATION_DELTA_VS_H340
                and item["confirmation_ic_delta_vs_h340"] > PASS_MIN_CONFIRMATION_DELTA_VS_H340
                and val_ic > 0.0
                and conf_ic > 0.0
                and val_rows >= MIN_PHASE_ROWS
                and conf_rows >= MIN_PHASE_ROWS
                and corr < PASS_CORR
            )
            mixed_condition = bool(
                not pass_condition
                and item["avg_ic_delta_vs_raw_c5"] > 0.0
                and item["validation_ic_delta_vs_raw_c5"] > 0.0
                and item["confirmation_ic_delta_vs_raw_c5"] > MIXED_MIN_RAW_CONFIRMATION_UPLIFT
                and val_ic > 0.0
                and conf_ic > 0.0
            )
            item["candidate_decision"] = "PASSED" if pass_condition else "MIXED" if mixed_condition else "FAILED"
        rows.append(item)

    out = pd.DataFrame(rows)
    rank = {"PASSED": 4, "MIXED": 3, "FAILED": 2, "H340_BENCHMARK": 1, "BASELINE": 0}
    out["_rank"] = out["candidate_decision"].map(rank).fillna(0)
    return out.sort_values(
        [
            "_rank",
            "confirmation_ic_delta_vs_h340",
            "validation_ic_delta_vs_h340",
            "avg_ic_delta_vs_h340",
            "avg_ic",
            "signal_name",
        ],
        ascending=[False, False, False, False, False, True],
        ignore_index=True,
    ).drop(columns="_rank")


def main() -> None:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    panel = load_base_panel()
    panel, thresholds = build_candidate_scores(panel)
    candidate_cols = [
        "c5_raw",
        "h340_c5_scale_pos_buy_vol_ratio_cap_dev_median",
        "c5_gate_pos_ff_net_5d_gt_0",
        "c5_scale_pos_ff_net_5d_cap_dev_median",
        "c5_gate_pos_ff_net_5d_lag1_gt_0",
        "c5_scale_pos_ff_net_5d_lag1_cap_dev_median",
        "c5_gate_pos_order_and_ff_net_5d_gt_0",
        "c5_scale_pos_order_x_ff_net_5d_min_cap",
    ]
    results = pd.DataFrame([summarize_candidate(panel, col) for col in candidate_cols])
    results = apply_decisions(results)

    pass_rows = results.loc[results["candidate_decision"] == "PASSED"].copy()
    mixed_rows = results.loc[results["candidate_decision"] == "MIXED"].copy()
    decision = "PASSED" if not pass_rows.empty else "MIXED" if not mixed_rows.empty else "FAILED"
    best_foreign = results.loc[
        ~results["candidate_decision"].isin(["BASELINE", "H340_BENCHMARK"])
    ].iloc[0].to_dict()
    raw_row = results.loc[results["signal_name"] == "c5_raw"].iloc[0].to_dict()
    h340_row = results.loc[
        results["signal_name"] == "h340_c5_scale_pos_buy_vol_ratio_cap_dev_median"
    ].iloc[0].to_dict()

    artifact_stem = f"{ts}_h347_foreign_insider_agreement_split"
    results_path = OUT_DIR / f"{artifact_stem}_results.parquet"
    details_path = DETAILS_DIR / f"{artifact_stem}_details.json"
    results.to_parquet(results_path, index=False)

    candidate_definitions = {
        "c5_raw": "Standalone C5 baseline.",
        "h340_c5_scale_pos_buy_vol_ratio_cap_dev_median": "Current preferred H340 same-day buy-volume pressure rewrite.",
        "c5_gate_pos_ff_net_5d_gt_0": "Zero positive C5 rows unless same-day 5d foreign net-volume share is positive.",
        "c5_scale_pos_ff_net_5d_cap_dev_median": "Scale positive C5 rows by same-day 5d foreign net-volume share capped at the dev positive median.",
        "c5_gate_pos_ff_net_5d_lag1_gt_0": "Zero positive C5 rows unless prior-day 5d foreign net-volume share is positive.",
        "c5_scale_pos_ff_net_5d_lag1_cap_dev_median": "Scale positive C5 rows by prior-day 5d foreign net-volume share capped at the dev positive median.",
        "c5_gate_pos_order_and_ff_net_5d_gt_0": "Zero positive C5 rows unless both H340 order-pressure and foreign net 5d support are positive.",
        "c5_scale_pos_order_x_ff_net_5d_min_cap": "Scale positive C5 rows by the weaker of H340 order support and foreign net 5d support.",
    }
    summary = {
        "decision": decision,
        "protocol": PROTOCOL.describe(),
        "thresholds": thresholds,
        "panel": {
            "rows": int(len(panel)),
            "tickers": int(panel["ticker"].nunique()),
            "dates": int(panel["trading_day"].nunique()),
            "foreign_net_5d_non_null_pct": float(100.0 * panel["ff_net_vol_share_5d"].notna().mean()),
            "foreign_net_5d_lag1_non_null_pct": float(
                100.0 * panel["ff_net_vol_share_5d_lag1"].notna().mean()
            ),
        },
        "raw_c5": raw_row,
        "h340_benchmark": h340_row,
        "best_foreign_candidate": best_foreign,
        "pass_candidate_count": int(len(pass_rows)),
        "mixed_candidate_count": int(len(mixed_rows)),
        "branch_decision": {
            "PASSED": "Foreign-flow agreement improves the current H340 C5 rewrite in validation and confirmation. Next: run a tighter robustness/redundancy audit before any signal-library promotion.",
            "MIXED": "Foreign-flow agreement improves raw C5 in the fixed test but does not beat the stronger H340 order-pressure rewrite. Keep as offline interaction evidence only.",
            "FAILED": "Foreign-flow agreement does not improve raw C5 or H340 enough to justify continuing the foreign-insider interaction on this contract.",
        }[decision],
    }
    details_payload = {
        "summary": summary,
        "candidate_definitions": candidate_definitions,
        "results": results.to_dict(orient="records"),
        "pass_rows": pass_rows.to_dict(orient="records"),
        "mixed_rows": mixed_rows.to_dict(orient="records"),
        "decision_thresholds": {
            "pass_requires": "avg, validation, and confirmation IC deltas all positive versus H340 benchmark",
            "mixed_requires": "avg, validation, and confirmation IC deltas all positive versus raw C5 but not H340",
            "min_phase_rows": MIN_PHASE_ROWS,
            "max_abs_corr_with_s1": PASS_CORR,
        },
    }
    details_path.write_text(json.dumps(_json_safe(details_payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    write_run_summary(
        ts=ts,
        mode="research_branch_foreign_insider_agreement_split",
        name="h347_foreign_insider_agreement_split",
        summary=summary,
        artifacts={
            "results": results_path,
            "details": details_path,
        },
        metadata={
            "session": 186,
            "protocol": PROTOCOL.describe(),
            "hypothesis": "Standalone CafeF foreign-flow failed, but foreign buy/sell pressure may still work as a non-price agreement state for bullish C5 insider conviction.",
            "no_tuning_window": "2026+",
            "candidate_definitions": candidate_definitions,
        },
    )

    print("H347 foreign-insider agreement split")
    print(json.dumps(_json_safe(summary), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
