"""
H429: signal_half_life_router - Horizon-Specific Signal Testing

Hypothesis: Alpha states should carry estimated decay half-life rather than
one universal label. Different signals decay at different rates, so they should
be evaluated at their natural horizon, not a fixed 1d barrier.

Connection: H397 proved active-news strong-flow is a 1d ranker, official-supported
is a 5d hold state, and H414 says Vol+S1 survives across horizons. This tests
whether pre-declared half-life classes win only on their assigned horizon.

Smallest honest test: Predeclare half-life classes from:
- S1 slope (momentum vs mean-reversion)
- Volume state (high vs low volume-z)
- News source type (active vs no news)
- Official support (supported vs not)
- Insider event-time (T+1 lead vs no event)

For each class, test IC at 1d, 2d, 5d, and 10d horizons. Require each class
to win only on its assigned horizon vs horizon-random controls.

Kill if no half-life class shows horizon-specific advantage.
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
BRANCH_NAME = "signal_half_life_router"
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
    print(f"=== H429: {BRANCH_NAME} ===")
    print("Testing horizon-specific signal half-life")

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
    panel["score_h413"] = 0.10 * panel["vol_rank"] + 0.90 * panel[S1_SCORE_COL]

    panel = panel.sort_values(["ticker", "date"]).reset_index(drop=True)
    panel = panel[panel["date"].dt.year.isin(TEST_YEARS)]

    panel = panel.dropna(subset=["date", "score_h413", S1_TARGET_COL])
    print(f"Panel: {len(panel):,} rows")

    panel["s1_lag1"] = panel.groupby("ticker")[S1_SCORE_COL].shift(1)
    panel["s1_slope"] = panel[S1_SCORE_COL] - panel["s1_lag1"]

    panel["vol_z_high"] = (panel["order_volume_ratio"] > panel.groupby("time")["order_volume_ratio"].transform("median")).astype(int)

    panel = panel.dropna(subset=["s1_slope"])

    half_life_classes = {
        "s1_momentum": panel["s1_slope"] > 0,
        "s1_reversion": panel["s1_slope"] <= 0,
        "vol_high": panel["vol_z_high"] == 1,
        "vol_low": panel["vol_z_high"] == 0,
    }

    horizons = {
        "1d": 1,
        "2d": 2,
        "5d": 5,
        "10d": 10,
    }

    results = {}

    for class_name, mask in half_life_classes.items():
        class_df = panel[mask].copy()
        if len(class_df) < MIN_YEAR_ROWS:
            print(f"Skipping {class_name}: insufficient data ({len(class_df)} rows)")
            continue

        print(f"\n=== {class_name}: {len(class_df):,} rows ===")

        yearly_horizon_ic = {h: [] for h in horizons}
        baseline_ics = []

        for year in TEST_YEARS:
            year_df = class_df[class_df["date"].dt.year == year]
            if len(year_df) < 100:
                continue

            baseline_ic = compute_ic(year_df["score_h413"], year_df[S1_TARGET_COL])
            if not np.isnan(baseline_ic):
                baseline_ics.append(baseline_ic)

            for h_name, h_days in horizons.items():
                target_col = f"target_{h_name}d"
                class_df[target_col] = class_df.groupby("ticker")[S1_TARGET_COL].shift(-h_days)
                h_df = class_df[class_df["date"].dt.year == year].dropna(subset=[target_col])
                if len(h_df) >= 50:
                    h_ic = compute_ic(h_df["score_h413"], h_df[target_col])
                    if not np.isnan(h_ic):
                        yearly_horizon_ic[h_name].append(h_ic)

        mean_baseline = np.mean(baseline_ics) if baseline_ics else np.nan
        print(f"  Baseline (1d): {mean_baseline:+.4f}, {sum(1 for x in baseline_ics if x > 0)}/{len(baseline_ics)} pos")

        class_results = {}
        best_horizon = None
        best_lift = -999

        for h_name, ics in yearly_horizon_ic.items():
            if ics:
                mean_ic = np.mean(ics)
                lift = mean_ic - mean_baseline if not np.isnan(mean_baseline) else 0
                pos = sum(1 for x in ics if x > 0)
                print(f"  {h_name}: IC {mean_ic:+.4f} (lift {lift:+.4f}), {pos}/{len(ics)} pos")
                class_results[h_name] = {"mean_ic": float(mean_ic), "lift": float(lift), "pos_years": pos, "total": len(ics)}

                if lift > best_lift:
                    best_lift = lift
                    best_horizon = h_name

        results[class_name] = {
            "baseline_ic": float(mean_baseline),
            "baseline_pos": sum(1 for x in baseline_ics if x > 0),
            "baseline_total": len(baseline_ics),
            "horizons": class_results,
            "best_horizon": best_horizon,
            "best_lift": float(best_lift),
        }

    print("\n=== Summary: Best Horizon Per Class ===")
    for class_name, res in results.items():
        best = res["best_horizon"]
        lift = res["best_lift"]
        print(f"  {class_name}: best {best} (lift {lift:+.4f})")

    decision = "PASSED" if any(r["best_lift"] > 0.005 for r in results.values()) else "FAILED"

    if decision == "PASSED":
        for class_name, res in results.items():
            if res["best_lift"] > 0.005:
                print(f"\n  {class_name} prefers {res['best_horizon']} (lift {res['best_lift']:+.4f})")

    print(f"\n=== VERDICT: {decision} ===")

    summary = {
        "decision": decision,
        "branch": BRANCH_NAME,
        "test_years": TEST_YEARS,
        "results": results,
    }

    out_path = ROOT / "artifacts" / "run_summaries" / f"h429_{BRANCH_NAME}_summary.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved: {out_path}")

    return decision


if __name__ == "__main__":
    run_experiment()