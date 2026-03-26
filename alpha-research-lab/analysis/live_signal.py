"""
Live signal generator: what to buy at tomorrow's open.

Trains XGBoost on 2006-2025, then scores ALL stocks using today's (most recent)
OHLCV features. No future data required — features are purely backward-looking.

Usage:
    conda run -n stocks python analysis/live_signal.py

Output:
    - Top-N stocks ranked by model proba
    - VIX filter status
    - Key features explaining each pick
    - Suggested hold period and position sizes (square weighting)
"""
import sys
import warnings
import glob
import json
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data_loader import load_data
from src.feature_engineering import (
    generate_features,
    _add_ma_dist, _add_rsi, _add_macd, _add_bb, _add_atr,
    _add_candle, _add_stoch, _add_adx, _add_hist_vol,
    _add_market_relative,
)
from src.model_factory import get_model

warnings.filterwarnings("ignore")

STOCK_DIR = Path("data/stock")
VIX_PATH  = Path("data/fx-commodities/fx_commodities_vix_1D.parquet")
VNI_FILE  = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
EXCLUDE   = {"VNINDEX", "VN30"}

START_DATE  = "2012-01-01"
TRAIN_YEAR  = 2025   # train on all data <= this year
TOP_N       = 5
MIN_PROBA   = 0.55
VIX_MIN     = 15.0
VIX_MAX     = 30.0
COST_RT     = 0.003  # 0.30% round-trip cost assumption

