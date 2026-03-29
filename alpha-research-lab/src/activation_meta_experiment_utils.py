from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from src.activation_alpha import (
    ACTIVATION_STATE_PATH,
    BENCHMARK_PATH,
    RL_MATRIX_PATH,
    STOCK_DIR,
    TRADABILITY_PATH,
    load_activation_experiment_inputs,
    run_activation_scenarios,
)
from src.activation_experiment_utils import persist_activation_outputs, print_top_activation_results
from src.activation_meta import ACTIVATION_META_PATH, load_or_build_activation_meta
from src.run_summary import write_run_summary


def selector_prefix(selector) -> str:
    return "full" if getattr(selector, "strategy_name", "") == "full_library" else "s1"


def add_common_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--activation-state", type=str, default=str(ACTIVATION_STATE_PATH))
    parser.add_argument("--activation-meta", type=str, default=str(ACTIVATION_META_PATH))
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--initial-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--top-results", type=int, default=20)
    return parser


def load_meta_bundle(args: argparse.Namespace) -> tuple[object, pd.DataFrame, str]:
    inputs = load_activation_experiment_inputs(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )
    meta_state, meta_source = load_or_build_activation_meta(
        out_path=Path(args.activation_meta),
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        activation_state_path=Path(args.activation_state),
        start_year=2015,
        end_year=int(args.end_year),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.initial_notional_vnd),
    )
    meta_state = meta_state[
        (meta_state["time"].dt.year >= int(args.start_year))
        & (meta_state["time"].dt.year <= int(args.end_year))
    ].copy()
    return inputs, meta_state, meta_source


