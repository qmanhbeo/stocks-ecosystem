from __future__ import annotations

import pytest
import pandas as pd

from src.event_surface_trust_research import build_event_regime_activation_scale, build_topk_event_regime_frame


def test_build_topk_event_regime_frame_aggregates_topk_event_counts() -> None:
    scored = pd.DataFrame(
        {
            "time": pd.to_datetime(
                [
                    "2020-01-01",
                    "2020-01-01",
                    "2020-01-01",
                    "2020-01-02",
                    "2020-01-02",
                    "2020-01-02",
                ]
            ),
            "ticker": ["AAA", "BBB", "CCC", "AAA", "BBB", "CCC"],
            "actual": [0.10, 0.00, -0.05, 0.20, 0.10, 0.00],
            "score__alpha": [0.9, 0.8, 0.1, 0.2, 0.7, 0.6],
        }
    )
    event_surface = pd.DataFrame(
        {
            "time": pd.to_datetime(
                [
                    "2020-01-01",
                    "2020-01-01",
                    "2020-01-01",
                    "2020-01-02",
                    "2020-01-02",
                    "2020-01-02",
                ]
            ),
            "ticker": ["AAA", "BBB", "CCC", "AAA", "BBB", "CCC"],
            "recent_any_filing_5d": [1, 0, 0, 0, 1, 0],
            "in_report_w15_45": [0, 1, 0, 0, 0, 0],
            "in_report_w30_60": [0, 0, 0, 1, 0, 0],
            "dividend_window_pre_20d": [1, 0, 0, 0, 0, 0],
            "issuance_window_pre_20d": [0, 0, 1, 0, 1, 0],
            "event_density_20d": [1, 0, 0, 1, 1, 0],
        }
    )

    out = build_topk_event_regime_frame(scored, strategy_names=["alpha"], event_surface=event_surface, top_k=2)

    row0 = out.loc[out["time"] == pd.Timestamp("2020-01-01")].iloc[0]
    assert row0["selected_count"] == 2
    assert round(float(row0["topk_mean_actual"]), 6) == 0.05
    assert round(float(row0["topk_edge_actual"]), 6) == 0.033333
    assert row0["topk_any_event_count"] == 1
    assert row0["topk_recent_filing_count"] == 1
    assert row0["topk_report_window_count"] == 1
    assert row0["topk_corp_action_count"] == 1


def test_build_topk_event_regime_frame_requires_score_columns() -> None:
    with pytest.raises(ValueError, match="Missing score columns"):
        build_topk_event_regime_frame(
            pd.DataFrame({"time": [], "ticker": [], "actual": []}),
            strategy_names=["alpha"],
            event_surface=pd.DataFrame(columns=["time", "ticker"]),
            top_k=5,
        )


def test_build_event_regime_activation_scale_marks_regime_dates() -> None:
    topk_frame = pd.DataFrame(
        {
            "time": pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"]),
            "strategy_name": ["alpha", "alpha", "alpha"],
            "topk_report_window_count": [2, 1, 3],
            "topk_recent_filing_count": [0, 1, 1],
        }
    )

    out = build_event_regime_activation_scale(
        topk_frame,
        strategy_name="alpha",
        regime_name="top5_report_window_ge2",
        on_scale=1.0,
        off_scale=0.5,
    )

    assert out.index.tolist() == pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"]).tolist()
    assert out.tolist() == [1.0, 0.5, 1.0]


def test_build_event_regime_activation_scale_requires_known_regime() -> None:
    with pytest.raises(ValueError, match="Unknown event trust regime"):
        build_event_regime_activation_scale(
            pd.DataFrame({"time": pd.to_datetime(["2020-01-01"]), "strategy_name": ["alpha"]}),
            strategy_name="alpha",
            regime_name="unknown_regime",
        )
