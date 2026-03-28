"""
H107 — Overnight Gap Persistence Signal (Session 38)

Decomposes xs_open_close_asymmetry into overnight vs intraday components to find the
cleaner sub-signal. The overnight return (open_t / close_{t-1} - 1) reflects informed
auction activity using overnight information (US close, VNM ETF, global news) under
Vietnam's T+2 settlement structure.

Hypothesis: overnight_mom_5d (rolling 5d overnight return) has higher IC than the
combined oc_asym_5d, because it isolates the informed-auction component and discards
the noisy intraday mean-reversion.

Signals tested:
1. overnight_mom_5d   — primary: rolling 5d overnight return
2. intraday_mom_5d    — control: rolling 5d intraday return (open→close)
3. overnight_mom_20d  — longer window
4. intraday_mom_20d   — longer window control
5. overnight_aligned  — overnight_mom_5d * sign(intraday_mom_5d): both components agree
6. oc_asym_5d         — baseline (known IC +0.027, corr 0.147 with S1)

Target: actual (1-day barrier label) from S1 parquet — consistent with H93 evaluation.

Usage:
    conda run -n stocks python analysis/h107_overnight_standalone.py
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
OC_PATH = REPO_ROOT / "data" / "features" / "xs_open_close_asymmetry.parquet"

OC_FEATURES = [
    "overnight_mom_5d",
    "intraday_mom_5d",
    "overnight_mom_20d",
    "intraday_mom_20d",
    "oc_asym_5d",
    "oc_asym_20d",
    "gap_abs_5d",
]

PASS_IC = 0.01
PASS_CORR = 0.30
PASS_PCT_YEARS = 0.545  # >= 6/11


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


def gate_check(ic_summary: dict, corr: float) -> tuple[bool, str]:
    avg_ic = ic_summary.get("avg_ic") or 0
    pct_pos = ic_summary.get("pct_years_positive") or 0
    if avg_ic <= PASS_IC:
        return False, f"avg_ic {avg_ic:.4f} <= {PASS_IC}"
    if abs(corr) >= PASS_CORR:
        return False, f"|corr_with_s1| {abs(corr):.3f} >= {PASS_CORR}"
    if pct_pos < PASS_PCT_YEARS:
        return False, f"pct_years_positive {pct_pos:.2f} < {PASS_PCT_YEARS}"
    return True, "all gates passed"


def main():
    s1 = pd.read_parquet(S1_PATH)
    s1["time"] = pd.to_datetime(s1["time"])
    s1 = s1[s1["time"].dt.year <= 2025]

    oc = pd.read_parquet(OC_PATH, columns=["time", "ticker"] + OC_FEATURES)
    oc["time"] = pd.to_datetime(oc["time"])

    # Derive interaction signal: both overnight and intraday agree on direction
    oc["overnight_aligned"] = oc["overnight_mom_5d"] * np.sign(oc["intraday_mom_5d"])

    merged = s1.merge(oc, on=["time", "ticker"], how="inner")

    test_features = OC_FEATURES + ["overnight_aligned"]
    results = {}

    for feat in test_features:
        ic_rows = yearly_ic(merged, feat, "actual")
        ic_sum = summarize_ic(ic_rows)
        corr, _ = spearmanr(
            merged[feat].replace([np.inf, -np.inf], np.nan),
            merged["xs_proba"],
        )
        passed, reason = gate_check(ic_sum, corr)
        results[feat] = {
            **ic_sum,
            "corr_with_s1": float(corr),
            "gate_pass": passed,
            "gate_reason": reason,
        }

    # Primary verdict: overnight_mom_5d vs baseline oc_asym_5d
    primary = results["overnight_mom_5d"]
    baseline = results["oc_asym_5d"]

    improvement = None
    if primary["avg_ic"] is not None and baseline["avg_ic"] is not None:
        improvement = float(primary["avg_ic"] - baseline["avg_ic"])

    if primary["gate_pass"]:
        verdict = "PASS"
        reason = (
            f"overnight_mom_5d IC={primary['avg_ic']:.4f} passes all gates"
            + (f", improvement over oc_asym_5d: {improvement:+.4f}" if improvement is not None else "")
        )
    else:
        verdict = "FAIL"
        reason = f"overnight_mom_5d failed gate: {primary['gate_reason']}"

    # Check if any other feature passes
    passing = [f for f, r in results.items() if r["gate_pass"]]

    summary = {
        "verdict": verdict,
        "reason": reason,
        "primary_feature": "overnight_mom_5d",
        "baseline_feature": "oc_asym_5d",
        "overnight_vs_baseline_ic_delta": improvement,
        "passing_features": passing,
        "features": results,
    }

    print(json.dumps({k: v for k, v in summary.items() if k != "features"}, indent=2))
    print("\nPer-feature summary:")
    for feat, r in results.items():
        print(f"  {feat:30s}  IC={r['avg_ic'] or 0:.4f}  corr={r['corr_with_s1']:.3f}"
              f"  pos={r['pos_years']}/{r['years']}  {'PASS' if r['gate_pass'] else 'fail'}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    details_path = (
        REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h107_overnight_standalone_details.json"
    )
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h107_overnight_gap_persistence",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"session": 38, "signal": "H107", "hypothesis": "overnight_gap_persistence"},
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
