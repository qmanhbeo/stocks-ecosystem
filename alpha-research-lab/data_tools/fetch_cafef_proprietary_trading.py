"""
Fetch historical daily proprietary-trading data from CafeF's GDTuDoanh endpoint.

CafeF's public stock history page exposes "Tu doanh" through:
    https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDTuDoanh.ashx

Builds:
    data/proprietary_trading/cafef/per_ticker/<TICKER>.parquet
    data/proprietary_trading/cafef/proprietary_trading_daily.parquet
    data/proprietary_trading/cafef/manifest.json
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import date
from pathlib import Path

import pandas as pd

try:
    from cafef_history_common import (
        atomic_write_parquet,
        build_session,
        cache_covers_requested_window,
        cache_path,
        combine_frames,
        default_query_start,
        fetch_page_rows,
        load_cache_metadata,
        load_cached_frame,
        load_default_tickers,
        manifest_path,
        metadata_path,
        panel_path,
        parse_iso_date,
        parse_tickers,
        per_ticker_dir,
        utc_now_iso,
        write_cache_metadata,
        write_run_manifest,
        write_panel_from_disk,
    )
except ModuleNotFoundError:
    from data_tools.cafef_history_common import (
        atomic_write_parquet,
        build_session,
        cache_covers_requested_window,
        cache_path,
        combine_frames,
        default_query_start,
        fetch_page_rows,
        load_cache_metadata,
        load_cached_frame,
        load_default_tickers,
        manifest_path,
        metadata_path,
        panel_path,
        parse_iso_date,
        parse_tickers,
        per_ticker_dir,
        utc_now_iso,
        write_cache_metadata,
        write_run_manifest,
        write_panel_from_disk,
    )
from path_utils import data_path


URL = "https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDTuDoanh.ashx"
SOURCE = "cafef_gdtudoanh"
DEFAULT_START_DATE = "2000-01-01"
DEFAULT_END_DATE = date.today().isoformat()
DEFAULT_OUTPUT_ROOT = data_path("proprietary_trading/cafef")
CONTRACT_COLUMNS = [
    "ticker",
    "date",
    "source",
    "proprietary_buy_volume",
    "proprietary_sell_volume",
    "proprietary_net_volume",
    "proprietary_buy_value",
    "proprietary_sell_value",
    "proprietary_net_value",
]
CONTRACT_NOTES = [
    "Raw historical CafeF proprietary-trading surface from the GDTuDoanh endpoint.",
    "This is a raw source surface, not a published research feature contract.",
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
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop immediately on the first ticker failure instead of recording it and continuing.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print plan without fetching or writing.")
    return parser.parse_args()


def normalize_payload_rows(rows: list[dict[str, object]], ticker: str) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=CONTRACT_COLUMNS)

    frame = pd.DataFrame(rows)
    out = pd.DataFrame(index=frame.index)
    out["ticker"] = ticker.upper()
    out["date"] = pd.to_datetime(frame.get("Date"), format="%d/%m/%Y", errors="coerce")
    out["source"] = SOURCE
    out["proprietary_buy_volume"] = pd.to_numeric(frame.get("KLcpMua"), errors="coerce")
    out["proprietary_sell_volume"] = pd.to_numeric(frame.get("KlcpBan"), errors="coerce")
    out["proprietary_buy_value"] = pd.to_numeric(frame.get("GtMua"), errors="coerce")
    out["proprietary_sell_value"] = pd.to_numeric(frame.get("GtBan"), errors="coerce")
    out["proprietary_net_volume"] = out["proprietary_buy_volume"] - out["proprietary_sell_volume"]
    out["proprietary_net_value"] = out["proprietary_buy_value"] - out["proprietary_sell_value"]

    out = out.dropna(subset=["date"]).sort_values("date").drop_duplicates(["ticker", "date"], keep="last")
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    return out[CONTRACT_COLUMNS].reset_index(drop=True)


def _extract_rows(payload: dict[str, object]) -> list[dict[str, object]]:
    data = (payload.get("Data") or {}).get("Data") or {}
    if not isinstance(data, dict):
        return []
    rows = data.get("ListDataTudoanh") or []
    return rows if isinstance(rows, list) else []


def _extract_total_count(payload: dict[str, object]) -> int:
    return int(((payload.get("Data") or {}).get("TotalCount")) or 0)


def fetch_ticker(
    ticker: str,
    *,
    start_date: date,
    end_date: date,
    page_size: int,
    max_pages: int,
    timeout: float,
    retries: int,
) -> pd.DataFrame:
    session = build_session(referer=f"https://cafef.vn/du-lieu/lich-su-giao-dich-{ticker.lower()}-4.chn")
    rows = fetch_page_rows(
        session,
        url=URL,
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        page_size=page_size,
        max_pages=max_pages,
        timeout=timeout,
        retries=retries,
        extract_rows=_extract_rows,
        extract_total_count=_extract_total_count,
    )
    return normalize_payload_rows(rows, ticker)


def main() -> None:
    args = parse_args()
    start_date = parse_iso_date(args.start_date)
    end_date = parse_iso_date(args.end_date)
    if start_date > end_date:
        raise ValueError("--start-date must be on or before --end-date")
    if args.lookback_days < 0:
        raise ValueError("--lookback-days must be non-negative")

    tickers = parse_tickers(args.tickers) or load_default_tickers()
    if args.max_tickers:
        tickers = tickers[: args.max_tickers]
    if not tickers:
        raise RuntimeError("No tickers resolved for CafeF proprietary-trading fetch")

    output_root = Path(args.output_root)
    per_ticker_dir(output_root).mkdir(parents=True, exist_ok=True)

    print("CafeF proprietary-trading fetch")
    print("=" * 72)
    print(f"tickers       : {len(tickers)}")
    print(f"date range    : {start_date} -> {end_date}")
    print(f"output root   : {output_root}")
    print(f"force         : {args.force}")
    print(f"dry run       : {args.dry_run}")

    started_at_utc = utc_now_iso()
    last_run: list[dict[str, object]] = []
    fetched_count = 0
    cached_count = 0
    failed_count = 0
    active_ticker: str | None = None

    if not args.dry_run:
        write_run_manifest(
            output_root=output_root,
            source=SOURCE,
            panel_filename="proprietary_trading_daily.parquet",
            contract_columns=CONTRACT_COLUMNS,
            contract_notes=CONTRACT_NOTES,
            started_at_utc=started_at_utc,
            requested_start_date=start_date,
            requested_end_date=end_date,
            tickers_requested=len(tickers),
            tickers_processed=0,
            tickers_fetched=0,
            tickers_cached=0,
            tickers_failed=0,
            status="running",
            items=last_run,
        )

    try:
        for index, ticker in enumerate(tickers, start=1):
            active_ticker = ticker
            ticker_cache_path = cache_path(output_root, ticker)
            ticker_meta_path = metadata_path(output_root, ticker)
            cached_frame = load_cached_frame(ticker_cache_path)
            cached_meta = load_cache_metadata(ticker_meta_path)
            query_start = default_query_start(
                force=args.force,
                cached_frame=cached_frame,
                requested_start=start_date,
                requested_end=end_date,
                lookback_days=args.lookback_days,
            )
            progress_status = "running"
            if not args.dry_run:
                write_run_manifest(
                    output_root=output_root,
                    source=SOURCE,
                    panel_filename="proprietary_trading_daily.parquet",
                    contract_columns=CONTRACT_COLUMNS,
                    contract_notes=CONTRACT_NOTES,
                    started_at_utc=started_at_utc,
                    requested_start_date=start_date,
                    requested_end_date=end_date,
                    tickers_requested=len(tickers),
                    tickers_processed=len(last_run),
                    tickers_fetched=fetched_count,
                    tickers_cached=cached_count,
                    tickers_failed=failed_count,
                    status="running",
                    items=last_run,
                    current_ticker=ticker,
                )
            try:
                if not args.force and cache_covers_requested_window(cached_meta, start_date, end_date):
                    print(f"[{index}/{len(tickers)}] {ticker}: cached window already covers requested range")
                    cached_count += 1
                    last_run.append(
                        {
                            "ticker": ticker,
                            "status": "cached",
                            "rows": int(len(cached_frame)) if cached_frame is not None else 0,
                        }
                    )
                    continue

                if args.dry_run:
                    print(f"[{index}/{len(tickers)}] {ticker}: would fetch {query_start} -> {end_date}")
                    last_run.append({"ticker": ticker, "status": "planned", "query_start": query_start.isoformat()})
                    continue

                print(f"[{index}/{len(tickers)}] {ticker}: fetching {query_start} -> {end_date}")
                incoming = fetch_ticker(
                    ticker,
                    start_date=query_start,
                    end_date=end_date,
                    page_size=args.page_size,
                    max_pages=args.max_pages,
                    timeout=args.timeout,
                    retries=args.retries,
                )
                combined = combine_frames(cached_frame, incoming, CONTRACT_COLUMNS)
                atomic_write_parquet(combined, ticker_cache_path)
                write_cache_metadata(
                    ticker_meta_path,
                    ticker=ticker,
                    source=SOURCE,
                    query_start=query_start,
                    requested_end=end_date,
                    combined=combined,
                    previous_metadata=cached_meta,
                )
                fetched_count += 1
                last_run.append(
                    {
                        "ticker": ticker,
                        "status": "fetched",
                        "query_start": query_start.isoformat(),
                        "rows": int(len(combined)),
                    }
                )
                time.sleep(args.sleep)
            except Exception as exc:
                failed_count += 1
                print(f"[{index}/{len(tickers)}] {ticker}: FAILED ({exc})")
                last_run.append(
                    {
                        "ticker": ticker,
                        "status": "failed",
                        "query_start": query_start.isoformat(),
                        "error": str(exc),
                    }
                )
                if args.fail_fast:
                    progress_status = "failed"
                    raise
            finally:
                if not args.dry_run:
                    write_run_manifest(
                        output_root=output_root,
                        source=SOURCE,
                        panel_filename="proprietary_trading_daily.parquet",
                        contract_columns=CONTRACT_COLUMNS,
                        contract_notes=CONTRACT_NOTES,
                        started_at_utc=started_at_utc,
                        requested_start_date=start_date,
                        requested_end_date=end_date,
                        tickers_requested=len(tickers),
                        tickers_processed=len(last_run),
                        tickers_fetched=fetched_count,
                        tickers_cached=cached_count,
                        tickers_failed=failed_count,
                        status=progress_status,
                        items=last_run,
                        current_ticker=ticker if progress_status != "running" else None,
                    )
            active_ticker = None
    except KeyboardInterrupt:
        if not args.dry_run:
            write_run_manifest(
                output_root=output_root,
                source=SOURCE,
                panel_filename="proprietary_trading_daily.parquet",
                contract_columns=CONTRACT_COLUMNS,
                contract_notes=CONTRACT_NOTES,
                started_at_utc=started_at_utc,
                requested_start_date=start_date,
                requested_end_date=end_date,
                tickers_requested=len(tickers),
                tickers_processed=len(last_run),
                tickers_fetched=fetched_count,
                tickers_cached=cached_count,
                tickers_failed=failed_count,
                status="interrupted",
                items=last_run,
                current_ticker=active_ticker,
            )
        raise

    if args.dry_run:
        return

    panel = write_panel_from_disk(
        output_root=output_root,
        contract_columns=CONTRACT_COLUMNS,
        panel_filename="proprietary_trading_daily.parquet",
    )
    write_run_manifest(
        output_root=output_root,
        source=SOURCE,
        panel_filename="proprietary_trading_daily.parquet",
        contract_columns=CONTRACT_COLUMNS,
        contract_notes=CONTRACT_NOTES,
        started_at_utc=started_at_utc,
        requested_start_date=start_date,
        requested_end_date=end_date,
        tickers_requested=len(tickers),
        tickers_processed=len(last_run),
        tickers_fetched=fetched_count,
        tickers_cached=cached_count,
        tickers_failed=failed_count,
        status="completed_with_errors" if failed_count else "completed",
        items=last_run,
        panel=panel,
    )
    print(f"panel rows     : {len(panel)}")
    print(f"panel path     : {panel_path(output_root, 'proprietary_trading_daily.parquet')}")


if __name__ == "__main__":
    main()
