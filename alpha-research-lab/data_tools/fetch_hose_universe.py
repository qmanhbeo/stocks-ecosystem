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
from datetime import date
from pathlib import Path

from vnstock import Listing, Vnstock

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR  = REPO_ROOT / "data" / "stock"
EXCLUDE   = {"VNINDEX", "VN30"}
DEFAULT_END = date.today().isoformat()


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


def fetch_ticker(ticker: str, start: str = "2000-01-01", end: str = DEFAULT_END) -> bool:
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


def run_fetch_round(
    tickers: list[str],
    *,
    end: str,
    delay: float,
    round_label: str,
) -> tuple[list[str], list[str]]:
    success: list[str] = []
    failed: list[str] = []

    if not tickers:
        return success, failed

    print(f"\n{round_label} ({len(tickers)} tickers)")
    for i, ticker in enumerate(tickers):
        ok = fetch_ticker(ticker, end=end)
        (success if ok else failed).append(ticker)
        if i < len(tickers) - 1:
            time.sleep(delay)
    return success, failed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exchange", default="HOSE", choices=["HOSE", "HNX", "UPCOM"],
                        help="Exchange to fetch (default: HOSE)")
    parser.add_argument("--delay", type=float, default=0.8,
                        help="Seconds between requests (default: 0.8)")
    parser.add_argument("--dry-run", action="store_true",
                        help="List what would be fetched without actually fetching")
    parser.add_argument("--end", type=str, default=DEFAULT_END,
                        help="Inclusive end date for fetch (default: today)")
    parser.add_argument("--retry-rounds", type=int, default=2,
                        help="Automatic retry rounds for failed tickers after the initial pass (default: 2)")
    parser.add_argument("--retry-delay", type=float, default=1.0,
                        help="Delay between retry rounds in seconds (default: 1.0)")
    args = parser.parse_args()
    if args.retry_rounds < 0:
        raise ValueError("--retry-rounds must be non-negative")
    if args.retry_delay < 0:
        raise ValueError("--retry-delay must be non-negative")

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

    print(f"\nStarting fetch (delay={args.delay}s, retry_rounds={args.retry_rounds}, end={args.end})...")
    success: list[str] = []
    remaining = list(to_fetch)
    for attempt in range(args.retry_rounds + 1):
        round_label = "Initial pass" if attempt == 0 else f"Retry round {attempt}/{args.retry_rounds}"
        round_success, remaining = run_fetch_round(
            remaining,
            end=args.end,
            delay=args.delay,
            round_label=round_label,
        )
        success.extend(round_success)
        if not remaining:
            break
        if attempt < args.retry_rounds and args.retry_delay > 0:
            time.sleep(args.retry_delay)

    failed = remaining

    print(f"\n{'='*50}")
    print(f"Done: {len(success)} fetched, {len(failed)} failed")
    if failed:
        print(f"Failed: {failed[:30]}")
    print(f"Total in data/stock/ now: {len(already_fetched())} tickers")


if __name__ == "__main__":
    main()
