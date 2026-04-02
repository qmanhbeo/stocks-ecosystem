"""
H48: Signal Decay Curve with Real Returns.

On each day when top-5 is selected, track the actual relative return
(vs VNINDEX) at day +1, +2, +3, +5, +7, +10, +15.

Shows the EXACT holding period where the signal is still worth the cost.

Usage:
    conda run -n stocks python analysis/h48_signal_decay.py
"""
import numpy as np
import pandas as pd
from pathlib import Path
from path_utils import data_path

ALL_PROBAS  = data_path("features/xs_barrier_all_probas.parquet")
VIX_PATH    = data_path("fx-commodities/fx_commodities_vix_1D.parquet")
STOCK_DIR   = data_path("stock")
VNI_FILE    = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"

TOP_N       = 5
MIN_PROBA   = 0.55
VIX_MAX     = 30.0
START_YEAR  = 2015
HOLD_DAYS   = [1, 2, 3, 5, 7, 10, 15]
COST_RT     = 0.003


def load_prices():
    """Build a wide price table: rows=date, cols=ticker; also VNINDEX."""
    print("Loading VNINDEX...")
    vni = pd.read_parquet(VNI_FILE)[["time", "close"]].rename(columns={"close": "vni"})
    vni["time"] = pd.to_datetime(vni["time"])
    vni = vni.sort_values("time").reset_index(drop=True)

    print("Loading all stock prices...")
    stock_files = sorted(STOCK_DIR.glob("gia_lich_su_*_1D.parquet"))
    stock_files = [f for f in stock_files if "VNINDEX" not in f.name]

    all_prices = {}
    for sf in stock_files:
        ticker = sf.name.replace("gia_lich_su_", "").replace("_1D.parquet", "")
        raw = pd.read_parquet(sf)[["time", "close"]].copy()
        raw["time"] = pd.to_datetime(raw["time"])
        raw = raw.sort_values("time").drop_duplicates("time")
        all_prices[ticker] = raw.set_index("time")["close"]

    # Build wide DataFrame
    price_wide = pd.DataFrame(all_prices)
    price_wide = price_wide.sort_index()

    # Add VNINDEX
    vni_series = vni.set_index("time")["vni"]
    price_wide["VNINDEX"] = vni_series

    print(f"  Price table: {len(price_wide)} dates x {price_wide.shape[1]} tickers")
    return price_wide


def compute_fwd_rel_returns(price_wide: pd.DataFrame, hold_days: list):
    """
    Compute N-day forward relative return vs VNINDEX for each (date, ticker).
    Returns a dict: hold -> DataFrame(date, ticker, fwd_rel)
    """
    times = price_wide.index.values
    n = len(times)
    vni = price_wide["VNINDEX"].values
    results = {}

    for hold in hold_days:
        records = []
        for i in range(n - hold):
            t0 = times[i]
            if pd.Timestamp(t0).year > 2025:
                continue
            vni0 = vni[i]
            vnih = vni[i + hold]
            if pd.isna(vni0) or pd.isna(vnih) or vni0 == 0:
                continue
            vni_ret = vnih / vni0 - 1.0

            for ticker in price_wide.columns:
                if ticker == "VNINDEX":
                    continue
                p0 = price_wide.iloc[i][ticker]
                ph = price_wide.iloc[i + hold][ticker]
                if pd.isna(p0) or pd.isna(ph) or p0 == 0:
                    continue
                stock_ret = ph / p0 - 1.0
                records.append({"time": t0, "ticker": ticker, "fwd_rel": stock_ret - vni_ret})

        results[hold] = pd.DataFrame(records)
        print(f"  hold={hold}d: {len(results[hold]):,} records")

    return results


def load_probas():
    df = pd.read_parquet(ALL_PROBAS)
    df["time"] = pd.to_datetime(df["time"])
    vix = pd.read_parquet(VIX_PATH)[["time", "close"]].rename(columns={"close": "vix"})
    vix["time"] = pd.to_datetime(vix["time"])
    df = df.merge(vix, on="time", how="left")
    df["vix"] = df["vix"].ffill()
    return df


def get_portfolio_groups(probas: pd.DataFrame):
    """
    For each trading day, classify each stock into:
      - "top5"   : selected in top-5 (model's recommendation)
      - "Q5"     : top quintile (top 20%) but not necessarily top-5
      - "Q1"     : bottom quintile (bottom 20%)
      - "naive"  : all stocks (random baseline)
    Returns DataFrame with (time, ticker, group).
    """
    records = []
    for date, day in probas[
        (probas["year"] >= START_YEAR) & (probas["year"] <= 2025)
    ].groupby("time"):
        vix_val = day["vix"].iloc[0]
        if vix_val > VIX_MAX:
            continue

        n_stocks = len(day)
        if n_stocks < 10:
            continue

        day = day.sort_values("xs_proba", ascending=False).reset_index(drop=True)
        day["rank_pct"] = day["xs_proba"].rank(pct=True)

        top5_set = set(day.head(TOP_N)["ticker"].values)
        min_top5_proba = day.head(TOP_N)["xs_proba"].min()

        if min_top5_proba < MIN_PROBA:
            continue

        for _, row in day.iterrows():
            if row["ticker"] in top5_set:
                group = "top5"
            elif row["rank_pct"] >= 0.8:
                group = "Q5"
            elif row["rank_pct"] <= 0.2:
                group = "Q1"
            else:
                group = "mid"

            records.append({
                "time": date,
                "ticker": row["ticker"],
                "group": group,
            })

    return pd.DataFrame(records)


