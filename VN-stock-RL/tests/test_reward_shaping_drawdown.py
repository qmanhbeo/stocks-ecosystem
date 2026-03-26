"""
Tests for drawdown-based reward shaping.
"""

import numpy as np
import pandas as pd

from vn_stock_rl.evaluation.metadata import _merge_env_overrides
from test_utils import TestEnv


def _make_df(opens):
    opens_arr = np.asarray(opens, dtype=float)
    return pd.DataFrame(
        {
            "time": np.arange(len(opens_arr), dtype=int),
            "open": opens_arr,
            "high": opens_arr,
            "low": opens_arr,
            "close": opens_arr,
            "volume": np.ones(len(opens_arr), dtype=float),
        }
    )


def test_drawdown_penalty_math_known_values():
    print("\n" + "=" * 80)
    print("TEST: Drawdown Penalty Math Known Values")
    print("=" * 80)

    # Build a path that rises then draws down while long.
    df = _make_df([100, 100, 100, 100, 110, 90, 95, 100, 98, 105, 103])
    env = TestEnv(
        df=df,
        start_idx=4,
        end_idx=8,
        mode="train",
        lookback_window=2,
        drawdown_penalty_enabled=True,
        drawdown_penalty_lambda=0.5,
        drawdown_penalty_train_only=True,
        include_can_exit=False,
        min_hold_days=1,
        stop_loss=None,
        buy_fee_rate=0.0,
        sell_fee_rate=0.0,
        capital_gains_tax_rate=0.0,
    )
    env.reset()

    # Keep requesting long so we stay in position after entry execution.
    for _ in range(4):
        _obs, reward, _terminated, _truncated, info = env.step(1)
        expected_drawdown = max(0.0, (float(info["peak_equity"]) - float(info["equity"])) / float(info["peak_equity"]))
        expected_penalty = 0.5 * expected_drawdown
        assert np.isclose(float(info["drawdown"]), expected_drawdown, atol=1e-12)
        assert np.isclose(float(info["drawdown_penalty"]), expected_penalty, atol=1e-12)
        assert np.isclose(float(reward), float(info["raw_return"]) - float(info["drawdown_penalty"]), atol=1e-12)


def test_drawdown_penalty_train_only_gate():
    print("\n" + "=" * 80)
    print("TEST: Drawdown Penalty Train-Only Gate")
    print("=" * 80)

    df = _make_df([100, 100, 100, 100, 105, 95, 92, 97, 96, 99])
    common_kwargs = dict(
        df=df,
        start_idx=4,
        end_idx=8,
        lookback_window=2,
        drawdown_penalty_enabled=True,
        drawdown_penalty_lambda=0.5,
        drawdown_penalty_train_only=True,
        include_can_exit=False,
        min_hold_days=1,
        stop_loss=None,
        buy_fee_rate=0.0,
        sell_fee_rate=0.0,
        capital_gains_tax_rate=0.0,
    )

    env_train = TestEnv(mode="train", **common_kwargs)
    env_train.reset()
    _obs_t, reward_t, _term_t, _trunc_t, info_t = env_train.step(1)

    env_val = TestEnv(mode="val", **common_kwargs)
    env_val.reset()
    _obs_v, reward_v, _term_v, _trunc_v, info_v = env_val.step(1)

    # At least train-side penalty path is active and val-side is disabled by train_only gate.
    assert np.isclose(float(reward_t), float(info_t["raw_return"]) - float(info_t["drawdown_penalty"]), atol=1e-12)
    assert np.isclose(float(info_v["drawdown_penalty"]), 0.0, atol=1e-12)
    assert np.isclose(float(reward_v), float(info_v["raw_return"]), atol=1e-12)


def test_drawdown_penalty_zero_on_new_peak():
    print("\n" + "=" * 80)
    print("TEST: Drawdown Penalty Zero On New Peak")
    print("=" * 80)

    df = _make_df([100, 100, 100, 100, 101, 102, 103, 104, 105])
    env = TestEnv(
        df=df,
        start_idx=4,
        end_idx=7,
        mode="train",
        lookback_window=2,
        drawdown_penalty_enabled=True,
        drawdown_penalty_lambda=0.5,
        drawdown_penalty_train_only=True,
        include_can_exit=False,
        min_hold_days=1,
        stop_loss=None,
        buy_fee_rate=0.0,
        sell_fee_rate=0.0,
        capital_gains_tax_rate=0.0,
    )
    env.reset()
    for _ in range(3):
        _obs, _reward, _term, _trunc, info = env.step(1)
        assert np.isclose(float(info["drawdown"]), 0.0, atol=1e-12)
        assert np.isclose(float(info["drawdown_penalty"]), 0.0, atol=1e-12)


def test_drawdown_penalty_invalid_lambda_rejected():
    print("\n" + "=" * 80)
    print("TEST: Drawdown Penalty Invalid Lambda Rejected")
    print("=" * 80)

    df = _make_df([100, 100, 100, 100, 100, 100])
    try:
        TestEnv(
            df=df,
            start_idx=3,
            end_idx=4,
            mode="train",
            lookback_window=2,
            drawdown_penalty_enabled=True,
            drawdown_penalty_lambda=-0.1,
            include_can_exit=False,
            min_hold_days=1,
            stop_loss=None,
        )
    except ValueError as exc:
        assert "drawdown_penalty_lambda" in str(exc)
        return
    raise AssertionError("Expected ValueError for negative drawdown_penalty_lambda")


