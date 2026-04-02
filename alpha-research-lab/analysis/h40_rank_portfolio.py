"""
H40: Rank-based portfolio using XS barrier probabilities for ALL 52 tickers.

Instead of predicting UP/DOWN per stock and using a fixed threshold, we:
  1. Each trading day, rank ALL 52 stocks by their XS barrier proba
  2. Go long the top-N stocks (highest predicted outperformance probability)
  3. Measure: does the top-ranked quintile actually outperform the bottom-ranked quintile?

This is how factor investing works in practice. It eliminates the "is the market
going up?" problem — we only care about RELATIVE performance.

Two variants:
  A. Top-N portfolio: long top-5 stocks each day (same as H23 but dynamic, not fixed stocks)
  B. Quintile spread: top-quintile edge vs bottom-quintile (pure academic factor test)

Usage:
    conda run -n stocks python analysis/h40_rank_portfolio.py
"""
import numpy as np
import pandas as pd
import sys
from pathlib import Path
from path_utils import data_path
from datetime import datetime
from scipy.stats import binomtest, spearmanr

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.run_summary import write_run_summary

ALL_PROBAS = data_path("features/xs_barrier_all_probas.parquet")
VIX_PATH   = data_path("fx-commodities/fx_commodities_vix_1D.parquet")
MACRO_PATH = data_path("features/macro_regime_daily.parquet")

TOP_N       = 5       # long top-N stocks each day
MIN_PROBA   = 0.55    # only count days where top stock has proba >= this
RANK_COL    = "xs_proba"
MIN_PROBA_COL = "xs_proba"
VIX_MIN     = 15.0
VIX_MAX     = 30.0
START_YEAR  = 2015    # use all available walk-forward years


def load_data(probas_path: Path = ALL_PROBAS):
    df = pd.read_parquet(probas_path)
    df["time"] = pd.to_datetime(df["time"])

    vix = pd.read_parquet(VIX_PATH)[["time", "close"]].rename(columns={"close": "vix"})
    vix["time"] = pd.to_datetime(vix["time"])

    df = df.merge(vix, on="time", how="left")
    df["vix"] = df["vix"].ffill()
    return df


def quintile_factor_test(df: pd.DataFrame):
    """
    Academic factor test: on each day, bucket stocks into quintiles by xs_proba.
    Measure whether Q5 (top) outperforms Q1 (bottom) in the actual label.
    This tests whether the model's RANKING is informative, not just threshold.
    """
    print("\n" + "=" * 70)
    print("QUINTILE FACTOR TEST — Does proba RANK predict actual outcome?")
    print(f"(Using all {df['ticker'].nunique()} tickers, no VIX filter)")
    print(f"  {'year':>5}  {'Q5_rate':>8}  {'Q1_rate':>8}  {'spread':>8}  {'IC':>8}  {'pval':>8}")
    print("  " + "-" * 55)

    per_year = []
    for year, grp in df.groupby("year"):
        if year < START_YEAR:
            continue
        daily_results = []
        for date, day in grp.groupby("time"):
            if len(day) < 10:
                continue
            day = day.copy()
            day["rank"] = day[RANK_COL].rank(pct=True)
            q5 = day[day["rank"] >= 0.8]["actual"].values
            q1 = day[day["rank"] <= 0.2]["actual"].values
            if len(q5) >= 2 and len(q1) >= 2:
                daily_results.append({
                    "q5_rate": q5.mean(),
                    "q1_rate": q1.mean(),
                    "spread":  q5.mean() - q1.mean(),
                    "ic":      spearmanr(day[RANK_COL], day["actual"])[0],
                })
        if not daily_results:
            continue
        dr = pd.DataFrame(daily_results)
        avg_spread = dr["spread"].mean()
        avg_q5 = dr["q5_rate"].mean()
        avg_q1 = dr["q1_rate"].mean()
        avg_ic = dr["ic"].mean()
        # t-test on daily spreads
        from scipy.stats import ttest_1samp
        pval = ttest_1samp(dr["spread"], 0).pvalue
        sig = "*" if pval < 0.05 else " "
        print(f"  {year:>5}  {avg_q5*100:>7.1f}%  {avg_q1*100:>7.1f}%  {avg_spread*100:>+7.2f}%  {avg_ic:>+7.3f}  {pval:>7.4f}{sig}")
        per_year.append({"year": year, "spread": avg_spread, "ic": avg_ic})

    if per_year:
        spreads = [r["spread"] for r in per_year]
        ics = [r["ic"] for r in per_year]
        print(f"\n  Avg Q5-Q1 spread : {np.mean(spreads)*100:+.2f}%  (std: {np.std(spreads)*100:.2f}%)")
        print(f"  Avg IC (Spearman): {np.mean(ics):+.4f}")
        print(f"  Sig years        : {sum(1 for r in per_year if abs(r['spread']) > 0.02)}/{len(per_year)}")
        return {
            "avg_q5_q1_spread": round(float(np.mean(spreads)), 4),
            "avg_ic": round(float(np.mean(ics)), 4),
            "sig_years": sum(1 for r in per_year if abs(r["spread"]) > 0.02),
            "total_years": len(per_year),
        }
    return None


