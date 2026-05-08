"""
H430: candidate_temperature_entropy - Score Entropy as Signal

Hypothesis: Candidate panel score entropy predicts forward returns. When scores
cluster tight (low entropy), forward degrades; when dispersed (high entropy),
there's hidden alpha.

Connection: H379/H380 tested candidate-count POLICY, not score ENTROPY. This tests
whether entropy of top-10 scores predicts forward IC.

Smallest honest test: Bucket dates by full_top10_score_entropy and s1_top10_score_entropy
into quintiles. Test if high-entropy dates have better forward ranker IC vs low-entropy.
Compare against random-date controls.

Kill if entropy does not predict forward IC.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

S1_SCORE_COL = "xs_proba"
S1_TARGET_COL = "actual"
BRANCH_NAME = "candidate_temperature_entropy"
MODE = "research_branch"
MAX_YEAR = 2025
TEST_YEARS = list(range(2018, MAX_YEAR + 1))
MIN_YEAR_ROWS = 500


def compute_ic(series: pd.Series, target: pd.Series) -> float:
    valid = series.notna() & target.notna()
    if valid.sum() < 50:
        return np.nan
    ic, _ = spearmanr(series[valid], target[valid])
    return float(ic)


def run_experiment():
    print(f"=== H430: {BRANCH_NAME} ===")
    print("Testing candidate score entropy as forward predictor")

    s1 = pd.read_parquet(
        ROOT / "data/features/xs_barrier_vol_1d_hose_full.parquet",
        columns=["ticker", "time", S1_SCORE_COL, S1_TARGET_COL],
    )

    vol = pd.read_parquet(
        ROOT / "data/features/xs_order_pressure_daily.parquet",
        columns=["ticker", "time", "order_volume_ratio"],
    )

    activation = pd.read_parquet(
        ROOT / "data/features/activation_state_daily.parquet",
        columns=["time", "full_top10_score_entropy", "s1_top10_score_entropy", "candidate_count"],
    )

    panel = s1.merge(vol, on=["ticker", "time"], how="inner")
    panel = panel.merge(activation, on="time", how="inner")

    panel = panel[
        panel[S1_SCORE_COL].notna()
        & panel[S1_TARGET_COL].notna()
        & panel["order_volume_ratio"].notna()
        & panel["full_top10_score_entropy"].notna()
    ].copy()

    panel["vol_rank"] = panel.groupby("time")["order_volume_ratio"].rank(method="average", pct=True)
    panel["score_h413"] = 0.10 * panel["vol_rank"] + 0.90 * panel[S1_SCORE_COL]

    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)
    panel = panel[panel["time"].dt.year.isin(TEST_YEARS)]

    print(f"Panel: {len(panel):,} rows, {panel['time'].nunique()} dates")

    date_entropy = panel.groupby("time").agg({
        "full_top10_score_entropy": "first",
        "s1_top10_score_entropy": "first",
        "candidate_count": "first",
    }).reset_index()

    entropy_col = "full_top10_score_entropy"
    date_entropy["entropy_quintile"] = pd.qcut(
        date_entropy[entropy_col], 5, labels=["Q1_low", "Q2", "Q3", "Q4", "Q5_high"]
    )

    panel = panel.merge(
        date_entropy[["time", "entropy_quintile"]], on="time", how="left"
    )

    yearly_entropy_ic = {q: [] for q in ["Q1_low", "Q2", "Q3", "Q4", "Q5_high"]}
    baseline_ics = []

    for year in TEST_YEARS:
        year_df = panel[panel["time"].dt.year == year]
        if len(year_df) < MIN_YEAR_ROWS:
            continue

        baseline_ic = compute_ic(year_df["score_h413"], year_df[S1_TARGET_COL])
        if not np.isnan(baseline_ic):
            baseline_ics.append(baseline_ic)

        for q in ["Q1_low", "Q2", "Q3", "Q4", "Q5_high"]:
            q_df = year_df[year_df["entropy_quintile"] == q]
            if len(q_df) >= 50:
                q_ic = compute_ic(q_df["score_h413"], q_df[S1_TARGET_COL])
                if not np.isnan(q_ic):
                    yearly_entropy_ic[q].append(q_ic)

    baseline_mean = np.mean(baseline_ics) if baseline_ics else np.nan
    baseline_pos = sum(1 for x in baseline_ics if x > 0)

    print(f"\nBaseline (all dates): mean IC {baseline_mean:+.4f}, {baseline_pos}/{len(baseline_ics)} pos years")

    print("\nIC by entropy quintile:")
    entropy_results = {}
    for q in ["Q1_low", "Q2", "Q3", "Q4", "Q5_high"]:
        ics = yearly_entropy_ic[q]
        if ics:
            mean_ic = np.mean(ics)
            lift = mean_ic - baseline_mean
            pos = sum(1 for x in ics if x > 0)
            print(f"  {q}: mean IC {mean_ic:+.4f} (lift {lift:+.4f}), {pos}/{len(ics)} pos years")
            entropy_results[q] = {"mean_ic": float(mean_ic), "lift": float(lift), "pos_years": pos, "total": len(ics)}

    high_entropy_lift = entropy_results.get("Q5_high", {}).get("lift", 0)
    low_entropy_lift = entropy_results.get("Q1_low", {}).get("lift", 0)

    dev_years = list(range(2018, 2023))
    val_years = list(range(2023, 2026))

    val_entropy_ics = {q: [] for q in ["Q1_low", "Q2", "Q3", "Q4", "Q5_high"]}
    for year in val_years:
        year_df = panel[panel["time"].dt.year == year]
        for q in ["Q1_low", "Q2", "Q3", "Q4", "Q5_high"]:
            q_df = year_df[year_df["entropy_quintile"] == q]
            if len(q_df) >= 50:
                q_ic = compute_ic(q_df["score_h413"], q_df[S1_TARGET_COL])
                if not np.isnan(q_ic):
                    val_entropy_ics[q].append(q_ic)

    val_high = np.mean(val_entropy_ics["Q5_high"]) if val_entropy_ics["Q5_high"] else np.nan
    val_low = np.mean(val_entropy_ics["Q1_low"]) if val_entropy_ics["Q1_low"] else np.nan
    val_lift = val_high - val_low if not (np.isnan(val_high) or np.isnan(val_low)) else 0.0

    print(f"\nValidation (2023-2025): High entropy = {val_high:+.4f}, Low entropy = {val_low:+.4f}, Lift = {val_lift:+.4f}")

    if high_entropy_lift > 0.010 and val_lift > 0.005:
        decision = "PASSED"
    elif high_entropy_lift > 0.005 or val_lift > 0:
        decision = "MIXED"
    else:
        decision = "FAILED"

    print(f"\n=== VERDICT: {decision} ===")

    summary = {
        "decision": decision,
        "branch": BRANCH_NAME,
        "baseline_ic": float(baseline_mean),
        "baseline_pos_years": baseline_pos,
        "baseline_total_years": len(baseline_ics),
        "entropy_results": entropy_results,
        "dev_years": dev_years,
        "val_years": val_years,
        "val_high_entropy_ic": float(val_high) if not np.isnan(val_high) else None,
        "val_low_entropy_ic": float(val_low) if not np.isnan(val_low) else None,
        "val_lift": float(val_lift),
    }

    out_path = ROOT / "artifacts" / "run_summaries" / f"h430_{BRANCH_NAME}_summary.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved: {out_path}")

    return decision


if __name__ == "__main__":
    run_experiment()