"""
H26: Macro regime filter sweep on H22 (FPT) and H23 portfolio.

Tests each composite macro indicator as a trade filter and reports which
improve avg_edge, Sharpe, and 2022 performance vs unfiltered baseline.

Usage:
    conda run -n stocks python analysis/h26_macro_regime_sweep.py
    conda run -n stocks python analysis/h26_macro_regime_sweep.py --target portfolio
"""
import argparse
import numpy as np
import pandas as pd
from scipy.stats import binomtest
from pathlib import Path
from path_utils import data_path


MACRO_PATH = str(data_path("features/macro_regime_daily.parquet"))
XS_BARRIER = str(data_path("features/xs_barrier_fpt_proba.csv"))
SS_E32 = str(data_path("features/ss_fpt_proba_e32.csv"))
VIX_PATH = str(data_path("fx-commodities/fx_commodities_vix_1D.parquet"))
ALL_PROBAS = str(data_path("features/xs_barrier_all_probas.parquet"))


# ── helpers ──────────────────────────────────────────────────────────────────

def load_h22_merged() -> pd.DataFrame:
    """Load H22-style ensemble (barrier XS + E32, min-conf=0.55, agree-only, VIX 18-35)."""
    xs = pd.read_csv(XS_BARRIER, parse_dates=["time"])
    ss = pd.read_csv(SS_E32, parse_dates=["time"])
    vix_df = pd.read_parquet(VIX_PATH)[["time","close"]].copy()
    vix_df["time"] = pd.to_datetime(vix_df["time"])
    vix_s = vix_df.set_index("time")["close"]

    df = xs.merge(ss[["time","ss_proba"]], on="time")
    df["ens_proba"] = (df["xs_proba"] + df["ss_proba"]) / 2
    df["ens_pred"]  = (df["ens_proba"] > 0.5).astype(int)
    df["xs_pred"]   = (df["xs_proba"] > 0.5).astype(int)
    df["ss_pred"]   = (df["ss_proba"] > 0.5).astype(int)
    df["agree"]     = (df["xs_pred"] == df["ss_pred"]).astype(int)
    df["base_conf"] = (np.abs(df["ens_proba"] - 0.5) >= 0.05).astype(int)
    df["vix"] = vix_s.reindex(df["time"].values, method="ffill").values
    df["base_conf"] &= ((df["vix"] >= 18) & (df["vix"] <= 35)).astype(int)
    df["base_conf"] &= df["agree"]
    return df


def load_portfolio_merged(threshold: float = 0.05) -> pd.DataFrame:
    """Load H23-style portfolio (top-5 tickers, XS barrier proba, no extra filters)."""
    TOP5 = ["EIB", "STB", "POW", "MSN", "BID"]
    df = pd.read_parquet(ALL_PROBAS)
    df["time"] = pd.to_datetime(df["time"])
    df = df[df["ticker"].isin(TOP5)].copy()
    df["conf"] = (np.abs(df["xs_proba"] - 0.5) > threshold).astype(int)
    df["pred"] = (df["xs_proba"] > 0.5).astype(int)
    return df


def score_h22(df: pd.DataFrame, active: pd.Series, label: str) -> dict:
    """active: boolean series aligned to df.index selecting allowed trade dates."""
    filt = df["base_conf"].astype(bool) & active.values.astype(bool)
    per_year = []
    for year, grp in df.groupby(df["time"].dt.year):
        if year < 2015:
            continue
        gmask = filt[grp.index]
        n = gmask.sum()
        naive = grp["actual"].mean()
        if n < 5:
            per_year.append(None)
            continue
        pred = grp["ens_pred"].values[gmask]
        actual = grp["actual"].values[gmask]
        acc = (pred == actual).mean()
        edge = acc - naive
        pval = binomtest(int((pred == actual).sum()), n, naive).pvalue
        per_year.append({"year": year, "n": n, "edge": edge, "pval": pval})

    valid = [r for r in per_year if r is not None]
    if not valid:
        return None
    edges = [r["edge"] for r in valid]
    n_sig = sum(1 for r in valid if r["pval"] < 0.05)
    e22 = next((r["edge"] for r in valid if r["year"] == 2022), float("nan"))
    avg = np.mean(edges)
    std = np.std(edges) if len(edges) > 1 else float("nan")
    sharpe = avg / std if std > 0 else float("nan")
    trades_yr = np.mean([r["n"] for r in valid])
    return {"label": label, "avg_edge": avg, "sharpe": sharpe, "n_sig": n_sig,
            "n_years": len(valid), "trades_yr": trades_yr, "edge_2022": e22}


