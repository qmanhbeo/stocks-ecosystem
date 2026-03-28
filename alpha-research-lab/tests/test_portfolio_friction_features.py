from __future__ import annotations

import pandas as pd

from src.portfolio_friction_features import (
    add_liquidity_aware_score_variants,
    build_boolean_matrix,
    build_friction_feature_frame,
)


def test_build_friction_feature_frame_adds_expected_columns():
    scored = pd.DataFrame(
        {
            "time": pd.to_datetime(["2024-01-01", "2024-01-01", "2024-01-02", "2024-01-02"]),
            "ticker": ["AAA", "BBB", "AAA", "BBB"],
            "actual": [1, 0, 0, 1],
            "score__full_library": [0.8, 0.2, 0.7, 0.3],
        }
    )
    price_panel = pd.DataFrame(
        {
            "time": scored["time"],
            "ticker": scored["ticker"],
            "close": [10, 20, 11, 19],
            "volume": [100, 50, 120, 70],
            "traded_value_vnd": [1000, 1000, 1320, 1330],
            "adv20_value": [900, 1100, 1000, 1200],
            "adv5_value": [950, 1050, 980, 1180],
            "clv": [0.7, 0.4, 0.8, 0.3],
        }
    )
    tradability = pd.DataFrame(
        {
            "time": scored["time"],
            "ticker": scored["ticker"],
            "can_buy_next_open": [True, False, True, True],
            "can_sell_next_open": [True, True, True, True],
        }
    )

    feature_frame = build_friction_feature_frame(scored, price_panel, tradability)
    feature_frame, variants = add_liquidity_aware_score_variants(
        feature_frame,
        base_score_column="score__full_library",
    )

    assert {"xs_adv20_rank", "xs_tv_to_adv20_rank", "xs_tradability_rank", "tv_to_adv20"}.issubset(
        feature_frame.columns
    )
    assert "score__liq_x_tradability_rank" in feature_frame.columns
    assert "liq_blend_70_30" in variants


def test_build_boolean_matrix_pivots_by_date_and_ticker():
    frame = pd.DataFrame(
        {
            "time": pd.to_datetime(["2024-01-01", "2024-01-01", "2024-01-02"]),
            "ticker": ["AAA", "BBB", "AAA"],
            "flag": [True, False, True],
        }
    )
    matrix = build_boolean_matrix(
        frame,
        value_column="flag",
        dates=pd.to_datetime(["2024-01-01", "2024-01-02"]),
        tickers=["AAA", "BBB"],
    )

    assert matrix.shape == (2, 2)
    assert bool(matrix[0, 0]) is True
    assert bool(matrix[0, 1]) is False
    assert bool(matrix[1, 1]) is False
