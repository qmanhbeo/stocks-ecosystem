from __future__ import annotations

import pandas as pd

from data_tools.build_tradability_flags import build_tradability_frame


def test_build_tradability_frame_emits_expected_columns(tmp_path):
    price_df = pd.DataFrame(
        {
            "time": pd.date_range("2024-01-01", periods=4, freq="D"),
            "open": [100.0, 100.0, 100.0, 100.0],
            "high": [100.0, 107.0, 100.0, 101.0],
            "low": [100.0, 100.0, 93.0, 100.0],
            "close": [100.0, 107.0, 93.0, 101.0],
            "volume": [1_000.0, 1_000.0, 0.0, 1_000.0],
        }
    )
    price_df.to_parquet(tmp_path / "gia_lich_su_ACB_1D.parquet", index=False)

    tradability = build_tradability_frame(tmp_path)

    assert list(tradability.columns) == [
        "time",
        "ticker",
        "has_volume",
        "is_ceiling",
        "is_floor",
        "can_buy_next_open",
        "can_sell_next_open",
    ]
    assert tradability["ticker"].unique().tolist() == ["ACB"]
    assert bool(tradability.loc[1, "is_ceiling"])
    assert not bool(tradability.loc[1, "can_buy_next_open"])
    assert not bool(tradability.loc[2, "can_sell_next_open"])
