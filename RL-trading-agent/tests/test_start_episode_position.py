"""
Tests for historical already-long randomized episode starts.
"""

import numpy as np
import pandas as pd

from test_utils import TestEnv


def _make_df(opens: np.ndarray) -> pd.DataFrame:
    opens = np.asarray(opens, dtype=np.float64)
    return pd.DataFrame(
        {
            "time": np.arange(len(opens), dtype=int),
            "open": opens,
            "high": opens + 1.0,
            "low": opens - 1.0,
            "close": opens.copy(),
            "volume": np.linspace(1000.0, 1000.0 + len(opens) - 1, len(opens)),
        }
    )


def _make_env(mode: str, start_episode_position: float) -> TestEnv:
    df = _make_df(np.linspace(100.0, 150.0, 200))
    return TestEnv(
        df=df,
        start_idx=80,
        end_idx=140,
        mode=mode,
        lookback_window=20,
        min_hold_days=3,
        start_episode_position=start_episode_position,
    )


def test_start_episode_position_train_probability():
    print("\n" + "=" * 80)
    print("TEST: Start Episode Position Train Probability")
    print("=" * 80)
    env = _make_env(mode="train", start_episode_position=0.3)
    n = 400
    starts_long = 0
    for _ in range(n):
        _, info = env.reset()
        starts_long += int(bool(info["start_in_position"]))
    observed = starts_long / n
    assert 0.20 <= observed <= 0.40, f"Expected ~0.30 long-start frequency, got {observed:.3f}"


def test_start_episode_position_val_test_always_flat():
    print("\n" + "=" * 80)
    print("TEST: Start Episode Position Val/Test Always Flat")
    print("=" * 80)
    for mode in ("val", "test"):
        env = _make_env(mode=mode, start_episode_position=1.0)
        for _ in range(20):
            _, info = env.reset()
            assert env.position == 0
            assert env.hold_count == 0
            assert env.entry_price is None
            assert info["start_in_position"] is False
            assert info["synthetic_entry_idx"] is None


def test_start_long_historical_entry_consistency():
    print("\n" + "=" * 80)
    print("TEST: Start Long Historical Entry Consistency")
    print("=" * 80)
    env = _make_env(mode="train", start_episode_position=1.0)
    for _ in range(60):
        _, info = env.reset()
        if info["start_in_position"] and int(info["synthetic_entry_idx"]) < env.current_step:
            entry_idx = int(info["synthetic_entry_idx"])
            assert env.hold_count >= 1
            assert entry_idx == env.current_step - (env.hold_count - 1)
            expected_entry = float(env._open[entry_idx])
            assert np.isclose(float(env.entry_price), expected_entry)
            assert np.isclose(float(info["synthetic_entry_price"]), expected_entry)
            assert env.position == 1
            assert env.pending_action == 1
            return
    raise AssertionError("Could not sample a historical-entry start (hold_count > 1)")


def test_start_long_equity_normalized_no_buy_fee():
    print("\n" + "=" * 80)
    print("TEST: Start Long Equity Normalized No Buy Fee")
    print("=" * 80)
    env = _make_env(mode="train", start_episode_position=1.0)
    for _ in range(30):
        env.reset()
        if env.position == 1:
            open_now = float(env._open[env.current_step])
            assert np.isclose(env.cash, 0.0)
            assert np.isclose(env.shares, 1.0 / open_now)
            assert np.isclose(env._equity_at_open(env.current_step), 1.0)
            return
    raise AssertionError("Expected to sample long-start state with probability 1.0")


def test_min_hold_gate_uses_sampled_hold_count():
    print("\n" + "=" * 80)
    print("TEST: Min Hold Gate Uses Sampled Hold Count")
    print("=" * 80)
    env = _make_env(mode="train", start_episode_position=1.0)
    for _ in range(60):
        env.reset()
        if env.position != 1:
            continue
        _, _, _, _, info = env.step(0)  # request exit
        can_exit_expected = env.hold_count >= env.min_hold_days
        if can_exit_expected:
            assert env.pending_action == 0
        else:
            assert env.pending_action == 1
        assert bool(info["position"]) is True
        return
    raise AssertionError("Expected long-start state with probability 1.0")


def test_stop_loss_uses_historical_entry_price():
    print("\n" + "=" * 80)
    print("TEST: Stop-Loss Uses Historical Entry Price")
    print("=" * 80)
    opens = np.array([220, 210, 200, 190, 180, 170, 160, 150, 140, 130, 120, 110], dtype=np.float64)
    df = _make_df(opens)
    # Use close at t+1 = 150 to separate historical-entry loss from current-open loss.
    df.loc[:, "close"] = opens
    df.loc[7, "close"] = 150.0
    env = TestEnv(
        df=df,
        start_idx=6,
        end_idx=10,
        mode="train",
        lookback_window=5,
        min_hold_days=0,
        stop_loss=0.1,
        start_episode_position=1.0,
    )

    for _ in range(80):
        _, reset_info = env.reset()
        if not reset_info["start_in_position"]:
            continue
        entry_idx = int(reset_info["synthetic_entry_idx"])
        if entry_idx >= env.current_step:
            continue
        current_open = float(df.iloc[env.current_step]["open"])
        historical_entry = float(reset_info["synthetic_entry_price"])
        close_now = float(df.iloc[env.current_step + 1]["close"])

        loss_hist = (close_now / historical_entry) - 1.0
        loss_curr = (close_now / current_open) - 1.0
        expected_hist_pending = 0 if loss_hist <= -env.stop_loss else 1
        expected_curr_pending = 0 if loss_curr <= -env.stop_loss else 1
        if expected_hist_pending == expected_curr_pending:
            continue

        env.step(1)
        assert env.pending_action == expected_hist_pending
        return

    raise AssertionError("Could not sample differentiating case for historical-vs-current stop-loss anchor")
