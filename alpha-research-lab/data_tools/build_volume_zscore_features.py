"""
Build volume activity cross-sectional features (H116).

Tests whether abnormal volume (relative to a stock's own history) has standalone
cross-sectional IC. Hypothesis: stocks with unusually high volume relative to their
own 60d baseline are being "discovered" or actively rotated into, predicting
near-term continuation. The cross-sectional rank compares each stock's relative
activity against peers.

Features generated:
  xs_vol_zscore_5d   — 5d avg volume zscore (vs 60d baseline), cross-sectional rank
  xs_vol_zscore_1d   — 1d volume zscore (vs 60d baseline), cross-sectional rank
  xs_vol_surge_5d    — fraction of days in past 5d with volume > 1.5× 60d avg, rank
  xs_value_zscore_5d — same but using trading value (close × volume), rank

Input:  data/stock/gia_lich_su_*_1D.parquet  (OHLCV for all tickers)
Output: data/features/xs_volume_zscore_daily.parquet

Usage:
    conda run -n stocks python data_tools/build_volume_zscore_features.py
"""

from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
STOCK_DIR = REPO_ROOT / "data" / "stock"
OUT_PATH = REPO_ROOT / "data" / "features" / "xs_volume_zscore_daily.parquet"
EXCLUDE = {"VNINDEX", "VN30"}

BASELINE_WINDOW = 60


def load_volume_data() -> pd.DataFrame:
    """Load volume and value per ticker per day."""
    parts = []
    for f in sorted(glob.glob(str(STOCK_DIR / "gia_lich_su_*_1D.parquet"))):
        ticker = Path(f).stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        df = pd.read_parquet(f, columns=["time", "close", "volume"])
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time")
        if len(df) < BASELINE_WINDOW + 10:
            continue
        df["daily_value"] = df["close"] * df["volume"]
        df["ticker"] = ticker
        parts.append(df[["time", "ticker", "volume", "daily_value"]])

    return pd.concat(parts, ignore_index=True)


def build_features(long_df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-ticker volume zscore features, then cross-sectional rank."""
    long_df = long_df.sort_values(["ticker", "time"])

    # Per-ticker rolling stats over 60d baseline window
    vol_mean = long_df.groupby("ticker")["volume"].transform(
        lambda s: s.shift(1).rolling(BASELINE_WINDOW, min_periods=20).mean()
    )
    vol_std = long_df.groupby("ticker")["volume"].transform(
        lambda s: s.shift(1).rolling(BASELINE_WINDOW, min_periods=20).std()
    )
    val_mean = long_df.groupby("ticker")["daily_value"].transform(
        lambda s: s.shift(1).rolling(BASELINE_WINDOW, min_periods=20).mean()
    )
    val_std = long_df.groupby("ticker")["daily_value"].transform(
        lambda s: s.shift(1).rolling(BASELINE_WINDOW, min_periods=20).std()
    )

    # 1d zscore
    long_df["vol_z1d"] = (long_df["volume"] - vol_mean) / vol_std.clip(lower=1)
    long_df["val_z1d"] = (long_df["daily_value"] - val_mean) / val_std.clip(lower=1)

    # 5d rolling average zscore
    long_df["vol_z5d"] = long_df.groupby("ticker")["vol_z1d"].transform(
        lambda s: s.rolling(5, min_periods=3).mean()
    )
    long_df["val_z5d"] = long_df.groupby("ticker")["val_z1d"].transform(
        lambda s: s.rolling(5, min_periods=3).mean()
    )

    # 5d surge fraction: fraction of last 5 days with volume > 1.5× baseline mean
    high_vol = (long_df["volume"] > 1.5 * vol_mean).astype(float)
    long_df["vol_surge_5d"] = long_df.groupby("ticker")["vol_z1d"].transform(
        lambda s: s.rolling(5, min_periods=3).count()  # placeholder
    )
    high_vol_series = high_vol.copy()
    high_vol_series.index = long_df.index
    long_df["vol_surge_5d"] = long_df.groupby("ticker").apply(
        lambda g: high_vol_series.loc[g.index].rolling(5, min_periods=3).sum()
    ).reset_index(level=0, drop=True)

    # Cross-sectional rank per date
    raw_to_rank = {
        "vol_z1d": "xs_vol_zscore_1d",
        "vol_z5d": "xs_vol_zscore_5d",
        "val_z5d": "xs_value_zscore_5d",
        "vol_surge_5d": "xs_vol_surge_5d",
    }

    result_parts = []
    for raw_col, out_col in raw_to_rank.items():
        wide = long_df.pivot_table(index="time", columns="ticker", values=raw_col)
        ranked = wide.rank(axis=1, method="average", ascending=True, pct=True)
        melted = ranked.reset_index().melt(id_vars="time", var_name="ticker", value_name=out_col)
        result_parts.append(melted.set_index(["time", "ticker"]))

    return pd.concat(result_parts, axis=1).reset_index()


def main():
    print("Loading volume data...")
    long_df = load_volume_data()
    print(f"  Loaded {len(long_df):,} rows, {long_df['ticker'].nunique()} tickers")

    print("Computing volume zscore features...")
    feat = build_features(long_df)
    feat = feat.dropna(subset=["xs_vol_zscore_1d"])

    print(f"\nOutput: {len(feat):,} rows, {feat['ticker'].nunique()} tickers")
    for col in [c for c in feat.columns if c.startswith("xs_")]:
        nz = feat[col].notna().sum()
        print(f"  {col}: {nz:,} non-null ({100*nz/len(feat):.1f}%)")

    feat.to_parquet(OUT_PATH, index=False)
    print(f"\nSaved -> {OUT_PATH}")


if __name__ == "__main__":
    main()
