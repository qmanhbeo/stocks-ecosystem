from __future__ import annotations

import pandas as pd

from data_tools import adjust_cafef_intraday_to_vci as cafef_adjust


def _write_raw_intraday(path, rows: list[tuple[str, float]]) -> None:
    frame = pd.DataFrame(
        {
            "time": pd.to_datetime([time for time, _ in rows]),
            "open": [price for _, price in rows],
            "high": [price for _, price in rows],
            "low": [price for _, price in rows],
            "close": [price for _, price in rows],
            "volume": [100] * len(rows),
        }
    )
    frame.to_parquet(path, index=False)


def _write_daily(path, rows: list[tuple[str, float]]) -> None:
    frame = pd.DataFrame(
        {
            "time": pd.to_datetime([day for day, _ in rows]),
            "open": [price for _, price in rows],
            "high": [price for _, price in rows],
            "low": [price for _, price in rows],
            "close": [price for _, price in rows],
            "volume": [1000] * len(rows),
        }
    )
    frame.to_parquet(path, index=False)


def test_adjust_one_ticker_refreshes_stale_existing_outputs(monkeypatch, tmp_path):
    stock_dir = tmp_path / "stock"
    stock_dir.mkdir(parents=True)
    factor_dir = stock_dir / "_cafef_adjustment_factors"
    factor_dir.mkdir(parents=True)
    monkeypatch.setattr(cafef_adjust, "DATA_DIR", stock_dir)

    ticker = "AAA"
    raw_label = "1H_CAFEF"
    adjusted_label = "1H_CAFEF_ADJ"

    _write_raw_intraday(
        stock_dir / f"gia_lich_su_{ticker}_{raw_label}.parquet",
        [
            ("2024-01-01 10:00:00", 10.0),
            ("2024-01-02 10:00:00", 20.0),
        ],
    )
    _write_daily(
        stock_dir / f"gia_lich_su_{ticker}_1D.parquet",
        [("2024-01-01", 5.0), ("2024-01-02", 10.0)],
    )

    # Simulate a pre-metadata stale adjusted output that only contains the first day.
    _write_raw_intraday(
        stock_dir / f"gia_lich_su_{ticker}_{adjusted_label}.parquet",
        [("2024-01-01 10:00:00", 5.0)],
    )
    pd.DataFrame({"session_date": pd.to_datetime(["2024-01-01"]), "price_factor": [0.5]}).to_parquet(
        factor_dir / f"gia_lich_su_{ticker}_{raw_label}_to_{adjusted_label}.parquet",
        index=False,
    )

    ok, message = cafef_adjust.adjust_one_ticker(
        ticker,
        raw_label=raw_label,
        adjusted_label=adjusted_label,
        factor_dir=factor_dir,
        overwrite=False,
    )

    assert ok is True
    assert "adjusted 2 bars across 2/2 days" in message

    adjusted = pd.read_parquet(stock_dir / f"gia_lich_su_{ticker}_{adjusted_label}.parquet")
    factors = pd.read_parquet(factor_dir / f"gia_lich_su_{ticker}_{raw_label}_to_{adjusted_label}.parquet")

    assert adjusted["time"].dt.strftime("%Y-%m-%d %H:%M:%S").tolist() == [
        "2024-01-01 10:00:00",
        "2024-01-02 10:00:00",
    ]
    assert factors["session_date"].dt.strftime("%Y-%m-%d").tolist() == ["2024-01-01", "2024-01-02"]
    assert cafef_adjust.build_metadata_path(ticker, raw_label, adjusted_label, factor_dir).exists()


def test_adjust_one_ticker_skips_when_metadata_matches(monkeypatch, tmp_path):
    stock_dir = tmp_path / "stock"
    stock_dir.mkdir(parents=True)
    factor_dir = stock_dir / "_cafef_adjustment_factors"
    factor_dir.mkdir(parents=True)
    monkeypatch.setattr(cafef_adjust, "DATA_DIR", stock_dir)

    ticker = "AAA"
    raw_label = "1H_CAFEF"
    adjusted_label = "1H_CAFEF_ADJ"

    _write_raw_intraday(
        stock_dir / f"gia_lich_su_{ticker}_{raw_label}.parquet",
        [
            ("2024-01-01 10:00:00", 10.0),
            ("2024-01-02 10:00:00", 20.0),
        ],
    )
    _write_daily(
        stock_dir / f"gia_lich_su_{ticker}_1D.parquet",
        [("2024-01-01", 5.0), ("2024-01-02", 10.0)],
    )

    first_ok, _ = cafef_adjust.adjust_one_ticker(
        ticker,
        raw_label=raw_label,
        adjusted_label=adjusted_label,
        factor_dir=factor_dir,
        overwrite=False,
    )
    second_ok, second_message = cafef_adjust.adjust_one_ticker(
        ticker,
        raw_label=raw_label,
        adjusted_label=adjusted_label,
        factor_dir=factor_dir,
        overwrite=False,
    )

    assert first_ok is True
    assert second_ok is True
    assert second_message == f"{ticker}: adjusted output is up to date, skipping"
