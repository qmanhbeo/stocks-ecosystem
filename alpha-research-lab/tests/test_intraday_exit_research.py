from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.intraday_exit_research import (
    FAMILY_CONTRADICTION_MODEL_SPECS,
    INTRADAY_SHAPE_ATOM_COLUMNS,
    REDUCED_SHAPE_FEATURE_COLUMNS,
    add_intraday_shape_atoms,
    annotate_family_contradiction_results,
    build_family_aware_router_scores,
    build_reduced_shape_feature_panel,
    family_score_column,
    fit_family_scoped_continuation_models,
    merge_reduced_shape_panel,
    summarize_reduced_shape_feature_panel,
    summarize_family_router_choices,
)


def _write_daily(path: Path, rows: list[tuple[str, float, float]]) -> None:
    frame = pd.DataFrame(
        {
            "time": pd.to_datetime([day for day, _, _ in rows]),
            "open": [open_price for _, open_price, _ in rows],
            "high": [close_price for _, _, close_price in rows],
            "low": [open_price for _, open_price, _ in rows],
            "close": [close_price for _, _, close_price in rows],
            "volume": [1_000_000] * len(rows),
        }
    )
    frame.to_parquet(path, index=False)


def _write_intraday(path: Path, rows: list[tuple[str, float, float, float, float, int]]) -> None:
    frame = pd.DataFrame(
        {
            "time": pd.to_datetime([time for time, *_ in rows]),
            "open": [open_price for _, open_price, *_ in rows],
            "high": [high_price for _, _, high_price, *_ in rows],
            "low": [low_price for _, _, _, low_price, *_ in rows],
            "close": [close_price for _, _, _, _, close_price, _ in rows],
            "volume": [volume for _, _, _, _, _, volume in rows],
        }
    )
    frame.to_parquet(path, index=False)


def test_build_reduced_shape_feature_panel_collects_features_and_summary(tmp_path):
    stock_dir = tmp_path / "stock"
    stock_dir.mkdir(parents=True)

    for ticker, open_day_2, close_day_2 in [("AAA", 20.0, 20.0), ("BBB", 40.0, 41.0)]:
        _write_daily(
            stock_dir / f"gia_lich_su_{ticker}_1D.parquet",
            [
                ("2022-12-30", open_day_2 - 2.0, open_day_2 - 2.0),
                ("2023-01-02", open_day_2, close_day_2),
                ("2023-01-03", open_day_2 + 1.0, close_day_2 + 1.0),
            ],
        )
        _write_intraday(
            stock_dir / f"gia_lich_su_{ticker}_1H_CAFEF.parquet",
            [
                ("2023-01-02 10:00:00", 10.0, 10.2, 9.9, 10.1, 100),
                ("2023-01-02 11:00:00", 10.1, 10.2, 10.0, 10.0, 100),
                ("2023-01-02 12:00:00", 10.0, 10.1, 9.9, 10.05, 100),
                ("2023-01-02 13:00:00", 10.05, 10.1, 10.0, 10.08, 100),
                ("2023-01-02 14:00:00", 10.08, 10.1, 10.0, 10.0, 100),
                ("2023-01-03 10:00:00", 11.0, 11.2, 10.9, 11.1, 100),
                ("2023-01-03 11:00:00", 11.1, 11.2, 11.0, 11.0, 100),
                ("2023-01-03 12:00:00", 11.0, 11.1, 10.9, 11.05, 100),
                ("2023-01-03 13:00:00", 11.05, 11.1, 11.0, 11.08, 100),
                ("2023-01-03 14:00:00", 11.08, 11.1, 11.0, 11.0, 100),
            ],
        )

    bundle = build_reduced_shape_feature_panel(
        stock_dir=stock_dir,
        start_date="2023-01-01",
        end_date="2023-01-31",
    )

    assert bundle.feature_panel["ticker"].nunique() == 2
    assert set(REDUCED_SHAPE_FEATURE_COLUMNS).issubset(bundle.feature_panel.columns)
    assert bundle.ticker_summary["ticker"].nunique() == 2

    summary = summarize_reduced_shape_feature_panel(bundle.feature_panel)
    assert summary["observed_rows"] == 4
    assert np.isclose(float(summary["first_60m_feature_share"]), 1.0)
    assert np.isclose(float(summary["close_hour_feature_share"]), 1.0)


def test_merge_reduced_shape_panel_marks_observed_rows_and_builds_atoms():
    panel = pd.DataFrame(
        {
            "time": pd.to_datetime(["2023-01-02", "2023-01-03", "2023-01-04"]),
            "ticker": ["AAA", "AAA", "AAA"],
            "continuation_label": [1.0, 0.0, 1.0],
        }
    )
    feature_panel = pd.DataFrame(
        {
            "session_date": pd.to_datetime(["2023-01-02", "2023-01-03"]),
            "ticker": ["AAA", "AAA"],
            "open_gap_vs_prev_close": [0.02, -0.01],
            "first_60m_return": [0.03, -0.02],
            "first_60m_range_pct": [0.04, 0.01],
            "close_hour_return": [-0.01, 0.02],
            "close_repair_return": [-0.02, 0.03],
            "full_session_return": [0.01, 0.00],
        }
    )
    coverage = pd.DataFrame(
        {
            "session_date": pd.to_datetime(["2023-01-02", "2023-01-03", "2023-01-04"]),
            "ticker": ["AAA", "AAA", "AAA"],
            "coverage_bucket": ["observed_complete", "observed_incomplete", "missing_with_volume"],
        }
    )

    merged = merge_reduced_shape_panel(panel, feature_panel=feature_panel, coverage_frame=coverage)
    assert merged["intraday_observed"].tolist() == [True, True, False]
    assert merged["coverage_bucket"].tolist() == ["observed_complete", "observed_incomplete", "missing_with_volume"]

    atoms = add_intraday_shape_atoms(merged)
    assert set(INTRADAY_SHAPE_ATOM_COLUMNS).issubset(atoms.columns)
    assert np.isclose(atoms.loc[0, "first_hour_fade_proxy"], 0.04)
    assert np.isclose(atoms.loc[1, "weak_open_strong_close_proxy"], 0.05)