def score_portfolio(df: pd.DataFrame, active: pd.Series, label: str) -> dict:
    """active: boolean series with DatetimeIndex, aligned by date."""
    df2 = df.copy()
    act_s = active.reindex(df2["time"], method="ffill").fillna(False)
    df2["final_conf"] = df2["conf"].astype(bool) & act_s.values
    per_year = []
    for year, grp in df2.groupby("year"):
        if year < 2015:
            continue
        g = grp[grp["final_conf"]]
        n = len(g)
        naive = grp["actual"].mean()
        if n < 5:
            per_year.append(None)
            continue
        acc = (g["pred"].values == g["actual"].values).mean()
        edge = acc - naive
        pval = binomtest(int((g["pred"] == g["actual"]).sum()), n, naive).pvalue
        per_year.append({"year": year, "n": n, "edge": edge, "pval": pval})
    valid = [r for r in per_year if r is not None]
    if not valid:
        return None
    edges = [r["edge"] for r in valid]
    n_sig = sum(1 for r in valid if r["pval"] < 0.05)
    e22 = next((r["edge"] for r in valid if r["year"] == 2022), float("nan"))
    avg = np.mean(edges)
    std = np.std(edges) if len(edges) > 1 else float("nan")
    sharpe = avg / std if std > 0 else float("nan")
    trades_yr = np.mean([r["n"] for r in valid])
    return {"label": label, "avg_edge": avg, "sharpe": sharpe, "n_sig": n_sig,
            "n_years": len(valid), "trades_yr": trades_yr, "edge_2022": e22}


def print_results(results: list, baseline: dict, title: str):
    print(f"\n{'='*85}")
    print(f"{title}")
    print(f"{'='*85}")
    b = baseline
    print(f"  {'Filter':40s}  {'avg_edge':>9}  {'Sharpe':>7}  {'n_sig':>6}  {'trades/yr':>10}  {'2022':>7}")
    print("  " + "-"*80)
    print(f"  {'BASELINE (no macro filter)':40s}  {b['avg_edge']*100:>+8.2f}%"
          f"  {b['sharpe']:>7.2f}  {b['n_sig']:>3}/{b['n_years']}  {b['trades_yr']:>9.0f}  "
          f"{b['edge_2022']*100:>+6.2f}%")
    print("  " + "-"*80)
    for r in sorted(results, key=lambda x: x["avg_edge"], reverse=True):
        delta = r["avg_edge"] - b["avg_edge"]
        marker = " ↑" if delta > 0.005 else (" ↓" if delta < -0.005 else "  ")
        print(f"  {r['label']:40s}  {r['avg_edge']*100:>+8.2f}%{marker}"
              f"  {r['sharpe']:>7.2f}  {r['n_sig']:>3}/{r['n_years']}  {r['trades_yr']:>9.0f}  "
              f"{r['edge_2022']*100:>+6.2f}%")


# ── main sweep ────────────────────────────────────────────────────────────────

