"""
cross_sectional_wf.py -- Walk-forward validation on ALL Vietnamese stocks simultaneously.

Instead of training on FPT alone (~250 rows/year), trains on all 55 stocks
(~13,750 rows/year), then tests on all stocks AND reports FPT-specific accuracy.

This is the strongest test of whether relative momentum is a real signal:
if the pattern generalizes across stocks, it's almost certainly not overfitting.

Usage:
    python cross_sectional_wf.py
    python cross_sectional_wf.py --min-train-years 3 --start-date 2012-01-01

Output:
    - Per-year results: overall + FPT-specific
    - Summary appended to xs_wf_results.jsonl
    - Compact per-run summary written to artifacts/run_summaries/
"""
import argparse
import json
import glob
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from scipy.stats import binomtest

from src.data_loader import load_data
from src.feature_engineering import generate_features, get_feature_columns
from src.model_factory import get_model
from src.evaluator import evaluate_model
from src.run_summary import write_run_summary


DATA_DIR = Path("data/stock")
EXCLUDE  = {"VNINDEX", "VN30"}


# Feature config used for all stocks — E8-style: rel lags + tech, no abs lags
BASE_CONFIG = {
    "data": {
        "target_col": "future_rel_dir_5d",
        "test_size": 0.15, "val_size": 0.15,
        "start_date": "2012-01-01",   # wider window for cross-sectional
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
        "use_cross_sectional": False,  # off by default (optional)
        "use_news": False,
    },
    "model": {
        "type": "xgboost_classifier",
        "params": {
            "n_estimators": 500, "max_depth": 3, "learning_rate": 0.05,
            "subsample": 0.8, "colsample_bytree": 0.8, "early_stopping_rounds": 30
        }
    }
}


def load_all_stocks(start_date: str = "2012-01-01") -> pd.DataFrame:
    files = sorted(glob.glob(str(DATA_DIR / "gia_lich_su_*_1D.parquet")))
    frames = []
    for f in files:
        ticker = Path(f).stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
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
        except Exception as e:
            print(f"  [WARN] {ticker}: {e}")

    all_df = pd.concat(frames, ignore_index=True)
    print(f"Loaded {len(frames)} stocks, {len(all_df):,} total rows")
    return all_df


GLOBAL_MACRO_FILES = [
    {"path": "data/fx-commodities/fx_commodities_vix_1D.parquet",      "alias": "vix"},
    {"path": "data/fx-commodities/fx_commodities_us10y_1D.parquet",     "alias": "us10y"},
    {"path": "data/fx-commodities/fx_commodities_shanghai_1D.parquet",  "alias": "shanghai"},
    {"path": "data/fx-commodities/fx_commodities_hsi_1D.parquet",       "alias": "hsi"},
    {"path": "data/fx-commodities/fx_commodities_gold_1D.parquet",      "alias": "gold"},
    {"path": "data/fx-commodities/fx_commodities_oil_1D.parquet",       "alias": "oil"},
    {"path": "data/fx-commodities/fx_commodities_cny_x_1D.parquet",     "alias": "cny"},
]


