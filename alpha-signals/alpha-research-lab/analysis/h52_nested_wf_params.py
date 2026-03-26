"""
H52: Nested walk-forward parameter search (Option A).

For each test year T:
  - Meta-validation window: years T-3 to T-1 (last 3 years before test)
  - Grid search over: VIX_MAX, MIN_PROBA, TOP_N
  - Pick best Sharpe on meta-validation (min 5 trades/year avg required)
  - Apply winning parameters to test year T

Eliminates all three contaminated parameters (VIX_MAX, MIN_PROBA, TOP_N).
Most rigorous approach: what would a walk-forward-honest system choose?

Baseline: H43 (contaminated) +13.75% avg edge, Sharpe 4.58, 11/11 years.
"""
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from itertools import product

ALL_PROBAS  = Path("data/features/xs_barrier_all_probas.parquet")
VIX_PATH    = Path("data/fx-commodities/fx_commodities_vix_1D.parquet")
START_YEAR  = 2015
META_WINDOW = 3     # years used for parameter selection
MIN_TRADES_PER_YEAR = 5   # skip param combos with too few trades (avoid pathological Sharpe)

VIX_MAX_GRID   = [25.0, 28.0, 30.0, 32.0, 35.0]
MIN_PROBA_GRID = [0.50, 0.52, 0.55, 0.58]
TOP_N_GRID     = [3, 5, 7]
VIX_MIN        = 15.0
VIX_MIN_DEFAULT = 15.0


def load_data(probas_path: Path = ALL_PROBAS) -> pd.DataFrame:
    df = pd.read_parquet(probas_path)
    df["time"] = pd.to_datetime(df["time"])
    vix = pd.read_parquet(VIX_PATH)[["time", "close"]].rename(columns={"close": "vix"})
    vix["time"] = pd.to_datetime(vix["time"])
    df = df.merge(vix, on="time", how="left")
    df["vix"] = df["vix"].ffill()
    return df


def compute_year_edge(grp: pd.DataFrame, top_n: int, min_proba: float,
                      vix_min: float, vix_max: float):
    """Compute edge for a single year's data. Returns (edge, n_trades) or (nan, 0)."""
    naive_rate = grp["actual"].mean()
    day_correct = []
    for date, day in grp.groupby("time"):
        vix_val = day["vix"].iloc[0]
        if not (vix_min <= vix_val <= vix_max):
            continue
        top = day.nlargest(top_n, "xs_proba")
        if top["xs_proba"].min() >= min_proba:
            day_correct.extend(top["actual"].tolist())
    if len(day_correct) < top_n:
        return float("nan"), 0
    edge = np.mean(day_correct) - naive_rate
    return edge, len(day_correct) // top_n


def compute_meta_sharpe(df_meta: pd.DataFrame, top_n: int, min_proba: float,
                        vix_min: float, vix_max: float, min_trades: int = MIN_TRADES_PER_YEAR):
    """
    Compute Sharpe over meta-validation years.
    Returns (sharpe, avg_trades) or (nan, 0) if insufficient data or too few trades.
    """
    per_year = []
    for year, grp in df_meta.groupby("year"):
        edge, n_trades = compute_year_edge(grp, top_n, min_proba, vix_min, vix_max)
        if not np.isnan(edge):
            per_year.append({"edge": edge, "n_trades": n_trades})

    if len(per_year) < 2:
        return float("nan"), 0
    avg_trades = np.mean([r["n_trades"] for r in per_year])
    if avg_trades < min_trades:
        return float("nan"), 0   # too sparse — pathological Sharpe
    edges = [r["edge"] for r in per_year]
    std = np.std(edges)
    if std == 0:
        return float("nan"), avg_trades
    return np.mean(edges) / std, avg_trades


