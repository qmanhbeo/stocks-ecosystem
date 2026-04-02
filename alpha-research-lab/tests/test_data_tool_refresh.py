from __future__ import annotations

import pandas as pd

from data_tools import fetch_all_stock_fundamentals as fundamentals
from data_tools import fetch_fx_commodities as fx
from data_tools import fetch_global_macro as macro
from data_tools import fetch_ssi_intraday as ssi


def _write_timeseries(path, rows: list[tuple[str, float]]) -> None:
    frame = pd.DataFrame(
        {
            "time": pd.to_datetime([time for time, _ in rows]),
            "open": [value for _, value in rows],
            "high": [value for _, value in rows],
            "low": [value for _, value in rows],
            "close": [value for _, value in rows],
            "volume": [100] * len(rows),
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)


def test_fetch_fx_commodities_overwrite_keeps_existing_file_on_empty_refresh(monkeypatch, tmp_path):
    monkeypatch.setattr(fx, "OUT_DIR", tmp_path)
    alias_map = dict(fx.DEFAULT_ALIASES)
    output_path = tmp_path / "fx_commodities_fx_vnd_usd_1D.parquet"
    _write_timeseries(output_path, [("2024-01-01", 1.0)])

    monkeypatch.setattr(fx.yf, "download", lambda *args, **kwargs: pd.DataFrame())

    ok = fx.fetch_ticker(
        "VND=X",
        "1D",
        "2000-01-01",
        "2026-12-31",
        alias_map,
        overwrite=True,
    )

    assert ok is True
    saved = pd.read_parquet(output_path)
    assert saved["time"].dt.strftime("%Y-%m-%d").tolist() == ["2024-01-01"]


def test_fetch_fx_commodities_incremental_append(monkeypatch, tmp_path):
    monkeypatch.setattr(fx, "OUT_DIR", tmp_path)
    alias_map = dict(fx.DEFAULT_ALIASES)
    output_path = tmp_path / "fx_commodities_fx_vnd_usd_1D.parquet"
    _write_timeseries(output_path, [("2024-01-01", 1.0)])

    def fake_download(ticker, start, end, interval, progress, auto_adjust):
        assert start == "2024-01-02"
        return pd.DataFrame(
            {
                "Date": pd.to_datetime(["2024-01-02"]),
                "Open": [2.0],
                "High": [2.0],
                "Low": [2.0],
                "Close": [2.0],
                "Volume": [100],
            }
        )

    monkeypatch.setattr(fx.yf, "download", fake_download)

    ok = fx.fetch_ticker(
        "VND=X",
        "1D",
        "2000-01-01",
        "2026-12-31",
        alias_map,
        overwrite=False,
    )

    assert ok is True
    saved = pd.read_parquet(output_path)
    assert saved["time"].dt.strftime("%Y-%m-%d").tolist() == ["2024-01-01", "2024-01-02"]


def test_fetch_fx_commodities_default_macro_basket_aliases():
    assert "DX-Y.NYB" in fx.DEFAULT_TICKERS
    assert "BTC-USD" in fx.DEFAULT_TICKERS
    assert "000001.SS" in fx.DEFAULT_TICKERS
    assert fx.DEFAULT_ALIASES["DX-Y.NYB"] == "dxy"
    assert fx.DEFAULT_ALIASES["TWII"] == "taiex"
    assert fx.DEFAULT_ALIASES["N225"] == "nikkei"


def test_fetch_global_macro_incremental_append(monkeypatch, tmp_path):
    monkeypatch.setattr(macro, "OUT_DIR", tmp_path)
    output_path = tmp_path / "fx_commodities_dxy_1D.parquet"
    _write_timeseries(output_path, [("2024-01-01", 100.0)])

    def fake_download(ticker, start, end, progress, auto_adjust):
        assert start == "2024-01-02"
        return pd.DataFrame(
            {
                "Date": pd.to_datetime(["2024-01-02"]),
                "Open": [101.0],
                "High": [101.0],
                "Low": [101.0],
                "Close": [101.0],
                "Volume": [100],
            }
        )

    monkeypatch.setattr(macro.yf, "download", fake_download)

    ok = macro.fetch_one("DX-Y.NYB", "dxy", overwrite=False)

    assert ok is True
    saved = pd.read_parquet(output_path)
    assert saved["time"].dt.strftime("%Y-%m-%d").tolist() == ["2024-01-01", "2024-01-02"]


def test_fetch_ssi_intraday_incremental_append(monkeypatch, tmp_path):
    monkeypatch.setattr(ssi, "DATA_DIR", tmp_path)
    output_path = tmp_path / "gia_lich_su_AAA_1H.parquet"
    _write_timeseries(output_path, [("2024-01-01 10:00:00", 10.0)])

    class DummyClient:
        def fetch_intraday_window(self, **kwargs):
            return [
                {
                    "TradingDate": "01/01/2024",
                    "Time": "2024-01-01 10:00:00",
                    "Open": 10.0,
                    "High": 10.0,
                    "Low": 10.0,
                    "Close": 10.0,
                    "Volume": 100,
                },
                {
                    "TradingDate": "02/01/2024",
                    "Time": "2024-01-02 10:00:00",
                    "Open": 11.0,
                    "High": 11.0,
                    "Low": 11.0,
                    "Close": 11.0,
                    "Volume": 100,
                },
            ]

    ok, message = ssi.fetch_one_ticker(
        DummyClient(),
        ticker="AAA",
        start_date=ssi.parse_iso_date("2000-01-01"),
        end_date=ssi.parse_iso_date("2026-12-31"),
        resolution=60,
        interval_label="1H",
        chunk_days=365,
        page_size=1000,
        max_pages=10,
        ascending=True,
        chunk_delay=0.0,
        overwrite=False,
    )

    assert ok is True
    assert "appended 1 bars" in message
    saved = pd.read_parquet(output_path)
    assert saved["time"].dt.strftime("%Y-%m-%d %H:%M:%S").tolist() == [
        "2024-01-01 10:00:00",
        "2024-01-02 10:00:00",
    ]


def test_fetch_all_stock_fundamentals_refetches_corrupt_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(fundamentals, "CACHE_DIR", tmp_path)
    cache_path = tmp_path / "AAA_ratios.parquet"
    cache_path.write_text("bad-cache", encoding="utf-8")

    ratio_df = pd.DataFrame(
        {
            "yearReport": [2024],
            "lengthReport": [1],
            "P/E": [10.0],
            "EPS (VND)": [1000.0],
            "ROE (%)": [12.0],
        }
    )

    class DummyFinance:
        @staticmethod
        def ratio(period, lang):
            assert period == "quarter"
            assert lang == "en"
            return ratio_df

    class DummyStock:
        finance = DummyFinance()

    class DummyVnstock:
        def stock(self, symbol, source):
            assert symbol == "AAA"
            assert source == "VCI"
            return DummyStock()

    monkeypatch.setattr(fundamentals, "Vnstock", DummyVnstock)

    fetched = fundamentals.fetch_ticker_ratios("AAA")

    assert fetched is not None
    reloaded = pd.read_parquet(cache_path)
    assert reloaded["yearReport"].tolist() == [2024]
