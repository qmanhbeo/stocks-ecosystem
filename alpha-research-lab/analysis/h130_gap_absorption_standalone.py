"""
H130 — Gap Absorption Asymmetry (Session 43)

Tests whether the market's intraday acceptance or rejection of the overnight gap
predicts next-day cross-sectional returns.

Signals tested:
1. xs_gap_absorb_1
2. xs_gap_absorb_2
3. xs_gap_absorb_3
4. xs_gap_reject_1

For any strongly negative raw feature, the sign-flipped orientation is also tested.

Usage:
    conda run -n stocks python analysis/h130_gap_absorption_standalone.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.run_summary import write_run_summary
from src.standalone_signal_utils import (
    PASS_IC,
    annotate_redundancy,
    evaluate_features,
    load_ohlcv_wide,
    load_s1_frame,
    rank_frame,
    safe_clv,
    to_long,
)


def build_features() -> pd.DataFrame:
    panels = load_ohlcv_wide(min_rows=80)
    high = panels["high"]
    low = panels["low"]
    open_ = panels["open"]
    close = panels["close"]

    gap = open_.div(close.shift(1)) - 1.0
    intraday = close.div(open_.replace(0, np.nan)) - 1.0
    clv = safe_clv(high, low, close)
    intraday_positive = (intraday > 0).astype(float)

    gap_absorb_1 = rank_frame(gap * clv)
    gap_absorb_2 = rank_frame(gap - intraday)
    gap_absorb_3 = rank_frame(gap * intraday_positive * clv)
    gap_reject_1 = rank_frame((-gap) * (1.0 - clv))

    feature_df = (
        to_long(gap_absorb_1, "xs_gap_absorb_1")
        .merge(to_long(gap_absorb_2, "xs_gap_absorb_2"), on=["time", "ticker"])
        .merge(to_long(gap_absorb_3, "xs_gap_absorb_3"), on=["time", "ticker"])
        .merge(to_long(gap_reject_1, "xs_gap_reject_1"), on=["time", "ticker"])
        .dropna(subset=["xs_gap_absorb_1"])
    )
    return feature_df


def add_inverted_features(merged: pd.DataFrame, results: dict[str, dict]) -> tuple[pd.DataFrame, list[str]]:
    added = []
    for feat, res in list(results.items()):
        if (res.get("avg_ic") or 0) < -PASS_IC:
            flipped = f"{feat}_inverted"
            merged[flipped] = 1.0 - merged[feat]
            added.append(flipped)
    return merged, added


def main():
    s1 = load_s1_frame()

    print("Loading OHLCV data for gap absorption...")
    feature_df = build_features()
    feature_df["time"] = pd.to_datetime(feature_df["time"])

    merged = s1.merge(feature_df, on=["time", "ticker"], how="inner")
    print(
        f"Merged rows: {len(merged):,}  tickers: {merged['ticker'].nunique()}  "
        f"dates: {merged['time'].nunique()}"
    )

    base_features = [
        "xs_gap_absorb_1",
        "xs_gap_absorb_2",
        "xs_gap_absorb_3",
        "xs_gap_reject_1",
    ]
    results = evaluate_features(merged, base_features)
    merged, inverted = add_inverted_features(merged, results)
    all_features = base_features + inverted
    if inverted:
        results.update(evaluate_features(merged, inverted))

    feature_cols = ["time", "ticker"] + all_features
    feature_eval_df = merged[feature_cols].copy()
    results = annotate_redundancy(feature_eval_df, results)

    final_passers = [col for col, res in results.items() if res.get("final_pass")]
    standalone_passers = [col for col, res in results.items() if res.get("gate_pass")]
    best_feat = max(all_features, key=lambda col: results[col].get("avg_ic") or -99)

    c4_overlap = {
        col: results[col].get("candidate_corrs", {}).get("c4_oc_asym_5d")
        for col in standalone_passers
    }

    if final_passers:
        verdict = "PASS"
        reason = f"Gap absorption passes: {', '.join(final_passers)}"
    elif standalone_passers:
        verdict = "REJECTED_AS_REDUNDANT"
        reason = (
            "Gap absorption passes standalone but overlaps existing candidates: "
            + ", ".join(
                f"{col} vs {results[col]['redundant_with']}" for col in standalone_passers
            )
        )
    else:
        verdict = "FAIL"
        reason = (
            f"No gap-absorption feature passes gate. Best: {best_feat} IC="
            f"{(results[best_feat].get('avg_ic') or 0):+.4f}."
        )

    summary = {
        "verdict": verdict,
        "reason": reason,
        "primary_feature": best_feat,
        "standalone_passing_features": standalone_passers,
        "final_passing_features": final_passers,
        "c4_overlap": c4_overlap,
        "features": results,
    }

    print("\nH130 GAP ABSORPTION RESULTS")
    print("=" * 72)
    print(f"Universe: {merged['ticker'].nunique()} tickers")
    print()
    print(
        f"  {'Feature':<28s}  {'IC':>7s}  {'Pos Yrs':>7s}  {'Corr S1':>8s}  "
        f"{'Corr C4':>8s}  Final"
    )
    for feat in all_features:
        res = results[feat]
        corr_c4 = res.get("candidate_corrs", {}).get("c4_oc_asym_5d")
        corr_c4_text = f"{corr_c4:+.3f}" if corr_c4 is not None and pd.notna(corr_c4) else "   n/a"
        final_state = "PASS" if res.get("final_pass") else ("dup" if res.get("gate_pass") else "fail")
        print(
            f"  {feat:<28s}  {(res.get('avg_ic') or 0):+.4f}  "
            f"{res['pos_years']:>2d}/{res['years']:<2d}   {res['corr_with_s1']:+.3f}   "
            f"{corr_c4_text:>8s}  {final_state}"
        )
    print(f"\nVerdict: {verdict}")
    print(f"Reason:  {reason}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    details_path = (
        REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h130_gap_absorption_details.json"
    )
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h130_gap_absorption",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"session": 43, "signal": "H130"},
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
