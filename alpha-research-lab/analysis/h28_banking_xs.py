"""
H28: Sector-specific XS walk-forward — banking stocks only.

Hypothesis: Training on a homogeneous sector (banking) should give
cleaner cross-sectional momentum signals than training on all 52 stocks.
Banks tend to move together (same rate sensitivity), so relative momentum
within the sector may be more predictable.

Banking universe (12 tickers): ACB, BID, CTG, EIB, HDB, MBB, SHB, STB, TCB, TPB, VCB, VPB
Target: EIB and STB (top-2 performers from H23 analysis)

Usage:
    conda run -n stocks python analysis/h28_banking_xs.py
"""
import json
import glob
import numpy as np
import pandas as pd
from pathlib import Path
from path_utils import data_path
from datetime import datetime
from scipy.stats import binomtest

from src.data_loader import load_data
from src.feature_engineering import generate_features, get_feature_columns
from src.model_factory import get_model

# Banking sector tickers in our universe
BANKING = ["ACB", "BID", "CTG", "EIB", "HDB", "MBB", "SHB", "STB", "TCB", "TPB", "VCB", "VPB"]

DATA_DIR = data_path("stock")
OUT_FILE = "xs_wf_results.jsonl"

BASE_CONFIG = {
    "data": {
        "target_col": "future_rel_barrier_5d",
        "test_size": 0.15, "val_size": 0.15,
        "start_date": "2012-01-01",
    },
    "features": {
        "base_cols": [],
        "use_lags": False,
        "use_ma": False, "use_ma_dist": True, "ma_windows": [5, 10, 20, 50],
        "use_rsi": True, "use_macd": True, "use_bb": True, "use_atr": True,
        "use_candle": True, "use_stoch": True, "use_willr": False, "use_adx": True,
        "use_hist_vol": True, "hist_vol_windows": [5, 10, 20],
        "use_cci": False, "use_volume_signals": False,
        "use_market_relative": True,
        "index_file": "data/stock/gia_lich_su_VNINDEX_1D.parquet",
        "rel_lag_days": [1, 2, 3, 5, 10, 20],
        "barrier_pct": 0.01,
    },
    "model": {
        "type": "xgboost_classifier",
        "params": {
            "n_estimators": 500, "max_depth": 3, "learning_rate": 0.05,
            "subsample": 0.8, "colsample_bytree": 0.8, "early_stopping_rounds": 30
        }
    }
}


def load_banking_stocks(start_date: str = "2012-01-01") -> pd.DataFrame:
    frames = []
    for ticker in BANKING:
        f = str(DATA_DIR / f"gia_lich_su_{ticker}_1D.parquet")
        if not Path(f).exists():
            print(f"  [SKIP] {ticker}: file not found")
            continue
        config = json.loads(json.dumps(BASE_CONFIG))
        config["data"]["file_path"] = f
        config["data"]["start_date"] = start_date
        try:
            df_raw = load_data(f, start_date)
            if len(df_raw) < 300:
                continue
            df_feat = generate_features(df_raw, config)
            if len(df_feat) < 100:
                continue
            df_feat["ticker"] = ticker
            frames.append(df_feat)
            print(f"  {ticker}: {len(df_feat)} rows")
        except Exception as e:
            print(f"  [WARN] {ticker}: {e}")

    all_df = pd.concat(frames, ignore_index=True)
    print(f"Banking XS: {len(frames)} stocks, {len(all_df):,} total rows")
    return all_df


