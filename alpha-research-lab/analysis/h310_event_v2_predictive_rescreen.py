"""
H310: event-v2 predictive re-screen.

Question:
    Does the richer H309 issuer-validated event-v2 surface now survive the old
    H307 predictive contract, or was H309 only a mapping win with no real alpha
    rescue?
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
from src.news_event_source_research import (
    build_alias_expanded_news_event_bundle,
    scan_news_event_archive,
)
from src.research_protocol import ResearchProtocol, phase_mask
from src.run_summary import write_run_summary


H309_SUMMARY_PATH = ROOT / "artifacts" / "run_summaries" / "latest_research_branch_issuer_lexicon_event_surface.json"
S1_PATH = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
EVENT_V1_PATH = data_path("features/event_surface_daily.parquet")
RAW_NEWS_DIR = data_path("news/cafef/raw")
OUT_DIR = ROOT / "artifacts" / "timing_data"
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"

PROTOCOL = ResearchProtocol(
    dev_start_year=2023,
    dev_end_year=2023,
    validation_start_year=2024,
    validation_end_year=2024,
    confirmation_year=2025,
    forward_start_year=2026,
)

START_DATE = "2023-01-01"
END_DATE = "2025-12-31"

COHORT_SPECS = (
    ("no_recent5_v2_event", "No recent H310 v2 event window", "control"),
    ("recent5_any_v2_event", "Any H310 v2 event in recent 5d", "baseline"),
    ("recent5_low_repeat20", "Recent 5d H310 event, low repeat over 20d", "recent_window"),
    ("recent5_repeat20", "Recent 5d H310 event, repeat over 20d", "recent_window"),
    ("recent5_crowded20", "Recent 5d H310 event, crowded over 20d", "recent_window"),
    ("event_today_any_v2", "Same-day H310 event", "baseline"),
    ("event_today_novel20", "Same-day H310 event, first-public over 20d", "same_day"),
    ("event_today_follow20", "Same-day H310 event, follow-up over 20d", "same_day"),
    ("event_today_crowded20", "Same-day H310 event, crowded over 20d", "same_day"),
    ("v1_proxy_5d", "Broad v1 company proxy recent 5d", "control"),
)

MIN_DAILY_IC_OBS = 3
PASS_MIN_RECENT_VALIDATION_DAYS = 120
PASS_MIN_RECENT_CONFIRMATION_DAYS = 120
PASS_RECENT_UPLIFT_VS_CROWDED = 0.010
PASS_RECENT_UPLIFT_VS_V1 = 0.0
PASS_MIN_SAME_DAY_VALIDATION_DAYS = 25
PASS_MIN_SAME_DAY_CONFIRMATION_DAYS = 25
PASS_SAME_DAY_UPLIFT_VS_CROWDED = 0.025
MIXED_MIN_SAME_DAY_VALIDATION_DAYS = 15
MIXED_MIN_SAME_DAY_CONFIRMATION_DAYS = 15
MIXED_SAME_DAY_UPLIFT_VS_CROWDED = 0.015


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


def _load_combined_alias_map_path() -> Path:
    return resolve_summary_artifact(H309_SUMMARY_PATH, "combined_alias_map")


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


def _materialize_h309_surface(ts: str) -> tuple[dict[str, Path], dict[str, object]]:
    alias_map = pd.read_parquet(_load_combined_alias_map_path()).copy()
    universe = _load_s1_panel()[["time", "ticker"]].drop_duplicates().copy()
    allowed_tickers = set(universe["ticker"].dropna().astype(str).unique().tolist())

    scan = scan_news_event_archive(
        raw_dir=RAW_NEWS_DIR,
        start_date=START_DATE,
        end_date=END_DATE,
        allowed_tickers=allowed_tickers,
    )
    bundle, assignment_df = build_alias_expanded_news_event_bundle(scan, alias_map)
    article_events = bundle.article_events.copy()
    article_events["time"] = pd.to_datetime(article_events["time"], errors="coerce").dt.normalize()
    article_events["published_at"] = pd.to_datetime(article_events["published_at"], errors="coerce")

    first_public = (
        article_events.groupby(["time", "ticker", "event_family"], as_index=False)
        .agg(
            first_published_at=("published_at", "min"),
            article_count_1d=("article_id", "nunique"),
        )
        .sort_values(["time", "ticker", "event_family"])
        .reset_index(drop=True)
    )

    count_wide = (
        first_public.pivot_table(
            index=["time", "ticker"],
            columns="event_family",
            values="article_count_1d",
            aggfunc="sum",
            fill_value=0,
        )
        .reset_index()
    )
    count_wide.columns.name = None
    count_columns: list[str] = []
    for column in [c for c in count_wide.columns if c not in {"time", "ticker"}]:
        renamed = f"event_count__{column}"
        count_wide = count_wide.rename(columns={column: renamed})
        count_columns.append(renamed)
    count_wide["event_count__all"] = count_wide[count_columns].sum(axis=1) if count_columns else 0.0

    pilot_surface = universe.merge(count_wide, on=["time", "ticker"], how="left")
    for column in count_columns + ["event_count__all"]:
        pilot_surface[column] = pd.to_numeric(pilot_surface[column], errors="coerce").fillna(0.0)
        binary_col = column.replace("event_count__", "event_flag__")
        recent_col = column.replace("event_count__", "event_recent5__")
        pilot_surface[binary_col] = pilot_surface[column].gt(0.0).astype(int)
        pilot_surface[recent_col] = (
            pilot_surface.sort_values(["ticker", "time"])
            .groupby("ticker")[column]
            .rolling(window=5, min_periods=1)
            .sum()
            .reset_index(level=0, drop=True)
            .astype(float)
        )
    pilot_surface["has_company_event_article_v2"] = pilot_surface["event_count__all"].gt(0.0).astype(int)
    pilot_surface["recent_company_event_article_v2_5d"] = (
        pilot_surface.sort_values(["ticker", "time"])
        .groupby("ticker")["has_company_event_article_v2"]
        .rolling(window=5, min_periods=1)
        .sum()
        .reset_index(level=0, drop=True)
        .astype(float)
    )

    artifacts = {
        "combined_article_events": OUT_DIR / f"{ts}_h310_event_v2_predictive_rescreen_article_events.parquet",
        "combined_first_public": OUT_DIR / f"{ts}_h310_event_v2_predictive_rescreen_first_public.parquet",
        "combined_pilot_surface": OUT_DIR / f"{ts}_h310_event_v2_predictive_rescreen_pilot_surface.parquet",
        "combined_alias_assignments": OUT_DIR / f"{ts}_h310_event_v2_predictive_rescreen_alias_assignments.parquet",
    }
    article_events.to_parquet(artifacts["combined_article_events"], index=False)
    first_public.to_parquet(artifacts["combined_first_public"], index=False)
    pilot_surface.to_parquet(artifacts["combined_pilot_surface"], index=False)
    assignment_df.to_parquet(artifacts["combined_alias_assignments"], index=False)

    surface_summary = {
        "article_rows": int(len(article_events)),
        "unique_articles": int(article_events["article_id"].nunique()) if not article_events.empty else 0,
        "unique_tickers": int(article_events["ticker"].nunique()) if not article_events.empty else 0,
        "first_public_rows": int(len(first_public)),
        "pilot_5d_coverage": float((pilot_surface["recent_company_event_article_v2_5d"] > 0).mean()) if not pilot_surface.empty else 0.0,
        "title_alias_unique_articles": int(assignment_df["article_id"].nunique()) if not assignment_df.empty else 0,
    }
    return artifacts, surface_summary


def _build_h310_state_panel(universe: pd.DataFrame, first_public_path: Path) -> tuple[pd.DataFrame, int]:
    first_public = pd.read_parquet(
        first_public_path,
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


def _daily_ic_series(frame: pd.DataFrame, *, score_col: str = "xs_proba") -> pd.DataFrame:
    rows = []
    for time, group in frame.groupby("time", sort=True):
        clean = group[[score_col, "actual"]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(clean) < MIN_DAILY_IC_OBS or clean[score_col].nunique() < 2 or clean["actual"].nunique() < 2:
            continue
        rho, p_value = spearmanr(clean[score_col], clean["actual"])
        if np.isfinite(rho):
            rows.append({"time": pd.Timestamp(time), "n": int(len(clean)), "ic": float(np.asarray(rho).flat[0]), "p_value": float(p_value)})
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
        "daily_ic_rows": int(len(ic_rows)),
        "daily_ic_mean": _safe_float(ic_rows["ic"].mean()) if not ic_rows.empty else None,
        "daily_ic_hit_rate": _safe_float((ic_rows["ic"] > 0.0).mean()) if not ic_rows.empty else None,
        "actual_mean": _safe_float(scoped["actual"].mean()) if not scoped.empty else None,
    }


def _evaluate_results(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for cohort_name, cohort_note, cohort_group in COHORT_SPECS:
        row = {"cohort_name": cohort_name, "cohort_note": cohort_note, "cohort_group": cohort_group}
        for phase in ("dev", "validation", "confirmation"):
            summary = _phase_summary(panel, cohort_col=cohort_name, phase=phase)
            for key, value in summary.items():
                row[f"{phase}_{key}"] = value
        rows.append(row)
    results = pd.DataFrame(rows)
    by_name = results.set_index("cohort_name")

    def lift(col: str, base: str, ref: str) -> float | None:
        base_val = _safe_float(by_name.loc[base, col]) if base in by_name.index else None
        ref_val = _safe_float(by_name.loc[ref, col]) if ref in by_name.index else None
        if base_val is None or ref_val is None:
            return None
        return float(base_val - ref_val)

    for phase in ("validation", "confirmation"):
        results.loc[results["cohort_name"].eq("recent5_low_repeat20"), f"{phase}_uplift_vs_crowded"] = lift(
            f"{phase}_pooled_ic", "recent5_low_repeat20", "recent5_crowded20"
        )
        results.loc[results["cohort_name"].eq("recent5_low_repeat20"), f"{phase}_uplift_vs_v1"] = lift(
            f"{phase}_pooled_ic", "recent5_low_repeat20", "v1_proxy_5d"
        )
        results.loc[results["cohort_name"].eq("event_today_novel20"), f"{phase}_uplift_vs_crowded"] = lift(
            f"{phase}_pooled_ic", "event_today_novel20", "event_today_crowded20"
        )
        results.loc[results["cohort_name"].eq("event_today_novel20"), f"{phase}_uplift_vs_v1"] = lift(
            f"{phase}_pooled_ic", "event_today_novel20", "v1_proxy_5d"
        )
    results["candidate_decision"] = "FAILED"

    recent_mask = results["cohort_name"].eq("recent5_low_repeat20")
    same_day_mask = results["cohort_name"].eq("event_today_novel20")

    recent_pass = bool(
        int(pd.to_numeric(results.loc[recent_mask, "validation_active_dates"], errors="coerce").fillna(0).iloc[0]) >= PASS_MIN_RECENT_VALIDATION_DAYS
        and int(pd.to_numeric(results.loc[recent_mask, "confirmation_active_dates"], errors="coerce").fillna(0).iloc[0]) >= PASS_MIN_RECENT_CONFIRMATION_DAYS
        and (_safe_float(results.loc[recent_mask, "validation_pooled_ic"].iloc[0]) or -np.inf) > 0.0
        and (_safe_float(results.loc[recent_mask, "confirmation_pooled_ic"].iloc[0]) or -np.inf) > 0.0
        and (_safe_float(results.loc[recent_mask, "validation_uplift_vs_crowded"].iloc[0]) or -np.inf) >= PASS_RECENT_UPLIFT_VS_CROWDED
        and (_safe_float(results.loc[recent_mask, "confirmation_uplift_vs_crowded"].iloc[0]) or -np.inf) >= 0.0
        and (_safe_float(results.loc[recent_mask, "validation_uplift_vs_v1"].iloc[0]) or -np.inf) >= PASS_RECENT_UPLIFT_VS_V1
    )
    same_day_pass = bool(
        int(pd.to_numeric(results.loc[same_day_mask, "validation_active_dates"], errors="coerce").fillna(0).iloc[0]) >= PASS_MIN_SAME_DAY_VALIDATION_DAYS
        and int(pd.to_numeric(results.loc[same_day_mask, "confirmation_active_dates"], errors="coerce").fillna(0).iloc[0]) >= PASS_MIN_SAME_DAY_CONFIRMATION_DAYS
        and (_safe_float(results.loc[same_day_mask, "validation_pooled_ic"].iloc[0]) or -np.inf) > 0.0
        and (_safe_float(results.loc[same_day_mask, "confirmation_pooled_ic"].iloc[0]) or -np.inf) > 0.0
        and (_safe_float(results.loc[same_day_mask, "validation_uplift_vs_crowded"].iloc[0]) or -np.inf) >= PASS_SAME_DAY_UPLIFT_VS_CROWDED
        and (_safe_float(results.loc[same_day_mask, "confirmation_uplift_vs_crowded"].iloc[0]) or -np.inf) >= 0.0
    )
    same_day_mixed = bool(
        int(pd.to_numeric(results.loc[same_day_mask, "validation_active_dates"], errors="coerce").fillna(0).iloc[0]) >= MIXED_MIN_SAME_DAY_VALIDATION_DAYS
        and int(pd.to_numeric(results.loc[same_day_mask, "confirmation_active_dates"], errors="coerce").fillna(0).iloc[0]) >= MIXED_MIN_SAME_DAY_CONFIRMATION_DAYS
        and (_safe_float(results.loc[same_day_mask, "validation_pooled_ic"].iloc[0]) or -np.inf) > 0.0
        and (_safe_float(results.loc[same_day_mask, "confirmation_pooled_ic"].iloc[0]) or -np.inf) > 0.0
        and (_safe_float(results.loc[same_day_mask, "validation_uplift_vs_crowded"].iloc[0]) or -np.inf) >= MIXED_SAME_DAY_UPLIFT_VS_CROWDED
    )

    if recent_pass or same_day_pass:
        results.loc[recent_mask | same_day_mask, "candidate_decision"] = "PASSED"
    elif same_day_mixed:
        results.loc[same_day_mask, "candidate_decision"] = "MIXED"
    return results


def load_panel(first_public_path: Path) -> tuple[pd.DataFrame, int]:
    s1 = _load_s1_panel()
    universe = s1[["time", "ticker"]].drop_duplicates().copy()
    h310_panel, first_public_rows = _build_h310_state_panel(universe, first_public_path)
    v1 = _build_v1_controls()
    panel = s1.merge(h310_panel, on=["time", "ticker"], how="left", validate="one_to_one")
    panel = panel.merge(v1, on=["time", "ticker"], how="left", validate="one_to_one")
    for column in (
        "recent_event_days_5d",
        "recent_event_days_20d",
        "prior_event_days_20d",
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


def main() -> None:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    surface_artifacts, surface_summary = _materialize_h309_surface(ts)
    panel, first_public_rows = load_panel(surface_artifacts["combined_first_public"])
    results = _evaluate_results(panel)

    recent_row = results.loc[results["cohort_name"].eq("recent5_low_repeat20")].iloc[0].to_dict()
    same_day_row = results.loc[results["cohort_name"].eq("event_today_novel20")].iloc[0].to_dict()

    if "PASSED" in set(results["candidate_decision"]):
        decision = "PASSED"
        branch_decision = "The richer H309 surface now clears the predictive re-screen bar; event-v2 is reopened as a real predictive branch."
    elif "MIXED" in set(results["candidate_decision"]):
        decision = "MIXED"
        branch_decision = "H309 rescues only the same-day first-public pocket; event-v2 improves, but the broad recent-window branch still does not reopen cleanly."
    else:
        decision = "FAILED"
        branch_decision = "H309 was only a mapping win; the richer surface still does not rescue the predictive event-v2 branch."

    details = {
        "surface_summary": surface_summary,
        "results": results.to_dict(orient="records"),
        "recent_row": recent_row,
        "same_day_row": same_day_row,
    }
    details_path = DETAILS_DIR / f"{ts}_h310_event_v2_predictive_rescreen_details.json"
    details_path.write_text(json.dumps(_json_safe(details), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    summary = {
        "decision": decision,
        "branch_decision": branch_decision,
        "surface_summary": surface_summary,
        "recent_window_candidate": {
            "validation_pooled_ic": recent_row.get("validation_pooled_ic"),
            "confirmation_pooled_ic": recent_row.get("confirmation_pooled_ic"),
            "validation_uplift_vs_crowded": recent_row.get("validation_uplift_vs_crowded"),
            "confirmation_uplift_vs_crowded": recent_row.get("confirmation_uplift_vs_crowded"),
            "validation_uplift_vs_v1": recent_row.get("validation_uplift_vs_v1"),
            "validation_active_dates": recent_row.get("validation_active_dates"),
            "confirmation_active_dates": recent_row.get("confirmation_active_dates"),
            "candidate_decision": recent_row.get("candidate_decision"),
        },
        "same_day_candidate": {
            "validation_pooled_ic": same_day_row.get("validation_pooled_ic"),
            "confirmation_pooled_ic": same_day_row.get("confirmation_pooled_ic"),
            "validation_uplift_vs_crowded": same_day_row.get("validation_uplift_vs_crowded"),
            "confirmation_uplift_vs_crowded": same_day_row.get("confirmation_uplift_vs_crowded"),
            "validation_uplift_vs_v1": same_day_row.get("validation_uplift_vs_v1"),
            "validation_active_dates": same_day_row.get("validation_active_dates"),
            "confirmation_active_dates": same_day_row.get("confirmation_active_dates"),
            "candidate_decision": same_day_row.get("candidate_decision"),
        },
    }
    artifacts = {**surface_artifacts, "details": details_path}
    write_run_summary(
        ts=ts,
        mode="research_branch_event_v2_predictive_rescreen",
        name="h310_event_v2_predictive_rescreen",
        summary=summary,
        artifacts=artifacts,
        metadata={
            "session": 136,
            "branch_contract": "H310 reruns the H307 predictive contract on the richer H309 event-v2 surface; only a clean same-day or recent-window rescue reopens the branch.",
        },
    )


if __name__ == "__main__":
    main()
