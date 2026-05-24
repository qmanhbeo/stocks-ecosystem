import math
import json

import pandas as pd

from profit_pipeline import (
    _compute_curve_metrics,
    _compute_filter_metrics,
    _compute_fallback_metrics,
    ReadinessThresholds,
    _write_paper_handoff_bundle,
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


def test_write_paper_handoff_bundle_outputs_files(tmp_path) -> None:
    canonical_dir = tmp_path / "canonical_wfv"
    strategy_dir = canonical_dir / "strategies" / "s_primary"
    strategy_dir.mkdir(parents=True)
    (strategy_dir / "config_effective.json").write_text('{"name":"s_primary"}', encoding="utf-8")

    readiness_df = pd.DataFrame(
        [
            {
                "strategy_name": "s_primary",
                "is_profit_ready": True,
                "mean_excess_return": 0.05,
                "h_w_mean_return": 0.01,
                "h_w_positive_rate": 0.62,
                "h_w_worst_return": -0.08,
                "h_w_n_periods": 50,
                "h_6m_mean_return": 0.07,
                "h_6m_positive_rate": 0.71,
                "h_6m_worst_return": -0.14,
                "h_6m_n_periods": 18,
            },
            {
                "strategy_name": "s_fallback",
                "is_profit_ready": False,
                "mean_excess_return": 0.01,
            },
        ]
    )
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True)

    _write_paper_handoff_bundle(
        readiness_df=readiness_df,
        canonical_dir=canonical_dir,
        output_dir=out_dir,
        thresholds=ReadinessThresholds(),
        fallback_strategy="s_fallback",
    )

    bundle_path = out_dir / "paper_handoff_bundle.json"
    checklist_path = out_dir / "paper_handoff_checklist.md"
    assert bundle_path.exists()
    assert checklist_path.exists()

    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert payload["primary_strategy"]["name"] == "s_primary"
    assert payload["fallback_strategy"]["name"] == "s_fallback"
    assert payload["horizon_lens"]["horizons"] == ["W", "M", "Q", "6M"]
    assert payload["horizon_lens"]["informational_only"] is True
    assert payload["primary_strategy"]["horizon_metrics"]["W"]["n_periods"] == 50
    assert payload["primary_strategy"]["horizon_metrics"]["6M"]["n_periods"] == 18
