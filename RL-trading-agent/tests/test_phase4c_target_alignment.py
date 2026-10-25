import numpy as np
import pytest

from vn_stock_rl.trade_episode.phase4c_target_alignment import (
    entry_reward_samples,
    exit_reward_advantage,
    exit_state_features,
    terminal_trade_reward,
)


def test_terminal_trade_reward_matches_formula_for_positive_flat_and_negative_returns():
    benchmark = np.log1p(0.07)
    assert terminal_trade_reward(100.0, 110.0, 10) == pytest.approx(
        252 / 10 * np.log(1.1) - benchmark
    )
    assert terminal_trade_reward(100.0, 100.0, 10) == pytest.approx(-benchmark)
    assert terminal_trade_reward(100.0, 90.0, 10) == pytest.approx(
        252 / 10 * np.log(0.9) - benchmark
    )
    with pytest.raises(ValueError, match="at least three"):
        terminal_trade_reward(100.0, 101.0, 2)


def test_entry_samples_use_next_open_and_exclude_cross_partition_fills():
    opens = np.asarray([100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0])
    partitions = np.asarray(["train"] * 5 + ["validation"] * 3, dtype=object)
    indices, rewards = entry_reward_samples(
        opens,
        np.ones(len(opens), dtype=bool),
        np.ones(len(opens), dtype=bool),
        partitions,
        horizon=3,
    )
    # t=0 uses entry open[1], decision t=3, and exit open[4]. t=1 would
    # exit at open[5] in validation and therefore cannot belong to train.
    assert indices.tolist() == [0]
    assert rewards.tolist() == pytest.approx(
        [252 / 3 * np.log(opens[4] / opens[1]) - np.log1p(0.07)]
    )


def test_exit_advantage_compares_sell_now_with_continuing_then_selling():
    opens = np.asarray([100.0, 99.0, 101.0, 103.0, 102.0, 104.0, 107.0, 105.0, 110.0, 111.0])
    decision_index = 4
    entry_age = 3
    horizon = 3
    entry_price = opens[decision_index - entry_age]
    reward_now = terminal_trade_reward(entry_price, opens[decision_index + 1], entry_age + 1)
    reward_later = terminal_trade_reward(
        entry_price,
        opens[decision_index + horizon + 1],
        entry_age + horizon + 1,
    )
    assert exit_reward_advantage(
        opens,
        decision_index=decision_index,
        entry_age=entry_age,
        continue_horizon=horizon,
    ) == pytest.approx(reward_later - reward_now)


def test_synthetic_exit_state_is_finite_and_has_expected_episode_fields():
    values = exit_state_features(
        current_close=110.0,
        entry_price=100.0,
        entry_volatility=0.02,
        entry_age=10,
    )
    assert values.shape == (5,)
    assert np.isfinite(values).all()
    assert values[0] == 1.0
    assert values[1] == pytest.approx(10 / 756)
    assert values[3] == 0.0
    assert values[4] == pytest.approx(11 / 756)
