"""
H82: Classifier + Regressor Ensemble — Does blending XGBoost classifier and regressor scores
improve portfolio performance over the classifier alone?

The classifier (xs_proba) predicts UP/DOWN direction probability.
The regressor (xs_reg_score) predicts continuous future excess return.
Both use the same walk-forward framework and feature set.

Method:
  - Load classifier probas: xs_barrier_all_probas_hose_full.parquet
  - Load regressor scores: xs_regressor_scores_hose_full.parquet
  - Merge on (time, ticker)
  - Normalize regressor score to [0,1] via daily rank percentile
  - Blend: rank_score = alpha * xs_proba + (1-alpha) * reg_rank_pct
  - Sweep alpha in {0.3, 0.5, 0.7, 1.0}; 1.0 = classifier only (H54 baseline)
  - MIN_PROBA gate stays on original xs_proba (not blended score)
  - Report avg_edge and Sharpe per alpha vs H54 baseline

Baseline (H54): avg_edge = +25.52%, Sharpe = 9.17, 11/11 years positive.

Usage:
    conda run -n stocks python analysis/h82_regressor_ensemble.py
"""
import numpy as np
import pandas as pd
import sys
from datetime import datetime
from pathlib import Path
from path_utils import data_path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.run_summary import write_run_summary

CLASSIFIER_PROBAS = data_path("features/xs_barrier_all_probas_hose_full.parquet")
REGRESSOR_SCORES  = data_path("features/xs_regressor_scores_hose_full.parquet")

TOP_N     = 5
MIN_PROBA = 0.55
START_YEAR = 2015


def summarize_per_year(per_year: list):
    if not per_year:
        return None
    edges = [r["edge"] for r in per_year]
    avg_edge = float(np.mean(edges))
    std_edge = float(np.std(edges))
    sharpe = avg_edge / std_edge if std_edge > 0 else None
    return {
        "avg_edge": avg_edge,
        "std_edge": std_edge,
        "sharpe": float(sharpe) if sharpe is not None else None,
        "positive_years": int(sum(1 for e in edges if e > 0)),
        "total_years": len(edges),
        "avg_trade_days": float(np.mean([r["n_days"] for r in per_year])),
    }


def evaluate_portfolio(df: pd.DataFrame, rank_col: str, min_proba_col: str = "xs_proba",
                       top_n: int = TOP_N, min_proba: float = MIN_PROBA):
    """
    Evaluate top-N portfolio using rank_col for ranking.
    MIN_PROBA gate uses original xs_proba.
    Returns list of {year, edge} dicts.
    """
    per_year = []
    for test_year, grp in df.groupby("year"):
        if test_year < START_YEAR:
            continue
        naive_rate = grp["actual"].mean()
        day_edges = []
        for date, day in grp.groupby("time"):
            top = day.nlargest(top_n, rank_col)
            if top[min_proba_col].min() >= min_proba:
                day_edges.append(top["actual"].mean() - naive_rate)
        if len(day_edges) >= 5:
            per_year.append({"year": test_year, "edge": np.mean(day_edges),
                             "n_days": len(day_edges)})
    return per_year


