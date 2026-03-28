"""
H125 — Orthogonalized Beta Residual (Session 43)

Tests whether rolling 60d beta contains a distinct cross-sectional edge once the
illiquidity and abnormal-volume components are removed.

Hypothesis:
- Raw beta collapsed onto C10 in H124.
- The residual beta axis may still matter if we strip out the illiquidity/attention
  components that dominate simple low-beta behavior.

Signals tested:
1. xs_beta_resid_60d_rank  — residualized beta rank
2. xs_low_beta_resid_60d   — 1 - residualized beta rank

Usage:
    conda run -n stocks python analysis/h125_beta_residual_standalone.py
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
    compute_beta,
    compute_illiq_level_rank,
    compute_volume_zscore,
    evaluate_features,
    load_ohlcv_wide,
    load_s1_frame,
    load_vni_close,
    rank_frame,
    to_long,
)

BETA_WINDOW = 60
BETA_MIN_DAYS = 40


def cross_sectional_residual(
    target: pd.DataFrame, control_1: pd.DataFrame, control_2: pd.DataFrame
) -> pd.DataFrame:
    residual = pd.DataFrame(index=target.index, columns=target.columns, dtype=float)
    for date in target.index:
        frame = pd.concat(
            [
                target.loc[date].rename("target"),
                control_1.loc[date].rename("control_1"),
                control_2.loc[date].rename("control_2"),
            ],
            axis=1,
        ).dropna()
        if len(frame) < 20:
            continue
        x = np.column_stack(
            [
                np.ones(len(frame), dtype=float),
                frame["control_1"].to_numpy(dtype=float),
                frame["control_2"].to_numpy(dtype=float),
            ]
        )
        y = frame["target"].to_numpy(dtype=float)
        beta = np.linalg.lstsq(x, y, rcond=None)[0]
        resid = y - x @ beta
        residual.loc[date, frame.index] = resid
    return residual


def build_features() -> pd.DataFrame:
    panels = load_ohlcv_wide(min_rows=BETA_WINDOW + 10)
    close = panels["close"]
    volume = panels["volume"]
    vni_close = load_vni_close()

    beta = compute_beta(close, vni_close, window=BETA_WINDOW, min_days=BETA_MIN_DAYS)
    xs_beta_rank = rank_frame(beta)
    xs_illiq_rank = compute_illiq_level_rank(close, volume)
    vol_zscore_5d = compute_volume_zscore(volume).rolling(5, min_periods=3).mean()
    xs_vol_zscore_5d = rank_frame(vol_zscore_5d)

    beta_resid = cross_sectional_residual(xs_beta_rank, xs_illiq_rank, xs_vol_zscore_5d)
    xs_beta_resid = rank_frame(beta_resid)
    xs_low_beta_resid = 1.0 - xs_beta_resid

    feature_df = (
        to_long(xs_beta_resid, "xs_beta_resid_60d_rank")
        .merge(to_long(xs_low_beta_resid, "xs_low_beta_resid_60d"), on=["time", "ticker"])
        .dropna(subset=["xs_beta_resid_60d_rank"])
    )
    return feature_df


def main():
    s1 = load_s1_frame()

    print("Loading OHLCV data for beta residual...")
    feature_df = build_features()
    feature_df["time"] = pd.to_datetime(feature_df["time"])

    merged = s1.merge(feature_df, on=["time", "ticker"], how="inner")
    print(
        f"Merged rows: {len(merged):,}  tickers: {merged['ticker'].nunique()}  "
        f"dates: {merged['time'].nunique()}"
    )

    feature_cols = ["xs_beta_resid_60d_rank", "xs_low_beta_resid_60d"]
    results = annotate_redundancy(feature_df, evaluate_features(merged, feature_cols))

    final_passers = [col for col, res in results.items() if res.get("final_pass")]
    standalone_passers = [col for col, res in results.items() if res.get("gate_pass")]
    primary = results["xs_beta_resid_60d_rank"]
    low = results["xs_low_beta_resid_60d"]

    if final_passers:
        verdict = "PASS"
        reason = f"Residual beta survives redundancy screen: {', '.join(final_passers)}"
    elif standalone_passers:
        verdict = "REJECTED_AS_REDUNDANT"
        reason = (
            "Residual beta passes standalone IC but overlaps existing candidates: "
            + ", ".join(
                f"{col} vs {results[col]['redundant_with']}" for col in standalone_passers
            )
        )
    else:
        verdict = "FAIL"
        reason = (
            f"No residual-beta feature passes gate. xs_beta_resid_60d_rank IC="
            f"{(primary.get('avg_ic') or 0):+.4f}, xs_low_beta_resid_60d IC="
            f"{(low.get('avg_ic') or 0):+.4f}."
        )

    summary = {
        "verdict": verdict,
        "reason": reason,
        "primary_feature": "xs_beta_resid_60d_rank",
        "standalone_passing_features": standalone_passers,
        "final_passing_features": final_passers,
        "features": results,
    }

    print("\nH125 BETA RESIDUAL RESULTS")
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
    details_path = REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h125_beta_residual_details.json"
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h125_beta_residual",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"session": 43, "signal": "H125"},
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
