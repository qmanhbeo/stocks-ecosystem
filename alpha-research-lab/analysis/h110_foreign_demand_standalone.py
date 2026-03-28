"""
H110 — VNM ETF Foreign Demand Proxy (Session 38)

Tests whether the VNM ETF premium signal and stock foreign-affinity beta
yield a cross-sectional IC vs 1-day returns.

Signals tested:
1. xs_fa_signal        — primary: foreign_affinity_120d × vnm_premium_1d (interaction)
2. xs_fa_rank          — foreign affinity rank (static 120d rolling Spearman)
3. xs_foreign_affinity_120d  — raw affinity beta
4. xs_foreign_affinity_20d   — shorter-window affinity
5. xs_vnm_premium_1d   — date-level premium scalar (no stock differentiation)

Expected: xs_fa_signal should have higher IC on days when |vnm_premium_1d| > 1%
(the premium is large enough to actually signal foreign flow).

Target: actual (1-day barrier label from S1) — consistent with H93 evaluation.

Usage:
    conda run -n stocks python analysis/h110_foreign_demand_standalone.py
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
FD_PATH = REPO_ROOT / "data" / "features" / "xs_foreign_demand_daily.parquet"

FEATURES = [
    "xs_fa_signal",
    "xs_fa_rank",
    "xs_foreign_affinity_120d",
    "xs_foreign_affinity_20d",
    "xs_vnm_premium_1d",
]

PASS_IC = 0.01
PASS_CORR = 0.30
PASS_PCT_YEARS = 0.545
STRONG_PREMIUM_THRESHOLD = 0.01  # |vnm_premium| > 1%


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

    fd = pd.read_parquet(FD_PATH)
    fd["time"] = pd.to_datetime(fd["time"])

    merged = s1.merge(fd, on=["time", "ticker"], how="inner")

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

    # Conditional IC: high premium days vs low premium days for xs_fa_signal
    high_prem = merged[merged["xs_vnm_premium_1d"].abs() > STRONG_PREMIUM_THRESHOLD]
    low_prem = merged[merged["xs_vnm_premium_1d"].abs() <= STRONG_PREMIUM_THRESHOLD]
    conditional = {}
    if len(high_prem) > 1000 and "xs_fa_signal" in merged.columns:
        ic_rows_high = yearly_ic(high_prem, "xs_fa_signal")
        ic_rows_low = yearly_ic(low_prem, "xs_fa_signal")
        conditional = {
            "high_premium_days": {
                "n_rows": int(len(high_prem)),
                **summarize_ic(ic_rows_high),
            },
            "low_premium_days": {
                "n_rows": int(len(low_prem)),
                **summarize_ic(ic_rows_low),
            },
            "threshold": STRONG_PREMIUM_THRESHOLD,
        }

    passing = [f for f, r in results.items() if r.get("gate_pass")]
    primary = results.get("xs_fa_signal", {})
    primary_ic = primary.get("avg_ic") or 0

    if primary.get("gate_pass"):
        verdict = "PASS"
        reason = f"xs_fa_signal IC={primary_ic:.4f} passes all gates"
    elif passing:
        verdict = "PASS"
        reason = f"Gate passed by: {', '.join(passing)}"
    else:
        verdict = "FAIL"
        reason = f"No feature passes gate. Best: xs_fa_signal IC={primary_ic:.4f}"

    summary = {
        "verdict": verdict,
        "reason": reason,
        "primary_feature": "xs_fa_signal",
        "passing_features": passing,
        "conditional_ic_by_premium_regime": conditional,
        "features": results,
    }

    print("\nH110 VNM ETF FOREIGN DEMAND RESULTS")
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
    if conditional:
        hi = conditional["high_premium_days"]
        lo = conditional["low_premium_days"]
        print(f"\n  Conditional IC (xs_fa_signal):")
        print(f"    High premium (|prem|>{STRONG_PREMIUM_THRESHOLD:.0%}): "
              f"IC={hi.get('avg_ic') or 0:+.4f}  n={hi['n_rows']:,}")
        print(f"    Low premium:  IC={lo.get('avg_ic') or 0:+.4f}  n={lo['n_rows']:,}")
    print(f"\nVerdict: {verdict}")
    print(f"Reason:  {reason}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    details_path = REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h110_foreign_demand_details.json"
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h110_foreign_demand",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"session": 38, "signal": "H110"},
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
