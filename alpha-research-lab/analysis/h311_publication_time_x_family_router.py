"""
H311: publication-time x family router audit.

Question:
    Does exact publication time interact with event family strongly enough to
    create a usable same-day router on the richer H310/H309 event surface?
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

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

FAMILIES = ("earnings_company", "rights_issuance", "board_management", "shareholder_meeting")
REFERENCE_BUCKET = "intraday"
COMPARE_BUCKETS = ("pre_open", "post_close")
PASS_MIN_ROWS = 20
PASS_ACTUAL_UPLIFT = 0.01
PASS_FWD5_UPLIFT = 0.02
MIXED_MIN_ROWS = 12


def _safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _load_first_public_path() -> Path:
    return resolve_summary_artifact(H310_SUMMARY_PATH, "combined_first_public")


def _publication_bucket(ts: pd.Timestamp) -> str | None:
    if pd.isna(ts):
        return None
    hour = int(ts.hour)
    minute = int(ts.minute)
    total_minutes = hour * 60 + minute
    if total_minutes < 9 * 60:
        return "pre_open"
    if total_minutes < 14 * 60 + 30:
        return "intraday"
    return "post_close"


def load_panel() -> pd.DataFrame:
    first_public = pd.read_parquet(
        _load_first_public_path(),
        columns=["time", "ticker", "event_family", "first_published_at", "article_count_1d"],
    ).copy()
    first_public["time"] = pd.to_datetime(first_public["time"], errors="coerce").dt.normalize()
    first_public["first_published_at"] = pd.to_datetime(first_public["first_published_at"], errors="coerce")
    first_public = first_public.loc[
        first_public["time"].dt.year.between(2023, 2025) & first_public["event_family"].isin(FAMILIES)
    ].copy()
    first_public["publication_bucket"] = first_public["first_published_at"].map(_publication_bucket)
    first_public = first_public.dropna(subset=["publication_bucket"]).copy()

    actual = pd.read_parquet(S1_PATH, columns=["time", "ticker", "actual"]).copy()
    actual["time"] = pd.to_datetime(actual["time"], errors="coerce").dt.normalize()
    actual = actual.loc[actual["time"].dt.year.between(2023, 2025)].copy()

    future5 = load_future_rel_5d(start_year=2023, end_year=2025).copy()
    panel = first_public.merge(actual, on=["time", "ticker"], how="left", validate="many_to_one")
    panel = panel.merge(future5, on=["time", "ticker"], how="left", validate="many_to_one")
    return panel.dropna(subset=["actual", "fwd_rel_5d"]).reset_index(drop=True)


def _phase_bucket_summary(frame: pd.DataFrame, *, phase: str, family: str, bucket: str) -> dict[str, object]:
    scoped = frame.loc[
        phase_mask(frame, phase, protocol=PROTOCOL)
        & frame["event_family"].eq(family)
        & frame["publication_bucket"].eq(bucket)
    ].copy()
    return {
        "rows": int(len(scoped)),
        "dates": int(scoped["time"].nunique()) if not scoped.empty else 0,
        "actual_mean": _safe_float(scoped["actual"].mean()) if not scoped.empty else None,
        "fwd5_mean": _safe_float(scoped["fwd_rel_5d"].mean()) if not scoped.empty else None,
    }


def evaluate(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for family in FAMILIES:
        reference = {
            phase: _phase_bucket_summary(panel, phase=phase, family=family, bucket=REFERENCE_BUCKET)
            for phase in ("dev", "validation", "confirmation")
        }
        for bucket in COMPARE_BUCKETS:
            row = {"event_family": family, "bucket": bucket, "reference_bucket": REFERENCE_BUCKET}
            for phase in ("dev", "validation", "confirmation"):
                summary = _phase_bucket_summary(panel, phase=phase, family=family, bucket=bucket)
                for key, value in summary.items():
                    row[f"{phase}_{key}"] = value
                row[f"{phase}_actual_uplift_vs_intraday"] = (
                    (_safe_float(summary.get("actual_mean")) or 0.0)
                    - (_safe_float(reference[phase].get("actual_mean")) or 0.0)
                )
                row[f"{phase}_fwd5_uplift_vs_intraday"] = (
                    (_safe_float(summary.get("fwd5_mean")) or 0.0)
                    - (_safe_float(reference[phase].get("fwd5_mean")) or 0.0)
                )
                row[f"{phase}_intraday_rows"] = reference[phase].get("rows")
            pass_condition = bool(
                int(pd.to_numeric(row.get("validation_rows"), errors="coerce") or 0) >= PASS_MIN_ROWS
                and int(pd.to_numeric(row.get("confirmation_rows"), errors="coerce") or 0) >= PASS_MIN_ROWS
                and int(pd.to_numeric(row.get("validation_intraday_rows"), errors="coerce") or 0) >= PASS_MIN_ROWS
                and int(pd.to_numeric(row.get("confirmation_intraday_rows"), errors="coerce") or 0) >= PASS_MIN_ROWS
                and (_safe_float(row.get("validation_actual_uplift_vs_intraday")) or -np.inf) >= PASS_ACTUAL_UPLIFT
                and (_safe_float(row.get("confirmation_actual_uplift_vs_intraday")) or -np.inf) >= 0.0
                and (_safe_float(row.get("validation_fwd5_uplift_vs_intraday")) or -np.inf) >= PASS_FWD5_UPLIFT
                and (_safe_float(row.get("confirmation_fwd5_uplift_vs_intraday")) or -np.inf) >= 0.0
            )
            mixed_condition = bool(
                not pass_condition
                and int(pd.to_numeric(row.get("validation_rows"), errors="coerce") or 0) >= MIXED_MIN_ROWS
                and int(pd.to_numeric(row.get("confirmation_rows"), errors="coerce") or 0) >= MIXED_MIN_ROWS
                and (
                    (_safe_float(row.get("validation_actual_uplift_vs_intraday")) or -np.inf) > 0.0
                    or (_safe_float(row.get("validation_fwd5_uplift_vs_intraday")) or -np.inf) > 0.0
                    or (_safe_float(row.get("confirmation_actual_uplift_vs_intraday")) or -np.inf) > 0.0
                    or (_safe_float(row.get("confirmation_fwd5_uplift_vs_intraday")) or -np.inf) > 0.0
                )
            )
            row["candidate_decision"] = "PASSED" if pass_condition else "MIXED" if mixed_condition else "FAILED"
            rows.append(row)
    results = pd.DataFrame(rows)
    return results.sort_values(
        ["candidate_decision", "validation_fwd5_uplift_vs_intraday", "confirmation_fwd5_uplift_vs_intraday"],
        ascending=[True, False, False],
        ignore_index=True,
    )


def main() -> None:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    panel = load_panel()
    results = evaluate(panel)
    results_path = OUT_DIR / f"{ts}_h311_publication_time_x_family_router_results.parquet"
    panel_path = OUT_DIR / f"{ts}_h311_publication_time_x_family_router_panel.parquet"
    results.to_parquet(results_path, index=False)
    panel.to_parquet(panel_path, index=False)

    best_row = results.iloc[0].to_dict() if not results.empty else {}
    if not results.empty and (results["candidate_decision"] == "PASSED").any():
        decision = "PASSED"
        branch_decision = "Publication time and event family jointly create a stable same-day router on the richer H310/H309 surface."
    elif not results.empty and (results["candidate_decision"] == "MIXED").any():
        decision = "MIXED"
        branch_decision = "Publication time matters for some families, but the bucket effects are too local or unstable to call a broad router yet."
    else:
        decision = "FAILED"
        branch_decision = "Exact publication time does not add a stable family-specific routing effect on the current H310/H309 event surface."

    details = {
        "results": results.to_dict(orient="records"),
        "best_row": best_row,
        "families_tested": list(FAMILIES),
        "panel_rows": int(len(panel)),
    }
    details_path = DETAILS_DIR / f"{ts}_h311_publication_time_x_family_router_details.json"
    details_path.write_text(json.dumps(details, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    summary = {
        "decision": decision,
        "branch_decision": branch_decision,
        "panel_rows": int(len(panel)),
        "families_tested": list(FAMILIES),
        "best_candidate": {
            "event_family": best_row.get("event_family"),
            "bucket": best_row.get("bucket"),
            "candidate_decision": best_row.get("candidate_decision"),
            "validation_rows": best_row.get("validation_rows"),
            "confirmation_rows": best_row.get("confirmation_rows"),
            "validation_actual_uplift_vs_intraday": best_row.get("validation_actual_uplift_vs_intraday"),
            "confirmation_actual_uplift_vs_intraday": best_row.get("confirmation_actual_uplift_vs_intraday"),
            "validation_fwd5_uplift_vs_intraday": best_row.get("validation_fwd5_uplift_vs_intraday"),
            "confirmation_fwd5_uplift_vs_intraday": best_row.get("confirmation_fwd5_uplift_vs_intraday"),
        },
    }
    write_run_summary(
        ts=ts,
        mode="research_branch_publication_time_x_family_router",
        name="h311_publication_time_x_family_router",
        summary=summary,
        artifacts={"results": results_path, "panel": panel_path, "details": details_path},
        metadata={
            "session": 136,
            "branch_contract": "Only a stable family-specific publication-time advantage over intraday references can reopen an event publication router branch.",
        },
    )


if __name__ == "__main__":
    main()
