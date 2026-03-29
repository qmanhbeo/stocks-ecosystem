from __future__ import annotations

import pandas as pd

from src.exit_alpha import ExitRuleSpec, build_exit_state_panel
from src.deterministic_portfolio import _build_thesis_family_matrix, _compute_exit_signal_mask


def test_exit_rule_spec_variant_name_is_stable() -> None:
    spec = ExitRuleSpec(
        family="rank_decay",
        params={"rank_exit_threshold": 8, "replacement_margin": 0.05},
    )
    assert spec.variant_name == "rank_decay__rank_exit_threshold_8__replacement_margin_0p05"


def test_build_exit_state_panel_filters_to_preexisting_positions() -> None:
    blotter = pd.DataFrame(
        [
            {
                "signal_date": "2026-01-01",
                "execution_date": "2026-01-02",
                "ticker": "AAA",
                "held_before": True,
                "holding_age_before": 4,
                "signal_score": 0.7,
                "score_rank": 3.0,
                "entry_score": 0.8,
                "entry_rank": 2.0,
                "score_change_since_entry": -0.1,
                "return_since_entry": 0.12,
                "peak_return_since_entry": 0.15,
                "underwater_days_since_entry": 1,
                "blocked_sell_streak": 1,
                "entry_thesis_family": "breakout_followthrough",
                "entry_thesis_score": 0.75,
                "current_thesis_score": 0.52,
                "thesis_score_change_since_entry": -0.23,
                "can_sell_next_open": True,
                "sell_blocked": False,
                "exit_signal": True,
                "requested_action": "sell",
                "executed_action": "sell",
            },
            {
                "signal_date": "2026-01-01",
                "execution_date": "2026-01-02",
                "ticker": "BBB",
                "held_before": False,
                "holding_age_before": 0,
                "signal_score": 0.9,
                "requested_action": "buy",
                "executed_action": "buy",
            },
        ]
    )
    panel = build_exit_state_panel(blotter)
    assert panel["ticker"].tolist() == ["AAA"]
    assert panel["exit_signal"].tolist() == [True]
    assert "entry_thesis_family" in panel.columns


def test_build_thesis_family_matrix_averages_available_components() -> None:
    feature_matrices = {
        "s1_proba": pd.DataFrame([[0.8, 0.2]]).to_numpy(),
        "c11_ret_60d_lag_rank": pd.DataFrame([[0.6, 0.4]]).to_numpy(),
        "c12_gap_absorb_3": pd.DataFrame([[0.9, 0.3]]).to_numpy(),
        "c13_compress_blowoff_2": pd.DataFrame([[0.7, 0.1]]).to_numpy(),
        "c14_clv_volconf_resid_rank": pd.DataFrame([[0.5, 0.4]]).to_numpy(),
        "c8_vol_zscore_5d": pd.DataFrame([[0.6, 0.2]]).to_numpy(),
        "c7_ceiling_count_5d": pd.DataFrame([[0.4, 0.9]]).to_numpy(),
        "c10_illiq_level_rank": pd.DataFrame([[0.2, 0.8]]).to_numpy(),
    }
    matrix, names = _build_thesis_family_matrix(feature_matrices)
    assert names == ("momentum_continuation", "breakout_followthrough", "crowding_pressure")
    assert matrix.shape == (3, 1, 2)
    assert matrix[0, 0, 0] == 0.7


