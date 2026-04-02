"""
Fetch Vietnam macroeconomic data from FRED.

Default behavior is safe and incremental:
  - reuse the existing daily parquet when present
  - fetch only a buffered tail window when the requested end date moves forward
  - extend the daily forward-filled parquet only through the requested end date
  - atomically replace the output after merging

Use --overwrite to force a full rebuild from the requested --start/--end window.

Output: data/macro/fred_vietnam_macro.parquet
"""

from __future__ import annotations

import argparse
import os
from datetime import timedelta
from pathlib import Path

import pandas as pd

try:
    from stock_refresh_utils import atomic_write_parquet, combine_frames, load_existing_frame
except ModuleNotFoundError:
    from data_tools.stock_refresh_utils import atomic_write_parquet, combine_frames, load_existing_frame


REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "data" / "macro"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PATH = OUT_DIR / "fred_vietnam_macro.parquet"
DEFAULT_LOOKBACK_DAYS = 400
DEFAULT_END = pd.Timestamp.today().normalize().date().isoformat()

# source: https://fred.stlouisfed.org/categories/32267 (Vietnam)
FRED_SERIES = {
    "DEXVNUS": "USD/VND_official_daily",
    "IRSTCI01VNM156N": "vn_deposit_rate_monthly",
    "VNMCPIALLMINMEI": "vn_cpi_monthly",
    "DDSM01VNM066STSA": "vn_stock_monthly",
    "XTEXVA01VNM667S": "vn_exports_quarterly",
    "XTIMVA01VNM667S": "vn_imports_quarterly",
    "NGDPRSAXDCVNQ": "vn_gdp_quarterly",
    "MYAGM2VNM189N": "vn_m2_monthly",
}


def parse_iso_date(value: str) -> pd.Timestamp:
    return pd.Timestamp(value).normalize()


def load_existing_daily() -> pd.DataFrame | None:
    existing = load_existing_frame(OUT_PATH)
    if existing is None or existing.empty:
        return None
    existing = existing.copy()
    if "time" not in existing.columns:
        return None
    existing["time"] = pd.to_datetime(existing["time"], errors="coerce").dt.normalize()
    existing = existing.dropna(subset=["time"]).sort_values("time").drop_duplicates(subset=["time"], keep="last")
    return existing.reset_index(drop=True)


def fetch_with_fredapi(api_key: str, start: str, end: str) -> pd.DataFrame:
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
            if len(data) == 0:
                print(f"  {alias:<40} NO DATA")
                continue
            print(f"  {alias:<40} {len(data):>5} obs, {data.index.min().date()} to {data.index.max().date()}")
            df = data.to_frame(name=alias)
            df.index.name = "time"
            frames.append(df)
        except Exception as exc:
            print(f"  {alias:<40} ERROR: {exc}")

    if not frames:
        return pd.DataFrame()
    result = pd.concat(frames, axis=1)
    result.index = pd.to_datetime(result.index).normalize()
    return result.sort_index()


def fetch_with_requests(api_key: str, start: str, end: str) -> pd.DataFrame:
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
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
            observations = (response.json() or {}).get("observations", [])
            if not observations:
                print(f"  {alias:<40} NO DATA")
                continue
            df = pd.DataFrame(observations)[["date", "value"]]
            df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            df = df.dropna(subset=["date"]).set_index("date").rename(columns={"value": alias})
            frames.append(df)
            print(f"  {alias:<40} {len(df):>5} obs, {df.index.min().date()} to {df.index.max().date()}")
        except Exception as exc:
            print(f"  {alias:<40} ERROR: {exc}")

    if not frames:
        return pd.DataFrame()
    result = pd.concat(frames, axis=1)
    result.index.name = "time"
    result.index = pd.to_datetime(result.index).normalize()
    return result.sort_index()


def build_daily(
    observations: pd.DataFrame,
    *,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    seed_row: pd.Series | None,
) -> pd.DataFrame:
    working = observations.copy()
    working.index = pd.to_datetime(working.index).normalize()
    working = working.sort_index()
    working = working[~working.index.duplicated(keep="last")]

    if seed_row is not None:
        seed = seed_row.drop(labels=["time"]).to_frame().T
        seed.index = pd.DatetimeIndex([start_date - pd.Timedelta(days=1)], name="time")
        working = pd.concat([seed, working]).sort_index()
        working = working[~working.index.duplicated(keep="last")]

    if working.empty:
        return pd.DataFrame(columns=["time"])

    full_index = pd.date_range(start_date, end_date, freq="D", name="time")
    daily = (
        working.reindex(working.index.union(full_index))
        .sort_index()
        .ffill()
        .reindex(full_index)
        .reset_index()
    )
    return daily


