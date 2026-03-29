from __future__ import annotations

import pandas as pd

from src.activation_meta import _forward_gross_returns
from src.activation_meta_experiment_utils import (
    hysteresis_schedule,
    selector_recent_hit_rate_ewm,
    selector_recent_relative_ewm_from_prev,
    subperiod_relative_return,
    thresholded_three_state_schedule,
    three_level_schedule,
    walk_forward_logistic_scores,
)


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


def test_thresholded_three_state_schedule_respects_thresholds():
    series = pd.Series([-0.02, -0.005, 0.02], dtype=float)
    out = thresholded_three_state_schedule(series, low_threshold=-0.01, high_threshold=0.01)
    assert out.tolist() == [0.0, 0.5, 1.0]


def test_subperiod_relative_return_uses_subset_only():
    daily = pd.DataFrame(
        {
            "execution_date": pd.to_datetime(["2020-01-02", "2020-01-03", "2021-01-04"]),
            "portfolio_return": [0.10, 0.0, 0.10],
            "benchmark_return": [0.0, 0.0, 0.0],
        }
    )
    assert round(subperiod_relative_return(daily, start_year=2020, end_year=2020), 6) == 0.10


def test_walk_forward_logistic_scores_only_fill_after_min_train_years():
    frame = pd.DataFrame(
        {
            "time": pd.to_datetime(
                [
                    "2019-01-01",
                    "2019-06-01",
                    "2020-01-01",
                    "2020-06-01",
                    "2021-01-01",
                    "2021-06-01",
                ]
            ),
            "feature_a": [0.0, 0.1, 0.2, 0.3, 0.8, 0.9],
            "feature_b": [0.0, 0.1, 0.2, 0.2, 0.8, 0.9],
            "target": [0, 0, 0, 1, 1, 1],
        }
    )
    scores = walk_forward_logistic_scores(
        frame,
        feature_columns=["feature_a", "feature_b"],
        target_column="target",
        min_train_years=2,
    )
    assert scores.iloc[:4].isna().all()
    assert scores.iloc[4:].notna().all()


def test_selector_recent_relative_ewm_from_prev_uses_prev_cycle_series():
    frame = pd.DataFrame({"full_prev_cycle_relative_return": [0.10, 0.00, -0.10]})
    out = selector_recent_relative_ewm_from_prev(frame, prefix="full", span=2)
    assert round(float(out.iloc[0]), 6) == 0.10
    assert round(float(out.iloc[-1]), 6) < 0.0


def test_selector_recent_hit_rate_ewm_reads_requested_span():
    frame = pd.DataFrame({"full_recent_hit_rate_ewm5": [0.2, 0.4, 0.6]})
    out = selector_recent_hit_rate_ewm(frame, prefix="full", span=5)
    assert out.tolist() == [0.2, 0.4, 0.6]
