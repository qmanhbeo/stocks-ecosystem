"""
H49: Patient Rebalancing — exit only when stock drops below rank M (M > N).

Standard factor investing: don't rebalance strictly to top-N every day.
Instead:
  - Buy: stock must be in top-N (very high bar)
  - Hold: keep stock as long as it stays in top-M (broader holding zone)
  - Sell: only when stock falls below rank M

Sweep: (N=5, M=7), (N=5, M=10), (N=5, M=15)

Usage:
    conda run -n stocks python analysis/h49_patient_rebalancing.py
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


def run_patient(df: pd.DataFrame, N: int, M: int):
    """
    Patient rebalancing with buy zone top-N and hold zone top-M.

    For each day:
      1. Get today's ranking of all stocks by xs_proba
      2. Stocks currently held that are still in top-M: KEEP
      3. Stocks held that fell below rank M: SELL
      4. Fill empty slots with best available stock in top-N (with min_proba filter)
      5. If no valid replacement, hold cash in that slot

    Returns: per-year stats dict
    """
    dates = sorted(df["time"].unique())
    portfolio = set()   # current holdings (up to N stocks)
    year_data = {}

    for date in dates:
        year = pd.Timestamp(date).year
        if year < START_YEAR or year > 2025:
            portfolio = set()
            continue

        day = df[df["time"] == date].copy()
        vix_val = day["vix"].iloc[0]

        if vix_val > VIX_MAX:
            portfolio = set()
            continue

        naive = df[df["year"] == year]["actual"].mean()

        # Rank all stocks by xs_proba for this day
        day_sorted = day.sort_values("xs_proba", ascending=False).reset_index(drop=True)
        day_sorted["rank"] = day_sorted.index + 1  # rank 1 = best

        rank_lookup = day_sorted.set_index("ticker")["rank"].to_dict()
        proba_lookup = day_sorted.set_index("ticker")["xs_proba"].to_dict()

        # Step 1: Remove holdings that fell below rank M
        to_sell = {t for t in portfolio if rank_lookup.get(t, 999) > M}
        portfolio -= to_sell

        # Step 2: Fill empty slots from top-N (must have proba >= MIN_PROBA)
        top_n_candidates = day_sorted[
            (day_sorted["rank"] <= N) & (day_sorted["xs_proba"] >= MIN_PROBA)
        ]["ticker"].values

        new_buys = set()
        for candidate in top_n_candidates:
            if len(portfolio) >= N:
                break
            if candidate not in portfolio:
                portfolio.add(candidate)
                new_buys.add(candidate)

        # If portfolio is still empty (no valid top-N candidates), skip
        if not portfolio:
            continue

        # Step 3: Compute edge
        held_actuals = day[day["ticker"].isin(portfolio)]["actual"].values
        if len(held_actuals) == 0:
            continue

        edge = held_actuals.mean() - naive

        if year not in year_data:
            year_data[year] = {
                "edges": [], "new_buys": 0, "rebal_days": 0,
                "portfolio_sizes": [], "sell_events": 0,
            }

        year_data[year]["edges"].append(edge)
        year_data[year]["new_buys"] += len(new_buys)
        year_data[year]["rebal_days"] += 1
        year_data[year]["portfolio_sizes"].append(len(portfolio))
        year_data[year]["sell_events"] += len(to_sell)

    return year_data


def summarize(year_data: dict, N: int, M: int):
    edges = []
    total_new_buys = 0
    total_days = 0
    total_sells = 0

    for year in sorted(year_data):
        yd = year_data[year]
        if len(yd["edges"]) < 5:
            continue
        edges.append(np.mean(yd["edges"]))
        total_new_buys += yd["new_buys"]
        total_days += yd["rebal_days"]
        total_sells += yd["sell_events"]

    if not edges:
        return None

    avg_edge = np.mean(edges)
    std_edge = np.std(edges) if len(edges) > 1 else float("nan")
    sharpe = avg_edge / std_edge if std_edge > 0 else float("nan")

    # Turnover: buys per day as fraction of portfolio
    avg_buys_per_day = total_new_buys / max(total_days, 1)
    turnover = avg_buys_per_day / N

    # Annual cost: each buy is 1 round trip on 1/TOP_N of portfolio
    # cost_per_day = buys_per_day * COST_RT * (1/TOP_N) position weight
    annual_cost = avg_buys_per_day * COST_RT / TOP_N * 250
    net_edge = avg_edge - annual_cost

    # Sells per day
    avg_sells_per_day = total_sells / max(total_days, 1)

    return {
        "N": N, "M": M,
        "avg_edge": avg_edge,
        "sharpe": sharpe,
        "n_years": len(edges),
        "trades_yr": total_days / len(edges),
        "turnover": turnover,
        "annual_cost": annual_cost,
        "net_edge": net_edge,
        "sells_per_day": avg_sells_per_day,
        "buys_per_day": avg_buys_per_day,
    }


def main():
    print("Loading data...")
    df = load_data()
    print(f"  {len(df):,} rows | {df['ticker'].nunique()} tickers | "
          f"years {df['year'].min()}-{df['year'].max()}")

    print("\n" + "=" * 78)
    print("H49: PATIENT REBALANCING — buy top-N, hold until rank falls below M")
    print(f"  Filter: VIX<{VIX_MAX} | min_proba={MIN_PROBA} | {START_YEAR}-2025")
    print("=" * 78)

    print(f"\n  {'(N,M)':>8}  {'avg_edge':>9}  {'sharpe':>8}  {'n_yrs':>6}  "
          f"{'trades/yr':>10}  {'turnover':>10}  {'ann_cost':>10}  {'net_@0.3%':>10}  {'sells/d':>8}")
    print("  " + "-" * 90)

    configs = [
        (5, 5),   # baseline: strict top-5 only (same as H43)
        (5, 7),
        (5, 10),
        (5, 15),
    ]

    all_results = []
    for N, M in configs:
        year_data = run_patient(df, N, M)
        result = summarize(year_data, N, M)
        if result is None:
            print(f"  ({N},{M:>2})   (no data)")
            continue
        all_results.append((N, M, year_data, result))
        r = result
        label = f"({N},{M})"
        print(f"  {label:>8}  {r['avg_edge']*100:>+8.2f}%  {r['sharpe']:>8.2f}  "
              f"{r['n_years']:>6}  {r['trades_yr']:>9.1f}  {r['turnover']*100:>9.1f}%  "
              f"{r['annual_cost']*100:>9.2f}%  {r['net_edge']*100:>+9.2f}%  "
              f"{r['sells_per_day']:>7.2f}")

    # Per-year breakdown for each config
    for N, M, year_data, result in all_results:
        print(f"\n  (N={N}, M={M}) per-year detail:")
        print(f"  {'year':>6}  {'n_days':>7}  {'avg_edge':>9}  {'buys/d':>8}  "
              f"{'turnover':>10}  {'ann_cost':>10}  {'net':>8}")
        print("  " + "-" * 62)
        for year in sorted(year_data):
            yd = year_data[year]
            if len(yd["edges"]) < 5:
                continue
            avg_e = np.mean(yd["edges"])
            n_days = yd["rebal_days"]
            buys_d = yd["new_buys"] / n_days if n_days > 0 else 0.0
            to = buys_d / N
            ann_cost = buys_d * COST_RT / TOP_N * 250
            net = avg_e - ann_cost
            print(f"  {year:>6}  {n_days:>7}  {avg_e*100:>+8.2f}%  "
                  f"{buys_d:>7.2f}  {to*100:>9.1f}%  {ann_cost*100:>9.2f}%  "
                  f"{net*100:>+7.2f}%")

    print(f"\n  INTERPRETATION:")
    if len(all_results) >= 2:
        base = all_results[0][3]  # (5,5) strict
        print(f"  Baseline (N=5,M=5): edge={base['avg_edge']*100:+.2f}%, "
              f"turnover={base['turnover']*100:.1f}%, net={base['net_edge']*100:+.2f}%")
        for N, M, _, r in all_results[1:]:
            turn_drop = (base["turnover"] - r["turnover"]) / base["turnover"] * 100
            net_gain = (r["net_edge"] - base["net_edge"]) * 100
            print(f"  (N={N},M={M}): turnover -{turn_drop:.1f}%, net {net_gain:+.2f}% vs baseline")
    print(f"  Wider exit zone = less churn, similar edge if signal is sticky")


if __name__ == "__main__":
    main()
