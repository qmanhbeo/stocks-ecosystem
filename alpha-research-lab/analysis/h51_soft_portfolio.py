"""
H51: Soft (parameterless) portfolio using softmax weights over all XS probas.

Option B from Session 16 plan: replace 3 contaminated parameters
    (TOP_N=5, MIN_PROBA=0.55, VIX_MAX=30)
with a single parameterless rule:
    weights = softmax(xs_proba) over all stocks each day
    always invested, weighted by model confidence — no thresholds, no cutoffs

If H51 ≈ H43: the parameters were pure noise (H43 is safe to report as clean).
If H51 < H43: the parameters add real value → need Option A (nested walk-forward search).

Usage:
    conda run -n stocks python analysis/h51_soft_portfolio.py
    conda run -n stocks python analysis/h51_soft_portfolio.py --probas data/features/xs_barrier_vix_feature_all_probas.parquet
    conda run -n stocks python analysis/h51_soft_portfolio.py --temperature 2.0
"""
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from path_utils import data_path
from scipy.special import softmax as scipy_softmax

ALL_PROBAS = data_path("features/xs_barrier_all_probas.parquet")
VIX_PATH   = data_path("fx-commodities/fx_commodities_vix_1D.parquet")
START_YEAR = 2015


def load_data(probas_path: Path = ALL_PROBAS) -> pd.DataFrame:
    df = pd.read_parquet(probas_path)
    df["time"] = pd.to_datetime(df["time"])
    vix = pd.read_parquet(VIX_PATH)[["time", "close"]].rename(columns={"close": "vix"})
    vix["time"] = pd.to_datetime(vix["time"])
    df = df.merge(vix, on="time", how="left")
    df["vix"] = df["vix"].ffill()
    return df


def run_soft_portfolio(df: pd.DataFrame, temperature: float = 1.0,
                       vix_filter: bool = True, vix_min: float = 15.0, vix_max: float = 30.0):
    """
    Each day: compute softmax weights over all stocks' xs_proba.
    Weighted accuracy = sum(w_i * actual_i) for each stock.
    Edge = weighted_accuracy - naive_rate.

    temperature: softmax temperature. 1.0 = natural (default).
                 Higher T → flatter weights (more diversified).
                 Lower T → more concentrated on top stocks.
    vix_filter: if True, only count days in VIX band (for comparison with H43).
                if False, always invested (fully parameterless).
    """
    label = f"SOFT PORTFOLIO (temperature={temperature:.1f}"
    if vix_filter:
        label += f", VIX[{vix_min},{vix_max}])"
    else:
        label += ", no VIX filter)"

    print("\n" + "=" * 70)
    print(label)
    print(f"  {'year':>5}  {'n_days':>7}  {'wtd_acc':>8}  {'naive':>8}  {'edge':>8}  {'pval':>8}")
    print("  " + "-" * 55)

    per_year = []
    for year, grp in df.groupby("year"):
        if year < START_YEAR:
            continue
        naive_rate = grp["actual"].mean()
        daily_wtd_accs = []

        for date, day in grp.groupby("time"):
            if vix_filter:
                vix_val = day["vix"].iloc[0]
                if not (vix_min <= vix_val <= vix_max):
                    continue

            if len(day) < 5:
                continue

            # Softmax weights over xs_proba
            probas = day["xs_proba"].values
            weights = scipy_softmax(probas / temperature)
            wtd_correct = (weights * day["actual"].values).sum()
            daily_wtd_accs.append(wtd_correct)

        if len(daily_wtd_accs) < 3:
            print(f"  {year:>5}  {'N/A':>7}  {'N/A':>8}  {naive_rate*100:>7.1f}%  {'N/A':>8}  {'N/A':>8}")
            continue

        from scipy.stats import ttest_1samp
        avg_wtd_acc = np.mean(daily_wtd_accs)
        edge = avg_wtd_acc - naive_rate
        pval = ttest_1samp(daily_wtd_accs, naive_rate).pvalue
        sig = "*" if pval < 0.05 else " "

        print(f"  {year:>5}  {len(daily_wtd_accs):>7}  {avg_wtd_acc*100:>7.2f}%  "
              f"{naive_rate*100:>7.1f}%  {edge*100:>+7.2f}%  {pval:>7.4f}{sig}")
        per_year.append({"year": year, "edge": edge, "n_days": len(daily_wtd_accs)})

    if not per_year:
        print("  No data.")
        return

    edges = [r["edge"] for r in per_year]
    sharpe = np.mean(edges) / np.std(edges) if np.std(edges) > 0 else float("nan")
    n_pos = sum(1 for e in edges if e > 0)
    print(f"\n  Avg edge : {np.mean(edges)*100:+.2f}%  (std: {np.std(edges)*100:.2f}%)")
    print(f"  Sharpe   : {sharpe:.2f}")
    print(f"  Positive : {n_pos}/{len(edges)} years")
    print(f"  Trades/yr: {np.mean([r['n_days'] for r in per_year]):.1f} days")
    return per_year


