"""
Fetch open historical intraday data from CafeF MatchPrice and aggregate it into
repo-style intraday OHLCV bars.

CafeF exposes a public per-day MatchPrice endpoint with individual matched trades.
This script uses the existing 1D stock files as the trading calendar, fetches the
raw public session data day by day, then aggregates it into hourly bars.

Default output uses a source-specific suffix so it can coexist with vnstock / SSI:
    data/stock/gia_lich_su_<TICKER>_1H_CAFEF.parquet

To make long-range fetches resumable, the script first writes complete yearly
parts under:
    data/stock/_cafef_intraday_parts/<INTERVAL_LABEL>/<TICKER>/

Only years that finish without unresolved request failures are written as parts.
The final ticker parquet is then rebuilt by concatenating the saved yearly parts.

Examples:
    conda run -n stocks python data_tools/fetch_cafef_intraday.py --dry-run
    conda run -n stocks python data_tools/fetch_cafef_intraday.py --tickers FPT,ACB --start 2019-01-01 --end 2025-12-31
    conda run -n stocks python data_tools/fetch_cafef_intraday.py --tickers FPT --start 2024-06-20 --end 2024-06-21 --interval-label 1H
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import threading
import time
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from path_utils import data_path
from typing import Callable, Iterable

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = data_path("stock")
DATA_DIR.mkdir(parents=True, exist_ok=True)

MATCH_PRICE_URL = "https://msh-appdata.cafef.vn/rest-api/api/v1/MatchPrice"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; stocks-alpha-research/1.0)",
    "Referer": "https://cafef.vn/",
    "Accept": "application/json",
}
UNIVERSE_INTERVAL = "1D"
DEFAULT_INTERVAL_LABEL = "1H_CAFEF"
DEFAULT_TIMEOUT = 20
DEFAULT_DELAY = 0.0
DEFAULT_RETRY_ROUNDS = 2
DEFAULT_RETRY_DELAY = 1.0
DEFAULT_WORKERS = 8
DEFAULT_PARTS_DIR = DATA_DIR / "_cafef_intraday_parts"
METADATA_SUFFIX = ".meta.json"
EXCLUDE = {"VNINDEX", "VN30"}
BAR_COLUMNS = ["time", "open", "high", "low", "close", "volume"]


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=5,
        read=5,
        connect=5,
        status=5,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.headers.update(HEADERS)
    return session


def build_parser(*, include_tickers: bool = True, description: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=description or "Fetch open historical intraday data from CafeF MatchPrice"
    )
    if include_tickers:
        parser.add_argument(
            "--tickers",
            type=str,
            help="Comma-separated tickers. Defaults to the existing 1D stock universe under data/stock/",
        )
    parser.add_argument("--start", type=str, default="2015-01-01", help="Start date in YYYY-MM-DD")
    parser.add_argument("--end", type=str, default=date.today().isoformat(), help="End date in YYYY-MM-DD")
    parser.add_argument(
        "--interval-label",
        type=str,
        default=DEFAULT_INTERVAL_LABEL,
        help=f"Output file suffix label (default: {DEFAULT_INTERVAL_LABEL})",
    )
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help="Delay between date requests in seconds")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTP timeout in seconds")
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Parallel date-fetch workers per ticker-year (default: {DEFAULT_WORKERS})",
    )
    parser.add_argument(
        "--retry-rounds",
        type=int,
        default=DEFAULT_RETRY_ROUNDS,
        help="Automatic retry rounds for failed date requests after the initial pass (default: 2)",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=DEFAULT_RETRY_DELAY,
        help="Delay between retry rounds in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--parts-dir",
        type=str,
        default=str(DEFAULT_PARTS_DIR),
        help=f"Directory for yearly CafeF part files (default: {DEFAULT_PARTS_DIR})",
    )
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing output files and yearly parts")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be fetched without hitting CafeF")
    return parser


def parse_args(argv: list[str] | None = None, *, include_tickers: bool = True) -> argparse.Namespace:
    parser = build_parser(include_tickers=include_tickers)
    return parser.parse_args(argv)


def parse_iso_date(value: str) -> date:
    return datetime.fromisoformat(value).date()


def empty_bar_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": pd.Series(dtype="datetime64[ns]"),
            "open": pd.Series(dtype="float64"),
            "high": pd.Series(dtype="float64"),
            "low": pd.Series(dtype="float64"),
            "close": pd.Series(dtype="float64"),
            "volume": pd.Series(dtype="int64"),
        }
    )


def get_universe_tickers() -> list[str]:
    tickers = []
    for path in sorted(DATA_DIR.glob(f"gia_lich_su_*_{UNIVERSE_INTERVAL}.parquet")):
        ticker = path.stem.replace("gia_lich_su_", "").replace(f"_{UNIVERSE_INTERVAL}", "").upper()
        if ticker in EXCLUDE:
            continue
        tickers.append(ticker)
    return tickers


def resolve_tickers(raw: str | None) -> list[str]:
    if raw:
        tickers = [ticker.strip().upper() for ticker in raw.split(",") if ticker.strip()]
        if not tickers:
            raise ValueError("No tickers were parsed from --tickers")
        return tickers
    tickers = get_universe_tickers()
    if not tickers:
        raise RuntimeError("No existing 1D stock files found under data/stock/ to define the fetch universe")
    return tickers


def build_daily_path(ticker: str) -> Path:
    return DATA_DIR / f"gia_lich_su_{ticker}_{UNIVERSE_INTERVAL}.parquet"


def build_output_path(ticker: str, interval_label: str) -> Path:
    return DATA_DIR / f"gia_lich_su_{ticker}_{interval_label}.parquet"


def build_parts_root(parts_dir: Path, interval_label: str, ticker: str) -> Path:
    root = parts_dir / interval_label / ticker
    root.mkdir(parents=True, exist_ok=True)
    return root


def build_year_part_path(parts_dir: Path, ticker: str, interval_label: str, year: int) -> Path:
    return build_parts_root(parts_dir, interval_label, ticker) / f"gia_lich_su_{ticker}_{interval_label}_{year}.parquet"


def build_year_metadata_path(parts_dir: Path, ticker: str, interval_label: str, year: int) -> Path:
    return build_parts_root(parts_dir, interval_label, ticker) / f"gia_lich_su_{ticker}_{interval_label}_{year}{METADATA_SUFFIX}"


def load_trading_dates(ticker: str, start_date: date, end_date: date) -> list[date]:
    path = build_daily_path(ticker)
    if not path.exists():
        raise RuntimeError(f"Missing daily source file for {ticker}: {path}")
    daily = pd.read_parquet(path, columns=["time"])
    trading_dates = pd.to_datetime(daily["time"], errors="coerce").dropna().dt.date.tolist()
    return [d for d in sorted(dict.fromkeys(trading_dates)) if start_date <= d <= end_date]


def group_dates_by_year(trading_dates: Iterable[date]) -> dict[int, list[date]]:
    grouped: dict[int, list[date]] = defaultdict(list)
    for trading_date in trading_dates:
        grouped[trading_date.year].append(trading_date)
    return dict(sorted(grouped.items()))


def build_dates_signature(trading_dates: Iterable[date]) -> str:
    payload = ",".join(trading_date.isoformat() for trading_date in trading_dates)
    return hashlib.sha1(payload.encode("ascii")).hexdigest()


def format_optional_timestamp(value: pd.Timestamp | None) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).isoformat()


def build_year_metadata(
    ticker: str,
    interval_label: str,
    year: int,
    trading_dates: list[date],
    year_frame: pd.DataFrame,
) -> dict[str, object]:
    first_bar_time = year_frame["time"].min() if not year_frame.empty else None
    last_bar_time = year_frame["time"].max() if not year_frame.empty else None
    bar_dates = (
        int(pd.to_datetime(year_frame["time"]).dt.normalize().nunique())
        if not year_frame.empty
        else 0
    )
    return {
        "ticker": ticker,
        "interval_label": interval_label,
        "year": year,
        "requested_trading_days": len(trading_dates),
        "requested_dates_signature": build_dates_signature(trading_dates),
        "first_requested_date": trading_dates[0].isoformat() if trading_dates else None,
        "last_requested_date": trading_dates[-1].isoformat() if trading_dates else None,
        "bars": int(len(year_frame)),
        "bar_dates": bar_dates,
        "observed_empty": bool(year_frame.empty),
        "first_bar_time": format_optional_timestamp(first_bar_time),
        "last_bar_time": format_optional_timestamp(last_bar_time),
        "written_at_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


def load_year_metadata(metadata_path: Path) -> dict[str, object] | None:
    if not metadata_path.exists():
        return None
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def write_year_metadata(metadata_path: Path, metadata: dict[str, object]) -> None:
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def metadata_matches_requested_calendar(metadata: dict[str, object], trading_dates: list[date]) -> bool:
    if not trading_dates:
        return False
    return (
        metadata.get("requested_trading_days") == len(trading_dates)
        and metadata.get("requested_dates_signature") == build_dates_signature(trading_dates)
        and metadata.get("first_requested_date") == trading_dates[0].isoformat()
        and metadata.get("last_requested_date") == trading_dates[-1].isoformat()
    )


def should_refresh_year_part(
    part_path: Path,
    metadata_path: Path,
    year: int,
    latest_requested_year: int,
    trading_dates: list[date],
    overwrite: bool,
) -> tuple[bool, str]:
    if overwrite:
        return True, "overwrite requested"
    if not part_path.exists():
        return True, "yearly part missing"

    metadata = load_year_metadata(metadata_path)
    if metadata is None:
        if year == latest_requested_year:
            return True, "latest requested year metadata missing"
        return False, "legacy yearly part exists without metadata, reusing historical cache"

    if metadata_matches_requested_calendar(metadata, trading_dates):
        return False, "yearly part metadata matches requested calendar"

    return True, "requested trading calendar changed"


def fetch_match_price(session: requests.Session, ticker: str, trading_date: date, timeout: int) -> list[dict[str, object]]:
    response = session.get(
        MATCH_PRICE_URL,
        params={
            "symbol": ticker,
            "date": trading_date.strftime("%Y%m%d"),
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("data") or []
    if not isinstance(rows, list):
        raise RuntimeError(f"Unexpected CafeF payload for {ticker} {trading_date}: 'data' is not a list")
    return rows


def normalize_trade_times(series: pd.Series) -> pd.Series:
    full = pd.to_datetime(series, errors="coerce")
    hours = full.dt.hour.dropna()
    if hours.empty:
        return pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")

    # CafeF old sessions often arrive as 02:xx-07:xx timestamps for what are
    # actually 09:xx-14:xx exchange-local trades. Shift those legacy rows,
    # regardless of whether CafeF encoded the timestamp as tz-aware or naive.
    if int(hours.max()) <= 8:
        full = full + pd.Timedelta(hours=7)

    if isinstance(full.dtype, pd.DatetimeTZDtype):
        full = full.dt.tz_localize(None)
    return full


def assign_cafef_hour_bucket(ts: pd.Timestamp) -> pd.Timestamp | pd.NaT:
    if pd.isna(ts):
        return pd.NaT
    base = ts.normalize()
    minutes = ts.hour * 60 + ts.minute + ts.second / 60.0

    if 9 * 60 <= minutes < 10 * 60:
        return base + pd.Timedelta(hours=10)
    if 10 * 60 <= minutes < 11 * 60:
        return base + pd.Timedelta(hours=11)
    if 11 * 60 <= minutes < 13 * 60:
        return base + pd.Timedelta(hours=12)
    if 13 * 60 <= minutes < 14 * 60:
        return base + pd.Timedelta(hours=13)
    if 14 * 60 <= minutes <= 15 * 60:
        return base + pd.Timedelta(hours=14)
    return pd.NaT


def aggregate_to_repo_1h(rows: list[dict[str, object]]) -> pd.DataFrame:
    if not rows:
        return empty_bar_frame()

    raw = pd.DataFrame(rows)
    trades = pd.DataFrame(
        {
            "trade_time": normalize_trade_times(raw["tradeDate"]),
            "price": pd.to_numeric(raw["price"], errors="coerce"),
            "volume": pd.to_numeric(raw["volume"], errors="coerce") * 100.0,
        }
    )
    trades = trades.dropna(subset=["trade_time", "price", "volume"]).copy()
    if trades.empty:
        return empty_bar_frame()

    trades = trades.sort_values("trade_time").reset_index(drop=True)
    trades["time"] = trades["trade_time"].apply(assign_cafef_hour_bucket)
    trades = trades.dropna(subset=["time"]).copy()
    if trades.empty:
        return empty_bar_frame()

    grouped = (
        trades.groupby("time", sort=True)
        .agg(
            open=("price", "first"),
            high=("price", "max"),
            low=("price", "min"),
            close=("price", "last"),
            volume=("volume", "sum"),
        )
        .reset_index()
    )
    grouped["volume"] = grouped["volume"].round().astype("int64")
    return grouped[BAR_COLUMNS]


def finalize_intraday_frame(frames: list[pd.DataFrame]) -> pd.DataFrame:
    if not frames:
        return empty_bar_frame()
    out = (
        pd.concat(frames, ignore_index=True)
        .sort_values("time")
        .drop_duplicates(subset=["time"], keep="last")
        .reset_index(drop=True)
    )
    out["volume"] = pd.to_numeric(out["volume"], errors="coerce").fillna(0).round().astype("int64")
    return out[BAR_COLUMNS]


def make_thread_session_getter() -> Callable[[], requests.Session]:
    thread_state = threading.local()

    def get_session() -> requests.Session:
        session = getattr(thread_state, "session", None)
        if session is None:
            session = build_session()
            thread_state.session = session
        return session

    return get_session


def fetch_one_date(
    get_session: Callable[[], requests.Session],
    ticker: str,
    trading_date: date,
    *,
    timeout: int,
) -> tuple[date, list[dict[str, object]], pd.DataFrame]:
    rows = fetch_match_price(get_session(), ticker, trading_date, timeout=timeout)
    bars = aggregate_to_repo_1h(rows)
    return trading_date, rows, bars


def fetch_one_year(
    session: requests.Session,
    ticker: str,
    year: int,
    trading_dates: list[date],
    *,
    timeout: int,
    delay: float,
    workers: int,
    retry_rounds: int,
    retry_delay: float,
) -> tuple[pd.DataFrame, list[date]]:
    total_attempts = retry_rounds + 1
    frames: list[pd.DataFrame] = []
    pending = list(trading_dates)
    get_session = make_thread_session_getter()

    for attempt in range(1, total_attempts + 1):
        if attempt > 1:
            print(
                f"    Retry round {attempt - 1}/{retry_rounds} for {ticker} {year}: "
                f"{len(pending)} failed dates",
                flush=True,
            )

        current_round = list(pending)
        pending = []
        zero_trade_dates = 0
        zero_bar_dates = 0
        bar_dates = 0
        sample_zero_bar_dates: list[tuple[date, int]] = []
        total_round = len(current_round)

        if workers == 1:
            results_iter = []
            for index, trading_date in enumerate(current_round, start=1):
                try:
                    result = fetch_one_date(
                        lambda: session,
                        ticker,
                        trading_date,
                        timeout=timeout,
                    )
                    results_iter.append((index, trading_date, result, None))
                except Exception as exc:
                    results_iter.append((index, trading_date, None, exc))
                if delay > 0 and index < total_round:
                    time.sleep(delay)
        else:
            results_iter = []
            with cf.ThreadPoolExecutor(max_workers=workers, thread_name_prefix=f"cafef-{ticker}-{year}") as executor:
                futures: dict[cf.Future[tuple[date, list[dict[str, object]], pd.DataFrame]], date] = {}
                for index, trading_date in enumerate(current_round, start=1):
                    future = executor.submit(
                        fetch_one_date,
                        get_session,
                        ticker,
                        trading_date,
                        timeout=timeout,
                    )
                    futures[future] = trading_date
                    if delay > 0 and index < total_round:
                        time.sleep(delay)

                for index, future in enumerate(cf.as_completed(futures), start=1):
                    trading_date = futures[future]
                    try:
                        result = future.result()
                        results_iter.append((index, trading_date, result, None))
                    except Exception as exc:
                        results_iter.append((index, trading_date, None, exc))

        for index, trading_date, result, exc in results_iter:
            if exc is not None:
                print(
                    f"    Failed to fetch {ticker} {trading_date} "
                    f"(attempt {attempt}/{total_attempts}): {exc}",
                    flush=True,
                )
                pending.append(trading_date)
                continue

            _, rows, bars = result
            if not rows:
                zero_trade_dates += 1
            elif bars.empty:
                zero_bar_dates += 1
                if len(sample_zero_bar_dates) < 3:
                    sample_zero_bar_dates.append((trading_date, len(rows)))
            else:
                bar_dates += 1
                frames.append(bars)

            if attempt == 1 and (index % 100 == 0 or index == total_round):
                print(
                    f"    {ticker} {year}: processed {index}/{total_round} dates "
                    f"(bar dates={bar_dates}, zero-trade={zero_trade_dates}, trade/no-bar={zero_bar_dates})",
                    flush=True,
                )

        if attempt == 1 and sample_zero_bar_dates:
            sample_text = ", ".join(f"{d} ({rows} trades)" for d, rows in sample_zero_bar_dates)
            print(
                f"    {ticker} {year}: sample trade/no-bar dates after normalization -> {sample_text}",
                flush=True,
            )

        if not pending:
            break
        if retry_delay > 0 and attempt < total_attempts:
            time.sleep(retry_delay)

    return finalize_intraday_frame(frames), pending


def rebuild_ticker_output(
    output_path: Path,
    year_part_paths: list[Path],
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    frames = [pd.read_parquet(path) for path in year_part_paths if path.exists()]
    out = finalize_intraday_frame(frames)
    if not out.empty:
        calendar = pd.to_datetime(out["time"], errors="coerce").dt.date
        mask = (calendar >= start_date) & (calendar <= end_date)
        out = out.loc[mask].reset_index(drop=True)
    out.to_parquet(output_path, index=False)
    return out


def fetch_one_ticker(
    session: requests.Session,
    ticker: str,
    trading_dates: Iterable[date],
    *,
    interval_label: str,
    timeout: int,
    delay: float,
    workers: int,
    retry_rounds: int,
    retry_delay: float,
    overwrite: bool,
    parts_dir: Path,
) -> tuple[bool, str]:
    dates = list(trading_dates)
    if not dates:
        return False, f"{ticker}: no trading dates in requested window"

    grouped_dates = group_dates_by_year(dates)
    latest_requested_year = max(grouped_dates)
    output_path = build_output_path(ticker, interval_label)
    year_part_paths = [
        build_year_part_path(parts_dir, ticker, interval_label, year)
        for year in grouped_dates
    ]

    failed_years: list[int] = []
    unresolved_dates_total = 0
    legacy_reuse_years: list[int] = []

    for year, year_dates in grouped_dates.items():
        part_path = build_year_part_path(parts_dir, ticker, interval_label, year)
        metadata_path = build_year_metadata_path(parts_dir, ticker, interval_label, year)
        refresh_year, reason = should_refresh_year_part(
            part_path,
            metadata_path,
            year,
            latest_requested_year,
            year_dates,
            overwrite,
        )
        if not refresh_year:
            print(f"    {ticker} {year}: {reason}", flush=True)
            if "without metadata" in reason:
                legacy_reuse_years.append(year)
            continue

        year_frame, unresolved_dates = fetch_one_year(
            session,
            ticker,
            year,
            year_dates,
            timeout=timeout,
            delay=delay,
            workers=workers,
            retry_rounds=retry_rounds,
            retry_delay=retry_delay,
        )

        if unresolved_dates:
            failed_years.append(year)
            unresolved_dates_total += len(unresolved_dates)
            print(
                f"    Failed to fetch {ticker} {year} after {retry_rounds + 1} attempts: "
                f"{len(unresolved_dates)} unresolved date(s)",
                flush=True,
            )
            continue

        year_frame.to_parquet(part_path, index=False)
        write_year_metadata(
            metadata_path,
            build_year_metadata(ticker, interval_label, year, year_dates, year_frame),
        )
        print(
            f"    {ticker} {year}: saved yearly part with {len(year_frame)} bars "
            f"from {len(year_dates)} dates",
            flush=True,
        )

    available_parts = [path for path in year_part_paths if path.exists()]
    if not available_parts:
        return False, f"{ticker}: no yearly parts available to append"

    out = rebuild_ticker_output(output_path, available_parts, dates[0], dates[-1])
    if out.empty:
        return False, f"{ticker}: yearly parts appended but no intraday bars produced"

    message = (
        f"{ticker}: saved {len(out)} bars "
        f"({out['time'].min()} -> {out['time'].max()}) from {len(available_parts)}/{len(year_part_paths)} yearly parts"
    )
    if legacy_reuse_years:
        message += (
            f" | legacy reused without metadata: {','.join(str(year) for year in legacy_reuse_years)}"
            " (run with --overwrite once to seed metadata)"
        )
    if failed_years:
        message += (
            f" | unresolved years: {','.join(str(year) for year in failed_years)}"
            f" ({unresolved_dates_total} unresolved dates)"
        )
        return False, message
    return True, message


def main(argv: list[str] | None = None, *, include_tickers: bool = True) -> None:
    args = parse_args(argv, include_tickers=include_tickers)
    start_date = parse_iso_date(args.start)
    end_date = parse_iso_date(args.end)

    if start_date > end_date:
        raise ValueError("--start must be on or before --end")
    if args.delay < 0:
        raise ValueError("--delay must be non-negative")
    if args.timeout <= 0:
        raise ValueError("--timeout must be positive")
    if args.workers <= 0:
        raise ValueError("--workers must be positive")
    if args.retry_rounds < 0:
        raise ValueError("--retry-rounds must be non-negative")
    if args.retry_delay < 0:
        raise ValueError("--retry-delay must be non-negative")

    tickers = resolve_tickers(getattr(args, "tickers", None))
    interval_label = args.interval_label.upper()
    parts_dir = Path(args.parts_dir)

    calendars: dict[str, list[date]] = {
        ticker: load_trading_dates(ticker, start_date, end_date) for ticker in tickers
    }
    total_dates = sum(len(dates) for dates in calendars.values())

    print("=" * 60)
    print("CafeF MatchPrice Intraday Fetcher")
    print("=" * 60)
    print(f"Tickers         : {len(tickers)}")
    print(f"Date range      : {start_date} to {end_date}")
    print(f"Output label    : {interval_label}")
    print(f"Total date calls: {total_dates}")
    print(f"Workers         : {args.workers}")
    print(f"Retry rounds    : {args.retry_rounds}")
    print(f"Parts dir       : {parts_dir / interval_label}")
    print(f"Output dir      : {DATA_DIR}")
    print("=" * 60)

    if args.dry_run:
        for ticker in tickers[:10]:
            dates = calendars[ticker]
            preview = f"{dates[0]} -> {dates[-1]}" if dates else "no dates"
            years = sorted({d.year for d in dates})
            year_preview = f"{years[0]} -> {years[-1]}" if years else "no years"
            print(
                f"[DRY RUN] {ticker}: {len(dates)} trading dates ({preview}) | "
                f"{len(years)} years ({year_preview})",
            )
        return

    session = build_session()

    success_count = 0
    failed: list[str] = []
    for index, ticker in enumerate(tickers, start=1):
        dates = calendars[ticker]
        years = sorted({d.year for d in dates})
        year_text = f"{len(years)} years" if years else "0 years"
        print(
            f"[{index}/{len(tickers)}] {ticker} ({len(dates)} trading dates, {year_text})",
            flush=True,
        )
        try:
            ok, message = fetch_one_ticker(
                session,
                ticker,
                dates,
                interval_label=interval_label,
                timeout=args.timeout,
                delay=args.delay,
                workers=args.workers,
                retry_rounds=args.retry_rounds,
                retry_delay=args.retry_delay,
                overwrite=args.overwrite,
                parts_dir=parts_dir,
            )
        except Exception as exc:
            ok = False
            message = f"{ticker}: ERROR -- {exc}"
        print(f"  {message}", flush=True)
        if ok:
            success_count += 1
        else:
            failed.append(ticker)

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Success: {success_count}/{len(tickers)}")
    if failed:
        print(f"Failed : {', '.join(failed)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
