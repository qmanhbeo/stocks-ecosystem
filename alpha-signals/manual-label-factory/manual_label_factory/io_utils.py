"""Reusable IO helpers for supervised labeling market data."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd

from .config import SupervisedLabelConfig, get_default_config


FILENAME_PATTERN = re.compile(r"^gia_lich_su_(?P<ticker>[A-Za-z0-9]+)_(?P<timeframe>[A-Za-z0-9]+)\.parquet$")
COLUMN_ALIASES = {
    "time": ("time", "date", "datetime", "timestamp", "trading_date"),
    "open": ("open", "Open", "gia_mo_cua"),
    "high": ("high", "High", "gia_cao_nhat"),
    "low": ("low", "Low", "gia_thap_nhat"),
    "close": ("close", "Close", "gia_dong_cua"),
    "volume": ("volume", "Volume", "vol", "khoi_luong"),
}
REQUIRED_COLUMNS = tuple(COLUMN_ALIASES.keys())


def list_stock_parquet_files(
    data_dir: Optional[Path] = None,
    timeframe: Optional[str] = None,
    config: Optional[SupervisedLabelConfig] = None,
) -> List[Path]:
    config = config or get_default_config()
    root = Path(data_dir or config.raw_data_dir)
    pattern = "*.parquet" if timeframe is None else f"*_{timeframe}.parquet"
    files = sorted(path for path in root.glob(pattern) if path.is_file())
    return files


def extract_ticker_from_filename(filename: str, timeframe: Optional[str] = None) -> str:
    match = FILENAME_PATTERN.match(Path(filename).name)
    if not match:
        raise ValueError(f"Unsupported stock parquet filename: {filename}")
    if timeframe and match.group("timeframe").upper() != str(timeframe).upper():
        raise ValueError(
            f"Filename timeframe mismatch for {filename}: expected {timeframe}, got {match.group('timeframe')}"
        )
    return match.group("ticker").upper()


def extract_timeframe_from_filename(filename: str) -> str:
    match = FILENAME_PATTERN.match(Path(filename).name)
    if not match:
        raise ValueError(f"Unsupported stock parquet filename: {filename}")
    return match.group("timeframe").upper()


def get_ticker_to_path_map(
    data_dir: Optional[Path] = None,
    timeframe: Optional[str] = None,
    config: Optional[SupervisedLabelConfig] = None,
) -> Dict[str, Path]:
    mapping: Dict[str, Path] = {}
    for path in list_stock_parquet_files(data_dir=data_dir, timeframe=timeframe, config=config):
        ticker = extract_ticker_from_filename(path.name)
        mapping[ticker] = path
    return mapping


def _resolve_column_name(columns: Iterable[str], candidates: Iterable[str]) -> Optional[str]:
    lower_map = {str(column).lower(): str(column) for column in columns}
    for candidate in candidates:
        actual = lower_map.get(str(candidate).lower())
        if actual:
            return actual
    return None


def normalize_market_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    rename_map: Dict[str, str] = {}
    for canonical_name, aliases in COLUMN_ALIASES.items():
        resolved_name = _resolve_column_name(df.columns, aliases)
        if resolved_name is None:
            raise ValueError(
                f"Missing required market column '{canonical_name}'. Available columns: {list(df.columns)}"
            )
        rename_map[resolved_name] = canonical_name

    normalized = df.rename(columns=rename_map).copy()
    normalized["time"] = pd.to_datetime(normalized["time"], utc=False)
    numeric_columns = ["open", "high", "low", "close", "volume"]
    for column in numeric_columns:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    normalized = normalized.dropna(subset=["time", "open", "high", "low", "close"])
    normalized = normalized.sort_values("time").drop_duplicates(subset=["time"], keep="last").reset_index(drop=True)
    validate_market_dataframe(normalized)
    return normalized


def validate_market_dataframe(df: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Market dataframe missing required columns: {missing}")
    if df.empty:
        raise ValueError("Market dataframe is empty")
    if not df["time"].is_monotonic_increasing:
        raise ValueError("Market dataframe must be sorted by ascending time")


def load_market_dataframe(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    return normalize_market_dataframe(frame)


def load_ticker_dataframe(
    ticker: str,
    data_dir: Optional[Path] = None,
    timeframe: Optional[str] = None,
    config: Optional[SupervisedLabelConfig] = None,
) -> pd.DataFrame:
    config = config or get_default_config()
    ticker_map = get_ticker_to_path_map(data_dir=data_dir, timeframe=timeframe or config.timeframe, config=config)
    normalized_ticker = str(ticker).upper()
    if normalized_ticker not in ticker_map:
        raise FileNotFoundError(f"No parquet file found for ticker: {normalized_ticker}")
    return load_market_dataframe(ticker_map[normalized_ticker])


def make_relative_to_repo(path: Path, config: Optional[SupervisedLabelConfig] = None) -> str:
    config = config or get_default_config()
    try:
        return str(Path(path).resolve().relative_to(config.repo_root.resolve()))
    except ValueError:
        return str(Path(path))
