from pathlib import Path
from path_utils import data_path
import argparse
import time

import pandas as pd
from vnstock import Vnstock

from stock_refresh_utils import (
    atomic_write_parquet,
    build_probe_cache_entry,
    build_probe_cache_path,
    combine_frames,
    format_probe_cache_skip_message,
    load_existing_frame,
    load_probe_cache,
    plan_refresh,
    probe_cache_record_is_fresh,
    update_probe_cache_state,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = data_path("stock")
DATA_DIR.mkdir(parents=True, exist_ok=True)
PROBE_CACHE_STATUS_SKIP_ELIGIBLE = {"unchanged", "partial"}
DEFAULT_END = pd.Timestamp.today().normalize().date().isoformat()


def probe_cache_path(interval: str) -> Path:
    safe_interval = interval.upper().replace("/", "_")
    return build_probe_cache_path(DATA_DIR, f"fetch_stock_vci_{safe_interval}_probe_cache")


def probe_cache_metadata(interval: str) -> dict[str, object]:
    return {
        "tool": "fetch_stock",
        "source": "VCI",
        "interval": interval.upper(),
    }


def plan_ticker_refresh(
    ticker: str,
    time_interval: str,
    start: str,
    end: str,
    *,
    full_refresh: bool,
    probe_cache: dict[str, dict[str, object]] | None = None,
    probe_cache_ttl_hours: float = 24.0,
):
    if probe_cache is None:
        probe_cache = load_probe_cache(probe_cache_path(time_interval)) if probe_cache_ttl_hours > 0 else {}
    file_path = DATA_DIR / f"gia_lich_su_{ticker}_{time_interval}.parquet"
    plan = plan_refresh(
        file_path,
        time_interval,
        start,
        end,
        full_refresh=full_refresh,
    )
    if plan.mode != "incremental":
        return file_path, plan

    record = probe_cache.get(ticker)
    if probe_cache_record_is_fresh(
        record,
        requested_end=end,
        path=file_path,
        latest_value=plan.existing_last_time,
        ttl_hours=probe_cache_ttl_hours,
        eligible_statuses=PROBE_CACHE_STATUS_SKIP_ELIGIBLE,
    ):
        plan = type(plan)(
            mode="probe_skip",
            fetch_start=None,
            existing_last_time=plan.existing_last_time,
            message=format_probe_cache_skip_message(record),
        )
    return file_path, plan


def fetch_ticker(
    ticker,
    time_interval="1D",
    start="2000-01-01",
    end="2026-12-31",
    full_refresh=False,
    *,
    probe_cache=None,
    probe_cache_ttl_hours: float = 24.0,
):
    """Fetch data for a single ticker."""

    try:
        file_path, plan = plan_ticker_refresh(
            ticker,
            time_interval,
            start,
            end,
            full_refresh=full_refresh,
            probe_cache=probe_cache,
            probe_cache_ttl_hours=probe_cache_ttl_hours,
        )
        if plan.mode in {"skip", "probe_skip"}:
            print(f"⏭️  {ticker}: {plan.message}")
            return True, None

        print(f"📥 Fetching {ticker} ({plan.message})...", end=" ", flush=True)
        stock = Vnstock().stock(symbol=ticker, source="VCI")
        df = stock.quote.history(
            start=plan.fetch_start,
            end=end,
            interval=time_interval
        )

        if len(df) == 0:
            if file_path.exists():
                print("⏭️  No new data returned, keeping existing file")
                return True, build_probe_cache_entry(
                    status="unchanged",
                    checked_end=end,
                    path=file_path,
                    latest_value=plan.existing_last_time,
                )
            print(f"❌ No data returned")
            return False, None

        existing = load_existing_frame(file_path) if plan.mode == "incremental" else None
        before_rows = 0 if existing is None else len(existing)
        combined = combine_frames(existing, df)
        atomic_write_parquet(combined, file_path)
        latest_time = pd.to_datetime(combined["time"], errors="coerce").dropna().max()
        latest_date = None if pd.isna(latest_time) else latest_time.date()
        requested_end_date = pd.Timestamp(end).normalize().date()
        cache_status = "current"
        if latest_date is None or latest_date < requested_end_date:
            cache_status = "partial" if len(combined) - before_rows > 0 else "unchanged"
        cache_entry = build_probe_cache_entry(
            status=cache_status,
            checked_end=end,
            path=file_path,
            latest_value=None if pd.isna(latest_time) else latest_time,
        )
        if plan.mode == "incremental":
            added_rows = len(combined) - before_rows
            if added_rows > 0:
                print(f"✅ Appended {added_rows} new rows (latest {latest_time})")
            else:
                print(f"✅ Refreshed overlap window (latest {latest_time})")
        else:
            print(f"✅ Saved ({len(combined)} rows)")
        return True, cache_entry

    except Exception as e:
        print(f"❌ Error: {e}")
        return False, None


def run_fetch_round(
    tickers,
    *,
    interval,
    start,
    end,
    delay,
    round_label,
    full_refresh,
    probe_cache,
    probe_cache_ttl_hours,
    probe_cache_enabled,
):
    success = []
    failed = []

    if not tickers:
        return success, failed

    print(f"\n{round_label} ({len(tickers)} tickers)")
    for i, ticker in enumerate(tickers):
        success_flag, cache_entry = fetch_ticker(
            ticker,
            interval,
            start,
            end,
            full_refresh=full_refresh,
            probe_cache=probe_cache,
            probe_cache_ttl_hours=probe_cache_ttl_hours,
        )
        update_probe_cache_state(
            probe_cache_path(interval) if probe_cache_enabled else None,
            probe_cache,
            item_key=ticker,
            entry=cache_entry,
            metadata=probe_cache_metadata(interval),
        )
        if success_flag:
            success.append(ticker)
        else:
            failed.append(ticker)
        if i < len(tickers) - 1:
            time.sleep(delay)
    return success, failed


def main():
    parser = argparse.ArgumentParser(description="Fetch stock data from VCI")
    parser.add_argument(
        "--tickers",
        type=str,
        default="ACB",
        help="Comma-separated list of tickers (e.g., ACB,VNM,HPG)"
    )
    parser.add_argument(
        "--interval",
        type=str,
        default="1D",
        help="Time interval (default: 1D)"
    )
    parser.add_argument(
        "--start",
        type=str,
        default="2000-01-01",
        help="Start date (default: 2000-01-01)"
    )
    parser.add_argument(
        "--end",
        type=str,
        default=DEFAULT_END,
        help="End date (default: today)"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Rewrite the target files from the requested --start/--end window"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between requests in seconds (default: 1.0)"
    )
    parser.add_argument(
        "--retry-rounds",
        type=int,
        default=2,
        help="Automatic retry rounds for failed tickers after the initial pass (default: 2)"
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=1.0,
        help="Delay between retry rounds in seconds (default: 1.0)"
    )
    parser.add_argument(
        "--probe-cache-ttl-hours",
        type=float,
        default=24.0,
        help="Trust cached no-change/partial VCI probes for this many hours (default: 24; 0 disables)",
    )

    args = parser.parse_args()
    if args.retry_rounds < 0:
        raise ValueError("--retry-rounds must be non-negative")
    if args.retry_delay < 0:
        raise ValueError("--retry-delay must be non-negative")
    if args.probe_cache_ttl_hours < 0:
        raise ValueError("--probe-cache-ttl-hours must be non-negative")
    args.interval = args.interval.upper()
    probe_cache_enabled = args.probe_cache_ttl_hours > 0
    probe_cache = load_probe_cache(probe_cache_path(args.interval)) if probe_cache_enabled else {}
    
    # Parse tickers
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    
    print("="*60)
    print("Stock Data Fetcher")
    print("="*60)
    print(f"Tickers: {', '.join(tickers)}")
    print(f"Interval: {args.interval}")
    print(f"Period: {args.start} to {args.end}")
    print(f"Retry rounds: {args.retry_rounds}")
    print(f"Mode: {'full refresh' if args.overwrite else 'incremental append'}")
    print(f"Probe cache TTL: {args.probe_cache_ttl_hours}h")
    print(f"Output: {DATA_DIR}")
    print("="*60 + "\n")

    success_tickers = []
    remaining = list(tickers)
    for attempt in range(args.retry_rounds + 1):
        round_label = "Initial pass" if attempt == 0 else f"Retry round {attempt}/{args.retry_rounds}"
        round_success, remaining = run_fetch_round(
            remaining,
            interval=args.interval,
            start=args.start,
            end=args.end,
            delay=args.delay,
            round_label=round_label,
            full_refresh=args.overwrite,
            probe_cache=probe_cache,
            probe_cache_ttl_hours=args.probe_cache_ttl_hours,
            probe_cache_enabled=probe_cache_enabled,
        )
        success_tickers.extend(round_success)
        if not remaining:
            break
        if attempt < args.retry_rounds and args.retry_delay > 0:
            time.sleep(args.retry_delay)

    success_count = len(success_tickers)
    failed_tickers = remaining
    
    # Summary
    print("\n" + "="*60)
    print("Summary")
    print("="*60)
    print(f"✅ Successfully fetched: {success_count}/{len(tickers)}")
    if failed_tickers:
        print(f"❌ Failed: {', '.join(failed_tickers)}")
    print("="*60)


if __name__ == "__main__":
    main()
