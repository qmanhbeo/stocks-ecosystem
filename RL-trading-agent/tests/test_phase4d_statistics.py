import numpy as np
import pytest

from vn_stock_rl.trade_episode.phase4d_statistics import (
    annualized_year_blocks,
    hierarchical_paired_bootstrap,
)


def test_annualized_year_blocks_exclude_initial_capital_anchor():
    result = {
        "daily_path": [
            {"year": 2023, "regime": "warmup", "log_return": 0.0},
            {"year": 2023, "regime": "rising", "log_return": 0.01},
            {"year": 2023, "regime": "sideways", "log_return": 0.02},
        ]
    }
    assert annualized_year_blocks(result)[2023] == pytest.approx((0.03 / 2) * 252)


def test_hierarchical_bootstrap_pairs_ticker_years_and_is_reproducible():
    values = {}
    groups = {"A": "training_universe", "B": "training_universe", "DGC": "unseen_ticker"}
    for ticker in groups:
        for year in (2023, 2024):
            values[("candidate", ticker, year)] = 0.12
            values[("control", ticker, year)] = 0.08
    first = hierarchical_paired_bootstrap(
        candidate_policy="candidate",
        comparator_policy="control",
        ticker_group="training_universe",
        block_returns=values,
        ticker_groups=groups,
        replicates=100,
        seed=4,
    )
    second = hierarchical_paired_bootstrap(
        candidate_policy="candidate",
        comparator_policy="control",
        ticker_group="training_universe",
        block_returns=values,
        ticker_groups=groups,
        replicates=100,
        seed=4,
    )
    assert first == second
    assert first["paired_tickers"] == 2
    assert first["paired_ticker_years"] == 4
    assert first["bootstrap_ci_95_low"] == pytest.approx(np.exp(0.12) - np.exp(0.08))
