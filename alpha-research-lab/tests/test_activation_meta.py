from __future__ import annotations

import pandas as pd

from src.activation_meta import _forward_gross_returns
from src.activation_meta_experiment_utils import hysteresis_schedule, three_level_schedule


def test_forward_gross_returns_aligns_future_window_to_current_row():
    series = pd.Series([0.10, 0.00, -0.10, 0.05], dtype=float)
    out = _forward_gross_returns(series, 2)
    assert round(float(out.iloc[0]), 6) == 0.10
    assert round(float(out.iloc[1]), 6) == -0.10
    assert pd.isna(out.iloc[3])


def test_three_level_schedule_maps_quantiles_to_zero_half_full():
    series = pd.Series([1.0, 2.0, 3.0, 4.0], dtype=float)
    out = three_level_schedule(series, mid_quantile=0.50, high_quantile=0.75)
    assert set(out.round(6).tolist()) <= {0.0, 0.5, 1.0}
    assert float(out.iloc[-1]) == 1.0


def test_hysteresis_schedule_requires_streaks_to_flip_state():
    strong = pd.Series([False, True, True, False, False, True, True], dtype=bool)
    weak = pd.Series([False, False, False, True, True, False, False], dtype=bool)
    out = hysteresis_schedule(strong, weak, on_streak=2, off_streak=2)
    assert out.tolist() == [0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0]
