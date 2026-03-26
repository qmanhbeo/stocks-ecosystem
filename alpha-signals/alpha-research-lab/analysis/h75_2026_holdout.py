"""
H75: 2026 live validation for the current H54 signal family.

This script scores all rows in year == 2026 using the same feature engineering
and model infrastructure as the production cross-sectional barrier pipeline,
then evaluates:
1. cross-sectional IC vs prior years
2. executable E=1 H=1 portfolio returns on the 2026 slice

Unlike the earlier terminal-only holdout script, this version also:
- saves the 2026 scored probabilities to a permanent parquet artifact
- writes a compact machine-readable run summary under artifacts/run_summaries/

Usage:
    conda run -n stocks python analysis/h75_2026_holdout.py
    conda run -n stocks python analysis/h75_2026_holdout.py --no-vix-filter
"""

import argparse
import glob
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_loader import load_data
from src.feature_engineering import generate_features, get_feature_columns
from src.model_factory import get_model
from src.run_summary import write_run_summary

warnings.filterwarnings("ignore")


STOCK_DIR = Path("data/stock")
VIX_PATH = Path("data/fx-commodities/fx_commodities_vix_1D.parquet")
VNI_FILE = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
EXCLUDE = {"VNINDEX", "VN30"}

START_DATE = "2012-01-01"
TEST_YEAR = 2026
MIN_ROWS = 300

COST_RT = 0.003
TOP_N = 5
MIN_PROBA = 0.55
VIX_MIN = 15.0
VIX_MAX = 30.0

DEFAULT_SAVE_PROBAS = Path("data/features/xs_live_validation_h54_2026.parquet")
PRIOR_PROBAS_PATH = Path("data/features/xs_barrier_all_probas_hose_full.parquet")

