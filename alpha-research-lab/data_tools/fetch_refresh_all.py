"""
Refresh all existing stock files with the latest available data.

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
    conda run -n stocks python data_tools/fetch_refresh_all.py --workers 2 --delay 0.5
    conda run -n stocks python data_tools/fetch_refresh_all.py --full-refresh
    conda run -n stocks python data_tools/fetch_refresh_all.py --dry-run
    conda run -n stocks python data_tools/fetch_refresh_all.py --skip-updated-since 2026-03-18T20:00
"""
import argparse
import concurrent.futures as cf
import socket
import time
from datetime import datetime
from pathlib import Path
from path_utils import data_path
import os

import pandas as pd
from vnstock import Vnstock

from stock_refresh_utils import (
    RefreshPlan,
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

# Hard timeout on all socket operations — prevents hanging on unresponsive tickers
socket.setdefaulttimeout(30)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR  = data_path("stock")
EXCLUDE   = {"VNINDEX", "VN30"}
UNIVERSE_INTERVAL = "1D"
PROBE_CACHE_STATUS_SKIP_ELIGIBLE = {"unchanged", "partial"}
DEFAULT_END = pd.Timestamp.today().normalize().date().isoformat()


def price_file_path(ticker: str, interval: str) -> Path:
    return DATA_DIR / f"gia_lich_su_{ticker}_{interval}.parquet"


def probe_cache_path(interval: str) -> Path:
    safe_interval = interval.upper().replace("/", "_")
    return build_probe_cache_path(DATA_DIR, f"fetch_refresh_all_vci_{safe_interval}_probe_cache")


def probe_cache_metadata(interval: str) -> dict[str, object]:
    return {
        "tool": "fetch_refresh_all",
        "source": "VCI",
        "interval": interval.upper(),
    }


def probe_cache_skip_plan(
    ticker: str,
    fpath: Path,
    plan: RefreshPlan,
    requested_end: str,
    *,
    probe_cache: dict[str, dict[str, object]],
    probe_cache_ttl_hours: float,
) -> RefreshPlan:
    if probe_cache_ttl_hours <= 0 or plan.mode != "incremental":
        return plan

    record = probe_cache.get(ticker)
    if not probe_cache_record_is_fresh(
        record,
        requested_end=requested_end,
        path=fpath,
        latest_value=plan.existing_last_time,
        ttl_hours=probe_cache_ttl_hours,
        eligible_statuses=PROBE_CACHE_STATUS_SKIP_ELIGIBLE,
    ):
        return plan

    return RefreshPlan(
        mode="probe_skip",
        fetch_start=None,
        existing_last_time=plan.existing_last_time,
        message=format_probe_cache_skip_message(record),
    )


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


def plan_ticker_refresh(
    ticker: str,
    interval: str,
    start: str,
    end: str,
    *,
    full_refresh: bool,
    probe_cache: dict[str, dict[str, object]],
    probe_cache_ttl_hours: float,
) -> tuple[str, object]:
    fpath = price_file_path(ticker, interval)
    plan = plan_refresh(
        fpath,
        interval,
        start,
        end,
        full_refresh=full_refresh,
    )
    plan = probe_cache_skip_plan(
        ticker,
        fpath,
        plan,
        end,
        probe_cache=probe_cache,
        probe_cache_ttl_hours=probe_cache_ttl_hours,
    )
    return ticker, plan


def build_refresh_plans(
    tickers: list[str],
    *,
    interval: str,
    start: str,
    end: str,
    full_refresh: bool,
    check_workers: int,
    probe_cache: dict[str, dict[str, object]],
    probe_cache_ttl_hours: float,
) -> list[tuple[str, object]]:
    if not tickers:
        return []

    if check_workers <= 1:
        return [
            plan_ticker_refresh(
                ticker,
                interval,
                start,
                end,
                full_refresh=full_refresh,
                probe_cache=probe_cache,
                probe_cache_ttl_hours=probe_cache_ttl_hours,
            )
            for ticker in tickers
        ]

    planned_by_ticker: dict[str, object] = {}
    with cf.ThreadPoolExecutor(max_workers=check_workers, thread_name_prefix="refresh-check") as executor:
        future_to_ticker = {
            executor.submit(
                plan_ticker_refresh,
                ticker,
                interval,
                start,
                end,
                full_refresh=full_refresh,
                probe_cache=probe_cache,
                probe_cache_ttl_hours=probe_cache_ttl_hours,
            ): ticker
            for ticker in tickers
        }
        for future in cf.as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            planned_ticker, plan = future.result()
            planned_by_ticker[planned_ticker or ticker] = plan
    return [(ticker, planned_by_ticker[ticker]) for ticker in tickers]


def fetch_ticker(
    ticker: str,
    interval: str,
    start: str,
    end: str,
    *,
    plan,
    full_refresh: bool,
) -> tuple[bool, str, dict[str, object] | None]:
    fpath = price_file_path(ticker, interval)
    try:
        if plan.mode == "skip":
            return True, f"{ticker}: {plan.message}", None

        stock = Vnstock().stock(symbol=ticker, source="VCI")
        df = stock.quote.history(start=plan.fetch_start, end=end, interval=interval)
        if len(df) == 0:
            if fpath.exists():
                return (
                    True,
                    f"{ticker}: no new data returned ({plan.message}), keeping existing file",
                    build_probe_cache_entry(
                        status="unchanged",
                        checked_end=end,
                        path=fpath,
                        latest_value=plan.existing_last_time,
                    ),
                )
            return False, f"{ticker}: no data returned", None

        existing = load_existing_frame(fpath) if plan.mode == "incremental" else None
        before_rows = 0 if existing is None else len(existing)
        combined = combine_frames(existing, df)
        atomic_write_parquet(combined, fpath)

        new_rows_added = len(combined) - before_rows
        latest_time = pd.to_datetime(combined["time"], errors="coerce").dropna().max()
        latest_date = None if pd.isna(latest_time) else latest_time.date()
        requested_end_date = datetime.fromisoformat(end).date()
        cache_status = "current"
        if latest_date is None or latest_date < requested_end_date:
            cache_status = "partial" if new_rows_added > 0 else "unchanged"
        cache_entry = build_probe_cache_entry(
            status=cache_status,
            checked_end=end,
            path=fpath,
            latest_value=None if pd.isna(latest_time) else latest_time,
        )
        if plan.mode == "incremental":
            if new_rows_added > 0:
                return (
                    True,
                    f"{ticker}: appended {new_rows_added} new rows "
                    f"(latest {latest_time})",
                    cache_entry,
                )
            return (
                True,
                f"{ticker}: refreshed overlap window with no row-count change "
                f"(latest {latest_time})",
                cache_entry,
            )
        return True, f"{ticker}: {len(combined)} rows saved", cache_entry
    except Exception as e:
        err = str(e).encode("ascii", errors="replace").decode("ascii")
        return False, f"{ticker}: ERROR -- {err[:120]}", None


def run_fetch_round_sequential(
    tickers: list[str],
    plans_by_ticker: dict[str, object],
    *,
    interval: str,
    start: str,
    end: str,
    delay: float,
    full_refresh: bool,
    probe_cache: dict[str, dict[str, object]],
    probe_cache_enabled: bool,
) -> tuple[list[str], list[str]]:
    success: list[str] = []
    failed: list[str] = []

    for index, ticker in enumerate(tickers, 1):
        ok, message, cache_entry = fetch_ticker(
            ticker,
            interval,
            start,
            end,
            plan=plans_by_ticker[ticker],
            full_refresh=full_refresh,
        )
        print(f"[{index}/{len(tickers)}] {message}", flush=True)
        update_probe_cache_state(
            probe_cache_path(interval) if probe_cache_enabled else None,
            probe_cache,
            item_key=ticker,
            entry=cache_entry,
            metadata=probe_cache_metadata(interval),
        )
        (success if ok else failed).append(ticker)
        if delay > 0 and index < len(tickers):
            time.sleep(delay)
    return success, failed


def run_fetch_round_parallel(
    tickers: list[str],
    plans_by_ticker: dict[str, object],
    *,
    interval: str,
    start: str,
    end: str,
    delay: float,
    full_refresh: bool,
    workers: int,
    probe_cache: dict[str, dict[str, object]],
    probe_cache_enabled: bool,
) -> tuple[list[str], list[str]]:
    success: list[str] = []
    failed: list[str] = []
    future_to_ticker: dict[cf.Future[tuple[bool, str, dict[str, object] | None]], str] = {}

    with cf.ThreadPoolExecutor(max_workers=workers, thread_name_prefix="refresh-all") as executor:
        ticker_iter = iter(tickers)

        def submit_next() -> bool:
            try:
                ticker = next(ticker_iter)
            except StopIteration:
                return False

            future = executor.submit(
                fetch_ticker,
                ticker,
                interval,
                start,
                end,
                plan=plans_by_ticker[ticker],
                full_refresh=full_refresh,
            )
            future_to_ticker[future] = ticker
            if delay > 0:
                time.sleep(delay)
            return True

        for _ in range(min(workers, len(tickers))):
            if not submit_next():
                break

        completed = 0
        while future_to_ticker:
            done, _ = cf.wait(tuple(future_to_ticker), return_when=cf.FIRST_COMPLETED)
            for future in done:
                ticker = future_to_ticker.pop(future)
                try:
                    ok, message, cache_entry = future.result()
                except Exception as e:  # defensive: fetch_ticker already traps errors
                    err = str(e).encode("ascii", errors="replace").decode("ascii")
                    ok = False
                    message = f"{ticker}: ERROR -- {err[:120]}"
                    cache_entry = None
                completed += 1
                print(f"[{completed}/{len(tickers)}] {message}", flush=True)
                update_probe_cache_state(
                    probe_cache_path(interval) if probe_cache_enabled else None,
                    probe_cache,
                    item_key=ticker,
                    entry=cache_entry,
                    metadata=probe_cache_metadata(interval),
                )
                (success if ok else failed).append(ticker)
                submit_next()
    return success, failed


def run_fetch_round(
    tickers: list[str],
    plans_by_ticker: dict[str, object],
    *,
    interval: str,
    start: str,
    end: str,
    delay: float,
    round_label: str,
    full_refresh: bool,
    workers: int,
    probe_cache: dict[str, dict[str, object]],
    probe_cache_enabled: bool,
) -> tuple[list[str], list[str]]:
    success: list[str] = []
    failed: list[str] = []

    if not tickers:
        return success, failed

    worker_label = f"{workers} workers" if workers > 1 else "serial"
    print(f"\n{round_label} ({len(tickers)} tickers, {worker_label})")
    if workers <= 1:
        return run_fetch_round_sequential(
            tickers,
            plans_by_ticker,
            interval=interval,
            start=start,
            end=end,
            delay=delay,
            full_refresh=full_refresh,
            probe_cache=probe_cache,
            probe_cache_enabled=probe_cache_enabled,
        )
    return run_fetch_round_parallel(
        tickers,
        plans_by_ticker,
        interval=interval,
        start=start,
        end=end,
        delay=delay,
        full_refresh=full_refresh,
        workers=workers,
        probe_cache=probe_cache,
        probe_cache_enabled=probe_cache_enabled,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", default="1D",
                        help="Bar interval to fetch (default: 1D)")
    parser.add_argument("--start",   default="2000-01-01")
    parser.add_argument("--end", default=DEFAULT_END, help="Inclusive end date (default: today)")
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay between ticker submissions in seconds (default: 0.5)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=2,
        help="Number of concurrent ticker fetch workers (default: 2)",
    )
    parser.add_argument(
        "--check-workers",
        type=int,
        default=max(4, min(32, (os.cpu_count() or 8) * 2)),
        help="Number of concurrent local parquet-check workers before network fetch begins",
    )
    parser.add_argument(
        "--probe-cache-ttl-hours",
        type=float,
        default=24.0,
        help=(
            "Trust cached no-change/partial probe metadata for this many hours "
            "when the local parquet has not changed (default: 24; 0 disables)"
        ),
    )
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
    if args.workers <= 0:
        raise ValueError("--workers must be positive")
    if args.check_workers <= 0:
        raise ValueError("--check-workers must be positive")
    if args.probe_cache_ttl_hours < 0:
        raise ValueError("--probe-cache-ttl-hours must be non-negative")

    universe_tickers = get_universe_tickers()
    tickers = get_existing_tickers(args.interval, skip_updated_since=skip_dt)
    skipped = len(universe_tickers) - len(tickers)
    probe_cache_enabled = args.probe_cache_ttl_hours > 0
    probe_cache = load_probe_cache(probe_cache_path(args.interval)) if probe_cache_enabled else {}

    print(f"Refreshing {len(tickers)} tickers at {args.interval} ({args.start} to {args.end})")
    print(f"Ticker universe source: existing {UNIVERSE_INTERVAL} files ({len(universe_tickers)} names)")
    if skip_dt:
        print(f"Skipping {skipped} already updated since {skip_dt}")
    mode_label = "full refresh" if args.full_refresh else "incremental append"
    print(f"Mode: {mode_label}")
    print(
        f"Delay: {args.delay}s | Workers: {args.workers} | "
        f"Check workers: {args.check_workers} | "
        f"Probe cache TTL: {args.probe_cache_ttl_hours}h | "
        f"Retry rounds: {args.retry_rounds} | Socket timeout: 30s"
    )
    print("Precheck: scanning parquet tails...", flush=True)
    planned = build_refresh_plans(
        tickers,
        interval=args.interval,
        start=args.start,
        end=args.end,
        full_refresh=args.full_refresh,
        check_workers=args.check_workers,
        probe_cache=probe_cache,
        probe_cache_ttl_hours=args.probe_cache_ttl_hours,
    )
    plans_by_ticker = {ticker: plan for ticker, plan in planned}
    stale_tickers = [ticker for ticker, plan in planned if plan.mode not in {"skip", "probe_skip"}]
    current_tickers = [ticker for ticker, plan in planned if plan.mode == "skip"]
    probe_cached_tickers = [ticker for ticker, plan in planned if plan.mode == "probe_skip"]

    print(
        f"Precheck done: {len(current_tickers)} already current, "
        f"{len(probe_cached_tickers)} probe-cached, "
        f"{len(stale_tickers)} require fetch",
        flush=True,
    )

    if args.dry_run:
        for ticker, plan in planned[:10]:
            print(f"[DRY RUN] {ticker}: {plan.message}")
        return

    success: list[str] = []
    remaining = list(stale_tickers)

    for attempt in range(args.retry_rounds + 1):
        round_label = "Initial pass" if attempt == 0 else f"Retry round {attempt}/{args.retry_rounds}"
        round_success, remaining = run_fetch_round(
            remaining,
            plans_by_ticker,
            interval=args.interval,
            start=args.start,
            end=args.end,
            delay=args.delay,
            round_label=round_label,
            full_refresh=args.full_refresh,
            workers=args.workers,
            probe_cache=probe_cache,
            probe_cache_enabled=probe_cache_enabled,
        )
        success.extend(round_success)
        if not remaining:
            break
        if attempt < args.retry_rounds and args.retry_delay > 0:
            time.sleep(args.retry_delay)

    failed = remaining

    print(f"\n{'='*50}")
    print(
        f"Done: {len(current_tickers)} already current, "
        f"{len(probe_cached_tickers)} probe-cached, "
        f"{len(success)} refreshed, {len(failed)} failed"
    )
    if failed:
        print(f"Failed: {failed}")


if __name__ == "__main__":
    main()
