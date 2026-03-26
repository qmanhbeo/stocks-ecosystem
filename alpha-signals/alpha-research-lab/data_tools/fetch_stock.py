from pathlib import Path
from vnstock import Vnstock
import argparse
import time

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data" / "stock"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def fetch_ticker(ticker, time_interval="1D", start="2000-01-01", end="2026-12-31"):
    """Fetch data for a single ticker."""
    
    file_path = DATA_DIR / f"gia_lich_su_{ticker}_{time_interval}.parquet"
    
    # Skip if file already exists
    if file_path.exists():
        print(f"⏭️  {ticker}: Already exists, skipping...")
        return True
    
    try:
        print(f"📥 Fetching {ticker}...", end=" ", flush=True)
        stock = Vnstock().stock(symbol=ticker, source="VCI")
        df = stock.quote.history(
            start=start,
            end=end,
            interval=time_interval
        )
        
        if len(df) == 0:
            print(f"❌ No data returned")
            return False
        
        df.to_parquet(file_path, index=False)
        print(f"✅ Saved ({len(df)} days)")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


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
        help="Overwrite existing files"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between requests in seconds (default: 1.0)"
    )
    
    args = parser.parse_args()
    
    # Parse tickers
    tickers = [t.strip().upper() for t in args.tickers.split(",")]
    
    print("="*60)
    print("Stock Data Fetcher")
    print("="*60)
    print(f"Tickers: {', '.join(tickers)}")
    print(f"Interval: {args.interval}")
    print(f"Period: {args.start} to {args.end}")
    print(f"Output: {DATA_DIR}")
    print("="*60 + "\n")
    
    # Remove existing files if overwrite is enabled
    if args.overwrite:
        for ticker in tickers:
            file_path = DATA_DIR / f"gia_lich_su_{ticker}_{args.interval}.parquet"
            if file_path.exists():
                file_path.unlink()
                print(f"🗑️  Removed existing file: {ticker}")
    
    # Fetch all tickers
    success_count = 0
    failed_tickers = []
    
    for i, ticker in enumerate(tickers):
        success = fetch_ticker(ticker, args.interval, args.start, args.end)
        
        if success:
            success_count += 1
        else:
            failed_tickers.append(ticker)
        
        # Delay between requests (except for last one)
        if i < len(tickers) - 1:
            time.sleep(args.delay)
    
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
