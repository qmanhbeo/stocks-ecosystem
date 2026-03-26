"""
Fetch quarterly financial ratios (P/E, EPS, ROE, debt ratio, etc.) for ALL 52
Vietnamese stocks via vnstock, then build cross-sectional fundamental features.

Output: data/features/xs_fundamentals_daily.parquet
  Columns: date, ticker, pe_ratio, eps_vnd, roe, npm, debt_ratio,
            pe_rank (0-1), eps_yoy_rank, roe_rank  ← within-year cross-sectional ranks

These ranks can be fed directly into cross_sectional_wf.py as additional features,
letting the XS model learn whether cheap/profitable stocks outperform.

Usage:
    conda run -n stocks python data_tools/fetch_all_stock_fundamentals.py
    conda run -n stocks python data_tools/fetch_all_stock_fundamentals.py --skip-fetch
"""
import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd
from vnstock import Vnstock

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = REPO_ROOT / "data" / "fundamentals_cache"
OUT_PATH  = REPO_ROOT / "data" / "features" / "xs_fundamentals_daily.parquet"
VNI_PATH  = REPO_ROOT / "data" / "stock" / "gia_lich_su_VNINDEX_1D.parquet"

CACHE_DIR.mkdir(parents=True, exist_ok=True)

# The 52 stocks in the XS walk-forward universe
TICKERS = [
    "AAA","ACB","ANV","BCG","BID","BVH","CII","CMG","CTD","CTG",
    "DBC","DCM","DGC","DGW","DPM","DXG","EIB","FPT","GAS","GEX",
    "GMD","HCM","HDB","HPG","HSG","KBC","KDH","MBB","MSN","MWG",
    "NLG","NVL","PDR","PLX","PNJ","POW","PVB","REE","SAB","SHB",
    "SSI","STB","TCB","TPB","VCB","VHM","VIC","VJC","VND","VNM",
    "VPB","VRE",
]

LAG_DAYS = 45  # conservative release delay after quarter-end
QUARTER_END_MONTH = {1: 3, 2: 6, 3: 9, 4: 12}


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
        # Flatten multi-level columns
        df.columns = [c[1] if isinstance(c, tuple) else c for c in df.columns]
        # Normalize meta col names
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


