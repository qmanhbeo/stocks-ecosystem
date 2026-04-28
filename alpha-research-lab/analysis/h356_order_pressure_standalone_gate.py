"""
H356 - CafeF Order-Pressure Standalone Gate.

Question:
- H340 showed same-day CafeF posted buy-volume pressure is a strong robustness
  conditioner for bullish C5 insider rows. Does the same order-statistics
  surface carry broad standalone alpha, or is its useful role mainly
  conditional?

Design:
- Use the raw CafeF order-statistics daily summary surface only.
- Exclude 2026 entirely.
- Primary target: canonical 1d barrier label from S1/H93.
- Diagnostic target: existing 5d forward relative-return cache, because H340's
  C5 rewrite was evaluated on the original 5d relative-return target.
- Test a small predeclared order-pressure feature set:
  same-day volume/count/average-size imbalance ranks, lagged volume/count
  imbalance ranks, a 5d mean volume-imbalance rank, and CafeF raw volume
  imbalance rank.

Decision ladder:
- PASSED: a feature clears the standalone 1d gate and the locked
  dev / validation / confirmation split:
  dev IC > 0.01, validation IC > 0.01, confirmation IC > 0.01,
  >= 60% positive years, and abs(corr with S1) < 0.30.
- MIXED: no strict 1d pass, but a feature clears the broad 1d standalone gate
  with positive validation / confirmation, or a feature clears the same strict
  split on the 5d diagnostic target.
- FAILED: no feature clears those bars.
"""

from __future__ import annotations

from datetime import datetime
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.repo_paths import artifact_path, data_path
from src.run_summary import write_run_summary
from src.standalone_signal_utils import load_s1_frame, spearman_stat


ORDER_STATS_PATH = data_path("order_stats/cafef/order_stats_daily.parquet")
FWD_REL_5D_PATH = artifact_path("cache/future_rel_return_5d_hose.parquet")
OUT_DIR = artifact_path("portfolio_baselines")

START_YEAR = 2015
DEV_YEARS = set(range(2015, 2023))
VALIDATION_YEARS = {2023, 2024}
CONFIRMATION_YEARS = {2025}
END_YEAR = 2025

PASS_IC = 0.01
PASS_CORR = 0.30
PASS_PCT_YEARS = 0.60
MIN_YEAR_ROWS = 500
MIN_PHASE_ROWS = 500

ORDER_RATIO_FEATURES = (
    "order_volume_ratio_rank",
    "order_count_ratio_rank",
    "avg_order_size_ratio_rank",
    "order_volume_ratio_lag1_rank",
    "order_count_ratio_lag1_rank",
    "order_volume_ratio_5d_rank",
    "buy_sell_volume_imbalance_rank",
)

FEATURE_DESCRIPTIONS = {
    "order_volume_ratio_rank": "rank((buy_order_volume - sell_order_volume) / total posted order volume)",
    "order_count_ratio_rank": "rank((buy_order_count - sell_order_count) / total posted order count)",
    "avg_order_size_ratio_rank": "rank((avg_buy_order_volume - avg_sell_order_volume) / total avg order size)",
    "order_volume_ratio_lag1_rank": "lag-1 rank of posted order-volume imbalance",
    "order_count_ratio_lag1_rank": "lag-1 rank of posted order-count imbalance",
    "order_volume_ratio_5d_rank": "rank of 5d mean posted order-volume imbalance",
    "buy_sell_volume_imbalance_rank": "rank of CafeF raw buy_sell_volume_imbalance",
}


def _safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _ratio(numerator_left: pd.Series, numerator_right: pd.Series) -> pd.Series:
    left = pd.to_numeric(numerator_left, errors="coerce")
    right = pd.to_numeric(numerator_right, errors="coerce")
    denom = left + right
    out = (left - right).div(denom.replace(0.0, np.nan))
    return out.replace([np.inf, -np.inf], np.nan)


