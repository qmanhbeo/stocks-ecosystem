import pandas as pd
import numpy as np
from typing import List, Dict, Any
from src.repo_paths import resolve_data_path


# ---------------------------------------------------------------------------
# Vietnam-specific calendar constants
# ---------------------------------------------------------------------------

# Tet (Lunar New Year) first day — primary market discontinuity in Vietnam
TET_DATES = pd.to_datetime([
    "2010-02-14", "2011-02-03", "2012-01-23", "2013-02-10", "2014-01-31",
    "2015-02-19", "2016-02-08", "2017-01-28", "2018-02-16", "2019-02-05",
    "2020-01-25", "2021-02-12", "2022-02-01", "2023-01-22", "2024-02-10",
    "2025-01-29", "2026-02-17",  # 2026 estimate
])


# ---------------------------------------------------------------------------
# Target creation
# ---------------------------------------------------------------------------

def _make_target(df: pd.DataFrame, target_col: str, config: Dict[str, Any]) -> pd.DataFrame:
    """
    Compute the target column.
    Supported target_col patterns:
      future_return_Nd       : N-day price return (continuous)
      future_dir_Nd          : 1 if return > 0, else 0 (binary)
      future_vol_Nd          : absolute return magnitude (volatility proxy)
      future_rel_return_Nd   : FPT N-day return MINUS VN-Index N-day return (excess, continuous)
      future_rel_dir_Nd      : 1 if FPT outperforms VN-Index over N days, else 0 (binary, no drift)
      future_rel_barrier_Nd  : Triple barrier: 1 if FPT hits +profit_pct vs VNINDEX within N days,
                               0 if it hits -profit_pct first, NaN if neither (sample dropped)
                               Uses features.barrier_pct (default 0.015 = 1.5%)
    """
    try:
        horizon = int(target_col.split("_")[-1].replace("d", ""))
    except ValueError:
        horizon = 5

    if "future_rel_barrier_" in target_col:
        # Triple barrier: hit profit_pct above VNINDEX before hitting -profit_pct,
        # or use fixed-time horizon as timeout
        feat_cfg   = config.get("features", {})
        index_file = resolve_data_path(feat_cfg.get("index_file", "data/stock/gia_lich_su_VNINDEX_1D.parquet"))
        barrier_pct = feat_cfg.get("barrier_pct", 0.015)  # 1.5% relative gain/loss threshold

        idx = pd.read_parquet(index_file)[["time", "close"]].rename(columns={"close": "_idx_close"})
        df  = df.merge(idx, on="time", how="left")
        df["_idx_close"] = df["_idx_close"].ffill()

        labels = np.full(len(df), np.nan)
        fpt_prices = df["close"].values
        idx_prices = df["_idx_close"].values

        for i in range(len(df) - horizon):
            entry_fpt = fpt_prices[i]
            entry_idx = idx_prices[i]
            if entry_fpt <= 0 or entry_idx <= 0:
                continue
            label = np.nan
            for j in range(1, horizon + 1):
                fpt_ret_j = fpt_prices[i + j] / entry_fpt - 1
                idx_ret_j = idx_prices[i + j] / entry_idx - 1
                rel_ret_j = fpt_ret_j - idx_ret_j
                if rel_ret_j >= barrier_pct:
                    label = 1.0
                    break
                elif rel_ret_j <= -barrier_pct:
                    label = 0.0
                    break
            if np.isnan(label):
                # timeout: use fixed-time direction
                fpt_ret_h = fpt_prices[i + horizon] / entry_fpt - 1
                idx_ret_h = idx_prices[i + horizon] / entry_idx - 1
                label = float(fpt_ret_h - idx_ret_h > 0)
            labels[i] = label

        df[target_col] = labels

    elif "future_rel_" in target_col:
        # Load market index for relative target — removes absolute drift bias
        feat_cfg   = config.get("features", {})
        index_file = resolve_data_path(feat_cfg.get("index_file", "data/stock/gia_lich_su_VNINDEX_1D.parquet"))
        idx = pd.read_parquet(index_file)[["time", "close"]].rename(columns={"close": "_idx_close"})
        df  = df.merge(idx, on="time", how="left")
        df["_idx_close"] = df["_idx_close"].ffill()

        fpt_ret = df["close"].shift(-horizon) / df["close"] - 1
        idx_ret = df["_idx_close"].shift(-horizon) / df["_idx_close"] - 1
        rel_ret = fpt_ret - idx_ret
        df[f"future_rel_return_{horizon}d"] = rel_ret

        if "future_rel_dir_" in target_col:
            df[target_col] = (rel_ret > 0).astype(int)
        else:
            df[target_col] = rel_ret

    elif "future_dir_" in target_col:
        ret = df["close"].shift(-horizon) / df["close"] - 1
        df[f"future_return_{horizon}d"] = ret
        df[target_col] = (ret > 0).astype(int)

    elif "future_vol_" in target_col:
        df[target_col] = (df["close"].shift(-horizon) / df["close"] - 1).abs()

    else:
        df[target_col] = df["close"].shift(-horizon) / df["close"] - 1

    return df


# ---------------------------------------------------------------------------
# Feature groups
# ---------------------------------------------------------------------------

def _add_lags(df, cfg):
    for i in cfg.get("lag_days", [1, 2, 3, 5, 10]):
        df[f"past_return_{i}d"] = df["close"] / df["close"].shift(i) - 1
    return df


