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

import pandas as pd
import yfinance as yf

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
OUT_DIR   = REPO_ROOT / "data" / "fx-commodities"
OUT_DIR.mkdir(parents=True, exist_ok=True)

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
PROBE_CACHE_STATUS_SKIP_ELIGIBLE = {"unchanged", "partial"}


def exclusive_yf_end(end: str) -> str:
    return (pd.Timestamp(end).normalize() + pd.Timedelta(days=1)).date().isoformat()


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
    start: str,
    end: str,
    probe_cache: dict[str, dict[str, object]],
    probe_cache_ttl_hours: float,
) -> tuple[bool, dict[str, object] | None]:
    out = OUT_DIR / f"fx_commodities_{alias}_1D.parquet"
    existing = load_existing_frame(out)
    try:
        plan = plan_refresh(out, "1D", start, end, full_refresh=overwrite)
        if plan.mode == "incremental" and probe_cache_record_is_fresh(
            probe_cache.get(alias),
            requested_end=end,
            path=out,
            latest_value=plan.existing_last_time,
            ttl_hours=probe_cache_ttl_hours,
            eligible_statuses=PROBE_CACHE_STATUS_SKIP_ELIGIBLE,
        ):
            print(f"  SKIP {alias} ({format_probe_cache_skip_message(probe_cache[alias])})")
            return True, None
        if plan.mode == "skip":
            print(f"  SKIP {alias} ({plan.message})")
            return True, None

        print(f"  Fetching {ticker} ({alias}, {plan.message})...", end=" ", flush=True)
        df = yf.download(
            ticker,
            start=plan.fetch_start,
            end=exclusive_yf_end(end),
            progress=False,
            auto_adjust=True,
        )
        if df.empty:
            if existing is not None:
                print("NO NEW DATA (keeping existing file)")
                return True, build_probe_cache_entry(
                    status="unchanged",
                    checked_end=end,
                    path=out,
                    latest_value=plan.existing_last_time,
                )
            print("NO DATA")
            return False, None
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
        cache_status = "current"
        if latest_time.normalize().date() < pd.Timestamp(end).normalize().date():
            cache_status = "partial" if len(combined) - before_rows > 0 else "unchanged"
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
        return True, cache_entry
    except Exception as e:
        print(f"ERROR: {e}")
        return False, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default=DEFAULT_START, help="Inclusive start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=DEFAULT_END, help="Inclusive end date (YYYY-MM-DD)")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--probe-cache-ttl-hours",
        type=float,
        default=24.0,
        help="Trust cached no-change/partial probes for this many hours (default: 24; 0 disables)",
    )
    args = parser.parse_args()
    if args.probe_cache_ttl_hours < 0:
        raise ValueError("--probe-cache-ttl-hours must be non-negative")
    if pd.Timestamp(args.start).normalize() > pd.Timestamp(args.end).normalize():
        raise ValueError("--start must be on or before --end")
    probe_cache_enabled = args.probe_cache_ttl_hours > 0
    probe_cache = load_probe_cache(probe_cache_path()) if probe_cache_enabled else {}

    print("=" * 55)
    print("Fetching new global macro / risk tickers")
    print("=" * 55)
    print(f"Date range      : {args.start} -> {args.end}")
    print(f"Probe cache TTL: {args.probe_cache_ttl_hours}h")
    ok = err = 0
    for ticker, alias in TICKERS.items():
        fetch_ok, cache_entry = fetch_one(
            ticker,
            alias,
            args.overwrite,
            start=args.start,
            end=args.end,
            probe_cache=probe_cache,
            probe_cache_ttl_hours=args.probe_cache_ttl_hours,
        )
        update_probe_cache_state(
            probe_cache_path() if probe_cache_enabled else None,
            probe_cache,
            item_key=alias,
            entry=cache_entry,
            metadata=probe_cache_metadata(),
        )
        if fetch_ok:
            ok += 1
        else:
            err += 1
        time.sleep(0.5)

    print(f"\nDone: {ok} OK, {err} failed")
    print(f"Output: {OUT_DIR}")


if __name__ == "__main__":
    main()
