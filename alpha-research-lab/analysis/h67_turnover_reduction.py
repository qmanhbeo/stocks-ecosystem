"""
H67: Turnover Reduction via Position Hysteresis.

Problem: H66 kill tests showed 91.3% daily turnover — nearly the entire top-5
changes every day. This drives 637 buy-legs/yr, execution cost, and slippage.

Solution: "Stay-in" rule.
  - Standard (K=N=5): always rebalance to exact top-5 each day.
  - Hysteresis (K>N):  keep a currently-held stock if it's still ranked in the
    top-K today, even if a marginally better stock enters the top-5.
  - Only displace a held stock when it falls below rank K.

This reduces churn without sacrificing the signal — a stock ranked 6th today
is still in the top 1.5% of 393 stocks. Replacing it with rank-5 is noise-trading.

Cost model (per trade day):
  - n_swaps = # positions exited (= # entered, since portfolio stays at size N)
  - daily_cost = (n_swaps / N) × COST_RT
  - With K=5 baseline: ~4.6 swaps/day → 0.27%/day cost
  - With K=8:          ~2-3 swaps/day → 0.13-0.18%/day cost → big net gain

Uses actual E=1 H=1 OHLC excess returns. VIX[15,30] filter, min_proba=0.55.

Usage:
    conda run -n stocks python analysis/h67_turnover_reduction.py
"""
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from path_utils import data_path

warnings.filterwarnings("ignore", category=RuntimeWarning)

DEFAULT_PROBAS = data_path("features/xs_barrier_all_probas_hose_full.parquet")
VIX_PATH  = data_path("fx-commodities/fx_commodities_vix_1D.parquet")
STOCK_DIR = data_path("stock")
VNI_FILE  = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"

START_YEAR = 2015
END_YEAR   = 2025
TOP_N      = 5
MIN_PROBA  = 0.55
VIX_MIN    = 15.0
VIX_MAX    = 30.0
COST_RT    = 0.003   # round-trip per position swap

STAY_IN_K = [5, 6, 7, 8, 10]   # K=5 = baseline (always rebalance)


def load_vni():
    df = pd.read_parquet(VNI_FILE, columns=["time", "open"])
    df["time"] = pd.to_datetime(df["time"])
    return df.sort_values("time").reset_index(drop=True)


def load_prices_e1_h1(tickers, vni):
    """E=1 entry (T+1 open), H=1 exit (T+2 open). Actual excess return over VNINDEX."""
    vni_open  = vni["open"].values
    vni_times = vni["time"].values
    vni_idx   = {t: i for i, t in enumerate(vni_times)}
    ticker_set = set(tickers)
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
        ret_arr = np.full(n, np.nan)
        for i in range(n):
            vi0 = vni_idx.get(times_arr[i])
            if vi0 is None:
                continue
            if i + 2 >= n or vi0 + 2 >= len(vni_open):
                continue
            p_in  = open_arr[i + 1]
            p_out = open_arr[i + 2]
            v_in  = vni_open[vi0 + 1]
            v_out = vni_open[vi0 + 2]
            if p_in <= 0 or v_in <= 0:
                continue
            ret_arr[i] = (p_out / p_in - 1.0) - (v_out / v_in - 1.0)
        df["fwd_e1_h1"] = ret_arr
        records.append(df[["time", "ticker", "fwd_e1_h1"]])

    return pd.concat(records, ignore_index=True) if records else pd.DataFrame()


