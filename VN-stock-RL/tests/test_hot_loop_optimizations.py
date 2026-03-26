"""
Targeted regression tests for hot-loop optimizations.

These tests assert behavior invariants while validating optimization-specific
implementation properties.
"""

import os
import shutil
import uuid
from unittest.mock import patch
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from vn_stock_rl.env import MultiStockEnv
from vn_stock_rl.evaluation.reporting import _extract_trades
from test_utils import TestEnv, create_price_dataframe


def _make_df(start: int, length: int, price: float) -> pd.DataFrame:
    times = np.arange(start, start + length)
    prices = np.full(length, price, dtype=float)
    return pd.DataFrame(
        {
            "time": times,
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "volume": np.ones(length, dtype=float),
        }
    )


def _extract_trades_reference(
    df_history: pd.DataFrame,
    buy_fee_rate: float = 0.0,
    sell_fee_rate: float = 0.0,
    capital_gains_tax_rate: float = 0.0,
) -> pd.DataFrame:
    """Reference implementation matching pre-optimization behavior."""
    trades = []
    entry_step = None
    entry_price = None
    entry_date = None

    for i in range(1, len(df_history)):
        if df_history["position"].iloc[i] == 1 and df_history["position"].iloc[i - 1] == 0:
            entry_step = df_history["step"].iloc[i]
            entry_price = df_history["open"].iloc[i]
            entry_date = df_history["date"].iloc[i]

        if df_history["position"].iloc[i] == 0 and df_history["position"].iloc[i - 1] == 1:
            exit_step = df_history["step"].iloc[i]
            exit_price = df_history["open"].iloc[i]
            exit_date = df_history["date"].iloc[i]

            if entry_step is not None:
                net_return = (
                    (1.0 - float(buy_fee_rate))
                    * (1.0 - float(sell_fee_rate) - float(capital_gains_tax_rate))
                    * (exit_price / entry_price)
                    - 1.0
                )
                hold_days = exit_step - entry_step

                trades.append(
                    {
                        "entry_date": entry_date,
                        "exit_date": exit_date,
                        "entry_step": entry_step,
                        "exit_step": exit_step,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "hold_days": hold_days,
                        "return": net_return,
                        "profit": "Win" if net_return > 0 else "Loss",
                    }
                )

                entry_step = None

    return pd.DataFrame(trades)


def test_observation_snapshots_are_independent():
    """Consecutive observations must be independent arrays (no aliasing)."""
    opens = [100 + i for i in range(40)]
    df = create_price_dataframe(opens)
    env = TestEnv(
        df=df,
        start_idx=6,
        end_idx=30,
        mode="train",
        lookback_window=5,
        source_mode="return",
        min_hold_days=1,
        stop_loss=None,
        buy_fee_rate=0.001,
        sell_fee_rate=0.001,
        capital_gains_tax_rate=0.0,
    )

    obs0, _ = env.reset()
    obs1, _, _, _, _ = env.step(1)
    obs2, _, _, _, _ = env.step(1)

    assert not np.shares_memory(obs0, obs1), "obs0 and obs1 should not share memory"
    assert not np.shares_memory(obs1, obs2), "obs1 and obs2 should not share memory"

    obs1[:] = 12345.0
    fresh_obs = env._get_observation()
    assert not np.shares_memory(obs1, fresh_obs), "Mutated prior obs must not alias fresh observation"
    assert np.all(fresh_obs != 12345.0), "Mutating old observation must not affect current env observation"


def test_multistock_helper_data_is_preloaded_once():
    """Helper parquet files should be loaded once each, not once per stock."""
    base_tmp = Path(__file__).resolve().parent / "results" / f"_hotloop_preload_{uuid.uuid4().hex}"
    data_dir = os.path.join(str(base_tmp), "data")
    try:
        os.makedirs(data_dir, exist_ok=True)

        # Three base stocks.
        for ticker, base_price in [("ACB", 100.0), ("VNM", 120.0), ("HPG", 80.0)]:
            _make_df(0, 140, base_price).to_parquet(
                os.path.join(data_dir, f"gia_lich_su_{ticker}_1D.parquet"),
                index=False,
            )

        # Two helper tickers.
        _make_df(0, 140, 200.0).to_parquet(
            os.path.join(data_dir, "gia_lich_su_VNINDEX_1D.parquet"),
            index=False,
        )
        _make_df(0, 140, 300.0).to_parquet(
            os.path.join(data_dir, "gia_lich_su_VN30_1D.parquet"),
            index=False,
        )

        original_read_parquet = pd.read_parquet
        read_counts = {}

        def _counted_read_parquet(path, *args, **kwargs):
            normalized = os.path.normcase(os.path.abspath(str(path)))
            read_counts[normalized] = read_counts.get(normalized, 0) + 1
            return original_read_parquet(path, *args, **kwargs)

        with patch("pandas.read_parquet", side_effect=_counted_read_parquet):
            env = MultiStockEnv(
                data_dir=data_dir,
                mode="train",
                stocks=["ACB", "VNM", "HPG"],
                lookback_window=10,
                help_tickers=["VNINDEX", "VN30"],
                market_data_dir=data_dir,
            )
            env.close()

        helper_paths = [
            os.path.normcase(os.path.abspath(os.path.join(data_dir, "gia_lich_su_VNINDEX_1D.parquet"))),
            os.path.normcase(os.path.abspath(os.path.join(data_dir, "gia_lich_su_VN30_1D.parquet"))),
        ]
        for helper_path in helper_paths:
            assert read_counts.get(helper_path, 0) == 1, (
                f"Expected helper parquet to be read once: {helper_path}, "
                f"got {read_counts.get(helper_path, 0)}"
            )
    finally:
        shutil.rmtree(base_tmp, ignore_errors=True)


def test_extract_trades_matches_reference_implementation():
    """Optimized trade extraction must match the pre-optimization output."""
    df_history = pd.DataFrame(
        {
            "step": np.arange(12),
            "date": pd.date_range("2025-01-01", periods=12, freq="D"),
            "open": np.array([100, 101, 102, 103, 104, 105, 106, 105, 104, 103, 102, 101], dtype=float),
            "position": np.array([0, 1, 1, 0, 0, 1, 1, 1, 0, 0, 1, 0], dtype=int),
            "close": np.array([100, 101, 102, 103, 104, 105, 106, 105, 104, 103, 102, 101], dtype=float),
            "hold_count": np.array([0, 1, 2, 0, 0, 1, 2, 3, 0, 0, 1, 0], dtype=int),
            "action": np.array([0, 1, 1, 0, 0, 1, 1, 1, 0, 0, 1, 0], dtype=int),
            "reward": np.zeros(12, dtype=float),
            "portfolio_value": np.ones(12, dtype=float),
        }
    )
    buy_fee_rate = 0.003
    sell_fee_rate = 0.003
    capital_gains_tax_rate = 0.001

    actual = _extract_trades(
        df_history,
        buy_fee_rate=buy_fee_rate,
        sell_fee_rate=sell_fee_rate,
        capital_gains_tax_rate=capital_gains_tax_rate,
    ).reset_index(drop=True)
    expected = _extract_trades_reference(
        df_history,
        buy_fee_rate=buy_fee_rate,
        sell_fee_rate=sell_fee_rate,
        capital_gains_tax_rate=capital_gains_tax_rate,
    ).reset_index(drop=True)

    assert_frame_equal(actual, expected, check_dtype=False, check_exact=False, rtol=1e-12, atol=1e-12)
