"""
H275: library-grade reduced-shape intraday atom audit.
"""

from __future__ import annotations

import argparse
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
from src.intraday_exit_research import add_intraday_shape_atoms
from src.research_protocol import ResearchProtocol, phase_mask
from src.run_summary import write_run_summary
from src.standalone_signal_utils import PASS_CORR, PASS_IC, PASS_PCT_YEARS, spearman_stat, summarize_ic, yearly_ic


RL_MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
H258_SUMMARY_PATH = ROOT / "artifacts/run_summaries/latest_timing_reduced_shape_intraday_contract_audit.json"
OUT_DIR = ROOT / "artifacts/portfolio_baselines"

INTRADAY_RESTART_PROTOCOL = ResearchProtocol(
    dev_start_year=2023,
    dev_end_year=2023,
    validation_start_year=2024,
    validation_end_year=2024,
    confirmation_year=2025,
    forward_start_year=2026,
)
ANCHOR_COLUMNS = ("s1_proba", "c4_oc_asym_5d", "c12_gap_absorb_3")
MIN_REGRESSION_OBS = 20
CANDIDATE_SIGNAL_SPECS = (
    ("fade_tension_rank", "rank(first_hour_fade_proxy)", "raw"),
    ("failed_breakout_rank", "rank(failed_breakout_proxy)", "raw"),
    ("intraday_shape_core_rank", "mean(fade_rank, failed_breakout_rank, drive_rank)", "raw"),
    ("fade_tension_disagreement", "residual(rank(first_hour_fade_proxy) | S1,C4,C12)", "disagreement"),
    ("intraday_shape_core_disagreement", "residual(shape_core | S1,C4,C12)", "disagreement"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H275: library-grade reduced-shape intraday atom audit")
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--h258-summary", type=str, default=str(H258_SUMMARY_PATH))
    parser.add_argument("--start-year", type=int, default=2023)
    parser.add_argument("--end-year", type=int, default=2025)
    return parser.parse_args()


def _daily_rank(series: pd.Series, time_index: pd.Series, *, ascending: bool = True) -> pd.Series:
    ranked = pd.to_numeric(series, errors="coerce").groupby(time_index, sort=False).rank(
        method="average",
        pct=True,
        ascending=ascending,
    )
    return ranked.astype(float)


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


def _safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _phase_signal_summary(frame: pd.DataFrame, *, signal_column: str, phase: str) -> dict[str, object]:
    scoped = frame.loc[phase_mask(frame, phase, protocol=INTRADAY_RESTART_PROTOCOL)].copy()
    ic_summary = summarize_ic(yearly_ic(scoped, signal_column, "actual"))
    out = {
        "avg_ic": ic_summary.get("avg_ic"),
        "pct_years_positive": ic_summary.get("pct_years_positive"),
        "rows": int(len(scoped)),
        "dates": int(scoped["time"].nunique()) if not scoped.empty else 0,
    }
    for anchor in ANCHOR_COLUMNS:
        out[f"corr_with_{anchor}"] = spearman_stat(scoped[signal_column], scoped[anchor])
    return out


def _decision_row(frame: pd.DataFrame, *, signal_name: str, formula: str, signal_type: str) -> dict[str, object]:
    dev = _phase_signal_summary(frame, signal_column=signal_name, phase="dev")
    validation = _phase_signal_summary(frame, signal_column=signal_name, phase="validation")
    confirmation = _phase_signal_summary(frame, signal_column=signal_name, phase="confirmation")

    dev_max_anchor_corr = max(
        abs(_safe_float(dev.get(f"corr_with_{anchor}")) or 0.0)
        for anchor in ANCHOR_COLUMNS
    )
    dev_gate = bool(
        (_safe_float(dev.get("avg_ic")) or 0.0) > PASS_IC
        and (_safe_float(dev.get("pct_years_positive")) or 0.0) >= PASS_PCT_YEARS
        and float(dev_max_anchor_corr) < PASS_CORR
    )
    validation_ic = _safe_float(validation.get("avg_ic"))
    confirmation_ic = _safe_float(confirmation.get("avg_ic"))

    passes = bool(
        dev_gate
        and validation_ic is not None
        and confirmation_ic is not None
        and validation_ic > PASS_IC
        and confirmation_ic > PASS_IC
    )
    mixed = bool(
        not passes
        and dev_gate
        and validation_ic is not None
        and confirmation_ic is not None
        and validation_ic > 0.0
        and confirmation_ic > 0.0
    )

    row: dict[str, object] = {
        "signal_name": signal_name,
        "formula": formula,
        "signal_type": signal_type,
        "dev_avg_ic": dev.get("avg_ic"),
        "dev_pct_years_positive": dev.get("pct_years_positive"),
        "dev_max_anchor_corr": dev_max_anchor_corr,
        "dev_gate_pass": dev_gate,
        "validation_avg_ic": validation.get("avg_ic"),
        "confirmation_avg_ic": confirmation.get("avg_ic"),
        "candidate_decision": "PASSED" if passes else "MIXED" if mixed else "FAILED",
        "pass_ic_threshold": PASS_IC,
        "pass_corr_threshold": PASS_CORR,
        "pass_pct_years_threshold": PASS_PCT_YEARS,
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
        by=[
            "_decision_rank",
            "validation_avg_ic",
            "confirmation_avg_ic",
            "dev_avg_ic",
            "dev_max_anchor_corr",
            "signal_name",
        ],
        ascending=[False, False, False, False, True, True],
        ignore_index=True,
    ).drop(columns="_decision_rank")


def _print_table(results: pd.DataFrame) -> None:
    print("\n" + "=" * 200)
    print("H275: LIBRARY-GRADE INTRADAY SHAPE ATOMS")
    print("=" * 200)
    print(
        f"{'signal':<34} {'type':<13} {'decision':<8} {'dev_ic':>9} {'dev_max':>9} "
        f"{'val_ic':>9} {'2025_ic':>9} {'corr_s1':>9} {'corr_c4':>9} {'corr_c12':>10}"
    )
    print("-" * 200)
    for row in results.itertuples(index=False):
        print(
            f"{str(row.signal_name):<34} "
            f"{str(row.signal_type):<13} "
            f"{str(row.candidate_decision):<8} "
            f"{(_safe_float(row.dev_avg_ic) or 0.0):>+8.4f} "
            f"{(_safe_float(row.dev_max_anchor_corr) or 0.0):>+8.4f} "
            f"{(_safe_float(row.validation_avg_ic) or 0.0):>+8.4f} "
            f"{(_safe_float(row.confirmation_avg_ic) or 0.0):>+8.4f} "
            f"{(_safe_float(row.dev_corr_with_s1_proba) or 0.0):>+8.4f} "
            f"{(_safe_float(row.dev_corr_with_c4_oc_asym_5d) or 0.0):>+8.4f} "
            f"{(_safe_float(row.dev_corr_with_c12_gap_absorb_3) or 0.0):>+9.4f}"
        )


def main() -> None:
    args = parse_args()
    h258_summary_path = Path(args.h258_summary)
    h258_summary = load_summary_payload(h258_summary_path)
    if not bool(h258_summary.get("summary", {}).get("advance_to_h259", False)):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        write_run_summary(
            ts=ts,
            mode="signal_library_intraday_shape_atoms",
            name="h275_library_grade_intraday_shape_atoms",
            summary={
                "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
                "skipped": True,
                "reason": "H258 did not clear the reduced-shape intraday contract audit",
            },
            artifacts={},
            metadata={"protocol": INTRADAY_RESTART_PROTOCOL.describe()},
        )
        return

    reduced_shape_path = resolve_summary_artifact(h258_summary_path, "reduced_shape_panel")
    reduced_shape = pd.read_parquet(reduced_shape_path)
    reduced_shape = add_intraday_shape_atoms(reduced_shape.rename(columns={"session_date": "time"}))
    reduced_shape["time"] = pd.to_datetime(reduced_shape["time"], errors="coerce").dt.normalize()

    matrix = pd.read_parquet(
        Path(args.matrix),
        columns=["time", "ticker", "actual", "s1_proba", "c4_oc_asym_5d", "c12_gap_absorb_3"],
    )
    matrix["time"] = pd.to_datetime(matrix["time"], errors="coerce").dt.normalize()
    matrix = matrix.loc[matrix["time"].dt.year.between(int(args.start_year), int(args.end_year))].copy()
    if matrix.empty:
        raise ValueError("No matrix rows found in requested year range")

    observed_panel = matrix.merge(
        reduced_shape[
            [
                "time",
                "ticker",
                "first_hour_fade_proxy",
                "failed_breakout_proxy",
                "open_drive_then_fade_proxy",
            ]
        ],
        on=["time", "ticker"],
        how="inner",
        validate="one_to_one",
    )
    if observed_panel.empty:
        raise ValueError("No overlapping observed intraday rows found for H275")

    observed_panel["fade_tension_rank"] = _daily_rank(
        observed_panel["first_hour_fade_proxy"],
        observed_panel["time"],
        ascending=True,
    )
    observed_panel["failed_breakout_rank"] = _daily_rank(
        observed_panel["failed_breakout_proxy"],
        observed_panel["time"],
        ascending=True,
    )
    observed_panel["drive_rank"] = _daily_rank(
        observed_panel["open_drive_then_fade_proxy"],
        observed_panel["time"],
        ascending=True,
    )
    observed_panel["intraday_shape_core_rank"] = observed_panel[
        ["fade_tension_rank", "failed_breakout_rank", "drive_rank"]
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
    if results.empty:
        raise ValueError("H275 produced no candidate results")

    promoted = results.loc[results["candidate_decision"] == "PASSED"].copy()
    mixed = results.loc[results["candidate_decision"] == "MIXED"].copy()
    decision = "PASSED" if not promoted.empty else "MIXED" if not mixed.empty else "FAILED"
    best_candidate = results.iloc[0].to_dict()

    observed_row_count = int(len(observed_panel))
    matrix_row_count = int(len(matrix))
    observed_row_share = float(observed_row_count / matrix_row_count) if matrix_row_count else 0.0
    observed_dates = int(observed_panel["time"].nunique())
    observed_tickers = int(observed_panel["ticker"].nunique())

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h275_library_grade_intraday_shape_atoms_results.parquet"
    panel_path = OUT_DIR / f"{ts}_h275_library_grade_intraday_shape_atoms_scored_panel.parquet"
    results.to_parquet(results_path, index=False)
    observed_panel[
        [
            "time",
            "ticker",
            "actual",
            *ANCHOR_COLUMNS,
            "fade_tension_rank",
            "failed_breakout_rank",
            "intraday_shape_core_rank",
            "fade_tension_disagreement",
            "intraday_shape_core_disagreement",
        ]
    ].to_parquet(panel_path, index=False)

    summary = {
        "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
        "decision": decision,
        "observed_row_count": observed_row_count,
        "matrix_row_count": matrix_row_count,
        "observed_row_share": observed_row_share,
        "observed_dates": observed_dates,
        "observed_tickers": observed_tickers,
        "best_candidate": best_candidate,
        "promoted_offline_state_atoms": promoted[
            [
                "signal_name",
                "signal_type",
                "dev_avg_ic",
                "validation_avg_ic",
                "confirmation_avg_ic",
                "dev_max_anchor_corr",
            ]
        ].to_dict("records"),
        "tested_atoms": results[
            [
                "signal_name",
                "signal_type",
                "candidate_decision",
                "dev_avg_ic",
                "validation_avg_ic",
                "confirmation_avg_ic",
                "dev_max_anchor_corr",
            ]
        ].to_dict("records"),
        "advance_to_signal_library_promotion": bool(decision == "PASSED"),
        "close_library_grade_intraday_shape_atoms_branch": bool(decision == "FAILED"),
    }
    write_run_summary(
        ts=ts,
        mode="signal_library_intraday_shape_atoms",
        name="h275_library_grade_intraday_shape_atoms",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "scored_panel": str(panel_path),
        },
        metadata={
            "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
            "branch_contract": "Observed reduced-shape intraday subset only, 2023-2025 only, standalone signal-library audit vs S1/C4/C12 anchors",
            "intraday_source": str(reduced_shape_path),
        },
    )
    _print_table(results)


if __name__ == "__main__":
    main()
