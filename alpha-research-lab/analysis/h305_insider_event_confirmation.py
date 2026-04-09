"""
H305: insider-event confirmation audit.

Question:
    Does the C5 insider relative-size signal become materially stronger when it
    confirms fresh company-event windows, or is the broad event-conditioning
    story still too weak to justify another sparse timing branch?
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

from src.research_protocol import ResearchProtocol, phase_mask
from src.run_summary import write_run_summary


BARRIER_PATH = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
INSIDER_PATH = data_path("features/xs_insider_quality_features.parquet")
EVENT_V1_PATH = data_path("features/event_surface_daily.parquet")
H301_SUMMARY_PATH = ROOT / "artifacts" / "run_summaries" / "latest_research_branch_cafef_event_surface_v2_pilot.json"
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"

PROTOCOL = ResearchProtocol(
    dev_start_year=2023,
    dev_end_year=2023,
    validation_start_year=2024,
    validation_end_year=2024,
    confirmation_year=2025,
    forward_start_year=2026,
)

PASS_MIN_VALIDATION_ROWS = 100
PASS_MIN_CONFIRMATION_ROWS = 60
PASS_VALIDATION_IC_UPLIFT = 0.005
PASS_CONFIRMATION_IC_UPLIFT = 0.005
MIXED_MIN_VALIDATION_ROWS = 50
MIXED_MIN_CONFIRMATION_ROWS = 50

MASK_SPECS = (
    ("c5_all", "Standalone C5 fire rows"),
    ("v1_recent_any_filing_5d", "C5 inside v1 recent filing 5d"),
    ("v1_corporate_action_window", "C5 inside v1 corporate-action window"),
    ("v2_recent_company_event_article_v2_5d", "C5 inside v2 recent company event 5d"),
    ("v2_earnings_company_5d", "C5 inside v2 earnings-company 5d"),
    ("v2_rights_issuance_5d", "C5 inside v2 rights / issuance 5d"),
    ("v2_board_management_5d", "C5 inside v2 board / management 5d"),
)

MASK_COMPLEMENTS = {
    "v1_recent_any_filing_5d": "v1_no_recent_any_filing_5d",
    "v1_corporate_action_window": "v1_no_corporate_action_window",
    "v2_recent_company_event_article_v2_5d": "v2_no_recent_company_event_article_v2_5d",
    "v2_earnings_company_5d": "v2_no_earnings_company_5d",
    "v2_rights_issuance_5d": "v2_no_rights_issuance_5d",
    "v2_board_management_5d": "v2_no_board_management_5d",
}


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


def _load_h301_pilot_surface_path() -> Path:
    payload = json.loads(H301_SUMMARY_PATH.read_text(encoding="utf-8"))
    ref = payload["artifacts"]["pilot_surface"]
    return ROOT / ref


def load_panel() -> pd.DataFrame:
    barrier = pd.read_parquet(BARRIER_PATH, columns=["time", "ticker", "actual"]).copy()
    insider = pd.read_parquet(
        INSIDER_PATH,
        columns=["trading_day", "ticker", "xs_ins_relative_size_5d"],
    ).rename(columns={"trading_day": "time"})
    event_v1 = pd.read_parquet(
        EVENT_V1_PATH,
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
    event_v2 = pd.read_parquet(
        _load_h301_pilot_surface_path(),
        columns=[
            "time",
            "ticker",
            "recent_company_event_article_v2_5d",
            "event_recent5__earnings_company",
            "event_recent5__rights_issuance",
            "event_recent5__board_management",
        ],
    ).copy()

    for frame in (barrier, insider, event_v1, event_v2):
        frame["time"] = pd.to_datetime(frame["time"], errors="coerce").dt.normalize()

    barrier = barrier.loc[barrier["time"].dt.year.between(2023, 2025)].copy()
    insider = insider.loc[insider["time"].dt.year.between(2023, 2025)].copy()
    event_v1 = event_v1.loc[event_v1["time"].dt.year.between(2023, 2025)].copy()
    event_v2 = event_v2.loc[event_v2["time"].dt.year.between(2023, 2025)].copy()

    panel = barrier.merge(insider, on=["time", "ticker"], how="left", validate="one_to_one")
    panel = panel.merge(event_v1, on=["time", "ticker"], how="left", validate="one_to_one")
    panel = panel.merge(event_v2, on=["time", "ticker"], how="left", validate="one_to_one")

    numeric_cols = [
        "xs_ins_relative_size_5d",
        "recent_any_filing_5d",
        "dividend_window_pre_20d",
        "dividend_window_post_5d",
        "issuance_window_pre_20d",
        "issuance_window_post_5d",
        "recent_company_event_article_v2_5d",
        "event_recent5__earnings_company",
        "event_recent5__rights_issuance",
        "event_recent5__board_management",
    ]
    for column in numeric_cols:
        panel[column] = pd.to_numeric(panel[column], errors="coerce").fillna(0.0)

    panel["c5_nonzero"] = panel["xs_ins_relative_size_5d"] != 0.0
    panel["v1_recent_any_filing_5d"] = panel["c5_nonzero"] & (panel["recent_any_filing_5d"] > 0.0)
    panel["v1_corporate_action_window"] = panel["c5_nonzero"] & (
        (panel["dividend_window_pre_20d"] > 0.0)
        | (panel["dividend_window_post_5d"] > 0.0)
        | (panel["issuance_window_pre_20d"] > 0.0)
        | (panel["issuance_window_post_5d"] > 0.0)
    )
    panel["v2_recent_company_event_article_v2_5d"] = panel["c5_nonzero"] & (
        panel["recent_company_event_article_v2_5d"] > 0.0
    )
    panel["v2_earnings_company_5d"] = panel["c5_nonzero"] & (
        panel["event_recent5__earnings_company"] > 0.0
    )
    panel["v2_rights_issuance_5d"] = panel["c5_nonzero"] & (
        panel["event_recent5__rights_issuance"] > 0.0
    )
    panel["v2_board_management_5d"] = panel["c5_nonzero"] & (
        panel["event_recent5__board_management"] > 0.0
    )
    panel["c5_all"] = panel["c5_nonzero"]

    for mask_name in list(MASK_COMPLEMENTS.values()):
        panel[mask_name] = False
    panel["v1_no_recent_any_filing_5d"] = panel["c5_nonzero"] & ~panel["v1_recent_any_filing_5d"]
    panel["v1_no_corporate_action_window"] = panel["c5_nonzero"] & ~panel["v1_corporate_action_window"]
    panel["v2_no_recent_company_event_article_v2_5d"] = panel["c5_nonzero"] & ~panel["v2_recent_company_event_article_v2_5d"]
    panel["v2_no_earnings_company_5d"] = panel["c5_nonzero"] & ~panel["v2_earnings_company_5d"]
    panel["v2_no_rights_issuance_5d"] = panel["c5_nonzero"] & ~panel["v2_rights_issuance_5d"]
    panel["v2_no_board_management_5d"] = panel["c5_nonzero"] & ~panel["v2_board_management_5d"]
    return panel


def _pooled_spearman(df: pd.DataFrame, *, score_col: str, target_col: str) -> float | None:
    clean = df[[score_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < 30 or clean[score_col].nunique() < 3 or clean[target_col].nunique() < 2:
        return None
    stat = spearmanr(clean[score_col], clean[target_col]).statistic
    if not np.isfinite(stat):
        return None
    return float(np.asarray(stat).flat[0])


def _quintile_spread(df: pd.DataFrame, *, score_col: str, target_col: str) -> dict[str, object]:
    clean = df[[score_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < 30 or clean[score_col].nunique() < 5:
        return {"q5_minus_q1": None, "top_mean": None, "bottom_mean": None}
    ranked = clean.assign(
        quintile=pd.qcut(
            clean[score_col].rank(method="first"),
            q=5,
            labels=False,
            duplicates="drop",
        )
    )
    if ranked["quintile"].nunique() < 2:
        return {"q5_minus_q1": None, "top_mean": None, "bottom_mean": None}
    top_mean = float(ranked.loc[ranked["quintile"] == ranked["quintile"].max(), target_col].mean())
    bottom_mean = float(ranked.loc[ranked["quintile"] == ranked["quintile"].min(), target_col].mean())
    return {
        "q5_minus_q1": float(top_mean - bottom_mean),
        "top_mean": top_mean,
        "bottom_mean": bottom_mean,
    }


def _phase_summary(frame: pd.DataFrame, *, mask_col: str, phase: str) -> dict[str, object]:
    scoped = frame.loc[phase_mask(frame, phase, protocol=PROTOCOL)].copy()
    scoped = scoped.loc[scoped[mask_col].fillna(False).astype(bool)].copy()
    spread = _quintile_spread(scoped, score_col="xs_ins_relative_size_5d", target_col="actual")
    return {
        "rows": int(len(scoped)),
        "dates": int(scoped["time"].nunique()) if not scoped.empty else 0,
        "tickers": int(scoped["ticker"].nunique()) if not scoped.empty else 0,
        "pooled_ic": _pooled_spearman(scoped, score_col="xs_ins_relative_size_5d", target_col="actual"),
        **spread,
    }


def _decision_row(frame: pd.DataFrame, *, mask_name: str, mask_note: str) -> dict[str, object]:
    phase_rows = {
        phase: _phase_summary(frame, mask_col=mask_name, phase=phase)
        for phase in ("dev", "validation", "confirmation")
    }
    baseline_rows = {
        phase: _phase_summary(frame, mask_col="c5_all", phase=phase)
        for phase in ("dev", "validation", "confirmation")
    }
    complement_name = MASK_COMPLEMENTS.get(mask_name)
    complement_rows = {
        phase: _phase_summary(frame, mask_col=complement_name, phase=phase)
        for phase in ("dev", "validation", "confirmation")
    } if complement_name else {}

    row = {
        "mask_name": mask_name,
        "mask_note": mask_note,
        "complement_name": complement_name,
    }
    for phase in ("dev", "validation", "confirmation"):
        current = phase_rows[phase]
        baseline = baseline_rows[phase]
        complement = complement_rows.get(phase, {})
        for key, value in current.items():
            row[f"{phase}_{key}"] = value
        row[f"{phase}_ic_uplift_vs_baseline"] = (
            (_safe_float(current.get("pooled_ic")) or 0.0) - (_safe_float(baseline.get("pooled_ic")) or 0.0)
        )
        row[f"{phase}_qspread_uplift_vs_baseline"] = (
            (_safe_float(current.get("q5_minus_q1")) or 0.0) - (_safe_float(baseline.get("q5_minus_q1")) or 0.0)
        )
        if complement_name:
            row[f"{phase}_ic_uplift_vs_complement"] = (
                (_safe_float(current.get("pooled_ic")) or 0.0) - (_safe_float(complement.get("pooled_ic")) or 0.0)
            )
            row[f"{phase}_complement_rows"] = complement.get("rows")
        else:
            row[f"{phase}_ic_uplift_vs_complement"] = None
            row[f"{phase}_complement_rows"] = None

    if mask_name == "c5_all":
        row["candidate_decision"] = "BASELINE"
        return row

    pass_condition = bool(
        int(pd.to_numeric(row.get("validation_rows"), errors="coerce") or 0) >= PASS_MIN_VALIDATION_ROWS
        and int(pd.to_numeric(row.get("confirmation_rows"), errors="coerce") or 0) >= PASS_MIN_CONFIRMATION_ROWS
        and (_safe_float(row.get("validation_pooled_ic")) or -np.inf) > 0.0
        and (_safe_float(row.get("confirmation_pooled_ic")) or -np.inf) > 0.0
        and (_safe_float(row.get("validation_ic_uplift_vs_baseline")) or -np.inf) >= PASS_VALIDATION_IC_UPLIFT
        and (_safe_float(row.get("confirmation_ic_uplift_vs_baseline")) or -np.inf) >= PASS_CONFIRMATION_IC_UPLIFT
        and (_safe_float(row.get("validation_q5_minus_q1")) or -np.inf) > 0.0
        and (_safe_float(row.get("confirmation_q5_minus_q1")) or -np.inf) > 0.0
    )
    mixed_condition = bool(
        not pass_condition
        and int(pd.to_numeric(row.get("validation_rows"), errors="coerce") or 0) >= MIXED_MIN_VALIDATION_ROWS
        and int(pd.to_numeric(row.get("confirmation_rows"), errors="coerce") or 0) >= MIXED_MIN_CONFIRMATION_ROWS
        and (_safe_float(row.get("dev_pooled_ic")) or -np.inf) > 0.0
        and (_safe_float(row.get("validation_pooled_ic")) or -np.inf) > 0.0
        and (_safe_float(row.get("confirmation_pooled_ic")) or -np.inf) > 0.0
        and (
            (_safe_float(row.get("validation_ic_uplift_vs_baseline")) or -np.inf) > 0.0
            or (_safe_float(row.get("confirmation_ic_uplift_vs_baseline")) or -np.inf) > 0.0
            or (_safe_float(row.get("confirmation_ic_uplift_vs_complement")) or -np.inf) > 0.0
        )
    )
    row["candidate_decision"] = "PASSED" if pass_condition else "MIXED" if mixed_condition else "FAILED"
    return row


def _sort_results(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return results.copy()
    work = results.copy()
    for column in (
        "validation_pooled_ic",
        "confirmation_pooled_ic",
        "validation_ic_uplift_vs_baseline",
        "confirmation_ic_uplift_vs_baseline",
        "validation_q5_minus_q1",
        "confirmation_q5_minus_q1",
    ):
        work[column] = pd.to_numeric(work[column], errors="coerce")
    rank_map = {"PASSED": 3, "MIXED": 2, "FAILED": 1, "BASELINE": 0}
    work["_decision_rank"] = work["candidate_decision"].map(rank_map).fillna(0)
    return work.sort_values(
        by=[
            "_decision_rank",
            "confirmation_ic_uplift_vs_baseline",
            "validation_ic_uplift_vs_baseline",
            "confirmation_pooled_ic",
            "validation_pooled_ic",
            "confirmation_rows",
            "mask_name",
        ],
        ascending=[False, False, False, False, False, False, True],
        ignore_index=True,
    ).drop(columns="_decision_rank")


def main() -> None:
    panel = load_panel()
    results = pd.DataFrame(
        [_decision_row(panel, mask_name=mask_name, mask_note=mask_note) for mask_name, mask_note in MASK_SPECS]
    )
    results = _sort_results(results)

    pass_rows = results.loc[results["candidate_decision"] == "PASSED"].copy()
    mixed_rows = results.loc[results["candidate_decision"] == "MIXED"].copy()
    decision = "PASSED" if not pass_rows.empty else "MIXED" if not mixed_rows.empty else "FAILED"
    best_candidate = (
        results.loc[results["candidate_decision"] != "BASELINE"].iloc[0].to_dict()
        if not results.loc[results["candidate_decision"] != "BASELINE"].empty
        else {}
    )
    baseline_row = results.loc[results["mask_name"] == "c5_all"].iloc[0].to_dict()

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    artifact_stem = f"{ts}_h305_insider_event_confirmation"
    results_path = OUT_DIR / f"{artifact_stem}_results.parquet"
    details_path = ROOT / "artifacts" / "run_summaries" / f"{artifact_stem}_details.json"

    results.to_parquet(results_path, index=False)

    summary = {
        "decision": decision,
        "protocol": PROTOCOL.describe(),
        "baseline_row": baseline_row,
        "best_candidate": best_candidate,
        "pass_candidate_count": int(len(pass_rows)),
        "mixed_candidate_count": int(len(mixed_rows)),
        "branch_decision": {
            "PASSED": "At least one fresh company-event window materially sharpens C5 enough to justify a narrower conditioned-insider follow-through.",
            "MIXED": "Broad event confirmation does not rescue C5 cleanly, but one narrow event pocket shows enough local support to preserve a bounded sparse-state follow-up.",
            "FAILED": "Fresh company-event windows do not materially sharpen C5 on the current 2023-2025 contract; keep insider and event timing separate for now.",
        }[decision],
    }
    details_payload = {
        "summary": summary,
        "results": results.to_dict(orient="records"),
        "pass_rows": pass_rows.to_dict(orient="records"),
        "mixed_rows": mixed_rows.to_dict(orient="records"),
        "thresholds": {
            "pass_min_validation_rows": PASS_MIN_VALIDATION_ROWS,
            "pass_min_confirmation_rows": PASS_MIN_CONFIRMATION_ROWS,
            "pass_validation_ic_uplift": PASS_VALIDATION_IC_UPLIFT,
            "pass_confirmation_ic_uplift": PASS_CONFIRMATION_IC_UPLIFT,
            "mixed_min_validation_rows": MIXED_MIN_VALIDATION_ROWS,
            "mixed_min_confirmation_rows": MIXED_MIN_CONFIRMATION_ROWS,
        },
    }
    details_path.write_text(json.dumps(_json_safe(details_payload), indent=2) + "\n", encoding="utf-8")

    write_run_summary(
        ts=ts,
        mode="research_branch_insider_event_confirmation",
        name="h305_insider_event_confirmation",
        summary=summary,
        artifacts={
            "results": results_path,
            "details": details_path,
        },
        metadata={
            "session": 131,
            "protocol": PROTOCOL.describe(),
            "branch_contract": "H305 is a pooled sparse-row 2023-2025 audit on C5 fire rows versus event-v1/v2 windows; no live-branch change.",
        },
    )

    print("H305 insider-event confirmation audit")
    print(json.dumps(_json_safe(summary), indent=2))


if __name__ == "__main__":
    main()
