"""
H303: event-conditioned intraday disagreement audit.

Question:
    Do the surviving H299 disagreement atoms sharpen materially when restricted
    to the fresh company-event windows recovered by the H301 CafeF event-v2
    pilot, or do the intraday and event branches stay better treated as
    separate offline evidence lines?
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
WORKSPACE_ROOT = ROOT.parent
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.additive_selector_research import load_summary_payload, resolve_summary_artifact
from src.research_protocol import ResearchProtocol, phase_mask
from src.run_summary import write_run_summary


H299_SUMMARY_PATH = ROOT / "artifacts" / "run_summaries/latest_research_branch_intraday_library_atoms.json"
H301_SUMMARY_PATH = ROOT / "artifacts" / "run_summaries/latest_research_branch_cafef_event_surface_v2_pilot.json"
EVENT_SURFACE_V1_PATH = data_path("features/event_surface_daily.parquet")
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"

PROTOCOL = ResearchProtocol(
    dev_start_year=2023,
    dev_end_year=2023,
    validation_start_year=2024,
    validation_end_year=2024,
    confirmation_year=2025,
    forward_start_year=2026,
)

SIGNAL_COLUMNS = (
    "fade_tension_disagreement",
    "intraday_shape_core_disagreement",
)

COHORT_SPECS = (
    ("full_observed", "Full observed H299 panel", "all"),
    ("event_v2_1d", "H301 event-v2 same-day", "event_v2"),
    ("no_event_v2_1d", "No H301 event-v2 same-day", "control"),
    ("event_v2_5d", "H301 event-v2 recent 5d", "event_v2"),
    ("no_event_v2_5d", "No H301 event-v2 recent 5d", "control"),
    ("v1_proxy_1d", "Broad v1 company proxy same-day", "control"),
    ("v1_proxy_5d", "Broad v1 company proxy recent 5d", "control"),
)

MIN_DAILY_IC_OBS = 3
PASS_VALIDATION_UPLIFT_VS_FULL = 0.010
PASS_CONFIRMATION_UPLIFT_VS_FULL = 0.005
PASS_VALIDATION_UPLIFT_VS_NO_EVENT = 0.010
PASS_CONFIRMATION_UPLIFT_VS_NO_EVENT = 0.005
PASS_VALIDATION_UPLIFT_VS_V1 = 0.005
PASS_CONFIRMATION_UPLIFT_VS_V1 = 0.000
PASS_MIN_VALIDATION_DAYS = 150
PASS_MIN_CONFIRMATION_DAYS = 150


def _json_safe(value: object):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        if pd.isna(value):
            return None
        return value.item()
    if isinstance(value, float) and pd.isna(value):
        return None
    return value


def _safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _build_v1_controls() -> pd.DataFrame:
    v1 = pd.read_parquet(
        EVENT_SURFACE_V1_PATH,
        columns=[
            "time",
            "ticker",
            "dividend_window_pre_20d",
            "dividend_window_post_5d",
            "issuance_window_pre_20d",
            "issuance_window_post_5d",
            "recent_insider_filing_5d",
            "recent_major_holder_filing_5d",
            "recent_any_filing_5d",
        ],
    ).copy()
    v1["time"] = pd.to_datetime(v1["time"], errors="coerce").dt.normalize()
    v1 = v1.loc[v1["time"].dt.year.between(2023, 2025)].copy()
    proxy_cols = [
        "dividend_window_pre_20d",
        "dividend_window_post_5d",
        "issuance_window_pre_20d",
        "issuance_window_post_5d",
        "recent_insider_filing_5d",
        "recent_major_holder_filing_5d",
        "recent_any_filing_5d",
    ]
    for column in proxy_cols:
        v1[column] = pd.to_numeric(v1[column], errors="coerce").fillna(0.0)
    v1["has_company_proxy_v1"] = v1[proxy_cols].gt(0.0).any(axis=1).astype(int)
    v1 = v1.sort_values(["ticker", "time"]).reset_index(drop=True)
    v1["recent_company_proxy_v1_5d"] = (
        v1.groupby("ticker")["has_company_proxy_v1"]
        .rolling(window=5, min_periods=1)
        .sum()
        .reset_index(level=0, drop=True)
        .astype(float)
    )
    return v1[["time", "ticker", "has_company_proxy_v1", "recent_company_proxy_v1_5d"]].copy()


def _attach_cohort_flags(scored_panel: pd.DataFrame, pilot_surface: pd.DataFrame) -> pd.DataFrame:
    work = scored_panel.copy()
    work["time"] = pd.to_datetime(work["time"], errors="coerce").dt.normalize()
    work = work.loc[work["time"].dt.year.between(2023, 2025)].copy()

    pilot = pilot_surface[["time", "ticker", "has_company_event_article_v2", "recent_company_event_article_v2_5d"]].copy()
    pilot["time"] = pd.to_datetime(pilot["time"], errors="coerce").dt.normalize()

    v1 = _build_v1_controls()
    work = work.merge(pilot, on=["time", "ticker"], how="left", validate="one_to_one")
    work = work.merge(v1, on=["time", "ticker"], how="left", validate="one_to_one")
    fill_zero_cols = [
        "has_company_event_article_v2",
        "recent_company_event_article_v2_5d",
        "has_company_proxy_v1",
        "recent_company_proxy_v1_5d",
    ]
    for column in fill_zero_cols:
        work[column] = pd.to_numeric(work[column], errors="coerce").fillna(0.0)
    work["event_v2_1d"] = work["has_company_event_article_v2"].gt(0.0)
    work["no_event_v2_1d"] = ~work["event_v2_1d"]
    work["event_v2_5d"] = work["recent_company_event_article_v2_5d"].gt(0.0)
    work["no_event_v2_5d"] = ~work["event_v2_5d"]
    work["v1_proxy_1d"] = work["has_company_proxy_v1"].gt(0.0)
    work["v1_proxy_5d"] = work["recent_company_proxy_v1_5d"].gt(0.0)
    work["full_observed"] = True
    return work


def _daily_ic_series(frame: pd.DataFrame, signal_col: str) -> pd.DataFrame:
    rows = []
    for time, group in frame.groupby("time", sort=True):
        clean = group[[signal_col, "actual"]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(clean) < MIN_DAILY_IC_OBS or clean[signal_col].nunique() < 2 or clean["actual"].nunique() < 2:
            continue
        rho, p_value = spearmanr(clean[signal_col], clean["actual"])
        if np.isfinite(rho):
            rows.append(
                {
                    "time": pd.Timestamp(time),
                    "n": int(len(clean)),
                    "ic": float(rho),
                    "p_value": float(p_value),
                }
            )
    return pd.DataFrame(rows)


def _phase_summary(frame: pd.DataFrame, *, signal_col: str, phase: str) -> dict[str, object]:
    scoped = frame.loc[phase_mask(frame, phase, protocol=PROTOCOL)].copy()
    ic_rows = _daily_ic_series(scoped, signal_col)
    yearly = ic_rows.assign(year=ic_rows["time"].dt.year).groupby("year")["ic"].mean() if not ic_rows.empty else pd.Series(dtype=float)
    return {
        "avg_ic": float(ic_rows["ic"].mean()) if not ic_rows.empty else None,
        "daily_hit_rate": float((ic_rows["ic"] > 0.0).mean()) if not ic_rows.empty else None,
        "positive_years": int((yearly > 0.0).sum()) if not yearly.empty else 0,
        "years_present": int(len(yearly)),
        "daily_ic_rows": int(len(ic_rows)),
        "cohort_rows": int(len(scoped)),
        "active_dates": int(scoped["time"].nunique()) if not scoped.empty else 0,
        "avg_names_per_ic_day": float(ic_rows["n"].mean()) if not ic_rows.empty else None,
        "median_names_per_ic_day": float(ic_rows["n"].median()) if not ic_rows.empty else None,
    }


def _cohort_mask(frame: pd.DataFrame, cohort_name: str) -> pd.Series:
    if cohort_name not in frame.columns:
        raise KeyError(f"Unknown cohort column {cohort_name!r}")
    return frame[cohort_name].fillna(False).astype(bool)


def _cohort_row(frame: pd.DataFrame, *, signal_name: str, cohort_name: str, cohort_label: str, cohort_family: str) -> dict[str, object]:
    scoped = frame.loc[_cohort_mask(frame, cohort_name)].copy()
    row = {
        "signal_name": signal_name,
        "cohort_name": cohort_name,
        "cohort_label": cohort_label,
        "cohort_family": cohort_family,
    }
    for phase in ("dev", "validation", "confirmation"):
        summary = _phase_summary(scoped, signal_col=signal_name, phase=phase)
        for key, value in summary.items():
            row[f"{phase}_{key}"] = value
    return row


def _lookup_row(results: pd.DataFrame, *, signal_name: str, cohort_name: str) -> pd.Series | None:
    match = results.loc[(results["signal_name"] == signal_name) & (results["cohort_name"] == cohort_name)]
    if match.empty:
        return None
    return match.iloc[0]


def _attach_comparisons(results: pd.DataFrame) -> pd.DataFrame:
    work = results.copy()
    for phase in ("dev", "validation", "confirmation"):
        for suffix in ("uplift_vs_full", "uplift_vs_no_event", "uplift_vs_v1"):
            work[f"{phase}_{suffix}"] = np.nan

    for idx, row in work.iterrows():
        cohort_name = str(row["cohort_name"])
        if not cohort_name.startswith("event_v2_"):
            continue
        signal_name = str(row["signal_name"])
        window = cohort_name.rsplit("_", 1)[-1]
        baseline_row = _lookup_row(work, signal_name=signal_name, cohort_name="full_observed")
        no_event_row = _lookup_row(work, signal_name=signal_name, cohort_name=f"no_event_v2_{window}")
        v1_row = _lookup_row(work, signal_name=signal_name, cohort_name=f"v1_proxy_{window}")
        for phase in ("dev", "validation", "confirmation"):
            current_ic = _safe_float(row.get(f"{phase}_avg_ic"))
            baseline_ic = _safe_float(baseline_row.get(f"{phase}_avg_ic")) if baseline_row is not None else None
            no_event_ic = _safe_float(no_event_row.get(f"{phase}_avg_ic")) if no_event_row is not None else None
            v1_ic = _safe_float(v1_row.get(f"{phase}_avg_ic")) if v1_row is not None else None
            work.loc[idx, f"{phase}_uplift_vs_full"] = current_ic - baseline_ic if current_ic is not None and baseline_ic is not None else np.nan
            work.loc[idx, f"{phase}_uplift_vs_no_event"] = current_ic - no_event_ic if current_ic is not None and no_event_ic is not None else np.nan
            work.loc[idx, f"{phase}_uplift_vs_v1"] = current_ic - v1_ic if current_ic is not None and v1_ic is not None else np.nan
    return work


def _sort_results(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return results.copy()
    work = results.copy()
    for column in [
        "validation_uplift_vs_full",
        "confirmation_uplift_vs_full",
        "validation_avg_ic",
        "confirmation_avg_ic",
        "dev_avg_ic",
    ]:
        work[column] = pd.to_numeric(work[column], errors="coerce")
    work["_priority"] = np.where(work["cohort_name"].eq("event_v2_5d"), 2, np.where(work["cohort_name"].eq("event_v2_1d"), 1, 0))
    return work.sort_values(
        by=["_priority", "validation_uplift_vs_full", "confirmation_uplift_vs_full", "validation_avg_ic", "signal_name", "cohort_name"],
        ascending=[False, False, False, False, True, True],
        ignore_index=True,
    ).drop(columns="_priority")


def _pass_condition(row: pd.Series) -> bool:
    return bool(
        row.get("cohort_name") == "event_v2_5d"
        and (_safe_float(row.get("validation_uplift_vs_full")) or -np.inf) >= PASS_VALIDATION_UPLIFT_VS_FULL
        and (_safe_float(row.get("confirmation_uplift_vs_full")) or -np.inf) >= PASS_CONFIRMATION_UPLIFT_VS_FULL
        and (_safe_float(row.get("validation_uplift_vs_no_event")) or -np.inf) >= PASS_VALIDATION_UPLIFT_VS_NO_EVENT
        and (_safe_float(row.get("confirmation_uplift_vs_no_event")) or -np.inf) >= PASS_CONFIRMATION_UPLIFT_VS_NO_EVENT
        and (_safe_float(row.get("validation_uplift_vs_v1")) or -np.inf) >= PASS_VALIDATION_UPLIFT_VS_V1
        and (_safe_float(row.get("confirmation_uplift_vs_v1")) or -np.inf) >= PASS_CONFIRMATION_UPLIFT_VS_V1
        and int(pd.to_numeric(row.get("validation_daily_ic_rows"), errors="coerce") or 0) >= PASS_MIN_VALIDATION_DAYS
        and int(pd.to_numeric(row.get("confirmation_daily_ic_rows"), errors="coerce") or 0) >= PASS_MIN_CONFIRMATION_DAYS
    )


def _mixed_condition(row: pd.Series) -> bool:
    return bool(
        (_safe_float(row.get("validation_uplift_vs_full")) or -np.inf) > 0.0
        and (_safe_float(row.get("validation_uplift_vs_no_event")) or -np.inf) > 0.0
        and (_safe_float(row.get("validation_uplift_vs_v1")) or -np.inf) > 0.0
        and (_safe_float(row.get("confirmation_avg_ic")) or -np.inf) > 0.0
    )


def main() -> None:
    h299_payload = load_summary_payload(H299_SUMMARY_PATH)
    h301_payload = load_summary_payload(H301_SUMMARY_PATH)
    if h299_payload.get("summary", {}).get("decision") != "PASSED":
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        write_run_summary(
            ts=ts,
            mode="research_branch_event_conditioned_intraday_disagreement",
            name="h303_event_conditioned_intraday_disagreement",
            summary={
                "decision": "SKIP",
                "skipped": True,
                "reason": "H299 did not survive as the active disagreement-atom continuation branch.",
            },
            artifacts={},
            metadata={"session": 129, "protocol": PROTOCOL.describe()},
        )
        return
    if h301_payload.get("summary", {}).get("decision") not in {"PASSED", "MIXED"}:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        write_run_summary(
            ts=ts,
            mode="research_branch_event_conditioned_intraday_disagreement",
            name="h303_event_conditioned_intraday_disagreement",
            summary={
                "decision": "SKIP",
                "skipped": True,
                "reason": "H301 event-v2 pilot artifact is not available as a usable acquisition surface.",
            },
            artifacts={},
            metadata={"session": 129, "protocol": PROTOCOL.describe()},
        )
        return

    scored_panel_path = resolve_summary_artifact(H299_SUMMARY_PATH, "scored_panel")
    pilot_surface_path = resolve_summary_artifact(H301_SUMMARY_PATH, "pilot_surface")

    scored_panel = pd.read_parquet(scored_panel_path, columns=["time", "ticker", "actual", *SIGNAL_COLUMNS]).copy()
    pilot_surface = pd.read_parquet(
        pilot_surface_path,
        columns=["time", "ticker", "has_company_event_article_v2", "recent_company_event_article_v2_5d"],
    ).copy()
    panel = _attach_cohort_flags(scored_panel, pilot_surface)

    rows = []
    for signal_name in SIGNAL_COLUMNS:
        for cohort_name, cohort_label, cohort_family in COHORT_SPECS:
            rows.append(
                _cohort_row(
                    panel,
                    signal_name=signal_name,
                    cohort_name=cohort_name,
                    cohort_label=cohort_label,
                    cohort_family=cohort_family,
                )
            )
    results = _attach_comparisons(pd.DataFrame(rows))
    results = _sort_results(results)

    event_rows = results.loc[results["cohort_name"].isin(["event_v2_1d", "event_v2_5d"])].copy()
    pass_rows = event_rows.loc[event_rows.apply(_pass_condition, axis=1)].copy()
    mixed_rows = event_rows.loc[event_rows.apply(_mixed_condition, axis=1)].copy()
    decision = "PASSED" if not pass_rows.empty else "MIXED" if not mixed_rows.empty else "FAILED"
    best_event_row = event_rows.iloc[0].to_dict() if not event_rows.empty else {}

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    artifact_stem = f"{ts}_h303_event_conditioned_intraday_disagreement"
    results_path = OUT_DIR / f"{artifact_stem}_results.parquet"
    panel_path = OUT_DIR / f"{artifact_stem}_panel.parquet"
    details_path = ROOT / "artifacts" / "run_summaries" / f"{artifact_stem}_details.json"

    results.to_parquet(results_path, index=False)
    panel[
        [
            "time",
            "ticker",
            "actual",
            *SIGNAL_COLUMNS,
            "has_company_event_article_v2",
            "recent_company_event_article_v2_5d",
            "has_company_proxy_v1",
            "recent_company_proxy_v1_5d",
            "event_v2_1d",
            "event_v2_5d",
            "v1_proxy_1d",
            "v1_proxy_5d",
        ]
    ].to_parquet(panel_path, index=False)

    summary = {
        "decision": decision,
        "protocol": PROTOCOL.describe(),
        "observed_rows": int(len(panel)),
        "observed_dates": int(panel["time"].nunique()) if not panel.empty else 0,
        "observed_tickers": int(panel["ticker"].nunique()) if not panel.empty else 0,
        "best_event_candidate": best_event_row,
        "pass_candidate_count": int(len(pass_rows)),
        "mixed_candidate_count": int(len(mixed_rows)),
        "tested_signals": list(SIGNAL_COLUMNS),
        "branch_decision": {
            "PASSED": "A recent H301 event-v2 window materially sharpens at least one H299 disagreement atom beyond the unconditional baseline, the no-event complement, and the broad v1 proxy.",
            "MIXED": "Event-v2 windows create local uplift for the disagreement atoms, but the effect is not strong or stable enough to reopen a predictive timing branch yet.",
            "FAILED": "The H299 disagreement atoms do not sharpen enough inside H301 event-v2 windows to beat the unconditional baseline or the broad v1 company-proxy control.",
        }[decision],
    }

    details_payload = {
        "summary": summary,
        "event_rows": event_rows.to_dict(orient="records"),
        "all_rows": results.to_dict(orient="records"),
        "pass_rows": pass_rows.to_dict(orient="records"),
        "mixed_rows": mixed_rows.to_dict(orient="records"),
        "thresholds": {
            "pass_validation_uplift_vs_full": PASS_VALIDATION_UPLIFT_VS_FULL,
            "pass_confirmation_uplift_vs_full": PASS_CONFIRMATION_UPLIFT_VS_FULL,
            "pass_validation_uplift_vs_no_event": PASS_VALIDATION_UPLIFT_VS_NO_EVENT,
            "pass_confirmation_uplift_vs_no_event": PASS_CONFIRMATION_UPLIFT_VS_NO_EVENT,
            "pass_validation_uplift_vs_v1": PASS_VALIDATION_UPLIFT_VS_V1,
            "pass_confirmation_uplift_vs_v1": PASS_CONFIRMATION_UPLIFT_VS_V1,
            "pass_min_validation_days": PASS_MIN_VALIDATION_DAYS,
            "pass_min_confirmation_days": PASS_MIN_CONFIRMATION_DAYS,
            "min_daily_ic_obs": MIN_DAILY_IC_OBS,
        },
    }
    details_path.write_text(json.dumps(_json_safe(details_payload), indent=2) + "\n", encoding="utf-8")

    write_run_summary(
        ts=ts,
        mode="research_branch_event_conditioned_intraday_disagreement",
        name="h303_event_conditioned_intraday_disagreement",
        summary=summary,
        artifacts={
            "results": results_path,
            "panel": panel_path,
            "details": details_path,
        },
        metadata={
            "session": 129,
            "protocol": PROTOCOL.describe(),
            "branch_contract": "H303 is a narrow continuation of H299 on the 2023-2025 observed subset only; no live-branch change.",
            "source_h299_summary": H299_SUMMARY_PATH,
            "source_h301_summary": H301_SUMMARY_PATH,
        },
    )

    print("H303 event-conditioned intraday disagreement audit")
    print(json.dumps(_json_safe(summary), indent=2))


if __name__ == "__main__":
    main()
