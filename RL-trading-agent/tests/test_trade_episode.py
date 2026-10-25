from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sb3_contrib.common.maskable.utils import get_action_masks, is_masking_supported
from stable_baselines3.common.vec_env import DummyVecEnv

from vn_stock_rl.trade_episode import (
    FeatureStandardizer,
    TradeEpisodeConfig,
    TradeEpisodeEnv,
    TradeEpisodePaths,
    annualized_log_excess_reward,
    chronological_splits,
)
from vn_stock_rl.trade_episode.data import (
    load_daily_stock_bars,
    load_daily_tradability_flags,
    stock_bars_path,
)
from vn_stock_rl.trade_episode.evaluation import (
    evaluate_chronological_policy,
    summarize_calendar_performance,
)
from vn_stock_rl.trade_episode.market_features import build_causal_market_features
from vn_stock_rl.trade_episode.signals import load_alpha_signals


def make_env(
    *,
    opens=None,
    closes=None,
    features=None,
    dates=None,
    can_buy=None,
    can_sell=None,
    **kwargs,
):
    opens = np.asarray(
        opens if opens is not None else [10, 10, 10, 10, 11, 11, 11, 11], dtype=float
    )
    closes = np.asarray(closes if closes is not None else opens, dtype=float)
    return TradeEpisodeEnv(
        opens,
        closes,
        price_basis="synthetic",
        market_features=features,
        dates=dates,
        can_buy_next_open=can_buy,
        can_sell_next_open=can_sell,
        **kwargs,
    )


def test_action_interpretation_in_both_position_states():
    env = make_env()
    env.reset()
    _, reward, terminated, truncated, info = env.step(0)
    assert (reward, terminated, truncated, info["position"]) == (0.0, False, False, 0)
    _, reward, terminated, truncated, info = env.step(1)
    assert (reward, terminated, truncated, info["position"]) == (0.0, False, False, 1)
    assert info["action_meaning"] == "IN"


def test_buy_executes_at_next_open_and_uses_all_normalized_capital():
    env = make_env(opens=[10, 12, 13, 14, 15], closes=[10, 99, 13, 14, 15])
    env.reset()
    obs, reward, terminated, truncated, info = env.step(1)
    assert env.open_prices[1] == 12
    assert info["entry_price"] == 12
    assert info["entry_date"] == "1"
    assert info["cash"] == 0
    assert info["position"] == 1
    assert info["mark_to_market_portfolio_value"] == pytest.approx(99 / 12)
    assert (reward, terminated, truncated) == (0.0, False, False)
    assert obs.shape == env.observation_space.shape


def test_hold_keeps_position_and_rewards_zero():
    env = make_env()
    env.reset()
    env.step(1)
    _, reward, terminated, truncated, info = env.step(1)
    assert info["position"] == 1
    assert info["entry_price"] == 10
    assert (reward, terminated, truncated) == (0.0, False, False)


def test_sell_mask_off_by_one_for_three_fill_intervals():
    env = make_env()
    env.reset()
    env.step(1)  # buy at open[1]
    assert env.action_masks().tolist() == [False, True]  # decision close[1], fill would be open[2]
    env.step(1)  # hold; now close[2]
    assert env.action_masks().tolist() == [
        False,
        True,
    ]  # sell would fill at open[3], only 2 intervals
    env.step(1)  # hold; now close[3]
    assert env.action_masks().tolist() == [
        True,
        True,
    ]  # sell fills open[4], 3 intervals after entry
    _, reward, terminated, truncated, info = env.step(0)
    assert info["holding_duration"] == 3
    assert (terminated, truncated) == (True, False)
    assert np.isfinite(reward)


def test_direct_early_sell_is_rejected():
    env = make_env()
    env.reset()
    env.step(1)
    with pytest.raises(ValueError, match="invalid"):
        env.step(0)


def test_action_mask_includes_next_open_tradability():
    can_buy = [True, False, True, True, True, True, True, True]
    can_sell = [True, True, True, True, True, False, True, True]
    env = make_env(can_buy=can_buy, can_sell=can_sell)
    env.reset()
    assert env.action_masks().tolist() == [True, True]
    env.step(0)
    assert env.action_masks().tolist() == [True, False]
    env.step(0)  # remain OUT until the next-open buy flag allows entry
    assert env.action_masks().tolist() == [True, True]
    env.step(1)  # buy at open[3]
    env.step(1)
    env.step(1)
    assert env.action_masks().tolist() == [
        False,
        True,
    ]  # exit fill disallowed by sell flag on decision row 5