def run(target: str):
    macro = pd.read_parquet(MACRO_PATH)
    macro["time"] = pd.to_datetime(macro["time"])
    macro = macro.set_index("time")

    if target == "h22":
        df = load_h22_merged()
        score_fn = score_h22
        # baseline: always active
        baseline_active = pd.Series(True, index=df.index)
        baseline = score_fn(df, baseline_active, "BASELINE")

        filters = {}

        # 1. VIX momentum filters (avoid fast-falling VIX periods)
        for thr in [-0.05, -0.08, -0.12, -0.15]:
            s = (macro["vix_mom_5d"] >= thr).reindex(df["time"], method="ffill").fillna(True)
            filters[f"vix_mom_5d >= {thr:.0%}"] = pd.Series(s.values, index=df.index)

        for thr in [-0.10, -0.15, -0.20]:
            s = (macro["vix_mom_20d"] >= thr).reindex(df["time"], method="ffill").fillna(True)
            filters[f"vix_mom_20d >= {thr:.0%}"] = pd.Series(s.values, index=df.index)

        # VIX vs MA (avoid when VIX is collapsing back toward MA)
        for thr in [-0.10, -0.20, -0.30]:
            s = (macro["vix_vs_ma60"] >= thr).reindex(df["time"], method="ffill").fillna(True)
            filters[f"vix_vs_ma60 >= {thr:.0%}"] = pd.Series(s.values, index=df.index)

        # 2. VNM ETF vs VNINDEX divergence (foreigners bullish on Vietnam)
        for thr in [-0.03, -0.05, -0.08, 0.0]:
            s = (macro["vnm_vs_vni_20d"] >= thr).reindex(df["time"], method="ffill").fillna(True)
            filters[f"vnm_vs_vni_20d >= {thr:.0%}"] = pd.Series(s.values, index=df.index)

        for thr in [-0.02, -0.04, 0.0]:
            s = (macro["vnm_vs_vni_5d"] >= thr).reindex(df["time"], method="ffill").fillna(True)
            filters[f"vnm_vs_vni_5d >= {thr:.0%}"] = pd.Series(s.values, index=df.index)

        # 3. US10Y level (avoid EM risk-off from high rates)
        for thr in [3.0, 4.0, 4.5]:
            s = (macro["us10y_level"] <= thr).reindex(df["time"], method="ffill").fillna(True)
            filters[f"us10y_level <= {thr:.1f}%"] = pd.Series(s.values, index=df.index)

        # US10Y rising (avoid when rates surging = EM outflows)
        for thr in [0.3, 0.5, 1.0]:
            s = (macro["us10y_mom_20d"] <= thr).reindex(df["time"], method="ffill").fillna(True)
            filters[f"us10y_mom_20d <= +{thr:.1f}pp"] = pd.Series(s.values, index=df.index)

        # 4. Copper/Gold ratio (risk appetite)
        for thr in [0.0, -0.05, -0.10]:
            s = (macro["cu_gold_mom_20d"] >= thr).reindex(df["time"], method="ffill").fillna(True)
            filters[f"cu_gold_mom_20d >= {thr:.0%}"] = pd.Series(s.values, index=df.index)

        # 5. Multi-asset breadth score
        for thr in [2, 3, 4]:
            s = (macro["breadth_score"] >= thr).reindex(df["time"], method="ffill").fillna(True)
            filters[f"breadth_score >= {thr}"] = pd.Series(s.values, index=df.index)

        # 6. VND/USD (avoid when VND weakening sharply = capital flight)
        for thr in [0.02, 0.03, 0.05]:
            s = (macro["vnd_usd_mom_20d"] <= thr).reindex(df["time"], method="ffill").fillna(True)
            filters[f"vnd_usd_mom_20d <= +{thr:.0%}"] = pd.Series(s.values, index=df.index)

        # 7. News surge (avoid high-noise information events)
        for thr in [2.0, 3.0]:
            s = (macro["news_surge_5d"] < thr).reindex(df["time"], method="ffill").fillna(True)
            filters[f"news_surge_5d < {thr:.0f}"] = pd.Series(s.values, index=df.index)

        results = []
        for label, active in filters.items():
            r = score_fn(df, active, label)
            if r:
                results.append(r)

        print_results(results, baseline, "H26 MACRO REGIME FILTER SWEEP — H22 (FPT)")

        # Also test best combinations
        print(f"\n{'='*85}")
        print("TOP COMBINATIONS (stacking best individual filters)")
        print(f"{'='*85}")
        # Sort by avg_edge to find top individual filters
        top_individual = sorted(results, key=lambda x: x["avg_edge"], reverse=True)[:6]
        print(f"  Top individual filters by avg_edge:")
        for r in top_individual[:6]:
            print(f"    {r['label']:40s}  avg={r['avg_edge']*100:+.2f}%  sharpe={r['sharpe']:.2f}")

    else:  # portfolio
        df = load_portfolio_merged()
        score_fn = score_portfolio

        # Build active series indexed by date
        macro_idx = macro.index

        baseline_active = pd.Series(True, index=macro_idx)
        baseline = score_fn(df, baseline_active, "BASELINE")

        filters = {}

        # Same filters as above but for portfolio
        for thr in [-0.05, -0.08, -0.12]:
            s = macro["vix_mom_5d"] >= thr
            filters[f"vix_mom_5d >= {thr:.0%}"] = s

        for thr in [-0.03, -0.05, 0.0]:
            s = macro["vnm_vs_vni_20d"] >= thr
            filters[f"vnm_vs_vni_20d >= {thr:.0%}"] = s

        for thr in [3.0, 4.0]:
            s = macro["us10y_level"] <= thr
            filters[f"us10y_level <= {thr:.1f}%"] = s

        for thr in [0.0, -0.05]:
            s = macro["cu_gold_mom_20d"] >= thr
            filters[f"cu_gold_mom_20d >= {thr:.0%}"] = s

        for thr in [2, 3, 4]:
            s = macro["breadth_score"] >= thr
            filters[f"breadth_score >= {thr}"] = s

        for thr in [0.02, 0.03]:
            s = macro["vnd_usd_mom_20d"] <= thr
            filters[f"vnd_usd_mom_20d <= +{thr:.0%}"] = s

        for thr in [-0.10, -0.20]:
            s = macro["vix_vs_ma60"] >= thr
            filters[f"vix_vs_ma60 >= {thr:.0%}"] = s

        results = []
        for label, active in filters.items():
            r = score_fn(df, active, label)
            if r:
                results.append(r)

        print_results(results, baseline, "H27 MACRO REGIME FILTER SWEEP — H23 PORTFOLIO (top-5)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=["h22", "portfolio"], default="h22",
                        help="Apply filters to H22 (FPT) or H23 portfolio")
    args = parser.parse_args()
    run(args.target)
