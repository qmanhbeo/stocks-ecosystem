from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.continuation_exit_research import (
    BASE_CONTINUATION_FEATURES,
    ContinuationModelSpec,
    _phase_metrics,
    fit_continuation_model,
)
from src.intraday_acquisition_research import (
    build_intraday_pilot_bundle,
    list_available_intraday_tickers,
)


REDUCED_SHAPE_FEATURE_COLUMNS = (
    "open_gap_vs_prev_close",
    "first_60m_return",
    "first_60m_range_pct",
    "close_hour_return",
    "close_repair_return",
    "full_session_return",
)

INTRADAY_SHAPE_ATOM_COLUMNS = (
    "first_hour_fade_proxy",
    "weak_open_strong_close_proxy",
    "failed_breakout_proxy",
    "open_drive_then_fade_proxy",
)

FAMILY_SCOPED_BASELINE_MODEL_NAME = "path_core"
FAMILY_SCOPED_SCORE_PREFIX = "family_score__"

FAMILY_CONTRADICTION_MODEL_SPECS = (
    ContinuationModelSpec(name="path_core", feature_columns=tuple(BASE_CONTINUATION_FEATURES)),
    ContinuationModelSpec(name="intraday_atoms", feature_columns=tuple(INTRADAY_SHAPE_ATOM_COLUMNS)),
    ContinuationModelSpec(
        name="intraday_atoms_plus_path",
        feature_columns=tuple(list(BASE_CONTINUATION_FEATURES) + list(INTRADAY_SHAPE_ATOM_COLUMNS)),
    ),
)


@dataclass(frozen=True)
class ReducedShapeFeatureBundle:
    feature_panel: pd.DataFrame
    ticker_summary: pd.DataFrame


@dataclass(frozen=True)
class FamilyScopedContinuationBundle:
    results: pd.DataFrame
    scored_panel: pd.DataFrame


def family_score_column(model_name: str) -> str:
    return f"{FAMILY_SCOPED_SCORE_PREFIX}{str(model_name)}"


def build_reduced_shape_feature_panel(
    *,
    stock_dir: Path,
    start_date: str,
    end_date: str,
    tickers: list[str] | None = None,
) -> ReducedShapeFeatureBundle:
    selected_tickers = list(tickers or list_available_intraday_tickers(stock_dir))
    feature_frames: list[pd.DataFrame] = []
    summary_rows: list[dict[str, object]] = []

    for ticker in selected_tickers:
        bundle = build_intraday_pilot_bundle(
            stock_dir=stock_dir,
            ticker=str(ticker),
            start_date=str(start_date),
            end_date=str(end_date),
        )
        summary_rows.append(bundle.summary_row)
        if bundle.features.empty:
            continue
        feature_frames.append(bundle.features.copy())

    feature_panel = pd.concat(feature_frames, ignore_index=True) if feature_frames else pd.DataFrame()
    ticker_summary = pd.DataFrame(summary_rows)
    return ReducedShapeFeatureBundle(
        feature_panel=feature_panel,
        ticker_summary=ticker_summary,
    )


def summarize_reduced_shape_feature_panel(feature_panel: pd.DataFrame) -> dict[str, float | int | None]:
    if feature_panel.empty:
        return {
            "observed_rows": 0,
            "tickers": 0,
            "complete_day_share": None,
            "midday_window_share": None,
            "open_gap_feature_share": None,
            "first_60m_feature_share": None,
            "close_hour_feature_share": None,
            "full_session_feature_share": None,
        }

    work = feature_panel.copy()
    observed_rows = int(len(work))
    tickers = int(work["ticker"].nunique()) if "ticker" in work.columns else 0

    def _finite_share(column: str) -> float | None:
        if column not in work.columns:
            return None
        numeric = pd.to_numeric(work[column], errors="coerce")
        return float(np.isfinite(numeric.to_numpy(dtype=float)).mean()) if len(numeric) else None

    return {
        "observed_rows": observed_rows,
        "tickers": tickers,
        "complete_day_share": float(pd.to_numeric(work["complete_day"], errors="coerce").fillna(0).mean()) if "complete_day" in work.columns else None,
        "midday_window_share": float(pd.to_numeric(work["has_midday_window"], errors="coerce").fillna(0).mean()) if "has_midday_window" in work.columns else None,
        "open_gap_feature_share": _finite_share("open_gap_vs_prev_close"),
        "first_60m_feature_share": _finite_share("first_60m_return"),
        "close_hour_feature_share": _finite_share("close_hour_return"),
        "full_session_feature_share": _finite_share("full_session_return"),
    }


