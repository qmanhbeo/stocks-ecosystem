"""
H30: Expanded macro regime filter sweep with new global indicators.

New indicators tested (added in Session 11 via fetch_global_macro.py):
  sp500_mom_5d/20d   S&P 500 short/medium momentum
  yield_curve        US 10Y - 3M spread (negative = recession signal)
  yield_curve_mom    20d change in yield curve (flattening = risk-off)
  hyg_tlt_ratio      HYG/TLT ratio (junk vs safe bonds = credit risk appetite)
  hyg_tlt_mom_20d    HYG/TLT 20d momentum
  hyg_mom_20d        High-yield credit 20d return
  tlt_mom_20d        Long-duration treasury 20d return (flight-to-safety)
  eem_vs_sp500_20d   EEM vs S&P500 20d relative return (EM flows)
  eem_mom_20d        EM equity 20d return
  kospi_mom_20d      Korea 20d return (Asian tech proxy)
  taiex_mom_20d      Taiwan 20d return (semiconductor cycle)
  btc_mom_20d        Bitcoin 20d return (global speculative appetite)
  breadth_score_ext  0-9 multi-asset breadth (original + KOSPI + TAIEX + EWH)
  credit_risk_on     0-3 count of HYG, EEM, SP500 all in uptrend

Usage:
    conda run -n stocks python analysis/h30_expanded_macro_sweep.py
    conda run -n stocks python analysis/h30_expanded_macro_sweep.py --target portfolio
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


def load_h22_merged() -> pd.DataFrame:
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
    TOP5 = ["EIB", "STB", "POW", "MSN", "BID"]
    df = pd.read_parquet(ALL_PROBAS)
    df["time"] = pd.to_datetime(df["time"])
    df = df[df["ticker"].isin(TOP5)].copy()
    df["conf"] = (np.abs(df["xs_proba"] - 0.5) > threshold).astype(int)
    df["pred"] = (df["xs_proba"] > 0.5).astype(int)
    return df


def score_h22(df: pd.DataFrame, active: pd.Series, label: str) -> dict:
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
        pred   = grp["ens_pred"].values[gmask]
        actual = grp["actual"].values[gmask]
        acc    = (pred == actual).mean()
        edge   = acc - naive
        pval   = binomtest(int((pred == actual).sum()), n, naive).pvalue
        per_year.append({"year": year, "n": n, "edge": edge, "pval": pval})

    valid = [r for r in per_year if r is not None]
    if not valid:
        return None
    edges = [r["edge"] for r in valid]
    n_sig = sum(1 for r in valid if r["pval"] < 0.05)
    e22   = next((r["edge"] for r in valid if r["year"] == 2022), float("nan"))
    avg   = np.mean(edges)
    std   = np.std(edges) if len(edges) > 1 else float("nan")
    sharpe = avg / std if std > 0 else float("nan")
    trades_yr = np.mean([r["n"] for r in valid])
    return {"label": label, "avg_edge": avg, "sharpe": sharpe, "n_sig": n_sig,
            "n_years": len(valid), "trades_yr": trades_yr, "edge_2022": e22}


def score_portfolio(df: pd.DataFrame, active: pd.Series, label: str) -> dict:
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
        acc  = (g["pred"].values == g["actual"].values).mean()
        edge = acc - naive
        pval = binomtest(int((g["pred"] == g["actual"]).sum()), n, naive).pvalue
        per_year.append({"year": year, "n": n, "edge": edge, "pval": pval})

    valid = [r for r in per_year if r is not None]
    if not valid:
        return None
    edges = [r["edge"] for r in valid]
    n_sig = sum(1 for r in valid if r["pval"] < 0.05)
    e22   = next((r["edge"] for r in valid if r["year"] == 2022), float("nan"))
    avg   = np.mean(edges)
    std   = np.std(edges) if len(edges) > 1 else float("nan")
    sharpe = avg / std if std > 0 else float("nan")
    trades_yr = np.mean([r["n"] for r in valid])
    return {"label": label, "avg_edge": avg, "sharpe": sharpe, "n_sig": n_sig,
            "n_years": len(valid), "trades_yr": trades_yr, "edge_2022": e22}


def print_results(results: list, baseline: dict, title: str):
    print(f"\n{'='*90}")
    print(f"{title}")
    print(f"{'='*90}")
    b = baseline
    print(f"  {'Filter':44s}  {'avg_edge':>9}  {'Sharpe':>7}  {'n_sig':>6}  {'trades/yr':>10}  {'2022':>7}")
    print("  " + "-"*85)
    print(f"  {'BASELINE (no macro filter)':44s}  {b['avg_edge']*100:>+8.2f}%"
          f"  {b['sharpe']:>7.2f}  {b['n_sig']:>3}/{b['n_years']}  {b['trades_yr']:>9.0f}  "
          f"{b['edge_2022']*100:>+6.2f}%")
    print("  " + "-"*85)
    for r in sorted(results, key=lambda x: x["avg_edge"], reverse=True):
        delta  = r["avg_edge"] - b["avg_edge"]
        marker = " ↑" if delta > 0.005 else (" ↓" if delta < -0.005 else "  ")
        print(f"  {r['label']:44s}  {r['avg_edge']*100:>+8.2f}%{marker}"
              f"  {r['sharpe']:>7.2f}  {r['n_sig']:>3}/{r['n_years']}  {r['trades_yr']:>9.0f}  "
              f"{r['edge_2022']*100:>+6.2f}%")


def build_new_filters(macro: pd.DataFrame) -> dict:
    """Build new-indicator filters from the expanded 32-col macro_regime_daily."""
    filters = {}
    cols = macro.columns.tolist()

    # ── SP500 momentum ─────────────────────────────────────────────────────────
    if "sp500_mom_5d" in cols:
        for thr in [-0.03, -0.05, 0.0, 0.02]:
            filters[f"sp500_mom_5d >= {thr:.0%}"] = macro["sp500_mom_5d"] >= thr
    if "sp500_mom_20d" in cols:
        for thr in [-0.05, -0.10, 0.0]:
            filters[f"sp500_mom_20d >= {thr:.0%}"] = macro["sp500_mom_20d"] >= thr

    # ── Yield curve ────────────────────────────────────────────────────────────
    if "yield_curve" in cols:
        # Positive = normal, negative = inverted = recession
        for thr in [-0.5, 0.0, 0.5]:
            filters[f"yield_curve >= {thr:.1f}pp"] = macro["yield_curve"] >= thr
    if "yield_curve_mom" in cols:
        # Steepening (positive change) = reflation risk-on
        for thr in [-0.2, 0.0]:
            filters[f"yield_curve_mom >= {thr:.1f}pp"] = macro["yield_curve_mom"] >= thr

    # ── Credit risk (HYG/TLT) ─────────────────────────────────────────────────
    if "hyg_tlt_mom_20d" in cols:
        for thr in [-0.03, 0.0, 0.02]:
            filters[f"hyg_tlt_mom_20d >= {thr:.0%}"] = macro["hyg_tlt_mom_20d"] >= thr
    if "hyg_mom_20d" in cols:
        for thr in [-0.05, 0.0]:
            filters[f"hyg_mom_20d >= {thr:.0%}"] = macro["hyg_mom_20d"] >= thr
    if "tlt_mom_20d" in cols:
        # TLT falling = rates rising = risk-off; avoid trading when TLT rallying strongly
        for thr in [-0.05, 0.0, 0.05]:
            filters[f"tlt_mom_20d <= {thr:.0%}"] = macro["tlt_mom_20d"] <= thr

    # ── EM flows (EEM) ─────────────────────────────────────────────────────────
    if "eem_vs_sp500_20d" in cols:
        for thr in [-0.05, -0.03, 0.0]:
            filters[f"eem_vs_sp500_20d >= {thr:.0%}"] = macro["eem_vs_sp500_20d"] >= thr
    if "eem_mom_20d" in cols:
        for thr in [-0.05, 0.0]:
            filters[f"eem_mom_20d >= {thr:.0%}"] = macro["eem_mom_20d"] >= thr

    # ── Asian tech cycle ───────────────────────────────────────────────────────
    if "kospi_mom_20d" in cols:
        for thr in [-0.05, 0.0]:
            filters[f"kospi_mom_20d >= {thr:.0%}"] = macro["kospi_mom_20d"] >= thr
    if "taiex_mom_20d" in cols:
        for thr in [-0.05, 0.0, 0.03]:
            filters[f"taiex_mom_20d >= {thr:.0%}"] = macro["taiex_mom_20d"] >= thr

    # ── Bitcoin (speculative appetite) ─────────────────────────────────────────
    if "btc_mom_20d" in cols:
        for thr in [-0.10, 0.0, 0.10]:
            filters[f"btc_mom_20d >= {thr:.0%}"] = macro["btc_mom_20d"] >= thr

    # ── Extended breadth ───────────────────────────────────────────────────────
    if "breadth_score_ext" in cols:
        for thr in [3, 4, 5, 6]:
            filters[f"breadth_score_ext >= {thr}"] = macro["breadth_score_ext"] >= thr

    # ── Credit regime composite ────────────────────────────────────────────────
    if "credit_risk_on" in cols:
        for thr in [1, 2, 3]:
            filters[f"credit_risk_on >= {thr}"] = macro["credit_risk_on"] >= thr

    return filters


def run(target: str):
    macro = pd.read_parquet(MACRO_PATH)
    macro["time"] = pd.to_datetime(macro["time"])
    macro = macro.set_index("time")

    print(f"Macro regime features available ({len(macro.columns)}): {sorted(macro.columns.tolist())}")

    if target == "h22":
        df = load_h22_merged()
        score_fn = score_h22
        baseline_active = pd.Series(True, index=df.index)
        baseline = score_fn(df, baseline_active, "BASELINE")

        filters_raw = build_new_filters(macro)
        filters = {}
        for label, s in filters_raw.items():
            aligned = s.reindex(df["time"], method="ffill").fillna(True)
            filters[label] = pd.Series(aligned.values, index=df.index)

        results = [r for r in (score_fn(df, act, lbl) for lbl, act in filters.items()) if r]
        print_results(results, baseline, "H30 EXPANDED MACRO SWEEP — H22 (FPT)")

        # Best combos from Session 10 (known winners) + new best filters
        print(f"\n{'='*90}")
        print("TOP INDIVIDUAL FILTERS (new indicators only, sorted by avg_edge)")
        top = sorted(results, key=lambda x: x["avg_edge"], reverse=True)[:10]
        for r in top:
            print(f"  {r['label']:44s}  avg={r['avg_edge']*100:+.2f}%  sharpe={r['sharpe']:.2f}  "
                  f"2022={r['edge_2022']*100:+.2f}%")

    else:  # portfolio
        df = load_portfolio_merged()
        score_fn = score_portfolio

        macro_idx = macro.index
        baseline_active = pd.Series(True, index=macro_idx)
        baseline = score_fn(df, baseline_active, "BASELINE")

        filters = build_new_filters(macro)

        results = [r for r in (score_fn(df, act, lbl) for lbl, act in filters.items()) if r]
        print_results(results, baseline, "H30 EXPANDED MACRO SWEEP — H23 PORTFOLIO (top-5)")

        top = sorted(results, key=lambda x: x["avg_edge"], reverse=True)[:10]
        print(f"\nTop 10 new filters by avg_edge:")
        for r in top:
            print(f"  {r['label']:44s}  avg={r['avg_edge']*100:+.2f}%  sharpe={r['sharpe']:.2f}  "
                  f"2022={r['edge_2022']*100:+.2f}%")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=["h22", "portfolio"], default="h22")
    args = parser.parse_args()
    run(args.target)
