"""
Fetch corporate events (ex-dividend dates) for the legacy 52-stock universe.

Default behavior is safe and incremental:
  - reuse per-ticker cache files when they already cover the requested end date
  - refetch only stale or missing tickers and merge/dedupe into cache
  - rebuild only a rolling tail of xs_dividend_calendar.parquet, not the full file

Use --force to refetch all ticker event caches and rebuild the full calendar window.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from path_utils import data_path

import numpy as np
import pandas as pd
from vnstock import Vnstock

try:
    from stock_refresh_utils import (
        atomic_write_parquet,
        build_probe_cache_entry,
        build_probe_cache_path,
        format_probe_cache_skip_message,
        load_probe_cache,
        probe_cache_record_is_fresh,
        update_probe_cache_state,
    )
except ModuleNotFoundError:
    from data_tools.stock_refresh_utils import (
        atomic_write_parquet,
        build_probe_cache_entry,
        build_probe_cache_path,
        format_probe_cache_skip_message,
        load_probe_cache,
        probe_cache_record_is_fresh,
        update_probe_cache_state,
    )


REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = data_path("dividend_cache")
OUT_PATH = data_path("features/xs_dividend_calendar.parquet")
VNI_PATH = data_path("stock/gia_lich_su_VNINDEX_1D.parquet")

CACHE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_START = "2012-01-01"
ROLLING_LOOKBACK_DAYS = 30
PROBE_CACHE_STATUS_SKIP_ELIGIBLE = {"unchanged", "partial"}

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


def load_cached_events(ticker: str) -> pd.DataFrame | None:
    cache = CACHE_DIR / f"{ticker}_events.parquet"
    if not cache.exists():
        return None
    try:
        frame = pd.read_parquet(cache)
    except Exception as exc:
        print(f"    WARN {ticker}: unreadable cache, refetching ({exc})")
        return None
    if "ticker" not in frame.columns:
        frame = frame.copy()
        frame["ticker"] = ticker
    return frame


def max_cached_exright_date(frame: pd.DataFrame | None) -> pd.Timestamp | None:
    if frame is None or frame.empty or "exright_date" not in frame.columns:
        return None
    exright = pd.to_datetime(frame["exright_date"], errors="coerce").dropna()
    if exright.empty:
        return None
    return exright.max().normalize()


def probe_cache_path() -> Path:
    return build_probe_cache_path(CACHE_DIR, "fetch_dividend_events_probe_cache")


def probe_cache_metadata() -> dict[str, object]:
    return {
        "tool": "fetch_dividend_events",
        "source": "VCI company.events",
    }


def fetch_ticker_events(ticker: str) -> pd.DataFrame | None:
    try:
        stock = Vnstock().stock(symbol=ticker, source="VCI")
        events = stock.company.events()
        events["ticker"] = ticker
        return events
    except Exception as exc:
        print(f"    ERROR {ticker}: {exc}")
        return None


def combine_event_frames(existing: pd.DataFrame | None, incoming: pd.DataFrame | None, ticker: str) -> pd.DataFrame:
    if existing is None or existing.empty:
        combined = incoming.copy() if incoming is not None else pd.DataFrame()
    elif incoming is None or incoming.empty:
        combined = existing.copy()
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
    if "exright_date" in combined.columns:
        combined["exright_date"] = pd.to_datetime(combined["exright_date"], errors="coerce")
    combined = combined.drop_duplicates(keep="last")
    if "exright_date" in combined.columns:
        combined = combined.sort_values(["exright_date"]).reset_index(drop=True)
    return combined


def extract_dividend_dates(all_events: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for ticker, events in all_events.items():
        if events is None or events.empty:
            continue
        if "event_list_code" not in events.columns:
            continue
        div_events = events[events["event_list_code"] == "DIV"].copy()
        for _, row in div_events.iterrows():
            try:
                exright = pd.to_datetime(row.get("exright_date"), errors="coerce")
                if pd.isna(exright):
                    continue
                rows.append(
                    {
                        "ticker": ticker,
                        "exright_date": exright.normalize(),
                        "dividend_value": pd.to_numeric(row.get("value"), errors="coerce"),
                    }
                )
            except Exception:
                continue
    if not rows:
        return pd.DataFrame(columns=["ticker", "exright_date", "dividend_value"])
    return pd.DataFrame(rows).drop_duplicates().sort_values(["ticker", "exright_date"]).reset_index(drop=True)


def build_calendar(div_df: pd.DataFrame, vni_dates: pd.DatetimeIndex) -> pd.DataFrame:
    if div_df.empty or len(vni_dates) == 0:
        return pd.DataFrame(
            columns=[
                "time",
                "ticker",
                "days_to_ex_div",
                "days_since_ex_div",
                "pre_div_window",
                "post_div_window",
                "div_count_30d",
            ]
        )

    div_df = div_df.sort_values(["ticker", "exright_date"]).reset_index(drop=True)
    div_dates_ns = div_df["exright_date"].astype(np.int64).values
    div_tickers = div_df["ticker"].values

    result_rows = []
    for dt in vni_dates:
        dt_ns = dt.value
        dt_ts = pd.Timestamp(dt)
        window_start = dt_ts - pd.Timedelta(days=30)
        div_count_30d = int(((div_df["exright_date"] >= window_start) & (div_df["exright_date"] < dt_ts)).sum())

        for ticker in TICKERS:
            mask = div_tickers == ticker
            if not mask.any():
                continue
            ticker_dates = div_dates_ns[mask]
            future_mask = ticker_dates > dt_ns
            past_mask = ticker_dates <= dt_ns

            days_to_next = (
                int((ticker_dates[future_mask].min() - dt_ns) // (24 * 3600 * int(1e9)))
                if future_mask.any()
                else 999
            )
            days_since_last = (
                int((dt_ns - ticker_dates[past_mask].max()) // (24 * 3600 * int(1e9)))
                if past_mask.any()
                else 999
            )

            result_rows.append(
                {
                    "time": dt_ts,
                    "ticker": ticker,
                    "days_to_ex_div": days_to_next,
                    "days_since_ex_div": days_since_last,
                    "pre_div_window": 1 if 0 < days_to_next <= 21 else 0,
                    "post_div_window": 1 if 0 <= days_since_last <= 7 else 0,
                    "div_count_30d": div_count_30d,
                }
            )

    return pd.DataFrame(result_rows)


def load_vni_dates(start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.DatetimeIndex:
    vni = pd.read_parquet(VNI_PATH, columns=["time"]).copy()
    vni["time"] = pd.to_datetime(vni["time"], errors="coerce").dt.normalize()
    vni = vni.dropna(subset=["time"])
    vni = vni[(vni["time"] >= start_date) & (vni["time"] <= end_date)]
    return pd.DatetimeIndex(vni["time"].sort_values().drop_duplicates())


def load_existing_calendar() -> pd.DataFrame | None:
    if not OUT_PATH.exists():
        return None
    try:
        frame = pd.read_parquet(OUT_PATH)
    except Exception:
        return None
    frame = frame.copy()
    frame["time"] = pd.to_datetime(frame["time"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["time"])
    return frame.sort_values(["time", "ticker"]).drop_duplicates(subset=["time", "ticker"], keep="last")


def combine_calendars(existing: pd.DataFrame | None, tail: pd.DataFrame, rebuild_start: pd.Timestamp) -> pd.DataFrame:
    if tail.empty:
        return existing.copy() if existing is not None else tail.copy()
    if existing is None or existing.empty:
        combined = tail.copy()
    else:
        base = existing[existing["time"] < rebuild_start].copy()
        combined = pd.concat([base, tail], ignore_index=True)
    if combined.empty:
        return combined
    return combined.sort_values(["time", "ticker"]).drop_duplicates(subset=["time", "ticker"], keep="last").reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default=DEFAULT_START, help="Inclusive calendar start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=None, help="Inclusive calendar end date (default: latest VNINDEX date)")
    parser.add_argument("--force", action="store_true", help="Refetch all ticker caches and rebuild the full calendar window")
    parser.add_argument(
        "--probe-cache-ttl-hours",
        type=float,
        default=24.0,
        help="Trust cached no-change/partial probes for this many hours (default: 24; 0 disables)",
    )
    args = parser.parse_args()
    if args.probe_cache_ttl_hours < 0:
        raise ValueError("--probe-cache-ttl-hours must be non-negative")

    start_date = parse_iso_date(args.start)
    vni_all = pd.read_parquet(VNI_PATH, columns=["time"]).copy()
    vni_all["time"] = pd.to_datetime(vni_all["time"], errors="coerce").dt.normalize()
    vni_all = vni_all.dropna(subset=["time"])
    latest_vni_date = vni_all["time"].max().normalize()
    end_date = parse_iso_date(args.end) if args.end else latest_vni_date
    if start_date > end_date:
        raise ValueError("--start must be on or before --end")

    print("=" * 55)
    print("Refreshing dividend events")
    print("=" * 55)
    print(f"Calendar window: {start_date.date()} -> {end_date.date()}")
    print(f"Probe cache TTL: {args.probe_cache_ttl_hours}h")

    probe_cache_enabled = args.probe_cache_ttl_hours > 0
    probe_cache = load_probe_cache(probe_cache_path()) if probe_cache_enabled else {}
    all_events: dict[str, pd.DataFrame] = {}
    reused = refreshed = skipped = probe_cached = 0

    for index, ticker in enumerate(TICKERS, start=1):
        cache_path = CACHE_DIR / f"{ticker}_events.parquet"
        cached = load_cached_events(ticker)
        cached_max = max_cached_exright_date(cached)

        if not args.force and cached is not None and cached_max is not None and cached_max >= end_date:
            all_events[ticker] = cached
            reused += 1
            print(f"  [{index:02d}/{len(TICKERS)}] {ticker}: cached through {cached_max.date()}")
            continue

        if (
            not args.force
            and cached is not None
            and cached_max is not None
            and probe_cache_record_is_fresh(
                probe_cache.get(ticker),
                requested_end=end_date.isoformat(),
                path=cache_path,
                latest_value=cached_max,
                ttl_hours=args.probe_cache_ttl_hours,
                eligible_statuses=PROBE_CACHE_STATUS_SKIP_ELIGIBLE,
            )
        ):
            all_events[ticker] = cached
            probe_cached += 1
            print(f"  [{index:02d}/{len(TICKERS)}] {ticker}: {format_probe_cache_skip_message(probe_cache[ticker])}")
            continue

        incoming = fetch_ticker_events(ticker)
        if incoming is None:
            if cached is not None:
                all_events[ticker] = cached
                reused += 1
            else:
                all_events[ticker] = pd.DataFrame()
                skipped += 1
            continue

        combined = combine_event_frames(cached, incoming, ticker)
        atomic_write_parquet(combined, cache_path)
        all_events[ticker] = combined
        refreshed += 1
        new_max = max_cached_exright_date(combined)
        cache_status = "current"
        if new_max is None or new_max < end_date:
            had_new_rows = False
            if cached is None:
                had_new_rows = not combined.empty
            else:
                had_new_rows = len(combined) > len(cached) or (
                    cached_max is not None and new_max is not None and new_max > cached_max
                )
            cache_status = "partial" if had_new_rows else "unchanged"
        update_probe_cache_state(
            probe_cache_path() if probe_cache_enabled else None,
            probe_cache,
            item_key=ticker,
            entry=build_probe_cache_entry(
                status=cache_status,
                checked_end=end_date.isoformat(),
                path=cache_path,
                latest_value=new_max,
            ),
            metadata=probe_cache_metadata(),
        )
        label = new_max.date().isoformat() if new_max is not None else "no exright date"
        print(f"  [{index:02d}/{len(TICKERS)}] {ticker}: refreshed -> {label}")
        time.sleep(0.3)

    print(
        f"\nTicker cache summary: reused={reused} probe_cached={probe_cached} "
        f"refreshed={refreshed} skipped={skipped}"
    )

    div_df = extract_dividend_dates(all_events)
    existing_calendar = None if args.force else load_existing_calendar()

    if existing_calendar is not None and not existing_calendar.empty:
        existing_max = existing_calendar["time"].max().normalize()
        if existing_max >= end_date and refreshed == 0:
            print(f"Calendar already current through {existing_max.date()} -> {OUT_PATH}")
            return
        rebuild_start = max(start_date, min(existing_max - pd.Timedelta(days=ROLLING_LOOKBACK_DAYS), end_date))
    else:
        rebuild_start = start_date

    vni_dates = load_vni_dates(rebuild_start, end_date)
    tail = build_calendar(div_df, vni_dates)
    combined_calendar = combine_calendars(existing_calendar, tail, rebuild_start)

    atomic_write_parquet(combined_calendar, OUT_PATH)
    print(f"\nSaved: {OUT_PATH}")
    if not combined_calendar.empty:
        print(f"Rows: {len(combined_calendar):,}  Tickers: {combined_calendar['ticker'].nunique()}")
        print(f"Date range: {combined_calendar['time'].min().date()} -> {combined_calendar['time'].max().date()}")


if __name__ == "__main__":
    main()
