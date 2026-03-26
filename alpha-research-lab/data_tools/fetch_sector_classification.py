"""
Fetch ICB sector classification for all HOSE stocks via vnstock company.overview().

Outputs: data/features/sector_classification.parquet
Columns: symbol, icb_name2, icb_name3, icb_name4

Usage:
    conda run -n stocks python data_tools/fetch_sector_classification.py
    conda run -n stocks python data_tools/fetch_sector_classification.py --delay 0.3 --dry-run
"""
import sys
import io
import argparse
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from vnstock import Listing, Vnstock
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH  = REPO_ROOT / "data" / "features" / "sector_classification.parquet"
STOCK_DIR = REPO_ROOT / "data" / "stock"


def get_hose_tickers() -> list[str]:
    listing = Listing()
    df = listing.symbols_by_exchange()
    hose = df[df['exchange'].str.upper() == 'HOSE'] if 'exchange' in df.columns else df
    tickers = hose['symbol'].dropna().unique().tolist()
    return sorted(tickers)


def fetch_sector(symbol: str) -> dict:
    """Fetch ICB sector fields for one symbol. Returns dict with symbol + sector cols."""
    try:
        s = Vnstock().stock(symbol=symbol, source='VCI')
        ov = s.company.overview()
        if isinstance(ov, pd.DataFrame) and len(ov) > 0:
            row = ov.iloc[0]
            return {
                'symbol':    symbol,
                'icb_name2': str(row.get('icb_name2', '')).strip(),
                'icb_name3': str(row.get('icb_name3', '')).strip(),
                'icb_name4': str(row.get('icb_name4', '')).strip(),
            }
    except Exception as e:
        print(f"  ERROR {symbol}: {e}")
    return {'symbol': symbol, 'icb_name2': '', 'icb_name3': '', 'icb_name4': ''}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--delay',   type=float, default=0.4,  help='Seconds between API calls')
    parser.add_argument('--dry-run', action='store_true',       help='Fetch first 5 tickers only')
    args = parser.parse_args()

    # Only fetch stocks we actually have price data for
    # Files are named: gia_lich_su_{SYM}_1D.parquet
    available = set()
    for f in STOCK_DIR.glob('gia_lich_su_*_1D.parquet'):
        sym = f.stem.replace('gia_lich_su_', '').replace('_1D', '')
        available.add(sym)
    hose = get_hose_tickers()
    tickers = [t for t in hose if t in available]
    print(f"HOSE tickers with price data: {len(tickers)}")

    if args.dry_run:
        tickers = tickers[:5]
        print(f"DRY RUN: fetching first {len(tickers)}")

    records = []
    for i, sym in enumerate(tickers):
        rec = fetch_sector(sym)
        records.append(rec)
        print(f"  [{i+1}/{len(tickers)}] {sym}: {rec['icb_name3'] or rec['icb_name2'] or '?'}")
        if args.delay > 0 and i < len(tickers) - 1:
            time.sleep(args.delay)

    df = pd.DataFrame(records)
    df = df.replace('nan', '').replace('None', '')
    print(f"\nTotal records: {len(df)}")
    if len(df) > 0 and 'icb_name2' in df.columns:
        print(df['icb_name2'].value_counts().head(20))
        print(df['icb_name3'].value_counts().head(30))

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PATH, index=False)
    print(f"\nSaved: {OUT_PATH}")


if __name__ == '__main__':
    main()