def test_drawdown_penalty_metadata_roundtrip():
    print("\n" + "=" * 80)
    print("TEST: Drawdown Penalty Metadata Roundtrip")
    print("=" * 80)

    meta = {
        "environment_config": {
            "reward_shaping": {
                "drawdown_penalty": {
                    "enabled": True,
                    "lambda": 0.07,
                    "train_only": True,
                }
            }
        }
    }
    merged = _merge_env_overrides(meta, explicit_env_overrides={}, forced_policy=None)
    assert merged["drawdown_penalty_enabled"] is True
    assert np.isclose(float(merged["drawdown_penalty_lambda"]), 0.07, atol=1e-12)
    assert merged["drawdown_penalty_train_only"] is True


def test_benchmark_relative_reward_flat_underperforms_buy_hold():
    print("\n" + "=" * 80)
    print("TEST: Benchmark Relative Reward Penalizes Missing Benchmark Move")
    print("=" * 80)

    df = _make_df([100, 100, 100, 100, 110, 121])
    env = TestEnv(
        df=df,
        start_idx=4,
        end_idx=4,
        mode="train",
        lookback_window=2,
        benchmark_relative_reward=True,
        reward_benchmark="self_buy_hold",
        benchmark_weight=1.0,
        drawdown_penalty_enabled=False,
        include_can_exit=False,
        min_hold_days=1,
        stop_loss=None,
        buy_fee_rate=0.0,
        sell_fee_rate=0.0,
        capital_gains_tax_rate=0.0,
    )
    env.reset()
    _obs, reward, _terminated, _truncated, info = env.step(0)
    assert np.isclose(float(info["raw_return"]), 0.0, atol=1e-12)
    assert np.isclose(float(info["benchmark_return"]), 0.1, atol=1e-12)
    assert np.isclose(float(info["excess_return"]), -0.1, atol=1e-12)
    assert np.isclose(float(reward), -0.1, atol=1e-12)


def test_benchmark_relative_reward_buy_hold_behavior_gets_zero_excess():
    print("\n" + "=" * 80)
    print("TEST: Benchmark Relative Reward Neutralizes Passive Buy-Hold")
    print("=" * 80)

    df = _make_df([100, 100, 100, 100, 110, 121])
    env = TestEnv(
        df=df,
        start_idx=4,
        end_idx=4,
        mode="train",
        lookback_window=2,
        start_episode_position=1.0,
        benchmark_relative_reward=True,
        reward_benchmark="self_buy_hold",
        benchmark_weight=1.0,
        drawdown_penalty_enabled=False,
        include_can_exit=False,
        min_hold_days=1,
        stop_loss=None,
        buy_fee_rate=0.0,
        sell_fee_rate=0.0,
        capital_gains_tax_rate=0.0,
    )
    _obs, info = env.reset()
    assert info["start_in_position"] is True
    _obs, reward, _terminated, _truncated, info = env.step(1)
    assert np.isclose(float(info["raw_return"]), 0.1, atol=1e-12)
    assert np.isclose(float(info["benchmark_return"]), 0.1, atol=1e-12)
    assert np.isclose(float(info["excess_return"]), 0.0, atol=1e-12)
    assert np.isclose(float(reward), 0.0, atol=1e-12)


def test_benchmark_relative_reward_weight_scales_penalty():
    print("\n" + "=" * 80)
    print("TEST: Benchmark Relative Reward Weight Scales Benchmark Penalty")
    print("=" * 80)

    df = _make_df([100, 100, 100, 100, 110, 121])
    env = TestEnv(
        df=df,
        start_idx=4,
        end_idx=4,
        mode="train",
        lookback_window=2,
        benchmark_relative_reward=True,
        reward_benchmark="self_buy_hold",
        benchmark_weight=0.5,
        drawdown_penalty_enabled=False,
        include_can_exit=False,
        min_hold_days=1,
        stop_loss=None,
        buy_fee_rate=0.0,
        sell_fee_rate=0.0,
        capital_gains_tax_rate=0.0,
    )
    env.reset()
    _obs, reward, _terminated, _truncated, info = env.step(0)
    assert np.isclose(float(info["benchmark_return"]), 0.1, atol=1e-12)
    assert np.isclose(float(info["excess_return"]), -0.1, atol=1e-12)
    assert np.isclose(float(reward), -0.05, atol=1e-12)


def test_benchmark_relative_reward_metadata_roundtrip():
    print("\n" + "=" * 80)
    print("TEST: Benchmark Relative Reward Metadata Roundtrip")
    print("=" * 80)

    meta = {
        "environment_config": {
            "reward_shaping": {
                "benchmark_relative": {
                    "enabled": True,
                    "benchmark": "self_buy_hold",
                    "weight": 0.8,
                }
            }
        }
    }
    merged = _merge_env_overrides(meta, explicit_env_overrides={}, forced_policy=None)
    assert merged["benchmark_relative_reward"] is True
    assert merged["reward_benchmark"] == "self_buy_hold"
    assert np.isclose(float(merged["benchmark_weight"]), 0.8, atol=1e-12)


def test_benchmark_relative_reward_invalid_benchmark_rejected():
    print("\n" + "=" * 80)
    print("TEST: Benchmark Relative Reward Invalid Benchmark Rejected")
    print("=" * 80)

    df = _make_df([100, 100, 100, 100, 110, 121])
    try:
        TestEnv(
            df=df,
            start_idx=4,
            end_idx=4,
            mode="train",
            lookback_window=2,
            benchmark_relative_reward=True,
            reward_benchmark="bogus",
        )
    except ValueError as exc:
        assert "reward_benchmark" in str(exc)
        return
    raise AssertionError("Expected ValueError for invalid reward_benchmark")
