"""
Fetch insider + large-shareholder transaction disclosures for all HOSE tickers
from CafeF's GDCoDong endpoint.

Default behavior is safe and incremental:
  - load the existing per-ticker cache if present
  - if the cache already reaches the requested end date, reuse it
  - otherwise refetch only a bounded lookback window and merge/dedupe into cache
  - atomically replace both per-ticker cache files and the combined feature file

Use --force to refetch the full requested window for every ticker.

Builds: data/insider_cache/<TICKER>.parquet  (raw per-ticker)
        data/features/xs_insider_deals_raw.parquet  (combined, deduped)
"""

from __future__ import annotations

import argparse
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from path_utils import data_path

import pandas as pd
import requests

try:
    from stock_refresh_utils import (
        atomic_write_parquet,
        build_probe_cache_entry,
        build_probe_cache_path,
        format_probe_cache_skip_message,
        load_probe_cache,
        probe_cache_record_is_fresh,
        update_probe_cache_state,
    )
except ModuleNotFoundError:
    from data_tools.stock_refresh_utils import (
        atomic_write_parquet,
        build_probe_cache_entry,
        build_probe_cache_path,
        format_probe_cache_skip_message,
        load_probe_cache,
        probe_cache_record_is_fresh,
        update_probe_cache_state,
    )


REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = data_path("insider_cache")
OUT_PATH = data_path("features/xs_insider_deals_raw.parquet")
FEAT_SRC = data_path("features/xs_barrier_vol_1d_hose_full.parquet")

URL = "https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDCoDong.ashx"
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://cafef.vn/"}
PAGE_SIZE = 500
DEFAULT_START_DATE = "2010-01-01"
DEFAULT_END_DATE = datetime.today().date().isoformat()
DEFAULT_LOOKBACK_DAYS = 30
SLEEP = 0.2
PROBE_CACHE_STATUS_SKIP_ELIGIBLE = {"unchanged", "partial"}


def parse_ms_date(ms_str) -> str | None:
    if not isinstance(ms_str, str):
        return None
    match = re.search(r"(\d+)", ms_str)
    if match:
        return datetime.fromtimestamp(int(match.group(1)) / 1000).strftime("%Y-%m-%d")
    return None


def parse_iso_date(value: str) -> datetime.date:
    return datetime.fromisoformat(value).date()


def format_query_date(value: datetime.date) -> str:
    return value.strftime("%m/%d/%Y")


