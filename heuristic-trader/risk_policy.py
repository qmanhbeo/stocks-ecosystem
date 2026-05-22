"""
Explicit risk and promotion policy for heuristic-trader.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

STATUS_RESEARCH_CANDIDATE = "RESEARCH_CANDIDATE"
STATUS_LAB_PROMOTED_PENDING_EXECUTION = "LAB_PROMOTED_PENDING_EXECUTION"
STATUS_EXECUTION_VALIDATED = "EXECUTION_VALIDATED"
STATUS_FINAL_PROMOTED = "FINAL_PROMOTED"
STATUS_OVERRIDE_PROMOTED = "OVERRIDE_PROMOTED"

VALID_PROMOTION_STATUSES = {
    STATUS_RESEARCH_CANDIDATE,
    STATUS_LAB_PROMOTED_PENDING_EXECUTION,
    STATUS_EXECUTION_VALIDATED,
    STATUS_FINAL_PROMOTED,
    STATUS_OVERRIDE_PROMOTED,
}

UPSTREAM_EXECUTION_ELIGIBLE_STATUSES = {
    STATUS_LAB_PROMOTED_PENDING_EXECUTION,
    STATUS_EXECUTION_VALIDATED,
    STATUS_FINAL_PROMOTED,
    STATUS_OVERRIDE_PROMOTED,
}


@dataclass(frozen=True)
class RiskPolicy:
    # Portfolio robustness / readiness
    min_positive_folds: int = 7
    min_beating_benchmark_folds: int = 5
    min_mean_excess_return: float = 0.0
    max_mean_drawdown: float = 0.35
    max_worst_fold_return: float = -0.30

    # Execution health
    max_failure_cash_pct: float = 65.0
    max_failure_underfill_pct: float = 65.0
    min_failure_selection_fill_rate: float = 0.35


DEFAULT_RISK_POLICY = RiskPolicy()


def evaluate_strategy_row(
    row: pd.Series,
    *,
    policy: RiskPolicy = DEFAULT_RISK_POLICY,
) -> dict[str, Any]:
    """Evaluate strategy row against explicit risk gates."""
    checks = {
        "gate_positive_folds": int(row.get("positive_folds", 0)) >= policy.min_positive_folds,
        "gate_beating_benchmark": int(row.get("beating_benchmark_folds", 0)) >= policy.min_beating_benchmark_folds,
        "gate_mean_excess": float(row.get("mean_excess_return", float("nan"))) >= policy.min_mean_excess_return,
        "gate_mean_drawdown": float(row.get("mean_max_drawdown", float("nan"))) <= policy.max_mean_drawdown,
        "gate_worst_fold": float(row.get("worst_fold_return", float("nan"))) >= policy.max_worst_fold_return,
    }

    failure_cash = row.get("failure_cash_pct", float("nan"))
    if pd.notna(failure_cash):
        checks["gate_failure_cash"] = float(failure_cash) <= policy.max_failure_cash_pct

    failure_underfill = row.get("failure_underfill_pct", float("nan"))
    if pd.notna(failure_underfill):
        checks["gate_failure_underfill"] = float(failure_underfill) <= policy.max_failure_underfill_pct

    failure_fill = row.get("failure_selection_fill_rate", float("nan"))
    if pd.notna(failure_fill):
        checks["gate_failure_selection_fill"] = float(failure_fill) >= policy.min_failure_selection_fill_rate

    checks["all_pass"] = all(checks.values())
    return checks


def policy_dict(policy: RiskPolicy = DEFAULT_RISK_POLICY) -> dict[str, Any]:
    return asdict(policy)


def infer_lab_handoff_status(strategy_name: str) -> str:
    """
    Infer upstream lab handoff status for a strategy row.

    Sweep controls are treated as research comparators, while non-control
    strategies are treated as lab-promoted candidates pending execution
    validation.
    """
    if str(strategy_name).startswith("ctrl_"):
        return STATUS_RESEARCH_CANDIDATE
    return STATUS_LAB_PROMOTED_PENDING_EXECUTION


def derive_execution_status(
    *,
    strategy_name: str,
    checks: dict[str, Any],
    manual_override: bool = False,
    upstream_status: str | None = None,
) -> tuple[str, str]:
    """
    Map gate checks to contract status.

    Returns:
        (promotion_status, status_warning)
    """
    if manual_override:
        return STATUS_OVERRIDE_PROMOTED, "manual override enabled; require explicit note justification"

    if upstream_status is not None and upstream_status not in VALID_PROMOTION_STATUSES:
        return STATUS_RESEARCH_CANDIDATE, f"invalid upstream status '{upstream_status}'"

    if upstream_status is not None and upstream_status not in UPSTREAM_EXECUTION_ELIGIBLE_STATUSES:
        return STATUS_RESEARCH_CANDIDATE, (
            f"blocked by upstream contract status '{upstream_status}' "
            "(requires LAB_PROMOTED_PENDING_EXECUTION or higher)"
        )

    all_pass = bool(checks.get("all_pass", False))
    if all_pass:
        return STATUS_EXECUTION_VALIDATED, ""

    upstream = upstream_status or infer_lab_handoff_status(strategy_name)
    if upstream == STATUS_LAB_PROMOTED_PENDING_EXECUTION:
        return upstream, "lab-promoted signal failed execution validation gates"

    return STATUS_RESEARCH_CANDIDATE, "did not clear readiness gates"
