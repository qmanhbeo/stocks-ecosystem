"""
H61: Liquidity-Filtered Universe.

Real trading requires liquidity. Does the signal survive when we restrict
to only the stocks you can actually trade?

Method (look-ahead free):
  - For each date in the probas, compute each stock's 20-day trailing avg
    VND volume (shares × close price) using HISTORICAL data only (shifted 1d).
  - Test universe sizes: all 393, top 200, 150, 100, 50 most liquid stocks per day.
  - For each filtered universe: quintile IC test + top-5 Sharpe (nested WF).

Key question: Does restricting to liquid stocks HURT or HELP the signal?

Usage:
    conda run -n stocks python analysis/h61_liquidity_filter.py
    conda run -n stocks python analysis/h61_liquidity_filter.py --probas data/features/xs_barrier_all_probas_hose_full.parquet
"""
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from path_utils import data_path
from itertools import product
from scipy.stats import spearmanr, ttest_1samp

DEFAULT_PROBAS = data_path("features/xs_barrier_all_probas_hose_full.parquet")
VIX_PATH       = data_path("fx-commodities/fx_commodities_vix_1D.parquet")
STOCK_DIR      = data_path("stock")

START_YEAR  = 2015
TOP_N       = 5
MIN_PROBA   = 0.55
VIX_MIN     = 15.0
VIX_MAX     = 30.0
VOL_WINDOW  = 20   # trailing days for volume average
META_WINDOW = 3    # years for nested WF meta-validation

# Universe size thresholds to test (top-N most liquid stocks per day)
UNIVERSE_SIZES = [393, 200, 150, 100, 50]


def build_rolling_volume(tickers: list) -> pd.DataFrame:
    """
    Load historical OHLCV for all tickers, compute trailing 20d avg VND volume
    (shares × close), shift forward 1 day so we never use same-day volume
    to decide same-day universe membership.

    Returns DataFrame with columns: time, ticker, avg_vnd_vol
    """
    print(f"  Loading volume data for {len(tickers)} tickers...")
    records = []
    for t in tickers:
        fp = STOCK_DIR / f"gia_lich_su_{t}_1D.parquet"
        if not fp.exists():
            continue
        try:
            df = pd.read_parquet(fp, columns=["time", "close", "volume"])
            df["time"] = pd.to_datetime(df["time"])
            df = df.sort_values("time").reset_index(drop=True)
            df["vnd_vol"] = df["close"] * df["volume"]
            # Trailing average — shift 1 to avoid look-ahead
            df["avg_vnd_vol"] = df["vnd_vol"].rolling(VOL_WINDOW, min_periods=5).mean().shift(1)
            df["ticker"] = t
            records.append(df[["time", "ticker", "avg_vnd_vol"]].dropna())
        except Exception:
            pass

    if not records:
        return pd.DataFrame()
    return pd.concat(records, ignore_index=True)


def filter_by_universe(df: pd.DataFrame, vol_df: pd.DataFrame, top_k: int) -> pd.DataFrame:
    """
    For each date, keep only the top-k most liquid stocks.
    If top_k >= total tickers, returns full df unchanged.
    """
    if top_k >= 390:
        return df

    # Rank by avg_vnd_vol per day, keep top-k
    merged = df.merge(vol_df, on=["time", "ticker"], how="left")
    merged["avg_vnd_vol"] = merged["avg_vnd_vol"].fillna(0)
    merged["liq_rank"] = merged.groupby("time")["avg_vnd_vol"].rank(
        ascending=False, method="first"
    )
    return merged[merged["liq_rank"] <= top_k].drop(columns=["avg_vnd_vol", "liq_rank"])


def quintile_ic(df: pd.DataFrame, label: str) -> float:
    """Run quintile factor test, return avg IC."""
    per_year = []
    for year, grp in df.groupby("year"):
        if year < START_YEAR:
            continue
        daily = []
        for _, day in grp.groupby("time"):
            if len(day) < 10:
                continue
            ic = spearmanr(day["xs_proba"], day["actual"])[0]
            q5 = day[day["xs_proba"].rank(pct=True) >= 0.8]["actual"].mean()
            q1 = day[day["xs_proba"].rank(pct=True) <= 0.2]["actual"].mean()
            daily.append({"ic": ic, "spread": q5 - q1})
        if daily:
            d = pd.DataFrame(daily)
            per_year.append({
                "year": year,
                "ic": d["ic"].mean(),
                "spread": d["spread"].mean(),
                "pval": ttest_1samp(d["spread"], 0).pvalue,
            })

    if not per_year:
        return float("nan")
    avg_ic  = np.mean([r["ic"] for r in per_year])
    avg_sp  = np.mean([r["spread"] for r in per_year])
    n_sig   = sum(1 for r in per_year if r["pval"] < 0.05)
    print(f"  {label:<22}  IC={avg_ic:+.4f}  Q5-Q1={avg_sp*100:+.2f}%  sig={n_sig}/{len(per_year)}yrs", end="")
    return avg_ic