def run_temperature_sweep(df: pd.DataFrame, vix_filter: bool = True):
    """Sweep temperature values to understand sensitivity."""
    print("\n" + "=" * 70)
    vix_label = "VIX[15,30]" if vix_filter else "no VIX filter"
    print(f"TEMPERATURE SWEEP ({vix_label})")
    print(f"  {'temp':>6}  {'avg_edge':>9}  {'sharpe':>8}  {'pos_yrs':>8}  {'days/yr':>8}")
    print("  " + "-" * 50)

    for temp in [0.1, 0.3, 0.5, 1.0, 2.0, 5.0]:
        results = []
        for year, grp in df.groupby("year"):
            if year < START_YEAR:
                continue
            naive_rate = grp["actual"].mean()
            daily = []
            for date, day in grp.groupby("time"):
                if vix_filter:
                    vix_val = day["vix"].iloc[0]
                    if not (15.0 <= vix_val <= 30.0):
                        continue
                if len(day) < 5:
                    continue
                weights = scipy_softmax(day["xs_proba"].values / temp)
                daily.append((weights * day["actual"].values).sum())
            if len(daily) >= 3:
                edge = np.mean(daily) - naive_rate
                results.append({"edge": edge, "n": len(daily)})

        if results:
            edges = [r["edge"] for r in results]
            sharpe = np.mean(edges) / np.std(edges) if np.std(edges) > 0 else float("nan")
            n_pos = sum(1 for e in edges if e > 0)
            days = np.mean([r["n"] for r in results])
            print(f"  {temp:>6.1f}  {np.mean(edges)*100:>+8.2f}%  {sharpe:>8.2f}  "
                  f"{n_pos:>4}/{len(results):>2}   {days:>7.1f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--probas", type=str, default=str(ALL_PROBAS),
                        help="Path to all-ticker probas parquet")
    parser.add_argument("--temperature", type=float, default=1.0,
                        help="Softmax temperature (default: 1.0). Lower=more concentrated.")
    parser.add_argument("--no-vix-filter", action="store_true",
                        help="Disable VIX band filter (fully parameterless)")
    args = parser.parse_args()

    print(f"Loading probas from {args.probas}...")
    df = load_data(Path(args.probas))
    print(f"  {len(df):,} rows | {df['ticker'].nunique()} tickers | years {df['year'].min()}-{df['year'].max()}")

    # Main comparison: soft portfolio vs H43 baseline
    print("\n--- H43 BASELINE REFERENCE: +13.75% avg edge, Sharpe 4.58, 11/11 years ---")

    # 1. Fully parameterless (no VIX filter, temperature=1)
    run_soft_portfolio(df, temperature=1.0, vix_filter=False)

    # 2. VIX-filtered (still uses VIX band, but removes TOP_N + MIN_PROBA)
    run_soft_portfolio(df, temperature=1.0, vix_filter=True)

    # 3. Temperature sweep (VIX-filtered, to understand sensitivity)
    run_temperature_sweep(df, vix_filter=True)

    # 4. Temperature sweep (no VIX filter, fully parameterless)
    run_temperature_sweep(df, vix_filter=False)
