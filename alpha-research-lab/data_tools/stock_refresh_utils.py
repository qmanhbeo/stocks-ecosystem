from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd


TIME_COL = "time"


@dataclass(frozen=True)
class RefreshPlan:
    mode: str
    fetch_start: str | None
    existing_last_time: pd.Timestamp | None
    message: str


def parse_iso_date(value: str) -> date:
    return datetime.fromisoformat(value).date()


def load_latest_time(path: Path) -> pd.Timestamp | None:
    if not path.exists():
        return None
    try:
        frame = pd.read_parquet(path, columns=[TIME_COL])
    except Exception:
        return None
    ts = pd.to_datetime(frame[TIME_COL], errors="coerce").dropna()
    if ts.empty:
        return None
    return ts.max()


def plan_refresh(
    path: Path,
    interval: str,
    requested_start: str,
    requested_end: str,
    *,
    full_refresh: bool = False,
) -> RefreshPlan:
    start_date = parse_iso_date(requested_start)
    end_date = parse_iso_date(requested_end)
    if start_date > end_date:
        raise ValueError("requested_start must be on or before requested_end")

    interval = interval.upper()
    if full_refresh or not path.exists():
        mode = "full" if full_refresh and path.exists() else "new"
        return RefreshPlan(
            mode=mode,
            fetch_start=start_date.isoformat(),
            existing_last_time=None,
            message=f"{mode} fetch from {start_date.isoformat()}",
        )

    latest_time = load_latest_time(path)
    if latest_time is None:
        return RefreshPlan(
            mode="new",
            fetch_start=start_date.isoformat(),
            existing_last_time=None,
            message=f"existing file unreadable/empty, refetching from {start_date.isoformat()}",
        )

    latest_date = latest_time.date()
    if interval == "1D":
        fetch_start = max(start_date, latest_date + timedelta(days=1))
    else:
        # Intraday runs should refetch the last stored trading date to capture
        # any late-added bars and then dedupe on merge.
        fetch_start = max(start_date, latest_date)

    if fetch_start > end_date:
        return RefreshPlan(
            mode="skip",
            fetch_start=None,
            existing_last_time=latest_time,
            message=f"already current through {latest_date.isoformat()}",
        )

    return RefreshPlan(
        mode="incremental",
        fetch_start=fetch_start.isoformat(),
        existing_last_time=latest_time,
        message=(
            f"incremental fetch from {fetch_start.isoformat()} "
            f"(existing latest {latest_date.isoformat()})"
        ),
    )


def combine_frames(existing: pd.DataFrame | None, incoming: pd.DataFrame) -> pd.DataFrame:
    if existing is None or existing.empty:
        combined = incoming.copy()
    else:
        columns = list(existing.columns)
        for column in incoming.columns:
            if column not in columns:
                columns.append(column)
        existing_aligned = existing.copy()
        incoming_aligned = incoming.copy()
        for column in columns:
            if column not in existing_aligned.columns:
                existing_aligned[column] = pd.NA
            if column not in incoming_aligned.columns:
                incoming_aligned[column] = pd.NA
        combined = pd.concat(
            [existing_aligned[columns], incoming_aligned[columns]],
            ignore_index=True,
        )

    combined[TIME_COL] = pd.to_datetime(combined[TIME_COL], errors="coerce")
    combined = combined.dropna(subset=[TIME_COL])
    combined = (
        combined.sort_values(TIME_COL)
        .drop_duplicates(subset=[TIME_COL], keep="last")
        .reset_index(drop=True)
    )
    return combined


def load_existing_frame(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception:
        return None


def atomic_write_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    frame.to_parquet(temp_path, index=False)
    temp_path.replace(path)
