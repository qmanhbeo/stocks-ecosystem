"""
H64: VN30-Only Universe.

VN30 = the 30 most liquid HOSE stocks. This is the subset you can actually
trade at meaningful size without moving the market.

Hypothesis: restricting to VN30 gives up most of the universe but may
IMPROVE the Sharpe (fewer noisy small-caps), and is far more executable.

This runs the same rigorous tests as H56 (nested WF) but restricted to VN30:
  1. Quintile factor test (does proba rank predict actual?)
  2. Top-N sweep (N=1..10) — with H54 params
  3. Nested WF (zero contamination)

Baseline comparisons:
  - H54 (393 stocks, contaminated): +25.52% edge, Sharpe 9.17
  - H56 (393 stocks, nested WF):    +25.98% edge, Sharpe 7.35

Usage:
    conda run -n stocks python analysis/h64_vn30_universe.py
"""
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from path_utils import data_path
from itertools import product
from scipy.stats import spearmanr, ttest_1samp

DEFAULT_PROBAS = data_path("features/xs_barrier_all_probas_hose_full.parquet")
VIX_PATH   = data_path("fx-commodities/fx_commodities_vix_1D.parquet")

START_YEAR  = 2015
TOP_N       = 5
MIN_PROBA   = 0.55
VIX_MIN     = 15.0
VIX_MAX     = 30.0
META_WINDOW = 3

# VN30 components (standard 2024-2025 composition — frozen for look-ahead free use)
# These are the 30 most-traded HOSE stocks included in the VN30 index.
VN30_TICKERS = {
    "ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG",
    "MBB", "MWG", "NVL", "PDR", "PLX", "PNJ", "POW", "SAB", "SHB", "SSI",
    "STB", "TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB",
}


def load_data(probas_path: Path, tickers: set = None) -> pd.DataFrame:
    df = pd.read_parquet(probas_path)
    df["time"] = pd.to_datetime(df["time"])
    if tickers:
        df = df[df["ticker"].isin(tickers)].copy()
    vix = pd.read_parquet(VIX_PATH)[["time", "close"]].rename(columns={"close": "vix"})
    vix["time"] = pd.to_datetime(vix["time"])
    df = df.merge(vix, on="time", how="left")
    df["vix"] = df["vix"].ffill()
    return df


def quintile_factor_test(df: pd.DataFrame, label: str):
    print(f"\n{'='*70}")
    print(f"QUINTILE FACTOR TEST — {label}")
    print(f"  {'year':>5}  {'Q5_rate':>8}  {'Q1_rate':>8}  {'spread':>8}  {'IC':>8}  {'pval':>8}")
    print("  " + "-"*55)

    per_year = []
    for year, grp in df.groupby("year"):
        if year < START_YEAR:
            continue
        daily = []
        for _, day in grp.groupby("time"):
            if len(day) < 5:
                continue
            ic = spearmanr(day["xs_proba"], day["actual"])[0]
            ranks = day["xs_proba"].rank(pct=True)
            q5 = day[ranks >= 0.8]["actual"].mean()
            q1 = day[ranks <= 0.2]["actual"].mean()
            if not (np.isnan(q5) or np.isnan(q1)):
                daily.append({"ic": ic, "spread": q5 - q1})
        if len(daily) < 20:
            continue
        d = pd.DataFrame(daily)
        avg_sp = d["spread"].mean()
        avg_ic = d["ic"].mean()
        pval = ttest_1samp(d["spread"], 0).pvalue
        sig = "*" if pval < 0.05 else " "
        q5_avg = avg_sp + grp["actual"].mean()
        q1_avg = grp["actual"].mean() - avg_sp / 2
        print(f"  {year:>5}  {q5_avg*100:>7.1f}%  {q1_avg*100:>7.1f}%  {avg_sp*100:>+7.2f}%  {avg_ic:>+7.3f}  {pval:>7.4f}{sig}")
        per_year.append({"year": year, "spread": avg_sp, "ic": avg_ic})

    if per_year:
        sp = [r["spread"] for r in per_year]
        ic = [r["ic"] for r in per_year]
        n_sig = sum(1 for r in per_year if abs(r["spread"]) * 100 > 2)
        print(f"\n  Avg Q5-Q1 spread : {np.mean(sp)*100:+.2f}%  (std: {np.std(sp)*100:.2f}%)")
        print(f"  Avg IC (Spearman): {np.mean(ic):+.4f}")
        print(f"  Sig years        : {n_sig}/{len(per_year)}")


def top_n_sweep(df: pd.DataFrame, label: str):
    print(f"\n{'='*70}")
    print(f"TOP-N SWEEP — {label}")
    print(f"VIX[{VIX_MIN},{VIX_MAX}] | min_proba={MIN_PROBA}")
    print(f"  {'N':>4}  {'avg_edge':>9}  {'sharpe':>8}  {'n_yrs':>6}  {'trades/yr':>10}")
    print("  " + "-"*50)

    for n in [1, 2, 3, 5, 7, 10]:
        per_year = []
        for year, grp in df.groupby("year"):
            if year < START_YEAR:
                continue
            naive = grp["actual"].mean()
            day_eds = []
            for _, day in grp.groupby("time"):
                vix_val = day["vix"].iloc[0]
                if not (VIX_MIN <= vix_val <= VIX_MAX):
                    continue
                top = day.nlargest(n, "xs_proba")
                if len(top) < n:
                    continue
                if top["xs_proba"].min() >= MIN_PROBA:
                    day_eds.append(top["actual"].mean() - naive)
            if len(day_eds) >= 5:
                per_year.append({"edge": np.mean(day_eds), "n_trades": len(day_eds)})
        if per_year:
            edges = [r["edge"] for r in per_year]
            sharpe = np.mean(edges) / (np.std(edges) + 1e-9)
            trades = np.mean([r["n_trades"] for r in per_year])
            print(f"  {n:>4}  {np.mean(edges)*100:>+8.2f}%  {sharpe:>8.2f}  "
                  f"{len(per_year):>6}  {trades:>9.1f}")