def pct_rank(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.rank(method="average", pct=True).fillna(0.5).astype(float)


def selector_confidence_series(meta_state: pd.DataFrame, *, prefix: str) -> pd.Series:
    components = [
        pct_rank(meta_state[f"{prefix}_top1_minus_top5_spread"]),
        pct_rank(meta_state[f"{prefix}_top5_mean_score"]),
        pct_rank(meta_state[f"{prefix}_top5_score_std"]),
        pct_rank(meta_state[f"{prefix}_top5_prev_overlap_ratio"]),
    ]
    return sum(components) / float(len(components))


def selector_entry_quality_series(meta_state: pd.DataFrame, *, prefix: str) -> pd.Series:
    return (
        pd.to_numeric(meta_state[f"{prefix}_top5_mean_clv"], errors="coerce").clip(0.0, 1.0).fillna(0.5)
        + pd.to_numeric(meta_state[f"{prefix}_top5_mean_tv_to_adv20_rank"], errors="coerce").clip(0.0, 1.0).fillna(0.5)
        + pd.to_numeric(meta_state[f"{prefix}_top5_buyable_count"], errors="coerce").clip(0.0, 5.0).fillna(0.0) / 5.0
    ) / 3.0


def selector_recent_relative_ewm_from_prev(
    meta_state: pd.DataFrame,
    *,
    prefix: str,
    span: int,
) -> pd.Series:
    prev = pd.to_numeric(meta_state[f"{prefix}_prev_cycle_relative_return"], errors="coerce")
    return prev.ewm(span=int(span), adjust=False, min_periods=1).mean()


def selector_recent_hit_rate_ewm(
    meta_state: pd.DataFrame,
    *,
    prefix: str,
    span: int,
) -> pd.Series:
    return pd.to_numeric(meta_state[f"{prefix}_recent_hit_rate_ewm{int(span)}"], errors="coerce")


def quantile_gate(series: pd.Series, quantile: float, *, operator: str = ">=") -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    threshold = float(numeric.quantile(float(quantile)))
    if operator == ">=":
        return numeric >= threshold
    if operator == "<=":
        return numeric <= threshold
    raise ValueError(f"Unsupported operator {operator!r}")


def threshold_gate(series: pd.Series, threshold: float, *, operator: str = ">=") -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if operator == ">=":
        return numeric >= float(threshold)
    if operator == "<=":
        return numeric <= float(threshold)
    raise ValueError(f"Unsupported operator {operator!r}")


def three_level_schedule(
    series: pd.Series,
    *,
    mid_quantile: float,
    high_quantile: float,
    mid_scale: float = 0.5,
    high_scale: float = 1.0,
) -> pd.Series:
    ranked = pct_rank(series)
    out = pd.Series(np.zeros(len(ranked), dtype=np.float64), index=ranked.index)
    out = out.mask(ranked >= float(mid_quantile), float(mid_scale))
    out = out.mask(ranked >= float(high_quantile), float(high_scale))
    return out.astype(float)


def thresholded_three_state_schedule(
    series: pd.Series,
    *,
    low_threshold: float,
    high_threshold: float,
    low_scale: float = 0.0,
    mid_scale: float = 0.5,
    high_scale: float = 1.0,
) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").fillna(float(low_threshold) - 1e-12)
    out = pd.Series(np.full(len(numeric), float(low_scale), dtype=np.float64), index=numeric.index)
    out = out.mask(numeric >= float(low_threshold), float(mid_scale))
    out = out.mask(numeric >= float(high_threshold), float(high_scale))
    return out.astype(float)


def hysteresis_schedule(
    strong_signal: pd.Series,
    weak_signal: pd.Series,
    *,
    on_streak: int = 2,
    off_streak: int = 2,
    on_scale: float = 1.0,
    off_scale: float = 0.0,
) -> pd.Series:
    strong = strong_signal.fillna(False).astype(bool).tolist()
    weak = weak_signal.fillna(False).astype(bool).tolist()
    state = float(off_scale)
    strong_count = 0
    weak_count = 0
    out: list[float] = []
    for is_strong, is_weak in zip(strong, weak):
        strong_count = strong_count + 1 if is_strong else 0
        weak_count = weak_count + 1 if is_weak else 0
        if state <= float(off_scale) + 1e-12 and strong_count >= int(on_streak):
            state = float(on_scale)
            weak_count = 0
        elif state > float(off_scale) + 1e-12 and weak_count >= int(off_streak):
            state = float(off_scale)
            strong_count = 0
        out.append(state)
    return pd.Series(out, index=strong_signal.index, dtype=float)


def subperiod_relative_return(
    daily: pd.DataFrame,
    *,
    start_year: int | None = None,
    end_year: int | None = None,
) -> float:
    if daily.empty:
        return float("-inf")
    work = daily.copy()
    years = pd.to_datetime(work["execution_date"]).dt.year
    mask = pd.Series(True, index=work.index)
    if start_year is not None:
        mask &= years >= int(start_year)
    if end_year is not None:
        mask &= years <= int(end_year)
    work = work.loc[mask].copy()
    if work.empty:
        return float("-inf")
    portfolio = np.prod(1.0 + pd.to_numeric(work["portfolio_return"], errors="coerce").to_numpy(dtype=np.float64))
    benchmark = np.prod(1.0 + pd.to_numeric(work["benchmark_return"], errors="coerce").to_numpy(dtype=np.float64))
    if not np.isfinite(portfolio) or not np.isfinite(benchmark) or benchmark <= 0.0:
        return float("-inf")
    return float(portfolio / benchmark - 1.0)


def walk_forward_logistic_scores(
    frame: pd.DataFrame,
    *,
    feature_columns: Sequence[str],
    target_column: str,
    min_train_years: int = 2,
) -> pd.Series:
    work = frame.copy()
    work["time"] = pd.to_datetime(work["time"])
    years = work["time"].dt.year
    unique_years = sorted(years.dropna().unique().tolist())
    out = pd.Series(np.nan, index=work.index, dtype=float)
    for pos, year in enumerate(unique_years):
        if pos < int(min_train_years):
            continue
        train_mask = years < int(year)
        test_mask = years == int(year)
        if not bool(test_mask.any()):
            continue
        train = work.loc[train_mask, list(feature_columns) + [target_column]].copy()
        train = train.replace([np.inf, -np.inf], np.nan).dropna()
        test = work.loc[test_mask, list(feature_columns)].copy()
        test = test.replace([np.inf, -np.inf], np.nan)
        if train.empty:
            continue
        y_train = pd.to_numeric(train[target_column], errors="coerce").astype(int)
        if y_train.nunique() < 2:
            out.loc[test_mask] = float(y_train.iloc[0]) if not y_train.empty else 0.0
            continue
        scaler = StandardScaler()
        x_train = scaler.fit_transform(train[list(feature_columns)].to_numpy(dtype=np.float64))
        model = LogisticRegression(
            max_iter=2000,
            class_weight="balanced",
            solver="lbfgs",
            random_state=0,
        )
        model.fit(x_train, y_train.to_numpy(dtype=np.int64))
        test_fill = test.fillna(train[list(feature_columns)].median(numeric_only=True))
        x_test = scaler.transform(test_fill[list(feature_columns)].to_numpy(dtype=np.float64))
        out.loc[test_mask] = model.predict_proba(x_test)[:, 1]
    return out.clip(0.0, 1.0)


def selector_baseline_rows(results: pd.DataFrame) -> dict[str, list[dict[str, object]]]:
    return {
        selector: results.loc[(results["selector_name"] == selector) & (results["gate_name"] == "always_on")]
        .head(1)
        .to_dict(orient="records")
        for selector in results["selector_name"].drop_duplicates().tolist()
    }


def run_and_persist_activation_experiment(
    *,
    args: argparse.Namespace,
    inputs,
    meta_state: pd.DataFrame,
    meta_source: str,
    gates_by_selector: Mapping[str, Mapping[str, pd.Series | np.ndarray]] | None,
    mode: str,
    name: str,
    stem: str,
    title: str,
    extra_summary: Mapping[str, object] | None = None,
    metadata_extra: Mapping[str, object] | None = None,
) -> tuple[pd.DataFrame, dict[tuple[str, str], pd.DataFrame]]:
    results, daily_outputs = run_activation_scenarios(
        activation_state=meta_state,
        market_inputs=inputs.market_inputs,
        selectors=inputs.selectors,
        gates_by_selector=gates_by_selector,
        initial_notional_vnd=float(args.initial_notional_vnd),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
    )
    print_top_activation_results(results, title=title, top_n=int(args.top_results))

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    results_path, best_daily_path = persist_activation_outputs(
        ts=ts,
        stem=stem,
        results=results,
        daily_outputs=daily_outputs,
    )
    best_non_baseline = results.loc[results["gate_name"] != "always_on"].head(1)
    summary = {
        "meta_source": meta_source,
        "best_overall": best_non_baseline.iloc[0].to_dict() if not best_non_baseline.empty else {},
        "selector_baselines": selector_baseline_rows(results),
    }
    if extra_summary:
        summary.update(dict(extra_summary))
    write_run_summary(
        ts=ts,
        mode=mode,
        name=name,
        summary=summary,
        artifacts={
            "results": str(results_path),
            "best_daily": str(best_daily_path) if best_daily_path is not None else None,
        },
        metadata={
            "matrix": str(args.matrix),
            "activation_state": str(args.activation_state),
            "activation_meta": str(args.activation_meta),
            "benchmark": str(args.benchmark),
            "meta_source": meta_source,
            **(dict(metadata_extra) if metadata_extra else {}),
        },
    )
    return results, daily_outputs
