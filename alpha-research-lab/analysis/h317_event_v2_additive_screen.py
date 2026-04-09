"""
H317: event-v2 additive screen.

Question:
    Do the passed H310 event-v2 states add enough value on top of a frozen
    S1/C4/C13 core score to justify a broader additive promotion screen, or do
    they stay as predictive cohort evidence only?
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

from analysis.h310_event_v2_predictive_rescreen import _build_h310_state_panel, _build_v1_controls


H310_SUMMARY_PATH = ROOT / "artifacts" / "run_summaries" / "latest_research_branch_event_v2_predictive_rescreen.json"
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

OVERLAY_WEIGHTS = (0.15, 0.30)
TOP_QUINTILE = 0.80
BOTTOM_QUINTILE = 0.20
MIN_DAILY_IC_OBS = 8

STATE_SPECS = (
    ("event_today_novel20", "H310 same-day first-public state", "candidate"),
    ("recent5_low_repeat20", "H310 recent low-repeat state", "candidate"),
    ("v1_proxy_5d", "Broad v1 company-event proxy", "control"),
)

ADDITIVE_SPECS = (
    ("event_today_novel20", "candidate"),
    ("recent5_low_repeat20", "candidate"),
    ("v1_proxy_5d", "control"),
)


def _safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _daily_rank(series: pd.Series, time_index: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").groupby(time_index, sort=False).rank(
        method="average",
        pct=True,
        ascending=True,
    )


def _load_panel() -> pd.DataFrame:
    matrix = pd.read_parquet(
        MATRIX_PATH,
        columns=["time", "ticker", "actual", "s1_proba", "c4_oc_asym_5d", "c13_compress_blowoff_2"],
    ).copy()
    matrix["time"] = pd.to_datetime(matrix["time"], errors="coerce").dt.normalize()
    matrix = matrix.loc[matrix["time"].dt.year.between(2023, 2025)].copy()

    first_public_path = resolve_summary_artifact(H310_SUMMARY_PATH, "combined_first_public")
    state_panel, _ = _build_h310_state_panel(matrix[["time", "ticker"]].drop_duplicates(), first_public_path)
    v1 = _build_v1_controls()

    panel = (
        matrix.merge(
            state_panel[["time", "ticker", "event_today_novel20", "recent5_low_repeat20"]],
            on=["time", "ticker"],
            how="left",
            validate="one_to_one",
        )
        .merge(v1, on=["time", "ticker"], how="left", validate="one_to_one")
        .sort_values(["time", "ticker"])
        .reset_index(drop=True)
    )

    for column in ("event_today_novel20", "recent5_low_repeat20", "v1_proxy_5d"):
        panel[column] = panel[column].fillna(False).astype(bool)

    panel["s1_rank"] = _daily_rank(panel["s1_proba"], panel["time"])
    panel["c4_rank"] = _daily_rank(panel["c4_oc_asym_5d"], panel["time"])
    panel["c13_rank"] = _daily_rank(panel["c13_compress_blowoff_2"], panel["time"])
    panel["core_baseline"] = panel[["s1_rank", "c4_rank", "c13_rank"]].mean(axis=1)

    for state_name, _state_type in ADDITIVE_SPECS:
        state_values = panel[state_name].astype(float)
        for weight in OVERLAY_WEIGHTS:
            score_name = f"core_mul__{state_name}__{int(round(weight * 100)):02d}"
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
    active = scoped.loc[scoped[state_col].fillna(False).astype(bool)].copy()
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
    }


def _pooled_corr(series_a: pd.Series, series_b: pd.Series) -> float | None:
    clean = pd.DataFrame({"a": pd.to_numeric(series_a, errors="coerce"), "b": pd.to_numeric(series_b, errors="coerce")}).dropna()
    if len(clean) < 50 or clean["a"].nunique() < 2 or clean["b"].nunique() < 2:
        return None
    rho = clean["a"].corr(clean["b"], method="spearman")
    return _safe_float(rho)


def _build_standalone_results(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for state_name, state_note, state_type in STATE_SPECS:
        row = {"state_name": state_name, "state_note": state_note, "state_type": state_type}
        for phase in ("dev", "validation", "confirmation"):
            summary = _state_phase_summary(frame, state_name, phase)
            for key, value in summary.items():
                row[f"{phase}_{key}"] = value
        row["corr_with_s1"] = _pooled_corr(frame[state_name].astype(float), frame["s1_rank"])
        row["corr_with_c4"] = _pooled_corr(frame[state_name].astype(float), frame["c4_rank"])
        row["corr_with_c13"] = _pooled_corr(frame[state_name].astype(float), frame["c13_rank"])
        rows.append(row)
    return pd.DataFrame(rows)


def _build_additive_results(frame: pd.DataFrame) -> pd.DataFrame:
    baseline = {
        "variant_name": "core_baseline",
        "variant_type": "baseline",
        "state_name": None,
        "weight": 0.0,
        "score_col": "core_baseline",
    }
    rows = [baseline]
    for state_name, state_type in ADDITIVE_SPECS:
        for weight in OVERLAY_WEIGHTS:
            rows.append(
                {
                    "variant_name": f"core_mul__{state_name}__{int(round(weight * 100)):02d}",
                    "variant_type": state_type,
                    "state_name": state_name,
                    "weight": float(weight),
                    "score_col": f"core_mul__{state_name}__{int(round(weight * 100)):02d}",
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
        v1_match = results.loc[
            results["state_name"].eq("v1_proxy_5d") & results["weight"].eq(weight),
        ].iloc[0]

        val_ic_delta_vs_baseline = (_safe_float(row["validation_avg_ic"]) or 0.0) - (_safe_float(baseline_row["validation_avg_ic"]) or 0.0)
        conf_ic_delta_vs_baseline = (_safe_float(row["confirmation_avg_ic"]) or 0.0) - (_safe_float(baseline_row["confirmation_avg_ic"]) or 0.0)
        val_spread_delta_vs_baseline = (_safe_float(row["validation_spread"]) or 0.0) - (_safe_float(baseline_row["validation_spread"]) or 0.0)
        conf_spread_delta_vs_baseline = (_safe_float(row["confirmation_spread"]) or 0.0) - (_safe_float(baseline_row["confirmation_spread"]) or 0.0)
        val_ic_delta_vs_v1 = (_safe_float(row["validation_avg_ic"]) or 0.0) - (_safe_float(v1_match["validation_avg_ic"]) or 0.0)
        conf_ic_delta_vs_v1 = (_safe_float(row["confirmation_avg_ic"]) or 0.0) - (_safe_float(v1_match["confirmation_avg_ic"]) or 0.0)

        results.loc[idx, "validation_ic_delta_vs_baseline"] = val_ic_delta_vs_baseline
        results.loc[idx, "confirmation_ic_delta_vs_baseline"] = conf_ic_delta_vs_baseline
        results.loc[idx, "validation_spread_delta_vs_baseline"] = val_spread_delta_vs_baseline
        results.loc[idx, "confirmation_spread_delta_vs_baseline"] = conf_spread_delta_vs_baseline
        results.loc[idx, "validation_ic_delta_vs_v1_control"] = val_ic_delta_vs_v1
        results.loc[idx, "confirmation_ic_delta_vs_v1_control"] = conf_ic_delta_vs_v1

        pass_condition = bool(
            row["variant_type"] == "candidate"
            and val_ic_delta_vs_baseline >= 0.002
            and val_spread_delta_vs_baseline >= 0.002
            and val_ic_delta_vs_v1 >= 0.002
            and conf_ic_delta_vs_baseline >= 0.0
            and conf_spread_delta_vs_baseline >= 0.0
        )
        mixed_condition = bool(
            row["variant_type"] == "candidate"
            and not pass_condition
            and val_ic_delta_vs_baseline > 0.0
            and val_ic_delta_vs_v1 > 0.0
            and conf_ic_delta_vs_baseline >= -0.001
        )
        results.loc[idx, "candidate_decision"] = "PASSED" if pass_condition else "MIXED" if mixed_condition else "FAILED"
    return results


def _json_safe(value: object):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
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


def main() -> None:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    panel = _load_panel()
    standalone = _build_standalone_results(panel)
    additive = _build_additive_results(panel)

    candidate_rows = additive.loc[additive["variant_type"].eq("candidate")].copy()
    promoted = candidate_rows.loc[candidate_rows["candidate_decision"].eq("PASSED")].copy()
    mixed = candidate_rows.loc[candidate_rows["candidate_decision"].eq("MIXED")].copy()
    best_candidate = (
        candidate_rows.sort_values(
            by=[
                "candidate_decision",
                "validation_ic_delta_vs_baseline",
                "validation_ic_delta_vs_v1_control",
                "confirmation_ic_delta_vs_baseline",
                "variant_name",
            ],
            ascending=[False, False, False, False, True],
            ignore_index=True,
        ).iloc[0].to_dict()
        if not candidate_rows.empty
        else {}
    )
    best_state = (
        standalone.sort_values(
            by=["validation_avg_ic", "confirmation_avg_ic", "validation_active_lift", "state_name"],
            ascending=[False, False, False, True],
            ignore_index=True,
        ).iloc[0].to_dict()
        if not standalone.empty
        else {}
    )

    if not promoted.empty:
        decision = "PASSED"
        branch_decision = (
            "At least one H310 event-v2 state clears the additive screen over the frozen "
            "S1/C4/C13 core and the v1 control; advance to a broader core/full-library bakeoff."
        )
    elif not mixed.empty or (
        (_safe_float(best_state.get("validation_avg_ic")) or 0.0) > 0.0
        and (_safe_float(best_state.get("confirmation_avg_ic")) or 0.0) > 0.0
    ):
        decision = "MIXED"
        branch_decision = (
            "H310 event-v2 states remain predictively real, especially the same-day first-public "
            "state, but they are not additive enough over the frozen core to justify promotion yet."
        )
    else:
        decision = "FAILED"
        branch_decision = (
            "The passed H310 states do not survive as standalone or additive screen candidates on top "
            "of the frozen core; keep the branch as cohort evidence only."
        )

    standalone_path = OUT_DIR / f"{ts}_h317_event_v2_additive_screen_standalone.parquet"
    additive_path = OUT_DIR / f"{ts}_h317_event_v2_additive_screen_additive.parquet"
    panel_path = OUT_DIR / f"{ts}_h317_event_v2_additive_screen_panel.parquet"
    details_path = DETAILS_DIR / f"{ts}_h317_event_v2_additive_screen_details.json"
    standalone.to_parquet(standalone_path, index=False)
    additive.to_parquet(additive_path, index=False)
    panel[
        [
            "time",
            "ticker",
            "actual",
            "s1_rank",
            "c4_rank",
            "c13_rank",
            "core_baseline",
            "event_today_novel20",
            "recent5_low_repeat20",
            "v1_proxy_5d",
            *[f"core_mul__{state_name}__{int(round(weight * 100)):02d}" for state_name, _ in ADDITIVE_SPECS for weight in OVERLAY_WEIGHTS],
        ]
    ].to_parquet(panel_path, index=False)

    details = {
        "protocol": PROTOCOL.describe(),
        "best_standalone_state": best_state,
        "best_additive_candidate": best_candidate,
        "standalone_results": standalone.to_dict(orient="records"),
        "additive_results": additive.to_dict(orient="records"),
    }
    details_path.write_text(json.dumps(_json_safe(details), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    summary = {
        "decision": decision,
        "branch_decision": branch_decision,
        "panel_rows": int(len(panel)),
        "panel_dates": int(panel["time"].nunique()),
        "panel_tickers": int(panel["ticker"].nunique()),
        "best_standalone_state": best_state,
        "best_additive_candidate": best_candidate,
    }
    write_run_summary(
        ts=ts,
        mode="research_branch_event_v2_additive_screen",
        name="h317_event_v2_additive_screen",
        summary=summary,
        artifacts={
            "standalone_results": standalone_path,
            "additive_results": additive_path,
            "panel": panel_path,
            "details": details_path,
        },
        metadata={
            "session": 137,
            "branch_contract": "Only a passed H310 event-v2 state that improves a frozen S1/C4/C13 core over both baseline and v1 control can advance to broader additive promotion work.",
        },
    )


if __name__ == "__main__":
    main()
