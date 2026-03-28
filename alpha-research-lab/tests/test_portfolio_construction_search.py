from __future__ import annotations

import pandas as pd

from src.portfolio_construction_search import (
    build_year_splits,
    enumerate_config_grid,
    parse_min_score_grid,
    sort_candidate_results,
)


def test_build_year_splits_expanding_window():
    splits = build_year_splits(start_year=2015, end_year=2020, min_train_years=3)
    assert splits == [
        {"train_start_year": 2015, "train_end_year": 2017, "test_year": 2018},
        {"train_start_year": 2015, "train_end_year": 2018, "test_year": 2019},
        {"train_start_year": 2015, "train_end_year": 2019, "test_year": 2020},
    ]


def test_build_year_splits_rolling_window():
    splits = build_year_splits(start_year=2015, end_year=2021, min_train_years=3, train_years=3)
    assert splits == [
        {"train_start_year": 2015, "train_end_year": 2017, "test_year": 2018},
        {"train_start_year": 2016, "train_end_year": 2018, "test_year": 2019},
        {"train_start_year": 2017, "train_end_year": 2019, "test_year": 2020},
        {"train_start_year": 2018, "train_end_year": 2020, "test_year": 2021},
    ]


def test_sort_candidate_results_uses_return_then_ir_then_turnover():
    frame = pd.DataFrame(
        [
            {
                "top_k": 5,
                "rebalance_every": 5,
                "weighting": "equal",
                "min_score": None,
                "portfolio_total_return": 1.0,
                "information_ratio_annualized": 0.2,
                "portfolio_sharpe_annualized": 0.3,
                "avg_daily_turnover": 0.4,
            },
            {
                "top_k": 8,
                "rebalance_every": 10,
                "weighting": "linear",
                "min_score": 0.6,
                "portfolio_total_return": 1.0,
                "information_ratio_annualized": 0.3,
                "portfolio_sharpe_annualized": 0.2,
                "avg_daily_turnover": 0.5,
            },
        ]
    )
    ranked = sort_candidate_results(frame)
    assert ranked.loc[0, "rebalance_every"] == 10


def test_parse_min_score_grid_uses_quantiles_when_unspecified():
    scores = pd.Series([0.1, 0.2, 0.5, 0.7, 0.9])
    grid = parse_min_score_grid(None, scores)
    assert grid[0] is None
    assert len(grid) >= 2


def test_enumerate_config_grid_deduplicates_inputs():
    grid = enumerate_config_grid(
        top_k_grid=[5, 5],
        rebalance_grid=[3, 5, 3],
        weighting_grid=["equal", "linear"],
        min_score_grid=[None, 0.5],
    )
    assert len(grid) == 2 * 2 * 2