def run_cross_sectional_wf(min_train_years: int = 3, start_date: str = "2012-01-01",
                            use_xs_features: bool = False, use_news: bool = False,
                            threshold: float = 0.0, save_proba: str = "",
                            use_macro: bool = False, target_horizon: int = 5,
                            barrier_pct: float = 0.0, model_type: str = "xgboost",
                            save_all_probas: str = "", use_xs_fundamentals: bool = False,
                            use_dividend_calendar: bool = False,
                            use_macro_regime: bool = False,
                            use_risk_adj: bool = False,
                            depth: int = 3,
                            rolling_window: int = 0,
                            use_vix_feature: bool = False,
                            use_dormant_features: bool = False,
                            use_sector_relative: bool = False,
                            use_volume_signals: bool = False,
                            sector_filter: str = "",
                            use_rolling_news: bool = False,
                            news_path: str = "",
                            use_insider: bool = False,
                            use_llm_news: bool = False,
                            use_llm_market: bool = False,
                            use_oc_asymmetry: bool = False,
                            use_dispersion_regime: bool = False,
                            use_return_skewness: bool = False,
                            use_earnings_calendar: bool = False):
    """
    threshold      : X2 — only report accuracy on predictions where |prob - 0.5| > threshold.
                     0.0 = use all predictions (default), 0.1 = min 60%% confidence.
    save_proba     : X3 — if non-empty, save per-date FPT probabilities to this CSV path.
    barrier_pct    : H17 — if > 0, use triple barrier target instead of fixed direction.
                     E.g. 0.01 = ±1% relative threshold; sets target to future_rel_barrier_5d.
    model_type     : H24 — "xgboost" (default) or "lightgbm".
    save_all_probas: H23 — if non-empty, save per-date probabilities for ALL tickers to this
                     parquet path (columns: time, year, ticker, xs_proba, actual).
    """
    print(f"\n{'='*70}")
    print(f"CROSS-SECTIONAL WALK-FORWARD VALIDATION")
    print(f"Features: E8-style (rel lags + tech) | Target: future_rel_dir_5d")
    print(f"Min train years: {min_train_years} | Start: {start_date} | Model: {model_type}")
    if model_type == "xgboost_reg":
        target_col = f"future_rel_return_{target_horizon}d"  # continuous excess return
    elif barrier_pct > 0:
        target_col = f"future_rel_barrier_{target_horizon}d"
        BASE_CONFIG["features"]["barrier_pct"] = barrier_pct
        print(f"H17 Triple barrier: ±{barrier_pct:.1%} relative threshold → {target_col}")
    else:
        target_col = f"future_rel_dir_{target_horizon}d"
    BASE_CONFIG["data"]["target_col"] = target_col
    lgbm_type = "lightgbm_classifier"
    xgb_type  = "xgboost_classifier"
    MODEL_MAP = {
        "xgboost":      "xgboost_classifier",
        "xgboost_reg":  "xgboost",
        "lightgbm":     "lightgbm_classifier",
        "random_forest":"random_forest_classifier",
        "extra_trees":  "extra_trees_classifier",
        "mlp":          "mlp_classifier",
    }
    BASE_CONFIG["model"]["type"] = MODEL_MAP.get(model_type, "xgboost_classifier")
    BASE_CONFIG["model"]["params"]["max_depth"] = depth
    if threshold > 0:
        print(f"X2 Confidence threshold: |prob-0.5| > {threshold:.2f} (min conf: {0.5+threshold:.2f})")
    if target_horizon != 5 and barrier_pct == 0:
        print(f"Target horizon: {target_horizon}d ({target_col})")
    if use_macro:
        print(f"Global macro features: VIX, US10Y, Shanghai, HSI, Gold, Oil, CNY (1d/5d returns)")
    if use_xs_fundamentals:
        print(f"XS Fundamentals: P/E rank, EPS YoY rank, ROE rank, NPM rank, Debt/Eq rank")
    if use_dividend_calendar:
        print(f"Dividend Calendar: pre_div_window, post_div_window, days_to_ex_div, div_count_30d")
    if use_macro_regime:
        print(f"Macro Regime (as training features): vix, taiex, kospi, sp500, yield_curve, ...")
    if use_risk_adj:
        print(f"Risk-Adjusted Momentum: rel_sharpe_5d/10d/20d")
    if depth != 3:
        print(f"XGBoost depth override: {depth}")
    if rolling_window > 0:
        print(f"Rolling window training: last {rolling_window} years only (not expanding)")
    if use_vix_feature:
        print(f"H50 VIX-as-feature: vix_level, vix_mom_5d, vix_mom_20d (no external VIX filter)")
    if use_dormant_features:
        print(f"H77 Dormant features: vol_regime, calendar, CCI, Williams %R")
    if use_sector_relative:
        print(f"H80 Sector-relative features: sector_rel_1d, sector_rel_5d, sector_rel_20d")
    if use_volume_signals:
        print(f"H90 Volume features: vol_ratio, obv_roc, vwap_dev_5d, vol_trend")
    if sector_filter:
        print(f"H92 Sector filter: '{sector_filter}'")
    if use_llm_news:
        print("H98 LLM ticker-day features: enabled")
    if use_llm_market:
        print("H98 LLM market-daily features: enabled")
    if use_oc_asymmetry:
        print("H100 Open/close asymmetry features: enabled")
    if use_dispersion_regime:
        print("H101 Cross-sectional dispersion regime: enabled")
    if use_return_skewness:
        print("H103 Return skewness features: enabled")
    if use_earnings_calendar:
        print("H104 Earnings calendar features: enabled")
    print(f"{'='*70}")

    # Optionally enable extra features
    if use_xs_features:
        BASE_CONFIG["features"]["use_cross_sectional"] = True
    if use_news:
        BASE_CONFIG["features"]["use_news"] = True
    if use_macro:
        BASE_CONFIG["features"]["use_macro"] = True
        BASE_CONFIG["features"]["macro_lag_days"] = [1, 5]
        BASE_CONFIG["features"]["macro_files"] = GLOBAL_MACRO_FILES
    if use_risk_adj:
        BASE_CONFIG["features"]["use_risk_adj_momentum"] = True
    if use_dormant_features:
        BASE_CONFIG["features"]["use_vol_regime"] = True
        BASE_CONFIG["features"]["use_calendar"]   = True
        BASE_CONFIG["features"]["use_willr"]      = True
        BASE_CONFIG["features"]["use_cci"]        = True
    if use_volume_signals:
        BASE_CONFIG["features"]["use_volume_signals"] = True

    all_df = load_all_stocks(start_date)

    # H92: sector filter — keep only tickers in the specified ICB sector/sub-sector
    if sector_filter:
        import unicodedata
        def _strip_diacritics(s: str) -> str:
            # Map Vietnamese-specific non-decomposable chars before NFKD normalization
            s = str(s).replace('đ', 'd').replace('Đ', 'D')
            return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii').lower()

        sec_path = Path("data/features/sector_classification.parquet")
        if sec_path.exists():
            sec_df = pd.read_parquet(sec_path)
            # Match against icb_name2/3/4 after stripping diacritical marks on both sides
            sf_norm = _strip_diacritics(sector_filter)
            def _norm_col(col):
                return col.fillna('').apply(_strip_diacritics)
            mask = (
                _norm_col(sec_df['icb_name2']).str.contains(sf_norm, na=False) |
                _norm_col(sec_df['icb_name3']).str.contains(sf_norm, na=False) |
                _norm_col(sec_df['icb_name4']).str.contains(sf_norm, na=False)
            )
            sector_tickers = set(sec_df.loc[mask, 'symbol'].tolist())
            before = all_df['ticker'].nunique()
            all_df = all_df[all_df['ticker'].isin(sector_tickers)].copy()
            after = all_df['ticker'].nunique()
            print(f"  H92 Sector filter '{sector_filter}': {before} → {after} tickers")
            if after < 5:
                raise ValueError(f"Too few tickers ({after}) after sector filter '{sector_filter}'. "
                                 f"Check sector name or classification file.")
        else:
            raise FileNotFoundError("data/features/sector_classification.parquet not found. "
                                    "Run: python data_tools/fetch_sector_classification.py")

    # H29: merge cross-sectional quarterly fundamentals (P/E rank, EPS YoY rank, ROE rank, etc.)
    XS_FUND_COLS = ["pe_ratio_rank", "eps_yoy_rank", "roe_rank", "npm_rank", "debt_eq_rank"]
    if use_xs_fundamentals:
        fund_path = Path("data/features/xs_fundamentals_daily.parquet")
        if fund_path.exists():
            fund = pd.read_parquet(fund_path)
            fund["time"] = pd.to_datetime(fund["time"])
            keep = ["time", "ticker"] + [c for c in XS_FUND_COLS if c in fund.columns]
            fund = fund[keep].drop_duplicates(["time", "ticker"])
            all_df["time"] = pd.to_datetime(all_df["time"])
            all_df = all_df.merge(fund, on=["time", "ticker"], how="left")
            avail_fund_cols = [c for c in XS_FUND_COLS if c in all_df.columns]
            print(f"  Merged XS fundamentals: {avail_fund_cols} ({fund['ticker'].nunique()} tickers)")
        else:
            print("  [WARN] xs_fundamentals_daily.parquet not found — run fetch_all_stock_fundamentals.py")
            use_xs_fundamentals = False

    # H31: merge dividend calendar features (pre/post ex-dividend windows)
    XS_DIV_COLS = ["pre_div_window", "post_div_window", "days_to_ex_div", "days_since_ex_div", "div_count_30d"]
    if use_dividend_calendar:
        div_path = Path("data/features/xs_dividend_calendar.parquet")
        if div_path.exists():
            div_cal = pd.read_parquet(div_path)
            div_cal["time"] = pd.to_datetime(div_cal["time"])
            keep = ["time", "ticker"] + [c for c in XS_DIV_COLS if c in div_cal.columns]
            div_cal = div_cal[keep].drop_duplicates(["time", "ticker"])
            all_df["time"] = pd.to_datetime(all_df["time"])
            all_df = all_df.merge(div_cal, on=["time", "ticker"], how="left")
            for c in XS_DIV_COLS:
                if c in all_df.columns:
                    all_df[c] = all_df[c].fillna(0)
            avail_div_cols = [c for c in XS_DIV_COLS if c in all_df.columns]
            print(f"  Merged dividend calendar: {avail_div_cols}")
        else:
            print("  [WARN] xs_dividend_calendar.parquet not found — run fetch_dividend_events.py")
            use_dividend_calendar = False

    # H89/H99: merge news sentiment features (per-ticker daily)
    NEWS_SENT_COLS = ["sentiment_score", "sentiment_cs_z", "positive_ratio", "article_count"]
    if use_news:
        sent_path = Path(news_path) if news_path else Path("data/features/xs_news_sentiment_daily.parquet")
        if sent_path.exists():
            sent_df = pd.read_parquet(sent_path)
            sent_df["time"] = pd.to_datetime(sent_df["time"])
            avail_sent_cols = [c for c in NEWS_SENT_COLS if c in sent_df.columns]
            keep = ["time", "ticker"] + avail_sent_cols
            sent_df = sent_df[keep].drop_duplicates(["time", "ticker"])
            all_df["time"] = pd.to_datetime(all_df["time"])
            all_df = all_df.merge(sent_df, on=["time", "ticker"], how="left")
            # Fill NaN (no news) with 0 — neutral sentiment
            for c in avail_sent_cols:
                if c in all_df.columns:
                    all_df[c] = all_df[c].fillna(0)
            print(f"  H89 News sentiment merged: {avail_sent_cols} ({sent_df['ticker'].nunique()} tickers)")
        else:
            print("  [WARN] xs_news_sentiment_daily.parquet not found — "
                  "run: python data_tools/extract_news_sentiment.py")
            use_news = False

    # H96: merge rolling news sentiment features (5d/30d windows, denser than daily)
    ROLLING_NEWS_COLS = [
        "sentiment_score_5d", "sentiment_score_30d",
        "article_count_5d",   "article_count_30d",
        "positive_ratio_5d",  "has_news_5d", "has_news_30d",
    ]
    if use_rolling_news:
        rn_path = Path("data/features/xs_news_sentiment_rolling.parquet")
        if rn_path.exists():
            rn_df = pd.read_parquet(rn_path)
            rn_df["time"] = pd.to_datetime(rn_df["time"])
            avail_rn_cols = [c for c in ROLLING_NEWS_COLS if c in rn_df.columns]
            keep = ["time", "ticker"] + avail_rn_cols
            rn_df = rn_df[keep].drop_duplicates(["time", "ticker"])
            all_df["time"] = pd.to_datetime(all_df["time"])
            all_df = all_df.merge(rn_df, on=["time", "ticker"], how="left")
            for c in avail_rn_cols:
                if c in all_df.columns:
                    all_df[c] = all_df[c].fillna(0)
            print(f"  H96 Rolling news merged: {avail_rn_cols} ({rn_df['ticker'].nunique()} tickers)")
        else:
            print("  [WARN] xs_news_sentiment_rolling.parquet not found — "
                  "run: python data_tools/build_rolling_news_sentiment.py")
            use_rolling_news = False

    # H97: merge insider deal features (net planned buy/sell per ticker per day)
    INSIDER_COLS = [
        "insider_net_plan_5d", "insider_net_plan_30d",
        "insider_net_real_5d", "insider_net_real_30d",
        "insider_buy_flag_5d", "insider_sell_flag_5d",
        "large_sh_net_plan_5d", "large_sh_net_plan_30d",
    ]
    if use_insider:
        ins_path = Path("data/features/xs_insider_features.parquet")
        if ins_path.exists():
            ins_df = pd.read_parquet(ins_path)
            ins_df = ins_df.rename(columns={"trading_day": "time"})
            ins_df["time"] = pd.to_datetime(ins_df["time"])
            avail_ins_cols = [c for c in INSIDER_COLS if c in ins_df.columns]
            keep = ["time", "ticker"] + avail_ins_cols
            ins_df = ins_df[keep].drop_duplicates(["time", "ticker"])
            all_df["time"] = pd.to_datetime(all_df["time"])
            all_df = all_df.merge(ins_df, on=["time", "ticker"], how="left")
            for c in avail_ins_cols:
                if c in all_df.columns:
                    all_df[c] = all_df[c].fillna(0)
            print(f"  H97 Insider features merged: {avail_ins_cols} ({ins_df['ticker'].nunique()} tickers)")
        else:
            print("  [WARN] xs_insider_features.parquet not found — "
                  "run: python data_tools/fetch_insider_deals.py && python data_tools/build_insider_features.py")
            use_insider = False

    # H98: merge LLM ticker-day features (sparse per ticker/day features)
    LLM_NEWS_COLS = [
        "llm_sentiment_raw", "llm_confidence", "llm_sentiment_conf_weighted",
        "llm_sentiment_5d", "llm_sentiment_30d", "llm_insider_buy_5d",
        "llm_insider_sell_5d", "llm_contract_win_5d", "llm_legal_issue_5d",
        "llm_earnings_event_5d", "llm_is_forward_looking", "llm_magnitude_5d",
    ]
    if use_llm_news:
        llm_news_path = Path("data/features/xs_llm_news_ticker_day.parquet")
        if llm_news_path.exists():
            llm_df = pd.read_parquet(llm_news_path)
            llm_df["time"] = pd.to_datetime(llm_df["time"])
            avail_llm_cols = [c for c in LLM_NEWS_COLS if c in llm_df.columns]
            keep = ["time", "ticker"] + avail_llm_cols
            llm_df = llm_df[keep].drop_duplicates(["time", "ticker"])
            all_df["time"] = pd.to_datetime(all_df["time"])
            all_df = all_df.merge(llm_df, on=["time", "ticker"], how="left")
            for c in avail_llm_cols:
                if c in all_df.columns:
                    all_df[c] = all_df[c].fillna(0)
            print(f"  H98 LLM ticker-day merged: {avail_llm_cols} ({llm_df['ticker'].nunique()} tickers)")
        else:
            print("  [WARN] xs_llm_news_ticker_day.parquet not found — "
                  "run: python data_tools/build_llm_news_features.py")
            use_llm_news = False

    # H98: merge LLM market-daily features (dense date-level features)
    LLM_MARKET_COLS = [
        "daily_market_tone", "daily_market_tone_5d", "daily_market_tone_30d",
        "market_tone_momentum", "frac_positive_news", "frac_negative_news",
        "uncertainty_index", "frac_forward_looking", "frac_earnings_news",
        "frac_macro_news", "sector_banking_tone", "sector_realestate_tone",
        "sector_tech_tone", "event_diversity", "avg_magnitude",
    ]
    if use_llm_market:
        llm_mkt_path = Path("data/features/xs_llm_news_market_daily.parquet")
        if llm_mkt_path.exists():
            llm_mkt = pd.read_parquet(llm_mkt_path)
            llm_mkt["time"] = pd.to_datetime(llm_mkt["time"])
            avail_mkt_cols = [c for c in LLM_MARKET_COLS if c in llm_mkt.columns]
            keep = ["time"] + avail_mkt_cols
            llm_mkt = llm_mkt[keep].drop_duplicates(["time"])
            all_df["time"] = pd.to_datetime(all_df["time"])
            all_df = all_df.merge(llm_mkt, on="time", how="left")
            for c in avail_mkt_cols:
                if c in all_df.columns:
                    all_df[c] = all_df[c].ffill().fillna(0)
            print(f"  H98 LLM market-daily merged: {avail_mkt_cols}")
        else:
            print("  [WARN] xs_llm_news_market_daily.parquet not found — "
                  "run: python data_tools/build_llm_news_features.py")
            use_llm_market = False

    # H100: merge dense ticker-day open/close asymmetry features
    OC_ASYM_COLS = [
        "overnight_ret_1d", "intraday_ret_1d",
        "open_to_open_ret_1d", "close_to_close_ret_1d",
        "oc_asym_1d", "overnight_mom_5d", "overnight_mom_20d",
        "intraday_mom_5d", "intraday_mom_20d",
        "oc_asym_5d", "oc_asym_20d", "gap_abs_5d",
    ]
    if use_oc_asymmetry:
        oc_path = Path("data/features/xs_open_close_asymmetry.parquet")
        if oc_path.exists():
            oc_df = pd.read_parquet(oc_path)
            oc_df["time"] = pd.to_datetime(oc_df["time"])
            avail_oc_cols = [c for c in OC_ASYM_COLS if c in oc_df.columns]
            keep = ["time", "ticker"] + avail_oc_cols
            oc_df = oc_df[keep].drop_duplicates(["time", "ticker"])
            all_df["time"] = pd.to_datetime(all_df["time"])
            all_df = all_df.merge(oc_df, on=["time", "ticker"], how="left")
            for c in avail_oc_cols:
                all_df[c] = all_df[c].fillna(0)
            print(f"  H100 OC asymmetry merged: {avail_oc_cols}")
        else:
            print("  [WARN] xs_open_close_asymmetry.parquet not found — "
                  "run: python data_tools/build_open_close_asymmetry_features.py")
            use_oc_asymmetry = False

    # H101: merge dense date-level dispersion regime features
    DISP_REGIME_COLS = [
        "xs_ret_std_1d", "xs_ret_iqr_1d", "xs_tail_spread_1d",
        "xs_breadth_up_1d", "xs_breadth_down_1d", "xs_mean_ret_1d",
        "xs_overnight_intraday_spread", "xs_ret_std_5d", "xs_ret_std_20d",
        "xs_breadth_up_5d", "xs_breadth_up_20d", "xs_dispersion_z20",
    ]
    if use_dispersion_regime:
        disp_path = Path("data/features/xs_dispersion_regime_daily.parquet")
        if disp_path.exists():
            disp_df = pd.read_parquet(disp_path)
            disp_df["time"] = pd.to_datetime(disp_df["time"])
            avail_disp_cols = [c for c in DISP_REGIME_COLS if c in disp_df.columns]
            keep = ["time"] + avail_disp_cols
            disp_df = disp_df[keep].drop_duplicates(["time"])
            all_df["time"] = pd.to_datetime(all_df["time"])
            all_df = all_df.merge(disp_df, on="time", how="left")
            for c in avail_disp_cols:
                all_df[c] = all_df[c].ffill().fillna(0)
            print(f"  H101 Dispersion regime merged: {avail_disp_cols}")
        else:
            print("  [WARN] xs_dispersion_regime_daily.parquet not found — "
                  "run: python data_tools/build_dispersion_regime_features.py")
            use_dispersion_regime = False

    # H103: merge dense ticker-day return skewness/tail-shape features
    RET_SKEW_COLS = [
        "ret_skew_5d", "ret_skew_20d", "ret_skew_60d",
        "downside_dev_20d", "upside_dev_20d", "down_up_vol_ratio_20d",
        "left_tail_frac_20d", "ret_skew_z20",
    ]
    if use_return_skewness:
        skew_path = Path("data/features/xs_return_skewness.parquet")
        if skew_path.exists():
            skew_df = pd.read_parquet(skew_path)
            skew_df["time"] = pd.to_datetime(skew_df["time"])
            avail_skew_cols = [c for c in RET_SKEW_COLS if c in skew_df.columns]
            keep = ["time", "ticker"] + avail_skew_cols
            skew_df = skew_df[keep].drop_duplicates(["time", "ticker"])
            all_df["time"] = pd.to_datetime(all_df["time"])
            all_df = all_df.merge(skew_df, on=["time", "ticker"], how="left")
            for c in avail_skew_cols:
                all_df[c] = all_df[c].fillna(0)
            print(f"  H103 Return skewness merged: {avail_skew_cols}")
        else:
            print("  [WARN] xs_return_skewness.parquet not found — "
                  "run: python data_tools/build_return_skewness_features.py")
            use_return_skewness = False

    # H104: merge dense date-level earnings/reporting calendar features
    EARN_CAL_COLS = [
        "days_since_q_end", "days_to_next_q_end",
        "in_report_w15_45", "in_report_w30_60", "in_report_w20_50",
        "pre_q_end_10d", "post_q_end_10d",
        "quarter_phase", "quarter_phase_sin", "quarter_phase_cos",
        "q1_flag", "q2_flag", "q3_flag", "q4_flag",
    ]
    if use_earnings_calendar:
        ec_path = Path("data/features/xs_earnings_calendar_daily.parquet")
        if ec_path.exists():
            ec_df = pd.read_parquet(ec_path)
            ec_df["time"] = pd.to_datetime(ec_df["time"])
            avail_ec_cols = [c for c in EARN_CAL_COLS if c in ec_df.columns]
            keep = ["time"] + avail_ec_cols
            ec_df = ec_df[keep].drop_duplicates(["time"])
            all_df["time"] = pd.to_datetime(all_df["time"])
            all_df = all_df.merge(ec_df, on="time", how="left")
            for c in avail_ec_cols:
                all_df[c] = all_df[c].ffill().fillna(0)
            print(f"  H104 Earnings calendar merged: {avail_ec_cols}")
        else:
            print("  [WARN] xs_earnings_calendar_daily.parquet not found — "
                  "run: python data_tools/build_earnings_calendar_features.py")
            use_earnings_calendar = False

    # H32: merge macro regime features as direct training features (date-level join, same value for all tickers)
    MACRO_REGIME_COLS = [
        "vix", "vix_mom_5d", "vix_mom_20d", "vni_mom_5d", "vni_mom_20d",
        "gold_mom_5d", "gold_mom_20d", "oil_mom_5d", "oil_mom_20d",
        "hsi_mom_5d", "hsi_mom_20d", "shanghai_mom_5d", "shanghai_mom_20d",
        "sp500_mom_5d", "sp500_mom_20d", "yield_curve", "yield_curve_mom",
        "hyg_tlt_ratio", "hyg_tlt_mom_20d", "eem_vs_sp500_20d",
        "kospi_mom_20d", "taiex_mom_20d", "btc_mom_20d",
        "breadth_score", "breadth_score_ext", "credit_risk_on",
    ]
    if use_macro_regime:
        macro_path = Path("data/features/macro_regime_daily.parquet")
        if macro_path.exists():
            macro_df = pd.read_parquet(macro_path)
            macro_df["time"] = pd.to_datetime(macro_df["time"])
            avail_macro_cols = [c for c in MACRO_REGIME_COLS if c in macro_df.columns]
            keep = ["time"] + avail_macro_cols
            macro_df = macro_df[keep].drop_duplicates("time")
            all_df["time"] = pd.to_datetime(all_df["time"])
            all_df = all_df.merge(macro_df, on="time", how="left")
            for c in avail_macro_cols:
                all_df[c] = all_df[c].fillna(0)
            print(f"  Merged macro regime features ({len(avail_macro_cols)} cols): {avail_macro_cols}")
        else:
            print("  [WARN] macro_regime_daily.parquet not found — run build_macro_regime_features.py")
            use_macro_regime = False
            avail_macro_cols = []

    # H50: VIX as a training feature (level + momentum). Lets the model learn regime internally.
    # Distinct from H32 (full macro regime) — just VIX alone.
    VIX_FEATURE_COLS = ["vix_level", "vix_mom_5d", "vix_mom_20d"]
    if use_vix_feature:
        vix_fpath = Path("data/fx-commodities/fx_commodities_vix_1D.parquet")
        if vix_fpath.exists():
            vix_df = pd.read_parquet(vix_fpath)[["time", "close"]].copy()
            vix_df["time"] = pd.to_datetime(vix_df["time"])
            vix_df = vix_df.rename(columns={"close": "vix_level"}).sort_values("time")
            vix_df["vix_mom_5d"]  = vix_df["vix_level"].pct_change(5).clip(-5, 5)
            vix_df["vix_mom_20d"] = vix_df["vix_level"].pct_change(20).clip(-5, 5)
            all_df["time"] = pd.to_datetime(all_df["time"])
            all_df = all_df.merge(vix_df[["time", "vix_level", "vix_mom_5d", "vix_mom_20d"]],
                                  on="time", how="left")
            for c in VIX_FEATURE_COLS:
                all_df[c] = all_df[c].ffill().fillna(0)
            print(f"  Merged VIX features: {VIX_FEATURE_COLS}")
        else:
            print("  [WARN] VIX parquet not found — disabling use_vix_feature")
            use_vix_feature = False

    # H80: sector-relative momentum features (computed cross-sectionally after load)
    SECTOR_REL_COLS = ["sector_rel_1d", "sector_rel_5d", "sector_rel_20d"]
    if use_sector_relative:
        from analysis.h72_sector_neutral import SECTOR_MAP
        from src.feature_engineering import add_sector_relative_features
        all_df = add_sector_relative_features(all_df, SECTOR_MAP)
        avail_sr_cols = [c for c in SECTOR_REL_COLS if c in all_df.columns]
        print(f"  Sector-relative features added: {avail_sr_cols}")

    # H36: risk-adjusted momentum features (rel_sharpe_5d/10d/20d from feature_engineering)
    # Already set in BASE_CONFIG["features"]["use_risk_adj_momentum"] = True before load_all_stocks,
    # so columns should already be in all_df if feature_engineering supports the flag.
    RISK_ADJ_COLS = ["rel_sharpe_5d", "rel_sharpe_10d", "rel_sharpe_20d"]
    if use_risk_adj:
        avail_ra_cols = [c for c in RISK_ADJ_COLS if c in all_df.columns]
        if avail_ra_cols:
            print(f"  Risk-adj momentum features: {avail_ra_cols}")
        else:
            print("  [WARN] Risk-adj cols not found in all_df — check use_risk_adj_momentum in feature_engineering")

    feature_cols = get_feature_columns(all_df, BASE_CONFIG)
    if use_xs_fundamentals:
        avail_fund_cols = [c for c in XS_FUND_COLS if c in all_df.columns]
        feature_cols = feature_cols + avail_fund_cols
    if use_dividend_calendar:
        avail_div_cols = [c for c in XS_DIV_COLS if c in all_df.columns]
        feature_cols = feature_cols + avail_div_cols
    if use_macro_regime:
        avail_macro_cols = [c for c in MACRO_REGIME_COLS if c in all_df.columns]
        feature_cols = feature_cols + avail_macro_cols
    if use_risk_adj:
        avail_ra_cols = [c for c in RISK_ADJ_COLS if c in all_df.columns]
        feature_cols = feature_cols + [c for c in avail_ra_cols if c not in feature_cols]
    if use_vix_feature:
        avail_vix_cols = [c for c in VIX_FEATURE_COLS if c in all_df.columns]
        feature_cols = feature_cols + [c for c in avail_vix_cols if c not in feature_cols]
    if use_sector_relative:
        avail_sr_cols = [c for c in SECTOR_REL_COLS if c in all_df.columns]
        feature_cols = feature_cols + [c for c in avail_sr_cols if c not in feature_cols]
    if use_news:
        avail_sent_cols = [c for c in NEWS_SENT_COLS if c in all_df.columns]
        feature_cols = feature_cols + [c for c in avail_sent_cols if c not in feature_cols]
    if use_rolling_news:
        avail_rn_cols = [c for c in ROLLING_NEWS_COLS if c in all_df.columns]
        feature_cols = feature_cols + [c for c in avail_rn_cols if c not in feature_cols]
    if use_insider:
        avail_ins_cols = [c for c in INSIDER_COLS if c in all_df.columns]
        feature_cols = feature_cols + [c for c in avail_ins_cols if c not in feature_cols]
    if use_llm_news:
        avail_llm_cols = [c for c in LLM_NEWS_COLS if c in all_df.columns]
        feature_cols = feature_cols + [c for c in avail_llm_cols if c not in feature_cols]
    if use_llm_market:
        avail_mkt_cols = [c for c in LLM_MARKET_COLS if c in all_df.columns]
        feature_cols = feature_cols + [c for c in avail_mkt_cols if c not in feature_cols]
    if use_oc_asymmetry:
        avail_oc_cols = [c for c in OC_ASYM_COLS if c in all_df.columns]
        feature_cols = feature_cols + [c for c in avail_oc_cols if c not in feature_cols]
    if use_dispersion_regime:
        avail_disp_cols = [c for c in DISP_REGIME_COLS if c in all_df.columns]
        feature_cols = feature_cols + [c for c in avail_disp_cols if c not in feature_cols]
    if use_return_skewness:
        avail_skew_cols = [c for c in RET_SKEW_COLS if c in all_df.columns]
        feature_cols = feature_cols + [c for c in avail_skew_cols if c not in feature_cols]
    if use_earnings_calendar:
        avail_ec_cols = [c for c in EARN_CAL_COLS if c in all_df.columns]
        feature_cols = feature_cols + [c for c in avail_ec_cols if c not in feature_cols]
    print(f"Features ({len(feature_cols)}): {feature_cols}")

    all_df["_year"] = pd.to_datetime(all_df["time"]).dt.year
    start_year = int(all_df["_year"].min()) + min_train_years
    end_year   = int(all_df["_year"].max())
    if end_year == datetime.now().year:
        end_year -= 1

    per_year = []
    all_fpt_probas = []      # X3: accumulate per-date FPT probabilities across all test years
    all_ticker_probas = []   # H23: accumulate per-date probabilities for ALL tickers
    thr_label = f" [threshold={threshold:.2f}]" if threshold > 0 else ""
    print(f"\n  {'year':>5}  {'n_test':>8}  {'all_acc':>8}  {'fpt_acc':>12}  {'fpt_edge':>9}  {'fpt_pval':>9}{thr_label}")
    print("  " + "-" * 72)

    for test_year in range(start_year, end_year + 1):
        if rolling_window > 0:
            train_mask = (all_df["_year"] >= test_year - rolling_window) & (all_df["_year"] < test_year)
        else:
            train_mask = all_df["_year"] < test_year
        test_mask  = all_df["_year"] == test_year

        train_df = all_df[train_mask].copy()
        test_df  = all_df[test_mask].copy()

        if len(train_df) < 500 or len(test_df) < 50:
            continue

        X_train = train_df[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0)
        y_train = train_df[target_col]
        X_test  = test_df[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0)
        y_test  = test_df[target_col]

        # Drop NaN/inf targets (regression target has NaN for last N rows; inf from zero-price stocks)
        valid_train = y_train.notna() & np.isfinite(y_train) & (y_train.abs() < 10)
        X_train, y_train = X_train[valid_train], y_train[valid_train]
        valid_test = y_test.notna() & np.isfinite(y_test) & (y_test.abs() < 10)
        X_test, y_test = X_test[valid_test], y_test[valid_test]
        test_df = test_df[valid_test.values]

        # Internal val for early stopping (last 15% of train chronologically per ticker)
        n_val = max(50, int(len(X_train) * 0.12))
        X_tr, y_tr = X_train.iloc[:-n_val], y_train.iloc[:-n_val]
        X_v,  y_v  = X_train.iloc[-n_val:], y_train.iloc[-n_val:]

        model = get_model(BASE_CONFIG)
        if model_type == "lightgbm":
            try:
                import lightgbm as lgb
                model.fit(X_tr, y_tr, eval_set=[(X_v, y_v)],
                          callbacks=[lgb.early_stopping(30, verbose=False),
                                     lgb.log_evaluation(-1)])
            except Exception:
                model.fit(X_tr, y_tr)
        elif model_type in ("xgboost", "xgboost_reg"):
            model.fit(X_tr, y_tr, eval_set=[(X_v, y_v)], verbose=False)
        else:
            # RF, ExtraTrees, MLP — no eval_set support
            model.fit(X_tr, y_tr)

        preds = model.predict(X_test)
        has_proba = hasattr(model, "predict_proba")
        if has_proba:
            probas = model.predict_proba(X_test)[:, 1]
        else:
            probas = preds.copy()  # regressor: raw predicted excess return as ranking score

        # Overall accuracy (all stocks)
        if model_type == "xgboost_reg":
            preds_binary = (preds > 0).astype(int)
            overall_acc = (preds_binary == (y_test.values > 0).astype(int)).mean()
        else:
            preds_binary = preds
            overall_acc = (preds == y_test.values).mean()
        naive_all   = y_test.mean()

        # FPT-specific accuracy
        fpt_mask = test_df["ticker"] == "FPT"

        # --- X3: save per-date FPT probabilities ---
        if save_proba and fpt_mask.sum() > 0 and probas is not None:
            fpt_proba_rows = []
            fpt_idx = np.where(fpt_mask.values)[0]
            fpt_dates = test_df["time"].iloc[fpt_idx].values
            fpt_probas = probas[fpt_idx]
            fpt_y = y_test.values[fpt_idx]
            for d, p, y in zip(fpt_dates, fpt_probas, fpt_y):
                fpt_proba_rows.append({"time": d, "year": test_year, "xs_proba": round(float(p), 4), "actual": int(y)})
            all_fpt_probas.extend(fpt_proba_rows)

        # --- H23: save per-date probabilities for ALL tickers ---
        if save_all_probas and probas is not None:
            tickers_arr = test_df["ticker"].values
            times_arr   = test_df["time"].values
            y_arr       = y_test.values
            for tick, d, p, y_val in zip(tickers_arr, times_arr, probas, y_arr):
                actual_label = int(y_val > 0) if model_type == "xgboost_reg" else int(y_val)
                all_ticker_probas.append({
                    "time": d, "year": test_year, "ticker": tick,
                    "xs_proba": round(float(p), 4), "actual": actual_label,
                })

        if fpt_mask.sum() > 10:
            y_fpt    = y_test[fpt_mask]
            p_fpt    = preds_binary[fpt_mask.values]
            # For regression, convert continuous target to binary direction for accuracy reporting
            y_fpt_bin = (y_fpt.values > 0).astype(int) if model_type == "xgboost_reg" else y_fpt.values
            naive_fpt = y_fpt_bin.mean()

            # X2: confidence threshold filter (skip for regression — scores aren't [0,1])
            if threshold > 0 and probas is not None and model_type != "xgboost_reg":
                fpt_probas_all = probas[fpt_mask.values]
                confident = np.abs(fpt_probas_all - 0.5) > threshold
                n_confident = confident.sum()
                n_abstain = (~confident).sum()
                if n_confident > 5:
                    y_conf = y_fpt_bin[confident]
                    p_conf = p_fpt[confident]
                    fpt_acc  = (p_conf == y_conf).mean()
                    edge_fpt = fpt_acc - naive_fpt
                    pval = binomtest(int((p_conf == y_conf).sum()), len(y_conf), naive_fpt).pvalue
                    fpt_str  = f"{fpt_acc*100:.1f}%(n={n_confident})"
                    edge_str = f"{edge_fpt*100:+.2f}%"
                    sig = "*" if pval < 0.05 else " "
                    conf_str = f" [{n_abstain} abstain]"
                else:
                    fpt_acc = edge_fpt = pval = float("nan")
                    fpt_str = "LOW-CONF"
                    edge_str = "  N/A"
                    sig = " "
                    conf_str = f" [all {n_abstain} abstain]"
            else:
                fpt_acc  = (p_fpt == y_fpt_bin).mean()
                edge_fpt = fpt_acc - naive_fpt
                pval = binomtest(int((p_fpt == y_fpt_bin).sum()),
                                 len(y_fpt_bin), naive_fpt).pvalue
                fpt_str  = f"{fpt_acc*100:.1f}%"
                edge_str = f"{edge_fpt*100:+.2f}%"
                sig = "*" if pval < 0.05 else " "
                conf_str = ""
        else:
            fpt_acc = edge_fpt = pval = float("nan")
            fpt_str = edge_str = "  N/A"
            sig = " "
            conf_str = ""

        line = (f"  {test_year:>5}  {len(test_df):>8,}  {overall_acc*100:>7.2f}%"
                f"  {fpt_str:>12}  {edge_str:>8}  {pval:>7.4f}{sig}{conf_str}"
                if not np.isnan(fpt_acc) else
                f"  {test_year:>5}  {len(test_df):>8,}  {overall_acc*100:>7.2f}%  {'N/A':>12}  {'N/A':>8}  {'N/A':>7}")
        print(line)

        per_year.append({
            "year": test_year,
            "n_total": len(test_df),
            "overall_acc": round(overall_acc, 4),
            "naive_all": round(float(naive_all), 4),
            "fpt_acc": round(fpt_acc, 4) if not np.isnan(fpt_acc) else None,
            "fpt_naive": round(float(naive_fpt), 4) if not np.isnan(fpt_acc) else None,
            "fpt_edge": round(edge_fpt, 4) if not np.isnan(fpt_acc) else None,
            "fpt_pval": round(pval, 4) if not np.isnan(fpt_acc) else None,
        })

    if not per_year:
        print("Not enough data.")
        return

    # Summary
    overall_accs = [r["overall_acc"] for r in per_year]
    fpt_edges = [r["fpt_edge"] for r in per_year if r["fpt_edge"] is not None]
    fpt_pvs   = [r["fpt_pval"] for r in per_year if r["fpt_pval"] is not None]
    n_sig = sum(1 for p in fpt_pvs if p < 0.05)

    print(f"\n  SUMMARY (Cross-Sectional)")
    print(f"  Avg overall acc : {np.mean(overall_accs)*100:.2f}%")
    if fpt_edges:
        print(f"  FPT avg edge    : {np.mean(fpt_edges)*100:+.2f}%  (std: {np.std(fpt_edges)*100:.2f}%)")
        print(f"  FPT sig years   : {n_sig}/{len(fpt_pvs)} (p<0.05)")

    run_name = "X1_cross_sectional"
    if target_horizon != 5:
        run_name = f"X7_xs_{target_horizon}d"
    if use_macro:
        run_name = "X4_xs_with_macro"
    if barrier_pct > 0:
        run_name = f"X10_xs_barrier{barrier_pct:.2f}"
    if threshold > 0:
        run_name = f"X2_threshold_{threshold:.2f}"
        if use_macro:
            run_name = f"X4_xs_macro_thr_{threshold:.2f}"
        if target_horizon != 5:
            run_name = f"X7_xs_{target_horizon}d_thr_{threshold:.2f}"
        if barrier_pct > 0:
            run_name = f"X10_xs_barrier{barrier_pct:.2f}_thr_{threshold:.2f}"
    if model_type == "lightgbm":
        run_name = run_name.replace("X1_", "H24_lgbm_").replace("X10_", "H24_lgbm_")
        if run_name == run_name:  # fallback if neither prefix matched
            run_name = f"H24_lgbm_{run_name}"
    if use_oc_asymmetry:
        run_name = f"{run_name}_h100_oc_asym"
    if use_dispersion_regime:
        run_name = f"{run_name}_h101_dispersion"
    if use_return_skewness:
        run_name = f"{run_name}_h103_ret_skew"
    if use_earnings_calendar:
        run_name = f"{run_name}_h104_earn_cal"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    record = {
        "ts": ts,
        "name": run_name,
        "model": BASE_CONFIG["model"]["type"],
        "target": target_col,
        "barrier_pct": barrier_pct,
        "threshold": threshold,
        "n_features": len(feature_cols),
        "avg_overall_acc": round(np.mean(overall_accs), 4),
        "fpt_avg_edge": round(np.mean(fpt_edges), 4) if fpt_edges else None,
        "fpt_std_edge": round(np.std(fpt_edges), 4) if fpt_edges else None,
        "fpt_n_sig": n_sig,
        "total_years": len(per_year),
        "per_year": per_year,
    }
    with open("xs_wf_results.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    print(f"\n  Results appended to xs_wf_results.jsonl")

    # X3: save per-date FPT probabilities for ensemble use
    if save_proba and all_fpt_probas:
        proba_df = pd.DataFrame(all_fpt_probas)
        proba_df.to_csv(save_proba, index=False)
        print(f"  X3: FPT probabilities saved to {save_proba} ({len(proba_df)} rows)")

    # H23: save per-date probabilities for ALL tickers
    if save_all_probas and all_ticker_probas:
        all_proba_df = pd.DataFrame(all_ticker_probas)
        all_proba_df["time"] = pd.to_datetime(all_proba_df["time"])
        Path(save_all_probas).parent.mkdir(parents=True, exist_ok=True)
        all_proba_df.to_parquet(save_all_probas, index=False)
        n_tickers = all_proba_df["ticker"].nunique()
        print(f"  H23: All-ticker probabilities saved to {save_all_probas} "
              f"({len(all_proba_df):,} rows, {n_tickers} tickers)")

    artifacts = {"xs_wf_log": "xs_wf_results.jsonl"}
    if save_proba:
        artifacts["fpt_proba_csv"] = save_proba
    if save_all_probas:
        artifacts["all_ticker_probas"] = save_all_probas

    summary_path = write_run_summary(
        ts=ts,
        mode="cross_sectional",
        name=run_name,
        summary={
            "avg_overall_acc": round(np.mean(overall_accs), 4),
            "fpt_avg_edge": round(np.mean(fpt_edges), 4) if fpt_edges else None,
            "fpt_std_edge": round(np.std(fpt_edges), 4) if fpt_edges else None,
            "fpt_n_sig_years": n_sig,
            "total_years": len(per_year),
        },
        artifacts=artifacts,
        metadata={
            "target": target_col,
            "model": BASE_CONFIG["model"]["type"],
            "threshold": threshold,
            "barrier_pct": barrier_pct,
            "n_features": len(feature_cols),
        },
    )
    print(f"  Run summary saved to {summary_path}")

    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-train-years", type=int, default=3)
    parser.add_argument("--start-date", type=str, default="2012-01-01")
    parser.add_argument("--use-xs-features", action="store_true")
    parser.add_argument("--use-news", action="store_true")
    # X2: confidence threshold
    parser.add_argument("--threshold", type=float, default=0.0,
                        help="Only count predictions where |prob-0.5| > threshold. "
                             "0.0=all predictions (default), 0.1=min 60%% confidence.")
    # X3: save probabilities for ensemble
    parser.add_argument("--save-proba", type=str, default="",
                        help="Save per-date FPT probabilities to this CSV file (X3 ensemble prep).")
    # X4: add global macro features
    parser.add_argument("--use-macro", action="store_true",
                        help="Add global macro features (VIX, US10Y, Shanghai, HSI, etc.) to XS model.")
    # H11: alternative target horizon
    parser.add_argument("--target-horizon", type=int, default=5,
                        help="Target prediction horizon in days (default 5). E.g. 10 or 20.")
    # H17: triple barrier labels for XS model
    parser.add_argument("--barrier-pct", type=float, default=0.0,
                        help="H17: use triple barrier target. E.g. 0.01 = ±1%% relative threshold. "
                             "0 = standard fixed-direction target (default).")
    # H24: model type
    parser.add_argument("--model", type=str, default="xgboost",
                        choices=["xgboost", "xgboost_reg", "lightgbm", "random_forest", "extra_trees", "mlp"],
                        help="Model type for XS walk-forward (default: xgboost).")
    # H23: save all-ticker probabilities
    parser.add_argument("--save-all-probas", type=str, default="",
                        help="H23: save per-date probabilities for ALL tickers to this parquet path.")
    # H29: cross-sectional quarterly fundamentals as additional features
    parser.add_argument("--use-xs-fundamentals", action="store_true",
                        help="H29: add P/E rank, EPS YoY rank, ROE rank from xs_fundamentals_daily.parquet.")
    # H31: dividend calendar features
    parser.add_argument("--use-dividend-calendar", action="store_true",
                        help="H31: add pre/post ex-dividend window features from xs_dividend_calendar.parquet.")
    # H32: macro regime features as direct training features
    parser.add_argument("--use-macro-regime", action="store_true",
                        help="H32: add macro regime columns (VIX mom, TAIEX, KOSPI, etc.) as training features.")
    # H36: risk-adjusted momentum features
    parser.add_argument("--use-risk-adj", action="store_true",
                        help="H36: add risk-adjusted momentum (rel_sharpe_5d/10d/20d) as training features.")
    # H34: XGBoost tree depth override
    parser.add_argument("--depth", type=int, default=3,
                        help="H34: XGBoost max_depth (default 3). E.g. --depth 5 for deeper trees.")
    # H42: rolling window training
    parser.add_argument("--rolling-window", type=int, default=0,
                        help="H42: use rolling N-year training window instead of expanding. 0 = expanding (default).")
    # H50: VIX as a training feature
    parser.add_argument("--use-vix-feature", action="store_true",
                        help="H50: add VIX level + 5d/20d momentum as training features. "
                             "Lets model learn regime internally — run portfolio with --no-vix-filter.")
    # H77: dormant features
    parser.add_argument("--use-dormant-features", action="store_true",
                        help="H77: enable vol_regime, calendar, CCI, Williams %%R features.")
    # H80: sector-relative momentum features
    parser.add_argument("--use-sector-relative", action="store_true",
                        help="H80: add sector-relative momentum features (sector_rel_1d/5d/20d).")
    # H90: volume/VWAP features
    parser.add_argument("--use-volume-signals", action="store_true",
                        help="H90: add volume features (vol_ratio, obv_roc, vwap_dev_5d, vol_trend).")
    # H92: sector sub-model filter
    parser.add_argument("--sector", type=str, default="",
                        help="H92: restrict universe to tickers in this ICB sector/sub-sector "
                             "(case-insensitive substring match on icb_name2/3/4). "
                             "E.g. --sector 'ngan hang' or --sector 'chung khoan'.")
    # H96: rolling news sentiment
    parser.add_argument("--use-rolling-news", action="store_true",
                        help="H96: add rolling 5d/30d news sentiment features from xs_news_sentiment_rolling.parquet.")
    # H99: custom news sentiment path override
    parser.add_argument("--news-path", type=str, default="",
                        help="H99: override path for news sentiment parquet (used with --use-news). "
                             "Default: data/features/xs_news_sentiment_daily.parquet.")
    # H97: insider deal features
    parser.add_argument("--use-insider", action="store_true",
                        help="H97: add insider deal features from xs_insider_features.parquet.")
    # H98: LLM news features
    parser.add_argument("--use-llm-news", action="store_true",
                        help="H98: add sparse ticker-day LLM features from xs_llm_news_ticker_day.parquet.")
    parser.add_argument("--use-llm-market", action="store_true",
                        help="H98: add dense date-level LLM market features from xs_llm_news_market_daily.parquet.")
    # H100: open/close asymmetry dense ticker-day features
    parser.add_argument("--use-oc-asymmetry", action="store_true",
                        help="H100: add dense open/close asymmetry features from xs_open_close_asymmetry.parquet.")
    # H101: dispersion regime dense date-level features
    parser.add_argument("--use-dispersion-regime", action="store_true",
                        help="H101: add dense cross-sectional dispersion regime features from xs_dispersion_regime_daily.parquet.")
    # H103: return skewness/tail-shape features
    parser.add_argument("--use-return-skewness", action="store_true",
                        help="H103: add dense return skewness features from xs_return_skewness.parquet.")
    # H104: earnings/reporting calendar dense date-level features
    parser.add_argument("--use-earnings-calendar", action="store_true",
                        help="H104: add dense earnings/reporting calendar features from xs_earnings_calendar_daily.parquet.")
    args = parser.parse_args()
    run_cross_sectional_wf(args.min_train_years, args.start_date,
                           args.use_xs_features, args.use_news,
                           args.threshold, args.save_proba, args.use_macro,
                           args.target_horizon, args.barrier_pct,
                           args.model, args.save_all_probas,
                           args.use_xs_fundamentals, args.use_dividend_calendar,
                           args.use_macro_regime, args.use_risk_adj, args.depth,
                           args.rolling_window, args.use_vix_feature,
                           args.use_dormant_features, args.use_sector_relative,
                           args.use_volume_signals, args.sector,
                           args.use_rolling_news, args.news_path,
                           args.use_insider, args.use_llm_news,
                           args.use_llm_market, args.use_oc_asymmetry,
                           args.use_dispersion_regime, args.use_return_skewness,
                           args.use_earnings_calendar)