def merge_reduced_shape_panel(
    panel: pd.DataFrame,
    *,
    feature_panel: pd.DataFrame,
    coverage_frame: pd.DataFrame | None = None,
) -> pd.DataFrame:
    work = panel.copy()
    work["time"] = pd.to_datetime(work["time"], errors="coerce").dt.normalize()

    feature_view = feature_panel.copy()
    if not feature_view.empty:
        feature_view = feature_view.rename(columns={"session_date": "time"})
        feature_view["time"] = pd.to_datetime(feature_view["time"], errors="coerce").dt.normalize()
    merged = work.merge(feature_view, on=["time", "ticker"], how="left")

    if coverage_frame is not None and not coverage_frame.empty:
        coverage_view = coverage_frame.copy()
        coverage_view = coverage_view.rename(columns={"session_date": "time"})
        coverage_view["time"] = pd.to_datetime(coverage_view["time"], errors="coerce").dt.normalize()
        merged = merged.merge(
            coverage_view[["time", "ticker", "coverage_bucket"]].drop_duplicates(),
            on=["time", "ticker"],
            how="left",
        )

    observed = np.zeros(len(merged), dtype=bool)
    for column in REDUCED_SHAPE_FEATURE_COLUMNS:
        if column in merged.columns:
            observed |= np.isfinite(pd.to_numeric(merged[column], errors="coerce").to_numpy(dtype=float))
    merged["intraday_observed"] = observed.astype(bool)
    return merged


def add_intraday_shape_atoms(frame: pd.DataFrame) -> pd.DataFrame:
    work = frame.copy()
    for column in REDUCED_SHAPE_FEATURE_COLUMNS:
        if column not in work.columns:
            work[column] = np.nan
        work[column] = pd.to_numeric(work[column], errors="coerce")

    work["first_hour_fade_proxy"] = work["first_60m_return"] - work["close_hour_return"]
    work["weak_open_strong_close_proxy"] = work["close_repair_return"] - work["first_60m_return"]
    work["failed_breakout_proxy"] = work["first_60m_range_pct"] - work["full_session_return"]
    work["open_drive_then_fade_proxy"] = (
        work["open_gap_vs_prev_close"] + work["first_60m_return"] - work["full_session_return"]
    )
    return work


def fit_family_scoped_continuation_models(
    panel: pd.DataFrame,
    *,
    family_column: str = "entry_thesis_family",
    specs: tuple[ContinuationModelSpec, ...] = FAMILY_CONTRADICTION_MODEL_SPECS,
) -> FamilyScopedContinuationBundle:
    if family_column not in panel.columns:
        raise ValueError(f"Family column {family_column!r} is missing from the continuation panel")

    work = panel.copy()
    results_rows: list[dict[str, object]] = []
    for spec in specs:
        work[family_score_column(spec.name)] = np.nan

    families = sorted(str(value) for value in work[family_column].dropna().unique().tolist())
    for family in families:
        family_frame = work.loc[work[family_column].astype(str) == family].copy()
        phase_counts = (
            family_frame["research_phase"].astype(str).value_counts().to_dict()
            if "research_phase" in family_frame.columns
            else {}
        )
        for spec in specs:
            base_row: dict[str, object] = {
                family_column: family,
                "model_name": spec.name,
                "feature_columns": list(spec.feature_columns),
                "family_row_count": int(len(family_frame)),
                "family_dev_count": int(phase_counts.get("dev", 0)),
                "family_validation_count": int(phase_counts.get("validation", 0)),
                "family_confirmation_count": int(phase_counts.get("confirmation", 0)),
            }
            try:
                fit = fit_continuation_model(family_frame, spec=spec)
            except ValueError as exc:
                base_row["fit_error"] = str(exc)
                results_rows.append(base_row)
                continue

            row = dict(fit.summary_row)
            row.update(base_row)
            results_rows.append(row)
            work.loc[fit.scored_dataset.index, family_score_column(spec.name)] = pd.to_numeric(
                fit.scored_dataset["continuation_prob"],
                errors="coerce",
            ).to_numpy(dtype=float)

    return FamilyScopedContinuationBundle(
        results=pd.DataFrame(results_rows),
        scored_panel=work,
    )


