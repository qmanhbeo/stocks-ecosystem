"""
H299: intraday library atom audit.

Question:
    Does the reduced-shape CafeF 1H surface survive as standalone daily atoms
    on the observed 2023-2025 subset after the router branch failed?
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
WORKSPACE_ROOT = ROOT.parent
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.additive_selector_research import load_summary_payload, resolve_summary_artifact
from src.intraday_exit_research import REDUCED_SHAPE_FEATURE_COLUMNS, add_intraday_shape_atoms
from src.research_protocol import ResearchProtocol, phase_mask
from src.run_summary import write_run_summary
from src.standalone_signal_utils import spearman_stat


RL_MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
H258_SUMMARY_PATH = ROOT / "artifacts" / "run_summaries/latest_timing_reduced_shape_intraday_contract_audit.json"
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"

PROTOCOL = ResearchProtocol(
    dev_start_year=2023,
    dev_end_year=2023,
    validation_start_year=2024,
    validation_end_year=2024,
    confirmation_year=2025,
    forward_start_year=2026,
)
ANCHOR_COLUMNS = ("s1_proba", "c4_oc_asym_5d", "c13_compress_blowoff_2")
MIN_REGRESSION_OBS = 20

CANDIDATE_SIGNAL_SPECS = (
    ("open_gap_vs_prev_close_rank", "rank(open_gap_vs_prev_close)", "raw"),
    ("first_60m_return_rank", "rank(first_60m_return)", "raw"),
    ("first_60m_range_pct_rank", "rank(first_60m_range_pct)", "raw"),
    ("close_hour_return_rank", "rank(close_hour_return)", "raw"),
    ("close_repair_return_rank", "rank(close_repair_return)", "raw"),
    ("full_session_return_rank", "rank(full_session_return)", "raw"),
    ("fade_tension_rank", "rank(first_hour_fade_proxy)", "atom"),
    ("weak_open_strong_close_rank", "rank(weak_open_strong_close_proxy)", "atom"),
    ("failed_breakout_rank", "rank(failed_breakout_proxy)", "atom"),
    ("open_drive_then_fade_rank", "rank(open_drive_then_fade_proxy)", "atom"),
    ("intraday_shape_core_rank", "mean(fade, failed_breakout, drive)", "atom"),
    ("fade_tension_disagreement", "residual(fade | S1,C4,C13)", "disagreement"),
    ("intraday_shape_core_disagreement", "residual(shape_core | S1,C4,C13)", "disagreement"),
)


def _daily_rank(series: pd.Series, time_index: pd.Series, *, ascending: bool = True) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").groupby(time_index, sort=False).rank(
        method="average",
        pct=True,
        ascending=ascending,
    )


def _residualize_by_day(
    frame: pd.DataFrame,
    *,
    target_column: str,
    control_columns: tuple[str, ...],
    out_column: str,
    min_obs: int = MIN_REGRESSION_OBS,
) -> pd.DataFrame:
    work = frame.copy()
    parts: list[pd.Series] = []
    for _, group in work.groupby("time", sort=False):
        clean = group[[target_column, *control_columns]].replace([np.inf, -np.inf], np.nan).dropna()
        out = pd.Series(np.nan, index=group.index, dtype=float)
        if len(clean) >= int(min_obs):
            x = np.column_stack([np.ones(len(clean), dtype=float)] + [clean[column].to_numpy(dtype=float) for column in control_columns])
            y = clean[target_column].to_numpy(dtype=float)
            beta = np.linalg.lstsq(x, y, rcond=None)[0]
            resid = y - x @ beta
            out.loc[clean.index] = resid
        parts.append(out)
    work[out_column] = pd.concat(parts).sort_index()
    work[out_column] = _daily_rank(work[out_column], work["time"], ascending=True)
    return work


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


def _phase_signal_summary(frame: pd.DataFrame, *, signal_column: str, phase: str) -> dict[str, object]:
    scoped = frame.loc[phase_mask(frame, phase, protocol=PROTOCOL)].copy()
    series = _daily_ic_series(scoped, signal_column)
    yearly = series.assign(year=series["time"].dt.year).groupby("year")["ic"].mean() if not series.empty else pd.Series(dtype=float)
    out = {
        "avg_ic": float(series["ic"].mean()) if not series.empty else None,
        "hit_rate": float((series["ic"] > 0.0).mean()) if not series.empty else None,
        "positive_years": int((yearly > 0.0).sum()) if not yearly.empty else 0,
        "years_present": int(len(yearly)),
        "rows": int(len(scoped)),
        "dates": int(scoped["time"].nunique()) if not scoped.empty else 0,
    }
    for anchor in ANCHOR_COLUMNS:
        out[f"corr_with_{anchor}"] = spearman_stat(scoped[signal_column], scoped[anchor])
    return out


def _safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _decision_row(frame: pd.DataFrame, *, signal_name: str, formula: str, signal_type: str) -> dict[str, object]:
    dev = _phase_signal_summary(frame, signal_column=signal_name, phase="dev")
    validation = _phase_signal_summary(frame, signal_column=signal_name, phase="validation")
    confirmation = _phase_signal_summary(frame, signal_column=signal_name, phase="confirmation")
    dev_max_anchor_corr = max(
        abs(_safe_float(dev.get(f"corr_with_{anchor}")) or 0.0)
        for anchor in ANCHOR_COLUMNS
    )
    pass_condition = bool(
        (_safe_float(dev.get("avg_ic")) or 0.0) > 0.01
        and (_safe_float(validation.get("avg_ic")) or 0.0) > 0.01
        and (_safe_float(confirmation.get("avg_ic")) or 0.0) > 0.0
        and (signal_type == "disagreement" or dev_max_anchor_corr < 0.30)
    )
    mixed_condition = bool(
        not pass_condition
        and (_safe_float(dev.get("avg_ic")) or 0.0) > 0.0
        and (_safe_float(validation.get("avg_ic")) or 0.0) > 0.0
    )
    row = {
        "signal_name": signal_name,
        "formula": formula,
        "signal_type": signal_type,
        "candidate_decision": "PASSED" if pass_condition else "MIXED" if mixed_condition else "FAILED",
        "dev_avg_ic": dev.get("avg_ic"),
        "validation_avg_ic": validation.get("avg_ic"),
        "confirmation_avg_ic": confirmation.get("avg_ic"),
        "dev_max_anchor_corr": dev_max_anchor_corr,
    }
    for prefix, summary in (("dev", dev), ("validation", validation), ("confirmation", confirmation)):
        row[f"{prefix}_rows"] = summary.get("rows")
        row[f"{prefix}_dates"] = summary.get("dates")
        for anchor in ANCHOR_COLUMNS:
            row[f"{prefix}_corr_with_{anchor}"] = summary.get(f"corr_with_{anchor}")
    return row


def _sort_results(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return results.copy()
    work = results.copy()
    work["_decision_rank"] = work["candidate_decision"].map({"FAILED": 0, "MIXED": 1, "PASSED": 2}).fillna(-1)
    for column in ("validation_avg_ic", "confirmation_avg_ic", "dev_avg_ic", "dev_max_anchor_corr"):
        work[column] = pd.to_numeric(work[column], errors="coerce")
    return work.sort_values(
        by=["_decision_rank", "validation_avg_ic", "confirmation_avg_ic", "dev_avg_ic", "signal_name"],
        ascending=[False, False, False, False, True],
        ignore_index=True,
    ).drop(columns="_decision_rank")


def main() -> None:
    h258_payload = load_summary_payload(Path(H258_SUMMARY_PATH))
    if not bool(h258_payload.get("summary", {}).get("advance_to_h259", False)):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        write_run_summary(
            ts=ts,
            mode="research_branch_intraday_library_atoms",
            name="h299_intraday_library_atoms",
            summary={
                "protocol": PROTOCOL.describe(),
                "decision": "SKIP",
                "skipped": True,
                "reason": "H258 did not clear the reduced-shape intraday contract audit",
            },
            artifacts={},
            metadata={"protocol": PROTOCOL.describe()},
        )
        return

    reduced_shape_path = resolve_summary_artifact(Path(H258_SUMMARY_PATH), "reduced_shape_panel")
    reduced_shape = pd.read_parquet(reduced_shape_path)
    reduced_shape = add_intraday_shape_atoms(reduced_shape.rename(columns={"session_date": "time"}))
    reduced_shape["time"] = pd.to_datetime(reduced_shape["time"], errors="coerce").dt.normalize()

    matrix = pd.read_parquet(
        RL_MATRIX_PATH,
        columns=["time", "ticker", "actual", "s1_proba", "c4_oc_asym_5d", "c13_compress_blowoff_2"],
    ).copy()
    matrix["time"] = pd.to_datetime(matrix["time"], errors="coerce").dt.normalize()
    matrix = matrix.loc[matrix["time"].dt.year.between(2023, 2025)].copy()
    observed_panel = matrix.merge(
        reduced_shape[["time", "ticker", *REDUCED_SHAPE_FEATURE_COLUMNS, "first_hour_fade_proxy", "weak_open_strong_close_proxy", "failed_breakout_proxy", "open_drive_then_fade_proxy"]],
        on=["time", "ticker"],
        how="inner",
        validate="one_to_one",
    )
    if observed_panel.empty:
        raise ValueError("No overlapping observed intraday rows found for H299")

    for raw_col in REDUCED_SHAPE_FEATURE_COLUMNS:
        observed_panel[f"{raw_col}_rank"] = _daily_rank(observed_panel[raw_col], observed_panel["time"], ascending=True)
    observed_panel["fade_tension_rank"] = _daily_rank(observed_panel["first_hour_fade_proxy"], observed_panel["time"], ascending=True)
    observed_panel["weak_open_strong_close_rank"] = _daily_rank(observed_panel["weak_open_strong_close_proxy"], observed_panel["time"], ascending=True)
    observed_panel["failed_breakout_rank"] = _daily_rank(observed_panel["failed_breakout_proxy"], observed_panel["time"], ascending=True)
    observed_panel["open_drive_then_fade_rank"] = _daily_rank(observed_panel["open_drive_then_fade_proxy"], observed_panel["time"], ascending=True)
    observed_panel["intraday_shape_core_rank"] = observed_panel[
        ["fade_tension_rank", "failed_breakout_rank", "open_drive_then_fade_rank"]
    ].mean(axis=1)

    observed_panel = _residualize_by_day(
        observed_panel,
        target_column="fade_tension_rank",
        control_columns=ANCHOR_COLUMNS,
        out_column="fade_tension_disagreement",
    )
    observed_panel = _residualize_by_day(
        observed_panel,
        target_column="intraday_shape_core_rank",
        control_columns=ANCHOR_COLUMNS,
        out_column="intraday_shape_core_disagreement",
    )

    rows = [
        _decision_row(observed_panel, signal_name=signal_name, formula=formula, signal_type=signal_type)
        for signal_name, formula, signal_type in CANDIDATE_SIGNAL_SPECS
    ]
    results = _sort_results(pd.DataFrame(rows))
    promoted = results.loc[results["candidate_decision"] == "PASSED"].copy()
    mixed = results.loc[results["candidate_decision"] == "MIXED"].copy()
    decision = "PASSED" if not promoted.empty else "MIXED" if not mixed.empty else "FAILED"
    best_candidate = results.iloc[0].to_dict()

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h299_intraday_library_atoms_results.parquet"
    panel_path = OUT_DIR / f"{ts}_h299_intraday_library_atoms_scored_panel.parquet"
    details_path = ROOT / "artifacts" / "run_summaries" / f"{ts}_h299_intraday_library_atoms_details.json"
    results.to_parquet(results_path, index=False)
    observed_panel.to_parquet(panel_path, index=False)

    summary = {
        "decision": decision,
        "protocol": PROTOCOL.describe(),
        "observed_row_count": int(len(observed_panel)),
        "observed_dates": int(observed_panel["time"].nunique()),
        "observed_tickers": int(observed_panel["ticker"].nunique()),
        "best_candidate": best_candidate,
        "tested_atoms": results[
            ["signal_name", "signal_type", "candidate_decision", "dev_avg_ic", "validation_avg_ic", "confirmation_avg_ic", "dev_max_anchor_corr"]
        ].to_dict("records"),
        "branch_decision": {
            "PASSED": "Reduced-shape atoms survive as a narrow observed-subset offline branch and can advance to candidate-library review.",
            "MIXED": "Only a small disagreement-style residue survives; keep the branch as bounded offline evidence only.",
            "FAILED": "Close reduced-shape intraday atom work on the model side until better intraday data exists.",
        }[decision],
    }
    details_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    write_run_summary(
        ts=ts,
        mode="research_branch_intraday_library_atoms",
        name="h299_intraday_library_atoms",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "scored_panel": str(panel_path),
            "details": str(details_path),
        },
        metadata={
            "session": 128,
            "protocol": PROTOCOL.describe(),
            "intraday_source": str(reduced_shape_path),
        },
    )

    print("H299 intraday library atoms")
    print(
        results[
            [
                "signal_name",
                "signal_type",
                "candidate_decision",
                "dev_avg_ic",
                "validation_avg_ic",
                "confirmation_avg_ic",
                "dev_max_anchor_corr",
            ]
        ].to_string(index=False)
    )
    print(f"\nDecision: {decision}")
    print(summary["branch_decision"])


if __name__ == "__main__":
    main()
