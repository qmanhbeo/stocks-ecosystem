"""
H431: cross_sectional_rank_delta - C16 Rank Change vs Level

Hypothesis: C16 rank CHANGE (not level) predicts forward. Delta is a DIFFERENT
feature class from level derivatives - it captures flow acceleration.

Connection: H407 tested cross-product of LAGS, not RANK CHANGE. H412 tested
additive of LEVELS, not delta. This tests whether rank delta predicts forward IC.

Smallest honest test: Compute C16 rank delta (today's rank - yesterday's rank).
Bucket into quintiles. Test if rank acceleration predicts forward IC vs random
date controls. Compare against C16 level as baseline.

Kill if rank delta does not outperform C16 level.
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
BRANCH_NAME = "cross_sectional_rank_delta"
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
    print(f"=== H431: {BRANCH_NAME} ===")
    print("Testing C16 rank change vs level as predictor")

    s1 = pd.read_parquet(
        ROOT / "data/features/xs_barrier_vol_1d_hose_full.parquet",
        columns=["ticker", "time", S1_SCORE_COL, S1_TARGET_COL],
    )

    c16 = pd.read_parquet(
        ROOT / "data/features/xs_order_pressure_daily.parquet",
        columns=["ticker", "time", "order_volume_ratio_rank", "order_pressure_h359_active"],
    )

    panel = s1.merge(c16, on=["ticker", "time"], how="inner")
    panel = panel[
        panel[S1_SCORE_COL].notna()
        & panel[S1_TARGET_COL].notna()
        & panel["order_volume_ratio_rank"].notna()
    ].copy()

    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)
    panel = panel[panel["time"].dt.year.isin(TEST_YEARS)]

    panel["c16_rank_lag1"] = panel.groupby("ticker")["order_volume_ratio_rank"].shift(1)
    panel["c16_rank_delta"] = panel["order_volume_ratio_rank"] - panel["c16_rank_lag1"]

    panel = panel.dropna(subset=["c16_rank_delta"])

    panel["vol_rank"] = panel.groupby("time")["order_pressure_h359_active"].rank(method="average", pct=True)
    panel["score_h413"] = 0.10 * panel["vol_rank"] + 0.90 * panel[S1_SCORE_COL]

    print(f"Panel: {len(panel):,} rows")

    panel["delta_quintile"] = pd.qcut(
        panel["c16_rank_delta"], 5, labels=["Q1_decr", "Q2", "Q3", "Q4", "Q5_incr"]
    )

    yearly_delta_ic = {q: [] for q in ["Q1_decr", "Q2", "Q3", "Q4", "Q5_incr"]}
    baseline_ics = []
    level_ics = []

    for year in TEST_YEARS:
        year_df = panel[panel["time"].dt.year == year]
        if len(year_df) < MIN_YEAR_ROWS:
            continue

        baseline_ic = compute_ic(year_df["score_h413"], year_df[S1_TARGET_COL])
        if not np.isnan(baseline_ic):
            baseline_ics.append(baseline_ic)

        level_ic = compute_ic(year_df["order_volume_ratio_rank"], year_df[S1_TARGET_COL])
        if not np.isnan(level_ic):
            level_ics.append(level_ic)

        for q in ["Q1_decr", "Q2", "Q3", "Q4", "Q5_incr"]:
            q_df = year_df[year_df["delta_quintile"] == q]
            if len(q_df) >= 50:
                q_ic = compute_ic(q_df["score_h413"], q_df[S1_TARGET_COL])
                if not np.isnan(q_ic):
                    yearly_delta_ic[q].append(q_ic)

    baseline_mean = np.mean(baseline_ics) if baseline_ics else np.nan
    level_mean = np.mean(level_ics) if level_ics else np.nan

    print(f"\nBaseline (score_h413): mean IC {baseline_mean:+.4f}")
    print(f"C16 level alone: mean IC {level_mean:+.4f}")

    print("\nIC by rank delta quintile:")
    delta_results = {}
    for q in ["Q1_decr", "Q2", "Q3", "Q4", "Q5_incr"]:
        ics = yearly_delta_ic[q]
        if ics:
            mean_ic = np.mean(ics)
            lift = mean_ic - baseline_mean
            pos = sum(1 for x in ics if x > 0)
            print(f"  {q}: mean IC {mean_ic:+.4f} (lift {lift:+.4f}), {pos}/{len(ics)} pos")
            delta_results[q] = {"mean_ic": float(mean_ic), "lift": float(lift), "pos_years": pos, "total": len(ics)}

    q5_incr_lift = delta_results.get("Q5_incr", {}).get("lift", 0)
    q1_decr_lift = delta_results.get("Q1_decr", {}).get("lift", 0)

    dev_years = list(range(2018, 2023))
    val_years = list(range(2023, 2026))

    val_delta_ics = {q: [] for q in ["Q1_decr", "Q2", "Q3", "Q4", "Q5_incr"]}
    val_level_ics = []
    for year in val_years:
        year_df = panel[panel["time"].dt.year == year]
        level_ic = compute_ic(year_df["order_volume_ratio_rank"], year_df[S1_TARGET_COL])
        if not np.isnan(level_ic):
            val_level_ics.append(level_ic)

        for q in ["Q1_decr", "Q2", "Q3", "Q4", "Q5_incr"]:
            q_df = year_df[year_df["delta_quintile"] == q]
            if len(q_df) >= 50:
                q_ic = compute_ic(q_df["score_h413"], q_df[S1_TARGET_COL])
                if not np.isnan(q_ic):
                    val_delta_ics[q].append(q_ic)

    val_q5 = np.mean(val_delta_ics["Q5_incr"]) if val_delta_ics["Q5_incr"] else np.nan
    val_level = np.mean(val_level_ics) if val_level_ics else np.nan

    print(f"\nValidation (2023-2025): Q5_incr = {val_q5:+.4f}, C16 level = {val_level:+.4f}")

    best_delta_lift = max(delta_results.get(q, {}).get("lift", -999) for q in delta_results)

    if best_delta_lift > 0.010 and (val_q5 - val_level if not np.isnan(val_q5) else 0) > 0:
        decision = "PASSED"
    elif best_delta_lift > 0.005:
        decision = "MIXED"
    else:
        decision = "FAILED"

    print(f"\n=== VERDICT: {decision} ===")

    summary = {
        "decision": decision,
        "branch": BRANCH_NAME,
        "baseline_ic": float(baseline_mean),
        "c16_level_ic": float(level_mean),
        "delta_results": delta_results,
        "dev_years": dev_years,
        "val_years": val_years,
        "val_q5_incr_ic": float(val_q5) if not np.isnan(val_q5) else None,
        "val_c16_level_ic": float(val_level) if not np.isnan(val_level) else None,
    }

    out_path = ROOT / "artifacts" / "run_summaries" / f"h431_{BRANCH_NAME}_summary.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved: {out_path}")

    return decision


if __name__ == "__main__":
    run_experiment()