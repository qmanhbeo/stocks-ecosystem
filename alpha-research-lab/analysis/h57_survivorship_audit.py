"""
H57: Survivorship Bias Audit.

Problem: Our 393 stocks are all *currently* listed. Stocks that were listed in
2015-2018 but delisted before 2025 are missing. Those could be systematic losers.

This script estimates the bias magnitude by comparing:
  - "Old cohort": stocks present in 2015 probas (existed since ≥2012)
  - "New cohort": stocks first appearing 2018+ (listed after ~2015)
  - "Full universe": all 393 stocks

If new-cohort stocks outperform old-cohort, survivorship bias is inflating results.
If old-cohort matches new-cohort, the improvement over H43 is genuine.

Usage:
    conda run -n stocks python analysis/h57_survivorship_audit.py
"""
import numpy as np
import pandas as pd
from pathlib import Path
from path_utils import data_path

PROBAS_PATH = data_path("features/xs_barrier_all_probas_hose_full.parquet")
VIX_PATH    = data_path("fx-commodities/fx_commodities_vix_1D.parquet")

TOP_N     = 5
MIN_PROBA = 0.55
# No VIX filter (consistent with H54)


def run_portfolio(df: pd.DataFrame, label: str):
    """Run the rank portfolio on a (possibly filtered) probas dataframe."""
    naive_rate = df["actual"].mean()

    per_year = []
    for year, grp in df.groupby("year"):
        day_correct = []
        for _, day in grp.groupby("time"):
            top = day.nlargest(TOP_N, "xs_proba")
            if top["xs_proba"].min() >= MIN_PROBA:
                day_correct.extend(top["actual"].tolist())
        if len(day_correct) < TOP_N:
            continue
        edge = np.mean(day_correct) - naive_rate
        n_trades = len(day_correct) // TOP_N
        per_year.append({"year": year, "edge": edge, "n_trades": n_trades,
                         "n_tickers": grp["ticker"].nunique()})

    if not per_year:
        print(f"  [{label}] No results.")
        return

    edges = [r["edge"] for r in per_year]
    sharpe = np.mean(edges) / np.std(edges) if np.std(edges) > 0 else float("nan")
    n_pos  = sum(1 for e in edges if e > 0)
    avg_tickers = np.mean([r["n_tickers"] for r in per_year])

    print(f"\n  --- {label} ---")
    print(f"  Tickers/yr (avg): {avg_tickers:.0f}")
    print(f"  Avg edge  : {np.mean(edges)*100:+.2f}%  Sharpe: {sharpe:.2f}  Pos: {n_pos}/{len(edges)}")
    print(f"  {'year':>6}  {'edge':>9}  {'trades':>7}  {'tickers':>8}")
    for r in per_year:
        print(f"  {r['year']:>6}  {r['edge']*100:>+8.2f}%  {r['n_trades']:>7}  {r['n_tickers']:>8}")


def main():
    print("Loading probas...")
    df = pd.read_parquet(PROBAS_PATH)
    df["time"] = pd.to_datetime(df["time"])

    # Identify cohorts: first year each ticker appears in the probas
    first_year = df.groupby("ticker")["year"].min()

    old_cohort  = set(first_year[first_year <= 2015].index)  # existed since at least 2012 training
    mid_cohort  = set(first_year[(first_year >= 2016) & (first_year <= 2018)].index)
    new_cohort  = set(first_year[first_year >= 2019].index)

    print(f"\nCohort breakdown (by first year appearing in probas):")
    print(f"  Old  (first year ≤2015, existed since ≥2012): {len(old_cohort):>4} tickers")
    print(f"  Mid  (first year 2016-2018):                  {len(mid_cohort):>4} tickers")
    print(f"  New  (first year ≥2019):                      {len(new_cohort):>4} tickers")
    print(f"  Total:                                        {len(first_year):>4} tickers")
    print(f"\nNote: 'first year' = first test year they appear in walk-forward probas")
    print(f"  Old cohort ≈ stocks that existed since ~2012 (needed 3 train years for 2015 test)")
    print(f"  These are most similar to H43's original 52 stocks")

    print(f"\n{'='*70}")
    print(f"PORTFOLIO COMPARISON — Top-{TOP_N}, min_proba={MIN_PROBA}, NO VIX filter")
    print(f"{'='*70}")

    # Full universe
    run_portfolio(df, f"ALL {len(first_year)} tickers (H54 baseline)")

    # Old cohort only (most similar to H43, least survivorship bias)
    run_portfolio(df[df["ticker"].isin(old_cohort)], f"OLD cohort ({len(old_cohort)} tickers, existed ≥2012)")

    # Mid cohort only
    if mid_cohort:
        run_portfolio(df[df["ticker"].isin(mid_cohort)], f"MID cohort ({len(mid_cohort)} tickers, listed 2013-2015)")

    # New cohort only
    if new_cohort:
        run_portfolio(df[df["ticker"].isin(new_cohort)], f"NEW cohort ({len(new_cohort)} tickers, listed 2016+)")

    print(f"\n{'='*70}")
    print(f"INTERPRETATION:")
    print(f"  If old_cohort edge ≈ full edge → expansion benefit is genuine signal")
    print(f"  If new_cohort edge >> old_cohort → survivorship bias inflating new stocks")
    print(f"  H43 baseline (52 stocks): +13.75% edge, Sharpe 4.58")
    print(f"  Old cohort should approximate H43 if signal is consistent")


if __name__ == "__main__":
    main()
