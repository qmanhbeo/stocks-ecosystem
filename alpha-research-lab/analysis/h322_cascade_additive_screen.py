"""
H322: cascade additive screen.

Question:
    Does the H321 same-day cascade winner add enough value on top of the
    frozen S1/C4/C13 core to justify promotion beyond sparse cohort evidence?

Design:
    - reuse the saved H321 panel and do not re-fit cascade thresholds
    - compare today_self_accel_high against H310 event-state controls
    - test the same simple multiplicative core overlays used in H317
    - require additive improvement over the frozen core and matched
      event_today_follow20 control in validation, without breaking 2025
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
from src.research_protocol import ResearchProtocol, phase_mask
from src.run_summary import write_run_summary


H321_SUMMARY_PATH = ROOT / "artifacts" / "run_summaries" / "latest_research_branch_hawkes_disclosure_cascade.json"
MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
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

OVERLAY_WEIGHTS = (0.15, 0.30, 0.50)
TOP_QUINTILE = 0.80
BOTTOM_QUINTILE = 0.20
MIN_DAILY_IC_OBS = 8

STATE_SPECS = (
    ("today_self_accel_high", "H321 same-day fast self-excitation state", "candidate"),
    ("today_low_self_tau5", "H321 low self-intensity same-day state", "diagnostic"),
    ("event_today_novel20", "H310 same-day first-public control", "control"),
    ("event_today_follow20", "H310 same-day follow-up matched control", "control"),
    ("event_today_crowded20", "H310 same-day crowded control", "control"),
    ("v1_proxy_5d", "Broad v1 company-event proxy", "control"),
)

ADDITIVE_SPECS = (
    ("today_self_accel_high", "candidate"),
    ("event_today_novel20", "control"),
    ("event_today_follow20", "matched_control"),
    ("v1_proxy_5d", "control"),
)


def _safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


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


def _daily_rank(series: pd.Series, time_index: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").groupby(time_index, sort=False).rank(
        method="average",
        pct=True,
        ascending=True,
    )


def _load_panel() -> pd.DataFrame:
    h321_panel_path = resolve_summary_artifact(H321_SUMMARY_PATH, "panel")
    h321 = pd.read_parquet(
        h321_panel_path,
        columns=[
            "time",
            "ticker",
            "today_self_accel_high",
            "today_low_self_tau5",
            "event_today_novel20",
            "event_today_follow20",
            "event_today_crowded20",
            "v1_proxy_5d",
        ],
    ).copy()
    h321["time"] = pd.to_datetime(h321["time"], errors="coerce").dt.normalize()
    h321["ticker"] = h321["ticker"].astype(str).str.upper()

    matrix = pd.read_parquet(
        MATRIX_PATH,
        columns=["time", "ticker", "actual", "s1_proba", "c4_oc_asym_5d", "c13_compress_blowoff_2"],
    ).copy()
    matrix["time"] = pd.to_datetime(matrix["time"], errors="coerce").dt.normalize()
    matrix["ticker"] = matrix["ticker"].astype(str).str.upper()
    matrix = matrix.loc[matrix["time"].dt.year.between(2023, 2025)].copy()

    panel = (
        matrix.merge(h321, on=["time", "ticker"], how="left", validate="one_to_one")
        .sort_values(["time", "ticker"])
        .reset_index(drop=True)
    )
    for state_name, _note, _state_type in STATE_SPECS:
        panel[state_name] = panel[state_name].fillna(False).astype(bool)

    panel["s1_rank"] = _daily_rank(panel["s1_proba"], panel["time"])
    panel["c4_rank"] = _daily_rank(panel["c4_oc_asym_5d"], panel["time"])
    panel["c13_rank"] = _daily_rank(panel["c13_compress_blowoff_2"], panel["time"])
    panel["core_baseline"] = panel[["s1_rank", "c4_rank", "c13_rank"]].mean(axis=1)

    for state_name, _state_type in ADDITIVE_SPECS:
        state_values = panel[state_name].astype(float)
        for weight in OVERLAY_WEIGHTS:
            suffix = int(round(weight * 100))
            score_name = f"core_mul__{state_name}__{suffix:02d}"
            panel[score_name] = panel["core_baseline"] * (1.0 + float(weight) * state_values)
    return panel


def _daily_score_series(frame: pd.DataFrame, score_col: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for time, group in frame.groupby("time", sort=True):
        clean = group[[score_col, "actual"]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(clean) < MIN_DAILY_IC_OBS or clean[score_col].nunique() < 3 or clean["actual"].nunique() < 2:
            continue
        ic = clean[score_col].corr(clean["actual"], method="spearman")
        if not np.isfinite(ic):
            continue
        pct_rank = clean[score_col].rank(method="average", pct=True)
        top_mean = _safe_float(clean.loc[pct_rank >= TOP_QUINTILE, "actual"].mean())
        bottom_mean = _safe_float(clean.loc[pct_rank <= BOTTOM_QUINTILE, "actual"].mean())
        rows.append(
            {
                "time": pd.Timestamp(time),
                "ic": float(ic),
                "top_mean": top_mean,
                "bottom_mean": bottom_mean,
                "spread": None if top_mean is None or bottom_mean is None else float(top_mean - bottom_mean),
            }
        )
    return pd.DataFrame(rows)


def _score_phase_summary(frame: pd.DataFrame, score_col: str, phase: str) -> dict[str, object]:
    scoped = frame.loc[phase_mask(frame, phase, protocol=PROTOCOL)].copy()
    daily = _daily_score_series(scoped, score_col)
    return {
        "rows": int(len(scoped)),
        "dates": int(scoped["time"].nunique()) if not scoped.empty else 0,
        "avg_ic": _safe_float(daily["ic"].mean()) if not daily.empty else None,
        "hit_rate": _safe_float((daily["ic"] > 0.0).mean()) if not daily.empty else None,
        "top_mean": _safe_float(daily["top_mean"].mean()) if not daily.empty else None,
        "bottom_mean": _safe_float(daily["bottom_mean"].mean()) if not daily.empty else None,
        "spread": _safe_float(daily["spread"].mean()) if not daily.empty else None,
    }


def _state_phase_summary(frame: pd.DataFrame, state_col: str, phase: str) -> dict[str, object]:
    scoped = frame.loc[phase_mask(frame, phase, protocol=PROTOCOL)].copy()
    scoped_state = scoped[state_col].fillna(False).astype(bool)
    active = scoped.loc[scoped_state].copy()
    rows: list[dict[str, object]] = []
    for time, group in scoped.groupby("time", sort=True):
        clean = group[[state_col, "actual"]].replace([np.inf, -np.inf], np.nan).dropna()
        if clean.empty or clean[state_col].nunique() < 2 or clean["actual"].nunique() < 2:
            continue
        ic = clean[state_col].astype(float).corr(clean["actual"], method="spearman")
        active_mean = _safe_float(clean.loc[clean[state_col].astype(bool), "actual"].mean())
        all_mean = _safe_float(clean["actual"].mean())
        rows.append(
            {
                "time": pd.Timestamp(time),
                "ic": _safe_float(ic),
                "active_lift": None if active_mean is None or all_mean is None else float(active_mean - all_mean),
                "active_count": int(clean[state_col].astype(bool).sum()),
            }
        )
    daily = pd.DataFrame(rows)
    return {
        "rows": int(len(active)),
        "dates": int(active["time"].nunique()) if not active.empty else 0,
        "coverage": float(scoped_state.mean()) if not scoped.empty else 0.0,
        "avg_ic": _safe_float(daily["ic"].mean()) if not daily.empty else None,
        "active_lift": _safe_float(daily["active_lift"].mean()) if not daily.empty else None,
        "avg_active_names_per_day": _safe_float(daily["active_count"].mean()) if not daily.empty else None,
        "actual_mean": _safe_float(active["actual"].mean()) if not active.empty else None,
    }


def _pooled_corr(series_a: pd.Series, series_b: pd.Series) -> float | None:
    clean = pd.DataFrame(
        {
            "a": pd.to_numeric(series_a, errors="coerce"),
            "b": pd.to_numeric(series_b, errors="coerce"),
        }
    ).dropna()
    if len(clean) < 50 or clean["a"].nunique() < 2 or clean["b"].nunique() < 2:
        return None
    return _safe_float(clean["a"].corr(clean["b"], method="spearman"))


def _build_standalone_results(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for state_name, state_note, state_type in STATE_SPECS:
        row: dict[str, object] = {"state_name": state_name, "state_note": state_note, "state_type": state_type}
        for phase in ("dev", "validation", "confirmation"):
            summary = _state_phase_summary(frame, state_name, phase)
            for key, value in summary.items():
                row[f"{phase}_{key}"] = value
        row["corr_with_s1"] = _pooled_corr(frame[state_name].astype(float), frame["s1_rank"])
        row["corr_with_c4"] = _pooled_corr(frame[state_name].astype(float), frame["c4_rank"])
        row["corr_with_c13"] = _pooled_corr(frame[state_name].astype(float), frame["c13_rank"])
        rows.append(row)
    results = pd.DataFrame(rows)
    by_state = results.set_index("state_name", drop=False)
    matched = by_state.loc["event_today_follow20"]
    novelty = by_state.loc["event_today_novel20"]
    candidate_mask = results["state_name"].eq("today_self_accel_high")
    idx = results.loc[candidate_mask].index[0]
    for phase in ("dev", "validation", "confirmation"):
        for control_name, control in (("matched", matched), ("novelty", novelty)):
            cand_ic = _safe_float(results.loc[idx, f"{phase}_avg_ic"])
            ctrl_ic = _safe_float(control[f"{phase}_avg_ic"])
            cand_lift = _safe_float(results.loc[idx, f"{phase}_active_lift"])
            ctrl_lift = _safe_float(control[f"{phase}_active_lift"])
            results.loc[idx, f"{phase}_ic_delta_vs_{control_name}"] = (
                None if cand_ic is None or ctrl_ic is None else cand_ic - ctrl_ic
            )
            results.loc[idx, f"{phase}_active_lift_delta_vs_{control_name}"] = (
                None if cand_lift is None or ctrl_lift is None else cand_lift - ctrl_lift
            )
    return results


def _build_additive_results(frame: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "variant_name": "core_baseline",
            "variant_type": "baseline",
            "state_name": None,
            "weight": 0.0,
            "score_col": "core_baseline",
        }
    ]
    for state_name, state_type in ADDITIVE_SPECS:
        for weight in OVERLAY_WEIGHTS:
            suffix = int(round(weight * 100))
            rows.append(
                {
                    "variant_name": f"core_mul__{state_name}__{suffix:02d}",
                    "variant_type": state_type,
                    "state_name": state_name,
                    "weight": float(weight),
                    "score_col": f"core_mul__{state_name}__{suffix:02d}",
                }
            )
    results = pd.DataFrame(rows)
    for idx, row in results.iterrows():
        for phase in ("dev", "validation", "confirmation"):
            summary = _score_phase_summary(frame, str(row["score_col"]), phase)
            for key, value in summary.items():
                results.loc[idx, f"{phase}_{key}"] = value

    baseline_row = results.loc[results["variant_name"].eq("core_baseline")].iloc[0]
    for idx, row in results.iterrows():
        if row["variant_name"] == "core_baseline":
            results.loc[idx, "candidate_decision"] = "BASELINE"
            continue
        weight = float(row["weight"])
        matched = results.loc[
            results["state_name"].eq("event_today_follow20") & results["weight"].eq(weight),
        ].iloc[0]
        novelty = results.loc[
            results["state_name"].eq("event_today_novel20") & results["weight"].eq(weight),
        ].iloc[0]
        for phase in ("dev", "validation", "confirmation"):
            ic = _safe_float(row[f"{phase}_avg_ic"]) or 0.0
            spread = _safe_float(row[f"{phase}_spread"]) or 0.0
            results.loc[idx, f"{phase}_ic_delta_vs_baseline"] = ic - (_safe_float(baseline_row[f"{phase}_avg_ic"]) or 0.0)
            results.loc[idx, f"{phase}_spread_delta_vs_baseline"] = spread - (_safe_float(baseline_row[f"{phase}_spread"]) or 0.0)
            results.loc[idx, f"{phase}_ic_delta_vs_matched_control"] = ic - (_safe_float(matched[f"{phase}_avg_ic"]) or 0.0)
            results.loc[idx, f"{phase}_ic_delta_vs_novelty_control"] = ic - (_safe_float(novelty[f"{phase}_avg_ic"]) or 0.0)

        val_ic_base = _safe_float(results.loc[idx, "validation_ic_delta_vs_baseline"]) or 0.0
        conf_ic_base = _safe_float(results.loc[idx, "confirmation_ic_delta_vs_baseline"]) or 0.0
        val_spread_base = _safe_float(results.loc[idx, "validation_spread_delta_vs_baseline"]) or 0.0
        conf_spread_base = _safe_float(results.loc[idx, "confirmation_spread_delta_vs_baseline"]) or 0.0
        val_ic_matched = _safe_float(results.loc[idx, "validation_ic_delta_vs_matched_control"]) or 0.0
        conf_ic_matched = _safe_float(results.loc[idx, "confirmation_ic_delta_vs_matched_control"]) or 0.0
        val_ic_novelty = _safe_float(results.loc[idx, "validation_ic_delta_vs_novelty_control"]) or 0.0
        conf_ic_novelty = _safe_float(results.loc[idx, "confirmation_ic_delta_vs_novelty_control"]) or 0.0

        pass_condition = bool(
            row["variant_type"] == "candidate"
            and val_ic_base >= 0.002
            and val_spread_base >= 0.002
            and val_ic_matched >= 0.002
            and val_ic_novelty >= 0.0
            and conf_ic_base >= 0.0
            and conf_spread_base >= 0.0
            and conf_ic_matched >= 0.0
            and conf_ic_novelty >= -0.001
        )
        mixed_condition = bool(
            row["variant_type"] == "candidate"
            and not pass_condition
            and val_ic_base > 0.0
            and val_ic_matched > 0.0
            and conf_ic_base >= -0.001
            and conf_ic_matched >= -0.001
        )
        if row["variant_type"] == "candidate":
            results.loc[idx, "candidate_decision"] = "PASSED" if pass_condition else "MIXED" if mixed_condition else "FAILED"
        else:
            results.loc[idx, "candidate_decision"] = "CONTROL"
    return results


def main() -> int:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    panel = _load_panel()
    standalone = _build_standalone_results(panel)
    additive = _build_additive_results(panel)

    candidate_rows = additive.loc[additive["variant_type"].eq("candidate")].copy()
    decision_rank = {"PASSED": 0, "MIXED": 1, "FAILED": 2}
    candidate_rows["decision_rank"] = candidate_rows["candidate_decision"].map(decision_rank).fillna(9)
    best_candidate = candidate_rows.sort_values(
        [
            "decision_rank",
            "validation_ic_delta_vs_baseline",
            "validation_ic_delta_vs_matched_control",
            "confirmation_ic_delta_vs_baseline",
            "weight",
        ],
        ascending=[True, False, False, False, True],
    ).iloc[0]
    best_standalone = standalone.loc[standalone["state_name"].eq("today_self_accel_high")].iloc[0]

    if (candidate_rows["candidate_decision"] == "PASSED").any():
        decision = "PASSED"
        branch_decision = (
            "The H321 cascade state clears the additive screen over the frozen S1/C4/C13 core "
            "and matched H310 controls. Advance to a broader library bakeoff."
        )
    elif (candidate_rows["candidate_decision"] == "MIXED").any() or (
        (_safe_float(best_standalone["validation_avg_ic"]) or 0.0) > 0.0
        and (_safe_float(best_standalone["confirmation_avg_ic"]) or 0.0) > 0.0
    ):
        decision = "MIXED"
        branch_decision = (
            "The H321 cascade state remains a strong sparse cohort, but it is not additive enough "
            "over the frozen core to promote. Keep it as offline timing evidence only."
        )
    else:
        decision = "FAILED"
        branch_decision = (
            "The H321 cascade state does not survive standalone or additive promotion checks. "
            "Park the cascade branch on the current data."
        )

    standalone_path = OUT_DIR / f"{ts}_h322_cascade_additive_screen_standalone.parquet"
    additive_path = OUT_DIR / f"{ts}_h322_cascade_additive_screen_additive.parquet"
    panel_path = OUT_DIR / f"{ts}_h322_cascade_additive_screen_panel.parquet"
    details_path = DETAILS_DIR / f"{ts}_research_branch_cascade_additive_screen_details.json"

    standalone.to_parquet(standalone_path, index=False)
    additive.to_parquet(additive_path, index=False)
    panel_columns = [
        "time",
        "ticker",
        "actual",
        "s1_rank",
        "c4_rank",
        "c13_rank",
        "core_baseline",
        *[state_name for state_name, _note, _state_type in STATE_SPECS],
        *[f"core_mul__{state_name}__{int(round(weight * 100)):02d}" for state_name, _ in ADDITIVE_SPECS for weight in OVERLAY_WEIGHTS],
    ]
    panel[panel_columns].to_parquet(panel_path, index=False)

    details = {
        "protocol": PROTOCOL.describe(),
        "best_standalone_state": _json_safe(best_standalone.to_dict()),
        "best_additive_candidate": _json_safe(best_candidate.to_dict()),
        "standalone_results": _json_safe(standalone.to_dict(orient="records")),
        "additive_results": _json_safe(additive.to_dict(orient="records")),
    }
    details_path.write_text(json.dumps(details, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "decision": decision,
        "branch_decision": branch_decision,
        "panel_rows": int(len(panel)),
        "panel_dates": int(panel["time"].nunique()),
        "panel_tickers": int(panel["ticker"].nunique()),
        "best_standalone_state": _json_safe(best_standalone.to_dict()),
        "best_additive_candidate": _json_safe(best_candidate.to_dict()),
    }
    write_run_summary(
        ts=ts,
        mode="research_branch_cascade_additive_screen",
        name="h322_cascade_additive_screen",
        summary=summary,
        artifacts={
            "standalone_results": standalone_path,
            "additive_results": additive_path,
            "panel": panel_path,
            "details": details_path,
        },
        metadata={
            "session": 142,
            "branch_contract": "Only the H321 today_self_accel_high cascade state is eligible for promotion; it must improve a frozen S1/C4/C13 core over both the matched H310 follow-up and H310 novelty controls.",
            "source_summary": H321_SUMMARY_PATH,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
