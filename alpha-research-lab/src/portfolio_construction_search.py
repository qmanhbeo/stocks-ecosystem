from __future__ import annotations

from itertools import product
from typing import Iterable

import pandas as pd

from src.deterministic_portfolio import WEIGHTING_RULES


def parse_min_score_grid(raw_values: list[str] | None, strategy_scores: pd.Series) -> list[float | None]:
    if raw_values:
        parsed: list[float | None] = []
        for value in raw_values:
            text = str(value).strip().lower()
            if text in {"none", "null", "na"}:
                parsed.append(None)
            else:
                parsed.append(float(text))
        return parsed

    finite = strategy_scores.dropna().astype(float)
    quantiles = finite.quantile([0.75, 0.9, 0.95]).tolist()
    grid: list[float | None] = [None]
    for value in quantiles:
        rounded = round(float(value), 3)
        if rounded not in {v for v in grid if v is not None}:
            grid.append(rounded)
    return grid


def sortable_min_score(value: float | None) -> float:
    return -1.0 if value is None else float(value)


def candidate_sort_key(row: dict[str, object]) -> tuple[float, float, float, float]:
    return (
        float(row["portfolio_total_return"]),
        float(row["information_ratio_annualized"] or -999.0),
        float(row["portfolio_sharpe_annualized"] or -999.0),
        -float(row["avg_daily_turnover"]),
    )


def sort_candidate_results(results: pd.DataFrame) -> pd.DataFrame:
    return results.sort_values(
        by=[
            "portfolio_total_return",
            "information_ratio_annualized",
            "portfolio_sharpe_annualized",
            "avg_daily_turnover",
            "top_k",
            "rebalance_every",
            "weighting",
            "min_score",
        ],
        ascending=[False, False, False, True, True, True, True, True],
        key=lambda col: col.map(sortable_min_score) if col.name == "min_score" else col,
        ignore_index=True,
    )


def sort_retail_results(results: pd.DataFrame) -> pd.DataFrame:
    sort_columns = [
        "relative_total_return",
        "portfolio_total_return",
        "information_ratio_annualized",
        "avg_cash_weight",
        "avg_daily_turnover",
    ]
    if "top_k" in results.columns:
        sort_columns.append("top_k")
    if "rebalance_every" in results.columns:
        sort_columns.append("rebalance_every")
    if "weighting" in results.columns:
        sort_columns.append("weighting")
    if "min_score" in results.columns:
        sort_columns.append("min_score")
    if "portfolio_notional_vnd" in results.columns:
        sort_columns.append("portfolio_notional_vnd")
    if "max_adv_participation" in results.columns:
        sort_columns.append("max_adv_participation")
    if "min_adv20_value_vnd" in results.columns:
        sort_columns.append("min_adv20_value_vnd")

    ascending = [False, False, False, True, True] + [True] * (len(sort_columns) - 5)
    return results.sort_values(
        by=sort_columns,
        ascending=ascending,
        key=lambda col: col.map(sortable_min_score) if col.name == "min_score" else col,
        ignore_index=True,
    )


def retail_viable_mask(
    results: pd.DataFrame,
    *,
    min_relative_total_return: float = 0.0,
    max_avg_cash_weight: float = 0.25,
    min_positive_years: int = 5,
) -> pd.Series:
    return (
        (pd.to_numeric(results["relative_total_return"], errors="coerce") > float(min_relative_total_return))
        & (pd.to_numeric(results["avg_cash_weight"], errors="coerce") < float(max_avg_cash_weight))
        & (pd.to_numeric(results["positive_years"], errors="coerce") >= int(min_positive_years))
    )


def enumerate_config_grid(
    *,
    top_k_grid: Iterable[int],
    rebalance_grid: Iterable[int],
    weighting_grid: Iterable[str],
    min_score_grid: Iterable[float | None],
) -> list[tuple[int, int, str, float | None]]:
    weightings = [str(v) for v in weighting_grid]
    invalid = sorted(set(weightings) - set(WEIGHTING_RULES))
    if invalid:
        raise ValueError(f"Unknown weighting values: {invalid}; expected subset of {WEIGHTING_RULES}")
    return list(
        product(
            sorted(set(int(v) for v in top_k_grid)),
            sorted(set(int(v) for v in rebalance_grid)),
            weightings,
            list(min_score_grid),
        )
    )


def build_year_splits(
    *,
    start_year: int,
    end_year: int,
    min_train_years: int,
    train_years: int | None = None,
) -> list[dict[str, int]]:
    if min_train_years <= 0:
        raise ValueError("min_train_years must be > 0")
    if train_years is not None and train_years <= 0:
        raise ValueError("train_years must be > 0 when provided")
    if end_year <= start_year:
        raise ValueError("end_year must be greater than start_year")

    splits: list[dict[str, int]] = []
    first_test_year = start_year + int(min_train_years)
    for test_year in range(first_test_year, end_year + 1):
        if train_years is None:
            train_start = start_year
        else:
            train_start = max(start_year, test_year - int(train_years))
        train_end = test_year - 1
        if (train_end - train_start + 1) < min_train_years:
            continue
        splits.append(
            {
                "train_start_year": int(train_start),
                "train_end_year": int(train_end),
                "test_year": int(test_year),
            }
        )
    if not splits:
        raise ValueError("No valid year splits produced")
    return splits


def parse_fixed_menu_candidates(raw_specs: list[str] | None) -> list[dict[str, object]]:
    if not raw_specs:
        return [
            {"name": "k5_r10_eq", "top_k": 5, "rebalance_every": 10, "weighting": "equal", "min_score": None},
            {"name": "k5_r5_eq", "top_k": 5, "rebalance_every": 5, "weighting": "equal", "min_score": None},
            {"name": "k3_r5_eq", "top_k": 3, "rebalance_every": 5, "weighting": "equal", "min_score": None},
        ]

    candidates: list[dict[str, object]] = []
    for spec in raw_specs:
        parts = [part.strip() for part in str(spec).split(":")]
        if len(parts) != 5:
            raise ValueError(
                f"Candidate spec {spec!r} must have 5 colon-separated fields: "
                "name:top_k:rebalance_every:weighting:min_score"
            )
        name, top_k, rebalance_every, weighting, min_score = parts
        if weighting not in WEIGHTING_RULES:
            raise ValueError(f"Unknown weighting {weighting!r}; expected one of {WEIGHTING_RULES}")
        min_score_value = None if min_score.lower() in {"none", "null", "na"} else float(min_score)
        candidates.append(
            {
                "name": name,
                "top_k": int(top_k),
                "rebalance_every": int(rebalance_every),
                "weighting": weighting,
                "min_score": min_score_value,
            }
        )
    return candidates
