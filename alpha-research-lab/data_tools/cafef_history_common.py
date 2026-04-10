from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from path_utils import data_path

try:
    from stock_refresh_utils import atomic_write_parquet
except ModuleNotFoundError:
    from data_tools.stock_refresh_utils import atomic_write_parquet


STOCK_DIR = data_path("stock")
EXCLUDE_DEFAULT = {"VNINDEX", "VN30"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_iso_date(value: str) -> date:
    return datetime.fromisoformat(value).date()


def format_query_date(value: date) -> str:
    return value.strftime("%m/%d/%Y")


def parse_tickers(value: str | None) -> list[str]:
    if not value:
        return []
    return sorted(dict.fromkeys(item.strip().upper() for item in value.split(",") if item.strip()))


def load_default_tickers() -> list[str]:
    tickers: list[str] = []
    for path in STOCK_DIR.glob("gia_lich_su_*_1D.parquet"):
        ticker = path.stem.replace("gia_lich_su_", "").replace("_1D", "").upper()
        if ticker and ticker not in EXCLUDE_DEFAULT:
            tickers.append(ticker)
    return sorted(dict.fromkeys(tickers))


def per_ticker_dir(output_root: Path) -> Path:
    return output_root / "per_ticker"


def panel_path(output_root: Path, filename: str) -> Path:
    return output_root / filename


def manifest_path(output_root: Path) -> Path:
    return output_root / "manifest.json"


def cache_path(output_root: Path, ticker: str) -> Path:
    return per_ticker_dir(output_root) / f"{ticker.upper()}.parquet"


def metadata_path(output_root: Path, ticker: str) -> Path:
    return per_ticker_dir(output_root) / f"{ticker.upper()}.meta.json"


def load_cached_frame(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception as exc:
        print(f"  WARN {path.name}: unreadable cache, refetching ({exc})")
        return None


def latest_cached_date(frame: pd.DataFrame | None) -> date | None:
    if frame is None or frame.empty or "date" not in frame.columns:
        return None
    values = pd.to_datetime(frame["date"], errors="coerce").dropna()
    if values.empty:
        return None
    return values.max().date()


def earliest_cached_date(frame: pd.DataFrame | None) -> date | None:
    if frame is None or frame.empty or "date" not in frame.columns:
        return None
    values = pd.to_datetime(frame["date"], errors="coerce").dropna()
    if values.empty:
        return None
    return values.min().date()


def load_cache_metadata(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def parse_optional_iso_date(value: object) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return parse_iso_date(value)
    except Exception:
        return None


def cache_covers_requested_window(metadata: dict[str, Any] | None, start_date: date, end_date: date) -> bool:
    if not metadata:
        return False
    coverage_start = parse_optional_iso_date(metadata.get("coverage_start_date"))
    coverage_end = parse_optional_iso_date(metadata.get("coverage_end_date"))
    if coverage_start is None or coverage_end is None:
        return False
    return coverage_start <= start_date and coverage_end >= end_date


def write_cache_metadata(
    path: Path,
    *,
    ticker: str,
    source: str,
    query_start: date,
    requested_end: date,
    combined: pd.DataFrame,
    previous_metadata: dict[str, Any] | None,
) -> None:
    previous_coverage_start = parse_optional_iso_date((previous_metadata or {}).get("coverage_start_date"))
    coverage_start = min(previous_coverage_start, query_start) if previous_coverage_start is not None else query_start
    observed_start = earliest_cached_date(combined)
    observed_end = latest_cached_date(combined)
    payload = {
        "ticker": ticker.upper(),
        "source": source,
        "fetched_at_utc": utc_now_iso(),
        "coverage_start_date": coverage_start.isoformat(),
        "coverage_end_date": requested_end.isoformat(),
        "observed_date_min": observed_start.isoformat() if observed_start is not None else None,
        "observed_date_max": observed_end.isoformat() if observed_end is not None else None,
        "rows": int(len(combined)),
    }
    atomic_write_json(payload, path)


def combine_frames(existing: pd.DataFrame | None, incoming: pd.DataFrame, contract_columns: list[str]) -> pd.DataFrame:
    if existing is None or existing.empty:
        combined = incoming.copy()
    elif incoming.empty:
        combined = existing.copy()
    else:
        columns = list(dict.fromkeys([*existing.columns, *incoming.columns]))
        existing_aligned = existing.copy()
        incoming_aligned = incoming.copy()
        for column in columns:
            if column not in existing_aligned.columns:
                existing_aligned[column] = pd.NA
            if column not in incoming_aligned.columns:
                incoming_aligned[column] = pd.NA
        combined = pd.concat([existing_aligned[columns], incoming_aligned[columns]], ignore_index=True)

    if combined.empty:
        return pd.DataFrame(columns=contract_columns)

    combined["date"] = pd.to_datetime(combined["date"], errors="coerce")
    combined = combined.dropna(subset=["date", "ticker"])
    combined["ticker"] = combined["ticker"].astype(str).str.upper()
    combined = combined.sort_values(["ticker", "date"]).drop_duplicates(["ticker", "date"], keep="last")
    combined["date"] = combined["date"].dt.strftime("%Y-%m-%d")
    for column in contract_columns:
        if column not in combined.columns:
            combined[column] = pd.NA
    return combined[contract_columns].reset_index(drop=True)


def atomic_write_json(payload: dict[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(path)


def path_for_json(path: Path) -> str:
    try:
        return str(path.relative_to(data_path("")))
    except ValueError:
        return str(path)


def write_run_manifest(
    *,
    output_root: Path,
    source: str,
    panel_filename: str,
    contract_columns: list[str],
    contract_notes: list[str],
    started_at_utc: str,
    requested_start_date: date,
    requested_end_date: date,
    tickers_requested: int,
    tickers_processed: int,
    tickers_fetched: int,
    tickers_cached: int,
    tickers_failed: int,
    status: str,
    items: list[dict[str, object]],
    current_ticker: str | None = None,
    panel: pd.DataFrame | None = None,
) -> None:
    payload: dict[str, object] = {
        "contract": {
            "source": source,
            "root": path_for_json(output_root),
            "per_ticker_dir": path_for_json(per_ticker_dir(output_root)),
            "panel": path_for_json(panel_path(output_root, panel_filename)),
            "primary_key": ["ticker", "date"],
            "contract_columns": contract_columns,
            "notes": contract_notes,
        },
        "last_run": {
            "status": status,
            "started_at_utc": started_at_utc,
            "updated_at_utc": utc_now_iso(),
            "requested_start_date": requested_start_date.isoformat(),
            "requested_end_date": requested_end_date.isoformat(),
            "tickers_requested": int(tickers_requested),
            "tickers_processed": int(tickers_processed),
            "tickers_remaining": int(max(tickers_requested - tickers_processed, 0)),
            "tickers_fetched": int(tickers_fetched),
            "tickers_cached": int(tickers_cached),
            "tickers_failed": int(tickers_failed),
            "current_ticker": current_ticker,
            "items": items,
        },
    }
    if panel is not None:
        payload["last_run"]["panel_rows"] = int(len(panel))
        payload["last_run"]["panel_tickers"] = int(panel["ticker"].nunique()) if not panel.empty else 0
    atomic_write_json(payload, manifest_path(output_root))


def build_session(*, referer: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0",
            "Referer": referer,
        }
    )
    return session


def request_page(
    session: requests.Session,
    *,
    url: str,
    ticker: str,
    start_date: date,
    end_date: date,
    page_index: int,
    page_size: int,
    timeout: float,
    retries: int,
) -> dict[str, object]:
    params = {
        "Symbol": ticker,
        "StartDate": format_query_date(start_date),
        "EndDate": format_query_date(end_date),
        "PageIndex": page_index,
        "PageSize": page_size,
    }
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = session.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
            if payload.get("Success") is False:
                raise ValueError(f"CafeF returned Success=false: {payload.get('Message')}")
            if not isinstance(payload, dict):
                raise ValueError("CafeF returned a non-dict JSON payload")
            return payload
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"{ticker}: page {page_index} failed after {retries + 1} attempts: {last_exc}")


def default_query_start(
    *,
    force: bool,
    cached_frame: pd.DataFrame | None,
    requested_start: date,
    requested_end: date,
    lookback_days: int,
) -> date:
    if force:
        return requested_start
    cached_latest = latest_cached_date(cached_frame)
    if cached_latest is None:
        return requested_start
    return max(requested_start, min(cached_latest, requested_end) - timedelta(days=lookback_days))


def fetch_page_rows(
    session: requests.Session,
    *,
    url: str,
    ticker: str,
    start_date: date,
    end_date: date,
    page_size: int,
    max_pages: int,
    timeout: float,
    retries: int,
    extract_rows: Any,
    extract_total_count: Any,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    total_count: int | None = None
    for page_index in range(1, max_pages + 1):
        payload = request_page(
            session,
            url=url,
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            page_index=page_index,
            page_size=page_size,
            timeout=timeout,
            retries=retries,
        )
        chunk = extract_rows(payload)
        if not isinstance(chunk, list):
            raise ValueError(f"{ticker}: payload rows are not a list")
        if total_count is None:
            total_count = int(extract_total_count(payload) or 0)
        rows.extend(chunk)
        if len(rows) >= total_count or not chunk or len(chunk) < page_size:
            break
    else:
        raise RuntimeError(f"{ticker}: hit --max-pages={max_pages}; increase the cap or lower date range")
    return rows


def write_panel_from_disk(
    *,
    output_root: Path,
    contract_columns: list[str],
    panel_filename: str,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in sorted(per_ticker_dir(output_root).glob("*.parquet")):
        try:
            frame = pd.read_parquet(path)
        except Exception as exc:
            print(f"  WARN {path.name}: skipping unreadable cache during panel rebuild ({exc})")
            continue
        if frame.empty:
            continue
        frames.append(frame)
    if not frames:
        panel = pd.DataFrame(columns=contract_columns)
    else:
        panel = combine_frames(None, pd.concat(frames, ignore_index=True), contract_columns)
    atomic_write_parquet(panel, panel_path(output_root, panel_filename))
    return panel
