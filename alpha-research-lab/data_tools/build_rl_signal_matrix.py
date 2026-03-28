"""
Build combined RL signal state matrix from all confirmed/candidate signals.

Assembles S1 + all passing candidate signals (C4-C9) into a single feature
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

Usage:
    conda run -n stocks python data_tools/build_rl_signal_matrix.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
FEAT_DIR = REPO_ROOT / "data" / "features"
STOCK_DIR = REPO_ROOT / "data" / "stock"
OUT_PATH = FEAT_DIR / "xs_rl_signal_matrix.parquet"

S1_PATH       = FEAT_DIR / "xs_barrier_vol_1d_hose_full.parquet"
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
BETA_WINDOW = 60
BETA_MIN_DAYS = 40
EXCLUDE = {"VNINDEX", "VN30"}


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


def main():
    print("Building RL signal matrix...")

    # S1 — primary signal spine (394 tickers, 2015–2025)
    s1 = pd.read_parquet(S1_PATH)[["time", "ticker", "xs_proba", "actual"]]
    s1["time"] = pd.to_datetime(s1["time"])
    print(f"  S1:  {len(s1):,} rows, {s1['ticker'].nunique()} tickers")

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
    ]:
        result = result.merge(df, on=["time", "ticker"], how="left")
        print(f"  After {name}: {result.shape}")

    # Rename S1 column
    result = result.rename(columns={"xs_proba": "s1_proba"})

    signal_cols = ["s1_proba", "c4_oc_asym_5d", "c5_ins_relative_size_5d", "c5_signal_present",
                   "c6_contrarian_intra_5d", "c7_ceiling_count_5d", "c8_vol_zscore_5d",
                   "c9_reversal_1d", "c10_illiq_level_rank", "c11_ret_60d_lag_rank"]

    print("\nCoverage summary:")
    for col in signal_cols:
        nz = result[col].notna().sum()
        print(f"  {col:<32s}: {nz:,} ({100*nz/len(result):.1f}%)")

    result.to_parquet(OUT_PATH, index=False)
    print(f"\nSaved -> {OUT_PATH}")
    print(f"Shape: {result.shape}")


if __name__ == "__main__":
    main()
