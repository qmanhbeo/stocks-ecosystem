#!/usr/bin/env python3
"""Export migration-ready C23-family signal bundle for heuristic-trader.

Export-only contract:
- Use earliest available S1 rows (historical + live when present).
- Allow forward export window up to caller-provided end-date.
- Preserve rows where possible; avoid arbitrary early-date dropping.

Default output (for migration):
  data/features/xs_heuristic_signal_bundle.parquet
  data/features/xs_heuristic_signal_bundle_manifest.json
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.artifact_contract import (
    atomic_write_parquet,
    build_input_fingerprint,
    validate_required_columns,
    validate_unique_keys,
    write_manifest,
)
from src.repo_paths import data_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export heuristic-trader signal bundle from alpha-lab.")
    parser.add_argument(
        "--s1-historical-path",
        type=str,
        default=str(data_path("features/xs_barrier_vol_1d_hose_full.parquet")),
    )
    parser.add_argument(
        "--s1-live-path",
        type=str,
        default=str(data_path("features/xs_barrier_vol_1d_hose_live_current.parquet")),
    )
    parser.add_argument(
        "--order-stats-path",
        type=str,
        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")),
    )
    parser.add_argument(
        "--tradability-path",
        type=str,
        default=str(data_path("features/execution/tradability_daily.parquet")),
    )
    parser.add_argument(
        "--output-path",
        type=str,
        default=str(data_path("features/xs_heuristic_signal_bundle.parquet")),
    )
    parser.add_argument(
        "--manifest-path",
        type=str,
        default=str(data_path("features/xs_heuristic_signal_bundle_manifest.json")),
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Inclusive start date (YYYY-MM-DD). Default: earliest available S1 row.",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default="2026-03-31",
        help="Inclusive end date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--exclude-live",
        action="store_true",
        help="Ignore live S1 surface even if present.",
    )
    return parser.parse_args()


def _parse_price_change(value: object) -> float:
    if pd.isna(value):
        return np.nan
    match = re.search(r"\(\s*([+-]?[\d,]+)\s*%\)", str(value))
    if not match:
        return np.nan
    return float(match.group(1).replace(",", "."))


def _load_s1_union(args: argparse.Namespace) -> pd.DataFrame:
    required = ["time", "ticker", "xs_proba", "actual"]
    frames: list[pd.DataFrame] = []

    hist_path = Path(args.s1_historical_path)
    if not hist_path.exists():
        raise FileNotFoundError(f"missing S1 historical path: {hist_path}")
    frames.append(pd.read_parquet(hist_path, columns=required))

    live_path = Path(args.s1_live_path)
    if (not args.exclude_live) and live_path.exists():
        frames.append(pd.read_parquet(live_path, columns=required))

    s1 = pd.concat(frames, ignore_index=True)
    s1["time"] = pd.to_datetime(s1["time"], errors="coerce").dt.normalize()
    s1 = s1.dropna(subset=["time", "ticker"]).copy()
    s1["ticker"] = s1["ticker"].astype(str).str.upper()
    s1["s1_xs_proba"] = pd.to_numeric(s1["xs_proba"], errors="coerce")
    s1["s1_barrier_hit_1d"] = pd.to_numeric(s1["actual"], errors="coerce")
    s1 = s1[["time", "ticker", "s1_xs_proba", "s1_barrier_hit_1d"]]

    # Keep one row per key if historical/live overlap.
    s1 = s1.sort_values(["time", "ticker"]).drop_duplicates(["time", "ticker"], keep="last")

    start_ts = pd.to_datetime(args.start_date).normalize() if args.start_date else None
    end_ts = pd.to_datetime(args.end_date).normalize() if args.end_date else None
    if start_ts is not None:
        s1 = s1[s1["time"] >= start_ts]
    if end_ts is not None:
        s1 = s1[s1["time"] <= end_ts]

    return s1.reset_index(drop=True)


def _load_ohlcv_amihud(end_ts: pd.Timestamp | None) -> pd.DataFrame:
    stock_dir = Path(data_path("stock"))
    parts: list[pd.DataFrame] = []
    for path in stock_dir.glob("gia_lich_su_*_1D.parquet"):
        try:
            one = pd.read_parquet(path)
            ticker = path.stem.replace("gia_lich_su_", "").replace("_1D", "")
            one["ticker"] = ticker
            parts.append(one)
        except Exception:
            continue
    if not parts:
        raise RuntimeError("No OHLCV files available under data/stock")

    ohlcv = pd.concat(parts, ignore_index=True)
    ohlcv = ohlcv.rename(columns={"date": "time"})
    ohlcv["time"] = pd.to_datetime(ohlcv["time"], errors="coerce").dt.normalize()
    ohlcv = ohlcv.dropna(subset=["time", "ticker", "close", "volume"]).copy()
    if end_ts is not None:
        ohlcv = ohlcv[ohlcv["time"] <= end_ts].copy()

    ohlcv = ohlcv.sort_values(["ticker", "time"]).copy()
    ohlcv["daily_return"] = ohlcv.groupby("ticker")["close"].pct_change(fill_method=None)
    ohlcv["daily_return_abs"] = ohlcv["daily_return"].abs()
    ohlcv["turnover_bil"] = (ohlcv["close"] * ohlcv["volume"]) / 1e9
    ohlcv["amihud"] = ohlcv["daily_return_abs"] / (ohlcv["turnover_bil"] + 1e-9)
    ohlcv["amihud_20d_avg"] = ohlcv.groupby("ticker")["amihud"].transform(
        lambda s: s.rolling(window=20, min_periods=10).mean()
    )

    return ohlcv[["time", "ticker", "amihud_20d_avg", "close"]]


def _load_order_stats(end_ts: pd.Timestamp | None) -> pd.DataFrame:
    order_stats = pd.read_parquet(data_path("order_stats/cafef/order_stats_daily.parquet"))
    order_stats = order_stats.rename(columns={"date": "time"})
    order_stats["time"] = pd.to_datetime(order_stats["time"], errors="coerce").dt.normalize()
    if end_ts is not None:
        order_stats = order_stats[order_stats["time"] <= end_ts].copy()

    order_stats["pct_change"] = order_stats["price_change_raw"].apply(_parse_price_change)
    order_stats["total_volume"] = order_stats["buy_order_volume"] + order_stats["sell_order_volume"]

    return order_stats[
        [
            "time",
            "ticker",
            "pct_change",
            "total_volume",
            "buy_order_volume",
            "sell_order_volume",
            "buy_order_count",
            "sell_order_count",
        ]
    ]


def _build_bundle(args: argparse.Namespace) -> pd.DataFrame:
    end_ts = pd.to_datetime(args.end_date).normalize() if args.end_date else None

    panel = _load_s1_union(args)
    if panel.empty:
        raise ValueError("S1 union is empty for requested date window")

    ohlcv = _load_ohlcv_amihud(end_ts)
    panel = panel.merge(ohlcv, on=["time", "ticker"], how="left")

    order_stats = _load_order_stats(end_ts)
    panel = panel.merge(order_stats, on=["time", "ticker"], how="left")

    trad = pd.read_parquet(args.tradability_path)
    trad = trad.rename(columns={"date": "time"}) if "date" in trad.columns else trad
    trad["time"] = pd.to_datetime(trad["time"], errors="coerce").dt.normalize()
    if end_ts is not None:
        trad = trad[trad["time"] <= end_ts].copy()
    panel = panel.merge(
        trad[["time", "ticker", "can_buy_next_open", "can_sell_next_open"]],
        on=["time", "ticker"],
        how="left",
    )

    panel = panel.sort_values(["ticker", "time"]).copy()

    panel["pct_change_vol"] = panel.groupby("ticker")["pct_change"].transform(
        lambda s: s.rolling(window=5, min_periods=3).std()
    )
    panel["vol_change"] = panel.groupby("ticker")["pct_change_vol"].transform(lambda s: s.diff())

    panel["vol_rank"] = panel.groupby("time", sort=False)["vol_change"].rank(method="average", pct=True)
    panel["amihud_rank"] = panel.groupby("time", sort=False)["amihud_20d_avg"].rank(method="average", pct=True)
    panel["pct_rank"] = panel.groupby("time", sort=False)["pct_change"].rank(method="average", pct=True)

    panel["vol_expansion"] = panel["vol_rank"] >= 0.8
    panel["high_illiq"] = panel["amihud_rank"] >= 0.8

    panel["buy_sell_imbalance"] = (
        (panel["buy_order_volume"] - panel["sell_order_volume"]) /
        (panel["buy_order_volume"] + panel["sell_order_volume"] + 1)
    )
    panel["imbalance_rank"] = panel.groupby("time", sort=False)["buy_sell_imbalance"].rank(method="average", pct=True)
    panel["buy_heavy"] = panel["imbalance_rank"] >= 0.8

    # C23-family contract used by active h62x branch.
    panel["c23"] = panel["high_illiq"] & panel["vol_expansion"]
    panel["c24"] = (panel["pct_change"] >= 5.0) & panel["vol_expansion"]
    panel["c25"] = (panel["pct_change"] <= -2.0) & panel["vol_expansion"]
    panel["c26"] = panel["buy_heavy"] & panel["high_illiq"] & panel["vol_expansion"]

    panel["signal_count"] = (
        panel["c23"].astype(int)
        + panel["c24"].astype(int)
        + panel["c25"].astype(int)
        + panel["c26"].astype(int)
    )
    panel["composite_2plus"] = panel["signal_count"] >= 2

    panel["market_active_fraction"] = panel.groupby("time")["composite_2plus"].transform("mean")
    date_active = panel[["time", "market_active_fraction"]].drop_duplicates()
    low_cut = date_active["market_active_fraction"].quantile(0.20)
    panel["low_breadth"] = panel["market_active_fraction"] <= low_cut

    panel["signal_count_30d_avg"] = panel.groupby("ticker")["signal_count"].transform(
        lambda s: s.rolling(window=30, min_periods=10).mean()
    )
    panel["self_breadth_ratio"] = panel["signal_count"] / (panel["signal_count_30d_avg"] + 1e-6)

    date_mass = panel.groupby("time", as_index=False)["signal_count"].sum().rename(columns={"signal_count": "sum_signal_count"})
    top_mass = (
        panel.sort_values(["time", "signal_count"], ascending=[True, False])
        .groupby("time")
        .head(5)
        .groupby("time", as_index=False)["signal_count"]
        .sum()
        .rename(columns={"signal_count": "top5_signal_count"})
    )
    conc = date_mass.merge(top_mass, on="time", how="left")
    conc["signal_concentration"] = conc["top5_signal_count"] / (conc["sum_signal_count"] + 1e-6)
    panel = panel.merge(conc[["time", "signal_concentration"]], on="time", how="left")
    conc_cut = conc["signal_concentration"].quantile(0.70)
    panel["high_concentration"] = panel["signal_concentration"] >= conc_cut

    panel["blocked_either"] = (~panel["can_buy_next_open"].fillna(False)) | (~panel["can_sell_next_open"].fillna(False))
    panel["liquid_either"] = ~panel["blocked_either"]

    panel["total_order_count"] = panel["buy_order_count"].fillna(0) + panel["sell_order_count"].fillna(0)
    panel["order_count_rank"] = panel.groupby("time")["total_order_count"].rank(method="average", pct=True)
    panel["tight_capacity"] = panel["order_count_rank"] <= 0.20

    panel["accum_intensity_30d"] = panel.groupby("ticker")["signal_count"].transform(
        lambda s: s.rolling(window=30, min_periods=10).sum()
    )
    hi_cut = panel["accum_intensity_30d"].quantile(0.80)
    lo_cut = panel["accum_intensity_30d"].quantile(0.20)
    panel["high_accum_30d"] = panel["accum_intensity_30d"] >= hi_cut
    panel["low_accum_30d"] = panel["accum_intensity_30d"] <= lo_cut

    panel["cofire_isolated"] = panel["signal_count"] == 1
    panel["triple_amp"] = panel["tight_capacity"] & panel["low_breadth"] & panel["cofire_isolated"]

    panel["vol_depth_pct"] = panel.groupby("time")["vol_change"].rank(method="average", pct=True)
    panel["vol_deep"] = panel["vol_depth_pct"] >= 0.90
    panel["vol_mild"] = panel["vol_depth_pct"].between(0.80, 0.90, inclusive="left")

    panel["tight_high_accum"] = panel["tight_capacity"] & panel["high_accum_30d"]
    panel["tight_low_accum"] = panel["tight_capacity"] & panel["low_accum_30d"]

    panel["c24_non_blocked"] = panel["c24"] & (~panel["blocked_either"])
    panel["c24_blocked"] = panel["c24"] & panel["blocked_either"]

    panel["score_c23"] = panel["s1_xs_proba"].where(panel["c23"])
    panel["score_c24_non_blocked"] = panel["s1_xs_proba"].where(panel["c24_non_blocked"])
    panel["score_c25"] = panel["s1_xs_proba"].where(panel["c25"])
    panel["score_c26"] = panel["s1_xs_proba"].where(panel["c26"])
    panel["score_composite_2plus"] = panel["s1_xs_proba"].where(panel["composite_2plus"])
    panel["score_composite_2plus_low_breadth"] = panel["s1_xs_proba"].where(panel["composite_2plus"] & panel["low_breadth"])
    panel["score_triple_amp"] = panel["s1_xs_proba"].where(panel["triple_amp"])
    panel["score_tight_high_accum"] = panel["s1_xs_proba"].where(panel["tight_high_accum"])

    keep_cols = [
        "time",
        "ticker",
        "s1_xs_proba",
        "s1_barrier_hit_1d",
        "c23",
        "c24",
        "c25",
        "c26",
        "signal_count",
        "composite_2plus",
        "low_breadth",
        "market_active_fraction",
        "signal_concentration",
        "high_concentration",
        "blocked_either",
        "liquid_either",
        "tight_capacity",
        "cofire_isolated",
        "triple_amp",
        "vol_deep",
        "vol_mild",
        "accum_intensity_30d",
        "high_accum_30d",
        "low_accum_30d",
        "tight_high_accum",
        "tight_low_accum",
        "c24_non_blocked",
        "c24_blocked",
        "score_c23",
        "score_c24_non_blocked",
        "score_c25",
        "score_c26",
        "score_composite_2plus",
        "score_composite_2plus_low_breadth",
        "score_triple_amp",
        "score_tight_high_accum",
    ]

    out = panel[keep_cols].copy()
    out["time"] = pd.to_datetime(out["time"]).dt.normalize()
    out = out.sort_values(["time", "ticker"]).reset_index(drop=True)
    return out


def main() -> None:
    args = parse_args()
    output_path = Path(args.output_path)
    manifest_path = Path(args.manifest_path)

    bundle = _build_bundle(args)

    validate_required_columns(bundle, ["time", "ticker", "s1_xs_proba", "c23", "c24", "c25", "c26"], "xs_heuristic_signal_bundle")
    validate_unique_keys(bundle, ["time", "ticker"], "xs_heuristic_signal_bundle")

    atomic_write_parquet(bundle, output_path)

    fingerprint = build_input_fingerprint(
        {
            "s1_historical_path": str(args.s1_historical_path),
            "s1_live_path": str(args.s1_live_path),
            "exclude_live": bool(args.exclude_live),
            "order_stats_path": str(args.order_stats_path),
            "tradability_path": str(args.tradability_path),
            "start_date": args.start_date,
            "end_date": args.end_date,
        }
    )

    min_time = bundle["time"].min()
    max_time = bundle["time"].max()
    manifest = {
        "artifact": "xs_heuristic_signal_bundle",
        "path": str(output_path),
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "schema_version": 2,
        "row_count": int(len(bundle)),
        "ticker_count": int(bundle["ticker"].nunique()),
        "date_count": int(bundle["time"].nunique()),
        "date_min": None if pd.isna(min_time) else pd.Timestamp(min_time).date().isoformat(),
        "date_max": None if pd.isna(max_time) else pd.Timestamp(max_time).date().isoformat(),
        "window": {
            "start_date_arg": args.start_date,
            "end_date_arg": args.end_date,
            "exclude_live": bool(args.exclude_live),
        },
        "ready_signal_columns": [
            "score_c23",
            "score_c24_non_blocked",
            "score_c25",
            "score_c26",
            "score_composite_2plus",
            "score_composite_2plus_low_breadth",
            "score_triple_amp",
            "score_tight_high_accum",
        ],
        "state_columns": [
            "c23",
            "c24",
            "c25",
            "c26",
            "composite_2plus",
            "low_breadth",
            "triple_amp",
            "tight_high_accum",
            "vol_deep",
            "c24_non_blocked",
            "c24_blocked",
        ],
        "notes": {
            "c25_contract": "C25 uses active h62x proxy contract (pct_change <= -2 AND vol_expansion), not VWAP-deviation reconstruction.",
            "c24_router": "Prefer c24_non_blocked over raw c24 per C27 router finding.",
            "score_contract": "All score_* columns use S1 rank score masked by the state for direct top-k routing in heuristic-trader.",
            "row_preservation": "Exporter avoids the previous base-panel dropna truncation and keeps earliest source rows where keys exist.",
        },
        "input_fingerprint": fingerprint,
    }
    write_manifest(manifest_path, manifest)

    print(f"[ok] wrote bundle: {output_path}")
    print(f"[ok] wrote manifest: {manifest_path}")
    print(f"[ok] rows={len(bundle):,} tickers={bundle['ticker'].nunique():,} dates={bundle['time'].nunique():,}")
    print(f"[ok] range={bundle['time'].min().date()} -> {bundle['time'].max().date()}")


if __name__ == "__main__":
    main()