def _add_ma(df, cfg):
    """Raw moving average (non-stationary — kept for backward compat)."""
    for w in cfg.get("ma_windows", [5, 10, 20]):
        df[f"ma_{w}"] = df["close"].rolling(w).mean()
    return df


def _add_ma_dist(df, cfg):
    """Distance of close from MA: (close/MA - 1). Stationary."""
    for w in cfg.get("ma_windows", [5, 10, 20, 50]):
        df[f"ma_dist_{w}"] = df["close"] / df["close"].rolling(w).mean() - 1
    return df


def _add_rsi(df, cfg):
    p = cfg.get("rsi_period", 14)
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=p - 1, min_periods=p).mean()
    avg_loss = loss.ewm(com=p - 1, min_periods=p).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df[f"rsi_{p}"] = 100 - (100 / (1 + rs))
    return df


def _add_macd(df, cfg):
    fast = cfg.get("macd_fast", 12)
    slow = cfg.get("macd_slow", 26)
    sig  = cfg.get("macd_signal", 9)
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    macd_line = (ema_fast - ema_slow) / df["close"]   # price-normalized
    signal_line = macd_line.ewm(span=sig, adjust=False).mean()
    df["macd_line"] = macd_line
    df["macd_signal_line"] = signal_line
    df["macd_hist"] = macd_line - signal_line
    return df


def _add_bb(df, cfg):
    p    = cfg.get("bb_period", 20)
    nstd = cfg.get("bb_std", 2)
    ma   = df["close"].rolling(p).mean()
    std  = df["close"].rolling(p).std()
    upper = ma + nstd * std
    lower = ma - nstd * std
    band_width = (upper - lower).replace(0, np.nan)
    df["bb_width"] = (upper - lower) / ma          # vol proxy
    df["bb_pct"]   = (df["close"] - lower) / band_width  # 0=at lower, 1=at upper
    return df


def _add_atr(df, cfg):
    p = cfg.get("atr_period", 14)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift(1)).abs(),
        (df["low"]  - df["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    df[f"atr_{p}"] = tr.ewm(com=p - 1, min_periods=p).mean() / df["close"]
    return df


def _add_volume_signals(df, cfg):
    vol_ma = cfg.get("vol_ma_period", 20)
    vol_ma_mean = df["volume"].rolling(vol_ma).mean().replace(0, np.nan)
    df["vol_ratio"] = df["volume"] / vol_ma_mean
    price_dir = df["close"].diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    obv = (df["volume"] * price_dir).cumsum()
    obv_ma = obv.rolling(vol_ma).mean()
    df["obv_roc"] = (obv - obv_ma) / (obv_ma.abs() + 1)
    # H90: VWAP deviation — price vs 5-day rolling VWAP (typical price weighted by volume)
    typical = (df["high"] + df["low"] + df["close"]) / 3
    vwap_num = (typical * df["volume"]).rolling(5).sum()
    vwap_den = df["volume"].rolling(5).sum().replace(0, np.nan)
    vwap_5d = vwap_num / vwap_den
    df["vwap_dev_5d"] = df["close"] / vwap_5d - 1
    # H90: volume trend — 5d avg vs 20d avg (acceleration)
    vol_5d  = df["volume"].rolling(5).mean()
    df["vol_trend"] = vol_5d / vol_ma_mean - 1
    return df


# ---- New OHLCV features not tested in Sessions 1-2 ----

def _add_candle(df, cfg):
    """
    Candle body and wick ratios — pure price action from OHLCV.
    candle_body  : (close-open)/(high-low) +1=full bull candle, -1=full bear
    upper_wick   : fraction of range above the real body (rejection of highs)
    lower_wick   : fraction of range below the real body (rejection of lows)
    gap          : open/prev_close - 1 (overnight gap, positive=gap up)
    """
    hl = (df["high"] - df["low"]).replace(0, np.nan)
    df["candle_body"]  = (df["close"] - df["open"]) / hl
    df["upper_wick"]   = (df["high"] - df[["open","close"]].max(axis=1)) / hl
    df["lower_wick"]   = (df[["open","close"]].min(axis=1) - df["low"]) / hl
    df["gap"]          = df["open"] / df["close"].shift(1) - 1
    return df


def _add_stoch(df, cfg):
    """
    Stochastic oscillator — momentum using high/low range (different from RSI).
    %K: where is close within the N-day high-low range?
    %D: 3-day smoothing of %K.
    """
    p = cfg.get("stoch_period", 14)
    hh = df["high"].rolling(p).max()
    ll = df["low"].rolling(p).min()
    df["stoch_k"] = (df["close"] - ll) / (hh - ll).replace(0, np.nan) * 100
    df["stoch_d"] = df["stoch_k"].rolling(3).mean()
    return df


def _add_willr(df, cfg):
    """Williams %R: inverse of stochastic, range [-100, 0]. Near 0 = overbought."""
    p = cfg.get("willr_period", 14)
    hh = df["high"].rolling(p).max()
    ll = df["low"].rolling(p).min()
    df["willr"] = (hh - df["close"]) / (hh - ll).replace(0, np.nan) * -100
    return df


def _add_adx(df, cfg):
    """
    ADX (Average Directional Index): measures trend STRENGTH, not direction.
    adx    : 0-100, >25 = trending market, <20 = ranging market
    di_diff: +DI - -DI (positive = uptrend context, negative = downtrend context)
    """
    p = cfg.get("adx_period", 14)
    hl   = df["high"] - df["low"]
    h_pc = (df["high"] - df["close"].shift(1)).abs()
    l_pc = (df["low"]  - df["close"].shift(1)).abs()
    tr   = pd.concat([hl, h_pc, l_pc], axis=1).max(axis=1)

    up   = df["high"] - df["high"].shift(1)
    down = df["low"].shift(1) - df["low"]
    plus_dm  = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)

    atr14    = tr.ewm(com=p-1, min_periods=p).mean()
    plus_di  = plus_dm.ewm(com=p-1, min_periods=p).mean()  / atr14 * 100
    minus_di = minus_dm.ewm(com=p-1, min_periods=p).mean() / atr14 * 100

    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100)
    df["adx"]     = dx.ewm(com=p-1, min_periods=p).mean() / 100   # normalize to [0,1]
    df["di_diff"] = (plus_di - minus_di) / 100                    # sign = trend direction
    return df


