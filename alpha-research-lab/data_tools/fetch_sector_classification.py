"""
Fetch ICB sector classification for HOSE stocks via vnstock company.overview().

Default behavior is safe and incremental:
  - reuse existing rows from data/features/sector_classification.parquet
  - fetch only missing symbols or rows with blank sector fields
  - atomically replace the output after merging

Use --refresh-existing to force a full refetch of all covered symbols.

Outputs: data/features/sector_classification.parquet
Columns: symbol, icb_name2, icb_name3, icb_name4

Usage:
    conda run -n stocks python data_tools/fetch_sector_classification.py
    conda run -n stocks python data_tools/fetch_sector_classification.py --delay 0.3 --dry-run
    conda run -n stocks python data_tools/fetch_sector_classification.py --refresh-existing
"""

import argparse
import io
import sys
import time
from pathlib import Path

import pandas as pd
from vnstock import Listing, Vnstock

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


sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = REPO_ROOT / "data" / "features" / "sector_classification.parquet"
STOCK_DIR = REPO_ROOT / "data" / "stock"
REQUIRED_COLUMNS = ["symbol", "icb_name2", "icb_name3", "icb_name4"]
PROBE_CACHE_STATUS_SKIP_ELIGIBLE = {"unchanged", "partial"}
SECTOR_PROBE_TARGET = "9999-12-31"


def get_hose_tickers() -> list[str]:
    listing = Listing()
    df = listing.symbols_by_exchange()
    hose = df[df["exchange"].str.upper() == "HOSE"] if "exchange" in df.columns else df
    tickers = hose["symbol"].dropna().astype(str).str.strip().str.upper().unique().tolist()
    return sorted(tickers)


def load_existing_rows() -> pd.DataFrame:
    if not OUT_PATH.exists():
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    try:
        existing = pd.read_parquet(OUT_PATH)
    except Exception as exc:
        print(f"WARN: unable to read existing sector file, refetching all needed rows ({exc})")
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

    existing = existing.copy()
    if "ticker" in existing.columns and "symbol" not in existing.columns:
        existing = existing.rename(columns={"ticker": "symbol"})
    for column in REQUIRED_COLUMNS:
        if column not in existing.columns:
            existing[column] = ""
    existing["symbol"] = existing["symbol"].fillna("").astype(str).str.strip().str.upper()
    for column in REQUIRED_COLUMNS[1:]:
        existing[column] = existing[column].fillna("").astype(str).str.strip()
    existing = existing[REQUIRED_COLUMNS]
    existing = existing[existing["symbol"] != ""]
    return existing.drop_duplicates(subset=["symbol"], keep="last").reset_index(drop=True)


def row_is_complete(row: pd.Series) -> bool:
    return all(str(row.get(column, "")).strip() for column in REQUIRED_COLUMNS[1:])


def row_signature(row: pd.Series | dict[str, object] | None) -> str:
    if row is None:
        return ""
    return "|".join(str(row.get(column, "")).strip() for column in REQUIRED_COLUMNS[1:])


def probe_cache_path() -> Path:
    return build_probe_cache_path(OUT_PATH.parent, "fetch_sector_classification_probe_cache")


def probe_cache_metadata() -> dict[str, object]:
    return {
        "tool": "fetch_sector_classification",
        "source": "VCI company.overview",
    }