def run():
    print("=" * 70)
    print("H28: BANKING-SECTOR-ONLY XS WALK-FORWARD")
    print(f"Tickers: {BANKING}")
    print("Target: future_rel_barrier_5d (±1%)")
    print("=" * 70)

    all_df = load_banking_stocks()
    target_col = "future_rel_barrier_5d"
    feature_cols = get_feature_columns(all_df, BASE_CONFIG)
    print(f"Features ({len(feature_cols)}): {feature_cols}")

    all_df["_year"] = pd.to_datetime(all_df["time"]).dt.year
    start_year = int(all_df["_year"].min()) + 3
    end_year   = int(all_df["_year"].max())
    if end_year == datetime.now().year:
        end_year -= 1

    per_year = []
    all_ticker_probas = []

    # Track accuracy for key tickers of interest
    TARGETS = ["EIB", "STB", "MBB", "VCB", "ACB"]

    print(f"\n  {'year':>5}  {'n_test':>8}  {'all_acc':>8}  ", end="")
    for t in TARGETS:
        print(f"  {t:>3}_edge", end="")
    print()
    print("  " + "-"*80)

    for test_year in range(start_year, end_year + 1):
        train_mask = all_df["_year"] < test_year
        test_mask  = all_df["_year"] == test_year

        train_df = all_df[train_mask].copy()
        test_df  = all_df[test_mask].copy()

        if len(train_df) < 200 or len(test_df) < 30:
            continue

        X_train = train_df[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0)
        y_train = train_df[target_col]
        X_test  = test_df[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0)
        y_test  = test_df[target_col]

        n_val = max(30, int(len(X_train) * 0.12))
        X_tr, y_tr = X_train.iloc[:-n_val], y_train.iloc[:-n_val]
        X_v,  y_v  = X_train.iloc[-n_val:], y_train.iloc[-n_val:]

        model = get_model(BASE_CONFIG)
        model.fit(X_tr, y_tr, eval_set=[(X_v, y_v)], verbose=False)

        preds  = model.predict(X_test)
        probas = model.predict_proba(X_test)[:, 1]

        overall_acc = (preds == y_test.values).mean()
        naive_all   = y_test.mean()

        # Save all ticker probas
        tickers_arr = test_df["ticker"].values
        times_arr   = test_df["time"].values
        y_arr       = y_test.values
        for tick, d, p, y_val in zip(tickers_arr, times_arr, probas, y_arr):
            all_ticker_probas.append({
                "time": d, "year": test_year, "ticker": tick,
                "xs_proba": round(float(p), 4), "actual": int(y_val),
            })

        print(f"  {test_year:>5}  {len(test_df):>8,}  {overall_acc*100:>7.2f}%", end="")
        for t in TARGETS:
            t_mask = test_df["ticker"] == t
            if t_mask.sum() < 10:
                print(f"  {'N/A':>8}", end="")
                continue
            y_t   = y_test[t_mask]
            p_t   = preds[t_mask.values]
            prob_t = probas[t_mask.values]
            naive_t = y_t.mean()

            conf_t = np.abs(prob_t - 0.5) > 0.05
            if conf_t.sum() >= 5:
                acc_t  = (p_t[conf_t] == y_t.values[conf_t]).mean()
                edge_t = acc_t - naive_t
            else:
                edge_t = float("nan")
            print(f"  {edge_t*100:>+8.2f}%" if not np.isnan(edge_t) else f"  {'LOW-C':>8}", end="")

        print()
        per_year.append({
            "year": test_year,
            "n_total": len(test_df),
            "overall_acc": round(overall_acc, 4),
        })

    # Save all-ticker probas
    if all_ticker_probas:
        all_proba_df = pd.DataFrame(all_ticker_probas)
        all_proba_df["time"] = pd.to_datetime(all_proba_df["time"])
        out_path = str(data_path("features/xs_banking_barrier_all_probas.parquet"))
        all_proba_df.to_parquet(out_path, index=False)
        n_t = all_proba_df["ticker"].nunique()
        print(f"\n  Banking XS probas saved: {out_path} ({len(all_proba_df):,} rows, {n_t} tickers)")

    # Summary per-ticker
    if all_ticker_probas:
        df_all = pd.DataFrame(all_ticker_probas)
        print(f"\n  Per-ticker summary (conf threshold=0.05):")
        print(f"  {'ticker':>8}  {'avg_edge':>10}  {'sharpe':>8}  {'n_sig':>7}  {'trades_yr':>10}")
        print("  " + "-" * 55)
        for ticker in sorted(df_all["ticker"].unique()):
            t_df = df_all[df_all["ticker"] == ticker]
            per_yr_t = []
            for year, grp in t_df.groupby("year"):
                if year < 2015:
                    continue
                naive = grp["actual"].mean()
                conf = np.abs(grp["xs_proba"] - 0.5) > 0.05
                n = conf.sum()
                if n < 5:
                    continue
                pred  = (grp["xs_proba"].values[conf] > 0.5).astype(int)
                actual = grp["actual"].values[conf]
                acc   = (pred == actual).mean()
                edge  = acc - naive
                pval  = binomtest(int((pred == actual).sum()), n, naive).pvalue
                per_yr_t.append({"edge": edge, "n": n, "pval": pval})
            if not per_yr_t:
                continue
            edges = [r["edge"] for r in per_yr_t]
            n_sig = sum(1 for r in per_yr_t if r["pval"] < 0.05)
            avg = np.mean(edges)
            std = np.std(edges) if len(edges) > 1 else float("nan")
            sharpe = avg / std if std > 0 else float("nan")
            trades_yr = np.mean([r["n"] for r in per_yr_t])
            print(f"  {ticker:>8}  {avg*100:>+9.2f}%  {sharpe:>8.2f}  {n_sig:>3}/{len(per_yr_t)}  {trades_yr:>9.0f}")


if __name__ == "__main__":
    run()