def test_thesis_inconsistency_exit_uses_entry_family_drop() -> None:
    current_thesis_scores = pd.DataFrame([[0.40, 0.60], [0.80, 0.20]]).to_numpy()
    exit_mask = _compute_exit_signal_mask(
        exit_rule_name="thesis_inconsistency",
        exit_rule_params={"thesis_drop_threshold": 0.15, "score_drop_threshold": 0.05},
        scores=pd.Series([0.50, 0.70]).to_numpy(),
        rank_positions=pd.Series([6.0, 2.0]).to_numpy(),
        holding_ages=pd.Series([4, 4]).to_numpy(),
        held_mask=pd.Series([True, True]).to_numpy(),
        eligible_mask=pd.Series([True, True]).to_numpy(),
        required_holding_age=3,
        top_k=5,
        blocked_sell_streaks=pd.Series([0, 0]).to_numpy(),
        entry_scores=pd.Series([0.65, 0.72]).to_numpy(),
        return_since_entry=pd.Series([0.02, 0.10]).to_numpy(),
        adv20_current=pd.Series([1.0, 1.0]).to_numpy(),
        entry_adv20_values=pd.Series([1.0, 1.0]).to_numpy(),
        peak_return_since_entry=pd.Series([0.05, 0.12]).to_numpy(),
        underwater_days_since_entry=pd.Series([1, 0]).to_numpy(),
        entry_thesis_family_codes=pd.Series([0, 1]).to_numpy(),
        entry_thesis_scores=pd.Series([0.70, 0.82]).to_numpy(),
        current_thesis_scores=current_thesis_scores,
    )
    assert exit_mask.tolist() == [True, False]


def test_failed_followthrough_exit_requires_no_progress() -> None:
    exit_mask = _compute_exit_signal_mask(
        exit_rule_name="failed_followthrough",
        exit_rule_params={"grace_days": 2, "peak_return_threshold": 0.03, "current_return_threshold": 0.0, "score_drop_threshold": 0.0},
        scores=pd.Series([0.50]).to_numpy(),
        rank_positions=pd.Series([4.0]).to_numpy(),
        holding_ages=pd.Series([5]).to_numpy(),
        held_mask=pd.Series([True]).to_numpy(),
        eligible_mask=pd.Series([True]).to_numpy(),
        required_holding_age=3,
        top_k=5,
        blocked_sell_streaks=pd.Series([0]).to_numpy(),
        entry_scores=pd.Series([0.55]).to_numpy(),
        return_since_entry=pd.Series([-0.01]).to_numpy(),
        adv20_current=pd.Series([1.0]).to_numpy(),
        entry_adv20_values=pd.Series([1.0]).to_numpy(),
        peak_return_since_entry=pd.Series([0.02]).to_numpy(),
        underwater_days_since_entry=pd.Series([2]).to_numpy(),
        entry_thesis_family_codes=pd.Series([-1]).to_numpy(),
        entry_thesis_scores=pd.Series([float("nan")]).to_numpy(),
        current_thesis_scores=None,
    )
    assert exit_mask.tolist() == [True]


def test_time_under_water_exit_requires_persistent_stall() -> None:
    exit_mask = _compute_exit_signal_mask(
        exit_rule_name="time_under_water",
        exit_rule_params={"grace_days": 5, "underwater_days_threshold": 3, "peak_return_threshold": 0.05},
        scores=pd.Series([0.60]).to_numpy(),
        rank_positions=pd.Series([3.0]).to_numpy(),
        holding_ages=pd.Series([8]).to_numpy(),
        held_mask=pd.Series([True]).to_numpy(),
        eligible_mask=pd.Series([True]).to_numpy(),
        required_holding_age=3,
        top_k=5,
        blocked_sell_streaks=pd.Series([0]).to_numpy(),
        entry_scores=pd.Series([0.62]).to_numpy(),
        return_since_entry=pd.Series([-0.02]).to_numpy(),
        adv20_current=pd.Series([1.0]).to_numpy(),
        entry_adv20_values=pd.Series([1.0]).to_numpy(),
        peak_return_since_entry=pd.Series([0.03]).to_numpy(),
        underwater_days_since_entry=pd.Series([4]).to_numpy(),
        entry_thesis_family_codes=pd.Series([-1]).to_numpy(),
        entry_thesis_scores=pd.Series([float("nan")]).to_numpy(),
        current_thesis_scores=None,
    )
    assert exit_mask.tolist() == [True]