MODEL_CONFIG = {
    "data": {
        "target_col": "future_rel_barrier_5d",
        "start_date": START_DATE,
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
        "index_file": str(VNI_FILE),
        "rel_lag_days": [1, 2, 3, 5, 10, 20],
        "use_macro": False, "use_cross_sectional": False, "use_news": False,
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

FEATURE_COLS = [
    "ma_dist_5", "ma_dist_10", "ma_dist_20", "ma_dist_50",
    "rsi_14",
    "macd_line", "macd_signal_line", "macd_hist",
    "bb_width", "bb_pct",
    "atr_14",
    "candle_body", "upper_wick", "lower_wick", "gap",
    "stoch_k", "stoch_d",
    "adx", "di_diff",
    "hist_vol_5", "hist_vol_10", "hist_vol_20", "intraday_range",
    "rel_ret_1d", "rel_ret_2d", "rel_ret_3d", "rel_ret_5d", "rel_ret_10d", "rel_ret_20d",
    "idx_ret_1d", "idx_ret_2d", "idx_ret_3d", "idx_ret_5d", "idx_ret_10d", "idx_ret_20d",
]


def compute_features_for_scoring(df_raw: pd.DataFrame, feat_cfg: dict) -> pd.DataFrame:
    """Compute all feature columns WITHOUT requiring a target. Returns the last row."""
    df = df_raw.copy()
    df = _add_ma_dist(df, feat_cfg)
    df = _add_rsi(df, feat_cfg)
    df = _add_macd(df, feat_cfg)
    df = _add_bb(df, feat_cfg)
    df = _add_atr(df, feat_cfg)
    df = _add_candle(df, feat_cfg)
    df = _add_stoch(df, feat_cfg)
    df = _add_adx(df, feat_cfg)
    df = _add_hist_vol(df, feat_cfg)
    df = _add_market_relative(df, feat_cfg)
    return df


def load_training_data() -> tuple:
    """Load all stocks, generate features+target for training (drops last ~5 rows per stock)."""
    files = sorted(glob.glob(str(STOCK_DIR / "gia_lich_su_*_1D.parquet")))
    frames = []
    for f in files:
        ticker = Path(f).stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        cfg = json.loads(json.dumps(MODEL_CONFIG))
        try:
            df_raw = load_data(f, START_DATE)
            if len(df_raw) < 300:
                continue
            df_feat = generate_features(df_raw, cfg)
            if len(df_feat) < 100:
                continue
            df_feat["ticker"] = ticker
            frames.append(df_feat)
        except Exception:
            continue
    all_df = pd.concat(frames, ignore_index=True)
    return all_df, len(frames)


def load_scoring_data() -> pd.DataFrame:
    """Load all stocks, compute features for the LATEST available date (no target needed)."""
    files = sorted(glob.glob(str(STOCK_DIR / "gia_lich_su_*_1D.parquet")))
    feat_cfg = MODEL_CONFIG["features"]
    records = []
    for f in files:
        ticker = Path(f).stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        try:
            df_raw = load_data(f, START_DATE)
            if len(df_raw) < 300:
                continue
            df_feat = compute_features_for_scoring(df_raw, feat_cfg)
            # Take the last row (most recent date)
            last = df_feat.iloc[[-1]].copy()
            last["ticker"] = ticker
            records.append(last)
        except Exception:
            continue
    if not records:
        return pd.DataFrame()
    return pd.concat(records, ignore_index=True)


def square_weights(probas: np.ndarray) -> np.ndarray:
    w = np.maximum(probas - 0.5, 1e-6) ** 2
    return w / w.sum()


def get_vix_today() -> float:
    try:
        vix = pd.read_parquet(VIX_PATH, columns=["time", "close"])
        vix["time"] = pd.to_datetime(vix["time"])
        vix = vix.sort_values("time")
        latest = vix.iloc[-1]
        return float(latest["close"]), str(latest["time"].date())
    except Exception:
        return float("nan"), "unknown"


def describe_feature(name: str, val: float) -> str:
    """Human-readable interpretation of a feature value."""
    if "ma_dist" in name:
        w = name.split("_")[-1]
        direction = "above" if val > 0 else "below"
        return f"{val*100:+.1f}% {direction} {w}d MA"
    if name == "rsi_14":
        level = "oversold" if val < 40 else ("overbought" if val > 60 else "neutral")
        return f"RSI={val:.0f} ({level})"
    if name == "macd_hist":
        return f"MACD hist={val*100:+.2f}% ({'bullish' if val > 0 else 'bearish'})"
    if name == "bb_pct":
        return f"BB position={val:.2f} ({'upper half' if val > 0.5 else 'lower half'})"
    if "rel_ret_5d" in name:
        return f"5d excess vs VNI={val*100:+.2f}%"
    if "rel_ret_1d" in name:
        return f"1d excess vs VNI={val*100:+.2f}%"
    if "hist_vol_20" in name:
        return f"20d realized vol={val*100:.1f}%/day"
    if name == "candle_body":
        return f"candle body={val:+.2f} ({'bullish' if val > 0 else 'bearish'})"
    if name == "adx":
        strength = "strong trend" if val > 0.25 else "weak/ranging"
        return f"ADX={val*100:.0f} ({strength})"
    return f"{name}={val:.4f}"


def main():
    print("\n" + "="*65)
    print("LIVE SIGNAL — What to buy at tomorrow's open")
    print("="*65)

    # --- VIX check ---
    vix_val, vix_date = get_vix_today()
    print(f"\nVIX check (last available: {vix_date}): {vix_val:.1f}")
    vix_ok = VIX_MIN <= vix_val <= VIX_MAX
    if vix_ok:
        print(f"  VIX [{VIX_MIN:.0f}, {VIX_MAX:.0f}]: PASS — signal is active")
    else:
        if vix_val < VIX_MIN:
            print(f"  VIX < {VIX_MIN:.0f}: market too calm — signal filter OFF, no trades today")
        else:
            print(f"  VIX > {VIX_MAX:.0f}: market too stressed — signal filter OFF, no trades today")

    # --- Step 1: Train model ---
    print(f"\nLoading training data (2012-{TRAIN_YEAR})...")
    all_df, n_stocks = load_training_data()
    all_df["_year"] = pd.to_datetime(all_df["time"]).dt.year
    train_df = all_df[all_df["_year"] <= TRAIN_YEAR].copy()
    print(f"  {n_stocks} stocks loaded | {len(train_df):,} training rows")

    target_col  = MODEL_CONFIG["data"]["target_col"]
    X_train = train_df[FEATURE_COLS].replace([np.inf, -np.inf], np.nan).fillna(0)
    y_train = train_df[target_col]
    valid   = y_train.notna() & np.isfinite(y_train)
    X_train, y_train = X_train[valid], y_train[valid]

    n_val = max(500, int(len(X_train) * 0.12))
    X_tr, y_tr = X_train.iloc[:-n_val], y_train.iloc[:-n_val]
    X_v,  y_v  = X_train.iloc[-n_val:], y_train.iloc[-n_val:]

    print(f"Training XGBoost on {len(X_tr):,} rows...")
    model = get_model(MODEL_CONFIG)
    model.fit(X_tr, y_tr, eval_set=[(X_v, y_v)], verbose=False)
    print(f"  Done.")

    # --- Step 2: Score latest data ---
    print(f"\nComputing features for latest available date (all {n_stocks} stocks)...")
    score_df = load_scoring_data()
    score_df["time"] = pd.to_datetime(score_df["time"])
    signal_date = score_df["time"].max().date()
    print(f"  Signal date: {signal_date} ({score_df['ticker'].nunique()} stocks)")

    # Filter to the most recent common date (or close to it)
    max_date = score_df["time"].max()
    # Allow up to 2 days lag (some stocks may have slightly older data)
    score_df = score_df[score_df["time"] >= max_date - pd.Timedelta(days=5)].copy()
    print(f"  Scoring {len(score_df)} stocks from last 5 calendar days")

    X_score = score_df[FEATURE_COLS].replace([np.inf, -np.inf], np.nan).fillna(0)
    score_df["proba"] = model.predict_proba(X_score)[:, 1]

    # --- Step 3: Rank and filter ---
    score_df = score_df.sort_values("proba", ascending=False).reset_index(drop=True)
    top_all  = score_df.head(20)   # top 20 before proba filter
    top_pass = score_df[score_df["proba"] >= MIN_PROBA].head(TOP_N)

    print(f"\n{'='*65}")
    print(f"FULL RANKING — Top 20 stocks by model score")
    print(f"{'='*65}")
    print(f"  {'Rank':<5} {'Ticker':<8} {'Proba':>6}  {'Signal date':<12} {'ma_dist_5':>10}  {'rel_ret_5d':>10}  {'rsi_14':>7}")
    print(f"  {'-'*65}")
    for i, row in top_all.iterrows():
        flag = " <-- BUY" if row["proba"] >= MIN_PROBA and (i < TOP_N) else ""
        print(f"  {i+1:<5} {row['ticker']:<8} {row['proba']:>6.3f}  "
              f"{str(row['time'].date()):<12} "
              f"{row['ma_dist_5']*100:>+9.2f}%  "
              f"{row['rel_ret_5d']*100:>+9.2f}%  "
              f"{row['rsi_14']:>7.1f}"
              f"{flag}")

    print(f"\n{'='*65}")
    if not vix_ok:
        print(f"TRADE SIGNAL: NO TRADE (VIX={vix_val:.1f} outside [{VIX_MIN:.0f},{VIX_MAX:.0f}])")
        print(f"{'='*65}")
        print(f"\nModel is running but VIX filter blocks execution.")
        print(f"The top-ranked stocks above are what the model would pick IF VIX were in range.")
        return

    if len(top_pass) < TOP_N:
        print(f"TRADE SIGNAL: NO TRADE")
        print(f"  Only {len(top_pass)} stocks pass proba >= {MIN_PROBA} (need {TOP_N})")
        print(f"{'='*65}")
        return

    print(f"TRADE SIGNAL: BUY at tomorrow's open (T+1 opening auction)")
    print(f"{'='*65}")

    weights = square_weights(top_pass["proba"].values)

    print(f"\n  Strategy: Square-weighted, top-{TOP_N}, VIX={vix_val:.1f} (PASS)")
    print(f"  Signal date: {signal_date} | Entry: tomorrow open | Exit: day+2 open")
    print(f"  Estimated gross/trade: +0.26% (2026 avg) | Breakeven RT cost: ~0.26%")
    print()
    print(f"  {'#':<3} {'Ticker':<8} {'Proba':>6}  {'Weight':>7}  {'Implied allocation'}")
    print(f"  {'-'*55}")
    for i, (_, row) in enumerate(top_pass.iterrows()):
        w = weights[i]
        print(f"  {i+1:<3} {row['ticker']:<8} {row['proba']:>6.3f}  {w*100:>6.1f}%  "
              f"e.g. {w*100:.1f}% of portfolio")

    print(f"\n  Why each stock was selected:")
    print(f"  {'-'*55}")
    key_features = ["ma_dist_5", "rel_ret_5d", "rel_ret_1d", "rsi_14",
                    "macd_hist", "candle_body", "hist_vol_20"]
    for i, (_, row) in enumerate(top_pass.iterrows()):
        print(f"\n  {i+1}. {row['ticker']} (proba={row['proba']:.3f}, weight={weights[i]*100:.1f}%)")
        for feat in key_features:
            if feat in row and not np.isnan(row[feat]):
                print(f"     - {describe_feature(feat, row[feat])}")

    print(f"\n{'='*65}")
    print(f"HOLD PERIOD GUIDANCE")
    print(f"{'='*65}")
    print(f"  Baseline (H=1): Enter tomorrow open, exit day-after-tomorrow open.")
    print(f"    - Daily turnover ~88% (K=10 stay-in reduces churn)")
    print(f"    - Breakeven cost: ~0.70% RT (historical avg)")
    print(f"    - Gross/trade (2026 so far): +0.26%")
    print(f"    - Net/trade at 0.30% RT: -0.04% (marginal — monitor closely)")
    print()
    print(f"  H=2 or H=3 (untested — see H78 proposal):")
    print(f"    - Would reduce turnover and may improve net edge")
    print(f"    - Not yet validated — use H=1 until H78 is run")
    print()
    print(f"  Key execution constraint (H74): MUST enter at T+1 OPEN (opening auction).")
    print(f"  Entering at T+2 kills the edge entirely.")
    print(f"\n  IMPORTANT: This is a quantitative signal, not financial advice.")
    print(f"  The 2026 strategy is in MONITORED DEPLOYMENT — keep position sizes small.")


if __name__ == "__main__":
    main()
