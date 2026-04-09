"""
Collect forward-only current-day foreign-flow fields from vnstock/VCI price_board.

This is not a historical backfill. The VCI board exposes current-day accumulated
foreign buy/sell fields, so every run stores a timestamped snapshot that can
only become research-usable after enough forward history accrues.

Outputs:
    data/foreign_flow_forward/vci_price_board/snapshots/YYYY-MM-DD/*.parquet
    data/foreign_flow_forward/vci_price_board/latest_snapshot.parquet
    data/foreign_flow_forward/vci_price_board/daily_latest.parquet
    data/foreign_flow_forward/vci_price_board/manifest.json

Usage:
    python data_tools/collect_forward_foreign_flow.py --dry-run
    python data_tools/collect_forward_foreign_flow.py --tickers FPT,VCB,HPG
    python data_tools/collect_forward_foreign_flow.py --max-tickers 50
"""

from __future__ import annotations

import argparse
import json
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from path_utils import data_path
from vnstock import Vnstock

try:
    from stock_refresh_utils import atomic_write_parquet
except ModuleNotFoundError:
    from data_tools.stock_refresh_utils import atomic_write_parquet


SOURCE = "vnstock_vci_price_board"
OUT_ROOT = data_path("foreign_flow_forward/vci_price_board")
STOCK_DIR = data_path("stock")
MANIFEST_PATH = OUT_ROOT / "manifest.json"
LATEST_SNAPSHOT_PATH = OUT_ROOT / "latest_snapshot.parquet"
DAILY_LATEST_PATH = OUT_ROOT / "daily_latest.parquet"
EXCLUDE_DEFAULT = {"VNINDEX", "VN30"}

