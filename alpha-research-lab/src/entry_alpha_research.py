from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.repo_paths import artifact_path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.activation_alpha import BENCHMARK_PATH, RL_MATRIX_PATH, STOCK_DIR, TRADABILITY_PATH
from src.additive_selector_research import additive_candidate_deltas, additive_candidate_passes
from src.deterministic_portfolio import simulate_strategy
from src.entry_alpha import (
    ENTRY_ALPHA_CANDIDATE_PANEL_PATH,
    ENTRY_ALPHA_DIR,
    ENTRY_ALPHA_LABELS_CYCLE5_PATH,
    EntryAlphaInputs,
    build_entry_candidate_panel,
    build_entry_labels,
    load_entry_alpha_inputs,
    persist_entry_alpha_artifacts,
)
from src.portfolio_friction_features import build_boolean_matrix
from src.research_protocol import DEFAULT_PROTOCOL, PHASE_ORDER, ResearchProtocol, assign_research_phase
from src.tradability_conditioned_research import compute_phase_portfolio_summary


ENTRY_ALPHA_SCORES_PATH = ENTRY_ALPHA_DIR / "entry_scores_daily.parquet"
ENTRY_ALPHA_OUT_DIR = artifact_path("entry_alpha")

LATEST_H240_SUMMARY_PATH = artifact_path("run_summaries/latest_entry_alpha_single_family_screens.json")
LATEST_H241_SUMMARY_PATH = artifact_path("run_summaries/latest_entry_alpha_compact_model.json")
LATEST_H242_SUMMARY_PATH = artifact_path("run_summaries/latest_entry_alpha_soft_exposure_prior.json")
LATEST_H244_SUMMARY_PATH = artifact_path("run_summaries/latest_entry_alpha_sparse_breadth_protocol.json")


@dataclass(frozen=True)
class EntryScreenSpec:
    name: str
    family: str
    description: str


@dataclass(frozen=True)
class EntryModelSpec:
    name: str
    feature_columns: tuple[str, ...]


@dataclass(frozen=True)
class EntryModelFit:
    spec: EntryModelSpec
    intercept: float
    raw_coefficients: dict[str, float]
    scored_dataset: pd.DataFrame
    summary_row: dict[str, object]


