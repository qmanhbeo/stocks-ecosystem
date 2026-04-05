"""
Fetch quarterly financial ratios for the legacy 52-stock universe and build
cross-sectional daily fundamentals.

Default behavior is safe and incremental:
  - refresh per-ticker caches only when they appear stale for the current quarter
  - merge/dedupe new ratio rows into cache files atomically
  - extend xs_fundamentals_daily.parquet only when caches are unchanged
  - if any cache changed, rebuild the published daily artifact from cache

Use --skip-fetch to trust the current caches and only rebuild/extend the daily output.
Use --force to refetch and merge every ticker cache.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from path_utils import data_path

import pandas as pd
from vnstock import Vnstock

try:
    from stock_refresh_utils import atomic_write_parquet
except ModuleNotFoundError:
    from data_tools.stock_refresh_utils import atomic_write_parquet


REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = data_path("fundamentals_cache")
OUT_PATH = data_path("features/xs_fundamentals_daily.parquet")
VNI_PATH = data_path("stock/gia_lich_su_VNINDEX_1D.parquet")

CACHE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_START = "2012-01-01"
LAG_DAYS = 45
QUARTER_END_MONTH = {1: 3, 2: 6, 3: 9, 4: 12}

TICKERS = [
    "AAA","ACB","ANV","BCG","BID","BVH","CII","CMG","CTD","CTG",
    "DBC","DCM","DGC","DGW","DPM","DXG","EIB","FPT","GAS","GEX",
    "GMD","HCM","HDB","HPG","HSG","KBC","KDH","MBB","MSN","MWG",
    "NLG","NVL","PDR","PLX","PNJ","POW","PVB","REE","SAB","SHB",
    "SSI","STB","TCB","TPB","VCB","VHM","VIC","VJC","VND","VNM",
    "VPB","VRE",
]


def parse_iso_date(value: str) -> pd.Timestamp:
    return pd.Timestamp(value).normalize()


def quarter_end_date(year: int, quarter: int) -> pd.Timestamp:
    month = QUARTER_END_MONTH[quarter]
    return pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)


def normalize_ratio_frame(df: pd.DataFrame | None, ticker: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    frame = df.copy()
    frame.columns = [column[1] if isinstance(column, tuple) else column for column in frame.columns]
    rename = {}
    for column in frame.columns:
        lowered = str(column).lower()
        if "year" in lowered and "report" in lowered:
            rename[column] = "yearReport"
        elif "length" in lowered and "report" in lowered:
            rename[column] = "lengthReport"
    frame = frame.rename(columns=rename)
    frame["ticker"] = ticker
    if "yearReport" in frame.columns:
        frame["yearReport"] = pd.to_numeric(frame["yearReport"], errors="coerce").astype("Int64")
    if "lengthReport" in frame.columns:
        frame["lengthReport"] = pd.to_numeric(frame["lengthReport"], errors="coerce").astype("Int64")
    frame = frame.sort_values(
        [column for column in ["yearReport", "lengthReport"] if column in frame.columns]
    ).reset_index(drop=True)
    return frame


def load_cached_ratios(ticker: str) -> pd.DataFrame | None:
    cache = CACHE_DIR / f"{ticker}_ratios.parquet"
    if not cache.exists():
        return None
    try:
        cached = pd.read_parquet(cache)
    except Exception as exc:
        print(f"    WARN {ticker}: unreadable cached ratios, refetching ({exc})")
        return None
    return normalize_ratio_frame(cached, ticker)


def expected_latest_quarter(as_of_date: pd.Timestamp) -> tuple[int, int] | None:
    candidates: list[tuple[pd.Timestamp, int, int]] = []
    for year in range(as_of_date.year - 2, as_of_date.year + 1):
        for quarter in QUARTER_END_MONTH:
            release = quarter_end_date(year, quarter) + pd.Timedelta(days=LAG_DAYS)
            if release <= as_of_date:
                candidates.append((release, year, quarter))
    if not candidates:
        return None
    _release, year, quarter = max(candidates, key=lambda item: item[0])
    return year, quarter


def cache_covers_expected_quarter(cached: pd.DataFrame | None, as_of_date: pd.Timestamp) -> bool:
    if cached is None or cached.empty or "yearReport" not in cached.columns or "lengthReport" not in cached.columns:
        return False
    expected = expected_latest_quarter(as_of_date)
    if expected is None:
        return True
    year, quarter = expected
    mask = (
        pd.to_numeric(cached["yearReport"], errors="coerce").fillna(-1).astype(int) == year
    ) & (
        pd.to_numeric(cached["lengthReport"], errors="coerce").fillna(-1).astype(int) == quarter
    )
    return bool(mask.any())


def fetch_raw_ratios(ticker: str) -> pd.DataFrame | None:
    try:
        stock = Vnstock().stock(symbol=ticker, source="VCI")
        return normalize_ratio_frame(stock.finance.ratio(period="quarter", lang="en"), ticker)
    except Exception as exc:
        print(f"    ERROR {ticker}: {exc}")
        return None


def fetch_ticker_ratios(ticker: str) -> pd.DataFrame | None:
    cached = load_cached_ratios(ticker)
    if cached is not None and not cached.empty:
        return cached

    fresh = fetch_raw_ratios(ticker)
    if fresh is None or fresh.empty:
        return fresh

    atomic_write_parquet(fresh, CACHE_DIR / f"{ticker}_ratios.parquet")
    return fresh


def merge_ratio_frames(existing: pd.DataFrame | None, incoming: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if existing is None or existing.empty:
        combined = incoming.copy()
    else:
        columns = list(existing.columns)
        for column in incoming.columns:
            if column not in columns:
                columns.append(column)
        existing_aligned = existing.copy()
        incoming_aligned = incoming.copy()
        for column in columns:
            if column not in existing_aligned.columns:
                existing_aligned[column] = pd.NA
            if column not in incoming_aligned.columns:
                incoming_aligned[column] = pd.NA
        combined = pd.concat(
            [existing_aligned[columns], incoming_aligned[columns]],
            ignore_index=True,
        )
    if combined.empty:
        return combined
    combined["ticker"] = ticker
    dedupe_cols = [column for column in ["yearReport", "lengthReport", "ticker"] if column in combined.columns]
    if dedupe_cols:
        combined = combined.drop_duplicates(subset=dedupe_cols, keep="last")
        combined = combined.sort_values(dedupe_cols).reset_index(drop=True)
    else:
        combined = combined.drop_duplicates(keep="last").reset_index(drop=True)
    return combined


def frames_equal(left: pd.DataFrame | None, right: pd.DataFrame | None) -> bool:
    if left is None and right is None:
        return True
    if left is None:
        return right is not None and right.empty
    if right is None:
        return left.empty
    left_frame = left.copy().fillna(pd.NA)
    right_frame = right.copy().fillna(pd.NA)
    columns = sorted(set(left_frame.columns) | set(right_frame.columns))
    for column in columns:
        if column not in left_frame.columns:
            left_frame[column] = pd.NA
        if column not in right_frame.columns:
            right_frame[column] = pd.NA
    left_frame = left_frame[columns].reset_index(drop=True)
    right_frame = right_frame[columns].reset_index(drop=True)
    return left_frame.equals(right_frame)


def ratios_to_daily(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if df.empty or "yearReport" not in df.columns or "lengthReport" not in df.columns:
        return pd.DataFrame()

    pe_col = next((column for column in df.columns if column == "P/E"), None)
    eps_col = next((column for column in df.columns if "EPS" in str(column) and "VND" in str(column)), None)
    roe_col = next((column for column in df.columns if "ROE" in str(column)), None)
    npm_col = next((column for column in df.columns if "Net Profit Margin" in str(column)), None)
    debt_col = next((column for column in df.columns if "Debt" in str(column) and "Equity" in str(column)), None)

    rows = []
    for _, row in df.iterrows():
        try:
            year = int(row["yearReport"])
            quarter = int(row["lengthReport"])
        except (TypeError, ValueError):
            continue
        if quarter not in QUARTER_END_MONTH:
            continue
        release = quarter_end_date(year, quarter) + pd.Timedelta(days=LAG_DAYS)
        payload: dict[str, object] = {
            "release_date": release,
            "year": year,
            "quarter": quarter,
            "ticker": ticker,
        }
        if pe_col:
            payload["pe_ratio"] = pd.to_numeric(row.get(pe_col), errors="coerce")
        if eps_col:
            payload["eps_vnd"] = pd.to_numeric(row.get(eps_col), errors="coerce")
        if roe_col:
            payload["roe"] = pd.to_numeric(row.get(roe_col), errors="coerce")
        if npm_col:
            payload["npm"] = pd.to_numeric(row.get(npm_col), errors="coerce")
        if debt_col:
            payload["debt_eq"] = pd.to_numeric(row.get(debt_col), errors="coerce")
        rows.append(payload)

    if not rows:
        return pd.DataFrame()

    qdf = pd.DataFrame(rows).sort_values(["year", "quarter"]).reset_index(drop=True)
    if "eps_vnd" in qdf.columns:
        qdf["eps_yoy"] = qdf["eps_vnd"].pct_change(4)
    if "roe" in qdf.columns:
        qdf["roe_qoq"] = qdf["roe"].pct_change(1)
    return qdf


def load_vni_dates(start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.DatetimeIndex:
    vni = pd.read_parquet(VNI_PATH, columns=["time"]).copy()
    vni["time"] = pd.to_datetime(vni["time"], errors="coerce").dt.normalize()
    vni = vni.dropna(subset=["time"])
    vni = vni[(vni["time"] >= start_date) & (vni["time"] <= end_date)]
    return pd.DatetimeIndex(vni["time"].sort_values().drop_duplicates())


def build_xs_fundamentals(start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.DataFrame:
    dates = load_vni_dates(start_date, end_date)
    if len(dates) == 0:
        return pd.DataFrame()

    all_q = []
    for ticker in TICKERS:
        cached = load_cached_ratios(ticker)
        qdf = ratios_to_daily(cached if cached is not None else pd.DataFrame(), ticker)
        if not qdf.empty:
            all_q.append(qdf)

    if not all_q:
        return pd.DataFrame()

    all_q_df = pd.concat(all_q, ignore_index=True)
    fund_cols = [
        column
        for column in ["pe_ratio", "eps_vnd", "roe", "npm", "debt_eq", "eps_yoy", "roe_qoq"]
        if column in all_q_df.columns
    ]

    result_rows = []
    all_q_df = all_q_df.sort_values(["ticker", "release_date"]).reset_index(drop=True)

    for dt in dates:
        known = all_q_df[all_q_df["release_date"] <= dt]
        if known.empty:
            continue
        latest = known.groupby("ticker")[fund_cols + ["release_date"]].last().reset_index()
        latest["time"] = dt

        for column, ascending in [
            ("pe_ratio", False),
            ("eps_yoy", True),
            ("roe", True),
            ("npm", True),
            ("debt_eq", False),
        ]:
            if column in latest.columns:
                values = pd.to_numeric(latest[column], errors="coerce")
                latest[f"{column}_rank"] = values.rank(pct=True, ascending=ascending, na_option="keep")

        result_rows.append(latest)

    if not result_rows:
        return pd.DataFrame()
    return pd.concat(result_rows, ignore_index=True)


def load_existing_daily_output() -> pd.DataFrame | None:
    if not OUT_PATH.exists():
        return None
    try:
        frame = pd.read_parquet(OUT_PATH)
    except Exception:
        return None
    frame = frame.copy()
    frame["time"] = pd.to_datetime(frame["time"], errors="coerce").dt.normalize()
    return frame.dropna(subset=["time"]).sort_values(["time", "ticker"]).drop_duplicates(subset=["time", "ticker"], keep="last")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-fetch", action="store_true", help="Skip fetching and rely on current caches")
    parser.add_argument("--force", action="store_true", help="Refresh and merge every ticker cache")
    parser.add_argument("--start", default=DEFAULT_START, help="Inclusive output start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=None, help="Inclusive output end date (default: latest VNINDEX date)")
    args = parser.parse_args()

    start_date = parse_iso_date(args.start)
    vni_all = pd.read_parquet(VNI_PATH, columns=["time"]).copy()
    vni_all["time"] = pd.to_datetime(vni_all["time"], errors="coerce").dt.normalize()
    vni_all = vni_all.dropna(subset=["time"])
    latest_vni_date = vni_all["time"].max().normalize()
    end_date = parse_iso_date(args.end) if args.end else latest_vni_date
    if start_date > end_date:
        raise ValueError("--start must be on or before --end")

    print("=" * 60)
    print("Refreshing quarterly fundamentals caches")
    print("=" * 60)
    print(f"Output window: {start_date.date()} -> {end_date.date()}")

    cache_changed = False
    refreshed = reused = 0

    if not args.skip_fetch:
        for index, ticker in enumerate(TICKERS, start=1):
            cached = load_cached_ratios(ticker)
            should_refresh = args.force or not cache_covers_expected_quarter(cached, end_date)

            if not should_refresh:
                reused += 1
                print(f"  [{index:02d}/{len(TICKERS)}] {ticker}: cache covers expected quarter")
                continue

            fresh = fetch_raw_ratios(ticker)
            if fresh is None or fresh.empty:
                print(f"  [{index:02d}/{len(TICKERS)}] {ticker}: fetch failed or empty, keeping cache")
                time.sleep(0.5)
                continue

            merged = merge_ratio_frames(cached, fresh, ticker)
            if not frames_equal(cached, merged):
                atomic_write_parquet(merged, CACHE_DIR / f"{ticker}_ratios.parquet")
                cache_changed = True
            refreshed += 1
            print(f"  [{index:02d}/{len(TICKERS)}] {ticker}: refreshed ({len(merged)} rows)")
            time.sleep(0.5)
    else:
        print("Skipping fetch, using current caches.")

    print(f"\nCache summary: refreshed={refreshed} reused={reused} changed={cache_changed}")

    existing_daily = load_existing_daily_output()
    if cache_changed or existing_daily is None or existing_daily.empty:
        rebuild_start = start_date
        mode = "full rebuild"
    else:
        existing_max = existing_daily["time"].max().normalize()
        if existing_max >= end_date:
            print(f"Daily fundamentals already current through {existing_max.date()} -> {OUT_PATH}")
            return
        rebuild_start = existing_max + pd.Timedelta(days=1)
        mode = "tail extension"

    print(f"\nBuilding cross-sectional daily fundamentals ({mode}) from {rebuild_start.date()}...")
    tail = build_xs_fundamentals(rebuild_start, end_date)
    if tail.empty:
        print("Nothing to save.")
        return

    if mode == "full rebuild":
        out = tail
    else:
        base = existing_daily[existing_daily["time"] < rebuild_start].copy()
        out = pd.concat([base, tail], ignore_index=True)
        out = out.sort_values(["time", "ticker"]).drop_duplicates(subset=["time", "ticker"], keep="last").reset_index(drop=True)

    atomic_write_parquet(out, OUT_PATH)
    print(f"\nSaved: {OUT_PATH}")
    print(
        f"Rows: {len(out):,}   Tickers: {out['ticker'].nunique()}   "
        f"Date range: {out['time'].min().date()} -> {out['time'].max().date()}"
    )


if __name__ == "__main__":
    main()