def nested_wf(df: pd.DataFrame, label: str):
    print(f"\n{'='*70}")
    print(f"NESTED WF (zero contamination) — {label}")
    print(f"Meta window: {META_WINDOW} yrs | Grid: VIX_MAX, MIN_PROBA, TOP_N")
    print(f"  {'year':>5}  {'params':>22}  {'meta_sh':>8}  {'test_edge':>10}  {'trades':>7}")
    print("  " + "-"*65)

    vix_max_grid   = [25.0, 28.0, 30.0, 32.0, 35.0]
    min_proba_grid = [0.50, 0.52, 0.55, 0.58]
    top_n_grid     = [1, 2, 3, 5, 7]
    all_years = sorted(df["year"].unique())
    test_years = [y for y in all_years if y >= START_YEAR]

    results = []
    for test_year in test_years:
        meta_years = [y for y in all_years if test_year - META_WINDOW <= y < test_year]
        if len(meta_years) < 2:
            print(f"  {test_year:>5}  insufficient meta data")
            continue
        df_meta = df[df["year"].isin(meta_years)]
        df_test = df[df["year"] == test_year]

        best_sh, best_params = -999, None
        for top_n, min_proba, vix_max in product(top_n_grid, min_proba_grid, vix_max_grid):
            yr_eds = []
            for yr, grp in df_meta.groupby("year"):
                naive = grp["actual"].mean()
                day_eds = []
                for _, day in grp.groupby("time"):
                    if not (VIX_MIN <= day["vix"].iloc[0] <= vix_max):
                        continue
                    top = day.nlargest(top_n, "xs_proba")
                    if len(top) < top_n:
                        continue
                    if top["xs_proba"].min() >= min_proba:
                        day_eds.append(top["actual"].mean() - naive)
                if len(day_eds) >= 5:
                    yr_eds.append(np.mean(day_eds))
            if len(yr_eds) >= 2:
                sh = np.mean(yr_eds) / (np.std(yr_eds) + 1e-9)
                if sh > best_sh:
                    best_sh, best_params = sh, (top_n, min_proba, vix_max)

        if best_params is None:
            print(f"  {test_year:>5}  no valid combo found")
            continue

        top_n, min_proba, vix_max = best_params
        naive = df_test["actual"].mean()
        day_eds = []
        for _, day in df_test.groupby("time"):
            if not (VIX_MIN <= day["vix"].iloc[0] <= vix_max):
                continue
            top = day.nlargest(top_n, "xs_proba")
            if len(top) < top_n:
                continue
            if top["xs_proba"].min() >= min_proba:
                day_eds.append(top["actual"].mean() - naive)
        if not day_eds:
            continue

        test_edge = np.mean(day_eds)
        params_str = f"N={top_n},p={min_proba:.2f},V={vix_max:.0f}"
        print(f"  {test_year:>5}  {params_str:>22}  {best_sh:>8.2f}  "
              f"{test_edge*100:>+9.2f}%  {len(day_eds):>6}")
        results.append({"year": test_year, "edge": test_edge, "n_trades": len(day_eds)})

    if results:
        edges = [r["edge"] for r in results]
        sharpe = np.mean(edges) / (np.std(edges) + 1e-9)
        n_pos  = sum(1 for e in edges if e > 0)
        trades = np.mean([r["n_trades"] for r in results])
        print(f"\n  {label} NESTED WF RESULT")
        print(f"  Avg edge : {np.mean(edges)*100:+.2f}%  (std: {np.std(edges)*100:.2f}%)")
        print(f"  Sharpe   : {sharpe:.2f}")
        print(f"  Positive : {n_pos}/{len(results)} years")
        print(f"  Trades/yr: {trades:.1f}")
        print(f"\n  H56 BASELINE (393 stocks): +25.98% edge, Sharpe 7.35, 9/9 years")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probas", type=str, default=str(DEFAULT_PROBAS))
    parser.add_argument("--no-vn30-filter", action="store_true",
                        help="Run on ALL tickers (useful for comparison baseline in same run)")
    args = parser.parse_args()

    print(f"\nH64: VN30-ONLY UNIVERSE")
    df_full = load_data(Path(args.probas))
    all_n = df_full["ticker"].nunique()
    print(f"  Full universe: {len(df_full):,} rows | {all_n} tickers")

    # Filter to VN30 tickers available in the probas
    available_vn30 = VN30_TICKERS & set(df_full["ticker"].unique())
    missing = VN30_TICKERS - available_vn30
    print(f"  VN30 tickers in data: {len(available_vn30)}/30"
          + (f" (missing: {sorted(missing)})" if missing else ""))

    df_vn30 = df_full[df_full["ticker"].isin(available_vn30)].copy()
    print(f"  VN30 subset: {len(df_vn30):,} rows | {df_vn30['ticker'].nunique()} tickers")

    # Run all tests on VN30
    quintile_factor_test(df_vn30, f"VN30 ({len(available_vn30)} tickers)")
    top_n_sweep(df_vn30, f"VN30 ({len(available_vn30)} tickers)")
    nested_wf(df_vn30, f"VN30 ({len(available_vn30)} tickers)")

    # Baseline comparison on full universe (same run, same params)
    if not args.no_vn30_filter:
        print(f"\n{'='*70}")
        print(f"BASELINE COMPARISON — Full {all_n}-ticker universe (same params)")
        quintile_factor_test(df_full, f"Full ({all_n} tickers)")


if __name__ == "__main__":
    main()