def test_sell_terminates_and_records_trade_instrumentation():
    env = make_env(opens=[10, 10, 10, 10, 12, 12], closes=[10, 10, 10, 10, 12, 12])
    env.reset()
    env.step(1)
    env.step(1)
    env.step(1)
    obs, reward, terminated, truncated, info = env.step(0)
    assert terminated and not truncated
    assert reward == pytest.approx(annualized_log_excess_reward(10, 12, 3))
    assert info["entry_price"] == 10
    assert info["exit_price"] == 12
    assert info["raw_trade_return"] == pytest.approx(0.2)
    assert info["annualized_log_trade_return"] == pytest.approx(252 / 3 * np.log(1.2))
    assert info["terminal_rl_reward"] == pytest.approx(reward)
    assert info["cash"] == pytest.approx(1.2)
    assert info["position_value"] == 0
    assert info["termination_reason"] == "sell"
    assert obs.shape == env.observation_space.shape


def test_reward_formula_exactly_matches_specification():
    result = annualized_log_excess_reward(100, 110, 10)
    expected = (252 / 10) * np.log(110 / 100) - np.log(1.07)
    assert result == pytest.approx(expected)


@pytest.mark.parametrize("sell_price", [12.0, 10.0, 8.0])
def test_reward_handles_positive_zero_and_negative_returns(sell_price):
    expected = (252 / 3) * np.log(sell_price / 10.0) - np.log(1.07)
    env = make_env(
        opens=[10, 10, 10, 10, sell_price, sell_price],
        closes=[10, 10, 10, 10, sell_price, sell_price],
    )
    env.reset()
    for action in (1, 1, 1):
        env.step(action)
    _, reward, terminated, truncated, info = env.step(0)
    assert terminated and not truncated
    assert reward == pytest.approx(expected)
    assert info["raw_trade_return"] == pytest.approx(sell_price / 10.0 - 1.0)
    assert annualized_log_excess_reward(10, sell_price, 3) == pytest.approx(expected)


def test_waiting_in_cash_does_not_change_capital_or_equity():
    env = make_env(opens=[10, 20, 30, 40, 50], closes=[10, 20, 30, 40, 50])
    env.reset()
    _, reward, _, _, first = env.step(0)
    _, reward2, _, _, second = env.step(0)
    assert (reward, reward2) == (0.0, 0.0)
    assert first["cash"] == second["cash"] == 1.0
    assert first["position_value"] == second["position_value"] == 0.0
    assert (
        first["mark_to_market_portfolio_value"] == second["mark_to_market_portfolio_value"] == 1.0
    )
    assert second["waiting_duration"] == 2


def test_data_end_truncates_without_fabricated_sell_reward():
    env = make_env(opens=[10, 10, 10], closes=[10, 11, 12])
    env.reset()
    _, reward, terminated, truncated, info = env.step(0)
    assert reward == 0 and not terminated and not truncated
    _, reward, terminated, truncated, info = env.step(0)
    assert reward == 0 and not terminated and truncated
    assert info["truncation_reason"] == "data_end"
    assert info["exit_price"] is None
    assert info["terminal_rl_reward"] is None
    assert info["position"] == 0


def test_open_position_at_data_end_is_marked_but_not_sold():
    env = make_env(opens=[10, 12, 13], closes=[10, 12, 15])
    env.reset()
    env.step(1)
    _, reward, terminated, truncated, info = env.step(1)
    assert reward == 0 and not terminated and truncated
    assert info["truncation_reason"] == "data_end"
    assert info["exit_price"] is None
    assert info["truncated_open_position_value"] == pytest.approx(15 / 12)
    assert info["mark_to_market_portfolio_value"] == pytest.approx(15 / 12)


def test_maximum_episode_duration_truncates_without_sale():
    env = make_env(max_episode_steps=2, max_wait_steps=20)
    env.reset()
    env.step(0)
    _, reward, terminated, truncated, info = env.step(0)
    assert reward == 0 and not terminated and truncated
    assert info["truncation_reason"] == "max_episode_steps"


def test_maximum_wait_duration_truncates_no_buy_trajectory():
    env = make_env(max_wait_steps=2, max_episode_steps=20)
    env.reset()
    env.step(0)
    _, reward, terminated, truncated, info = env.step(0)
    assert reward == 0 and not terminated and truncated
    assert info["truncation_reason"] == "max_wait_steps"
    assert info["entry_price"] is None