def extend_existing_forward(existing: pd.DataFrame, end_date: pd.Timestamp) -> pd.DataFrame:
    if existing.empty:
        return existing
    latest_time = pd.to_datetime(existing["time"], errors="coerce").dropna().max()
    if latest_time is None or pd.isna(latest_time) or latest_time.normalize() >= end_date:
        return existing

    last_row = existing.sort_values("time").iloc[-1].copy()
    extension_index = pd.date_range(latest_time.normalize() + pd.Timedelta(days=1), end_date, freq="D")
    if extension_index.empty:
        return existing

    extension = pd.DataFrame([last_row] * len(extension_index))
    extension["time"] = extension_index
    return combine_frames(existing, extension)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--api-key",
        type=str,
        default=os.getenv("FRED_API_KEY", ""),
        help="FRED API key (or set FRED_API_KEY env var)",
    )
    parser.add_argument("--start", type=str, default="2000-01-01")
    parser.add_argument("--end", type=str, default=DEFAULT_END)
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=DEFAULT_LOOKBACK_DAYS,
        help="Buffered lookback window when incrementally extending the daily parquet",
    )
    parser.add_argument("--overwrite", action="store_true", help="Rebuild from the requested --start/--end window")
    args = parser.parse_args()

    if not args.api_key:
        print("ERROR: No FRED API key. Set FRED_API_KEY or use --api-key.")
        return
    if args.lookback_days < 0:
        raise ValueError("--lookback-days must be non-negative")

    requested_start = parse_iso_date(args.start)
    requested_end = parse_iso_date(args.end)
    if requested_start > requested_end:
        raise ValueError("--start must be on or before --end")

    existing = None if args.overwrite else load_existing_daily()
    if existing is not None:
        latest_existing = pd.to_datetime(existing["time"], errors="coerce").dropna().max()
        if latest_existing is not None and latest_existing.normalize() >= requested_end:
            print(f"Already current through {latest_existing.date()} -> {OUT_PATH}")
            return
        fetch_start = max(requested_start, latest_existing.normalize() - pd.Timedelta(days=args.lookback_days))
        seed_row = existing.sort_values("time").iloc[-1]
    else:
        latest_existing = None
        fetch_start = requested_start
        seed_row = None

    print("=" * 60)
    print("Fetching Vietnam macro data from FRED")
    print("=" * 60)
    print(f"Requested window: {requested_start.date()} -> {requested_end.date()}")
    print(f"Fetch window    : {fetch_start.date()} -> {requested_end.date()}")
    print(f"Mode            : {'full rebuild' if args.overwrite else 'incremental merge'}")

    try:
        import fredapi  # noqa: F401

        raw = fetch_with_fredapi(args.api_key, fetch_start.date().isoformat(), requested_end.date().isoformat())
    except ImportError:
        print("fredapi not available, using requests...")
        raw = fetch_with_requests(args.api_key, fetch_start.date().isoformat(), requested_end.date().isoformat())

    if raw.empty:
        if existing is None:
            print("No data fetched. Check API key and network.")
            return
        extended = extend_existing_forward(existing, requested_end)
        if len(extended) != len(existing):
            atomic_write_parquet(extended, OUT_PATH)
            print(f"Extended existing daily file forward to {requested_end.date()} -> {OUT_PATH}")
        else:
            print(f"No new observations returned; keeping existing file current through {latest_existing.date()}")
        return

    daily_tail = build_daily(
        raw,
        start_date=fetch_start,
        end_date=requested_end,
        seed_row=seed_row,
    )
    if daily_tail.empty:
        if existing is None:
            print("No daily data produced.")
            return
        extended = extend_existing_forward(existing, requested_end)
        atomic_write_parquet(extended, OUT_PATH)
        print(f"Extended existing daily file forward to {requested_end.date()} -> {OUT_PATH}")
        return

    if existing is not None:
        base = existing[pd.to_datetime(existing["time"], errors="coerce") < fetch_start].copy()
        combined = combine_frames(base if not base.empty else None, daily_tail)
    else:
        combined = daily_tail

    atomic_write_parquet(combined, OUT_PATH)
    latest_time = pd.to_datetime(combined["time"], errors="coerce").dropna().max()
    print(f"\nSaved {len(combined)} daily rows, {combined.shape[1] - 1} series -> {OUT_PATH}")
    print(f"Latest date: {latest_time.date() if latest_time is not None and not pd.isna(latest_time) else 'n/a'}")


if __name__ == "__main__":
    main()
