from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from vn_stock_rl.external_features import shared_data_root

OHLCV_COLUMNS = ("time", "open", "high", "low", "close", "volume")
TRADABILITY_COLUMNS = ("time", "ticker", "can_buy_next_open", "can_sell_next_open")


def stock_bars_path(ticker: str, *, data_root: str | Path | None = None) -> Path:
    symbol = str(ticker).strip().upper()
    if not symbol or any(character in symbol for character in "/\\"):
        raise ValueError("ticker must be a non-empty ticker symbol")
    if data_root is not None:
        root = Path(data_root).expanduser().resolve()
    else:
        if not os.environ.get("STOCKS_DATA_ROOT"):
            raise RuntimeError(
                "Set STOCKS_DATA_ROOT to the shared canonical "
                "data directory before loading stock data"
            )
        root = shared_data_root()
    return root / "stock" / f"gia_lich_su_{symbol}_1D.parquet"


def load_daily_stock_bars(
    ticker: str,
    *,
    data_root: str | Path | None = None,
    start_date=None,
    end_date=None,
) -> pd.DataFrame:
    """Read OHLCV through a read-only handle and enforce exact inclusive date bounds.

    Parquet ``filters`` can prune row groups without filtering rows inside a
    surviving row group. Apply the date predicates again in memory before the
    caller constructs features or statistics.
    """

    path = stock_bars_path(ticker, data_root=data_root)
    if not path.is_file():
        raise FileNotFoundError(f"Daily stock bars not found: {path}")
    filters = []
    if start_date is not None:
        filters.append(("time", ">=", pd.Timestamp(start_date)))
    if end_date is not None:
        filters.append(("time", "<=", pd.Timestamp(end_date)))
    with path.open("rb") as stream:
        frame = pd.read_parquet(
            stream,
            columns=list(OHLCV_COLUMNS),
            filters=filters or None,
        )
    missing = set(OHLCV_COLUMNS).difference(frame.columns)
    if missing:
        raise ValueError(f"Stock bars are missing columns: {sorted(missing)}")
    result = frame.loc[:, list(OHLCV_COLUMNS)].copy()
    result["time"] = pd.to_datetime(result["time"], errors="raise")
    normalized_dates = result["time"].dt.normalize()
    if start_date is not None:
        start = pd.Timestamp(start_date).normalize()
        result = result.loc[normalized_dates >= start].copy()
        normalized_dates = result["time"].dt.normalize()
    if end_date is not None:
        end = pd.Timestamp(end_date).normalize()
        result = result.loc[normalized_dates <= end].copy()
    result = result.sort_values("time", kind="stable").reset_index(drop=True)
    if result.empty:
        raise ValueError(f"No OHLCV rows remain inside the requested date bounds: {path}")
    bounded_dates = result["time"].dt.normalize()
    if start_date is not None and (bounded_dates < pd.Timestamp(start_date).normalize()).any():
        raise RuntimeError("OHLCV start-date filter was not enforced")
    if end_date is not None and (bounded_dates > pd.Timestamp(end_date).normalize()).any():
        raise RuntimeError("OHLCV end-date filter was not enforced")
    if result["time"].duplicated().any():
        raise ValueError(f"Stock bars contain duplicate dates: {path}")
    for column in ("open", "high", "low", "close"):
        values = pd.to_numeric(result[column], errors="coerce")
        if values.isna().any() or (values <= 0.0).any():
            raise ValueError(f"Stock bars contain invalid positive-price values in {column}")
        result[column] = values.astype(float)
    result["volume"] = pd.to_numeric(result["volume"], errors="coerce")
    result.attrs["source_path"] = str(path)
    result.attrs["price_basis"] = "unverified"
    return result


def load_daily_tradability_flags(
    ticker: str,
    dates,
    *,
    data_root: str | Path | None = None,
) -> tuple[pd.Series, pd.Series]:
    """Read shared next-open flags and align them by date without writing to data."""

    if data_root is not None:
        root = Path(data_root).expanduser().resolve()
    else:
        if not os.environ.get("STOCKS_DATA_ROOT"):
            raise RuntimeError(
                "Set STOCKS_DATA_ROOT to the shared canonical "
                "data directory before loading tradability data"
            )
        root = shared_data_root()
    path = root / "features" / "execution" / "tradability_daily.parquet"
    if not path.is_file():
        raise FileNotFoundError(f"Shared tradability data not found: {path}")
    symbol = str(ticker).strip().upper()
    requested = pd.DatetimeIndex(pd.to_datetime(dates)).normalize()
    if requested.empty:
        raise ValueError("dates must contain at least one requested date")
    filters = [
        ("ticker", "=", symbol),
        ("time", ">=", requested.min()),
        ("time", "<=", requested.max()),
    ]
    with path.open("rb") as stream:
        flags = pd.read_parquet(stream, columns=list(TRADABILITY_COLUMNS), filters=filters)
    flags = flags.loc[flags["ticker"].astype(str).str.upper() == symbol].copy()
    flags["time"] = pd.to_datetime(flags["time"], errors="raise").dt.normalize()
    flags = flags.loc[
        flags["time"].between(requested.min(), requested.max(), inclusive="both")
    ].copy()
    if flags["time"].duplicated().any():
        raise ValueError(f"Shared tradability data has duplicate {symbol} dates")
    indexed = flags.set_index("time")
    aligned = indexed.reindex(requested)
    if aligned[["can_buy_next_open", "can_sell_next_open"]].isna().any().any():
        raise ValueError(f"Shared tradability data is incomplete for {symbol} requested dates")
    buy_flags, sell_flags = (
        aligned["can_buy_next_open"].astype(bool).reset_index(drop=True),
        aligned["can_sell_next_open"].astype(bool).reset_index(drop=True),
    )
    return buy_flags, sell_flags