def _add_hist_vol(df, cfg):
    """Realized (historical) volatility — rolling std of daily returns. Vol clusters."""
    windows = cfg.get("hist_vol_windows", [5, 10, 20])
    daily_ret = df["close"] / df["close"].shift(1) - 1
    for w in windows:
        df[f"hist_vol_{w}"] = daily_ret.rolling(w).std()
    # Intraday range as another vol proxy
    df["intraday_range"] = (df["high"] - df["low"]) / df["close"]
    return df


def _add_cci(df, cfg):
    """
    Commodity Channel Index: how far is typical price from its MA?
    Positive = above average (bullish), negative = below (bearish). Range roughly [-200, 200].
    """
    p = cfg.get("cci_period", 20)
    typical = (df["high"] + df["low"] + df["close"]) / 3
    tp_ma   = typical.rolling(p).mean()
    tp_mad  = typical.rolling(p).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    df["cci"] = (typical - tp_ma) / (0.015 * tp_mad.replace(0, np.nan))
    df["cci"] = df["cci"] / 200  # normalize to roughly [-1, 1]
    return df


# ---- External / cross-asset features ----

def _add_market_relative(df, cfg):
    """
    Load VN-Index (or other index) and compute FPT's RELATIVE performance.
    Idiosyncratic returns = FPT_return - market_return. May be more predictable.
    Also includes raw market returns as features (market context).
    """
    index_file = resolve_data_path(cfg.get("index_file", "data/stock/gia_lich_su_VNINDEX_1D.parquet"))
    lags = cfg.get("rel_lag_days", [1, 2, 3, 5, 10, 20])

    idx = pd.read_parquet(index_file)[["time", "close"]].rename(columns={"close": "idx_close"})
    df  = df.merge(idx, on="time", how="left")
    df["idx_close"] = df["idx_close"].ffill()  # fill market holidays

    # Relative returns (FPT excess vs market)
    for lag in lags:
        fpt_ret = df["close"] / df["close"].shift(lag) - 1
        idx_ret = df["idx_close"] / df["idx_close"].shift(lag) - 1
        df[f"rel_ret_{lag}d"]   = fpt_ret - idx_ret      # alpha
        df[f"idx_ret_{lag}d"]   = idx_ret                 # market context

    return df


def _add_macro(df, cfg):
    """
    Load macro/FX files and add their return features.
    cfg keys: macro_files = [{"path": "...", "alias": "gold"}, ...]
    """
    macro_files = cfg.get("macro_files", [])
    lag_days = cfg.get("macro_lag_days", [1, 5])

    for mf in macro_files:
        path  = resolve_data_path(mf["path"])
        alias = mf["alias"]
        try:
            ext = pd.read_parquet(path)[["time", "close"]].rename(columns={"close": f"{alias}_close"})
            df  = df.merge(ext, on="time", how="left")
            df[f"{alias}_close"] = df[f"{alias}_close"].ffill()
            for lag in lag_days:
                df[f"{alias}_ret_{lag}d"] = df[f"{alias}_close"] / df[f"{alias}_close"].shift(lag) - 1
        except Exception as e:
            print(f"  [WARN] Could not load macro file {path}: {e}")

    return df


# ---- Sector peer relative features ----

def _add_sector_peers(df, cfg):
    """
    Add peer stock relative returns as features.
    Hypothesis: sector momentum (IT peer outperformance) predicts FPT outperformance.

    For each peer ticker, compute:
      {peer}_rel_ret_{lag}d : peer's excess return vs VNINDEX over lag days

    cfg keys:
      peer_tickers : list of tickers, e.g. ["CMG", "MWG"]
      peer_data_dir: directory with stock parquet files
      peer_lag_days : list of lag days
      index_file   : VNINDEX parquet for relative return computation
    """
    peers     = cfg.get("peer_tickers", [])
    data_dir  = resolve_data_path(cfg.get("peer_data_dir", "data/stock"))
    lags      = cfg.get("peer_lag_days", [1, 5, 10, 20])
    idx_file  = resolve_data_path(cfg.get("index_file", "data/stock/gia_lich_su_VNINDEX_1D.parquet"))

    try:
        idx = pd.read_parquet(idx_file)[["time", "close"]].rename(columns={"close": "_idx_close"})
        idx["time"] = pd.to_datetime(idx["time"])
    except Exception:
        return df

    for ticker in peers:
        peer_file = data_dir / f"gia_lich_su_{ticker}_1D.parquet"
        try:
            peer = pd.read_parquet(peer_file)[["time", "close"]].rename(columns={"close": f"_{ticker}_close"})
            peer["time"] = pd.to_datetime(peer["time"])
            peer = peer.merge(idx, on="time", how="left")
            peer[f"_{ticker}_close"] = peer[f"_{ticker}_close"].ffill()
            peer["_idx_close"] = peer["_idx_close"].ffill()
            for lag in lags:
                peer_ret = peer[f"_{ticker}_close"] / peer[f"_{ticker}_close"].shift(lag) - 1
                idx_ret  = peer["_idx_close"] / peer["_idx_close"].shift(lag) - 1
                peer[f"{ticker}_rel_{lag}d"] = peer_ret - idx_ret
            peer_cols = ["time"] + [f"{ticker}_rel_{lag}d" for lag in lags]
            df = df.merge(peer[peer_cols], on="time", how="left")
        except Exception as e:
            print(f"  [WARN] Could not load peer {ticker}: {e}")

    return df