def run_nested_wf(df: pd.DataFrame, meta_window: int = META_WINDOW,
                  fix_vix_max: bool = False):
    """
    fix_vix_max=True: VIX_MAX is not searched — fixed at 999 (no external VIX filter).
    Use when probas already have VIX embedded as a feature (H50 probas).
    Only MIN_PROBA and TOP_N are searched.
    """
    vix_max_grid = [999.0] if fix_vix_max else VIX_MAX_GRID
    vix_label = "disabled (VIX in model)" if fix_vix_max else str(VIX_MAX_GRID)

    print("\n" + "=" * 70)
    print(f"NESTED WALK-FORWARD PARAMETER SEARCH")
    print(f"Meta-validation: last {meta_window} years before test year")
    print(f"Min trades/year (meta): {MIN_TRADES_PER_YEAR}")
    print(f"Grid: VIX_MAX={vix_label}, MIN_PROBA={MIN_PROBA_GRID}, TOP_N={TOP_N_GRID}")
    print(f"  {'year':>5}  {'chosen_params':>28}  {'meta_sh':>8}  {'test_edge':>10}  {'trades':>7}")
    print("  " + "-" * 70)

    all_years = sorted(df["year"].unique())
    test_years = [y for y in all_years if y >= START_YEAR]

    per_year_results = []
    for test_year in test_years:
        meta_years = [y for y in all_years if test_year - meta_window <= y < test_year]
        if len(meta_years) < 2:
            print(f"  {test_year:>5}  {'insufficient meta data (<2 yrs)':>28}")
            continue

        df_meta = df[df["year"].isin(meta_years)]
        df_test = df[df["year"] == test_year]

        # Grid search on meta-validation
        best_sharpe = -999
        best_params = None
        best_avg_trades = 0
        for top_n, min_proba, vix_max in product(TOP_N_GRID, MIN_PROBA_GRID, vix_max_grid):
            sharpe, avg_trades = compute_meta_sharpe(df_meta, top_n, min_proba, VIX_MIN, vix_max)
            if np.isnan(sharpe):
                continue
            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_params = (top_n, min_proba, vix_max)
                best_avg_trades = avg_trades

        if best_params is None:
            print(f"  {test_year:>5}  {'no valid param combo found':>28}")
            continue

        top_n, min_proba, vix_max = best_params
        if fix_vix_max:
            params_str = f"N={top_n},p={min_proba:.2f}"
        else:
            params_str = f"N={top_n},p={min_proba:.2f},V={vix_max:.0f}"

        # Apply to test year
        test_edge, n_trades = compute_year_edge(df_test, top_n, min_proba, VIX_MIN, vix_max)
        edge_str = f"{test_edge*100:+.2f}%" if not np.isnan(test_edge) else "  N/A"
        sig = "*" if not np.isnan(test_edge) and abs(test_edge) > 0.02 else " "

        print(f"  {test_year:>5}  {params_str:>28}  {best_sharpe:>8.2f}  {edge_str:>10}{sig}  {n_trades:>6}")
        if not np.isnan(test_edge):
            per_year_results.append({
                "year": test_year, "edge": test_edge, "params": best_params, "n_trades": n_trades
            })

    if not per_year_results:
        print("  No results with sufficient data.")
        return

    edges = [r["edge"] for r in per_year_results]
    sharpe = np.mean(edges) / np.std(edges) if np.std(edges) > 0 else float("nan")
    n_pos = sum(1 for e in edges if e > 0)

    print(f"\n  NESTED WF RESULT ({len(per_year_results)} test years with trades)")
    print(f"  Avg edge : {np.mean(edges)*100:+.2f}%  (std: {np.std(edges)*100:.2f}%)")
    print(f"  Sharpe   : {sharpe:.2f}")
    print(f"  Positive : {n_pos}/{len(edges)} years")
    print(f"  Trades/yr: {np.mean([r['n_trades'] for r in per_year_results]):.1f} days")

    print(f"\n  Parameter selection history:")
    for r in per_year_results:
        top_n, min_proba, vix_max = r["params"]
        vix_str = "" if fix_vix_max else f", VIX_MAX={vix_max:.0f}"
        print(f"    {r['year']}: TOP_N={top_n}, MIN_PROBA={min_proba:.2f}{vix_str}"
              f"  → test edge={r['edge']*100:+.2f}%  ({r['n_trades']} trade-days)")

    print(f"\n  H43 BASELINE (contaminated): +13.75% avg edge, Sharpe 4.58, 11/11 years, ~45 trades/yr")
    label = "H53 (VIX in model + nested WF)" if fix_vix_max else "H52 NESTED WF"
    print(f"  {label:<30}: {np.mean(edges)*100:+.2f}% avg edge, "
          f"Sharpe {sharpe:.2f}, {n_pos}/{len(edges)} years, "
          f"~{np.mean([r['n_trades'] for r in per_year_results]):.0f} trades/yr")

    return per_year_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--probas", type=str, default=str(ALL_PROBAS))
    parser.add_argument("--meta-window", type=int, default=META_WINDOW,
                        help=f"Years for meta-validation (default: {META_WINDOW})")
    parser.add_argument("--min-trades", type=int, default=MIN_TRADES_PER_YEAR,
                        help=f"Min avg trades/year in meta-val to consider a param combo (default: {MIN_TRADES_PER_YEAR})")
    parser.add_argument("--no-vix-search", action="store_true",
                        help="H53: fix VIX_MAX=999 (no external VIX filter). Use with VIX-feature probas.")
    args = parser.parse_args()

    MIN_TRADES_PER_YEAR = args.min_trades
    print(f"Loading probas from {args.probas}...")
    df = load_data(Path(args.probas))
    print(f"  {len(df):,} rows | {df['ticker'].nunique()} tickers | years {df['year'].min()}-{df['year'].max()}")

    run_nested_wf(df, meta_window=args.meta_window, fix_vix_max=args.no_vix_search)