def annotate_family_contradiction_results(
    results: pd.DataFrame,
    *,
    family_column: str = "entry_thesis_family",
    baseline_model_name: str = FAMILY_SCOPED_BASELINE_MODEL_NAME,
    confirmation_pass_floor: float = -0.01,
    confirmation_mixed_floor: float = -0.02,
) -> pd.DataFrame:
    if results.empty:
        return results.copy()

    work = results.copy()
    for column in (
        "validation_auc_delta_vs_family_path_core",
        "validation_top_quintile_delta_vs_family_path_core",
        "confirmation_top_quintile_hold_advantage_vs_family_path_core",
    ):
        work[column] = pd.to_numeric(work.get(column), errors="coerce")
    work["candidate_decision"] = pd.Series(["FAILED"] * len(work), index=work.index, dtype=object)
    work["family_best_candidate_model"] = pd.Series([None] * len(work), index=work.index, dtype=object)
    work["family_best_candidate_decision"] = pd.Series([None] * len(work), index=work.index, dtype=object)
    work["family_router_model"] = pd.Series([None] * len(work), index=work.index, dtype=object)
    work["is_family_best_candidate"] = False
    work["beats_family_path_on_validation"] = False

    for family in sorted(str(value) for value in work[family_column].dropna().unique().tolist()):
        family_mask = work[family_column].astype(str) == family
        family_rows = work.loc[family_mask].copy()
        baseline_rows = family_rows.loc[family_rows["model_name"] == baseline_model_name].copy()
        if baseline_rows.empty:
            continue

        baseline_row = baseline_rows.iloc[0]
        baseline_idx = baseline_row.name
        work.loc[baseline_idx, "candidate_decision"] = "BASELINE"
        work.loc[baseline_idx, "validation_auc_delta_vs_family_path_core"] = 0.0
        work.loc[baseline_idx, "validation_top_quintile_delta_vs_family_path_core"] = 0.0
        work.loc[baseline_idx, "confirmation_top_quintile_hold_advantage_vs_family_path_core"] = 0.0

        baseline_val_auc = pd.to_numeric(baseline_row.get("validation_auc"), errors="coerce")
        baseline_val_tq = pd.to_numeric(
            baseline_row.get("validation_top_quintile_hold_advantage"),
            errors="coerce",
        )
        baseline_conf_tq = pd.to_numeric(
            baseline_row.get("confirmation_top_quintile_hold_advantage"),
            errors="coerce",
        )

        candidate_rows = family_rows.loc[family_rows["model_name"] != baseline_model_name].copy()
        if candidate_rows.empty:
            work.loc[family_mask, "family_router_model"] = baseline_model_name
            continue

        for idx, row in candidate_rows.iterrows():
            val_auc = pd.to_numeric(row.get("validation_auc"), errors="coerce")
            val_tq = pd.to_numeric(row.get("validation_top_quintile_hold_advantage"), errors="coerce")
            conf_tq = pd.to_numeric(row.get("confirmation_top_quintile_hold_advantage"), errors="coerce")
            val_auc_delta = val_auc - baseline_val_auc
            val_tq_delta = val_tq - baseline_val_tq
            conf_tq_delta = conf_tq - baseline_conf_tq

            beats_validation = bool(
                np.isfinite(val_auc_delta)
                and float(val_auc_delta) > 0.0
                and np.isfinite(val_tq_delta)
                and float(val_tq_delta) > 0.0
            )
            passes = bool(
                beats_validation
                and np.isfinite(conf_tq)
                and float(conf_tq) > float(confirmation_pass_floor)
            )
            mixed = bool(
                not passes
                and beats_validation
                and np.isfinite(conf_tq)
                and float(conf_tq) > float(confirmation_mixed_floor)
            )

            work.loc[idx, "validation_auc_delta_vs_family_path_core"] = val_auc_delta
            work.loc[idx, "validation_top_quintile_delta_vs_family_path_core"] = val_tq_delta
            work.loc[idx, "confirmation_top_quintile_hold_advantage_vs_family_path_core"] = conf_tq_delta
            work.loc[idx, "beats_family_path_on_validation"] = beats_validation
            work.loc[idx, "candidate_decision"] = "PASSED" if passes else "MIXED" if mixed else "FAILED"

        ranked = candidate_rows.copy()
        ranked["decision_rank"] = ranked.index.map(
            lambda idx: {"FAILED": 0, "MIXED": 1, "PASSED": 2}.get(str(work.loc[idx, "candidate_decision"]), -1)
        )
        ranked["validation_auc_delta_vs_family_path_core"] = ranked.index.map(
            lambda idx: pd.to_numeric(work.loc[idx, "validation_auc_delta_vs_family_path_core"], errors="coerce")
        )
        ranked["validation_top_quintile_delta_vs_family_path_core"] = ranked.index.map(
            lambda idx: pd.to_numeric(work.loc[idx, "validation_top_quintile_delta_vs_family_path_core"], errors="coerce")
        )
        ranked["confirmation_top_quintile_hold_advantage"] = pd.to_numeric(
            ranked["confirmation_top_quintile_hold_advantage"],
            errors="coerce",
        )
        ranked = ranked.sort_values(
            by=[
                "decision_rank",
                "validation_auc_delta_vs_family_path_core",
                "validation_top_quintile_delta_vs_family_path_core",
                "confirmation_top_quintile_hold_advantage",
                "model_name",
            ],
            ascending=[False, False, False, False, True],
        )

        best_row = ranked.iloc[0]
        best_idx = best_row.name
        best_decision = str(work.loc[best_idx, "candidate_decision"])
        router_model = str(best_row["model_name"]) if best_decision in {"PASSED", "MIXED"} else baseline_model_name

        work.loc[family_mask, "family_best_candidate_model"] = str(best_row["model_name"])
        work.loc[family_mask, "family_best_candidate_decision"] = best_decision
        work.loc[family_mask, "family_router_model"] = router_model
        work.loc[best_idx, "is_family_best_candidate"] = True

    return work


