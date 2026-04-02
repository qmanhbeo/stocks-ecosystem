"""
H69: Square-Weighted Position Sizing — Honest Nested Walk-Forward.

H65 validated that square weighting (proba-0.5)² improves Sharpe vs equal-weight
on dollar returns using fixed H54 params. H69 runs the same nested WF as H56/H63
but with square weighting to get the zero-contamination honest Sharpe.

Baseline (H63, EW, fixed params): gross/trade ~+0.629%, net Sharpe ~1.30
H65 (EW vs SQUARE, fixed params): EW dollar-Sharpe 7.61, SQUARE 9.07 (+19%)
H69: does the SQUARE improvement hold in nested WF (zero contamination)?

Both EW and SQUARE run in the same nested WF, so the comparison is apples-to-apples.

Usage:
    conda run -n stocks python analysis/h69_square_wf.py
"""
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from path_utils import data_path
from itertools import product

warnings.filterwarnings("ignore", category=RuntimeWarning)

DEFAULT_PROBAS = data_path("features/xs_barrier_all_probas_hose_full.parquet")
VIX_PATH  = data_path("fx-commodities/fx_commodities_vix_1D.parquet")
STOCK_DIR = data_path("stock")
VNI_FILE  = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"

START_YEAR  = 2015
END_YEAR    = 2025
META_WINDOW = 3
VIX_MIN     = 15.0
COST_RT     = 0.003

# Same grid as H56
VIX_MAX_GRID   = [25.0, 28.0, 30.0, 32.0, 35.0]
MIN_PROBA_GRID = [0.50, 0.52, 0.55, 0.58]
TOP_N_GRID     = [1, 2, 3, 5, 7]


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


def square_weights(probas: np.ndarray) -> np.ndarray:
    w = np.maximum(probas - 0.5, 1e-6) ** 2
    return w / w.sum()


def run_strategy(df: pd.DataFrame, top_n: int, min_proba: float,
                 vix_max: float, use_square: bool) -> dict:
    """
    Run daily portfolio for given params. Returns {year: [trade_gross_rets]}.
    """
    per_year = {}
    for date, day in df.groupby("time"):
        year = date.year
        if not (VIX_MIN <= day["vix"].iloc[0] <= vix_max):
            continue
        top = day.nlargest(top_n, "xs_proba")
        if len(top) < top_n or top["xs_proba"].min() < min_proba:
            continue
        valid = top.dropna(subset=["fwd_e1_h1"])
        if len(valid) < 2:
            continue
        rets   = valid["fwd_e1_h1"].values
        probas = valid["xs_proba"].values
        if use_square:
            w = square_weights(probas)
            trade_ret = (w * rets).sum()
        else:
            trade_ret = rets.mean()
        per_year.setdefault(year, []).append(trade_ret)
    return per_year


def sharpe_from_per_year(per_year: dict) -> float:
    yr_avgs = [np.mean(ts) for ts in per_year.values()]
    if len(yr_avgs) < 2:
        return float("nan")
    return np.mean(yr_avgs) / (np.std(yr_avgs) + 1e-9)


