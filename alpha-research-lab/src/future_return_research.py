from __future__ import annotations

import glob
from pathlib import Path

import pandas as pd
from path_utils import data_path

from src.data_loader import load_data
from src.feature_engineering import generate_features
from src.repo_paths import artifact_path


STOCK_DIR = data_path("stock")
INDEX_FILE = data_path("stock/gia_lich_su_VNINDEX_1D.parquet")
EXCLUDE = {"VNINDEX", "VN30"}
CACHE_PATH = artifact_path("cache/future_rel_return_5d_hose.parquet")

CFG = {
    "data": {"target_col": "future_rel_dir_5d", "start_date": "2012-01-01"},
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
        "use_volume_signals": False,
        "use_market_relative": True,
        "index_file": str(INDEX_FILE),
        "rel_lag_days": [1, 2, 3, 5, 10, 20],
        "use_macro": False,
        "use_cross_sectional": False,
        "use_news": False,
    },
    "model": {"type": "xgboost_classifier", "params": {}},
}


def _build_future_rel_5d() -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for path in sorted(glob.glob(str(STOCK_DIR / "gia_lich_su_*_1D.parquet"))):
        ticker = Path(path).stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        raw = load_data(path, "2012-01-01")
        if len(raw) < 300:
            continue
        feat = generate_features(raw, CFG)
        if "future_rel_return_5d" not in feat.columns:
            continue
        part = feat[["time", "future_rel_return_5d"]].assign(ticker=ticker)
        parts.append(part)
    if not parts:
        return pd.DataFrame(columns=["time", "ticker", "fwd_rel_5d"])
    out = pd.concat(parts, ignore_index=True)
    out = out.rename(columns={"future_rel_return_5d": "fwd_rel_5d"})
    out["time"] = pd.to_datetime(out["time"], errors="coerce").dt.normalize()
    return out.sort_values(["time", "ticker"]).reset_index(drop=True)


def load_future_rel_5d(*, start_year: int | None = None, end_year: int | None = None) -> pd.DataFrame:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if CACHE_PATH.exists():
        frame = pd.read_parquet(CACHE_PATH).copy()
    else:
        frame = _build_future_rel_5d()
        frame.to_parquet(CACHE_PATH, index=False)

    frame["time"] = pd.to_datetime(frame["time"], errors="coerce").dt.normalize()
    if start_year is not None:
        frame = frame.loc[frame["time"].dt.year >= int(start_year)].copy()
    if end_year is not None:
        frame = frame.loc[frame["time"].dt.year <= int(end_year)].copy()
    return frame.reset_index(drop=True)
