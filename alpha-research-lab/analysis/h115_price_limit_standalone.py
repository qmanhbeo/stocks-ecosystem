"""
H115 — Price Limit (Ceiling/Floor) Frequency Signal (Session 39)

Vietnamese stocks have ±7% daily price limits. When a stock hits the ceiling
(+7% from prev_close), demand overwhelmed all available supply — the true
equilibrium price was higher than the allowed close. When it hits the floor,
distressed selling truncated further downside.

Hypotheses:
1. Recent ceiling touches predict next-day continuation (pent-up demand)
2. Recent floor touches predict next-day continuation (continued distress)
   OR reversal (oversold bounce)
3. Net limit pressure (ceiling - floor) predicts direction

Signals tested:
1. xs_ceiling_count_5d  — ceiling touch count rank (5d window)
2. xs_floor_count_5d    — floor touch count rank (5d window)
3. xs_ceiling_count_20d — ceiling touch count rank (20d window)
4. xs_limit_net_5d      — net ceiling-floor pressure rank (5d)

Target: actual (1-day barrier label from S1) — consistent with H93 evaluation.

Usage:
    conda run -n stocks python analysis/h115_price_limit_standalone.py
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
LIMIT_PATH = data_path("features/xs_price_limit_daily.parquet")

FEATURES = [
    "xs_ceiling_count_5d",
    "xs_floor_count_5d",
    "xs_ceiling_count_20d",
    "xs_floor_count_20d",
    "xs_limit_net_5d",
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

    limit_df = pd.read_parquet(LIMIT_PATH)
    limit_df["time"] = pd.to_datetime(limit_df["time"])

    merged = s1.merge(limit_df, on=["time", "ticker"], how="inner")
    print(
        f"Merged rows: {len(merged):,}  tickers: {merged['ticker'].nunique()}  "
        f"dates: {merged['time'].nunique()}"
    )

    # Print base rate of limit touches in merged dataset
    if "xs_ceiling_count_5d" in merged.columns:
        ceil_any = (merged["xs_ceiling_count_5d"] > 0.5).mean()
        floor_any = (merged["xs_floor_count_5d"] > 0.5).mean()
        print(f"  Ceiling count > median: {100*ceil_any:.1f}% of rows")
        print(f"  Floor count > median:   {100*floor_any:.1f}% of rows")

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
        reason = f"Passing features: {', '.join(passing)}"
    else:
        verdict = "FAIL"
        reason = (
            f"No price-limit feature passes gate. Best: {best_feat} IC={best_ic:.4f}. "
            f"Price limit touches may not predict next-day direction reliably."
        )

    summary = {
        "verdict": verdict,
        "reason": reason,
        "passing_features": passing,
        "features": results,
    }

    print("\nH115 PRICE LIMIT REVERSAL/CONTINUATION RESULTS")
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
        REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h115_price_limit_details.json"
    )
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h115_price_limit",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"session": 39, "signal": "H115"},
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
