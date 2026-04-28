"""
H346: Residual long-horizon reversal after removing C11.

Question:
    H126 showed 90d/120d continuation is real but redundant with C11. Does the
    remaining 90d/120d residual, after removing C11's 60d continuation axis,
    work in the opposite direction as a distinct reversal signal?

Design:
    - compute the promoted C11-style 60d relative-strength rank
    - compute 90d and 120d relative-strength ranks
    - residualize 90d/120d ranks against C11 cross-sectionally each day
    - test the sign-flipped residuals plus continuation controls
    - keep the H126 standalone/redundancy gate

This resolves the old H137 queue idea without publishing a feature.
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
    cross_sectional_residual,
    evaluate_features,
    load_ohlcv_wide,
    load_s1_frame,
    load_vni_close,
    rank_frame,
    to_long,
)


FEATURE_COLS = [
    "xs_ret_90d_resid_c11_reversal_rank",
    "xs_ret_120d_resid_c11_reversal_rank",
    "xs_ret_90d_resid_c11_continuation_rank",
    "xs_ret_120d_resid_c11_continuation_rank",
]


def build_features() -> pd.DataFrame:
    panels = load_ohlcv_wide(min_rows=150)
    close = panels["close"]
    vni_close = load_vni_close()

    xs_60 = rank_frame(compute_excess_return(close, vni_close, periods=60)).shift(1)
    xs_90 = rank_frame(compute_excess_return(close, vni_close, periods=90)).shift(1)
    xs_120 = rank_frame(compute_excess_return(close, vni_close, periods=120)).shift(1)

    resid_90 = cross_sectional_residual(xs_90, xs_60)
    resid_120 = cross_sectional_residual(xs_120, xs_60)
    resid_90_rank = rank_frame(resid_90)
    resid_120_rank = rank_frame(resid_120)

    feature_df = (
        to_long(1.0 - resid_90_rank, "xs_ret_90d_resid_c11_reversal_rank")
        .merge(to_long(1.0 - resid_120_rank, "xs_ret_120d_resid_c11_reversal_rank"), on=["time", "ticker"])
        .merge(to_long(resid_90_rank, "xs_ret_90d_resid_c11_continuation_rank"), on=["time", "ticker"])
        .merge(to_long(resid_120_rank, "xs_ret_120d_resid_c11_continuation_rank"), on=["time", "ticker"])
        .dropna(subset=["xs_ret_90d_resid_c11_reversal_rank"])
    )
    feature_df["time"] = pd.to_datetime(feature_df["time"])
    return feature_df


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def main() -> int:
    print("Loading OHLCV data for residual long-horizon reversal...")
    s1 = load_s1_frame()
    feature_df = build_features()
    merged = s1.merge(feature_df, on=["time", "ticker"], how="inner")
    print(
        f"Merged rows: {len(merged):,}  tickers: {merged['ticker'].nunique()}  "
        f"dates: {merged['time'].nunique()}"
    )

    results = annotate_redundancy(feature_df, evaluate_features(merged, FEATURE_COLS))
    final_passers = [col for col, res in results.items() if res.get("final_pass")]
    standalone_passers = [col for col, res in results.items() if res.get("gate_pass")]
    best_feat = max(FEATURE_COLS, key=lambda col: results[col].get("avg_ic") or -99)

    if final_passers:
        verdict = "PASSED"
        reason = f"Residual long-horizon reversal passes final gate: {', '.join(final_passers)}"
    elif standalone_passers:
        verdict = "REJECTED_AS_REDUNDANT"
        reason = (
            "Residual long-horizon variants pass standalone but overlap existing candidates: "
            + ", ".join(f"{col} vs {results[col]['redundant_with']}" for col in standalone_passers)
        )
    else:
        verdict = "FAILED"
        reason = (
            f"No residual long-horizon reversal feature passes the standalone gate. Best: {best_feat} "
            f"IC={(results[best_feat].get('avg_ic') or 0):+.4f}."
        )

    summary = {
        "verdict": verdict,
        "reason": reason,
        "primary_feature": best_feat,
        "standalone_passing_features": standalone_passers,
        "final_passing_features": final_passers,
        "features": results,
        "merged_rows": int(len(merged)),
        "merged_tickers": int(merged["ticker"].nunique()),
        "merged_dates": int(merged["time"].nunique()),
    }

    print("\nH346 RESIDUAL LONG-HORIZON REVERSAL RESULTS")
    print("=" * 72)
    print(
        f"  {'Feature':<44s}  {'IC':>7s}  {'Pos Yrs':>7s}  {'Corr S1':>8s}  "
        f"{'Max Corr':>8s}  Final"
    )
    for feat in FEATURE_COLS:
        res = results[feat]
        max_corr = res.get("max_abs_candidate_corr")
        max_corr_text = f"{max_corr:+.3f}" if max_corr is not None else "   n/a"
        final_state = "PASS" if res.get("final_pass") else ("dup" if res.get("gate_pass") else "fail")
        print(
            f"  {feat:<44s}  {(res.get('avg_ic') or 0):+.4f}  "
            f"{res['pos_years']:>2d}/{res['years']:<2d}   {res['corr_with_s1']:+.3f}   "
            f"{max_corr_text:>8s}  {final_state}"
        )
    print(f"\nVerdict: {verdict}")
    print(f"Reason:  {reason}")

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    details_path = (
        REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h346_residual_long_horizon_reversal_details.json"
    )
    details_path.write_text(json.dumps(_json_safe(summary), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary_path = write_run_summary(
        ts=ts,
        mode="research_branch_residual_long_horizon_reversal",
        name="h346_residual_long_horizon_reversal",
        summary=summary,
        artifacts={"details_json": details_path},
        metadata={
            "resolves_queue_item": "H137 residual long-horizon reversal",
            "hypothesis": (
                "After removing C11's 60d continuation axis, the remaining 90d/120d "
                "relative-strength residual may reverse rather than continue."
            ),
            "protocol": "H126 standalone signal gate plus candidate-redundancy audit; 2026 excluded by S1 loader.",
        },
    )
    print(f"\nsummary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
