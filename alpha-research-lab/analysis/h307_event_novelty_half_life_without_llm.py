"""
H307: event novelty half-life without LLM audit.

Question:
    Do the first-public company-event rows recovered by H301 support a usable
    novelty-versus-crowding split on the observed 2023-2025 panel, or is the
    event-novelty effect still too sparse and unstable without full LLM news
    coverage?
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


H301_SUMMARY_PATH = ROOT / "artifacts" / "run_summaries" / "latest_research_branch_cafef_event_surface_v2_pilot.json"
S1_PATH = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
EVENT_V1_PATH = data_path("features/event_surface_daily.parquet")
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"

PROTOCOL = ResearchProtocol(
    dev_start_year=2023,
    dev_end_year=2023,
    validation_start_year=2024,
    validation_end_year=2024,
    confirmation_year=2025,
    forward_start_year=2026,
)

COHORT_SPECS = (
    ("no_recent5_v2_event", "No recent H301 v2 event window", "control"),
    ("recent5_any_v2_event", "Any H301 v2 event in recent 5d", "baseline"),
    ("recent5_low_repeat20", "Recent 5d H301 event, low repeat over 20d", "recent_window"),
    ("recent5_repeat20", "Recent 5d H301 event, repeat over 20d", "recent_window"),
    ("recent5_crowded20", "Recent 5d H301 event, crowded over 20d", "recent_window"),
    ("event_today_any_v2", "Same-day H301 event", "baseline"),
    ("event_today_novel20", "Same-day H301 event, first-public over 20d", "same_day"),
    ("event_today_follow20", "Same-day H301 event, follow-up over 20d", "same_day"),
    ("event_today_crowded20", "Same-day H301 event, crowded over 20d", "same_day"),
    ("v1_proxy_5d", "Broad v1 company proxy recent 5d", "control"),
)

MIN_DAILY_IC_OBS = 3
PASS_MIN_RECENT_VALIDATION_DAYS = 150
PASS_MIN_RECENT_CONFIRMATION_DAYS = 150
PASS_RECENT_UPLIFT_VS_CROWDED = 0.015
PASS_RECENT_UPLIFT_VS_V1 = 0.0
MIXED_MIN_SAME_DAY_VALIDATION_DAYS = 15
MIXED_MIN_SAME_DAY_CONFIRMATION_DAYS = 15
MIXED_SAME_DAY_UPLIFT_VS_CROWDED = 0.03


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


def _load_first_public_path() -> Path:
    return resolve_summary_artifact(H301_SUMMARY_PATH, "first_public")


def _load_s1_panel() -> pd.DataFrame:
    panel = pd.read_parquet(S1_PATH, columns=["time", "ticker", "xs_proba", "actual"]).copy()
    panel["time"] = pd.to_datetime(panel["time"], errors="coerce").dt.normalize()
    panel = panel.loc[panel["time"].dt.year.between(2023, 2025)].copy()
    return panel


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


def _build_h301_state_panel(universe: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    first_public = pd.read_parquet(
        _load_first_public_path(),
        columns=["time", "ticker", "event_family", "article_count_1d"],
    ).copy()
    first_public["time"] = pd.to_datetime(first_public["time"], errors="coerce").dt.normalize()
    first_public = first_public.loc[first_public["time"].dt.year.between(2023, 2025)].copy()

    daily = (
        first_public.groupby(["time", "ticker"], as_index=False)
        .agg(
            event_today_v2=("event_family", "size"),
            event_family_count_1d=("event_family", "nunique"),
            article_count_1d=("article_count_1d", "sum"),
        )
        .sort_values(["ticker", "time"])
        .reset_index(drop=True)
    )

    panel = universe.merge(daily, on=["time", "ticker"], how="left", validate="one_to_one")
    for column in ("event_today_v2", "event_family_count_1d", "article_count_1d"):
        panel[column] = pd.to_numeric(panel[column], errors="coerce").fillna(0.0)
    panel["event_today_v2"] = panel["event_today_v2"].clip(lower=0.0)
    panel["has_event_today_v2"] = panel["event_today_v2"] > 0.0

    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)
    panel["recent_event_days_5d"] = panel.groupby("ticker")["has_event_today_v2"].transform(
        lambda s: s.astype(float).rolling(5, min_periods=1).sum()
    )
    panel["recent_event_days_20d"] = panel.groupby("ticker")["has_event_today_v2"].transform(
        lambda s: s.astype(float).rolling(20, min_periods=1).sum()
    )
    panel["prior_event_days_20d"] = panel.groupby("ticker")["has_event_today_v2"].transform(
        lambda s: s.astype(float).shift(1).rolling(20, min_periods=1).sum()
    ).fillna(0.0)
    panel["prior_article_count_20d"] = panel.groupby("ticker")["article_count_1d"].transform(
        lambda s: s.shift(1).rolling(20, min_periods=1).sum()
    ).fillna(0.0)

    panel["no_recent5_v2_event"] = panel["recent_event_days_5d"] <= 0.0
    panel["recent5_any_v2_event"] = panel["recent_event_days_5d"] > 0.0
    panel["recent5_low_repeat20"] = panel["recent5_any_v2_event"] & (panel["recent_event_days_20d"] <= 1.0)
    panel["recent5_repeat20"] = panel["recent5_any_v2_event"] & (panel["recent_event_days_20d"] >= 2.0)
    panel["recent5_crowded20"] = panel["recent5_any_v2_event"] & (panel["recent_event_days_20d"] >= 3.0)
    panel["event_today_any_v2"] = panel["has_event_today_v2"]
    panel["event_today_novel20"] = panel["event_today_any_v2"] & (panel["prior_event_days_20d"] <= 0.0)
    panel["event_today_follow20"] = panel["event_today_any_v2"] & (panel["prior_event_days_20d"] >= 1.0)
    panel["event_today_crowded20"] = panel["event_today_any_v2"] & (panel["prior_event_days_20d"] >= 2.0)

    return panel, int(len(first_public))


def load_panel() -> tuple[pd.DataFrame, int]:
    s1 = _load_s1_panel()
    universe = s1[["time", "ticker"]].drop_duplicates().copy()
    h301_panel, first_public_rows = _build_h301_state_panel(universe)
    v1 = _build_v1_controls()
    panel = s1.merge(h301_panel, on=["time", "ticker"], how="left", validate="one_to_one")
    panel = panel.merge(v1, on=["time", "ticker"], how="left", validate="one_to_one")
    for column in (
        "recent_event_days_5d",
        "recent_event_days_20d",
        "prior_event_days_20d",
        "prior_article_count_20d",
        "event_today_v2",
        "event_family_count_1d",
        "article_count_1d",
    ):
        panel[column] = pd.to_numeric(panel[column], errors="coerce").fillna(0.0)
    for column in (
        "no_recent5_v2_event",
        "recent5_any_v2_event",
        "recent5_low_repeat20",
        "recent5_repeat20",
        "recent5_crowded20",
        "event_today_any_v2",
        "event_today_novel20",
        "event_today_follow20",
        "event_today_crowded20",
        "v1_proxy_5d",
    ):
        panel[column] = panel[column].fillna(False).astype(bool)
    return panel, first_public_rows


def _daily_ic_series(frame: pd.DataFrame, *, score_col: str = "xs_proba") -> pd.DataFrame:
    rows = []
    for time, group in frame.groupby("time", sort=True):
        clean = group[[score_col, "actual"]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(clean) < MIN_DAILY_IC_OBS or clean[score_col].nunique() < 2 or clean["actual"].nunique() < 2:
            continue
        rho, p_value = spearmanr(clean[score_col], clean["actual"])
        if np.isfinite(rho):
            rows.append(
                {
                    "time": pd.Timestamp(time),
                    "n": int(len(clean)),
                    "ic": float(np.asarray(rho).flat[0]),
                    "p_value": float(p_value),
                }
            )
    return pd.DataFrame(rows)


def _pooled_ic(frame: pd.DataFrame, *, score_col: str = "xs_proba") -> float | None:
    clean = frame[[score_col, "actual"]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < 30 or clean[score_col].nunique() < 3 or clean["actual"].nunique() < 2:
        return None
    rho = spearmanr(clean[score_col], clean["actual"]).statistic
    if not np.isfinite(rho):
        return None
    return float(np.asarray(rho).flat[0])


def _phase_summary(frame: pd.DataFrame, *, cohort_col: str, phase: str) -> dict[str, object]:
    scoped = frame.loc[phase_mask(frame, phase, protocol=PROTOCOL)].copy()
    scoped = scoped.loc[scoped[cohort_col].fillna(False).astype(bool)].copy()
    ic_rows = _daily_ic_series(scoped)
    return {
        "cohort_rows": int(len(scoped)),
        "active_dates": int(scoped["time"].nunique()) if not scoped.empty else 0,
        "tickers": int(scoped["ticker"].nunique()) if not scoped.empty else 0,
        "pooled_ic": _pooled_ic(scoped),
        "avg_ic": float(ic_rows["ic"].mean()) if not ic_rows.empty else None,
        "daily_hit_rate": float((ic_rows["ic"] > 0.0).mean()) if not ic_rows.empty else None,
        "daily_ic_rows": int(len(ic_rows)),
        "avg_names_per_ic_day": float(ic_rows["n"].mean()) if not ic_rows.empty else None,
        "median_names_per_ic_day": float(ic_rows["n"].median()) if not ic_rows.empty else None,
        "mean_actual": float(scoped["actual"].mean()) if not scoped.empty else None,
        "actual_hit_rate": float((scoped["actual"] > 0).mean()) if not scoped.empty else None,
    }


def _lookup_row(results: pd.DataFrame, *, cohort_name: str) -> pd.Series | None:
    match = results.loc[results["cohort_name"] == cohort_name]
    if match.empty:
        return None
    return match.iloc[0]


def _decision_row(frame: pd.DataFrame, *, cohort_name: str, cohort_label: str, cohort_family: str) -> dict[str, object]:
    row = {
        "cohort_name": cohort_name,
        "cohort_label": cohort_label,
        "cohort_family": cohort_family,
    }
    for phase in ("dev", "validation", "confirmation"):
        summary = _phase_summary(frame, cohort_col=cohort_name, phase=phase)
        for key, value in summary.items():
            row[f"{phase}_{key}"] = value
    row["candidate_decision"] = "PENDING"
    return row


def _attach_comparisons(results: pd.DataFrame) -> pd.DataFrame:
    work = results.copy()
    comparisons = (
        "uplift_vs_recent5_any",
        "uplift_vs_recent5_crowded",
        "uplift_vs_v1_proxy",
        "uplift_vs_event_today_any",
        "uplift_vs_event_today_crowded",
    )
    for phase in ("dev", "validation", "confirmation"):
        for suffix in comparisons:
            work[f"{phase}_{suffix}"] = np.nan

    for idx, row in work.iterrows():
        cohort_name = str(row["cohort_name"])
        recent5_any = _lookup_row(work, cohort_name="recent5_any_v2_event")
        recent5_crowded = _lookup_row(work, cohort_name="recent5_crowded20")
        v1_proxy = _lookup_row(work, cohort_name="v1_proxy_5d")
        event_today_any = _lookup_row(work, cohort_name="event_today_any_v2")
        event_today_crowded = _lookup_row(work, cohort_name="event_today_crowded20")
        for phase in ("dev", "validation", "confirmation"):
            current_ic = _safe_float(row.get(f"{phase}_avg_ic"))
            if cohort_name.startswith("recent5_"):
                base_ic = _safe_float(recent5_any.get(f"{phase}_avg_ic")) if recent5_any is not None else None
                crowded_ic = _safe_float(recent5_crowded.get(f"{phase}_avg_ic")) if recent5_crowded is not None else None
                v1_ic = _safe_float(v1_proxy.get(f"{phase}_avg_ic")) if v1_proxy is not None else None
                if current_ic is not None and base_ic is not None:
                    work.loc[idx, f"{phase}_uplift_vs_recent5_any"] = current_ic - base_ic
                if current_ic is not None and crowded_ic is not None:
                    work.loc[idx, f"{phase}_uplift_vs_recent5_crowded"] = current_ic - crowded_ic
                if current_ic is not None and v1_ic is not None:
                    work.loc[idx, f"{phase}_uplift_vs_v1_proxy"] = current_ic - v1_ic
            if cohort_name.startswith("event_today_"):
                base_ic = _safe_float(event_today_any.get(f"{phase}_avg_ic")) if event_today_any is not None else None
                crowded_ic = _safe_float(event_today_crowded.get(f"{phase}_avg_ic")) if event_today_crowded is not None else None
                if current_ic is not None and base_ic is not None:
                    work.loc[idx, f"{phase}_uplift_vs_event_today_any"] = current_ic - base_ic
                if current_ic is not None and crowded_ic is not None:
                    work.loc[idx, f"{phase}_uplift_vs_event_today_crowded"] = current_ic - crowded_ic
    return work


def _assign_candidate_decisions(results: pd.DataFrame) -> pd.DataFrame:
    work = results.copy()
    for idx, row in work.iterrows():
        cohort_name = str(row["cohort_name"])
        if cohort_name in {"recent5_any_v2_event", "event_today_any_v2"}:
            work.loc[idx, "candidate_decision"] = "BASELINE"
            continue
        if cohort_name in {"no_recent5_v2_event", "v1_proxy_5d"}:
            work.loc[idx, "candidate_decision"] = "CONTROL"
            continue
        if cohort_name == "recent5_low_repeat20":
            pass_condition = bool(
                int(pd.to_numeric(row.get("validation_daily_ic_rows"), errors="coerce") or 0) >= PASS_MIN_RECENT_VALIDATION_DAYS
                and int(pd.to_numeric(row.get("confirmation_daily_ic_rows"), errors="coerce") or 0) >= PASS_MIN_RECENT_CONFIRMATION_DAYS
                and (_safe_float(row.get("validation_avg_ic")) or -np.inf) > 0.0
                and (_safe_float(row.get("confirmation_avg_ic")) or -np.inf) > 0.0
                and (_safe_float(row.get("validation_uplift_vs_recent5_crowded")) or -np.inf) >= PASS_RECENT_UPLIFT_VS_CROWDED
                and (_safe_float(row.get("confirmation_uplift_vs_recent5_crowded")) or -np.inf) >= PASS_RECENT_UPLIFT_VS_CROWDED
                and (_safe_float(row.get("validation_uplift_vs_v1_proxy")) or -np.inf) >= PASS_RECENT_UPLIFT_VS_V1
                and (_safe_float(row.get("confirmation_uplift_vs_v1_proxy")) or -np.inf) >= PASS_RECENT_UPLIFT_VS_V1
            )
            work.loc[idx, "candidate_decision"] = "PASSED" if pass_condition else "FAILED"
            continue
        if cohort_name == "event_today_novel20":
            mixed_condition = bool(
                int(pd.to_numeric(row.get("validation_daily_ic_rows"), errors="coerce") or 0) >= MIXED_MIN_SAME_DAY_VALIDATION_DAYS
                and int(pd.to_numeric(row.get("confirmation_daily_ic_rows"), errors="coerce") or 0) >= MIXED_MIN_SAME_DAY_CONFIRMATION_DAYS
                and (_safe_float(row.get("validation_avg_ic")) or -np.inf) > 0.0
                and (_safe_float(row.get("confirmation_avg_ic")) or -np.inf) > 0.0
                and (_safe_float(row.get("validation_uplift_vs_event_today_crowded")) or -np.inf) >= MIXED_SAME_DAY_UPLIFT_VS_CROWDED
                and (_safe_float(row.get("confirmation_uplift_vs_event_today_crowded")) or -np.inf) >= MIXED_SAME_DAY_UPLIFT_VS_CROWDED
            )
            work.loc[idx, "candidate_decision"] = "MIXED" if mixed_condition else "FAILED"
            continue
        work.loc[idx, "candidate_decision"] = "FAILED"
    return work


def _sort_results(results: pd.DataFrame) -> pd.DataFrame:
    work = results.copy()
    rank_map = {"PASSED": 4, "MIXED": 3, "FAILED": 2, "BASELINE": 1, "CONTROL": 0}
    work["_decision_rank"] = work["candidate_decision"].map(rank_map).fillna(0)
    for column in (
        "confirmation_avg_ic",
        "validation_avg_ic",
        "confirmation_uplift_vs_recent5_crowded",
        "validation_uplift_vs_recent5_crowded",
        "confirmation_uplift_vs_event_today_crowded",
        "validation_uplift_vs_event_today_crowded",
        "confirmation_daily_ic_rows",
        "validation_daily_ic_rows",
    ):
        work[column] = pd.to_numeric(work.get(column), errors="coerce")
    return work.sort_values(
        by=[
            "_decision_rank",
            "confirmation_avg_ic",
            "validation_avg_ic",
            "confirmation_daily_ic_rows",
            "validation_daily_ic_rows",
            "cohort_name",
        ],
        ascending=[False, False, False, False, False, True],
        ignore_index=True,
    ).drop(columns="_decision_rank")


def main() -> None:
    panel, first_public_rows = load_panel()
    results = pd.DataFrame(
        [
            _decision_row(panel, cohort_name=cohort_name, cohort_label=cohort_label, cohort_family=cohort_family)
            for cohort_name, cohort_label, cohort_family in COHORT_SPECS
        ]
    )
    results = _attach_comparisons(results)
    results = _assign_candidate_decisions(results)
    results = _sort_results(results)

    pass_rows = results.loc[results["candidate_decision"] == "PASSED"].copy()
    mixed_rows = results.loc[results["candidate_decision"] == "MIXED"].copy()
    decision = "PASSED" if not pass_rows.empty else "MIXED" if not mixed_rows.empty else "FAILED"

    recent_window_target = _lookup_row(results, cohort_name="recent5_low_repeat20")
    same_day_target = _lookup_row(results, cohort_name="event_today_novel20")
    crowded_control = _lookup_row(results, cohort_name="recent5_crowded20")
    v1_proxy = _lookup_row(results, cohort_name="v1_proxy_5d")

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    artifact_stem = f"{ts}_h307_event_novelty_half_life_without_llm"
    panel_path = OUT_DIR / f"{artifact_stem}_panel.parquet"
    results_path = OUT_DIR / f"{artifact_stem}_results.parquet"
    details_path = ROOT / "artifacts" / "run_summaries" / f"{artifact_stem}_details.json"

    panel_cols = [
        "time",
        "ticker",
        "xs_proba",
        "actual",
        "event_today_v2",
        "event_family_count_1d",
        "article_count_1d",
        "recent_event_days_5d",
        "recent_event_days_20d",
        "prior_event_days_20d",
        "prior_article_count_20d",
        "no_recent5_v2_event",
        "recent5_any_v2_event",
        "recent5_low_repeat20",
        "recent5_repeat20",
        "recent5_crowded20",
        "event_today_any_v2",
        "event_today_novel20",
        "event_today_follow20",
        "event_today_crowded20",
        "v1_proxy_5d",
    ]
    panel[panel_cols].to_parquet(panel_path, index=False)
    results.to_parquet(results_path, index=False)

    summary = {
        "decision": decision,
        "protocol": PROTOCOL.describe(),
        "first_public_rows": int(first_public_rows),
        "recent_window_target": recent_window_target.to_dict() if recent_window_target is not None else {},
        "same_day_target": same_day_target.to_dict() if same_day_target is not None else {},
        "crowded_recent_window_control": crowded_control.to_dict() if crowded_control is not None else {},
        "v1_proxy_control": v1_proxy.to_dict() if v1_proxy is not None else {},
        "pass_candidate_count": int(len(pass_rows)),
        "mixed_candidate_count": int(len(mixed_rows)),
        "branch_decision": {
            "PASSED": "H301 novelty states are broad enough and strong enough to justify a predictive event-novelty branch without waiting for the LLM cache.",
            "MIXED": "The broad recent-window novelty split does not clear, but the same-day first-public pocket is directionally real enough to preserve only as sparse offline evidence.",
            "FAILED": "H301 novelty versus crowding does not separate cleanly enough on the observed 2023-2025 panel; keep the branch closed until better mapping or LLM coverage arrives.",
        }[decision],
    }
    details_payload = {
        "summary": summary,
        "results": results.to_dict(orient="records"),
        "pass_rows": pass_rows.to_dict(orient="records"),
        "mixed_rows": mixed_rows.to_dict(orient="records"),
        "thresholds": {
            "pass_min_recent_validation_days": PASS_MIN_RECENT_VALIDATION_DAYS,
            "pass_min_recent_confirmation_days": PASS_MIN_RECENT_CONFIRMATION_DAYS,
            "pass_recent_uplift_vs_crowded": PASS_RECENT_UPLIFT_VS_CROWDED,
            "pass_recent_uplift_vs_v1": PASS_RECENT_UPLIFT_VS_V1,
            "mixed_min_same_day_validation_days": MIXED_MIN_SAME_DAY_VALIDATION_DAYS,
            "mixed_min_same_day_confirmation_days": MIXED_MIN_SAME_DAY_CONFIRMATION_DAYS,
            "mixed_same_day_uplift_vs_crowded": MIXED_SAME_DAY_UPLIFT_VS_CROWDED,
        },
    }
    details_path.write_text(json.dumps(_json_safe(details_payload), indent=2) + "\n", encoding="utf-8")

    write_run_summary(
        ts=ts,
        mode="research_branch_event_novelty_half_life_without_llm",
        name="h307_event_novelty_half_life_without_llm",
        summary=summary,
        artifacts={
            "panel": panel_path,
            "results": results_path,
            "details": details_path,
        },
        metadata={
            "session": 133,
            "protocol": PROTOCOL.describe(),
            "h301_first_public_source": _load_first_public_path(),
            "branch_contract": "H307 is a 2023-2025 observed-subset audit of frozen S1 efficacy inside H301 novelty-versus-crowding states; only a broad recent-window split can PASS.",
        },
    )

    print("H307 event novelty half-life without LLM audit")
    print(json.dumps(_json_safe(summary), indent=2))


if __name__ == "__main__":
    main()