def simulate_portfolio(merged: pd.DataFrame, K: int) -> dict:
    """
    Simulate top-N portfolio with stay-in threshold K.
      K = N (=5): always rebalance to exact top-N (baseline).
      K > N:      keep currently held stocks if still ranked <= K today.

    Returns per_year dict: {year: {"gross": [...], "net": [...], "swaps": [...], "days": int}}
    """
    grouped   = {date: grp for date, grp in merged.groupby("time")}
    all_dates = sorted(grouped.keys())

    held     = set()
    prev_year = None
    per_year  = {}

    for date in all_dates:
        day  = grouped[date]
        year = date.year

        # Reset held position at year boundary (clean slate each year)
        if year != prev_year:
            held = set()
            prev_year = year

        if year < START_YEAR or year > END_YEAR:
            held = set()
            continue

        vix_val = day["vix"].iloc[0]
        if not (VIX_MIN <= vix_val <= VIX_MAX):
            held = set()  # exit all when VIX out of band
            continue

        # Ideal top-N (in proba order)
        top_n_df = day.nlargest(TOP_N, "xs_proba")
        if top_n_df["xs_proba"].min() < MIN_PROBA:
            held = set()  # signal too weak, exit
            continue

        top_n_tickers = list(top_n_df["ticker"])  # ordered by proba desc

        # Stay-in: which held stocks are still in today's top-K?
        top_k_tickers = set(day.nlargest(K, "xs_proba")["ticker"])
        retained      = held & top_k_tickers

        # Fill remaining slots from top-N (preserving proba order)
        needed    = TOP_N - len(retained)
        additions = [t for t in top_n_tickers if t not in retained][:needed]
        new_held  = retained | set(additions)

        # Safety: ensure exactly TOP_N (shouldn't happen, but guard anyway)
        if len(new_held) < TOP_N:
            extra = [t for t in top_n_tickers if t not in new_held]
            new_held |= set(extra[:TOP_N - len(new_held)])

        # Turnover cost: each sell-then-buy costs COST_RT per position
        if held:
            n_swaps = len(held - new_held)   # positions exited (= positions entered)
        else:
            n_swaps = TOP_N                  # first entry: full position cost

        daily_cost = (n_swaps / TOP_N) * COST_RT

        # Dollar return for the portfolio
        port_data = day[day["ticker"].isin(new_held)]
        rets = port_data["fwd_e1_h1"].dropna().values
        if len(rets) < 2:
            held = new_held
            continue

        gross_ret = rets.mean()
        net_ret   = gross_ret - daily_cost

        if year not in per_year:
            per_year[year] = {"gross": [], "net": [], "swaps": [], "days": 0}
        per_year[year]["gross"].append(gross_ret)
        per_year[year]["net"].append(net_ret)
        per_year[year]["swaps"].append(n_swaps)
        per_year[year]["days"] += 1

        held = new_held

    return per_year