def print_results(label: str, per_year: list, h54_edge: float = 0.2552, h54_sharpe: float = 9.17):
    stats = summarize_per_year(per_year)
    if not stats:
        print(f"  {label:30s}  NO RESULTS")
        return
    avg_edge = stats["avg_edge"]
    sharpe = stats["sharpe"] if stats["sharpe"] is not None else float("nan")
    vs_h54 = avg_edge * 100 - h54_edge * 100
    verdict = "PASS" if avg_edge > h54_edge or (avg_edge > h54_edge * 0.92 and sharpe > h54_sharpe) else "FAIL"
    print(f"  {label:30s}  edge={avg_edge*100:+.2f}%  sharpe={sharpe:5.2f}  "
          f"pos={stats['positive_years']}/{stats['total_years']}  vs_H54={vs_h54:+.2f}%  [{verdict}]")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--clf-probas", type=str, default=str(CLASSIFIER_PROBAS))
    parser.add_argument("--reg-scores", type=str, default=str(REGRESSOR_SCORES))
    parser.add_argument("--alpha", type=float, default=None,
                        help="Optional single alpha to export as a blended artifact.")
    parser.add_argument("--save-blend", type=str, default="",
                        help="Optional parquet path for saving the blended all-ticker artifact.")
    args = parser.parse_args()

    clf_path = Path(args.clf_probas)
    reg_path = Path(args.reg_scores)

    print(f"Loading classifier probas from {clf_path}...")
    clf = pd.read_parquet(clf_path)
    clf["time"] = pd.to_datetime(clf["time"])
    print(f"  {len(clf):,} rows | {clf['ticker'].nunique()} tickers")

    if not reg_path.exists():
        print(f"\n[ERROR] Regressor scores not found: {reg_path}")
        print("  Run: PYTHONIOENCODING=utf-8 conda run -n stocks python cross_sectional_wf.py \\")
        print("         --barrier-pct 0.01 --threshold 0.05 --model xgboost_reg \\")
        print("         --save-all-probas data/features/xs_regressor_scores_hose_full.parquet")
        raise SystemExit(1)

    print(f"Loading regressor scores from {reg_path}...")
    reg = pd.read_parquet(reg_path)
    reg["time"] = pd.to_datetime(reg["time"])
    print(f"  {len(reg):,} rows | {reg['ticker'].nunique()} tickers")

    # Determine regressor score column name
    reg_score_col = None
    for candidate in ["xs_proba", "xs_score", "reg_score", "score"]:
        if candidate in reg.columns:
            reg_score_col = candidate
            break
    if reg_score_col is None:
        print(f"[ERROR] Could not find score column in regressor file. Columns: {list(reg.columns)}")
        raise SystemExit(1)
    print(f"  Using regressor column: '{reg_score_col}'")

    # Merge
    merge_cols = ["time", "ticker", reg_score_col]
    if "year" in reg.columns:
        merge_cols.append("year")
    merged = clf.merge(
        reg[merge_cols].rename(columns={reg_score_col: "reg_score"}),
        on=["time", "ticker"], how="inner"
    )
    print(f"  After merge: {len(merged):,} rows | {merged['ticker'].nunique()} tickers")
    if "year" not in merged.columns:
        merged["year"] = merged["time"].dt.year

    # Daily rank-normalize regressor score to [0, 1]
    merged["reg_rank_pct"] = merged.groupby("time")["reg_score"].rank(pct=True)

    print(f"\n{'='*70}")
    print(f"H82: CLASSIFIER + REGRESSOR ENSEMBLE SWEEP")
    print(f"TOP_N={TOP_N} | MIN_PROBA={MIN_PROBA} | no VIX filter")
    print(f"  {'alpha (clf weight)':30s}  edge        sharpe   pos      vs_H54")
    print(f"  {'-'*70}")

    alphas = [1.0, 0.7, 0.5, 0.3, 0.0]
    results_by_alpha = {}
    alpha_metrics = {}
    for alpha in alphas:
        blend_col = f"blend_{alpha:.1f}"
        merged[blend_col] = alpha * merged["xs_proba"] + (1 - alpha) * merged["reg_rank_pct"]
        label = f"alpha={alpha:.1f} (clf={alpha:.0%}, reg={1-alpha:.0%})"
        per_year = evaluate_portfolio(merged, rank_col=blend_col)
        print_results(label, per_year)
        results_by_alpha[alpha] = per_year
        alpha_metrics[f"{alpha:.1f}"] = summarize_per_year(per_year)

    # Find best alpha
    best_alpha = None
    best_edge = -999
    for alpha, py in results_by_alpha.items():
        if py:
            e = float(np.mean([r["edge"] for r in py]))
            if e > best_edge:
                best_edge = e
                best_alpha = alpha

    print(f"\n  Best alpha: {best_alpha:.1f}  (avg_edge={best_edge*100:+.2f}%)")
    print(f"  H54 baseline:             (+25.52%, Sharpe 9.17, 11/11 yrs)")
    verdict = "PASS" if best_edge * 100 > 25.52 else "FAIL"
    print(f"  H82 Verdict: {verdict}")

    blend_artifact = ""
    if args.save_blend:
        if args.alpha is None:
            print("[ERROR] --save-blend requires --alpha")
            raise SystemExit(1)
        blend_col = f"blend_{args.alpha:.1f}"
        if blend_col not in merged.columns:
            merged[blend_col] = args.alpha * merged["xs_proba"] + (1 - args.alpha) * merged["reg_rank_pct"]
        out_df = merged[["time", "year", "ticker", "xs_proba", "actual", "reg_score", "reg_rank_pct", blend_col]].copy()
        out_df = out_df.rename(columns={blend_col: "blend_score"})
        blend_artifact = str(Path(args.save_blend))
        Path(blend_artifact).parent.mkdir(parents=True, exist_ok=True)
        out_df.to_parquet(blend_artifact, index=False)
        print(f"  Blended artifact saved to {blend_artifact}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_path = write_run_summary(
        ts=ts,
        mode="regressor_blend",
        name=f"h82_regressor_ensemble_{clf_path.stem}",
        summary={
            "best_alpha_by_edge": best_alpha,
            "best_avg_edge": round(best_edge, 4),
            "alpha_0_5": alpha_metrics.get("0.5"),
            "baseline_alpha_1_0": alpha_metrics.get("1.0"),
        },
        artifacts={
            "classifier_probas": str(clf_path),
            "regressor_scores": str(reg_path),
            "blend_artifact": blend_artifact,
        },
        metadata={
            "top_n": TOP_N,
            "min_proba": MIN_PROBA,
            "export_alpha": args.alpha,
            "alpha_metrics": alpha_metrics,
        },
    )
    print(f"  Run summary saved to {summary_path}")
