"""
build_xs_features.py -- Pre-build cross-sectional rank features for all stocks.

For each (date, ticker), compute where that stock ranks within the universe of
all VN stocks on that day. This gives the model cross-sectional context that
single-stock time-series features cannot capture.

Output: data/features/xs_features_daily.parquet
  time, ticker, xs_rank_1d, xs_rank_5d, xs_rank_20d,
  xs_univ_mean_1d, xs_univ_mean_5d, xs_univ_std_5d,
  xs_above_median_5d (binary: 1 = top half of market)

Run: conda run -n stocks python src/build_xs_features.py
"""
import os
import glob
import pandas as pd
import numpy as np
from pathlib import Path


DATA_DIR  = Path("data/stock")
OUT_DIR   = Path("data/features")
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE  = OUT_DIR / "xs_features_daily.parquet"
VNI_FILE  = DATA_DIR / "gia_lich_su_VNINDEX_1D.parquet"

# Exclude index files (not individual stocks)
EXCLUDE = {"VNINDEX", "VN30"}


def load_returns(ticker: str, file_path: str) -> pd.DataFrame:
    try:
        df = pd.read_parquet(file_path)[["time", "close"]].copy()
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time").reset_index(drop=True)
        df["ret_1d"]  = df["close"] / df["close"].shift(1)  - 1
        df["ret_5d"]  = df["close"] / df["close"].shift(5)  - 1
        df["ret_20d"] = df["close"] / df["close"].shift(20) - 1
        df["ticker"] = ticker
        return df[["time", "ticker", "ret_1d", "ret_5d", "ret_20d"]].dropna()
    except Exception as e:
        print(f"  [WARN] {ticker}: {e}")
        return pd.DataFrame()


def main():
    files = glob.glob(str(DATA_DIR / "gia_lich_su_*_1D.parquet"))
    frames = []
    for f in sorted(files):
        ticker = Path(f).stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        df = load_returns(ticker, f)
        if len(df) > 100:
            frames.append(df)
            print(f"  Loaded {ticker}: {len(df)} rows")

    print(f"\nTotal tickers: {len(frames)}")
    all_df = pd.concat(frames, ignore_index=True)

    # Cross-sectional ranking per date
    # Only dates where at least 10 stocks have data
    date_counts = all_df.groupby("time")["ticker"].count()
    valid_dates = date_counts[date_counts >= 10].index
    all_df = all_df[all_df["time"].isin(valid_dates)]

    print(f"Computing ranks across {len(valid_dates)} dates, {len(all_df)} rows...")

    # Load VNINDEX for breadth computation (V5)
    vnindex_rets = {}
    try:
        vni = pd.read_parquet(VNI_FILE)[["time", "close"]].copy()
        vni["time"] = pd.to_datetime(vni["time"])
        vni = vni.sort_values("time").reset_index(drop=True)
        vni["vni_ret_1d"]  = vni["close"] / vni["close"].shift(1)  - 1
        vni["vni_ret_5d"]  = vni["close"] / vni["close"].shift(5)  - 1
        vni["vni_ret_20d"] = vni["close"] / vni["close"].shift(20) - 1
        for col in ["vni_ret_1d", "vni_ret_5d", "vni_ret_20d"]:
            vnindex_rets[col] = vni.set_index("time")[col]
        print(f"  Loaded VNINDEX for breadth computation")
    except Exception as e:
        print(f"  [WARN] Could not load VNINDEX for breadth: {e}")

    def _rank(series):
        """Percentile rank within group, NaN → NaN."""
        return series.rank(pct=True)

    g = all_df.groupby("time")
    all_df["xs_rank_1d"]  = g["ret_1d"].transform(_rank)
    all_df["xs_rank_5d"]  = g["ret_5d"].transform(_rank)
    all_df["xs_rank_20d"] = g["ret_20d"].transform(_rank)

    # Universe-level aggregates (market breadth)
    agg = g.agg(
        xs_univ_mean_1d=("ret_1d",  "mean"),
        xs_univ_mean_5d=("ret_5d",  "mean"),
        xs_univ_std_5d =("ret_5d",  "std"),
        xs_n_stocks    =("ticker",  "count"),
    ).reset_index()

    all_df = all_df.merge(agg, on="time", how="left")
    all_df["xs_above_median_5d"] = (all_df["xs_rank_5d"] >= 0.5).astype(float)

    # V5: Market breadth — fraction of stocks beating VNINDEX on each horizon
    for horizon, ret_col, vni_col in [
        ("1d",  "ret_1d",  "vni_ret_1d"),
        ("5d",  "ret_5d",  "vni_ret_5d"),
        ("20d", "ret_20d", "vni_ret_20d"),
    ]:
        breadth_col = f"xs_breadth_{horizon}"
        if vni_col in vnindex_rets:
            # Map VNINDEX return to each (time, ticker) row
            all_df[f"_vni_{horizon}"] = all_df["time"].map(vnindex_rets[vni_col])
            # excess = stock_ret - vnindex_ret; breadth = fraction with excess > 0
            excess = all_df[ret_col] - all_df[f"_vni_{horizon}"]
            all_df["_beats"] = (excess > 0).astype(float)
            breadth = all_df.groupby("time")["_beats"].transform("mean")
            all_df[breadth_col] = breadth
            all_df = all_df.drop(columns=[f"_vni_{horizon}", "_beats"])
        else:
            all_df[breadth_col] = np.nan

    feat_cols = [
        "time", "ticker",
        "xs_rank_1d", "xs_rank_5d", "xs_rank_20d",
        "xs_univ_mean_1d", "xs_univ_mean_5d", "xs_univ_std_5d",
        "xs_above_median_5d", "xs_n_stocks",
        "xs_breadth_1d", "xs_breadth_5d", "xs_breadth_20d",
    ]
    out = all_df[feat_cols]
    out.to_parquet(OUT_FILE, index=False)
    print(f"\nSaved {len(out)} rows to {OUT_FILE}")
    print(f"Date range: {out['time'].min().date()} to {out['time'].max().date()}")
    print(f"Tickers: {out['ticker'].nunique()}")


if __name__ == "__main__":
    main()