def test_maximum_holding_duration_truncates_open_trade():
    env = make_env(max_holding_intervals=3, max_episode_steps=20)
    env.reset()
    env.step(1)
    env.step(1)
    env.step(1)
    _, reward, terminated, truncated, info = env.step(1)
    assert reward == 0 and not terminated and truncated
    assert info["truncation_reason"] == "max_holding_intervals"
    assert info["holding_duration"] == 3
    assert info["truncated_open_position_value"] == pytest.approx(1.1)


def test_no_buy_and_buy_without_sell_trajectories_are_distinct():
    no_buy = make_env(opens=[10, 10, 10], closes=[10, 10, 10])
    no_buy.reset()
    no_buy.step(0)
    _, _, terminated, truncated, no_buy_info = no_buy.step(0)
    assert not terminated and truncated and no_buy_info["entry_price"] is None

    no_sell = make_env(opens=[10, 10, 10], closes=[10, 11, 12])
    no_sell.reset()
    no_sell.step(1)
    _, reward, terminated, truncated, no_sell_info = no_sell.step(1)
    assert reward == 0 and not terminated and truncated
    assert no_sell_info["entry_price"] == 10
    assert no_sell_info["exit_price"] is None


def test_observation_dimensions_and_values_are_finite():
    features = np.arange(16, dtype=np.float32).reshape(8, 2) / 10
    env = make_env(features=features)
    obs, _ = env.reset()
    assert obs.shape == (7,)
    assert obs.dtype == np.float32
    assert np.isfinite(obs).all()
    for action in [1, 1, 1]:
        obs, _, _, _, _ = env.step(action)
        assert np.isfinite(obs).all()


def test_observation_and_execution_do_not_use_same_close_or_future_features():
    features = np.array([[1.0], [2.0], [999.0], [999.0], [999.0]])
    env = make_env(opens=[10, 12, 13, 14, 15], closes=[1000, 99, 13, 14, 15], features=features)
    initial, _ = env.reset()
    assert initial[0] == 1.0
    assert env.action_masks().tolist() == [True, True]
    _, _, _, _, info = env.step(1)
    assert info["entry_price"] == 12.0  # open[1], not observed close[0]
    assert env._observation()[0] == 2.0  # features at current day only


def test_reset_can_select_a_start_inside_a_pre_split_segment():
    env = make_env()
    _, info = env.reset(options={"start_index": 2})
    assert info["episode_start_date"] == "2"
    assert env._market_index == 2


def test_unverified_prices_are_rejected():
    with pytest.raises(ValueError, match="price_basis"):
        TradeEpisodeEnv([10, 11], [10, 11], price_basis="unverified")


def test_train_only_feature_scaler_and_chronological_split():
    values = np.array([[1.0], [3.0], [100.0], [200.0]])
    scaler = FeatureStandardizer.fit(values[:2])
    assert scaler.mean[0] == pytest.approx(2.0)
    assert scaler.transform(values[2:])[0, 0] > 40
    splits = chronological_splits(100)
    assert splits["train"].stop == splits["validation"].start
    assert splits["validation"].stop == splits["test"].start
    assert splits["test"].stop == 100


def test_output_paths_are_outside_worktree_and_shared_data():
    paths = TradeEpisodePaths()
    worktree = __import__("pathlib").Path(__file__).resolve().parents[1].parent
    shared_data = __import__("pathlib").Path("/home/manh/stocks-ecosystem/data").resolve()
    assert not paths.root.is_relative_to(worktree)
    assert not paths.root.is_relative_to(shared_data)
    assert paths.models == paths.root / "models"
    assert paths.logs == paths.root / "logs"
    assert paths.cache == paths.root / "cache"
    with pytest.raises(ValueError, match="outside"):
        TradeEpisodePaths(root=worktree / "artifacts")


