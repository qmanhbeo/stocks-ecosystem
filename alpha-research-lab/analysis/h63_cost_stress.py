"""
H63: Cost stress test for executable E=1 returns.

Purpose:
- quantify the round-trip transaction cost where H54 breaks even
- compare daily H=1 against weekly H=5 as a higher-cost fallback

This script uses actual open-to-open excess returns with T+1-open entry:
signal at T close -> enter at T+1 open -> exit at T+1+H open.

Usage:
    conda run -n stocks python analysis/h63_cost_stress.py --no-vix-filter
"""
import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.run_summary import write_run_summary

warnings.filterwarnings("ignore", category=RuntimeWarning)


DEFAULT_PROBAS = Path("data/features/xs_barrier_all_probas_hose_full.parquet")
VIX_PATH = Path("data/fx-commodities/fx_commodities_vix_1D.parquet")
STOCK_DIR = Path("data/stock")
VNI_FILE = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"

START_YEAR = 2015
END_YEAR = 2025
TOP_N = 5
MIN_PROBA = 0.55
RANK_COL = "xs_proba"
MIN_PROBA_COL = "xs_proba"
VIX_MIN = 15.0
VIX_MAX = 30.0

COST_GRID = [
    0.0000, 0.0010, 0.0015, 0.0020, 0.0030, 0.0040,
    0.0050, 0.0070, 0.0100, 0.0150, 0.0200,
]


def load_vni() -> pd.DataFrame:
    df = pd.read_parquet(VNI_FILE, columns=["time", "open"])
    df["time"] = pd.to_datetime(df["time"])
    return df.sort_values("time").reset_index(drop=True)


def load_prices_e1(tickers: list[str], vni: pd.DataFrame, hold_days: tuple[int, ...] = (1, 5)) -> pd.DataFrame:
    """Compute E=1 forward excess returns keyed by signal date."""
    vni_open = vni["open"].values
    vni_times = vni["time"].values
    vni_idx = {t: i for i, t in enumerate(vni_times)}
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
        open_arr = df["open"].values.astype(float)
        times_arr = df["time"].values
        n = len(df)

        for hold in hold_days:
            col = f"fwd_h{hold}"
            arr = np.full(n, np.nan)
            for i in range(n):
                vi0 = vni_idx.get(times_arr[i])
                if vi0 is None:
                    continue
                stock_exit = i + 1 + hold
                vni_exit = vi0 + 1 + hold
                if stock_exit >= n or vni_exit >= len(vni_open):
                    continue
                p_in = open_arr[i + 1]
                p_out = open_arr[stock_exit]
                v_in = vni_open[vi0 + 1]
                v_out = vni_open[vni_exit]
                if p_in <= 0 or v_in <= 0:
                    continue
                arr[i] = (p_out / p_in - 1.0) - (v_out / v_in - 1.0)
            df[col] = arr

        records.append(df[["time", "ticker"] + [f"fwd_h{h}" for h in hold_days]])

    return pd.concat(records, ignore_index=True) if records else pd.DataFrame()


def build_portfolio(merged: pd.DataFrame, hold: int, weekly: bool = False) -> dict[int, list[float]]:
    """
    Collect per-signal realized portfolio excess returns.

    Returns:
      {year: [gross_excess_return_per_signal, ...]}
    """
    col = f"fwd_h{hold}"
    per_year: dict[int, list[float]] = {}

    for year, grp in merged.groupby(merged["time"].dt.year):
        if year < START_YEAR or year > END_YEAR:
            continue
        signal_returns = []
        dates = sorted(grp["time"].unique())
        last_signal_idx = -999
        for di, date in enumerate(dates):
            day = grp[grp["time"] == date]
            vix_val = day["vix"].iloc[0]
            if not (VIX_MIN <= vix_val <= VIX_MAX):
                continue
            if weekly and di - last_signal_idx < 5:
                continue

            top = day.nlargest(TOP_N, RANK_COL)
            if len(top) < TOP_N or top[MIN_PROBA_COL].min() < MIN_PROBA:
                continue

            realized = top[col].dropna().values
            if len(realized) == 0:
                continue

            signal_returns.append(float(realized.mean()))
            last_signal_idx = di

        if signal_returns:
            per_year[int(year)] = signal_returns

    return per_year


