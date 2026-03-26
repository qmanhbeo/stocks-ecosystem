"""
H23: Multi-stock portfolio analysis using all-ticker XS barrier probabilities.

Loads the parquet saved by:
    python cross_sectional_wf.py --barrier-pct 0.01 --threshold 0.05 \
        --save-all-probas data/features/xs_barrier_all_probas.parquet

Then for each ticker:
  - Computes annual confident days, accuracy, edge vs naive
  - Ranks tickers by avg_edge across years (only years with >= 5 conf trades)
  - Identifies top-N stocks for a portfolio approach

Usage:
    conda run -n stocks python analysis/h23_portfolio_analysis.py
    conda run -n stocks python analysis/h23_portfolio_analysis.py \
        --probas data/features/xs_barrier_all_probas.parquet \
        --threshold 0.05 --top-n 5
"""
import argparse
import numpy as np
import pandas as pd
from scipy.stats import binomtest
from pathlib import Path


def analyze_ticker(df_ticker: pd.DataFrame, threshold: float) -> dict:
    """Compute per-year signal stats for a single ticker."""
    per_year = []
    for year, grp in df_ticker.groupby("year"):
        actual = grp["actual"].values
        probas = grp["xs_proba"].values
        naive  = actual.mean()
        conf   = np.abs(probas - 0.5) > threshold
        n_conf = conf.sum()
        if n_conf < 5:
            continue
        preds_conf  = (probas[conf] > 0.5).astype(int)
        actual_conf = actual[conf]
        acc  = (preds_conf == actual_conf).mean()
        edge = acc - naive
        pval = binomtest(int((preds_conf == actual_conf).sum()), n_conf, naive).pvalue
        per_year.append({"year": year, "n_conf": n_conf, "acc": acc, "edge": edge, "pval": pval})
    return per_year


def run(probas_path: str, threshold: float, top_n: int, min_years: int):
    df = pd.read_parquet(probas_path)
    df["time"] = pd.to_datetime(df["time"])
    print(f"\nLoaded {len(df):,} rows, {df['ticker'].nunique()} tickers, "
          f"{df['year'].nunique()} years ({df['year'].min()}–{df['year'].max()})")
    print(f"Threshold: |prob-0.5| > {threshold} (min conf {0.5+threshold:.2f})")
    print(f"\n{'='*80}")
    print(f"PER-TICKER SIGNAL QUALITY (min {min_years} valid years with n_conf >= 5)")
    print(f"{'='*80}")
    print(f"  {'ticker':>7}  {'n_yrs':>6}  {'avg_edge':>9}  {'std_edge':>9}  "
          f"{'n_sig':>6}  {'sharpe':>7}  {'years_summary'}")
    print("  " + "-" * 75)

    ticker_stats = []
    for ticker, grp in df.groupby("ticker"):
        per_year = analyze_ticker(grp, threshold)
        if len(per_year) < min_years:
            continue
        edges = [r["edge"] for r in per_year]
        sigs  = sum(1 for r in per_year if r["pval"] < 0.05)
        avg_e = np.mean(edges)
        std_e = np.std(edges) if len(edges) > 1 else float("nan")
        sharpe = avg_e / std_e if std_e > 0 else float("nan")
        yr_sum = "  ".join(
            f"{r['year']}:{r['edge']*100:+.1f}%{'*' if r['pval']<0.05 else ''}"
            for r in per_year
        )
        ticker_stats.append({
            "ticker": ticker, "n_years": len(per_year),
            "avg_edge": avg_e, "std_edge": std_e,
            "n_sig": sigs, "sharpe": sharpe, "per_year": per_year,
        })
        print(f"  {ticker:>7}  {len(per_year):>6}  {avg_e*100:>+8.2f}%  "
              f"{std_e*100:>8.2f}%  {sigs:>6}  {sharpe:>7.2f}  {yr_sum}")

    if not ticker_stats:
        print("No tickers with enough valid years.")
        return

    # Rank by avg_edge
    ticker_stats.sort(key=lambda x: x["avg_edge"], reverse=True)
    top = ticker_stats[:top_n]

    print(f"\n{'='*80}")
    print(f"TOP {top_n} TICKERS BY AVG EDGE")
    print(f"{'='*80}")
    for i, t in enumerate(top, 1):
        print(f"  #{i}: {t['ticker']:>6}  avg_edge={t['avg_edge']*100:+.2f}%  "
              f"Sharpe={t['sharpe']:.2f}  n_sig={t['n_sig']}/{t['n_years']} yrs")

    # Portfolio simulation: trade across top-N stocks simultaneously
    print(f"\n{'='*80}")
    print(f"PORTFOLIO: Equal-weight across top-{top_n} stocks (per-trade edge)")
    print(f"{'='*80}")
    top_tickers = [t["ticker"] for t in top]
    df_top = df[df["ticker"].isin(top_tickers)].copy()
    conf_mask = np.abs(df_top["xs_proba"].values - 0.5) > threshold
    df_conf = df_top[conf_mask].copy()
    df_conf["pred"] = (df_conf["xs_proba"] > 0.5).astype(int)
    df_conf["correct"] = (df_conf["pred"] == df_conf["actual"]).astype(int)

    print(f"\n  {'year':>5}  {'n_trades':>9}  {'tickers':>8}  {'acc':>7}  {'edge':>7}")
    print("  " + "-" * 50)
    port_edges = []
    for year, grp in df_conf.groupby("year"):
        if len(grp) < 5:
            continue
        naive_y = grp["actual"].mean()
        acc_y   = grp["correct"].mean()
        edge_y  = acc_y - naive_y
        n_ticks = grp["ticker"].nunique()
        pval_y  = binomtest(int(grp["correct"].sum()), len(grp), naive_y).pvalue
        sig = "*" if pval_y < 0.05 else " "
        port_edges.append(edge_y)
        print(f"  {year:>5}  {len(grp):>9}  {n_ticks:>8}  "
              f"{acc_y*100:>6.1f}%  {edge_y*100:>+6.2f}%{sig}")

    if port_edges:
        print(f"\n  Portfolio avg edge : {np.mean(port_edges)*100:+.2f}%")
        print(f"  Portfolio std edge : {np.std(port_edges)*100:.2f}%")
        sharpe_p = np.mean(port_edges) / np.std(port_edges) if np.std(port_edges) > 0 else float("nan")
        print(f"  Portfolio Sharpe   : {sharpe_p:.2f}")

    print(f"\n  FPT for comparison (same threshold):")
    fpt_stats = next((t for t in ticker_stats if t["ticker"] == "FPT"), None)
    if fpt_stats:
        print(f"    avg_edge={fpt_stats['avg_edge']*100:+.2f}%  "
              f"Sharpe={fpt_stats['sharpe']:.2f}  n_sig={fpt_stats['n_sig']}/{fpt_stats['n_years']} yrs")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--probas", default="data/features/xs_barrier_all_probas.parquet",
                        help="Path to all-ticker proba parquet (from --save-all-probas)")
    parser.add_argument("--threshold", type=float, default=0.05,
                        help="Confidence threshold: |prob-0.5| > threshold (default 0.05 = min 55%%)")
    parser.add_argument("--top-n", type=int, default=5,
                        help="Number of top tickers to include in portfolio (default 5)")
    parser.add_argument("--min-years", type=int, default=3,
                        help="Minimum years with n_conf>=5 for a ticker to be ranked (default 3)")
    args = parser.parse_args()
    run(args.probas, args.threshold, args.top_n, args.min_years)
