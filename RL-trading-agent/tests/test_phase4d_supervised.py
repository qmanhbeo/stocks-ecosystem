from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from vn_stock_rl.trade_episode.environment import annualized_log_excess_reward
from vn_stock_rl.trade_episode.phase4a_data import PHASE4A_TICKERS
from vn_stock_rl.trade_episode.phase4d_supervised import (
    counterfactual_exit_target,
    exit_feature_vector,
    feature_names,
    terminal_reward,
)


def _stock(n: int = 16):
    dates = pd.bdate_range("2020-01-01", periods=n)
    opens = np.linspace(100.0, 115.0, n)
    closes = opens + 0.25
    return SimpleNamespace(
        ticker="FPT",
        dates=dates,
        opens=opens,
        closes=closes,
        market_features=np.arange(n * 9, dtype=np.float32).reshape(n, 9),
        alpha_features=np.column_stack(
            [np.full(n, 0.6), np.ones(n), np.full(n, 0.4), np.ones(n)]
        ).astype(np.float32),
        daily_volatility_scale=np.full(n, 0.02, dtype=np.float64),
        can_buy=np.ones(n, dtype=bool),
        can_sell=np.ones(n, dtype=bool),
    )


def test_reward_matches_phase4a_formula_for_positive_flat_and_negative_returns():
    for exit_price in (110.0, 100.0, 90.0):
        assert terminal_reward(100.0, exit_price, 3) == pytest.approx(
            annualized_log_excess_reward(100.0, exit_price, 3)
        )
    with pytest.raises(ValueError, match="at least three"):
        terminal_reward(100.0, 101.0, 2)


def test_sell_now_and_hold_labels_use_next_open_and_exact_durations():
    stock = _stock()
    t, age = 6, 2
    partition = np.ones(len(stock.opens), dtype=bool)
    observed = counterfactual_exit_target(
        stock, decision_index=t, current_holding_age=age, partition_mask=partition
    )
    entry_fill = t - age
    expected = annualized_log_excess_reward(
        stock.opens[entry_fill], stock.opens[t + 4], age + 4
    ) - annualized_log_excess_reward(
        stock.opens[entry_fill], stock.opens[t + 1], age + 1
    )
    assert observed == pytest.approx(expected)


def test_minimum_holding_age_and_partition_boundary_are_enforced():
    stock = _stock()
    partition = np.ones(len(stock.opens), dtype=bool)
    assert counterfactual_exit_target(
        stock, decision_index=6, current_holding_age=1, partition_mask=partition
    ) is None
    partition[10] = False  # HOLD's next-open fill is t+4.
    assert counterfactual_exit_target(
        stock, decision_index=6, current_holding_age=2, partition_mask=partition
    ) is None


def test_predictive_inputs_do_not_change_when_future_rows_change():
    stock = _stock()
    state_config = {"max_holding_intervals": 756, "max_episode_steps": 756}
    original = exit_feature_vector(
        stock,
        decision_index=8,
        current_holding_age=3,
        phase4a_state_config=state_config,
    )
    stock.closes[9:] = 10_000.0
    stock.market_features[9:, :] = -99_999.0
    stock.alpha_features[9:, :] = 0.0
    stock.daily_volatility_scale[9:] = 99.0
    changed_future = exit_feature_vector(
        stock,
        decision_index=8,
        current_holding_age=3,
        phase4a_state_config=state_config,
    )
    for before, after in zip(original, changed_future, strict=True):
        np.testing.assert_array_equal(before, after)


def test_feature_contract_has_no_ticker_identity_and_is_finite():
    names = feature_names()
    assert len(names["market_only"]) == 15
    assert len(names["market_plus_alpha"]) == 19
    assert all("ticker" not in name.lower() for values in names.values() for name in values)
    assert set(PHASE4A_TICKERS).issuperset({"FPT", "DGC", "MBB", "VHC"})
    values = exit_feature_vector(
        _stock(),
        decision_index=8,
        current_holding_age=3,
        phase4a_state_config={"max_holding_intervals": 756, "max_episode_steps": 756},
    )
    assert all(np.isfinite(row).all() for row in values)
