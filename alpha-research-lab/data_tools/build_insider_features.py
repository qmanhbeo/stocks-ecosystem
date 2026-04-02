"""
Build insider-signal feature matrix for the XS walk-forward.

Input:  data/features/xs_insider_deals_raw.parquet
        (from data_tools/fetch_insider_deals.py)

Output: data/features/xs_insider_features.parquet
  Columns: trading_day, ticker,
    insider_net_plan_5d    : sum of insider net_plan_vol over last 5 trading days
    insider_net_plan_30d   : sum of insider net_plan_vol over last 30 trading days
    insider_net_real_5d    : sum of net_real_vol over last 5 trading days
    insider_net_real_30d   : sum over last 30 trading days
    insider_buy_flag_5d    : 1 if any insider net buy in last 5 days
    insider_sell_flag_5d   : 1 if any insider net sell in last 5 days
    large_sh_net_plan_5d   : same for large shareholders (non-insider)
    large_sh_net_plan_30d

Signal design:
  - Use published_date as the event date (avoid look-ahead on real volumes)
  - Rolling backward aggregation: features at day T use disclosures from [T-N, T-1]
  - The XS WF then uses these features alongside price/volume signals

Usage:
    conda activate stocks
    python data_tools/build_insider_features.py
"""

from pathlib import Path
from path_utils import data_path
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_PATH  = data_path("features/xs_insider_deals_raw.parquet")
OUT_PATH  = data_path("features/xs_insider_features.parquet")

# Reference grid: (trading_day, ticker) universe from existing features
GRID_SRC  = data_path("features/xs_barrier_vol_1d_hose_full.parquet")


def build_features() -> pd.DataFrame:
    raw = pd.read_parquet(RAW_PATH)
    raw["published_date"] = pd.to_datetime(raw["published_date"])

    # Daily aggregate per ticker per published_date
    # Insider vs large shareholder
    insider = raw[raw["is_insider"]].copy()
    large_sh = raw[~raw["is_insider"]].copy()

    def daily_agg(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
        g = df.groupby(["published_date", "ticker"]).agg(
            net_plan=("net_plan_vol", "sum"),
            net_real=("net_real_vol", "sum"),
        ).reset_index()
        g = g.rename(columns={"net_plan": f"{prefix}_net_plan", "net_real": f"{prefix}_net_real"})
        return g

    ins_daily = daily_agg(insider, "ins")
    lsh_daily = daily_agg(large_sh, "lsh")

    # Load the (trading_day, ticker) grid — column is "time" in this parquet
    grid_df = pd.read_parquet(GRID_SRC, columns=["time", "ticker"])
    grid_df = grid_df.rename(columns={"time": "trading_day"})
    grid_df["trading_day"] = pd.to_datetime(grid_df["trading_day"])
    grid = grid_df.drop_duplicates()

    tickers = sorted(grid["ticker"].unique())
    trading_days = sorted(grid["trading_day"].unique())

    print(f"Grid: {len(trading_days)} trading days x {len(tickers)} tickers = {len(grid):,} rows")
    print(f"Raw insider events: {len(insider):,} rows, {insider['ticker'].nunique()} tickers")
    print(f"Raw large-sh events: {len(large_sh):,} rows, {large_sh['ticker'].nunique()} tickers")

    # Pivot to (date, ticker) daily signal series
    def make_panel(daily: pd.DataFrame, signal_col: str) -> pd.DataFrame:
        piv = daily.pivot_table(
            index="published_date", columns="ticker", values=signal_col, aggfunc="sum"
        ).reindex(index=pd.to_datetime(trading_days))
        piv = piv.fillna(0)
        return piv

    ins_plan_piv = make_panel(ins_daily, "ins_net_plan")
    ins_real_piv = make_panel(ins_daily, "ins_net_real")
    lsh_plan_piv = make_panel(lsh_daily, "lsh_net_plan")
    lsh_real_piv = make_panel(lsh_daily, "lsh_net_real")

    # Rolling sums (backward-looking: use data up to but NOT including today)
    # shift(1) ensures we don't use same-day data
    def rolling_sum(piv: pd.DataFrame, window: int) -> pd.DataFrame:
        return piv.shift(1).rolling(window, min_periods=1).sum()

    ins_plan_5  = rolling_sum(ins_plan_piv, 5)
    ins_plan_30 = rolling_sum(ins_plan_piv, 30)
    ins_real_5  = rolling_sum(ins_real_piv, 5)
    ins_real_30 = rolling_sum(ins_real_piv, 30)
    lsh_plan_5  = rolling_sum(lsh_plan_piv, 5)
    lsh_plan_30 = rolling_sum(lsh_plan_piv, 30)

    # Binary flags
    ins_buy_flag_5  = (ins_plan_5 > 0).astype(float)
    ins_sell_flag_5 = (ins_plan_5 < 0).astype(float)

    # Melt back to long format
    def melt_panel(piv: pd.DataFrame, col_name: str) -> pd.DataFrame:
        m = piv.reset_index().rename(columns={"index": "trading_day", "published_date": "trading_day"})
        m = m.melt(id_vars="trading_day", var_name="ticker", value_name=col_name)
        return m

    dfs = [
        melt_panel(ins_plan_5,      "insider_net_plan_5d"),
        melt_panel(ins_plan_30,     "insider_net_plan_30d"),
        melt_panel(ins_real_5,      "insider_net_real_5d"),
        melt_panel(ins_real_30,     "insider_net_real_30d"),
        melt_panel(ins_buy_flag_5,  "insider_buy_flag_5d"),
        melt_panel(ins_sell_flag_5, "insider_sell_flag_5d"),
        melt_panel(lsh_plan_5,      "large_sh_net_plan_5d"),
        melt_panel(lsh_plan_30,     "large_sh_net_plan_30d"),
    ]

    # Merge all feature columns
    result = dfs[0]
    for df in dfs[1:]:
        result = result.merge(df, on=["trading_day", "ticker"], how="left")

    # Restrict to the exact grid
    result = grid.merge(result, on=["trading_day", "ticker"], how="left")
    for col in result.columns[2:]:
        result[col] = result[col].fillna(0)

    result = result.sort_values(["trading_day", "ticker"]).reset_index(drop=True)
    return result


def main():
    print("Building insider features...")
    feat = build_features()

    nonzero_mask = feat.drop(columns=["trading_day","ticker"]).abs().sum(axis=1) > 0
    nonzero_rows = nonzero_mask.sum()
    pct = 100 * nonzero_rows / len(feat)
    print(f"\nNon-zero rows: {nonzero_rows:,} / {len(feat):,} ({pct:.1f}%)")
    print(f"Coverage by feature:")
    for col in feat.columns[2:]:
        nz = (feat[col] != 0).sum()
        print(f"  {col}: {nz:,} ({100*nz/len(feat):.2f}%)")

    feat.to_parquet(OUT_PATH, index=False)
    print(f"\nSaved {len(feat):,} rows -> {OUT_PATH}")


if __name__ == "__main__":
    main()
