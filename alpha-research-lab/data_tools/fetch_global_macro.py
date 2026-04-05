"""
Fetch additional global macro / risk indicators via yfinance.

New tickers not in the original fetch_fx_commodities.py:
  ^GSPC    S&P 500 (US equity market)
  DX-Y.NYB DXY — US Dollar Index
  ^IRX     US 3-Month T-Bill yield
  EEM      iShares Emerging Markets ETF (EM flow proxy)
  HYG      iShares High Yield Corporate Bond ETF (credit risk appetite)
  TLT      iShares 20+ Year Treasury ETF (flight-to-safety / rates)
  ^KS11    KOSPI (Korea — Asian tech/manufacturing leading indicator)
  ^TWII    Taiwan Weighted Index (semiconductor cycle)
  BTC-USD  Bitcoin (global risk sentiment / speculative appetite)
  EWH      iShares MSCI Hong Kong ETF (China/HK trade proxy)

Usage:
    conda run -n stocks python data_tools/fetch_global_macro.py
    conda run -n stocks python data_tools/fetch_global_macro.py --overwrite
"""
import argparse
import time
from pathlib import Path
from path_utils import data_path

import pandas as pd
import yfinance as yf
import yfinance.shared as yf_shared

try:
    from stock_refresh_utils import (
        atomic_write_parquet,
        build_probe_cache_entry,
        build_probe_cache_path,
        combine_frames,
        error_message_indicates_rate_limit,
        format_probe_cache_skip_message,
        latest_value_covers_requested_end,
        load_existing_frame,
        load_probe_cache,
        plan_refresh,
        probe_cache_record_is_fresh,
        update_probe_cache_state,
    )
except ModuleNotFoundError:
    from data_tools.stock_refresh_utils import (
        atomic_write_parquet,
        build_probe_cache_entry,
        build_probe_cache_path,
        combine_frames,
        error_message_indicates_rate_limit,
        format_probe_cache_skip_message,
        latest_value_covers_requested_end,
        load_existing_frame,
        load_probe_cache,
        plan_refresh,
        probe_cache_record_is_fresh,
        update_probe_cache_state,
    )

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR   = data_path("fx-commodities")
OUT_DIR.mkdir(parents=True, exist_ok=True)
YF_CACHE_DIR = OUT_DIR / "_cache" / "yfinance"
YF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
yf.set_tz_cache_location(str(YF_CACHE_DIR))

TICKERS = {
    "^GSPC":     "sp500",
    "DX-Y.NYB":  "dxy",
    "^IRX":      "us3m",
    "EEM":       "eem",
    "HYG":       "hyg",
    "TLT":       "tlt",
    "^KS11":     "kospi",
    "^TWII":     "taiex",
    "BTC-USD":   "btc",
    "EWH":       "ewh",
}

DEFAULT_START = "2000-01-01"
DEFAULT_END = pd.Timestamp.today().normalize().date().isoformat()
PROBE_CACHE_STATUS_SKIP_ELIGIBLE = {"unchanged"}
PROBE_CACHE_MAX_LAG_DAYS = 3
FETCH_STATUS_FETCHED = "fetched"
FETCH_STATUS_SKIPPED = "skipped"
FETCH_STATUS_RETRYABLE = "retryable"
FETCH_STATUS_RATE_LIMITED = "rate_limited"
FETCH_STATUS_FAILED = "failed"


def exclusive_yf_end(end: str) -> str:
    return (pd.Timestamp(end).normalize() + pd.Timedelta(days=1)).date().isoformat()


def _download_with_rate_limit_retry(
    ticker: str,
    *,
    start: str,
    end: str,
    auto_adjust: bool,
    rate_limit_retries: int,
    rate_limit_backoff_seconds: float,
) -> tuple[pd.DataFrame, bool]:
    attempts = max(rate_limit_retries, 0) + 1
    for attempt in range(attempts):
        df = yf.download(
            ticker,
            start=start,
            end=end,
            progress=False,
            auto_adjust=auto_adjust,
        )
        error_message = getattr(yf_shared, "_ERRORS", {}).get(ticker.upper())
        if not error_message_indicates_rate_limit(error_message):
            return df, False
        if attempt == attempts - 1:
            print(
                f"YAHOO RATE LIMITED {ticker}; exhausted {attempts} attempt(s)",
                flush=True,
            )
            return pd.DataFrame(), True
        wait_seconds = rate_limit_backoff_seconds * (attempt + 1)
        print(
            f"YAHOO RATE LIMITED {ticker}; retrying in {wait_seconds:.1f}s...",
            flush=True,
        )
        time.sleep(wait_seconds)
    return pd.DataFrame(), False


