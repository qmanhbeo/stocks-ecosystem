import numpy as np
import pandas as pd

from signal_sweep import _classify_strategy, _load_horizon_lens_payload, _strategy_to_signal_id


def test_classify_promote_candidate() -> None:
    row = pd.Series(
        {
            "is_profit_ready": True,
            "mean_excess_return": 0.01,
            "worst_fold_return": -0.2,
        }
    )
    label, _ = _classify_strategy(
        readiness_row=row,
        failure_excess=0.02,
        failure_cash=50.0,
        failure_underfill=45.0,
        baseline_failure_excess=0.01,
        baseline_failure_cash=52.0,
        baseline_failure_underfill=48.0,
    )
    assert label == "PROMOTE_CANDIDATE"


def test_classify_kill_on_negative_excess_or_tail() -> None:
    row = pd.Series(
        {
            "is_profit_ready": False,
            "mean_excess_return": -0.06,
            "worst_fold_return": -0.2,
        }
    )
    label, _ = _classify_strategy(
        readiness_row=row,
        failure_excess=np.nan,
        failure_cash=np.nan,
        failure_underfill=np.nan,
        baseline_failure_excess=None,
        baseline_failure_cash=None,
        baseline_failure_underfill=None,
    )
    assert label == "KILL"


def test_classify_research_only_when_mixed() -> None:
    row = pd.Series(
        {
            "is_profit_ready": False,
            "mean_excess_return": -0.01,
            "worst_fold_return": -0.25,
        }
    )
    label, _ = _classify_strategy(
        readiness_row=row,
        failure_excess=0.0,
        failure_cash=60.0,
        failure_underfill=60.0,
        baseline_failure_excess=0.01,
        baseline_failure_cash=55.0,
        baseline_failure_underfill=55.0,
    )
    assert label == "RESEARCH_ONLY"


def test_strategy_to_signal_id_mapping() -> None:
    assert _strategy_to_signal_id("ctrl_s1_depth5") == "s1"
    assert _strategy_to_signal_id("m_c11_ret_60d_lag_rank_depth5") == "c11"
    assert _strategy_to_signal_id("s1b_c8_vol_zscore_5d_70_30_depth5") == "c8"


def test_strategy_to_signal_id_unknown() -> None:
    assert _strategy_to_signal_id("some_custom_strategy") is None


def test_load_horizon_lens_payload_reads_and_widens(tmp_path) -> None:
    path = tmp_path / "profit_horizon_metrics.csv"
    pd.DataFrame(
        [
            {
                "strategy_name": "s1",
                "horizon": "W",
                "mean_return": 0.01,
                "positive_period_rate": 0.6,
                "worst_period_return": -0.05,
                "n_periods": 40,
                "window_start": "2015-01-01",
                "window_end": "2025-12-31",
                "selection_lockbox_max_date": "2025-12-31",
                "informational_lens_only": True,
            },
            {
                "strategy_name": "s1",
                "horizon": "M",
                "mean_return": 0.02,
                "positive_period_rate": 0.7,
                "worst_period_return": -0.08,
                "n_periods": 12,
                "window_start": "2015-01-01",
                "window_end": "2025-12-31",
                "selection_lockbox_max_date": "2025-12-31",
                "informational_lens_only": True,
            },
        ]
    ).to_csv(path, index=False)

    wide_df, summary = _load_horizon_lens_payload(path)
    assert summary["enabled"] is True
    assert summary["horizons"] == ["M", "W"]
    assert summary["window_end"] == "2025-12-31"
    assert summary["informational_only"] is True
    assert len(wide_df) == 1
    row = wide_df.iloc[0]
    assert row["strategy_name"] == "s1"
    assert row["h_w_n_periods"] == 40
    assert row["h_m_n_periods"] == 12
