from pathlib import Path
import argparse
import time

import pandas as pd
from vnstock import Vnstock

from stock_refresh_utils import (
    atomic_write_parquet,
    combine_frames,
    load_existing_frame,
    plan_refresh,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data" / "stock"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def fetch_ticker(ticker, time_interval="1D", start="2000-01-01", end="2026-12-31", full_refresh=False):
    """Fetch data for a single ticker."""

    file_path = DATA_DIR / f"gia_lich_su_{ticker}_{time_interval}.parquet"

    try:
        plan = plan_refresh(
            file_path,
            time_interval,
            start,
            end,
            full_refresh=full_refresh,
        )
        if plan.mode == "skip":
            print(f"⏭️  {ticker}: {plan.message}")
            return True

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
                return True
            print(f"❌ No data returned")
            return False

        existing = load_existing_frame(file_path) if plan.mode == "incremental" else None
        before_rows = 0 if existing is None else len(existing)
        combined = combine_frames(existing, df)
        atomic_write_parquet(combined, file_path)
        latest_time = pd.to_datetime(combined["time"], errors="coerce").dropna().max()
        if plan.mode == "incremental":
            added_rows = len(combined) - before_rows
            if added_rows > 0:
                print(f"✅ Appended {added_rows} new rows (latest {latest_time})")
            else:
                print(f"✅ Refreshed overlap window (latest {latest_time})")
        else:
            print(f"✅ Saved ({len(combined)} rows)")
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def run_fetch_round(tickers, *, interval, start, end, delay, round_label, full_refresh):
    success = []
    failed = []

    if not tickers:
        return success, failed

    print(f"\n{round_label} ({len(tickers)} tickers)")
    for i, ticker in enumerate(tickers):
        success_flag = fetch_ticker(ticker, interval, start, end, full_refresh=full_refresh)
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
        default="2026-12-31",
        help="End date (default: 2026-12-31)"
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

    args = parser.parse_args()
    if args.retry_rounds < 0:
        raise ValueError("--retry-rounds must be non-negative")
    if args.retry_delay < 0:
        raise ValueError("--retry-delay must be non-negative")
    args.interval = args.interval.upper()
    
    # Parse tickers
    tickers = [t.strip().upper() for t in args.tickers.split(",")]
    
    print("="*60)
    print("Stock Data Fetcher")
    print("="*60)
    print(f"Tickers: {', '.join(tickers)}")
    print(f"Interval: {args.interval}")
    print(f"Period: {args.start} to {args.end}")
    print(f"Retry rounds: {args.retry_rounds}")
    print(f"Mode: {'full refresh' if args.overwrite else 'incremental append'}")
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
