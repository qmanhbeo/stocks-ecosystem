"""
H432: volume_price_divergence - Return vs Volume-Z Divergence

Hypothesis: Price vs volume response divergence defines edge. When they diverge,
hidden pressure exists - large move on small volume = real force, large move on
large volume = fade.

Connection: H411 tested volume LEVELS and triple-storm, not DIVERGENCE. This tests
whether return vs volume-z divergence buckets predict forward IC.

Smallest honest test: Compute return quintiles and volume-z quintiles. Test
the interaction - does high return + low volume-z (real force) outperform
high return + high volume-z (fade)?

Kill if divergence does not predict forward IC.
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
BRANCH_NAME = "volume_price_divergence"
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
    print(f"=== H432: {BRANCH_NAME} ===")
    print("Testing return vs volume-z divergence as predictor")

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

    panel["return_quintile"] = pd.qcut(panel[S1_SCORE_COL], 5, labels=["R1_low", "R2", "R3", "R4", "R5_high"])
    panel["vol_z_quintile"] = pd.qcut(panel["vol_rank"], 5, labels=["V1_low", "V2", "V3", "V4", "V5_high"])

    print(f"Panel: {len(panel):,} rows")

    divergence_states = {
        "real_force": (["R4", "R5_high"], ["V1_low", "V2"]),
        "fade": (["R4", "R5_high"], ["V4", "V5_high"]),
        "hidden_support": (["R1_low", "R2"], ["V4", "V5_high"]),
        "crowded": (["R1_low", "R2"], ["V1_low", "V2"]),
    }

    baseline_ics = []
    for year in TEST_YEARS:
        year_df = panel[panel["time"].dt.year == year]
        if len(year_df) >= MIN_YEAR_ROWS:
            ic = compute_ic(year_df["score_h413"], year_df[S1_TARGET_COL])
            if not np.isnan(ic):
                baseline_ics.append(ic)

    baseline_mean = np.mean(baseline_ics) if baseline_ics else np.nan
    print(f"\nBaseline: mean IC {baseline_mean:+.4f}")

    yearly_divergence_ic = {name: [] for name in divergence_states}

    for year in TEST_YEARS:
        year_df = panel[panel["time"].dt.year == year]
        if len(year_df) < MIN_YEAR_ROWS:
            continue

        for state_name, (ret_qs, vol_qs) in divergence_states.items():
            state_df = year_df[
                (year_df["return_quintile"].isin(ret_qs)) &
                (year_df["vol_z_quintile"].isin(vol_qs))
            ]
            if len(state_df) >= 50:
                ic = compute_ic(state_df["score_h413"], state_df[S1_TARGET_COL])
                if not np.isnan(ic):
                    yearly_divergence_ic[state_name].append(ic)

    print("\nIC by divergence state:")
    divergence_results = {}
    for state_name, ics in yearly_divergence_ic.items():
        if ics:
            mean_ic = np.mean(ics)
            lift = mean_ic - baseline_mean
            pos = sum(1 for x in ics if x > 0)
            print(f"  {state_name}: mean IC {mean_ic:+.4f} (lift {lift:+.4f}), {pos}/{len(ics)} pos")
            divergence_results[state_name] = {"mean_ic": float(mean_ic), "lift": float(lift), "pos_years": pos, "total": len(ics)}

    real_force_lift = divergence_results.get("real_force", {}).get("lift", 0)
    fade_lift = divergence_results.get("fade", {}).get("lift", 0)

    dev_years = list(range(2018, 2023))
    val_years = list(range(2023, 2026))

    val_real_force_ics = []
    val_fade_ics = []
    for year in val_years:
        year_df = panel[panel["time"].dt.year == year]
        rf_df = year_df[
            (year_df["return_quintile"].isin(["R4", "R5_high"])) &
            (year_df["vol_z_quintile"].isin(["V1_low", "V2"]))
        ]
        if len(rf_df) >= 50:
            ic = compute_ic(rf_df["score_h413"], rf_df[S1_TARGET_COL])
            if not np.isnan(ic):
                val_real_force_ics.append(ic)

        f_df = year_df[
            (year_df["return_quintile"].isin(["R4", "R5_high"])) &
            (year_df["vol_z_quintile"].isin(["V4", "V5_high"]))
        ]
        if len(f_df) >= 50:
            ic = compute_ic(f_df["score_h413"], f_df[S1_TARGET_COL])
            if not np.isnan(ic):
                val_fade_ics.append(ic)

    val_real_force = np.mean(val_real_force_ics) if val_real_force_ics else np.nan
    val_fade = np.mean(val_fade_ics) if val_fade_ics else np.nan

    print(f"\nValidation (2023-2025): real_force = {val_real_force:+.4f}, fade = {val_fade:+.4f}")

    if real_force_lift > 0.010 and (val_real_force - val_fade if not (np.isnan(val_real_force) or np.isnan(val_fade)) else 0) > 0.010:
        decision = "PASSED"
    elif real_force_lift > 0.005:
        decision = "MIXED"
    else:
        decision = "FAILED"

    print(f"\n=== VERDICT: {decision} ===")

    summary = {
        "decision": decision,
        "branch": BRANCH_NAME,
        "baseline_ic": float(baseline_mean),
        "divergence_results": divergence_results,
        "dev_years": dev_years,
        "val_years": val_years,
        "val_real_force_ic": float(val_real_force) if not np.isnan(val_real_force) else None,
        "val_fade_ic": float(val_fade) if not np.isnan(val_fade) else None,
    }

    out_path = ROOT / "artifacts" / "run_summaries" / f"h432_{BRANCH_NAME}_summary.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved: {out_path}")

    return decision


if __name__ == "__main__":
    run_experiment()