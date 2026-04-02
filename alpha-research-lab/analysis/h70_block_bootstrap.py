"""
H70: Block Bootstrap P-Values for IC Significance.

Standard t-tests on daily IC assume observations are IID. But:
  - Stocks are cross-sectionally correlated (sector co-movement)
  - Daily rankings are autocorrelated (momentum → yesterday's ranking ≈ today's)
  - Consecutive IC values are NOT independent

Solution: circular block bootstrap.
  - Treat the pooled daily IC time series as the data
  - Resample contiguous B-day blocks with replacement (preserves autocorrelation)
  - Compute bootstrap distribution of mean IC
  - P-value = P(boot_mean >= observed | H0: true mean = 0)

Block sizes tested: B=1 (IID baseline), B=5 (weekly), B=10, B=20 (monthly).
10,000 bootstrap resamples.

Note: IC already aggregates 393 cross-sectional observations into one scalar per day,
so it partially accounts for cross-sectional dependence. Block bootstrap addresses
the remaining temporal autocorrelation.

Usage:
    conda run -n stocks python analysis/h70_block_bootstrap.py
"""
import numpy as np
import pandas as pd
from pathlib import Path
from path_utils import data_path
from scipy.stats import spearmanr, ttest_1samp

DEFAULT_PROBAS = data_path("features/xs_barrier_all_probas_hose_full.parquet")

START_YEAR  = 2015
END_YEAR    = 2025
N_BOOT      = 10_000
BLOCK_SIZES = [1, 5, 10, 20]


def compute_daily_ic(df: pd.DataFrame) -> pd.DataFrame:
    """Spearman IC between xs_proba and actual, per day."""
    records = []
    for date, day in df.groupby("time"):
        if len(day) < 10:
            continue
        ic, _ = spearmanr(day["xs_proba"], day["actual"])
        if not np.isnan(ic):
            records.append({"time": date, "year": date.year, "ic": ic})
    return pd.DataFrame(records)


def circular_block_bootstrap(ic_arr: np.ndarray, B: int,
                              n_boot: int, rng: np.random.Generator) -> np.ndarray:
    """
    Circular block bootstrap. The series wraps around to avoid edge effects.
    Returns array of n_boot bootstrap mean ICs.
    """
    n = len(ic_arr)
    n_blocks = int(np.ceil(n / B))
    boot_means = np.empty(n_boot)

    for i in range(n_boot):
        starts = rng.integers(0, n, size=n_blocks)
        # Build sample from contiguous circular blocks
        indices = np.concatenate([
            np.arange(s, s + B) % n for s in starts
        ])[:n]
        boot_means[i] = ic_arr[indices].mean()

    return boot_means


