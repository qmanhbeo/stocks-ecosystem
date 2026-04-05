from pathlib import Path
from path_utils import data_path
import argparse
import time
import yfinance as yf
import yfinance.shared as yf_shared
import pandas as pd
import re

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
OUT_DIR = data_path("fx-commodities")
OUT_DIR.mkdir(parents=True, exist_ok=True)
YF_CACHE_DIR = OUT_DIR / "_cache" / "yfinance"
YF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
yf.set_tz_cache_location(str(YF_CACHE_DIR))
DEFAULT_END = pd.Timestamp.today().normalize().date().isoformat()
DEFAULT_TICKERS = [
    "VND=X",
    "GC=F",
    "CL=F",
    "HG=F",
    "CNY=X",
    "^VIX",
    "^GSPC",
    "^HSI",
    "000001.SS",
    "^KS11",
    "^TWII",
    "^N225",
    "EEM",
    "EWH",
    "VNM",
    "HYG",
    "TLT",
    "^TNX",
    "^IRX",
    "BTC-USD",
    "DX-Y.NYB",
]

# Default human-readable aliases
DEFAULT_ALIASES = {
    "VND=X": "fx_vnd_usd",
    "GC=F": "gold",
    "CL=F": "oil",
    "HG=F": "hg_f",
    "CNY=X": "cny_x",
    "^VIX": "vix",
    "^GSPC": "sp500",
    "000001.SS": "shanghai",
    "^KS11": "kospi",
    "TWII": "taiex",
    "^TWII": "taiex",
    "N225": "nikkei",
    "^N225": "nikkei",
    "VNM": "vnm_etf",
    "^TNX": "us10y",
    "^IRX": "us3m",
    "BTC-USD": "btc",
    "DX-Y.NYB": "dxy",
}
PROBE_CACHE_STATUS_SKIP_ELIGIBLE = {"unchanged"}
PROBE_CACHE_MAX_LAG_DAYS = 3
FETCH_STATUS_FETCHED = "fetched"
FETCH_STATUS_SKIPPED = "skipped"
FETCH_STATUS_RETRYABLE = "retryable"
FETCH_STATUS_RATE_LIMITED = "rate_limited"
FETCH_STATUS_FAILED = "failed"
YAHOO_TICKER_CANONICAL = {
    "TWII": "^TWII",
    "N225": "^N225",
}


def _sanitize_ticker(ticker: str) -> str:
    # Replace any non-alphanumeric with underscore
    return re.sub(r"[^A-Za-z0-9]+", "_", ticker).strip("_").lower()


def _alias_for_ticker(ticker: str, alias_map: dict) -> str:
    return alias_map.get(ticker.upper(), _sanitize_ticker(ticker))


def _ticker_for_yahoo(ticker: str) -> str:
    return YAHOO_TICKER_CANONICAL.get(ticker.upper(), ticker.upper())


def probe_cache_path(interval: str) -> Path:
    safe_interval = interval.upper().replace("/", "_")
    return build_probe_cache_path(OUT_DIR, f"fetch_fx_commodities_{safe_interval}_probe_cache")


def probe_cache_metadata(interval: str) -> dict[str, object]:
    return {
        "tool": "fetch_fx_commodities",
        "source": "yfinance",
        "interval": interval.upper(),
    }


def _normalize_yf_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df = df.rename(columns={
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "adj_close",
        "Volume": "volume",
    })
    if "Date" in df.columns:
        df = df.rename(columns={"Date": "time"})
    elif df.index.name:
        df = df.reset_index().rename(columns={df.index.name: "time"})
    else:
        df = df.reset_index().rename(columns={"index": "time"})
    return df


def _exclusive_yf_end(end: str) -> str:
    return (pd.Timestamp(end).normalize() + pd.Timedelta(days=1)).date().isoformat()


