"""
Build earnings quality cross-sectional features for all 394 HOSE tickers (H109).

Extends the 52-ticker fundamentals fetch to the full universe. New features:
- EPS acceleration (2nd derivative of YoY growth: is growth speeding up?)
- Net margin trend (3-quarter rolling slope)
- ROE quarter-over-quarter change
- Debt trend (YoY D/E ratio change)

These trend/acceleration features capture earnings momentum orthogonal to price,
and are distinct from the raw P/E level tested at 52 tickers (IC −0.024).

Input:  data/fundamentals_cache/{TICKER}_ratios.parquet  (fetches if missing)
Output: data/features/xs_earnings_quality_daily.parquet
  Columns: time, ticker,
    xs_eps_accel_rank    — cross-sectional rank of EPS acceleration
    xs_eps_yoy_rank      — cross-sectional rank of EPS YoY growth
    xs_npm_trend_rank    — rank of 3-quarter net margin slope
    xs_roe_delta_rank    — rank of quarter-over-quarter ROE change
    xs_debt_trend_rank   — rank of D/E YoY change (lower debt growth = higher rank)

Usage:
    # Fetch + build (394 tickers, ~5 min)
    conda run -n stocks python data_tools/build_earnings_quality_features.py

    # Build from cache only (if already fetched)
    conda run -n stocks python data_tools/build_earnings_quality_features.py --skip-fetch
"""

from __future__ import annotations

import argparse
import glob
import time
from pathlib import Path
from path_utils import data_path

import numpy as np
import pandas as pd
from vnstock import Vnstock

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = data_path("fundamentals_cache")
OUT_PATH = data_path("features/xs_earnings_quality_daily.parquet")
VNI_PATH = data_path("stock/gia_lich_su_VNINDEX_1D.parquet")
STOCK_DIR = data_path("stock")
EXCLUDE = {"VNINDEX", "VN30"}

CACHE_DIR.mkdir(parents=True, exist_ok=True)

LAG_DAYS = 45
QUARTER_END_MONTH = {1: 3, 2: 6, 3: 9, 4: 12}


def get_all_tickers() -> list[str]:
    files = sorted(glob.glob(str(STOCK_DIR / "gia_lich_su_*_1D.parquet")))
    return [
        Path(f).stem.replace("gia_lich_su_", "").replace("_1D", "")
        for f in files
        if Path(f).stem.replace("gia_lich_su_", "").replace("_1D", "") not in EXCLUDE
    ]


def quarter_end_date(year: int, q: int) -> pd.Timestamp:
    month = QUARTER_END_MONTH[q]
    return pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)


def fetch_ticker_ratios(ticker: str) -> pd.DataFrame | None:
    cache = CACHE_DIR / f"{ticker}_ratios.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    try:
        stock = Vnstock().stock(symbol=ticker, source="VCI")
        df = stock.finance.ratio(period="quarter", lang="en")
        df.columns = [c[1] if isinstance(c, tuple) else c for c in df.columns]
        rename = {}
        for c in df.columns:
            cl = c.lower()
            if "year" in cl and "report" in cl:
                rename[c] = "yearReport"
            elif "length" in cl and "report" in cl:
                rename[c] = "lengthReport"
        df = df.rename(columns=rename)
        df["ticker"] = ticker
        df.to_parquet(cache, index=False)
        return df
    except Exception as e:
        print(f"    ERROR {ticker}: {e}")
        return None


