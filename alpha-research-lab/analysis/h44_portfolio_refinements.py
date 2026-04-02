"""
H44: Portfolio refinement experiments.

Four experiments building on H43 (dynamic top-N rank portfolio):

  1. TURNOVER ANALYSIS  — how stable is the top-5 daily? Real cost burden.
  2. REBALANCING FREQ   — trade every N days; does edge decay? After-cost results.
  3. CONFIDENCE SIZING  — weight positions proportional to xs_proba score.
  4. SECTOR CAP         — force max 2 stocks per sector per day.

Usage:
    conda run -n stocks python analysis/h44_portfolio_refinements.py
"""
import numpy as np
import pandas as pd
from pathlib import Path
from path_utils import data_path
from scipy.stats import ttest_1samp

ALL_PROBAS = data_path("features/xs_barrier_all_probas.parquet")
VIX_PATH   = data_path("fx-commodities/fx_commodities_vix_1D.parquet")

TOP_N      = 5
MIN_PROBA  = 0.55
VIX_MAX    = 30.0
START_YEAR = 2015

# Round-trip cost per stock position (entry + exit combined)
# Vietnam retail brokerage: ~0.15% each way = 0.30% round-trip
COST_RT = 0.003

SECTOR_MAP = {
    # Banking (12 stocks)
    "ACB": "banking",  "BID": "banking",  "CTG": "banking",  "EIB": "banking",
    "HDB": "banking",  "MBB": "banking",  "SHB": "banking",  "STB": "banking",
    "TCB": "banking",  "TPB": "banking",  "VCB": "banking",  "VPB": "banking",
    # Finance / Securities / Insurance (5)
    "BVH": "finance",  "HCM": "finance",  "SSI": "finance",
    "VND": "finance",  "PVB": "finance",
    # Real Estate (9)
    "BCG": "realestate", "DXG": "realestate", "KBC": "realestate",
    "KDH": "realestate", "NLG": "realestate", "NVL": "realestate",
    "PDR": "realestate", "VHM": "realestate", "VRE": "realestate",
    # Technology (2)
    "CMG": "technology", "FPT": "technology",
    # Energy / Oil & Gas (3)
    "GAS": "energy",  "PLX": "energy",   "POW": "energy",
    # Industrials / Construction / Manufacturing (5)
    "CII": "industrial", "CTD": "industrial", "GEX": "industrial",
    "HPG": "industrial", "HSG": "industrial",
    # Consumer Staples & Discretionary (7)
    "DBC": "consumer", "DGW": "consumer", "MSN": "consumer", "MWG": "consumer",
    "PNJ": "consumer", "SAB": "consumer", "VNM": "consumer",
    # Chemicals / Fertilizers (3)
    "DCM": "chemicals", "DGC": "chemicals", "DPM": "chemicals",
    # Transport / Logistics (3)
    "ANV": "transport", "GMD": "transport", "VJC": "transport",
    # Conglomerate (1)
    "VIC": "conglomerate",
    # Materials / Utilities (2)
    "AAA": "materials", "REE": "utilities",
}


def load_data():
    df = pd.read_parquet(ALL_PROBAS)
    df["time"] = pd.to_datetime(df["time"])
    vix = pd.read_parquet(VIX_PATH)[["time", "close"]].rename(columns={"close": "vix"})
    vix["time"] = pd.to_datetime(vix["time"])
    df = df.merge(vix, on="time", how="left")
    df["vix"] = df["vix"].ffill()
    df["sector"] = df["ticker"].map(SECTOR_MAP).fillna("other")
    return df.sort_values("time").reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# EXP 1: Turnover Analysis
