"""
H482: sentiment_scope_filter

Hypothesis: Ultra_negative (from H480) identifies noise states where S1 quality fails.
Test: S1 IC WITH ultra_negative vs WITHOUT. Mechanism: sentiment extremes may identify 
states where signal quality underperforms.

Decision ladder:
- PASS: S1 WITHOUT ultra_negative > S1 WITH ultra_negative by >+0.01 IC (filter helps)
- MIXED: Pattern exists but marginal (<0.01)
- FAIL: ultra_negative does not filter signal quality (S1 same with/without)
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiment_contract import (
    S1_DEFAULT_PATH,
    S1_SCORE_COL,
    S1_TARGET_COL,
    data_path,
    load_s1_decision_panel,
)


BRANCH_NAME = "sentiment_scope_filter"


def load_phobert_sentiment() -> pd.DataFrame:
    """Load PhoBERT sentiment data."""
    phobert_path = data_path("features/news/datasets/phobert_ticker_day_sentiment.parquet")
    phobert = pd.read_parquet(phobert_path)
    phobert["time"] = pd.to_datetime(phobert["date"])
    phobert = phobert[phobert["time"].dt.year <= 2025]
    return phobert[["time", "ticker", "phobert_prob_neg_mean", "phobert_sentiment_score_mean", "phobert_article_count_1d"]]


def compute_ic(df: pd.DataFrame, score_col: str, target_col: str) -> float:
    """Compute IC for a dataframe."""
    if len(df) < 50:
        return np.nan
    
    valid = df[[score_col, target_col]].dropna()
    if len(valid) < 50:
        return np.nan
    
    return valid[score_col].corr(valid[target_col])


def main():
    parser = argparse.ArgumentParser(description="H482 sentiment scope filter")
    args = parser.parse_args()
    
    print("Loading S1 panel...")
    panel = load_s1_decision_panel(
        S1_DEFAULT_PATH,
        start_year=2015,
        end_year=2025,
    )
    print(f"Loaded panel: {len(panel)} rows")
    
    print("Loading PhoBERT sentiment...")
    phobert = load_phobert_sentiment()
    print(f"Loaded PhoBERT: {len(phobert)} rows")
    
    panel = panel.merge(phobert, on=["time", "ticker"], how="inner")
    print(f"After inner join with sentiment: {len(panel)} rows")
    
    panel = panel[panel["phobert_article_count_1d"] > 0]
    print(f"After filtering rows with news: {len(panel)} rows")
    
    neg_rank = panel.groupby("time", sort=False)["phobert_prob_neg_mean"].rank(method="average", pct=True)
    panel["ultra_negative"] = (neg_rank <= 0.05).astype(bool)
    panel["extreme_negative"] = (neg_rank <= 0.10).astype(bool)
    panel["moderate_negative"] = ((neg_rank > 0.10) & (neg_rank <= 0.30)).astype(bool)
    panel["neutral"] = ((neg_rank > 0.30) & (neg_rank <= 0.70)).astype(bool)
    panel["positive"] = (neg_rank > 0.70).astype(bool)
    
    score_col = S1_SCORE_COL
    target_col = S1_TARGET_COL
    baseline_ic = compute_ic(panel, score_col, target_col)
    
    print(f"\n=== H482 Sentiment Scope Filter Results ===")
    print(f"Baseline (all S1 rows with news) IC: {baseline_ic:.4f}")
    print(f"Total rows with news: {len(panel)}")
    
    results = {}
    
    no_ultra = panel[panel["ultra_negative"] == False]
    no_ultra_ic = compute_ic(no_ultra, score_col, target_col)
    results["no_ultra_negative"] = {"ic": no_ultra_ic, "rows": len(no_ultra)}
    print(f"\nS1 WITHOUT ultra_negative (bottom 5%): IC={no_ultra_ic:.4f}, rows={len(no_ultra)}, lift={no_ultra_ic-baseline_ic:+.4f}")
    
    with_ultra = panel[panel["ultra_negative"] == True]
    with_ultra_ic = compute_ic(with_ultra, score_col, target_col)
    results["with_ultra_negative"] = {"ic": with_ultra_ic, "rows": len(with_ultra)}
    print(f"S1 WITH ultra_negative: IC={with_ultra_ic:.4f}, rows={len(with_ultra)}, lift={with_ultra_ic-baseline_ic:+.4f}")
    
    filter_lift = no_ultra_ic - with_ultra_ic
    results["filter_lift"] = filter_lift
    
    no_extreme = panel[panel["extreme_negative"] == False]
    no_extreme_ic = compute_ic(no_extreme, score_col, target_col)
    with_extreme = panel[panel["extreme_negative"] == True]
    with_extreme_ic = compute_ic(with_extreme, score_col, target_col)
    results["extreme_filter_lift"] = no_extreme_ic - with_extreme_ic
    print(f"\nExtreme (bottom 10%) filter lift: {results['extreme_filter_lift']:+.4f}")
    
    no_moderate = panel[panel["moderate_negative"] == False]
    no_moderate_ic = compute_ic(no_moderate, score_col, target_col)
    with_moderate = panel[panel["moderate_negative"] == True]
    with_moderate_ic = compute_ic(with_moderate, score_col, target_col)
    results["moderate_filter_lift"] = no_moderate_ic - with_moderate_ic
    print(f"Moderate negative (10-30%) filter lift: {results['moderate_filter_lift']:+.4f}")
    
    positive_df = panel[panel["positive"] == True]
    positive_ic = compute_ic(positive_df, score_col, target_col)
    results["positive_ic"] = positive_ic
    print(f"Positive sentiment (top 30%): IC={positive_ic:.4f}, rows={len(positive_df)}, lift={positive_ic-baseline_ic:+.4f}")
    
    print(f"\n=== Verdict ===")
    if filter_lift > 0.01 and len(with_ultra) > 100:
        verdict = "PASS"
        print(f"PASS: ultra_negative filter helps by {filter_lift:.4f} IC")
    elif filter_lift > 0.005:
        verdict = "MIXED"
        print(f"MIXED: filter effect is marginal ({filter_lift:.4f})")
    else:
        verdict = "FAIL"
        print(f"FAIL: no filter benefit ({filter_lift:.4f})")
    
    import json
    summary = {
        "branch": BRANCH_NAME,
        "verdict": verdict,
        "baseline_ic": float(baseline_ic),
        "no_ultra_negative_ic": float(no_ultra_ic),
        "with_ultra_negative_ic": float(with_ultra_ic),
        "filter_lift": float(filter_lift),
    }
    
    summary_path = ROOT / "artifacts" / "run_summaries" / f"h482_sentiment_scope_filter_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Summary saved to {summary_path}")


if __name__ == "__main__":
    main()