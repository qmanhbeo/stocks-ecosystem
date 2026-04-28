"""
H351: sector ownership-pressure audit.

Question:
    After ticker-level foreign-flow ranks and simple flow interactions failed,
    does the remaining honest H95 path live at the sector level: foreign
    ownership pressure, sector heat, and room scarcity?

Design:
    - do not retune raw ticker-level foreign-flow windows
    - build a small predeclared sector-level feature set
    - compare against S1 and existing sector anchors (C6 / sector breadth)
    - evaluate only 2015-2025; 2026 is excluded
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
ANALYSIS_DIR = ROOT / "analysis"
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from analysis.h327_cafef_foreign_flow_source_audit import (  # noqa: E402
    CONFIRMATION_END,
    CONFIRMATION_START,
    DEV_END,
    DEV_START,
    MIN_YEARLY_OBS,
    PASS_CORR,
    PASS_IC,
    PASS_PCT_YEARS,
    PREDICTIVE_END,
    PREDICTIVE_START,
    VALIDATION_END,
    VALIDATION_MIN_ABS_IC,
    VALIDATION_START,
    _json_safe,
    load_flow,
    load_stock_panel,
    phase_mask,
    rank_by_day,
    summarize_years,
)
from src.run_summary import write_run_summary  # noqa: E402
from src.standalone_signal_utils import load_s1_frame, spearman_stat  # noqa: E402


SECTOR_PATH = data_path("features/sector_classification.parquet")
SECTOR_ROTATION_PATH = data_path("features/xs_sector_rotation_daily.parquet")
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"

FEATURE_COLS = [
    "xs_sector_ff_pressure_5d_rank",
    "xs_sector_ff_pressure_20d_rank",
    "xs_sector_ff_participation_20d_rank",
    "xs_sector_ff_ownership_level_rank",
    "xs_sector_ff_ownership_delta_20d_rank",
    "xs_sector_ff_pressure_x_heat_5d_rank",
    "xs_sector_ff_pressure_x_room_5d_rank",
]

SECTOR_ANCHORS = [
    "c6_contrarian_intra_5d",
    "xs_sector_breadth_5d",
]

MAX_SECTOR_ANCHOR_CORR = 0.45


def _safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _load_sector_labels() -> pd.DataFrame:
    sector = pd.read_parquet(SECTOR_PATH).rename(columns={"symbol": "ticker"}).copy()
    sector["ticker"] = sector["ticker"].astype(str).str.upper()
    sector["sector_label"] = sector["icb_name3"].fillna(sector["icb_name2"]).fillna("Unknown").astype(str)
    return sector[["ticker", "sector_label"]].drop_duplicates()


def _load_sector_rotation() -> pd.DataFrame:
    rotation = pd.read_parquet(
        SECTOR_ROTATION_PATH,
        columns=["time", "ticker", "xs_sector_mom_5d_rank", "xs_sector_breadth_5d"],
    ).copy()
    rotation["time"] = pd.to_datetime(rotation["time"], errors="coerce").dt.normalize()
    rotation["ticker"] = rotation["ticker"].astype(str).str.upper()
    labels = _load_sector_labels()
    rotation = rotation.merge(labels, on="ticker", how="left", validate="many_to_one")
    return (
        rotation.dropna(subset=["sector_label"])
        .groupby(["time", "sector_label"], as_index=False)
        .agg(
            sector_heat_5d=("xs_sector_mom_5d_rank", "mean"),
            sector_breadth_5d=("xs_sector_breadth_5d", "mean"),
        )
    )


def _rolling_sum_by_sector(frame: pd.DataFrame, column: str, window: int) -> pd.Series:
    return (
        frame.groupby("sector_label", group_keys=False)[column]
        .rolling(window, min_periods=max(3, window // 2))
        .sum()
        .reset_index(level=0, drop=True)
    )


def _build_sector_pressure_panel(flow: pd.DataFrame, stock: pd.DataFrame) -> pd.DataFrame:
    labels = _load_sector_labels()
    merged = stock.merge(flow, on=["time", "ticker"], how="inner", suffixes=("", "_flow"))
    merged = merged.merge(labels, on="ticker", how="left", validate="many_to_one")
    merged = merged.dropna(subset=["sector_label"]).copy()
    merged["traded_value"] = pd.to_numeric(merged["close"], errors="coerce") * pd.to_numeric(
        merged["volume"], errors="coerce"
    )
    merged["foreign_abs_value"] = (
        pd.to_numeric(merged["foreign_buy_value"], errors="coerce").fillna(0.0)
        + pd.to_numeric(merged["foreign_sell_value"], errors="coerce").fillna(0.0)
    )

    sector_daily = (
        merged.groupby(["time", "sector_label"], as_index=False)
        .agg(
            sector_foreign_net_value=("foreign_net_value", "sum"),
            sector_foreign_abs_value=("foreign_abs_value", "sum"),
            sector_traded_value=("traded_value", "sum"),
            sector_foreign_ownership_pct=("foreign_ownership_pct", "median"),
            sector_foreign_room_remaining=("foreign_room_remaining", "median"),
            sector_tickers=("ticker", "nunique"),
        )
        .sort_values(["sector_label", "time"])
        .reset_index(drop=True)
    )

    for window in (5, 20):
        sector_daily[f"sector_net_value_{window}d"] = _rolling_sum_by_sector(
            sector_daily, "sector_foreign_net_value", window
        )
        sector_daily[f"sector_traded_value_{window}d"] = _rolling_sum_by_sector(
            sector_daily, "sector_traded_value", window
        )
    sector_daily["sector_abs_value_20d"] = _rolling_sum_by_sector(
        sector_daily, "sector_foreign_abs_value", 20
    )
    sector_daily["sector_ff_pressure_5d"] = sector_daily["sector_net_value_5d"] / sector_daily[
        "sector_traded_value_5d"
    ].replace(0, np.nan)
    sector_daily["sector_ff_pressure_20d"] = sector_daily["sector_net_value_20d"] / sector_daily[
        "sector_traded_value_20d"
    ].replace(0, np.nan)
    sector_daily["sector_ff_participation_20d"] = sector_daily["sector_abs_value_20d"] / sector_daily[
        "sector_traded_value_20d"
    ].replace(0, np.nan)
    sector_daily["sector_ff_ownership_delta_20d"] = sector_daily.groupby("sector_label", group_keys=False)[
        "sector_foreign_ownership_pct"
    ].diff(20)

    heat = _load_sector_rotation()
    sector_daily = sector_daily.merge(heat, on=["time", "sector_label"], how="left", validate="one_to_one")
    sector_daily["sector_ff_pressure_x_heat_5d"] = (
        sector_daily["sector_ff_pressure_5d"] * sector_daily["sector_heat_5d"]
    )
    sector_daily["sector_ff_pressure_x_room_5d"] = (
        sector_daily["sector_ff_pressure_5d"] * sector_daily["sector_foreign_ownership_pct"]
    )

    panel = merged[["time", "ticker", "sector_label"]].drop_duplicates()
    panel = panel.merge(
        sector_daily[
            [
                "time",
                "sector_label",
                "sector_ff_pressure_5d",
                "sector_ff_pressure_20d",
                "sector_ff_participation_20d",
                "sector_foreign_ownership_pct",
                "sector_ff_ownership_delta_20d",
                "sector_ff_pressure_x_heat_5d",
                "sector_ff_pressure_x_room_5d",
                "sector_heat_5d",
                "sector_breadth_5d",
                "sector_tickers",
            ]
        ],
        on=["time", "sector_label"],
        how="left",
        validate="many_to_one",
    )

    rank_specs = [
        ("sector_ff_pressure_5d", "xs_sector_ff_pressure_5d_rank"),
        ("sector_ff_pressure_20d", "xs_sector_ff_pressure_20d_rank"),
        ("sector_ff_participation_20d", "xs_sector_ff_participation_20d_rank"),
        ("sector_foreign_ownership_pct", "xs_sector_ff_ownership_level_rank"),
        ("sector_ff_ownership_delta_20d", "xs_sector_ff_ownership_delta_20d_rank"),
        ("sector_ff_pressure_x_heat_5d", "xs_sector_ff_pressure_x_heat_5d_rank"),
        ("sector_ff_pressure_x_room_5d", "xs_sector_ff_pressure_x_room_5d_rank"),
    ]
    ranked = panel[["time", "ticker", "sector_label", "sector_heat_5d", "sector_breadth_5d", "sector_tickers"]].copy()
    for source_col, output_col in rank_specs:
        ranked = ranked.merge(rank_by_day(panel, source_col, output_col, ascending=True), on=["time", "ticker"])
    return ranked


def _load_s1_with_sector_anchors() -> pd.DataFrame:
    s1 = load_s1_frame()
    matrix = pd.read_parquet(
        data_path("features/xs_rl_signal_matrix.parquet"),
        columns=["time", "ticker", "c6_contrarian_intra_5d"],
    ).copy()
    matrix["time"] = pd.to_datetime(matrix["time"], errors="coerce").dt.normalize()
    matrix["ticker"] = matrix["ticker"].astype(str).str.upper()
    rotation = pd.read_parquet(
        SECTOR_ROTATION_PATH,
        columns=["time", "ticker", "xs_sector_breadth_5d"],
    ).copy()
    rotation["time"] = pd.to_datetime(rotation["time"], errors="coerce").dt.normalize()
    rotation["ticker"] = rotation["ticker"].astype(str).str.upper()
    return (
        s1.merge(matrix, on=["time", "ticker"], how="left", validate="one_to_one")
        .merge(rotation, on=["time", "ticker"], how="left", validate="one_to_one")
    )


def _ic_for_frame(frame: pd.DataFrame, feature_col: str) -> dict[str, object]:
    clean = frame[[feature_col, "actual"]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < MIN_YEARLY_OBS or clean[feature_col].nunique() < 3:
        return {"n": int(len(clean)), "avg_ic": None, "p_value": None}
    stat = spearmanr(clean[feature_col], clean["actual"])
    return {
        "n": int(len(clean)),
        "avg_ic": float(np.asarray(stat.statistic).flat[0]),
        "p_value": float(np.asarray(stat.pvalue).flat[0]),
    }


def _yearly_ic(frame: pd.DataFrame, feature_col: str, phase: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for year, group in frame.groupby(frame["time"].dt.year):
        clean = group[[feature_col, "actual"]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(clean) < MIN_YEARLY_OBS or clean[feature_col].nunique() < 3:
            continue
        stat = spearmanr(clean[feature_col], clean["actual"])
        rows.append(
            {
                "phase": phase,
                "feature": feature_col,
                "year": int(year),
                "n": int(len(clean)),
                "ic": float(np.asarray(stat.statistic).flat[0]),
                "p_value": float(np.asarray(stat.pvalue).flat[0]),
            }
        )
    return rows


def _max_anchor_corr(frame: pd.DataFrame, feature_col: str) -> tuple[float | None, str | None, dict[str, float | None]]:
    corr_by_anchor: dict[str, float | None] = {}
    for anchor in SECTOR_ANCHORS:
        if anchor not in frame.columns:
            corr_by_anchor[anchor] = None
        else:
            corr_by_anchor[anchor] = spearman_stat(frame[feature_col], frame[anchor])
    finite = {key: value for key, value in corr_by_anchor.items() if value is not None and np.isfinite(value)}
    if not finite:
        return None, None, corr_by_anchor
    best_anchor, best_value = max(finite.items(), key=lambda item: abs(float(item[1])))
    return float(abs(best_value)), best_anchor, corr_by_anchor


def evaluate_features(merged: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    result_rows: list[dict[str, object]] = []
    yearly_rows: list[dict[str, object]] = []
    phase_specs = {
        "dev_2015_2022": (DEV_START, DEV_END),
        "validation_2023_2024": (VALIDATION_START, VALIDATION_END),
        "confirmation_2025": (CONFIRMATION_START, CONFIRMATION_END),
        "full_2015_2025": (PREDICTIVE_START, PREDICTIVE_END),
    }

    for feature_col in FEATURE_COLS:
        phase_stats: dict[str, dict[str, object]] = {}
        phase_years: dict[str, list[dict[str, object]]] = {}
        for phase, (start, end) in phase_specs.items():
            phase_frame = merged.loc[phase_mask(merged, start, end)].copy()
            stats = _ic_for_frame(phase_frame, feature_col)
            years = _yearly_ic(phase_frame, feature_col, phase)
            phase_stats[phase] = stats
            phase_years[phase] = years
            yearly_rows.extend(years)

        dev_ic = phase_stats["dev_2015_2022"].get("avg_ic")
        direction = 1 if (dev_ic or 0.0) >= 0 else -1
        dev_year_summary = summarize_years(phase_years["dev_2015_2022"], direction=direction)
        validation_ic = phase_stats["validation_2023_2024"].get("avg_ic")
        confirmation_ic = phase_stats["confirmation_2025"].get("avg_ic")
        corr_s1 = spearman_stat(merged[feature_col], merged["xs_proba"])
        max_anchor_corr, max_anchor_name, anchor_corrs = _max_anchor_corr(merged, feature_col)

        dev_gate = (
            abs(dev_ic or 0.0) >= PASS_IC
            and (dev_year_summary.get("pct_directional_years") or 0.0) >= PASS_PCT_YEARS
        )
        validation_gate = validation_ic is not None and direction * validation_ic >= VALIDATION_MIN_ABS_IC
        confirmation_ok = confirmation_ic is not None and direction * confirmation_ic > 0.0
        corr_gate = abs(corr_s1) < PASS_CORR
        sector_redundancy_gate = (
            max_anchor_corr is None or float(max_anchor_corr) < MAX_SECTOR_ANCHOR_CORR
        )
        candidate_gate = bool(dev_gate and validation_gate and confirmation_ok and corr_gate and sector_redundancy_gate)
        redundant_candidate = bool(dev_gate and validation_gate and confirmation_ok and corr_gate and not sector_redundancy_gate)
        result_rows.append(
            {
                "feature": feature_col,
                "direction": "positive" if direction > 0 else "negative",
                "coverage": float(merged[feature_col].notna().mean()),
                "corr_with_s1": corr_s1,
                "max_sector_anchor_corr": max_anchor_corr,
                "max_sector_anchor": max_anchor_name,
                "sector_anchor_corrs_json": json.dumps(_json_safe(anchor_corrs), sort_keys=True),
                "dev_avg_ic": dev_ic,
                "dev_n": phase_stats["dev_2015_2022"].get("n"),
                "dev_years": dev_year_summary.get("years"),
                "dev_directional_years": dev_year_summary.get("directional_years"),
                "dev_pct_directional_years": dev_year_summary.get("pct_directional_years"),
                "validation_avg_ic": validation_ic,
                "validation_n": phase_stats["validation_2023_2024"].get("n"),
                "confirmation_avg_ic": confirmation_ic,
                "confirmation_n": phase_stats["confirmation_2025"].get("n"),
                "full_avg_ic": phase_stats["full_2015_2025"].get("avg_ic"),
                "full_n": phase_stats["full_2015_2025"].get("n"),
                "dev_gate": dev_gate,
                "validation_gate": validation_gate,
                "confirmation_ok": confirmation_ok,
                "corr_gate": corr_gate,
                "sector_redundancy_gate": sector_redundancy_gate,
                "candidate_gate": candidate_gate,
                "redundant_candidate": redundant_candidate,
            }
        )

    results = pd.DataFrame(result_rows)
    yearly = pd.DataFrame(yearly_rows)
    if not results.empty:
        results["abs_validation_ic"] = results["validation_avg_ic"].abs()
        results["abs_dev_ic"] = results["dev_avg_ic"].abs()
        results = results.sort_values(
            [
                "candidate_gate",
                "redundant_candidate",
                "abs_validation_ic",
                "abs_dev_ic",
                "feature",
            ],
            ascending=[False, False, False, False, True],
        ).reset_index(drop=True)

    passing = results.loc[results["candidate_gate"]].copy()
    redundant = results.loc[results["redundant_candidate"]].copy()
    summary = {
        "merged_rows": int(len(merged)),
        "merged_tickers": int(merged["ticker"].nunique()) if not merged.empty else 0,
        "merged_dates": int(merged["time"].nunique()) if not merged.empty else 0,
        "feature_count": int(len(FEATURE_COLS)),
        "passing_features": passing["feature"].tolist() if not passing.empty else [],
        "redundant_candidates": redundant["feature"].tolist() if not redundant.empty else [],
        "best_feature": _json_safe(results.iloc[0].to_dict()) if not results.empty else {},
    }
    return results, yearly, summary


def _print_results(results: pd.DataFrame) -> None:
    cols = [
        "feature",
        "direction",
        "dev_avg_ic",
        "validation_avg_ic",
        "confirmation_avg_ic",
        "corr_with_s1",
        "max_sector_anchor_corr",
        "candidate_gate",
        "redundant_candidate",
    ]
    print("\nH351: SECTOR OWNERSHIP-PRESSURE AUDIT")
    print(results[cols].to_string(index=False))


def main() -> int:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    flow = load_flow()
    stock = load_stock_panel()
    sector_panel = _build_sector_pressure_panel(flow, stock)
    s1 = _load_s1_with_sector_anchors()
    merged = s1.merge(sector_panel, on=["time", "ticker"], how="inner")
    merged = merged.loc[phase_mask(merged, PREDICTIVE_START, PREDICTIVE_END)].copy()
    if (merged["time"].dt.year >= 2026).any():
        raise ValueError("H351 predictive panel unexpectedly includes 2026+ rows")

    results, yearly, predictive_summary = evaluate_features(merged)
    results_path = OUT_DIR / f"{ts}_h351_sector_ownership_pressure_results.parquet"
    yearly_path = OUT_DIR / f"{ts}_h351_sector_ownership_pressure_yearly_ic.parquet"
    details_path = DETAILS_DIR / f"{ts}_h351_sector_ownership_pressure_details.json"
    results.to_parquet(results_path, index=False)
    yearly.to_parquet(yearly_path, index=False)

    passing_features = predictive_summary.get("passing_features") or []
    redundant_candidates = predictive_summary.get("redundant_candidates") or []
    if passing_features:
        verdict = "PASSED"
        branch_decision = (
            "A sector-level ownership-pressure feature survived the standalone, validation, "
            "confirmation, S1-correlation, and sector-anchor redundancy gates. Next: run "
            "a small redundancy and portfolio-integration audit before publishing anything."
        )
    elif redundant_candidates:
        verdict = "MIXED"
        branch_decision = (
            "A sector ownership-pressure feature had predictive structure but was too close to "
            "existing sector anchors. Keep as offline evidence, not a new branch."
        )
    else:
        verdict = "FAILED"
        branch_decision = (
            "Sector-level ownership pressure does not rescue H95 under the current contract. "
            "Do not keep tuning foreign-flow sector pressure variants without a new target or data source."
        )

    summary = {
        "verdict": verdict,
        "branch_decision": branch_decision,
        "predictive": predictive_summary,
    }
    details_path.write_text(
        json.dumps(
            {
                "summary": summary,
                "features": _json_safe(results.to_dict(orient="records")),
                "yearly_ic": _json_safe(yearly.to_dict(orient="records")),
                "feature_contract": {
                    "features": FEATURE_COLS,
                    "sector_anchor_corr_gate": MAX_SECTOR_ANCHOR_CORR,
                    "sector_anchors": SECTOR_ANCHORS,
                    "predictive_window": f"{PREDICTIVE_START}..{PREDICTIVE_END}",
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    summary_path = write_run_summary(
        ts=ts,
        mode="research_branch_sector_ownership_pressure",
        name="h351_sector_ownership_pressure",
        summary=summary,
        artifacts={
            "feature_results": str(results_path),
            "yearly_ic": str(yearly_path),
            "details": str(details_path),
        },
        metadata={
            "branch_contract": (
                "Sector-level H95 continuation only; no raw ticker-level foreign-flow rank tuning."
            ),
            "foreign_flow": str(data_path("foreign_flow/cafef/foreign_flow_daily.parquet")),
            "sector_classification": str(SECTOR_PATH),
            "sector_rotation": str(SECTOR_ROTATION_PATH),
        },
    )

    _print_results(results)
    print(f"\nverdict={verdict}")
    print(f"branch_decision={branch_decision}")
    print(f"summary={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