def print_summary(per_year: dict, label: str) -> tuple:
    """Print per-year breakdown. Returns (sh_net, avg_turnover_pct, avg_gross)."""
    print(f"\n  {'year':>5}  {'days':>5}  {'gross/d':>9}  {'net/d':>9}  {'swaps/d':>9}  {'turn%':>7}  {'ann_net':>10}")
    print("  " + "-"*68)

    gross_yr_avgs = []
    net_yr_avgs   = []

    for year in sorted(per_year):
        g = np.mean(per_year[year]["gross"])
        n = np.mean(per_year[year]["net"])
        s = np.mean(per_year[year]["swaps"])
        d = per_year[year]["days"]
        turnover_pct = s / TOP_N * 100
        ann_net = n * d
        gross_yr_avgs.append(g)
        net_yr_avgs.append(n)
        print(f"  {year:>5}  {d:>5}  {g*100:>+8.3f}%  {n*100:>+8.3f}%  "
              f"{s:>8.2f}  {turnover_pct:>6.1f}%  {ann_net*100:>+9.2f}%")

    if not gross_yr_avgs:
        return float("nan"), float("nan"), float("nan")

    avg_gross = np.mean(gross_yr_avgs)
    avg_net   = np.mean(net_yr_avgs)
    sh_gross  = avg_gross / (np.std(gross_yr_avgs) + 1e-9)
    sh_net    = avg_net   / (np.std(net_yr_avgs)   + 1e-9)
    n_pos_net = sum(1 for n in net_yr_avgs if n > 0)
    avg_swaps = np.mean([np.mean(v["swaps"]) for v in per_year.values()])
    avg_turn  = avg_swaps / TOP_N * 100

    print(f"\n  {label}")
    print(f"  Avg gross/day:    {avg_gross*100:>+.3f}%  |  Sharpe (gross): {sh_gross:.2f}")
    print(f"  Avg net/day:      {avg_net*100:>+.3f}%  |  Sharpe (net):   {sh_net:.2f}")
    print(f"  Avg swaps/day:    {avg_swaps:.2f}  |  Avg daily turnover: {avg_turn:.1f}%")
    print(f"  Pos net years:    {n_pos_net}/{len(net_yr_avgs)}")
    return sh_net, avg_turn, avg_gross


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--probas", type=str, default=str(DEFAULT_PROBAS))
    args = parser.parse_args()

    print(f"\nH67: TURNOVER REDUCTION VIA POSITION HYSTERESIS")
    print(f"TOP_N={TOP_N} | MIN_PROBA={MIN_PROBA} | VIX[{VIX_MIN},{VIX_MAX}] | COST_RT={COST_RT*100:.2f}% per swap")
    print(f"Stay-in K values: {STAY_IN_K}  (K=N={TOP_N} is baseline; K>N reduces turnover)")

    probas = pd.read_parquet(args.probas)
    probas["time"] = pd.to_datetime(probas["time"])
    tickers = probas["ticker"].unique().tolist()
    print(f"  {len(probas):,} rows | {len(tickers)} tickers")

    vix = pd.read_parquet(VIX_PATH)[["time", "close"]].rename(columns={"close": "vix"})
    vix["time"] = pd.to_datetime(vix["time"])
    probas = probas.merge(vix, on="time", how="left")
    probas["vix"] = probas["vix"].ffill()

    print(f"Loading E=1 H=1 OHLC prices for {len(tickers)} tickers...")
    vni = load_vni()
    prices = load_prices_e1_h1(tickers, vni)
    print(f"  {len(prices):,} rows")

    merged = probas.merge(prices, on=["time", "ticker"], how="left")
    merged = merged[(merged["time"].dt.year >= START_YEAR) &
                    (merged["time"].dt.year <= END_YEAR)]

    summary_rows = []
    for K in STAY_IN_K:
        lbl = (f"K={K} (baseline — always rebalance)"
               if K == TOP_N else f"K={K} (keep if still in top-{K})")
        print(f"\n{'='*72}")
        print(f"  {lbl}")
        per_year = simulate_portfolio(merged, K)
        sh_net, avg_turn, avg_gross = print_summary(per_year, lbl)
        summary_rows.append({"K": K, "sh_net": sh_net,
                             "avg_turn": avg_turn, "avg_gross": avg_gross})

    # Comparison table
    print(f"\n{'='*72}")
    print(f"SUMMARY: Stay-in threshold sweep")
    print(f"{'='*72}")
    print(f"  {'K':>4}  {'turnover%':>10}  {'gross/d':>9}  {'sh_net':>8}  {'vs_baseline':>12}")
    print("  " + "-"*58)
    baseline_sh = next((r["sh_net"] for r in summary_rows if r["K"] == TOP_N), float("nan"))
    for r in summary_rows:
        note = ""
        if not np.isnan(r["sh_net"]) and not np.isnan(baseline_sh) and baseline_sh != 0:
            delta = (r["sh_net"] / baseline_sh - 1) * 100
            note  = f"{delta:+.1f}%" if r["K"] != TOP_N else "(baseline)"
        if not np.isnan(r["sh_net"]):
            print(f"  {r['K']:>4}  {r['avg_turn']:>9.1f}%  {r['avg_gross']*100:>+8.3f}%  "
                  f"{r['sh_net']:>8.2f}  {note:>12}")

    print(f"\n  Cost logic: each position swap costs {COST_RT*100:.2f}% RT.")
    print(f"  K=5 (baseline): ~91% daily turnover, ~4.6 swaps/day.")
    print(f"  Optimal K: best net Sharpe after accounting for gross return sacrifice.")
    print(f"  Key tension: higher K → fewer swaps → lower cost but potentially staler picks.")


if __name__ == "__main__":
    main()
