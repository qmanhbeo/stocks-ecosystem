"""
Build dense ticker-day return skewness and tail-shape features.

Output:
- data/features/xs_return_skewness.parquet
"""

from pathlib import Path
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
STOCK_DIR = REPO_ROOT / "data" / "stock"
GRID_SRC = REPO_ROOT / "data" / "features" / "xs_barrier_vol_1d_hose_full.parquet"
OUT_PATH = REPO_ROOT / "data" / "features" / "xs_return_skewness.parquet"
EXCLUDE = {"VNINDEX", "VN30"}


def _down_std(x: np.ndarray) -> float:
    y = x[~np.isnan(x)]
    y = y[y < 0]
    if len(y) < 2:
        return 0.0
    return float(np.std(y))


def _up_std(x: np.ndarray) -> float:
    y = x[~np.isnan(x)]
    y = y[y > 0]
    if len(y) < 2:
        return 0.0
    return float(np.std(y))


def _left_tail_frac(x: np.ndarray) -> float:
    y = x[~np.isnan(x)]
    if len(y) < 5:
        return 0.0
    mu = float(np.mean(y))
    sd = float(np.std(y))
    if sd <= 1e-12:
        return 0.0
    thr = mu - sd
    return float((y < thr).mean())


def _build_ticker(path: Path) -> pd.DataFrame:
    ticker = path.stem.replace("gia_lich_su_", "").replace("_1D", "")
    if ticker in EXCLUDE:
        return pd.DataFrame()

    df = pd.read_parquet(path, columns=["time", "close"]).copy()
    if len(df) < 300:
        return pd.DataFrame()
    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values("time").drop_duplicates("time")
    df["ret_1d"] = df["close"].pct_change()
    r = df["ret_1d"]

    df["ret_skew_5d"] = r.rolling(5, min_periods=3).skew()
    df["ret_skew_20d"] = r.rolling(20, min_periods=10).skew()
    df["ret_skew_60d"] = r.rolling(60, min_periods=30).skew()
    df["downside_dev_20d"] = r.rolling(20, min_periods=10).apply(_down_std, raw=True)
    df["upside_dev_20d"] = r.rolling(20, min_periods=10).apply(_up_std, raw=True)
    df["down_up_vol_ratio_20d"] = df["downside_dev_20d"] / (df["upside_dev_20d"] + 1e-9)
    df["left_tail_frac_20d"] = r.rolling(20, min_periods=10).apply(_left_tail_frac, raw=True)

    mu20 = df["ret_skew_20d"].rolling(20, min_periods=10).mean()
    sd20 = df["ret_skew_20d"].rolling(20, min_periods=10).std()
    df["ret_skew_z20"] = (df["ret_skew_20d"] - mu20) / (sd20 + 1e-9)

    keep = [
        "time",
        "ret_skew_5d",
        "ret_skew_20d",
        "ret_skew_60d",
        "downside_dev_20d",
        "upside_dev_20d",
        "down_up_vol_ratio_20d",
        "left_tail_frac_20d",
        "ret_skew_z20",
    ]
    out = df[keep].copy()
    out["ticker"] = ticker
    return out


def main():
    files = sorted(STOCK_DIR.glob("gia_lich_su_*_1D.parquet"))
    parts = []
    for i, f in enumerate(files, start=1):
        if i % 100 == 0:
            print(f"processed {i}/{len(files)} files")
        p = _build_ticker(f)
        if not p.empty:
            parts.append(p)
    if not parts:
        raise RuntimeError("No features built.")

    feat = pd.concat(parts, ignore_index=True).sort_values(["time", "ticker"])
    grid = pd.read_parquet(GRID_SRC, columns=["time", "ticker"]).drop_duplicates()
    grid["time"] = pd.to_datetime(grid["time"])
    out = grid.merge(feat, on=["time", "ticker"], how="left")
    for c in out.columns:
        if c not in {"time", "ticker"}:
            out[c] = out[c].replace([np.inf, -np.inf], np.nan).fillna(0.0)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT_PATH, index=False)
    print(f"saved {len(out):,} rows -> {OUT_PATH}")
    nz = (out.drop(columns=["time", "ticker"]).abs().sum(axis=1) > 0).sum()
    print(f"non-zero rows: {nz:,} / {len(out):,} ({100*nz/len(out):.2f}%)")


if __name__ == "__main__":
    main()
