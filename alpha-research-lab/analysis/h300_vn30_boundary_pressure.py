"""
H300: VN30 boundary-pressure overlay audit.

Question:
    Can VN30 boundary pressure help as a recipient-state overlay on top of
    existing signals even though standalone VN30 and broad big-name branches failed?
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

from src.research_protocol import DEFAULT_PROTOCOL, phase_mask
from src.run_summary import write_run_summary


MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
VN30_PATH = data_path("features/xs_vn30_rebalancing.parquet")
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"

INTERACTION_FEATURES = [
    ("boundary_rank", "raw_vn30", "rank(xs_vn30_boundary_score)"),
    ("add_pressure_rank", "raw_vn30", "rank(xs_vn30_add_pressure)"),
    ("rank_change_rank", "raw_vn30", "rank(xs_vn30_rank_change_5d)"),
    ("s1_x_boundary", "interaction", "rank(S1) * rank(boundary_score)"),
    ("s1_x_add_pressure", "interaction", "rank(S1) * rank(add_pressure)"),
    ("c13_x_boundary", "interaction", "rank(C13) * rank(boundary_score)"),
    ("c13_x_add_pressure", "interaction", "rank(C13) * rank(add_pressure)"),
]


def _daily_rank(series: pd.Series, time_index: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").groupby(time_index, sort=False).rank(method="average", pct=True)


def _safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _daily_ic_series(df: pd.DataFrame, signal_col: str) -> pd.DataFrame:
    rows = []
    for time, group in df.groupby("time", sort=True):
        gg = group[[signal_col, "actual"]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(gg) < 8 or gg[signal_col].nunique() < 3 or gg["actual"].nunique() < 2:
            continue
        rho = gg[signal_col].corr(gg["actual"], method="spearman")
        if np.isfinite(rho):
            rows.append({"time": pd.Timestamp(time), "ic": float(rho), "n": int(len(gg))})
    return pd.DataFrame(rows)


def _phase_summary(frame: pd.DataFrame, *, signal_col: str, phase: str) -> dict[str, object]:
    scoped = frame.loc[phase_mask(frame, phase, protocol=DEFAULT_PROTOCOL)].copy()
    series = _daily_ic_series(scoped, signal_col)
    return {
        "rows": int(len(scoped)),
        "dates": int(scoped["time"].nunique()) if not scoped.empty else 0,
        "avg_ic": _safe_float(series["ic"].mean()) if not series.empty else None,
        "hit_rate": _safe_float((series["ic"] > 0.0).mean()) if not series.empty else None,
        "days": int(len(series)),
    }


def _feature_row(frame: pd.DataFrame, *, feature_name: str, feature_group: str, formula: str) -> dict[str, object]:
    dev = _phase_summary(frame, signal_col=feature_name, phase="dev")
    validation = _phase_summary(frame, signal_col=feature_name, phase="validation")
    confirmation = _phase_summary(frame, signal_col=feature_name, phase="confirmation")
    pass_condition = bool(
        (_safe_float(validation.get("avg_ic")) or 0.0) > 0.01
        and (_safe_float(confirmation.get("avg_ic")) or 0.0) > 0.0
    )
    mixed_condition = bool(
        not pass_condition
        and (_safe_float(validation.get("avg_ic")) or 0.0) > 0.0
        and (_safe_float(confirmation.get("avg_ic")) or 0.0) >= 0.0
    )
    return {
        "feature_name": feature_name,
        "feature_group": feature_group,
        "formula": formula,
        "candidate_decision": "PASSED" if pass_condition else "MIXED" if mixed_condition else "FAILED",
        "dev_avg_ic": dev.get("avg_ic"),
        "validation_avg_ic": validation.get("avg_ic"),
        "confirmation_avg_ic": confirmation.get("avg_ic"),
        "phase_details": {
            "dev": dev,
            "validation": validation,
            "confirmation": confirmation,
        },
    }


def _cohort_stats(frame: pd.DataFrame, *, signal_col: str, mask_col: str) -> dict[str, object]:
    rows = {}
    for label, scoped in {
        "boundary": frame.loc[frame[mask_col].fillna(False).astype(bool)].copy(),
        "rest": frame.loc[~frame[mask_col].fillna(False).astype(bool)].copy(),
    }.items():
        series = _daily_ic_series(scoped, signal_col)
        rows[label] = {
            "avg_ic": _safe_float(series["ic"].mean()) if not series.empty else None,
            "days": int(len(series)),
            "mean_universe_size": _safe_float(scoped.groupby("time")["ticker"].nunique().mean()) if not scoped.empty else None,
        }
    return rows


def _sort_results(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return results.copy()
    work = results.copy()
    work["_decision_rank"] = work["candidate_decision"].map({"FAILED": 0, "MIXED": 1, "PASSED": 2}).fillna(-1)
    for column in ("validation_avg_ic", "confirmation_avg_ic", "dev_avg_ic"):
        work[column] = pd.to_numeric(work[column], errors="coerce")
    return work.sort_values(
        by=["_decision_rank", "validation_avg_ic", "confirmation_avg_ic", "dev_avg_ic", "feature_name"],
        ascending=[False, False, False, False, True],
        ignore_index=True,
    ).drop(columns="_decision_rank")


def main() -> None:
    matrix = pd.read_parquet(
        MATRIX_PATH,
        columns=["time", "ticker", "actual", "s1_proba", "c13_compress_blowoff_2"],
    ).copy()
    vn30 = pd.read_parquet(
        VN30_PATH,
        columns=["time", "ticker", "xs_vn30_boundary_score", "xs_vn30_rank_change_5d", "xs_vn30_add_pressure"],
    ).copy()
    for frame in (matrix, vn30):
        frame["time"] = pd.to_datetime(frame["time"], errors="coerce").dt.normalize()
    matrix = matrix.loc[matrix["time"].dt.year.between(2015, 2025)].copy()
    vn30 = vn30.loc[vn30["time"].dt.year.between(2015, 2025)].copy()

    panel = matrix.merge(vn30, on=["time", "ticker"], how="inner", validate="one_to_one")
    if panel.empty:
        raise ValueError("No overlapping VN30 boundary rows found for H300")

    panel["boundary_rank"] = _daily_rank(panel["xs_vn30_boundary_score"], panel["time"])
    panel["add_pressure_rank"] = _daily_rank(panel["xs_vn30_add_pressure"], panel["time"])
    panel["rank_change_rank"] = _daily_rank(panel["xs_vn30_rank_change_5d"], panel["time"])
    panel["s1_rank"] = _daily_rank(panel["s1_proba"], panel["time"])
    panel["c13_rank"] = _daily_rank(panel["c13_compress_blowoff_2"], panel["time"])

    panel["s1_x_boundary"] = panel["s1_rank"] * panel["boundary_rank"]
    panel["s1_x_add_pressure"] = panel["s1_rank"] * panel["add_pressure_rank"]
    panel["c13_x_boundary"] = panel["c13_rank"] * panel["boundary_rank"]
    panel["c13_x_add_pressure"] = panel["c13_rank"] * panel["add_pressure_rank"]
    panel["boundary_cohort"] = panel["boundary_rank"] >= 0.80

    rows = [
        _feature_row(panel, feature_name=feature_name, feature_group=feature_group, formula=formula)
        for feature_name, feature_group, formula in INTERACTION_FEATURES
    ]
    results = _sort_results(pd.DataFrame(rows))
    best_interaction = results.loc[results["feature_group"] == "interaction"].iloc[0].to_dict()
    best_raw = results.loc[results["feature_group"] == "raw_vn30"].iloc[0].to_dict()

    cohort_summary = {
        "s1_rank": _cohort_stats(panel, signal_col="s1_rank", mask_col="boundary_cohort"),
        "c13_rank": _cohort_stats(panel, signal_col="c13_rank", mask_col="boundary_cohort"),
    }
    s1_boundary_uplift = (_safe_float(cohort_summary["s1_rank"]["boundary"]["avg_ic"]) or 0.0) - (_safe_float(cohort_summary["s1_rank"]["rest"]["avg_ic"]) or 0.0)
    c13_boundary_uplift = (_safe_float(cohort_summary["c13_rank"]["boundary"]["avg_ic"]) or 0.0) - (_safe_float(cohort_summary["c13_rank"]["rest"]["avg_ic"]) or 0.0)

    pass_condition = bool(
        best_interaction.get("candidate_decision") == "PASSED"
        and (_safe_float(best_interaction.get("validation_avg_ic")) or 0.0) > (_safe_float(best_raw.get("validation_avg_ic")) or 0.0) + 0.01
        and max(s1_boundary_uplift, c13_boundary_uplift) > 0.01
    )
    mixed_condition = bool(
        not pass_condition
        and (
            best_interaction.get("candidate_decision") == "MIXED"
            or (_safe_float(best_interaction.get("validation_avg_ic")) or 0.0) > (_safe_float(best_raw.get("validation_avg_ic")) or 0.0)
            or max(s1_boundary_uplift, c13_boundary_uplift) > 0.0
        )
    )
    verdict = "PASSED" if pass_condition else "MIXED" if mixed_condition else "FAILED"
    branch_decision = {
        "PASSED": "VN30 boundary pressure survives as a narrow recipient overlay on top of existing signals.",
        "MIXED": "Boundary pressure is directionally real but too weak or too local to reopen the VN30 branch broadly.",
        "FAILED": "Close the VN30 recipient-overlay idea; boundary pressure does not survive even as a narrow interaction.",
    }[verdict]

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h300_vn30_boundary_pressure_results.parquet"
    panel_path = OUT_DIR / f"{ts}_h300_vn30_boundary_pressure_panel.parquet"
    details_path = ROOT / "artifacts" / "run_summaries" / f"{ts}_h300_vn30_boundary_pressure_details.json"
    results.to_parquet(results_path, index=False)
    panel.to_parquet(panel_path, index=False)

    summary = {
        "verdict": verdict,
        "hypothesis": (
            "Large-cap level is weak, but VN30 boundary pressure may still matter as a recipient-state overlay "
            "on top of S1 or C13."
        ),
        "best_interaction": best_interaction,
        "best_raw_vn30_feature": best_raw,
        "cohort_summary": cohort_summary,
        "s1_boundary_uplift": s1_boundary_uplift,
        "c13_boundary_uplift": c13_boundary_uplift,
        "tested_rows": results[
            ["feature_name", "feature_group", "candidate_decision", "dev_avg_ic", "validation_avg_ic", "confirmation_avg_ic"]
        ].to_dict("records"),
        "branch_decision": branch_decision,
    }
    details_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    write_run_summary(
        ts=ts,
        mode="research_branch_vn30_boundary_pressure",
        name="h300_vn30_boundary_pressure",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "panel": str(panel_path),
            "details": str(details_path),
        },
        metadata={
            "session": 128,
            "years": [2015, 2025],
        },
    )

    print("H300 VN30 boundary pressure")
    print(
        results[
            ["feature_name", "feature_group", "candidate_decision", "dev_avg_ic", "validation_avg_ic", "confirmation_avg_ic"]
        ].to_string(index=False)
    )
    print(f"\nVerdict: {verdict}")
    print(branch_decision)


if __name__ == "__main__":
    main()
