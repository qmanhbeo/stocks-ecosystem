from __future__ import annotations

import numpy as np
import pandas as pd

from src.entry_alpha_research import (
    EntryModelSpec,
    build_entry_row_mask,
    build_entry_allowed_matrix_from_score,
    build_small_book_confirmation_overlay_frame,
    build_small_book_threshold_series,
    build_entry_score_panel,
    build_single_family_screen_frame,
    build_soft_exposure_scale,
    build_soft_threshold_by_date,
    build_soft_top_m_by_date,
    fit_entry_model,
    load_or_build_entry_artifacts,
    prepare_entry_research_panel,
)


def test_prepare_entry_research_panel_adds_phase_release_and_ranks():
    candidate_panel = pd.DataFrame(
        {
            "time": pd.to_datetime(["2022-12-29", "2023-01-03", "2025-01-03"]),
            "ticker": ["AAA", "AAA", "AAA"],
            "selection_score": [0.60, 0.72, 0.80],
            "candidate_pool_rank": [2, 1, 1],
            "can_buy_next_open": [False, True, True],
            "tv_to_adv20": [0.9, 1.3, 1.4],
            "clv": [0.40, 0.55, 0.60],
            "gap_to_prev_close": [-0.03, -0.01, 0.01],
            "ret_1d": [-0.05, 0.02, 0.03],
            "c7_ceiling_count_5d": [3.0, 1.0, 0.0],
            "c9_reversal_1d": [0.10, 0.80, 0.75],
            "c12_gap_absorb_3": [0.15, 0.70, 0.65],
            "c14_clv_volconf_resid_rank": [0.20, 0.85, 0.70],
        }
    )
    labels = pd.DataFrame(
        {
            "time": pd.to_datetime(["2022-12-29", "2023-01-03", "2025-01-03"]),
            "ticker": ["AAA", "AAA", "AAA"],
            "cycle_return_net": [0.01, 0.02, -0.01],
            "buy_now_label": pd.Series([1, 1, 0], dtype="Int64"),
        }
    )

    panel = prepare_entry_research_panel(candidate_panel, labels)

    assert panel["research_phase"].tolist() == ["dev", "validation", "confirmation"]
    assert panel["release_flag"].tolist() == [0.0, 1.0, 0.0]
    assert "entry_gap_down_rank" in panel.columns
    assert "entry_low_ceiling_rank" in panel.columns
    assert float(panel.loc[panel["time"] == pd.Timestamp("2023-01-03"), "entry_gap_down_rank"].iloc[0]) >= 0.5


def test_build_single_family_screen_frame_flags_expected_rows():
    panel = pd.DataFrame(
        {
            "time": pd.to_datetime(["2023-01-03", "2023-01-03", "2023-01-03"]),
            "ticker": ["AAA", "BBB", "CCC"],
            "can_buy_next_open": [True, True, True],
            "tv_to_adv20": [1.30, 1.20, 1.00],
            "clv": [0.60, 0.48, 0.55],
            "release_flag": [1.0, 0.0, 0.0],
            "entry_low_ceiling_rank": [0.80, 0.40, 0.70],
            "entry_tv_to_adv20_rank": [0.90, 0.60, 0.45],
            "entry_clv_rank": [0.90, 0.60, 0.60],
            "entry_c12_rank": [0.70, 0.45, 0.40],
            "entry_gap_down_rank": [0.80, 0.30, 0.20],
            "entry_c9_rank": [0.20, 0.80, 0.40],
            "entry_recent_weakness_rank": [0.20, 0.70, 0.30],
            "entry_c8_rank": [0.90, 0.40, 0.30],
            "entry_c14_rank": [0.88, 0.45, 0.20],
        }
    )

    screened, _ = build_single_family_screen_frame(panel)

    assert screened["screen__impl_liquidity_quality"].tolist() == [True, True, False]
    assert screened["screen__impl_release_quality"].tolist() == [True, False, False]
    assert screened["screen__impl_uncrowded_quality"].tolist() == [True, False, False]
    assert screened["screen__price_gap_absorb"].tolist() == [True, False, False]
    assert screened["screen__price_reversal_quality"].tolist() == [False, True, False]
    assert screened["screen__price_volconf_quality"].tolist() == [True, False, False]


