"""
H46: Persistence Filter — reduce turnover by requiring K consecutive days in top-N.

Only buy a stock if it has appeared in top-N for K consecutive days.
This "confirmation" filter delays entry by K-1 days but cuts churn significantly.

Sweep: K=1 (baseline), 2, 3 consecutive days in top-N required.

Usage:
    conda run -n stocks python analysis/h46_persistence_filter.py
"""
import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict

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


def run_persistence(df: pd.DataFrame, K: int):
    """
    For each day, select top-N stocks that have been in top-N for K consecutive days.
    If fewer than TOP_N qualifying stocks, skip the day (stay in cash).

    Returns: per-year edge, turnover, trade count.
    """
    dates = sorted(df["time"].unique())

    # Track consecutive top-N streak per ticker: streak[ticker] = count of consecutive days in top-N
    streak = defaultdict(int)
    prev_portfolio = set()
    new_stocks_total = 0
    rebal_count = 0

    year_data = defaultdict(lambda: {"edges": [], "new_stocks": 0, "rebal": 0})

    for date in dates:
        year = pd.Timestamp(date).year
        if year < START_YEAR or year > 2025:
            streak.clear()
            prev_portfolio = set()
            continue

        day = df[df["time"] == date]
        vix_val = day["vix"].iloc[0]

        if vix_val > VIX_MAX:
            # Reset on VIX breach — signal regime not valid
            streak.clear()
            prev_portfolio = set()
            continue

        naive = df[df["year"] == year]["actual"].mean()

        # Identify today's top-N by xs_proba (raw ranking, no proba filter yet)
        today_top_n = set(day.nlargest(TOP_N + K + 5, "xs_proba")["ticker"].values[:TOP_N + K + 5])

        # Update streaks: increment for stocks in today's top-N, reset others
        all_tickers = set(day["ticker"].values)
        for ticker in all_tickers:
            if ticker in today_top_n:
                streak[ticker] += 1
            else:
                streak[ticker] = 0

        # Eligible: in today's top-N AND streak >= K AND xs_proba >= MIN_PROBA
        day_dict = day.set_index("ticker")
        top_n_today = day.nlargest(TOP_N, "xs_proba")
        top_n_tickers = set(top_n_today["ticker"].values)

        # For K=1: standard top-N (no extra filter)
        if K == 1:
            eligible = top_n_tickers
        else:
            # Need streak >= K in top-N
            # Also allow being in top-(N*2) for streak counting, but must be in top-N today to trade
            eligible = {t for t in top_n_tickers if streak.get(t, 0) >= K}

        # Check min proba for eligible set
        elig_rows = day[day["ticker"].isin(eligible)].nlargest(TOP_N, "xs_proba")
        if len(elig_rows) < TOP_N or elig_rows["xs_proba"].min() < MIN_PROBA:
            # Not enough confident persistent stocks — stay in previous portfolio or skip
            prev_portfolio = set()
            continue

        curr_portfolio = set(elig_rows["ticker"].values[:TOP_N])

        # Compute edge
        portfolio_actuals = day[day["ticker"].isin(curr_portfolio)]["actual"].values
        edge = portfolio_actuals.mean() - naive
        year_data[year]["edges"].append(edge)

        # Turnover
        if prev_portfolio:
            n_new = len(curr_portfolio - prev_portfolio)
        else:
            n_new = TOP_N  # initial buy
        year_data[year]["new_stocks"] += n_new
        year_data[year]["rebal"] += 1

        prev_portfolio = curr_portfolio

    return year_data


