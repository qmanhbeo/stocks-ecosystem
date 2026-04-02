"""
Build sector rotation features (H111).

Computes sector-level momentum and intra-sector leadership rankings.
The composite signal (sector_mom × intra_sector_rank) targets the "best horse
in the hot race" — the leading stock within the leading sector.

Input:
  data/features/sector_classification.parquet  — ICB sector labels per ticker
  data/stock/gia_lich_su_*_1D.parquet          — OHLCV for all tickers
  data/stock/gia_lich_su_VNINDEX_1D.parquet    — market index returns

Output: data/features/xs_sector_rotation_daily.parquet
  time, ticker,
  xs_sector_mom_5d_rank   — sector's 5d excess return, cross-sector percentile
  xs_sector_mom_20d_rank  — sector's 20d excess return, cross-sector percentile
  xs_intra_sector_rank    — stock's 5d excess return within its sector
  xs_sector_rotation_signal  — xs_sector_mom_5d_rank * xs_intra_sector_rank
  xs_sector_breadth_5d    — fraction of sector stocks with positive 5d excess return
  xs_sector_accel         — sector_excess_5d - sector_excess_20d/4 (fresh momentum)

Usage:
    conda activate stocks
    python data_tools/build_sector_rotation_features.py
"""

from __future__ import annotations

from pathlib import Path
from path_utils import data_path
import glob
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
STOCK_DIR = data_path("stock")
SECTOR_PATH = data_path("features/sector_classification.parquet")
OUT_PATH = data_path("features/xs_sector_rotation_daily.parquet")
EXCLUDE = {"VNINDEX", "VN30"}


def load_returns() -> pd.DataFrame:
    """Load 5d and 20d returns for all tickers, plus VNINDEX baseline."""
    vnindex = pd.read_parquet(STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet")[["time", "close"]]
    vnindex["time"] = pd.to_datetime(vnindex["time"])
    vnindex = vnindex.sort_values("time").set_index("time")
    vni_ret5 = vnindex["close"].pct_change(5).rename("vni_ret5")
    vni_ret20 = vnindex["close"].pct_change(20).rename("vni_ret20")

    parts = []
    for f in sorted(glob.glob(str(STOCK_DIR / "gia_lich_su_*_1D.parquet"))):
        ticker = Path(f).stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        df = pd.read_parquet(f, columns=["time", "close"])
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time").set_index("time")
        if len(df) < 100:
            continue
        df["ret5"] = df["close"].pct_change(5)
        df["ret20"] = df["close"].pct_change(20)
        df["ticker"] = ticker
        parts.append(df[["ret5", "ret20", "ticker"]].reset_index())

    returns = pd.concat(parts, ignore_index=True)
    returns = returns.merge(
        pd.concat([vni_ret5, vni_ret20], axis=1).reset_index(),
        on="time", how="left",
    )
    returns["excess5"] = returns["ret5"] - returns["vni_ret5"]
    returns["excess20"] = returns["ret20"] - returns["vni_ret20"]
    return returns


def build_features(returns: pd.DataFrame, sectors: pd.DataFrame) -> pd.DataFrame:
    """Build sector-level and intra-sector rank features."""
    df = returns.merge(
        sectors[["symbol", "icb_name2"]].rename(columns={"symbol": "ticker", "icb_name2": "sector"}),
        on="ticker", how="inner",
    ).dropna(subset=["excess5", "excess20", "sector"])

    # --- Sector-level momentum ---
    sector_agg = (
        df.groupby(["time", "sector"])
        .agg(
            sector_excess5=("excess5", "mean"),
            sector_excess20=("excess20", "mean"),
            sector_breadth5=("excess5", lambda x: (x > 0).mean()),
        )
        .reset_index()
    )

    # Cross-sector percentile rank for each date
    def rank_within_date(grp: pd.DataFrame, col: str) -> pd.Series:
        return grp.groupby("time")[col].rank(pct=True)

    sector_agg["xs_sector_mom_5d_rank"] = rank_within_date(sector_agg, "sector_excess5")
    sector_agg["xs_sector_mom_20d_rank"] = rank_within_date(sector_agg, "sector_excess20")
    sector_agg["xs_sector_accel"] = (
        sector_agg["sector_excess5"] - sector_agg["sector_excess20"] / 4
    )

    # --- Intra-sector rank ---
    df["xs_intra_sector_rank"] = (
        df.groupby(["time", "sector"])["excess5"].rank(pct=True)
    )

    # Merge sector-level features back to stock level
    result = df[["time", "ticker", "sector", "xs_intra_sector_rank"]].merge(
        sector_agg[[
            "time", "sector",
            "xs_sector_mom_5d_rank", "xs_sector_mom_20d_rank",
            "xs_sector_accel",
            "sector_breadth5",
        ]].rename(columns={"sector_breadth5": "xs_sector_breadth_5d"}),
        on=["time", "sector"], how="left",
    )

    result["xs_sector_rotation_signal"] = (
        result["xs_sector_mom_5d_rank"] * result["xs_intra_sector_rank"]
    )

    return result.drop(columns=["sector"]).sort_values(["time", "ticker"]).reset_index(drop=True)


def main():
    print("Loading sector classification...")
    sectors = pd.read_parquet(SECTOR_PATH)
    print(f"  {len(sectors)} tickers, {sectors['icb_name2'].nunique()} sectors")

    print("Loading stock returns (this takes ~30s)...")
    returns = load_returns()
    print(f"  {returns['ticker'].nunique()} tickers, {returns['time'].nunique()} dates, {len(returns):,} rows")

    print("Building sector rotation features...")
    feat = build_features(returns, sectors)
    print(f"  Output: {len(feat):,} rows, {feat['ticker'].nunique()} tickers")

    feat.to_parquet(OUT_PATH, index=False)
    print(f"Saved -> {OUT_PATH}")

    for col in [c for c in feat.columns if c.startswith("xs_")]:
        nz = feat[col].notna().sum()
        print(f"  {col}: {nz:,} non-null ({100*nz/len(feat):.1f}%)")


if __name__ == "__main__":
    main()
