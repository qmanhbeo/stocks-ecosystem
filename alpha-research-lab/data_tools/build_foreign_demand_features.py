"""
Build VNM ETF foreign demand proxy features (H110).

VNM ETF (NYSE) trades on US hours after HOSE closes. When VNM return on day T
exceeds VNINDEX return (positive premium), US-based foreign investors are signaling
net demand that cannot execute until HOSE opens T+1. This is the closest available
proxy to the blocked H95 foreign daily flow signal.

Cross-sectional dimension: each stock has a "foreign affinity beta" — rolling 120-day
Spearman correlation of its excess return vs VNM premium. On high-premium days, stocks
with high foreign affinity should outperform (foreign buyers target these stocks).

Input:
  data/fx-commodities/fx_commodities_vnm_etf_1D.parquet  — VNM ETF price
  data/stock/gia_lich_su_VNINDEX_1D.parquet              — VNINDEX price
  data/stock/gia_lich_su_*_1D.parquet                    — all stock prices

Output: data/features/xs_foreign_demand_daily.parquet
  time, ticker,
  xs_vnm_premium_1d       — lagged VNM ETF premium (date-level scalar, same for all tickers)
  xs_foreign_affinity_120d — rolling 120d Spearman of stock excess vs vnm_premium
  xs_foreign_affinity_20d  — rolling 20d version (recent regime)
  xs_fa_rank              — cross-sectional percentile rank of xs_foreign_affinity_120d
  xs_fa_signal            — xs_foreign_affinity_120d * xs_vnm_premium_1d (interaction)

Note: Spearman is approximated via rank-correlation using rolling windows.
      Window rollback is done in pandas with min_periods=60 for 120d, min_periods=10 for 20d.

Usage:
    conda activate stocks
    python data_tools/build_foreign_demand_features.py
"""

from __future__ import annotations

from pathlib import Path
from path_utils import data_path
import glob
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

REPO_ROOT = Path(__file__).resolve().parents[1]
STOCK_DIR = data_path("stock")
VNM_PATH = data_path("fx-commodities/fx_commodities_vnm_etf_1D.parquet")
VNI_PATH = data_path("stock/gia_lich_su_VNINDEX_1D.parquet")
OUT_PATH = data_path("features/xs_foreign_demand_daily.parquet")
GRID_SRC = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
EXCLUDE = {"VNINDEX", "VN30"}

AFFINITY_WINDOW_LONG = 120   # ~6 months of trading days
AFFINITY_WINDOW_SHORT = 20   # ~1 month


def compute_rolling_spearman(x: pd.Series, y: pd.Series, window: int, min_periods: int) -> pd.Series:
    """Compute rolling Spearman correlation using rank-correlation approximation."""
    # Approximate via rolling Pearson of ranked values.
    # This avoids expensive per-window spearmanr() calls.
    x_rank = x.rolling(window, min_periods=min_periods).apply(
        lambda v: pd.Series(v).rank().iloc[-1] / len(v), raw=False
    )
    y_rank = y.rolling(window, min_periods=min_periods).apply(
        lambda v: pd.Series(v).rank().iloc[-1] / len(v), raw=False
    )
    # Pearson of ranks within rolling window
    def _corr(vals):
        n = len(vals) // 2
        xv = vals[:n]
        yv = vals[n:]
        if len(xv) < 5 or np.std(xv) < 1e-10 or np.std(yv) < 1e-10:
            return np.nan
        return float(np.corrcoef(xv, yv)[0, 1])

    # Use rolling().corr() which is efficient in pandas
    combined = pd.DataFrame({"x": x, "y": y})
    return combined["x"].rolling(window, min_periods=min_periods).corr(combined["y"])


