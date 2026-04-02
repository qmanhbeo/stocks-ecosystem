from __future__ import annotations

import pandas as pd

from data_tools import fetch_fx_commodities as fx
from data_tools import fetch_global_macro as macro
from data_tools.stock_refresh_utils import (
    build_probe_cache_entry,
    error_message_indicates_rate_limit,
    latest_value_covers_requested_end,
)


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


def test_latest_value_covers_requested_end_allows_small_gap_but_rejects_stale_tail():
    assert latest_value_covers_requested_end("2026-03-29", "2026-03-31", max_lag_days=3) is True
    assert latest_value_covers_requested_end("2026-03-17", "2026-03-31", max_lag_days=3) is False
    assert error_message_indicates_rate_limit("YFRateLimitError('Too Many Requests')") is True
    assert error_message_indicates_rate_limit("other failure") is False
    assert fx._ticker_for_yahoo("TWII") == "^TWII"
    assert fx._ticker_for_yahoo("N225") == "^N225"
    assert "^TWII" in fx.DEFAULT_TICKERS
    assert "^N225" in fx.DEFAULT_TICKERS


def test_fetch_fx_commodities_does_not_probe_skip_stale_unchanged_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(fx, "OUT_DIR", tmp_path)
    output_path = tmp_path / "fx_commodities_fx_vnd_usd_1D.parquet"
    _write_timeseries(output_path, [("2026-03-17", 1.0)])

    cache_record = build_probe_cache_entry(
        status="unchanged",
        checked_end="2026-03-31",
        path=output_path,
        latest_value=pd.Timestamp("2026-03-17"),
    )
    assert cache_record is not None

    calls: list[tuple[str, str, str]] = []

    def fake_download(ticker, start, end, interval, progress, auto_adjust):
        calls.append((ticker, start, end))
        return pd.DataFrame()

    monkeypatch.setattr(fx.yf, "download", fake_download)

    status, cache_entry = fx.fetch_ticker(
        "VND=X",
        "1D",
        "2000-01-01",
        "2026-03-31",
        dict(fx.DEFAULT_ALIASES),
        overwrite=False,
        probe_cache={"fx_vnd_usd": cache_record},
        probe_cache_ttl_hours=24.0,
    )

    assert status == fx.FETCH_STATUS_RETRYABLE
    assert calls == [("VND=X", "2026-03-18", "2026-04-01")]
    assert cache_entry is None


def test_fetch_global_macro_does_not_probe_skip_stale_unchanged_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(macro, "OUT_DIR", tmp_path)
    output_path = tmp_path / "fx_commodities_dxy_1D.parquet"
    _write_timeseries(output_path, [("2026-03-17", 100.0)])

    cache_record = build_probe_cache_entry(
        status="unchanged",
        checked_end="2026-03-31",
        path=output_path,
        latest_value=pd.Timestamp("2026-03-17"),
    )
    assert cache_record is not None

    calls: list[tuple[str, str, str]] = []

    def fake_download(ticker, start, end, progress, auto_adjust):
        calls.append((ticker, start, end))
        return pd.DataFrame()

    monkeypatch.setattr(macro.yf, "download", fake_download)

    status, cache_entry = macro.fetch_one(
        "DX-Y.NYB",
        "dxy",
        overwrite=False,
        start="2000-01-01",
        end="2026-03-31",
        probe_cache={"dxy": cache_record},
        probe_cache_ttl_hours=24.0,
    )

    assert status == macro.FETCH_STATUS_RETRYABLE
    assert calls == [("DX-Y.NYB", "2026-03-18", "2026-04-01")]
    assert cache_entry is None


def test_fetch_fx_commodities_returns_rate_limited_status(monkeypatch, tmp_path):
    monkeypatch.setattr(fx, "OUT_DIR", tmp_path)
    output_path = tmp_path / "fx_commodities_fx_vnd_usd_1D.parquet"
    _write_timeseries(output_path, [("2026-03-17", 1.0)])

    def fake_download(ticker, start, end, interval, progress, auto_adjust):
        fx.yf_shared._ERRORS = {ticker.upper(): "YFRateLimitError('Too Many Requests. Rate limited. Try after a while.')"}
        return pd.DataFrame()

    monkeypatch.setattr(fx.yf, "download", fake_download)
    monkeypatch.setattr(fx.time, "sleep", lambda _: None)

    status, cache_entry = fx.fetch_ticker(
        "VND=X",
        "1D",
        "2000-01-01",
        "2026-03-31",
        dict(fx.DEFAULT_ALIASES),
        overwrite=False,
        probe_cache={},
        probe_cache_ttl_hours=24.0,
        rate_limit_retries=0,
    )

    assert status == fx.FETCH_STATUS_RATE_LIMITED
    assert cache_entry is None


def test_fetch_global_macro_returns_rate_limited_status(monkeypatch, tmp_path):
    monkeypatch.setattr(macro, "OUT_DIR", tmp_path)
    output_path = tmp_path / "fx_commodities_dxy_1D.parquet"
    _write_timeseries(output_path, [("2026-03-17", 100.0)])

    def fake_download(ticker, start, end, progress, auto_adjust):
        macro.yf_shared._ERRORS = {ticker.upper(): "YFRateLimitError('Too Many Requests. Rate limited. Try after a while.')"}
        return pd.DataFrame()

    monkeypatch.setattr(macro.yf, "download", fake_download)
    monkeypatch.setattr(macro.time, "sleep", lambda _: None)

    status, cache_entry = macro.fetch_one(
        "DX-Y.NYB",
        "dxy",
        overwrite=False,
        start="2000-01-01",
        end="2026-03-31",
        probe_cache={},
        probe_cache_ttl_hours=24.0,
        rate_limit_retries=0,
    )

    assert status == macro.FETCH_STATUS_RATE_LIMITED
    assert cache_entry is None
