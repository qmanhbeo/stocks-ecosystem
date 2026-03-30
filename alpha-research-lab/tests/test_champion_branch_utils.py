from __future__ import annotations

import numpy as np
import pandas as pd

from src.activation_alpha import ActivationExperimentInputs
from src.champion_activation_utils import (
    ChampionSetup,
    ChampionVariantSpec,
    build_champion_gate,
    calibration_mask_before_year,
    current_live_variant,
    project_champion_variant_to_next_open,
)
from src.champion_branch_experiment_utils import (
    compare_daily_frames,
    summarize_latest_recommendation,
)
from src.deterministic_portfolio import MarketInputs


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


def _market_inputs(score_matrix: np.ndarray) -> MarketInputs:
    dates = pd.bdate_range("2026-03-26", periods=score_matrix.shape[0]).to_numpy()
    tickers = ("AAA", "BBB")
    return MarketInputs(
        dates=dates,
        tickers=tickers,
        benchmark_open=np.full(score_matrix.shape[0], 100.0, dtype=np.float64),
        open_matrix=np.full(score_matrix.shape, 100.0, dtype=np.float64),
        adv20_matrix=np.full(score_matrix.shape, 1e12, dtype=np.float64),
        can_buy_matrix=np.ones(score_matrix.shape, dtype=bool),
        can_sell_matrix=np.ones(score_matrix.shape, dtype=bool),
        availability_matrix=np.ones(score_matrix.shape, dtype=bool),
        score_matrices={"full_library": score_matrix.astype(np.float64)},
        tradability_source="test",
    )


def _projection_setup() -> ChampionSetup:
    scores = np.array(
        [
            [0.9, 0.1],
            [0.8, 0.2],
        ],
        dtype=np.float64,
    )
    market_inputs = _market_inputs(scores)
    inputs = ActivationExperimentInputs(
        matrix=pd.DataFrame(),
        scored=pd.DataFrame(),
        price_panel=pd.DataFrame(),
        tradability=pd.DataFrame(),
        market_inputs=market_inputs,
        selectors=(),
    )
    meta_state = pd.DataFrame(
        {
            "time": pd.to_datetime(["2026-03-26", "2026-03-27"]),
            "full_prev_cycle_relative_return": [0.10, 0.12],
        }
    )
    return ChampionSetup(
        selector_name="full_library_k5_r5_eq",
        selector_strategy_name="full_library",
        signal_columns=("s1_proba",),
        inputs=inputs,
        meta_state=meta_state,
        meta_source="test",
        rel2=pd.Series([0.10, 0.12], index=meta_state["time"]),
        common_kwargs={
            "strategy_name": "full_library",
            "signal_columns": ["s1_proba"],
            "market_inputs": market_inputs,
            "top_k": 1,
            "rebalance_every": 1,
            "weighting": "equal",
            "initial_notional_vnd": 1.0,
            "max_adv_participation": 0.0,
            "required_holding_age": 0,
            "buy_fee_rate": 0.0,
            "sell_fee_rate": 0.0,
            "capital_gains_tax_rate": 0.0,
        },
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


def test_current_live_variant_matches_sticky_live_branch():
    spec = current_live_variant()
    assert spec.name == "sticky_bonus_0p015"
    assert spec.blocked_buy_span is None
    assert spec.max_names_per_sector is None


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


def test_project_champion_variant_to_next_open_emits_future_execution_without_future_market_row():
    setup = _projection_setup()
    spec = ChampionVariantSpec(name="sticky_bonus_0p015", incumbent_score_bonus=0.0)
    run = project_champion_variant_to_next_open(setup, spec=spec, capture_blotter=True)

    recommendation = summarize_latest_recommendation(run.result.daily, run.result.blotter)

    assert recommendation["signal_date"] == "2026-03-27"
    assert recommendation["execution_date"] == "2026-03-30"
    assert recommendation["activation_on"] is True
    assert recommendation["held_tickers_after_execution"] == ["AAA"]
    assert recommendation["positions_after_execution"][0]["ticker"] == "AAA"
    assert recommendation["positions_after_execution"][0]["executed_weight"] == 1.0
