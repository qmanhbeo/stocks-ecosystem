from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.event_surface_research import build_event_hazard_params, build_event_surface, merge_event_surface


def test_build_event_surface_and_merge(tmp_path: Path) -> None:
    cache_dir = tmp_path / "dividend_cache"
    cache_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "public_date": "2020-01-02",
                "issue_date": "2020-01-02",
                "exright_date": "2020-01-10",
                "event_list_code": "DIV",
            },
            {
                "public_date": "2020-01-03",
                "issue_date": "2020-01-20",
                "exright_date": None,
                "event_list_code": "ISS",
            },
        ]
    ).to_parquet(cache_dir / "AAA_events.parquet", index=False)

    earnings_path = tmp_path / "earnings.parquet"
    pd.DataFrame(
        {
            "time": ["2020-01-06", "2020-01-07"],
            "days_since_q_end": [6, 7],
            "days_to_next_q_end": [84, 83],
            "in_report_w15_45": [0.0, 0.0],
            "in_report_w30_60": [0.0, 0.0],
            "pre_q_end_10d": [0.0, 0.0],
            "post_q_end_10d": [1.0, 1.0],
            "quarter_phase_sin": [0.1, 0.2],
            "quarter_phase_cos": [0.9, 0.8],
        }
    ).to_parquet(earnings_path, index=False)

    insider_path = tmp_path / "insider.parquet"
    pd.DataFrame(
        {
            "ticker": ["AAA", "AAA"],
            "published_date": ["2020-01-06", "2020-01-07"],
            "is_insider": [True, False],
        }
    ).to_parquet(insider_path, index=False)

    spine = pd.DataFrame(
        {
            "time": pd.to_datetime(["2020-01-06", "2020-01-07", "2020-01-21"]),
            "ticker": ["AAA", "AAA", "AAA"],
        }
    )
    bundle = build_event_surface(
        spine=spine,
        dividend_cache_dir=cache_dir,
        earnings_calendar_path=earnings_path,
        insider_raw_path=insider_path,
    )
    surface = bundle.surface
    assert "days_to_next_dividend" in surface.columns
    assert "days_to_next_issuance" in surface.columns
    assert surface.loc[surface["time"] == pd.Timestamp("2020-01-06"), "dividend_window_pre_20d"].iloc[0] == 1.0
    assert surface.loc[surface["time"] == pd.Timestamp("2020-01-21"), "issuance_window_post_5d"].iloc[0] == 1.0

    panel = pd.DataFrame({"time": pd.to_datetime(["2020-01-06"]), "ticker": ["AAA"]})
    merged = merge_event_surface(panel, surface)
    assert merged.coverage_summary["coverage_share"] == 1.0
    assert merged.merged_panel.loc[0, "recent_any_filing_5d"] >= 1.0


def test_build_event_hazard_params_keeps_generic_coefficients() -> None:
    row = pd.Series({
        "intercept": 0.3,
        "coef__holding_age_before": -0.2,
        "coef__event_density_20d": 0.5,
        "validation_auc": 0.6,
    })
    params = build_event_hazard_params(row, continue_prob_threshold=0.45)
    assert params["intercept"] == 0.3
    assert params["continue_prob_threshold"] == 0.45
    assert params["coef__event_density_20d"] == 0.5
