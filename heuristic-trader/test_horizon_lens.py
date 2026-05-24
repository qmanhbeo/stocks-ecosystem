import math

import pandas as pd

from horizon_lens import compute_horizon_metrics_from_curve, horizon_metrics_to_wide, to_records


def test_compute_horizon_metrics_from_curve_constant_growth() -> None:
    dates = pd.bdate_range("2024-01-02", periods=260)
    portfolio_value = 100.0 * (1.001 ** pd.Series(range(len(dates)), dtype=float))
    curve = pd.DataFrame({"date": dates, "portfolio_value": portfolio_value})

    stats = compute_horizon_metrics_from_curve(curve)
    by_horizon = {s.horizon: s for s in stats}
    assert set(by_horizon.keys()) == {"W", "M", "Q", "6M"}
    for horizon in ("W", "M", "Q", "6M"):
        s = by_horizon[horizon]
        assert s.n_periods > 0
        assert math.isclose(s.positive_period_rate, 1.0, rel_tol=1e-9)
        assert s.worst_period_return > 0.0


def test_horizon_metrics_to_wide_handles_empty_and_roundtrip() -> None:
    empty = horizon_metrics_to_wide(pd.DataFrame())
    assert list(empty.columns) == ["strategy_name"]

    curve = pd.DataFrame(
        {
            "date": pd.bdate_range("2025-01-02", periods=130),
            "portfolio_value": pd.Series([100.0 + i for i in range(130)], dtype=float),
        }
    )
    stats = compute_horizon_metrics_from_curve(curve)
    long_df = pd.DataFrame(to_records("sample_strategy", stats))
    wide = horizon_metrics_to_wide(long_df)
    assert len(wide) == 1
    row = wide.iloc[0]
    assert row["strategy_name"] == "sample_strategy"
    assert "h_w_mean_return" in wide.columns
    assert "h_6m_n_periods" in wide.columns