def test_small_book_confirmation_helpers_build_counts_and_thresholds():
    panel = pd.DataFrame(
        {
            "time": pd.to_datetime(["2023-01-03", "2023-01-03", "2023-01-03"]),
            "ticker": ["AAA", "BBB", "CCC"],
            "screen__price_reversal_quality": [True, False, False],
            "screen__price_gap_absorb": [True, False, False],
            "screen__impl_uncrowded_quality": [False, True, False],
            "screen__price_volconf_quality": [False, True, False],
        }
    )

    enriched = build_small_book_confirmation_overlay_frame(panel)
    thresholds = build_small_book_threshold_series(
        enriched,
        base_threshold=0.60,
        supportive_bonus=0.02,
        consensus_bonus=0.05,
        no_confirm_penalty=0.03,
    )

    assert enriched["confirm_count"].tolist() == [2, 2, 0]
    assert enriched["confirm_any"].tolist() == [True, True, False]
    assert enriched["confirm_consensus"].tolist() == [True, True, False]
    assert thresholds.round(4).tolist() == [0.55, 0.55, 0.63]


def test_build_entry_row_mask_applies_rank_score_gap_and_buyability():
    panel = pd.DataFrame(
        {
            "candidate_pool_rank": [1, 2, 3, 4],
            "selection_score": [0.68, 0.62, 0.61, 0.80],
            "selection_score_gap_to_next_candidate": [0.05, 0.02, 0.01, 0.10],
            "can_buy_next_open": [True, True, False, True],
        }
    )

    mask = build_entry_row_mask(
        panel,
        top_m=3,
        min_selection_score=0.60,
        min_score_gap=0.02,
        require_buyable=True,
    )

    assert mask.tolist() == [True, True, False, False]


def test_fit_entry_model_scores_dataset_and_builds_score_panel():
    panel = pd.DataFrame(
        {
            "time": pd.to_datetime(
                [
                    "2022-01-03",
                    "2022-01-04",
                    "2022-01-05",
                    "2022-01-06",
                    "2023-01-03",
                    "2023-01-04",
                    "2025-01-03",
                    "2025-01-04",
                ]
            ),
            "ticker": ["AAA", "BBB", "CCC", "DDD", "AAA", "BBB", "AAA", "BBB"],
            "research_phase": ["dev", "dev", "dev", "dev", "validation", "validation", "confirmation", "confirmation"],
            "buy_now_label": [1, 1, 0, 0, 1, 0, 1, 0],
            "cycle_return_net": [0.03, 0.02, -0.02, -0.03, 0.02, -0.01, 0.01, -0.02],
            "selection_score": [0.90, 0.80, 0.20, 0.10, 0.88, 0.25, 0.86, 0.22],
            "candidate_pool_rank": [1, 2, 3, 4, 1, 3, 1, 3],
            "tv_to_adv20": [1.40, 1.20, 0.80, 0.70, 1.35, 0.85, 1.30, 0.75],
            "clv": [0.62, 0.55, 0.35, 0.30, 0.60, 0.38, 0.58, 0.32],
            "release_flag": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
            "activation_state": ["on"] * 8,
            "activation_scale": [1.0] * 8,
            "activation_rel2": [0.02, 0.01, -0.01, -0.02, 0.03, -0.01, 0.02, -0.02],
            "can_buy_next_open": [True] * 8,
        }
    )
    spec = EntryModelSpec(
        name="test_blend",
        feature_columns=("selection_score", "candidate_pool_rank", "tv_to_adv20", "clv", "release_flag", "activation_rel2"),
    )

    fit = fit_entry_model(panel, spec=spec)
    score_column = "entry_prob__test_blend"

    assert score_column in fit.scored_dataset.columns
    assert fit.summary_row["validation_auc"] is not None
    score_panel = build_entry_score_panel([fit])
    assert score_column in score_panel.columns
    assert len(score_panel) == len(panel)


