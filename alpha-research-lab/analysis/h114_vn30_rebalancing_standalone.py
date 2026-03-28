"""
H114 — VN30 Rebalancing Proximity Signal (Session 39)

Tests whether cross-sectional proximity to the VN30 index liquidity boundary
has standalone predictive IC for next-day returns.

Mechanism: VN30 is rebalanced semi-annually (January/July). Stocks approaching
the top-30 trading-value boundary attract passive ETF tracking demand (VN30 ETF
manages ~$1B AUM). Stocks moving toward inclusion have consistent buying pressure
from index trackers who must pre-position before the formal rebalancing.

Features tested (from xs_vn30_rebalancing.parquet):
1. xs_vn30_rank_pctile    — liquidity rank (1 = most liquid = secure VN30 member)
2. xs_vn30_boundary_score — Gaussian proximity to rank-30 threshold
3. xs_vn30_rank_change_5d — 5d rank improvement (positive = approaching VN30)
4. xs_vn30_add_pressure   — composite: rank_change × boundary_score (addition candidates)

Target: actual (1-day barrier label from S1) — consistent with H93 evaluation.

Usage:
    conda run -n stocks python analysis/h114_vn30_rebalancing_standalone.py
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
VN30_PATH = REPO_ROOT / "data" / "features" / "xs_vn30_rebalancing.parquet"

FEATURES = [
    "xs_vn30_rank_pctile",
    "xs_vn30_boundary_score",
    "xs_vn30_rank_change_5d",
    "xs_vn30_add_pressure",
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

    vn30 = pd.read_parquet(VN30_PATH)
    vn30["time"] = pd.to_datetime(vn30["time"])

    merged = s1.merge(vn30, on=["time", "ticker"], how="inner")
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
            f"VN30 boundary signal passes gate. Passing: {', '.join(passing)}. "
            f"Liquidity-proximity effect is learnable as RL state feature."
        )
    else:
        verdict = "FAIL"
        reason = (
            f"No VN30 boundary feature passes gate. Best: {best_feat} IC={best_ic:.4f}. "
            f"Trading-value rank may proxy size/momentum rather than pure rebalancing effect."
        )

    summary = {
        "verdict": verdict,
        "reason": reason,
        "passing_features": passing,
        "features": results,
    }

    print("\nH114 VN30 REBALANCING PROXIMITY RESULTS")
    print("=" * 72)
    print(f"Universe: {merged['ticker'].nunique()} tickers")
    print()
    print(f"  {'Feature':<30s}  {'IC':>7s}  {'Pos Yrs':>7s}  {'Corr S1':>8s}  Gate")
    for feat in FEATURES:
        r = results.get(feat, {})
        if "error" in r:
            print(f"  {feat:<30s}  MISSING")
            continue
        ic_val = r.get("avg_ic") or 0
        print(
            f"  {feat:<30s}  {ic_val:+.4f}  {r['pos_years']:>2d}/{r['years']:<2d}   "
            f"{r['corr_with_s1']:+.3f}   {'PASS' if r['gate_pass'] else 'fail'}"
        )
    print(f"\nVerdict: {verdict}")
    print(f"Reason:  {reason}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    details_path = (
        REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h114_vn30_rebalancing_details.json"
    )
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h114_vn30_rebalancing",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"session": 39, "signal": "H114"},
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
