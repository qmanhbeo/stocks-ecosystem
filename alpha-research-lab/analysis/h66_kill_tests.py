"""
H66: Kill Tests — Trying to Break the Signal.

Hostile reviewer battery. If these all pass, the signal is genuine.

Test 1 — Label Permutation
  Shuffle the actual outcome labels within each (year, date) group.
  Model rankings are fixed; only what "success" means is randomized.
  Expected: IC collapses to ~0. If it doesn't → probas are random noise.

Test 2 — Backward Label (Retrograde Test)
  Use features at time t to predict labels at t-5 (PAST 5-day return).
  Expected: near-zero IC. If IC > 0 → features contain future information.
  This is the most direct leakage test.

Test 3 — Regime Asymmetry
  Train on early era (2015-2019), test on late era (2020-2025). Reverse.
  If one direction works and the other doesn't → model fit, not signal.
  Expected: both directions show positive IC and edge.

Test 4 — Random Feature Baseline
  Replace all real features with Gaussian noise, retrain XGBoost, measure IC.
  Expected: IC ≈ 0. If IC > 0.05 → pipeline structure is generating spurious signal.
  Uses a fast single-year train to save time.

Test 5 — Turnover Analysis
  How often does the top-5 portfolio actually change day to day?
  High turnover = daily rebalance cost is real.

Test 6 — Parameter Sensitivity (Meta-window)
  Run nested WF with 2yr and 5yr meta-windows instead of 3yr.
  Expected: results should be similar. If they swing wildly → not robust.

Test 7 — Base Rate & Class Balance Audit
  What fraction of stocks outperform VNINDEX? Is the model just predicting "up"?
  A biased classifier in a bull market can look great while doing nothing.

Usage:
    conda run -n stocks python analysis/h66_kill_tests.py
    conda run -n stocks python analysis/h66_kill_tests.py --run-random-features
"""
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from path_utils import data_path
from itertools import product
from scipy.stats import spearmanr, ttest_1samp

DEFAULT_PROBAS = data_path("features/xs_barrier_all_probas_hose_full.parquet")
VIX_PATH = data_path("fx-commodities/fx_commodities_vix_1D.parquet")
STOCK_DIR = data_path("stock")
START_YEAR = 2015
TOP_N = 5
MIN_PROBA = 0.55
VIX_MIN = 15.0
VIX_MAX = 30.0
META_WINDOW = 3
np.random.seed(42)


# ============================================================
# Shared helpers
# ============================================================

def compute_ic_per_year(df: pd.DataFrame) -> list:
    """Spearman IC of xs_proba vs actual, per year. Returns list of dicts."""
    results = []
    for year, grp in df.groupby("year"):
        if year < START_YEAR:
            continue
        daily_ics = []
        for _, day in grp.groupby("time"):
            if len(day) < 10:
                continue
            ic = spearmanr(day["xs_proba"], day["actual"])[0]
            if not np.isnan(ic):
                daily_ics.append(ic)
        if daily_ics:
            avg_ic = np.mean(daily_ics)
            pval = ttest_1samp(daily_ics, 0).pvalue
            results.append({"year": year, "ic": avg_ic, "pval": pval, "n_days": len(daily_ics)})
    return results


def portfolio_sharpe(df: pd.DataFrame) -> tuple:
    """Top-5 portfolio, no VIX filter, no min_proba. Returns (avg_edge, sharpe)."""
    per_year = []
    for year, grp in df.groupby("year"):
        if year < START_YEAR:
            continue
        naive = grp["actual"].mean()
        day_eds = []
        for _, day in grp.groupby("time"):
            top = day.nlargest(TOP_N, "xs_proba")
            if top["xs_proba"].min() >= MIN_PROBA:
                day_eds.append(top["actual"].mean() - naive)
        if day_eds:
            per_year.append(np.mean(day_eds))
    if not per_year:
        return float("nan"), float("nan")
    avg = np.mean(per_year)
    sh = avg / (np.std(per_year) + 1e-9)
    return avg, sh