# ─────────────────────────────────────────────────────────────────────────────
def exp1_turnover(df):
    print("=" * 70)
    print("EXP 1: TURNOVER ANALYSIS — how stable is the top-5 day to day?")
    print("=" * 70)

    dates = sorted(df["time"].unique())
    prev_top = set()
    turnovers = []  # fraction of top-5 that changed vs previous day

    for date in dates:
        day = df[df["time"] == date]
        if day["vix"].iloc[0] > VIX_MAX:
            prev_top = set()
            continue
        top = day.nlargest(TOP_N, "xs_proba")
        if top["xs_proba"].min() < MIN_PROBA:
            prev_top = set()
            continue
        curr_top = set(top["ticker"].values)
        if prev_top:
            n_new = len(curr_top - prev_top)
            turnovers.append(n_new)
        prev_top = curr_top

    turnovers = np.array(turnovers)
    avg_new = turnovers.mean()

    print(f"\n  Total rebalancing days : {len(turnovers)}")
    print(f"  Avg new stocks per day : {avg_new:.2f} out of {TOP_N}")
    print(f"  Avg daily turnover     : {avg_new/TOP_N*100:.1f}%")
    print(f"\n  Distribution of daily changes:")
    for n in range(TOP_N + 1):
        pct = (turnovers == n).mean() * 100
        bar = "#" * int(pct / 2)
        print(f"    {n} stocks changed: {pct:5.1f}%  {bar}")

    print(f"\n  Cost burden at different brokerage rates:")
    print(f"  {'Rate (RT)':>12}  {'Daily drag':>12}  {'Annual drag':>13}  {'Breakeven edge':>15}")
    print("  " + "-" * 58)
    # Gross portfolio edge ≈ 12.81% per year over 250 days = 0.0512%/day
    gross_daily = 0.1281 / 250
    for rate in [0.001, 0.002, 0.003, 0.005, 0.007, 0.010]:
        daily_cost = avg_new * rate / TOP_N       # cost as fraction of portfolio
        annual_cost = daily_cost * 250
        be_edge = annual_cost / 0.1281 * 100      # % of our gross edge consumed
        print(f"  {rate*100:>11.2f}%  {daily_cost*100:>11.4f}%  {annual_cost*100:>12.2f}%  "
              f"{be_edge:>13.1f}% of signal")

    print(f"\n  At 0.30% RT (typical VN retail): annual drag = "
          f"{avg_new * COST_RT / TOP_N * 250 * 100:.2f}% of portfolio")
    print(f"  Signal gross (H43): ~12.81%/yr → net after cost: "
          f"~{(0.1281 - avg_new * COST_RT / TOP_N * 250)*100:.2f}%/yr")


# ─────────────────────────────────────────────────────────────────────────────
# EXP 2: Rebalancing Frequency
# ─────────────────────────────────────────────────────────────────────────────
def exp2_rebalancing_freq(df):
    print("\n" + "=" * 70)
    print("EXP 2: REBALANCING FREQUENCY — trade every N days")
    print(f"  Filter: VIX<{VIX_MAX} | min_proba={MIN_PROBA} | top-{TOP_N}")
    print("=" * 70)

    dates = sorted(df["time"].unique())
    date_to_idx = {d: i for i, d in enumerate(dates)}

    print(f"\n  {'N days':>8}  {'avg_edge':>9}  {'sharpe':>8}  {'n_years':>8}  "
          f"{'trades/yr':>10}  {'turnover':>10}  {'net_edge@0.3%':>14}")
    print("  " + "-" * 78)

    for rebal_n in [1, 2, 3, 5, 7, 10, 15, 21]:
        # For each year, pick top-5 every rebal_n days, hold for rebal_n days
        year_edges = []
        total_trades = 0
        total_new_stocks = 0
        total_rebal = 0

        for year in range(START_YEAR, 2026):
            year_dates = [d for d in dates
                          if pd.Timestamp(d).year == year]
            if len(year_dates) < rebal_n:
                continue

            naive = df[df["year"] == year]["actual"].mean()
            held_actuals = []
            prev_portfolio = set()

            # Rebalance on 0, rebal_n, 2*rebal_n, ... indexed days
            for i in range(0, len(year_dates), rebal_n):
                rebal_date = year_dates[i]
                day = df[df["time"] == rebal_date]
                if day["vix"].iloc[0] > VIX_MAX:
                    prev_portfolio = set()
                    continue
                top = day.nlargest(TOP_N, "xs_proba")
                if top["xs_proba"].min() < MIN_PROBA:
                    prev_portfolio = set()
                    continue

                curr_portfolio = set(top["ticker"].values)
                n_new = len(curr_portfolio - prev_portfolio) if prev_portfolio else TOP_N
                total_new_stocks += n_new
                total_rebal += 1
                prev_portfolio = curr_portfolio

                # Collect actuals for held period
                held_dates = year_dates[i: i + rebal_n]
                for hd in held_dates:
                    held_day = df[(df["time"] == hd) & (df["ticker"].isin(curr_portfolio))]
                    if len(held_day) > 0:
                        held_actuals.append(held_day["actual"].mean() - naive)

            if len(held_actuals) >= 5:
                year_edges.append(np.mean(held_actuals))
                total_trades += len(year_dates) // rebal_n

        if not year_edges:
            continue

        avg_edge = np.mean(year_edges)
        std_edge = np.std(year_edges) if len(year_edges) > 1 else float("nan")
        sharpe = avg_edge / std_edge if std_edge > 0 else float("nan")
        trades_yr = total_trades / max(len(year_edges), 1)
        avg_turnover = total_new_stocks / (total_rebal * TOP_N) if total_rebal > 0 else float("nan")

        # Net edge after costs (cost = avg_new_stocks * COST_RT / TOP_N per rebalancing)
        # Annualized cost = (avg_new_stocks/rebal * COST_RT / TOP_N) * (250/rebal_n)
        cost_per_rebal = (total_new_stocks / max(total_rebal, 1)) * COST_RT / TOP_N
        rebal_per_yr = 250 / rebal_n
        annual_cost = cost_per_rebal * rebal_per_yr
        net_edge = avg_edge - annual_cost

        print(f"  {rebal_n:>8}  {avg_edge*100:>+8.2f}%  {sharpe:>8.2f}  {len(year_edges):>8}  "
              f"{trades_yr:>9.1f}  {avg_turnover*100:>9.1f}%  {net_edge*100:>+13.2f}%")


