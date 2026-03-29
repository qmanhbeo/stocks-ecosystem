"""
Build current-year live extension for the canonical H93 / S1 panel.

The historical S1 artifact is an expanding walk-forward panel that intentionally
stops before the current calendar year. This tool trains the same H93 config on
all rows from prior years, then scores every row in the current year, keeping
`actual` where the forward label is already known and leaving it missing for the
latest unlabeled live rows.

Output:
    data/features/xs_barrier_vol_1d_hose_live_current.parquet

Usage:
    conda run -n stocks python data_tools/build_s1_live_extension.py
"""

from __future__ import annotations

import glob
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_loader import load_data
from src.feature_engineering import (
    _add_adx,
    _add_atr,
    _add_bb,
    _add_candle,
    _add_hist_vol,
    _add_ma_dist,
    _add_macd,
    _add_market_relative,
    _add_rsi,
    _add_stoch,
    _add_volume_signals,
    _make_target,
    get_feature_columns,
)
from src.model_factory import get_model

STOCK_DIR = ROOT / "data" / "stock"
OUT_PATH = ROOT / "data" / "features" / "xs_barrier_vol_1d_hose_live_current.parquet"
VNI_FILE = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
EXCLUDE = {"VNINDEX", "VN30"}
START_DATE = "2012-01-01"
CURRENT_YEAR = pd.Timestamp.now().year

MODEL_CONFIG = {
    "data": {
        "target_col": "future_rel_barrier_1d",
        "test_size": 0.15,
        "val_size": 0.15,
        "start_date": START_DATE,
    },
    "features": {
        "base_cols": [],
        "use_lags": False,
        "use_ma": False,
        "use_ma_dist": True,
        "ma_windows": [5, 10, 20, 50],
        "use_rsi": True,
        "use_macd": True,
        "use_bb": True,
        "use_atr": True,
        "use_candle": True,
        "use_stoch": True,
        "use_willr": False,
        "use_adx": True,
        "use_hist_vol": True,
        "hist_vol_windows": [5, 10, 20],
        "use_cci": False,
        "use_volume_signals": True,
        "use_market_relative": True,
        "index_file": str(VNI_FILE),
        "rel_lag_days": [1, 2, 3, 5, 10, 20],
        "use_macro": False,
        "use_cross_sectional": False,
        "use_news": False,
        "barrier_pct": 0.01,
    },
    "model": {
        "type": "xgboost_classifier",
        "params": {
            "n_estimators": 500,
            "max_depth": 3,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "early_stopping_rounds": 30,
        },
    },
}


def load_all_stocks() -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for file_path in sorted(glob.glob(str(STOCK_DIR / "gia_lich_su_*_1D.parquet"))):
        ticker = Path(file_path).stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        config = json.loads(json.dumps(MODEL_CONFIG))
        config["data"]["file_path"] = file_path
        try:
            raw = load_data(file_path, START_DATE)
            if len(raw) < 300:
                continue
            feat = build_features_with_live_rows(raw, config)
            if len(feat) < 100:
                continue
            feat["ticker"] = ticker
            parts.append(feat)
        except Exception:
            continue

    if not parts:
        raise RuntimeError("No stock features were built for S1 live extension.")
    return pd.concat(parts, ignore_index=True)


def build_features_with_live_rows(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    feat_cfg = config.get("features", {})
    target_col = config.get("data", {}).get("target_col", "future_return_5d")

    work = df.copy()
    work = _make_target(work, target_col, config)
    if feat_cfg.get("use_ma_dist", False):
        work = _add_ma_dist(work, feat_cfg)
    if feat_cfg.get("use_rsi", False):
        work = _add_rsi(work, feat_cfg)
    if feat_cfg.get("use_macd", False):
        work = _add_macd(work, feat_cfg)
    if feat_cfg.get("use_bb", False):
        work = _add_bb(work, feat_cfg)
    if feat_cfg.get("use_atr", False):
        work = _add_atr(work, feat_cfg)
    if feat_cfg.get("use_volume_signals", False):
        work = _add_volume_signals(work, feat_cfg)
    if feat_cfg.get("use_candle", False):
        work = _add_candle(work, feat_cfg)
    if feat_cfg.get("use_stoch", False):
        work = _add_stoch(work, feat_cfg)
    if feat_cfg.get("use_adx", False):
        work = _add_adx(work, feat_cfg)
    if feat_cfg.get("use_hist_vol", False):
        work = _add_hist_vol(work, feat_cfg)
    if feat_cfg.get("use_market_relative", False):
        work = _add_market_relative(work, feat_cfg)

    feature_cols = get_feature_columns(work, config)
    required_cols = ["time", "open", "high", "low", "close", "volume"] + feature_cols
    keep = work.dropna(subset=[column for column in required_cols if column in work.columns]).reset_index(drop=True)
    return keep


def main() -> None:
    print("Building current-year S1 live extension...")
    all_df = load_all_stocks()
    all_df["_year"] = pd.to_datetime(all_df["time"]).dt.year

    feature_cols = get_feature_columns(all_df, MODEL_CONFIG)
    target_col = MODEL_CONFIG["data"]["target_col"]

    train_df = all_df.loc[all_df["_year"] < CURRENT_YEAR].copy()
    score_df = all_df.loc[all_df["_year"] == CURRENT_YEAR].copy()
    if score_df.empty:
        raise RuntimeError(f"No rows found for current year {CURRENT_YEAR}")

    x_train = train_df[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0)
    y_train = pd.to_numeric(train_df[target_col], errors="coerce")
    valid_train = y_train.notna() & np.isfinite(y_train) & (y_train.abs() < 10)
    x_train = x_train.loc[valid_train]
    y_train = y_train.loc[valid_train]
    if len(x_train) < 1_000:
        raise RuntimeError(f"Too few valid training rows for S1 live extension: {len(x_train):,}")

    x_score = score_df[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0)
    y_score = pd.to_numeric(score_df[target_col], errors="coerce")
    valid_actual = y_score.notna() & np.isfinite(y_score) & (y_score.abs() < 10)

    n_val = max(500, int(len(x_train) * 0.12))
    x_tr, y_tr = x_train.iloc[:-n_val], y_train.iloc[:-n_val]
    x_val, y_val = x_train.iloc[-n_val:], y_train.iloc[-n_val:]

    model = get_model(MODEL_CONFIG)
    model.fit(x_tr, y_tr, eval_set=[(x_val, y_val)], verbose=False)
    probas = model.predict_proba(x_score)[:, 1]

    actual = pd.Series(pd.NA, index=score_df.index, dtype="Int64")
    actual.loc[valid_actual] = y_score.loc[valid_actual].round().astype("Int64")

    out = pd.DataFrame(
        {
            "time": pd.to_datetime(score_df["time"].values),
            "year": int(CURRENT_YEAR),
            "ticker": score_df["ticker"].values,
            "xs_proba": np.round(probas, 4),
            "actual": actual.to_numpy(),
        }
    ).sort_values(["time", "ticker"]).reset_index(drop=True)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT_PATH, index=False)

    latest_labeled = out.loc[out["actual"].notna(), "time"].max()
    latest_scored = out["time"].max()
    print(f"saved {len(out):,} rows -> {OUT_PATH}")
    print(f"date range: {out['time'].min().date()} -> {latest_scored.date()}")
    if pd.notna(latest_labeled):
        print(f"latest labeled date: {pd.Timestamp(latest_labeled).date()}")
    print(f"tickers: {out['ticker'].nunique()}")


if __name__ == "__main__":
    main()