def fetch_sector(symbol: str) -> dict[str, str]:
    """Fetch ICB sector fields for one symbol."""
    try:
        stock = Vnstock().stock(symbol=symbol, source="VCI")
        overview = stock.company.overview()
        if isinstance(overview, pd.DataFrame) and len(overview) > 0:
            row = overview.iloc[0]
            return {
                "symbol": symbol,
                "icb_name2": str(row.get("icb_name2", "")).strip(),
                "icb_name3": str(row.get("icb_name3", "")).strip(),
                "icb_name4": str(row.get("icb_name4", "")).strip(),
            }
    except Exception as exc:
        print(f"  ERROR {symbol}: {exc}")
    return {"symbol": symbol, "icb_name2": "", "icb_name3": "", "icb_name4": ""}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=0.4, help="Seconds between API calls")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be fetched")
    parser.add_argument(
        "--refresh-existing",
        action="store_true",
        help="Refetch all covered symbols instead of only missing/blank rows",
    )
    parser.add_argument(
        "--probe-cache-ttl-hours",
        type=float,
        default=168.0,
        help="Trust cached blank/incomplete sector probes for this many hours (default: 168; 0 disables)",
    )
    args = parser.parse_args()
    if args.probe_cache_ttl_hours < 0:
        raise ValueError("--probe-cache-ttl-hours must be non-negative")

    available = {
        path.stem.replace("gia_lich_su_", "").replace("_1D", "")
        for path in STOCK_DIR.glob("gia_lich_su_*_1D.parquet")
    }
    hose = get_hose_tickers()
    tickers = [ticker for ticker in hose if ticker in available]
    print(f"HOSE tickers with price data: {len(tickers)}")
    print(f"Probe cache TTL: {args.probe_cache_ttl_hours}h")

    existing = load_existing_rows()
    existing_map = {row["symbol"]: row for row in existing.to_dict("records")}
    probe_cache_enabled = args.probe_cache_ttl_hours > 0
    probe_cache = load_probe_cache(probe_cache_path()) if probe_cache_enabled else {}

    to_fetch: list[str] = []
    probe_cached = 0
    for symbol in tickers:
        if args.refresh_existing:
            to_fetch.append(symbol)
            continue
        cached_row = existing_map.get(symbol)
        if cached_row is None or not row_is_complete(pd.Series(cached_row)):
            if (
                cached_row is not None
                and OUT_PATH.exists()
                and probe_cache_record_is_fresh(
                    probe_cache.get(symbol),
                    requested_end=SECTOR_PROBE_TARGET,
                    path=OUT_PATH,
                    latest_value=row_signature(cached_row),
                    ttl_hours=args.probe_cache_ttl_hours,
                    eligible_statuses=PROBE_CACHE_STATUS_SKIP_ELIGIBLE,
                )
            ):
                probe_cached += 1
                continue
            to_fetch.append(symbol)

    reusable_current = sum(
        1
        for symbol in tickers
        if symbol not in set(to_fetch) and symbol in existing_map
    )
    print(f"Existing reusable rows: {reusable_current}")
    print(f"Probe-cached incomplete rows: {probe_cached}")
    print(f"Rows to fetch: {len(to_fetch)}")

    if args.dry_run:
        preview = to_fetch[:10]
        print(f"[DRY RUN] Would fetch: {preview}{'...' if len(to_fetch) > 10 else ''}")
        return

    to_fetch_set = set(to_fetch)
    merged_records = [row for symbol, row in existing_map.items() if symbol not in to_fetch_set]
    fetched_status: dict[str, str] = {}
    for index, symbol in enumerate(to_fetch, start=1):
        before_signature = row_signature(existing_map.get(symbol))
        record = fetch_sector(symbol)
        merged_records.append(record)
        after_signature = row_signature(record)
        if row_is_complete(pd.Series(record)):
            fetched_status[symbol] = "current"
        else:
            fetched_status[symbol] = "partial" if after_signature and after_signature != before_signature else "unchanged"
        label = record["icb_name3"] or record["icb_name2"] or "?"
        print(f"  [{index}/{len(to_fetch)}] {symbol}: {label}")
        if args.delay > 0 and index < len(to_fetch):
            time.sleep(args.delay)

    out = pd.DataFrame(merged_records)
    if out.empty:
        out = pd.DataFrame(columns=REQUIRED_COLUMNS)
    for column in REQUIRED_COLUMNS:
        if column not in out.columns:
            out[column] = ""
    out["symbol"] = out["symbol"].fillna("").astype(str).str.strip().str.upper()
    for column in REQUIRED_COLUMNS[1:]:
        out[column] = out[column].fillna("").astype(str).str.strip()
    out = out[REQUIRED_COLUMNS]
    out = out[out["symbol"] != ""]
    out = out.drop_duplicates(subset=["symbol"], keep="last").sort_values("symbol").reset_index(drop=True)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_parquet(out, OUT_PATH)
    out_map = {row["symbol"]: row for row in out.to_dict("records")}
    for symbol, status in fetched_status.items():
        update_probe_cache_state(
            probe_cache_path() if probe_cache_enabled else None,
            probe_cache,
            item_key=symbol,
            entry=build_probe_cache_entry(
                status=status,
                checked_end=SECTOR_PROBE_TARGET,
                path=OUT_PATH,
                latest_value=row_signature(out_map.get(symbol)),
            ),
            metadata=probe_cache_metadata(),
        )
    print(f"\nSaved {len(out)} rows -> {OUT_PATH}")


if __name__ == "__main__":
    main()
