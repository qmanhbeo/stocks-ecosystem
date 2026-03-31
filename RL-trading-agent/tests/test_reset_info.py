from __future__ import annotations

from test_utils import TestEnv, create_price_dataframe


def test_reset_info_total_steps_is_inclusive() -> None:
    df = create_price_dataframe([10, 11, 12, 13, 14, 15, 16])
    env = TestEnv(
        df=df,
        start_idx=3,
        end_idx=5,
        mode="train",
        lookback_window=2,
        source_mode="raw",
        min_hold_days=1,
        stop_loss=None,
        buy_fee_rate=0.0,
        sell_fee_rate=0.0,
        capital_gains_tax_rate=0.0,
    )

    _, info = env.reset()

    assert info["start_idx"] == 3
    assert info["end_idx"] == 5
    assert info["total_steps"] == 3
