from __future__ import annotations

import pandas as pd

from src.champion_activation_utils import (
    ChampionSetup,
    ChampionVariantSpec,
    build_champion_gate,
    calibration_mask_before_year,
)
from src.champion_branch_experiment_utils import compare_daily_frames


def _dummy_setup(meta_state: pd.DataFrame) -> ChampionSetup:
    return ChampionSetup(
        selector_name="full_library_k5_r5_eq",
        selector_strategy_name="full_library",
        signal_columns=("s1_proba",),
        inputs=object(),
        meta_state=meta_state,
        meta_source="test",
        rel2=pd.Series([0.0] * len(meta_state)),
        common_kwargs={},
    )


def test_build_champion_gate_respects_train_only_quantile_mask():
    meta_state = pd.DataFrame(
        {
            "time": pd.to_datetime(
                ["2022-12-29", "2022-12-30", "2023-01-02", "2023-01-03"]
            ),
            "full_prev_cycle_relative_return": [0.05, 0.04, 0.03, 0.02],
            "full_recent_blocked_buy_ewm5": [0.10, 0.20, 0.05, 0.05],
        }
    )
    setup = _dummy_setup(meta_state)
    spec = ChampionVariantSpec(
        name="impl__blocked5_q50",
        rel_span=2,
        rel_threshold=0.0,
        blocked_buy_span=5,
        blocked_buy_max_quantile=0.50,
    )
    train_mask = calibration_mask_before_year(meta_state, 2023)
    gate, _, blocked, on_threshold, _ = build_champion_gate(
        setup,
        spec=spec,
        calibration_mask=train_mask,
    )
    assert round(float(on_threshold), 6) == 0.15
    assert blocked is not None
    assert gate.tolist() == [True, False, True, True]


def test_compare_daily_frames_detects_list_value_mismatches():
    left = pd.DataFrame(
        {
            "signal_date": pd.to_datetime(["2026-01-02"]),
            "execution_date": pd.to_datetime(["2026-01-03"]),
            "held_tickers": [["AAA", "BBB"]],
            "activation_on": [True],
        }
    )
    right = pd.DataFrame(
        {
            "signal_date": pd.to_datetime(["2026-01-02"]),
            "execution_date": pd.to_datetime(["2026-01-03"]),
            "held_tickers": [["AAA", "CCC"]],
            "activation_on": [True],
        }
    )
    comparison = compare_daily_frames(
        left,
        right,
        on=("signal_date", "execution_date"),
        columns=("held_tickers", "activation_on"),
    )
    assert comparison["matches"] is False
    assert comparison["value_diffs"][0]["column"] == "held_tickers"