# ─────────────────────────────────────────────────────────────────────────────
# EXP 3: Confidence-Weighted Position Sizing
# ─────────────────────────────────────────────────────────────────────────────
def exp3_confidence_weighting(df):
    print("\n" + "=" * 70)
    print("EXP 3: CONFIDENCE-WEIGHTED SIZING vs EQUAL WEIGHT")
    print(f"  Weight ∝ xs_proba (vs 1/N equal weight) | top-{TOP_N} | VIX<{VIX_MAX}")
    print("=" * 70)
    print(f"\n  {'year':>5}  {'eq_edge':>9}  {'wt_edge':>9}  {'delta':>8}  {'improvement':>12}")
    print("  " + "-" * 55)

    year_results = []
    for year in range(START_YEAR, 2026):
        ydf = df[df["year"] == year]
        naive = ydf["actual"].mean()

        eq_day_edges, wt_day_edges = [], []
        for date, day in ydf.groupby("time"):
            if day["vix"].iloc[0] > VIX_MAX:
                continue
            top = day.nlargest(TOP_N, "xs_proba")
            if top["xs_proba"].min() < MIN_PROBA:
                continue

            actuals = top["actual"].values
            probas  = top["xs_proba"].values

            eq_edge = actuals.mean() - naive
            wt_edge = np.average(actuals, weights=probas) - naive

            eq_day_edges.append(eq_edge)
            wt_day_edges.append(wt_edge)

        if len(eq_day_edges) < 5:
            continue

        eq_yr  = np.mean(eq_day_edges)
        wt_yr  = np.mean(wt_day_edges)
        delta  = wt_yr - eq_yr
        improv = delta / abs(eq_yr) * 100 if eq_yr != 0 else float("nan")
        print(f"  {year:>5}  {eq_yr*100:>+8.2f}%  {wt_yr*100:>+8.2f}%  "
              f"{delta*100:>+7.3f}%  {improv:>+10.1f}%")
        year_results.append({"year": year, "eq": eq_yr, "wt": wt_yr})

    if year_results:
        eq_avg = np.mean([r["eq"] for r in year_results])
        wt_avg = np.mean([r["wt"] for r in year_results])
        eq_std = np.std([r["eq"] for r in year_results])
        wt_std = np.std([r["wt"] for r in year_results])
        print(f"\n  {'avg':>5}  {eq_avg*100:>+8.2f}%  {wt_avg*100:>+8.2f}%  "
              f"{(wt_avg-eq_avg)*100:>+7.3f}%")
        print(f"  Equal weight Sharpe  : {eq_avg/eq_std:.2f}")
        print(f"  Prob  weight Sharpe  : {wt_avg/wt_std:.2f}")


