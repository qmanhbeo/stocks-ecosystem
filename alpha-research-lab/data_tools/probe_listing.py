"""
Probe vnstock Listing API to understand the full universe of available Vietnamese stocks.
Also cross-references with what we already have in data/stock/ and checks data quality.
"""
import sys
import io
import pandas as pd
from pathlib import Path
from path_utils import data_path
from vnstock import Listing

# Force UTF-8 output to avoid cp1252 encoding errors on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DATA_DIR = data_path("stock")

def main():
    listing = Listing()

    print("=" * 60)
    print("1. ALL SYMBOLS (filtered to STOCK)")
    print("=" * 60)
    all_syms = listing.all_symbols()
    print(f"Total available: {len(all_syms)}")
    print(f"Columns: {list(all_syms.columns)}")
    # Print only ASCII-safe columns to avoid encoding issues
    safe_cols = [c for c in all_syms.columns if all_syms[c].dtype != object or c in ("ticker", "symbol", "exchange", "comGroupCode")]
    print(all_syms[safe_cols].head(10).to_string())

    print("\n" + "=" * 60)
    print("2. BY EXCHANGE")
    print("=" * 60)
    try:
        by_exchange = listing.symbols_by_exchange()
        print(f"Columns: {list(by_exchange.columns)}")
        if "exchange" in by_exchange.columns:
            print(by_exchange["exchange"].value_counts())
        elif "comGroupCode" in by_exchange.columns:
            print(by_exchange["comGroupCode"].value_counts())
        else:
            print(by_exchange.head(5).to_string())
    except Exception as e:
        print(f"  [WARN] symbols_by_exchange failed: {e}")

    print("\n" + "=" * 60)
    print("3. WHAT WE ALREADY HAVE")
    print("=" * 60)
    existing = sorted([
        p.stem.replace("gia_lich_su_", "").replace("_1D", "")
        for p in DATA_DIR.glob("gia_lich_su_*_1D.parquet")
    ])
    print(f"Already in data/stock/: {len(existing)} tickers")
    print(f"  {existing}")

    print("\n" + "=" * 60)
    print("4. WHAT'S NEW (in listing but not in data/stock/)")
    print("=" * 60)
    if "ticker" in all_syms.columns:
        ticker_col = "ticker"
    elif "symbol" in all_syms.columns:
        ticker_col = "symbol"
    else:
        ticker_col = all_syms.columns[0]

    available = set(all_syms[ticker_col].str.strip().str.upper())
    existing_set = set(t.upper() for t in existing)
    new_tickers = sorted(available - existing_set - {"VNINDEX", "VN30"})
    print(f"New tickers available (not yet fetched): {len(new_tickers)}")
    print(f"  First 30: {new_tickers[:30]}")

    print("\n" + "=" * 60)
    print("5. VOLUME CHECK on existing tickers (2023-2025)")
    print("=" * 60)
    volume_summary = []
    for ticker in existing:
        fpath = DATA_DIR / f"gia_lich_su_{ticker}_1D.parquet"
        if not fpath.exists():
            continue
        try:
            df = pd.read_parquet(fpath)
            df["time"] = pd.to_datetime(df["time"])
            recent = df[df["time"].dt.year >= 2023]
            if len(recent) > 0 and "volume" in recent.columns:
                avg_vol = recent["volume"].mean()
                volume_summary.append({"ticker": ticker, "avg_vol_2023_25": avg_vol})
        except Exception:
            pass

    if volume_summary:
        vol_df = pd.DataFrame(volume_summary).sort_values("avg_vol_2023_25", ascending=False)
        print(f"Top 20 by avg daily volume (2023-2025):")
        print(vol_df.head(20).to_string(index=False))
        median_vol = vol_df["avg_vol_2023_25"].median()
        print(f"\nMedian volume across {len(vol_df)} existing tickers: {median_vol:,.0f}")
        print(f"Suggested liquidity filter for new tickers: > {median_vol*0.5:,.0f} avg daily volume")

if __name__ == "__main__":
    main()