def summarize_family_router_choices(
    results: pd.DataFrame,
    *,
    family_column: str = "entry_thesis_family",
    baseline_model_name: str = FAMILY_SCOPED_BASELINE_MODEL_NAME,
) -> pd.DataFrame:
    if results.empty:
        return pd.DataFrame()

    rows: list[dict[str, object]] = []
    work = results.copy()
    for family in sorted(str(value) for value in work[family_column].dropna().unique().tolist()):
        family_rows = work.loc[work[family_column].astype(str) == family].copy()
        baseline_rows = family_rows.loc[family_rows["model_name"] == baseline_model_name].copy()
        if baseline_rows.empty:
            continue
        baseline_row = baseline_rows.iloc[0]
        best_candidate_values = family_rows["family_best_candidate_model"].dropna()
        best_candidate_name = str(best_candidate_values.iloc[0]) if not best_candidate_values.empty else None
        best_candidate_row = (
            family_rows.loc[family_rows["model_name"] == best_candidate_name].iloc[0]
            if best_candidate_name is not None and not family_rows.loc[family_rows["model_name"] == best_candidate_name].empty
            else baseline_row
        )
        router_model_values = family_rows["family_router_model"].dropna()
        router_model_name = str(router_model_values.iloc[0]) if not router_model_values.empty else baseline_model_name
        family_row_count = pd.to_numeric(baseline_row.get("family_row_count"), errors="coerce")
        family_dev_count = pd.to_numeric(baseline_row.get("family_dev_count"), errors="coerce")
        family_validation_count = pd.to_numeric(baseline_row.get("family_validation_count"), errors="coerce")
        family_confirmation_count = pd.to_numeric(baseline_row.get("family_confirmation_count"), errors="coerce")
        rows.append(
            {
                family_column: family,
                "family_row_count": 0 if pd.isna(family_row_count) else int(family_row_count),
                "family_dev_count": 0 if pd.isna(family_dev_count) else int(family_dev_count),
                "family_validation_count": 0 if pd.isna(family_validation_count) else int(family_validation_count),
                "family_confirmation_count": 0 if pd.isna(family_confirmation_count) else int(family_confirmation_count),
                "baseline_model_name": baseline_model_name,
                "baseline_validation_auc": pd.to_numeric(baseline_row.get("validation_auc"), errors="coerce"),
                "baseline_validation_top_quintile_hold_advantage": pd.to_numeric(
                    baseline_row.get("validation_top_quintile_hold_advantage"),
                    errors="coerce",
                ),
                "baseline_confirmation_top_quintile_hold_advantage": pd.to_numeric(
                    baseline_row.get("confirmation_top_quintile_hold_advantage"),
                    errors="coerce",
                ),
                "best_candidate_model_name": None if best_candidate_name is None else best_candidate_name,
                "best_candidate_decision": best_candidate_row.get("candidate_decision"),
                "best_candidate_validation_auc_delta_vs_path_core": pd.to_numeric(
                    best_candidate_row.get("validation_auc_delta_vs_family_path_core"),
                    errors="coerce",
                ),
                "best_candidate_validation_top_quintile_delta_vs_path_core": pd.to_numeric(
                    best_candidate_row.get("validation_top_quintile_delta_vs_family_path_core"),
                    errors="coerce",
                ),
                "best_candidate_confirmation_top_quintile_hold_advantage": pd.to_numeric(
                    best_candidate_row.get("confirmation_top_quintile_hold_advantage"),
                    errors="coerce",
                ),
                "router_model_name": router_model_name,
                "router_uses_intraday": bool(router_model_name != baseline_model_name),
            }
        )

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    decision_rank = out["best_candidate_decision"].map({"FAILED": 0, "MIXED": 1, "PASSED": 2}).fillna(-1)
    return out.assign(_decision_rank=decision_rank).sort_values(
        by=[
            "_decision_rank",
            "best_candidate_validation_auc_delta_vs_path_core",
            "best_candidate_validation_top_quintile_delta_vs_path_core",
            "best_candidate_confirmation_top_quintile_hold_advantage",
            family_column,
        ],
        ascending=[False, False, False, False, True],
    ).drop(columns="_decision_rank")