REQUIRED_SOURCE_COLUMNS = {
    "listing__symbol",
    "match__current_room",
    "match__total_room",
    "match__foreign_buy_volume",
    "match__foreign_sell_volume",
    "match__foreign_buy_value",
    "match__foreign_sell_value",
}
CONTRACT_COLUMNS = [
    "collected_at_utc",
    "source",
    "ticker",
    "exchange",
    "trading_date",
    "listing_sending_time",
    "match_sending_time",
    "transaction_time",
    "current_room",
    "total_room",
    "foreign_buy_volume",
    "foreign_sell_volume",
    "foreign_net_volume",
    "foreign_buy_value",
    "foreign_sell_value",
    "foreign_net_value",
    "foreign_room_used_ratio",
    "accumulated_volume",
    "accumulated_value",
    "match_price",
    "open_price",
    "reference_price",
    "ceiling_price",
    "floor_price",
]
NUMERIC_COLUMNS = [
    "current_room",
    "total_room",
    "foreign_buy_volume",
    "foreign_sell_volume",
    "foreign_net_volume",
    "foreign_buy_value",
    "foreign_sell_value",
    "foreign_net_value",
    "foreign_room_used_ratio",
    "accumulated_volume",
    "accumulated_value",
    "match_price",
    "open_price",
    "reference_price",
    "ceiling_price",
    "floor_price",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def snapshot_label(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_tickers(value: str | None) -> list[str]:
    if not value:
        return []
    tickers = [item.strip().upper() for item in value.split(",") if item.strip()]
    return sorted(dict.fromkeys(tickers))


def load_default_tickers() -> list[str]:
    tickers = []
    for path in STOCK_DIR.glob("gia_lich_su_*_1D.parquet"):
        ticker = path.stem.replace("gia_lich_su_", "").replace("_1D", "").upper()
        if ticker and ticker not in EXCLUDE_DEFAULT:
            tickers.append(ticker)
    return sorted(dict.fromkeys(tickers))


def chunked(values: list[str], chunk_size: int) -> Iterable[list[str]]:
    for start in range(0, len(values), chunk_size):
        yield values[start : start + chunk_size]


def flatten_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = [
            "__".join(str(part).strip() for part in col if str(part).strip())
            for col in out.columns.to_flat_index()
        ]
    else:
        out.columns = [str(col).strip().replace(".", "__") for col in out.columns]
    return out


def _col(frame: pd.DataFrame, name: str, default: object = pd.NA) -> pd.Series:
    if name in frame.columns:
        return frame[name]
    return pd.Series(default, index=frame.index)


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denom = _to_numeric(denominator).replace(0, np.nan)
    return _to_numeric(numerator) / denom


def validate_required_source_columns(frame: pd.DataFrame) -> list[str]:
    return sorted(REQUIRED_SOURCE_COLUMNS - set(frame.columns))


def normalize_price_board_frame(raw: pd.DataFrame, collected_at_utc: str) -> pd.DataFrame:
    flat = flatten_columns(raw)
    missing = validate_required_source_columns(flat)
    if missing:
        raise ValueError(f"price_board missing required columns: {missing}")

    out = flat.copy()
    out.insert(0, "source", SOURCE)
    out.insert(0, "collected_at_utc", collected_at_utc)

    out["ticker"] = _col(flat, "listing__symbol").astype(str).str.strip().str.upper()
    out["exchange"] = _col(flat, "listing__exchange")
    out["trading_date"] = pd.to_datetime(
        _col(flat, "listing__trading_date"), errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    out["listing_sending_time"] = _col(flat, "listing__sending_time")
    out["match_sending_time"] = _col(flat, "match__sending_time")
    out["transaction_time"] = _col(flat, "bid_ask__transaction_time")

    direct_map = {
        "current_room": "match__current_room",
        "total_room": "match__total_room",
        "foreign_buy_volume": "match__foreign_buy_volume",
        "foreign_sell_volume": "match__foreign_sell_volume",
        "foreign_buy_value": "match__foreign_buy_value",
        "foreign_sell_value": "match__foreign_sell_value",
        "accumulated_volume": "match__accumulated_volume",
        "accumulated_value": "match__accumulated_value",
        "match_price": "match__match_price",
        "open_price": "match__open_price",
        "reference_price": "match__reference_price",
        "ceiling_price": "match__ceiling_price",
        "floor_price": "match__floor_price",
    }
    for target, source in direct_map.items():
        out[target] = _to_numeric(_col(flat, source))

    out["foreign_net_volume"] = out["foreign_buy_volume"] - out["foreign_sell_volume"]
    out["foreign_net_value"] = out["foreign_buy_value"] - out["foreign_sell_value"]
    out["foreign_room_used_ratio"] = 1.0 - _safe_ratio(out["current_room"], out["total_room"])

    for column in NUMERIC_COLUMNS:
        if column in out.columns:
            out[column] = _to_numeric(out[column])

    ordered = [column for column in CONTRACT_COLUMNS if column in out.columns]
    raw_columns = [column for column in out.columns if column not in ordered]
    out = out[ordered + raw_columns]
    out = out[out["ticker"].notna() & out["ticker"].ne("")]
    return out.sort_values("ticker").reset_index(drop=True)


def fetch_price_board(tickers: list[str], chunk_size: int, delay: float) -> tuple[pd.DataFrame, list[dict[str, object]]]:
    frames = []
    failures: list[dict[str, object]] = []
    for index, symbols in enumerate(chunked(tickers, chunk_size), start=1):
        try:
            stock = Vnstock().stock(symbol=symbols[0], source="VCI")
            frame = stock.trading.price_board(symbols_list=symbols)
            if frame is not None and len(frame) > 0:
                frames.append(frame)
            else:
                failures.append({"chunk": index, "tickers": symbols, "error": "empty frame"})
        except Exception as exc:
            failures.append({"chunk": index, "tickers": symbols, "error": f"{type(exc).__name__}: {exc}"})
        if delay > 0 and index * chunk_size < len(tickers):
            time.sleep(delay)
    if not frames:
        return pd.DataFrame(), failures
    return pd.concat(frames, ignore_index=True), failures


def merge_daily_latest(existing: pd.DataFrame | None, snapshot: pd.DataFrame) -> pd.DataFrame:
    if existing is None or existing.empty:
        combined = snapshot.copy()
    else:
        columns = list(existing.columns)
        for column in snapshot.columns:
            if column not in columns:
                columns.append(column)
        older = existing.copy()
        newer = snapshot.copy()
        for column in columns:
            if column not in older.columns:
                older[column] = pd.NA
            if column not in newer.columns:
                newer[column] = pd.NA
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=(
                    "The behavior of DataFrame concatenation with empty or all-NA "
                    "entries is deprecated"
                ),
                category=FutureWarning,
            )
            combined = pd.concat([older[columns], newer[columns]], ignore_index=True)
    combined["collected_at_utc"] = pd.to_datetime(combined["collected_at_utc"], errors="coerce", utc=True)
    combined = combined.dropna(subset=["collected_at_utc", "ticker", "trading_date"])
    combined = (
        combined.sort_values("collected_at_utc")
        .drop_duplicates(subset=["trading_date", "ticker"], keep="last")
        .sort_values(["trading_date", "ticker"])
        .reset_index(drop=True)
    )
    combined["collected_at_utc"] = combined["collected_at_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return combined


def atomic_write_json(payload: dict[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(path)


def path_for_json(path: Path) -> str:
    try:
        return str(path.relative_to(data_path("")))
    except ValueError:
        return str(path)


def write_outputs(snapshot: pd.DataFrame, collected_at: datetime, failures: list[dict[str, object]]) -> dict[str, object]:
    label = snapshot_label(collected_at)
    day_dir = OUT_ROOT / "snapshots" / collected_at.date().isoformat()
    snapshot_path = day_dir / f"vci_price_board_foreign_flow_{label}.parquet"
    atomic_write_parquet(snapshot, snapshot_path)
    atomic_write_parquet(snapshot, LATEST_SNAPSHOT_PATH)

    existing_daily = pd.read_parquet(DAILY_LATEST_PATH) if DAILY_LATEST_PATH.exists() else None
    daily_latest = merge_daily_latest(existing_daily, snapshot)
    atomic_write_parquet(daily_latest, DAILY_LATEST_PATH)

    trading_dates = sorted(snapshot["trading_date"].dropna().astype(str).unique().tolist())
    manifest = {
        "contract": {
            "source": SOURCE,
            "forward_only": True,
            "not_backtestable_yet": True,
            "reason": "VCI price_board exposes current-day accumulated fields, not historical backfill.",
            "root": path_for_json(OUT_ROOT),
            "snapshot_path_pattern": "snapshots/YYYY-MM-DD/vci_price_board_foreign_flow_YYYYMMDDTHHMMSSZ.parquet",
            "latest_snapshot": path_for_json(LATEST_SNAPSHOT_PATH),
            "daily_latest": path_for_json(DAILY_LATEST_PATH),
            "snapshot_primary_key": ["collected_at_utc", "ticker"],
            "daily_latest_primary_key": ["trading_date", "ticker"],
            "required_source_columns": sorted(REQUIRED_SOURCE_COLUMNS),
            "contract_columns": CONTRACT_COLUMNS,
        },
        "last_run": {
            "collected_at_utc": format_utc(collected_at),
            "rows": int(len(snapshot)),
            "tickers": int(snapshot["ticker"].nunique()),
            "trading_dates": trading_dates,
            "snapshot": path_for_json(snapshot_path),
            "latest_snapshot": path_for_json(LATEST_SNAPSHOT_PATH),
            "daily_latest": path_for_json(DAILY_LATEST_PATH),
            "daily_latest_rows": int(len(daily_latest)),
            "failed_chunks": failures,
        },
    }
    atomic_write_json(manifest, MANIFEST_PATH)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect forward-only VCI price_board foreign-flow snapshots")
    parser.add_argument("--tickers", default=None, help="Comma-separated tickers. Defaults to all local HOSE 1D files.")
    parser.add_argument("--max-tickers", type=int, default=None, help="Limit the ticker list for smoke tests")
    parser.add_argument("--chunk-size", type=int, default=50, help="Symbols per price_board call")
    parser.add_argument("--delay", type=float, default=0.2, help="Delay between price_board chunks")
    parser.add_argument("--dry-run", action="store_true", help="Print contract and ticker count without network or writes")
    parser.add_argument("--no-write", action="store_true", help="Fetch and normalize, but do not write outputs")
    parser.add_argument("--require-complete", action="store_true", help="Exit non-zero if any chunk fails")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.chunk_size <= 0:
        raise ValueError("--chunk-size must be positive")
    if args.delay < 0:
        raise ValueError("--delay must be non-negative")
    if args.max_tickers is not None and args.max_tickers <= 0:
        raise ValueError("--max-tickers must be positive when set")

    tickers = parse_tickers(args.tickers) or load_default_tickers()
    if args.max_tickers is not None:
        tickers = tickers[: args.max_tickers]
    if not tickers:
        raise ValueError("No tickers selected")

    print(f"Selected tickers: {len(tickers)}")
    print(f"Output root: {OUT_ROOT}")
    print("Contract: forward-only current-day board snapshots; not historical/backtestable yet")
    if args.dry_run:
        print(f"[DRY RUN] First tickers: {tickers[:10]}")
        print(f"[DRY RUN] Required source columns: {sorted(REQUIRED_SOURCE_COLUMNS)}")
        return 0

    collected_at = utc_now()
    raw, failures = fetch_price_board(tickers, args.chunk_size, args.delay)
    if raw.empty:
        print(f"No rows collected. Failures: {failures}")
        return 1

    collected_at_label = format_utc(collected_at)
    snapshot = normalize_price_board_frame(raw, collected_at_label)
    missing_contract = [column for column in CONTRACT_COLUMNS if column not in snapshot.columns]
    if missing_contract:
        raise ValueError(f"normalized snapshot missing contract columns: {missing_contract}")

    print(
        f"Collected {len(snapshot)} rows / {snapshot['ticker'].nunique()} tickers "
        f"for trading dates {sorted(snapshot['trading_date'].dropna().astype(str).unique().tolist())}"
    )
    if failures:
        print(f"Failed chunks: {len(failures)}")
        if args.require_complete:
            print(json.dumps(failures, indent=2, ensure_ascii=False))
            return 2

    if args.no_write:
        print("[NO WRITE] Snapshot normalized successfully")
        return 0

    manifest = write_outputs(snapshot, collected_at, failures)
    print(f"Saved snapshot: data/{manifest['last_run']['snapshot']}")
    print(f"Saved latest: data/{manifest['last_run']['latest_snapshot']}")
    print(f"Saved daily latest: data/{manifest['last_run']['daily_latest']}")
    print(f"Saved manifest: data/{path_for_json(MANIFEST_PATH)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