def nested_wf(merged: pd.DataFrame, use_square: bool, label: str) -> dict:
    print(f"\n{'='*72}")
    print(f"NESTED WF — {label}")
    print(f"  Meta-window: {META_WINDOW} yrs | Grid: VIX_MAX x MIN_PROBA x TOP_N")
    print(f"  {'year':>5}  {'best_params':>22}  {'meta_sh':>8}  {'gross/d':>9}  {'net/d':>9}  {'trades':>7}")
    print("  " + "-"*68)

    all_years  = sorted(merged["time"].dt.year.unique())
    test_years = [y for y in all_years if START_YEAR <= y <= END_YEAR]
    results    = []

    for test_year in test_years:
        meta_years = [y for y in all_years if test_year - META_WINDOW <= y < test_year]
        if len(meta_years) < 2:
            print(f"  {test_year:>5}  insufficient meta data")
            continue
        df_meta = merged[merged["time"].dt.year.isin(meta_years)]
        df_test = merged[merged["time"].dt.year == test_year]

        best_sh, best_params = -999.0, None
        for top_n, min_proba, vix_max in product(TOP_N_GRID, MIN_PROBA_GRID, VIX_MAX_GRID):
            py = run_strategy(df_meta, top_n, min_proba, vix_max, use_square)
            if len(py) >= 2:
                sh = sharpe_from_per_year(py)
                if sh > best_sh:
                    best_sh, best_params = sh, (top_n, min_proba, vix_max)

        if best_params is None:
            print(f"  {test_year:>5}  no valid param combo")
            continue

        top_n, min_proba, vix_max = best_params
        py_test = run_strategy(df_test, top_n, min_proba, vix_max, use_square)
        if not py_test:
            continue

        all_rets  = [r for ts in py_test.values() for r in ts]
        gross     = np.mean(all_rets)
        net       = gross - COST_RT
        n_trades  = len(all_rets)

        params_str = f"N={top_n},p={min_proba:.2f},V={vix_max:.0f}"
        print(f"  {test_year:>5}  {params_str:>22}  {best_sh:>8.2f}  "
              f"{gross*100:>+8.3f}%  {net*100:>+8.3f}%  {n_trades:>6}")
        results.append({"year": test_year, "gross": gross, "net": net, "n_trades": n_trades})

    summary = {}
    if results:
        gross_yrs = [r["gross"] for r in results]
        net_yrs   = [r["net"]   for r in results]
        sh_gross  = np.mean(gross_yrs) / (np.std(gross_yrs) + 1e-9)
        sh_net    = np.mean(net_yrs)   / (np.std(net_yrs)   + 1e-9)
        n_pos_g   = sum(1 for g in gross_yrs if g > 0)
        n_pos_n   = sum(1 for n in net_yrs   if n > 0)
        avg_trades = np.mean([r["n_trades"] for r in results])
        print(f"\n  {label} — RESULT")
        print(f"  Avg gross/trade: {np.mean(gross_yrs)*100:+.3f}%")
        print(f"  Avg net/trade:   {np.mean(net_yrs)*100:+.3f}%")
        print(f"  Sharpe (gross):  {sh_gross:.2f}")
        print(f"  Sharpe (net):    {sh_net:.2f}")
        print(f"  Positive years:  gross {n_pos_g}/{len(results)}, net {n_pos_n}/{len(results)}")
        print(f"  Avg trades/yr:   {avg_trades:.0f}")
        summary = {"sh_gross": sh_gross, "sh_net": sh_net,
                   "avg_gross": np.mean(gross_yrs), "avg_net": np.mean(net_yrs),
                   "n_years": len(results), "n_pos_net": n_pos_n}
    return summary


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--probas", type=str, default=str(DEFAULT_PROBAS))
    args = parser.parse_args()

    print(f"\nH69: SQUARE-WEIGHTED POSITION SIZING — HONEST NESTED WF")
    print(f"COST_RT={COST_RT*100:.2f}% | META_WINDOW={META_WINDOW} | 2015-2025")

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
    merged = merged[(merged["time"].dt.year >= START_YEAR - META_WINDOW) &
                    (merged["time"].dt.year <= END_YEAR)]

    ew     = nested_wf(merged, use_square=False, label="Equal Weight (EW) -- baseline")
    square = nested_wf(merged, use_square=True,  label="Square Weight: (proba-0.5)^2")

    print(f"\n{'='*72}")
    print(f"HEAD-TO-HEAD COMPARISON")
    print(f"{'='*72}")
    print(f"  {'Scheme':<28}  {'gross/trade':>12}  {'net/trade':>10}  {'sh_net':>8}  {'pos_yrs'}")
    print("  " + "-"*70)
    for label, r in [("Equal Weight (EW)", ew), ("Square Weight", square)]:
        if r:
            print(f"  {label:<28}  {r['avg_gross']*100:>+11.3f}%  {r['avg_net']*100:>+9.3f}%  "
                  f"{r['sh_net']:>8.2f}  {r['n_pos_net']}/{r['n_years']}")

    if ew and square and ew["sh_net"] > 0:
        delta = (square["sh_net"] / ew["sh_net"] - 1) * 100
        print(f"\n  Square vs EW Sharpe improvement: {delta:+.1f}%")
        print(f"  H65 (fixed params) showed: EW 7.61 -> SQUARE 9.07 (+19%)")
        print(f"  H69 (nested WF)  shows: EW {ew['sh_net']:.2f} -> SQUARE {square['sh_net']:.2f} ({delta:+.1f}%)")

    print(f"\n  Note: Sharpe here is annual net dollar Sharpe (11 years).")
    print(f"  Compare to H63 fixed-param net Sharpe ~1.30 and H65 daily Sharpe 2.57.")


if __name__ == "__main__":
    main()