# ─────────────────────────────────────────────────────────────────────────────
# EXP 4: Sector Diversification Cap
# ─────────────────────────────────────────────────────────────────────────────
def exp4_sector_cap(df, max_per_sector=2):
    print("\n" + "=" * 70)
    print(f"EXP 4: SECTOR CAP (max {max_per_sector} stocks/sector) vs UNCAPPED")
    print(f"  Filter: VIX<{VIX_MAX} | min_proba={MIN_PROBA}")
    print("=" * 70)
    print(f"\n  {'year':>5}  {'uncap_n':>8}  {'uncap_edge':>11}  "
          f"{'cap_n':>7}  {'cap_edge':>10}  {'delta':>8}")
    print("  " + "-" * 62)

    year_results = []
    for year in range(START_YEAR, 2026):
        ydf = df[df["year"] == year]
        naive = ydf["actual"].mean()

        uncap_edges, cap_edges = [], []
        uncap_n_total, cap_n_total = 0, 0

        for date, day in ydf.groupby("time"):
            if day["vix"].iloc[0] > VIX_MAX:
                continue

            # Uncapped: top-N by proba
            top_uncap = day.nlargest(TOP_N, "xs_proba")
            if top_uncap["xs_proba"].min() < MIN_PROBA:
                continue

            uncap_edges.append(top_uncap["actual"].mean() - naive)
            uncap_n_total += len(top_uncap)

            # Sector-capped: greedy selection, highest proba first, skip if sector full
            day_sorted = day.sort_values("xs_proba", ascending=False)
            sector_count = {}
            selected = []
            for _, row in day_sorted.iterrows():
                sec = row["sector"]
                if sector_count.get(sec, 0) >= max_per_sector:
                    continue
                if row["xs_proba"] < MIN_PROBA:
                    break
                selected.append(row)
                sector_count[sec] = sector_count.get(sec, 0) + 1
                if len(selected) == TOP_N:
                    break

            if len(selected) >= 2:
                sel_df = pd.DataFrame(selected)
                cap_edges.append(sel_df["actual"].mean() - naive)
                cap_n_total += len(selected)

        if len(uncap_edges) < 5:
            continue

        uncap_avg = np.mean(uncap_edges)
        cap_avg   = np.mean(cap_edges) if cap_edges else float("nan")
        delta     = cap_avg - uncap_avg if not np.isnan(cap_avg) else float("nan")
        avg_cap_n = cap_n_total / max(len(cap_edges), 1)
        avg_uncap_n = uncap_n_total / max(len(uncap_edges), 1)

        print(f"  {year:>5}  {avg_uncap_n:>8.1f}  {uncap_avg*100:>+10.2f}%  "
              f"{avg_cap_n:>7.1f}  {cap_avg*100:>+9.2f}%  {delta*100:>+7.3f}%")
        year_results.append({"year": year, "uncap": uncap_avg, "cap": cap_avg})

    if year_results:
        uncap_avg = np.mean([r["uncap"] for r in year_results])
        cap_avg   = np.mean([r["cap"] for r in year_results if not np.isnan(r["cap"])])
        uncap_std = np.std([r["uncap"] for r in year_results])
        cap_std   = np.std([r["cap"] for r in year_results if not np.isnan(r["cap"])])
        print(f"\n  Uncapped avg edge: {uncap_avg*100:+.2f}%  Sharpe: {uncap_avg/uncap_std:.2f}")
        print(f"  Capped   avg edge: {cap_avg*100:+.2f}%  Sharpe: {cap_avg/cap_std:.2f}")

        # Show what sectors dominate the uncapped portfolio
        print(f"\n  Sector concentration in uncapped top-{TOP_N} picks:")
        sector_counts = {}
        for date, day in df[df["year"] >= START_YEAR].groupby("time"):
            if day["vix"].iloc[0] > VIX_MAX:
                continue
            top = day.nlargest(TOP_N, "xs_proba")
            if top["xs_proba"].min() < MIN_PROBA:
                continue
            for sec in top["sector"].values:
                sector_counts[sec] = sector_counts.get(sec, 0) + 1
        total = sum(sector_counts.values())
        for sec, cnt in sorted(sector_counts.items(), key=lambda x: -x[1]):
            print(f"    {sec:>14}: {cnt:>5} picks  ({cnt/total*100:.1f}%)")


if __name__ == "__main__":
    print("Loading data...")
    df = load_data()
    print(f"  {len(df):,} rows | {df['ticker'].nunique()} tickers | "
          f"years {df['year'].min()}-{df['year'].max()}")

    exp1_turnover(df)
    exp2_rebalancing_freq(df)
    exp3_confidence_weighting(df)
    exp4_sector_cap(df)