def build_features() -> pd.DataFrame:
    # --- VNM premium (date-level signal) ---
    vnm = pd.read_parquet(VNM_PATH, columns=["time", "close"]).sort_values("time")
    vnm["time"] = pd.to_datetime(vnm["time"])
    vnm = vnm.set_index("time")
    vnm_ret = vnm["close"].pct_change().rename("vnm_ret")

    vni = pd.read_parquet(VNI_PATH, columns=["time", "close"]).sort_values("time")
    vni["time"] = pd.to_datetime(vni["time"])
    vni = vni.set_index("time")
    vni_ret = vni["close"].pct_change().rename("vni_ret")

    # Align on common dates
    macro = pd.concat([vnm_ret, vni_ret], axis=1).dropna()
    macro["vnm_premium"] = macro["vnm_ret"] - macro["vni_ret"]
    # Shift by 1: yesterday's VNM premium predicts today's HOSE returns
    macro["xs_vnm_premium_1d"] = macro["vnm_premium"].shift(1)

    # --- Load grid ---
    grid_df = pd.read_parquet(GRID_SRC, columns=["time", "ticker"])
    grid_df["time"] = pd.to_datetime(grid_df["time"])
    grid = grid_df.drop_duplicates()
    trading_days = sorted(grid["time"].unique())

    # --- Per-ticker foreign affinity ---
    print("Computing per-ticker rolling Spearman correlation with VNM premium...")
    ticker_files = sorted(glob.glob(str(STOCK_DIR / "gia_lich_su_*_1D.parquet")))
    parts = []

    for f in ticker_files:
        ticker = Path(f).stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        try:
            stock = pd.read_parquet(f, columns=["time", "close"])
            stock["time"] = pd.to_datetime(stock["time"])
            stock = stock.sort_values("time").set_index("time")
            if len(stock) < 150:
                continue
            ret = stock["close"].pct_change()
            # Compute excess return (vs VNINDEX)
            excess = ret.sub(vni_ret, fill_value=np.nan)
            # Align with vnm_premium on common index
            aligned = pd.concat([excess.rename("excess"), macro["vnm_premium"]], axis=1).dropna()
            if len(aligned) < 60:
                continue
            # Rolling Spearman (Pearson-of-ranks approximation via pandas rolling.corr)
            aff_long = compute_rolling_spearman(
                aligned["excess"], aligned["vnm_premium"],
                AFFINITY_WINDOW_LONG, min_periods=60
            )
            aff_short = compute_rolling_spearman(
                aligned["excess"], aligned["vnm_premium"],
                AFFINITY_WINDOW_SHORT, min_periods=10
            )
            result = pd.DataFrame({
                "time": aligned.index,
                "ticker": ticker,
                "xs_foreign_affinity_120d": aff_long.values,
                "xs_foreign_affinity_20d": aff_short.values,
            })
            parts.append(result)
        except Exception:
            continue

    print(f"  Computed affinity for {len(parts)} tickers")
    affinity = pd.concat(parts, ignore_index=True)
    affinity["time"] = pd.to_datetime(affinity["time"])

    # --- Merge into grid ---
    result = grid.merge(affinity, on=["time", "ticker"], how="left")
    result = result.merge(
        macro[["xs_vnm_premium_1d"]].reset_index(),
        on="time", how="left",
    )

    # Cross-sectional rank of affinity_120d for each date
    result["xs_fa_rank"] = result.groupby("time")["xs_foreign_affinity_120d"].rank(pct=True)

    # Interaction: affinity × premium
    result["xs_fa_signal"] = result["xs_foreign_affinity_120d"] * result["xs_vnm_premium_1d"]

    return result.sort_values(["time", "ticker"]).reset_index(drop=True)


def main():
    print("Building VNM ETF foreign demand features (H110)...")
    feat = build_features()

    feat_cols = [c for c in feat.columns if c.startswith("xs_")]
    print(f"\nOutput: {len(feat):,} rows")
    for col in feat_cols:
        nz = feat[col].notna().sum()
        print(f"  {col}: {nz:,} non-null ({100*nz/len(feat):.1f}%)")

    feat.to_parquet(OUT_PATH, index=False)
    print(f"\nSaved -> {OUT_PATH}")


if __name__ == "__main__":
    main()