def ratios_to_quarterly(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Extract quarterly fundamental metrics with release-date lag."""
    if df is None or df.empty:
        return pd.DataFrame()
    if "yearReport" not in df.columns or "lengthReport" not in df.columns:
        return pd.DataFrame()

    eps_col = next((c for c in df.columns if "EPS" in c and "VND" in c), None)
    roe_col = next((c for c in df.columns if "ROE" in c), None)
    npm_col = next((c for c in df.columns if "Net Profit Margin" in c), None)
    debt_col = next((c for c in df.columns if "Debt" in c and "Equity" in c), None)

    rows = []
    for _, row in df.iterrows():
        try:
            year = int(row["yearReport"])
            q = int(row["lengthReport"])
        except (ValueError, KeyError):
            continue
        if q not in QUARTER_END_MONTH:
            continue
        release = quarter_end_date(year, q) + pd.Timedelta(days=LAG_DAYS)
        r = {"release_date": release, "year": year, "quarter": q, "ticker": ticker}
        if eps_col:
            r["eps_vnd"] = pd.to_numeric(row.get(eps_col), errors="coerce")
        if roe_col:
            r["roe"] = pd.to_numeric(row.get(roe_col), errors="coerce")
        if npm_col:
            r["npm"] = pd.to_numeric(row.get(npm_col), errors="coerce")
        if debt_col:
            r["debt_eq"] = pd.to_numeric(row.get(debt_col), errors="coerce")
        rows.append(r)

    if not rows:
        return pd.DataFrame()

    qdf = pd.DataFrame(rows).sort_values(["year", "quarter"])

    # Derived features
    if "eps_vnd" in qdf.columns:
        qdf["eps_yoy"] = qdf["eps_vnd"].pct_change(4)            # YoY growth
        qdf["eps_accel"] = qdf["eps_yoy"].diff(1)                # Acceleration (2nd derivative)
    if "roe" in qdf.columns:
        qdf["roe_delta"] = qdf["roe"].diff(1)                    # QoQ change
    if "npm" in qdf.columns:
        # 3-quarter rolling linear slope proxy: (npm_t - npm_{t-2}) / 2
        qdf["npm_trend"] = qdf["npm"].diff(2) / 2
    if "debt_eq" in qdf.columns:
        qdf["debt_yoy"] = qdf["debt_eq"].pct_change(4)           # YoY debt change

    return qdf.sort_values("release_date")


def build_xs_quality(all_q_df: pd.DataFrame, dates: np.ndarray) -> pd.DataFrame:
    """For each VNINDEX trading date, compute cross-sectional quality ranks."""
    quality_cols = ["eps_accel", "eps_yoy", "npm_trend", "roe_delta", "debt_yoy"]
    fund_cols = [c for c in quality_cols if c in all_q_df.columns]

    all_q_df = all_q_df.sort_values(["ticker", "release_date"])
    result_rows = []

    for dt in dates:
        known = all_q_df[all_q_df["release_date"] <= dt]
        if known.empty:
            continue
        latest = known.groupby("ticker")[fund_cols + ["release_date"]].last().reset_index()
        if len(latest) < 10:
            continue
        latest["time"] = dt

        # Cross-sectional percentile ranks
        rank_specs = [
            ("eps_accel", True, "xs_eps_accel_rank"),
            ("eps_yoy", True, "xs_eps_yoy_rank"),
            ("npm_trend", True, "xs_npm_trend_rank"),
            ("roe_delta", True, "xs_roe_delta_rank"),
            ("debt_yoy", False, "xs_debt_trend_rank"),  # lower debt growth = better
        ]
        for col, ascending, rank_col in rank_specs:
            if col in latest.columns:
                vals = pd.to_numeric(latest[col], errors="coerce")
                latest[rank_col] = vals.rank(pct=True, ascending=ascending, na_option="keep")

        result_rows.append(latest)

    if not result_rows:
        return pd.DataFrame()

    out = pd.concat(result_rows, ignore_index=True)
    rank_cols = [r[2] for r in rank_specs if r[0] in all_q_df.columns]
    keep = ["time", "ticker"] + rank_cols
    return out[[c for c in keep if c in out.columns]]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-fetch", action="store_true", help="Use cached data only")
    args = parser.parse_args()

    tickers = get_all_tickers()
    print(f"Target tickers: {len(tickers)}")

    if not args.skip_fetch:
        missing = [t for t in tickers if not (CACHE_DIR / f"{t}_ratios.parquet").exists()]
        print(f"Fetching {len(missing)} tickers (skipping {len(tickers) - len(missing)} cached)...")
        ok = err = 0
        for i, ticker in enumerate(missing):
            result = fetch_ticker_ratios(ticker)
            if result is not None:
                ok += 1
            else:
                err += 1
            time.sleep(3.5)
            if (i + 1) % 20 == 0:
                print(f"  {i+1}/{len(missing)} fetched ({ok} ok, {err} err)")
        print(f"Fetch complete: {ok} ok, {err} errors")

    print("Building quarterly feature rows...")
    all_q = []
    for ticker in tickers:
        cache = CACHE_DIR / f"{ticker}_ratios.parquet"
        if not cache.exists():
            continue
        try:
            raw = pd.read_parquet(cache)
            qdf = ratios_to_quarterly(raw, ticker)
            if not qdf.empty:
                all_q.append(qdf)
        except Exception:
            continue

    print(f"  {len(all_q)} tickers with valid fundamental data")
    if not all_q:
        print("No data available.")
        return

    all_q_df = pd.concat(all_q, ignore_index=True)
    print(f"  Total quarterly rows: {len(all_q_df):,}")

    # Load VNINDEX trading dates as spine
    vni = pd.read_parquet(VNI_PATH)[["time"]].copy()
    vni["time"] = pd.to_datetime(vni["time"])
    dates = vni[vni["time"] >= "2012-01-01"].sort_values("time")["time"].values

    print(f"Building cross-sectional quality ranks for {len(dates)} trading dates...")
    feat = build_xs_quality(all_q_df, dates)

    if feat.empty:
        print("No output generated.")
        return

    print(f"Output: {len(feat):,} rows, {feat['ticker'].nunique()} tickers")
    feat.to_parquet(OUT_PATH, index=False)
    print(f"Saved -> {OUT_PATH}")

    for col in [c for c in feat.columns if c.startswith("xs_")]:
        nz = feat[col].notna().sum()
        print(f"  {col}: {nz:,} non-null ({100*nz/len(feat):.1f}%)")


if __name__ == "__main__":
    main()
