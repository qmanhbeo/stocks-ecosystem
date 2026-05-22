import pandas as pd

from select_challenge_set import _select_challenger


def test_select_challenger_prefers_promote() -> None:
    df = pd.DataFrame(
        [
            {"strategy_name": "base", "decision_label": "KILL", "mean_excess_return": -0.1, "mean_annualized_return": 0.0},
            {"strategy_name": "a", "decision_label": "RESEARCH_ONLY", "mean_excess_return": 0.02, "mean_annualized_return": 0.05},
            {"strategy_name": "b", "decision_label": "PROMOTE_CANDIDATE", "mean_excess_return": 0.01, "mean_annualized_return": 0.04},
        ]
    )
    challenger, reason = _select_challenger(df, baseline="base")
    assert challenger == "b"
    assert "PROMOTE_CANDIDATE" in reason


def test_select_challenger_fallback_research() -> None:
    df = pd.DataFrame(
        [
            {"strategy_name": "base", "decision_label": "KILL", "mean_excess_return": -0.1, "mean_annualized_return": 0.0},
            {"strategy_name": "a", "decision_label": "RESEARCH_ONLY", "mean_excess_return": 0.02, "mean_annualized_return": 0.05},
            {"strategy_name": "b", "decision_label": "RESEARCH_ONLY", "mean_excess_return": 0.01, "mean_annualized_return": 0.04},
        ]
    )
    challenger, reason = _select_challenger(df, baseline="base", selection_mode="research")
    assert challenger == "a"
    assert "RESEARCH_ONLY" in reason


def test_select_challenger_fallback_non_baseline_when_all_kill() -> None:
    df = pd.DataFrame(
        [
            {"strategy_name": "base", "decision_label": "KILL", "mean_excess_return": -0.2, "mean_annualized_return": 0.0},
            {"strategy_name": "a", "decision_label": "KILL", "mean_excess_return": -0.05, "mean_annualized_return": 0.03},
            {"strategy_name": "b", "decision_label": "KILL", "mean_excess_return": -0.1, "mean_annualized_return": 0.04},
        ]
    )
    challenger, reason = _select_challenger(df, baseline="base", selection_mode="any")
    assert challenger == "a"
    assert "fallback top non-baseline" in reason


def test_select_challenger_strict_returns_none_when_no_promote() -> None:
    df = pd.DataFrame(
        [
            {"strategy_name": "base", "decision_label": "KILL", "mean_excess_return": -0.2, "mean_annualized_return": 0.0},
            {"strategy_name": "a", "decision_label": "RESEARCH_ONLY", "mean_excess_return": 0.01, "mean_annualized_return": 0.03},
        ]
    )
    challenger, reason = _select_challenger(df, baseline="base")
    assert challenger is None
    assert "no strict-eligible" in reason
