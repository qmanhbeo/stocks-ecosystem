"""Shared path helpers for loading market data."""

from __future__ import annotations

from pathlib import Path


def stock_parquet_path(data_dir: str | Path, ticker: str, timeframe: str = "1D") -> Path:
    return Path(data_dir) / f"gia_lich_su_{ticker}_{timeframe}.parquet"


def fx_parquet_path(data_dir: str | Path, asset_name: str, timeframe: str = "1d") -> Path:
    return Path(data_dir) / f"gia_lich_su_{asset_name}_{timeframe}.parquet"
