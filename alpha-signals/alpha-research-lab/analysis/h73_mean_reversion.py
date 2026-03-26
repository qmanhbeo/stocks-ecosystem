"""
H73: Mean-Reversion Baseline — Does XGBoost add value over a simple rule?

Hostile reviewer concern: XGBoost cross-sectional model may just be capturing
short-term mean reversion — a well-known equity effect. If so, a simple rule
(buy the week's biggest losers) would produce comparable IC to the full model.

Method:
  1. Compute 5-day and 10-day rolling past excess return per stock over VNINDEX.
     Past excess return = (stock_close_T / stock_close_{T-k}) - (vni_close_T / vni_close_{T-k})
     MR signal = -past_excess (buy laggards)
  2. Daily Spearman(MR_signal, actual_tomorrow_outperform)
  3. Compare IC_mr5, IC_mr10 vs IC_model (Spearman(xs_proba, actual))
  4. Correlation test: Spearman(MR_signal, xs_proba) per day -- does model encode MR?

Interpretation:
  IC_mr ~= IC_model: XGBoost is essentially an elaborate MR rule -- limited value added.
  IC_mr << IC_model: XGBoost captures something fundamentally different -- genuine alpha.
  High corr(MR, xs_proba): model explicitly learned MR; lower uniqueness.

Uses close prices for past returns and binary actual from probas file for outcome.

Usage:
    conda run -n stocks python analysis/h73_mean_reversion.py
"""
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.stats import spearmanr

warnings.filterwarnings("ignore", category=RuntimeWarning)

DEFAULT_PROBAS = Path("data/features/xs_barrier_all_probas_hose_full.parquet")
STOCK_DIR      = Path("data/stock")
VNI_FILE       = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"

START_YEAR = 2015
MR_WINDOWS = [5, 10]   # lookback days for mean-reversion signal


def load_close_prices(tickers: list) -> pd.DataFrame:
    """Load daily close prices for all tickers. Returns tidy (time, ticker, close)."""
    ticker_set = set(tickers)
    records = []
    for sf in sorted(STOCK_DIR.glob("gia_lich_su_*_1D.parquet")):
        ticker = sf.name.replace("gia_lich_su_", "").replace("_1D.parquet", "")
        if ticker not in ticker_set or ticker == "VNINDEX":
            continue
        try:
            df = pd.read_parquet(sf, columns=["time", "close"])
        except Exception:
            continue
        df["time"] = pd.to_datetime(df["time"])
        df["ticker"] = ticker
        records.append(df[["time", "ticker", "close"]])
    return pd.concat(records, ignore_index=True) if records else pd.DataFrame()


def load_vni_close() -> pd.DataFrame:
    df = pd.read_parquet(VNI_FILE, columns=["time", "close"])
    df["time"] = pd.to_datetime(df["time"])
    return df.sort_values("time").reset_index(drop=True)


def compute_daily_ic(df: pd.DataFrame, signal_col: str, outcome_col: str,
                     min_stocks: int = 20) -> list:
    """Daily cross-sectional Spearman IC. Returns list of (ic, n_stocks)."""
    ics = []
    for _, day in df.groupby("time"):
        sub = day[[signal_col, outcome_col]].dropna()
        if len(sub) < min_stocks:
            continue
        ic, _ = spearmanr(sub[signal_col], sub[outcome_col])
        if not np.isnan(ic):
            ics.append(ic)
    return ics


def compute_daily_corr(df: pd.DataFrame, col_a: str, col_b: str,
                       min_stocks: int = 20) -> list:
    """Daily Spearman correlation between two signals. Returns list of corr values."""
    corrs = []
    for _, day in df.groupby("time"):
        sub = day[[col_a, col_b]].dropna()
        if len(sub) < min_stocks:
            continue
        r, _ = spearmanr(sub[col_a], sub[col_b])
        if not np.isnan(r):
            corrs.append(r)
    return corrs


