from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import re
import warnings

import pandas as pd


TIME_COL = "time"
PROBE_CACHE_DIRNAME = "_refresh_metadata"
DEFAULT_PROBE_CACHE_ELIGIBLE_STATUSES = frozenset({"unchanged", "partial"})


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
        # Missing columns are intentionally padded with all-NA placeholders so
        # older files can merge with newer schemas without rewriting history.
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=(
                    "The behavior of DataFrame concatenation with empty or all-NA "
                    "entries is deprecated"
                ),
                category=FutureWarning,
            )
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


def _sanitize_probe_namespace(namespace: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(namespace)).strip("._")
    return cleaned or "probe_cache"


def build_probe_cache_path(base_dir: Path, namespace: str) -> Path:
    return base_dir / PROBE_CACHE_DIRNAME / f"{_sanitize_probe_namespace(namespace)}.json"


def load_probe_cache(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    item_state = payload.get("item_state")
    if not isinstance(item_state, dict):
        item_state = payload.get("ticker_state")
    if not isinstance(item_state, dict):
        return {}
    return {
        str(item_key): record
        for item_key, record in item_state.items()
        if isinstance(record, dict)
    }


def save_probe_cache(
    path: Path,
    item_state: dict[str, dict[str, object]],
    *,
    metadata: dict[str, object] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "item_state": dict(sorted((str(item_key), record) for item_key, record in item_state.items())),
    }
    if metadata:
        payload.update(metadata)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)


def serialize_probe_cache_value(value: object | None) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return str(value)


def latest_value_covers_requested_end(
    latest_value: object | None,
    requested_end: str,
    *,
    max_lag_days: int = 0,
) -> bool:
    if latest_value is None:
        return False
    try:
        latest_ts = pd.Timestamp(latest_value).normalize()
        requested_end_ts = pd.Timestamp(requested_end).normalize()
    except Exception:
        return False
    return latest_ts >= (requested_end_ts - pd.Timedelta(days=max_lag_days))


def error_message_indicates_rate_limit(error_message: object | None) -> bool:
    if error_message is None:
        return False
    text = str(error_message)
    return "YFRateLimitError" in text or "Too Many Requests" in text


def build_probe_cache_entry(
    *,
    status: str,
    checked_end: str,
    path: Path,
    latest_value: object | None,
    extras: dict[str, object] | None = None,
) -> dict[str, object] | None:
    if not path.exists():
        return None
    entry: dict[str, object] = {
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "checked_end": checked_end,
        "file_mtime_ns": path.stat().st_mtime_ns,
        "latest_value": serialize_probe_cache_value(latest_value),
        "status": status,
    }
    if extras:
        entry.update(extras)
    return entry


def probe_cache_record_is_fresh(
    record: dict[str, object] | None,
    *,
    requested_end: str,
    path: Path,
    latest_value: object | None,
    ttl_hours: float,
    eligible_statuses: set[str] | frozenset[str] | None = None,
) -> bool:
    if ttl_hours <= 0 or not isinstance(record, dict):
        return False

    statuses = eligible_statuses or DEFAULT_PROBE_CACHE_ELIGIBLE_STATUSES
    if str(record.get("status")) not in statuses:
        return False

    try:
        checked_end = pd.Timestamp(record["checked_end"]).normalize()
        requested_end_ts = pd.Timestamp(requested_end).normalize()
        checked_at = datetime.fromisoformat(str(record["checked_at"]))
        cached_mtime_ns = int(record["file_mtime_ns"])
    except Exception:
        return False

    if requested_end_ts > checked_end:
        return False
    if checked_at < (datetime.now() - timedelta(hours=ttl_hours)):
        return False
    if not path.exists():
        return False
    try:
        current_mtime_ns = path.stat().st_mtime_ns
    except Exception:
        return False
    if current_mtime_ns != cached_mtime_ns:
        return False
    return serialize_probe_cache_value(record.get("latest_value")) == serialize_probe_cache_value(latest_value)


def format_probe_cache_skip_message(
    record: dict[str, object],
    *,
    subject: str = "source",
) -> str:
    checked_end = str(record.get("checked_end", "?"))
    latest_value = serialize_probe_cache_value(record.get("latest_value"))
    latest_label = latest_value.split("T", 1)[0] if latest_value else "unknown"
    checked_at = str(record.get("checked_at", "unknown"))
    checked_label = checked_at.replace("T", " ")
    return (
        f"probe cache says {subject} was already checked through "
        f"{checked_end} with latest {latest_label} "
        f"(checked {checked_label})"
    )


def update_probe_cache_state(
    cache_path: Path | None,
    item_state: dict[str, dict[str, object]],
    *,
    item_key: str,
    entry: dict[str, object] | None,
    metadata: dict[str, object] | None = None,
) -> None:
    if cache_path is None or entry is None:
        return
    item_state[str(item_key)] = entry
    save_probe_cache(cache_path, item_state, metadata=metadata)
