"""
H62: 5-Day Hold vs Daily Rebalancing.

The current model predicts 5-day excess returns and rebalances DAILY.
This creates two practical problems:
  1. T+2 settlement: can't sell today and rebuy tomorrow freely
  2. High turnover: ~250 trades/yr × 5 stocks = 1250 trade-legs/yr

This experiment tests: HOLD EACH POSITION FOR 5 TRADING DAYS.
  - Signal fires on day T (model output)
  - Enter at T+1 OPEN (avoids T+0 close lookahead, satisfies T+2 realistically)
  - Hold until T+6 OPEN
  - Rebalance: (a) daily-signal with 5d hold, (b) every-5d-signal with 5d hold

Key comparisons (all using actual OHLC returns, not binary labels):
  - E=1 H=1  daily:    baseline (current strategy, realistic entry)
  - E=1 H=5  daily:    same entry, hold 5 days — cost 1x instead of 5x
  - E=1 H=5  weekly:   signal every 5d, hold 5d — non-overlapping (cleanest)

Usage:
    conda run -n stocks python analysis/h62_five_day_hold.py
"""
import argparse
import warnings
import numpy as np
import pandas as pd
from pathlib import Path

warnings.filterwarnings("ignore", category=RuntimeWarning)

DEFAULT_PROBAS = Path("data/features/xs_barrier_all_probas_hose_full.parquet")
VIX_PATH   = Path("data/fx-commodities/fx_commodities_vix_1D.parquet")
STOCK_DIR  = Path("data/stock")
VNI_FILE   = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"

START_YEAR = 2015
END_YEAR   = 2025
TOP_N      = 5
MIN_PROBA  = 0.55
VIX_MIN    = 15.0
VIX_MAX    = 30.0
COST_RT    = 0.003   # 0.30% round-trip


def load_vni() -> pd.DataFrame:
    df = pd.read_parquet(VNI_FILE, columns=["time", "open", "close"])
    df["time"] = pd.to_datetime(df["time"])
    return df.sort_values("time").reset_index(drop=True)


def load_prices(tickers: list, vni: pd.DataFrame, hold_days: list = [1, 5]) -> pd.DataFrame:
    """
    Load open prices for each ticker, compute E=1 forward relative returns
    for each hold period. Entry: T+1 open. Exit: T+1+H open.
    """
    vni_open  = vni["open"].values
    vni_times = vni["time"].values
    vni_idx   = {t: i for i, t in enumerate(vni_times)}

    ticker_set = set(tickers)
    col_names  = [f"fwd_e1_h{h}" for h in hold_days]
    records = []

    for sf in sorted(STOCK_DIR.glob("gia_lich_su_*_1D.parquet")):
        ticker = sf.name.replace("gia_lich_su_", "").replace("_1D.parquet", "")
        if ticker not in ticker_set or ticker == "VNINDEX":
            continue
        try:
            df = pd.read_parquet(sf, columns=["time", "open"])
        except Exception:
            continue
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time").reset_index(drop=True)
        df["ticker"] = ticker

        open_arr  = df["open"].values.astype(float)
        times_arr = df["time"].values
        n = len(df)

        for h in hold_days:
            col = f"fwd_e1_h{h}"
            arr = np.full(n, np.nan)
            for i in range(n):
                vi0 = vni_idx.get(times_arr[i])
                if vi0 is None:
                    continue
                si_entry = i + 1          # T+1 stock
                si_exit  = i + 1 + h      # T+1+H stock
                vi_entry = vi0 + 1        # T+1 vni
                vi_exit  = vi0 + 1 + h    # T+1+H vni
                if si_exit >= n or vi_exit >= len(vni_open):
                    continue
                p_in  = open_arr[si_entry]
                p_out = open_arr[si_exit]
                v_in  = vni_open[vi_entry]
                v_out = vni_open[vi_exit]
                if p_in <= 0 or v_in <= 0:
                    continue
                arr[i] = (p_out / p_in - 1.0) - (v_out / v_in - 1.0)
            df[col] = arr

        records.append(df[["time", "ticker"] + col_names])

    return pd.concat(records, ignore_index=True) if records else pd.DataFrame()


