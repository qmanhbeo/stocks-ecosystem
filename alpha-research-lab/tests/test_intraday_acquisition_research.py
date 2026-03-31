from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.intraday_acquisition_research import (
    build_intraday_coverage_taxonomy,
    build_intraday_pilot_bundle,
    select_pilot_tickers,
    summarize_coverage_against_continuation,
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


def test_select_pilot_tickers_keeps_required_cohorts(tmp_path):
    stock_dir = tmp_path / "stock"
    stock_dir.mkdir(parents=True)
    sector_path = tmp_path / "sector.parquet"

    sectors = pd.DataFrame(
        {
            "symbol": ["BANK1", "BANK2", "IND1", "IND2", "TAIL1", "TAIL2", "FILL1"],
            "icb_name2": [
                "Ngân hàng",
                "Ngân hàng",
                "Hàng & Dịch vụ Công nghiệp",
                "Hàng & Dịch vụ Công nghiệp",
                "Bán lẻ",
                "Hóa chất",
                "Công nghệ Thông tin",
            ],
        }
    )
    sectors.to_parquet(sector_path, index=False)

    liquidity_map = {
        "BANK1": 9_000_000,
        "BANK2": 8_000_000,
        "IND1": 7_000_000,
        "IND2": 6_000_000,
        "FILL1": 5_000_000,
        "TAIL1": 100,
        "TAIL2": 50,
    }
    for ticker, close_price in liquidity_map.items():
        _write_daily(
            stock_dir / f"gia_lich_su_{ticker}_1D.parquet",
            [("2025-01-02", close_price, close_price), ("2025-01-03", close_price, close_price)],
        )
        _write_intraday(
            stock_dir / f"gia_lich_su_{ticker}_1H_CAFEF.parquet",
            [("2025-01-02 10:00:00", 10.0, 10.0, 10.0, 10.0, 1_000)],
        )

    selected = select_pilot_tickers(
        stock_dir=stock_dir,
        sector_path=sector_path,
        sample_size=6,
    )

    assert len(selected) == 6
    assert "liquid_bank" in set(selected["pilot_role"])
    assert "liquid_industrial" in set(selected["pilot_role"])
    assert "small_tail" in set(selected["pilot_role"])


def test_build_intraday_pilot_bundle_extracts_adjusted_daily_features(tmp_path):
    stock_dir = tmp_path / "stock"
    stock_dir.mkdir(parents=True)

    _write_daily(
        stock_dir / "gia_lich_su_AAA_1D.parquet",
        [
            ("2022-12-30", 18.0, 18.0),
            ("2023-01-02", 20.0, 20.0),
            ("2023-01-03", 22.0, 22.0),
        ],
    )
    _write_intraday(
        stock_dir / "gia_lich_su_AAA_1H_CAFEF.parquet",
        [
            ("2023-01-02 10:00:00", 10.0, 10.2, 9.9, 10.2, 100),
            ("2023-01-02 11:00:00", 10.2, 10.3, 10.1, 10.25, 100),
            ("2023-01-02 12:00:00", 10.25, 10.3, 10.2, 10.28, 100),
            ("2023-01-02 13:00:00", 10.28, 10.32, 10.26, 10.30, 100),
            ("2023-01-02 14:00:00", 10.30, 10.32, 10.28, 10.00, 100),
            ("2023-01-03 10:00:00", 11.0, 11.1, 10.9, 11.05, 100),
            ("2023-01-03 11:00:00", 11.05, 11.1, 11.0, 11.0, 100),
            ("2023-01-03 13:00:00", 11.0, 11.05, 10.95, 11.02, 100),
            ("2023-01-03 14:00:00", 11.02, 11.05, 11.0, 11.0, 100),
        ],
    )

    bundle = build_intraday_pilot_bundle(
        stock_dir=stock_dir,
        ticker="AAA",
        start_date="2023-01-01",
        end_date="2023-01-31",
    )

    features = bundle.features.sort_values("session_date").reset_index(drop=True)
    assert len(features) == 2
    assert bool(features.loc[0, "complete_day"]) is True
    assert bool(features.loc[1, "complete_day"]) is False
    assert bool(features.loc[0, "has_midday_window"]) is True
    assert bool(features.loc[1, "has_midday_window"]) is False
    assert np.isclose(features.loc[0, "open_gap_vs_prev_close"], (20.0 / 18.0) - 1.0)
    assert np.isclose(features.loc[0, "first_60m_return"], (20.4 / 20.0) - 1.0)
    assert bundle.summary_row["overlap_days"] == 2


def test_build_intraday_coverage_taxonomy_separates_prefix_and_in_window_missing(tmp_path):
    stock_dir = tmp_path / "stock"
    stock_dir.mkdir(parents=True)

    _write_daily(
        stock_dir / "gia_lich_su_AAA_1D.parquet",
        [
            ("2023-01-02", 10.0, 10.0),
            ("2023-01-03", 10.0, 10.0),
            ("2023-01-04", 10.0, 10.0),
            ("2023-01-05", 10.0, 10.0),
            ("2023-01-06", 10.0, 10.0),
        ],
    )
    _write_intraday(
        stock_dir / "gia_lich_su_AAA_1H_CAFEF.parquet",
        [
            ("2023-01-03 10:00:00", 10.0, 10.0, 10.0, 10.0, 100),
            ("2023-01-03 11:00:00", 10.0, 10.0, 10.0, 10.0, 100),
            ("2023-01-03 12:00:00", 10.0, 10.0, 10.0, 10.0, 100),
            ("2023-01-03 13:00:00", 10.0, 10.0, 10.0, 10.0, 100),
            ("2023-01-03 14:00:00", 10.0, 10.0, 10.0, 10.0, 100),
            ("2023-01-06 10:00:00", 10.0, 10.0, 10.0, 10.0, 100),
            ("2023-01-06 11:00:00", 10.0, 10.0, 10.0, 10.0, 100),
            ("2023-01-06 12:00:00", 10.0, 10.0, 10.0, 10.0, 100),
            ("2023-01-06 13:00:00", 10.0, 10.0, 10.0, 10.0, 100),
            ("2023-01-06 14:00:00", 10.0, 10.0, 10.0, 10.0, 100),
        ],
    )
    tradability = pd.DataFrame(
        {
            "session_date": pd.to_datetime(
                ["2023-01-02", "2023-01-03", "2023-01-04", "2023-01-05", "2023-01-06"]
            ),
            "ticker": ["AAA"] * 5,
            "has_volume": [True, True, True, False, True],
        }
    )

    coverage, ticker_summary = build_intraday_coverage_taxonomy(
        stock_dir=stock_dir,
        tradability=tradability,
        start_date="2023-01-01",
        end_date="2023-01-31",
    )

    buckets = coverage.sort_values("session_date")["coverage_bucket"].tolist()
    assert buckets == [
        "source_empty_prefix",
        "observed_complete",
        "missing_with_volume",
        "missing_no_volume",
        "observed_complete",
    ]

    summary = ticker_summary.iloc[0].to_dict()
    assert summary["overlap_days"] == 2
    assert summary["missing_with_volume_days"] == 1
    assert summary["missing_no_volume_days"] == 1
    assert np.isclose(summary["missing_session_rate_in_window"], 1 / 3)

    lower_bound = summarize_coverage_against_continuation(
        coverage_frame=coverage,
        ticker_summary=ticker_summary,
        continuation_panel=pd.DataFrame(
            {
                "time": pd.to_datetime(["2023-01-03", "2023-01-04", "2023-01-06"]),
                "ticker": ["AAA", "AAA", "AAA"],
            }
        ),
    )
    assert lower_bound["available_raw_tickers"] == 1
    assert np.isclose(lower_bound["held_row_coverage_lower_bound"], 2 / 3)
