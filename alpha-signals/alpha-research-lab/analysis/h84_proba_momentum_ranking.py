"""
H84: Probability Momentum + Reversal Ranking (Zaremba 2020 / Han 2021)

Literature grounding:
  Zaremba 2020 "Opposites Attract" — combining short-term alpha momentum
  (past-winner alphas keep winning) with long-term alpha reversal (persistent
  winners mean-revert) generates 1.16–1.44% monthly alpha in cross-sectional tests.

  Han 2021 "Bimodal Momentum" — filter out stocks with high model confidence
  variance (bimodal/unstable predictions) to avoid crash risk.

Implementation:
  rank_score = xs_proba + alpha * (proba_ma5 - proba_ma20)

  where alpha ∈ {0.0, 0.3, 0.5, 0.7, 1.0}
  alpha=0.0 reproduces H54 baseline exactly (sanity check).

  Han variant: pre-filter day to stocks with proba_std5 <= 0.15

Runs on existing H54 probas — no model retrain needed.

Usage:
    PYTHONIOENCODING=utf-8 conda run -n stocks python analysis/h84_proba_momentum_ranking.py \\
        --probas data/features/xs_barrier_all_probas_hose_full.parquet --no-vix-filter
"""
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.stats import spearmanr, ttest_1samp

ALL_PROBAS = Path("data/features/xs_barrier_all_probas_hose_full.parquet")
VIX_PATH   = Path("data/fx-commodities/fx_commodities_vix_1D.parquet")

TOP_N     = 5
MIN_PROBA = 0.55
VIX_MIN   = 0.0
VIX_MAX   = 999.0
START_YEAR = 2015

# Zaremba alpha values to sweep
ALPHA_VALUES = [0.0, 0.3, 0.5, 0.7, 1.0]
# Han 2021 proba-std threshold (bimodal crash guard)
HAN_STD_THRESH = 0.15
# Rolling windows for momentum signal
SHORT_WINDOW = 5
LONG_WINDOW  = 20


def load_data(probas_path: Path) -> pd.DataFrame:
    df = pd.read_parquet(probas_path)
    df["time"] = pd.to_datetime(df["time"])

    vix = pd.read_parquet(VIX_PATH)[["time", "close"]].rename(columns={"close": "vix"})
    vix["time"] = pd.to_datetime(vix["time"])
    df = df.merge(vix, on="time", how="left")
    df["vix"] = df["vix"].ffill()
    return df