def _daily_rank(frame: pd.DataFrame, source_col: str, out_col: str) -> None:
    frame[out_col] = (
        pd.to_numeric(frame[source_col], errors="coerce")
        .groupby(frame["time"], sort=False)
        .rank(method="average", pct=True, ascending=True)
    )


def _load_order_features() -> pd.DataFrame:
    order = pd.read_parquet(
        ORDER_STATS_PATH,
        columns=[
            "ticker",
            "date",
            "buy_order_count",
            "buy_order_volume",
            "avg_buy_order_volume",
            "sell_order_count",
            "sell_order_volume",
            "avg_sell_order_volume",
            "buy_sell_volume_imbalance",
        ],
    ).copy()
    order = order.rename(columns={"date": "time"})
    order["time"] = pd.to_datetime(order["time"], errors="coerce").dt.normalize()
    order["ticker"] = order["ticker"].astype(str).str.upper()
    order = order.loc[order["time"].dt.year.between(START_YEAR, END_YEAR)].copy()
    order = order.dropna(subset=["time", "ticker"]).sort_values(["ticker", "time"]).reset_index(drop=True)

    order["has_order_row"] = True
    order["order_volume_ratio"] = _ratio(order["buy_order_volume"], order["sell_order_volume"])
    order["order_count_ratio"] = _ratio(order["buy_order_count"], order["sell_order_count"])
    order["avg_order_size_ratio"] = _ratio(order["avg_buy_order_volume"], order["avg_sell_order_volume"])
    order["buy_sell_volume_imbalance"] = pd.to_numeric(order["buy_sell_volume_imbalance"], errors="coerce")

    order["order_volume_ratio_lag1"] = order.groupby("ticker", sort=False)["order_volume_ratio"].shift(1)
    order["order_count_ratio_lag1"] = order.groupby("ticker", sort=False)["order_count_ratio"].shift(1)
    order["order_volume_ratio_5d"] = (
        order.groupby("ticker", sort=False)["order_volume_ratio"]
        .rolling(5, min_periods=3)
        .mean()
        .reset_index(level=0, drop=True)
    )

    for raw_col, rank_col in (
        ("order_volume_ratio", "order_volume_ratio_rank"),
        ("order_count_ratio", "order_count_ratio_rank"),
        ("avg_order_size_ratio", "avg_order_size_ratio_rank"),
        ("order_volume_ratio_lag1", "order_volume_ratio_lag1_rank"),
        ("order_count_ratio_lag1", "order_count_ratio_lag1_rank"),
        ("order_volume_ratio_5d", "order_volume_ratio_5d_rank"),
        ("buy_sell_volume_imbalance", "buy_sell_volume_imbalance_rank"),
    ):
        _daily_rank(order, raw_col, rank_col)

    return order[["time", "ticker", "has_order_row", *ORDER_RATIO_FEATURES]]


def _load_panel() -> pd.DataFrame:
    s1 = load_s1_frame()[["time", "ticker", "actual", "xs_proba"]].copy()
    s1["time"] = pd.to_datetime(s1["time"], errors="coerce").dt.normalize()
    s1["ticker"] = s1["ticker"].astype(str).str.upper()
    s1 = s1.loc[s1["time"].dt.year.between(START_YEAR, END_YEAR)].copy()

    order = _load_order_features()
    panel = s1.merge(order, on=["time", "ticker"], how="left", validate="one_to_one")
    panel["has_order_row"] = panel["has_order_row"].where(panel["has_order_row"].notna(), False).astype(bool)

    fwd = pd.read_parquet(FWD_REL_5D_PATH, columns=["time", "ticker", "fwd_rel_5d"]).copy()
    fwd["time"] = pd.to_datetime(fwd["time"], errors="coerce").dt.normalize()
    fwd["ticker"] = fwd["ticker"].astype(str).str.upper()
    fwd = fwd.loc[fwd["time"].dt.year.between(START_YEAR, END_YEAR)].copy()
    panel = panel.merge(fwd, on=["time", "ticker"], how="left", validate="one_to_one")
    return panel


