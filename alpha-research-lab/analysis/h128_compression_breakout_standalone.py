"""
H128 — Compression-Then-Expansion Breakout (Session 43)

Tests whether a stock emerging from multi-day range compression with expansion,
strong close, and volume confirmation predicts next-day continuation.

Signals tested:
1. xs_compress_breakout_1
2. xs_compress_breakout_2
3. xs_compress_breakout_3

Usage:
    conda run -n stocks python analysis/h128_compression_breakout_standalone.py
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

from src.run_summary import write_run_summary
from src.standalone_signal_utils import (
    annotate_redundancy,
    compute_excess_return,
    evaluate_features,
    load_ohlcv_wide,
    load_s1_frame,
    load_vni_close,
    rank_frame,
    safe_clv,
    to_long,
)


def build_features() -> pd.DataFrame:
    panels = load_ohlcv_wide(min_rows=80)
    high = panels["high"]
    low = panels["low"]
    close = panels["close"]
    volume = panels["volume"]
    vni_close = load_vni_close()

    range_pct = (high - low).div(close.shift(1))
    compress_5 = range_pct.rolling(5, min_periods=3).mean()
    compress_10 = range_pct.rolling(10, min_periods=5).mean()
    range_expansion = range_pct.div(range_pct.rolling(10, min_periods=5).mean())
    close_strength = safe_clv(high, low, close)
    vol_confirmation = volume.div(volume.rolling(20, min_periods=10).mean())
    breakout_ret = compute_excess_return(close, vni_close, periods=1).clip(lower=0)

    compress_5_rank = 1.0 - rank_frame(compress_5)
    compress_10_rank = 1.0 - rank_frame(compress_10)
    expansion_rank = rank_frame(range_expansion)
    close_rank = rank_frame(close_strength)
    vol_rank = rank_frame(vol_confirmation)
    breakout_rank = rank_frame(breakout_ret)

    breakout_1 = rank_frame(compress_5_rank * expansion_rank * close_rank)
    breakout_2 = rank_frame(compress_10_rank * expansion_rank * close_rank * vol_rank)
    breakout_3 = rank_frame(compress_10_rank * breakout_rank * close_rank)

    feature_df = (
        to_long(breakout_1, "xs_compress_breakout_1")
        .merge(to_long(breakout_2, "xs_compress_breakout_2"), on=["time", "ticker"])
        .merge(to_long(breakout_3, "xs_compress_breakout_3"), on=["time", "ticker"])
        .dropna(subset=["xs_compress_breakout_1"])
    )
    return feature_df


def main():
    s1 = load_s1_frame()

    print("Loading OHLCV data for compression breakout...")
    feature_df = build_features()
    feature_df["time"] = pd.to_datetime(feature_df["time"])

    merged = s1.merge(feature_df, on=["time", "ticker"], how="inner")
    print(
        f"Merged rows: {len(merged):,}  tickers: {merged['ticker'].nunique()}  "
        f"dates: {merged['time'].nunique()}"
    )

    feature_cols = [
        "xs_compress_breakout_1",
        "xs_compress_breakout_2",
        "xs_compress_breakout_3",
    ]
    results = annotate_redundancy(feature_df, evaluate_features(merged, feature_cols))

    final_passers = [col for col, res in results.items() if res.get("final_pass")]
    standalone_passers = [col for col, res in results.items() if res.get("gate_pass")]
    best_feat = max(feature_cols, key=lambda col: results[col].get("avg_ic") or -99)

    if final_passers:
        verdict = "PASS"
        reason = f"Compression-breakout state passes: {', '.join(final_passers)}"
    elif standalone_passers:
        verdict = "REJECTED_AS_REDUNDANT"
        reason = (
            "Compression-breakout state passes standalone but overlaps existing candidates: "
            + ", ".join(
                f"{col} vs {results[col]['redundant_with']}" for col in standalone_passers
            )
        )
    else:
        verdict = "FAIL"
        reason = (
            f"No compression-breakout feature passes gate. Best: {best_feat} IC="
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

    print("\nH128 COMPRESSION BREAKOUT RESULTS")
    print("=" * 72)
    print(f"Universe: {merged['ticker'].nunique()} tickers")
    print()
    print(
        f"  {'Feature':<26s}  {'IC':>7s}  {'Pos Yrs':>7s}  {'Corr S1':>8s}  "
        f"{'Max Corr':>8s}  Final"
    )
    for feat in feature_cols:
        res = results[feat]
        max_corr = res.get("max_abs_candidate_corr")
        max_corr_text = f"{max_corr:+.3f}" if max_corr is not None else "   n/a"
        final_state = "PASS" if res.get("final_pass") else ("dup" if res.get("gate_pass") else "fail")
        print(
            f"  {feat:<26s}  {(res.get('avg_ic') or 0):+.4f}  "
            f"{res['pos_years']:>2d}/{res['years']:<2d}   {res['corr_with_s1']:+.3f}   "
            f"{max_corr_text:>8s}  {final_state}"
        )
    print(f"\nVerdict: {verdict}")
    print(f"Reason:  {reason}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    details_path = (
        REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h128_compression_breakout_details.json"
    )
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h128_compression_breakout",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"session": 43, "signal": "H128"},
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
