"""
Build dense ticker-day open/close asymmetry features.

Output:
- data/features/xs_open_close_asymmetry.parquet

Columns:
- time, ticker
- overnight_ret_1d
- intraday_ret_1d
- open_to_open_ret_1d
- close_to_close_ret_1d
- oc_asym_1d
- overnight_mom_5d, overnight_mom_20d
- intraday_mom_5d, intraday_mom_20d
- oc_asym_5d, oc_asym_20d
- gap_abs_5d
"""

from pathlib import Path
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
STOCK_DIR = REPO_ROOT / "data" / "stock"
GRID_SRC = REPO_ROOT / "data" / "features" / "xs_barrier_vol_1d_hose_full.parquet"
OUT_PATH = REPO_ROOT / "data" / "features" / "xs_open_close_asymmetry.parquet"
EXCLUDE = {"VNINDEX", "VN30"}


def _build_for_ticker(path: Path) -> pd.DataFrame:
    ticker = path.stem.replace("gia_lich_su_", "").replace("_1D", "")
    if ticker in EXCLUDE:
        return pd.DataFrame()

    df = pd.read_parquet(path, columns=["time", "open", "close"]).copy()
    if len(df) < 300:
        return pd.DataFrame()

    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values("time").drop_duplicates("time")
    df["prev_close"] = df["close"].shift(1)
    df["prev_open"] = df["open"].shift(1)

    df["overnight_ret_1d"] = (df["open"] / df["prev_close"]) - 1.0
    df["intraday_ret_1d"] = (df["close"] / df["open"]) - 1.0
    df["open_to_open_ret_1d"] = (df["open"] / df["prev_open"]) - 1.0
    df["close_to_close_ret_1d"] = (df["close"] / df["prev_close"]) - 1.0
    df["oc_asym_1d"] = df["overnight_ret_1d"] - df["intraday_ret_1d"]

    for col in ["overnight_ret_1d", "intraday_ret_1d", "oc_asym_1d"]:
        df[col] = df[col].replace([np.inf, -np.inf], np.nan)

    df["overnight_mom_5d"] = df["overnight_ret_1d"].rolling(5, min_periods=1).sum()
    df["overnight_mom_20d"] = df["overnight_ret_1d"].rolling(20, min_periods=1).sum()
    df["intraday_mom_5d"] = df["intraday_ret_1d"].rolling(5, min_periods=1).sum()
    df["intraday_mom_20d"] = df["intraday_ret_1d"].rolling(20, min_periods=1).sum()
    df["oc_asym_5d"] = df["oc_asym_1d"].rolling(5, min_periods=1).mean()
    df["oc_asym_20d"] = df["oc_asym_1d"].rolling(20, min_periods=1).mean()
    df["gap_abs_5d"] = df["overnight_ret_1d"].abs().rolling(5, min_periods=1).mean()

    keep = [
        "time",
        "overnight_ret_1d",
        "intraday_ret_1d",
        "open_to_open_ret_1d",
        "close_to_close_ret_1d",
        "oc_asym_1d",
        "overnight_mom_5d",
        "overnight_mom_20d",
        "intraday_mom_5d",
        "intraday_mom_20d",
        "oc_asym_5d",
        "oc_asym_20d",
        "gap_abs_5d",
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
        feat = _build_for_ticker(f)
        if not feat.empty:
            parts.append(feat)

    if not parts:
        raise RuntimeError("No ticker features were built.")

    all_feat = pd.concat(parts, ignore_index=True)
    all_feat = all_feat.sort_values(["time", "ticker"]).reset_index(drop=True)

    grid = pd.read_parquet(GRID_SRC, columns=["time", "ticker"]).drop_duplicates()
    grid["time"] = pd.to_datetime(grid["time"])
    out = grid.merge(all_feat, on=["time", "ticker"], how="left")
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
