"""
Build the scoped C16 order-pressure feature surface.

The published artifact is:
  data/features/xs_order_pressure_daily.parquet

It is derived from the raw CafeF order-statistics archive and the shared
tradability surface. The H359 promoted variant blends the order rank into a
base selector only when the row is buyable at the next open:

  blended_score = (1 - w) * base_score + w * order_volume_ratio_rank

where w is `order_pressure_h359_blend_weight`.

By default the builder stops at 2025-12-31 to preserve the 2026 lockbox used by
the research branch. Pass both `--end-date` and `--include-2026` for an explicit
live/monitoring refresh.

Usage:
  python data_tools/build_order_pressure_features.py
  python data_tools/build_order_pressure_features.py --end-date 2025-12-31
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from path_utils import data_path

from src.run_summary import write_run_summary


ORDER_STATS_PATH = data_path("order_stats/cafef/order_stats_daily.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
OUT_PATH = data_path("features/xs_order_pressure_daily.parquet")

DEFAULT_END_DATE = "2025-12-31"
H359_BLEND_WEIGHT = 0.05


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the C16 order-pressure feature artifact.")
    parser.add_argument("--order-stats", type=Path, default=ORDER_STATS_PATH)
    parser.add_argument("--tradability", type=Path, default=TRADABILITY_PATH)
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    parser.add_argument("--start-date", type=str, default=None)
    parser.add_argument("--end-date", type=str, default=DEFAULT_END_DATE)
    parser.add_argument(
        "--include-2026",
        action="store_true",
        help="Explicitly allow rows dated 2026-01-01 or later.",
    )
    return parser.parse_args()


def _parse_optional_date(value: str | None, *, name: str) -> pd.Timestamp | None:
    if value is None or str(value).strip() == "":
        return None
    parsed = pd.to_datetime(value, errors="raise").normalize()
    if pd.isna(parsed):
        raise ValueError(f"{name} could not be parsed as a date: {value!r}")
    return pd.Timestamp(parsed)


def _check_lockbox(end_date: pd.Timestamp | None, *, include_2026: bool) -> None:
    if include_2026:
        return
    if end_date is None or end_date >= pd.Timestamp("2026-01-01"):
        raise ValueError(
            "This builder defaults to the research lockbox. Pass --end-date 2025-12-31 "
            "or use --include-2026 for an explicit live/monitoring refresh."
        )


def _ratio(left: pd.Series, right: pd.Series) -> pd.Series:
    left_num = pd.to_numeric(left, errors="coerce")
    right_num = pd.to_numeric(right, errors="coerce")
    denom = (left_num + right_num).replace(0.0, np.nan)
    return (left_num - right_num).div(denom).replace([np.inf, -np.inf], np.nan)


def _filter_dates(frame: pd.DataFrame, *, start_date: pd.Timestamp | None, end_date: pd.Timestamp | None) -> pd.DataFrame:
    out = frame
    if start_date is not None:
        out = out.loc[out["time"] >= start_date]
    if end_date is not None:
        out = out.loc[out["time"] <= end_date]
    return out


def _load_order_stats(
    path: Path,
    *,
    start_date: pd.Timestamp | None,
    end_date: pd.Timestamp | None,
) -> tuple[pd.DataFrame, int]:
    order = pd.read_parquet(
        path,
        columns=[
            "ticker",
            "date",
            "buy_order_volume",
            "sell_order_volume",
        ],
    ).copy()
    order = order.rename(columns={"date": "time"})
    order["time"] = pd.to_datetime(order["time"], errors="coerce").dt.normalize()
    order["ticker"] = order["ticker"].astype(str).str.upper()
    order = order.dropna(subset=["time", "ticker"])
    order = _filter_dates(order, start_date=start_date, end_date=end_date)
    order = order.sort_values(["time", "ticker"]).reset_index(drop=True)

    duplicate_mask = order.duplicated(["time", "ticker"], keep="last")
    duplicate_rows = int(duplicate_mask.sum())
    if duplicate_rows:
        order = order.loc[~duplicate_mask].copy()

    order["order_volume_ratio"] = _ratio(order["buy_order_volume"], order["sell_order_volume"])
    order["order_volume_ratio_rank"] = (
        order["order_volume_ratio"]
        .groupby(order["time"], sort=False)
        .rank(method="average", pct=True, ascending=True)
    )
    return order[["time", "ticker", "order_volume_ratio", "order_volume_ratio_rank"]], duplicate_rows


def _load_tradability(
    path: Path,
    *,
    start_date: pd.Timestamp | None,
    end_date: pd.Timestamp | None,
) -> pd.DataFrame:
    tradability = pd.read_parquet(
        path,
        columns=["time", "ticker", "can_buy_next_open"],
    ).copy()
    tradability["time"] = pd.to_datetime(tradability["time"], errors="coerce").dt.normalize()
    tradability["ticker"] = tradability["ticker"].astype(str).str.upper()
    tradability = tradability.dropna(subset=["time", "ticker"])
    tradability = _filter_dates(tradability, start_date=start_date, end_date=end_date)
    tradability = tradability.sort_values(["time", "ticker"]).drop_duplicates(["time", "ticker"], keep="last")
    return tradability.reset_index(drop=True)


def build_order_pressure_features(
    order_stats_path: Path,
    tradability_path: Path,
    *,
    start_date: pd.Timestamp | None,
    end_date: pd.Timestamp | None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    order, duplicate_order_rows = _load_order_stats(order_stats_path, start_date=start_date, end_date=end_date)
    tradability = _load_tradability(tradability_path, start_date=start_date, end_date=end_date)

    features = order.merge(tradability, on=["time", "ticker"], how="left", validate="one_to_one")
    has_tradability = features["can_buy_next_open"].notna()
    features.loc[~has_tradability, "can_buy_next_open"] = False
    features["can_buy_next_open"] = features["can_buy_next_open"].astype(bool)
    features["order_pressure_available"] = features["order_volume_ratio_rank"].notna()
    features["order_pressure_h359_active"] = (
        features["order_pressure_available"] & features["can_buy_next_open"]
    )
    features["order_pressure_h359_blend_weight"] = np.where(
        features["order_pressure_h359_active"],
        H359_BLEND_WEIGHT,
        0.0,
    ).astype(float)

    ordered_columns = [
        "time",
        "ticker",
        "order_volume_ratio",
        "order_volume_ratio_rank",
        "order_pressure_available",
        "can_buy_next_open",
        "order_pressure_h359_active",
        "order_pressure_h359_blend_weight",
    ]
    features = features[ordered_columns].sort_values(["time", "ticker"]).reset_index(drop=True)

    row_count = int(len(features))
    active_rows = int(features["order_pressure_h359_active"].sum())
    rank_rows = int(features["order_volume_ratio_rank"].notna().sum())
    tradability_rows = int(has_tradability.sum())
    summary = {
        "row_count": row_count,
        "ticker_count": int(features["ticker"].nunique()) if row_count else 0,
        "date_count": int(features["time"].nunique()) if row_count else 0,
        "min_date": features["time"].min() if row_count else None,
        "max_date": features["time"].max() if row_count else None,
        "rank_rows": rank_rows,
        "rank_coverage": float(rank_rows / row_count) if row_count else 0.0,
        "active_rows": active_rows,
        "active_coverage": float(active_rows / row_count) if row_count else 0.0,
        "tradability_rows": tradability_rows,
        "tradability_coverage": float(tradability_rows / row_count) if row_count else 0.0,
        "duplicate_order_rows_removed": duplicate_order_rows,
    }
    return features, summary


def _write_parquet_atomic(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    frame.to_parquet(tmp_path, index=False)
    tmp_path.replace(path)


def main() -> None:
    args = parse_args()
    start_date = _parse_optional_date(args.start_date, name="start-date")
    end_date = _parse_optional_date(args.end_date, name="end-date")
    _check_lockbox(end_date, include_2026=bool(args.include_2026))

    print("Building C16 order-pressure features...")
    print(f"  order stats: {args.order_stats}")
    print(f"  tradability: {args.tradability}")
    print(f"  date range: {start_date.date() if start_date is not None else 'start'} to {end_date.date() if end_date is not None else 'end'}")

    features, summary = build_order_pressure_features(
        Path(args.order_stats),
        Path(args.tradability),
        start_date=start_date,
        end_date=end_date,
    )
    _write_parquet_atomic(features, Path(args.out))

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    summary_path = write_run_summary(
        ts=ts,
        mode="published_feature_order_pressure_daily",
        name="build_order_pressure_features",
        summary=summary,
        artifacts={"output": str(Path(args.out))},
        metadata={
            "order_stats_path": str(Path(args.order_stats)),
            "tradability_path": str(Path(args.tradability)),
            "start_date": str(start_date.date()) if start_date is not None else None,
            "end_date": str(end_date.date()) if end_date is not None else None,
            "include_2026": bool(args.include_2026),
            "h359_blend_formula": "(1 - w) * base_score + w * order_volume_ratio_rank",
            "h359_blend_weight_column": "order_pressure_h359_blend_weight",
        },
    )

    print(
        f"Saved {summary['row_count']:,} rows, {summary['ticker_count']:,} tickers, "
        f"{summary['date_count']:,} dates -> {args.out}"
    )
    print(
        f"  active rows: {summary['active_rows']:,} "
        f"({summary['active_coverage'] * 100:.2f}%); summary -> {summary_path}"
    )


if __name__ == "__main__":
    main()