def dynamic_top_n_portfolio(df: pd.DataFrame):
    """
    Dynamic top-N portfolio: each day, long the top-N stocks by xs_proba.
    Only trade if the top-N all have proba >= MIN_PROBA AND VIX in band.
    Compare to fixed H23 portfolio (EIB/STB/POW/MSN/BID).
    """
    H23_STOCKS = {"EIB", "STB", "POW", "MSN", "BID"}

    print("\n" + "=" * 70)
    print(f"DYNAMIC TOP-{TOP_N} PORTFOLIO (rebalanced daily by xs_proba rank)")
    print(f"Filter: VIX [{VIX_MIN},{VIX_MAX}] | min_proba={MIN_PROBA}")
    print(f"  {'year':>5}  {'n_days':>7}  {'trades':>7}  {'dyn_edge':>9}  {'h23_edge':>9}  {'overlap':>8}")
    print("  " + "-" * 60)

    per_year = []
    for year, grp in df.groupby("year"):
        if year < START_YEAR:
            continue
        naive_rate = grp["actual"].mean()

        dyn_correct = []
        h23_correct = []
        h23_trades  = 0
        dyn_days    = 0
        overlap_days = 0

        for date, day in grp.groupby("time"):
            vix_val = day["vix"].iloc[0]
            if not (VIX_MIN <= vix_val <= VIX_MAX):
                continue

            day_sorted = day.nlargest(TOP_N, RANK_COL)
            top_probas  = day_sorted[MIN_PROBA_COL].values
            top_tickers = set(day_sorted["ticker"].values)
            top_actuals = day_sorted["actual"].values

            # Dynamic portfolio: trade only if top-N all confident
            if top_probas.min() >= MIN_PROBA:
                dyn_days += 1
                dyn_correct.extend(top_actuals.tolist())

            # Fixed H23 portfolio: trade if any H23 stock is confident
            h23_day = day[day["ticker"].isin(H23_STOCKS)]
            h23_conf = h23_day[h23_day[MIN_PROBA_COL] >= MIN_PROBA]
            if len(h23_conf) >= 2:
                h23_trades += 1
                h23_correct.extend(h23_conf["actual"].tolist())

            # Overlap: same day traded in both
            h23_conf_tickers = set(h23_conf["ticker"].values)
            if dyn_days > 0 and top_probas.min() >= MIN_PROBA and len(h23_conf_tickers) >= 2:
                overlap = len(top_tickers & h23_conf_tickers)
                if overlap >= 1:
                    overlap_days += 1

        dyn_edge = (np.mean(dyn_correct) - naive_rate) if dyn_correct else float("nan")
        h23_edge = (np.mean(h23_correct) - naive_rate) if h23_correct else float("nan")
        ov_pct   = (overlap_days / max(1, min(dyn_days, h23_trades))) * 100

        print(f"  {year:>5}  {len(grp['time'].unique()):>7}  {dyn_days:>7}  "
              f"{dyn_edge*100:>+8.2f}%  {h23_edge*100:>+8.2f}%  {ov_pct:>6.0f}%")
        per_year.append({
            "year": year, "dyn_edge": dyn_edge, "h23_edge": h23_edge,
            "dyn_trades": dyn_days, "h23_trades": h23_trades,
        })

    valid_dyn = [r["dyn_edge"] for r in per_year if not np.isnan(r["dyn_edge"])]
    valid_h23 = [r["h23_edge"] for r in per_year if not np.isnan(r["h23_edge"])]
    if valid_dyn:
        print(f"\n  Dynamic Top-{TOP_N} avg edge : {np.mean(valid_dyn)*100:+.2f}%  "
              f"(std: {np.std(valid_dyn)*100:.2f}%,  Sharpe: {np.mean(valid_dyn)/np.std(valid_dyn):.2f})")
    if valid_h23:
        print(f"  Fixed H23 avg edge    : {np.mean(valid_h23)*100:+.2f}%  "
              f"(std: {np.std(valid_h23)*100:.2f}%,  Sharpe: {np.mean(valid_h23)/np.std(valid_h23):.2f})")
    return {
        "avg_dyn_edge": round(float(np.mean(valid_dyn)), 4) if valid_dyn else None,
        "dyn_sharpe": round(float(np.mean(valid_dyn) / np.std(valid_dyn)), 4)
        if valid_dyn and np.std(valid_dyn) > 0 else None,
        "avg_h23_edge": round(float(np.mean(valid_h23)), 4) if valid_h23 else None,
        "h23_sharpe": round(float(np.mean(valid_h23) / np.std(valid_h23)), 4)
        if valid_h23 and np.std(valid_h23) > 0 else None,
        "total_years": len(per_year),
    }


