"""
Fetch historical daily foreign-investor flow from CafeF's GDKhoiNgoai endpoint.

CafeF's public stock history page has a "Khối ngoại" tab backed by:
    https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDKhoiNgoai.ashx

Builds:
    data/foreign_flow/cafef/per_ticker/<TICKER>.parquet
    data/foreign_flow/cafef/foreign_flow_daily.parquet
    data/foreign_flow/cafef/manifest.json

Usage:
    python data_tools/fetch_cafef_foreign_flow.py --tickers FPT,VCB,HPG
    python data_tools/fetch_cafef_foreign_flow.py --start-date 2015-01-01 --end-date 2026-04-09
    python data_tools/fetch_cafef_foreign_flow.py --dry-run --max-tickers 10
"""

from __future__ import annotations

import argparse
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


URL = "https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDKhoiNgoai.ashx"
SOURCE = "cafef_gdkhoingoai"
DEFAULT_START_DATE = "2000-01-01"
DEFAULT_END_DATE = date.today().isoformat()
DEFAULT_OUTPUT_ROOT = data_path("foreign_flow/cafef")
STOCK_DIR = data_path("stock")
EXCLUDE_DEFAULT = {"VNINDEX", "VN30"}
CONTRACT_COLUMNS = [
    "ticker",
    "date",
    "source",
    "foreign_buy_volume",
    "foreign_sell_volume",
    "foreign_net_volume",
    "foreign_buy_value",
    "foreign_sell_value",
    "foreign_net_value",
    "foreign_room_remaining",
    "foreign_ownership_pct",
    "price_change_raw",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", help="Comma-separated tickers. Defaults to root data/stock universe.")
    parser.add_argument("--start-date", default=DEFAULT_START_DATE, help="Inclusive start date, YYYY-MM-DD")
    parser.add_argument("--end-date", default=DEFAULT_END_DATE, help="Inclusive end date, YYYY-MM-DD")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--force", action="store_true", help="Refetch the full requested window.")
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=7,
        help="When cache exists, refetch this many days before latest cached date.",
    )
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--max-pages", type=int, default=1000)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--sleep", type=float, default=0.2, help="Sleep between ticker requests.")
    parser.add_argument("--max-tickers", type=int, help="Limit ticker count for probes.")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without fetching or writing.")
    return parser.parse_args()


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


def panel_path(output_root: Path) -> Path:
    return output_root / "foreign_flow_daily.parquet"


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
        "source": SOURCE,
        "fetched_at_utc": utc_now_iso(),
        "coverage_start_date": coverage_start.isoformat(),
        "coverage_end_date": requested_end.isoformat(),
        "observed_date_min": observed_start.isoformat() if observed_start is not None else None,
        "observed_date_max": observed_end.isoformat() if observed_end is not None else None,
        "rows": int(len(combined)),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(path)


def load_panel_from_disk(output_root: Path) -> pd.DataFrame:
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
        return pd.DataFrame(columns=CONTRACT_COLUMNS)
    return combine_frames(None, pd.concat(frames, ignore_index=True))


def normalize_payload_rows(rows: list[dict[str, object]], ticker: str) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=CONTRACT_COLUMNS)

    frame = pd.DataFrame(rows)
    out = pd.DataFrame(index=frame.index)
    out["ticker"] = ticker.upper()
    out["date"] = pd.to_datetime(frame.get("Ngay"), format="%d/%m/%Y", errors="coerce")
    out["source"] = SOURCE
    out["foreign_buy_volume"] = pd.to_numeric(frame.get("KLMua"), errors="coerce")
    out["foreign_sell_volume"] = pd.to_numeric(frame.get("KLBan"), errors="coerce")
    out["foreign_net_volume"] = pd.to_numeric(frame.get("KLGDRong"), errors="coerce")
    out["foreign_buy_value"] = pd.to_numeric(frame.get("GtMua"), errors="coerce")
    out["foreign_sell_value"] = pd.to_numeric(frame.get("GtBan"), errors="coerce")
    out["foreign_net_value"] = pd.to_numeric(frame.get("GTDGRong"), errors="coerce")
    out["foreign_room_remaining"] = pd.to_numeric(frame.get("RoomConLai"), errors="coerce")
    out["foreign_ownership_pct"] = pd.to_numeric(frame.get("DangSoHuu"), errors="coerce")
    out["price_change_raw"] = frame.get("ThayDoi")

    out = out.dropna(subset=["date"]).sort_values("date").drop_duplicates(["ticker", "date"], keep="last")
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    return out[CONTRACT_COLUMNS].reset_index(drop=True)


def combine_frames(existing: pd.DataFrame | None, incoming: pd.DataFrame) -> pd.DataFrame:
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
        return pd.DataFrame(columns=CONTRACT_COLUMNS)

    combined["date"] = pd.to_datetime(combined["date"], errors="coerce")
    combined = combined.dropna(subset=["date", "ticker"])
    combined["ticker"] = combined["ticker"].astype(str).str.upper()
    combined = combined.sort_values(["ticker", "date"]).drop_duplicates(["ticker", "date"], keep="last")
    combined["date"] = combined["date"].dt.strftime("%Y-%m-%d")
    for column in CONTRACT_COLUMNS:
        if column not in combined.columns:
            combined[column] = pd.NA
    return combined[CONTRACT_COLUMNS].reset_index(drop=True)


