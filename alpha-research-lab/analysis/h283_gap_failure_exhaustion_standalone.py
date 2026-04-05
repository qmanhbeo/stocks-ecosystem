"""
H283 — Gap-Failure Exhaustion.

Tests whether a failed gap-acceptance state becomes stronger when it occurs
inside the compression/blow-off regime from H133.

Design:
- start from the H130 gap-absorption state
- flip it into a gap-failure proxy
- gate it with the H133 compression blow-off state
- keep the test small and honest: one narrow combined family, no parameter sweep

Usage:
    conda run -n stocks python analysis/h283_gap_failure_exhaustion_standalone.py
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
    volume = panels["volume"]

    gap = open_.div(close.shift(1)) - 1.0
    intraday = close.div(open_.replace(0, np.nan)) - 1.0
    clv = safe_clv(high, low, close)
    intraday_positive = (intraday > 0).astype(float)

    range_pct = (high - low).div(close.shift(1))
    compress_10 = range_pct.rolling(10, min_periods=5).mean()
    compress_10_rank = 1.0 - rank_frame(compress_10)
    range_expansion = range_pct.div(range_pct.rolling(10, min_periods=5).mean())
    expansion_rank = rank_frame(range_expansion)
    close_rank = rank_frame(clv)
    vol_confirmation = volume.div(volume.rolling(20, min_periods=10).mean())
    vol_rank = rank_frame(vol_confirmation)

    # H133 state proxy: the sign-flipped compression / expansion / close / volume pattern.
    compress_blowoff_2 = 1.0 - rank_frame(compress_10_rank * expansion_rank * close_rank * vol_rank)

    # H130-inspired gap failure: a positive gap that fails to hold intraday and closes weak.
    gap_up = gap.clip(lower=0.0)
    gap_failure = rank_frame(gap_up * (1.0 - intraday_positive) * (1.0 - clv))

    # The actual branch hypothesis: failed gap acceptance becomes most interesting when the
    # stock is already in a compression blow-off regime.
    gap_failure_exhaustion_1 = rank_frame((1.0 - rank_frame(gap_up * intraday_positive * clv)) * compress_blowoff_2)
    gap_failure_exhaustion_2 = rank_frame(gap_failure * compress_blowoff_2)
    gap_failure_exhaustion_3 = rank_frame((1.0 - rank_frame(gap_up * clv)) * compress_blowoff_2)

    feature_df = (
        to_long(gap_failure_exhaustion_1, "xs_gap_failure_exhaustion_1")
        .merge(to_long(gap_failure_exhaustion_2, "xs_gap_failure_exhaustion_2"), on=["time", "ticker"])
        .merge(to_long(gap_failure_exhaustion_3, "xs_gap_failure_exhaustion_3"), on=["time", "ticker"])
        .dropna(subset=["xs_gap_failure_exhaustion_1"])
    )
    return feature_df


def main() -> None:
    s1 = load_s1_frame()

    print("Loading OHLCV data for gap-failure exhaustion...")
    feature_df = build_features()
    feature_df["time"] = pd.to_datetime(feature_df["time"])

    merged = s1.merge(feature_df, on=["time", "ticker"], how="inner")
    print(
        f"Merged rows: {len(merged):,}  tickers: {merged['ticker'].nunique()}  "
        f"dates: {merged['time'].nunique()}"
    )

    feature_cols = [
        "xs_gap_failure_exhaustion_1",
        "xs_gap_failure_exhaustion_2",
        "xs_gap_failure_exhaustion_3",
    ]
    results = annotate_redundancy(feature_df, evaluate_features(merged, feature_cols))

    final_passers = [col for col, res in results.items() if res.get("final_pass")]
    standalone_passers = [col for col, res in results.items() if res.get("gate_pass")]
    best_feat = max(feature_cols, key=lambda col: results[col].get("avg_ic") or -99)

    if final_passers:
        verdict = "PASS"
        reason = f"Gap-failure exhaustion passes: {', '.join(final_passers)}"
    elif standalone_passers:
        verdict = "REJECTED_AS_REDUNDANT"
        reason = (
            "Gap-failure exhaustion passes standalone but overlaps existing candidates: "
            + ", ".join(
                f"{col} vs {results[col]['redundant_with']}" for col in standalone_passers
            )
        )
    else:
        verdict = "FAIL"
        reason = (
            f"No gap-failure exhaustion feature passes gate. Best: {best_feat} IC="
            f"{(results[best_feat].get('avg_ic') or 0):+.4f}."
        )

    summary = {
        "verdict": verdict,
        "reason": reason,
        "primary_feature": best_feat,
        "standalone_passing_features": standalone_passers,
        "final_passing_features": final_passers,
        "features": results,
    }

    print("\nH283 GAP-FAILURE EXHAUSTION RESULTS")
    print("=" * 76)
    print(f"Universe: {merged['ticker'].nunique()} tickers")
    print()
    print(
        f"  {'Feature':<30s}  {'IC':>7s}  {'Pos Yrs':>7s}  {'Corr S1':>8s}  "
        f"{'Max Corr':>8s}  Final"
    )
    for feat in feature_cols:
        res = results[feat]
        max_corr = res.get("max_abs_candidate_corr")
        max_corr_text = f"{max_corr:+.3f}" if max_corr is not None else "   n/a"
        final_state = "PASS" if res.get("final_pass") else ("dup" if res.get("gate_pass") else "fail")
        print(
            f"  {feat:<30s}  {(res.get('avg_ic') or 0):+.4f}  "
            f"{res['pos_years']:>2d}/{res['years']:<2d}   {res['corr_with_s1']:+.3f}   "
            f"{max_corr_text:>8s}  {final_state}"
        )
    print(f"\nVerdict: {verdict}")
    print(f"Reason:  {reason}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    details_path = (
        REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h283_gap_failure_exhaustion_details.json"
    )
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h283_gap_failure_exhaustion",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"signal": "H283"},
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
