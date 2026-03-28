"""
Build VN30 rebalancing proximity features (H114).

The VN30 index tracks the 30 largest and most liquid HOSE stocks. It rebalances
semi-annually (January and July). Stocks approaching the top-30 liquidity boundary
attract passive ETF tracking inflows; stocks at risk of exclusion face selling pressure.

This builder derives VN30 boundary proximity from daily trading value (close × volume)
without requiring historical VN30 composition data. The signal lives in the cross-
sectional rank dynamics near the top-30 threshold.

Features generated:
  xs_vn30_rank_pctile    — daily cross-sectional percentile rank by 60d avg value
                           (1.0 = most liquid = highest VN30 inclusion probability)
  xs_vn30_boundary_score — Gaussian proximity to top-30 threshold (peak at rank 30)
  xs_vn30_rank_change_5d — 5-day improvement in rank percentile (approaching = positive)
  xs_vn30_add_pressure   — composite: rank_change_5d × boundary_score × not_top10
                           (targets stocks gaining liquidity toward VN30 threshold)

Input:  data/stock/gia_lich_su_*_1D.parquet  (OHLCV for all tickers)
Output: data/features/xs_vn30_rebalancing.parquet

Usage:
    conda run -n stocks python data_tools/build_vn30_rebalancing_features.py
"""

from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
STOCK_DIR = REPO_ROOT / "data" / "stock"
OUT_PATH = REPO_ROOT / "data" / "features" / "xs_vn30_rebalancing.parquet"
EXCLUDE = {"VNINDEX", "VN30"}

VALUE_WINDOW = 60   # rolling window for avg daily value
BOUNDARY_WIDTH = 25.0  # sigma^2 for Gaussian proximity to rank 30


def load_daily_values() -> pd.DataFrame:
    """Load close × volume for all tickers into a long DataFrame."""
    parts = []
    files = sorted(glob.glob(str(STOCK_DIR / "gia_lich_su_*_1D.parquet")))
    for f in files:
        ticker = Path(f).stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        df = pd.read_parquet(f, columns=["time", "close", "volume"])
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time")
        if len(df) < VALUE_WINDOW + 10:
            continue
        df["daily_value"] = df["close"] * df["volume"]
        df["ticker"] = ticker
        parts.append(df[["time", "ticker", "daily_value"]])

    return pd.concat(parts, ignore_index=True)


def build_features(long_df: pd.DataFrame) -> pd.DataFrame:
    """Compute cross-sectional VN30 boundary features from the long value DataFrame."""
    # Rolling 60d average value per ticker
    long_df = long_df.sort_values(["ticker", "time"])
    long_df["avg_val_60d"] = (
        long_df.groupby("ticker")["daily_value"]
        .transform(lambda s: s.rolling(VALUE_WINDOW, min_periods=VALUE_WINDOW // 2).mean())
    )
    long_df = long_df.dropna(subset=["avg_val_60d"])

    # For each date, compute cross-sectional rank and proximity features
    print("Computing cross-sectional ranks...")

    # Pivot to wide format (dates × tickers) for vectorized cross-sectional ops
    wide = long_df.pivot_table(index="time", columns="ticker", values="avg_val_60d")

    n_tickers = wide.notna().sum(axis=1)  # number of valid tickers per day

    # Percentile rank across tickers for each day (0=least liquid, 1=most liquid)
    pctile_wide = wide.rank(axis=1, method="average", ascending=True, pct=True)
    # NaN where fewer than 20 tickers are available
    pctile_wide = pctile_wide.where(n_tickers >= 20)

    # Integer rank from top (1 = most liquid)
    int_rank_wide = wide.rank(axis=1, method="average", ascending=False)
    int_rank_wide = int_rank_wide.where(n_tickers >= 20)

    # Gaussian proximity to rank-30-from-top threshold
    boundary_wide = np.exp(-0.5 * (int_rank_wide - 30.0) ** 2 / BOUNDARY_WIDTH)

    # Melt back to long format
    pctile_long = pctile_wide.reset_index().melt(id_vars="time", var_name="ticker", value_name="xs_vn30_rank_pctile")
    boundary_long = boundary_wide.reset_index().melt(id_vars="time", var_name="ticker", value_name="xs_vn30_boundary_score")
    int_rank_long = int_rank_wide.reset_index().melt(id_vars="time", var_name="ticker", value_name="int_rank")

    result = pctile_long.merge(boundary_long, on=["time", "ticker"]).merge(int_rank_long, on=["time", "ticker"])
    result = result.dropna(subset=["xs_vn30_rank_pctile"])
    result = result.sort_values(["ticker", "time"])

    # 5-day change in rank percentile (positive = improving toward VN30)
    result["xs_vn30_rank_change_5d"] = result.groupby("ticker")["xs_vn30_rank_pctile"].diff(5)

    # Composite add-pressure signal:
    # rank_change_5d × boundary_score × (not_top10 indicator)
    # Only fires for boundary stocks (rank 20-50), excludes already-secure top-10
    not_dominant = (result["int_rank"] > 10).astype(float)
    result["xs_vn30_add_pressure"] = (
        result["xs_vn30_rank_change_5d"].clip(-1, 1)
        * result["xs_vn30_boundary_score"]
        * not_dominant
    )

    keep_cols = [
        "time", "ticker",
        "xs_vn30_rank_pctile",
        "xs_vn30_boundary_score",
        "xs_vn30_rank_change_5d",
        "xs_vn30_add_pressure",
    ]
    return result[[c for c in keep_cols if c in result.columns]].copy()


def main():
    print("Loading daily OHLCV values...")
    long_df = load_daily_values()
    print(f"  Loaded {len(long_df):,} rows, {long_df['ticker'].nunique()} tickers")
    print(f"  Date range: {long_df['time'].min().date()} to {long_df['time'].max().date()}")

    feat = build_features(long_df)
    feat = feat.dropna(subset=["xs_vn30_rank_pctile"])

    print(f"\nOutput: {len(feat):,} rows, {feat['ticker'].nunique()} tickers")
    for col in [c for c in feat.columns if c.startswith("xs_")]:
        nz = feat[col].notna().sum()
        print(f"  {col}: {nz:,} non-null ({100*nz/len(feat):.1f}%)")

    feat.to_parquet(OUT_PATH, index=False)
    print(f"\nSaved -> {OUT_PATH}")


if __name__ == "__main__":
    main()
