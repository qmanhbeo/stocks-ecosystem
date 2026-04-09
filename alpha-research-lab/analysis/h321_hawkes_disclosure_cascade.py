"""
H321: Hawkes-style disclosure cascade audit.

Question:
    Do CafeF company-event disclosures behave like a self-exciting cascade,
    where decayed prior ticker / sector event intensity separates first-public
    shock, follow-up drift, and crowded states better than the H310 novelty
    windows?

Design:
    - reuse the H309/H310 issuer-validated event-v2 surface
    - compute simple Hawkes-style decayed prior event counts on the trading-day
      panel, not a full likelihood model
    - predeclare same-day and recent-window cascade states
    - compare them against the H310 event_today_novel20 / follow20 /
      crowded20 and recent5_low_repeat20 / crowded20 controls
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

from analysis.h310_event_v2_predictive_rescreen import (  # noqa: E402
    _build_h310_state_panel,
    _build_v1_controls,
)
from src.additive_selector_research import resolve_summary_artifact  # noqa: E402
from src.future_return_research import load_future_rel_5d  # noqa: E402
from src.research_protocol import ResearchProtocol, phase_mask  # noqa: E402
from src.run_summary import write_run_summary  # noqa: E402


H310_SUMMARY_PATH = ROOT / "artifacts" / "run_summaries" / "latest_research_branch_event_v2_predictive_rescreen.json"
S1_PATH = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
SECTOR_PATH = data_path("features/sector_classification.parquet")
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

MIN_DAILY_IC_OBS = 3
PASS_MIN_SAME_DAY_IC_ROWS = 20
PASS_MIN_RECENT_IC_ROWS = 120
PASS_SAME_DAY_IC_UPLIFT = 0.025
PASS_RECENT_IC_UPLIFT = 0.010
MIXED_MIN_IC_UPLIFT = 0.0
MIXED_ONE_PHASE_IC_UPLIFT = 0.020

THRESHOLD_CONTEXTS = {
    "today": "event_today_any_v2",
    "recent": "recent5_any_v2_event",
}

CASCADE_SPECS = (
    {
        "state_name": "today_low_self_tau5",
        "state_note": "Same-day event with low decayed prior ticker intensity",
        "state_group": "same_day",
        "matched_control": "event_today_novel20",
    },
    {
        "state_name": "today_high_self_tau5",
        "state_note": "Same-day event with high decayed prior ticker intensity",
        "state_group": "same_day",
        "matched_control": "event_today_follow20",
    },
    {
        "state_name": "today_high_sector_low_self",
        "state_note": "Same-day event in a high sector-peer cascade but low own prior intensity",
        "state_group": "same_day",
        "matched_control": "event_today_novel20",
    },
    {
        "state_name": "today_self_accel_high",
        "state_note": "Same-day event with fast self-excitation acceleration",
        "state_group": "same_day",
        "matched_control": "event_today_follow20",
    },
    {
        "state_name": "recent5_high_self_no_today",
        "state_note": "Recent 5d event window, no same-day event, high decayed prior ticker intensity",
        "state_group": "recent_window",
        "matched_control": "recent5_crowded20",
    },
    {
        "state_name": "recent5_low_self_no_today",
        "state_note": "Recent 5d event window, no same-day event, low decayed prior ticker intensity",
        "state_group": "recent_window",
        "matched_control": "recent5_low_repeat20",
    },
    {
        "state_name": "recent5_high_sector_no_today",
        "state_note": "Recent 5d event window, no same-day event, high sector-peer intensity",
        "state_group": "recent_window",
        "matched_control": "recent5_crowded20",
    },
)

CONTROL_SPECS = (
    ("event_today_novel20", "H310 same-day first-public control", "control"),
    ("event_today_follow20", "H310 same-day follow-up control", "control"),
    ("event_today_crowded20", "H310 same-day crowded control", "control"),
    ("recent5_low_repeat20", "H310 recent low-repeat control", "control"),
    ("recent5_crowded20", "H310 recent crowded control", "control"),
    ("v1_proxy_5d", "Broad v1 company-event proxy", "control"),
)


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


def _load_s1_panel() -> pd.DataFrame:
    panel = pd.read_parquet(S1_PATH, columns=["time", "ticker", "xs_proba", "actual"]).copy()
    panel["time"] = pd.to_datetime(panel["time"], errors="coerce").dt.normalize()
    panel = panel.loc[panel["time"].dt.year.between(2023, 2025)].copy()
    panel["ticker"] = panel["ticker"].astype(str).str.upper()
    return panel


def _load_article_counts() -> pd.DataFrame:
    article_events_path = resolve_summary_artifact(H310_SUMMARY_PATH, "combined_article_events")
    article_events = pd.read_parquet(article_events_path).copy()
    article_events["time"] = pd.to_datetime(article_events["time"], errors="coerce").dt.normalize()
    article_events = article_events.loc[article_events["time"].dt.year.between(2023, 2025)].copy()
    article_events["ticker"] = article_events["ticker"].astype(str).str.upper()
    counts = (
        article_events.groupby(["time", "ticker"], as_index=False)
        .agg(
            event_article_count_1d=("article_id", "nunique"),
            event_article_family_count_1d=("event_family", "nunique"),
        )
        .sort_values(["ticker", "time"])
        .reset_index(drop=True)
    )
    return counts


def _load_sector_labels() -> pd.DataFrame:
    sector = pd.read_parquet(SECTOR_PATH).rename(columns={"symbol": "ticker"}).copy()
    sector["ticker"] = sector["ticker"].astype(str).str.upper()
    sector["sector_label"] = sector["icb_name3"].fillna(sector["icb_name2"]).fillna("Unknown").astype(str)
    return sector[["ticker", "sector_label"]].drop_duplicates()


def _decayed_prior_count(series: pd.Series, tau: float) -> pd.Series:
    decay = float(np.exp(-1.0 / float(tau)))
    values = pd.to_numeric(series, errors="coerce").fillna(0.0).to_numpy(dtype=float)
    out = np.zeros(len(values), dtype=float)
    intensity = 0.0
    for idx, value in enumerate(values):
        out[idx] = intensity
        intensity = intensity * decay + max(float(value), 0.0)
    return pd.Series(out, index=series.index)


def _add_intensity_columns(panel: pd.DataFrame) -> pd.DataFrame:
    work = panel.sort_values(["ticker", "time"]).reset_index(drop=True).copy()
    for tau in (2.0, 5.0, 10.0):
        suffix = str(int(tau))
        work[f"self_intensity_tau{suffix}"] = (
            work.groupby("ticker", group_keys=False)["event_article_count_1d"].apply(lambda s: _decayed_prior_count(s, tau))
        )

    sector_daily = (
        work.groupby(["time", "sector_label"], as_index=False)["event_article_count_1d"]
        .sum()
        .rename(columns={"event_article_count_1d": "sector_event_article_count_1d"})
        .sort_values(["sector_label", "time"])
        .reset_index(drop=True)
    )
    for tau in (2.0, 5.0, 10.0):
        suffix = str(int(tau))
        sector_daily[f"sector_intensity_tau{suffix}"] = (
            sector_daily.groupby("sector_label", group_keys=False)["sector_event_article_count_1d"].apply(
                lambda s: _decayed_prior_count(s, tau)
            )
        )

    work = work.merge(
        sector_daily[
            [
                "time",
                "sector_label",
                "sector_event_article_count_1d",
                "sector_intensity_tau2",
                "sector_intensity_tau5",
                "sector_intensity_tau10",
            ]
        ],
        on=["time", "sector_label"],
        how="left",
        validate="many_to_one",
    )
    for tau in ("2", "5", "10"):
        work[f"sector_peer_intensity_tau{tau}"] = (
            pd.to_numeric(work[f"sector_intensity_tau{tau}"], errors="coerce").fillna(0.0)
            - pd.to_numeric(work[f"self_intensity_tau{tau}"], errors="coerce").fillna(0.0)
        ).clip(lower=0.0)
    work["self_accel_tau2_10"] = work["self_intensity_tau2"] - work["self_intensity_tau10"]
    work["sector_peer_accel_tau2_10"] = work["sector_peer_intensity_tau2"] - work["sector_peer_intensity_tau10"]
    return work


def _context_thresholds(panel: pd.DataFrame) -> dict[str, float]:
    thresholds: dict[str, float] = {}
    dev_mask = phase_mask(panel, "dev", protocol=PROTOCOL)
    for context_name, context_col in THRESHOLD_CONTEXTS.items():
        scoped = panel.loc[dev_mask & panel[context_col].fillna(False).astype(bool)].copy()
        if scoped.empty:
            continue
        for col in ("self_intensity_tau5", "sector_peer_intensity_tau5", "self_accel_tau2_10"):
            values = pd.to_numeric(scoped[col], errors="coerce").dropna()
            if len(values) < 30:
                continue
            thresholds[f"{context_name}_{col}_q33"] = float(values.quantile(0.33))
            thresholds[f"{context_name}_{col}_q50"] = float(values.quantile(0.50))
            thresholds[f"{context_name}_{col}_q67"] = float(values.quantile(0.67))
    return thresholds


def _build_panel() -> tuple[pd.DataFrame, dict[str, float]]:
    s1 = _load_s1_panel()
    universe = s1[["time", "ticker"]].drop_duplicates().copy()
    first_public_path = resolve_summary_artifact(H310_SUMMARY_PATH, "combined_first_public")
    h310_panel, _ = _build_h310_state_panel(universe, first_public_path)
    v1 = _build_v1_controls()
    counts = _load_article_counts()
    sector = _load_sector_labels()

    panel = (
        s1.merge(h310_panel, on=["time", "ticker"], how="left", validate="one_to_one")
        .merge(v1, on=["time", "ticker"], how="left", validate="one_to_one")
        .merge(counts, on=["time", "ticker"], how="left", validate="one_to_one")
        .merge(sector, on="ticker", how="left", validate="many_to_one")
        .merge(load_future_rel_5d(start_year=2023, end_year=2025), on=["time", "ticker"], how="left", validate="one_to_one")
    )
    panel["sector_label"] = panel["sector_label"].fillna("Unknown").astype(str)
    for col in (
        "event_today_v2",
        "event_family_count_1d",
        "article_count_1d",
        "recent_event_days_5d",
        "recent_event_days_20d",
        "prior_event_days_20d",
        "event_article_count_1d",
        "event_article_family_count_1d",
    ):
        panel[col] = pd.to_numeric(panel[col], errors="coerce").fillna(0.0)
    for col, default in (
        ("event_article_count_1d", 0.0),
        ("event_article_family_count_1d", 0.0),
    ):
        panel[col] = pd.to_numeric(panel[col], errors="coerce").fillna(default)
    for col in (
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
        panel[col] = panel[col].fillna(False).astype(bool)

    panel = _add_intensity_columns(panel)
    thresholds = _context_thresholds(panel)

    today_self_low = thresholds.get("today_self_intensity_tau5_q33", 0.0)
    today_self_high = thresholds.get("today_self_intensity_tau5_q67", 0.0)
    today_self_median = thresholds.get("today_self_intensity_tau5_q50", 0.0)
    today_sector_high = thresholds.get("today_sector_peer_intensity_tau5_q67", 0.0)
    today_accel_high = thresholds.get("today_self_accel_tau2_10_q67", 0.0)
    recent_self_low = thresholds.get("recent_self_intensity_tau5_q33", 0.0)
    recent_self_high = thresholds.get("recent_self_intensity_tau5_q67", 0.0)
    recent_sector_high = thresholds.get("recent_sector_peer_intensity_tau5_q67", 0.0)

    panel["today_low_self_tau5"] = panel["event_today_any_v2"] & (panel["self_intensity_tau5"] <= today_self_low)
    panel["today_high_self_tau5"] = panel["event_today_any_v2"] & (panel["self_intensity_tau5"] >= today_self_high)
    panel["today_high_sector_low_self"] = (
        panel["event_today_any_v2"]
        & (panel["sector_peer_intensity_tau5"] >= today_sector_high)
        & (panel["self_intensity_tau5"] <= today_self_median)
    )
    panel["today_self_accel_high"] = panel["event_today_any_v2"] & (panel["self_accel_tau2_10"] >= today_accel_high)
    panel["recent5_high_self_no_today"] = (
        panel["recent5_any_v2_event"] & ~panel["event_today_any_v2"] & (panel["self_intensity_tau5"] >= recent_self_high)
    )
    panel["recent5_low_self_no_today"] = (
        panel["recent5_any_v2_event"] & ~panel["event_today_any_v2"] & (panel["self_intensity_tau5"] <= recent_self_low)
    )
    panel["recent5_high_sector_no_today"] = (
        panel["recent5_any_v2_event"]
        & ~panel["event_today_any_v2"]
        & (panel["sector_peer_intensity_tau5"] >= recent_sector_high)
    )
    return panel.sort_values(["time", "ticker"]).reset_index(drop=True), thresholds


def _daily_ic_series(frame: pd.DataFrame, *, score_col: str = "xs_proba") -> pd.DataFrame:
    rows: list[dict[str, object]] = []
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


def _daily_active_lift(phase_frame: pd.DataFrame, state_col: str) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for time, group in phase_frame.groupby("time", sort=True):
        active = group.loc[group[state_col].fillna(False).astype(bool)].copy()
        if active.empty:
            continue
        actual_mean = _safe_float(group["actual"].mean())
        active_actual = _safe_float(active["actual"].mean())
        fwd5_mean = _safe_float(group["fwd_rel_5d"].mean())
        active_fwd5 = _safe_float(active["fwd_rel_5d"].mean())
        rows.append(
            {
                "time": pd.Timestamp(time),
                "active_rows": int(len(active)),
                "actual_lift": None if actual_mean is None or active_actual is None else float(active_actual - actual_mean),
                "fwd5_lift": None if fwd5_mean is None or active_fwd5 is None else float(active_fwd5 - fwd5_mean),
            }
        )
    if not rows:
        return {
            "avg_actual_lift": None,
            "avg_fwd5_lift": None,
            "avg_active_names_per_day": None,
        }
    lift = pd.DataFrame(rows)
    return {
        "avg_actual_lift": _safe_float(lift["actual_lift"].mean()),
        "avg_fwd5_lift": _safe_float(lift["fwd5_lift"].mean()),
        "avg_active_names_per_day": _safe_float(lift["active_rows"].mean()),
    }


def _phase_summary(frame: pd.DataFrame, *, state_col: str, phase: str) -> dict[str, object]:
    phase_frame = frame.loc[phase_mask(frame, phase, protocol=PROTOCOL)].copy()
    scoped = phase_frame.loc[phase_frame[state_col].fillna(False).astype(bool)].copy()
    ic_rows = _daily_ic_series(scoped)
    lift = _daily_active_lift(phase_frame, state_col)
    return {
        "cohort_rows": int(len(scoped)),
        "active_dates": int(scoped["time"].nunique()) if not scoped.empty else 0,
        "tickers": int(scoped["ticker"].nunique()) if not scoped.empty else 0,
        "pooled_ic": _pooled_ic(scoped),
        "daily_ic_rows": int(len(ic_rows)),
        "daily_ic_mean": _safe_float(ic_rows["ic"].mean()) if not ic_rows.empty else None,
        "daily_ic_hit_rate": _safe_float((ic_rows["ic"] > 0.0).mean()) if not ic_rows.empty else None,
        "actual_mean": _safe_float(scoped["actual"].mean()) if not scoped.empty else None,
        "fwd5_mean": _safe_float(scoped["fwd_rel_5d"].mean()) if not scoped.empty else None,
        "actual_hit_rate": _safe_float((scoped["actual"] > 0.0).mean()) if not scoped.empty else None,
        **lift,
    }


def _evaluate(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    specs = [
        {
            "state_name": state_name,
            "state_note": state_note,
            "state_group": state_group,
            "matched_control": None,
            "state_kind": "control",
        }
        for state_name, state_note, state_group in CONTROL_SPECS
    ] + [
        {
            **spec,
            "state_kind": "cascade_candidate",
        }
        for spec in CASCADE_SPECS
    ]
    for spec in specs:
        row: dict[str, object] = dict(spec)
        for phase in ("dev", "validation", "confirmation"):
            stats = _phase_summary(panel, state_col=spec["state_name"], phase=phase)
            for key, value in stats.items():
                row[f"{phase}_{key}"] = value
        rows.append(row)

    results = pd.DataFrame(rows)
    by_state = results.set_index("state_name", drop=False)
    for idx, row in results.iterrows():
        if row["state_kind"] != "cascade_candidate":
            results.loc[idx, "candidate_decision"] = "CONTROL"
            continue
        control_name = row["matched_control"]
        control = by_state.loc[control_name] if control_name in by_state.index else None
        if control is None:
            results.loc[idx, "candidate_decision"] = "FAILED"
            continue
        for phase in ("dev", "validation", "confirmation"):
            cand_ic = _safe_float(row[f"{phase}_daily_ic_mean"])
            ctrl_ic = _safe_float(control[f"{phase}_daily_ic_mean"])
            cand_actual = _safe_float(row[f"{phase}_actual_mean"])
            ctrl_actual = _safe_float(control[f"{phase}_actual_mean"])
            cand_fwd5 = _safe_float(row[f"{phase}_fwd5_mean"])
            ctrl_fwd5 = _safe_float(control[f"{phase}_fwd5_mean"])
            results.loc[idx, f"{phase}_ic_uplift_vs_control"] = None if cand_ic is None or ctrl_ic is None else cand_ic - ctrl_ic
            results.loc[idx, f"{phase}_actual_uplift_vs_control"] = (
                None if cand_actual is None or ctrl_actual is None else cand_actual - ctrl_actual
            )
            results.loc[idx, f"{phase}_fwd5_uplift_vs_control"] = (
                None if cand_fwd5 is None or ctrl_fwd5 is None else cand_fwd5 - ctrl_fwd5
            )

        min_rows = PASS_MIN_SAME_DAY_IC_ROWS if row["state_group"] == "same_day" else PASS_MIN_RECENT_IC_ROWS
        pass_uplift = PASS_SAME_DAY_IC_UPLIFT if row["state_group"] == "same_day" else PASS_RECENT_IC_UPLIFT
        val_rows = int(row["validation_daily_ic_rows"] or 0)
        conf_rows = int(row["confirmation_daily_ic_rows"] or 0)
        val_ic_uplift = _safe_float(results.loc[idx, "validation_ic_uplift_vs_control"]) or 0.0
        conf_ic_uplift = _safe_float(results.loc[idx, "confirmation_ic_uplift_vs_control"]) or 0.0
        val_fwd_uplift = _safe_float(results.loc[idx, "validation_fwd5_uplift_vs_control"]) or 0.0
        conf_fwd_uplift = _safe_float(results.loc[idx, "confirmation_fwd5_uplift_vs_control"]) or 0.0

        passes = (
            val_rows >= min_rows
            and conf_rows >= min_rows
            and val_ic_uplift >= pass_uplift
            and conf_ic_uplift >= pass_uplift
            and val_fwd_uplift >= 0.0
            and conf_fwd_uplift >= 0.0
        )
        mixed = (
            not passes
            and val_rows >= min_rows
            and conf_rows >= min_rows
            and val_ic_uplift >= MIXED_MIN_IC_UPLIFT
            and conf_ic_uplift >= MIXED_MIN_IC_UPLIFT
        ) or (
            val_rows >= min_rows
            and conf_rows >= min_rows
            and max(val_ic_uplift, conf_ic_uplift) >= MIXED_ONE_PHASE_IC_UPLIFT
            and min(val_ic_uplift, conf_ic_uplift) >= -0.010
        )
        results.loc[idx, "candidate_decision"] = "PASSED" if passes else "MIXED" if mixed else "FAILED"
    return results


def main() -> int:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    panel, thresholds = _build_panel()
    results = _evaluate(panel)
    candidates = results.loc[results["state_kind"].eq("cascade_candidate")].copy()
    decision_rank = {"PASSED": 0, "MIXED": 1, "FAILED": 2}
    candidates["decision_rank"] = candidates["candidate_decision"].map(decision_rank).fillna(9)
    candidates["score"] = (
        pd.to_numeric(candidates["validation_ic_uplift_vs_control"], errors="coerce").fillna(-9.0)
        + pd.to_numeric(candidates["confirmation_ic_uplift_vs_control"], errors="coerce").fillna(-9.0)
    )
    best = candidates.sort_values(["decision_rank", "score"], ascending=[True, False]).iloc[0]

    if (candidates["candidate_decision"] == "PASSED").any():
        verdict = "PASSED"
        branch_decision = (
            "A Hawkes-style cascade state beats the matched H310 novelty/control window. "
            "Advance to a narrower cascade feature or additive follow-up."
        )
    elif (candidates["candidate_decision"] == "MIXED").any():
        verdict = "MIXED"
        branch_decision = (
            "Cascade intensity carries local information but does not reliably beat the matched H310 controls. "
            "Keep it as offline timing evidence only."
        )
    else:
        verdict = "FAILED"
        branch_decision = (
            "Simple decayed ticker / sector disclosure intensity does not improve on H310 novelty windows. "
            "Park the Hawkes-cascade branch unless a richer timestamped disclosure source arrives."
        )

    panel_path = OUT_DIR / f"{ts}_h321_hawkes_disclosure_cascade_panel.parquet"
    results_path = OUT_DIR / f"{ts}_h321_hawkes_disclosure_cascade_results.parquet"
    details_path = DETAILS_DIR / f"{ts}_research_branch_hawkes_disclosure_cascade_details.json"
    panel.to_parquet(panel_path, index=False)
    results.to_parquet(results_path, index=False)

    detail_payload = {
        "branch_decision": branch_decision,
        "thresholds": thresholds,
        "best_candidate": _json_safe(best.to_dict()),
        "results": _json_safe(results.to_dict(orient="records")),
    }
    details_path.write_text(json.dumps(detail_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "verdict": verdict,
        "branch_decision": branch_decision,
        "best_state": best["state_name"],
        "best_state_decision": best["candidate_decision"],
        "best_matched_control": best["matched_control"],
        "best_validation_daily_ic_mean": _safe_float(best["validation_daily_ic_mean"]),
        "best_confirmation_daily_ic_mean": _safe_float(best["confirmation_daily_ic_mean"]),
        "best_validation_ic_uplift_vs_control": _safe_float(best["validation_ic_uplift_vs_control"]),
        "best_confirmation_ic_uplift_vs_control": _safe_float(best["confirmation_ic_uplift_vs_control"]),
        "best_validation_fwd5_uplift_vs_control": _safe_float(best["validation_fwd5_uplift_vs_control"]),
        "best_confirmation_fwd5_uplift_vs_control": _safe_float(best["confirmation_fwd5_uplift_vs_control"]),
        "panel_rows": int(len(panel)),
        "panel_tickers": int(panel["ticker"].nunique()),
        "panel_dates": int(panel["time"].nunique()),
    }
    artifacts = {
        "panel": panel_path,
        "results": results_path,
        "details": details_path,
    }
    metadata = {
        "question": "Can simple Hawkes-style self/sector disclosure intensity improve on H310 novelty windows?",
        "protocol": {"dev": "2023", "validation": "2024", "confirmation": "2025"},
        "source_surface": str(H310_SUMMARY_PATH),
        "intensity_model": "decayed prior trading-day event article counts with tau=2/5/10; no full Hawkes likelihood fit",
        "controls": [spec[0] for spec in CONTROL_SPECS],
    }
    write_run_summary(
        ts=ts,
        mode="research_branch_hawkes_disclosure_cascade",
        name="hawkes_disclosure_cascade",
        summary=summary,
        artifacts=artifacts,
        metadata=metadata,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
