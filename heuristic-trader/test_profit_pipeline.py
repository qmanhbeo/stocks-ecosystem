import math

import pandas as pd

from profit_pipeline import (
    _compute_curve_metrics,
    _compute_filter_metrics,
    _compute_fallback_metrics,
)


def test_compute_curve_metrics_underfill_and_cash() -> None:
    curve = pd.DataFrame(
        {
            "cash": [30.0, 40.0, 20.0],
            "portfolio_value": [100.0, 100.0, 100.0],
            "holdings_value": [70.0, 60.0, 80.0],
            "n_holdings": [5, 4, 3],
        }
    )
    m = _compute_curve_metrics(curve, top_k=5)
    assert math.isclose(m["avg_cash_pct"], 30.0, rel_tol=1e-9)
    assert math.isclose(m["avg_invested_pct"], 70.0, rel_tol=1e-9)
    assert math.isclose(m["avg_n_holdings"], 4.0, rel_tol=1e-9)
    assert math.isclose(m["avg_underfill_pct"], 20.0, rel_tol=1e-9)
    assert math.isclose(m["underfilled_days_pct"], (2 / 3) * 100.0, rel_tol=1e-9)


def test_compute_filter_metrics_rates() -> None:
    filtered = pd.DataFrame(
        {
            "n_candidates": [15, 15],
            "n_filtered_liquidity": [3, 2],
            "n_filtered_tradability": [2, 1],
            "n_selected": [5, 4],
        }
    )
    m = _compute_filter_metrics(filtered, top_k=5)
    assert math.isclose(m["rebalance_count"], 2.0, rel_tol=1e-9)
    assert math.isclose(m["avg_selected_per_rebalance"], 4.5, rel_tol=1e-9)
    assert math.isclose(m["selection_fill_rate"], 0.9, rel_tol=1e-9)
    assert math.isclose(m["liquidity_rejection_rate"], 5 / 30, rel_tol=1e-9)
    assert math.isclose(m["tradability_rejection_rate"], 3 / 30, rel_tol=1e-9)


def test_compute_fallback_metrics() -> None:
    fallback = pd.DataFrame({"fallback_triggered": [True, False, True, False]})
    m = _compute_fallback_metrics(fallback)
    assert math.isclose(m["fallback_trigger_rate"], 0.5, rel_tol=1e-9)
