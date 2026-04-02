"""
H71: Probability Calibration Check.

Are the model's probabilities reliable as position weights?
  - If proba=0.65 → stock actually outperforms ~65% of the time: well calibrated.
  - If proba=0.65 → stock actually outperforms ~55% of the time: overconfident.
  - Overconfidence means square weighting (H65/H69) over-concentrates in the
    most uncertain picks. Underconfidence means under-concentrating.

Tests:
  1. Reliability diagram: expected proba vs actual outperformance rate per bucket
  2. Brier score (lower = better): mean squared error of proba vs binary outcome
  3. Brier skill score: improvement over naive base-rate prediction
  4. Year-by-year calibration: does calibration degrade over time?
  5. Traded-universe calibration: specifically for proba >= 0.55 (what we trade)

Brier score decomposition:
  Brier = reliability - resolution + uncertainty
  Lower reliability (closer to calibration curve) → better
  Higher resolution (spread of predicted probas) → better

Usage:
    conda run -n stocks python analysis/h71_calibration.py
"""
import numpy as np
import pandas as pd
from pathlib import Path
from path_utils import data_path

DEFAULT_PROBAS = data_path("features/xs_barrier_all_probas_hose_full.parquet")

START_YEAR = 2015
END_YEAR   = 2025
MIN_PROBA  = 0.55   # trading threshold

# Reliability diagram bins: probability buckets
BINS = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 1.01]


def brier_components(p: np.ndarray, y: np.ndarray) -> dict:
    """
    Murphy (1973) Brier score decomposition.
    Returns reliability, resolution, uncertainty, and overall Brier score.
    """
    brier = np.mean((p - y) ** 2)
    base_rate = y.mean()
    brier_clim = base_rate * (1 - base_rate)   # uncertainty term

    # Discretize into bins for reliability/resolution
    bin_means, bin_rates, bin_ns = [], [], []
    for i in range(len(BINS) - 1):
        mask = (p >= BINS[i]) & (p < BINS[i+1])
        if mask.sum() >= 5:
            bin_means.append(p[mask].mean())
            bin_rates.append(y[mask].mean())
            bin_ns.append(mask.sum())

    if bin_ns:
        N = len(p)
        reliability = sum(n * (pm - fr)**2 for pm, fr, n
                         in zip(bin_means, bin_rates, bin_ns)) / N
        resolution  = sum(n * (fr - base_rate)**2 for fr, n
                         in zip(bin_rates, bin_ns)) / N
    else:
        reliability = resolution = float("nan")

    return {
        "brier": brier, "reliability": reliability,
        "resolution": resolution, "uncertainty": brier_clim,
        "skill": 1 - brier / (brier_clim + 1e-9),
    }