def load_cached_frame(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        frame = pd.read_parquet(path)
    except Exception as exc:
        print(f"  WARN {path.name}: unreadable cache, refetching ({exc})")
        return None
    return frame


def normalize_disclosures(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    frame = df.copy()
    frame["ticker"] = symbol

    for source_column, target_column in [
        ("PublishedDate", "published_date"),
        ("OrderDate", "order_date"),
        ("RealEndDate", "real_end_date"),
    ]:
        if source_column in frame.columns:
            frame[target_column] = frame[source_column].apply(parse_ms_date)
        elif target_column not in frame.columns:
            frame[target_column] = None

    code = frame.get("ShareHolderCode", pd.Series("", index=frame.index)).fillna("").astype(str)
    frame["is_insider"] = code.str.startswith("CEO_") | code.str.startswith("LQ_")
    frame["net_plan_vol"] = pd.to_numeric(frame.get("PlanBuyVolume"), errors="coerce").fillna(0) - pd.to_numeric(
        frame.get("PlanSellVolume"), errors="coerce"
    ).fillna(0)
    frame["net_real_vol"] = pd.to_numeric(frame.get("RealBuyVolume"), errors="coerce").fillna(0) - pd.to_numeric(
        frame.get("RealSellVolume"), errors="coerce"
    ).fillna(0)

    keep = [
        "ticker",
        "published_date",
        "order_date",
        "real_end_date",
        "TransactionMan",
        "RelatedManPosition",
        "TransactionManPosition",
        "ShareHolderCode",
        "is_insider",
        "net_plan_vol",
        "net_real_vol",
        "PlanBuyVolume",
        "PlanSellVolume",
        "RealBuyVolume",
        "RealSellVolume",
        "VolumeBeforeTransaction",
        "VolumeAfterTransaction",
    ]
    keep = [column for column in keep if column in frame.columns]
    frame = frame[keep].copy()
    frame["published_date"] = pd.to_datetime(frame["published_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    frame["order_date"] = pd.to_datetime(frame["order_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    frame["real_end_date"] = pd.to_datetime(frame["real_end_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return frame


def combine_disclosures(existing: pd.DataFrame | None, incoming: pd.DataFrame) -> pd.DataFrame:
    if existing is None or existing.empty:
        combined = incoming.copy()
    elif incoming.empty:
        combined = existing.copy()
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
    if combined.empty:
        return combined

    combined["published_date"] = pd.to_datetime(combined["published_date"], errors="coerce")
    if "order_date" in combined.columns:
        combined["order_date"] = pd.to_datetime(combined["order_date"], errors="coerce")
    if "real_end_date" in combined.columns:
        combined["real_end_date"] = pd.to_datetime(combined["real_end_date"], errors="coerce")
    combined = combined.drop_duplicates(keep="last")
    combined = combined.sort_values(["published_date", "ticker"]).reset_index(drop=True)
    combined["published_date"] = combined["published_date"].dt.strftime("%Y-%m-%d")
    if "order_date" in combined.columns:
        combined["order_date"] = combined["order_date"].dt.strftime("%Y-%m-%d")
    if "real_end_date" in combined.columns:
        combined["real_end_date"] = combined["real_end_date"].dt.strftime("%Y-%m-%d")
    return combined


def latest_cached_published_date(frame: pd.DataFrame | None) -> datetime.date | None:
    if frame is None or frame.empty or "published_date" not in frame.columns:
        return None
    published = pd.to_datetime(frame["published_date"], errors="coerce").dropna()
    if published.empty:
        return None
    return published.max().date()


def probe_cache_path() -> Path:
    return build_probe_cache_path(CACHE_DIR, "fetch_insider_deals_probe_cache")


def probe_cache_metadata() -> dict[str, object]:
    return {
        "tool": "fetch_insider_deals",
        "source": "CafeF GDCoDong",
    }


def fetch_ticker(symbol: str, start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
    rows = []
    page = 1
    while True:
        params = {
            "Symbol": symbol,
            "StartDate": format_query_date(start_date),
            "EndDate": format_query_date(end_date),
            "PageIndex": page,
            "PageSize": PAGE_SIZE,
        }
        response = requests.get(URL, params=params, headers=HEADERS, timeout=15)
        response.raise_for_status()
        payload = response.json()
        chunk = (((payload.get("Data") or {}).get("Data")) or [])
        total = int(((payload.get("Data") or {}).get("TotalCount")) or 0)
        rows.extend(chunk)
        if len(rows) >= total or not chunk:
            break
        page += 1
    return normalize_disclosures(pd.DataFrame(rows), symbol)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Refetch the full requested window for every ticker")
    parser.add_argument("--start-date", default=DEFAULT_START_DATE, help="Inclusive start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", default=DEFAULT_END_DATE, help="Inclusive end date (YYYY-MM-DD)")
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=DEFAULT_LOOKBACK_DAYS,
        help="When a cache exists, refetch this many days before the latest cached published_date",
    )
    parser.add_argument(
        "--probe-cache-ttl-hours",
        type=float,
        default=24.0,
        help="Trust cached no-change/partial probes for this many hours (default: 24; 0 disables)",
    )
    args = parser.parse_args()
    if args.lookback_days < 0:
        raise ValueError("--lookback-days must be non-negative")
    if args.probe_cache_ttl_hours < 0:
        raise ValueError("--probe-cache-ttl-hours must be non-negative")

    start_date = parse_iso_date(args.start_date)
    end_date = parse_iso_date(args.end_date)
    if start_date > end_date:
        raise ValueError("--start-date must be on or before --end-date")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    probe_cache_enabled = args.probe_cache_ttl_hours > 0
    probe_cache = load_probe_cache(probe_cache_path()) if probe_cache_enabled else {}

    feat = pd.read_parquet(FEAT_SRC)
    tickers = sorted(feat["ticker"].dropna().astype(str).str.upper().unique())
    print(f"Universe: {len(tickers)} tickers")
    print(f"Probe cache TTL: {args.probe_cache_ttl_hours}h")

    all_dfs: list[pd.DataFrame] = []
    reused = fetched = skipped = probe_cached = 0

    for index, symbol in enumerate(tickers, start=1):
        cache_file = CACHE_DIR / f"{symbol}.parquet"
        cached = load_cached_frame(cache_file)
        latest_cached = latest_cached_published_date(cached)

        if not args.force and latest_cached is not None and latest_cached >= end_date:
            all_dfs.append(cached)
            reused += 1
            if index % 50 == 0 or index == len(tickers):
                print(f"  [{index}/{len(tickers)}] reused={reused} fetched={fetched} skipped={skipped}")
            continue

        if (
            not args.force
            and cached is not None
            and latest_cached is not None
            and probe_cache_record_is_fresh(
                probe_cache.get(symbol),
                requested_end=end_date.isoformat(),
                path=cache_file,
                latest_value=latest_cached,
                ttl_hours=args.probe_cache_ttl_hours,
                eligible_statuses=PROBE_CACHE_STATUS_SKIP_ELIGIBLE,
            )
        ):
            all_dfs.append(cached)
            probe_cached += 1
            print(f"  [{index}/{len(tickers)}] {symbol}: {format_probe_cache_skip_message(probe_cache[symbol])}")
            continue

        query_start = start_date
        if not args.force and latest_cached is not None:
            query_start = max(start_date, latest_cached - timedelta(days=args.lookback_days))

        try:
            incoming = fetch_ticker(symbol, query_start, end_date)
        except Exception as exc:
            print(f"  WARN {symbol}: {exc}")
            if cached is not None:
                all_dfs.append(cached)
                reused += 1
            else:
                skipped += 1
            if index % 20 == 0 or index == len(tickers):
                print(
                    f"  [{index}/{len(tickers)}] reused={reused} probe_cached={probe_cached} "
                    f"fetched={fetched} skipped={skipped}"
                )
            time.sleep(SLEEP)
            continue

        if incoming.empty and cached is None:
            skipped += 1
            if index % 20 == 0 or index == len(tickers):
                print(
                    f"  [{index}/{len(tickers)}] reused={reused} probe_cached={probe_cached} "
                    f"fetched={fetched} skipped={skipped}"
                )
            time.sleep(SLEEP)
            continue

        combined = combine_disclosures(cached, incoming)
        atomic_write_parquet(combined, cache_file)
        all_dfs.append(combined)
        fetched += 1
        combined_latest = latest_cached_published_date(combined)
        cache_status = "current"
        if combined_latest is None or combined_latest < end_date:
            had_new_rows = False
            if cached is None:
                had_new_rows = not combined.empty
            else:
                had_new_rows = len(combined) > len(cached) or (
                    latest_cached is not None and combined_latest is not None and combined_latest > latest_cached
                )
            cache_status = "partial" if had_new_rows else "unchanged"
        update_probe_cache_state(
            probe_cache_path() if probe_cache_enabled else None,
            probe_cache,
            item_key=symbol,
            entry=build_probe_cache_entry(
                status=cache_status,
                checked_end=end_date.isoformat(),
                path=cache_file,
                latest_value=combined_latest,
            ),
            metadata=probe_cache_metadata(),
        )

        if index % 20 == 0 or index == len(tickers):
            print(
                f"  [{index}/{len(tickers)}] reused={reused} probe_cached={probe_cached} "
                f"fetched={fetched} skipped={skipped}"
            )
        time.sleep(SLEEP)

    print(f"\nDone: {reused} reused, {probe_cached} probe-cached, {fetched} refreshed, {skipped} skipped")

    if not all_dfs:
        print("No data available — exiting.")
        return

    combined = pd.concat(all_dfs, ignore_index=True)
    combined = combined[combined["published_date"].notna()]
    combined["published_date"] = pd.to_datetime(combined["published_date"], errors="coerce")
    combined = combined.dropna(subset=["published_date"])
    combined = combined.sort_values(["published_date", "ticker"]).drop_duplicates(keep="last").reset_index(drop=True)
    combined["published_date"] = combined["published_date"].dt.strftime("%Y-%m-%d")

    atomic_write_parquet(combined, OUT_PATH)
    print(f"\nSaved {len(combined):,} rows -> {OUT_PATH}")
    print(f"Date range: {combined['published_date'].min()} -> {combined['published_date'].max()}")
    print(f"Tickers with data: {combined['ticker'].nunique()}")
    print(f"Insider-only rows: {int(combined['is_insider'].sum()):,} / {len(combined):,}")


if __name__ == "__main__":
    main()