def summarize(year_data: dict, K: int):
    """Print per-year results and return summary stats."""
    edges = []
    total_new = 0
    total_rebal = 0

    for year in sorted(year_data):
        yd = year_data[year]
        if len(yd["edges"]) < 5:
            continue
        avg_edge = np.mean(yd["edges"])
        edges.append(avg_edge)
        total_new += yd["new_stocks"]
        total_rebal += yd["rebal"]

    if not edges:
        return None

    avg_edge = np.mean(edges)
    std_edge = np.std(edges) if len(edges) > 1 else float("nan")
    sharpe = avg_edge / std_edge if std_edge > 0 else float("nan")
    avg_turnover = (total_new / (total_rebal * TOP_N)) if total_rebal > 0 else float("nan")
    trades_yr = total_rebal / len(edges)

    # Annual cost = daily_turnover * COST_RT * 250 trading days / TOP_N
    # More precisely: (avg new stocks per rebal / TOP_N) * COST_RT * rebal_per_yr
    avg_new_per_rebal = total_new / max(total_rebal, 1)
    cost_per_day = avg_new_per_rebal * COST_RT / TOP_N
    annual_cost = cost_per_day * 250
    net_edge = avg_edge - annual_cost

    return {
        "K": K,
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

    print("\n" + "=" * 78)
    print("H46: PERSISTENCE FILTER — K consecutive days in top-N required before buying")
    print(f"  Filter: VIX<{VIX_MAX} | min_proba={MIN_PROBA} | top-{TOP_N} | years {START_YEAR}-2025")
    print("=" * 78)

    print(f"\n  {'K':>4}  {'avg_edge':>9}  {'sharpe':>8}  {'n_yrs':>6}  "
          f"{'trades/yr':>10}  {'turnover':>10}  {'ann_cost':>10}  {'net_@0.3%':>10}")
    print("  " + "-" * 78)

    all_results = []
    for K in [1, 2, 3]:
        year_data = run_persistence(df, K)
        result = summarize(year_data, K)
        if result is None:
            print(f"  {K:>4}  (no data)")
            continue
        all_results.append(result)
        r = result
        print(f"  {r['K']:>4}  {r['avg_edge']*100:>+8.2f}%  {r['sharpe']:>8.2f}  "
              f"{r['n_years']:>6}  {r['trades_yr']:>9.1f}  {r['turnover']*100:>9.1f}%  "
              f"{r['annual_cost']*100:>9.2f}%  {r['net_edge']*100:>+9.2f}%")

    # Per-year detail for each K
    for K in [1, 2, 3]:
        year_data = run_persistence(df, K)
        print(f"\n  K={K} per-year detail:")
        print(f"  {'year':>6}  {'n_days':>7}  {'avg_edge':>9}  {'turnover':>10}  "
              f"{'ann_cost':>10}  {'net':>8}")
        print("  " + "-" * 56)
        for year in sorted(year_data):
            yd = year_data[year]
            if len(yd["edges"]) < 5:
                continue
            avg_e = np.mean(yd["edges"])
            to = (yd["new_stocks"] / (yd["rebal"] * TOP_N)) if yd["rebal"] > 0 else float("nan")
            avg_new = yd["new_stocks"] / max(yd["rebal"], 1)
            ann_cost = avg_new * COST_RT / TOP_N * 250
            net = avg_e - ann_cost
            print(f"  {year:>6}  {yd['rebal']:>7}  {avg_e*100:>+8.2f}%  "
                  f"{to*100:>9.1f}%  {ann_cost*100:>9.2f}%  {net*100:>+7.2f}%")

    print(f"\n  INTERPRETATION:")
    if len(all_results) >= 2:
        k1 = all_results[0]
        k2 = all_results[1]
        turnover_reduction = (k1["turnover"] - k2["turnover"]) / k1["turnover"] * 100
        edge_change = (k2["avg_edge"] - k1["avg_edge"]) * 100
        net_gain = (k2["net_edge"] - k1["net_edge"]) * 100
        print(f"  K=1→K=2: turnover drops {turnover_reduction:.1f}%, edge changes {edge_change:+.2f}%, net {net_gain:+.2f}%")
    print(f"  Verdict: K>=2 reduces turnover. Check if edge loss exceeds cost savings.")


if __name__ == "__main__":
    main()
