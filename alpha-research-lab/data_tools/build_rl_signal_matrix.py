"""
Build combined RL signal state matrix from all confirmed/candidate signals.

Assembles S1 + all promoted candidate signals (C4-C14) into a single feature
parquet for use by the RL trading agent. Handles different time columns
(time vs trading_day) and signal sparsity (C5 insider = 3.4% coverage).

Output: data/features/xs_rl_signal_matrix.parquet
  Columns:
    time, ticker              — merge keys
    s1_proba                  — S1/H93: cross-sectional momentum probability
    c4_oc_asym_5d             — C4: overnight/intraday contrast (oc_asym_5d)
    c5_ins_relative_size_5d    — C5: insider conviction (sparse, 3.4%)
    c6_contrarian_intra_5d    — C6: intra-sector mean reversion
    c7_ceiling_count_5d       — C7: price limit momentum
    c8_vol_zscore_5d          — C8: abnormal volume activity
    c9_reversal_1d            — C9: 1-day return reversal (1 - xs_ret_1d_lag_rank)
    c10_illiq_level_rank      — C10: Amihud illiquidity level
    c11_ret_60d_lag_rank      — C11: 3-month continuation / medium-term trend
    c12_gap_absorb_3          — C12: gap acceptance with intraday confirmation
    c13_compress_blowoff_2    — C13: post-compression expansion exhaustion
    c14_clv_volconf_resid_rank — C14: close-strength residual after removing C8
    c5_signal_present         — indicator: 1 if C5 fired on this (time, ticker)

Signal properties (all 2015–2025):
  S1:  IC +0.149, 11/11 yrs, corr N/A (primary signal)
  C4:  IC +0.023, 11/11 yrs, corr +0.147, coverage 100%
  C5:  IC +0.037, 10/11 yrs, corr -0.008, coverage 3.4%
  C6:  IC +0.030, 11/11 yrs, corr +0.142, coverage 100%
  C7:  IC +0.012,  8/11 yrs, corr +0.064, coverage 100%
  C8:  IC +0.011, 10/11 yrs, corr +0.068, coverage 100%
  C9:  IC +0.028, 11/11 yrs, corr +0.161, coverage 100%
  C10: IC +0.021, 10/11 yrs, corr +0.008, coverage 100%
  C11: IC +0.010, 9/11 yrs, corr +0.008, coverage 100%
  C12: IC +0.028, 11/11 yrs, corr +0.131, coverage 100%
  C13: IC +0.035, 10/11 yrs, corr +0.191, coverage 100%
  C14: IC +0.013, 11/11 yrs, corr +0.102, coverage 100%

Usage:
    conda run -n stocks python data_tools/build_rl_signal_matrix.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
FEAT_DIR = REPO_ROOT / "data" / "features"
STOCK_DIR = REPO_ROOT / "data" / "stock"
OUT_PATH = FEAT_DIR / "xs_rl_signal_matrix.parquet"

S1_PATH       = FEAT_DIR / "xs_barrier_vol_1d_hose_full.parquet"
S1_LIVE_PATH  = FEAT_DIR / "xs_barrier_vol_1d_hose_live_current.parquet"
C4_PATH       = FEAT_DIR / "xs_open_close_asymmetry.parquet"
C5_PATH       = FEAT_DIR / "xs_insider_quality_features.parquet"
C6_PATH       = FEAT_DIR / "xs_sector_rotation_daily.parquet"
C7_PATH       = FEAT_DIR / "xs_price_limit_daily.parquet"
C8_PATH       = FEAT_DIR / "xs_volume_zscore_daily.parquet"
C9_PATH       = FEAT_DIR / "xs_shortterm_reversal.parquet"

ILLIQ_WINDOW = 20
ILLIQ_MIN_DAYS = 10
VALUE_SCALE = 1e9
LOOKBACK_DAYS = 60
EXCLUDE = {"VNINDEX", "VN30"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the consolidated RL signal matrix.")
    return parser.parse_args()


def load_s1_spine() -> pd.DataFrame:
    s1 = pd.read_parquet(S1_PATH)[["time", "ticker", "xs_proba", "actual"]]
    s1["time"] = pd.to_datetime(s1["time"])
    if S1_LIVE_PATH.exists():
        live = pd.read_parquet(S1_LIVE_PATH)[["time", "ticker", "xs_proba", "actual"]]
        live["time"] = pd.to_datetime(live["time"])
        s1 = (
            pd.concat([s1, live], ignore_index=True)
            .sort_values(["time", "ticker"])
            .drop_duplicates(["time", "ticker"], keep="last")
            .reset_index(drop=True)
        )
    return s1


def build_illiq_level_features() -> pd.DataFrame:
    """Compute C10 directly from OHLCV via a vectorized pivot/rank workflow."""
    parts = []
    for f in sorted(STOCK_DIR.glob("gia_lich_su_*_1D.parquet")):
        ticker = f.stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        try:
            df = pd.read_parquet(f, columns=["time", "close", "volume"])
        except Exception:
            continue
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time")
        if len(df) < 50:
            continue
        df["ticker"] = ticker
        df["daily_value"] = df["close"] * df["volume"] / VALUE_SCALE
        df["ret1"] = df["close"].pct_change(1)
        df["illiq_raw"] = df["ret1"].abs() / df["daily_value"].replace(0, np.nan)
        parts.append(df[["time", "ticker", "illiq_raw"]])

    long = pd.concat(parts, ignore_index=True)

    wide = long.pivot_table(index="time", columns="ticker", values="illiq_raw")
    illiq_20d = wide.rolling(ILLIQ_WINDOW, min_periods=ILLIQ_MIN_DAYS).mean()
    xs_level = illiq_20d.rank(axis=1, method="average", ascending=True, pct=True)

    return (
        xs_level.reset_index()
        .melt(id_vars="time", var_name="ticker", value_name="c10_illiq_level_rank")
        .dropna(subset=["c10_illiq_level_rank"])
    )


def build_3m_continuation_features() -> pd.DataFrame:
    """Compute C11 directly from OHLCV via a vectorized pivot/rank workflow."""
    vni = pd.read_parquet(STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet", columns=["time", "close"])
    vni["time"] = pd.to_datetime(vni["time"])
    vni = vni.sort_values("time")
    vni["vni_ret60"] = vni["close"].pct_change(LOOKBACK_DAYS)
    vni = vni[["time", "vni_ret60"]]

    parts = []
    for f in sorted(STOCK_DIR.glob("gia_lich_su_*_1D.parquet")):
        ticker = f.stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        try:
            df = pd.read_parquet(f, columns=["time", "close"])
        except Exception:
            continue
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time")
        if len(df) < LOOKBACK_DAYS + 10:
            continue
        df["ticker"] = ticker
        df["ret60"] = df["close"].pct_change(LOOKBACK_DAYS)
        parts.append(df[["time", "ticker", "ret60"]])

    long = pd.concat(parts, ignore_index=True)
    long = long.merge(vni, on="time", how="left")
    long["excess60"] = long["ret60"] - long["vni_ret60"]

    wide = long.pivot_table(index="time", columns="ticker", values="excess60")
    xs_rank = wide.rank(axis=1, method="average", ascending=True, pct=True).shift(1)
    return (
        xs_rank.reset_index()
        .melt(id_vars="time", var_name="ticker", value_name="c11_ret_60d_lag_rank")
        .dropna(subset=["c11_ret_60d_lag_rank"])
    )


def build_gap_absorption_features() -> pd.DataFrame:
    """Compute C12 directly from OHLCV using confirmed-gap acceptance."""
    parts = []
    for f in sorted(STOCK_DIR.glob("gia_lich_su_*_1D.parquet")):
        ticker = f.stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        try:
            df = pd.read_parquet(f, columns=["time", "open", "high", "low", "close"])
        except Exception:
            continue
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time")
        if len(df) < 50:
            continue
        df["ticker"] = ticker
        parts.append(df[["time", "ticker", "open", "high", "low", "close"]])

    long = pd.concat(parts, ignore_index=True)
    wide_open = long.pivot_table(index="time", columns="ticker", values="open").sort_index()
    wide_high = long.pivot_table(index="time", columns="ticker", values="high").sort_index()
    wide_low = long.pivot_table(index="time", columns="ticker", values="low").sort_index()
    wide_close = long.pivot_table(index="time", columns="ticker", values="close").sort_index()

    gap = wide_open.div(wide_close.shift(1)) - 1.0
    intraday = wide_close.div(wide_open.replace(0, np.nan)) - 1.0
    intraday_positive = (intraday > 0).astype(float)
    denom = wide_high - wide_low
    clv = (wide_close - wide_low).div(denom.replace(0, np.nan)).mask(denom == 0, 0.5)

    xs_gap_absorb_3 = (gap * intraday_positive * clv).rank(
        axis=1, method="average", ascending=True, pct=True
    )
    return (
        xs_gap_absorb_3.reset_index()
        .melt(id_vars="time", var_name="ticker", value_name="c12_gap_absorb_3")
        .dropna(subset=["c12_gap_absorb_3"])
    )


def build_compress_blowoff_features() -> pd.DataFrame:
    """Compute C13 directly from OHLCV using the validated H133 formulation."""
    parts = []
    for f in sorted(STOCK_DIR.glob("gia_lich_su_*_1D.parquet")):
        ticker = f.stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        try:
            df = pd.read_parquet(f, columns=["time", "high", "low", "close", "volume"])
        except Exception:
            continue
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time")
        if len(df) < 80:
            continue
        df["ticker"] = ticker
        parts.append(df[["time", "ticker", "high", "low", "close", "volume"]])

    long = pd.concat(parts, ignore_index=True)
    wide_high = long.pivot_table(index="time", columns="ticker", values="high").sort_index()
    wide_low = long.pivot_table(index="time", columns="ticker", values="low").sort_index()
    wide_close = long.pivot_table(index="time", columns="ticker", values="close").sort_index()
    wide_volume = long.pivot_table(index="time", columns="ticker", values="volume").sort_index()

    range_pct = (wide_high - wide_low).div(wide_close.shift(1))
    compress_10 = range_pct.rolling(10, min_periods=5).mean()
    range_expansion = range_pct.div(range_pct.rolling(10, min_periods=5).mean())
    denom = wide_high - wide_low
    close_strength = (wide_close - wide_low).div(denom.replace(0, np.nan)).mask(denom == 0, 0.5)
    vol_confirmation = wide_volume.div(wide_volume.rolling(20, min_periods=10).mean())

    compress_10_rank = 1.0 - compress_10.rank(axis=1, method="average", ascending=True, pct=True)
    expansion_rank = range_expansion.rank(axis=1, method="average", ascending=True, pct=True)
    close_rank = close_strength.rank(axis=1, method="average", ascending=True, pct=True)
    vol_rank = vol_confirmation.rank(axis=1, method="average", ascending=True, pct=True)

    breakout_2 = (compress_10_rank * expansion_rank * close_rank * vol_rank).rank(
        axis=1, method="average", ascending=True, pct=True
    )
    blowoff_2 = 1.0 - breakout_2
    return (
        blowoff_2.reset_index()
        .melt(id_vars="time", var_name="ticker", value_name="c13_compress_blowoff_2")
        .dropna(subset=["c13_compress_blowoff_2"])
    )


def build_clv_resid_features(c8: pd.DataFrame) -> pd.DataFrame:
    """Compute C14 directly from OHLCV after residualizing against C8."""
    parts = []
    for f in sorted(STOCK_DIR.glob("gia_lich_su_*_1D.parquet")):
        ticker = f.stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        try:
            df = pd.read_parquet(f, columns=["time", "high", "low", "close", "volume"])
        except Exception:
            continue
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time")
        if len(df) < 80:
            continue
        df["ticker"] = ticker
        parts.append(df[["time", "ticker", "high", "low", "close", "volume"]])

    long = pd.concat(parts, ignore_index=True)
    wide_high = long.pivot_table(index="time", columns="ticker", values="high").sort_index()
    wide_low = long.pivot_table(index="time", columns="ticker", values="low").sort_index()
    wide_close = long.pivot_table(index="time", columns="ticker", values="close").sort_index()
    wide_volume = long.pivot_table(index="time", columns="ticker", values="volume").sort_index()

    denom = wide_high - wide_low
    clv = (wide_close - wide_low).div(denom.replace(0, np.nan)).mask(denom == 0, 0.5)
    vol_mean = wide_volume.rolling(60, min_periods=20).mean()
    vol_std = wide_volume.rolling(60, min_periods=20).std(ddof=0)
    vol_zscore_1d = (wide_volume - vol_mean).div(vol_std.replace(0, np.nan))
    clv_volconf_5d = (clv * vol_zscore_1d).rolling(5, min_periods=3).mean().rank(
        axis=1, method="average", ascending=True, pct=True
    )

    c8_wide = (
        c8.rename(columns={"c8_vol_zscore_5d": "xs_vol_zscore_5d"})
        .pivot_table(index="time", columns="ticker", values="xs_vol_zscore_5d")
        .sort_index()
    )
    common_index = clv_volconf_5d.index.intersection(c8_wide.index)
    clv_volconf_5d = clv_volconf_5d.reindex(common_index)
    c8_wide = c8_wide.reindex(common_index)

    resid = pd.DataFrame(index=common_index, columns=clv_volconf_5d.columns, dtype=float)
    for date in common_index:
        frame = pd.concat(
            [
                clv_volconf_5d.loc[date].rename("target"),
                c8_wide.loc[date].rename("control"),
            ],
            axis=1,
        ).dropna()
        if len(frame) < 20:
            continue
        x = np.column_stack([np.ones(len(frame), dtype=float), frame["control"].to_numpy(dtype=float)])
        y = frame["target"].to_numpy(dtype=float)
        beta = np.linalg.lstsq(x, y, rcond=None)[0]
        resid.loc[date, frame.index] = y - x @ beta

    resid_rank = resid.rank(axis=1, method="average", ascending=True, pct=True)
    return (
        resid_rank.reset_index()
        .melt(id_vars="time", var_name="ticker", value_name="c14_clv_volconf_resid_rank")
        .dropna(subset=["c14_clv_volconf_resid_rank"])
    )


def main():
    parse_args()
    print("Building RL signal matrix...")

    # S1 — primary signal spine (394 tickers, 2015–2025)
    s1 = load_s1_spine()
    print(
        f"  S1:  {len(s1):,} rows, {s1['ticker'].nunique()} tickers, "
        f"{s1['time'].min().date()} -> {s1['time'].max().date()}"
    )

    # C4 — open/close asymmetry
    c4 = pd.read_parquet(C4_PATH)[["time", "ticker", "oc_asym_5d"]]
    c4["time"] = pd.to_datetime(c4["time"])
    c4 = c4.rename(columns={"oc_asym_5d": "c4_oc_asym_5d"})

    # C5 — insider quality (sparse; time column is 'trading_day')
    c5_raw = pd.read_parquet(C5_PATH)[["trading_day", "ticker", "xs_ins_relative_size_5d"]]
    c5_raw = c5_raw.rename(columns={"trading_day": "time", "xs_ins_relative_size_5d": "c5_ins_relative_size_5d"})
    c5_raw["time"] = pd.to_datetime(c5_raw["time"])
    c5_raw["c5_signal_present"] = (c5_raw["c5_ins_relative_size_5d"].notna() & (c5_raw["c5_ins_relative_size_5d"] != 0)).astype(float)

    # C6 — contrarian intra-sector (computed on the fly)
    c6_raw = pd.read_parquet(C6_PATH)[["time", "ticker", "xs_sector_mom_5d_rank", "xs_intra_sector_rank"]]
    c6_raw["time"] = pd.to_datetime(c6_raw["time"])
    c6_raw["c6_contrarian_intra_5d"] = (
        c6_raw["xs_sector_mom_5d_rank"] * (1.0 - c6_raw["xs_intra_sector_rank"])
    )
    c6 = c6_raw[["time", "ticker", "c6_contrarian_intra_5d"]]

    # C7 — price limit count
    c7 = pd.read_parquet(C7_PATH)[["time", "ticker", "xs_ceiling_count_5d"]]
    c7["time"] = pd.to_datetime(c7["time"])
    c7 = c7.rename(columns={"xs_ceiling_count_5d": "c7_ceiling_count_5d"})

    # C8 — volume zscore
    c8 = pd.read_parquet(C8_PATH)[["time", "ticker", "xs_vol_zscore_5d"]]
    c8["time"] = pd.to_datetime(c8["time"])
    c8 = c8.rename(columns={"xs_vol_zscore_5d": "c8_vol_zscore_5d"})

    # C9 — short-term reversal
    c9 = pd.read_parquet(C9_PATH)[["time", "ticker", "xs_reversal_1d"]]
    c9["time"] = pd.to_datetime(c9["time"])
    c9 = c9.rename(columns={"xs_reversal_1d": "c9_reversal_1d"})

    # C10 — Amihud illiquidity level (computed on the fly from OHLCV)
    c10 = build_illiq_level_features()
    c10["time"] = pd.to_datetime(c10["time"])

    # C11 — 3-month continuation (medium-term trend)
    c11 = build_3m_continuation_features()
    c11["time"] = pd.to_datetime(c11["time"])

    # C12 — confirmed gap absorption
    c12 = build_gap_absorption_features()
    c12["time"] = pd.to_datetime(c12["time"])

    # C13 — compression blow-off reversal
    c13 = build_compress_blowoff_features()
    c13["time"] = pd.to_datetime(c13["time"])

    # C14 — close-location residual after removing C8
    c14 = build_clv_resid_features(c8)
    c14["time"] = pd.to_datetime(c14["time"])

    # Merge everything on (time, ticker) — left join to S1 spine
    result = s1.copy()
    for name, df in [
        ("C4", c4),
        ("C5", c5_raw[["time", "ticker", "c5_ins_relative_size_5d", "c5_signal_present"]]),
        ("C6", c6),
        ("C7", c7),
        ("C8", c8),
        ("C9", c9),
        ("C10", c10),
        ("C11", c11),
        ("C12", c12),
        ("C13", c13),
        ("C14", c14),
    ]:
        result = result.merge(df, on=["time", "ticker"], how="left")
        print(f"  After {name}: {result.shape}")

    # Rename S1 column
    result = result.rename(columns={"xs_proba": "s1_proba"})

    signal_cols = ["s1_proba", "c4_oc_asym_5d", "c5_ins_relative_size_5d", "c5_signal_present",
                   "c6_contrarian_intra_5d", "c7_ceiling_count_5d", "c8_vol_zscore_5d",
                   "c9_reversal_1d", "c10_illiq_level_rank", "c11_ret_60d_lag_rank",
                   "c12_gap_absorb_3", "c13_compress_blowoff_2", "c14_clv_volconf_resid_rank"]

    print("\nCoverage summary:")
    for col in signal_cols:
        nz = result[col].notna().sum()
        print(f"  {col:<32s}: {nz:,} ({100*nz/len(result):.1f}%)")

    result.to_parquet(OUT_PATH, index=False)
    print(f"\nSaved -> {OUT_PATH}")
    print(f"Shape: {result.shape}")


if __name__ == "__main__":
    main()