def request_page(
    session: requests.Session,
    ticker: str,
    start_date: date,
    end_date: date,
    page_index: int,
    page_size: int,
    timeout: float,
    retries: int,
) -> list[dict[str, object]]:
    params = {
        "Symbol": ticker,
        "StartDate": format_query_date(start_date),
        "EndDate": format_query_date(end_date),
        "PageIndex": page_index,
        "PageSize": page_size,
    }
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": f"https://cafef.vn/du-lieu/lich-su-giao-dich-{ticker.lower()}-3.chn",
    }
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = session.get(URL, params=params, headers=headers, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
            if payload.get("Success") is False:
                raise ValueError(f"CafeF returned Success=false: {payload.get('Message')}")
            data = payload.get("Data") or {}
            rows = data.get("Data") or []
            if not isinstance(rows, list):
                raise ValueError("CafeF returned a non-list Data.Data payload")
            return rows
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"{ticker}: page {page_index} failed after {retries + 1} attempts: {last_exc}")


def fetch_ticker(
    session: requests.Session,
    ticker: str,
    start_date: date,
    end_date: date,
    page_size: int,
    max_pages: int,
    timeout: float,
    retries: int,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for page_index in range(1, max_pages + 1):
        chunk = request_page(
            session,
            ticker,
            start_date,
            end_date,
            page_index,
            page_size,
            timeout,
            retries,
        )
        rows.extend(chunk)
        if not chunk or len(chunk) < page_size:
            break
    else:
        raise RuntimeError(f"{ticker}: hit --max-pages={max_pages}; increase the cap or lower date range")

    return normalize_payload_rows(rows, ticker)


def write_manifest(output_root: Path, payload: dict[str, object]) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path(output_root).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    start_date = parse_iso_date(args.start_date)
    end_date = parse_iso_date(args.end_date)
    if start_date > end_date:
        raise ValueError("--start-date must be on or before --end-date")
    if args.lookback_days < 0:
        raise ValueError("--lookback-days must be non-negative")
    if args.page_size <= 0:
        raise ValueError("--page-size must be positive")
    if args.max_pages <= 0:
        raise ValueError("--max-pages must be positive")

    tickers = parse_tickers(args.tickers) or load_default_tickers()
    if args.max_tickers is not None:
        tickers = tickers[: args.max_tickers]
    if not tickers:
        raise ValueError("No tickers selected")

    print(f"Source: {URL}")
    print(f"Output root: {args.output_root}")
    print(f"Window: {start_date.isoformat()} -> {end_date.isoformat()}")
    print(f"Tickers: {len(tickers)}")
    if args.dry_run:
        print("Dry run only. First tickers:", ", ".join(tickers[:20]))
        return

    per_ticker_dir(args.output_root).mkdir(parents=True, exist_ok=True)
    fetched = reused = skipped = 0
    failures: list[dict[str, str]] = []
    fetched_at_utc = utc_now_iso()

    with requests.Session() as session:
        for index, ticker in enumerate(tickers, start=1):
            path = cache_path(args.output_root, ticker)
            meta_path = metadata_path(args.output_root, ticker)
            cached = load_cached_frame(path)
            metadata = load_cache_metadata(meta_path)
            latest = latest_cached_date(cached)
            cache_has_coverage = cache_covers_requested_window(metadata, start_date, end_date)

            if (
                not args.force
                and latest is not None
                and cache_has_coverage
                and latest >= end_date
            ):
                reused += 1
            else:
                query_start = start_date
                if not args.force and latest is not None and cache_has_coverage:
                    query_start = max(start_date, latest - timedelta(days=args.lookback_days))
                try:
                    incoming = fetch_ticker(
                        session,
                        ticker,
                        query_start,
                        end_date,
                        args.page_size,
                        args.max_pages,
                        args.timeout,
                        args.retries,
                    )
                    combined = combine_frames(cached, incoming)
                    if combined.empty:
                        skipped += 1
                    else:
                        atomic_write_parquet(combined, path)
                        write_cache_metadata(
                            meta_path,
                            ticker=ticker,
                            query_start=query_start,
                            requested_end=end_date,
                            combined=combined,
                            previous_metadata=metadata if cache_has_coverage else None,
                        )
                        fetched += 1
                except Exception as exc:
                    failures.append({"ticker": ticker, "error": str(exc)})
                    if cached is not None and not cached.empty:
                        reused += 1
                    else:
                        skipped += 1
                    print(f"  WARN {ticker}: {exc}")

                time.sleep(args.sleep)

            if index % 25 == 0 or index == len(tickers):
                print(f"  [{index}/{len(tickers)}] fetched={fetched} reused={reused} skipped={skipped} failures={len(failures)}")

    panel = load_panel_from_disk(args.output_root)
    if panel.empty:
        panel = pd.DataFrame(columns=CONTRACT_COLUMNS)
        date_min = date_max = None
        rows = tickers_with_data = 0
    else:
        atomic_write_parquet(panel, panel_path(args.output_root))
        date_min = panel["date"].min()
        date_max = panel["date"].max()
        rows = int(len(panel))
        tickers_with_data = int(panel["ticker"].nunique())

    write_manifest(
        args.output_root,
        {
            "source": SOURCE,
            "endpoint": URL,
            "fetched_at_utc": fetched_at_utc,
            "requested_start_date": start_date.isoformat(),
            "requested_end_date": end_date.isoformat(),
            "tickers_requested": len(tickers),
            "tickers_with_data": tickers_with_data,
            "rows": rows,
            "date_min": date_min,
            "date_max": date_max,
            "per_ticker_dir": str(per_ticker_dir(args.output_root)),
            "panel_path": str(panel_path(args.output_root)),
            "failures": failures,
        },
    )

    print(f"\nSaved {rows:,} rows -> {panel_path(args.output_root)}")
    print(f"Date range: {date_min} -> {date_max}")
    print(f"Tickers with data: {tickers_with_data}")
    if failures:
        print(f"Failures: {len(failures)}")


if __name__ == "__main__":
    main()