def add_proba_momentum_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Per-ticker rolling stats on xs_proba (sorted by time within each ticker).
    Falls back to xs_proba when rolling window has NaN (start of each year / ticker).
    """
    df = df.sort_values(["ticker", "time"]).copy()

    grp = df.groupby("ticker")["xs_proba"]
    df["proba_ma5"]  = grp.transform(lambda x: x.rolling(SHORT_WINDOW, min_periods=1).mean())
    df["proba_ma20"] = grp.transform(lambda x: x.rolling(LONG_WINDOW,  min_periods=1).mean())
    df["proba_std5"] = grp.transform(lambda x: x.rolling(SHORT_WINDOW, min_periods=2).std().fillna(0))

    # Momentum signal: short-term rising vs long-term average
    df["momentum_signal"] = df["proba_ma5"] - df["proba_ma20"]
    return df


def run_alpha_sweep(df: pd.DataFrame, use_han_filter: bool = False) -> dict:
    """
    Sweep alpha values and report avg_edge + Sharpe for each.
    Returns dict: {alpha: {"avg_edge": ..., "sharpe": ..., "years": [...]}}
    """
    results = {}

    for alpha in ALPHA_VALUES:
        per_year = []

        for year, grp in df.groupby("year"):
            if year < START_YEAR:
                continue
            naive_rate = grp["actual"].mean()
            day_edges  = []

            for date, day in grp.groupby("time"):
                if len(day) < 5:
                    continue

                # Han 2021: filter out bimodal/unstable stocks
                if use_han_filter:
                    day = day[day["proba_std5"] <= HAN_STD_THRESH]
                    if len(day) < 5:
                        continue

                # Compute rank score
                if alpha == 0.0:
                    day = day.copy()
                    day["rank_score"] = day["xs_proba"]
                else:
                    day = day.copy()
                    day["rank_score"] = day["xs_proba"] + alpha * day["momentum_signal"]

                # MIN_PROBA gate on original xs_proba (not rank_score)
                top = day.nlargest(TOP_N, "rank_score")
                if top["xs_proba"].min() >= MIN_PROBA:
                    day_edges.append(top["actual"].mean() - naive_rate)

            if len(day_edges) >= 5:
                per_year.append(np.mean(day_edges))

        if per_year:
            avg = np.mean(per_year)
            std = np.std(per_year)
            sharpe = avg / std if std > 0 else float("nan")
            results[alpha] = {"avg_edge": avg, "sharpe": sharpe, "years": per_year, "n_years": len(per_year)}
        else:
            results[alpha] = {"avg_edge": float("nan"), "sharpe": float("nan"), "years": [], "n_years": 0}

    return results


def print_sweep_results(results: dict, label: str):
    print(f"\n{'='*70}")
    print(f"H84 PROBA MOMENTUM RANKING — {label}")
    print(f"TOP_N={TOP_N} | MIN_PROBA={MIN_PROBA} | short={SHORT_WINDOW}d, long={LONG_WINDOW}d")
    print(f"  {'alpha':>6}  {'avg_edge':>10}  {'sharpe':>8}  {'n_yrs':>6}  {'vs_H54':>8}")
    print("  " + "-" * 48)

    baseline_edge = results.get(0.0, {}).get("avg_edge", float("nan"))
    for alpha in ALPHA_VALUES:
        r = results[alpha]
        if np.isnan(r["avg_edge"]):
            print(f"  {alpha:>6.1f}  {'N/A':>10}  {'N/A':>8}  {r['n_years']:>6}")
            continue
        diff = (r["avg_edge"] - baseline_edge) * 100 if not np.isnan(baseline_edge) else float("nan")
        sign = "+" if diff >= 0 else ""
        print(f"  {alpha:>6.1f}  {r['avg_edge']*100:>+9.2f}%  {r['sharpe']:>8.2f}"
              f"  {r['n_years']:>6}  {sign}{diff:.2f}%")

    # Per-year detail for best alpha
    best_alpha = max(ALPHA_VALUES, key=lambda a: results[a]["avg_edge"]
                     if not np.isnan(results[a]["avg_edge"]) else -999)
    if best_alpha != 0.0:
        print(f"\n  Best alpha={best_alpha} — per-year breakdown:")
        print(f"  {'year':>5}  {'edge':>9}")
        for i, (year, edge) in enumerate(zip(
            range(START_YEAR, START_YEAR + len(results[best_alpha]["years"])),
            results[best_alpha]["years"]
        )):
            print(f"  {START_YEAR + i:>5}  {edge*100:>+8.2f}%")


def quintile_ic_by_alpha(df: pd.DataFrame):
    """Quick IC check: does adding momentum signal change IC vs just xs_proba?"""
    print(f"\n{'='*70}")
    print("IC CHECK — rank_score vs actual, by alpha")
    print(f"  {'alpha':>6}  {'avg_IC':>9}  {'sig_years':>10}")
    print("  " + "-" * 30)

    for alpha in [0.0, 0.5, 1.0]:
        ics = []
        for year, grp in df.groupby("year"):
            if year < START_YEAR:
                continue
            if alpha == 0.0:
                score_col = "xs_proba"
            else:
                grp = grp.copy()
                grp["rank_score"] = grp["xs_proba"] + alpha * grp["momentum_signal"]
                score_col = "rank_score"

            day_ics = []
            for date, day in grp.groupby("time"):
                if len(day) < 10:
                    continue
                ic, _ = spearmanr(day[score_col], day["actual"])
                if not np.isnan(ic):
                    day_ics.append(ic)
            if day_ics:
                ics.append(np.mean(day_ics))

        if ics:
            avg_ic = np.mean(ics)
            sig = sum(1 for ic in ics if abs(ic) > 0.02)
            print(f"  {alpha:>6.1f}  {avg_ic:>+8.4f}  {sig}/{len(ics)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="H84: Probability momentum ranking")
    parser.add_argument("--probas", type=str, default=str(ALL_PROBAS))
    parser.add_argument("--no-vix-filter", action="store_true",
                        help="Disable VIX band (required for H54 comparison)")
    parser.add_argument("--top-n", type=int, default=TOP_N)
    parser.add_argument("--min-proba", type=float, default=MIN_PROBA)
    parser.add_argument("--short-window", type=int, default=SHORT_WINDOW,
                        help="Short MA window for momentum signal (default 5)")
    parser.add_argument("--long-window", type=int, default=LONG_WINDOW,
                        help="Long MA window for momentum signal (default 20)")
    args = parser.parse_args()

    if args.no_vix_filter:
        VIX_MIN, VIX_MAX = 0.0, 999.0
        print("[H84] VIX filter DISABLED")
    TOP_N     = args.top_n
    MIN_PROBA = args.min_proba
    SHORT_WINDOW = args.short_window
    LONG_WINDOW  = args.long_window

    print(f"Loading probas from {args.probas}...")
    df = load_data(Path(args.probas))
    print(f"  {len(df):,} rows | {df['ticker'].nunique()} tickers | years {df['year'].min()}-{df['year'].max()}")

    print("Computing per-ticker rolling proba momentum features...")
    df = add_proba_momentum_features(df)

    # --- Standard Zaremba sweep ---
    results_std = run_alpha_sweep(df, use_han_filter=False)
    print_sweep_results(results_std, "Zaremba 2020 variant (no stability filter)")

    # --- Han 2021 bimodal filter variant ---
    results_han = run_alpha_sweep(df, use_han_filter=True)
    print_sweep_results(results_han, f"Han 2021 variant (proba_std5 <= {HAN_STD_THRESH})")

    # --- IC check ---
    quintile_ic_by_alpha(df)

    # --- Verdict ---
    base_edge = results_std[0.0]["avg_edge"]
    best_alpha_std = max(ALPHA_VALUES, key=lambda a: results_std[a]["avg_edge"]
                         if not np.isnan(results_std[a]["avg_edge"]) else -999)
    best_edge_std = results_std[best_alpha_std]["avg_edge"]
    best_sharpe_std = results_std[best_alpha_std]["sharpe"]

    print(f"\n{'='*70}")
    print(f"VERDICT")
    print(f"  H54 baseline (alpha=0.0): {base_edge*100:+.2f}% avg edge, Sharpe {results_std[0.0]['sharpe']:.2f}")
    print(f"  Best Zaremba alpha={best_alpha_std}: {best_edge_std*100:+.2f}% avg edge, Sharpe {best_sharpe_std:.2f}")

    if best_alpha_std != 0.0 and best_edge_std > base_edge + 0.002:
        print(f"  PASS — proba momentum improves edge by {(best_edge_std-base_edge)*100:+.2f}%")
    elif best_alpha_std != 0.0 and best_edge_std > base_edge - 0.002:
        print(f"  NEUTRAL — proba momentum within ±0.2% of baseline")
    else:
        print(f"  FAIL — proba momentum does not improve edge; concept does not transfer to VN stocks")