def test_soft_exposure_helpers_create_dynamic_thresholds_and_top_m():
    panel = pd.DataFrame(
        {
            "time": pd.to_datetime(["2023-01-03", "2023-01-04", "2023-01-05"]),
            "activation_rel2": [-0.04, 0.00, 0.04],
        }
    )

    scale = build_soft_exposure_scale(panel)
    thresholds = build_soft_threshold_by_date(base_threshold=0.55, exposure_scale=scale, off_penalty=0.10)
    top_m = build_soft_top_m_by_date(on_top_m=10, off_top_m=2, exposure_scale=scale)

    assert scale.loc[pd.Timestamp("2023-01-03")] < scale.loc[pd.Timestamp("2023-01-05")]
    assert thresholds[pd.Timestamp("2023-01-03")] > thresholds[pd.Timestamp("2023-01-05")]
    assert top_m[pd.Timestamp("2023-01-03")] < top_m[pd.Timestamp("2023-01-05")]


def test_build_entry_allowed_matrix_from_score_uses_dynamic_thresholds():
    panel = pd.DataFrame(
        {
            "time": pd.to_datetime(["2023-01-03", "2023-01-03", "2023-01-04", "2023-01-04"]),
            "ticker": ["AAA", "BBB", "AAA", "BBB"],
            "candidate_pool_rank": [1, 2, 1, 2],
            "can_buy_next_open": [True, True, True, True],
            "entry_prob__blend": [0.70, 0.52, 0.61, 0.58],
        }
    )
    threshold_by_date = {
        pd.Timestamp("2023-01-03"): 0.60,
        pd.Timestamp("2023-01-04"): 0.59,
    }

    matrix = build_entry_allowed_matrix_from_score(
        panel,
        dates=pd.to_datetime(["2023-01-03", "2023-01-04"]),
        tickers=["AAA", "BBB"],
        score_column="entry_prob__blend",
        top_m=2,
        threshold_by_date=threshold_by_date,
        require_buyable=True,
    )

    assert matrix.shape == (2, 2)
    assert matrix.tolist() == [[True, False], [True, False]]


def test_load_or_build_entry_artifacts_rebuilds_when_requested_dates_extend_existing_cache(tmp_path, monkeypatch):
    candidate_panel_path = tmp_path / "candidate_panel.parquet"
    labels_path = tmp_path / "labels.parquet"
    stale_candidate_panel = pd.DataFrame(
        {
            "time": pd.to_datetime(["2025-12-31"]),
            "ticker": ["AAA"],
            "candidate_pool_rank": [1],
        }
    )
    stale_labels = pd.DataFrame(
        {
            "time": pd.to_datetime(["2025-12-31"]),
            "ticker": ["AAA"],
        }
    )
    stale_candidate_panel.to_parquet(candidate_panel_path, index=False)
    stale_labels.to_parquet(labels_path, index=False)

    inputs = type(
        "DummyEntryAlphaInputs",
        (),
        {
            "matrix": pd.DataFrame({"time": pd.to_datetime(["2025-12-31", "2026-01-02"])}),
            "price_panel": pd.DataFrame({"time": pd.to_datetime(["2025-12-31", "2026-01-02"]), "ticker": ["AAA", "AAA"], "open": [10.0, 11.0]}),
            "benchmark_open": pd.Series([100.0, 101.0], index=pd.to_datetime(["2025-12-31", "2026-01-02"]), dtype=float),
        },
    )()

    rebuilt_panel = pd.DataFrame(
        {
            "time": pd.to_datetime(["2025-12-31", "2026-01-02"]),
            "ticker": ["AAA", "AAA"],
            "candidate_pool_rank": [1, 1],
        }
    )
    rebuilt_labels = pd.DataFrame(
        {
            "time": pd.to_datetime(["2025-12-31", "2026-01-02"]),
            "ticker": ["AAA", "AAA"],
        }
    )

    def _fake_build_panel(*args, **kwargs):
        return rebuilt_panel.copy()

    def _fake_build_labels(*args, **kwargs):
        return rebuilt_labels.copy()

    monkeypatch.setattr("src.entry_alpha_research.build_entry_candidate_panel", _fake_build_panel)
    monkeypatch.setattr("src.entry_alpha_research.build_entry_labels", _fake_build_labels)

    _, candidate_panel, labels = load_or_build_entry_artifacts(
        inputs=inputs,
        candidate_panel_path=candidate_panel_path,
        labels_path=labels_path,
        top_m_max=1,
        top_k=1,
        rebalance_every=1,
    )

    assert pd.Timestamp(candidate_panel["time"].max()) == pd.Timestamp("2026-01-02")
    assert pd.Timestamp(labels["time"].max()) == pd.Timestamp("2026-01-02")
