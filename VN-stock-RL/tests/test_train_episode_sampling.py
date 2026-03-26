"""
Tests for randomized train sub-episode sampling.
"""

import os
import tempfile
import numpy as np
import pandas as pd

from vn_stock_rl.env import TradingEnv, MultiStockEnv
from vn_stock_rl.evaluation.metadata import _merge_env_overrides
from test_utils import TestEnv


def _make_df(length: int, base_price: float = 100.0) -> pd.DataFrame:
    prices = base_price + np.linspace(0.0, 5.0, length)
    return pd.DataFrame(
        {
            "time": np.arange(length, dtype=int),
            "open": prices,
            "high": prices + 1.0,
            "low": prices - 1.0,
            "close": prices,
            "volume": np.linspace(1000.0, 1000.0 + length - 1, length),
        }
    )


def test_train_sampling_enabled_changes_bounds_single_stock():
    print("\n" + "=" * 80)
    print("TEST: Train Sampling Enabled Changes Bounds (Single Stock)")
    print("=" * 80)

    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = os.path.join(tmpdir, "data")
        os.makedirs(data_dir, exist_ok=True)
        base_path = os.path.join(data_dir, "gia_lich_su_ACB_1D.parquet")
        _make_df(500).to_parquet(base_path, index=False)

        env = TradingEnv(
            data_path=base_path,
            mode="train",
            lookback_window=20,
            train_episode_sampling_enabled=True,
            train_episode_min_fraction=0.2,
            train_episode_max_fraction=0.6,
        )

        decision_train_end = env.train_end_idx - 1
        seen = set()
        for _ in range(12):
            _, info = env.reset()
            start = int(env.episode_start_idx)
            end = int(env.episode_end_idx)
            seen.add((start, end))
            assert start >= env.train_start_idx
            assert end <= decision_train_end
            assert info["start_idx"] == start
            assert info["end_idx"] == end

        assert len(seen) > 1, "Expected varying sampled train episode bounds when sampling is enabled"


def test_train_sampling_respects_fraction_bounds():
    print("\n" + "=" * 80)
    print("TEST: Train Sampling Respects Fraction Bounds")
    print("=" * 80)

    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = os.path.join(tmpdir, "data")
        os.makedirs(data_dir, exist_ok=True)
        base_path = os.path.join(data_dir, "gia_lich_su_ACB_1D.parquet")
        _make_df(420).to_parquet(base_path, index=False)

        min_frac = 0.2
        max_frac = 0.6
        env = TradingEnv(
            data_path=base_path,
            mode="train",
            lookback_window=15,
            train_episode_sampling_enabled=True,
            train_episode_min_fraction=min_frac,
            train_episode_max_fraction=max_frac,
        )

        decision_train_end = env.train_end_idx - 1
        train_rows = decision_train_end - env.train_start_idx + 1
        expected_min_rows = max(int(np.floor(train_rows * min_frac)), 2)
        expected_max_rows = max(int(np.floor(train_rows * max_frac)), expected_min_rows)
        expected_max_rows = min(expected_max_rows, train_rows)

        for _ in range(20):
            env.reset()
            rows = env.episode_end_idx - env.episode_start_idx + 1
            assert expected_min_rows <= rows <= expected_max_rows


def test_train_sampling_disabled_matches_legacy_behavior():
    print("\n" + "=" * 80)
    print("TEST: Train Sampling Disabled Matches Legacy Behavior")
    print("=" * 80)

    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = os.path.join(tmpdir, "data")
        os.makedirs(data_dir, exist_ok=True)
        base_path = os.path.join(data_dir, "gia_lich_su_ACB_1D.parquet")
        _make_df(360).to_parquet(base_path, index=False)

        env = TradingEnv(
            data_path=base_path,
            mode="train",
            lookback_window=15,
            train_episode_sampling_enabled=False,
        )
        env.reset()
        assert env.episode_start_idx == env.train_start_idx
        assert env.episode_end_idx == env.train_end_idx - 1


