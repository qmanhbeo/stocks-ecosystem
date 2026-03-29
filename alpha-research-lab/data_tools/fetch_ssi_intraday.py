"""
Fetch historical intraday OHLCV from SSI FastConnect.

This is the best documented historical intraday candidate currently wired into the
repo. It uses the official SSI FastConnect `IntradayOhlc` endpoint, which requires
registered API credentials.

Examples:
    conda run -n stocks python data_tools/fetch_ssi_intraday.py --dry-run
    conda run -n stocks python data_tools/fetch_ssi_intraday.py --tickers FPT,ACB --resolution 60 --start 2019-01-01 --end 2025-12-31
    conda run -n stocks python data_tools/fetch_ssi_intraday.py --resolution 60 --start 2015-01-01 --end 2025-12-31 --overwrite

Credentials:
    Set SSI_FC_CONSUMER_ID and SSI_FC_CONSUMER_SECRET in the environment,
    or pass --consumer-id / --consumer-secret explicitly.
"""

from __future__ import annotations

import argparse
import math
import os
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data" / "stock"
DATA_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://fc-data.ssi.com.vn"
ACCESS_TOKEN_PATH = "/api/v2/Market/AccessToken"
INTRADAY_PATH = "/api/v2/Market/IntradayOhlc"
UNIVERSE_INTERVAL = "1D"
EXCLUDE = {"VNINDEX", "VN30"}
DEFAULT_TIMEOUT = 30
DEFAULT_PAGE_SIZE = 1000
DEFAULT_MAX_PAGES = 10
EXCHANGE_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
TRADING_MINUTES_PER_DAY = 255


@dataclass
class Credentials:
    consumer_id: str
    consumer_secret: str


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=5,
        read=5,
        connect=5,
        status=5,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "POST"),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "stocks-alpha-research/ssi-fastconnect-intraday",
        }
    )
    return session


