"""
H133 — Compression Blow-Off Reversal (Session 44)

Reinterprets H128's failed breakout-continuation features as exhaustion states.
If post-compression expansion is anti-predictive, the sign-flipped orientation
may capture blow-off reversal.

Signals tested:
1. xs_compress_blowoff_1 = 1 - xs_compress_breakout_1
2. xs_compress_blowoff_2 = 1 - xs_compress_breakout_2
3. xs_compress_blowoff_3 = 1 - xs_compress_breakout_3

Usage:
    conda run -n stocks python analysis/h133_compression_blowoff_reversal_standalone.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analysis.h128_compression_breakout_standalone import build_features as build_h128_features
from src.run_summary import write_run_summary
from src.standalone_signal_utils import annotate_redundancy, evaluate_features, load_s1_frame


def build_features() -> pd.DataFrame:
    feature_df = build_h128_features().copy()
    feature_df["xs_compress_blowoff_1"] = 1.0 - feature_df["xs_compress_breakout_1"]
    feature_df["xs_compress_blowoff_2"] = 1.0 - feature_df["xs_compress_breakout_2"]
    feature_df["xs_compress_blowoff_3"] = 1.0 - feature_df["xs_compress_breakout_3"]
    return feature_df[
        ["time", "ticker", "xs_compress_blowoff_1", "xs_compress_blowoff_2", "xs_compress_blowoff_3"]
    ]


def main():
    s1 = load_s1_frame()

    print("Loading OHLCV data for compression blow-off reversal...")
    feature_df = build_features()
    feature_df["time"] = pd.to_datetime(feature_df["time"])

    merged = s1.merge(feature_df, on=["time", "ticker"], how="inner")
    print(
        f"Merged rows: {len(merged):,}  tickers: {merged['ticker'].nunique()}  "
        f"dates: {merged['time'].nunique()}"
    )

    feature_cols = ["xs_compress_blowoff_1", "xs_compress_blowoff_2", "xs_compress_blowoff_3"]
    results = annotate_redundancy(feature_df, evaluate_features(merged, feature_cols))

    final_passers = [col for col, res in results.items() if res.get("final_pass")]
    standalone_passers = [col for col, res in results.items() if res.get("gate_pass")]
    best_feat = max(feature_cols, key=lambda col: results[col].get("avg_ic") or -99)

    if final_passers:
        verdict = "PASS"
        reason = f"Compression blow-off reversal passes: {', '.join(final_passers)}"
    elif standalone_passers:
        verdict = "REJECTED_AS_REDUNDANT"
        reason = (
            "Compression blow-off reversal passes standalone but overlaps existing candidates: "
            + ", ".join(
                f"{col} vs {results[col]['redundant_with']}" for col in standalone_passers
            )
        )
    else:
        verdict = "FAIL"
        reason = (
            f"No blow-off reversal feature passes gate. Best: {best_feat} IC="
            f"{(results[best_feat].get('avg_ic') or 0):+.4f}."
        )

    primary_feature = final_passers[0] if final_passers else best_feat

    summary = {
        "verdict": verdict,
        "reason": reason,
        "primary_feature": primary_feature,
        "standalone_passing_features": standalone_passers,
        "final_passing_features": final_passers,
        "features": results,
    }

    print("\nH133 COMPRESSION BLOW-OFF REVERSAL RESULTS")
    print("=" * 72)
    print(f"Universe: {merged['ticker'].nunique()} tickers")
    print()
    print(
        f"  {'Feature':<28s}  {'IC':>7s}  {'Pos Yrs':>7s}  {'Corr S1':>8s}  "
        f"{'Max Corr':>8s}  Final"
    )
    for feat in feature_cols:
        res = results[feat]
        max_corr = res.get("max_abs_candidate_corr")
        max_corr_text = f"{max_corr:+.3f}" if max_corr is not None else "   n/a"
        final_state = "PASS" if res.get("final_pass") else ("dup" if res.get("gate_pass") else "fail")
        print(
            f"  {feat:<28s}  {(res.get('avg_ic') or 0):+.4f}  "
            f"{res['pos_years']:>2d}/{res['years']:<2d}   {res['corr_with_s1']:+.3f}   "
            f"{max_corr_text:>8s}  {final_state}"
        )
    print(f"\nVerdict: {verdict}")
    print(f"Reason:  {reason}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    details_path = (
        REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h133_compression_blowoff_reversal_details.json"
    )
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h133_compression_blowoff_reversal",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"session": 44, "signal": "H133"},
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