def top_n_sweep(df: pd.DataFrame):
    """Sweep N=1..10 and min_proba to find optimal dynamic portfolio."""
    print("\n" + "=" * 70)
    print(f"TOP-N SWEEP | VIX [{VIX_MIN},{VIX_MAX}] | min_proba={MIN_PROBA}")
    print(f"  {'N':>4}  {'avg_edge':>9}  {'sharpe':>8}  {'n_yrs':>6}  {'trades/yr':>10}")
    print("  " + "-" * 50)

    sweep_rows = []
    for n in [1, 2, 3, 5, 7, 10, 15]:
        per_year = []
        for year, grp in df.groupby("year"):
            if year < START_YEAR:
                continue
            naive_rate = grp["actual"].mean()
            day_edges = []
            for date, day in grp.groupby("time"):
                vix_val = day["vix"].iloc[0]
                if not (VIX_MIN <= vix_val <= VIX_MAX):
                    continue
                top = day.nlargest(n, RANK_COL)
                if top[MIN_PROBA_COL].min() >= MIN_PROBA:
                    day_edges.append(top["actual"].mean() - naive_rate)
            if len(day_edges) >= 5:
                per_year.append({"edge": np.mean(day_edges), "n_trades": len(day_edges)})
        if per_year:
            edges = [r["edge"] for r in per_year]
            sharpe = np.mean(edges) / np.std(edges) if np.std(edges) > 0 else float("nan")
            trades = np.mean([r["n_trades"] for r in per_year])
            print(f"  {n:>4}  {np.mean(edges)*100:>+8.2f}%  {sharpe:>8.2f}  {len(per_year):>6}  {trades:>9.1f}")
            sweep_rows.append({
                "n": n,
                "avg_edge": float(np.mean(edges)),
                "sharpe": float(sharpe) if sharpe == sharpe else None,
                "n_years": len(per_year),
                "trades_per_year": float(trades),
            })
    if not sweep_rows:
        return None
    best = max(
        [row for row in sweep_rows if row["sharpe"] is not None],
        key=lambda row: row["sharpe"],
        default=None,
    )
    return {
        "best_n_by_sharpe": best["n"] if best else None,
        "best_sharpe": round(best["sharpe"], 4) if best else None,
        "best_avg_edge": round(best["avg_edge"], 4) if best else None,
        "rows": sweep_rows,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--probas", type=str, default=str(ALL_PROBAS),
                        help="Path to all-ticker probas parquet (default: xs_barrier_all_probas.parquet)")
    parser.add_argument("--no-vix-filter", action="store_true",
                        help="H50: disable VIX band filter (sets VIX_MIN=0, VIX_MAX=999)")
    parser.add_argument("--top-n", type=int, default=TOP_N,
                        help=f"Number of top stocks to hold each day (default: {TOP_N})")
    parser.add_argument("--min-proba", type=float, default=MIN_PROBA,
                        help=f"Minimum XS proba for top stock to enter (default: {MIN_PROBA})")
    parser.add_argument("--rank-col", type=str, default=RANK_COL,
                        help="Column used for ranking (default: xs_proba)")
    parser.add_argument("--min-proba-col", type=str, default=MIN_PROBA_COL,
                        help="Column used for the min-proba gate (default: xs_proba)")
    parser.add_argument("--no-min-proba", action="store_true",
                        help="Disable min-proba filter (always trade top-N regardless of proba)")
    args = parser.parse_args()

    if args.no_vix_filter:
        VIX_MIN = 0.0
        VIX_MAX = 999.0
        print(f"[H50] VIX filter DISABLED (no_vix_filter=True)")
    if args.top_n != TOP_N:
        TOP_N = args.top_n
        print(f"[OVERRIDE] TOP_N = {TOP_N}")
    if args.no_min_proba:
        MIN_PROBA = 0.0
        print(f"[OVERRIDE] MIN_PROBA disabled (=0.0)")
    elif args.min_proba != MIN_PROBA:
        MIN_PROBA = args.min_proba
        print(f"[OVERRIDE] MIN_PROBA = {MIN_PROBA}")
    RANK_COL = args.rank_col
    MIN_PROBA_COL = args.min_proba_col
    print(f"[OVERRIDE] RANK_COL = {RANK_COL} | MIN_PROBA_COL = {MIN_PROBA_COL}")

    probas_path = Path(args.probas)
    print(f"Loading all-ticker XS probas from {probas_path}...")
    df = load_data(probas_path)
    print(f"  {len(df):,} rows | {df['ticker'].nunique()} tickers | years {df['year'].min()}-{df['year'].max()}")

    quintile_summary = quintile_factor_test(df)
    dynamic_summary = dynamic_top_n_portfolio(df)
    sweep_summary = top_n_sweep(df)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_path = write_run_summary(
        ts=ts,
        mode="portfolio",
        name=f"h40_rank_portfolio_{probas_path.stem}",
        summary={
            "avg_dyn_edge": dynamic_summary.get("avg_dyn_edge") if dynamic_summary else None,
            "dyn_sharpe": dynamic_summary.get("dyn_sharpe") if dynamic_summary else None,
            "avg_q5_q1_spread": quintile_summary.get("avg_q5_q1_spread") if quintile_summary else None,
            "avg_ic": quintile_summary.get("avg_ic") if quintile_summary else None,
            "best_n_by_sharpe": sweep_summary.get("best_n_by_sharpe") if sweep_summary else None,
            "best_sharpe": sweep_summary.get("best_sharpe") if sweep_summary else None,
        },
        artifacts={
            "probas": str(probas_path),
        },
        metadata={
            "top_n": TOP_N,
            "min_proba": MIN_PROBA,
            "rank_col": RANK_COL,
            "min_proba_col": MIN_PROBA_COL,
            "vix_min": VIX_MIN,
            "vix_max": VIX_MAX,
        },
    )
    print(f"Run summary saved to {summary_path}")