def _write_parquet_atomic(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    frame.to_parquet(temp_path, index=False)
    temp_path.replace(path)


def _pct_rank_by_time(
    frame: pd.DataFrame,
    column: str,
    *,
    ascending: bool = True,
    fill_value: float = 0.5,
) -> pd.Series:
    ranked = pd.to_numeric(frame[column], errors="coerce").groupby(frame["time"], sort=False).rank(
        method="average",
        pct=True,
        ascending=ascending,
    )
    return ranked.fillna(float(fill_value)).astype(float)


def _safe_get_numeric(frame: pd.DataFrame, column: str, *, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.full(len(frame), float(default)), index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(float(default)).astype(float)


def _safe_bool(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.zeros(len(frame), dtype=bool), index=frame.index)
    return frame[column].fillna(False).astype(bool)


def _cached_constant_matches(frame: pd.DataFrame, column: str, expected: object) -> bool:
    if column not in frame.columns:
        return False
    series = frame[column].dropna()
    if series.empty:
        return False
    if isinstance(expected, str):
        return {str(value) for value in series.astype(str).unique()} == {str(expected)}
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.isna().any():
        return False
    return bool(np.allclose(numeric.to_numpy(dtype=float), float(expected), rtol=0.0, atol=1e-12))


def _existing_mtime(path_like: str | Path) -> float | None:
    path = Path(path_like)
    if not path.exists():
        return None
    return float(path.stat().st_mtime)


def _entry_artifact_source_fingerprint(
    entry_inputs: EntryAlphaInputs,
    *,
    matrix_path: Path,
    tradability_path: Path,
    stock_dir: Path,
    benchmark_path: Path,
) -> dict[str, float]:
    fingerprint: dict[str, float] = {}
    for column, path in [
        ("source_matrix_mtime", matrix_path),
        ("source_tradability_mtime", tradability_path),
        ("source_benchmark_mtime", benchmark_path),
    ]:
        mtime = _existing_mtime(path)
        if mtime is not None:
            fingerprint[column] = mtime

    activation_meta_source = str(getattr(entry_inputs, "activation_meta_source", "")).strip()
    if activation_meta_source:
        activation_mtime = _existing_mtime(activation_meta_source)
        if activation_mtime is not None:
            fingerprint["source_activation_meta_mtime"] = activation_mtime

    matrix = getattr(entry_inputs, "matrix", None)
    if isinstance(matrix, pd.DataFrame) and "ticker" in matrix.columns:
        stock_mtimes = []
        for ticker in pd.Index(matrix["ticker"]).dropna().unique():
            mtime = _existing_mtime(Path(stock_dir) / f"gia_lich_su_{ticker}_1D.parquet")
            if mtime is not None:
                stock_mtimes.append(mtime)
        if stock_mtimes:
            fingerprint["source_stock_max_mtime"] = max(stock_mtimes)

    return fingerprint


def load_or_build_entry_artifacts(
    *,
    inputs: EntryAlphaInputs | None = None,
    candidate_panel_path: Path = ENTRY_ALPHA_CANDIDATE_PANEL_PATH,
    labels_path: Path = ENTRY_ALPHA_LABELS_CYCLE5_PATH,
    top_m_max: int = 20,
    top_k: int = 5,
    rebalance_every: int = 5,
    round_trip_cost: float = 0.003,
    required_holding_age: int = 3,
    initial_notional_vnd: float = 100_000_000.0,
    label_edge_buffer: float = 0.0,
    matrix_path: Path = RL_MATRIX_PATH,
    tradability_path: Path = TRADABILITY_PATH,
    stock_dir: Path = STOCK_DIR,
    benchmark_path: Path = BENCHMARK_PATH,
    start_year: int = 2019,
    end_year: int = 2025,
    strategy_name: str = "full_library",
) -> tuple[EntryAlphaInputs, pd.DataFrame, pd.DataFrame]:
    entry_inputs = inputs
    if entry_inputs is None:
        entry_inputs = load_entry_alpha_inputs(
            matrix_path=matrix_path,
            tradability_path=tradability_path,
            stock_dir=stock_dir,
            benchmark_path=benchmark_path,
            start_year=int(start_year),
            end_year=int(end_year),
            strategy_name=str(strategy_name),
            round_trip_cost=float(round_trip_cost),
            required_holding_age=int(required_holding_age),
            initial_notional_vnd=float(initial_notional_vnd),
        )

    source_fingerprint = _entry_artifact_source_fingerprint(
        entry_inputs,
        matrix_path=matrix_path,
        tradability_path=tradability_path,
        stock_dir=stock_dir,
        benchmark_path=benchmark_path,
    )

    rebuild = True
    if candidate_panel_path.exists() and labels_path.exists():
        candidate_panel = pd.read_parquet(candidate_panel_path)
        labels = pd.read_parquet(labels_path)
        candidate_panel["time"] = pd.to_datetime(candidate_panel["time"])
        labels["time"] = pd.to_datetime(labels["time"])
        max_rank = int(pd.to_numeric(candidate_panel.get("candidate_pool_rank"), errors="coerce").max())
        requested_dates = pd.Index(sorted(pd.to_datetime(entry_inputs.matrix["time"]).drop_duplicates()))
        candidate_dates = pd.Index(sorted(pd.to_datetime(candidate_panel["time"]).drop_duplicates()))
        label_dates = pd.Index(sorted(pd.to_datetime(labels["time"]).drop_duplicates()))
        rebuild = (
            max_rank < int(top_m_max)
            or not candidate_dates.equals(requested_dates)
            or not label_dates.equals(requested_dates)
            or not _cached_constant_matches(candidate_panel, "strategy_name", str(strategy_name))
            or not _cached_constant_matches(candidate_panel, "top_k", int(top_k))
            or not _cached_constant_matches(candidate_panel, "rebalance_every", int(rebalance_every))
            or not _cached_constant_matches(candidate_panel, "candidate_round_trip_cost", float(round_trip_cost))
            or not _cached_constant_matches(candidate_panel, "candidate_required_holding_age", int(required_holding_age))
            or not _cached_constant_matches(candidate_panel, "candidate_initial_notional_vnd", float(initial_notional_vnd))
            or not _cached_constant_matches(labels, "horizon_signal_steps", int(rebalance_every))
            or not _cached_constant_matches(labels, "round_trip_cost", float(round_trip_cost))
            or not _cached_constant_matches(labels, "label_edge_buffer", float(label_edge_buffer))
            or any(
                not _cached_constant_matches(candidate_panel, column, value)
                for column, value in source_fingerprint.items()
            )
        )
        if not rebuild:
            return entry_inputs, candidate_panel, labels

    candidate_panel = build_entry_candidate_panel(
        entry_inputs,
        top_m_max=int(top_m_max),
        top_k=int(top_k),
        rebalance_every=int(rebalance_every),
        round_trip_cost=float(round_trip_cost),
        required_holding_age=int(required_holding_age),
        initial_notional_vnd=float(initial_notional_vnd),
    )
    labels = build_entry_labels(
        candidate_panel,
        price_panel=entry_inputs.price_panel,
        benchmark_open=entry_inputs.benchmark_open,
        horizon_signal_steps=int(rebalance_every),
        signal_dates=sorted(pd.to_datetime(entry_inputs.matrix["time"]).drop_duplicates()),
        round_trip_cost=float(round_trip_cost),
        label_edge_buffer=float(label_edge_buffer),
    )
    for column, value in source_fingerprint.items():
        candidate_panel[column] = float(value)
    persist_entry_alpha_artifacts(
        candidate_panel,
        labels,
        candidate_panel_path=candidate_panel_path,
        labels_path=labels_path,
    )
    return entry_inputs, candidate_panel, labels


def prepare_entry_research_panel(
    candidate_panel: pd.DataFrame,
    labels: pd.DataFrame,
    *,
    protocol: ResearchProtocol = DEFAULT_PROTOCOL,
) -> pd.DataFrame:
    label_columns = [
        "entry_execution_date",
        "cycle_exit_date",
        "entry_open_t1",
        "cycle_exit_open",
        "cycle_return_gross",
        "cycle_return_net",
        "cycle_relative_return_vs_vnindex",
        "cycle_relative_return_vs_cash",
        "buy_now_label",
        "label_edge_buffer",
    ]
    work = candidate_panel.copy()
    work["time"] = pd.to_datetime(work["time"])
    mergeable = [column for column in label_columns if column in labels.columns]
    if mergeable:
        work = work.merge(
            labels[["time", "ticker"] + mergeable].copy(),
            on=["time", "ticker"],
            how="left",
            validate="one_to_one",
        )
    work = assign_research_phase(work, date_column="time", protocol=protocol)

    work = work.sort_values(["ticker", "time"]).reset_index(drop=True)
    can_buy = _safe_bool(work, "can_buy_next_open")
    if "release_flag" not in work.columns:
        prev_buy = can_buy.groupby(work["ticker"], sort=False).shift(1).fillna(False).astype(bool)
        work["release_flag"] = (can_buy & ~prev_buy).astype(float)
    work["buyable_score"] = can_buy.astype(float)
    work["selection_score"] = _safe_get_numeric(work, "selection_score", default=0.0)
    work["candidate_pool_rank"] = _safe_get_numeric(work, "candidate_pool_rank", default=np.inf)
    work["tv_to_adv20"] = _safe_get_numeric(work, "tv_to_adv20", default=0.0)
    work["clv"] = _safe_get_numeric(work, "clv", default=0.5).clip(0.0, 1.0)

    work["entry_selection_score_rank"] = _pct_rank_by_time(work, "selection_score")
    work["entry_tv_to_adv20_rank"] = _pct_rank_by_time(work, "tv_to_adv20")
    work["entry_clv_rank"] = _pct_rank_by_time(work, "clv")

    if "gap_to_prev_close" in work.columns:
        work["_gap_down_proxy"] = -_safe_get_numeric(work, "gap_to_prev_close", default=0.0)
        work["entry_gap_down_rank"] = _pct_rank_by_time(work, "_gap_down_proxy")
    else:
        work["entry_gap_down_rank"] = 0.5
    if "ret_1d" in work.columns:
        work["_recent_weakness_proxy"] = -_safe_get_numeric(work, "ret_1d", default=0.0)
        work["entry_recent_weakness_rank"] = _pct_rank_by_time(work, "_recent_weakness_proxy")
    else:
        work["entry_recent_weakness_rank"] = 0.5
    if "c7_ceiling_count_5d" in work.columns:
        work["_low_ceiling_proxy"] = -_safe_get_numeric(work, "c7_ceiling_count_5d", default=0.0)
        work["entry_low_ceiling_rank"] = _pct_rank_by_time(work, "_low_ceiling_proxy")
    else:
        work["entry_low_ceiling_rank"] = 0.5

    for source_column, rank_column in [
        ("c8_vol_zscore_5d", "entry_c8_rank"),
        ("c9_reversal_1d", "entry_c9_rank"),
        ("c12_gap_absorb_3", "entry_c12_rank"),
        ("c14_clv_volconf_resid_rank", "entry_c14_rank"),
        ("breakout_20d", "entry_breakout_rank"),
        ("xs_sector_accel", "entry_sector_accel_rank"),
    ]:
        if source_column in work.columns:
            work[rank_column] = _pct_rank_by_time(work, source_column)
        else:
            work[rank_column] = 0.5

    cleanup = [column for column in ["_gap_down_proxy", "_recent_weakness_proxy", "_low_ceiling_proxy"] if column in work.columns]
    if cleanup:
        work = work.drop(columns=cleanup)
    return work.reset_index(drop=True)


def build_single_family_screen_frame(
    panel: pd.DataFrame,
) -> tuple[pd.DataFrame, list[EntryScreenSpec]]:
    work = panel.copy()
    can_buy = _safe_bool(work, "can_buy_next_open")
    work["screen__impl_liquidity_quality"] = (
        can_buy
        & (_safe_get_numeric(work, "tv_to_adv20", default=0.0) >= 1.10)
        & (_safe_get_numeric(work, "clv", default=0.5) >= 0.45)
    )
    work["screen__impl_release_quality"] = (
        can_buy
        & (_safe_get_numeric(work, "release_flag", default=0.0) > 0.0)
        & (_safe_get_numeric(work, "tv_to_adv20", default=0.0) >= 1.10)
        & (_safe_get_numeric(work, "clv", default=0.5) >= 0.45)
    )
    work["screen__impl_uncrowded_quality"] = (
        can_buy
        & (_safe_get_numeric(work, "entry_low_ceiling_rank", default=0.5) >= 0.60)
        & (_safe_get_numeric(work, "entry_tv_to_adv20_rank", default=0.5) >= 0.55)
        & (_safe_get_numeric(work, "entry_clv_rank", default=0.5) >= 0.55)
    )
    work["screen__price_gap_absorb"] = (
        can_buy
        & (_safe_get_numeric(work, "entry_c12_rank", default=0.5) >= 0.60)
        & (_safe_get_numeric(work, "entry_gap_down_rank", default=0.5) >= 0.55)
    )
    work["screen__price_reversal_quality"] = (
        can_buy
        & (_safe_get_numeric(work, "entry_c9_rank", default=0.5) >= 0.60)
        & (_safe_get_numeric(work, "entry_recent_weakness_rank", default=0.5) >= 0.55)
        & (_safe_get_numeric(work, "entry_clv_rank", default=0.5) >= 0.50)
    )
    work["screen__price_volconf_quality"] = (
        can_buy
        & (_safe_get_numeric(work, "entry_c8_rank", default=0.5) >= 0.55)
        & (_safe_get_numeric(work, "entry_c14_rank", default=0.5) >= 0.55)
    )

    specs = [
        EntryScreenSpec(
            name="screen__impl_liquidity_quality",
            family="implementation",
            description="buyable + decent traded-value participation + acceptable close location",
        ),
        EntryScreenSpec(
            name="screen__impl_release_quality",
            family="implementation",
            description="fresh buyability release with liquidity/CLV confirmation",
        ),
        EntryScreenSpec(
            name="screen__impl_uncrowded_quality",
            family="implementation",
            description="buyable, liquid, and not recently crowded into limit-up pressure",
        ),
        EntryScreenSpec(
            name="screen__price_gap_absorb",
            family="price_state",
            description="gap-down candidate with strong absorb/follow-through profile",
        ),
        EntryScreenSpec(
            name="screen__price_reversal_quality",
            family="price_state",
            description="recent weakness followed by local reversal confirmation",
        ),
        EntryScreenSpec(
            name="screen__price_volconf_quality",
            family="price_state",
            description="volume/CLV residual confirmation among top candidates",
        ),
    ]
    return work, specs


def build_entry_allowed_matrix_from_mask(
    panel: pd.DataFrame,
    *,
    dates: Sequence[pd.Timestamp],
    tickers: Sequence[str],
    mask: pd.Series | np.ndarray | list[bool],
) -> np.ndarray:
    allowed = panel.loc[pd.Series(mask, index=panel.index).fillna(False).astype(bool), ["time", "ticker"]].copy()
    allowed["entry_allowed"] = True
    return build_boolean_matrix(
        allowed,
        value_column="entry_allowed",
        dates=list(pd.to_datetime(dates)),
        tickers=list(tickers),
        fill_value=False,
    )


def apply_date_gate_to_entry_allowed_matrix(
    entry_allowed_matrix: np.ndarray,
    *,
    dates: Sequence[pd.Timestamp],
    allowed_by_date: Mapping[pd.Timestamp, bool],
) -> np.ndarray:
    matrix = np.asarray(entry_allowed_matrix, dtype=bool).copy()
    date_index = pd.Index(pd.to_datetime(list(dates)))
    if matrix.ndim != 2:
        raise ValueError("entry_allowed_matrix must be 2D")
    if matrix.shape[0] != len(date_index):
        raise ValueError(
            "entry_allowed_matrix row count must match dates "
            f"({len(date_index)}); got {matrix.shape[0]}"
        )
    gate = np.asarray(
        [bool(allowed_by_date.get(pd.Timestamp(value), False)) for value in date_index],
        dtype=bool,
    )
    matrix &= gate[:, None]
    return matrix


def build_entry_row_mask(
    panel: pd.DataFrame,
    *,
    top_m: int,
    min_selection_score: float | None = None,
    min_score_gap: float | None = None,
    require_buyable: bool = True,
) -> pd.Series:
    if int(top_m) <= 0:
        raise ValueError("top_m must be > 0")
    work = panel.copy()
    mask = _safe_get_numeric(work, "candidate_pool_rank", default=np.inf) <= float(top_m)
    if min_selection_score is not None:
        mask &= _safe_get_numeric(work, "selection_score", default=np.nan) >= float(min_selection_score)
    if min_score_gap is not None:
        mask &= _safe_get_numeric(work, "selection_score_gap_to_next_candidate", default=np.nan) >= float(min_score_gap)
    if require_buyable:
        mask &= _safe_bool(work, "can_buy_next_open")
    return pd.Series(mask, index=work.index).fillna(False).astype(bool)


def build_entry_allowed_matrix_from_score(
    panel: pd.DataFrame,
    *,
    dates: Sequence[pd.Timestamp],
    tickers: Sequence[str],
    score_column: str,
    top_m: int,
    min_score: float | None = None,
    threshold_by_date: Mapping[pd.Timestamp, float] | None = None,
    top_m_by_date: Mapping[pd.Timestamp, int] | None = None,
    require_buyable: bool = True,
) -> np.ndarray:
    work = panel.copy()
    work["candidate_pool_rank"] = _safe_get_numeric(work, "candidate_pool_rank", default=np.inf)
    if top_m_by_date is None:
        top_m_limit = pd.Series(np.full(len(work), int(top_m)), index=work.index, dtype=float)
    else:
        top_m_limit = work["time"].map(lambda value: top_m_by_date.get(pd.Timestamp(value), int(top_m))).astype(float)
    mask = work["candidate_pool_rank"] <= top_m_limit
    score_values = _safe_get_numeric(work, score_column, default=np.nan)
    if threshold_by_date is not None:
        threshold = work["time"].map(lambda value: threshold_by_date.get(pd.Timestamp(value), np.nan)).astype(float)
        mask &= score_values >= threshold
    elif min_score is not None:
        mask &= score_values >= float(min_score)
    if require_buyable:
        mask &= _safe_bool(work, "can_buy_next_open")
    return build_entry_allowed_matrix_from_mask(
        work,
        dates=dates,
        tickers=tickers,
        mask=mask,
    )


def build_small_book_confirmation_overlay_frame(panel: pd.DataFrame) -> pd.DataFrame:
    work = panel.copy()
    flag_map = {
        "confirm_reversal": "screen__price_reversal_quality",
        "confirm_gap_absorb": "screen__price_gap_absorb",
        "confirm_uncrowded": "screen__impl_uncrowded_quality",
        "confirm_volconf": "screen__price_volconf_quality",
    }
    confirm_columns: list[str] = []
    for out_column, source_column in flag_map.items():
        work[out_column] = _safe_bool(work, source_column)
        confirm_columns.append(out_column)
    count = pd.Series(np.zeros(len(work), dtype=int), index=work.index)
    for column in confirm_columns:
        count = count + work[column].astype(int)
    work["confirm_count"] = count.astype(int)
    work["confirm_any"] = (work["confirm_count"] >= 1).astype(bool)
    work["confirm_consensus"] = (work["confirm_count"] >= 2).astype(bool)
    return work


def build_small_book_threshold_series(
    panel: pd.DataFrame,
    *,
    base_threshold: float,
    confirm_count_column: str = "confirm_count",
    supportive_bonus: float = 0.02,
    consensus_bonus: float = 0.05,
    no_confirm_penalty: float = 0.03,
) -> pd.Series:
    confirm_count = _safe_get_numeric(panel, confirm_count_column, default=0.0)
    threshold = np.where(
        confirm_count >= 2.0,
        float(base_threshold) - float(consensus_bonus),
        np.where(
            confirm_count >= 1.0,
            float(base_threshold) - float(supportive_bonus),
            float(base_threshold) + float(no_confirm_penalty),
        ),
    )
    return pd.Series(np.asarray(threshold, dtype=float), index=panel.index).clip(lower=0.0)


def run_entry_backtest(
    inputs: EntryAlphaInputs,
    *,
    entry_allowed_matrix: np.ndarray,
    round_trip_cost: float,
    required_holding_age: int,
    initial_notional_vnd: float,
    top_k: int | None = None,
    rebalance_every: int | None = None,
    activation_scale: np.ndarray | None = None,
    activation_mask: np.ndarray | None = None,
    incumbent_score_bonus: float = 0.0,
) -> object:
    fee_leg = float(round_trip_cost) / 2.0
    return simulate_strategy(
        strategy_name=inputs.strategy_name,
        signal_columns=list(inputs.signal_columns),
        market_inputs=inputs.market_inputs,
        top_k=int(inputs.top_k if top_k is None else top_k),
        rebalance_every=int(inputs.rebalance_every if rebalance_every is None else rebalance_every),
        weighting="equal",
        initial_notional_vnd=float(initial_notional_vnd),
        max_adv_participation=0.0,
        required_holding_age=int(required_holding_age),
        buy_fee_rate=float(fee_leg),
        sell_fee_rate=float(fee_leg),
        capital_gains_tax_rate=0.0,
        entry_allowed_matrix=entry_allowed_matrix,
        activation_scale=activation_scale,
        activation_mask=activation_mask,
        incumbent_score_bonus=float(incumbent_score_bonus),
    )


def flatten_phase_portfolio_summary(
    phase_summary: Mapping[str, Mapping[str, object]],
    *,
    phases: Sequence[str] = ("dev", "validation", "confirmation", "forward"),
) -> dict[str, object]:
    row: dict[str, object] = {}
    for phase in phases:
        metrics = phase_summary.get(phase, {})
        row[f"{phase}_relative_total_return"] = metrics.get("relative_total_return")
        row[f"{phase}_information_ratio_annualized"] = metrics.get("information_ratio_annualized")
        row[f"{phase}_avg_cash_weight"] = metrics.get("avg_cash_weight")
        row[f"{phase}_avg_daily_turnover"] = metrics.get("avg_daily_turnover")
        row[f"{phase}_days"] = metrics.get("days")
    return row


def backtest_row_from_result(
    *,
    variant: str,
    family: str | None,
    result,
    protocol: ResearchProtocol = DEFAULT_PROTOCOL,
    extra: Mapping[str, object] | None = None,
) -> dict[str, object]:
    phase_summary = compute_phase_portfolio_summary(result.daily, protocol=protocol)
    row = {
        "variant": str(variant),
        "family": family,
        **flatten_phase_portfolio_summary(phase_summary),
        "overall_relative_total_return": result.summary.get("relative_total_return"),
        "overall_information_ratio_annualized": result.summary.get("information_ratio_annualized"),
        "overall_avg_cash_weight": result.summary.get("avg_cash_weight"),
        "overall_avg_num_holdings": result.summary.get("avg_num_holdings"),
        "overall_avg_daily_turnover": result.summary.get("avg_daily_turnover"),
    }
    if extra:
        row.update(extra)
    return row


def sort_entry_results(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return results.copy()
    return results.sort_values(
        by=[
            "promoted",
            "validation_relative_delta",
            "validation_ir_delta",
            "confirmation_relative_delta",
            "variant",
        ],
        ascending=[False, False, False, False, True],
        ignore_index=True,
    )


def add_baseline_deltas(
    results: pd.DataFrame,
    *,
    baseline_variant: str,
) -> pd.DataFrame:
    if results.empty:
        return results.copy()
    work = results.copy()
    baseline = work.loc[work["variant"] == baseline_variant].iloc[0]
    for idx, row in work.iterrows():
        deltas = additive_candidate_deltas(row, baseline)
        for key, value in deltas.items():
            work.loc[idx, key] = value
        work.loc[idx, "promoted"] = False if row["variant"] == baseline_variant else additive_candidate_passes(row, baseline)
    return sort_entry_results(work)


def _top_bucket_mean(
    frame: pd.DataFrame,
    *,
    score_column: str,
    value_column: str,
    q: float = 0.2,
) -> float | None:
    if frame.empty:
        return None
    work = frame[[score_column, value_column]].copy()
    work[score_column] = pd.to_numeric(work[score_column], errors="coerce")
    work[value_column] = pd.to_numeric(work[value_column], errors="coerce")
    work = work.dropna()
    if work.empty:
        return None
    threshold = float(work[score_column].quantile(1.0 - float(q)))
    bucket = work.loc[work[score_column] >= threshold, value_column]
    if bucket.empty:
        return None
    return float(bucket.mean())


def _phase_entry_metrics(
    frame: pd.DataFrame,
    *,
    score_column: str,
) -> dict[str, float | None]:
    if frame.empty:
        return {
            "count": 0,
            "auc": None,
            "positive_rate": None,
            "mean_cycle_return_net": None,
            "top_quintile_cycle_return_net": None,
        }
    work = frame.copy()
    work["buy_now_label"] = pd.to_numeric(work["buy_now_label"], errors="coerce")
    work[score_column] = pd.to_numeric(work[score_column], errors="coerce")
    work["cycle_return_net"] = pd.to_numeric(work["cycle_return_net"], errors="coerce")
    work = work.dropna(subset=[score_column, "cycle_return_net"])
    labeled = work.dropna(subset=["buy_now_label"]).copy()
    auc = None
    positive_rate = None
    if not labeled.empty:
        y = labeled["buy_now_label"].astype(int)
        positive_rate = float(y.mean())
        if y.nunique() >= 2:
            auc = float(roc_auc_score(y, labeled[score_column].astype(float)))
    return {
        "count": int(len(work)),
        "auc": auc,
        "positive_rate": positive_rate,
        "mean_cycle_return_net": float(work["cycle_return_net"].mean()) if not work.empty else None,
        "top_quintile_cycle_return_net": _top_bucket_mean(
            work,
            score_column=score_column,
            value_column="cycle_return_net",
            q=0.2,
        ),
    }


def fit_entry_model(
    panel: pd.DataFrame,
    *,
    spec: EntryModelSpec,
    protocol: ResearchProtocol = DEFAULT_PROTOCOL,
) -> EntryModelFit:
    missing = [column for column in spec.feature_columns if column not in panel.columns]
    if missing:
        raise ValueError(f"Missing entry-model features for {spec.name}: {missing}")

    work = panel.copy()
    for column in spec.feature_columns:
        work[column] = pd.to_numeric(work[column], errors="coerce").fillna(0.0)
    work["buy_now_label"] = pd.to_numeric(work["buy_now_label"], errors="coerce")

    train = work.loc[(work["research_phase"] == "dev") & work["buy_now_label"].notna()].copy()
    if train.empty or train["buy_now_label"].nunique() < 2:
        raise ValueError(f"Insufficient dev labels to fit entry model {spec.name}")

    X_train = train[list(spec.feature_columns)].to_numpy(dtype=np.float64)
    y_train = train["buy_now_label"].astype(int).to_numpy()
    pipeline = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("model", LogisticRegression(max_iter=1000, random_state=0)),
        ]
    )
    pipeline.fit(X_train, y_train)
    scaler = pipeline.named_steps["scaler"]
    model = pipeline.named_steps["model"]
    scales = np.where(np.asarray(scaler.scale_, dtype=np.float64) == 0.0, 1.0, np.asarray(scaler.scale_, dtype=np.float64))
    raw_coef = np.asarray(model.coef_[0], dtype=np.float64) / scales
    raw_intercept = float(
        model.intercept_[0]
        - np.sum(np.asarray(model.coef_[0], dtype=np.float64) * np.asarray(scaler.mean_, dtype=np.float64) / scales)
    )

    X_all = work[list(spec.feature_columns)].to_numpy(dtype=np.float64)
    scored = work.copy()
    score_column = f"entry_prob__{spec.name}"
    scored[score_column] = pipeline.predict_proba(X_all)[:, 1]

    row: dict[str, object] = {
        "model_name": spec.name,
        "feature_columns": list(spec.feature_columns),
        "intercept": raw_intercept,
    }
    for feature_name, coef in zip(spec.feature_columns, raw_coef):
        row[f"coef__{feature_name}"] = float(coef)
    for phase in PHASE_ORDER:
        metrics = _phase_entry_metrics(scored.loc[scored["research_phase"] == phase].copy(), score_column=score_column)
        for key, value in metrics.items():
            row[f"{phase}_{key}"] = value
    row["promoted_label_only"] = bool(
        (row.get("validation_auc") is not None and float(row["validation_auc"]) >= 0.55)
        and (row.get("confirmation_auc") is not None and float(row["confirmation_auc"]) >= 0.52)
        and (
            row.get("validation_top_quintile_cycle_return_net") is not None
            and float(row["validation_top_quintile_cycle_return_net"]) > 0.0
        )
        and (
            row.get("confirmation_top_quintile_cycle_return_net") is not None
            and float(row["confirmation_top_quintile_cycle_return_net"]) > -0.01
        )
    )
    return EntryModelFit(
        spec=spec,
        intercept=raw_intercept,
        raw_coefficients={feature: float(coef) for feature, coef in zip(spec.feature_columns, raw_coef)},
        scored_dataset=scored,
        summary_row=row,
    )


def build_entry_score_panel(model_fits: Sequence[EntryModelFit]) -> pd.DataFrame:
    if not model_fits:
        return pd.DataFrame(columns=["time", "ticker"])
    preferred = [
        "time",
        "ticker",
        "research_phase",
        "buy_now_label",
        "cycle_return_net",
        "selection_score",
        "candidate_pool_rank",
        "activation_state",
        "activation_scale",
        "activation_rel2",
        "can_buy_next_open",
    ]
    available = [column for column in preferred if column in model_fits[0].scored_dataset.columns]
    base = model_fits[0].scored_dataset[available].copy()
    for fit in model_fits:
        score_column = f"entry_prob__{fit.spec.name}"
        base = base.merge(
            fit.scored_dataset[["time", "ticker", score_column]].copy(),
            on=["time", "ticker"],
            how="left",
            validate="one_to_one",
        )
    return base.sort_values(["time", "ticker"]).reset_index(drop=True)


def persist_entry_score_panel(
    score_panel: pd.DataFrame,
    *,
    out_path: Path = ENTRY_ALPHA_SCORES_PATH,
) -> None:
    _write_parquet_atomic(score_panel, out_path)


def default_entry_model_specs(panel: pd.DataFrame) -> list[EntryModelSpec]:
    specs = [
        EntryModelSpec(
            name="implementation_context",
            feature_columns=tuple(
                column
                for column in (
                    "selection_score",
                    "candidate_pool_rank",
                    "tv_to_adv20",
                    "clv",
                    "release_flag",
                    "entry_low_ceiling_rank",
                    "entry_tv_to_adv20_rank",
                    "entry_clv_rank",
                    "activation_rel2",
                )
                if column in panel.columns
            ),
        ),
        EntryModelSpec(
            name="price_state",
            feature_columns=tuple(
                column
                for column in (
                    "selection_score",
                    "candidate_pool_rank",
                    "ret_1d",
                    "ret_3d",
                    "gap_to_prev_close",
                    "breakout_20d",
                    "c9_reversal_1d",
                    "c12_gap_absorb_3",
                    "c14_clv_volconf_resid_rank",
                    "entry_gap_down_rank",
                    "entry_recent_weakness_rank",
                )
                if column in panel.columns
            ),
        ),
        EntryModelSpec(
            name="blend",
            feature_columns=tuple(
                column
                for column in (
                    "selection_score",
                    "candidate_pool_rank",
                    "tv_to_adv20",
                    "clv",
                    "release_flag",
                    "ret_1d",
                    "gap_to_prev_close",
                    "c8_vol_zscore_5d",
                    "c9_reversal_1d",
                    "c12_gap_absorb_3",
                    "c14_clv_volconf_resid_rank",
                    "activation_rel2",
                )
                if column in panel.columns
            ),
        ),
    ]
    return [spec for spec in specs if len(spec.feature_columns) >= 3]


def build_soft_exposure_scale(
    panel: pd.DataFrame,
    *,
    rel2_column: str = "activation_rel2",
    min_scale: float = 0.25,
) -> pd.Series:
    daily_rel2 = (
        panel[["time", rel2_column]].drop_duplicates(subset=["time"]).set_index("time")[rel2_column].sort_index()
    )
    rel2 = pd.to_numeric(daily_rel2, errors="coerce").fillna(0.0)
    normalizer = float(rel2.abs().quantile(0.95))
    if not np.isfinite(normalizer) or normalizer <= 0.0:
        return pd.Series(np.full(len(rel2), 1.0), index=rel2.index, dtype=float)
    normalized = np.clip(rel2 / normalizer, -1.0, 1.0)
    scale = float(min_scale) + (1.0 - float(min_scale)) * (0.5 + 0.5 * normalized)
    return pd.Series(scale, index=rel2.index, dtype=float).clip(float(min_scale), 1.0)


def build_soft_threshold_by_date(
    *,
    base_threshold: float,
    exposure_scale: pd.Series,
    off_penalty: float,
) -> dict[pd.Timestamp, float]:
    return {
        pd.Timestamp(time): float(base_threshold) + float(off_penalty) * (1.0 - float(scale))
        for time, scale in exposure_scale.items()
    }


def build_soft_top_m_by_date(
    *,
    on_top_m: int,
    off_top_m: int,
    exposure_scale: pd.Series,
) -> dict[pd.Timestamp, int]:
    on_top_m = int(on_top_m)
    off_top_m = int(off_top_m)
    if on_top_m <= 0 or off_top_m <= 0:
        raise ValueError("on_top_m and off_top_m must be > 0")
    return {
        pd.Timestamp(time): int(round(off_top_m + (on_top_m - off_top_m) * float(scale)))
        for time, scale in exposure_scale.items()
    }