def test_val_test_unchanged_when_sampling_enabled():
    print("\n" + "=" * 80)
    print("TEST: Val/Test Unchanged With Sampling Enabled")
    print("=" * 80)

    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = os.path.join(tmpdir, "data")
        os.makedirs(data_dir, exist_ok=True)
        base_path = os.path.join(data_dir, "gia_lich_su_ACB_1D.parquet")
        _make_df(360).to_parquet(base_path, index=False)

        env_val = TradingEnv(
            data_path=base_path,
            mode="val",
            lookback_window=15,
            train_episode_sampling_enabled=True,
            train_episode_min_fraction=0.2,
            train_episode_max_fraction=0.6,
        )
        env_val.reset()
        assert env_val.episode_start_idx == env_val.val_start_idx
        assert env_val.episode_end_idx == env_val.val_end_idx - 1

        env_test = TradingEnv(
            data_path=base_path,
            mode="test",
            lookback_window=15,
            train_episode_sampling_enabled=True,
            train_episode_min_fraction=0.2,
            train_episode_max_fraction=0.6,
        )
        env_test.reset()
        assert env_test.episode_start_idx == env_test.test_start_idx
        assert env_test.episode_end_idx == env_test.test_end_idx - 1


def test_multistock_train_sampling_per_stock():
    print("\n" + "=" * 80)
    print("TEST: MultiStock Train Sampling Per Stock")
    print("=" * 80)

    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = os.path.join(tmpdir, "data")
        os.makedirs(data_dir, exist_ok=True)
        _make_df(420, 100.0).to_parquet(os.path.join(data_dir, "gia_lich_su_ACB_1D.parquet"), index=False)
        _make_df(420, 120.0).to_parquet(os.path.join(data_dir, "gia_lich_su_VNM_1D.parquet"), index=False)
        _make_df(420, 80.0).to_parquet(os.path.join(data_dir, "gia_lich_su_HPG_1D.parquet"), index=False)

        env = MultiStockEnv(
            data_dir=data_dir,
            mode="train",
            stocks=["ACB", "VNM", "HPG"],
            lookback_window=15,
            train_episode_sampling_enabled=True,
            train_episode_min_fraction=0.2,
            train_episode_max_fraction=0.6,
        )

        seen_stocks = set()
        for _ in range(15):
            env.reset()
            stock = env.current_stock["name"]
            seen_stocks.add(stock)
            decision_train_end = env.current_stock["train_end"] - 1
            train_rows = decision_train_end - env.current_stock["train_start"] + 1
            min_rows = max(int(np.floor(train_rows * env.train_episode_min_fraction)), 2)
            max_rows = max(int(np.floor(train_rows * env.train_episode_max_fraction)), min_rows)
            max_rows = min(max_rows, train_rows)
            rows = env.episode_end_idx - env.episode_start_idx + 1
            assert env.current_stock["train_start"] <= env.episode_start_idx <= decision_train_end
            assert env.current_stock["train_start"] <= env.episode_end_idx <= decision_train_end
            assert min_rows <= rows <= max_rows

        assert seen_stocks, "Expected at least one sampled stock"


def test_sampling_metadata_roundtrip():
    print("\n" + "=" * 80)
    print("TEST: Sampling Metadata Roundtrip")
    print("=" * 80)

    meta = {
        "environment_config": {
            "train_episode_sampling_enabled": True,
            "train_episode_min_fraction": 0.25,
            "train_episode_max_fraction": 0.55,
        }
    }
    merged = _merge_env_overrides(meta, explicit_env_overrides={}, forced_policy=None)
    assert merged["train_episode_sampling_enabled"] is True
    assert abs(float(merged["train_episode_min_fraction"]) - 0.25) < 1e-12
    assert abs(float(merged["train_episode_max_fraction"]) - 0.55) < 1e-12


def test_invalid_sampling_config_rejected():
    print("\n" + "=" * 80)
    print("TEST: Invalid Sampling Config Rejected")
    print("=" * 80)

    df = _make_df(120)
    try:
        TestEnv(
            df=df,
            start_idx=30,
            end_idx=80,
            mode="train",
            lookback_window=10,
            train_episode_sampling_enabled=True,
            train_episode_min_fraction=0.9,
            train_episode_max_fraction=0.5,
        )
    except ValueError as exc:
        assert "train_episode_min_fraction" in str(exc)
        return
    raise AssertionError("Expected ValueError for invalid train episode sampling fraction bounds")
