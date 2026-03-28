"""
H127 — Close-Location Persistence (Session 43)

Tests whether repeated closes near the high of the daily range capture unresolved
buying pressure better than raw return alone.

Signals tested:
1. xs_clv_5d_rank
2. xs_clv_10d_rank
3. xs_clv_posret_5d_rank
4. xs_clv_volconf_5d_rank

Usage:
    conda run -n stocks python analysis/h127_close_location_persistence_standalone.py
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
    compute_excess_return,
    compute_volume_zscore,
    evaluate_features,
    load_ohlcv_wide,
    load_s1_frame,
    load_vni_close,
    rank_frame,
    safe_clv,
    to_long,
    winsorize_by_row,
)


def build_features() -> pd.DataFrame:
    panels = load_ohlcv_wide(min_rows=80)
    high = panels["high"]
    low = panels["low"]
    close = panels["close"]
    volume = panels["volume"]
    vni_close = load_vni_close()

    clv = safe_clv(high, low, close)
    excess_ret1 = compute_excess_return(close, vni_close, periods=1)
    vol_zscore_1d = winsorize_by_row(compute_volume_zscore(volume))

    clv_5d = rank_frame(clv.rolling(5, min_periods=3).mean())
    clv_10d = rank_frame(clv.rolling(10, min_periods=5).mean())
    clv_posret_5d = rank_frame((clv * (excess_ret1 > 0).astype(float)).rolling(5, min_periods=3).mean())
    clv_volconf_5d = rank_frame((clv * vol_zscore_1d).rolling(5, min_periods=3).mean())

    feature_df = (
        to_long(clv_5d, "xs_clv_5d_rank")
        .merge(to_long(clv_10d, "xs_clv_10d_rank"), on=["time", "ticker"])
        .merge(to_long(clv_posret_5d, "xs_clv_posret_5d_rank"), on=["time", "ticker"])
        .merge(to_long(clv_volconf_5d, "xs_clv_volconf_5d_rank"), on=["time", "ticker"])
        .dropna(subset=["xs_clv_5d_rank"])
    )
    return feature_df


def main():
    s1 = load_s1_frame()

    print("Loading OHLCV data for close-location persistence...")
    feature_df = build_features()
    feature_df["time"] = pd.to_datetime(feature_df["time"])

    merged = s1.merge(feature_df, on=["time", "ticker"], how="inner")
    print(
        f"Merged rows: {len(merged):,}  tickers: {merged['ticker'].nunique()}  "
        f"dates: {merged['time'].nunique()}"
    )

    feature_cols = [
        "xs_clv_5d_rank",
        "xs_clv_10d_rank",
        "xs_clv_posret_5d_rank",
        "xs_clv_volconf_5d_rank",
    ]
    results = annotate_redundancy(feature_df, evaluate_features(merged, feature_cols))

    final_passers = [col for col, res in results.items() if res.get("final_pass")]
    standalone_passers = [col for col, res in results.items() if res.get("gate_pass")]
    best_feat = max(feature_cols, key=lambda col: results[col].get("avg_ic") or -99)

    if final_passers:
        verdict = "PASS"
        reason = f"Close-location persistence passes: {', '.join(final_passers)}"
    elif standalone_passers:
        verdict = "REJECTED_AS_REDUNDANT"
        reason = (
            "Close-location persistence passes standalone but overlaps existing candidates: "
            + ", ".join(
                f"{col} vs {results[col]['redundant_with']}" for col in standalone_passers
            )
        )
    else:
        verdict = "FAIL"
        reason = (
            f"No close-location feature passes gate. Best: {best_feat} IC="
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

    print("\nH127 CLOSE-LOCATION PERSISTENCE RESULTS")
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
        REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h127_close_location_persistence_details.json"
    )
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h127_close_location_persistence",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"session": 43, "signal": "H127"},
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
