"""
H312: v2-v1 disagreement router audit.

Question:
    Does the H309/H310 issuer-specific event surface add predictive value
    mainly when it disagrees with the broad v1 company proxy surface?
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

from src.additive_selector_research import resolve_summary_artifact
from src.future_return_research import load_future_rel_5d
from src.research_protocol import ResearchProtocol, phase_mask
from src.run_summary import write_run_summary


H310_SUMMARY_PATH = ROOT / "artifacts" / "run_summaries" / "latest_research_branch_event_v2_predictive_rescreen.json"
S1_PATH = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
EVENT_V1_PATH = data_path("features/event_surface_daily.parquet")
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"

PROTOCOL = ResearchProtocol(
    dev_start_year=2023,
    dev_end_year=2023,
    validation_start_year=2024,
    validation_end_year=2024,
    confirmation_year=2025,
    forward_start_year=2026,
)

COHORTS = ("none_5d", "v1_only_5d", "v2_only_5d", "both_5d")
MIN_DAILY_IC_OBS = 3
PASS_MIN_ROWS = 200
PASS_IC_UPLIFT = 0.01
PASS_FWD5_UPLIFT = 0.01
MIXED_MIN_ROWS = 100


def _safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _load_pilot_surface_path() -> Path:
    return resolve_summary_artifact(H310_SUMMARY_PATH, "combined_pilot_surface")


def _build_v1_controls() -> pd.DataFrame:
    v1 = pd.read_parquet(
        EVENT_V1_PATH,
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
    v1["v1_proxy_5d"] = v1[proxy_cols].gt(0.0).any(axis=1)
    return v1[["time", "ticker", "v1_proxy_5d"]].copy()


def load_panel() -> pd.DataFrame:
    s1 = pd.read_parquet(S1_PATH, columns=["time", "ticker", "xs_proba", "actual"]).copy()
    s1["time"] = pd.to_datetime(s1["time"], errors="coerce").dt.normalize()
    s1 = s1.loc[s1["time"].dt.year.between(2023, 2025)].copy()

    future5 = load_future_rel_5d(start_year=2023, end_year=2025).copy()
    v1 = _build_v1_controls()
    v2 = pd.read_parquet(
        _load_pilot_surface_path(),
        columns=["time", "ticker", "recent_company_event_article_v2_5d", "has_company_event_article_v2"],
    ).copy()
    v2["time"] = pd.to_datetime(v2["time"], errors="coerce").dt.normalize()
    v2 = v2.loc[v2["time"].dt.year.between(2023, 2025)].copy()
    for column in ("recent_company_event_article_v2_5d", "has_company_event_article_v2"):
        v2[column] = pd.to_numeric(v2[column], errors="coerce").fillna(0.0)

    panel = s1.merge(future5, on=["time", "ticker"], how="left", validate="one_to_one")
    panel = panel.merge(v1, on=["time", "ticker"], how="left", validate="one_to_one")
    panel = panel.merge(v2, on=["time", "ticker"], how="left", validate="one_to_one")
    panel["v1_proxy_5d"] = panel["v1_proxy_5d"].fillna(False).astype(bool)
    panel["v2_proxy_5d"] = pd.to_numeric(panel["recent_company_event_article_v2_5d"], errors="coerce").fillna(0.0) > 0.0
    panel["none_5d"] = ~panel["v1_proxy_5d"] & ~panel["v2_proxy_5d"]
    panel["v1_only_5d"] = panel["v1_proxy_5d"] & ~panel["v2_proxy_5d"]
    panel["v2_only_5d"] = panel["v2_proxy_5d"] & ~panel["v1_proxy_5d"]
    panel["both_5d"] = panel["v1_proxy_5d"] & panel["v2_proxy_5d"]
    return panel.dropna(subset=["actual", "fwd_rel_5d"]).reset_index(drop=True)


def _daily_ic_series(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for time, group in frame.groupby("time", sort=True):
        clean = group[["xs_proba", "actual"]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(clean) < MIN_DAILY_IC_OBS or clean["xs_proba"].nunique() < 2 or clean["actual"].nunique() < 2:
            continue
        rho, p = spearmanr(clean["xs_proba"], clean["actual"])
        if np.isfinite(rho):
            rows.append({"time": pd.Timestamp(time), "ic": float(np.asarray(rho).flat[0]), "p_value": float(p)})
    return pd.DataFrame(rows)


def _pooled_ic(frame: pd.DataFrame) -> float | None:
    clean = frame[["xs_proba", "actual"]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < 30 or clean["xs_proba"].nunique() < 3 or clean["actual"].nunique() < 2:
        return None
    rho = spearmanr(clean["xs_proba"], clean["actual"]).statistic
    return None if not np.isfinite(rho) else float(np.asarray(rho).flat[0])


def _phase_summary(frame: pd.DataFrame, *, cohort: str, phase: str) -> dict[str, object]:
    scoped = frame.loc[phase_mask(frame, phase, protocol=PROTOCOL) & frame[cohort].fillna(False).astype(bool)].copy()
    daily_ic = _daily_ic_series(scoped)
    return {
        "rows": int(len(scoped)),
        "dates": int(scoped["time"].nunique()) if not scoped.empty else 0,
        "pooled_ic": _pooled_ic(scoped),
        "daily_ic_mean": _safe_float(daily_ic["ic"].mean()) if not daily_ic.empty else None,
        "actual_mean": _safe_float(scoped["actual"].mean()) if not scoped.empty else None,
        "fwd5_mean": _safe_float(scoped["fwd_rel_5d"].mean()) if not scoped.empty else None,
    }


def evaluate(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for cohort in COHORTS:
        row = {"cohort": cohort}
        for phase in ("dev", "validation", "confirmation"):
            summary = _phase_summary(panel, cohort=cohort, phase=phase)
            for key, value in summary.items():
                row[f"{phase}_{key}"] = value
        rows.append(row)

    results = pd.DataFrame(rows)
    by_name = results.set_index("cohort")
    for phase in ("validation", "confirmation"):
        for ref in ("v1_only_5d", "both_5d"):
            results.loc[results["cohort"].eq("v2_only_5d"), f"{phase}_ic_uplift_vs_{ref}"] = (
                (_safe_float(by_name.loc["v2_only_5d", f"{phase}_pooled_ic"]) or 0.0)
                - (_safe_float(by_name.loc[ref, f"{phase}_pooled_ic"]) or 0.0)
            )
            results.loc[results["cohort"].eq("v2_only_5d"), f"{phase}_fwd5_uplift_vs_{ref}"] = (
                (_safe_float(by_name.loc["v2_only_5d", f"{phase}_fwd5_mean"]) or 0.0)
                - (_safe_float(by_name.loc[ref, f"{phase}_fwd5_mean"]) or 0.0)
            )

    results["candidate_decision"] = "FAILED"
    v2_only = results.loc[results["cohort"].eq("v2_only_5d")].iloc[0]
    pass_condition = bool(
        int(pd.to_numeric(v2_only.get("validation_rows"), errors="coerce") or 0) >= PASS_MIN_ROWS
        and int(pd.to_numeric(v2_only.get("confirmation_rows"), errors="coerce") or 0) >= PASS_MIN_ROWS
        and (_safe_float(v2_only.get("validation_pooled_ic")) or -np.inf) > 0.0
        and (_safe_float(v2_only.get("confirmation_pooled_ic")) or -np.inf) > 0.0
        and (_safe_float(v2_only.get("validation_ic_uplift_vs_v1_only_5d")) or -np.inf) >= PASS_IC_UPLIFT
        and (_safe_float(v2_only.get("confirmation_ic_uplift_vs_v1_only_5d")) or -np.inf) >= 0.0
        and (_safe_float(v2_only.get("validation_ic_uplift_vs_both_5d")) or -np.inf) >= PASS_IC_UPLIFT
        and (_safe_float(v2_only.get("validation_fwd5_uplift_vs_v1_only_5d")) or -np.inf) >= PASS_FWD5_UPLIFT
    )
    mixed_condition = bool(
        not pass_condition
        and int(pd.to_numeric(v2_only.get("validation_rows"), errors="coerce") or 0) >= MIXED_MIN_ROWS
        and int(pd.to_numeric(v2_only.get("confirmation_rows"), errors="coerce") or 0) >= MIXED_MIN_ROWS
        and (
            (_safe_float(v2_only.get("validation_ic_uplift_vs_v1_only_5d")) or -np.inf) > 0.0
            or (_safe_float(v2_only.get("confirmation_ic_uplift_vs_v1_only_5d")) or -np.inf) > 0.0
            or (_safe_float(v2_only.get("validation_fwd5_uplift_vs_v1_only_5d")) or -np.inf) > 0.0
        )
    )
    results.loc[results["cohort"].eq("v2_only_5d"), "candidate_decision"] = "PASSED" if pass_condition else "MIXED" if mixed_condition else "FAILED"
    return results


def main() -> None:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    panel = load_panel()
    results = evaluate(panel)
    panel_path = OUT_DIR / f"{ts}_h312_v2_v1_disagreement_router_panel.parquet"
    results_path = OUT_DIR / f"{ts}_h312_v2_v1_disagreement_router_results.parquet"
    panel.to_parquet(panel_path, index=False)
    results.to_parquet(results_path, index=False)

    v2_row = results.loc[results["cohort"].eq("v2_only_5d")].iloc[0].to_dict()
    if v2_row["candidate_decision"] == "PASSED":
        decision = "PASSED"
        branch_decision = "Issuer-specific v2 events are genuinely additive when v1 is silent; the disagreement router is real."
    elif v2_row["candidate_decision"] == "MIXED":
        decision = "MIXED"
        branch_decision = "v2-only disagreement is directionally better than the broad v1 states, but not strong enough to call a full router yet."
    else:
        decision = "FAILED"
        branch_decision = "The richer v2 surface does not add stable value mainly through v1 disagreement; broad v1 states still dominate."

    details = {"results": results.to_dict(orient="records"), "v2_only_row": v2_row, "panel_rows": int(len(panel))}
    details_path = DETAILS_DIR / f"{ts}_h312_v2_v1_disagreement_router_details.json"
    details_path.write_text(json.dumps(details, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    summary = {
        "decision": decision,
        "branch_decision": branch_decision,
        "panel_rows": int(len(panel)),
        "v2_only_candidate": {
            "candidate_decision": v2_row.get("candidate_decision"),
            "validation_rows": v2_row.get("validation_rows"),
            "confirmation_rows": v2_row.get("confirmation_rows"),
            "validation_pooled_ic": v2_row.get("validation_pooled_ic"),
            "confirmation_pooled_ic": v2_row.get("confirmation_pooled_ic"),
            "validation_ic_uplift_vs_v1_only_5d": v2_row.get("validation_ic_uplift_vs_v1_only_5d"),
            "validation_ic_uplift_vs_both_5d": v2_row.get("validation_ic_uplift_vs_both_5d"),
            "validation_fwd5_uplift_vs_v1_only_5d": v2_row.get("validation_fwd5_uplift_vs_v1_only_5d"),
        },
    }
    write_run_summary(
        ts=ts,
        mode="research_branch_v2_v1_disagreement_router",
        name="h312_v2_v1_disagreement_router",
        summary=summary,
        artifacts={"panel": panel_path, "results": results_path, "details": details_path},
        metadata={
            "session": 136,
            "branch_contract": "Only a stable v2-only advantage over v1-only and both-active cohorts can reopen a disagreement-router branch.",
        },
    )


if __name__ == "__main__":
    main()