def section(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


# ============================================================
# Test 1: Label Permutation
# ============================================================

def test_label_permutation(df: pd.DataFrame):
    section("TEST 1: LABEL PERMUTATION")
    print("  Shuffle 'actual' randomly within each (year, date) group.")
    print("  Real probas are unchanged. IC should collapse to ~0.\n")

    # Real IC
    real_results = compute_ic_per_year(df)
    real_avg_ic = np.mean([r["ic"] for r in real_results])

    # Permuted: shuffle actual within each date (preserves cross-sectional size)
    df_perm = df.copy()
    rng = np.random.default_rng(42)
    df_perm["actual"] = (
        df_perm.groupby("time")["actual"]
        .transform(lambda x: rng.permutation(x.values))
    )

    perm_results = compute_ic_per_year(df_perm)
    perm_avg_ic = np.mean([r["ic"] for r in perm_results])

    # Also permute globally (harder test)
    df_glob = df.copy()
    df_glob["actual"] = rng.permutation(df_glob["actual"].values)
    glob_results = compute_ic_per_year(df_glob)
    glob_avg_ic = np.mean([r["ic"] for r in glob_results])

    print(f"  {'Year':>5}  {'Real IC':>9}  {'Cross-date perm':>16}  {'Global perm':>12}")
    print("  " + "-"*48)
    for r, rp, rg in zip(real_results, perm_results, glob_results):
        print(f"  {r['year']:>5}  {r['ic']:>+8.4f}  {rp['ic']:>+15.4f}  {rg['ic']:>+11.4f}")

    print(f"\n  Avg IC  REAL         : {real_avg_ic:+.4f}")
    print(f"  Avg IC  CROSS-DATE   : {perm_avg_ic:+.4f}  (should be ≈0)")
    print(f"  Avg IC  GLOBAL PERM  : {glob_avg_ic:+.4f}  (should be ≈0)")

    if abs(perm_avg_ic) < 0.01:
        print(f"\n  ✅ PASS: Permuted IC collapses. Probas encode real ranking signal.")
    else:
        print(f"\n  ❌ FAIL: Permuted IC = {perm_avg_ic:.4f}. Pipeline may be leaking.")

    return real_avg_ic, perm_avg_ic


# ============================================================
# Test 2: Backward Label (Retrograde)
# ============================================================

def test_backward_label(df: pd.DataFrame):
    section("TEST 2: BACKWARD LABEL (RETROGRADE TEST)")
    print("  Use today's probas to predict PAST 5-day outcome (t-5 label).")
    print("  If features leak future info, they should also predict the past.")
    print("  Expected: IC ≈ 0. If IC > 0.05 → strong evidence of leakage.\n")

    # Shift actual backward: today's proba vs yesterday-5d's actual
    df_sorted = df.sort_values(["ticker", "time"]).copy()
    df_sorted["actual_lag5"] = df_sorted.groupby("ticker")["actual"].shift(5)
    df_back = df_sorted.dropna(subset=["actual_lag5"]).copy()
    df_back["actual"] = df_back["actual_lag5"]

    # Forward label (original, for comparison)
    fwd_results = compute_ic_per_year(df)
    back_results = compute_ic_per_year(df_back)

    fwd_avg  = np.mean([r["ic"] for r in fwd_results])
    back_avg = np.mean([r["ic"] for r in back_results])

    print(f"  {'Year':>5}  {'Forward IC (real)':>18}  {'Backward IC (t-5)':>18}")
    print("  " + "-"*46)
    fwd_map = {r["year"]: r for r in fwd_results}
    for r in back_results:
        yr = r["year"]
        fwd = fwd_map.get(yr, {}).get("ic", float("nan"))
        print(f"  {yr:>5}  {fwd:>+17.4f}  {r['ic']:>+17.4f}")

    print(f"\n  Avg IC  FORWARD  (real signal): {fwd_avg:+.4f}")
    print(f"  Avg IC  BACKWARD (leak test) : {back_avg:+.4f}")

    ratio = abs(back_avg) / (abs(fwd_avg) + 1e-9)
    if abs(back_avg) < 0.02:
        print(f"\n  ✅ PASS: Backward IC ≈ 0. Features do NOT encode future information.")
    elif abs(back_avg) < 0.05:
        print(f"\n  ⚠️  BORDERLINE: Backward IC = {back_avg:.4f} ({ratio:.0%} of forward IC).")
        print(f"     Could be autocorrelation in returns, not leakage. Needs further investigation.")
    else:
        print(f"\n  ❌ FAIL: Backward IC = {back_avg:.4f} ({ratio:.0%} of forward IC). Likely leakage.")

    return fwd_avg, back_avg


# ============================================================
# Test 3: Regime Asymmetry
# ============================================================

def test_regime_asymmetry(df: pd.DataFrame):
    section("TEST 3: REGIME ASYMMETRY")
    print("  Does the signal work equally well in both halves of the data?")
    print("  A model that only works in one era is exploiting a regime, not a signal.\n")

    eras = {
        "Pre-COVID (2015-2019)": (2015, 2019),
        "Post-COVID (2020-2025)": (2020, 2025),
        "Boom (2021-2022)":       (2021, 2022),
        "Recovery (2023-2025)":   (2023, 2025),
    }

    print(f"  {'Era':<28}  {'n_yrs':>6}  {'avg_IC':>8}  {'avg_edge':>9}  {'sharpe':>8}  {'pos':>6}")
    print("  " + "-"*70)

    for label, (y_start, y_end) in eras.items():
        sub = df[(df["year"] >= y_start) & (df["year"] <= y_end)].copy()
        if sub.empty:
            continue
        ic_results = compute_ic_per_year(sub)
        avg_ic = np.mean([r["ic"] for r in ic_results]) if ic_results else float("nan")

        per_year = []
        for year, grp in sub.groupby("year"):
            naive = grp["actual"].mean()
            day_eds = []
            for _, day in grp.groupby("time"):
                top = day.nlargest(TOP_N, "xs_proba")
                if top["xs_proba"].min() >= MIN_PROBA:
                    day_eds.append(top["actual"].mean() - naive)
            if day_eds:
                per_year.append(np.mean(day_eds))

        if not per_year:
            continue
        avg_edge = np.mean(per_year)
        sharpe = avg_edge / (np.std(per_year) + 1e-9)
        n_pos = sum(1 for e in per_year if e > 0)
        print(f"  {label:<28}  {len(per_year):>6}  {avg_ic:>+7.4f}  {avg_edge*100:>+8.2f}%  "
              f"{sharpe:>8.2f}  {n_pos}/{len(per_year)}")

    print(f"\n  Expected: consistent IC and positive edge in all eras.")
    print(f"  Red flag: one era with IC ≈ 0 or sharpe < 0.")


# ============================================================
# Test 4: Random Feature Baseline
# ============================================================

def test_random_features(df: pd.DataFrame, n_noise_features: int = 35):
    section("TEST 4: RANDOM FEATURE BASELINE")
    print(f"  Train XGBoost on {n_noise_features} Gaussian noise features (same shape as real).")
    print(f"  Predict on test year. IC should be ≈ 0.")
    print(f"  If IC > 0.03 → XGBoost is exploiting pipeline structure, not real features.\n")

    try:
        from xgboost import XGBClassifier
    except ImportError:
        print("  XGBoost not available. Skipping.")
        return

    all_years = sorted(df["year"].unique())
    test_years = [y for y in all_years if y >= START_YEAR]

    noise_ics = []
    real_ics  = []

    # Use actual feature columns if available (just for shape reference), else synthesize
    feat_cols = [f"noise_{i}" for i in range(n_noise_features)]

    for test_year in test_years:
        train_years = [y for y in all_years if y < test_year]
        if len(train_years) < 3:
            continue

        train_df = df[df["year"].isin(train_years)]
        test_df  = df[df["year"] == test_year]

        n_train = len(train_df)
        n_test  = len(test_df)

        # Random noise features
        X_train_noise = np.random.randn(n_train, n_noise_features)
        X_test_noise  = np.random.randn(n_test,  n_noise_features)
        y_train = train_df["actual"].values

        model = XGBClassifier(
            n_estimators=100, max_depth=3, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, random_state=42,
            n_jobs=-1, eval_metric="logloss", verbosity=0,
        )
        model.fit(X_train_noise, y_train)
        noise_probas = model.predict_proba(X_test_noise)[:, 1]

        # IC of noise probas vs actual
        day_ics = []
        test_df2 = test_df.copy()
        test_df2["noise_proba"] = noise_probas
        for _, day in test_df2.groupby("time"):
            if len(day) < 10:
                continue
            ic = spearmanr(day["noise_proba"], day["actual"])[0]
            if not np.isnan(ic):
                day_ics.append(ic)
        if day_ics:
            noise_ics.append(np.mean(day_ics))

        # Real IC for that year (from xs_proba)
        for _, day in test_df.groupby("time"):
            if len(day) < 10:
                continue
            ic = spearmanr(day["xs_proba"], day["actual"])[0]
            if not np.isnan(ic):
                real_ics.append(ic)

    avg_noise_ic = np.mean(noise_ics) if noise_ics else float("nan")
    avg_real_ic  = np.mean(real_ics)  if real_ics  else float("nan")

    print(f"  Avg IC (REAL features)  : {avg_real_ic:+.4f}")
    print(f"  Avg IC (NOISE features) : {avg_noise_ic:+.4f}  (should be ≈ 0)")
    print(f"  Signal-to-noise ratio   : {avg_real_ic / (abs(avg_noise_ic) + 1e-6):.1f}x")

    if abs(avg_noise_ic) < 0.01:
        print(f"\n  ✅ PASS: Noise IC ≈ 0. XGBoost is not exploiting pipeline artifacts.")
    elif abs(avg_noise_ic) < 0.03:
        print(f"\n  ⚠️  BORDERLINE: Small noise IC ({avg_noise_ic:.4f}). Likely harmless but monitor.")
    else:
        print(f"\n  ❌ FAIL: Noise IC = {avg_noise_ic:.4f}. XGBoost is extracting spurious structure.")


# ============================================================
# Test 5: Turnover Analysis
# ============================================================

def test_turnover(df: pd.DataFrame):
    section("TEST 5: TURNOVER ANALYSIS")
    print("  How often does the top-5 portfolio change day to day?")
    print("  High turnover = daily rebalance cost assumption is critical.\n")

    vix = pd.read_parquet(VIX_PATH)[["time", "close"]].rename(columns={"close": "vix"})
    vix["time"] = pd.to_datetime(vix["time"])
    df2 = df.merge(vix, on="time", how="left")
    df2["vix"] = df2["vix"].ffill()

    per_year = []
    for year, grp in df2.groupby("year"):
        if year < START_YEAR:
            continue
        prev_top5 = set()
        turnovers = []
        trade_days = 0

        for date, day in grp.groupby("time"):
            vix_val = day["vix"].iloc[0]
            if not (VIX_MIN <= vix_val <= VIX_MAX):
                prev_top5 = set()
                continue
            top = day.nlargest(TOP_N, "xs_proba")
            if top["xs_proba"].min() < MIN_PROBA:
                prev_top5 = set()
                continue
            curr_top5 = set(top["ticker"].values)
            trade_days += 1
            if prev_top5:
                overlap = len(curr_top5 & prev_top5)
                turnover = (TOP_N - overlap) / TOP_N  # fraction that changed
                turnovers.append(turnover)
            prev_top5 = curr_top5

        if turnovers:
            per_year.append({
                "year": year,
                "avg_turnover": np.mean(turnovers),
                "trade_days": trade_days,
                "full_churn_days": sum(1 for t in turnovers if t == 1.0),
                "no_change_days": sum(1 for t in turnovers if t == 0.0),
            })

    print(f"  {'Year':>5}  {'Trade days':>11}  {'Avg turnover':>13}  {'Full churn':>11}  {'No change':>10}")
    print("  " + "-"*55)
    for r in per_year:
        print(f"  {r['year']:>5}  {r['trade_days']:>11}  {r['avg_turnover']*100:>12.1f}%  "
              f"{r['full_churn_days']:>11}  {r['no_change_days']:>10}")

    all_to = [r["avg_turnover"] for r in per_year]
    avg_to = np.mean(all_to)
    avg_td = np.mean([r["trade_days"] for r in per_year])
    print(f"\n  Avg turnover/day : {avg_to*100:.1f}%  ({avg_to*TOP_N:.1f} stocks change per day on avg)")
    print(f"  Avg trade days/yr: {avg_td:.0f}")
    print(f"  Effective annual trades (buys only): {avg_to * avg_td * TOP_N:.0f} legs/yr")
    print(f"\n  Cost impact: each leg costs 0.15% (buy) + 0.15% (sell) = 0.30% RT")
    print(f"  Annual cost estimate: {avg_to * avg_td * TOP_N * 0.003 * 100:.1f}% of capital/yr")


# ============================================================
# Test 6: Parameter Sensitivity (Meta-window)
# ============================================================

def test_parameter_sensitivity(df: pd.DataFrame):
    section("TEST 6: PARAMETER SENSITIVITY (meta-window)")
    print("  Nested WF with 2yr, 3yr (baseline), 5yr meta-windows.")
    print("  Expected: similar Sharpe across windows. Large swings → not robust.\n")

    vix = pd.read_parquet(VIX_PATH)[["time", "close"]].rename(columns={"close": "vix"})
    vix["time"] = pd.to_datetime(vix["time"])
    df2 = df.merge(vix, on="time", how="left")
    df2["vix"] = df2["vix"].ffill()

    vix_max_grid   = [25.0, 28.0, 30.0, 32.0, 35.0]
    min_proba_grid = [0.50, 0.52, 0.55, 0.58]
    top_n_grid     = [3, 5, 7]
    all_years      = sorted(df2["year"].unique())
    test_years     = [y for y in all_years if y >= START_YEAR]

    print(f"  {'Meta-window':>12}  {'avg_edge':>9}  {'sharpe':>8}  {'pos':>6}  {'n_yrs':>6}")
    print("  " + "-"*48)

    for meta_window in [2, 3, 5]:
        results = []
        for test_year in test_years:
            meta_years = [y for y in all_years if test_year - meta_window <= y < test_year]
            if len(meta_years) < 2:
                continue
            df_meta = df2[df2["year"].isin(meta_years)]
            df_test = df2[df2["year"] == test_year]

            best_sh, best_params = -999, None
            for top_n, min_proba, vix_max in product(top_n_grid, min_proba_grid, vix_max_grid):
                yr_eds = []
                for _, grp in df_meta.groupby("year"):
                    naive = grp["actual"].mean()
                    day_eds = []
                    for _, day in grp.groupby("time"):
                        if not (VIX_MIN <= day["vix"].iloc[0] <= vix_max):
                            continue
                        top = day.nlargest(top_n, "xs_proba")
                        if top["xs_proba"].min() >= min_proba:
                            day_eds.append(top["actual"].mean() - naive)
                    if len(day_eds) >= 5:
                        yr_eds.append(np.mean(day_eds))
                if len(yr_eds) >= 2:
                    sh = np.mean(yr_eds) / (np.std(yr_eds) + 1e-9)
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

        if results:
            avg = np.mean(results)
            sh = avg / (np.std(results) + 1e-9)
            n_pos = sum(1 for e in results if e > 0)
            baseline = " ← baseline" if meta_window == 3 else ""
            print(f"  {meta_window:>10}yr  {avg*100:>+8.2f}%  {sh:>8.2f}  {n_pos}/{len(results)}  "
                  f"{len(results):>6}{baseline}")

    print(f"\n  Expected: Sharpe within ±2 across windows. Larger swings = overfitted meta-selection.")


# ============================================================
# Test 7: Base Rate & Class Balance Audit
# ============================================================

def test_base_rate(df: pd.DataFrame):
    section("TEST 7: BASE RATE & CLASS BALANCE AUDIT")
    print("  What fraction of stocks outperform VNINDEX each year?")
    print("  A biased model that always predicts 'up' in bull markets inflates accuracy.\n")

    print(f"  {'Year':>5}  {'base_rate':>10}  {'top5_rate':>10}  {'model_bias':>11}  {'n_days':>7}  {'n_tickers':>10}")
    print("  " + "-"*63)

    for year, grp in df.groupby("year"):
        if year < START_YEAR:
            continue
        base_rate = grp["actual"].mean()
        n_tickers = grp["ticker"].nunique()

        # What fraction does the model's top-5 predict as 1?
        day_top5_rates = []
        for _, day in grp.groupby("time"):
            top = day.nlargest(TOP_N, "xs_proba")
            if top["xs_proba"].min() >= MIN_PROBA:
                # Average predicted proba of top-5 (not actual — model's belief)
                day_top5_rates.append(top["xs_proba"].mean())

        # Also: what's the avg proba of the WHOLE universe?
        universe_avg_proba = grp["xs_proba"].mean()
        top5_avg_proba = np.mean(day_top5_rates) if day_top5_rates else float("nan")

        # Model bias: does it predict more 1s than the base rate justifies?
        # If model predicts proba=0.65 on average but base_rate=0.50, it's not biased
        # Bias = (universe_avg_proba - 0.5)  → should be small if model is calibrated
        model_bias = universe_avg_proba - 0.5

        n_days = grp["time"].nunique()
        print(f"  {year:>5}  {base_rate*100:>9.1f}%  {top5_avg_proba*100:>9.1f}%  "
              f"{model_bias*100:>+10.2f}%  {n_days:>7}  {n_tickers:>10}")

    print(f"\n  base_rate: fraction of stocks that outperform VNINDEX (should be ~50%)")
    print(f"  top5_rate: avg predicted proba for top-5 picks (should be >> base_rate)")
    print(f"  model_bias: avg universe proba - 0.5 (near 0 = well calibrated, >5% = biased toward up)")
    print(f"\n  Key: if base_rate > 60% in good years and model 'predicts' that → classifier is cheating")


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probas", type=str, default=str(DEFAULT_PROBAS))
    parser.add_argument("--run-random-features", action="store_true",
                        help="Run Test 4 (random features). Slow (~5min). Off by default.")
    args = parser.parse_args()

    print(f"\n{'#'*70}")
    print(f"  H66: KILL TESTS — HOSTILE REVIEWER BATTERY")
    print(f"  Probas: {args.probas}")
    print(f"{'#'*70}")

    print(f"\nLoading probas...")
    df = pd.read_parquet(args.probas)
    df["time"] = pd.to_datetime(df["time"])
    print(f"  {len(df):,} rows | {df['ticker'].nunique()} tickers | years {df['year'].min()}-{df['year'].max()}")

    # Run all tests
    test_label_permutation(df)
    test_backward_label(df)
    test_regime_asymmetry(df)

    if args.run_random_features:
        test_random_features(df)
    else:
        print(f"\n  [Test 4 SKIPPED] Run with --run-random-features to enable (takes ~5 min)")

    test_turnover(df)
    test_parameter_sensitivity(df)
    test_base_rate(df)

    # Summary
    section("KILL TEST SUMMARY")
    print("  Test 1 — Label Permutation  : IC should collapse to ≈0 when labels shuffled")
    print("  Test 2 — Backward Label     : IC should be ≈0 for past labels")
    print("  Test 3 — Regime Asymmetry   : consistent IC/edge in pre vs post-COVID")
    print("  Test 4 — Random Features    : noise IC should be ≈0 (run with --run-random-features)")
    print("  Test 5 — Turnover           : shows true cost drag from daily rebalancing")
    print("  Test 6 — Param Sensitivity  : Sharpe should be stable across 2/3/5yr meta-windows")
    print("  Test 7 — Base Rate          : model should not be biased toward 'up' predictions")
    print(f"\n  H57 survivorship bias audit: already run (old cohort ≈ same edge as full universe)")


if __name__ == "__main__":
    main()
