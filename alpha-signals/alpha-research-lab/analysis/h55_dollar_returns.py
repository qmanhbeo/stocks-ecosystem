"""
H55: Dollar Return Validation with Correct Execution Timing.

Three entry scenarios, each with multiple hold periods:
  E=0  (WRONG baseline): enter at signal-day close — not executable
  E=1  (realistic):      enter at T+1 open — "execute first thing next morning"
  E=3  (delayed):        enter at T+3 open — "3 days after signal"

For E>0, both entry and exit use OPEN prices, and VNINDEX is aligned to the same
calendar period. "Correct" is defined as fwd_rel > 0 from actual entry, not the
T→T+5 barrier label in the probas file.

Optional --min-volume filter restricts the eligible pool to liquid stocks only.

Usage:
    # All 393 stocks, all entry timings
    conda run -n stocks python analysis/h55_dollar_returns.py

    # Liquid stocks only (vol > 100k shares avg daily)
    conda run -n stocks python analysis/h55_dollar_returns.py --min-volume 100000
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

TOP_N      = 5
MIN_PROBA  = 0.55
START_YEAR = 2015
END_YEAR   = 2025

# Entry delays and hold periods to compute
ENTRY_DELAYS = [0, 1, 3]   # days after signal to enter
HOLD_DAYS    = [1, 2, 3, 5]

TURNOVER  = 0.69
COST_RT   = 0.003
VOLUME_WINDOW = 20


def load_vni():
    df = pd.read_parquet(VNI_FILE, columns=["time", "open", "close"])
    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values("time").reset_index(drop=True)
    return df


def compute_avg_volumes(tickers: list) -> dict:
    vols = {}
    for t in tickers:
        fp = STOCK_DIR / f"gia_lich_su_{t}_1D.parquet"
        if not fp.exists():
            continue
        try:
            df = pd.read_parquet(fp, columns=["volume"])
            if len(df) >= 5:
                vols[t] = df["volume"].tail(VOLUME_WINDOW).mean()
        except Exception:
            pass
    return vols


def load_prices(tickers: list, vni: pd.DataFrame) -> pd.DataFrame:
    """
    For each ticker, compute forward relative returns for all (entry_delay, hold) combos.

    Column naming: fwd_e{E}_h{H}
      E=0, H=1 → fwd_e0_h1: close[i+1]/close[i] - 1 vs VNI close (original, not executable)
      E=1, H=1 → fwd_e1_h1: open[i+1] entry, open[i+2] exit vs VNI open (correct T+1 entry)
      E=3, H=2 → fwd_e3_h2: open[i+3] entry, open[i+5] exit vs VNI open
    """
    vni_open  = vni["open"].values
    vni_close = vni["close"].values
    vni_times = vni["time"].values
    vni_idx   = {t: i for i, t in enumerate(vni_times)}

    ticker_set = set(tickers)
    combos = [(e, h) for e in ENTRY_DELAYS for h in HOLD_DAYS]
    col_names = [f"fwd_e{e}_h{h}" for e, h in combos]

    records = []
    for sf in sorted(STOCK_DIR.glob("gia_lich_su_*_1D.parquet")):
        ticker = sf.name.replace("gia_lich_su_", "").replace("_1D.parquet", "")
        if ticker not in ticker_set or ticker == "VNINDEX":
            continue
        try:
            df = pd.read_parquet(sf, columns=["time", "open", "close"])
        except Exception:
            continue
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time").reset_index(drop=True)
        df["ticker"] = ticker

        close_arr = df["close"].values.astype(float)
        open_arr  = df["open"].values.astype(float)
        times_arr = df["time"].values
        n = len(df)

        # Pre-build per-combo result arrays
        result_arrays = {(e, h): np.full(n, np.nan) for e, h in combos}

        for i in range(n):
            vi0 = vni_idx.get(times_arr[i])
            if vi0 is None:
                continue

            for e, h in combos:
                exit_stock_pos = i + e + h
                vi_entry = vi0 + e
                vi_exit  = vi0 + e + h

                if exit_stock_pos >= n or vi_exit >= len(vni_close):
                    continue

                if e == 0:
                    # Original (wrong): enter at T close, exit at T+H close
                    p_in  = close_arr[i]
                    p_out = close_arr[i + h]
                    v_in  = vni_close[vi0]
                    v_out = vni_close[vi0 + h]
                else:
                    # Correct: enter at T+E open, exit at T+E+H open
                    p_in  = open_arr[i + e]
                    p_out = open_arr[i + e + h]
                    v_in  = vni_open[vi_entry]
                    v_out = vni_open[vi_exit]

                if p_in <= 0 or v_in <= 0:
                    continue

                rel = (p_out / p_in - 1.0) - (v_out / v_in - 1.0)
                result_arrays[(e, h)][i] = rel

        for (e, h), arr in result_arrays.items():
            df[f"fwd_e{e}_h{h}"] = arr

        records.append(df[["time", "ticker"] + col_names])

    return pd.concat(records, ignore_index=True) if records else pd.DataFrame()


def analyze(probas: pd.DataFrame, prices: pd.DataFrame, label: str):
    combos = [(e, h) for e in ENTRY_DELAYS for h in HOLD_DAYS]

    # Merge probas with prices
    merge_cols = ["time", "ticker"] + [f"fwd_e{e}_h{h}" for e, h in combos]
    merged = probas.merge(prices[merge_cols], on=["time", "ticker"], how="left")
    merged = merged[(merged["year"] >= START_YEAR) & (merged["year"] <= END_YEAR)]

    # Select top-N by proba each day
    top_rows = []
    for _, day in merged.groupby("time"):
        top = day.nlargest(TOP_N, "xs_proba")
        if top["xs_proba"].min() >= MIN_PROBA:
            top_rows.append(top)

    if not top_rows:
        print(f"  [{label}] No valid trading days.")
        return

    top_df = pd.concat(top_rows, ignore_index=True)
    n_days    = top_df["time"].nunique()
    n_tickers = top_df["ticker"].nunique()

    print(f"\n{'='*78}")
    print(f"H55: DOLLAR RETURNS — {label}")
    print(f"  min_proba={MIN_PROBA} | top-{TOP_N} | {START_YEAR}-{END_YEAR}")
    print(f"  Trading days: {n_days} | Unique tickers: {n_tickers}")
    print(f"{'='*78}")

    # Header
    print(f"\n  {'Entry':>8}  {'Hold':>5}  {'P(win)':>7}  {'avg_win':>9}  {'avg_loss':>10}  "
          f"{'gross':>8}  {'net@0.3%':>9}  {'note':>20}")
    print("  " + "-"*85)

    prev_e = None
    for e, h in combos:
        col = f"fwd_e{e}_h{h}"
        sub = top_df[top_df[col].notna()].copy()
        if len(sub) < 50:
            continue

        # "Correct" = stock outperformed VNINDEX from actual entry date
        wins = sub[sub[col] > 0][col]
        loss = sub[sub[col] <= 0][col]
        p_win    = len(wins) / len(sub)
        avg_win  = wins.mean() if len(wins) > 0 else 0.0
        avg_loss = loss.mean() if len(loss) > 0 else 0.0
        gross    = sub[col].mean()

        if e == 0:
            note = "(not executable)"
        elif e == 1:
            note = "(T+1 open, correct)"
        else:
            note = f"(T+{e} open, delayed)"

        # Separator between entry delays
        if prev_e is not None and e != prev_e:
            print()
        prev_e = e

        net = gross - COST_RT
        print(f"  E={e} open  {h:>4}d  {p_win:>7.3f}  {avg_win*100:>+8.3f}%  "
              f"{avg_loss*100:>+9.3f}%  {gross*100:>+7.3f}%  {net*100:>+8.3f}%  {note:>20}")

    # Per-year breakdown for key combos: E=0 H=1, E=1 H=1, E=1 H=5, E=3 H=1
    key_combos = [(0, 1), (1, 1), (1, 5), (3, 1)]
    for e, h in key_combos:
        col = f"fwd_e{e}_h{h}"
        if col not in top_df.columns:
            continue
        sub = top_df[top_df[col].notna()]
        if len(sub) < 5:
            continue
        if e == 0:
            label_str = f"E=0 H={h}d (close, NOT executable)"
        else:
            label_str = f"E={e} open H={h}d"
        print(f"\n  PER-YEAR — {label_str}")
        print(f"  {'year':>6}  {'n_days':>7}  {'P(win)':>7}  {'avg_win':>9}  "
              f"{'avg_loss':>10}  {'gross':>8}")
        print("  " + "-"*60)
        for year in range(START_YEAR, END_YEAR + 1):
            ys = sub[sub["time"].dt.year == year]
            if len(ys) < 5:
                continue
            pw = (ys[col] > 0).mean()
            aw = ys[ys[col] > 0][col].mean() if pw > 0 else 0.0
            al = ys[ys[col] <= 0][col].mean() if pw < 1 else 0.0
            g  = ys[col].mean()
            print(f"  {year:>6}  {ys['time'].nunique():>7}  {pw:>7.3f}  "
                  f"{aw*100:>+8.3f}%  {al*100:>+9.3f}%  {g*100:>+7.3f}%")

    # Annualised estimate for E=1 H=1 (most realistic)
    col = "fwd_e1_h1"
    sub = top_df[top_df[col].notna()]
    if len(sub) >= 50:
        gross = sub[col].mean()
        tpy = (250 / 1) * TURNOVER
        print(f"\n  ANNUALISED ESTIMATE (E=1 H=1, linear, {tpy:.0f} effective trades/yr):")
        print(f"    Gross/trade: {gross*100:+.3f}%  |  "
              f"Gross/yr: {gross*tpy*100:+.2f}%  |  "
              f"Net/yr @0.3%RT: {(gross-COST_RT)*tpy*100:+.2f}%")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probas", type=str, default=str(DEFAULT_PROBAS))
    parser.add_argument("--min-volume", type=float, default=0.0,
                        help="Min avg daily share volume (default: 0 = no filter)")
    args = parser.parse_args()

    print(f"Loading probas: {args.probas}")
    probas = pd.read_parquet(args.probas)
    probas["time"] = pd.to_datetime(probas["time"])
    all_tickers = probas["ticker"].unique().tolist()
    print(f"  {len(probas):,} rows | {len(all_tickers)} tickers | "
          f"years {probas['year'].min()}-{probas['year'].max()}")

    # Apply liquidity filter
    if args.min_volume > 0:
        print(f"Computing avg volumes (last {VOLUME_WINDOW} days)...")
        vols = compute_avg_volumes(all_tickers)
        tickers = [t for t in all_tickers if vols.get(t, 0) >= args.min_volume]
        print(f"  Tickers above {args.min_volume:,.0f} vol: {len(tickers)}/{len(all_tickers)}")
        probas = probas[probas["ticker"].isin(tickers)]
    else:
        tickers = all_tickers

    print(f"\nLoading prices for {len(tickers)} tickers...")
    vni = load_vni()
    prices = load_prices(tickers, vni)
    print(f"  Price data: {len(prices):,} rows")

    vol_label = f" (vol>{args.min_volume/1e3:.0f}k)" if args.min_volume > 0 else ""
    analyze(probas, prices, f"{len(tickers)} tickers{vol_label}")


if __name__ == "__main__":
    main()
