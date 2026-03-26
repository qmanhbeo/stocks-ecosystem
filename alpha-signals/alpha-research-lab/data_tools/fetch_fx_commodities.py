from pathlib import Path
import argparse
import time
import yfinance as yf
import pandas as pd
import re


REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "data" / "fx-commodities"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Default human-readable aliases
DEFAULT_ALIASES = {
    "VND=X": "fx_vnd_usd",
    "GC=F": "gold",
    "CL=F": "oil",
}


def _sanitize_ticker(ticker: str) -> str:
    # Replace any non-alphanumeric with underscore
    return re.sub(r"[^A-Za-z0-9]+", "_", ticker).strip("_").lower()


def _alias_for_ticker(ticker: str, alias_map: dict) -> str:
    return alias_map.get(ticker.upper(), _sanitize_ticker(ticker))


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


def fetch_ticker(ticker: str, interval: str, start: str, end: str, alias_map: dict) -> bool:
    alias = _alias_for_ticker(ticker, alias_map)
    file_path = OUT_DIR / f"fx_commodities_{alias}_{interval}.parquet"
    if file_path.exists():
        print(f"⏭️  {ticker} ({alias}): Already exists, skipping...")
        return True
    
    try:
        print(f"📥 Fetching {ticker} ({alias})...", end=" ", flush=True)
        df = yf.download(ticker, start=start, end=end, interval=interval, progress=False, auto_adjust=False)
        df = _normalize_yf_df(df)
        if df.empty:
            print("❌ No data returned")
            return False
        df["ticker"] = ticker.upper()
        df["alias"] = alias
        df.to_parquet(file_path, index=False)
        print(f"✅ Saved ({len(df)} rows)")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


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
        default="2026-12-31",
        help="End date (default: 2026-12-31)"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between requests in seconds (default: 1.0)"
    )
    
    args = parser.parse_args()
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
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
    print(f"Output: {OUT_DIR}")
    print("=" * 60 + "\n")
    
    if args.overwrite:
        for ticker in tickers:
            alias = _alias_for_ticker(ticker, alias_map)
            file_path = OUT_DIR / f"fx_commodities_{alias}_{args.interval}.parquet"
            if file_path.exists():
                file_path.unlink()
                print(f"🗑️  Removed existing file: {ticker}")
    
    success_count = 0
    failed = []
    
    for i, ticker in enumerate(tickers):
        ok = fetch_ticker(ticker, args.interval, args.start, args.end, alias_map)
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
