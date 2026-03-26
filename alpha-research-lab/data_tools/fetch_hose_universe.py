"""
Fetch all HOSE-listed stocks not yet in data/stock/.

Strategy:
  - Pull HOSE ticker list from vnstock Listing API
  - Skip tickers already in data/stock/
  - Fetch remaining with rate-limit delay
  - cross_sectional_wf.py already filters to >=300 rows, so recently-listed
    or illiquid tickers with sparse data are automatically excluded at training time

Usage:
    conda run -n stocks python data_tools/fetch_hose_universe.py
    conda run -n stocks python data_tools/fetch_hose_universe.py --delay 0.5 --dry-run
    conda run -n stocks python data_tools/fetch_hose_universe.py --exchange HNX
"""
import sys
import io
import argparse
import time
from pathlib import Path

from vnstock import Listing, Vnstock

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR  = REPO_ROOT / "data" / "stock"
EXCLUDE   = {"VNINDEX", "VN30"}


def get_exchange_tickers(exchange: str = "HOSE") -> list[str]:
    listing = Listing()
    df = listing.symbols_by_exchange()
    tickers = df[df["exchange"] == exchange]["symbol"].str.strip().str.upper().tolist()
    # Keep only 3-letter tickers (real stocks). Longer ones are warrants/bonds (e.g. CFPT2526, CACB2502)
    tickers = [t for t in tickers if len(t) == 3]
    return sorted(set(tickers) - EXCLUDE)


def already_fetched() -> set[str]:
    return {
        p.stem.replace("gia_lich_su_", "").replace("_1D", "").upper()
        for p in DATA_DIR.glob("gia_lich_su_*_1D.parquet")
    }


def fetch_ticker(ticker: str, start: str = "2000-01-01", end: str = "2025-12-31") -> bool:
    fpath = DATA_DIR / f"gia_lich_su_{ticker}_1D.parquet"
    if fpath.exists():
        return True
    try:
        stock = Vnstock().stock(symbol=ticker, source="VCI")
        df = stock.quote.history(start=start, end=end, interval="1D")
        if len(df) == 0:
            print(f"  {ticker}: no data")
            return False
        df.to_parquet(fpath, index=False)
        print(f"  {ticker}: {len(df)} rows saved")
        return True
    except Exception as e:
        err = str(e).encode('ascii', errors='replace').decode('ascii')
        print(f"  {ticker}: ERROR -- {err}")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exchange", default="HOSE", choices=["HOSE", "HNX", "UPCOM"],
                        help="Exchange to fetch (default: HOSE)")
    parser.add_argument("--delay", type=float, default=0.8,
                        help="Seconds between requests (default: 0.8)")
    parser.add_argument("--dry-run", action="store_true",
                        help="List what would be fetched without actually fetching")
    parser.add_argument("--end", type=str, default="2025-12-31",
                        help="End date for fetch (default: 2025-12-31, never touch 2026)")
    args = parser.parse_args()

    print(f"Fetching {args.exchange} ticker list...")
    all_tickers = get_exchange_tickers(args.exchange)
    existing    = already_fetched()
    to_fetch    = [t for t in all_tickers if t not in existing]

    print(f"  {args.exchange} total  : {len(all_tickers)}")
    print(f"  Already have : {len(existing)}")
    print(f"  To fetch     : {len(to_fetch)}")

    if args.dry_run:
        print(f"\n[DRY RUN] Would fetch: {to_fetch[:20]}{'...' if len(to_fetch) > 20 else ''}")
        return

    print(f"\nStarting fetch (delay={args.delay}s, end={args.end})...")
    success, failed = [], []
    for i, ticker in enumerate(to_fetch):
        ok = fetch_ticker(ticker, end=args.end)
        (success if ok else failed).append(ticker)
        if i < len(to_fetch) - 1:
            time.sleep(args.delay)

    print(f"\n{'='*50}")
    print(f"Done: {len(success)} fetched, {len(failed)} failed")
    if failed:
        print(f"Failed: {failed[:30]}")
    print(f"Total in data/stock/ now: {len(already_fetched())} tickers")


if __name__ == "__main__":
    main()
