"""
Meta-labeling analysis: What distinguishes correct vs incorrect X3 ensemble predictions?

For each confident day in the X3 ensemble, compute meta-features and see whether
they predict whether the ensemble prediction was correct.

This is the first step toward H13 (meta-labeling).

Usage: python meta_analysis.py
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pandas as pd
import numpy as np
from pathlib import Path


def main():
    # Load XS and SS probas
    xs = pd.read_csv("data/features/xs_fpt_proba.csv", parse_dates=["time"])
    ss = pd.read_csv("data/features/ss_fpt_proba.csv", parse_dates=["time"])
    merged = xs.merge(ss[["time", "ss_proba"]], on="time", how="inner")
    merged["ens_proba"] = (merged["xs_proba"] + merged["ss_proba"]) / 2
    merged["ens_pred"]  = (merged["ens_proba"] > 0.5).astype(int)
    merged["confident"] = (np.abs(merged["ens_proba"] - 0.5) >= 0.05).astype(int)
    merged["correct"]   = (merged["ens_pred"] == merged["actual"]).astype(int)

    # Load meta-features
    def load_series(path, col, alias, window=None):
        df = pd.read_parquet(path)[["time", col]].copy()
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time")
        if window:
            df[alias] = df[col].rolling(window).mean()
        else:
            df[alias] = df[col]
        return df[["time", alias]].dropna()

    def pct_change_series(path, col, alias, lag):
        df = pd.read_parquet(path)[["time", col]].copy()
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time")
        df[alias] = df[col] / df[col].shift(lag) - 1
        return df[["time", alias]].dropna()

    # VIX level
    vix = load_series("data/fx-commodities/fx_commodities_vix_1D.parquet", "close", "vix_level")
    vix_ret = pct_change_series("data/fx-commodities/fx_commodities_vix_1D.parquet", "close", "vix_ret_5d", 5)

    # VNINDEX realized vol
    vni = pd.read_parquet("data/stock/gia_lich_su_VNINDEX_1D.parquet")[["time", "close"]].copy()
    vni["time"] = pd.to_datetime(vni["time"])
    vni = vni.sort_values("time")
    vni["vni_ret"] = vni["close"].pct_change()
    vni["vol20"] = vni["vni_ret"].rolling(20).std() * np.sqrt(252)
    vni["vol_pct"] = vni["vol20"].expanding(min_periods=252).rank(pct=True)
    vni_vol = vni[["time", "vol20", "vol_pct"]].dropna()

    # FPT 60d relative return vs VNINDEX
    fpt = pd.read_parquet("data/stock/gia_lich_su_FPT_1D.parquet")[["time", "close"]].copy()
    fpt["time"] = pd.to_datetime(fpt["time"])
    fpt = fpt.sort_values("time")
    vni_merge = vni[["time", "close"]].rename(columns={"close": "vni_close"})
    fpt = fpt.merge(vni_merge, on="time", how="left")
    fpt["fpt_ret60"] = fpt["close"] / fpt["close"].shift(60) - 1
    fpt["vni_ret60"] = fpt["vni_close"] / fpt["vni_close"].shift(60) - 1
    fpt["rel_ret60"] = fpt["fpt_ret60"] - fpt["vni_ret60"]
    fpt_rel = fpt[["time", "rel_ret60"]].dropna()

    # Merge all meta-features
    meta = merged.copy()
    meta = meta.merge(vix[["time", "vix_level"]], on="time", how="left")
    meta = meta.merge(vix_ret[["time", "vix_ret_5d"]], on="time", how="left")
    meta = meta.merge(vni_vol[["time", "vol20", "vol_pct"]], on="time", how="left")
    meta = meta.merge(fpt_rel[["time", "rel_ret60"]], on="time", how="left")

    conf_df = meta[meta["confident"] == 1].copy()
    print(f"Total confident predictions: {len(conf_df)}")
    print(f"Overall accuracy: {conf_df['correct'].mean()*100:.1f}%")
    print()

    # Bin by meta-features and show accuracy
    def show_bins(df, col, n_bins=4, label=None):
        if label is None:
            label = col
        valid = df[df[col].notna()]
        if len(valid) == 0:
            return
        bins = pd.qcut(valid[col], q=n_bins, duplicates='drop')
        summary = valid.groupby(bins)["correct"].agg(["mean", "count", "sum"])
        summary.columns = ["acc", "n", "n_correct"]
        summary["edge"] = summary["acc"] - valid["actual"].mean()
        print(f"  {label}:")
        for interval, row in summary.iterrows():
            print(f"    {str(interval):<30}  n={int(row['n']):<5}  acc={row['acc']*100:.1f}%  edge={row['edge']*100:+.1f}%")
        print()

    print("=== Accuracy by meta-feature bins ===\n")
    show_bins(conf_df, "vix_level", 4, "VIX level")
    show_bins(conf_df, "vix_ret_5d", 4, "VIX 5d return")
    show_bins(conf_df, "vol_pct", 4, "VNINDEX vol percentile")
    show_bins(conf_df, "rel_ret60", 4, "FPT 60d relative return")

    # Show per-year breakdown with meta-features
    print("\n=== Per-year meta-feature summary (confident days only) ===")
    print(f"{'year':>5}  {'n':>5}  {'acc':>6}  {'edge':>7}  {'vix':>7}  {'vol_pct':>8}  {'rel60':>8}")
    for yr, g in conf_df.groupby("year"):
        naive = g["actual"].mean()
        acc = g["correct"].mean()
        edge = acc - naive
        vix_m = g["vix_level"].mean()
        vol_m = g["vol_pct"].mean()
        rel60_m = g["rel_ret60"].mean()
        print(f"  {yr:>5}  {len(g):>5}  {acc*100:>5.1f}%  {edge*100:>+6.1f}%  {vix_m:>7.1f}  {vol_m:>8.2f}  {rel60_m*100:>+7.1f}%")

    # Simple meta-labeling: train a logistic regression to predict "correct"
    # Use years < test_year for training (walk-forward)
    print("\n=== Simple meta-classifier walk-forward ===")
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    meta_cols = ["vix_level", "vix_ret_5d", "vol_pct", "rel_ret60"]
    conf_clean = conf_df[meta_cols + ["correct", "year", "actual", "ens_pred"]].dropna()

    years = sorted(conf_clean["year"].unique())
    min_train_year = years[0] + 2  # need at least 2 years of meta-training data

    meta_results = []
    for test_year in years:
        if test_year < min_train_year:
            continue
        train = conf_clean[conf_clean["year"] < test_year]
        test  = conf_clean[conf_clean["year"] == test_year]
        if len(train) < 20 or len(test) < 5:
            continue

        X_tr = train[meta_cols].values
        y_tr = train["correct"].values
        X_te = test[meta_cols].values
        y_te = test["correct"].values

        sc = StandardScaler()
        X_tr = sc.fit_transform(X_tr)
        X_te = sc.transform(X_te)

        # Predict whether ensemble will be correct
        clf = LogisticRegression(max_iter=500, C=0.1)
        clf.fit(X_tr, y_tr)
        meta_proba = clf.predict_proba(X_te)[:, 1]
        meta_pred = (meta_proba > 0.5).astype(int)

        # Only trade when meta-classifier says "reliable" (meta_pred == 1)
        reliable = meta_pred == 1
        if reliable.sum() < 3:
            continue
        actual = test["actual"].values
        ens_pred = test["ens_pred"].values
        naive = actual.mean()
        edge_all    = (ens_pred == actual).mean() - naive
        edge_filtered = (ens_pred[reliable] == actual[reliable]).mean() - actual[reliable].mean()
        meta_results.append({
            "year": test_year, "n_all": len(test), "n_reliable": int(reliable.sum()),
            "edge_all": edge_all, "edge_filtered": edge_filtered
        })
        print(f"  {test_year}: all={len(test)} ({edge_all*100:+.1f}%), "
              f"filtered={reliable.sum()} ({edge_filtered*100:+.1f}%)")

    if meta_results:
        avg_all = np.mean([r["edge_all"] for r in meta_results])
        avg_filtered = np.mean([r["edge_filtered"] for r in meta_results])
        print(f"\n  Avg edge (all confident): {avg_all*100:+.2f}%")
        print(f"  Avg edge (meta-filtered): {avg_filtered*100:+.2f}%")


if __name__ == "__main__":
    main()
