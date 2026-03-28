"""
H116 — Volume Activity Cross-Sectional Signal (Session 39)

Tests whether abnormal volume relative to a stock's 60d baseline has standalone
cross-sectional IC. The H93 XGBoost model already uses volume features internally
(H90 showed volume features improve the combined model), but their standalone
predictive power — and independence from xs_proba — has not been tested.

Hypothesis: Stocks with unusually high volume relative to their own history attract
disproportionate investor attention, creating momentum that carries into next day.
Cross-sectional rank normalizes away the overall market volume environment.

Signals tested:
1. xs_vol_zscore_1d   — 1d volume zscore (vs 60d baseline), cross-sectional rank
2. xs_vol_zscore_5d   — 5d average volume zscore, cross-sectional rank
3. xs_value_zscore_5d — 5d trading value zscore, cross-sectional rank
4. xs_vol_surge_5d    — fraction of past 5d with volume > 1.5× baseline, rank

Target: actual (1-day barrier label from S1) — consistent with H93 evaluation.

Usage:
    conda run -n stocks python analysis/h116_volume_zscore_standalone.py
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
VOL_PATH = REPO_ROOT / "data" / "features" / "xs_volume_zscore_daily.parquet"

FEATURES = [
    "xs_vol_zscore_1d",
    "xs_vol_zscore_5d",
    "xs_value_zscore_5d",
    "xs_vol_surge_5d",
]

PASS_IC = 0.01
PASS_CORR = 0.30
PASS_PCT_YEARS = 0.60


def yearly_ic(df: pd.DataFrame, score_col: str, target_col: str = "actual") -> list[dict]:
    rows = []
    for y, g in df.groupby(df["time"].dt.year):
        gg = g[[score_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(gg) < 500:
            continue
        rho, p = spearmanr(gg[score_col], gg[target_col])
        rows.append({"year": int(y), "n": int(len(gg)), "ic": float(rho), "p_value": float(p)})
    return rows


def summarize_ic(rows: list[dict]) -> dict:
    if not rows:
        return {"avg_ic": None, "pos_years": 0, "years": 0, "pct_years_positive": None}
    ics = [r["ic"] for r in rows]
    pos = sum(1 for ic in ics if ic > 0)
    return {
        "avg_ic": float(np.mean(ics)),
        "pos_years": pos,
        "years": len(rows),
        "pct_years_positive": float(pos / len(rows)),
        "yearly": rows,
    }


def main():
    s1 = pd.read_parquet(S1_PATH)
    s1["time"] = pd.to_datetime(s1["time"])
    s1 = s1[s1["time"].dt.year <= 2025]

    vol_df = pd.read_parquet(VOL_PATH)
    vol_df["time"] = pd.to_datetime(vol_df["time"])

    merged = s1.merge(vol_df, on=["time", "ticker"], how="inner")
    print(
        f"Merged rows: {len(merged):,}  tickers: {merged['ticker'].nunique()}  "
        f"dates: {merged['time'].nunique()}"
    )

    results = {}
    for feat in FEATURES:
        if feat not in merged.columns:
            results[feat] = {"error": "column missing"}
            continue
        ic_rows = yearly_ic(merged, feat)
        ic_sum = summarize_ic(ic_rows)
        clean = merged[[feat, "xs_proba"]].replace([np.inf, -np.inf], np.nan).dropna()
        corr = float(spearmanr(clean[feat], clean["xs_proba"])[0]) if len(clean) > 100 else float("nan")
        passed = (
            (ic_sum["avg_ic"] or 0) > PASS_IC
            and abs(corr) < PASS_CORR
            and (ic_sum["pct_years_positive"] or 0) >= PASS_PCT_YEARS
        )
        results[feat] = {
            **ic_sum,
            "corr_with_s1": corr,
            "gate_pass": passed,
        }

    passing = [f for f, r in results.items() if r.get("gate_pass")]
    best_feat = max(
        (f for f in results if "error" not in results[f]),
        key=lambda f: results[f].get("avg_ic") or -99,
        default=None,
    )
    best_ic = results[best_feat].get("avg_ic") or 0 if best_feat else 0

    if passing:
        verdict = "PASS"
        reason = (
            f"Volume activity signal passes gate. Passing: {', '.join(passing)}. "
            f"Note: S1 (xs_proba) already incorporates volume signals — correlation check is critical."
        )
    else:
        verdict = "FAIL"
        reason = (
            f"No volume zscore feature passes gate. Best: {best_feat} IC={best_ic:.4f}. "
            f"Volume signal may already be captured by S1 (H90 showed IC improvement via combined model)."
        )

    summary = {
        "verdict": verdict,
        "reason": reason,
        "passing_features": passing,
        "note": "S1 model already uses volume features internally. Check correlation with xs_proba.",
        "features": results,
    }

    print("\nH116 VOLUME ACTIVITY CROSS-SECTIONAL RESULTS")
    print("=" * 72)
    print(f"Universe: {merged['ticker'].nunique()} tickers")
    print()
    print(f"  {'Feature':<28s}  {'IC':>7s}  {'Pos Yrs':>7s}  {'Corr S1':>8s}  Gate")
    for feat in FEATURES:
        r = results.get(feat, {})
        if "error" in r:
            print(f"  {feat:<28s}  MISSING")
            continue
        ic_val = r.get("avg_ic") or 0
        print(
            f"  {feat:<28s}  {ic_val:+.4f}  {r['pos_years']:>2d}/{r['years']:<2d}   "
            f"{r['corr_with_s1']:+.3f}   {'PASS' if r['gate_pass'] else 'fail'}"
        )
    print(f"\nVerdict: {verdict}")
    print(f"Reason:  {reason}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    details_path = (
        REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h116_volume_zscore_details.json"
    )
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h116_volume_zscore",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"session": 39, "signal": "H116"},
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