def _download_with_rate_limit_retry(
    ticker: str,
    *,
    start: str,
    end: str,
    interval: str,
    auto_adjust: bool,
    rate_limit_retries: int,
    rate_limit_backoff_seconds: float,
) -> tuple[pd.DataFrame, bool]:
    yahoo_ticker = _ticker_for_yahoo(ticker)
    attempts = max(rate_limit_retries, 0) + 1
    for attempt in range(attempts):
        df = yf.download(
            yahoo_ticker,
            start=start,
            end=end,
            interval=interval,
            progress=False,
            auto_adjust=auto_adjust,
        )
        error_message = getattr(yf_shared, "_ERRORS", {}).get(yahoo_ticker.upper())
        if not error_message_indicates_rate_limit(error_message):
            return df, False
        if attempt == attempts - 1:
            print(
                f"⚠️  Yahoo rate limited {yahoo_ticker}; exhausted {attempts} attempt(s)",
                flush=True,
            )
            return pd.DataFrame(), True
        wait_seconds = rate_limit_backoff_seconds * (attempt + 1)
        print(
            f"⚠️  Yahoo rate limited {yahoo_ticker}; retrying in {wait_seconds:.1f}s...",
            flush=True,
        )
        time.sleep(wait_seconds)
    return pd.DataFrame(), False


def fetch_ticker(
    ticker: str,
    interval: str,
    start: str,
    end: str,
    alias_map: dict,
    *,
    overwrite: bool = False,
    probe_cache: dict[str, dict[str, object]] | None = None,
    probe_cache_ttl_hours: float = 24.0,
    rate_limit_retries: int = 1,
    rate_limit_backoff_seconds: float = 30.0,
) -> tuple[str, dict[str, object] | None]:
    return_details = probe_cache is not None
    if probe_cache is None:
        probe_cache = load_probe_cache(probe_cache_path(interval)) if probe_cache_ttl_hours > 0 else {}
    alias = _alias_for_ticker(ticker, alias_map)
    file_path = OUT_DIR / f"fx_commodities_{alias}_{interval}.parquet"
    existing = load_existing_frame(file_path)

    try:
        plan = plan_refresh(
            file_path,
            interval,
            start,
            end,
            full_refresh=overwrite,
        )
        current_tail_covers_end = latest_value_covers_requested_end(
            plan.existing_last_time,
            end,
            max_lag_days=PROBE_CACHE_MAX_LAG_DAYS,
        )
        if plan.mode == "incremental" and current_tail_covers_end:
            if probe_cache_record_is_fresh(
                probe_cache.get(alias),
                requested_end=end,
                path=file_path,
                latest_value=plan.existing_last_time,
                ttl_hours=probe_cache_ttl_hours,
                eligible_statuses=PROBE_CACHE_STATUS_SKIP_ELIGIBLE,
            ):
                print(f"⏭️  {ticker} ({alias}): {format_probe_cache_skip_message(probe_cache[alias])}")
                if return_details:
                    return FETCH_STATUS_SKIPPED, None
                return True
        if plan.mode == "skip":
            print(f"⏭️  {ticker} ({alias}): {plan.message}")
            if return_details:
                return FETCH_STATUS_SKIPPED, None
            return True

        print(f"📥 Fetching {ticker} ({alias}, {plan.message})...", end=" ", flush=True)
        df, rate_limited = _download_with_rate_limit_retry(
            ticker,
            start=plan.fetch_start,
            end=_exclusive_yf_end(end),
            interval=interval,
            auto_adjust=False,
            rate_limit_retries=rate_limit_retries,
            rate_limit_backoff_seconds=rate_limit_backoff_seconds,
        )
        if rate_limited:
            if return_details:
                return FETCH_STATUS_RATE_LIMITED, None
            return False
        df = _normalize_yf_df(df)
        if df.empty:
            if existing is not None:
                if current_tail_covers_end or plan.mode != "incremental":
                    print("⏭️  No new data returned, keeping existing file")
                    if return_details:
                        return FETCH_STATUS_SKIPPED, build_probe_cache_entry(
                            status="unchanged",
                            checked_end=end,
                            path=file_path,
                            latest_value=plan.existing_last_time,
                        )
                    return True
                print("⚠️  No new data returned; existing file is still behind requested end, so probe cache remains retryable")
                if return_details:
                    return FETCH_STATUS_RETRYABLE, None
                return False
            print("❌ No data returned")
            if return_details:
                return FETCH_STATUS_FAILED, None
            return False
        df["ticker"] = ticker.upper()
        df["alias"] = alias
        base = existing if plan.mode == "incremental" else None
        before_rows = 0 if base is None else len(base)
        combined = combine_frames(base, df)
        atomic_write_parquet(combined, file_path)
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
            path=file_path,
            latest_value=latest_time,
        )
        if plan.mode == "incremental":
            added_rows = len(combined) - before_rows
            if added_rows > 0:
                print(f"✅ Appended {added_rows} new rows (latest {latest_time})")
            else:
                print(f"✅ Refreshed overlap window (latest {latest_time})")
        else:
            print(f"✅ Saved ({len(combined)} rows)")
        if return_details:
            return FETCH_STATUS_FETCHED, cache_entry
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        if return_details:
            return FETCH_STATUS_FAILED, None
        return False


