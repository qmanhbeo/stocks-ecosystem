"""
H298: calendar-conditioned quality audit.

Question:
    Do slow fundamentals and earnings-quality features become useful only
    inside predeclared report or company-event windows?
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

from src.research_protocol import DEFAULT_PROTOCOL, phase_mask
from src.run_summary import write_run_summary


BARRIER_PATH = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
EQ_PATH = data_path("features/xs_earnings_quality_daily.parquet")
FUND_PATH = data_path("features/xs_fundamentals_daily.parquet")
CALENDAR_PATH = data_path("features/xs_earnings_calendar_daily.parquet")
EVENT_PATH = data_path("features/event_surface_daily.parquet")
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"

QUALITY_COLUMNS = [
    "xs_eps_accel_rank",
    "xs_eps_yoy_rank",
    "xs_npm_trend_rank",
    "xs_roe_delta_rank",
    "xs_debt_trend_rank",
]
FUNDAMENTAL_COLUMNS = [
    "pe_ratio_rank",
    "eps_yoy_rank",
    "roe_rank",
    "npm_rank",
    "debt_eq_rank",
]
MASK_SPECS = [
    ("report_w15_45", "earnings calendar 15-45d report window"),
    ("report_w30_60", "earnings calendar 30-60d report window"),
    ("post_q_end_10d", "post quarter-end 10d"),
    ("recent_company_filing_5d", "company filing in last 5d"),
    ("corporate_action_window", "dividend or issuance window"),
    ("fresh_release_45d", "fundamental release freshness <=45d"),
    ("report_or_company_event", "report or company-event union"),
]
PASS_IC = 0.01
PASS_CORR = 0.30
PASS_COVERAGE = 0.01


def _daily_ic_series(df: pd.DataFrame, feature_col: str, target_col: str) -> pd.DataFrame:
    rows = []
    for time, group in df.groupby("time", sort=True):
        gg = group[[feature_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(gg) < 8 or gg[feature_col].nunique() < 3 or gg[target_col].nunique() < 2:
            continue
        rho = spearmanr(gg[feature_col], gg[target_col]).statistic
        if np.isfinite(rho):
            rows.append({"time": pd.Timestamp(time), "ic": float(np.asarray(rho).flat[0]), "n": int(len(gg))})
    return pd.DataFrame(rows)


def _safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _safe_spearman(left: pd.Series, right: pd.Series) -> float | None:
    clean = pd.concat([left.rename("left"), right.rename("right")], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < 100 or clean["left"].nunique() < 3:
        return None
    stat = spearmanr(clean["left"], clean["right"]).statistic
    if not np.isfinite(stat):
        return None
    return float(np.asarray(stat).flat[0])


def _summarize_phase(frame: pd.DataFrame, *, feature_col: str, mask_col: str, phase: str) -> dict[str, object]:
    scoped = frame.loc[phase_mask(frame, phase, protocol=DEFAULT_PROTOCOL)].copy()
    scoped = scoped.loc[scoped[mask_col].fillna(False).astype(bool)].copy()
    series = _daily_ic_series(scoped, feature_col, "actual")
    yearly = series.assign(year=series["time"].dt.year).groupby("year")["ic"].mean() if not series.empty else pd.Series(dtype=float)
    return {
        "rows": int(len(scoped)),
        "dates": int(scoped["time"].nunique()) if not scoped.empty else 0,
        "tickers": int(scoped["ticker"].nunique()) if not scoped.empty else 0,
        "mask_share": float(len(scoped) / len(frame.loc[phase_mask(frame, phase, protocol=DEFAULT_PROTOCOL)])) if len(frame.loc[phase_mask(frame, phase, protocol=DEFAULT_PROTOCOL)]) else 0.0,
        "avg_ic": _safe_float(series["ic"].mean()) if not series.empty else None,
        "hit_rate": _safe_float((series["ic"] > 0.0).mean()) if not series.empty else None,
        "positive_years": int((yearly > 0.0).sum()) if not yearly.empty else 0,
        "years_present": int(len(yearly)),
        "corr_with_s1": _safe_spearman(scoped[feature_col], scoped["xs_proba"]),
        "daily_ic_days": int(len(series)),
    }


def _build_panel() -> pd.DataFrame:
    barrier = pd.read_parquet(BARRIER_PATH, columns=["time", "ticker", "actual", "xs_proba"]).copy()
    eq = pd.read_parquet(EQ_PATH, columns=["time", "ticker", *QUALITY_COLUMNS]).copy()
    fund = pd.read_parquet(FUND_PATH, columns=["time", "ticker", "release_date", *FUNDAMENTAL_COLUMNS]).copy()
    calendar = pd.read_parquet(
        CALENDAR_PATH,
        columns=["time", "in_report_w15_45", "in_report_w30_60", "post_q_end_10d"],
    ).copy()
    event = pd.read_parquet(
        EVENT_PATH,
        columns=[
            "time",
            "ticker",
            "recent_any_filing_5d",
            "dividend_window_pre_20d",
            "dividend_window_post_5d",
            "issuance_window_pre_20d",
            "issuance_window_post_5d",
        ],
    ).copy()

    for frame in (barrier, eq, fund, calendar, event):
        frame["time"] = pd.to_datetime(frame["time"], errors="coerce").dt.normalize()

    fund["release_date"] = pd.to_datetime(fund["release_date"], errors="coerce")
    barrier = barrier.loc[barrier["time"].dt.year.between(2015, 2025)].copy()
    eq = eq.loc[eq["time"].dt.year.between(2015, 2025)].copy()
    fund = fund.loc[fund["time"].dt.year.between(2015, 2025)].copy()
    calendar = calendar.loc[calendar["time"].dt.year.between(2015, 2025)].copy()
    event = event.loc[event["time"].dt.year.between(2015, 2025)].copy()

    panel = barrier.merge(calendar, on="time", how="left", validate="many_to_one")
    panel = panel.merge(event, on=["time", "ticker"], how="left", validate="one_to_one")
    panel = panel.merge(eq, on=["time", "ticker"], how="left", validate="one_to_one")
    panel = panel.merge(fund, on=["time", "ticker"], how="left", validate="one_to_one")

    bool_like = [
        "in_report_w15_45",
        "in_report_w30_60",
        "post_q_end_10d",
        "recent_any_filing_5d",
        "dividend_window_pre_20d",
        "dividend_window_post_5d",
        "issuance_window_pre_20d",
        "issuance_window_post_5d",
    ]
    for column in bool_like:
        panel[column] = pd.to_numeric(panel[column], errors="coerce").fillna(0.0)

    release_lag = (panel["time"] - panel["release_date"]).dt.days
    panel["release_lag_days"] = release_lag
    panel["report_w15_45"] = panel["in_report_w15_45"] > 0.0
    panel["report_w30_60"] = panel["in_report_w30_60"] > 0.0
    panel["post_q_end_10d"] = panel["post_q_end_10d"] > 0.0
    panel["recent_company_filing_5d"] = panel["recent_any_filing_5d"] > 0.0
    panel["corporate_action_window"] = (
        (panel["dividend_window_pre_20d"] > 0.0)
        | (panel["dividend_window_post_5d"] > 0.0)
        | (panel["issuance_window_pre_20d"] > 0.0)
        | (panel["issuance_window_post_5d"] > 0.0)
    )
    panel["fresh_release_45d"] = release_lag.between(0, 45, inclusive="both")
    panel["report_or_company_event"] = (
        panel["report_w15_45"]
        | panel["recent_company_filing_5d"]
        | panel["corporate_action_window"]
        | panel["fresh_release_45d"]
    )
    return panel


def _decision_row(frame: pd.DataFrame, *, feature_col: str, feature_family: str, mask_col: str, mask_note: str) -> dict[str, object]:
    phase_rows = {
        phase: _summarize_phase(frame, feature_col=feature_col, mask_col=mask_col, phase=phase)
        for phase in ("dev", "validation", "confirmation")
    }
    dev = phase_rows["dev"]
    validation = phase_rows["validation"]
    confirmation = phase_rows["confirmation"]
    pass_condition = bool(
        (_safe_float(dev.get("avg_ic")) or 0.0) > PASS_IC
        and (_safe_float(validation.get("avg_ic")) or 0.0) > PASS_IC
        and (_safe_float(confirmation.get("avg_ic")) or 0.0) > 0.0
        and abs(_safe_float(dev.get("corr_with_s1")) or 0.0) < PASS_CORR
        and (_safe_float(validation.get("mask_share")) or 0.0) >= PASS_COVERAGE
    )
    mixed_condition = bool(
        not pass_condition
        and (_safe_float(dev.get("avg_ic")) or 0.0) > 0.0
        and (_safe_float(validation.get("avg_ic")) or 0.0) > 0.0
    )
    return {
        "feature_name": feature_col,
        "feature_family": feature_family,
        "mask_name": mask_col,
        "mask_note": mask_note,
        "candidate_decision": "PASSED" if pass_condition else "MIXED" if mixed_condition else "FAILED",
        "dev_avg_ic": dev.get("avg_ic"),
        "validation_avg_ic": validation.get("avg_ic"),
        "confirmation_avg_ic": confirmation.get("avg_ic"),
        "dev_corr_with_s1": dev.get("corr_with_s1"),
        "validation_mask_share": validation.get("mask_share"),
        "confirmation_mask_share": confirmation.get("mask_share"),
        "dev_tickers": dev.get("tickers"),
        "validation_tickers": validation.get("tickers"),
        "confirmation_tickers": confirmation.get("tickers"),
        "phase_details": phase_rows,
    }


def _sort_results(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return results.copy()
    work = results.copy()
    work["_decision_rank"] = work["candidate_decision"].map({"FAILED": 0, "MIXED": 1, "PASSED": 2}).fillna(-1)
    for column in ("validation_avg_ic", "confirmation_avg_ic", "dev_avg_ic"):
        work[column] = pd.to_numeric(work[column], errors="coerce")
    return work.sort_values(
        by=["_decision_rank", "validation_avg_ic", "confirmation_avg_ic", "dev_avg_ic", "feature_name", "mask_name"],
        ascending=[False, False, False, False, True, True],
        ignore_index=True,
    ).drop(columns="_decision_rank")


def main() -> None:
    panel = _build_panel()
    rows: list[dict[str, object]] = []
    for feature in QUALITY_COLUMNS:
        for mask_name, mask_note in MASK_SPECS:
            rows.append(_decision_row(panel, feature_col=feature, feature_family="earnings_quality", mask_col=mask_name, mask_note=mask_note))
    for feature in FUNDAMENTAL_COLUMNS:
        for mask_name, mask_note in MASK_SPECS:
            rows.append(_decision_row(panel, feature_col=feature, feature_family="fundamentals", mask_col=mask_name, mask_note=mask_note))
    results = _sort_results(pd.DataFrame(rows))
    if results.empty:
        raise ValueError("H298 produced no conditioned-quality rows")

    promoted = results.loc[results["candidate_decision"] == "PASSED"].copy()
    mixed = results.loc[results["candidate_decision"] == "MIXED"].copy()
    verdict = "PASSED" if not promoted.empty else "MIXED" if not mixed.empty else "FAILED"
    best_candidate = results.iloc[0].to_dict()
    branch_decision = {
        "PASSED": (
            "Slow-data quality survives only inside explicit report or company-event clocks. "
            "Advance the winning condition as a narrow conditioned branch."
        ),
        "MIXED": (
            "Conditioning helps, but not enough to reopen the slow-data family broadly. "
            "Keep only as constrained offline evidence tied to specific clocks."
        ),
        "FAILED": (
            "Close the conditioned-quality rescue branch on the current contract. "
            "Timing masks do not rescue the slow-data family enough to continue."
        ),
    }[verdict]

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h298_calendar_conditioned_quality_results.parquet"
    panel_path = OUT_DIR / f"{ts}_h298_calendar_conditioned_quality_panel.parquet"
    details_path = ROOT / "artifacts" / "run_summaries" / f"{ts}_h298_calendar_conditioned_quality_details.json"
    results.to_parquet(results_path, index=False)
    panel.to_parquet(panel_path, index=False)

    summary = {
        "verdict": verdict,
        "hypothesis": (
            "Earnings quality and fundamental ranks are not always-on factors, but may only activate "
            "near report clocks or fresh company-event windows."
        ),
        "protocol": DEFAULT_PROTOCOL.describe(),
        "panel_rows": int(len(panel)),
        "panel_dates": int(panel["time"].nunique()),
        "best_candidate": best_candidate,
        "passed_rows": promoted[
            [
                "feature_name",
                "feature_family",
                "mask_name",
                "dev_avg_ic",
                "validation_avg_ic",
                "confirmation_avg_ic",
                "dev_corr_with_s1",
            ]
        ].to_dict("records"),
        "tested_rows": results[
            [
                "feature_name",
                "feature_family",
                "mask_name",
                "candidate_decision",
                "dev_avg_ic",
                "validation_avg_ic",
                "confirmation_avg_ic",
                "validation_mask_share",
                "dev_tickers",
                "validation_tickers",
                "confirmation_tickers",
            ]
        ].to_dict("records"),
        "branch_decision": branch_decision,
    }
    details_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    write_run_summary(
        ts=ts,
        mode="research_branch_calendar_conditioned_quality",
        name="h298_calendar_conditioned_quality",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "panel": str(panel_path),
            "details": str(details_path),
        },
        metadata={
            "session": 128,
            "years": [2015, 2025],
        },
    )

    print("H298 calendar-conditioned quality")
    print(
        results[
            [
                "feature_name",
                "feature_family",
                "mask_name",
                "candidate_decision",
                "dev_avg_ic",
                "validation_avg_ic",
                "confirmation_avg_ic",
                "validation_mask_share",
            ]
        ].head(20).to_string(index=False)
    )
    print(f"\nVerdict: {verdict}")
    print(branch_decision)


if __name__ == "__main__":
    main()