def run_analysis(merged: pd.DataFrame, hold_days: list):
    """
    Compare three portfolio strategies:
    A. Daily signal, H=1 hold (current approach)
    B. Daily signal, H=5 hold (same entry every day, hold 5d)
    C. Weekly signal, H=5 hold (entry every 5 trading days, hold 5d, non-overlapping)
    """
    print(f"\n{'='*78}")
    print(f"STRATEGY COMPARISON (E=1 open, VIX[{VIX_MIN},{VIX_MAX}], min_proba={MIN_PROBA}, top-{TOP_N})")
    print(f"{'='*78}")

    strategies = {
        "A: Daily H=1":  {"col": "fwd_e1_h1",  "weekly": False},
        "B: Daily H=5":  {"col": "fwd_e1_h5",  "weekly": False},
        "C: Weekly H=5": {"col": "fwd_e1_h5",  "weekly": True},
    }

    results = {}
    for name, cfg in strategies.items():
        col = cfg["col"]
        if col not in merged.columns:
            continue

        per_year = []
        for year, grp in merged.groupby(merged["time"].dt.year):
            if year < START_YEAR or year > END_YEAR:
                continue
            naive = grp["actual"].mean()
            trade_returns = []
            last_signal_day = -999  # for weekly spacing

            dates = sorted(grp["time"].unique())
            for day_idx, date in enumerate(dates):
                day = grp[grp["time"] == date]
                vix_val = day["vix"].iloc[0]
                if not (VIX_MIN <= vix_val <= VIX_MAX):
                    continue

                # Weekly signal: skip if last signal was < 5 trading days ago
                if cfg["weekly"] and day_idx - last_signal_day < 5:
                    continue

                top = day.nlargest(TOP_N, "xs_proba")
                if top["xs_proba"].min() < MIN_PROBA:
                    continue
                if top[col].isna().all():
                    continue

                rets = top[col].dropna().values
                if len(rets) == 0:
                    continue

                last_signal_day = day_idx
                trade_returns.append(rets.mean())

            if len(trade_returns) >= 5:
                avg_gross = np.mean(trade_returns)
                # For H=5: cost is 0.30% RT per 5-day trade (NOT per day)
                # For H=1: cost is 0.30% RT per 1-day trade
                h = int(col.split("_h")[1])
                # Compare on annualized basis: multiply by trades/yr
                n_trades_yr = len(trade_returns)
                per_year.append({
                    "year": year,
                    "avg_gross": avg_gross,
                    "n_trades": n_trades_yr,
                    "naive": naive,
                })

        if not per_year:
            continue

        gross_edges = [r["avg_gross"] for r in per_year]
        avg_gross = np.mean(gross_edges)
        sharpe_gross = avg_gross / (np.std(gross_edges) + 1e-9)
        avg_trades = np.mean([r["n_trades"] for r in per_year])
        n_pos = sum(1 for e in gross_edges if e > 0)

        # Net return per trade after RT cost
        net_per_trade = avg_gross - COST_RT
        # Annual net excess from this strategy
        annual_net = net_per_trade * avg_trades

        results[name] = {
            "avg_gross": avg_gross, "sharpe_gross": sharpe_gross,
            "avg_trades": avg_trades, "n_pos": n_pos, "n_years": len(per_year),
            "net_per_trade": net_per_trade, "annual_net": annual_net,
            "per_year": per_year,
        }

    # Summary table
    print(f"\n  {'Strategy':<20}  {'gross/trade':>12}  {'net/trade':>10}  {'trades/yr':>10}  "
          f"{'net_ann':>10}  {'sharpe':>8}  {'pos':>6}")
    print("  " + "-"*80)
    for name, r in results.items():
        print(f"  {name:<20}  {r['avg_gross']*100:>+11.3f}%  {r['net_per_trade']*100:>+9.3f}%  "
              f"{r['avg_trades']:>10.1f}  {r['annual_net']*100:>+9.2f}%  "
              f"{r['sharpe_gross']:>8.2f}  {r['n_pos']}/{r['n_years']}")

    # Per-year breakdown for each strategy
    for name, r in results.items():
        print(f"\n  PER-YEAR — {name}")
        print(f"  {'year':>6}  {'n_trades':>9}  {'gross/trade':>12}  {'net/trade':>11}  {'ann_net':>10}")
        print("  " + "-"*55)
        for yr in r["per_year"]:
            net = yr["avg_gross"] - COST_RT
            ann = net * yr["n_trades"]
            print(f"  {yr['year']:>6}  {yr['n_trades']:>9}  {yr['avg_gross']*100:>+11.3f}%  "
                  f"{net*100:>+10.3f}%  {ann*100:>+9.2f}%")

    # Head-to-head: cost advantage of 5-day hold
    if "A: Daily H=1" in results and "C: Weekly H=5" in results:
        a = results["A: Daily H=1"]
        c = results["C: Weekly H=5"]
        print(f"\n  HEAD-TO-HEAD: Daily H=1 vs Weekly H=5")
        print(f"  Daily  H=1 : {a['avg_gross']*100:+.3f}% gross/trade, "
              f"{a['avg_trades']:.0f} trades/yr, {a['annual_net']*100:+.2f}% net/yr")
        print(f"  Weekly H=5 : {c['avg_gross']*100:+.3f}% gross/trade, "
              f"{c['avg_trades']:.0f} trades/yr, {c['annual_net']*100:+.2f}% net/yr")
        gain = c['annual_net'] - a['annual_net']
        print(f"  Annual net gain from 5d hold: {gain*100:+.2f}%")
        print(f"  (Lower turnover saves ~{(a['avg_trades']-c['avg_trades'])*COST_RT*100:.1f}% cost/yr)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probas", type=str, default=str(DEFAULT_PROBAS))
    args = parser.parse_args()

    print(f"\nH62: 5-DAY HOLD vs DAILY REBALANCING")
    print(f"Loading probas: {args.probas}")
    probas = pd.read_parquet(args.probas)
    probas["time"] = pd.to_datetime(probas["time"])
    tickers = probas["ticker"].unique().tolist()
    print(f"  {len(probas):,} rows | {len(tickers)} tickers | years {probas['year'].min()}-{probas['year'].max()}")

    print(f"Loading VIX...")
    vix = pd.read_parquet(VIX_PATH)[["time", "close"]].rename(columns={"close": "vix"})
    vix["time"] = pd.to_datetime(vix["time"])
    probas = probas.merge(vix, on="time", how="left")
    probas["vix"] = probas["vix"].ffill()

    print(f"Loading OHLC prices for {len(tickers)} tickers (E=1, H=1 and H=5)...")
    vni = load_vni()
    prices = load_prices(tickers, vni, hold_days=[1, 5])
    print(f"  Price data: {len(prices):,} rows")

    merged = probas.merge(prices, on=["time", "ticker"], how="left")
    merged = merged[(merged["time"].dt.year >= START_YEAR) & (merged["time"].dt.year <= END_YEAR)]

    run_analysis(merged, hold_days=[1, 5])


if __name__ == "__main__":
    main()
