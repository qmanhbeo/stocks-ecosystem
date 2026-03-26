"""
Fetch corporate events (ex-dividend dates) for all 52 VN stocks via vnstock.

Builds: data/features/xs_dividend_calendar.parquet
  Columns: date, ticker, days_to_ex_div, pre_div_window, post_div_window,
            div_count_30d (# of ex-div events in last 30 days across universe)

The dividend calendar provides a clean, forward-looking signal:
  - Pre-dividend (within 21 days): price may run up for dividend capture
  - Post-dividend (within 7 days): price recovery after mechanical ex-date drop
  - Sector dividend clustering: many financials pay at same time — macro effect

Usage:
    conda run -n stocks python data_tools/fetch_dividend_events.py
"""
import time
import json
from pathlib import Path

import numpy as np
import pandas as pd
from vnstock import Vnstock

REPO_ROOT  = Path(__file__).resolve().parents[1]
CACHE_DIR  = REPO_ROOT / "data" / "dividend_cache"
OUT_PATH   = REPO_ROOT / "data" / "features" / "xs_dividend_calendar.parquet"
VNI_PATH   = REPO_ROOT / "data" / "stock" / "gia_lich_su_VNINDEX_1D.parquet"

CACHE_DIR.mkdir(parents=True, exist_ok=True)

TICKERS = [
    "AAA","ACB","ANV","BCG","BID","BVH","CII","CMG","CTD","CTG",
    "DBC","DCM","DGC","DGW","DPM","DXG","EIB","FPT","GAS","GEX",
    "GMD","HCM","HDB","HPG","HSG","KBC","KDH","MBB","MSN","MWG",
    "NLG","NVL","PDR","PLX","PNJ","POW","PVB","REE","SAB","SHB",
    "SSI","STB","TCB","TPB","VCB","VHM","VIC","VJC","VND","VNM",
    "VPB","VRE",
]


def fetch_ticker_events(ticker: str) -> pd.DataFrame | None:
    cache = CACHE_DIR / f"{ticker}_events.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    try:
        stock = Vnstock().stock(symbol=ticker, source="VCI")
        ev = stock.company.events()
        ev["ticker"] = ticker
        ev.to_parquet(cache, index=False)
        return ev
    except Exception as e:
        print(f"    ERROR {ticker}: {e}")
        return None


def extract_dividend_dates(all_events: dict) -> pd.DataFrame:
    """Extract ex-dividend dates from all tickers, build a clean DataFrame."""
    rows = []
    for ticker, ev in all_events.items():
        if ev is None or ev.empty:
            continue
        div_ev = ev[ev["event_list_code"] == "DIV"].copy()
        for _, row in div_ev.iterrows():
            try:
                exright = pd.to_datetime(row.get("exright_date", None))
                if pd.isnull(exright) or exright.year < 2010 or exright.year > 2026:
                    continue
                rows.append({
                    "ticker": ticker,
                    "exright_date": exright,
                    "dividend_value": pd.to_numeric(row.get("value", None), errors="coerce"),
                })
            except Exception:
                continue
    return pd.DataFrame(rows)