def _yearly_ic(frame: pd.DataFrame, feature: str, target: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for year, group in frame.groupby(frame["time"].dt.year, sort=True):
        clean = group[[feature, target]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(clean) < MIN_YEAR_ROWS or clean[feature].nunique() < 3 or clean[target].nunique() < 2:
            continue
        rho, p_value = spearmanr(clean[feature], clean[target])
        if np.isfinite(rho):
            rows.append(
                {
                    "year": int(year),
                    "n": int(len(clean)),
                    "ic": float(np.asarray(rho).flat[0]),
                    "p_value": float(np.asarray(p_value).flat[0]),
                }
            )
    return rows


def _phase_summary(frame: pd.DataFrame, feature: str, target: str, years: set[int]) -> dict[str, object]:
    scoped = frame.loc[frame["time"].dt.year.isin(years), [feature, target]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(scoped) < MIN_PHASE_ROWS or scoped[feature].nunique() < 3 or scoped[target].nunique() < 2:
        return {"rows": int(len(scoped)), "pooled_ic": None}
    rho = spearmanr(scoped[feature], scoped[target]).statistic
    return {"rows": int(len(scoped)), "pooled_ic": float(np.asarray(rho).flat[0])}


def _summarize_target(frame: pd.DataFrame, feature: str, target: str) -> dict[str, object]:
    active = frame.loc[frame["has_order_row"].fillna(False) & frame[feature].notna()].copy()
    yearly = _yearly_ic(active, feature, target)
    ics = [float(row["ic"]) for row in yearly]
    pos_years = int(sum(1 for ic in ics if ic > 0.0))
    avg_ic = float(np.mean(ics)) if ics else None
    pct_years_positive = float(pos_years / len(ics)) if ics else None
    corr = spearman_stat(active[feature], active["xs_proba"]) if target == "actual" else None
    phases = {
        "dev": _phase_summary(active, feature, target, DEV_YEARS),
        "validation": _phase_summary(active, feature, target, VALIDATION_YEARS),
        "confirmation": _phase_summary(active, feature, target, CONFIRMATION_YEARS),
    }
    gate = bool(
        (avg_ic or 0.0) > PASS_IC
        and (pct_years_positive or 0.0) >= PASS_PCT_YEARS
        and (target != "actual" or abs(corr or 0.0) < PASS_CORR)
    )
    strict_split = bool(
        gate
        and (_safe_float(phases["dev"]["pooled_ic"]) or 0.0) > PASS_IC
        and (_safe_float(phases["validation"]["pooled_ic"]) or 0.0) > PASS_IC
        and (_safe_float(phases["confirmation"]["pooled_ic"]) or 0.0) > PASS_IC
    )
    positive_holdout = bool(
        (_safe_float(phases["validation"]["pooled_ic"]) or 0.0) > 0.0
        and (_safe_float(phases["confirmation"]["pooled_ic"]) or 0.0) > 0.0
    )
    return {
        "target": target,
        "avg_ic": avg_ic,
        "pos_years": pos_years,
        "years": int(len(yearly)),
        "pct_years_positive": pct_years_positive,
        "corr_with_s1": corr,
        "gate_pass": gate,
        "strict_split_pass": strict_split,
        "positive_holdout": positive_holdout,
        "phase_details": phases,
        "yearly": yearly,
    }


def _result_row(panel: pd.DataFrame, feature: str) -> dict[str, object]:
    active = panel.loc[panel["has_order_row"].fillna(False) & panel[feature].notna()].copy()
    one_day = _summarize_target(panel, feature, "actual")
    five_day = _summarize_target(panel, feature, "fwd_rel_5d")
    return {
        "feature_name": feature,
        "description": FEATURE_DESCRIPTIONS[feature],
        "active_rows": int(len(active)),
        "active_dates": int(active["time"].nunique()),
        "active_tickers": int(active["ticker"].nunique()),
        "coverage_pct": float(100.0 * len(active) / len(panel)) if len(panel) else 0.0,
        "barrier_1d": one_day,
        "fwd_rel_5d": five_day,
        "barrier_1d_avg_ic": one_day["avg_ic"],
        "barrier_1d_pos_years": one_day["pos_years"],
        "barrier_1d_years": one_day["years"],
        "barrier_1d_corr_with_s1": one_day["corr_with_s1"],
        "barrier_1d_gate_pass": one_day["gate_pass"],
        "barrier_1d_strict_split_pass": one_day["strict_split_pass"],
        "barrier_1d_positive_holdout": one_day["positive_holdout"],
        "fwd_rel_5d_avg_ic": five_day["avg_ic"],
        "fwd_rel_5d_pos_years": five_day["pos_years"],
        "fwd_rel_5d_years": five_day["years"],
        "fwd_rel_5d_gate_pass": five_day["gate_pass"],
        "fwd_rel_5d_strict_split_pass": five_day["strict_split_pass"],
        "fwd_rel_5d_positive_holdout": five_day["positive_holdout"],
    }


def _sort_results(results: pd.DataFrame) -> pd.DataFrame:
    work = results.copy()
    work["_rank"] = (
        work["barrier_1d_strict_split_pass"].astype(int) * 100
        + (work["barrier_1d_gate_pass"] & work["barrier_1d_positive_holdout"]).astype(int) * 20
        + work["fwd_rel_5d_strict_split_pass"].astype(int) * 10
    )
    for column in ("barrier_1d_avg_ic", "fwd_rel_5d_avg_ic", "coverage_pct"):
        work[column] = pd.to_numeric(work[column], errors="coerce")
    return work.sort_values(
        by=["_rank", "barrier_1d_avg_ic", "fwd_rel_5d_avg_ic", "coverage_pct", "feature_name"],
        ascending=[False, False, False, False, True],
        ignore_index=True,
    ).drop(columns="_rank")


def main() -> None:
    print("H356 - CafeF Order-Pressure Standalone Gate")
    print("=" * 78)

    panel = _load_panel()
    if panel.empty:
        raise ValueError("No S1/order-statistics panel rows were built")

    rows = [_result_row(panel, feature) for feature in ORDER_RATIO_FEATURES]
    results = _sort_results(pd.DataFrame(rows))
    best = results.iloc[0].to_dict()

    strict_1d_passes = int(results["barrier_1d_strict_split_pass"].sum())
    broad_1d_mixed = int((results["barrier_1d_gate_pass"] & results["barrier_1d_positive_holdout"]).sum())
    strict_5d_passes = int(results["fwd_rel_5d_strict_split_pass"].sum())

    if strict_1d_passes:
        verdict = "PASSED"
        branch_decision = (
            "CafeF order pressure has broad standalone 1d-barrier predictive value; "
            "advance to a separate integration audit before any publication."
        )
    elif broad_1d_mixed or strict_5d_passes:
        verdict = "MIXED"
        branch_decision = (
            "Order pressure is not a clean standalone 1d signal under the strict split, "
            "but it leaves enough broad or 5d evidence to keep it as conditional state "
            "rather than a published standalone factor."
        )
    else:
        verdict = "FAILED"
        branch_decision = (
            "Broad standalone order-pressure alpha failed; keep the H340 role as a C5 "
            "conditioner and avoid standalone order-statistics retuning."
        )

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h356_order_pressure_standalone_gate_results.parquet"
    details_path = artifact_path("run_summaries") / f"{ts}_h356_order_pressure_standalone_gate_details.json"

    results_for_parquet = results.drop(columns=["barrier_1d", "fwd_rel_5d"]).copy()
    results_for_parquet.to_parquet(results_path, index=False)

    summary = {
        "verdict": verdict,
        "panel_rows": int(len(panel)),
        "panel_dates": int(panel["time"].nunique()),
        "panel_tickers": int(panel["ticker"].nunique()),
        "order_row_coverage_pct": float(100.0 * panel["has_order_row"].fillna(False).mean()),
        "protocol": {
            "dev_years": [2015, 2022],
            "validation_years": [2023, 2024],
            "confirmation_year": 2025,
            "forward_start_year": 2026,
        },
        "primary_target": "actual",
        "diagnostic_target": "fwd_rel_5d",
        "strict_1d_passes": strict_1d_passes,
        "broad_1d_mixed_count": broad_1d_mixed,
        "strict_5d_passes": strict_5d_passes,
        "best_feature": best,
        "tested_features": [
            {
                "feature_name": row["feature_name"],
                "description": row["description"],
                "active_rows": int(row["active_rows"]),
                "coverage_pct": float(row["coverage_pct"]),
                "barrier_1d_avg_ic": _safe_float(row["barrier_1d_avg_ic"]),
                "barrier_1d_pos_years": int(row["barrier_1d_pos_years"]),
                "barrier_1d_years": int(row["barrier_1d_years"]),
                "barrier_1d_corr_with_s1": _safe_float(row["barrier_1d_corr_with_s1"]),
                "barrier_1d_gate_pass": bool(row["barrier_1d_gate_pass"]),
                "barrier_1d_strict_split_pass": bool(row["barrier_1d_strict_split_pass"]),
                "fwd_rel_5d_avg_ic": _safe_float(row["fwd_rel_5d_avg_ic"]),
                "fwd_rel_5d_pos_years": int(row["fwd_rel_5d_pos_years"]),
                "fwd_rel_5d_years": int(row["fwd_rel_5d_years"]),
                "fwd_rel_5d_gate_pass": bool(row["fwd_rel_5d_gate_pass"]),
                "fwd_rel_5d_strict_split_pass": bool(row["fwd_rel_5d_strict_split_pass"]),
            }
            for row in results.to_dict("records")
        ],
        "branch_decision": branch_decision,
        "next_step": {
            "PASSED": "Run one integration audit against the frozen selector / signal matrix before publishing.",
            "MIXED": "Keep order pressure as conditional state; do not tune standalone variants unless a new target requires it.",
            "FAILED": "Do not reopen standalone order-statistics ranks under this target.",
        }[verdict],
    }
    details_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    summary_path = write_run_summary(
        ts=ts,
        mode="research_branch_order_pressure_standalone_gate",
        name="h356_order_pressure_standalone_gate",
        summary=summary,
        artifacts={
            "results": results_path,
            "details": details_path,
            "order_stats": ORDER_STATS_PATH,
            "fwd_rel_5d": FWD_REL_5D_PATH,
        },
        metadata={
            "signal": "H356",
            "family": "order_pressure",
            "protocol": summary["protocol"],
        },
    )

    print(
        f"panel rows={len(panel):,}, order coverage={summary['order_row_coverage_pct']:.2f}%, "
        f"dates={summary['panel_dates']}, tickers={summary['panel_tickers']}",
        flush=True,
    )
    print(
        "Best feature: "
        f"{best['feature_name']} | 1d IC={_safe_float(best['barrier_1d_avg_ic']) or 0.0:+.4f} | "
        f"1d strict={bool(best['barrier_1d_strict_split_pass'])} | "
        f"5d IC={_safe_float(best['fwd_rel_5d_avg_ic']) or 0.0:+.4f} | "
        f"5d strict={bool(best['fwd_rel_5d_strict_split_pass'])}",
        flush=True,
    )
    print(f"VERDICT: {verdict}", flush=True)
    print(f"summary: {summary_path}", flush=True)


if __name__ == "__main__":
    main()
