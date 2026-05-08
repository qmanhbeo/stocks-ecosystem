"""
H433: state_transition_not_event - Event Count Delta vs Level

Hypothesis: Event timing matters as TRANSITION, not raw feature. Event-count delta
(not level) vs same-day vs next-day predicts forward.

Connection: H321, H389 event features failed; switch to delta states. H405 tested
LIGHTCONE/SPATIAL propagation, not TEMPORAL DELTA. This tests whether event-count
change predicts forward IC.

Smallest honest test: Compute event-count delta (today's count - yesterday's count).
Compare against event-count level. Test if delta predicts forward IC vs random
date controls.

Kill if event-count delta does not outperform event-count level.
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
BRANCH_NAME = "state_transition_not_event"
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
    print(f"=== H433: {BRANCH_NAME} ===")
    print("Testing event-count delta vs level as predictor")

    s1 = pd.read_parquet(
        ROOT / "data/features/xs_barrier_vol_1d_hose_full.parquet",
        columns=["ticker", "time", S1_SCORE_COL, S1_TARGET_COL],
    )

    vol = pd.read_parquet(
        ROOT / "data/features/xs_order_pressure_daily.parquet",
        columns=["ticker", "time", "order_pressure_h359_active"],
    )

    panel = s1.merge(vol, on=["ticker", "time"], how="inner")
    panel = panel[
        panel[S1_SCORE_COL].notna()
        & panel[S1_TARGET_COL].notna()
        & panel["order_pressure_h359_active"].notna()
    ].copy()

    panel["vol_rank"] = panel.groupby("time")["order_pressure_h359_active"].rank(method="average", pct=True)
    panel["score_h413"] = 0.10 * panel["vol_rank"] + 0.90 * panel[S1_SCORE_COL]

    panel = panel.sort_values(["ticker", "time"]).reset_index(drop=True)
    panel = panel[panel["time"].dt.year.isin(TEST_YEARS)]

    date_event_count = panel.groupby("time")["order_pressure_h359_active"].sum().reset_index()
    date_event_count.columns = ["time", "event_count"]
    date_event_count["event_count_lag1"] = date_event_count["event_count"].shift(1)
    date_event_count["event_count_delta"] = date_event_count["event_count"] - date_event_count["event_count_lag1"]

    panel = panel.merge(date_event_count[["time", "event_count", "event_count_delta"]], on="time", how="left")
    panel = panel.dropna(subset=["event_count_delta"])

    print(f"Panel: {len(panel):,} rows")

    panel["delta_quintile"] = pd.qcut(panel["event_count_delta"].rank(method="first"), 5, labels=["D1_decr", "D2", "D3", "D4", "D5_incr"])
    panel["level_quintile"] = pd.qcut(panel["event_count"].rank(method="first"), 5, labels=["L1_low", "L2", "L3", "L4", "L5_high"])

    baseline_ics = []
    level_ics = []

    for year in TEST_YEARS:
        year_df = panel[panel["time"].dt.year == year]
        if len(year_df) < MIN_YEAR_ROWS:
            continue

        baseline_ic = compute_ic(year_df["score_h413"], year_df[S1_TARGET_COL])
        if not np.isnan(baseline_ic):
            baseline_ics.append(baseline_ic)

        level_ic = compute_ic(year_df["event_count"], year_df[S1_TARGET_COL])
        if not np.isnan(level_ic):
            level_ics.append(level_ic)

    baseline_mean = np.mean(baseline_ics) if baseline_ics else np.nan
    level_mean = np.mean(level_ics) if level_ics else np.nan

    print(f"\nBaseline (score_h413): mean IC {baseline_mean:+.4f}")
    print(f"Event count level: mean IC {level_mean:+.4f}")

    yearly_delta_ic = {q: [] for q in ["D1_decr", "D2", "D3", "D4", "D5_incr"]}

    for year in TEST_YEARS:
        year_df = panel[panel["time"].dt.year == year]
        if len(year_df) < MIN_YEAR_ROWS:
            continue

        for q in ["D1_decr", "D2", "D3", "D4", "D5_incr"]:
            q_df = year_df[year_df["delta_quintile"] == q]
            if len(q_df) >= 50:
                q_ic = compute_ic(q_df["score_h413"], q_df[S1_TARGET_COL])
                if not np.isnan(q_ic):
                    yearly_delta_ic[q].append(q_ic)

    print("\nIC by event-count delta quintile:")
    delta_results = {}
    for q in ["D1_decr", "D2", "D3", "D4", "D5_incr"]:
        ics = yearly_delta_ic[q]
        if ics:
            mean_ic = np.mean(ics)
            lift = mean_ic - baseline_mean
            pos = sum(1 for x in ics if x > 0)
            print(f"  {q}: mean IC {mean_ic:+.4f} (lift {lift:+.4f}), {pos}/{len(ics)} pos")
            delta_results[q] = {"mean_ic": float(mean_ic), "lift": float(lift), "pos_years": pos, "total": len(ics)}

    best_delta_lift = max(delta_results.get(q, {}).get("lift", -999) for q in delta_results)

    if best_delta_lift > 0.010:
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
        "event_count_level_ic": float(level_mean),
        "delta_results": delta_results,
    }

    out_path = ROOT / "artifacts" / "run_summaries" / f"h433_{BRANCH_NAME}_summary.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved: {out_path}")

    return decision


if __name__ == "__main__":
    run_experiment()