def probe_cache_path() -> Path:
    return build_probe_cache_path(OUT_DIR, "fetch_global_macro_1d_probe_cache")


def probe_cache_metadata() -> dict[str, object]:
    return {
        "tool": "fetch_global_macro",
        "source": "yfinance",
        "interval": "1D",
    }


def fetch_one(
    ticker: str,
    alias: str,
    overwrite: bool,
    *,
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    probe_cache: dict[str, dict[str, object]] | None = None,
    probe_cache_ttl_hours: float = 24.0,
    rate_limit_retries: int = 1,
    rate_limit_backoff_seconds: float = 30.0,
) -> tuple[str, dict[str, object] | None]:
    return_details = probe_cache is not None
    if probe_cache is None:
        probe_cache = load_probe_cache(probe_cache_path()) if probe_cache_ttl_hours > 0 else {}
    out = OUT_DIR / f"fx_commodities_{alias}_1D.parquet"
    existing = load_existing_frame(out)
    try:
        plan = plan_refresh(out, "1D", start, end, full_refresh=overwrite)
        current_tail_covers_end = latest_value_covers_requested_end(
            plan.existing_last_time,
            end,
            max_lag_days=PROBE_CACHE_MAX_LAG_DAYS,
        )
        if plan.mode == "incremental" and current_tail_covers_end:
            if probe_cache_record_is_fresh(
                probe_cache.get(alias),
                requested_end=end,
                path=out,
                latest_value=plan.existing_last_time,
                ttl_hours=probe_cache_ttl_hours,
                eligible_statuses=PROBE_CACHE_STATUS_SKIP_ELIGIBLE,
            ):
                print(f"  SKIP {alias} ({format_probe_cache_skip_message(probe_cache[alias])})")
                if return_details:
                    return FETCH_STATUS_SKIPPED, None
                return True
        if plan.mode == "skip":
            print(f"  SKIP {alias} ({plan.message})")
            if return_details:
                return FETCH_STATUS_SKIPPED, None
            return True

        print(f"  Fetching {ticker} ({alias}, {plan.message})...", end=" ", flush=True)
        df, rate_limited = _download_with_rate_limit_retry(
            ticker,
            start=plan.fetch_start,
            end=exclusive_yf_end(end),
            auto_adjust=True,
            rate_limit_retries=rate_limit_retries,
            rate_limit_backoff_seconds=rate_limit_backoff_seconds,
        )
        if rate_limited:
            if return_details:
                return FETCH_STATUS_RATE_LIMITED, None
            return False
        if df.empty:
            if existing is not None:
                if current_tail_covers_end or plan.mode != "incremental":
                    print("NO NEW DATA (keeping existing file)")
                    if return_details:
                        return FETCH_STATUS_SKIPPED, build_probe_cache_entry(
                            status="unchanged",
                            checked_end=end,
                            path=out,
                            latest_value=plan.existing_last_time,
                        )
                    return True
                print("NO NEW DATA (existing file still behind requested end; probe cache remains retryable)")
                if return_details:
                    return FETCH_STATUS_RETRYABLE, None
                return False
            print("NO DATA")
            if return_details:
                return FETCH_STATUS_FAILED, None
            return False
        df = df.reset_index()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0].lower() if c[1] == "" or c[1] == ticker else c[0].lower()
                          for c in df.columns]
        else:
            df.columns = [c.lower() for c in df.columns]
        df = df.rename(columns={"date": "time", "Date": "time"})
        if "time" not in df.columns and "index" in df.columns:
            df = df.rename(columns={"index": "time"})
        df["ticker"] = ticker
        df["alias"]  = alias
        df["time"] = pd.to_datetime(df["time"])
        base = existing if plan.mode == "incremental" else None
        before_rows = 0 if base is None else len(base)
        combined = combine_frames(base, df)
        atomic_write_parquet(combined, out)
        latest_time = pd.to_datetime(combined["time"], errors="coerce").dropna().max()
        latest_covers_end = latest_value_covers_requested_end(
            latest_time,
            end,
            max_lag_days=PROBE_CACHE_MAX_LAG_DAYS,
        )
        if latest_covers_end:
            cache_status = "unchanged" if len(combined) == before_rows else "current"
        else:
            cache_status = "partial"
        cache_entry = build_probe_cache_entry(
            status=cache_status,
            checked_end=end,
            path=out,
            latest_value=latest_time,
        )
        if plan.mode == "incremental":
            added_rows = len(combined) - before_rows
            if added_rows > 0:
                print(f"OK (appended {added_rows} rows, latest {latest_time})")
            else:
                print(f"OK (refreshed overlap window, latest {latest_time})")
        else:
            print(f"OK ({len(combined)} rows)")
        if return_details:
            return FETCH_STATUS_FETCHED, cache_entry
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        if return_details:
            return FETCH_STATUS_FAILED, None
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default=DEFAULT_START, help="Inclusive start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=DEFAULT_END, help="Inclusive end date (YYYY-MM-DD)")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--probe-cache-ttl-hours",
        type=float,
        default=24.0,
        help="Trust cached fully current no-change probes for this many hours (default: 24; 0 disables)",
    )
    parser.add_argument(
        "--rate-limit-retries",
        type=int,
        default=1,
        help="Extra retries after Yahoo rate limits a ticker (default: 1)",
    )
    parser.add_argument(
        "--rate-limit-backoff-seconds",
        type=float,
        default=30.0,
        help="Base cooldown before retrying a rate-limited ticker (default: 30)",
    )
    args = parser.parse_args()
    if args.probe_cache_ttl_hours < 0:
        raise ValueError("--probe-cache-ttl-hours must be non-negative")
    if args.rate_limit_retries < 0:
        raise ValueError("--rate-limit-retries must be non-negative")
    if args.rate_limit_backoff_seconds < 0:
        raise ValueError("--rate-limit-backoff-seconds must be non-negative")
    if pd.Timestamp(args.start).normalize() > pd.Timestamp(args.end).normalize():
        raise ValueError("--start must be on or before --end")
    probe_cache_enabled = args.probe_cache_ttl_hours > 0
    probe_cache = load_probe_cache(probe_cache_path()) if probe_cache_enabled else {}

    print("=" * 55)
    print("Fetching new global macro / risk tickers")
    print("=" * 55)
    print(f"Date range      : {args.start} -> {args.end}")
    print(f"Probe cache TTL: {args.probe_cache_ttl_hours}h")
    fetched = skipped = 0
    retryable = 0
    rate_limited = 0
    err = 0
    tickers = list(TICKERS.items())
    not_attempted = []
    for index, (ticker, alias) in enumerate(tickers):
        status, cache_entry = fetch_one(
            ticker,
            alias,
            args.overwrite,
            start=args.start,
            end=args.end,
            probe_cache=probe_cache,
            probe_cache_ttl_hours=args.probe_cache_ttl_hours,
            rate_limit_retries=args.rate_limit_retries,
            rate_limit_backoff_seconds=args.rate_limit_backoff_seconds,
        )
        update_probe_cache_state(
            probe_cache_path() if probe_cache_enabled else None,
            probe_cache,
            item_key=alias,
            entry=cache_entry,
            metadata=probe_cache_metadata(),
        )
        if status == FETCH_STATUS_FETCHED:
            fetched += 1
        elif status == FETCH_STATUS_SKIPPED:
            skipped += 1
        elif status == FETCH_STATUS_RETRYABLE:
            retryable += 1
        elif status == FETCH_STATUS_RATE_LIMITED:
            rate_limited += 1
            not_attempted = [alias_name for _, alias_name in tickers[index + 1 :]]
            print("Stopping remaining tickers because Yahoo rate limiting persisted.")
            break
        else:
            err += 1
        time.sleep(0.5)

    print(
        f"\nDone: {fetched} fetched/refreshed, {skipped} already current, "
        f"{retryable} retryable stale, {rate_limited} rate limited, {err} failed"
    )
    if not_attempted:
        print(f"Not attempted after rate limit: {', '.join(not_attempted)}")
    print(f"Output: {OUT_DIR}")


if __name__ == "__main__":
    main()
