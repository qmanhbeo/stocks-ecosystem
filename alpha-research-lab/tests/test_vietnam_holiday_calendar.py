from __future__ import annotations

import pandas as pd

from src.vietnam_holiday_calendar import build_vietnam_major_holiday_states, holiday_state_data_checks


def test_tet_states_are_trading_dates_and_exclude_forward_years():
    all_days = pd.date_range("2024-02-01", "2024-02-23", freq="B")
    closed = pd.to_datetime(
        [
            "2024-02-08",
            "2024-02-09",
            "2024-02-12",
            "2024-02-13",
            "2024-02-14",
        ]
    )
    trading_dates = pd.DatetimeIndex([day for day in all_days if day not in set(closed)])

    states, clusters = build_vietnam_major_holiday_states(trading_dates, start_year=2024, end_year=2024)
    tet_states = states.loc[states["holiday_family"].eq("tet")].copy()

    assert not tet_states.empty
    assert set(tet_states["holiday_state"]) == {"pre_1", "pre_2", "pre_3", "pre_5", "post_1", "post_2", "post_3", "post_5"}
    assert pd.Timestamp("2024-02-07") in set(tet_states["time"])
    assert pd.Timestamp("2024-02-15") in set(tet_states["time"])
    assert int(tet_states["closure_weekdays"].max()) == 5
    assert clusters["holiday_cluster"].str.contains("tet").any()

    checks = holiday_state_data_checks(states, trading_dates, start_year=2024, end_year=2024)
    assert checks["all_state_dates_in_trading_calendar"] is True
    assert checks["state_rows_with_2026_or_later"] == 0
    assert checks["state_rows_outside_requested_years"] == 0
