from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd
import pytest

from vn_stock_rl.trade_episode.environment import TradeEpisodeEnv
from vn_stock_rl.trade_episode.evaluation import evaluate_chronological_policy
from vn_stock_rl.trade_episode.phase4b_controls import (
    ValidationScheduleRandomPolicy,
    derive_control_seed,
    summarize_duration_matching,
)
from vn_stock_rl.trade_episode.phase4b_experiment_support import summarize_h5_regimes
from vn_stock_rl.trade_episode.phase4b_provenance import verify_checkpoint_manifest
from vn_stock_rl.trade_episode.phase4b_regimes import (
    build_causal_vnindex_regimes,
    compound_interval_returns,
    regime_asof,
    summarize_regime_year_blocks,
)
from vn_stock_rl.trade_episode.phase4b_statistics import bootstrap_paired_blocks


def _state_observation(market_value: float, *, episode_steps: float = 0.0) -> np.ndarray:
    return np.asarray([market_value, -market_value, 0, 0, 0, 0, 0, 0, episode_steps], np.float32)


def test_random_control_ignores_market_features_and_reproduces_seeded_schedule():
    schedule = [(0, 3), (2, 8), (1, 5)]
    first = ValidationScheduleRandomPolicy(
        schedule, seed=42117, max_wait_steps=10, max_holding_intervals=10, max_episode_steps=10
    )
    second = ValidationScheduleRandomPolicy(
        schedule, seed=42117, max_wait_steps=10, max_holding_intervals=10, max_episode_steps=10
    )
    actions = []
    for index in range(50):
        market_value = float(index * 1000)
        obs_a = _state_observation(market_value)
        obs_b = _state_observation(-market_value)
        action_a, _ = first.predict(obs_a, action_masks=[True, True])
        action_b, _ = second.predict(obs_b, action_masks=[True, True])
        actions.append(int(action_a[0]))
        assert action_a.tolist() == action_b.tolist()
    assert first.sampled_pairs == second.sampled_pairs
    assert len(set(first.sampled_pairs)) > 1
    assert len(actions) == 50


def test_random_control_executes_next_open_and_enforces_three_interval_minimum():
    dates = pd.date_range("2024-01-01", periods=8, freq="B")
    env = TradeEpisodeEnv(
        [10, 11, 12, 13, 14, 15, 16, 17],
        [10, 11, 12, 13, 14, 15, 16, 17],
        price_basis="synthetic",
        dates=dates,
        max_episode_steps=10,
        max_wait_steps=10,
        max_holding_intervals=10,
    )
    policy = ValidationScheduleRandomPolicy(
        [(0, 3)],
        seed=2,
        max_wait_steps=10,
        max_holding_intervals=10,
        max_episode_steps=10,
    )
    observation, _ = env.reset(seed=9)
    done = False
    while not done:
        mask = env.action_masks()
        if env._position_in and env._holding_intervals() < 2:
            assert not bool(mask[0])
        action, _ = policy.predict(observation, action_masks=mask)
        assert mask[int(action[0])]
        observation, reward, terminated, truncated, info = env.step(int(action[0]))
        if terminated:
            done = True
            assert reward != 0
            assert info["entry_date"] == str(dates[1].to_datetime64())
            assert info["entry_price"] == 11
            assert info["exit_date"] == str(dates[4].to_datetime64())
            assert info["exit_price"] == 14
            assert info["holding_duration"] == 3
        elif truncated:
            pytest.fail("Synthetic series ended before the scheduled randomized exit")
    env.close()


def test_duration_match_metrics_report_signed_exposure_and_duration_errors():
    result = summarize_duration_matching(
        {
            "exposure_percentage": 90.0,
            "average_holding_duration": 10.0,
            "average_waiting_duration": 2.0,
        },
        {
            "exposure_percentage": 87.0,
            "average_holding_duration": 12.0,
            "average_waiting_duration": 3.5,
        },
    )
    assert result["exposure_error_percentage_points"] == -3.0
    assert result["holding_duration_relative_error"] == pytest.approx(0.2)
    assert result["waiting_duration_error_days"] == 1.5


def test_control_seed_derivation_is_stable_and_keyed_by_path():
    first = derive_control_seed(42000, "FPT", "market_only", "test")
    assert first == derive_control_seed(42000, "FPT", "market_only", "test")
    assert first != derive_control_seed(42000, "FPT", "market_plus_s1_c16", "test")
    assert first != derive_control_seed(42000, "FPT", "market_only", "validation")


def test_paired_bootstrap_weights_tickers_equally_not_trades_or_blocks():
    ppo = {
        ("A", 2023): [0.1],
        ("A", 2024): [0.1],
        ("A", 2025): [0.1],
        ("B", 2023): [0.0],
    }
    control = {key: [0.0] for key in ppo}
    result = bootstrap_paired_blocks(ppo, control, replicates=200, seed=91)
    assert result["mean_paired_excess_return"] == pytest.approx(0.05)
    assert result["ticker_count"] == 2
    assert result["paired_block_count"] == 4


