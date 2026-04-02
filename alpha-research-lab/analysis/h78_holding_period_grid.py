"""
H78: Holding period grid for the H54 portfolio.

Original H78 used E=0 close-to-close returns. This script now supports:

- entry_delay=0: legacy close-to-close simulation (not executable)
- entry_delay=1: executable T+1-open simulation

The signal is still generated at day T close from saved probabilities. For entry_delay=1,
the first realized holding-day return is open(T+1) -> open(T+2), which is the correct
tradable implementation under next-open execution.

Usage:
    PYTHONIOENCODING=utf-8 conda run -n stocks python analysis/h78_holding_period_grid.py \
        --probas data/features/xs_barrier_all_probas_hose_full.parquet --entry-delay 1 --no-vix-filter
"""
import argparse
import sys
from pathlib import Path
from path_utils import data_path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.run_summary import write_run_summary


ALL_PROBAS = data_path("features/xs_barrier_all_probas_hose_full.parquet")
VIX_PATH = data_path("fx-commodities/fx_commodities_vix_1D.parquet")
STOCK_DIR = data_path("stock")
VNI_FILE = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"

TOP_N = 5
MIN_PROBA = 0.55
VIX_MIN = 0.0
VIX_MAX = 999.0
START_YEAR = 2015
END_YEAR = 2025
HOLD_PERIODS = [1, 2, 3, 5]
COST_GRID = [0.0010, 0.0015, 0.0020, 0.0025, 0.0030, 0.0040]
K_BAND = 15