def print_ic_year_table(df: pd.DataFrame, signal_cols: list, outcome_col: str,
                         labels: list) -> None:
    """Print year-by-year IC table for multiple signals side by side."""
    years = sorted(df["time"].dt.year.unique())
    header = f"  {'year':>5}  " + "  ".join(f"{lbl:>12}" for lbl in labels)
    print(header)
    print("  " + "-" * (7 + 14 * len(labels)))
    for yr in years:
        yr_df = df[df["time"].dt.year == yr]
        vals = []
        for col in signal_cols:
            ics = compute_daily_ic(yr_df, col, outcome_col)
            vals.append(f"{np.mean(ics):>+12.4f}" if ics else f"{'n/a':>12}")
        print(f"  {yr:>5}  " + "  ".join(vals))


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--probas", type=str, default=str(DEFAULT_PROBAS))
    args = parser.parse_args()

    print("\nH73: MEAN-REVERSION BASELINE")
    print("Does XGBoost add value over a simple buy-the-losers rule?")

    probas = pd.read_parquet(args.probas)
    probas["time"] = pd.to_datetime(probas["time"])
    tickers = probas["ticker"].unique().tolist()
    print(f"  {len(probas):,} rows | {len(tickers)} tickers")

    # Load close prices
    print(f"Loading close prices for {len(tickers)} tickers...")
    closes = load_close_prices(tickers)
    vni    = load_vni_close().rename(columns={"close": "vni_close"})
    print(f"  {len(closes):,} rows loaded")

    # Pivot to wide format for vectorised rolling
    print("Computing rolling past-return signals...")
    wide = closes.pivot(index="time", columns="ticker", values="close")
    wide = wide.sort_index()

    vni = vni.set_index("time")["vni_close"]
    vni = vni.reindex(wide.index).ffill()

    # Compute rolling k-day log-return excess over VNINDEX
    # excess_{t,k} = log(close_t / close_{t-k}) - log(vni_t / vni_{t-k})
    mr_signals = {}
    for k in MR_WINDOWS:
        stock_ret = np.log(wide / wide.shift(k))
        vni_ret   = np.log(vni / vni.shift(k))
        excess    = stock_ret.sub(vni_ret, axis=0)
        # MR signal = -excess (buy the recent underperformers)
        mr_wide = -excess
        mr_long = mr_wide.stack().reset_index()
        mr_long.columns = ["time", "ticker", f"mr{k}"]
        mr_signals[k] = mr_long

    # Merge all MR signals with probas
    merged = probas[probas["time"].dt.year >= START_YEAR].copy()
    for k in MR_WINDOWS:
        merged = merged.merge(mr_signals[k], on=["time", "ticker"], how="left")

    signal_cols = [f"mr{k}" for k in MR_WINDOWS] + ["xs_proba"]
    labels      = [f"IC_mr{k}" for k in MR_WINDOWS] + ["IC_model"]

    # --- Overall IC ---
    print(f"\n{'='*65}")
    print(f"OVERALL IC COMPARISON  ({START_YEAR}-2025)")
    print(f"{'='*65}")
    print(f"  {'Signal':<15}  {'Mean IC':>9}  {'Std IC':>8}  {'n_days':>7}  {'t-stat':>7}")
    print(f"  {'-'*55}")

    ic_results = {}
    for col, lbl in zip(signal_cols, labels):
        ics = compute_daily_ic(merged, col, "actual")
        if not ics:
            continue
        mean_ic = np.mean(ics)
        std_ic  = np.std(ics)
        t_stat  = mean_ic / (std_ic / np.sqrt(len(ics)) + 1e-9)
        ic_results[col] = {"mean": mean_ic, "std": std_ic, "n": len(ics), "t": t_stat}
        print(f"  {lbl:<15}  {mean_ic:>+9.4f}  {std_ic:>8.4f}  {len(ics):>7}  {t_stat:>7.1f}")

    # IC comparison summary
    if "mr5" in ic_results and "xs_proba" in ic_results:
        ratio = ic_results["mr5"]["mean"] / ic_results["xs_proba"]["mean"]
        print(f"\n  MR-5d as % of model IC: {ratio*100:.1f}%")
        if ratio > 0.70:
            print("  CONCERN: Mean reversion explains >70% of model IC.")
            print("  XGBoost may add limited incremental value over simple MR rule.")
        elif ratio > 0.40:
            print("  MODERATE: MR explains 40-70% of model IC.")
            print("  Model likely captures MR plus additional factors.")
        else:
            print("  PASS: MR explains <40% of model IC.")
            print("  XGBoost captures a fundamentally different signal from pure MR.")

    # --- Year-by-year ---
    print(f"\n{'='*65}")
    print(f"YEAR-BY-YEAR IC BREAKDOWN")
    print(f"{'='*65}")
    print_ic_year_table(merged, signal_cols, "actual", labels)

    # --- Signal correlation: does model encode MR? ---
    print(f"\n{'='*65}")
    print(f"SIGNAL CORRELATION: Spearman(MR_signal, xs_proba)")
    print(f"{'='*65}")
    print(f"  High correlation -> model learned MR feature explicitly.")
    print(f"  Low correlation  -> model uses different information.")
    print(f"\n  {'Signal pair':<20}  {'Mean corr':>10}  {'Std corr':>9}  {'n_days':>7}")
    print(f"  {'-'*55}")
    for k in MR_WINDOWS:
        corrs = compute_daily_corr(merged, f"mr{k}", "xs_proba")
        if corrs:
            mc = np.mean(corrs)
            sc = np.std(corrs)
            print(f"  {'MR-'+str(k)+'d vs model':<20}  {mc:>+10.4f}  {sc:>9.4f}  {len(corrs):>7}")

    print(f"\n  If corr(MR, model) is low (<0.2) but IC_mr is also low: signals are")
    print(f"  uncorrelated AND mr adds no value -> model is genuinely different.")
    print(f"  If corr is high (>0.4) AND IC_mr ~= IC_model: model just adds complexity")
    print(f"  to a simple rule without new information.")


if __name__ == "__main__":
    main()
