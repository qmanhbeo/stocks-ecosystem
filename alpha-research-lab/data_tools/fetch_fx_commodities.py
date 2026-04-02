from pathlib import Path
import argparse
import time
import yfinance as yf
import pandas as pd
import re

try:
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
except ModuleNotFoundError:
    from data_tools.stock_refresh_utils import (
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
OUT_DIR = REPO_ROOT / "data" / "fx-commodities"
OUT_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_END = pd.Timestamp.today().normalize().date().isoformat()

# Default human-readable aliases
DEFAULT_ALIASES = {
    "VND=X": "fx_vnd_usd",
    "GC=F": "gold",
    "CL=F": "oil",
}
PROBE_CACHE_STATUS_SKIP_ELIGIBLE = {"unchanged", "partial"}


def _sanitize_ticker(ticker: str) -> str:
    # Replace any non-alphanumeric with underscore
    return re.sub(r"[^A-Za-z0-9]+", "_", ticker).strip("_").lower()


def _alias_for_ticker(ticker: str, alias_map: dict) -> str:
    return alias_map.get(ticker.upper(), _sanitize_ticker(ticker))


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


def fetch_ticker(
    ticker: str,
    interval: str,
    start: str,
    end: str,
    alias_map: dict,
    *,
    overwrite: bool = False,
    probe_cache: dict[str, dict[str, object]],
    probe_cache_ttl_hours: float,
) -> tuple[bool, dict[str, object] | None]:
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
        if plan.mode == "incremental" and probe_cache_record_is_fresh(
            probe_cache.get(alias),
            requested_end=end,
            path=file_path,
            latest_value=plan.existing_last_time,
            ttl_hours=probe_cache_ttl_hours,
            eligible_statuses=PROBE_CACHE_STATUS_SKIP_ELIGIBLE,
        ):
            print(f"⏭️  {ticker} ({alias}): {format_probe_cache_skip_message(probe_cache[alias])}")
            return True, None
        if plan.mode == "skip":
            print(f"⏭️  {ticker} ({alias}): {plan.message}")
            return True, None

        print(f"📥 Fetching {ticker} ({alias}, {plan.message})...", end=" ", flush=True)
        df = yf.download(
            ticker,
            start=plan.fetch_start,
            end=_exclusive_yf_end(end),
            interval=interval,
            progress=False,
            auto_adjust=False,
        )
        df = _normalize_yf_df(df)
        if df.empty:
            if existing is not None:
                print("⏭️  No new data returned, keeping existing file")
                return True, build_probe_cache_entry(
                    status="unchanged",
                    checked_end=end,
                    path=file_path,
                    latest_value=plan.existing_last_time,
                )
            print("❌ No data returned")
            return False, None
        df["ticker"] = ticker.upper()
        df["alias"] = alias
        base = existing if plan.mode == "incremental" else None
        before_rows = 0 if base is None else len(base)
        combined = combine_frames(base, df)
        atomic_write_parquet(combined, file_path)
        latest_time = pd.to_datetime(combined["time"], errors="coerce").dropna().max()
        cache_status = "current"
        if latest_time.normalize().date() < pd.Timestamp(end).normalize().date():
            cache_status = "partial" if len(combined) - before_rows > 0 else "unchanged"
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
        return True, cache_entry
    except Exception as e:
        print(f"❌ Error: {e}")
        return False, None


def main():
    parser = argparse.ArgumentParser(description="Fetch FX/commodities data from yfinance")
    parser.add_argument(
        "--tickers",
        type=str,
        default="VND=X,GC=F,CL=F",
        help="Comma-separated list of tickers (e.g., VND=X,GC=F,CL=F)"
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
        help="Trust cached no-change/partial probes for this many hours (default: 24; 0 disables)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between requests in seconds (default: 1.0)"
    )
    
    args = parser.parse_args()
    if args.probe_cache_ttl_hours < 0:
        raise ValueError("--probe-cache-ttl-hours must be non-negative")
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
    
    success_count = 0
    failed = []
    
    for i, ticker in enumerate(tickers):
        ok, cache_entry = fetch_ticker(
            ticker,
            args.interval,
            args.start,
            args.end,
            alias_map,
            overwrite=args.overwrite,
            probe_cache=probe_cache,
            probe_cache_ttl_hours=args.probe_cache_ttl_hours,
        )
        update_probe_cache_state(
            probe_cache_path(args.interval) if probe_cache_enabled else None,
            probe_cache,
            item_key=_alias_for_ticker(ticker, alias_map),
            entry=cache_entry,
            metadata=probe_cache_metadata(args.interval),
        )
        if ok:
            success_count += 1
        else:
            failed.append(ticker)
        if i < len(tickers) - 1:
            time.sleep(args.delay)
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"✅ Successfully fetched: {success_count}/{len(tickers)}")
    if failed:
        print(f"❌ Failed: {', '.join(failed)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
