"""
H47: Proba Smoothing — rank by N-day rolling average of xs_proba.

Instead of ranking by today's xs_proba, rank by the rolling N-day mean.
A stock that has been consistently top-ranked (not just today) is a stronger signal.

Sweep: rolling window N=1 (baseline), 3, 5, 7 days.

Usage:
    conda run -n stocks python analysis/h47_proba_smoothing.py
"""
import numpy as np
import pandas as pd
from pathlib import Path

ALL_PROBAS  = Path("data/features/xs_barrier_all_probas.parquet")
VIX_PATH    = Path("data/fx-commodities/fx_commodities_vix_1D.parquet")

TOP_N       = 5
MIN_PROBA   = 0.55
VIX_MAX     = 30.0
START_YEAR  = 2015
COST_RT     = 0.003   # 0.30% round-trip


def load_data():
    df = pd.read_parquet(ALL_PROBAS)
    df["time"] = pd.to_datetime(df["time"])
    vix = pd.read_parquet(VIX_PATH)[["time", "close"]].rename(columns={"close": "vix"})
    vix["time"] = pd.to_datetime(vix["time"])
    df = df.merge(vix, on="time", how="left")
    df["vix"] = df["vix"].ffill()
    return df.sort_values("time").reset_index(drop=True)


def add_smoothed_probas(df: pd.DataFrame) -> pd.DataFrame:
    """Add rolling-average proba columns for each window size."""
    df = df.sort_values(["ticker", "time"]).copy()
    for window in [3, 5, 7]:
        col = f"xs_proba_smooth_{window}"
        df[col] = df.groupby("ticker")["xs_proba"].transform(
            lambda x: x.rolling(window, min_periods=1).mean()
        )
    return df.sort_values("time").reset_index(drop=True)


def run_smoothing(df: pd.DataFrame, proba_col: str, window: int):
    """
    Rank stocks by proba_col each day; select top-N.
    Use MIN_PROBA filter on the *smoothed* proba.
    Measure edge and turnover.
    """
    dates = sorted(df["time"].unique())
    prev_portfolio = set()
    new_stocks_total = 0
    rebal_count = 0

    year_edges = {}
    year_new_stocks = {}
    year_rebal = {}

    for date in dates:
        year = pd.Timestamp(date).year
        if year < START_YEAR or year > 2025:
            prev_portfolio = set()
            continue

        day = df[df["time"] == date]
        vix_val = day["vix"].iloc[0]

        if vix_val > VIX_MAX:
            prev_portfolio = set()
            continue

        naive = df[df["year"] == year]["actual"].mean()

        top = day.nlargest(TOP_N, proba_col)
        # Filter: smoothed proba must still exceed MIN_PROBA
        if top[proba_col].min() < MIN_PROBA:
            prev_portfolio = set()
            continue

        curr_portfolio = set(top["ticker"].values)

        # Edge: actual accuracy of top-N picks vs naive
        edge = top["actual"].mean() - naive

        if year not in year_edges:
            year_edges[year] = []
            year_new_stocks[year] = 0
            year_rebal[year] = 0

        year_edges[year].append(edge)
        year_rebal[year] += 1

        if prev_portfolio:
            n_new = len(curr_portfolio - prev_portfolio)
        else:
            n_new = TOP_N
        year_new_stocks[year] += n_new

        prev_portfolio = curr_portfolio

    return year_edges, year_new_stocks, year_rebal


def summarize(year_edges, year_new_stocks, year_rebal, window: int):
    edges = []
    total_new = 0
    total_rebal = 0

    for year in sorted(year_edges):
        if len(year_edges[year]) < 5:
            continue
        edges.append(np.mean(year_edges[year]))
        total_new += year_new_stocks[year]
        total_rebal += year_rebal[year]

    if not edges:
        return None

    avg_edge = np.mean(edges)
    std_edge = np.std(edges) if len(edges) > 1 else float("nan")
    sharpe = avg_edge / std_edge if std_edge > 0 else float("nan")
    avg_turnover = total_new / (total_rebal * TOP_N) if total_rebal > 0 else float("nan")
    trades_yr = total_rebal / len(edges)

    avg_new_per_rebal = total_new / max(total_rebal, 1)
    annual_cost = avg_new_per_rebal * COST_RT / TOP_N * 250
    net_edge = avg_edge - annual_cost

    return {
        "window": window,
        "avg_edge": avg_edge,
        "sharpe": sharpe,
        "n_years": len(edges),
        "trades_yr": trades_yr,
        "turnover": avg_turnover,
        "annual_cost": annual_cost,
        "net_edge": net_edge,
    }


def main():
    print("Loading data...")
    df = load_data()
    print(f"  {len(df):,} rows | {df['ticker'].nunique()} tickers | "
          f"years {df['year'].min()}-{df['year'].max()}")

    print("Computing rolling probas (window=3,5,7)...")
    df = add_smoothed_probas(df)

    print("\n" + "=" * 78)
    print("H47: PROBA SMOOTHING — rank by N-day rolling average of xs_proba")
    print(f"  Filter: VIX<{VIX_MAX} | min_proba={MIN_PROBA} on smoothed proba | top-{TOP_N} | {START_YEAR}-2025")
    print("=" * 78)

    print(f"\n  {'Window':>8}  {'avg_edge':>9}  {'sharpe':>8}  {'n_yrs':>6}  "
          f"{'trades/yr':>10}  {'turnover':>10}  {'ann_cost':>10}  {'net_@0.3%':>10}")
    print("  " + "-" * 82)

    window_configs = [
        (1, "xs_proba"),
        (3, "xs_proba_smooth_3"),
        (5, "xs_proba_smooth_5"),
        (7, "xs_proba_smooth_7"),
    ]

    all_results = []
    for window, col in window_configs:
        ye, yn, yr = run_smoothing(df, col, window)
        result = summarize(ye, yn, yr, window)
        if result is None:
            print(f"  {window:>7}d  (no data)")
            continue
        all_results.append((window, col, ye, result))
        r = result
        print(f"  {window:>7}d  {r['avg_edge']*100:>+8.2f}%  {r['sharpe']:>8.2f}  "
              f"{r['n_years']:>6}  {r['trades_yr']:>9.1f}  {r['turnover']*100:>9.1f}%  "
              f"{r['annual_cost']*100:>9.2f}%  {r['net_edge']*100:>+9.2f}%")

    # Per-year breakdown for each window
    for window, col, year_edges, result in all_results:
        print(f"\n  Window={window}d per-year detail:")
        print(f"  {'year':>6}  {'n_days':>7}  {'avg_edge':>9}")
        print("  " + "-" * 28)
        for year in sorted(year_edges):
            if len(year_edges[year]) < 5:
                continue
            avg_e = np.mean(year_edges[year])
            print(f"  {year:>6}  {len(year_edges[year]):>7}  {avg_e*100:>+8.2f}%")

    print(f"\n  INTERPRETATION:")
    if len(all_results) >= 2:
        base = all_results[0][3]
        best_net = max(all_results, key=lambda x: x[3]["net_edge"])[3]
        print(f"  Baseline (N=1): edge={base['avg_edge']*100:+.2f}%, net={base['net_edge']*100:+.2f}%")
        print(f"  Best net (N={best_net['window']}): edge={best_net['avg_edge']*100:+.2f}%, net={best_net['net_edge']*100:+.2f}%")
    print(f"  If smoothing kills edge → signal is 1-day phenomenon")
    print(f"  If smoothing preserves edge with lower turnover → signal persists over days")


if __name__ == "__main__":
    main()
