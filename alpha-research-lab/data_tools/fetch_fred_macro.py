"""
Fetch Vietnam macroeconomic data from FRED (Federal Reserve Economic Data).

FRED has 330+ Vietnam data series. This script fetches the most useful ones:
- Interest rates (SBV policy rate)
- CPI inflation
- Exchange rate (official)
- Stock market index (if available)
- Trade balance

All data is quarterly/monthly. Forward-filled to daily and saved as parquet.

FRED API key required: get free key at https://fred.stlouisfed.org/docs/api/api_key.html
Set as FRED_API_KEY environment variable or pass via --api-key argument.

Usage:
    python data_tools/fetch_fred_macro.py
    python data_tools/fetch_fred_macro.py --api-key YOUR_KEY

Output: data/macro/fred_vietnam_macro.parquet
"""
import sys
import os
import argparse
import pandas as pd
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "data" / "macro"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Key FRED series for Vietnam macro analysis
# source: https://fred.stlouisfed.org/categories/32267 (Vietnam)
FRED_SERIES = {
    # Exchange rate
    "DEXVNUS":    "USD/VND_official_daily",        # USD/VND, daily, official rate
    # Interest rates (monthly, from World Bank/IFS)
    "IRSTCI01VNM156N": "vn_deposit_rate_monthly",  # Deposit rate (monthly)
    # CPI inflation
    "VNMCPIALLMINMEI": "vn_cpi_monthly",           # CPI all items, monthly
    # Stock market
    "DDSM01VNM066STSA": "vn_stock_monthly",        # Vietnam stock market index (monthly)
    # Trade
    "XTEXVA01VNM667S":  "vn_exports_quarterly",    # Exports
    "XTIMVA01VNM667S":  "vn_imports_quarterly",    # Imports
    # GDP
    "NGDPRSAXDCVNQ": "vn_gdp_quarterly",           # Real GDP, quarterly
    # Money supply
    "MYAGM2VNM189N": "vn_m2_monthly",              # M2 money supply
}


def fetch_with_fredapi(api_key: str, start: str = "2000-01-01", end: str = "2026-12-31") -> pd.DataFrame:
    """Fetch all FRED series using fredapi library."""
    try:
        from fredapi import Fred
        fred = Fred(api_key=api_key)
    except ImportError:
        print("ERROR: fredapi not installed. Run: pip install fredapi")
        return pd.DataFrame()

    frames = []
    for series_id, alias in FRED_SERIES.items():
        try:
            data = fred.get_series(series_id, observation_start=start, observation_end=end)
            print(f"  {alias:<40} {len(data):>5} obs, {data.index.min().date()} to {data.index.max().date()}")
            df = data.to_frame(name=alias)
            df.index.name = "date"
            frames.append(df)
        except Exception as e:
            print(f"  {alias:<40} ERROR: {e}")

    if not frames:
        return pd.DataFrame()

    result = pd.concat(frames, axis=1)
    return result


def fetch_with_requests(api_key: str, start: str = "2000-01-01", end: str = "2026-12-31") -> pd.DataFrame:
    """Fallback: fetch using requests directly (no fredapi required)."""
    import requests

    base_url = "https://api.stlouisfed.org/fred/series/observations"
    frames = []
    for series_id, alias in FRED_SERIES.items():
        try:
            params = {
                "series_id": series_id,
                "api_key": api_key,
                "file_type": "json",
                "observation_start": start,
                "observation_end": end,
            }
            resp = requests.get(base_url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            obs = data.get("observations", [])
            if not obs:
                print(f"  {alias:<40} NO DATA")
                continue
            df = pd.DataFrame(obs)[["date", "value"]]
            df["date"] = pd.to_datetime(df["date"])
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            df = df.set_index("date").rename(columns={"value": alias})
            frames.append(df)
            print(f"  {alias:<40} {len(df):>5} obs, {df.index.min().date()} to {df.index.max().date()}")
        except Exception as e:
            print(f"  {alias:<40} ERROR: {e}")

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, axis=1)


def build_daily(df: pd.DataFrame) -> pd.DataFrame:
    """Forward-fill macro data to daily frequency."""
    if df.empty:
        return df
    daily_idx = pd.date_range(df.index.min(), pd.Timestamp.today(), freq="D")
    daily = df.reindex(daily_idx, method="ffill")
    daily.index.name = "date"
    return daily


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", type=str, default=os.getenv("FRED_API_KEY", ""),
                        help="FRED API key (or set FRED_API_KEY env var)")
    parser.add_argument("--start", type=str, default="2000-01-01")
    parser.add_argument("--end", type=str, default="2026-12-31")
    args = parser.parse_args()

    if not args.api_key:
        print("ERROR: No FRED API key. Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html")
        print("Set FRED_API_KEY env var or use --api-key argument")
        return

    print("=" * 60)
    print("Fetching Vietnam macro data from FRED")
    print("=" * 60)

    # Try fredapi first, fall back to requests
    try:
        import fredapi
        df = fetch_with_fredapi(args.api_key, args.start, args.end)
    except ImportError:
        print("fredapi not available, using requests...")
        df = fetch_with_requests(args.api_key, args.start, args.end)

    if df.empty:
        print("No data fetched. Check API key and network.")
        return

    daily = build_daily(df)
    output_path = OUT_DIR / "fred_vietnam_macro.parquet"
    daily.to_parquet(output_path)
    print(f"\nSaved {len(daily)} daily rows, {daily.shape[1]} series to {output_path}")
    print(f"Columns: {daily.columns.tolist()}")
    print(f"\nRecent data:")
    print(daily.tail(5).to_string())


if __name__ == "__main__":
    main()