def main():
    parser = argparse.ArgumentParser(description="Fetch FX/commodities data from yfinance")
    parser.add_argument(
        "--tickers",
        type=str,
        default=",".join(DEFAULT_TICKERS),
        help="Comma-separated list of tickers (default: canonical shared macro basket)"
    )
    parser.add_argument(
        "--aliases",
        type=str,
        default=None,
        help="Optional alias overrides: TICKER=alias,TICKER2=alias2"
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
        help="Overwrite existing files"
    )
    parser.add_argument(
        "--probe-cache-ttl-hours",
        type=float,
        default=24.0,
        help="Trust cached fully current no-change probes for this many hours (default: 24; 0 disables)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between requests in seconds (default: 1.0)"
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
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    args.interval = args.interval.upper()
    probe_cache_enabled = args.probe_cache_ttl_hours > 0
    probe_cache = load_probe_cache(probe_cache_path(args.interval)) if probe_cache_enabled else {}
    alias_map = dict(DEFAULT_ALIASES)
    if args.aliases:
        for pair in args.aliases.split(","):
            if "=" not in pair:
                continue
            k, v = pair.split("=", 1)
            k = k.strip().upper()
            v = v.strip().lower()
            if k and v:
                alias_map[k] = v
    
    print("=" * 60)
    print("FX/Commodities Data Fetcher (yfinance)")
    print("=" * 60)
    print(f"Tickers: {', '.join(tickers)}")
    print(f"Interval: {args.interval}")
    print(f"Period: {args.start} to {args.end}")
    print(f"Probe cache TTL: {args.probe_cache_ttl_hours}h")
    print(f"Output: {OUT_DIR}")
    print("=" * 60 + "\n")
    
    fetched_count = 0
    skipped_count = 0
    retryable = []
    rate_limited = []
    failed = []
    not_attempted = []

    for i, ticker in enumerate(tickers):
        status, cache_entry = fetch_ticker(
            ticker,
            args.interval,
            args.start,
            args.end,
            alias_map,
            overwrite=args.overwrite,
            probe_cache=probe_cache,
            probe_cache_ttl_hours=args.probe_cache_ttl_hours,
            rate_limit_retries=args.rate_limit_retries,
            rate_limit_backoff_seconds=args.rate_limit_backoff_seconds,
        )
        update_probe_cache_state(
            probe_cache_path(args.interval) if probe_cache_enabled else None,
            probe_cache,
            item_key=_alias_for_ticker(ticker, alias_map),
            entry=cache_entry,
            metadata=probe_cache_metadata(args.interval),
        )
        if status == FETCH_STATUS_FETCHED:
            fetched_count += 1
        elif status == FETCH_STATUS_SKIPPED:
            skipped_count += 1
        elif status == FETCH_STATUS_RETRYABLE:
            retryable.append(ticker)
        elif status == FETCH_STATUS_RATE_LIMITED:
            rate_limited.append(ticker)
            not_attempted = tickers[i + 1 :]
            print("🛑 Yahoo rate limit persisted; stopping remaining tickers to avoid wasting requests.")
            break
        else:
            failed.append(ticker)
        if i < len(tickers) - 1:
            time.sleep(args.delay)
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"✅ Fetched/refreshed: {fetched_count}/{len(tickers)}")
    print(f"⏭️  Already current: {skipped_count}/{len(tickers)}")
    if retryable:
        print(f"⚠️  Retryable but still stale: {', '.join(retryable)}")
    if rate_limited:
        print(f"🚫 Rate limited: {', '.join(rate_limited)}")
    if not_attempted:
        print(f"⏸️  Not attempted after rate limit: {', '.join(not_attempted)}")
    if failed:
        print(f"❌ Failed: {', '.join(failed)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
