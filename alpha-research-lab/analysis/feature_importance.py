"""
feature_importance.py -- Train cross-sectional model on all data and show feature importances.

This uses the full dataset (no walk-forward) to get stable importance estimates.
Run: conda run -n stocks python feature_importance.py
"""
import glob
import json
import numpy as np
import pandas as pd
from pathlib import Path
from path_utils import data_path
from xgboost import XGBClassifier

from src.data_loader import load_data
from src.feature_engineering import generate_features, get_feature_columns

DATA_DIR = data_path("stock")
EXCLUDE  = {"VNINDEX", "VN30"}

BASE_CONFIG = {
    "data": {
        "target_col": "future_rel_dir_5d",
        "test_size": 0.15, "val_size": 0.15,
        "start_date": "2016-01-01",
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
        "use_macro": False,
        "use_cross_sectional": False,
        "use_news": False,
    },
    "model": {
        "type": "xgboost_classifier",
        "params": {
            "n_estimators": 300, "max_depth": 3, "learning_rate": 0.05,
            "subsample": 0.8, "colsample_bytree": 0.8,
        }
    }
}


def main():
    files = sorted(glob.glob(str(DATA_DIR / "gia_lich_su_*_1D.parquet")))
    frames = []
    for f in files:
        ticker = Path(f).stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        config = json.loads(json.dumps(BASE_CONFIG))
        config["data"]["file_path"] = f
        try:
            df_raw = load_data(f, "2016-01-01")
            if len(df_raw) < 200:
                continue
            df_feat = generate_features(df_raw, config)
            df_feat["ticker"] = ticker
            frames.append(df_feat)
        except Exception as e:
            print(f"  [WARN] {ticker}: {e}")

    all_df = pd.concat(frames, ignore_index=True)
    target_col   = "future_rel_dir_5d"
    feature_cols = get_feature_columns(all_df, BASE_CONFIG)
    print(f"Training on {len(all_df):,} rows, {len(feature_cols)} features")

    X = all_df[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0)
    y = all_df[target_col]

    # Use last 20% as holdout
    n = len(X)
    split = int(n * 0.8)
    model = XGBClassifier(
        n_estimators=300, max_depth=3, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        eval_metric="logloss", early_stopping_rounds=30,
        verbosity=0,
    )
    model.fit(
        X.iloc[:split], y.iloc[:split],
        eval_set=[(X.iloc[split:], y.iloc[split:])],
        verbose=False,
    )

    imp = pd.Series(model.feature_importances_, index=feature_cols)
    imp = imp.sort_values(ascending=False)

    print(f"\n{'='*55}")
    print(f"FEATURE IMPORTANCES (cross-sectional model, gain)")
    print(f"{'='*55}")
    for feat, val in imp.items():
        bar = "#" * int(val * 500)
        print(f"  {feat:<28} {val:.4f}  {bar}")

    # Group summary
    groups = {
        "rel_momentum": [c for c in imp.index if c.startswith("rel_ret") or c.startswith("idx_ret")],
        "tech_oscillators": ["rsi_14", "macd_line", "macd_signal_line", "macd_hist",
                             "stoch_k", "stoch_d", "adx", "di_diff"],
        "vol_features": ["bb_width", "bb_pct", "atr_14",
                         "hist_vol_5", "hist_vol_10", "hist_vol_20", "intraday_range"],
        "ma_features": [c for c in imp.index if c.startswith("ma_dist")],
        "candle": ["candle_body", "upper_wick", "lower_wick", "gap"],
    }
    print(f"\n  GROUP SUMMARY")
    print(f"  {'Group':<25} {'Total Imp':>10}  {'Avg/Feature':>12}")
    print("  " + "-" * 50)
    for grp, cols in groups.items():
        valid = [c for c in cols if c in imp.index]
        total = imp[valid].sum()
        avg   = imp[valid].mean() if valid else 0
        print(f"  {grp:<25} {total:>10.4f}  {avg:>12.4f}")


if __name__ == "__main__":
    main()
