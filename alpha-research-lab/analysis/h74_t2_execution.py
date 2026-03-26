"""
H74: T+2 Execution — Does signal survive one-day execution delay?

Hostile reviewer concern: the model's edge may live in the microstructure gap
between signal generation (end of day T) and the T+1 open. If execution is
delayed by one day (enter at T+2 open instead of T+1 open), returns may collapse.

Current setup (H54/H63 baseline):
  Signal at T -> Entry T+1 open -> Exit T+2 open   (E=1 H=1)

T+2 test (H74):
  Signal at T -> Entry T+2 open -> Exit T+3 open   (E=2 H=1)

A one-day delay is realistic: order not filled at open due to volume limit,
broker delay, or simply missed the session.

Both are run with H54 fixed params: TOP_N=5, MIN_PROBA=0.55, VIX[15,30], COST_RT=0.30%.

If E=2 H=1 net Sharpe remains positive -> signal is durable, not microstructure.
If E=2 H=1 collapses -> edge is purely in the T+1 open price reaction.

Usage:
    conda run -n stocks python analysis/h74_t2_execution.py
"""
import warnings
import numpy as np
import pandas as pd
from pathlib import Path

warnings.filterwarnings("ignore", category=RuntimeWarning)

DEFAULT_PROBAS = Path("data/features/xs_barrier_all_probas_hose_full.parquet")
VIX_PATH  = Path("data/fx-commodities/fx_commodities_vix_1D.parquet")
STOCK_DIR = Path("data/stock")
VNI_FILE  = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"

START_YEAR = 2015
END_YEAR   = 2025
TOP_N      = 5
MIN_PROBA  = 0.55
VIX_MIN    = 15.0
VIX_MAX    = 30.0
COST_RT    = 0.003


def load_vni():
    df = pd.read_parquet(VNI_FILE, columns=["time", "open"])
    df["time"] = pd.to_datetime(df["time"])
    return df.sort_values("time").reset_index(drop=True)


def load_prices(tickers: list, vni: pd.DataFrame, entry_lag: int) -> pd.DataFrame:
    """
    Load E=entry_lag H=1 excess returns over VNINDEX.
      entry_lag=1: enter T+1 open, exit T+2 open  (standard)
      entry_lag=2: enter T+2 open, exit T+3 open  (T+2 execution)

    Signal date T is the index date. Return is recorded at date T.
    """
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
        e = entry_lag
        for i in range(n):
            vi0 = vni_idx.get(times_arr[i])
            if vi0 is None:
                continue
            if i + e + 1 >= n or vi0 + e + 1 >= len(vni_open):
                continue
            p_in  = open_arr[i + e]
            p_out = open_arr[i + e + 1]
            v_in  = vni_open[vi0 + e]
            v_out = vni_open[vi0 + e + 1]
            if p_in <= 0 or v_in <= 0:
                continue
            ret_arr[i] = (p_out / p_in - 1.0) - (v_out / v_in - 1.0)
        col = f"fwd_e{e}_h1"
        df[col] = ret_arr
        records.append(df[["time", "ticker", col]])

    return pd.concat(records, ignore_index=True) if records else pd.DataFrame()


def run_portfolio(merged: pd.DataFrame, fwd_col: str) -> list:
    """
    Run top-N portfolio with fixed H54 params. Returns list of per-year dicts.
    Each dict: {year, gross_avg, net_avg, n_trades, n_pos_days}.
    """
    results = []
    for year in range(START_YEAR, END_YEAR + 1):
        yr_df = merged[merged["time"].dt.year == year]
        gross_list = []
        for date, day in yr_df.groupby("time"):
            vix_val = day["vix"].iloc[0]
            if not (VIX_MIN <= vix_val <= VIX_MAX):
                continue
            top = day.nlargest(TOP_N, "xs_proba")
            if len(top) < TOP_N or top["xs_proba"].min() < MIN_PROBA:
                continue
            valid = top.dropna(subset=[fwd_col])
            if len(valid) < 2:
                continue
            gross_list.append(valid[fwd_col].mean())
        if not gross_list:
            continue
        gross_avg = np.mean(gross_list)
        net_avg   = gross_avg - COST_RT
        results.append({
            "year": year,
            "gross": gross_avg,
            "net": net_avg,
            "n_trades": len(gross_list),
        })
    return results


