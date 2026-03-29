from __future__ import annotations

import pandas as pd

from src.research_protocol import DEFAULT_PROTOCOL
from src.tradability_conditioned_research import build_state_masks, compute_phase_portfolio_summary


def test_build_state_masks_respects_buyability_and_thresholds() -> None:
    frame = pd.DataFrame(
        {
            "time": pd.to_datetime(["2025-01-02", "2025-01-02", "2025-01-03"]),
            "ticker": ["AAA", "BBB", "CCC"],
            "can_buy_next_open": [True, True, False],
            "tv_to_adv20": [1.2, 1.3, 2.0],
            "clv": [0.5, 0.4, 0.8],
        }
    )
    masks = build_state_masks(frame)
    assert masks["buyable"].tolist() == [True, True, False]
    assert masks["liq_open_basic"].tolist() == [True, False, False]
    assert masks["liq_open_strict"].tolist() == [False, False, False]


def test_compute_phase_portfolio_summary_splits_daily_path() -> None:
    daily = pd.DataFrame(
        {
            "execution_date": pd.to_datetime(["2022-12-30", "2023-01-03", "2025-01-03", "2026-01-03"]),
            "portfolio_return": [0.01, 0.02, -0.01, 0.03],
            "benchmark_return": [0.00, 0.01, -0.02, 0.01],
            "relative_return": [0.01, 0.01, 0.01, 0.02],
            "portfolio_value_vnd": [101.0, 103.02, 101.9898, 105.049494],
            "cash_weight": [0.10, 0.20, 0.30, 0.40],
            "turnover": [0.05, 0.06, 0.07, 0.08],
        }
    )
    phases = compute_phase_portfolio_summary(daily, protocol=DEFAULT_PROTOCOL)
    assert phases["dev"]["days"] == 1
    assert phases["validation"]["days"] == 1
    assert phases["confirmation"]["days"] == 1
    assert phases["forward"]["days"] == 1
    assert phases["validation"]["relative_total_return"] is not None
    assert phases["forward"]["avg_cash_weight"] == 0.4
