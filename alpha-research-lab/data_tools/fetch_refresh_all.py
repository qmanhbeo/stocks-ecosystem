"""
Refresh all existing stock files with latest data (including 2026).

Uses the existing daily stock files as the ticker universe, then re-fetches
each ticker using vnstock VCI source at the requested interval.

Default behavior is incremental:
  - if a parquet already exists, fetch only the missing tail
  - merge on `time`
  - atomically replace the old file

Use `--full-refresh` to force a rewrite from the requested `--start/--end` window.

Usage:
    conda run -n stocks python data_tools/fetch_refresh_all.py
    conda run -n stocks python data_tools/fetch_refresh_all.py --interval 1H
    conda run -n stocks python data_tools/fetch_refresh_all.py --full-refresh
    conda run -n stocks python data_tools/fetch_refresh_all.py --dry-run
    conda run -n stocks python data_tools/fetch_refresh_all.py --skip-updated-since 2026-03-18T20:00
"""
import argparse
import socket
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from vnstock import Vnstock

from stock_refresh_utils import (
    atomic_write_parquet,
    combine_frames,
    load_existing_frame,
    plan_refresh,
)

# Hard timeout on all socket operations — prevents hanging on unresponsive tickers
socket.setdefaulttimeout(30)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR  = REPO_ROOT / "data" / "stock"
EXCLUDE   = {"VNINDEX", "VN30"}
UNIVERSE_INTERVAL = "1D"


def price_file_path(ticker: str, interval: str) -> Path:
    return DATA_DIR / f"gia_lich_su_{ticker}_{interval}.parquet"


def get_universe_tickers() -> list[str]:
    tickers = []
    for p in sorted(DATA_DIR.glob(f"gia_lich_su_*_{UNIVERSE_INTERVAL}.parquet")):
        t = p.stem.replace("gia_lich_su_", "").replace(f"_{UNIVERSE_INTERVAL}", "").upper()
        if t in EXCLUDE:
            continue
        tickers.append(t)
    return tickers


def get_existing_tickers(interval: str, skip_updated_since: datetime | None = None) -> list[str]:
    tickers = []
    for ticker in get_universe_tickers():
        if skip_updated_since is not None:
            target_path = price_file_path(ticker, interval)
            if not target_path.exists():
                tickers.append(ticker)
                continue
            mtime = datetime.fromtimestamp(target_path.stat().st_mtime)
            if mtime >= skip_updated_since:
                continue
        tickers.append(ticker)
    return tickers


def fetch_ticker(ticker: str, interval: str, start: str, end: str, *, full_refresh: bool) -> bool:
    fpath = price_file_path(ticker, interval)
    try:
        plan = plan_refresh(
            fpath,
            interval,
            start,
            end,
            full_refresh=full_refresh,
        )
        if plan.mode == "skip":
            print(f"  {ticker}: {plan.message}")
            return True

        stock = Vnstock().stock(symbol=ticker, source="VCI")
        df = stock.quote.history(start=plan.fetch_start, end=end, interval=interval)
        if len(df) == 0:
            if fpath.exists():
                print(f"  {ticker}: no new data returned ({plan.message}), keeping existing file")
                return True
            print(f"  {ticker}: no data returned")
            return False

        existing = load_existing_frame(fpath) if plan.mode == "incremental" else None
        before_rows = 0 if existing is None else len(existing)
        combined = combine_frames(existing, df)
        atomic_write_parquet(combined, fpath)

        new_rows_added = len(combined) - before_rows
        latest_time = pd.to_datetime(combined["time"], errors="coerce").dropna().max()
        if plan.mode == "incremental":
            if new_rows_added > 0:
                print(
                    f"  {ticker}: appended {new_rows_added} new rows "
                    f"(latest {latest_time})"
                )
            else:
                print(
                    f"  {ticker}: refreshed overlap window with no row-count change "
                    f"(latest {latest_time})"
                )
        else:
            print(f"  {ticker}: {len(combined)} rows saved")
        return True
    except Exception as e:
        err = str(e).encode("ascii", errors="replace").decode("ascii")
        print(f"  {ticker}: ERROR -- {err[:120]}")
        return False


def run_fetch_round(
    tickers: list[str],
    *,
    interval: str,
    start: str,
    end: str,
    delay: float,
    round_label: str,
    full_refresh: bool,
) -> tuple[list[str], list[str]]:
    success: list[str] = []
    failed: list[str] = []

    if not tickers:
        return success, failed

    print(f"\n{round_label} ({len(tickers)} tickers)")
    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}] ", end="", flush=True)
        ok = fetch_ticker(ticker, interval, start, end, full_refresh=full_refresh)
        (success if ok else failed).append(ticker)
        if i < len(tickers):
            time.sleep(delay)
    return success, failed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", default="1D",
                        help="Bar interval to fetch (default: 1D)")
    parser.add_argument("--start",   default="2000-01-01")
    parser.add_argument("--end",     default="2026-12-31")
    parser.add_argument("--delay",   type=float, default=0.3)
    parser.add_argument("--retry-rounds", type=int, default=2,
                        help="Automatic retry rounds for failed tickers after the initial pass (default: 2)")
    parser.add_argument("--retry-delay", type=float, default=1.0,
                        help="Delay between retry rounds in seconds (default: 1.0)")
    parser.add_argument("--skip-updated-since",
                        help="Skip files modified after this datetime (e.g. 2026-03-18T20:00)")
    parser.add_argument("--full-refresh", action="store_true",
                        help="Rewrite each parquet from the requested --start/--end window instead of incrementally appending")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    args.interval = args.interval.upper()

    skip_dt = None
    if args.skip_updated_since:
        skip_dt = datetime.fromisoformat(args.skip_updated_since)
    if args.retry_rounds < 0:
        raise ValueError("--retry-rounds must be non-negative")
    if args.retry_delay < 0:
        raise ValueError("--retry-delay must be non-negative")

    universe_tickers = get_universe_tickers()
    tickers = get_existing_tickers(args.interval, skip_updated_since=skip_dt)
    skipped = len(universe_tickers) - len(tickers)

    mode_label = "full refresh" if args.full_refresh else "incremental append"
    print(f"Refreshing {len(tickers)} tickers at {args.interval} ({args.start} to {args.end})")
    print(f"Ticker universe source: existing {UNIVERSE_INTERVAL} files ({len(universe_tickers)} names)")
    if skip_dt:
        print(f"Skipping {skipped} already updated since {skip_dt}")
    print(f"Mode: {mode_label}")
    print(f"Delay: {args.delay}s | Retry rounds: {args.retry_rounds} | Socket timeout: 30s")

    if args.dry_run:
        for ticker in tickers[:10]:
            plan = plan_refresh(
                price_file_path(ticker, args.interval),
                args.interval,
                args.start,
                args.end,
                full_refresh=args.full_refresh,
            )
            print(f"[DRY RUN] {ticker}: {plan.message}")
        return

    success: list[str] = []
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
            full_refresh=args.full_refresh,
        )
        success.extend(round_success)
        if not remaining:
            break
        if attempt < args.retry_rounds and args.retry_delay > 0:
            time.sleep(args.retry_delay)

    failed = remaining

    print(f"\n{'='*50}")
    print(f"Done: {len(success)} refreshed, {len(failed)} failed")
    if failed:
        print(f"Failed: {failed}")


if __name__ == "__main__":
    main()
