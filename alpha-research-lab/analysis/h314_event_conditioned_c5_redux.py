"""
H314: event-conditioned C5 redux.

Question:
    Does the richer H310/H309 event surface rescue any honest family-specific
    insider confirmation state that H305 could not validate under the thinner
    H301 contract?
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
from src.research_protocol import ResearchProtocol, phase_mask
from src.run_summary import write_run_summary


BARRIER_PATH = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
INSIDER_PATH = data_path("features/xs_insider_quality_features.parquet")
H310_SUMMARY_PATH = ROOT / "artifacts" / "run_summaries" / "latest_research_branch_event_v2_predictive_rescreen.json"
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"

PROTOCOL = ResearchProtocol(
    dev_start_year=2023,
    dev_end_year=2023,
    validation_start_year=2024,
    validation_end_year=2024,
    confirmation_year=2025,
    forward_start_year=2026,
)

PASS_MIN_VALIDATION_ROWS = 80
PASS_MIN_CONFIRMATION_ROWS = 50
PASS_VALIDATION_IC_UPLIFT = 0.005
PASS_CONFIRMATION_IC_UPLIFT = 0.005
MIXED_MIN_VALIDATION_ROWS = 40
MIXED_MIN_CONFIRMATION_ROWS = 30

MASK_SPECS = (
    ("c5_all", "Standalone C5 fire rows"),
    ("v2_recent_any_5d", "C5 inside H310 recent any-event 5d"),
    ("v2_same_day_any", "C5 inside H310 same-day any-event"),
    ("v2_recent_earnings_5d", "C5 inside H310 recent earnings 5d"),
    ("v2_same_day_earnings", "C5 inside H310 same-day earnings"),
    ("v2_recent_rights_5d", "C5 inside H310 recent rights / issuance 5d"),
    ("v2_same_day_rights", "C5 inside H310 same-day rights / issuance"),
    ("v2_recent_board_5d", "C5 inside H310 recent board / management 5d"),
    ("v2_same_day_board", "C5 inside H310 same-day board / management"),
)

MASK_COMPLEMENTS = {
    "v2_recent_any_5d": "v2_no_recent_any_5d",
    "v2_same_day_any": "v2_no_same_day_any",
    "v2_recent_earnings_5d": "v2_no_recent_earnings_5d",
    "v2_same_day_earnings": "v2_no_same_day_earnings",
    "v2_recent_rights_5d": "v2_no_recent_rights_5d",
    "v2_same_day_rights": "v2_no_same_day_rights",
    "v2_recent_board_5d": "v2_no_recent_board_5d",
    "v2_same_day_board": "v2_no_same_day_board",
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


def _load_pilot_surface_path() -> Path:
    return resolve_summary_artifact(H310_SUMMARY_PATH, "combined_pilot_surface")


def load_panel() -> pd.DataFrame:
    barrier = pd.read_parquet(BARRIER_PATH, columns=["time", "ticker", "actual"]).copy()
    insider = pd.read_parquet(
        INSIDER_PATH,
        columns=["trading_day", "ticker", "xs_ins_relative_size_5d"],
    ).rename(columns={"trading_day": "time"})
    event_v2 = pd.read_parquet(
        _load_pilot_surface_path(),
        columns=[
            "time",
            "ticker",
            "recent_company_event_article_v2_5d",
            "has_company_event_article_v2",
            "event_recent5__earnings_company",
            "event_flag__earnings_company",
            "event_recent5__rights_issuance",
            "event_flag__rights_issuance",
            "event_recent5__board_management",
            "event_flag__board_management",
        ],
    ).copy()

    for frame in (barrier, insider, event_v2):
        frame["time"] = pd.to_datetime(frame["time"], errors="coerce").dt.normalize()

    barrier = barrier.loc[barrier["time"].dt.year.between(2023, 2025)].copy()
    insider = insider.loc[insider["time"].dt.year.between(2023, 2025)].copy()
    event_v2 = event_v2.loc[event_v2["time"].dt.year.between(2023, 2025)].copy()

    panel = barrier.merge(insider, on=["time", "ticker"], how="left", validate="one_to_one")
    panel = panel.merge(event_v2, on=["time", "ticker"], how="left", validate="one_to_one")

    numeric_cols = [
        "xs_ins_relative_size_5d",
        "recent_company_event_article_v2_5d",
        "has_company_event_article_v2",
        "event_recent5__earnings_company",
        "event_flag__earnings_company",
        "event_recent5__rights_issuance",
        "event_flag__rights_issuance",
        "event_recent5__board_management",
        "event_flag__board_management",
    ]
    for column in numeric_cols:
        panel[column] = pd.to_numeric(panel[column], errors="coerce").fillna(0.0)

    panel["c5_nonzero"] = panel["xs_ins_relative_size_5d"] != 0.0
    panel["c5_all"] = panel["c5_nonzero"]
    panel["v2_recent_any_5d"] = panel["c5_nonzero"] & (panel["recent_company_event_article_v2_5d"] > 0.0)
    panel["v2_same_day_any"] = panel["c5_nonzero"] & (panel["has_company_event_article_v2"] > 0.0)
    panel["v2_recent_earnings_5d"] = panel["c5_nonzero"] & (panel["event_recent5__earnings_company"] > 0.0)
    panel["v2_same_day_earnings"] = panel["c5_nonzero"] & (panel["event_flag__earnings_company"] > 0.0)
    panel["v2_recent_rights_5d"] = panel["c5_nonzero"] & (panel["event_recent5__rights_issuance"] > 0.0)
    panel["v2_same_day_rights"] = panel["c5_nonzero"] & (panel["event_flag__rights_issuance"] > 0.0)
    panel["v2_recent_board_5d"] = panel["c5_nonzero"] & (panel["event_recent5__board_management"] > 0.0)
    panel["v2_same_day_board"] = panel["c5_nonzero"] & (panel["event_flag__board_management"] > 0.0)

    for mask_name in MASK_COMPLEMENTS.values():
        panel[mask_name] = False
    panel["v2_no_recent_any_5d"] = panel["c5_nonzero"] & ~panel["v2_recent_any_5d"]
    panel["v2_no_same_day_any"] = panel["c5_nonzero"] & ~panel["v2_same_day_any"]
    panel["v2_no_recent_earnings_5d"] = panel["c5_nonzero"] & ~panel["v2_recent_earnings_5d"]
    panel["v2_no_same_day_earnings"] = panel["c5_nonzero"] & ~panel["v2_same_day_earnings"]
    panel["v2_no_recent_rights_5d"] = panel["c5_nonzero"] & ~panel["v2_recent_rights_5d"]
    panel["v2_no_same_day_rights"] = panel["c5_nonzero"] & ~panel["v2_same_day_rights"]
    panel["v2_no_recent_board_5d"] = panel["c5_nonzero"] & ~panel["v2_recent_board_5d"]
    panel["v2_no_same_day_board"] = panel["c5_nonzero"] & ~panel["v2_same_day_board"]
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
    return {"q5_minus_q1": float(top_mean - bottom_mean), "top_mean": top_mean, "bottom_mean": bottom_mean}


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
    phase_rows = {phase: _phase_summary(frame, mask_col=mask_name, phase=phase) for phase in ("dev", "validation", "confirmation")}
    baseline_rows = {phase: _phase_summary(frame, mask_col="c5_all", phase=phase) for phase in ("dev", "validation", "confirmation")}
    complement_name = MASK_COMPLEMENTS.get(mask_name)
    complement_rows = {phase: _phase_summary(frame, mask_col=complement_name, phase=phase) for phase in ("dev", "validation", "confirmation")} if complement_name else {}

    row = {"mask_name": mask_name, "mask_note": mask_note, "complement_name": complement_name}
    for phase in ("dev", "validation", "confirmation"):
        current = phase_rows[phase]
        baseline = baseline_rows[phase]
        complement = complement_rows.get(phase, {})
        for key, value in current.items():
            row[f"{phase}_{key}"] = value
        row[f"{phase}_ic_uplift_vs_baseline"] = ((_safe_float(current.get("pooled_ic")) or 0.0) - (_safe_float(baseline.get("pooled_ic")) or 0.0))
        row[f"{phase}_qspread_uplift_vs_baseline"] = ((_safe_float(current.get("q5_minus_q1")) or 0.0) - (_safe_float(baseline.get("q5_minus_q1")) or 0.0))
        row[f"{phase}_ic_uplift_vs_complement"] = ((_safe_float(current.get("pooled_ic")) or 0.0) - (_safe_float(complement.get("pooled_ic")) or 0.0)) if complement_name else None
        row[f"{phase}_complement_rows"] = complement.get("rows") if complement_name else None

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


def evaluate(panel: pd.DataFrame) -> pd.DataFrame:
    rows = [_decision_row(panel, mask_name=mask_name, mask_note=mask_note) for mask_name, mask_note in MASK_SPECS]
    results = pd.DataFrame(rows)
    for column in ("validation_pooled_ic", "confirmation_pooled_ic", "validation_ic_uplift_vs_baseline", "confirmation_ic_uplift_vs_baseline"):
        results[column] = pd.to_numeric(results[column], errors="coerce")
    return results.sort_values(
        by=["candidate_decision", "validation_pooled_ic", "confirmation_pooled_ic", "validation_ic_uplift_vs_baseline", "confirmation_ic_uplift_vs_baseline"],
        ascending=[True, False, False, False, False],
        ignore_index=True,
    )


def main() -> None:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    panel = load_panel()
    results = evaluate(panel)
    results_path = OUT_DIR / f"{ts}_h314_event_conditioned_c5_redux_results.parquet"
    results.to_parquet(results_path, index=False)

    best_candidate = results.loc[~results["mask_name"].eq("c5_all")].iloc[0].to_dict()
    if (results["candidate_decision"] == "PASSED").any():
        decision = "PASSED"
        branch_decision = "The richer H310/H309 event surface rescues at least one honest insider-event confirmation state."
    elif (results["candidate_decision"] == "MIXED").any():
        decision = "MIXED"
        branch_decision = "The richer event surface improves some insider pockets, but no broad conditioned C5 branch is promotable yet."
    else:
        decision = "FAILED"
        branch_decision = "Even the richer H310/H309 event surface does not rescue an honest event-conditioned C5 branch."

    details = {
        "results": results.to_dict(orient="records"),
        "best_candidate": best_candidate,
        "panel_rows": int(len(panel)),
        "c5_nonzero_rows": int(panel["c5_nonzero"].sum()),
    }
    details_path = ROOT / "artifacts" / "run_summaries" / f"{ts}_h314_event_conditioned_c5_redux_details.json"
    details_path.write_text(json.dumps(_json_safe(details), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    summary = {
        "decision": decision,
        "branch_decision": branch_decision,
        "panel_rows": int(len(panel)),
        "c5_nonzero_rows": int(panel["c5_nonzero"].sum()),
        "best_candidate": {
            "mask_name": best_candidate.get("mask_name"),
            "candidate_decision": best_candidate.get("candidate_decision"),
            "validation_rows": best_candidate.get("validation_rows"),
            "confirmation_rows": best_candidate.get("confirmation_rows"),
            "validation_pooled_ic": best_candidate.get("validation_pooled_ic"),
            "confirmation_pooled_ic": best_candidate.get("confirmation_pooled_ic"),
            "validation_ic_uplift_vs_baseline": best_candidate.get("validation_ic_uplift_vs_baseline"),
            "confirmation_ic_uplift_vs_baseline": best_candidate.get("confirmation_ic_uplift_vs_baseline"),
        },
    }
    write_run_summary(
        ts=ts,
        mode="research_branch_event_conditioned_c5_redux",
        name="h314_event_conditioned_c5_redux",
        summary=summary,
        artifacts={"results": results_path, "details": details_path},
        metadata={
            "session": 136,
            "branch_contract": "Only a richer H310/H309 family-specific or same-day event state that beats baseline C5 in validation and confirmation can reopen the insider-event branch.",
        },
    )


if __name__ == "__main__":
    main()