def top5_nested_wf(df: pd.DataFrame) -> tuple:
    """
    Run nested WF (3-year meta window) on the filtered universe.
    Returns (avg_edge, sharpe, n_pos, n_years).
    """
    vix = pd.read_parquet(VIX_PATH)[["time", "close"]].rename(columns={"close": "vix"})
    vix["time"] = pd.to_datetime(vix["time"])
    df2 = df.merge(vix, on="time", how="left")
    df2["vix"] = df2["vix"].ffill()

    vix_max_grid   = [25.0, 28.0, 30.0, 32.0, 35.0]
    min_proba_grid = [0.50, 0.52, 0.55, 0.58]
    top_n_grid     = [3, 5, 7]
    all_years = sorted(df2["year"].unique())
    test_years = [y for y in all_years if y >= START_YEAR]

    results = []
    for test_year in test_years:
        meta_years = [y for y in all_years if test_year - META_WINDOW <= y < test_year]
        if len(meta_years) < 2:
            continue
        df_meta = df2[df2["year"].isin(meta_years)]
        df_test = df2[df2["year"] == test_year]

        best_sh, best_params = -999, None
        for top_n, min_proba, vix_max in product(top_n_grid, min_proba_grid, vix_max_grid):
            yr_edges = []
            for yr, grp in df_meta.groupby("year"):
                naive = grp["actual"].mean()
                day_eds = []
                for _, day in grp.groupby("time"):
                    if not (VIX_MIN <= day["vix"].iloc[0] <= vix_max):
                        continue
                    top = day.nlargest(top_n, "xs_proba")
                    if top["xs_proba"].min() >= min_proba:
                        day_eds.append(top["actual"].mean() - naive)
                if len(day_eds) >= 5:
                    yr_edges.append(np.mean(day_eds))
            if len(yr_edges) >= 2:
                sh = np.mean(yr_edges) / (np.std(yr_edges) + 1e-9)
                if sh > best_sh:
                    best_sh, best_params = sh, (top_n, min_proba, vix_max)

        if best_params is None:
            continue
        top_n, min_proba, vix_max = best_params
        naive = df_test["actual"].mean()
        day_eds = []
        for _, day in df_test.groupby("time"):
            if not (VIX_MIN <= day["vix"].iloc[0] <= vix_max):
                continue
            top = day.nlargest(top_n, "xs_proba")
            if top["xs_proba"].min() >= min_proba:
                day_eds.append(top["actual"].mean() - naive)
        if day_eds:
            results.append(np.mean(day_eds))

    if not results:
        return float("nan"), float("nan"), 0, 0
    avg   = np.mean(results)
    sharpe = avg / (np.std(results) + 1e-9)
    n_pos = sum(1 for e in results if e > 0)
    return avg, sharpe, n_pos, len(results)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probas", type=str, default=str(DEFAULT_PROBAS))
    args = parser.parse_args()

    print(f"\nH61: LIQUIDITY FILTER EXPERIMENT")
    print(f"Loading probas: {args.probas}")
    df = pd.read_parquet(args.probas)
    df["time"] = pd.to_datetime(df["time"])
    all_tickers = df["ticker"].unique().tolist()
    print(f"  {len(df):,} rows | {len(all_tickers)} tickers | years {df['year'].min()}-{df['year'].max()}")

    vol_df = build_rolling_volume(all_tickers)
    print(f"  Volume data: {len(vol_df):,} ticker-date rows")

    print(f"\n{'='*80}")
    print(f"LIQUIDITY FILTER RESULTS (Top-K most liquid stocks per day)")
    print(f"{'='*80}")
    print(f"\n  {'Universe':>22}  {'IC':>8}  {'Q5-Q1':>8}  {'Sig':>6}  {'NW_edge':>9}  {'NW_sh':>8}  {'pos':>6}")
    print("  " + "-"*78)

    for top_k in UNIVERSE_SIZES:
        label = f"Top-{top_k}" if top_k < 390 else f"All-{len(all_tickers)}"
        df_filt = filter_by_universe(df, vol_df, top_k)
        n_tickers = df_filt["ticker"].nunique()
        label_full = f"{label} ({n_tickers}tk)"

        avg_ic = quintile_ic(df_filt, label_full)
        avg_edge, sharpe, n_pos, n_yrs = top5_nested_wf(df_filt)

        edge_str  = f"{avg_edge*100:+.2f}%"  if not np.isnan(avg_edge) else "  N/A"
        sharpe_str = f"{sharpe:.2f}"          if not np.isnan(sharpe)   else "  N/A"
        print(f"  → nested WF: {edge_str} edge, Sharpe {sharpe_str}, {n_pos}/{n_yrs} pos yrs")
        print()

    # Also test VND volume thresholds (absolute)
    thresholds_bn = [0, 1, 5, 10, 20]  # billion VND avg daily
    print(f"\n  {'VND vol threshold':>25}  {'n_tickers_avg':>14}  ", end="")
    print(f"{'IC':>8}  {'NW_sh':>8}")
    print("  " + "-"*60)

    for thr_bn in thresholds_bn:
        thr = thr_bn * 1e9
        if thr == 0:
            df_filt = df
            label = "No filter"
        else:
            merged = df.merge(vol_df, on=["time", "ticker"], how="left")
            merged["avg_vnd_vol"] = merged["avg_vnd_vol"].fillna(0)
            df_filt = merged[merged["avg_vnd_vol"] >= thr].drop(columns=["avg_vnd_vol"])
            label = f">={thr_bn}B VND/day"

        n_avg = df_filt.groupby("time")["ticker"].count().mean()
        avg_ic = quintile_ic(df_filt, label)
        _, sharpe, _, _ = top5_nested_wf(df_filt)
        sharpe_str = f"{sharpe:.2f}" if not np.isnan(sharpe) else "N/A"
        print(f"  → avg tickers/day: {n_avg:.1f}, Sharpe {sharpe_str}")
        print()

    print("\nH61 DONE. Key questions to answer:")
    print("  1. Does IC hold or improve with liquidity filter?")
    print("  2. What is the minimum universe size before edge degrades?")
    print("  3. At what VND threshold does the strategy remain viable?")


if __name__ == "__main__":
    main()
