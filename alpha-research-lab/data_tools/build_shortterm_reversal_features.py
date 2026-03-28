"""
Build short-term return reversal features (H117 / C9).

Vietnamese market shows systematic 1-day reversal: stocks that outperformed
peers yesterday tend to underperform today (IC = −0.028, 0/11 years). The
usable RL signal is the NEGATION: buy yesterday's underperformers.

Features generated:
  xs_reversal_1d    — 1 − rank(1d excess return lag 1 day)  → buy underperformers
  xs_reversal_2d    — 1 − rank(2d excess return lag 1 day)  → same, 2d window
  xs_ret_1d_abs_rank — rank(|1d return|)                   → activity persistence

Input:  data/stock/gia_lich_su_*_1D.parquet
        data/stock/gia_lich_su_VNINDEX_1D.parquet
Output: data/features/xs_shortterm_reversal.parquet

Usage:
    conda run -n stocks python data_tools/build_shortterm_reversal_features.py
"""

from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
STOCK_DIR = REPO_ROOT / "data" / "stock"
OUT_PATH = REPO_ROOT / "data" / "features" / "xs_shortterm_reversal.parquet"
EXCLUDE = {"VNINDEX", "VN30"}


def main():
    print("Loading OHLCV data...")
    vnindex = pd.read_parquet(STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet")[["time", "close"]]
    vnindex["time"] = pd.to_datetime(vnindex["time"])
    vnindex = vnindex.sort_values("time").set_index("time")
    vni_ret1 = vnindex["close"].pct_change(1).rename("vni_ret1")
    vni_ret2 = vnindex["close"].pct_change(2).rename("vni_ret2")
    vni_wide = pd.concat([vni_ret1, vni_ret2], axis=1).reset_index()

    parts = []
    for f in sorted(glob.glob(str(STOCK_DIR / "gia_lich_su_*_1D.parquet"))):
        ticker = Path(f).stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        df = pd.read_parquet(f, columns=["time", "close"])
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time").set_index("time")
        if len(df) < 50:
            continue
        df["ret1"] = df["close"].pct_change(1)
        df["ret2"] = df["close"].pct_change(2)
        df["ticker"] = ticker
        parts.append(df[["ret1", "ret2", "ticker"]].reset_index())

    long = pd.concat(parts, ignore_index=True)
    long = long.merge(vni_wide, on="time", how="left")
    long["excess1d"] = long["ret1"] - long["vni_ret1"]
    long["excess2d"] = long["ret2"] - long["vni_ret2"]
    long["abs_ret1"] = long["ret1"].abs()
    print(f"  Loaded {len(long):,} rows, {long['ticker'].nunique()} tickers")

    wide1 = long.pivot_table(index="time", columns="ticker", values="excess1d")
    wide2 = long.pivot_table(index="time", columns="ticker", values="excess2d")
    wideabs = long.pivot_table(index="time", columns="ticker", values="abs_ret1")

    # Lagged rank (predict from yesterday's performance) — negated to create reversal signal
    rank1_lag = wide1.rank(axis=1, method="average", ascending=True, pct=True).shift(1)
    rank2_lag = wide2.rank(axis=1, method="average", ascending=True, pct=True).shift(1)
    rankabs = wideabs.rank(axis=1, method="average", ascending=True, pct=True)

    # Negate for reversal (high value = yesterday's underperformer = buy signal)
    rev1 = 1.0 - rank1_lag
    rev2 = 1.0 - rank2_lag

    r1_long = rev1.reset_index().melt(id_vars="time", var_name="ticker", value_name="xs_reversal_1d")
    r2_long = rev2.reset_index().melt(id_vars="time", var_name="ticker", value_name="xs_reversal_2d")
    ra_long = rankabs.reset_index().melt(id_vars="time", var_name="ticker", value_name="xs_ret_1d_abs_rank")

    feat = r1_long.merge(r2_long, on=["time", "ticker"]).merge(ra_long, on=["time", "ticker"])
    feat = feat.dropna(subset=["xs_reversal_1d"])

    print(f"\nOutput: {len(feat):,} rows, {feat['ticker'].nunique()} tickers")
    for col in [c for c in feat.columns if c.startswith("xs_")]:
        nz = feat[col].notna().sum()
        print(f"  {col}: {nz:,} non-null ({100*nz/len(feat):.1f}%)")

    feat.to_parquet(OUT_PATH, index=False)
    print(f"\nSaved -> {OUT_PATH}")


if __name__ == "__main__":
    main()
