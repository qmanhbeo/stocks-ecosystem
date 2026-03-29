from __future__ import annotations

from pathlib import Path

import pandas as pd


def build_stock_day_grid(
    *,
    stock_dir: Path,
    exclude: set[str] | frozenset[str],
    min_rows: int = 1,
    start_year: int | None = None,
    end_year: int | None = None,
) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for file_path in sorted(stock_dir.glob("gia_lich_su_*_1D.parquet")):
        ticker = file_path.stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in exclude:
            continue
        frame = pd.read_parquet(file_path, columns=["time"]).copy()
        frame["time"] = pd.to_datetime(frame["time"])
        frame = frame.sort_values("time").drop_duplicates("time")
        if len(frame) < int(min_rows):
            continue
        if start_year is not None:
            frame = frame.loc[frame["time"].dt.year >= int(start_year)]
        if end_year is not None:
            frame = frame.loc[frame["time"].dt.year <= int(end_year)]
        if frame.empty:
            continue
        frame["ticker"] = ticker
        parts.append(frame[["time", "ticker"]])

    if not parts:
        return pd.DataFrame(columns=["time", "ticker"])

    return (
        pd.concat(parts, ignore_index=True)
        .drop_duplicates(["time", "ticker"])
        .sort_values(["time", "ticker"])
        .reset_index(drop=True)
    )
