"""
H126 — Longer-Horizon Continuation (Session 44)

Extends C11 beyond 60d and checks whether sector-neutralized long-horizon
continuation survives after removing sector-level drift.

Signals tested:
1. xs_ret_90d_lag_rank
2. xs_ret_120d_lag_rank
3. xs_ret_90d_sector_neutral_rank
4. xs_ret_120d_sector_neutral_rank

Usage:
    conda run -n stocks python analysis/h126_long_horizon_continuation_standalone.py
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
    load_sector_labels,
    load_vni_close,
    rank_frame,
    to_long,
)


def sector_neutralize(wide_signal: pd.DataFrame, sector_map: pd.DataFrame) -> pd.DataFrame:
    long = to_long(wide_signal, "signal").merge(sector_map, on="ticker", how="left")
    long["sector_label"] = long["sector_label"].fillna("Other")
    long["signal_neutral"] = long["signal"] - long.groupby(["time", "sector_label"])["signal"].transform("mean")
    return long.pivot_table(index="time", columns="ticker", values="signal_neutral").sort_index()


def build_features() -> pd.DataFrame:
    panels = load_ohlcv_wide(min_rows=140)
    close = panels["close"]
    vni_close = load_vni_close()
    sector_map = load_sector_labels(level="icb_name3")

    excess_90 = compute_excess_return(close, vni_close, periods=90)
    excess_120 = compute_excess_return(close, vni_close, periods=120)
    excess_90_neutral = sector_neutralize(excess_90, sector_map)
    excess_120_neutral = sector_neutralize(excess_120, sector_map)

    xs_90 = rank_frame(excess_90).shift(1)
    xs_120 = rank_frame(excess_120).shift(1)
    xs_90_neutral = rank_frame(excess_90_neutral).shift(1)
    xs_120_neutral = rank_frame(excess_120_neutral).shift(1)

    feature_df = (
        to_long(xs_90, "xs_ret_90d_lag_rank")
        .merge(to_long(xs_120, "xs_ret_120d_lag_rank"), on=["time", "ticker"])
        .merge(to_long(xs_90_neutral, "xs_ret_90d_sector_neutral_rank"), on=["time", "ticker"])
        .merge(to_long(xs_120_neutral, "xs_ret_120d_sector_neutral_rank"), on=["time", "ticker"])
        .dropna(subset=["xs_ret_90d_lag_rank"])
    )
    return feature_df


def main():
    s1 = load_s1_frame()

    print("Loading OHLCV data for longer-horizon continuation...")
    feature_df = build_features()
    feature_df["time"] = pd.to_datetime(feature_df["time"])

    merged = s1.merge(feature_df, on=["time", "ticker"], how="inner")
    print(
        f"Merged rows: {len(merged):,}  tickers: {merged['ticker'].nunique()}  "
        f"dates: {merged['time'].nunique()}"
    )

    feature_cols = [
        "xs_ret_90d_lag_rank",
        "xs_ret_120d_lag_rank",
        "xs_ret_90d_sector_neutral_rank",
        "xs_ret_120d_sector_neutral_rank",
    ]
    results = annotate_redundancy(feature_df, evaluate_features(merged, feature_cols))

    final_passers = [col for col, res in results.items() if res.get("final_pass")]
    standalone_passers = [col for col, res in results.items() if res.get("gate_pass")]
    best_feat = max(feature_cols, key=lambda col: results[col].get("avg_ic") or -99)

    if final_passers:
        verdict = "PASS"
        reason = f"Longer-horizon continuation passes: {', '.join(final_passers)}"
    elif standalone_passers:
        verdict = "REJECTED_AS_REDUNDANT"
        reason = (
            "Longer-horizon continuation passes standalone but overlaps existing candidates: "
            + ", ".join(
                f"{col} vs {results[col]['redundant_with']}" for col in standalone_passers
            )
        )
    else:
        verdict = "FAIL"
        reason = (
            f"No longer-horizon continuation feature passes gate. Best: {best_feat} IC="
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

    print("\nH126 LONGER-HORIZON CONTINUATION RESULTS")
    print("=" * 72)
    print(f"Universe: {merged['ticker'].nunique()} tickers")
    print()
    print(
        f"  {'Feature':<32s}  {'IC':>7s}  {'Pos Yrs':>7s}  {'Corr S1':>8s}  "
        f"{'Max Corr':>8s}  Final"
    )
    for feat in feature_cols:
        res = results[feat]
        max_corr = res.get("max_abs_candidate_corr")
        max_corr_text = f"{max_corr:+.3f}" if max_corr is not None else "   n/a"
        final_state = "PASS" if res.get("final_pass") else ("dup" if res.get("gate_pass") else "fail")
        print(
            f"  {feat:<32s}  {(res.get('avg_ic') or 0):+.4f}  "
            f"{res['pos_years']:>2d}/{res['years']:<2d}   {res['corr_with_s1']:+.3f}   "
            f"{max_corr_text:>8s}  {final_state}"
        )
    print(f"\nVerdict: {verdict}")
    print(f"Reason:  {reason}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    details_path = (
        REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h126_long_horizon_continuation_details.json"
    )
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h126_long_horizon_continuation",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"session": 44, "signal": "H126"},
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
