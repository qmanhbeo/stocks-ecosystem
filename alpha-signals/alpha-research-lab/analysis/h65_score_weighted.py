"""
H65: Score-Weighted Position Sizing.

Current strategy: equal-weight top-N stocks (each gets 1/N of capital).
Alternative: weight by model score — higher proba = larger position.

Hypothesis: model confidence encodes useful information beyond just rank.
A stock at proba=0.75 should get more capital than one at proba=0.56.

Weighting schemes tested (all applied to top-N selected stocks only):
  EW:       equal weight (baseline, 1/N)
  LINEAR:   weight ∝ (proba - 0.5),       normalized to sum to 1
  SQUARE:   weight ∝ (proba - 0.5)²,      stronger concentration
  SOFTMAX:  weight ∝ exp(proba / temp),   temperature sweep

Uses actual E=1 H=1 OHLC returns for dollar-denominated comparison.
Binary accuracy edge is also shown for cross-validation with h40 baseline.

Usage:
    conda run -n stocks python analysis/h65_score_weighted.py
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
COST_RT    = 0.003

SOFTMAX_TEMPS = [0.1, 0.3, 0.5, 1.0, 2.0]


def load_vni() -> pd.DataFrame:
    df = pd.read_parquet(VNI_FILE, columns=["time", "open"])
    df["time"] = pd.to_datetime(df["time"])
    return df.sort_values("time").reset_index(drop=True)


def load_prices_e1_h1(tickers: list, vni: pd.DataFrame) -> pd.DataFrame:
    """E=1 entry (T+1 open), H=1 exit (T+2 open). Actual excess return."""
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


def compute_weights(probas: np.ndarray, scheme: str, temp: float = 1.0) -> np.ndarray:
    """Return normalized weights for the top-N stocks."""
    if scheme == "EW":
        return np.ones(len(probas)) / len(probas)
    elif scheme == "LINEAR":
        w = np.maximum(probas - 0.5, 1e-6)
    elif scheme == "SQUARE":
        w = np.maximum(probas - 0.5, 1e-6) ** 2
    elif scheme == "SOFTMAX":
        w = np.exp(probas / temp)
    else:
        raise ValueError(f"Unknown scheme: {scheme}")
    w = w / w.sum()
    return w


def run_scheme(merged: pd.DataFrame, scheme: str, temp: float = 1.0, label: str = None) -> dict:
    """
    Run one weighting scheme, return per-year metrics.
    Returns dict with gross returns, weighted accuracy, etc.
    """
    lbl = label or (f"{scheme}(t={temp})" if scheme == "SOFTMAX" else scheme)
    per_year = []

    for year, grp in merged.groupby(merged["time"].dt.year):
        if year < START_YEAR or year > END_YEAR:
            continue
        naive = grp["actual"].mean()
        day_wtd_acc  = []
        day_wtd_ret  = []

        for _, day in grp.groupby("time"):
            vix_val = day["vix"].iloc[0]
            if not (VIX_MIN <= vix_val <= VIX_MAX):
                continue
            top = day.nlargest(TOP_N, "xs_proba")
            if top["xs_proba"].min() < MIN_PROBA:
                continue

            probas_arr = top["xs_proba"].values
            actuals    = top["actual"].values
            rets       = top["fwd_e1_h1"].values

            w = compute_weights(probas_arr, scheme, temp)

            # Weighted accuracy (binary direction)
            wtd_acc = (w * actuals).sum()
            day_wtd_acc.append(wtd_acc - naive)

            # Weighted dollar return
            valid = ~np.isnan(rets)
            if valid.sum() >= 2:
                w_valid = w[valid]
                w_valid /= w_valid.sum()
                day_wtd_ret.append((w_valid * rets[valid]).sum())

        if len(day_wtd_acc) >= 5:
            per_year.append({
                "year": year,
                "acc_edge": np.mean(day_wtd_acc),
                "gross_ret": np.mean(day_wtd_ret) if day_wtd_ret else float("nan"),
                "n_days": len(day_wtd_acc),
            })

    if not per_year:
        return {}

    acc_edges  = [r["acc_edge"]  for r in per_year]
    gross_rets = [r["gross_ret"] for r in per_year if not np.isnan(r["gross_ret"])]
    n_trades   = np.mean([r["n_days"] for r in per_year])

    return {
        "label": lbl,
        "avg_acc_edge": np.mean(acc_edges),
        "sharpe_acc":   np.mean(acc_edges) / (np.std(acc_edges) + 1e-9),
        "avg_gross_ret": np.mean(gross_rets) if gross_rets else float("nan"),
        "net_ret":  np.mean(gross_rets) - COST_RT if gross_rets else float("nan"),
        "sharpe_ret": np.mean(gross_rets) / (np.std(gross_rets) + 1e-9) if len(gross_rets) >= 2 else float("nan"),
        "n_pos": sum(1 for e in acc_edges if e > 0),
        "n_years": len(per_year),
        "n_trades_yr": n_trades,
        "per_year": per_year,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probas", type=str, default=str(DEFAULT_PROBAS))
    args = parser.parse_args()

    print(f"\nH65: SCORE-WEIGHTED POSITION SIZING")
    print(f"Loading probas: {args.probas}")
    probas = pd.read_parquet(args.probas)
    probas["time"] = pd.to_datetime(probas["time"])
    tickers = probas["ticker"].unique().tolist()
    print(f"  {len(probas):,} rows | {len(tickers)} tickers")

    print(f"Loading VIX...")
    vix = pd.read_parquet(VIX_PATH)[["time", "close"]].rename(columns={"close": "vix"})
    vix["time"] = pd.to_datetime(vix["time"])
    probas = probas.merge(vix, on="time", how="left")
    probas["vix"] = probas["vix"].ffill()

    print(f"Loading E=1 H=1 OHLC prices for {len(tickers)} tickers...")
    vni = load_vni()
    prices = load_prices_e1_h1(tickers, vni)
    print(f"  {len(prices):,} rows")

    merged = probas.merge(prices, on=["time", "ticker"], how="left")
    merged = merged[(merged["time"].dt.year >= START_YEAR) & (merged["time"].dt.year <= END_YEAR)]

    # Run all schemes
    schemes_to_test = [
        ("EW",     1.0, "Equal Weight (baseline)"),
        ("LINEAR", 1.0, "Linear (proba-0.5)"),
        ("SQUARE", 1.0, "Square (proba-0.5)²"),
    ] + [("SOFTMAX", t, f"Softmax(temp={t})") for t in SOFTMAX_TEMPS]

    results = []
    for scheme, temp, label in schemes_to_test:
        r = run_scheme(merged, scheme, temp, label)
        if r:
            results.append(r)

    # Summary table
    print(f"\n{'='*90}")
    print(f"WEIGHTING SCHEME COMPARISON (top-{TOP_N}, min_proba={MIN_PROBA}, VIX[{VIX_MIN},{VIX_MAX}])")
    print(f"{'='*90}")
    print(f"\n  {'Scheme':<28}  {'acc_edge':>9}  {'sh_acc':>8}  "
          f"{'gross_ret':>10}  {'net_ret':>9}  {'sh_ret':>8}  {'pos':>6}")
    print("  " + "-"*85)

    for r in results:
        net = r['net_ret']
        net_str = f"{net*100:>+8.3f}%" if not np.isnan(net) else "    N/A"
        gr_str  = f"{r['avg_gross_ret']*100:>+9.3f}%" if not np.isnan(r['avg_gross_ret']) else "      N/A"
        sh_str  = f"{r['sharpe_ret']:>8.2f}"          if not np.isnan(r['sharpe_ret'])   else "     N/A"
        print(f"  {r['label']:<28}  {r['avg_acc_edge']*100:>+8.2f}%  "
              f"{r['sharpe_acc']:>8.2f}  {gr_str}  {net_str}  {sh_str}  "
              f"{r['n_pos']}/{r['n_years']}")

    # Per-year breakdown for top schemes: EW vs best non-EW
    best_non_ew = max(
        [r for r in results if r["label"] != "Equal Weight (baseline)" and not np.isnan(r["avg_gross_ret"])],
        key=lambda r: r["avg_gross_ret"],
        default=None,
    )
    for r in [results[0], best_non_ew]:
        if r is None:
            continue
        print(f"\n  PER-YEAR — {r['label']}")
        print(f"  {'year':>6}  {'days':>6}  {'acc_edge':>10}  {'gross_ret':>11}  {'net_ret':>10}")
        print("  " + "-"*50)
        for yr in r["per_year"]:
            net = yr["gross_ret"] - COST_RT if not np.isnan(yr["gross_ret"]) else float("nan")
            net_str = f"{net*100:>+9.3f}%" if not np.isnan(net) else "    N/A"
            print(f"  {yr['year']:>6}  {yr['n_days']:>6}  {yr['acc_edge']*100:>+9.2f}%  "
                  f"{yr['gross_ret']*100:>+10.3f}%  {net_str}")

    # Concentration analysis: how concentrated are the weights?
    print(f"\n{'='*90}")
    print(f"WEIGHT CONCENTRATION ANALYSIS (top-{TOP_N}, avg probas for illustration)")
    print(f"  Simulated with typical top-5 probas: [0.60, 0.58, 0.57, 0.56, 0.555]")
    example_probas = np.array([0.60, 0.58, 0.57, 0.56, 0.555])
    print(f"\n  {'Scheme':<28}  {'weights (stock 1..5)':>40}  {'HHI':>6}")
    print("  " + "-"*80)
    for scheme, temp, label in schemes_to_test:
        w = compute_weights(example_probas, scheme, temp)
        hhi = (w**2).sum()  # Herfindahl index: 0.2=equal, 1.0=full concentration
        w_str = "  ".join([f"{wi:.3f}" for wi in w])
        print(f"  {label:<28}  {w_str:>40}  {hhi:.3f}")

    print(f"\n  HHI interpretation: 0.200=equal-weight, 1.000=100% in 1 stock")
    print(f"  Higher HHI = more concentrated = higher variance but potentially higher return")


if __name__ == "__main__":
    main()