def test_h5_rule_requires_positive_results_in_both_unfavorable_regimes_and_groups():
    variants = ("market_only", "market_plus_s1_c16")
    tickers = {"training_universe": "FPT", "unseen_ticker": "DGC"}
    ppo, controls, benchmarks = {}, {}, {}
    matches = []
    for variant in variants:
        for group, ticker in tickers.items():
            for split in ("validation", "test"):
                matches.append(
                    {
                        "variant": variant,
                        "ticker_group": group,
                        "split": split,
                        "adequate_match": True,
                    }
                )
            for regime in ("falling", "sideways"):
                ppo[(variant, ticker, 2022, regime)] = [0.10]
                controls[(variant, ticker, 2022, regime)] = [0.0]
                benchmarks[("mechanical_immediate_entry_3day_exit", ticker, 2022, regime)] = [0.0]
                benchmarks[("buy_and_hold", ticker, 2022, regime)] = [0.0]

    details, combined = summarize_h5_regimes(
        ppo_regime_values=ppo,
        control_regime_values=controls,
        benchmark_regime_values=benchmarks,
        match_group_rows=matches,
        config={"uncertainty": {"seed": 7, "replicates": 100}},
    )
    assert combined == "contradicted by the evidence"
    assert all(row["classification"] == "contradicted by the evidence" for row in details.values())


def _index_bars() -> pd.DataFrame:
    dates = pd.date_range("2020-01-01", periods=320, freq="B")
    close = np.full(len(dates), 100.0)
    close[127:254] = 110.0
    close[254:] = 99.0
    return pd.DataFrame({"time": dates, "close": close})


def test_vnindex_regimes_are_causal_and_use_fixed_threshold_boundaries():
    bars = _index_bars()
    regimes = build_causal_vnindex_regimes(bars, lookback_sessions=126)
    assert regimes.loc[126, "regime"] == "sideways"
    assert regimes.loc[127, "regime"] == "rising"
    assert regimes.loc[254, "regime"] == "falling"
    assert regime_asof(regimes, bars.loc[254, "time"] + pd.Timedelta(days=1)) == "falling"

    altered = bars.copy()
    altered.loc[180:, "close"] *= 100.0
    changed_regimes = build_causal_vnindex_regimes(altered, lookback_sessions=126)
    assert regimes.loc[:179, "regime"].tolist() == changed_regimes.loc[:179, "regime"].tolist()


def test_regime_block_compounding_and_daily_equity_path_are_consistent():
    assert compound_interval_returns([0.10, -0.10]) == pytest.approx(-0.01)
    index = build_causal_vnindex_regimes(_index_bars(), lookback_sessions=126)
    daily_path = [
        {
            "decision_date": index.loc[254, "time"].strftime("%Y-%m-%d"),
            "execution_date": index.loc[255, "time"].strftime("%Y-%m-%d"),
            "interval_return": 0.10,
            "exposure": True,
        },
        {
            "decision_date": index.loc[255, "time"].strftime("%Y-%m-%d"),
            "execution_date": index.loc[256, "time"].strftime("%Y-%m-%d"),
            "interval_return": -0.05,
            "exposure": False,
        },
    ]
    blocks = summarize_regime_year_blocks(daily_path, index)
    assert sum(row["interval_count"] for row in blocks) == 2
    assert sum(row["conditional_compounded_return"] for row in blocks) == pytest.approx(0.045)

    class BuyAndHold:
        def predict(self, observation, *, action_masks, deterministic=True):
            del observation, deterministic
            return np.asarray([1 if action_masks[1] else 0]), None

    env = TradeEpisodeEnv(
        [10, 10, 10, 10, 10],
        [10, 11, 12, 13, 14],
        price_basis="synthetic",
        max_episode_steps=10,
        max_wait_steps=10,
        max_holding_intervals=10,
    )
    result = evaluate_chronological_policy(BuyAndHold(), env)
    assert np.prod([1 + row["interval_return"] for row in result["daily_path"]]) == pytest.approx(
        result["final_mark_to_market_value"]
    )
    assert result["daily_path"][-1]["execution_date"] == "4"
    env.close()


def test_checkpoint_manifest_hash_guard_detects_mutation(tmp_path):
    checkpoint = tmp_path / "frozen.zip"
    checkpoint.write_bytes(b"checkpoint-bytes")
    expected = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    entries = [{"path": str(checkpoint), "sha256": expected}]
    verify_checkpoint_manifest(entries)
    checkpoint.write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_checkpoint_manifest(entries)