def main():
    price_wide = load_prices()

    print("Computing forward returns for all hold periods...")
    fwd_returns = compute_fwd_rel_returns(price_wide, HOLD_DAYS)

    print("Loading probas and building portfolio groups...")
    probas = load_probas()
    groups = get_portfolio_groups(probas)

    print("\n" + "=" * 78)
    print("H48: SIGNAL DECAY CURVE — forward relative return vs VNINDEX over time")
    print(f"  Filter: VIX<{VIX_MAX} | min_proba={MIN_PROBA} | top-{TOP_N} | {START_YEAR}-2025")
    print("=" * 78)

    print(f"\n  {'Hold':>6}  {'top5_ret':>10}  {'Q5_ret':>9}  {'Q1_ret':>9}  "
          f"{'naive':>8}  {'edge(t5-naive)':>15}  {'still_worth_0.3%?':>18}")
    print("  " + "-" * 82)

    decay_rows = []
    for hold in HOLD_DAYS:
        fwd = fwd_returns[hold]
        merged = groups.merge(fwd, on=["time", "ticker"], how="inner")
        if merged.empty:
            continue

        top5_ret  = merged[merged["group"] == "top5"]["fwd_rel"].mean()
        q5_ret    = merged[merged["group"] == "Q5"]["fwd_rel"].mean()
        q1_ret    = merged[merged["group"] == "Q1"]["fwd_rel"].mean()
        naive_ret = merged["fwd_rel"].mean()
        edge      = top5_ret - naive_ret

        # Is the signal worth it? Edge must exceed round-trip cost
        # At hold=1: you pay COST_RT per stock per trade
        # The edge per stock must exceed COST_RT to be profitable
        worth_it = "YES" if edge > COST_RT else "NO "

        decay_rows.append({
            "hold": hold, "top5": top5_ret, "q5": q5_ret,
            "q1": q1_ret, "naive": naive_ret, "edge": edge,
        })

        print(f"  {hold:>5}d  {top5_ret*100:>+9.3f}%  {q5_ret*100:>+8.3f}%  "
              f"{q1_ret*100:>+8.3f}%  {naive_ret*100:>+7.3f}%  "
              f"{edge*100:>+14.3f}%  {worth_it:>18}")

    if decay_rows:
        # Find where edge crosses COST_RT threshold
        above = [r["hold"] for r in decay_rows if r["edge"] >= COST_RT]
        below = [r["hold"] for r in decay_rows if r["edge"] < COST_RT]
        print(f"\n  At 0.30% RT cost:")
        if above:
            print(f"    Signal profitable at holds: {above}")
        if below:
            print(f"    Signal NOT profitable at holds: {below}")

        if above:
            optimal_hold = max(above)
            print(f"\n  OPTIMAL HOLD PERIOD: {optimal_hold} days")
            print(f"  (Longest hold where edge still exceeds 0.30% round-trip cost)")

    # Per-year breakdown for 1-day hold
    print(f"\n  PER-YEAR DECAY at 1-day and 5-day hold:")
    print(f"  {'year':>6}  {'1d_edge':>9}  {'5d_edge':>9}  {'decay_ratio':>12}")
    print("  " + "-" * 42)

    if 1 in fwd_returns and 5 in fwd_returns:
        fwd1 = fwd_returns[1]
        fwd5 = fwd_returns[5]

        merged1 = groups.merge(fwd1, on=["time", "ticker"], how="inner")
        merged5 = groups.merge(fwd5, on=["time", "ticker"], how="inner")

        merged1["year"] = merged1["time"].dt.year
        merged5["year"] = merged5["time"].dt.year

        years_done = set()
        for year in range(START_YEAR, 2026):
            y1 = merged1[(merged1["year"] == year) & (merged1["group"] == "top5")]
            y5 = merged5[(merged5["year"] == year) & (merged5["group"] == "top5")]
            y_naive1 = merged1[merged1["year"] == year]
            y_naive5 = merged5[merged5["year"] == year]

            if len(y1) < 10 or len(y5) < 10:
                continue

            e1 = y1["fwd_rel"].mean() - y_naive1["fwd_rel"].mean()
            e5 = y5["fwd_rel"].mean() - y_naive5["fwd_rel"].mean()
            ratio = e5 / e1 if abs(e1) > 0.0001 else float("nan")

            print(f"  {year:>6}  {e1*100:>+8.3f}%  {e5*100:>+8.3f}%  {ratio:>11.2f}x")


if __name__ == "__main__":
    main()
