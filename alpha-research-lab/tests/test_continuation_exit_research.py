from __future__ import annotations

import pandas as pd

from src.continuation_exit_research import ContinuationModelSpec, fit_continuation_model


def test_fit_continuation_model_returns_raw_coefficients_and_scores() -> None:
    frame = pd.DataFrame(
        {
            'holding_age_before': [3, 4, 5, 6, 3, 4, 5, 6, 3, 4, 5, 6],
            'score_change_since_entry': [0.1, 0.05, -0.1, -0.2, 0.08, 0.02, -0.05, -0.15, 0.12, 0.03, -0.08, -0.12],
            'return_since_entry': [0.05, 0.03, -0.02, -0.08, 0.06, 0.01, -0.01, -0.05, 0.07, 0.02, -0.03, -0.04],
            'peak_return_since_entry': [0.06, 0.05, 0.01, 0.0, 0.08, 0.02, 0.03, 0.01, 0.09, 0.04, 0.02, 0.02],
            'underwater_days_since_entry': [0, 0, 1, 3, 0, 1, 2, 3, 0, 1, 2, 2],
            'blocked_sell_streak': [0, 0, 0, 1, 0, 0, 1, 1, 0, 0, 1, 1],
            'thesis_score_change_since_entry': [0.02, 0.01, -0.02, -0.08, 0.03, 0.0, -0.01, -0.05, 0.04, 0.01, -0.03, -0.04],
            'score_rank': [2, 3, 6, 8, 2, 4, 5, 7, 1, 3, 6, 7],
            'entry_rank': [2, 2, 4, 5, 2, 3, 4, 5, 1, 2, 4, 5],
            'future_hold_advantage_5d': [0.03, 0.02, -0.01, -0.04, 0.04, 0.01, -0.02, -0.03, 0.05, 0.02, -0.02, -0.01],
            'continuation_label': [1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0],
            'research_phase': ['dev'] * 8 + ['validation'] * 2 + ['confirmation'] * 2,
        }
    )
    spec = ContinuationModelSpec(
        name='test_model',
        feature_columns=(
            'holding_age_before',
            'score_change_since_entry',
            'return_since_entry',
            'peak_return_since_entry',
            'underwater_days_since_entry',
            'blocked_sell_streak',
            'thesis_score_change_since_entry',
        ),
    )
    fit = fit_continuation_model(frame, spec=spec)
    assert fit.spec.name == 'test_model'
    assert 'continuation_prob' in fit.scored_dataset.columns
    assert set(fit.raw_coefficients) == set(spec.feature_columns)
    assert 'validation_auc' in fit.summary_row
