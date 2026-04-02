"""
H113 — Earnings Quality Cross-Sectional Signal at 394 Tickers (Session 39)

Extends H109 (52-ticker subset) to the full 394-ticker HOSE universe.
H109 found xs_roe_delta_rank IC = +0.0049 (8/11 years positive) at 52 tickers —
directionally consistent but below the IC > 0.01 gate due to insufficient coverage.

Hypothesis: At 394 tickers, the wider cross-section provides enough diversity to
separate high-quality earnings compounders from low-quality peers, lifting ICs above
the 0.01 threshold, particularly for roe_delta (QoQ ROE improvement).

Signals tested (same as H109):
1. xs_eps_accel_rank  — EPS acceleration (2nd derivative of YoY growth)
2. xs_eps_yoy_rank    — EPS YoY growth rank
3. xs_npm_trend_rank  — Net profit margin 3-quarter slope rank
4. xs_roe_delta_rank  — ROE quarter-over-quarter change rank (promising: 8/11 at 52T)
5. xs_debt_trend_rank — D/E ratio YoY change rank (lower growth = higher rank)

H109 baseline (52 tickers):
  xs_roe_delta_rank: IC = +0.0049, 8/11 positive
  xs_eps_accel_rank: IC = +0.0029, 7/11 positive
  xs_eps_yoy_rank:   IC = +0.0030, 7/11 positive

Usage:
    conda run -n stocks python analysis/h113_earnings_quality_394.py
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
EQ_PATH = data_path("features/xs_earnings_quality_daily.parquet")

FEATURES = [
    "xs_eps_accel_rank",
    "xs_eps_yoy_rank",
    "xs_npm_trend_rank",
    "xs_roe_delta_rank",
    "xs_debt_trend_rank",
]

# H109 52-ticker baseline for comparison
H109_BASELINE = {
    "xs_roe_delta_rank": {"ic": +0.0049, "pos_years": 8, "years": 11},
    "xs_eps_accel_rank": {"ic": +0.0029, "pos_years": 7, "years": 11},
    "xs_eps_yoy_rank":   {"ic": +0.0030, "pos_years": 7, "years": 11},
    "xs_npm_trend_rank": {"ic": -0.0033, "pos_years": 1, "years": 11},
    "xs_debt_trend_rank":{"ic": -0.0006, "pos_years": 6, "years": 11},
}

PASS_IC = 0.01
PASS_CORR = 0.30
PASS_PCT_YEARS = 0.545


def yearly_ic(df: pd.DataFrame, score_col: str, target_col: str = "actual") -> list[dict]:
    rows = []
    for y, g in df.groupby(df["time"].dt.year):
        gg = g[[score_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(gg) < 100:
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

    eq = pd.read_parquet(EQ_PATH)
    eq["time"] = pd.to_datetime(eq["time"])

    print(f"Earnings quality file: {len(eq):,} rows, {eq['ticker'].nunique()} tickers")

    merged = s1.merge(eq, on=["time", "ticker"], how="inner")
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
        h109_ic = H109_BASELINE.get(feat, {}).get("ic")
        ic_delta = (ic_sum["avg_ic"] - h109_ic) if (ic_sum["avg_ic"] is not None and h109_ic is not None) else None
        results[feat] = {
            **ic_sum,
            "corr_with_s1": corr,
            "gate_pass": passed,
            "h109_ic": h109_ic,
            "ic_delta_vs_h109": float(ic_delta) if ic_delta is not None else None,
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
            f"Earnings quality passes at 394 tickers. Passing: {', '.join(passing)}. "
            f"Universe expansion from 52 to {merged['ticker'].nunique()} tickers confirmed the signal."
        )
    else:
        verdict = "FAIL"
        reason = (
            f"No earnings quality feature passes gate at 394 tickers. "
            f"Best: {best_feat} IC={best_ic:.4f}. "
            f"Fundamental signals may require event-driven evaluation (earnings release days only)."
        )

    summary = {
        "verdict": verdict,
        "reason": reason,
        "universe_size": int(merged["ticker"].nunique()),
        "h109_universe_size": 52,
        "passing_features": passing,
        "features": results,
    }

    print("\nH113 EARNINGS QUALITY (394 TICKERS) RESULTS")
    print("=" * 72)
    print(f"Universe: {merged['ticker'].nunique()} tickers (H109 was 52)")
    print()
    print(f"  {'Feature':<25s}  {'IC':>7s}  {'H109_IC':>8s}  {'Delta':>7s}  {'Pos Yrs':>7s}  {'Corr S1':>8s}  Gate")
    for feat in FEATURES:
        r = results.get(feat, {})
        if "error" in r:
            print(f"  {feat:<25s}  MISSING")
            continue
        ic_val = r.get("avg_ic") or 0
        h109_ic = r.get("h109_ic") or 0
        delta = r.get("ic_delta_vs_h109") or 0
        print(
            f"  {feat:<25s}  {ic_val:+.4f}  {h109_ic:+.4f}   {delta:+.4f}  "
            f"{r['pos_years']:>2d}/{r['years']:<2d}   {r['corr_with_s1']:+.3f}   "
            f"{'PASS' if r['gate_pass'] else 'fail'}"
        )
    print(f"\nVerdict: {verdict}")
    print(f"Reason:  {reason}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    details_path = (
        REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h113_earnings_quality_394_details.json"
    )
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h113_earnings_quality_394",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={
            "session": 39,
            "signal": "H113",
            "universe_tickers": int(merged["ticker"].nunique()),
            "h109_universe_tickers": 52,
        },
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