def print_year_table(results: list, label: str) -> dict:
    """Print year-by-year table. Returns summary dict."""
    print(f"\n{'='*65}")
    print(f"  {label}")
    print(f"  Fixed params: TOP_N={TOP_N}, MIN_PROBA={MIN_PROBA}, "
          f"VIX[{VIX_MIN:.0f},{VIX_MAX:.0f}], COST_RT={COST_RT*100:.2f}%")
    print(f"  {'year':>5}  {'gross/trade':>12}  {'net/trade':>11}  {'trades':>7}")
    print(f"  {'-'*45}")
    gross_yr = []
    net_yr   = []
    for r in results:
        print(f"  {r['year']:>5}  {r['gross']*100:>+11.3f}%  "
              f"{r['net']*100:>+10.3f}%  {r['n_trades']:>7}")
        gross_yr.append(r["gross"])
        net_yr.append(r["net"])
    if not gross_yr:
        return {}
    n = len(gross_yr)
    sh_gross = np.mean(gross_yr) / (np.std(gross_yr) + 1e-9)
    sh_net   = np.mean(net_yr)   / (np.std(net_yr)   + 1e-9)
    n_pos    = sum(1 for v in net_yr if v > 0)
    avg_trades = np.mean([r["n_trades"] for r in results])
    print(f"\n  Avg gross/trade:  {np.mean(gross_yr)*100:>+.3f}%")
    print(f"  Avg net/trade:    {np.mean(net_yr)*100:>+.3f}%")
    print(f"  Sharpe (gross):   {sh_gross:.2f}")
    print(f"  Sharpe (net):     {sh_net:.2f}")
    print(f"  Positive years:   {n_pos}/{n}")
    print(f"  Avg trades/yr:    {avg_trades:.0f}")
    return {
        "sh_net": sh_net, "sh_gross": sh_gross,
        "avg_gross": np.mean(gross_yr), "avg_net": np.mean(net_yr),
        "n_pos": n_pos, "n_years": n,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--probas", type=str, default=str(DEFAULT_PROBAS))
    args = parser.parse_args()

    print("\nH74: T+2 EXECUTION — ONE-DAY DELAY ROBUSTNESS")
    print(f"E=1 (standard): signal T -> enter T+1 open -> exit T+2 open")
    print(f"E=2 (delayed):  signal T -> enter T+2 open -> exit T+3 open")
    print(f"Fixed H54 params: TOP_N={TOP_N}, MIN_PROBA={MIN_PROBA}, "
          f"VIX[{VIX_MIN:.0f},{VIX_MAX:.0f}], COST_RT={COST_RT*100:.2f}%")

    probas = pd.read_parquet(args.probas)
    probas["time"] = pd.to_datetime(probas["time"])
    tickers = probas["ticker"].unique().tolist()
    print(f"  {len(probas):,} rows | {len(tickers)} tickers")

    vix = pd.read_parquet(VIX_PATH)[["time", "close"]].rename(columns={"close": "vix"})
    vix["time"] = pd.to_datetime(vix["time"])
    probas = probas.merge(vix, on="time", how="left")
    probas["vix"] = probas["vix"].ffill()

    vni = load_vni()

    print(f"Loading E=1 H=1 prices (entry T+1 open)...")
    prices_e1 = load_prices(tickers, vni, entry_lag=1)
    print(f"  {len(prices_e1):,} rows")

    print(f"Loading E=2 H=1 prices (entry T+2 open)...")
    prices_e2 = load_prices(tickers, vni, entry_lag=2)
    print(f"  {len(prices_e2):,} rows")

    # Merge both into probas
    merged = probas.merge(prices_e1, on=["time", "ticker"], how="left")
    merged = merged.merge(prices_e2, on=["time", "ticker"], how="left")
    merged = merged[(merged["time"].dt.year >= START_YEAR) &
                    (merged["time"].dt.year <= END_YEAR)]

    # Run portfolios
    res_e1 = run_portfolio(merged, "fwd_e1_h1")
    res_e2 = run_portfolio(merged, "fwd_e2_h1")

    sum_e1 = print_year_table(res_e1, "E=1 H=1 (standard: enter T+1 open)")
    sum_e2 = print_year_table(res_e2, "E=2 H=1 (delayed: enter T+2 open)")

    # Head-to-head comparison
    print(f"\n{'='*65}")
    print(f"HEAD-TO-HEAD: E=1 vs E=2")
    print(f"{'='*65}")
    print(f"  {'Scheme':<28}  {'gross/trade':>12}  {'net/trade':>10}  "
          f"{'sh_net':>8}  {'pos_yrs'}")
    print(f"  {'-'*70}")
    for lbl, s in [("E=1 H=1 (T+1 entry)", sum_e1), ("E=2 H=1 (T+2 entry)", sum_e2)]:
        if s:
            print(f"  {lbl:<28}  {s['avg_gross']*100:>+11.3f}%  "
                  f"{s['avg_net']*100:>+9.3f}%  {s['sh_net']:>8.2f}  "
                  f"{s['n_pos']}/{s['n_years']}")

    if sum_e1 and sum_e2 and sum_e1["sh_net"] != 0:
        delta_sh  = (sum_e2["sh_net"] / sum_e1["sh_net"] - 1) * 100
        delta_ret = (sum_e2["avg_net"] - sum_e1["avg_net"]) * 100
        print(f"\n  Net Sharpe change (E=2 vs E=1): {delta_sh:+.1f}%")
        print(f"  Net return change (E=2 vs E=1): {delta_ret:+.3f}% per trade")
        if sum_e2["sh_net"] > 0.5 and sum_e2["n_pos"] >= sum_e2["n_years"] * 0.7:
            print(f"  Verdict: PASS -- signal survives T+2 delay. Not microstructure-dependent.")
        elif sum_e2["sh_net"] > 0:
            print(f"  Verdict: MARGINAL -- some alpha at T+2 but meaningfully degraded.")
        else:
            print(f"  Verdict: FAIL -- signal collapses at T+2. Edge is in T+1 gap only.")

    print(f"\n  Context: E=1 Sharpe ~1.30 (H63 fixed params). T+2 tests execution flexibility.")
    print(f"  A positive E=2 Sharpe means the signal persists beyond the open-price reaction.")


if __name__ == "__main__":
    main()
