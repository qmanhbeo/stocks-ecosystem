"""
Build dense date-level cross-sectional dispersion regime features.

Output:
- data/features/xs_dispersion_regime_daily.parquet

Columns:
- time
- xs_ret_std_1d
- xs_ret_iqr_1d
- xs_tail_spread_1d
- xs_breadth_up_1d
- xs_breadth_down_1d
- xs_mean_ret_1d
- xs_overnight_intraday_spread
- xs_ret_std_5d
- xs_ret_std_20d
- xs_breadth_up_5d
- xs_breadth_up_20d
- xs_dispersion_z20
"""

from pathlib import Path
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
STOCK_DIR = REPO_ROOT / "data" / "stock"
GRID_SRC = REPO_ROOT / "data" / "features" / "xs_barrier_vol_1d_hose_full.parquet"
OUT_PATH = REPO_ROOT / "data" / "features" / "xs_dispersion_regime_daily.parquet"
EXCLUDE = {"VNINDEX", "VN30"}


def _per_ticker_rets(path: Path) -> pd.DataFrame:
    ticker = path.stem.replace("gia_lich_su_", "").replace("_1D", "")
    if ticker in EXCLUDE:
        return pd.DataFrame()
    df = pd.read_parquet(path, columns=["time", "open", "close"]).copy()
    if len(df) < 300:
        return pd.DataFrame()
    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values("time").drop_duplicates("time")
    df["prev_close"] = df["close"].shift(1)
    df["cc_ret_1d"] = (df["close"] / df["prev_close"]) - 1.0
    df["overnight_ret_1d"] = (df["open"] / df["prev_close"]) - 1.0
    df["intraday_ret_1d"] = (df["close"] / df["open"]) - 1.0
    out = df[["time", "cc_ret_1d", "overnight_ret_1d", "intraday_ret_1d"]].copy()
    out["ticker"] = ticker
    return out


def main():
    files = sorted(STOCK_DIR.glob("gia_lich_su_*_1D.parquet"))
    parts = []
    for i, f in enumerate(files, start=1):
        if i % 100 == 0:
            print(f"processed {i}/{len(files)} files")
        r = _per_ticker_rets(f)
        if not r.empty:
            parts.append(r)
    if not parts:
        raise RuntimeError("No return series built.")

    rets = pd.concat(parts, ignore_index=True)
    for c in ["cc_ret_1d", "overnight_ret_1d", "intraday_ret_1d"]:
        rets[c] = rets[c].replace([np.inf, -np.inf], np.nan)

    def _iqr(s: pd.Series) -> float:
        q = s.quantile([0.25, 0.75])
        return float(q.iloc[1] - q.iloc[0])

    def _tail_spread(s: pd.Series) -> float:
        q = s.quantile([0.1, 0.9])
        return float(q.iloc[1] - q.iloc[0])

    daily = (
        rets.groupby("time")
        .agg(
            xs_ret_std_1d=("cc_ret_1d", "std"),
            xs_ret_iqr_1d=("cc_ret_1d", _iqr),
            xs_tail_spread_1d=("cc_ret_1d", _tail_spread),
            xs_breadth_up_1d=("cc_ret_1d", lambda s: float((s > 0).mean())),
            xs_breadth_down_1d=("cc_ret_1d", lambda s: float((s < 0).mean())),
            xs_mean_ret_1d=("cc_ret_1d", "mean"),
            xs_overnight_intraday_spread=(
                "cc_ret_1d",
                lambda s: float(
                    (
                        rets.loc[s.index, "overnight_ret_1d"] -
                        rets.loc[s.index, "intraday_ret_1d"]
                    ).mean()
                ),
            ),
        )
        .reset_index()
        .sort_values("time")
    )

    daily["xs_ret_std_5d"] = daily["xs_ret_std_1d"].rolling(5, min_periods=1).mean()
    daily["xs_ret_std_20d"] = daily["xs_ret_std_1d"].rolling(20, min_periods=1).mean()
    daily["xs_breadth_up_5d"] = daily["xs_breadth_up_1d"].rolling(5, min_periods=1).mean()
    daily["xs_breadth_up_20d"] = daily["xs_breadth_up_1d"].rolling(20, min_periods=1).mean()

    mean20 = daily["xs_ret_std_1d"].rolling(20, min_periods=5).mean()
    std20 = daily["xs_ret_std_1d"].rolling(20, min_periods=5).std()
    daily["xs_dispersion_z20"] = (daily["xs_ret_std_1d"] - mean20) / (std20 + 1e-9)

    # Align to trading-day spine used in WF.
    days = pd.read_parquet(GRID_SRC, columns=["time"]).drop_duplicates().sort_values("time")
    days["time"] = pd.to_datetime(days["time"])
    out = days.merge(daily, on="time", how="left").sort_values("time")

    for c in out.columns:
        if c != "time":
            out[c] = out[c].replace([np.inf, -np.inf], np.nan).ffill().fillna(0.0)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT_PATH, index=False)
    print(f"saved {len(out):,} rows -> {OUT_PATH}")
    print(f"date range: {out['time'].min().date()} -> {out['time'].max().date()}")
    print(f"nan count: {int(out.drop(columns=['time']).isna().sum().sum())}")


if __name__ == "__main__":
    main()