def build_family_aware_router_scores(
    scored_panel: pd.DataFrame,
    family_summary: pd.DataFrame,
    *,
    family_column: str = "entry_thesis_family",
    out_column: str = "family_router_prob",
) -> pd.DataFrame:
    work = scored_panel.copy()
    if family_column not in work.columns:
        raise ValueError(f"Family column {family_column!r} is missing from scored_panel")
    if family_summary.empty:
        work[out_column] = np.nan
        return work

    router_scores = pd.Series(np.nan, index=work.index, dtype=float)
    for row in family_summary.itertuples(index=False):
        family = str(getattr(row, family_column))
        router_model_name = str(getattr(row, "router_model_name"))
        score_column = family_score_column(router_model_name)
        if score_column not in work.columns:
            raise ValueError(f"Router score column {score_column!r} is missing from scored_panel")
        family_mask = work[family_column].astype(str) == family
        router_scores.loc[family_mask] = pd.to_numeric(work.loc[family_mask, score_column], errors="coerce")
    work[out_column] = router_scores
    return work


def summarize_continuation_probability_frame(
    frame: pd.DataFrame,
    *,
    prob_column: str,
) -> dict[str, dict[str, float | int | None]]:
    out: dict[str, dict[str, float | int | None]] = {}
    for phase in ("dev", "validation", "confirmation"):
        phase_frame = frame.loc[frame["research_phase"] == phase].copy()
        out[phase] = _phase_metrics(phase_frame, prob_column=prob_column)
    return out
