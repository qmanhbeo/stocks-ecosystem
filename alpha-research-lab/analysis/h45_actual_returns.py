"""
H45: Actual Monetary Return per Trade — FOUNDATION.

For each day when top-5 stocks are selected, compute N-day forward
relative return (vs VNINDEX) for N=1,2,3,5,10.

Separates:
  actual=1 → model was right (stock outperformed VNINDEX)
  actual=0 → model was wrong (stock underperformed VNINDEX)

Then computes expected gross return and true break-even RT cost.

This anchors the entire cost analysis in real dollar units.

Usage:
    conda run -n stocks python analysis/h45_actual_returns.py
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
HOLD_DAYS   = [1, 2, 3, 5, 10]

# Average daily turnover fraction from H44: ~3.45 new stocks / 5 = 69%
TURNOVER    = 0.69
COST_RT     = 0.003   # 0.30% round-trip


def load_prices():
    """Load all ticker OHLC + VNINDEX, compute N-day forward relative returns."""
    print("Loading VNINDEX prices...")
    vni = pd.read_parquet(VNI_FILE)[["time", "close"]].rename(columns={"close": "vni_close"})
    vni["time"] = pd.to_datetime(vni["time"])
    vni = vni.sort_values("time").reset_index(drop=True)

    # Build a sorted time index for VNINDEX
    vni_times = vni["time"].values
    vni_close = vni["vni_close"].values

    # Index lookup: date → row position in VNINDEX
    vni_idx = {t: i for i, t in enumerate(vni_times)}

    print("Loading all stock prices...")
    stock_files = sorted(STOCK_DIR.glob("gia_lich_su_*_1D.parquet"))
    stock_files = [f for f in stock_files if "VNINDEX" not in f.name]

    records = []
    for sf in stock_files:
        ticker = sf.name.replace("gia_lich_su_", "").replace("_1D.parquet", "")
        df = pd.read_parquet(sf)[["time", "close"]].copy()
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time").reset_index(drop=True)
        df["ticker"] = ticker

        # Compute N-day forward relative return vs VNINDEX for each holding period
        close_arr = df["close"].values
        times_arr = df["time"].values
        n_rows = len(df)

        for hold in HOLD_DAYS:
            fwd_rels = []
            for i in range(n_rows):
                t0 = times_arr[i]
                # Find index in VNINDEX
                vi0 = vni_idx.get(t0, None)
                if vi0 is None or (i + hold) >= n_rows:
                    fwd_rels.append(np.nan)
                    continue
                # Forward price for stock (hold days later in stock's own time series)
                p0 = close_arr[i]
                ph = close_arr[i + hold]
                stock_ret = ph / p0 - 1.0

                # VNINDEX forward — find position hold days later in VNI time series
                # Try to find the same "hold" trading days forward in VNI
                vh_idx = vi0 + hold
                if vh_idx >= len(vni_close):
                    fwd_rels.append(np.nan)
                    continue
                vni_ret = vni_close[vh_idx] / vni_close[vi0] - 1.0
                fwd_rels.append(stock_ret - vni_ret)

            col = f"fwd_rel_{hold}d"
            df[col] = fwd_rels

        records.append(df)

    prices = pd.concat(records, ignore_index=True)
    print(f"  Price data: {len(prices):,} rows, {prices['ticker'].nunique()} tickers")
    return prices


def load_probas():
    df = pd.read_parquet(ALL_PROBAS)
    df["time"] = pd.to_datetime(df["time"])
    vix = pd.read_parquet(VIX_PATH)[["time", "close"]].rename(columns={"close": "vix"})
    vix["time"] = pd.to_datetime(vix["time"])
    df = df.merge(vix, on="time", how="left")
    df["vix"] = df["vix"].ffill()
    return df


def analyze_returns(probas: pd.DataFrame, prices: pd.DataFrame):
    """Merge probas with price returns, split by actual=1/0, report per hold period."""

    # Merge probas with forward returns
    merged = probas.merge(
        prices[["time", "ticker"] + [f"fwd_rel_{h}d" for h in HOLD_DAYS]],
        on=["time", "ticker"],
        how="left",
    )

    print("\n" + "=" * 78)
    print("H45: ACTUAL MONETARY RETURN PER TRADE")
    print(f"  Filter: VIX<{VIX_MAX} | min_proba={MIN_PROBA} | top-{TOP_N} | years {START_YEAR}-2025")
    print("=" * 78)

    # Filter to years 2015-2025 only
    merged = merged[(merged["year"] >= START_YEAR) & (merged["year"] <= 2025)]

    # Apply VIX filter
    merged = merged[merged["vix"] <= VIX_MAX]

    # For each day, pick top-N stocks and apply min_proba filter
    top_rows = []
    for date, day in merged.groupby("time"):
        top = day.nlargest(TOP_N, "xs_proba")
        if top["xs_proba"].min() < MIN_PROBA:
            continue
        top_rows.append(top)

    if not top_rows:
        print("No valid trading days found.")
        return

    top_df = pd.concat(top_rows, ignore_index=True)
    n_days = top_df["time"].nunique()
    n_stocks = len(top_df)
    p_correct = top_df["actual"].mean()

    print(f"\n  Total trading days  : {n_days}")
    print(f"  Total stock-days    : {n_stocks}")
    print(f"  P(actual=1)         : {p_correct:.3f}  (model hit rate in top-{TOP_N})")
    print(f"  P(actual=0)         : {1-p_correct:.3f}  (model miss rate)")

    print(f"\n  {'Hold':>6}  {'avg_win':>9}  {'avg_loss':>10}  {'gross_ret':>10}  "
          f"{'BE_RT_cost':>11}  {'@0.3%RT':>8}")
    print("  " + "-" * 66)

    results = []
    for hold in HOLD_DAYS:
        col = f"fwd_rel_{hold}d"
        sub = top_df[top_df[col].notna()]
        if len(sub) < 50:
            continue

        wins  = sub[sub["actual"] == 1][col]
        loss  = sub[sub["actual"] == 0][col]

        avg_win  = wins.mean() if len(wins) > 0 else 0.0
        avg_loss = loss.mean() if len(loss) > 0 else 0.0
        gross    = p_correct * avg_win + (1 - p_correct) * avg_loss

        # Break-even round-trip cost: gross_return / 1 trade = just gross_return
        # (If we pay BE_cost per round trip, we break even)
        be_cost  = gross  # break-even cost per stock per trade

        # Is it profitable at 0.30% RT?
        profit_03 = "YES" if gross > COST_RT else "NO "

        print(f"  {hold:>5}d  {avg_win*100:>+8.3f}%  {avg_loss*100:>+9.3f}%  "
              f"{gross*100:>+9.3f}%  {be_cost*100:>+10.3f}%  {profit_03:>8}")
        results.append({"hold": hold, "gross": gross, "avg_win": avg_win, "avg_loss": avg_loss})

    print(f"\n  Note: At 0.30% RT cost, trade is profitable if gross_ret > 0.30%")

    # Annualized view
    print(f"\n  ANNUALIZED RETURN ESTIMATE (equal-weight top-{TOP_N}, daily rebalancing)")
    print(f"  Assumptions: {n_days/10:.0f} trading days/yr, {TURNOVER*100:.0f}% daily turnover")
    print(f"\n  {'Hold':>6}  {'gross/trade':>12}  {'trades/yr':>10}  {'gross_ann':>10}  "
          f"{'cost_ann':>10}  {'net_ann':>10}")
    print("  " + "-" * 68)

    for r in results:
        hold = r["hold"]
        gross = r["gross"]
        # With daily selection and holding for `hold` days, actual rebalancing is effectively
        # every `hold` days if strict, but daily in the rolling sense.
        # trades_per_yr per stock = (250 / hold) * TURNOVER  [fraction that actually turn over]
        trades_per_yr = (250 / hold) * TURNOVER
        gross_ann = gross * trades_per_yr
        cost_ann  = COST_RT * trades_per_yr
        net_ann   = gross_ann - cost_ann
        print(f"  {hold:>5}d  {gross*100:>+11.3f}%  {trades_per_yr:>10.1f}  "
              f"{gross_ann*100:>+9.2f}%  {cost_ann*100:>+9.2f}%  {net_ann*100:>+9.2f}%")

    # Per-year breakdown for 1d hold
    print(f"\n  PER-YEAR GROSS RETURN (1-day holding)")
    print(f"  {'year':>6}  {'n_days':>7}  {'P(win)':>7}  {'avg_win':>9}  "
          f"{'avg_loss':>10}  {'gross':>8}")
    print("  " + "-" * 58)
    for year in range(START_YEAR, 2026):
        ysub = top_df[top_df["time"].dt.year == year]
        if len(ysub) < 10 or "fwd_rel_1d" not in ysub.columns:
            continue
        ys = ysub[ysub["fwd_rel_1d"].notna()]
        if len(ys) < 5:
            continue
        pw = ys["actual"].mean()
        aw = ys[ys["actual"] == 1]["fwd_rel_1d"].mean() if pw > 0 else 0.0
        al = ys[ys["actual"] == 0]["fwd_rel_1d"].mean() if pw < 1 else 0.0
        g  = pw * aw + (1 - pw) * al
        print(f"  {year:>6}  {ys['time'].nunique():>7}  {pw:>7.3f}  "
              f"{aw*100:>+8.3f}%  {al*100:>+9.3f}%  {g*100:>+7.3f}%")


if __name__ == "__main__":
    prices = load_prices()
    probas = load_probas()
    analyze_returns(probas, prices)