def test_fit_family_scoped_continuation_models_scores_each_family():
    rows = []
    for family, shift in [("momentum_continuation", 0.0), ("crowding_pressure", 0.5)]:
        for phase, label, offset in [
            ("dev", 0.0, -2.0),
            ("dev", 1.0, 2.0),
            ("validation", 0.0, -1.5),
            ("validation", 1.0, 1.5),
            ("confirmation", 0.0, -1.0),
            ("confirmation", 1.0, 1.0),
        ]:
            rows.append(
                {
                    "entry_thesis_family": family,
                    "research_phase": phase,
                    "continuation_label": label,
                    "future_hold_advantage_5d": offset / 100.0,
                    "holding_age_before": 5.0 + shift + label,
                    "score_change_since_entry": offset / 10.0,
                    "return_since_entry": offset / 12.0,
                    "peak_return_since_entry": offset / 8.0,
                    "underwater_days_since_entry": 2.0 - label,
                    "blocked_sell_streak": 1.0 + label,
                    "open_gap_vs_prev_close": offset / 20.0,
                    "first_60m_return": offset / 18.0,
                    "first_60m_range_pct": abs(offset) / 15.0 + 0.1,
                    "close_hour_return": -offset / 22.0,
                    "close_repair_return": offset / 16.0,
                    "full_session_return": offset / 25.0,
                }
            )
    frame = add_intraday_shape_atoms(pd.DataFrame(rows))

    bundle = fit_family_scoped_continuation_models(frame)

    assert len(bundle.results) == 2 * len(FAMILY_CONTRADICTION_MODEL_SPECS)
    for spec in FAMILY_CONTRADICTION_MODEL_SPECS:
        column = family_score_column(spec.name)
        assert column in bundle.scored_panel.columns
        assert bundle.scored_panel[column].notna().all()


def test_family_router_summary_uses_intraday_only_for_passing_family():
    results = pd.DataFrame(
        [
            {
                "entry_thesis_family": "momentum_continuation",
                "model_name": "path_core",
                "family_row_count": 10,
                "family_dev_count": 4,
                "family_validation_count": 3,
                "family_confirmation_count": 3,
                "validation_auc": 0.50,
                "validation_top_quintile_hold_advantage": -0.004,
                "confirmation_top_quintile_hold_advantage": -0.012,
            },
            {
                "entry_thesis_family": "momentum_continuation",
                "model_name": "intraday_atoms_plus_path",
                "family_row_count": 10,
                "family_dev_count": 4,
                "family_validation_count": 3,
                "family_confirmation_count": 3,
                "validation_auc": 0.57,
                "validation_top_quintile_hold_advantage": 0.002,
                "confirmation_top_quintile_hold_advantage": -0.005,
            },
            {
                "entry_thesis_family": "crowding_pressure",
                "model_name": "path_core",
                "family_row_count": 8,
                "family_dev_count": 3,
                "family_validation_count": 3,
                "family_confirmation_count": 2,
                "validation_auc": 0.53,
                "validation_top_quintile_hold_advantage": -0.001,
                "confirmation_top_quintile_hold_advantage": -0.004,
            },
            {
                "entry_thesis_family": "crowding_pressure",
                "model_name": "intraday_atoms_plus_path",
                "family_row_count": 8,
                "family_dev_count": 3,
                "family_validation_count": 3,
                "family_confirmation_count": 2,
                "validation_auc": 0.52,
                "validation_top_quintile_hold_advantage": -0.002,
                "confirmation_top_quintile_hold_advantage": -0.006,
            },
        ]
    )
    annotated = annotate_family_contradiction_results(results)
    family_summary = summarize_family_router_choices(annotated)

    momentum = family_summary.loc[family_summary["entry_thesis_family"] == "momentum_continuation"].iloc[0]
    crowding = family_summary.loc[family_summary["entry_thesis_family"] == "crowding_pressure"].iloc[0]
    assert momentum["router_model_name"] == "intraday_atoms_plus_path"
    assert bool(momentum["router_uses_intraday"])
    assert crowding["router_model_name"] == "path_core"
    assert not bool(crowding["router_uses_intraday"])

    scored_panel = pd.DataFrame(
        {
            "entry_thesis_family": ["momentum_continuation", "crowding_pressure"],
            family_score_column("path_core"): [0.10, 0.20],
            family_score_column("intraday_atoms_plus_path"): [0.90, 0.80],
        }
    )
    routed = build_family_aware_router_scores(scored_panel, family_summary)
    assert np.isclose(routed.loc[0, "family_router_prob"], 0.90)
    assert np.isclose(routed.loc[1, "family_router_prob"], 0.20)
