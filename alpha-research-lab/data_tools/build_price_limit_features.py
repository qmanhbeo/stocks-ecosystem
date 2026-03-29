"""
Build price limit (ceiling/floor) frequency features (H115).

Vietnamese stocks have daily price change limits of ±7% (±10% for some instrument
types). When a stock hits the ceiling (+7%), strong demand exceeded all supply —
a forced truncation of returns. When it hits the floor (−7%), forced selling.

Price limit touches reveal information that doesn't appear in OHLCV price/return
alone: ceiling hits can signal strong uninhibited demand, while floor hits signal
distressed selling or panic.

Features generated:
  xs_ceiling_count_5d  — number of ceiling touches in past 5 days (cross-sectional rank)
  xs_floor_count_5d    — number of floor touches in past 5 days (cross-sectional rank)
  xs_ceiling_count_20d — same, 20-day window
  xs_floor_count_20d   — same, 20-day window
  xs_limit_net_5d      — ceiling_count_5d - floor_count_5d (net limit pressure rank)

Ceiling definition: close ≥ prev_close × (1 + limit - 0.001)
  where limit = 0.07 for most HOSE stocks
Floor definition:   close ≤ prev_close × (1 - limit + 0.001)
  (small tolerance to handle rounding)

Input:  data/stock/gia_lich_su_*_1D.parquet  (OHLCV for all tickers)
Output: data/features/xs_price_limit_daily.parquet

Usage:
    conda run -n stocks python data_tools/build_price_limit_features.py
"""

from __future__ import annotations

import glob
from pathlib import Path
import sys

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = REPO_ROOT.parent
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))

from shared_market_rules import compute_price_limit_flags

STOCK_DIR = REPO_ROOT / "data" / "stock"
OUT_PATH = REPO_ROOT / "data" / "features" / "xs_price_limit_daily.parquet"
EXCLUDE = {"VNINDEX", "VN30"}


def load_limit_touches() -> pd.DataFrame:
    """Compute ceiling/floor touches per ticker per day."""
    parts = []
    for f in sorted(glob.glob(str(STOCK_DIR / "gia_lich_su_*_1D.parquet"))):
        ticker = Path(f).stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        df = pd.read_parquet(f, columns=["time", "close"])
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time")
        if len(df) < 30:
            continue
        price_flags = compute_price_limit_flags(df[["close"]].copy())
        df["ceiling"] = price_flags["is_ceiling"].astype(int)
        df["floor"] = price_flags["is_floor"].astype(int)
        df["ticker"] = ticker
        parts.append(df[["time", "ticker", "ceiling", "floor"]].dropna())

    return pd.concat(parts, ignore_index=True)


def build_features(long_df: pd.DataFrame) -> pd.DataFrame:
    """Build rolling limit-touch counts and cross-sectional ranks."""
    long_df = long_df.sort_values(["ticker", "time"])

    # Rolling counts per ticker
    for col, window, out_col in [
        ("ceiling", 5, "ceiling_count_5d"),
        ("ceiling", 20, "ceiling_count_20d"),
        ("floor", 5, "floor_count_5d"),
        ("floor", 20, "floor_count_20d"),
    ]:
        long_df[out_col] = long_df.groupby("ticker")[col].transform(
            lambda s: s.rolling(window, min_periods=1).sum()
        )

    long_df["limit_net_5d"] = long_df["ceiling_count_5d"] - long_df["floor_count_5d"]

    # Cross-sectional percentile ranks per date
    raw_cols = ["ceiling_count_5d", "ceiling_count_20d", "floor_count_5d", "floor_count_20d", "limit_net_5d"]
    rank_map = {
        "ceiling_count_5d": ("xs_ceiling_count_5d", True),
        "ceiling_count_20d": ("xs_ceiling_count_20d", True),
        "floor_count_5d": ("xs_floor_count_5d", True),
        "floor_count_20d": ("xs_floor_count_20d", True),
        "limit_net_5d": ("xs_limit_net_5d", True),
    }

    # Pivot for vectorized cross-sectional ranking
    result_parts = []
    for raw_col, (out_col, ascending) in rank_map.items():
        wide = long_df.pivot_table(index="time", columns="ticker", values=raw_col)
        ranked = wide.rank(axis=1, method="average", ascending=ascending, pct=True)
        melted = ranked.reset_index().melt(id_vars="time", var_name="ticker", value_name=out_col)
        result_parts.append(melted.set_index(["time", "ticker"]))

    result = pd.concat(result_parts, axis=1).reset_index()
    return result


def main():
    print("Loading price limit touch data...")
    long_df = load_limit_touches()
    print(f"  Loaded {len(long_df):,} rows, {long_df['ticker'].nunique()} tickers")
    print(f"  Date range: {long_df['time'].min().date()} to {long_df['time'].max().date()}")

    # Summary of limit touch frequency
    total_rows = len(long_df)
    ceiling_pct = 100 * long_df["ceiling"].sum() / total_rows
    floor_pct = 100 * long_df["floor"].sum() / total_rows
    print(f"  Ceiling touches: {long_df['ceiling'].sum():,} ({ceiling_pct:.2f}% of rows)")
    print(f"  Floor touches:   {long_df['floor'].sum():,} ({floor_pct:.2f}% of rows)")

    print("Computing cross-sectional ranks...")
    feat = build_features(long_df)
    feat = feat.dropna(subset=["xs_ceiling_count_5d"])

    print(f"\nOutput: {len(feat):,} rows, {feat['ticker'].nunique()} tickers")
    for col in [c for c in feat.columns if c.startswith("xs_")]:
        nz = feat[col].notna().sum()
        print(f"  {col}: {nz:,} non-null ({100*nz/len(feat):.1f}%)")

    feat.to_parquet(OUT_PATH, index=False)
    print(f"\nSaved -> {OUT_PATH}")


if __name__ == "__main__":
    main()
