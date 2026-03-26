"""
H81: IC Stability Filter — Does filtering to historically-predictable tickers improve the portfolio?

Hypothesis: tickers where the XS model has shown consistent predictive IC in prior years
may be more reliably predictable going forward. Filter the daily universe to only those
tickers with IC > 0 in >= 2 of the 3 prior years before selecting top-N.

Method:
  - For each test year Y, use train years [Y-3, Y-2, Y-1]
  - Compute per-ticker annual IC (Spearman of xs_proba vs actual) for each of those 3 years
  - On test year Y, restrict daily universe to tickers where IC > 0 in >= 2/3 prior years
  - Run same top-5 / min-proba=0.55 / no-VIX-filter evaluation
  - Compare avg_edge and Sharpe to H54 baseline

Baseline (H54): avg_edge = +25.52%, Sharpe = 9.17, 11/11 years positive.

Usage:
    conda run -n stocks python analysis/h81_ic_stability_filter.py
"""
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.stats import spearmanr

DEFAULT_PROBAS = Path("data/features/xs_barrier_all_probas_hose_full.parquet")
TOP_N      = 5
MIN_PROBA  = 0.55
START_YEAR = 2015
IC_WINDOW  = 3       # look back 3 prior years
IC_MIN_POSITIVE = 2  # ticker must have IC > 0 in >= this many of the prior years


def compute_annual_ic(df: pd.DataFrame) -> dict:
    """
    Compute per-ticker per-year Spearman IC (xs_proba vs actual).
    Returns dict: {(year, ticker): ic_value}
    """
    results = {}
    for (year, ticker), grp in df.groupby(["year", "ticker"]):
        sub = grp[["xs_proba", "actual"]].dropna()
        if len(sub) < 10:
            results[(year, ticker)] = float("nan")
            continue
        ic, _ = spearmanr(sub["xs_proba"], sub["actual"])
        results[(year, ticker)] = ic
    return results


def run_filtered_portfolio(df: pd.DataFrame, ic_lookup: dict, min_positive: int = IC_MIN_POSITIVE):
    """
    Run top-N portfolio with IC stability filter on universe.
    """
    print(f"\n{'='*70}")
    print(f"H81: IC STABILITY FILTER — IC > 0 in >= {min_positive}/{IC_WINDOW} prior years")
    print(f"Filter: no VIX | min_proba={MIN_PROBA} | TOP_N={TOP_N}")
    print(f"  {'year':>5}  {'n_tickers_avg':>13}  {'n_days':>7}  {'edge':>9}  {'vs_H54':>8}")
    print("  " + "-" * 55)

    per_year = []
    years = sorted(df["year"].unique())
    for test_year in years:
        if test_year < START_YEAR:
            continue
        prior_years = [test_year - i for i in range(1, IC_WINDOW + 1)]
        if not all(y in df["year"].values for y in prior_years[:1]):
            continue  # skip if no prior year data at all

        # Determine which tickers pass the IC stability filter
        stable_tickers = set()
        all_tickers = df[df["year"] == test_year]["ticker"].unique()
        for t in all_tickers:
            pos_count = sum(
                1 for py in prior_years
                if ic_lookup.get((py, t), float("nan")) > 0
            )
            if pos_count >= min_positive:
                stable_tickers.add(t)

        test_grp = df[df["year"] == test_year]
        naive_rate = test_grp["actual"].mean()

        day_edges = []
        avg_n_tickers = []
        for date, day in test_grp.groupby("time"):
            day_filtered = day[day["ticker"].isin(stable_tickers)]
            avg_n_tickers.append(len(day_filtered))
            if len(day_filtered) < TOP_N:
                continue
            top = day_filtered.nlargest(TOP_N, "xs_proba")
            if top["xs_proba"].min() >= MIN_PROBA:
                day_edges.append(top["actual"].mean() - naive_rate)

        if len(day_edges) < 5:
            print(f"  {test_year:>5}  {'N/A':>13}  {'<5':>7}  {'N/A':>9}  {'N/A':>8}")
            continue

        avg_edge = np.mean(day_edges)
        vs_h54 = avg_edge * 100 - 25.52
        avg_n = np.mean(avg_n_tickers) if avg_n_tickers else 0
        print(f"  {test_year:>5}  {avg_n:>13.0f}  {len(day_edges):>7}  "
              f"{avg_edge*100:>+8.2f}%  {vs_h54:>+7.2f}%")
        per_year.append({
            "year": test_year,
            "edge": avg_edge,
            "n_tickers": avg_n,
            "n_days": len(day_edges),
        })

    if per_year:
        edges = [r["edge"] for r in per_year]
        avg_edge = np.mean(edges)
        sharpe = avg_edge / np.std(edges) if np.std(edges) > 0 else float("nan")
        n_pos = sum(1 for e in edges if e > 0)
        print(f"\n  Avg edge : {avg_edge*100:+.2f}%  (std: {np.std(edges)*100:.2f}%)")
        print(f"  Sharpe   : {sharpe:.2f}")
        print(f"  Pos years: {n_pos}/{len(per_year)}")
        print(f"  H54 base : +25.52%  Sharpe 9.17  11/11 years")
        verdict = "PASS" if avg_edge * 100 > 25.52 or (avg_edge * 100 > 23.52 and sharpe > 9.17) else "FAIL"
        print(f"  Verdict  : {verdict}")
    return per_year


def run_unfiltered_baseline(df: pd.DataFrame):
    """H54 baseline on the same data for direct comparison."""
    print(f"\n{'='*70}")
    print(f"BASELINE (H54, no IC filter): TOP_N={TOP_N} | min_proba={MIN_PROBA} | no VIX")
    per_year = []
    for test_year, grp in df.groupby("year"):
        if test_year < START_YEAR:
            continue
        naive_rate = grp["actual"].mean()
        day_edges = []
        for date, day in grp.groupby("time"):
            top = day.nlargest(TOP_N, "xs_proba")
            if top["xs_proba"].min() >= MIN_PROBA:
                day_edges.append(top["actual"].mean() - naive_rate)
        if len(day_edges) < 5:
            continue
        per_year.append({"year": test_year, "edge": np.mean(day_edges)})
    if per_year:
        edges = [r["edge"] for r in per_year]
        sharpe = np.mean(edges) / np.std(edges) if np.std(edges) > 0 else float("nan")
        print(f"  Baseline avg_edge={np.mean(edges)*100:+.2f}%  Sharpe={sharpe:.2f}  "
              f"pos={sum(1 for e in edges if e > 0)}/{len(edges)}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--probas", type=str, default=str(DEFAULT_PROBAS))
    args = parser.parse_args()

    probas_path = Path(args.probas)
    print(f"Loading probas from {probas_path}...")
    df = pd.read_parquet(probas_path)
    df["time"] = pd.to_datetime(df["time"])
    print(f"  {len(df):,} rows | {df['ticker'].nunique()} tickers | years {df['year'].min()}-{df['year'].max()}")

    print("\nComputing annual per-ticker IC...")
    ic_lookup = compute_annual_ic(df)
    ic_vals = [v for v in ic_lookup.values() if not np.isnan(v)]
    print(f"  {len(ic_lookup)} (year, ticker) pairs | IC mean={np.mean(ic_vals):+.4f} "
          f"| frac IC>0: {sum(1 for v in ic_vals if v > 0)/len(ic_vals):.1%}")

    run_unfiltered_baseline(df)

    # Test different min_positive thresholds
    for min_pos in [1, 2, 3]:
        run_filtered_portfolio(df, ic_lookup, min_positive=min_pos)
