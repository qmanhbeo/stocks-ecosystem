"""
H428: ranker_error_taxonomy_v5 - S1 Rank Degradation Test

Hypothesis: High S1-ranked tickers predictably degrade in next-day ranker quality
(S1 mean reversion). This is a real error state for the ranker.

Connection: B8 (S1 Mean Reversion Signal) from bright-mind. The claim is that
top S1 tickers DECAY next day, not continue. H420 tested rank-based weights but
used the same-period pool split. The real test is temporal: top-S1 today -> IC tomorrow.

Smallest honest test: Bucket tickers by current S1 rank into quintiles.
For each quintile, measure mean NEXT-DAY ranker IC. If top quintile has
materially lower next-day IC, that's a real error-state detection.
Compare against random-bucket next-day IC as control.

Kill if top-S1 next-day IC is not materially lower than all-row baseline.
"""

from __future__ import annotations

import argparse
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
BRANCH_NAME = "ranker_error_taxonomy_v5"
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
    print(f"=== H428 v5: {BRANCH_NAME} ===")
    print("Testing S1 rank degradation (top today -> IC tomorrow)")

    s1 = pd.read_parquet(
        ROOT / "data/features/xs_barrier_vol_1d_hose_full.parquet",
        columns=["ticker", "time", S1_SCORE_COL, S1_TARGET_COL],
    )
    s1["date"] = pd.to_datetime(s1["time"])

    vol = pd.read_parquet(
        ROOT / "data/features/xs_order_pressure_daily.parquet",
        columns=["ticker", "time", "order_volume_ratio"],
    )

    panel = s1.merge(vol, on=["ticker", "time"], how="inner")
    panel = panel[
        panel[S1_SCORE_COL].notna()
        & panel[S1_TARGET_COL].notna()
        & panel["order_volume_ratio"].notna()
    ].copy()

    panel["vol_rank"] = panel.groupby("time")["order_volume_ratio"].rank(method="average", pct=True)
    panel["s1_rank"] = panel.groupby("time")[S1_SCORE_COL].rank(method="average", pct=True)
    panel["score_h413"] = 0.10 * panel["vol_rank"] + 0.90 * panel[S1_SCORE_COL]

    panel = panel.sort_values(["ticker", "date"]).reset_index(drop=True)
    panel = panel[panel["date"].dt.year.isin(TEST_YEARS)]

    panel["next_date"] = panel.groupby("ticker")["date"].shift(-1)
    panel["next_score"] = panel.groupby("ticker")["score_h413"].shift(-1)
    panel["next_target"] = panel.groupby("ticker")[S1_TARGET_COL].shift(-1)

    panel = panel.dropna(subset=["next_date", "next_score", "next_target"])

    date_quintiles = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    panel["s1_quintile"] = pd.qcut(panel["s1_rank"], 5, labels=["Q1_bot", "Q2", "Q3", "Q4", "Q5_top"])

    print(f"Panel with next-day data: {len(panel):,} rows")
    print(f"Quintile distribution:")
    print(panel["s1_quintile"].value_counts().sort_index())

    yearly_quintile_ic = {q: [] for q in ["Q1_bot", "Q2", "Q3", "Q4", "Q5_top"]}
    yearly_baseline_ic = []

    for year in TEST_YEARS:
        year_df = panel[panel["date"].dt.year == year]
        if len(year_df) < MIN_YEAR_ROWS:
            continue

        baseline_ic = compute_ic(year_df["next_score"], year_df["next_target"])
        yearly_baseline_ic.append(baseline_ic)

        for q in ["Q1_bot", "Q2", "Q3", "Q4", "Q5_top"]:
            q_df = year_df[year_df["s1_quintile"] == q]
            if len(q_df) >= 50:
                q_ic = compute_ic(q_df["next_score"], q_df["next_target"])
                yearly_quintile_ic[q].append(q_ic)

    baseline_mean = np.mean(yearly_baseline_ic)
    baseline_pos = sum(1 for ic in yearly_baseline_ic if ic > 0)
    print(f"\nNext-day baseline: mean IC {baseline_mean:+.4f}, {baseline_pos}/{len(yearly_baseline_ic)} pos years")

    print("\nNext-day IC by current-period S1 quintile:")
    degradation = {}
    for q in ["Q1_bot", "Q2", "Q3", "Q4", "Q5_top"]:
        ics = yearly_quintile_ic[q]
        if ics:
            mean_ic = np.mean(ics)
            pos = sum(1 for ic in ics if ic > 0)
            lift = mean_ic - baseline_mean
            print(f"  {q}: mean IC {mean_ic:+.4f} (lift {lift:+.4f}), {pos}/{len(ics)} pos years")
            degradation[q] = {"mean_ic": mean_ic, "lift": lift, "pos_years": pos, "total": len(ics)}

    top_degraded = degradation.get("Q5_top", {}).get("lift", 0) < -0.010
    bot_improved = degradation.get("Q1_bot", {}).get("lift", 0) > 0.005

    dev_years = [y for y in range(2018, 2023)]
    val_years = [y for y in range(2023, 2026)]

    dev_top = [degradation["Q5_top"]["mean_ic"]] * min(len(dev_years), 1) if "Q5_top" in degradation else []
    val_top = [degradation["Q5_top"]["mean_ic"]] * min(len(val_years), 1) if "Q5_top" in degradation else []

    val_top_ics = []
    for year in val_years:
        year_df = panel[panel["date"].dt.year == year]
        top_df = year_df[year_df["s1_quintile"] == "Q5_top"]
        if len(top_df) >= 50:
            ic = compute_ic(top_df["next_score"], top_df["next_target"])
            val_top_ics.append(ic)

    val_baseline_ics = []
    for year in val_years:
        year_df = panel[panel["date"].dt.year == year]
        ic = compute_ic(year_df["next_score"], year_df["next_target"])
        val_baseline_ics.append(ic)

    val_top_mean = np.mean(val_top_ics) if val_top_ics else np.nan
    val_baseline_mean = np.mean(val_baseline_ics) if val_baseline_ics else np.nan
    val_degradation = val_top_mean - val_baseline_mean if not np.isnan(val_top_mean) else 0.0

    print(f"\nVal next-day IC: Top-S1 = {val_top_mean:+.4f}, Baseline = {val_baseline_mean:+.4f}, Degradation = {val_degradation:+.4f}")
    print(f"Val top pos years: {sum(1 for ic in val_top_ics if ic > 0)}/{len(val_top_ics)}")

    if top_degraded and val_degradation < -0.005:
        decision = "MIXED"
    elif top_degraded and val_degradation < 0:
        decision = "MIXED"
    else:
        decision = "FAILED"

    print(f"\n=== VERDICT: {decision} ===")

    summary = {
        "decision": decision,
        "branch": BRANCH_NAME,
        "next_day_baseline_ic": float(baseline_mean),
        "baseline_pos_years": baseline_pos,
        "total_baseline_years": len(yearly_baseline_ic),
        "quintile_degradation": {q: degradation[q] for q in degradation},
        "val_top_mean_ic": float(val_top_mean),
        "val_baseline_mean_ic": float(val_baseline_mean),
        "val_degradation": float(val_degradation),
        "val_top_pos_years": sum(1 for ic in val_top_ics if ic > 0),
        "val_top_total_years": len(val_top_ics),
        "dev_years": dev_years,
        "val_years": val_years,
    }

    out_path = ROOT / "artifacts" / "run_summaries" / f"h428_{BRANCH_NAME}_summary.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved: {out_path}")

    return decision


if __name__ == "__main__":
    run_experiment()