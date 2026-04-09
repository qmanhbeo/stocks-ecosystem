"""
H325: queueing / open-fill source gate.

Question:
    Does the canonical data warehouse contain any historical auction,
    order-book, opening-queue, or fine-minute source that can honestly test
    queue imbalance / open-fill pain?

Design:
    - inventory local candidate paths under root data/
    - separate true queue/order-book/fine-minute candidates from known reduced
      CafeF / VCI hourly OHLCV surfaces
    - save a source-gate result rather than inventing a weak daily proxy when
      the required microstructure data is absent
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from path_utils import data_path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.run_summary import write_run_summary  # noqa: E402

try:  # parquet metadata is much cheaper than loading every intraday file
    import pyarrow.parquet as pq
except Exception:  # pragma: no cover - pandas fallback keeps the gate usable
    pq = None


DATA_ROOT = data_path("")
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"

PATH_KEYWORDS = re.compile(
    r"auction|order[-_ ]?book|depth|queue|matchprice|matched|"
    r"bid[-_ ]?ask|ask[-_ ]?bid|bid[-_ ]?(price|volume|qty|queue)|"
    r"ask[-_ ]?(price|volume|qty|queue)|intraday|cafef|ssi|"
    r"(^|[/_.-])(ticks?|tickdata|1h|1m|5m|15m|30m|minute|min|open[-_ ]?fill)([/_.-]|$)",
    re.IGNORECASE,
)
QUEUE_PATH_KEYWORDS = re.compile(
    r"auction|order[-_ ]?book|depth|queue|matchprice|matched|"
    r"bid[-_ ]?ask|ask[-_ ]?bid|bid[-_ ]?(price|volume|qty|queue)|"
    r"ask[-_ ]?(price|volume|qty|queue)|(^|[/_.-])(ticks?|tickdata)([/_.-]|$)",
    re.IGNORECASE,
)
FINE_INTERVAL_PATH = re.compile(
    r"(^|[/_.-])(1m|5m|15m|30m|60s|300s|minute|min)([/_.-]|$)",
    re.IGNORECASE,
)
HOURLY_PATH = re.compile(r"(^|[/_.-])1h([/_.-]|$)", re.IGNORECASE)

OHLCV_COLUMNS = {"time", "date", "ticker", "open", "high", "low", "close", "volume", "value"}
ORDERBOOK_COLUMN_EXACT = {
    "bid",
    "ask",
    "best_bid",
    "best_ask",
    "bid_price",
    "ask_price",
    "bid_volume",
    "ask_volume",
    "bid_qty",
    "ask_qty",
    "bid_value",
    "ask_value",
    "total_bid",
    "total_ask",
    "buy_queue",
    "sell_queue",
    "queue",
    "depth",
    "order_book",
    "order_id",
    "match_type",
    "match_price",
    "match_volume",
    "matched_price",
    "matched_volume",
    "side",
}
ORDERBOOK_COLUMN_TOKEN_PAT = re.compile(
    r"(^|_)(bid|ask|best_bid|best_ask|depth|queue|order_book|order_id|"
    r"match_type|match_price|match_volume|matched_price|matched_volume|"
    r"buy_queue|sell_queue|total_bid|total_ask|side)(_|$)",
    re.IGNORECASE,
)
KNOWN_REDUCED_PATH_CLASSES = {
    "reduced_hourly_cafef_raw",
    "reduced_hourly_cafef_adjusted",
    "reduced_hourly_legacy",
    "cafef_hourly_year_part",
    "cafef_adjustment_factor",
    "derived_intraday_daily",
}

SAMPLE_LIMIT_BY_CLASS = {
    "possible_queue_orderbook_path": 40,
    "possible_fine_minute_path": 40,
    "intraday_other": 20,
    "reduced_hourly_cafef_raw": 12,
    "reduced_hourly_cafef_adjusted": 12,
    "reduced_hourly_legacy": 12,
    "cafef_hourly_year_part": 12,
    "cafef_adjustment_factor": 6,
    "derived_intraday_daily": 10,
}


def _json_safe(value: object):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if value is pd.NaT:
        return None
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        if pd.isna(value):
            return None
        return value.item()
    if isinstance(value, float) and pd.isna(value):
        return None
    return value


def _rel(path: Path) -> str:
    return str(path.relative_to(DATA_ROOT))


def _classify_path(path: Path) -> str:
    rel = _rel(path).replace("\\", "/")
    lower = rel.lower()
    name = path.name.lower()

    if "stock/_cafef_intraday_parts/" in lower:
        return "cafef_hourly_year_part"
    if "stock/_cafef_adjustment_factors/" in lower:
        return "cafef_adjustment_factor"
    if re.match(r"stock/gia_lich_su_.+_1h_cafef_adj\.parquet$", lower):
        return "reduced_hourly_cafef_adjusted"
    if re.match(r"stock/gia_lich_su_.+_1h_cafef\.parquet$", lower):
        return "reduced_hourly_cafef_raw"
    if re.match(r"stock/gia_lich_su_.+_1h\.parquet$", lower):
        return "reduced_hourly_legacy"
    if lower == "features/fpt_intraday_daily.parquet":
        return "derived_intraday_daily"
    if "barrier_depth" in lower:
        return "barrier_depth_feature_not_orderbook"
    if FINE_INTERVAL_PATH.search(lower):
        return "possible_fine_minute_path"
    if QUEUE_PATH_KEYWORDS.search(lower):
        return "possible_queue_orderbook_path"
    if "intraday" in lower or "ssi" in lower or HOURLY_PATH.search(name):
        return "intraday_other"
    return "name_only_candidate"


def _read_parquet_schema(path: Path) -> tuple[list[str], int | None, str | None]:
    if path.suffix.lower() != ".parquet":
        return [], None, None
    try:
        if pq is not None:
            parquet_file = pq.ParquetFile(path)
            row_count = parquet_file.metadata.num_rows if parquet_file.metadata else None
            return [str(name) for name in parquet_file.schema.names], row_count, None
        frame = pd.read_parquet(path)
        return [str(column) for column in frame.columns], int(len(frame)), None
    except Exception as exc:  # pragma: no cover - inventory should keep going
        return [], None, f"{type(exc).__name__}: {exc}"


def _read_json_keys(path: Path) -> tuple[list[str], int | None, str | None]:
    if path.suffix.lower() != ".json":
        return [], None, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return sorted(str(key) for key in payload.keys()), None, None
        return [], None, None
    except Exception as exc:  # pragma: no cover
        return [], None, f"{type(exc).__name__}: {exc}"


def _column_hits(columns: list[str]) -> tuple[list[str], list[str]]:
    order_hits = []
    for column in columns:
        lower = column.lower()
        if lower in ORDERBOOK_COLUMN_EXACT or ORDERBOOK_COLUMN_TOKEN_PAT.search(lower):
            order_hits.append(column)
    order_hits = sorted(order_hits)
    ohlcv_hits = sorted(column for column in columns if column.lower() in OHLCV_COLUMNS)
    return order_hits, ohlcv_hits


def _time_ticker_stats(path: Path, columns: list[str]) -> dict[str, object]:
    lower_to_col = {column.lower(): column for column in columns}
    time_col = lower_to_col.get("time") or lower_to_col.get("date")
    ticker_col = lower_to_col.get("ticker")
    if path.suffix.lower() != ".parquet" or time_col is None:
        return {}

    selected = [time_col]
    if ticker_col and ticker_col not in selected:
        selected.append(ticker_col)

    try:
        frame = pd.read_parquet(path, columns=selected)
    except Exception as exc:  # pragma: no cover
        return {"sample_error": f"{type(exc).__name__}: {exc}"}
    if frame.empty:
        return {
            "time_min": None,
            "time_max": None,
            "ticker_count": 0 if ticker_col else None,
            "date_count": 0,
            "median_bars_per_ticker_day": None,
            "max_bars_per_ticker_day": None,
            "has_intraday_timestamps": False,
        }

    times = pd.to_datetime(frame[time_col], errors="coerce")
    valid = times.notna()
    out: dict[str, object] = {
        "time_min": _json_safe(times[valid].min()) if valid.any() else None,
        "time_max": _json_safe(times[valid].max()) if valid.any() else None,
        "date_count": int(times[valid].dt.normalize().nunique()) if valid.any() else 0,
        "has_intraday_timestamps": bool(
            (
                (times[valid].dt.hour != 0)
                | (times[valid].dt.minute != 0)
                | (times[valid].dt.second != 0)
            ).any()
        )
        if valid.any()
        else False,
    }

    if ticker_col:
        out["ticker_count"] = int(frame[ticker_col].astype(str).nunique())
        group_frame = pd.DataFrame(
            {
                "ticker": frame.loc[valid, ticker_col].astype(str).to_numpy(),
                "date": times[valid].dt.normalize().to_numpy(),
            }
        )
        counts = group_frame.groupby(["ticker", "date"], observed=True).size()
    else:
        out["ticker_count"] = None
        group_frame = pd.DataFrame({"date": times[valid].dt.normalize().to_numpy()})
        counts = group_frame.groupby("date", observed=True).size()

    if len(counts) > 0:
        out["median_bars_per_ticker_day"] = float(counts.median())
        out["max_bars_per_ticker_day"] = int(counts.max())
    else:
        out["median_bars_per_ticker_day"] = None
        out["max_bars_per_ticker_day"] = None
    return out


def _classify_schema(path_class: str, columns: list[str], row: dict[str, object]) -> str:
    lower_cols = {column.lower() for column in columns}
    order_hits, ohlcv_hits = _column_hits(columns)
    has_time = "time" in lower_cols or "date" in lower_cols
    has_intraday = bool(row.get("has_intraday_timestamps"))
    median_bars = row.get("median_bars_per_ticker_day")
    try:
        median_bars_float = float(median_bars) if median_bars is not None else None
    except (TypeError, ValueError):
        median_bars_float = None

    if path_class in {
        "reduced_hourly_cafef_raw",
        "reduced_hourly_cafef_adjusted",
        "reduced_hourly_legacy",
        "cafef_hourly_year_part",
    }:
        return "reduced_hourly_ohlcv"
    if path_class == "cafef_adjustment_factor":
        return "adjustment_audit"
    if path_class == "derived_intraday_daily":
        return "derived_daily_intraday_feature"
    if order_hits and has_time and has_intraday:
        return "possible_queue_or_orderbook"
    if path_class == "possible_queue_orderbook_path" and order_hits:
        return "possible_queue_or_orderbook"
    if path_class == "possible_fine_minute_path":
        return "possible_fine_minute_ohlcv"
    if median_bars_float is not None and median_bars_float > 8:
        return "possible_fine_minute_ohlcv"
    if {"open", "high", "low", "close", "volume"} <= lower_cols and has_intraday:
        return "intraday_ohlcv_not_queue"
    if ohlcv_hits:
        return "daily_or_reduced_ohlcv"
    return "schema_not_microstructure"


def _iter_candidate_paths() -> list[Path]:
    skip_parts = {"news", "llm_cache"}
    paths: list[Path] = []
    for path in DATA_ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(DATA_ROOT)
        if rel.parts and rel.parts[0] in skip_parts:
            continue
        if PATH_KEYWORDS.search(str(rel)):
            paths.append(path)
    return sorted(paths)


def _scan_candidates() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    samples_by_class: Counter[str] = Counter()

    for path in _iter_candidate_paths():
        path_class = _classify_path(path)
        rel = _rel(path)
        columns: list[str] = []
        row_count: int | None = None
        read_error: str | None = None
        if path.suffix.lower() == ".parquet":
            columns, row_count, read_error = _read_parquet_schema(path)
        elif path.suffix.lower() == ".json":
            columns, row_count, read_error = _read_json_keys(path)

        order_hits, ohlcv_hits = _column_hits(columns)
        sample_limit = SAMPLE_LIMIT_BY_CLASS.get(path_class, 4)
        should_sample = path.suffix.lower() == ".parquet" and samples_by_class[path_class] < sample_limit

        row: dict[str, object] = {
            "path": rel,
            "suffix": path.suffix,
            "size_bytes": int(path.stat().st_size),
            "path_class": path_class,
            "rows": row_count,
            "columns": columns,
            "orderbook_column_hits": order_hits,
            "ohlcv_column_hits": ohlcv_hits,
            "schema_sampled": should_sample,
            "read_error": read_error,
            "time_min": None,
            "time_max": None,
            "ticker_count": None,
            "date_count": None,
            "median_bars_per_ticker_day": None,
            "max_bars_per_ticker_day": None,
            "has_intraday_timestamps": None,
            "sample_error": None,
        }
        if should_sample:
            samples_by_class[path_class] += 1
            row.update(_time_ticker_stats(path, columns))
        row["schema_class"] = _classify_schema(path_class, columns, row)
        rows.append(row)

    return pd.DataFrame(rows)


def _representative_samples(inventory: pd.DataFrame) -> list[dict[str, object]]:
    if inventory.empty:
        return []
    sample_classes = [
        "possible_queue_orderbook_path",
        "possible_fine_minute_path",
        "reduced_hourly_cafef_adjusted",
        "reduced_hourly_cafef_raw",
        "reduced_hourly_legacy",
        "cafef_hourly_year_part",
        "derived_intraday_daily",
        "cafef_adjustment_factor",
    ]
    samples: list[pd.DataFrame] = []
    for path_class in sample_classes:
        subset = inventory.loc[
            inventory["path_class"].eq(path_class) & inventory["schema_sampled"].fillna(False)
        ].head(3)
        if not subset.empty:
            samples.append(subset)
    if not samples:
        return []
    out = pd.concat(samples, ignore_index=True)
    keep_cols = [
        "path",
        "path_class",
        "schema_class",
        "rows",
        "columns",
        "orderbook_column_hits",
        "time_min",
        "time_max",
        "ticker_count",
        "date_count",
        "median_bars_per_ticker_day",
        "max_bars_per_ticker_day",
        "has_intraday_timestamps",
    ]
    return _json_safe(out[keep_cols].to_dict(orient="records"))


def _compact_class_counts(inventory: pd.DataFrame, column: str) -> dict[str, int]:
    if inventory.empty or column not in inventory.columns:
        return {}
    return {str(k): int(v) for k, v in inventory[column].value_counts().sort_index().items()}


def _save_inventory(inventory: pd.DataFrame, path: Path) -> None:
    out = inventory.copy()
    for column in ["columns", "orderbook_column_hits", "ohlcv_column_hits"]:
        if column in out.columns:
            out[column] = out[column].map(
                lambda value: json.dumps(value, ensure_ascii=False)
                if isinstance(value, list)
                else value
            )
    out.to_parquet(path, index=False)


def main() -> int:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    inventory = _scan_candidates()
    if inventory.empty:
        true_queue_candidates = inventory.copy()
        true_fine_minute_candidates = inventory.copy()
    else:
        true_queue_candidates = inventory.loc[
            inventory["schema_class"].eq("possible_queue_or_orderbook")
            & ~inventory["path_class"].isin(KNOWN_REDUCED_PATH_CLASSES)
        ].copy()
        true_fine_minute_candidates = inventory.loc[
            inventory["schema_class"].eq("possible_fine_minute_ohlcv")
            & ~inventory["path_class"].isin(KNOWN_REDUCED_PATH_CLASSES)
        ].copy()

    reduced_hourly_count = int(
        inventory["path_class"].isin(
            {
                "reduced_hourly_cafef_raw",
                "reduced_hourly_cafef_adjusted",
                "reduced_hourly_legacy",
                "cafef_hourly_year_part",
            }
        ).sum()
    ) if not inventory.empty else 0

    if len(true_queue_candidates) or len(true_fine_minute_candidates):
        verdict = "NEUTRAL"
        branch_decision = (
            "A possible microstructure source exists locally. Validate ticker/date/time "
            "integrity and run a tiny blocked-buy / next-open drift pilot before any full "
            "feature build."
        )
    else:
        verdict = "SKIP"
        branch_decision = (
            "No local historical auction, order-book, opening-queue, or fine-minute source "
            "exists in the canonical warehouse. The available intraday surface is reduced "
            "hourly OHLCV plus daily derived features, so queue imbalance / open-fill pain "
            "cannot be honestly tested yet."
        )

    inventory_path = OUT_DIR / f"{ts}_h325_queueing_open_fill_source_inventory.parquet"
    details_path = DETAILS_DIR / f"{ts}_research_branch_queueing_open_fill_source_details.json"
    _save_inventory(inventory, inventory_path)

    path_counts = _compact_class_counts(inventory, "path_class")
    schema_counts = _compact_class_counts(inventory, "schema_class")
    sampled_hourly = inventory.loc[
        inventory["path_class"].isin(
            ["reduced_hourly_cafef_raw", "reduced_hourly_cafef_adjusted", "reduced_hourly_legacy"]
        )
        & inventory["schema_sampled"].fillna(False)
    ].copy() if not inventory.empty else pd.DataFrame()
    if not sampled_hourly.empty:
        median_bars = pd.to_numeric(
            sampled_hourly["median_bars_per_ticker_day"], errors="coerce"
        ).dropna()
        hourly_snapshot = {
            "sampled_files": int(len(sampled_hourly)),
            "median_of_file_median_bars_per_day": float(median_bars.median())
            if len(median_bars)
            else None,
            "max_observed_bars_per_day_in_samples": int(
                pd.to_numeric(sampled_hourly["max_bars_per_ticker_day"], errors="coerce")
                .dropna()
                .max()
            )
            if pd.to_numeric(sampled_hourly["max_bars_per_ticker_day"], errors="coerce").notna().any()
            else None,
        }
    else:
        hourly_snapshot = {
            "sampled_files": 0,
            "median_of_file_median_bars_per_day": None,
            "max_observed_bars_per_day_in_samples": None,
        }

    details = {
        "branch_decision": branch_decision,
        "source_contract": {
            "required_for_alpha_pilot": (
                "historical ticker-time rows with auction/order-book/queue fields, or "
                "fine-minute OHLCV substantially finer than the local hourly bars"
            ),
            "explicitly_not_sufficient": (
                "CafeF/VCI 1H OHLCV, adjustment factors, daily intraday-shape summaries, "
                "or price-limit blocked-buy proxies"
            ),
        },
        "path_class_counts": path_counts,
        "schema_class_counts": schema_counts,
        "reduced_hourly_count": reduced_hourly_count,
        "true_queue_candidates": _json_safe(true_queue_candidates.to_dict(orient="records")),
        "true_fine_minute_candidates": _json_safe(
            true_fine_minute_candidates.to_dict(orient="records")
        ),
        "representative_samples": _representative_samples(inventory),
        "hourly_snapshot": hourly_snapshot,
        "data_operator_notes": {
            "cafef_fetcher": "data_tools/fetch_cafef_intraday.py writes 1H_CAFEF OHLCV bars.",
            "cafef_adjuster": "data_tools/adjust_cafef_intraday_to_vci.py writes 1H_CAFEF_ADJ.",
            "ssi_fetcher": "data_tools/fetch_ssi_intraday.py can fetch OHLCV with credentials, but is not an open local queue source.",
            "current_local_state": "local order-book / auction / queue history is absent.",
        },
    }
    details_path.write_text(json.dumps(_json_safe(details), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "verdict": verdict,
        "branch_decision": branch_decision,
        "candidate_paths": int(len(inventory)),
        "path_class_counts": path_counts,
        "schema_class_counts": schema_counts,
        "reduced_hourly_source_paths": reduced_hourly_count,
        "true_queue_or_orderbook_candidates": int(len(true_queue_candidates)),
        "true_fine_minute_candidates": int(len(true_fine_minute_candidates)),
        "hourly_snapshot": hourly_snapshot,
    }
    artifacts = {
        "inventory": inventory_path,
        "details": details_path,
    }
    metadata = {
        "question": "Is queue/open-fill microstructure data available locally?",
        "source_gate": "No alpha test is run unless true auction/order-book/queue or fine-minute data exists.",
        "data_root": DATA_ROOT,
    }
    write_run_summary(
        ts=ts,
        mode="research_branch_queueing_open_fill_source",
        name="h325_queueing_open_fill_source",
        summary=summary,
        artifacts=artifacts,
        metadata=metadata,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
