"""
H68: Short Side — Does the Bottom Quintile Predict Negative Returns?

If the model encodes cross-sectional outperformance, the bottom-ranked stocks
should underperform the market. This test checks:
  1. Does bottom-N produce NEGATIVE excess dollar returns? (short alpha)
  2. Is a long-short portfolio (long top-N, short bottom-N) better than long-only?
  3. Where is the short signal strongest? (full 393-stock universe vs VN30 only)

Execution reality on HOSE:
  - Short selling is legally permitted but practically limited
  - Most brokers only offer margin short on VN30 large caps
  - Borrow cost ~5-15%/yr depending on stock and broker
  - Mid/small caps: essentially no borrow available
  → Short results are informational / theoretical except for VN30

Uses H54 fixed params: VIX[15,30], min_proba=0.55, top/bottom-5.
Actual E=1 H=1 OHLC dollar excess returns.

Usage:
    conda run -n stocks python analysis/h68_short_side.py
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
COST_RT    = 0.003   # per side per round-trip

# VN30 — the only stocks realistically shortable on HOSE
VN30_TICKERS = {
    "ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG",
    "MBB", "MWG", "NVL", "PDR", "PLX", "PNJ", "POW", "SAB", "SHB", "SSI",
    "STB", "TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB",
}


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


def analyze_long_short(merged: pd.DataFrame, universe_label: str, bottom_n: int = TOP_N):
    """
    For each trade day:
      LONG:  top-N stocks (proba >= MIN_PROBA, VIX filter)
      SHORT: bottom-N stocks by proba (same days only)
      L/S:   long - short (market-neutral excess return)

    Cost:
      Long  side: COST_RT per trade day
      Short side: COST_RT + borrowing cost (modeled separately in summary)
    """
    print(f"\n{'='*72}")
    print(f"LONG / SHORT ANALYSIS — {universe_label}")
    print(f"VIX[{VIX_MIN},{VIX_MAX}] | long top-{TOP_N} (proba>={MIN_PROBA}) | short bottom-{bottom_n}")
    print(f"  {'year':>5}  {'long/d':>9}  {'short/d':>10}  {'l/s_gross':>11}  "
          f"{'l/s_net':>9}  {'days':>5}")
    print("  " + "-"*62)

    per_year = {}

    for year, grp in merged.groupby(merged["time"].dt.year):
        if year < START_YEAR or year > END_YEAR:
            continue
        long_rets  = []
        short_rets = []

        for _, day in grp.groupby("time"):
            if not (VIX_MIN <= day["vix"].iloc[0] <= VIX_MAX):
                continue

            # Long side: top-N with min_proba filter
            top = day.nlargest(TOP_N, "xs_proba")
            if top["xs_proba"].min() < MIN_PROBA:
                continue
            long_day = top["fwd_e1_h1"].dropna().values
            if len(long_day) < 2:
                continue

            # Short side: bottom-N by proba (unconditional on their proba)
            bottom = day.nsmallest(bottom_n, "xs_proba")
            short_day = bottom["fwd_e1_h1"].dropna().values
            if len(short_day) < 2:
                continue

            long_rets.append(long_day.mean())
            short_rets.append(short_day.mean())

        if len(long_rets) < 5:
            continue

        avg_long  = np.mean(long_rets)
        avg_short = np.mean(short_rets)
        avg_ls    = avg_long - avg_short    # gross long-short (short return subtracted)
        # Net L/S: long costs COST_RT, short costs 2x COST_RT (borrow + RT)
        ls_net = avg_ls - COST_RT - 2 * COST_RT

        per_year[year] = {
            "long": avg_long, "short": avg_short,
            "ls": avg_ls, "ls_net": ls_net,
            "n_days": len(long_rets),
        }
        print(f"  {year:>5}  {avg_long*100:>+8.3f}%  {avg_short*100:>+9.3f}%  "
              f"{avg_ls*100:>+10.3f}%  {ls_net*100:>+8.3f}%  {len(long_rets):>5}")

    if not per_year:
        print("  (no data)")
        return

    long_yrs   = [r["long"]   for r in per_year.values()]
    short_yrs  = [r["short"]  for r in per_year.values()]
    ls_yrs     = [r["ls"]     for r in per_year.values()]
    ls_net_yrs = [r["ls_net"] for r in per_year.values()]

    sh_long  = np.mean(long_yrs)  / (np.std(long_yrs)  + 1e-9)
    sh_ls    = np.mean(ls_yrs)    / (np.std(ls_yrs)    + 1e-9)
    sh_ls_n  = np.mean(ls_net_yrs)/ (np.std(ls_net_yrs)+ 1e-9)
    n_short_neg = sum(1 for s in short_yrs if s < 0)   # short alpha: negative = good

    print(f"\n  SUMMARY ({universe_label})")
    print(f"  Long  avg/day:  {np.mean(long_yrs)*100:>+.3f}%  Sharpe: {sh_long:.2f}")
    print(f"  Short avg/day:  {np.mean(short_yrs)*100:>+.3f}%  "
          f"({'NEGATIVE=short alpha OK' if np.mean(short_yrs) < 0 else 'POSITIVE=no short alpha'})")
    print(f"  L/S gross/day:  {np.mean(ls_yrs)*100:>+.3f}%  Sharpe: {sh_ls:.2f}")
    print(f"  L/S net/day:    {np.mean(ls_net_yrs)*100:>+.3f}%  "
          f"(after long COST_RT + 2x short COST_RT)  Sharpe: {sh_ls_n:.2f}")
    print(f"  Short neg years (short pays): {n_short_neg}/{len(short_yrs)}")
    print(f"  L/S pos years: {sum(1 for x in ls_net_yrs if x > 0)}/{len(ls_net_yrs)}")


def quintile_short_signal(merged: pd.DataFrame, label: str):
    """Show return by decile of proba — does the bottom decile predict negative returns?"""
    print(f"\n{'='*72}")
    print(f"PROBA DECILE vs DOLLAR RETURN — {label}")
    print(f"(pooled 2015-{END_YEAR}, VIX filter applied)")
    print(f"  {'decile':>8}  {'proba_range':>14}  {'avg_proba':>10}  {'avg_ret':>10}  {'n':>8}")
    print("  " + "-"*58)

    rows = []
    for _, day in merged.groupby("time"):
        if not (VIX_MIN <= day["vix"].iloc[0] <= VIX_MAX):
            continue
        day2 = day.dropna(subset=["fwd_e1_h1"])
        if len(day2) < 10:
            continue
        day2 = day2.copy()
        day2["decile"] = pd.qcut(day2["xs_proba"], 10, labels=False, duplicates="drop")
        rows.append(day2[["decile", "xs_proba", "fwd_e1_h1"]])

    if not rows:
        print("  (no data)")
        return

    all_data = pd.concat(rows, ignore_index=True)
    for d in sorted(all_data["decile"].dropna().unique()):
        sub = all_data[all_data["decile"] == d]
        avg_p = sub["xs_proba"].mean()
        avg_r = sub["fwd_e1_h1"].mean()
        lo    = sub["xs_proba"].min()
        hi    = sub["xs_proba"].max()
        marker = "<- short target" if d <= 1 else ("<- long target" if d >= 8 else "")
        print(f"  {int(d)+1:>8}  [{lo:.3f},{hi:.3f}]  {avg_p:>9.3f}  {avg_r*100:>+9.3f}%  "
              f"{len(sub):>8,}  {marker}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--probas", type=str, default=str(DEFAULT_PROBAS))
    args = parser.parse_args()

    print(f"\nH68: SHORT SIDE — BOTTOM-N RETURN ANALYSIS")
    print(f"Testing whether low-proba stocks underperform -> short alpha")

    probas = pd.read_parquet(args.probas)
    probas["time"] = pd.to_datetime(probas["time"])
    tickers = probas["ticker"].unique().tolist()
    print(f"  {len(probas):,} rows | {len(tickers)} tickers")

    vix = pd.read_parquet(VIX_PATH)[["time", "close"]].rename(columns={"close": "vix"})
    vix["time"] = pd.to_datetime(vix["time"])
    probas = probas.merge(vix, on="time", how="left")
    probas["vix"] = probas["vix"].ffill()

    print(f"Loading E=1 H=1 OHLC prices...")
    vni = load_vni()
    prices = load_prices_e1_h1(tickers, vni)
    print(f"  {len(prices):,} rows")

    merged_full = probas.merge(prices, on=["time", "ticker"], how="left")
    merged_full = merged_full[(merged_full["time"].dt.year >= START_YEAR) &
                              (merged_full["time"].dt.year <= END_YEAR)]

    # Test 1: Full universe long/short
    analyze_long_short(merged_full, f"Full universe ({len(tickers)} stocks)")

    # Test 2: VN30 only (the only stocks realistically shortable)
    available_vn30 = VN30_TICKERS & set(tickers)
    missing = VN30_TICKERS - available_vn30
    print(f"\n  VN30 in data: {len(available_vn30)}/30"
          + (f" (missing: {sorted(missing)})" if missing else ""))
    merged_vn30 = merged_full[merged_full["ticker"].isin(available_vn30)]
    analyze_long_short(merged_vn30, f"VN30 ({len(available_vn30)} stocks — executable shorts)")

    # Test 3: Proba decile breakdown (full universe)
    quintile_short_signal(merged_full, f"Full universe ({len(tickers)} stocks)")

    # Execution reality note
    print(f"\n{'='*72}")
    print(f"EXECUTION NOTES")
    print(f"{'='*72}")
    print(f"  Short selling on HOSE:")
    print(f"    Legal:          Yes, permitted since 2012")
    print(f"    Practically:    VN30 only at most brokers (margin lending required)")
    print(f"    Borrow cost:    ~0.5-1.5%/yr for VN30, higher for others")
    print(f"    Settlement:     T+2 like longs — no intraday short")
    print(f"  ")
    print(f"  L/S net in this test uses 3x COST_RT (long RT + 2x short RT).")
    print(f"  Add ~0.1%/yr borrow cost for VN30 shorts at current rates.")
    print(f"  If short alpha > borrow cost -> L/S is viable on VN30.")
    print(f"  If short alpha ~= 0 -> stay long-only, signal is asymmetric.")


if __name__ == "__main__":
    main()