def ratios_to_daily(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Convert quarterly ratio rows → daily series with release-date lag."""
    if "yearReport" not in df.columns or "lengthReport" not in df.columns:
        return pd.DataFrame()

    # Find relevant columns
    pe_col  = next((c for c in df.columns if c == "P/E"), None)
    eps_col = next((c for c in df.columns if "EPS" in c and "VND" in c), None)
    roe_col = next((c for c in df.columns if "ROE" in c), None)
    npm_col = next((c for c in df.columns if "Net Profit Margin" in c), None)
    debt_col = next((c for c in df.columns
                     if "Debt" in c and "Equity" in c), None)

    rows = []
    for _, row in df.iterrows():
        try:
            year = int(row["yearReport"])
            q    = int(row["lengthReport"])
        except (ValueError, KeyError):
            continue
        if q not in QUARTER_END_MONTH:
            continue
        release = quarter_end_date(year, q) + pd.Timedelta(days=LAG_DAYS)
        r = {"release_date": release, "year": year, "quarter": q, "ticker": ticker}
        if pe_col:
            r["pe_ratio"] = pd.to_numeric(row.get(pe_col), errors="coerce")
        if eps_col:
            r["eps_vnd"]  = pd.to_numeric(row.get(eps_col), errors="coerce")
        if roe_col:
            r["roe"]      = pd.to_numeric(row.get(roe_col), errors="coerce")
        if npm_col:
            r["npm"]      = pd.to_numeric(row.get(npm_col), errors="coerce")
        if debt_col:
            r["debt_eq"]  = pd.to_numeric(row.get(debt_col), errors="coerce")
        rows.append(r)

    if not rows:
        return pd.DataFrame()

    qdf = pd.DataFrame(rows).sort_values("release_date")

    # YoY EPS growth (same quarter, 4 periods back)
    qdf = qdf.sort_values(["year", "quarter"])
    if "eps_vnd" in qdf.columns:
        qdf["eps_yoy"] = qdf["eps_vnd"].pct_change(4)
    if "roe" in qdf.columns:
        qdf["roe_qoq"] = qdf["roe"].pct_change(1)

    return qdf


def build_xs_fundamentals() -> pd.DataFrame:
    """For each VNINDEX trading date, compute cross-sectional ranks of all tickers."""
    # Load VNINDEX dates as spine
    vni = pd.read_parquet(VNI_PATH)[["time"]].copy()
    vni["time"] = pd.to_datetime(vni["time"])
    vni = vni[vni["time"] >= "2012-01-01"].sort_values("time")
    dates = vni["time"].values

    # Collect all quarterly rows across tickers
    all_q = []
    for ticker in TICKERS:
        qdf = ratios_to_daily(
            pd.read_parquet(CACHE_DIR / f"{ticker}_ratios.parquet")
            if (CACHE_DIR / f"{ticker}_ratios.parquet").exists()
            else pd.DataFrame(),
            ticker
        )
        if not qdf.empty:
            all_q.append(qdf)

    if not all_q:
        print("No data. Run without --skip-fetch first.")
        return pd.DataFrame()

    all_q_df = pd.concat(all_q, ignore_index=True)
    fund_cols = [c for c in ["pe_ratio","eps_vnd","roe","npm","debt_eq","eps_yoy","roe_qoq"]
                 if c in all_q_df.columns]

    # For each date, for each ticker: forward-fill the most recent quarterly obs
    result_rows = []
    all_q_df = all_q_df.sort_values(["ticker", "release_date"])

    for dt in dates:
        # For each ticker, get latest quarterly data released before dt
        known = all_q_df[all_q_df["release_date"] <= dt]
        if known.empty:
            continue
        latest = known.groupby("ticker")[fund_cols + ["release_date"]].last().reset_index()
        latest["date"] = dt

        # Cross-sectional ranks (percentile 0-1, higher = better signal)
        for col, ascending in [("pe_ratio", False),   # low P/E = cheaper = rank high
                                ("eps_yoy", True),     # high EPS growth = rank high
                                ("roe", True),         # high ROE = rank high
                                ("npm", True),         # high margin = rank high
                                ("debt_eq", False)]:   # low debt = rank high
            if col in latest.columns:
                vals = pd.to_numeric(latest[col], errors="coerce")
                ranks = vals.rank(pct=True, ascending=ascending, na_option="keep")
                latest[f"{col}_rank"] = ranks

        result_rows.append(latest)

    if not result_rows:
        return pd.DataFrame()

    out = pd.concat(result_rows, ignore_index=True)
    out = out.rename(columns={"date": "time"})
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-fetch", action="store_true",
                        help="Skip fetching (use cached data only)")
    args = parser.parse_args()

    # ── Step 1: Fetch quarterly ratios ────────────────────────────────────────
    if not args.skip_fetch:
        print("="*60)
        print(f"Fetching quarterly ratios for {len(TICKERS)} stocks...")
        print("="*60)
        ok = err = 0
        for i, ticker in enumerate(TICKERS):
            cache = CACHE_DIR / f"{ticker}_ratios.parquet"
            if cache.exists():
                print(f"  [{i+1:02d}/{len(TICKERS)}] {ticker}: cached")
                ok += 1
                continue
            print(f"  [{i+1:02d}/{len(TICKERS)}] {ticker}:", end=" ", flush=True)
            df = fetch_ticker_ratios(ticker)
            if df is not None and not df.empty:
                print(f"OK ({len(df)} quarters)")
                ok += 1
            else:
                err += 1
            time.sleep(0.5)
        print(f"\nFetch done: {ok} OK, {err} failed")
    else:
        print("Skipping fetch, using cache...")

    # ── Step 2: Build cross-sectional daily fundamentals ──────────────────────
    print("\nBuilding cross-sectional daily fundamentals...")
    df = build_xs_fundamentals()
    if df.empty:
        print("Nothing to save.")
        return

    df.to_parquet(OUT_PATH, index=False)
    print(f"\nSaved: {OUT_PATH}")
    print(f"  Rows: {len(df):,}   Tickers: {df['ticker'].nunique()}   "
          f"Date range: {df['time'].min().date()} → {df['time'].max().date()}")
    print(f"  Columns: {[c for c in df.columns if c not in ['time','ticker','release_date']]}")

    # Quick sanity check
    sample = df[df["ticker"] == "FPT"].tail(3)[
        ["time","pe_ratio","eps_yoy","roe","pe_ratio_rank","eps_yoy_rank","roe_rank"]
    ]
    print(f"\n  FPT sample (recent):\n{sample.to_string(index=False)}")


if __name__ == "__main__":
    main()
