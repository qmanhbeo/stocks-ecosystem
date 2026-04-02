"""
H111 — Sector Rotation with Intra-Sector Leadership (Session 38)

Tests whether the composite sector-rotation signal (sector momentum × intra-sector rank)
outperforms the standalone sector momentum rank (known IC = +0.013, 8/12 years).

The core thesis: buy the leading stock in the leading sector. In Vietnam's retail-dominated
market, sector herding propagates from sector-level momentum to individual stocks.

Signals tested:
1. xs_sector_rotation_signal  — primary: xs_sector_mom_5d_rank * xs_intra_sector_rank
2. xs_sector_mom_5d_rank      — sector-level momentum (5d), cross-sector percentile
3. xs_sector_mom_20d_rank     — sector-level momentum (20d), cross-sector percentile
4. xs_intra_sector_rank       — stock's rank within its own sector (5d excess)
5. xs_sector_breadth_5d       — fraction of sector stocks with positive excess return
6. xs_sector_accel            — fresh vs stale sector momentum

Target: actual (1-day barrier label from S1) — consistent with H93 evaluation.

Usage:
    conda run -n stocks python analysis/h111_sector_rotation_standalone.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from path_utils import data_path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.run_summary import write_run_summary

S1_PATH = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
SECTOR_PATH = data_path("features/xs_sector_rotation_daily.parquet")

FEATURES = [
    "xs_sector_rotation_signal",
    "xs_sector_mom_5d_rank",
    "xs_sector_mom_20d_rank",
    "xs_intra_sector_rank",
    "xs_sector_breadth_5d",
    "xs_sector_accel",
]

# Known baseline from exploration (sector 20d rank IC)
BASELINE_IC = 0.013
PASS_IC = 0.01
PASS_CORR = 0.30
PASS_PCT_YEARS = 0.545


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

    merged = s1.merge(sector, on=["time", "ticker"], how="inner")

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

    primary = results.get("xs_sector_rotation_signal", {})
    primary_ic = primary.get("avg_ic") or 0
    improvement = primary_ic - BASELINE_IC

    passing = [f for f, r in results.items() if r.get("gate_pass")]

    if primary.get("gate_pass"):
        verdict = "PASS"
        reason = (
            f"xs_sector_rotation_signal IC={primary_ic:.4f} passes all gates"
            + (f", improvement over standalone sector rank: {improvement:+.4f}" if improvement else "")
        )
    elif passing:
        verdict = "PASS"
        reason = f"Gate passed by: {', '.join(passing)}"
    else:
        verdict = "FAIL"
        reason = (
            f"No feature passes gate. xs_sector_rotation_signal IC={primary_ic:.4f}"
            + (f" (delta vs baseline {BASELINE_IC}: {improvement:+.4f})" if True else "")
        )

    summary = {
        "verdict": verdict,
        "reason": reason,
        "primary_feature": "xs_sector_rotation_signal",
        "baseline_ic": BASELINE_IC,
        "rotation_signal_ic": primary_ic,
        "ic_improvement_over_baseline": float(improvement),
        "passing_features": passing,
        "features": results,
    }

    print("\nH111 SECTOR ROTATION RESULTS")
    print("=" * 72)
    for feat in FEATURES:
        r = results.get(feat, {})
        if "error" in r:
            print(f"  {feat:35s}  MISSING")
            continue
        ic_val = r.get("avg_ic") or 0
        print(
            f"  {feat:35s}  IC={ic_val:+.4f}  pos={r['pos_years']}/{r['years']}"
            f"  corr={r['corr_with_s1']:+.3f}  {'PASS' if r['gate_pass'] else 'fail'}"
        )
    print(f"\nVerdict: {verdict}")
    print(f"Reason:  {reason}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    details_path = REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h111_sector_rotation_details.json"
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h111_sector_rotation",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"session": 38, "signal": "H111", "baseline_ic": BASELINE_IC},
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