# ---- V1: Volatility regime filter (VNINDEX realized vol percentile) ----

def _add_vol_regime(df, cfg):
    """
    V1: VNINDEX realized volatility regime.
    Hypothesis: cross-sectional relative momentum predicts reliably when VNINDEX vol > 70th pct.

    vnindex_vol_20d  : VNINDEX 20d realized vol (std of daily returns)
    vnindex_vol_pct  : rolling 252d percentile rank of that vol (0=calm, 1=crisis)
    high_vol_regime  : 1 if vnindex_vol_pct > 0.70
    """
    index_file = resolve_data_path(cfg.get("index_file", "data/stock/gia_lich_su_VNINDEX_1D.parquet"))
    vol_window = cfg.get("vol_regime_window", 20)
    pct_window = cfg.get("vol_pct_window", 252)

    idx = pd.read_parquet(index_file)[["time", "close"]].rename(columns={"close": "_vr_close"})
    idx["time"] = pd.to_datetime(idx["time"])
    df_t = pd.to_datetime(df["time"])

    # Build vol series on full VNINDEX index to get proper percentile context
    idx = idx.sort_values("time").reset_index(drop=True)
    idx_ret = idx["_vr_close"] / idx["_vr_close"].shift(1) - 1
    idx["_vol"] = idx_ret.rolling(vol_window).std()
    idx["_vol_pct"] = idx["_vol"].rolling(pct_window, min_periods=pct_window // 2).rank(pct=True)

    vol_map = idx.set_index("time")["_vol"]
    pct_map = idx.set_index("time")["_vol_pct"]

    df["vnindex_vol_20d"] = df_t.map(vol_map)
    df["vnindex_vol_pct"] = df_t.map(pct_map)
    df["vnindex_vol_20d"] = df["vnindex_vol_20d"].ffill()
    df["vnindex_vol_pct"] = df["vnindex_vol_pct"].ffill()
    df["high_vol_regime"] = (df["vnindex_vol_pct"] > cfg.get("vol_regime_threshold", 0.70)).astype(float)
    return df


# ---- V2: Tet holiday calendar features (Vietnam-specific) ----

def _add_calendar(df, cfg):
    """
    V2: Tet holiday features.
    Pre-Tet: institutional selling, FPT bonus payouts → selling pressure.
    Post-Tet: return buying, often 1-3 week rally.

    days_to_tet    : trading-calendar days until next Tet (0 on Tet day)
    days_since_tet : days since last Tet
    pre_tet_window : 1 if within pre_tet_days before Tet (default 21)
    post_tet_window: 1 if within post_tet_days after Tet (default 21)
    """
    pre_window  = cfg.get("pre_tet_days",  21)
    post_window = cfg.get("post_tet_days", 21)

    dates_ns = pd.to_datetime(df["time"]).astype(np.int64).values
    tet_ns   = TET_DATES.astype(np.int64)

    idxs = np.searchsorted(tet_ns, dates_ns)  # index of first Tet >= date

    # Days to next Tet (0 = on Tet day; negative not possible here since we take ceiling Tet)
    next_tet_idx = np.minimum(idxs, len(tet_ns) - 1)
    days_to_tet = ((tet_ns[next_tet_idx] - dates_ns) / (24 * 3600 * int(1e9))).astype(int)

    # Days since last Tet
    prev_tet_idx = np.maximum(idxs - 1, 0)
    days_since_tet = ((dates_ns - tet_ns[prev_tet_idx]) / (24 * 3600 * int(1e9))).astype(int)

    df["days_to_tet"]    = days_to_tet
    df["days_since_tet"] = days_since_tet
    df["pre_tet_window"]  = ((days_to_tet  >= 0) & (days_to_tet  <= pre_window)).astype(float)
    df["post_tet_window"] = ((days_since_tet >= 0) & (days_since_tet <= post_window)).astype(float)
    return df


# ---- V4: Risk-adjusted relative momentum (normalized by realized vol) ----

def _add_risk_adj_momentum(df, cfg):
    """
    V4: Divide relative returns by FPT's own realized vol → relative Sharpe ratio.
    More stable across vol regimes than raw excess returns.
    Requires _add_market_relative() to have run first.

    rel_sharpe_5d  : rel_ret_5d  / hist_vol_5d
    rel_sharpe_10d : rel_ret_10d / hist_vol_10d
    rel_sharpe_20d : rel_ret_20d / hist_vol_20d
    """
    daily_ret = df["close"] / df["close"].shift(1) - 1
    for lag in cfg.get("risk_adj_lags", [5, 10, 20]):
        hist_vol = daily_ret.rolling(lag).std().replace(0, np.nan)
        rel_col = f"rel_ret_{lag}d"
        if rel_col in df.columns:
            df[f"rel_sharpe_{lag}d"] = df[rel_col] / hist_vol
    return df


# ---- Seasonality features ----

def _add_seasonality(df, cfg):
    """
    General seasonality features. Vietnam-specific + universal effects.

    day_of_week        : 0=Mon … 4=Fri  (Monday/Friday effects documented globally)
    day_of_month       : 1-31 (turn-of-month effect: institutional rebalancing on last/first days)
    month              : 1-12 (January effect, sell-in-May, Q4 rally)
    quarter            : 1-4
    days_to_month_end  : calendar days until last day of month (rebalancing approach)
    days_to_quarter_end: calendar days until quarter end (institutional window-dressing)
    lunar_day          : approximate day within lunar month 1-30 (Vietnamese market significance)
    lunar_phase        : 0=new moon, ~0.5=full moon (continuous)
    is_lunar_new_moon  : 1 if within 2 days of new moon (Vietnamese 初一 — buying/praying)
    is_lunar_full_moon : 1 if within 2 days of full moon (Vietnamese 十五 — similar effect)
    """
    dates = pd.to_datetime(df["time"])

    df["day_of_week"]  = dates.dt.dayofweek  # 0=Mon, 4=Fri
    df["day_of_month"] = dates.dt.day
    df["month"]        = dates.dt.month
    df["quarter"]      = dates.dt.quarter

    # Days to month end (vectorized)
    month_end = dates + pd.offsets.MonthEnd(0)
    df["days_to_month_end"] = (month_end - dates).dt.days

    # Days to quarter end (March 31, June 30, Sept 30, Dec 31) — vectorized
    month_vals = dates.dt.month.values
    year_vals  = dates.dt.year.values
    q_end_month = ((month_vals - 1) // 3 + 1) * 3  # 3, 6, 9, or 12
    q_end_day   = np.where(q_end_month == 6, 30,
                  np.where(q_end_month == 9, 30, 31))  # Mar=31, Jun=30, Sep=30, Dec=31
    q_end_dates = pd.to_datetime({
        "year": year_vals, "month": q_end_month, "day": q_end_day
    })
    df["days_to_quarter_end"] = (q_end_dates - dates).dt.days

    # Lunar phase — approximate using known reference new moon (J2000 era)
    # Reference new moon: January 6, 2000 (widely used astronomical reference)
    ref_new_moon  = pd.Timestamp("2000-01-06")
    lunar_cycle   = 29.53058868  # mean synodic month in days
    days_since_ref = (dates - ref_new_moon).dt.days.values.astype(float)
    lunar_age      = days_since_ref % lunar_cycle  # 0 = new moon, ~14.77 = full moon

    df["lunar_day"]   = (np.floor(lunar_age) + 1).astype(int)  # 1-30
    df["lunar_phase"] = lunar_age / lunar_cycle  # [0, 1), 0=new, 0.5=full

    # Vietnamese significant lunar days: 初一 (day 1, new moon) and 十五 (day 15, full moon)
    df["is_lunar_new_moon"]  = ((lunar_age <= 2.0) | (lunar_age >= 27.5)).astype(float)
    df["is_lunar_full_moon"] = ((lunar_age >= 13.0) & (lunar_age <= 17.0)).astype(float)

    return df


# ---- S1: FPT quarterly earnings cycle features ----

def _add_earnings_cycle(df, cfg):
    """
    S1: FPT announces results ~45 days after each quarter end.
    Approximate schedule: Feb 15 (Q4/FY), May 15 (Q1), Aug 15 (Q2), Nov 15 (Q3).

    days_to_earnings    : days until next announcement (0 on announcement day)
    days_since_earnings : days since last announcement
    pre_earnings_window : 1 if within pre_earn_days before announcement (default 30)
    post_earnings_window: 1 if within post_earn_days after announcement (default 14)
    """
    pre_window  = cfg.get("pre_earn_days",  30)
    post_window = cfg.get("post_earn_days", 14)

    earn_dates = []
    for year in range(2010, 2027):
        earn_dates.extend([
            f"{year}-02-15",  # Q4/FY of prior year
            f"{year}-05-15",  # Q1
            f"{year}-08-15",  # Q2
            f"{year}-11-15",  # Q3
        ])
    earn_ns = pd.to_datetime(earn_dates).astype(np.int64)
    dates_ns = pd.to_datetime(df["time"]).astype(np.int64).values

    idxs = np.searchsorted(earn_ns, dates_ns)

    next_earn_idx = np.minimum(idxs, len(earn_ns) - 1)
    days_to_earn = ((earn_ns[next_earn_idx] - dates_ns) / (24 * 3600 * int(1e9))).astype(int)

    prev_earn_idx = np.maximum(idxs - 1, 0)
    days_since_earn = ((dates_ns - earn_ns[prev_earn_idx]) / (24 * 3600 * int(1e9))).astype(int)

    df["days_to_earnings"]     = days_to_earn
    df["days_since_earnings"]  = days_since_earn
    df["pre_earnings_window"]  = ((days_to_earn  >= 0) & (days_to_earn  <= pre_window)).astype(float)
    df["post_earnings_window"] = ((days_since_earn >= 0) & (days_since_earn <= post_window)).astype(float)
    return df


# ---- Cross-sectional rank features (from pre-built xs_features_daily.parquet) ----

def _add_cross_sectional(df, cfg):
    """
    Add cross-sectional rank features for this stock.
    Requires pre-built data/features/xs_features_daily.parquet (run src/build_xs_features.py).

    xs_rank_1d   : percentile rank of stock's 1d return within VN universe [0, 1]
    xs_rank_5d   : percentile rank of stock's 5d return within VN universe
    xs_rank_20d  : percentile rank of stock's 20d return
    xs_univ_mean_5d : universe mean 5d return (market breadth)
    xs_univ_std_5d  : universe 5d return dispersion (cross-sectional vol)
    xs_above_median_5d : 1 if stock is top half of market this week
    """
    xs_file = resolve_data_path(cfg.get("xs_file", "data/features/xs_features_daily.parquet"))
    ticker  = cfg.get("xs_ticker", "FPT")
    lags    = cfg.get("xs_lag_days", [1, 5, 20])

    try:
        xs = pd.read_parquet(xs_file)
        xs["time"] = pd.to_datetime(xs["time"])
        xs_cols = ["time", "xs_rank_1d", "xs_rank_5d", "xs_rank_20d",
                   "xs_univ_mean_1d", "xs_univ_mean_5d", "xs_univ_std_5d",
                   "xs_above_median_5d"]
        # V5: market breadth — include if present (added by updated build_xs_features.py)
        for bc in ["xs_breadth_1d", "xs_breadth_5d", "xs_breadth_20d"]:
            if bc in xs.columns:
                xs_cols.append(bc)
        xs_stock = xs[xs["ticker"] == ticker][xs_cols].copy()
        # Sanitize: replace inf/very large with NaN (will be dropped by dropna)
        num_cols = [c for c in xs_cols if c != "time"]
        xs_stock[num_cols] = xs_stock[num_cols].replace([np.inf, -np.inf], np.nan)
        df = df.merge(xs_stock, on="time", how="left")
    except FileNotFoundError:
        print(f"  [WARN] XS features file not found: {xs_file}. Run src/build_xs_features.py first.")
    return df


def _add_intraday(df, cfg):
    """
    Add intraday session features from pre-built fpt_intraday_daily.parquet.
    Only available from 2023-09 onward (1H data limitation).
    These features capture dynamics invisible at daily resolution.

    fh_ret    : first-hour return (how strong was the open?)
    am_ret    : morning session return (9:15-11:30)
    pm_ret    : afternoon session return (13:00-15:00)
    pm_vs_am  : pm_ret - am_ret (is afternoon reversing morning?)
    vol_am_frac: fraction of daily volume in morning
    """
    intraday_file = resolve_data_path(cfg.get("intraday_file", "data/features/fpt_intraday_daily.parquet"))
    try:
        intra = pd.read_parquet(intraday_file)
        intra = intra.rename(columns={"date": "time"})
        intra["time"] = pd.to_datetime(intra["time"])
        keep = ["time", "fh_ret", "am_ret", "pm_ret", "pm_vs_am",
                "vol_am_frac", "intraday_range_1h", "open_close_pct"]
        df = df.merge(intra[keep], on="time", how="left")
    except FileNotFoundError:
        print(f"  [WARN] Intraday file not found. Run src/build_intraday_features.py first.")
    return df


def _add_news(df, cfg):
    """
    Add FPT news sentiment features (from pre-built fpt_news_daily.parquet).
    Requires: run src/build_news_features.py first.
    Features are LAGGED by 1 day to avoid look-ahead bias.

    fpt_mentions_lag1   : FPT article count yesterday
    fpt_sentiment_lag1  : FPT sentiment yesterday (pos-neg keywords)
    news_surge_lag1     : 1 if yesterday was abnormally high news volume
    fpt_mentions_ma     : 20-day rolling avg FPT mentions
    """
    news_file = resolve_data_path(cfg.get("news_file", "data/features/fpt_news_daily.parquet"))
    try:
        news = pd.read_parquet(news_file)
        news = news.rename(columns={"date": "time"})
        news["time"] = pd.to_datetime(news["time"])
        news = news[["time", "fpt_mentions", "fpt_sentiment", "news_surge",
                     "fpt_mentions_ma", "fpt_title_mentions"]].copy()
        # Lag by 1 day to avoid look-ahead
        news["fpt_mentions_lag1"]      = news["fpt_mentions"].shift(1)
        news["fpt_sentiment_lag1"]     = news["fpt_sentiment"].shift(1)
        news["news_surge_lag1"]        = news["news_surge"].shift(1)
        news["fpt_title_mentions_lag1"]= news["fpt_title_mentions"].shift(1)
        news["fpt_mentions_ma_lag1"]   = news["fpt_mentions_ma"].shift(1)
        news = news.drop(columns=["fpt_mentions", "fpt_sentiment", "news_surge",
                                  "fpt_mentions_ma", "fpt_title_mentions"])
        df = df.merge(news, on="time", how="left")
    except FileNotFoundError:
        print(f"  [WARN] News file not found. Run src/build_news_features.py first.")
    return df


# ---- Session 6: Quarterly fundamental features from vnstock ----

def _add_fundamental_features(df, cfg):
    """
    Merge pre-built daily fundamental data (EPS, P/E, ROE, margins + momentum).
    Source: data/features/fpt_fundamentals.parquet (run data_tools/fetch_fundamentals.py)

    Features added:
      eps_qoq     : EPS quarter-over-quarter fractional change (earnings momentum)
      eps_yoy     : EPS year-over-year fractional change (earnings revision signal)
      pe_zscore   : P/E z-score vs own expanding history (valuation vs history)
      roe_qoq     : ROE quarter-over-quarter change (business quality momentum)
      npm_qoq     : Net profit margin QoQ change
    """
    fund_path = resolve_data_path(cfg.get("fundamentals_path", "data/features/fpt_fundamentals.parquet"))
    if not fund_path.exists():
        raise FileNotFoundError(
            f"Fundamentals parquet not found at {fund_path}. "
            "Run: python data_tools/fetch_fundamentals.py"
        )
    fund = pd.read_parquet(fund_path)
    fund.index = pd.to_datetime(fund.index)

    # Align on the stock's daily dates
    dates = pd.to_datetime(df["time"])
    fund_aligned = fund.reindex(dates.values, method="ffill")
    fund_aligned.index = df.index

    feat_cols = ["eps_qoq", "eps_yoy", "pe_zscore", "roe_qoq", "npm_qoq"]
    for col in feat_cols:
        if col in fund_aligned.columns:
            vals = fund_aligned[col].values.astype(float)
            # clip to avoid inf from pct_change on near-zero denominator
            vals = np.clip(vals, -5.0, 5.0)
            df[col] = vals

    return df


# ---------------------------------------------------------------------------
# Cross-sectional helpers (called on full all_df, not per-stock)
# ---------------------------------------------------------------------------

def add_sector_relative_features(all_df: pd.DataFrame, sector_map: dict) -> pd.DataFrame:
    """
    H80: Add sector-relative momentum features to the full cross-sectional DataFrame.

    For each (date, ticker), computes how the stock's relative return deviates
    from its sector's mean relative return on that date:
        sector_rel_Xd = rel_ret_Xd - sector_mean_Xd

    Tickers not in sector_map are assigned to "Other" and demeaned against the
    full-universe mean for that day.

    Must be called AFTER load_all_stocks() on the merged all_df.
    """
    all_df = all_df.copy()
    all_df["_sector"] = all_df["ticker"].map(sector_map).fillna("Other")
    all_df["time"] = pd.to_datetime(all_df["time"])

    for lag, col in [(1, "rel_ret_1d"), (5, "rel_ret_5d"), (20, "rel_ret_20d")]:
        out_col = f"sector_rel_{lag}d"
        if col not in all_df.columns:
            all_df[out_col] = 0.0
            continue
        # Compute sector mean per (date, sector), then subtract from individual stock
        sector_mean = (
            all_df.groupby(["time", "_sector"])[col]
            .transform("mean")
        )
        all_df[out_col] = all_df[col] - sector_mean

    all_df = all_df.drop(columns=["_sector"])
    return all_df


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def generate_features(df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
    df = df.copy()
    target_col  = config.get("data", {}).get("target_col", "future_return_5d")
    feat_cfg    = config.get("features", {})

    df = _make_target(df, target_col, config)

    if feat_cfg.get("use_lags",           True):  df = _add_lags(df, feat_cfg)
    if feat_cfg.get("use_ma",            False):  df = _add_ma(df, feat_cfg)
    if feat_cfg.get("use_ma_dist",       False):  df = _add_ma_dist(df, feat_cfg)
    if feat_cfg.get("use_rsi",           False):  df = _add_rsi(df, feat_cfg)
    if feat_cfg.get("use_macd",          False):  df = _add_macd(df, feat_cfg)
    if feat_cfg.get("use_bb",            False):  df = _add_bb(df, feat_cfg)
    if feat_cfg.get("use_atr",           False):  df = _add_atr(df, feat_cfg)
    if feat_cfg.get("use_volume_signals",False):  df = _add_volume_signals(df, feat_cfg)
    # New OHLCV (Sessions 3+)
    if feat_cfg.get("use_candle",        False):  df = _add_candle(df, feat_cfg)
    if feat_cfg.get("use_stoch",         False):  df = _add_stoch(df, feat_cfg)
    if feat_cfg.get("use_willr",         False):  df = _add_willr(df, feat_cfg)
    if feat_cfg.get("use_adx",           False):  df = _add_adx(df, feat_cfg)
    if feat_cfg.get("use_hist_vol",      False):  df = _add_hist_vol(df, feat_cfg)
    if feat_cfg.get("use_cci",           False):  df = _add_cci(df, feat_cfg)
    # Cross-asset (Sessions 3+)
    if feat_cfg.get("use_market_relative",False): df = _add_market_relative(df, feat_cfg)
    if feat_cfg.get("use_macro",         False):  df = _add_macro(df, feat_cfg)
    # Cross-sectional rank features (Session 4+)
    if feat_cfg.get("use_sector_peers",   False): df = _add_sector_peers(df, feat_cfg)
    if feat_cfg.get("use_cross_sectional",False): df = _add_cross_sectional(df, feat_cfg)
    if feat_cfg.get("use_news",           False): df = _add_news(df, feat_cfg)
    if feat_cfg.get("use_intraday",       False): df = _add_intraday(df, feat_cfg)
    # Session 5: new signal directions
    if feat_cfg.get("use_vol_regime",       False): df = _add_vol_regime(df, feat_cfg)
    if feat_cfg.get("use_calendar",         False): df = _add_calendar(df, feat_cfg)
    if feat_cfg.get("use_risk_adj_momentum",False): df = _add_risk_adj_momentum(df, feat_cfg)
    if feat_cfg.get("use_earnings_cycle",   False): df = _add_earnings_cycle(df, feat_cfg)
    if feat_cfg.get("use_seasonality",      False): df = _add_seasonality(df, feat_cfg)
    # Session 6: fundamental features from vnstock quarterly financials
    if feat_cfg.get("use_fundamentals",     False): df = _add_fundamental_features(df, feat_cfg)

    df = df.dropna().reset_index(drop=True)
    return df


def get_feature_columns(df: pd.DataFrame, config: Dict[str, Any]) -> List[str]:
    feat_cfg = config.get("features", {})
    cols: List[str] = []

    def _add(names):
        cols.extend([c for c in names if c in df.columns])

    _add(feat_cfg.get("base_cols", []))

    if feat_cfg.get("use_lags", True):
        _add([f"past_return_{i}d" for i in feat_cfg.get("lag_days", [1, 2, 3, 5, 10])])
    if feat_cfg.get("use_ma", False):
        _add([f"ma_{w}" for w in feat_cfg.get("ma_windows", [5, 10, 20])])
    if feat_cfg.get("use_ma_dist", False):
        _add([f"ma_dist_{w}" for w in feat_cfg.get("ma_windows", [5, 10, 20, 50])])
    if feat_cfg.get("use_rsi", False):
        _add([f"rsi_{feat_cfg.get('rsi_period', 14)}"])
    if feat_cfg.get("use_macd", False):
        _add(["macd_line", "macd_signal_line", "macd_hist"])
    if feat_cfg.get("use_bb", False):
        _add(["bb_width", "bb_pct"])
    if feat_cfg.get("use_atr", False):
        _add([f"atr_{feat_cfg.get('atr_period', 14)}"])
    if feat_cfg.get("use_volume_signals", False):
        _add(["vol_ratio", "obv_roc", "vwap_dev_5d", "vol_trend"])
    if feat_cfg.get("use_candle", False):
        _add(["candle_body", "upper_wick", "lower_wick", "gap"])
    if feat_cfg.get("use_stoch", False):
        _add(["stoch_k", "stoch_d"])
    if feat_cfg.get("use_willr", False):
        _add(["willr"])
    if feat_cfg.get("use_adx", False):
        _add(["adx", "di_diff"])
    if feat_cfg.get("use_hist_vol", False):
        _add([f"hist_vol_{w}" for w in feat_cfg.get("hist_vol_windows", [5, 10, 20])])
        _add(["intraday_range"])
    if feat_cfg.get("use_cci", False):
        _add(["cci"])
    if feat_cfg.get("use_market_relative", False):
        lags = feat_cfg.get("rel_lag_days", [1, 2, 3, 5, 10, 20])
        _add([f"rel_ret_{l}d"  for l in lags])
        _add([f"idx_ret_{l}d"  for l in lags])
    if feat_cfg.get("use_macro", False):
        for mf in feat_cfg.get("macro_files", []):
            alias = mf["alias"]
            _add([f"{alias}_ret_{l}d" for l in feat_cfg.get("macro_lag_days", [1, 5])])
    if feat_cfg.get("use_sector_peers", False):
        for ticker in feat_cfg.get("peer_tickers", []):
            _add([f"{ticker}_rel_{l}d" for l in feat_cfg.get("peer_lag_days", [1, 5, 10, 20])])
    if feat_cfg.get("use_cross_sectional", False):
        _add(["xs_rank_1d", "xs_rank_5d", "xs_rank_20d",
              "xs_univ_mean_1d", "xs_univ_mean_5d", "xs_univ_std_5d",
              "xs_above_median_5d"])
    if feat_cfg.get("use_news", False):
        _add(["fpt_mentions_lag1", "fpt_sentiment_lag1", "news_surge_lag1",
              "fpt_title_mentions_lag1", "fpt_mentions_ma_lag1"])
    if feat_cfg.get("use_intraday", False):
        _add(["fh_ret", "am_ret", "pm_ret", "pm_vs_am",
              "vol_am_frac", "intraday_range_1h", "open_close_pct"])
    # Session 5: new signal directions
    if feat_cfg.get("use_vol_regime", False):
        _add(["vnindex_vol_20d", "vnindex_vol_pct", "high_vol_regime"])
    if feat_cfg.get("use_calendar", False):
        _add(["days_to_tet", "days_since_tet", "pre_tet_window", "post_tet_window"])
    if feat_cfg.get("use_risk_adj_momentum", False):
        _add([f"rel_sharpe_{l}d" for l in feat_cfg.get("risk_adj_lags", [5, 10, 20])])
    if feat_cfg.get("use_earnings_cycle", False):
        _add(["days_to_earnings", "days_since_earnings",
              "pre_earnings_window", "post_earnings_window"])
    if feat_cfg.get("use_seasonality", False):
        _add(["day_of_week", "day_of_month", "month", "quarter",
              "days_to_month_end", "days_to_quarter_end",
              "lunar_day", "lunar_phase", "is_lunar_new_moon", "is_lunar_full_moon"])
    if feat_cfg.get("use_fundamentals", False):
        _add(["eps_qoq", "eps_yoy", "pe_zscore", "roe_qoq", "npm_qoq"])

    return cols