MODEL_CONFIG = {
    "data": {
        "target_col": "future_rel_barrier_5d",
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
        "use_volume_signals": False,
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


def square_weights(probas: np.ndarray) -> np.ndarray:
    weights = np.maximum(probas - 0.5, 1e-6) ** 2
    return weights / weights.sum()


def load_all_stocks() -> pd.DataFrame:
    files = sorted(glob.glob(str(STOCK_DIR / "gia_lich_su_*_1D.parquet")))
    frames = []
    for file_path in files:
        ticker = Path(file_path).stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        config = json.loads(json.dumps(MODEL_CONFIG))
        config["data"]["file_path"] = file_path
        try:
            df_raw = load_data(file_path, START_DATE)
            if len(df_raw) < MIN_ROWS:
                continue
            df_feat = generate_features(df_raw, config)
            if len(df_feat) < 100:
                continue
            df_feat["ticker"] = ticker
            frames.append(df_feat)
        except Exception:
            continue
    all_df = pd.concat(frames, ignore_index=True)
    print(f"  Loaded {len(frames)} stocks, {len(all_df):,} total rows")
    return all_df


def load_prices_e1_h1(tickers: list[str], vni: pd.DataFrame) -> pd.DataFrame:
    vni_open = vni["open"].values
    vni_times = vni["time"].values
    vni_idx = {t: i for i, t in enumerate(vni_times)}
    ticker_set = set(tickers)
    records = []

    for stock_file in sorted(STOCK_DIR.glob("gia_lich_su_*_1D.parquet")):
        ticker = stock_file.name.replace("gia_lich_su_", "").replace("_1D.parquet", "")
        if ticker not in ticker_set or ticker == "VNINDEX":
            continue
        try:
            df = pd.read_parquet(stock_file, columns=["time", "open"])
        except Exception:
            continue

        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time").reset_index(drop=True)
        df["ticker"] = ticker

        open_arr = df["open"].values.astype(float)
        times_arr = df["time"].values
        n_rows = len(df)
        ret_arr = np.full(n_rows, np.nan)

        for i in range(n_rows):
            vni_pos = vni_idx.get(times_arr[i])
            if vni_pos is None:
                continue
            if i + 2 >= n_rows or vni_pos + 2 >= len(vni_open):
                continue
            p_in = open_arr[i + 1]
            p_out = open_arr[i + 2]
            v_in = vni_open[vni_pos + 1]
            v_out = vni_open[vni_pos + 2]
            if p_in <= 0 or v_in <= 0:
                continue
            ret_arr[i] = (p_out / p_in - 1.0) - (v_out / v_in - 1.0)

        df["fwd_e1_h1"] = ret_arr
        records.append(df[["time", "ticker", "fwd_e1_h1"]])

    if not records:
        return pd.DataFrame(columns=["time", "ticker", "fwd_e1_h1"])
    return pd.concat(records, ignore_index=True)


def compute_daily_ics(df: pd.DataFrame) -> list[float]:
    values = []
    for _, day in df.groupby("time"):
        if len(day) < 5:
            continue
        ic, _ = spearmanr(day["xs_proba"], day["actual"])
        if not np.isnan(ic):
            values.append(float(ic))
    return values


def summarize_prior_ics() -> dict:
    prior_rows = []
    if not PRIOR_PROBAS_PATH.exists():
        return {"rows": prior_rows}

    prior = pd.read_parquet(PRIOR_PROBAS_PATH)
    prior["time"] = pd.to_datetime(prior["time"])

    print(f"  {'year':>5}  {'IC':>8}  {'n_days':>7}  {'n_tickers':>10}")
    print(f"  {'-' * 40}")
    for year in sorted(prior["time"].dt.year.unique()):
        if year < 2015:
            continue
        year_df = prior[prior["time"].dt.year == year]
        daily_ics = compute_daily_ics(year_df)
        if not daily_ics:
            continue
        avg_ic = float(np.mean(daily_ics))
        n_days = len(daily_ics)
        n_tickers = int(year_df["ticker"].nunique())
        print(f"  {year:>5}  {avg_ic:>+8.4f}  {n_days:>7}  {n_tickers:>10}")
        prior_rows.append(
            {
                "year": int(year),
                "avg_ic": round(avg_ic, 6),
                "n_days": n_days,
                "n_tickers": n_tickers,
            }
        )
    return {"rows": prior_rows}


def run_portfolio(probas_2026: pd.DataFrame, use_vix_filter: bool) -> dict:
    vix = pd.read_parquet(VIX_PATH)[["time", "close"]].rename(columns={"close": "vix"})
    vix["time"] = pd.to_datetime(vix["time"])

    tickers = probas_2026["ticker"].unique().tolist()
    vni = pd.read_parquet(VNI_FILE, columns=["time", "open"])
    vni["time"] = pd.to_datetime(vni["time"])
    vni = vni.sort_values("time").reset_index(drop=True)
    prices = load_prices_e1_h1(tickers, vni)

    merged = probas_2026.merge(vix, on="time", how="left")
    merged["vix"] = merged["vix"].ffill()
    merged = merged.merge(prices, on=["time", "ticker"], how="left")

    ew_trades = []
    sq_trades = []
    skipped_vix = 0
    skipped_conf = 0

    for _, day in merged.groupby("time"):
        vix_val = float(day["vix"].iloc[0])
        if use_vix_filter and not (VIX_MIN <= vix_val <= VIX_MAX):
            skipped_vix += 1
            continue

        top = day.nlargest(TOP_N, "xs_proba")
        if len(top) < TOP_N or top["xs_proba"].min() < MIN_PROBA:
            skipped_conf += 1
            continue

        valid = top.dropna(subset=["fwd_e1_h1"])
        if len(valid) < 2:
            continue

        returns = valid["fwd_e1_h1"].values
        probas = valid["xs_proba"].values
        ew_trades.append(float(returns.mean()))
        sq_trades.append(float((square_weights(probas) * returns).sum()))

    def build_trade_summary(trades: list[float], label: str) -> dict | None:
        if not trades:
            return None
        gross = float(np.mean(trades))
        net = gross - COST_RT
        std = float(np.std(trades))
        return {
            "label": label,
            "trades": len(trades),
            "gross_per_trade": round(gross, 6),
            "net_per_trade": round(net, 6),
            "trade_std": round(std, 6),
            "positive_trade_rate": round(float(np.mean(np.array(trades) > 0)), 6),
        }

    return {
        "equal_weight": build_trade_summary(ew_trades, "equal_weight"),
        "square_weight": build_trade_summary(sq_trades, "square_weight"),
        "days_total": int(probas_2026["time"].nunique()),
        "days_skipped_vix": skipped_vix,
        "days_skipped_confidence": skipped_conf,
    }


def main():
    global VIX_MIN, VIX_MAX

    parser = argparse.ArgumentParser()
    parser.add_argument("--no-vix-filter", action="store_true")
    parser.add_argument("--save-probas", type=str, default=str(DEFAULT_SAVE_PROBAS))
    args = parser.parse_args()

    use_vix_filter = not args.no_vix_filter
    if args.no_vix_filter:
        VIX_MIN, VIX_MAX = 0.0, 999.0

    print("\nH75: 2026 LIVE VALIDATION")
    print("=" * 72)
    print(f"  Test year: {TEST_YEAR}")
    print(f"  Portfolio: TOP_N={TOP_N}, MIN_PROBA={MIN_PROBA}, COST_RT={COST_RT*100:.2f}%")
    print(f"  VIX filter: {'ON' if use_vix_filter else 'OFF'} [{VIX_MIN:.0f}, {VIX_MAX:.0f}]")
    print("=" * 72)

    print("\nLoading features for all stocks...")
    all_df = load_all_stocks()
    all_df["_year"] = pd.to_datetime(all_df["time"]).dt.year

    feature_cols = get_feature_columns(all_df, MODEL_CONFIG)
    target_col = MODEL_CONFIG["data"]["target_col"]

    train_df = all_df[all_df["_year"] < TEST_YEAR].copy()
    test_df = all_df[all_df["_year"] == TEST_YEAR].copy()

    print(
        f"  Train: {len(train_df):,} rows ({train_df['_year'].min()}-{train_df['_year'].max()})"
    )
    print(
        f"  Test:  {len(test_df):,} rows ({TEST_YEAR}) | "
        f"{test_df['ticker'].nunique()} tickers | {test_df['time'].nunique()} days"
    )

    if len(test_df) < 50:
        raise SystemExit(f"[H75] insufficient {TEST_YEAR} test data: {len(test_df)} rows")

    print(f"\nTraining XGBoost on {len(train_df):,} rows (years < {TEST_YEAR})...")
    x_train = train_df[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0)
    y_train = train_df[target_col]
    valid_train = y_train.notna() & np.isfinite(y_train) & (y_train.abs() < 10)
    x_train = x_train[valid_train]
    y_train = y_train[valid_train]

    x_test = test_df[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0)
    y_test = test_df[target_col]
    valid_test = y_test.notna() & np.isfinite(y_test) & (y_test.abs() < 10)
    x_test = x_test[valid_test]
    y_test = y_test[valid_test]
    test_df = test_df[valid_test.values].copy()

    n_val = max(500, int(len(x_train) * 0.12))
    x_tr, y_tr = x_train.iloc[:-n_val], y_train.iloc[:-n_val]
    x_val, y_val = x_train.iloc[-n_val:], y_train.iloc[-n_val:]

    model = get_model(MODEL_CONFIG)
    model.fit(x_tr, y_tr, eval_set=[(x_val, y_val)], verbose=False)
    print("  Training complete.")

    probas_arr = model.predict_proba(x_test)[:, 1]
    actuals = y_test.values.astype(int)

    probas_2026 = pd.DataFrame(
        {
            "time": pd.to_datetime(test_df["time"].values),
            "year": TEST_YEAR,
            "ticker": test_df["ticker"].values,
            "xs_proba": probas_arr.round(4),
            "actual": actuals,
        }
    ).sort_values(["time", "ticker"]).reset_index(drop=True)

    save_path = Path(args.save_probas)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    probas_2026.to_parquet(save_path, index=False)

    n_tickers = int(probas_2026["ticker"].nunique())
    n_days = int(probas_2026["time"].nunique())
    date_min = probas_2026["time"].min().strftime("%Y-%m-%d")
    date_max = probas_2026["time"].max().strftime("%Y-%m-%d")
    print(
        f"\nSaved 2026 probas: {n_tickers} tickers | {n_days} days | "
        f"{date_min} to {date_max}"
    )
    print(
        f"  Proba distribution: min={probas_arr.min():.3f}, "
        f"mean={probas_arr.mean():.3f}, max={probas_arr.max():.3f}"
    )
    print(f"  Artifact: {save_path}")

    print("\nIC vs prior years")
    print("-" * 72)
    prior_ic = summarize_prior_ics()
    ic_2026_days = compute_daily_ics(probas_2026)
    ic_2026 = float(np.mean(ic_2026_days)) if ic_2026_days else float("nan")
    print(f"  {TEST_YEAR:>5}  {ic_2026:>+8.4f}  {len(ic_2026_days):>7}  {n_tickers:>10}  <-- live")

    print("\nExecutable portfolio check (E=1 H=1)")
    print("-" * 72)
    portfolio = run_portfolio(probas_2026, use_vix_filter=use_vix_filter)
    for key in ("equal_weight", "square_weight"):
        row = portfolio[key]
        if not row:
            print(f"  {key}: no trades")
            continue
        print(
            f"  {key:>13}: trades={row['trades']:>3} | "
            f"gross/trade={row['gross_per_trade']*100:+.3f}% | "
            f"net/trade={row['net_per_trade']*100:+.3f}%"
        )

    primary = portfolio["equal_weight"] if portfolio["equal_weight"] else portfolio["square_weight"]
    live_verdict = "fail"
    if not np.isnan(ic_2026):
        if ic_2026 >= 0.10 and primary and primary["gross_per_trade"] > 0:
            live_verdict = "pass"
        elif ic_2026 >= 0.05:
            live_verdict = "weak_pass"

    ts = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    summary_path = write_run_summary(
        ts=ts,
        mode="live_validation",
        name="h75_2026_holdout_h54",
        summary={
            "test_year": TEST_YEAR,
            "date_min": date_min,
            "date_max": date_max,
            "n_tickers": n_tickers,
            "n_days": n_days,
            "ic_2026": round(ic_2026, 6) if not np.isnan(ic_2026) else None,
            "n_ic_days": len(ic_2026_days),
            "portfolio": portfolio,
            "verdict": live_verdict,
        },
        artifacts={"probas_2026": str(save_path)},
        metadata={
            "top_n": TOP_N,
            "min_proba": MIN_PROBA,
            "cost_rt": COST_RT,
            "vix_min": VIX_MIN,
            "vix_max": VIX_MAX,
            "use_vix_filter": use_vix_filter,
            "prior_probas_path": str(PRIOR_PROBAS_PATH),
            "prior_ic_rows": prior_ic["rows"],
        },
    )
    print(f"\nRun summary saved to {summary_path}")


if __name__ == "__main__":
    main()