def test_shared_stock_loader_reads_configured_dataset_without_changing_it(tmp_path, monkeypatch):
    data_root = tmp_path / "shared-data"
    stock_dir = data_root / "stock"
    stock_dir.mkdir(parents=True)
    path = stock_dir / "gia_lich_su_TEST_1D.parquet"
    frame = pd.DataFrame(
        {
            "time": pd.to_datetime(["2020-01-02", "2020-01-01"]),
            "open": [11.0, 10.0],
            "high": [12.0, 11.0],
            "low": [10.0, 9.0],
            "close": [11.5, 10.5],
            "volume": [100, 200],
        }
    )
    frame.to_parquet(path, index=False)
    original_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    execution_dir = data_root / "features" / "execution"
    execution_dir.mkdir(parents=True)
    tradability_path = execution_dir / "tradability_daily.parquet"
    pd.DataFrame(
        {
            "time": pd.to_datetime(["2020-01-02", "2020-01-01"]),
            "ticker": ["TEST", "TEST"],
            "can_buy_next_open": [True, False],
            "can_sell_next_open": [False, True],
        }
    ).to_parquet(tradability_path, index=False)
    tradability_hash = hashlib.sha256(tradability_path.read_bytes()).hexdigest()
    monkeypatch.setenv("STOCKS_DATA_ROOT", str(data_root))
    assert stock_bars_path("test").resolve() == path.resolve()
    loaded = load_daily_stock_bars("TEST")
    buyable, sellable = load_daily_tradability_flags("TEST", loaded["time"])
    assert loaded["time"].is_monotonic_increasing
    assert loaded.attrs["price_basis"] == "unverified"
    assert buyable.tolist() == [False, True]
    assert sellable.tolist() == [True, False]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == original_hash
    assert hashlib.sha256(tradability_path.read_bytes()).hexdigest() == tradability_hash
    assert path.exists() and tradability_path.exists()


def test_experiment_config_sets_gamma_one_and_masked_ppo():
    config = TradeEpisodeConfig()
    assert config.gamma == 1.0
    assert config.algorithm == "MaskablePPO"


def test_maskableppo_action_masks_work_for_environment_and_vec_env():
    env = make_env()
    env.reset()
    assert is_masking_supported(env)
    assert get_action_masks(env).tolist() == [True, True]
    vector_env = DummyVecEnv([make_env])
    assert is_masking_supported(vector_env)
    assert get_action_masks(vector_env).tolist() == [[True, True]]
    vector_env.close()


def test_calendar_metrics_report_wealth_and_trade_metrics_separately():
    result = summarize_calendar_performance(
        [1.0, 1.1, 1.05, 1.2],
        [False, True, True, False],
        [
            {"waiting_duration": 2, "holding_duration": 3, "raw_trade_return": 0.1},
            {"waiting_duration": 1, "holding_duration": 4, "raw_trade_return": -0.02},
        ],
        buy_and_hold_equity=[1.0, 1.05, 1.1, 1.15],
    )
    assert result["number_of_trades"] == 2
    assert result["exposure_percentage"] == 50.0
    assert result["average_waiting_duration"] == 1.5
    assert result["average_holding_duration"] == 3.5
    assert result["win_rate"] == 0.5
    assert result["chronological_portfolio_cagr"] != result["buy_and_hold_cagr"]
    assert result["annual_benchmark_cagr"] == 0.07


def test_fractional_actions_are_rejected():
    env = make_env()
    env.reset()
    with pytest.raises(ValueError, match="integer"):
        env.step(1.5)


def test_train_only_scaler_imputes_missing_values_to_training_mean():
    training = np.array([[1.0, np.nan], [3.0, 2.0]])
    scaler = FeatureStandardizer.fit(training)
    assert scaler.mean.tolist() == pytest.approx([2.0, 2.0])
    transformed = scaler.transform(np.array([[100.0, np.nan]]))
    assert transformed[0, 0] > 40
    assert transformed[0, 1] == pytest.approx(0.0)


def test_random_training_start_is_seeded_and_keeps_full_horizon_inside_split():
    env = make_env(random_start=True, max_episode_steps=2)
    _, first = env.reset(seed=1208)
    _, second = env.reset(seed=1208)
    assert first["episode_start_index"] == second["episode_start_index"]
    assert first["episode_start_index"] <= len(env.open_prices) - 1 - 2


def test_causal_market_features_ignore_future_rows():
    count = 50
    bars = pd.DataFrame(
        {
            "time": pd.date_range("2020-01-01", periods=count),
            "open": np.linspace(10.0, 20.0, count),
            "high": np.linspace(11.0, 21.0, count),
            "low": np.linspace(9.0, 19.0, count),
            "close": np.linspace(10.5, 20.5, count),
            "volume": np.linspace(100.0, 200.0, count),
        }
    )
    changed_future = bars.copy()
    changed_future.loc[35:, ["open", "high", "low", "close", "volume"]] *= 100.0
    original_features = build_causal_market_features(bars)
    changed_features = build_causal_market_features(changed_future)
    np.testing.assert_allclose(
        original_features.iloc[:35].to_numpy(),
        changed_features.iloc[:35].to_numpy(),
        equal_nan=True,
    )


