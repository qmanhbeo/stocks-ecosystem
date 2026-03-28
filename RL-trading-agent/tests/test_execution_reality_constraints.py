from __future__ import annotations

import numpy as np
import pandas as pd

from test_utils import TestEnv


def _make_df(opens: list[float], closes: list[float] | None = None, volumes: list[float] | None = None) -> pd.DataFrame:
    closes = closes if closes is not None else list(opens)
    volumes = volumes if volumes is not None else [1.0] * len(opens)
    highs = [max(o, c) for o, c in zip(opens, closes)]
    lows = [min(o, c) for o, c in zip(opens, closes)]
    return pd.DataFrame(
        {
            "time": np.arange(len(opens)),
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        }
    )


def _make_env(df: pd.DataFrame, **kwargs) -> TestEnv:
    common = {
        "df": df,
        "start_idx": 4,
        "end_idx": len(df) - 2,
        "mode": "train",
        "lookback_window": 3,
        "source_mode": "return",
        "buy_fee_rate": 0.0,
        "sell_fee_rate": 0.0,
        "capital_gains_tax_rate": 0.0,
        "stop_loss": None,
    }
    common.update(kwargs)
    return TestEnv(**common)


def test_default_settlement_blocks_exit_until_t_plus_3_open():
    env = _make_env(_make_df([100.0] * 12))
    env.reset()

    env.step(1)
    assert env.position == 1
    assert env.hold_count == 1
    assert env.pending_action == 1

    env.step(0)
    assert env.position == 1
    assert env.hold_count == 2
    assert env.pending_action == 1

    env.step(0)
    assert env.position == 0


def test_zero_volume_execution_day_blocks_buys():
    df = _make_df(
        [100.0] * 12,
        volumes=[1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
    )
    env = _make_env(df)
    env.reset()

    env.step(1)
    assert env.position == 0


def test_ceiling_execution_day_blocks_buys():
    closes = [100.0, 100.0, 100.0, 100.0, 100.0, 107.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0]
    env = _make_env(_make_df([100.0] * 12, closes=closes))
    env.reset()

    env.step(1)
    assert env.position == 0


def test_floor_execution_day_blocks_sells():
    closes = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 93.0, 100.0, 100.0, 100.0, 100.0, 100.0]
    env = _make_env(_make_df([100.0] * 12, closes=closes), min_hold_days=1)
    env.reset()

    env.step(1)
    assert env.position == 1

    env.step(0)
    assert env.position == 1
