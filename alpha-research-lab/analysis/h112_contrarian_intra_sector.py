"""
H112 — Contrarian Intra-Sector Signal (Session 39)

H111 found that xs_intra_sector_rank (leaders within hot sectors) is strongly
anti-predictive: IC = −0.047, 0/11 years positive. This experiment tests whether
FLIPPING the signal — buying laggards in hot sectors — creates a positive signal.

Hypothesis: intra-sector mean reversion dominates sector herding in Vietnam's
T+2-settlement, ±7%-limit market. Stocks that have underperformed their sector
peers over 5d are more likely to bounce (relative to VNINDEX) next day.

Signals tested:
1. contrarian_intra_5d  — sector_mom_5d_rank × (1 − xs_intra_sector_rank)
   Buy the laggard in the hot sector (sector leader + intra-sector contrarian)
2. contrarian_intra_20d — sector_mom_20d_rank × (1 − xs_intra_sector_rank)
   Same using 20d sector momentum
3. reverse_intra        — 1 − xs_intra_sector_rank
   Pure intra-sector contrarian, no sector conditioning
4. xs_sector_breadth_5d — re-confirm from H111 (8/11 years, IC +0.014)

Target: actual (1-day barrier label from S1) — consistent with H93 evaluation.

Usage:
    conda run -n stocks python analysis/h112_contrarian_intra_sector.py
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
SECTOR_PATH = REPO_ROOT / "data" / "features" / "xs_sector_rotation_daily.parquet"

PASS_IC = 0.01
PASS_CORR = 0.30
PASS_PCT_YEARS = 0.60

# Baseline ICs from H111 (for reference)
H111_RESULTS = {
    "xs_sector_breadth_5d": {"ic": +0.0143, "pos_years": 8, "years": 11},
    "xs_intra_sector_rank": {"ic": -0.0466, "pos_years": 0, "years": 11},
    "xs_sector_rotation_signal": {"ic": -0.0379, "pos_years": 0, "years": 11},
}


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

    sector = pd.read_parquet(SECTOR_PATH)
    sector["time"] = pd.to_datetime(sector["time"])

    # Compute contrarian features on the fly
    sector["contrarian_intra_5d"] = (
        sector["xs_sector_mom_5d_rank"] * (1.0 - sector["xs_intra_sector_rank"])
    )
    sector["contrarian_intra_20d"] = (
        sector["xs_sector_mom_20d_rank"] * (1.0 - sector["xs_intra_sector_rank"])
    )
    sector["reverse_intra"] = 1.0 - sector["xs_intra_sector_rank"]

    merged = s1.merge(sector, on=["time", "ticker"], how="inner")
    print(
        f"Merged rows: {len(merged):,}  tickers: {merged['ticker'].nunique()}  "
        f"dates: {merged['time'].nunique()}"
    )

    features = [
        "contrarian_intra_5d",
        "contrarian_intra_20d",
        "reverse_intra",
        "xs_sector_breadth_5d",  # re-confirm H111 pass
    ]

    results = {}
    for feat in features:
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
    primary_ic = (results.get("contrarian_intra_5d") or {}).get("avg_ic") or 0

    if "contrarian_intra_5d" in passing:
        verdict = "PASS"
        reason = f"contrarian_intra_5d IC={primary_ic:+.4f} passes all gates (intra-sector mean reversion confirmed)"
    elif passing:
        verdict = "PASS"
        reason = f"Gate passed by: {', '.join(passing)}"
    else:
        verdict = "FAIL"
        reason = (
            f"No contrarian intra-sector feature passes gate. "
            f"contrarian_intra_5d IC={primary_ic:+.4f}. "
            f"Intra-sector mean reversion not strong enough for standalone signal."
        )

    summary = {
        "verdict": verdict,
        "reason": reason,
        "primary_feature": "contrarian_intra_5d",
        "h111_baseline": H111_RESULTS,
        "passing_features": passing,
        "features": results,
    }

    print("\nH112 CONTRARIAN INTRA-SECTOR RESULTS")
    print("=" * 72)
    print(f"Universe: {merged['ticker'].nunique()} tickers")
    print()
    print(f"  {'Feature':<30s}  {'IC':>7s}  {'Pos Yrs':>7s}  {'Corr S1':>8s}  Gate")
    for feat in features:
        r = results.get(feat, {})
        if "error" in r:
            print(f"  {feat:<30s}  MISSING")
            continue
        ic_val = r.get("avg_ic") or 0
        print(
            f"  {feat:<30s}  {ic_val:+.4f}  {r['pos_years']:>2d}/{r['years']:<2d}   "
            f"{r['corr_with_s1']:+.3f}   {'PASS' if r['gate_pass'] else 'fail'}"
        )
    print()
    print("H111 baselines for reference:")
    for feat, info in H111_RESULTS.items():
        print(f"  {feat:<30s}  {info['ic']:+.4f}  {info['pos_years']:>2d}/{info['years']:<2d}")
    print(f"\nVerdict: {verdict}")
    print(f"Reason:  {reason}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    details_path = (
        REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h112_contrarian_intra_details.json"
    )
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h112_contrarian_intra_sector",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"session": 39, "signal": "H112"},
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