class SsiFastConnectClient:
    def __init__(
        self,
        credentials: Credentials,
        *,
        base_url: str = BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self._credentials = credentials
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = build_session()
        self._access_token: str | None = None

    def authenticate(self, *, force: bool = False) -> str:
        if self._access_token is not None and not force:
            return self._access_token

        response = self._session.post(
            f"{self._base_url}{ACCESS_TOKEN_PATH}",
            json={
                "consumerID": self._credentials.consumer_id,
                "consumerSecret": self._credentials.consumer_secret,
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        status = int(payload.get("status", 0))
        if status != 200:
            raise RuntimeError(
                f"SSI token request failed: status={status} message={payload.get('message')!r}"
            )
        token = ((payload.get("data") or {}).get("accessToken") or "").strip()
        if not token:
            raise RuntimeError("SSI token request succeeded but returned no access token")
        self._access_token = token
        return token

    def request_json(
        self,
        path: str,
        *,
        params: dict[str, object],
        retry_auth: bool = True,
    ) -> dict[str, object]:
        token = self.authenticate()
        response = self._session.get(
            f"{self._base_url}{path}",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=self._timeout,
        )
        if response.status_code in {401, 403} and retry_auth:
            token = self.authenticate(force=True)
            response = self._session.get(
                f"{self._base_url}{path}",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
                timeout=self._timeout,
            )
        response.raise_for_status()
        payload = response.json()
        status = int(payload.get("status", 0))
        if status != 200:
            raise RuntimeError(
                f"SSI request failed for {path}: status={status} message={payload.get('message')!r}"
            )
        return payload

    def fetch_intraday_window(
        self,
        *,
        symbol: str,
        start_date: date,
        end_date: date,
        resolution: int,
        page_size: int,
        max_pages: int,
        ascending: bool,
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        total_record: int | None = None

        for page_index in range(1, max_pages + 1):
            payload = self.request_json(
                INTRADAY_PATH,
                params={
                    "Symbol": symbol,
                    "FromDate": format_api_date(start_date),
                    "ToDate": format_api_date(end_date),
                    "PageIndex": page_index,
                    "PageSize": page_size,
                    "Resolution": resolution,
                    "Ascending": str(bool(ascending)).lower(),
                },
            )
            page_rows = payload.get("data") or []
            total_record = int(payload.get("totalRecord", 0) or 0)
            if not isinstance(page_rows, list):
                raise RuntimeError(f"Unexpected SSI payload for {symbol}: data is not a list")
            rows.extend(page_rows)

            if not page_rows:
                break
            if len(page_rows) < page_size:
                break
            if total_record and len(rows) >= total_record:
                break

        if total_record and total_record > page_size * max_pages:
            raise RuntimeError(
                f"{symbol} {start_date}..{end_date} requires {total_record} rows, "
                f"which exceeds the configured page cap ({page_size * max_pages}). "
                "Lower --chunk-days or fetch a larger resolution."
            )
        if total_record and len(rows) < total_record:
            raise RuntimeError(
                f"{symbol} {start_date}..{end_date} returned {len(rows)}/{total_record} rows. "
                "Lower --chunk-days and retry."
            )

        return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch historical intraday OHLCV from SSI FastConnect")
    parser.add_argument(
        "--tickers",
        type=str,
        help="Comma-separated ticker list. Defaults to the existing 1D stock universe under data/stock/",
    )
    parser.add_argument("--start", type=str, default="2015-01-01", help="Start date in YYYY-MM-DD")
    parser.add_argument("--end", type=str, default=date.today().isoformat(), help="End date in YYYY-MM-DD")
    parser.add_argument(
        "--resolution",
        type=int,
        default=60,
        help="Intraday bar resolution in minutes for SSI IntradayOhlc (default: 60)",
    )
    parser.add_argument(
        "--interval-label",
        type=str,
        help="Output file suffix label (default: auto-derived from --resolution, e.g. 1H)",
    )
    parser.add_argument(
        "--chunk-days",
        type=int,
        help="Date window size per API chunk. Defaults to a safe auto-derived value from resolution.",
    )
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE, help="API page size (default: 1000)")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=DEFAULT_MAX_PAGES,
        help="Max pages per date chunk (default: 10, matches SSI docs)",
    )
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between ticker fetches in seconds")
    parser.add_argument("--chunk-delay", type=float, default=0.0, help="Delay between chunk fetches in seconds")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTP timeout in seconds")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing output files")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be fetched without calling SSI")
    parser.add_argument("--base-url", type=str, default=BASE_URL, help="SSI API base URL")
    parser.add_argument("--consumer-id", type=str, help="SSI FastConnect consumer ID")
    parser.add_argument("--consumer-secret", type=str, help="SSI FastConnect consumer secret")
    parser.add_argument(
        "--ascending",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Request bars in ascending order (default: true)",
    )
    return parser.parse_args()


def parse_iso_date(value: str) -> date:
    return datetime.fromisoformat(value).date()


def format_api_date(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def infer_interval_label(resolution: int) -> str:
    if resolution <= 0:
        raise ValueError("--resolution must be a positive integer")
    if resolution % 60 == 0:
        hours = resolution // 60
        return f"{hours}H"
    return f"{resolution}M"


def recommended_chunk_days(resolution: int, page_size: int, max_pages: int) -> int:
    bars_per_day = max(1, math.ceil(TRADING_MINUTES_PER_DAY / max(1, resolution)))
    safe_row_budget = int(page_size * max_pages * 0.8)
    return max(5, safe_row_budget // bars_per_day)


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


def iter_date_windows(start_date: date, end_date: date, chunk_days: int) -> Iterable[tuple[date, date]]:
    current = start_date
    step = timedelta(days=chunk_days - 1)
    while current <= end_date:
        window_end = min(end_date, current + step)
        yield current, window_end
        current = window_end + timedelta(days=1)


def load_credentials(args: argparse.Namespace) -> Credentials:
    consumer_id = args.consumer_id or os.environ.get("SSI_FC_CONSUMER_ID", "").strip()
    consumer_secret = args.consumer_secret or os.environ.get("SSI_FC_CONSUMER_SECRET", "").strip()
    if not consumer_id or not consumer_secret:
        raise RuntimeError(
            "Missing SSI FastConnect credentials. Set SSI_FC_CONSUMER_ID and "
            "SSI_FC_CONSUMER_SECRET, or pass --consumer-id and --consumer-secret."
        )
    return Credentials(consumer_id=consumer_id, consumer_secret=consumer_secret)


def build_output_path(ticker: str, interval_label: str) -> Path:
    return DATA_DIR / f"gia_lich_su_{ticker}_{interval_label}.parquet"


def choose_time_candidate(
    frame: pd.DataFrame,
    candidates: list[pd.Series],
) -> pd.Series:
    trading_date = None
    if "TradingDate" in frame.columns:
        trading_date = pd.to_datetime(frame["TradingDate"], errors="coerce", dayfirst=True)

    best_score: tuple[float, float, float] = (-1.0, -1.0, -1.0)
    best_candidate: pd.Series | None = None
    for candidate in candidates:
        if candidate is None:
            continue
        non_null = float(candidate.notna().mean())
        if non_null == 0:
            continue
        session_hour = float(candidate.dropna().dt.hour.between(8, 15).mean()) if non_null else 0.0
        date_match = 0.0
        if trading_date is not None:
            matched = pd.DataFrame({"cand": candidate, "date": trading_date}).dropna()
            if not matched.empty:
                date_match = float(
                    (matched["cand"].dt.normalize() == matched["date"].dt.normalize()).mean()
                )
        score = (date_match, session_hour, non_null)
        if score > best_score:
            best_score = score
            best_candidate = candidate

    if best_candidate is None:
        return pd.Series(pd.NaT, index=frame.index, dtype="datetime64[ns]")
    return best_candidate


def parse_time_column(frame: pd.DataFrame) -> pd.Series:
    raw_time = frame.get("Time", frame.get("time"))
    if raw_time is None:
        return pd.Series(pd.NaT, index=frame.index, dtype="datetime64[ns]")

    candidates: list[pd.Series] = []

    direct = pd.to_datetime(raw_time, errors="coerce", dayfirst=True)
    if not isinstance(direct.dtype, pd.DatetimeTZDtype):
        candidates.append(direct)
    else:
        candidates.append(direct.dt.tz_convert(EXCHANGE_TZ).dt.tz_localize(None))

    raw_numeric = pd.to_numeric(
        raw_time.astype(str).str.extract(r"(-?\d{10,16})")[0],
        errors="coerce",
    )
    if raw_numeric.notna().any():
        as_ms = pd.to_datetime(raw_numeric, unit="ms", errors="coerce", utc=True)
        candidates.append(as_ms.dt.tz_convert(EXCHANGE_TZ).dt.tz_localize(None))

        as_s = pd.to_datetime(raw_numeric, unit="s", errors="coerce", utc=True)
        candidates.append(as_s.dt.tz_convert(EXCHANGE_TZ).dt.tz_localize(None))

    if "TradingDate" in frame.columns:
        trading_date = pd.to_datetime(frame["TradingDate"], errors="coerce", dayfirst=True)
        time_text = raw_time.astype(str).str.extract(r"(\d{1,2}:\d{2}(?::\d{2})?)")[0]
        combined = pd.to_datetime(
            trading_date.dt.strftime("%Y-%m-%d") + " " + time_text.fillna(""),
            errors="coerce",
        )
        candidates.append(combined)

    return choose_time_candidate(frame, candidates)


def get_numeric_column(frame: pd.DataFrame, *names: str) -> pd.Series:
    for name in names:
        if name in frame.columns:
            return pd.to_numeric(frame[name], errors="coerce")
    return pd.Series(float("nan"), index=frame.index, dtype="float64")


def normalize_intraday_rows(rows: list[dict[str, object]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

    raw = pd.DataFrame(rows)
    out = pd.DataFrame(
        {
            "time": parse_time_column(raw),
            "open": get_numeric_column(raw, "Open", "open"),
            "high": get_numeric_column(raw, "High", "high"),
            "low": get_numeric_column(raw, "Low", "low"),
            "close": get_numeric_column(raw, "Close", "close"),
            "volume": get_numeric_column(raw, "Volume", "volume"),
        }
    )
    out = out.dropna(subset=["time", "open", "high", "low", "close", "volume"]).copy()
    out["time"] = pd.to_datetime(out["time"]).dt.tz_localize(None)
    out = out.sort_values("time").drop_duplicates(subset=["time"], keep="last").reset_index(drop=True)
    return out


def fetch_one_ticker(
    client: SsiFastConnectClient,
    *,
    ticker: str,
    start_date: date,
    end_date: date,
    resolution: int,
    interval_label: str,
    chunk_days: int,
    page_size: int,
    max_pages: int,
    ascending: bool,
    chunk_delay: float,
    overwrite: bool,
) -> tuple[bool, str]:
    output_path = build_output_path(ticker, interval_label)
    if output_path.exists() and not overwrite:
        return True, f"{ticker}: exists, skipping"

    all_chunks: list[pd.DataFrame] = []
    for window_start, window_end in iter_date_windows(start_date, end_date, chunk_days):
        rows = client.fetch_intraday_window(
            symbol=ticker,
            start_date=window_start,
            end_date=window_end,
            resolution=resolution,
            page_size=page_size,
            max_pages=max_pages,
            ascending=ascending,
        )
        frame = normalize_intraday_rows(rows)
        if not frame.empty:
            all_chunks.append(frame)
        print(
            f"    {ticker} {window_start}..{window_end}: "
            f"{len(frame)} bars",
            flush=True,
        )
        if chunk_delay > 0:
            time.sleep(chunk_delay)

    if not all_chunks:
        return False, f"{ticker}: no intraday data returned"

    out = (
        pd.concat(all_chunks, ignore_index=True)
        .sort_values("time")
        .drop_duplicates(subset=["time"], keep="last")
        .reset_index(drop=True)
    )
    out.to_parquet(output_path, index=False)
    min_time = out["time"].min()
    max_time = out["time"].max()
    return True, f"{ticker}: saved {len(out)} bars ({min_time} -> {max_time})"


def main() -> None:
    args = parse_args()

    start_date = parse_iso_date(args.start)
    end_date = parse_iso_date(args.end)
    if start_date > end_date:
        raise ValueError("--start must be on or before --end")
    if args.resolution <= 0:
        raise ValueError("--resolution must be positive")
    if args.chunk_days is not None and args.chunk_days <= 0:
        raise ValueError("--chunk-days must be positive")
    if args.page_size <= 0:
        raise ValueError("--page-size must be positive")
    if args.max_pages <= 0:
        raise ValueError("--max-pages must be positive")
    if args.delay < 0:
        raise ValueError("--delay must be non-negative")
    if args.chunk_delay < 0:
        raise ValueError("--chunk-delay must be non-negative")
    if args.timeout <= 0:
        raise ValueError("--timeout must be positive")

    tickers = resolve_tickers(args.tickers)
    interval_label = (args.interval_label or infer_interval_label(args.resolution)).upper()
    chunk_days = args.chunk_days or recommended_chunk_days(args.resolution, args.page_size, args.max_pages)

    print("=" * 60)
    print("SSI FastConnect Intraday Fetcher")
    print("=" * 60)
    print(f"Tickers       : {len(tickers)}")
    print(f"Resolution    : {args.resolution} minute(s)")
    print(f"Output label  : {interval_label}")
    print(f"Date range    : {start_date} to {end_date}")
    print(f"Chunk days    : {chunk_days}")
    print(f"Page size     : {args.page_size}")
    print(f"Max pages     : {args.max_pages}")
    print(f"Output dir    : {DATA_DIR}")
    print("=" * 60)

    if args.dry_run:
        windows = list(iter_date_windows(start_date, end_date, chunk_days))
        print(f"[DRY RUN] First 10 tickers: {tickers[:10]}")
        print(f"[DRY RUN] Window count per ticker: {len(windows)}")
        if windows:
            print(f"[DRY RUN] First window: {windows[0][0]} -> {windows[0][1]}")
            print(f"[DRY RUN] Last window : {windows[-1][0]} -> {windows[-1][1]}")
        return

    credentials = load_credentials(args)
    client = SsiFastConnectClient(credentials, base_url=args.base_url, timeout=args.timeout)

    success_count = 0
    failed: list[str] = []
    for index, ticker in enumerate(tickers, start=1):
        print(f"[{index}/{len(tickers)}] {ticker}", flush=True)
        try:
            ok, message = fetch_one_ticker(
                client,
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                resolution=args.resolution,
                interval_label=interval_label,
                chunk_days=chunk_days,
                page_size=args.page_size,
                max_pages=args.max_pages,
                ascending=bool(args.ascending),
                chunk_delay=args.chunk_delay,
                overwrite=args.overwrite,
            )
        except Exception as exc:
            ok = False
            message = f"{ticker}: ERROR -- {exc}"

        print(f"  {message}", flush=True)
        if ok:
            success_count += 1
        else:
            failed.append(ticker)

        if index < len(tickers) and args.delay > 0:
            time.sleep(args.delay)

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Success: {success_count}/{len(tickers)}")
    if failed:
        print(f"Failed : {', '.join(failed)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
