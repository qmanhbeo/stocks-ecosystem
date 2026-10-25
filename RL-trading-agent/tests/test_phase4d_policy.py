from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from vn_stock_rl.trade_episode.phase4d_policy import (
    make_entry_schedule,
    simulate_fixed_entry_policy,
)


def _stock(n: int = 120):
    dates = pd.bdate_range("2020-01-01", periods=n)
    opens = np.linspace(100.0, 140.0, n)
    return SimpleNamespace(
        ticker="FPT",
        dates=dates,
        opens=opens,
        closes=opens.copy(),
        market_features=np.zeros((n, 9), dtype=np.float32),
        alpha_features=np.column_stack(
            [np.full(n, 0.5), np.ones(n), np.full(n, 0.5), np.ones(n)]
        ).astype(np.float32),
        daily_volatility_scale=np.full(n, 0.02),
        can_buy=np.ones(n, dtype=bool),
        can_sell=np.ones(n, dtype=bool),
        split_masks={
            "train": np.ones(n, dtype=bool),
            "validation": np.ones(n, dtype=bool),
            "test": np.ones(n, dtype=bool),
        },
    )


def _simulate(stock, entry_indices, *, policy="fixed", duration=3, model=None):
    return simulate_fixed_entry_policy(
        stock,
        split="exploratory",
        entry_decision_indices=entry_indices,
        policy_id=policy,
        policy_kind="fixed" if policy != "supervised" else "supervised",
        phase4a_state_config={"max_holding_intervals": 756, "max_episode_steps": 756},
        maximum_holding_intervals=40,
        model_last_decision_age=36,
        regime_by_date={str(date.date()): "sideways" for date in stock.dates},
        model=model,
        threshold=0.0 if model is not None else None,
        fixed_duration=duration,
    )


def test_minimum_hold_and_fixed_entry_schedule_are_shared_across_exit_rules():
    stock = _stock()
    schedule = make_entry_schedule(
        stock, split="exploratory", stride=42, maximum_holding_intervals=40
    )
    first = schedule["decision_indices"][0]
    short = _simulate(stock, [first], policy="fixed_3", duration=3)
    long = _simulate(stock, [first], policy="fixed_10", duration=10)
    assert short["executed_entry_decision_indices"] == long["executed_entry_decision_indices"]
    assert short["trades"][0]["holding_duration"] == 3
    assert long["trades"][0]["holding_duration"] == 10
    assert short["trades"][0]["entry_date"] == str(stock.dates[first + 1].date())


def test_chronological_compounding_and_exposure_use_fills_and_marked_equity():
    stock = _stock(15)
    result = _simulate(stock, [0, 5], policy="fixed_3", duration=3)
    expected_value = (stock.opens[4] / stock.opens[1]) * (stock.opens[9] / stock.opens[6])
    assert result["final_portfolio_value"] == pytest.approx(expected_value)
    assert result["number_of_trades"] == 2
    assert result["exposure_percentage"] == pytest.approx(6 / 14 * 100)
    assert result["maximum_drawdown"] <= 0.0


def test_end_of_period_open_position_is_marked_not_fabricated_as_sold():
    stock = _stock(10)
    result = _simulate(stock, [8], policy="fixed_3", duration=3)
    trade = result["trades"][0]
    assert trade["incomplete"] is True
    assert trade["exit_date"] is None
    assert trade["terminal_rl_reward"] is None
    assert trade["mark_to_market_value"] == stock.closes[9] / stock.opens[9]

