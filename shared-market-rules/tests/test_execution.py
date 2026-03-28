from __future__ import annotations

import pandas as pd

from shared_market_rules import (
    compute_tradability_flags,
    earliest_sell_step_after_entry,
    required_holding_age_for_sell,
)


def test_compute_tradability_flags_blocks_limit_and_zero_volume_days():
    frame = pd.DataFrame(
        {
            "time": pd.date_range("2024-01-01", periods=4, freq="D"),
            "ticker": ["AAA"] * 4,
            "close": [100.0, 107.0, 99.51, 101.0],
            "volume": [1_000.0, 1_000.0, 0.0, 1_000.0],
        }
    )

    flags = compute_tradability_flags(frame)

    assert bool(flags.loc[1, "is_ceiling"])
    assert not bool(flags.loc[1, "can_buy_next_open"])
    assert bool(flags.loc[1, "can_sell_next_open"])

    assert bool(flags.loc[2, "is_floor"])
    assert not bool(flags.loc[2, "has_volume"])
    assert not bool(flags.loc[2, "can_buy_next_open"])
    assert not bool(flags.loc[2, "can_sell_next_open"])


def test_settlement_helpers_map_entry_to_earliest_sell_step():
    assert required_holding_age_for_sell() == 3
    assert required_holding_age_for_sell(min_hold_days_override=1) == 3
    assert required_holding_age_for_sell(min_hold_days_override=5) == 5
    assert earliest_sell_step_after_entry(5) == 8
