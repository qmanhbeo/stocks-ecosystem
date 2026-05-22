import pandas as pd

from risk_policy import (
    DEFAULT_RISK_POLICY,
    STATUS_EXECUTION_VALIDATED,
    STATUS_LAB_PROMOTED_PENDING_EXECUTION,
    STATUS_OVERRIDE_PROMOTED,
    STATUS_RESEARCH_CANDIDATE,
    derive_execution_status,
    evaluate_strategy_row,
)


def test_evaluate_strategy_row_all_pass() -> None:
    row = pd.Series(
        {
            "positive_folds": 8,
            "beating_benchmark_folds": 6,
            "mean_excess_return": 0.01,
            "mean_max_drawdown": 0.2,
            "worst_fold_return": -0.2,
            "failure_cash_pct": 50.0,
            "failure_underfill_pct": 40.0,
            "failure_selection_fill_rate": 0.5,
        }
    )
    gates = evaluate_strategy_row(row, policy=DEFAULT_RISK_POLICY)
    assert gates["all_pass"] is True


def test_evaluate_strategy_row_fail() -> None:
    row = pd.Series(
        {
            "positive_folds": 5,
            "beating_benchmark_folds": 2,
            "mean_excess_return": -0.01,
            "mean_max_drawdown": 0.5,
            "worst_fold_return": -0.4,
        }
    )
    gates = evaluate_strategy_row(row, policy=DEFAULT_RISK_POLICY)
    assert gates["all_pass"] is False


def test_derive_execution_status_defaults() -> None:
    status, warning = derive_execution_status(
        strategy_name="m_c8_vol_zscore_5d_depth5",
        checks={"all_pass": True},
        manual_override=False,
    )
    assert status == STATUS_EXECUTION_VALIDATED
    assert warning == ""

    status, warning = derive_execution_status(
        strategy_name="m_c8_vol_zscore_5d_depth5",
        checks={"all_pass": False},
        manual_override=False,
    )
    assert status == STATUS_LAB_PROMOTED_PENDING_EXECUTION
    assert "failed execution validation gates" in warning


def test_derive_execution_status_override() -> None:
    status, warning = derive_execution_status(
        strategy_name="m_c8_vol_zscore_5d_depth5",
        checks={"all_pass": False},
        manual_override=True,
    )
    assert status == STATUS_OVERRIDE_PROMOTED
    assert "manual override" in warning


def test_derive_execution_status_respects_upstream_research_candidate() -> None:
    status, warning = derive_execution_status(
        strategy_name="m_c8_vol_zscore_5d_depth5",
        checks={"all_pass": True},
        manual_override=False,
        upstream_status=STATUS_RESEARCH_CANDIDATE,
    )
    assert status == STATUS_RESEARCH_CANDIDATE
    assert "blocked by upstream contract status" in warning


def test_derive_execution_status_rejects_invalid_upstream_status() -> None:
    status, warning = derive_execution_status(
        strategy_name="m_c8_vol_zscore_5d_depth5",
        checks={"all_pass": True},
        manual_override=False,
        upstream_status="NOT_A_STATUS",
    )
    assert status == STATUS_RESEARCH_CANDIDATE
    assert "invalid upstream status" in warning
