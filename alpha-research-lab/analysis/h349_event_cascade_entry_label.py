"""
H349: event-cascade entry-label audit.

Question:
    Did H321/H322 fail additive promotion because the cascade state is an
    entry-opportunity state rather than a full-universe rank boost?

Design:
    - reuse the saved H321 cascade panel; do not refit cascade thresholds
    - join only existing entry-alpha candidate, label, and score artifacts
    - use the source-limited H321 window:
        2023 dev, 2024 validation, 2025 confirmation, 2026 excluded
    - test whether today_self_accel_high improves entry labels and cycle
      returns after matching against the existing entry prior
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

from src.additive_selector_research import resolve_summary_artifact  # noqa: E402
from src.research_protocol import ResearchProtocol, phase_mask  # noqa: E402
from src.run_summary import write_run_summary  # noqa: E402


H321_SUMMARY_PATH = ROOT / "artifacts" / "run_summaries" / "latest_research_branch_hawkes_disclosure_cascade.json"
CANDIDATE_PANEL_PATH = data_path("features/entry_alpha/candidate_panel_daily.parquet")
ENTRY_LABELS_PATH = data_path("features/entry_alpha/entry_labels_cycle5.parquet")
ENTRY_SCORES_PATH = data_path("features/entry_alpha/entry_scores_daily.parquet")
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"

PROTOCOL = ResearchProtocol(
    dev_start_year=2023,
    dev_end_year=2023,
    validation_start_year=2024,
    validation_end_year=2024,
    confirmation_year=2025,
    forward_start_year=2026,
)

STATE_SPECS = (
    ("today_self_accel_high", "H321 same-day self-excitation acceleration", "candidate"),
    ("event_today_follow20", "H310 same-day follow-up matched control", "control"),
    ("event_today_novel20", "H310 same-day first-public control", "control"),
    ("today_low_self_tau5", "H321 same-day low self-intensity diagnostic", "diagnostic"),
    ("v1_proxy_5d", "Broad event-surface-v1 proxy", "control"),
)

METRIC_SPECS = (
    ("buy_now_label", "label"),
    ("cycle_return_net", "net"),
    ("cycle_relative_return_vs_vnindex", "rel_vnindex"),
)

MIN_ACTIVE_ROWS = 8
MIN_ACTIVE_DATES = 4
MATCH_BUCKETS = 5


def _json_safe(value: object):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
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


def _daily_rank(series: pd.Series, time_index: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").groupby(time_index, sort=False).rank(
        method="average",
        pct=True,
        ascending=True,
    )


def _load_h321_states() -> pd.DataFrame:
    panel_path = resolve_summary_artifact(H321_SUMMARY_PATH, "panel")
    columns = ["time", "ticker", *[state for state, _note, _kind in STATE_SPECS]]
    panel = pd.read_parquet(panel_path, columns=columns).copy()
    panel["time"] = pd.to_datetime(panel["time"], errors="coerce").dt.normalize()
    panel["ticker"] = panel["ticker"].astype(str).str.upper()
    panel = panel.loc[panel["time"].dt.year.between(2023, 2025)].copy()
    for state_name, _note, _kind in STATE_SPECS:
        panel[state_name] = panel[state_name].fillna(False).astype(bool)
    return panel


def _load_entry_panel() -> pd.DataFrame:
    candidate_cols = [
        "time",
        "ticker",
        "selection_score",
        "selection_rank",
        "candidate_pool_rank",
        "candidate_pool_size",
        "can_buy_next_open",
        "activation_state",
        "activation_scale",
        "actual",
    ]
    label_cols = [
        "time",
        "ticker",
        "cycle_return_net",
        "cycle_relative_return_vs_vnindex",
        "cycle_relative_return_vs_cash",
        "buy_now_label",
    ]
    score_cols = [
        "time",
        "ticker",
        "research_phase",
        "entry_prob__implementation_context",
        "entry_prob__price_state",
        "entry_prob__blend",
    ]
    candidates = pd.read_parquet(CANDIDATE_PANEL_PATH, columns=candidate_cols).copy()
    labels = pd.read_parquet(ENTRY_LABELS_PATH, columns=label_cols).copy()
    scores = pd.read_parquet(ENTRY_SCORES_PATH, columns=score_cols).copy()

    for frame in (candidates, labels, scores):
        frame["time"] = pd.to_datetime(frame["time"], errors="coerce").dt.normalize()
        frame["ticker"] = frame["ticker"].astype(str).str.upper()

    candidates = candidates.loc[candidates["time"].dt.year.between(2023, 2025)].copy()
    labels = labels.loc[labels["time"].dt.year.between(2023, 2025)].copy()
    scores = scores.loc[scores["time"].dt.year.between(2023, 2025)].copy()

    panel = candidates.merge(labels, on=["time", "ticker"], how="inner", validate="one_to_one")
    panel = panel.merge(scores, on=["time", "ticker"], how="left", validate="one_to_one")

    numeric_cols = [
        "selection_score",
        "selection_rank",
        "candidate_pool_rank",
        "candidate_pool_size",
        "activation_scale",
        "actual",
        "cycle_return_net",
        "cycle_relative_return_vs_vnindex",
        "cycle_relative_return_vs_cash",
        "buy_now_label",
        "entry_prob__implementation_context",
        "entry_prob__price_state",
        "entry_prob__blend",
    ]
    for col in numeric_cols:
        if col in panel.columns:
            panel[col] = pd.to_numeric(panel[col], errors="coerce")
    panel["entry_prior_score"] = panel["entry_prob__blend"].combine_first(panel["selection_score"])
    panel["entry_prior_rank"] = _daily_rank(panel["entry_prior_score"], panel["time"])
    panel["selection_score_rank"] = _daily_rank(panel["selection_score"], panel["time"])
    bucket = np.ceil(pd.to_numeric(panel["entry_prior_rank"], errors="coerce") * MATCH_BUCKETS)
    panel["entry_prior_bucket"] = bucket.clip(lower=1, upper=MATCH_BUCKETS).astype("Int64")
    return panel.sort_values(["time", "ticker"]).reset_index(drop=True)


def _build_panel() -> pd.DataFrame:
    entry_panel = _load_entry_panel()
    states = _load_h321_states()
    panel = entry_panel.merge(states, on=["time", "ticker"], how="left", validate="one_to_one")
    for state_name, _note, _kind in STATE_SPECS:
        panel[state_name] = panel[state_name].fillna(False).astype(bool)
    return panel.sort_values(["time", "ticker"]).reset_index(drop=True)


def _daily_lift(frame: pd.DataFrame, state_col: str, metric_col: str) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for time, group in frame.groupby("time", sort=True):
        state = group[state_col].fillna(False).astype(bool)
        active_metric = pd.to_numeric(group.loc[state, metric_col], errors="coerce").dropna()
        all_metric = pd.to_numeric(group[metric_col], errors="coerce").dropna()
        if active_metric.empty or all_metric.empty:
            continue
        rows.append(
            {
                "time": pd.Timestamp(time),
                "active_count": int(active_metric.shape[0]),
                "lift": float(active_metric.mean() - all_metric.mean()),
            }
        )
    daily = pd.DataFrame(rows)
    return {
        "daily_count": int(len(daily)),
        "daily_lift": _safe_float(daily["lift"].mean()) if not daily.empty else None,
        "daily_lift_hit_rate": _safe_float((daily["lift"] > 0.0).mean()) if not daily.empty else None,
        "avg_active_names_per_active_day": _safe_float(daily["active_count"].mean()) if not daily.empty else None,
    }


def _entry_prior_matched_lift(frame: pd.DataFrame, state_col: str, metric_col: str) -> dict[str, object]:
    metric = pd.to_numeric(frame[metric_col], errors="coerce")
    state = frame[state_col].fillna(False).astype(bool)
    work = frame.loc[metric.notna() & frame["entry_prior_bucket"].notna()].copy()
    if work.empty:
        return {"matched_rows": 0, "matched_lift": None, "matched_lift_hit_rate": None}

    work["_metric"] = pd.to_numeric(work[metric_col], errors="coerce")
    work["_state"] = work[state_col].fillna(False).astype(bool)
    refs = (
        work.loc[~work["_state"]]
        .groupby(["time", "entry_prior_bucket"], as_index=False)["_metric"]
        .mean()
        .rename(columns={"_metric": "_matched_mean"})
    )
    active = work.loc[work["_state"], ["time", "ticker", "entry_prior_bucket", "_metric"]].copy()
    matched = active.merge(refs, on=["time", "entry_prior_bucket"], how="left", validate="many_to_one")
    matched = matched.dropna(subset=["_matched_mean", "_metric"]).copy()
    if matched.empty:
        return {"matched_rows": 0, "matched_lift": None, "matched_lift_hit_rate": None}
    matched["_lift"] = matched["_metric"] - matched["_matched_mean"]
    return {
        "matched_rows": int(len(matched)),
        "matched_lift": _safe_float(matched["_lift"].mean()),
        "matched_lift_hit_rate": _safe_float((matched["_lift"] > 0.0).mean()),
    }


def _daily_state_ic(frame: pd.DataFrame, state_col: str, metric_col: str) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for time, group in frame.groupby("time", sort=True):
        clean = group[[state_col, metric_col]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(clean) < 8 or clean[state_col].nunique() < 2 or clean[metric_col].nunique() < 2:
            continue
        ic = clean[state_col].astype(float).corr(pd.to_numeric(clean[metric_col], errors="coerce"), method="spearman")
        if not np.isfinite(ic):
            continue
        rows.append({"time": pd.Timestamp(time), "ic": float(ic)})
    daily = pd.DataFrame(rows)
    return {
        "daily_ic_count": int(len(daily)),
        "daily_ic_mean": _safe_float(daily["ic"].mean()) if not daily.empty else None,
        "daily_ic_hit_rate": _safe_float((daily["ic"] > 0.0).mean()) if not daily.empty else None,
    }


def _phase_state_summary(panel: pd.DataFrame, state_col: str, phase: str) -> dict[str, object]:
    scoped = panel.loc[phase_mask(panel, phase, protocol=PROTOCOL)].copy()
    state = scoped[state_col].fillna(False).astype(bool)
    active = scoped.loc[state].copy()
    summary: dict[str, object] = {
        "phase": phase,
        "state": state_col,
        "rows": int(len(scoped)),
        "dates": int(scoped["time"].nunique()) if not scoped.empty else 0,
        "active_rows": int(len(active)),
        "active_dates": int(active["time"].nunique()) if not active.empty else 0,
        "coverage": float(state.mean()) if not scoped.empty else 0.0,
        "active_entry_prior_rank_mean": _safe_float(active["entry_prior_rank"].mean()) if not active.empty else None,
        "all_entry_prior_rank_mean": _safe_float(scoped["entry_prior_rank"].mean()) if not scoped.empty else None,
    }
    for metric_col, metric_slug in METRIC_SPECS:
        active_metric = pd.to_numeric(active[metric_col], errors="coerce").dropna() if not active.empty else pd.Series(dtype=float)
        all_metric = pd.to_numeric(scoped[metric_col], errors="coerce").dropna() if not scoped.empty else pd.Series(dtype=float)
        summary[f"active_{metric_slug}_mean"] = _safe_float(active_metric.mean()) if not active_metric.empty else None
        summary[f"all_{metric_slug}_mean"] = _safe_float(all_metric.mean()) if not all_metric.empty else None
        summary[f"raw_{metric_slug}_lift"] = (
            None
            if active_metric.empty or all_metric.empty
            else float(active_metric.mean() - all_metric.mean())
        )
        daily = _daily_lift(scoped, state_col, metric_col)
        matched = _entry_prior_matched_lift(scoped, state_col, metric_col)
        daily_ic = _daily_state_ic(scoped, state_col, metric_col)
        summary[f"daily_{metric_slug}_lift"] = daily["daily_lift"]
        summary[f"daily_{metric_slug}_lift_days"] = daily["daily_count"]
        summary[f"daily_{metric_slug}_lift_hit_rate"] = daily["daily_lift_hit_rate"]
        summary[f"matched_{metric_slug}_lift"] = matched["matched_lift"]
        summary[f"matched_{metric_slug}_rows"] = matched["matched_rows"]
        summary[f"matched_{metric_slug}_lift_hit_rate"] = matched["matched_lift_hit_rate"]
        summary[f"daily_{metric_slug}_ic_mean"] = daily_ic["daily_ic_mean"]
        summary[f"daily_{metric_slug}_ic_days"] = daily_ic["daily_ic_count"]
        summary[f"daily_{metric_slug}_ic_hit_rate"] = daily_ic["daily_ic_hit_rate"]
    return summary


def _make_results(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for state_col, note, kind in STATE_SPECS:
        for phase in ("dev", "validation", "confirmation"):
            row = _phase_state_summary(panel, state_col, phase)
            row["state_note"] = note
            row["state_kind"] = kind
            rows.append(row)
    return pd.DataFrame(rows)


def _row(results: pd.DataFrame, state: str, phase: str) -> pd.Series:
    match = results.loc[(results["state"] == state) & (results["phase"] == phase)]
    if match.empty:
        raise ValueError(f"Missing result for {state} / {phase}")
    return match.iloc[0]


def _positive(value: object) -> bool:
    numeric = pd.to_numeric(value, errors="coerce")
    return bool(pd.notna(numeric) and float(numeric) > 0.0)


def _decide(results: pd.DataFrame) -> dict[str, object]:
    val = _row(results, "today_self_accel_high", "validation")
    conf = _row(results, "today_self_accel_high", "confirmation")
    val_control = _row(results, "event_today_follow20", "validation")
    conf_control = _row(results, "event_today_follow20", "confirmation")

    enough_validation = int(val["active_rows"]) >= MIN_ACTIVE_ROWS and int(val["active_dates"]) >= MIN_ACTIVE_DATES
    enough_confirmation = int(conf["active_rows"]) >= MIN_ACTIVE_ROWS and int(conf["active_dates"]) >= MIN_ACTIVE_DATES
    if not enough_validation or not enough_confirmation:
        return {
            "verdict": "SKIPPED",
            "branch_decision": (
                "Candidate state is too sparse on the entry-candidate panel for a valid validation/confirmation test."
            ),
            "reason": "insufficient_active_rows_or_dates",
        }

    validation_positive = (
        _positive(val["daily_label_lift"])
        and _positive(val["matched_label_lift"])
        and _positive(val["matched_net_lift"])
        and _positive(val["matched_rel_vnindex_lift"])
    )
    confirmation_positive = (
        _positive(conf["daily_label_lift"])
        and _positive(conf["matched_label_lift"])
        and _positive(conf["matched_net_lift"])
        and _positive(conf["matched_rel_vnindex_lift"])
    )
    beats_control_validation = (
        float(pd.to_numeric(val["matched_net_lift"], errors="coerce"))
        >= float(pd.to_numeric(val_control["matched_net_lift"], errors="coerce"))
    )
    beats_control_confirmation = (
        float(pd.to_numeric(conf["matched_net_lift"], errors="coerce"))
        >= float(pd.to_numeric(conf_control["matched_net_lift"], errors="coerce"))
    )

    if validation_positive and confirmation_positive and beats_control_validation and beats_control_confirmation:
        return {
            "verdict": "PASSED",
            "branch_decision": (
                "Cascade state survives as an entry-label candidate. Advance to a small-book integration audit."
            ),
            "reason": "positive_entry_lift_both_phases_and_beats_follow20_control",
        }
    if validation_positive and confirmation_positive:
        return {
            "verdict": "MIXED",
            "branch_decision": (
                "Cascade state has positive entry lift in both phases but does not cleanly beat the matched H310 follow-up control."
            ),
            "reason": "positive_both_phases_but_control_not_cleared",
        }
    if validation_positive or confirmation_positive:
        return {
            "verdict": "MIXED",
            "branch_decision": (
                "Cascade state shows one-phase entry lift only. Keep as weak offline evidence; do not integrate."
            ),
            "reason": "one_phase_positive_only",
        }
    return {
        "verdict": "FAILED",
        "branch_decision": (
            "Cascade state does not improve the entry-label contract after matching against the existing entry prior."
        ),
        "reason": "entry_lift_not_positive_in_validation_and_confirmation",
    }


def _print_results(results: pd.DataFrame, decision: dict[str, object]) -> None:
    table = results.loc[
        results["state"].isin(["today_self_accel_high", "event_today_follow20", "event_today_novel20"]),
        [
            "state",
            "phase",
            "active_rows",
            "active_dates",
            "daily_label_lift",
            "matched_label_lift",
            "matched_net_lift",
            "matched_rel_vnindex_lift",
            "active_entry_prior_rank_mean",
        ],
    ].copy()
    print("\nH349: EVENT-CASCADE ENTRY-LABEL AUDIT")
    print(table.to_string(index=False))
    print(f"\nverdict={decision['verdict']} | reason={decision['reason']}")


def main() -> None:
    panel = _build_panel()
    if (panel["time"].dt.year >= 2026).any():
        raise ValueError("H349 predictive panel unexpectedly includes 2026+ rows")

    results = _make_results(panel)
    decision = _decide(results)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)
    panel_out = OUT_DIR / f"{ts}_h349_event_cascade_entry_label_panel.parquet"
    results_out = OUT_DIR / f"{ts}_h349_event_cascade_entry_label_results.parquet"
    details_out = DETAILS_DIR / f"{ts}_h349_event_cascade_entry_label_details.json"

    panel.to_parquet(panel_out, index=False)
    results.to_parquet(results_out, index=False)

    primary_validation = _row(results, "today_self_accel_high", "validation")
    primary_confirmation = _row(results, "today_self_accel_high", "confirmation")
    summary = {
        **decision,
        "protocol": PROTOCOL.describe(),
        "panel_rows": int(len(panel)),
        "panel_dates": int(panel["time"].nunique()),
        "panel_tickers": int(panel["ticker"].nunique()),
        "candidate_state": "today_self_accel_high",
        "validation_active_rows": int(primary_validation["active_rows"]),
        "validation_active_dates": int(primary_validation["active_dates"]),
        "validation_daily_label_lift": _safe_float(primary_validation["daily_label_lift"]),
        "validation_matched_label_lift": _safe_float(primary_validation["matched_label_lift"]),
        "validation_matched_net_lift": _safe_float(primary_validation["matched_net_lift"]),
        "validation_matched_rel_vnindex_lift": _safe_float(primary_validation["matched_rel_vnindex_lift"]),
        "confirmation_active_rows": int(primary_confirmation["active_rows"]),
        "confirmation_active_dates": int(primary_confirmation["active_dates"]),
        "confirmation_daily_label_lift": _safe_float(primary_confirmation["daily_label_lift"]),
        "confirmation_matched_label_lift": _safe_float(primary_confirmation["matched_label_lift"]),
        "confirmation_matched_net_lift": _safe_float(primary_confirmation["matched_net_lift"]),
        "confirmation_matched_rel_vnindex_lift": _safe_float(primary_confirmation["matched_rel_vnindex_lift"]),
    }
    details = {
        "summary": summary,
        "state_specs": [
            {"state": state, "note": note, "kind": kind}
            for state, note, kind in STATE_SPECS
        ],
        "metric_specs": [
            {"metric": metric, "slug": slug}
            for metric, slug in METRIC_SPECS
        ],
        "decision_rules": {
            "minimum_active_rows_per_validation_phase": MIN_ACTIVE_ROWS,
            "minimum_active_dates_per_validation_phase": MIN_ACTIVE_DATES,
            "pass": (
                "validation and confirmation daily/matched label plus matched net and relative-return lifts are positive, "
                "and matched net lift beats the H310 follow-up control in both phases"
            ),
            "mixed": "one or both phases positive without clearing the full matched-control bar",
            "failed": "sufficient coverage but no positive validation/confirmation entry lift",
            "skipped": "insufficient validation or confirmation active rows/dates",
        },
    }
    details_out.write_text(json.dumps(_json_safe(details), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary_path = write_run_summary(
        ts=ts,
        mode="research_branch_event_cascade_entry_label",
        name="h349_event_cascade_entry_label",
        summary=summary,
        artifacts={
            "panel": str(panel_out),
            "results": str(results_out),
            "details": str(details_out),
        },
        metadata={
            "h321_summary": str(H321_SUMMARY_PATH),
            "candidate_panel": str(CANDIDATE_PANEL_PATH),
            "entry_labels": str(ENTRY_LABELS_PATH),
            "entry_scores": str(ENTRY_SCORES_PATH),
            "state_specs": [state for state, _note, _kind in STATE_SPECS],
        },
    )

    _print_results(results, decision)
    print(f"summary={summary_path}")


if __name__ == "__main__":
    main()