def bootstrap_pvalue(boot_means: np.ndarray, observed: float) -> float:
    """
    Two-sided p-value using shift method (Fraser 1999):
      1. Shift bootstrap distribution to be centered at 0 (consistent with H0)
      2. p-value = P(|T*| >= |observed|) under shifted distribution
    """
    boot_null = boot_means - boot_means.mean()
    p = np.mean(np.abs(boot_null) >= np.abs(observed))
    return p


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--probas", type=str, default=str(DEFAULT_PROBAS))
    parser.add_argument("--n-boot", type=int, default=N_BOOT)
    args = parser.parse_args()

    n_boot = args.n_boot
    print(f"\nH70: BLOCK BOOTSTRAP P-VALUES")
    print(f"Block sizes: {BLOCK_SIZES} | Bootstrap resamples: {n_boot:,}")
    print(f"H0: true mean IC = 0  (no predictive signal)")

    df = pd.read_parquet(args.probas)
    df["time"] = pd.to_datetime(df["time"])
    df = df[(df["time"].dt.year >= START_YEAR) & (df["time"].dt.year <= END_YEAR)]
    print(f"  {len(df):,} rows | {df['ticker'].nunique()} tickers | {START_YEAR}-{END_YEAR}")

    print(f"\nComputing daily IC...")
    ic_df = compute_daily_ic(df)
    print(f"  {len(ic_df):,} trading days with IC | "
          f"mean IC = {ic_df['ic'].mean():+.4f}")

    # Per-year reference (standard t-test for context)
    print(f"\n{'='*72}")
    print(f"PER-YEAR IC — standard t-test (IID assumption, for reference)")
    print(f"{'='*72}")
    print(f"  {'year':>5}  {'IC':>8}  {'std':>7}  {'n_days':>7}  {'t_stat':>8}  {'p_ttest':>9}  {'sig'}")
    print("  " + "-"*60)

    for year, grp in ic_df.groupby("year"):
        ic_yr = grp["ic"].values
        if len(ic_yr) < 10:
            continue
        t_stat = ic_yr.mean() / (ic_yr.std() / np.sqrt(len(ic_yr)) + 1e-9)
        pval = ttest_1samp(ic_yr, 0).pvalue
        sig = "**" if pval < 0.01 else ("*" if pval < 0.05 else "")
        print(f"  {year:>5}  {ic_yr.mean():>+7.4f}  {ic_yr.std():>6.4f}  "
              f"{len(ic_yr):>7}  {t_stat:>+7.2f}  {pval:>8.4f}  {sig}")

    # Pooled block bootstrap
    ic_arr = ic_df["ic"].values   # chronological order
    true_mean = ic_arr.mean()
    rng = np.random.default_rng(42)

    print(f"\n{'='*72}")
    print(f"POOLED BLOCK BOOTSTRAP — {len(ic_arr):,} trading days")
    print(f"{'='*72}")
    print(f"  Observed mean IC: {true_mean:+.4f}")
    print(f"\n  {'B':>5}  {'mean_IC':>9}  {'boot_SE':>9}  "
          f"{'95%_CI':>22}  {'p_value':>9}  {'note'}")
    print("  " + "-"*75)

    for B in BLOCK_SIZES:
        boot = circular_block_bootstrap(ic_arr, B, n_boot, rng)
        p    = bootstrap_pvalue(boot, true_mean)
        se   = boot.std()
        ci_lo = np.percentile(boot, 2.5)
        ci_hi = np.percentile(boot, 97.5)
        note = "IID baseline" if B == 1 else f"B={B}d blocks"
        sig  = "***" if p < 0.001 else ("**" if p < 0.01 else ("*" if p < 0.05 else "n.s."))
        print(f"  {B:>5}  {true_mean:>+8.4f}  {se:>9.4f}  "
              f"[{ci_lo:>+8.4f}, {ci_hi:>+8.4f}]  {p:>8.4f} {sig}  {note}")

    # Year-by-year block bootstrap (each year independently)
    print(f"\n{'='*72}")
    print(f"YEAR-BY-YEAR BLOCK BOOTSTRAP (B=5, each year independently)")
    print(f"{'='*72}")
    print(f"  {'year':>5}  {'IC':>8}  {'p_iid':>9}  {'p_B5':>9}  {'verdict'}")
    print("  " + "-"*50)

    rng2 = np.random.default_rng(99)
    for year, grp in ic_df.groupby("year"):
        ic_yr = grp["ic"].values
        if len(ic_yr) < 20:
            continue
        p_iid = ttest_1samp(ic_yr, 0).pvalue
        boot5 = circular_block_bootstrap(ic_yr, B=5, n_boot=n_boot, rng=rng2)
        p_b5  = bootstrap_pvalue(boot5, ic_yr.mean())
        verdict = "sig" if p_b5 < 0.05 else "n.s."
        print(f"  {year:>5}  {ic_yr.mean():>+7.4f}  {p_iid:>8.4f}  {p_b5:>8.4f}  {verdict}")

    print(f"\n{'='*72}")
    print(f"INTERPRETATION")
    print(f"{'='*72}")
    print(f"  B=1 (IID): smallest SE, most liberal p-value. Ignores autocorrelation.")
    print(f"  B=5/10/20: wider CI, more conservative. Accounts for weekly/monthly structure.")
    print(f"  If B=20 p-value still <0.001: signal survives the strictest blocking assumption.")
    print(f"  Note: IC already aggregates 393 stocks per day, reducing cross-sectional noise.")
    print(f"  The block bootstrap addresses the remaining temporal autocorrelation.")


if __name__ == "__main__":
    main()