def build_calendar(div_df: pd.DataFrame, vni_dates: pd.DatetimeIndex) -> pd.DataFrame:
    """
    For each (date, ticker) on VNINDEX trading days, compute dividend proximity features.
    """
    div_df = div_df.sort_values(["ticker", "exright_date"]).reset_index(drop=True)
    div_dates_ns = div_df["exright_date"].astype(np.int64).values
    div_tickers  = div_df["ticker"].values

    result_rows = []
    for dt in vni_dates:
        dt_ns = dt.value  # nanoseconds since epoch
        dt_ts = pd.Timestamp(dt)

        # Count total ex-div events in last 30 calendar days (market-wide effect)
        window_start = dt_ts - pd.Timedelta(days=30)
        div_count_30d = int(((div_df["exright_date"] >= window_start) &
                             (div_df["exright_date"] < dt_ts)).sum())

        for ticker in TICKERS:
            tmask = div_tickers == ticker
            if not tmask.any():
                continue
            t_dates = div_dates_ns[tmask]

            # Find closest future and past ex-dividend dates
            future_mask = t_dates > dt_ns
            past_mask   = t_dates <= dt_ns

            days_to_next  = int((t_dates[future_mask].min() - dt_ns) // (24 * 3600 * int(1e9))) if future_mask.any() else 999
            days_since_last = int((dt_ns - t_dates[past_mask].max())  // (24 * 3600 * int(1e9))) if past_mask.any() else 999

            pre_div  = 1 if (0 < days_to_next <= 21)  else 0
            post_div = 1 if (0 <= days_since_last <= 7) else 0

            result_rows.append({
                "date":            dt_ts,
                "ticker":          ticker,
                "days_to_ex_div":  days_to_next,
                "days_since_ex_div": days_since_last,
                "pre_div_window":  pre_div,
                "post_div_window": post_div,
                "div_count_30d":   div_count_30d,
            })

    return pd.DataFrame(result_rows)


def main():
    print("=" * 55)
    print("Fetching dividend events for 52 stocks...")
    print("=" * 55)

    all_events = {}
    ok = err = 0
    for i, ticker in enumerate(TICKERS):
        cache = CACHE_DIR / f"{ticker}_events.parquet"
        if cache.exists():
            print(f"  [{i+1:02d}/{len(TICKERS)}] {ticker}: cached")
            all_events[ticker] = pd.read_parquet(cache)
            ok += 1
            continue
        print(f"  [{i+1:02d}/{len(TICKERS)}] {ticker}:", end=" ", flush=True)
        ev = fetch_ticker_events(ticker)
        if ev is not None and not ev.empty:
            print(f"OK ({len(ev)} events)")
            all_events[ticker] = ev
            ok += 1
        else:
            print("EMPTY")
            all_events[ticker] = pd.DataFrame()
            err += 1
        time.sleep(0.3)

    print(f"\nFetch done: {ok} OK, {err} failed/empty")

    print("\nExtracting dividend dates...")
    div_df = extract_dividend_dates(all_events)
    print(f"  Total ex-dividend records: {len(div_df)}")
    print(f"  Tickers with dividends: {div_df['ticker'].nunique()}")
    if not div_df.empty:
        print(f"  Date range: {div_df['exright_date'].min().date()} → {div_df['exright_date'].max().date()}")

    # Load VNINDEX trading dates as spine (2012 onwards)
    vni = pd.read_parquet(VNI_PATH)[["time"]].copy()
    vni["time"] = pd.to_datetime(vni["time"])
    vni = vni[(vni["time"] >= "2012-01-01") & (vni["time"] <= "2026-01-01")]
    vni_dates = pd.DatetimeIndex(vni["time"].sort_values())
    print(f"\nVNINDEX spine: {len(vni_dates):,} trading days ({vni_dates[0].date()} → {vni_dates[-1].date()})")

    # Build per-ticker-per-date calendar (this is O(N*T) — takes a few minutes)
    print("Building dividend calendar (may take 3-5 min)...")
    cal = build_calendar(div_df, vni_dates)
    cal = cal.rename(columns={"date": "time"})

    cal.to_parquet(OUT_PATH, index=False)
    print(f"\nSaved: {OUT_PATH}")
    print(f"  Rows: {len(cal):,}  Tickers: {cal['ticker'].nunique()}")
    print(f"  Date range: {cal['time'].min().date()} → {cal['time'].max().date()}")
    print(f"  Pre-div windows: {cal['pre_div_window'].sum():,} ({cal['pre_div_window'].mean()*100:.1f}% of rows)")
    print(f"  Post-div windows: {cal['post_div_window'].sum():,} ({cal['post_div_window'].mean()*100:.1f}% of rows)")


if __name__ == "__main__":
    main()
