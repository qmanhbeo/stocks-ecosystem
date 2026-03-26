"""
Refresh all existing stock files with latest data (including 2026).

Reads the list of already-fetched tickers from data/stock/, then re-fetches
each one using vnstock VCI source.

Usage:
    conda run -n stocks python data_tools/fetch_refresh_all.py
    conda run -n stocks python data_tools/fetch_refresh_all.py --dry-run
    conda run -n stocks python data_tools/fetch_refresh_all.py --skip-updated-since 2026-03-18T20:00
"""
import argparse
import socket
import time
from datetime import datetime
from pathlib import Path
from vnstock import Vnstock

# Hard timeout on all socket operations — prevents hanging on unresponsive tickers
socket.setdefaulttimeout(30)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR  = REPO_ROOT / "data" / "stock"
EXCLUDE   = {"VNINDEX", "VN30"}


def get_existing_tickers(skip_updated_since: datetime | None = None) -> list[str]:
    tickers = []
    for p in sorted(DATA_DIR.glob("gia_lich_su_*_1D.parquet")):
        t = p.stem.replace("gia_lich_su_", "").replace("_1D", "").upper()
        if t in EXCLUDE:
            continue
        if skip_updated_since is not None:
            mtime = datetime.fromtimestamp(p.stat().st_mtime)
            if mtime >= skip_updated_since:
                continue
        tickers.append(t)
    return tickers


def fetch_ticker(ticker: str, start: str, end: str) -> bool:
    fpath = DATA_DIR / f"gia_lich_su_{ticker}_1D.parquet"
    try:
        stock = Vnstock().stock(symbol=ticker, source="VCI")
        df = stock.quote.history(start=start, end=end, interval="1D")
        if len(df) == 0:
            print(f"  {ticker}: no data returned")
            return False
        df.to_parquet(fpath, index=False)
        print(f"  {ticker}: {len(df)} rows saved")
        return True
    except Exception as e:
        err = str(e).encode("ascii", errors="replace").decode("ascii")
        print(f"  {ticker}: ERROR -- {err[:120]}")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start",   default="2000-01-01")
    parser.add_argument("--end",     default="2026-12-31")
    parser.add_argument("--delay",   type=float, default=0.3)
    parser.add_argument("--skip-updated-since",
                        help="Skip files modified after this datetime (e.g. 2026-03-18T20:00)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    skip_dt = None
    if args.skip_updated_since:
        skip_dt = datetime.fromisoformat(args.skip_updated_since)

    tickers = get_existing_tickers(skip_updated_since=skip_dt)
    total_files = len(list(DATA_DIR.glob("gia_lich_su_*_1D.parquet")))
    skipped = total_files - len(tickers) - len(EXCLUDE)

    print(f"Refreshing {len(tickers)} tickers ({args.start} to {args.end})")
    if skip_dt:
        print(f"Skipping {skipped} already updated since {skip_dt}")
    print(f"Delay: {args.delay}s | Socket timeout: 30s")

    if args.dry_run:
        print(f"[DRY RUN] First 10: {tickers[:10]}")
        return

    success, failed = [], []
    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}] ", end="", flush=True)
        ok = fetch_ticker(ticker, args.start, args.end)
        (success if ok else failed).append(ticker)
        if i < len(tickers):
            time.sleep(args.delay)

    print(f"\n{'='*50}")
    print(f"Done: {len(success)} refreshed, {len(failed)} failed")
    if failed:
        print(f"Failed: {failed}")


if __name__ == "__main__":
    main()