def load_probas(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df["time"] = pd.to_datetime(df["time"])

    vix = pd.read_parquet(VIX_PATH)[["time", "close"]].rename(columns={"close": "vix"})
    vix["time"] = pd.to_datetime(vix["time"])

    df = df.merge(vix, on="time", how="left")
    df["vix"] = df["vix"].ffill()
    return df.sort_values("time")


def load_prices() -> dict:
    """Return wide open/close price tables keyed by basis."""
    print("Loading prices...")
    vni = pd.read_parquet(VNI_FILE)[["time", "open", "close"]].copy()
    vni["time"] = pd.to_datetime(vni["time"])
    vni = vni.sort_values("time").drop_duplicates("time")

    stock_files = sorted(STOCK_DIR.glob("gia_lich_su_*_1D.parquet"))
    stock_files = [f for f in stock_files if "VNINDEX" not in f.name and "VN30" not in f.name]

    open_cols = {}
    close_cols = {}
    for sf in stock_files:
        ticker = sf.name.replace("gia_lich_su_", "").replace("_1D.parquet", "")
        raw = pd.read_parquet(sf)[["time", "open", "close"]].copy()
        raw["time"] = pd.to_datetime(raw["time"])
        raw = raw.sort_values("time").drop_duplicates("time")
        indexed = raw.set_index("time")
        open_cols[ticker] = indexed["open"]
        close_cols[ticker] = indexed["close"]

    open_wide = pd.DataFrame(open_cols).sort_index()
    close_wide = pd.DataFrame(close_cols).sort_index()
    open_wide["VNINDEX"] = vni.set_index("time")["open"]
    close_wide["VNINDEX"] = vni.set_index("time")["close"]
    print(f"  {len(open_wide)} dates x {open_wide.shape[1]} tickers")
    return {"open": open_wide, "close": close_wide}


def compute_1d_rel_returns(price_wide: pd.DataFrame, entry_delay: int) -> pd.DataFrame:
    """
    Compute 1-day forward relative returns keyed by signal date.

    entry_delay=0:
      return at time T = close(T+1)/close(T) - 1 minus VNINDEX same period

    entry_delay=1:
      return at time T = open(T+2)/open(T+1) - 1 minus VNINDEX same period
      This corresponds to signal at T close, enter at T+1 open, first holding day T+1 -> T+2.
    """
    basis = "close" if entry_delay == 0 else "open"
    print(f"Computing 1-day forward relative returns (basis={basis}, entry_delay={entry_delay})...")

    vni = price_wide["VNINDEX"]
    vni_fwd = vni.shift(-(entry_delay + 1)) / vni.shift(-entry_delay) - 1.0

    records = []
    for ticker in price_wide.columns:
        if ticker == "VNINDEX":
            continue
        px = price_wide[ticker]
        stock_fwd = px.shift(-(entry_delay + 1)) / px.shift(-entry_delay) - 1.0
        rel = (stock_fwd - vni_fwd).dropna()
        for dt, val in rel.items():
            if pd.isna(val) or abs(val) > 0.5:
                continue
            records.append({"time": dt, "ticker": ticker, "rel_1d": float(val)})

    return pd.DataFrame(records)


def simulate_portfolio(
    probas: pd.DataFrame,
    rel_returns: pd.DataFrame,
    hold: int,
    use_k_band: bool = False,
) -> dict:
    """
    Simulate an H-day holding portfolio on signal dates.

    The portfolio chosen on signal date T earns the rel_1d associated with that signal date.
    With entry_delay=1 that rel_1d is the first executable holding-day return from T+1 open to T+2 open.
    """
    ret_lookup = rel_returns.set_index(["time", "ticker"])["rel_1d"]

    dates = sorted(
        probas[(probas["year"] >= START_YEAR) & (probas["year"] <= END_YEAR)]["time"].unique()
    )

    proba_by_date = {}
    for dt, grp in probas[probas["time"].isin(dates)].groupby("time"):
        vix_val = grp["vix"].iloc[0]
        if not (VIX_MIN <= vix_val <= VIX_MAX):
            continue
        proba_by_date[dt] = grp.set_index("ticker")["xs_proba"]

    results_by_year = {}
    portfolio = set()
    days_held = 0

    for dt in dates:
        if dt not in proba_by_date:
            portfolio = set()
            days_held = 0
            continue

        proba_series = proba_by_date[dt]
        year = dt.year
        do_rebalance = (days_held == 0) or (days_held >= hold)

        if use_k_band and portfolio:
            ranked = proba_series.rank(ascending=False)
            worst_rank = max((ranked.get(t, 9999) for t in portfolio), default=0)
            if worst_rank > K_BAND:
                do_rebalance = True

        if do_rebalance:
            sorted_s = proba_series.sort_values(ascending=False)
            candidates = sorted_s[sorted_s >= MIN_PROBA]
            if len(candidates) < TOP_N:
                portfolio = set()
                days_held = 0
                continue

            new_portfolio = set(sorted_s.head(TOP_N).index)
            exits = portfolio - new_portfolio
            entries = new_portfolio - portfolio
            n_trades = len(exits) + len(entries)
            portfolio = new_portfolio
            days_held = 1
        else:
            n_trades = 0
            days_held += 1

        if not portfolio:
            continue

        gross_vals = []
        for ticker in portfolio:
            val = ret_lookup.get((dt, ticker), np.nan)
            if not np.isnan(val):
                gross_vals.append(val)

        if not gross_vals:
            continue

        gross_day = float(np.mean(gross_vals))
        bucket = results_by_year.setdefault(
            year,
            {"gross_sum": 0.0, "n_days": 0, "n_trades": 0, "n_rebalances": 0},
        )
        bucket["gross_sum"] += gross_day
        bucket["n_days"] += 1
        bucket["n_trades"] += n_trades
        if do_rebalance and n_trades > 0:
            bucket["n_rebalances"] += 1

    return results_by_year


def summarize(results_by_year: dict, hold: int, label: str):
    years = sorted(results_by_year)
    if not years:
        print(f"  No results for hold={hold}")
        return None

    print(f"\n{'=' * 70}")
    print(f"H78 - hold={hold}d | {label}")
    print(f"  {'year':>5}  {'gross/day':>10}  {'trades/yr':>10}  {'turnover%':>10}")
    print("  " + "-" * 42)

    agg_gross = []
    agg_trades = []
    agg_days = []

    for year in years:
        r = results_by_year[year]
        if r["n_days"] == 0:
            continue
        gross_per_day = r["gross_sum"] / r["n_days"]
        trades_per_yr = r["n_trades"]
        turnover_pct = r["n_trades"] / max(r["n_days"] * TOP_N, 1) * 100
        print(f"  {year:>5}  {gross_per_day*100:>+9.3f}%  {trades_per_yr:>10.0f}  {turnover_pct:>9.1f}%")
        agg_gross.append(gross_per_day)
        agg_trades.append(trades_per_yr)
        agg_days.append(r["n_days"])

    if not agg_gross:
        return None

    avg_gross_day = float(np.mean(agg_gross))
    avg_days_yr = float(np.mean(agg_days))
    avg_trades_yr = float(np.mean(agg_trades))
    avg_turnover = avg_trades_yr / max(avg_days_yr * TOP_N, 1) * 100
    avg_gross_yr = avg_gross_day * avg_days_yr

    print(f"\n  Avg gross/day   : {avg_gross_day*100:+.3f}%")
    print(f"  Avg days/yr     : {avg_days_yr:.0f}")
    print(f"  Avg trades/yr   : {avg_trades_yr:.0f}")
    print(f"  Avg turnover/day: {avg_turnover:.1f}% of portfolio")
    print(f"  Avg gross/yr    : {avg_gross_yr*100:+.2f}%")

    print(f"\n  Net annual return by RT cost:")
    print(f"  {'RT cost':>9}  {'net/yr':>9}  {'breakeven?':>12}")
    print("  " + "-" * 34)
    for cost_rt in COST_GRID:
        total_cost_yr = avg_trades_yr * cost_rt / (2 * TOP_N)
        net_yr = avg_gross_yr - total_cost_yr
        flag = " PROFIT" if net_yr > 0 else " LOSS"
        print(f"  {cost_rt*100:>8.2f}%  {net_yr*100:>+8.2f}%  {flag}")

    return {
        "avg_gross_day": avg_gross_day,
        "avg_days_yr": avg_days_yr,
        "avg_trades_yr": avg_trades_yr,
        "avg_turnover": avg_turnover,
        "avg_gross_yr": avg_gross_yr,
        "net_yr_at_0_20": avg_gross_yr - avg_trades_yr * 0.002 / (2 * TOP_N),
        "net_yr_at_0_30": avg_gross_yr - avg_trades_yr * 0.003 / (2 * TOP_N),
        "n_years": len(agg_gross),
    }


def print_comparison(all_summaries: dict):
    print(f"\n{'=' * 70}")
    print("COMPARISON SUMMARY")
    print(f"  {'variant':>15}  {'gross/day':>10}  {'trades/yr':>10}  {'turnover%':>10}  {'net@0.20%':>10}  {'net@0.30%':>10}")
    print("  " + "-" * 65)
    for key, s in all_summaries.items():
        print(
            f"  {key:>15}  {s['avg_gross_day']*100:>+9.3f}%  {s['avg_trades_yr']:>10.0f}  "
            f"{s['avg_turnover']:>9.1f}%  {s['net_yr_at_0_20']*100:>+9.2f}%  {s['net_yr_at_0_30']*100:>+9.2f}%"
        )

    print(f"\n  Cost formula: trades_yr * RT_cost / (2 * TOP_N)")
    print("  Gross: sum of daily portfolio relative excess returns vs VNINDEX")


def main():
    global TOP_N, MIN_PROBA, VIX_MIN, VIX_MAX
    parser = argparse.ArgumentParser(description="H78: Holding period grid")
    parser.add_argument("--probas", type=str, default=str(ALL_PROBAS))
    parser.add_argument("--no-vix-filter", action="store_true")
    parser.add_argument("--top-n", type=int, default=TOP_N)
    parser.add_argument("--min-proba", type=float, default=MIN_PROBA)
    parser.add_argument(
        "--entry-delay",
        type=int,
        default=0,
        help="Execution lag in trading days. 0=legacy close-to-close H78, 1=executable T+1-open.",
    )
    args = parser.parse_args()

    if args.no_vix_filter:
        VIX_MIN, VIX_MAX = 0.0, 999.0
        print("[H78] VIX filter DISABLED")
    TOP_N = args.top_n
    MIN_PROBA = args.min_proba

    print(f"Loading probas from {args.probas}...")
    probas = load_probas(Path(args.probas))
    print(
        f"  {len(probas):,} rows | {probas['ticker'].nunique()} tickers | "
        f"years {probas['year'].min()}-{probas['year'].max()}"
    )

    price_tables = load_prices()
    price_basis = "close" if args.entry_delay == 0 else "open"
    rel_returns = compute_1d_rel_returns(price_tables[price_basis], entry_delay=args.entry_delay)
    print(f"  {len(rel_returns):,} (date, ticker) daily return records")

    all_summaries = {}

    for hold in HOLD_PERIODS:
        print(f"\nSimulating hold={hold}d (standard)...")
        results = simulate_portfolio(probas, rel_returns, hold, use_k_band=False)
        label = (
            f"standard fixed-hold, TOP_N={TOP_N}, MIN_PROBA={MIN_PROBA}, "
            f"entry_delay={args.entry_delay}, basis={price_basis}"
        )
        summary = summarize(results, hold, label)
        if summary:
            all_summaries[f"h{hold}_std"] = summary

    print(f"\nSimulating hold=3d + K-band (stay if still in top-{K_BAND})...")
    results_kb = simulate_portfolio(probas, rel_returns, 3, use_k_band=True)
    summary_kb = summarize(
        results_kb,
        3,
        f"K-band stay-in (K={K_BAND}), TOP_N={TOP_N}, entry_delay={args.entry_delay}, basis={price_basis}",
    )
    if summary_kb:
        all_summaries["h3_kband"] = summary_kb

    print_comparison(all_summaries)

    best_net30 = max(
        all_summaries.items(),
        key=lambda kv: kv[1]["net_yr_at_0_30"],
        default=None,
    )
    ts = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    summary_path = write_run_summary(
        ts=ts,
        mode="holding_period",
        name=f"h78_hold_grid_e{args.entry_delay}_{Path(args.probas).stem}",
        summary={
            "best_variant_by_net_0_30": best_net30[0] if best_net30 else None,
            "best_net_yr_at_0_30": round(best_net30[1]["net_yr_at_0_30"], 4) if best_net30 else None,
            "variants": {
                key: {
                    "avg_gross_day": round(val["avg_gross_day"], 6),
                    "avg_gross_yr": round(val["avg_gross_yr"], 4),
                    "avg_trades_yr": round(val["avg_trades_yr"], 2),
                    "avg_turnover": round(val["avg_turnover"], 4),
                    "net_yr_at_0_20": round(val["net_yr_at_0_20"], 4),
                    "net_yr_at_0_30": round(val["net_yr_at_0_30"], 4),
                    "n_years": val["n_years"],
                }
                for key, val in all_summaries.items()
            },
        },
        artifacts={"probas": str(Path(args.probas))},
        metadata={
            "entry_delay": args.entry_delay,
            "price_basis": price_basis,
            "top_n": TOP_N,
            "min_proba": MIN_PROBA,
            "vix_min": VIX_MIN,
            "vix_max": VIX_MAX,
        },
    )
    print(f"Run summary saved to {summary_path}")


if __name__ == "__main__":
    main()
