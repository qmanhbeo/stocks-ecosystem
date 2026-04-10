"""
Fetch historical daily order-statistics data from CafeF's ThongKeDL endpoint.

CafeF's public stock history page exposes "Thong ke dat lenh" through:
    https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/ThongKeDL.ashx

Builds:
    data/order_stats/cafef/per_ticker/<TICKER>.parquet
    data/order_stats/cafef/order_stats_daily.parquet
    data/order_stats/cafef/manifest.json
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
        path_for_json,
        per_ticker_dir,
        utc_now_iso,
        write_cache_metadata,
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
        path_for_json,
        per_ticker_dir,
        utc_now_iso,
        write_cache_metadata,
        write_panel_from_disk,
    )
from path_utils import data_path


URL = "https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/ThongKeDL.ashx"
SOURCE = "cafef_thongkedatlenh"
DEFAULT_START_DATE = "2000-01-01"
DEFAULT_END_DATE = date.today().isoformat()
DEFAULT_OUTPUT_ROOT = data_path("order_stats/cafef")
CONTRACT_COLUMNS = [
    "ticker",
    "date",
    "source",
    "price_change_raw",
    "buy_order_count",
    "buy_order_volume",
    "avg_buy_order_volume",
    "sell_order_count",
    "sell_order_volume",
    "avg_sell_order_volume",
    "buy_sell_volume_imbalance",
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


def _parse_int_like(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not pd.isna(value):
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(".", "").replace(",", "").replace(" ", "")
    if text in {"-", "--"}:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def normalize_payload_rows(rows: list[dict[str, object]], ticker: str) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=CONTRACT_COLUMNS)

    frame = pd.DataFrame(rows)
    out = pd.DataFrame(index=frame.index)
    out["ticker"] = ticker.upper()
    out["date"] = pd.to_datetime(frame.get("Date"), format="%d/%m/%Y", errors="coerce")
    out["source"] = SOURCE
    out["price_change_raw"] = frame.get("ThayDoi")
    out["buy_order_count"] = frame.get("SoLenhMua").map(_parse_int_like)
    out["buy_order_volume"] = frame.get("KLDatMua").map(_parse_int_like)
    out["avg_buy_order_volume"] = frame.get("KLTB1LenhMua").map(_parse_int_like)
    out["sell_order_count"] = frame.get("SoLenhDatBan").map(_parse_int_like)
    out["sell_order_volume"] = frame.get("KLDatBan").map(_parse_int_like)
    out["avg_sell_order_volume"] = frame.get("KLTB1LenhBan").map(_parse_int_like)
    out["buy_sell_volume_imbalance"] = frame.get("ChenhLechKL").map(_parse_int_like)

    out = out.dropna(subset=["date"]).sort_values("date").drop_duplicates(["ticker", "date"], keep="last")
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    return out[CONTRACT_COLUMNS].reset_index(drop=True)


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
    session = build_session(referer=f"https://cafef.vn/du-lieu/lich-su-giao-dich-{ticker.lower()}-2.chn")
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
        extract_rows=lambda payload: ((payload.get("Data") or {}).get("Data")) or [],
        extract_total_count=lambda payload: ((payload.get("Data") or {}).get("TotalCount")) or 0,
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
        raise RuntimeError("No tickers resolved for CafeF order-stats fetch")

    output_root = Path(args.output_root)
    per_ticker_dir(output_root).mkdir(parents=True, exist_ok=True)

    print("CafeF order-statistics fetch")
    print("=" * 72)
    print(f"tickers       : {len(tickers)}")
    print(f"date range    : {start_date} -> {end_date}")
    print(f"output root   : {output_root}")
    print(f"force         : {args.force}")
    print(f"dry run       : {args.dry_run}")

    last_run: list[dict[str, object]] = []
    fetched_count = 0

    for index, ticker in enumerate(tickers, start=1):
        ticker_cache_path = cache_path(output_root, ticker)
        ticker_meta_path = metadata_path(output_root, ticker)
        cached_frame = load_cached_frame(ticker_cache_path)
        cached_meta = load_cache_metadata(ticker_meta_path)
        if not args.force and cache_covers_requested_window(cached_meta, start_date, end_date):
            print(f"[{index}/{len(tickers)}] {ticker}: cached window already covers requested range")
            last_run.append({"ticker": ticker, "status": "cached", "rows": int(len(cached_frame or []))})
            continue

        query_start = default_query_start(
            force=args.force,
            cached_frame=cached_frame,
            requested_start=start_date,
            requested_end=end_date,
            lookback_days=args.lookback_days,
        )
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

    if args.dry_run:
        return

    panel = write_panel_from_disk(
        output_root=output_root,
        contract_columns=CONTRACT_COLUMNS,
        panel_filename="order_stats_daily.parquet",
    )
    manifest_payload = {
        "contract": {
            "source": SOURCE,
            "root": path_for_json(output_root),
            "per_ticker_dir": path_for_json(per_ticker_dir(output_root)),
            "panel": path_for_json(panel_path(output_root, "order_stats_daily.parquet")),
            "primary_key": ["ticker", "date"],
            "contract_columns": CONTRACT_COLUMNS,
            "notes": [
                "Raw historical CafeF order-statistics surface from the ThongKeDL endpoint.",
                "This is a raw source surface, not a published research feature contract.",
            ],
        },
        "last_run": {
            "fetched_at_utc": utc_now_iso(),
            "requested_start_date": start_date.isoformat(),
            "requested_end_date": end_date.isoformat(),
            "tickers_requested": int(len(tickers)),
            "tickers_fetched": int(fetched_count),
            "panel_rows": int(len(panel)),
            "panel_tickers": int(panel["ticker"].nunique()) if not panel.empty else 0,
            "items": last_run,
        },
    }
    manifest_path(output_root).write_text(
        json.dumps(manifest_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"panel rows     : {len(panel)}")
    print(f"panel path     : {panel_path(output_root, 'order_stats_daily.parquet')}")


if __name__ == "__main__":
    main()