def reliability_diagram(p: np.ndarray, y: np.ndarray, title: str):
    """Print text reliability diagram."""
    base_rate = y.mean()
    print(f"\n{'='*72}")
    print(f"RELIABILITY DIAGRAM — {title}")
    print(f"  Base rate: {base_rate*100:.1f}% | Perfect calibration: expected% == actual%")
    print(f"\n  {'Bin':>12}  {'n':>8}  {'expected%':>10}  {'actual%':>10}  {'diff':>8}  {'calibration'}")
    print("  " + "-"*70)

    bin_data = []
    for i in range(len(BINS) - 1):
        lo, hi   = BINS[i], BINS[i+1]
        mask     = (p >= lo) & (p < hi)
        n        = mask.sum()
        if n < 10:
            continue
        expected = p[mask].mean()
        actual   = y[mask].mean()
        diff     = actual - expected
        marker   = ("^ over-actual" if diff > 0.03
                    else ("v over-proba" if diff < -0.03 else "~ calibrated"))
        bin_data.append({"lo": lo, "hi": hi, "n": n,
                         "expected": expected, "actual": actual})
        print(f"  [{lo:.2f},{hi:.2f})  {n:>8,}  {expected*100:>9.1f}%  "
              f"{actual*100:>9.1f}%  {diff*100:>+7.1f}%  {marker}")

    if bin_data:
        max_err = max(abs(b["actual"] - b["expected"]) for b in bin_data)
        avg_err = np.mean([abs(b["actual"] - b["expected"]) for b in bin_data])
        print(f"\n  Max calibration error: {max_err*100:.1f}%  |  Avg: {avg_err*100:.1f}%")

        if max_err < 0.05:
            verdict = "WELL CALIBRATED — probas are reliable as portfolio weights"
        elif max_err < 0.10:
            verdict = "MODERATE CALIBRATION — small systematic bias, weighting still useful"
        else:
            verdict = "POOR CALIBRATION — consider Platt scaling before using as weights"
        print(f"  Verdict: {verdict}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--probas", type=str, default=str(DEFAULT_PROBAS))
    args = parser.parse_args()

    print(f"\nH71: PROBABILITY CALIBRATION CHECK")
    df = pd.read_parquet(args.probas)
    df["time"] = pd.to_datetime(df["time"])
    df = df[(df["time"].dt.year >= START_YEAR) & (df["time"].dt.year <= END_YEAR)]
    print(f"  {len(df):,} predictions | {df['ticker'].nunique()} tickers | {START_YEAR}-{END_YEAR}")

    p = df["xs_proba"].values.astype(float)
    y = df["actual"].values.astype(float)

    # Overall Brier score and decomposition
    bc = brier_components(p, y)
    print(f"\n{'='*72}")
    print(f"BRIER SCORE — ALL PREDICTIONS")
    print(f"{'='*72}")
    print(f"  Base rate (actual outperform rate): {y.mean()*100:.1f}%")
    print(f"  Avg predicted proba:                {p.mean()*100:.1f}%")
    print(f"  Brier score:         {bc['brier']:.4f}  (lower = better)")
    print(f"  Brier skill score:   {bc['skill']:.4f}  (0=no skill, 1=perfect)")
    print(f"  Reliability:         {bc['reliability']:.4f}  (lower = better calibrated)")
    print(f"  Resolution:          {bc['resolution']:.4f}  (higher = more informative)")
    print(f"  Uncertainty:         {bc['uncertainty']:.4f}  (fixed by base rate)")
    print(f"\n  Decomposition check: reliability - resolution + uncertainty = "
          f"{bc['reliability'] - bc['resolution'] + bc['uncertainty']:.4f} "
          f"(should ~= {bc['brier']:.4f})")

    # Full-universe reliability diagram
    reliability_diagram(p, y, f"Full universe, {START_YEAR}-{END_YEAR}")

    # Traded universe (proba >= MIN_PROBA)
    print(f"\n{'='*72}")
    print(f"CALIBRATION — TRADED UNIVERSE (xs_proba >= {MIN_PROBA})")
    print(f"{'='*72}")
    mask_t = p >= MIN_PROBA
    p_t, y_t = p[mask_t], y[mask_t]
    print(f"  {mask_t.sum():,} predictions ({mask_t.mean()*100:.1f}% of all rows)")
    print(f"  Avg predicted proba: {p_t.mean()*100:.1f}%")
    print(f"  Actual win rate:     {y_t.mean()*100:.1f}%")
    print(f"  Bias: {(y_t.mean() - p_t.mean())*100:+.1f}%  "
          f"({'probas overestimate' if p_t.mean() > y_t.mean() else 'probas underestimate'})")
    bc_t = brier_components(p_t, y_t)
    print(f"  Brier skill score:   {bc_t['skill']:.4f}")

    reliability_diagram(p_t, y_t, f"Traded universe (proba >= {MIN_PROBA})")

    # Year-by-year Brier
    print(f"\n{'='*72}")
    print(f"BRIER SCORE BY YEAR")
    print(f"{'='*72}")
    print(f"  {'year':>5}  {'n':>8}  {'brier':>8}  {'skill':>8}  "
          f"{'base_rate':>10}  {'avg_proba':>10}  {'bias':>8}")
    print("  " + "-"*65)

    for year, grp in df.groupby(df["time"].dt.year):
        py = grp["xs_proba"].values.astype(float)
        yy = grp["actual"].values.astype(float)
        br = np.mean((py - yy) ** 2)
        br_base = yy.mean() * (1 - yy.mean())
        skill = 1 - br / (br_base + 1e-9)
        bias  = yy.mean() - py.mean()
        print(f"  {year:>5}  {len(grp):>8,}  {br:>8.4f}  {skill:>+7.4f}  "
              f"{yy.mean()*100:>9.1f}%  {py.mean()*100:>9.1f}%  {bias*100:>+7.1f}%")

    # Calibration for the top-proba decile specifically
    print(f"\n{'='*72}")
    print(f"TOP-DECILE CALIBRATION (top 10% by proba each day)")
    print(f"{'='*72}")
    top_decile_rows = []
    for _, day in df.groupby("time"):
        if len(day) < 10:
            continue
        cutoff = day["xs_proba"].quantile(0.9)
        top    = day[day["xs_proba"] >= cutoff]
        top_decile_rows.append(top[["xs_proba", "actual"]])

    if top_decile_rows:
        td = pd.concat(top_decile_rows, ignore_index=True)
        p_td = td["xs_proba"].values.astype(float)
        y_td = td["actual"].values.astype(float)
        print(f"  {len(td):,} observations (top decile per day)")
        print(f"  Avg proba: {p_td.mean()*100:.1f}%  |  Actual win rate: {y_td.mean()*100:.1f}%")
        print(f"  Bias: {(y_td.mean() - p_td.mean())*100:+.1f}%")
        bc_td = brier_components(p_td, y_td)
        print(f"  Brier skill: {bc_td['skill']:.4f}")
        reliability_diagram(p_td, y_td, "Top decile per day")

    # Implication for score weighting
    print(f"\n{'='*72}")
    print(f"IMPLICATION FOR SCORE-WEIGHTED SIZING (H65/H69)")
    print(f"{'='*72}")
    print(f"  Square weighting: w = (proba - 0.5)^2, concentrates capital in high-proba picks.")
    print(f"  Calibration check validates whether that concentration is justified:")
    print(f"    - Well calibrated -> high-proba stocks genuinely win more -> weighting is sound")
    print(f"    - Overconfident   -> reduce concentration (smaller exponent in weight formula)")
    print(f"    - Underconfident  -> increase concentration (larger exponent)")
    print(f"  Overall bias: {(y.mean() - p.mean())*100:+.1f}%  |  "
          f"Traded bias: {(y_t.mean() - p_t.mean())*100:+.1f}%")


if __name__ == "__main__":
    main()