def test_alpha_signal_loader_keeps_missingness_and_omits_target_column(tmp_path):
    features = tmp_path / "features"
    features.mkdir()
    dates = pd.to_datetime(["2020-01-02", "2020-01-03"])
    pd.DataFrame(
        {
            "time": dates,
            "ticker": ["TEST", "TEST"],
            "xs_proba": [0.4, 0.6],
            "actual": [1, 0],
        }
    ).to_parquet(features / "xs_barrier_vol_1d_hose_full.parquet", index=False)
    pd.DataFrame(
        {
            "time": [dates[0]],
            "ticker": ["TEST"],
            "order_volume_ratio_rank": [0.8],
            "order_pressure_available": [True],
            "future_label": [1],
        }
    ).to_parquet(features / "xs_order_pressure_daily.parquet", index=False)
    signals = load_alpha_signals("TEST", dates, data_root=tmp_path)
    assert signals["alpha_s1_xs_proba"].tolist() == pytest.approx([0.4, 0.6])
    assert signals["alpha_s1_available"].tolist() == [1.0, 1.0]
    assert signals["alpha_c16_order_volume_ratio_rank"].iloc[0] == pytest.approx(0.8)
    assert pd.isna(signals["alpha_c16_order_volume_ratio_rank"].iloc[1])
    assert signals["alpha_c16_available"].tolist() == [1.0, 0.0]
    assert "actual" not in signals.columns
    assert "future_label" not in signals.columns


def test_chronological_policy_evaluation_compounds_wealth_and_reports_cash_policy():
    class AlwaysWait:
        def predict(self, observation, *, deterministic, action_masks):
            assert action_masks[0]
            return np.array(0), None

    env = make_env(
        opens=[10, 11, 12, 13, 14],
        closes=[10, 11, 12, 13, 14],
        max_episode_steps=10,
        max_wait_steps=2,
        max_holding_intervals=10,
    )
    result = evaluate_chronological_policy(AlwaysWait(), env)
    assert result["number_of_trades"] == 0
    assert result["chronological_portfolio_cagr"] == pytest.approx(0.0)
    assert result["exposure_percentage"] == pytest.approx(0.0)
    assert result["open_position_at_end"] is False
    assert result["final_portfolio_value"] == pytest.approx(1.0)


def test_chronological_evaluator_compounds_completed_trades_and_marks_open_end():
    class BuyThenExitWhenLegal:
        def predict(self, observation, *, deterministic, action_masks):
            if observation[0] < 0.5:
                return np.array(1), None
            return np.array(0 if action_masks[0] else 1), None

    env = make_env(
        opens=[10, 10, 11, 12, 13, 14, 15, 16],
        closes=[10, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5, 16.5],
        max_episode_steps=20,
        max_wait_steps=20,
        max_holding_intervals=20,
    )
    result = evaluate_chronological_policy(BuyThenExitWhenLegal(), env)
    assert result["number_of_trades"] == 1
    assert result["trades"][0]["holding_duration"] >= 3
    assert result["final_portfolio_value"] > 1.0
    assert result["open_position_at_end"] is True
    assert result["mean_terminal_rl_reward"] == pytest.approx(
        result["trades"][0]["terminal_rl_reward"]
    )


def test_user_confirmed_adjusted_price_basis_is_explicitly_accepted():
    env = TradeEpisodeEnv(
        [10.0, 11.0],
        [10.0, 11.0],
        price_basis="user_assumed_dividend_adjusted",
    )
    assert env.price_basis == "user_assumed_dividend_adjusted"


def test_baseline_and_alpha_configs_share_all_training_protocol_settings():
    config_root = Path(__file__).resolve().parents[1] / "configs" / "trade_episode"
    baseline = json.loads((config_root / "baseline_market.json").read_text())
    alpha = json.loads((config_root / "market_plus_alpha.json").read_text())
    for key in ("data", "environment", "splits", "training", "smoke", "reserved_final_holdout"):
        assert baseline[key] == alpha[key]
    assert baseline["include_alpha_signals"] is False
    assert alpha["include_alpha_signals"] is True
