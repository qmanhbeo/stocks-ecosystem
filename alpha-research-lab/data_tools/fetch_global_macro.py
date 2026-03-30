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
        combine_frames,
        load_existing_frame,
        plan_refresh,
    )
except ModuleNotFoundError:
    from data_tools.stock_refresh_utils import (
        atomic_write_parquet,
        combine_frames,
        load_existing_frame,
        plan_refresh,
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

START = "2000-01-01"
END   = "2026-12-31"


def fetch_one(ticker: str, alias: str, overwrite: bool) -> bool:
    out = OUT_DIR / f"fx_commodities_{alias}_1D.parquet"
    existing = load_existing_frame(out)
    try:
        plan = plan_refresh(out, "1D", START, END, full_refresh=overwrite)
        if plan.mode == "skip":
            print(f"  SKIP {alias} ({plan.message})")
            return True

        print(f"  Fetching {ticker} ({alias}, {plan.message})...", end=" ", flush=True)
        df = yf.download(ticker, start=plan.fetch_start, end=END, progress=False, auto_adjust=True)
        if df.empty:
            if existing is not None:
                print("NO NEW DATA (keeping existing file)")
                return True
            print("NO DATA")
            return False
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
        if plan.mode == "incremental":
            added_rows = len(combined) - before_rows
            if added_rows > 0:
                print(f"OK (appended {added_rows} rows, latest {latest_time})")
            else:
                print(f"OK (refreshed overlap window, latest {latest_time})")
        else:
            print(f"OK ({len(combined)} rows)")
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    print("=" * 55)
    print("Fetching new global macro / risk tickers")
    print("=" * 55)
    ok = err = 0
    for ticker, alias in TICKERS.items():
        if fetch_one(ticker, alias, args.overwrite):
            ok += 1
        else:
            err += 1
        time.sleep(0.5)

    print(f"\nDone: {ok} OK, {err} failed")
    print(f"Output: {OUT_DIR}")


if __name__ == "__main__":
    main()
