"""
Fetch insider + large-shareholder transaction disclosures for all HOSE tickers
from CafeF's GDCoDong endpoint.

Source: https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDCoDong.ashx
  Returns: planned/actual buy/sell volumes + disclosure date for each
           insider/large-shareholder transaction (GDNB + GDCD).

Builds: data/insider_cache/<TICKER>.parquet  (raw per-ticker)
        data/features/xs_insider_deals_raw.parquet  (combined, deduped)

Signal columns in the output:
  - published_date   : date the disclosure was filed (use as signal date)
  - ticker           : stock ticker
  - is_insider       : True if ShareHolderCode starts with CEO_ or LQ_
  - net_plan_vol     : PlanBuyVolume - PlanSellVolume  (announced intention)
  - net_real_vol     : RealBuyVolume - RealSellVolume  (realised)

Usage:
    conda activate stocks
    python data_tools/fetch_insider_deals.py [--force]
"""

import argparse
import re
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = REPO_ROOT / "data" / "insider_cache"
OUT_PATH  = REPO_ROOT / "data" / "features" / "xs_insider_deals_raw.parquet"
FEAT_PATH = REPO_ROOT / "data" / "features" / "xs_insider_deals_raw.parquet"

# Universe source
FEAT_SRC  = REPO_ROOT / "data" / "features" / "xs_barrier_vol_1d_hose_full.parquet"

URL = "https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDCoDong.ashx"
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://cafef.vn/"}
PAGE_SIZE = 500   # CafeF caps at ~500 per request
SLEEP     = 0.2   # polite crawl rate (seconds between requests)


def parse_ms_date(ms_str) -> str | None:
    """Convert CafeF's /Date(1234567890000)/ to YYYY-MM-DD."""
    if not isinstance(ms_str, str):
        return None
    m = re.search(r"(\d+)", ms_str)
    if m:
        return datetime.fromtimestamp(int(m.group(1)) / 1000).strftime("%Y-%m-%d")
    return None


def fetch_ticker(symbol: str) -> pd.DataFrame:
    """Fetch all GDCoDong records for one ticker (handles pagination)."""
    rows = []
    page = 1
    while True:
        params = {
            "Symbol": symbol,
            "StartDate": "01/01/2010",
            "EndDate": "12/31/2030",
            "PageIndex": page,
            "PageSize": PAGE_SIZE,
        }
        try:
            r = requests.get(URL, params=params, headers=HEADERS, timeout=15)
            r.raise_for_status()
            data = r.json()
            chunk = data["Data"]["Data"]
            rows.extend(chunk)
            total = data["Data"]["TotalCount"]
            if len(rows) >= total or not chunk:
                break
            page += 1
        except Exception as e:
            print(f"  WARN: {symbol} page {page}: {e}")
            break

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["ticker"] = symbol

    # Parse dates
    for src, dst in [("PublishedDate", "published_date"),
                     ("OrderDate", "order_date"),
                     ("RealEndDate", "real_end_date")]:
        df[dst] = df[src].apply(parse_ms_date)

    # Insider flag: CEO_ = officers/directors, LQ_ = related persons
    code = df["ShareHolderCode"].fillna("")
    df["is_insider"] = code.str.startswith("CEO_") | code.str.startswith("LQ_")

    # Net volumes
    df["net_plan_vol"] = df["PlanBuyVolume"].fillna(0) - df["PlanSellVolume"].fillna(0)
    df["net_real_vol"] = df["RealBuyVolume"].fillna(0) - df["RealSellVolume"].fillna(0)

    keep = ["ticker", "published_date", "order_date", "real_end_date",
            "TransactionMan", "RelatedManPosition", "TransactionManPosition",
            "ShareHolderCode", "is_insider",
            "net_plan_vol", "net_real_vol",
            "PlanBuyVolume", "PlanSellVolume", "RealBuyVolume", "RealSellVolume",
            "VolumeBeforeTransaction", "VolumeAfterTransaction"]
    keep = [c for c in keep if c in df.columns]
    return df[keep]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                        help="Re-fetch even if cache exists")
    args = parser.parse_args()

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Universe
    feat = pd.read_parquet(FEAT_SRC)
    tickers = sorted(feat["ticker"].unique())
    print(f"Universe: {len(tickers)} tickers")

    all_dfs = []
    skipped = cached = fetched = 0

    for i, sym in enumerate(tickers):
        cache_file = CACHE_DIR / f"{sym}.parquet"

        if cache_file.exists() and not args.force:
            df = pd.read_parquet(cache_file)
            all_dfs.append(df)
            cached += 1
            if (i + 1) % 50 == 0:
                print(f"  [{i+1}/{len(tickers)}] cached={cached} fetched={fetched}")
            continue

        df = fetch_ticker(sym)
        if df.empty:
            skipped += 1
        else:
            df.to_parquet(cache_file, index=False)
            all_dfs.append(df)
            fetched += 1

        if (i + 1) % 20 == 0:
            print(f"  [{i+1}/{len(tickers)}] cached={cached} fetched={fetched} skipped={skipped}")

        time.sleep(SLEEP)

    print(f"\nDone: {cached} cached, {fetched} fetched, {skipped} skipped")

    if not all_dfs:
        print("No data fetched — exiting.")
        return

    combined = pd.concat(all_dfs, ignore_index=True)
    combined = combined[combined["published_date"].notna()]
    combined = combined.sort_values(["published_date", "ticker"]).reset_index(drop=True)

    combined.to_parquet(OUT_PATH, index=False)
    print(f"\nSaved {len(combined):,} rows -> {OUT_PATH}")
    print(f"Date range: {combined['published_date'].min()} -> {combined['published_date'].max()}")
    print(f"Tickers with data: {combined['ticker'].nunique()}")
    print(f"Insider-only rows: {combined['is_insider'].sum():,} / {len(combined):,}")


if __name__ == "__main__":
    main()