def summarize_costs(per_year: dict[int, list[float]], label: str) -> dict | None:
    """Sweep RT cost grid and return a machine-readable summary."""
    print(f"\n{'=' * 86}")
    print(f"COST STRESS TEST - {label}")
    print(f"{'=' * 86}")

    all_trades = [ret for yearly in per_year.values() for ret in yearly]
    if not all_trades:
        print("  No trades.")
        return None

    avg_gross_trade = float(np.mean(all_trades))
    trade_counts = {year: len(vals) for year, vals in per_year.items()}
    gross_annual = {year: float(np.sum(vals)) for year, vals in per_year.items()}
    avg_trades_yr = float(np.mean(list(trade_counts.values())))
    avg_gross_annual = float(np.mean(list(gross_annual.values())))
    exact_breakeven_rt = avg_gross_annual / avg_trades_yr if avg_trades_yr > 0 else None

    print(
        f"\n  {'RT_cost':>9}  {'gross/trade':>12}  {'net/trade':>11}  {'trades/yr':>10}  "
        f"{'ann_net':>10}  {'sharpe_ann':>11}  {'pos_yrs':>8}"
    )
    print("  " + "-" * 86)

    rows = []
    discrete_breakeven = None
    for cost in COST_GRID:
        net_trade = avg_gross_trade - cost
        ann_nets = []
        for year, vals in per_year.items():
            ann_nets.append((float(np.mean(vals)) - cost) * len(vals))
        avg_ann_net = float(np.mean(ann_nets))
        sharpe_ann = avg_ann_net / (float(np.std(ann_nets)) + 1e-9)
        pos_years = int(sum(1 for val in ann_nets if val > 0))
        if discrete_breakeven is None and avg_ann_net < 0:
            discrete_breakeven = cost

        print(
            f"  {cost*100:>8.2f}%  {avg_gross_trade*100:>+11.3f}%  {net_trade*100:>+10.3f}%  "
            f"{avg_trades_yr:>10.1f}  {avg_ann_net*100:>+9.2f}%  {sharpe_ann:>10.2f}  {pos_years}/{len(per_year)}"
        )
        rows.append(
            {
                "rt_cost": cost,
                "avg_gross_trade": avg_gross_trade,
                "net_trade": net_trade,
                "avg_trades_yr": avg_trades_yr,
                "avg_ann_net": avg_ann_net,
                "sharpe_ann": float(sharpe_ann),
                "positive_years": pos_years,
                "total_years": len(per_year),
            }
        )

    print(
        f"\n  Exact breakeven RT cost: {exact_breakeven_rt*100:.2f}%"
        if exact_breakeven_rt is not None
        else "\n  Exact breakeven RT cost: N/A"
    )
    if discrete_breakeven is not None:
        print(f"  First negative point on sweep: {discrete_breakeven*100:.2f}%")
    else:
        print(f"  Edge stays positive through highest tested cost: {COST_GRID[-1]*100:.2f}%")

    return {
        "avg_gross_trade": round(avg_gross_trade, 6),
        "avg_trades_yr": round(avg_trades_yr, 2),
        "avg_gross_annual": round(avg_gross_annual, 4),
        "exact_breakeven_rt": round(exact_breakeven_rt, 6) if exact_breakeven_rt is not None else None,
        "first_negative_rt_on_grid": round(discrete_breakeven, 6) if discrete_breakeven is not None else None,
        "rows": rows,
    }


def main():
    global VIX_MIN, VIX_MAX, RANK_COL, MIN_PROBA_COL

    parser = argparse.ArgumentParser()
    parser.add_argument("--probas", type=str, default=str(DEFAULT_PROBAS))
    parser.add_argument("--no-vix-filter", action="store_true")
    parser.add_argument("--rank-col", type=str, default=RANK_COL)
    parser.add_argument("--min-proba-col", type=str, default=MIN_PROBA_COL)
    args = parser.parse_args()

    if args.no_vix_filter:
        VIX_MIN, VIX_MAX = 0.0, 999.0
        print("[H63] VIX filter DISABLED")
    RANK_COL = args.rank_col
    MIN_PROBA_COL = args.min_proba_col
    print(f"[H63] RANK_COL={RANK_COL} | MIN_PROBA_COL={MIN_PROBA_COL}")

    print("\nH63: COST STRESS TEST")
    print(f"Loading probas: {args.probas}")
    probas = pd.read_parquet(args.probas)
    probas["time"] = pd.to_datetime(probas["time"])
    tickers = probas["ticker"].unique().tolist()
    print(f"  {len(probas):,} rows | {len(tickers)} tickers")

    print("Loading VIX...")
    vix = pd.read_parquet(VIX_PATH)[["time", "close"]].rename(columns={"close": "vix"})
    vix["time"] = pd.to_datetime(vix["time"])
    probas = probas.merge(vix, on="time", how="left")
    probas["vix"] = probas["vix"].ffill()

    print("Loading prices (E=1, H=1 and H=5)...")
    vni = load_vni()
    prices = load_prices_e1(tickers, vni, hold_days=(1, 5))
    print(f"  {len(prices):,} rows")

    merged = probas.merge(prices, on=["time", "ticker"], how="left")
    merged = merged[(merged["time"].dt.year >= START_YEAR) & (merged["time"].dt.year <= END_YEAR)]

    daily_h1 = build_portfolio(merged, hold=1, weekly=False)
    weekly_h5 = build_portfolio(merged, hold=5, weekly=True)

    daily_summary = summarize_costs(daily_h1, "Strategy A: Daily H=1")
    weekly_summary = summarize_costs(weekly_h5, "Strategy C: Weekly H=5")

    ts = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    summary_path = write_run_summary(
        ts=ts,
        mode="cost_stress",
        name=f"h63_cost_stress_{Path(args.probas).stem}",
        summary={
            "daily_h1": daily_summary,
            "weekly_h5": weekly_summary,
        },
        artifacts={"probas": str(Path(args.probas))},
        metadata={
            "top_n": TOP_N,
            "min_proba": MIN_PROBA,
            "rank_col": RANK_COL,
            "min_proba_col": MIN_PROBA_COL,
            "vix_min": VIX_MIN,
            "vix_max": VIX_MAX,
            "start_year": START_YEAR,
            "end_year": END_YEAR,
        },
    )
    print(f"\nRun summary saved to {summary_path}")


if __name__ == "__main__":
    main()
