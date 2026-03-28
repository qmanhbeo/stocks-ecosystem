"""
C3 Dispersion Regime — Regime-Conditional IC Analysis (Session 37)

More rigorous standalone test for C3/H101 beyond Session 35's single-feature check.

Tests:
1. Day-level Spearman for all dispersion features vs S1 daily top-5 accuracy (extends S35 check)
2. Regime-conditional IC: split days into terciles by dispersion, compute S1 IC per regime
   - IC = Spearman(xs_proba, actual) — higher IC in high-dispersion regime means C3 is useful
3. Regime-conditional top-5 accuracy

RL verdict criteria:
- Regime IC spread (high vs low tercile) > 10% relative → C3 valuable as regime gate
- Day-level Spearman vs S1 top-5 accuracy, p < 0.10 → C3 directly predictive of strategy quality

Usage:
    conda run -n stocks python analysis/c3_dispersion_regime_ic_analysis.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.run_summary import write_run_summary

S1_PATH = REPO_ROOT / "data" / "features" / "xs_barrier_vol_1d_hose_full.parquet"
DISP_PATH = REPO_ROOT / "data" / "features" / "xs_dispersion_regime_daily.parquet"

# Dispersion features to test as regime signals
DISP_FEATURES = [
    "xs_dispersion_z20",
    "xs_ret_std_1d",
    "xs_breadth_up_1d",
    "xs_tail_spread_1d",
]

TOP_N = 5


def compute_daily_top5_accuracy(df: pd.DataFrame) -> pd.DataFrame:
    """Compute daily top-5 accuracy: fraction of top-5 picks with actual=1."""
    top5 = (
        df.sort_values(["time", "xs_proba"], ascending=[True, False])
        .groupby("time")
        .head(TOP_N)
        .groupby("time")["actual"]
        .mean()
        .rename("top5_acc")
        .reset_index()
    )
    return top5


def regime_ic(df: pd.DataFrame, feature: str) -> dict:
    """
    Split days into dispersion terciles, compute Spearman IC per tercile.

    IC = Spearman(xs_proba, actual) computed on all ticker-day pairs in each regime.
    """
    # Build day-level tercile labels
    day_disp = df[["time", feature]].drop_duplicates("time").copy()
    day_disp["tercile"] = pd.qcut(day_disp[feature], q=3, labels=["low", "mid", "high"])
    merged = df.merge(day_disp[["time", "tercile"]], on="time", how="inner")

    rows = {}
    for label in ["low", "mid", "high"]:
        g = merged[merged["tercile"] == label][["xs_proba", "actual"]].dropna()
        if len(g) < 200:
            rows[label] = {"ic": None, "n": len(g)}
            continue
        rho, p = spearmanr(g["xs_proba"], g["actual"])
        rows[label] = {"ic": float(rho), "p_value": float(p), "n": int(len(g))}

    low_ic = rows["low"]["ic"] if rows["low"]["ic"] is not None else float("nan")
    high_ic = rows["high"]["ic"] if rows["high"]["ic"] is not None else float("nan")
    spread = high_ic - low_ic
    relative_spread = (spread / abs(low_ic)) if abs(low_ic) > 1e-6 else float("nan")

    return {
        "terciles": rows,
        "ic_spread_high_minus_low": float(spread) if not np.isnan(spread) else None,
        "ic_relative_spread_pct": float(relative_spread * 100) if not np.isnan(relative_spread) else None,
    }


def daily_spearman_vs_top5(top5: pd.DataFrame, disp: pd.DataFrame, feature: str) -> dict:
    """Day-level Spearman between a dispersion feature and S1 daily top-5 accuracy."""
    merged = top5.merge(disp[["time", feature]], on="time", how="inner").dropna()
    if len(merged) < 100:
        return {"spearman": None, "p_value": None, "n_days": len(merged)}
    rho, p = spearmanr(merged[feature], merged["top5_acc"])
    return {"spearman": float(rho), "p_value": float(p), "n_days": int(len(merged))}


def main():
    s1 = pd.read_parquet(S1_PATH, columns=["time", "xs_proba", "actual"])
    s1["time"] = pd.to_datetime(s1["time"])

    disp_cols = ["time"] + DISP_FEATURES
    try:
        disp = pd.read_parquet(DISP_PATH, columns=disp_cols)
    except Exception:
        disp = pd.read_parquet(DISP_PATH)
    disp["time"] = pd.to_datetime(disp["time"])

    # Restrict to in-sample years (exclude 2026 per working rules)
    s1 = s1[s1["time"].dt.year <= 2025]

    top5 = compute_daily_top5_accuracy(s1)

    avail_feats = [f for f in DISP_FEATURES if f in disp.columns]
    merged_s1 = s1.merge(disp[["time"] + avail_feats], on="time", how="inner")

    results = {}

    for feat in avail_feats:
        results[feat] = {
            "regime_conditional_ic": regime_ic(merged_s1, feat),
            "daily_spearman_vs_top5": daily_spearman_vs_top5(top5, disp, feat),
        }

    # --- Verdict ---
    # Check xs_dispersion_z20 as primary feature (used in Session 35)
    primary = results.get("xs_dispersion_z20", {})
    regime = primary.get("regime_conditional_ic", {})
    spread_pct = regime.get("ic_relative_spread_pct")
    dsp = primary.get("daily_spearman_vs_top5", {})
    day_p = dsp.get("p_value")

    if spread_pct is not None and spread_pct > 10:
        verdict = "PASS"
        reason = f"Regime IC spread {spread_pct:.1f}% > 10% threshold — C3 is useful as RL regime gate"
    elif day_p is not None and day_p < 0.10:
        verdict = "PASS"
        reason = f"Day-level Spearman vs top-5 acc p={day_p:.3f} < 0.10 — C3 directly predictive"
    else:
        verdict = "FAIL"
        reason = (
            f"Regime IC spread {spread_pct:.1f}% <= 10% and "
            f"day-level p={day_p:.3f} >= 0.10 — C3 does not pass standalone RL gate"
            if spread_pct is not None and day_p is not None
            else "Insufficient data or missing features"
        )

    summary = {
        "verdict": verdict,
        "reason": reason,
        "primary_feature": "xs_dispersion_z20",
        "features": results,
    }

    print(json.dumps(summary, indent=2))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    details_path = (
        REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_c3_dispersion_regime_ic_details.json"
    )
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="c3_dispersion_regime_ic",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"session": 37, "signal": "C3"},
    )
    print(f"summary: {path}")


if __name__ == "__main__":
    main()
