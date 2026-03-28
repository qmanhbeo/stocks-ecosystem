"""
H134 — Close-Location Residual vs C8 (Session 44)

Tests whether the H127 volume-confirmed close-location signal still contains a
distinct edge after removing the existing C8 volume-activity axis.

Signals tested:
1. xs_clv_volconf_resid_rank
2. xs_clv_volconf_resid_inverted

Usage:
    conda run -n stocks python analysis/h134_close_location_residual_standalone.py
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
    cross_sectional_residual,
    evaluate_features,
    load_s1_frame,
    rank_frame,
)

C8_PATH = REPO_ROOT / "data" / "features" / "xs_volume_zscore_daily.parquet"


def build_features() -> pd.DataFrame:
    h127_path = (
        REPO_ROOT
        / "artifacts"
        / "run_summaries"
        / "20260328_124334_h127_close_location_persistence_details.json"
    )
    if not h127_path.exists():
        raise FileNotFoundError("Expected H127 artifact not found; H134 depends on H127 results.")

    from analysis.h127_close_location_persistence_standalone import build_features as build_h127_features

    clv_df = build_h127_features()[["time", "ticker", "xs_clv_volconf_5d_rank"]].copy()
    c8 = pd.read_parquet(C8_PATH, columns=["time", "ticker", "xs_vol_zscore_5d"])
    c8["time"] = pd.to_datetime(c8["time"])

    merged = clv_df.merge(c8, on=["time", "ticker"], how="inner")
    wide_clv = merged.pivot_table(index="time", columns="ticker", values="xs_clv_volconf_5d_rank").sort_index()
    wide_c8 = merged.pivot_table(index="time", columns="ticker", values="xs_vol_zscore_5d").sort_index()
    common_index = wide_clv.index.intersection(wide_c8.index)
    wide_clv = wide_clv.reindex(common_index)
    wide_c8 = wide_c8.reindex(common_index)

    resid = cross_sectional_residual(wide_clv, wide_c8)
    resid_rank = rank_frame(resid)
    resid_inverted = 1.0 - resid_rank

    feature_df = (
        resid_rank.reset_index()
        .melt(id_vars="time", var_name="ticker", value_name="xs_clv_volconf_resid_rank")
        .merge(
            resid_inverted.reset_index().melt(
                id_vars="time", var_name="ticker", value_name="xs_clv_volconf_resid_inverted"
            ),
            on=["time", "ticker"],
        )
        .dropna(subset=["xs_clv_volconf_resid_rank"])
    )
    return feature_df


def main():
    s1 = load_s1_frame()

    print("Loading close-location residual vs C8...")
    feature_df = build_features()
    feature_df["time"] = pd.to_datetime(feature_df["time"])

    merged = s1.merge(feature_df, on=["time", "ticker"], how="inner")
    print(
        f"Merged rows: {len(merged):,}  tickers: {merged['ticker'].nunique()}  "
        f"dates: {merged['time'].nunique()}"
    )

    feature_cols = ["xs_clv_volconf_resid_rank", "xs_clv_volconf_resid_inverted"]
    results = annotate_redundancy(feature_df, evaluate_features(merged, feature_cols))

    final_passers = [col for col, res in results.items() if res.get("final_pass")]
    standalone_passers = [col for col, res in results.items() if res.get("gate_pass")]
    best_feat = max(feature_cols, key=lambda col: results[col].get("avg_ic") or -99)

    if final_passers:
        verdict = "PASS"
        reason = f"Close-location residual survives C8: {', '.join(final_passers)}"
    elif standalone_passers:
        verdict = "REJECTED_AS_REDUNDANT"
        reason = (
            "Close-location residual passes standalone but still overlaps existing candidates: "
            + ", ".join(
                f"{col} vs {results[col]['redundant_with']}" for col in standalone_passers
            )
        )
    else:
        verdict = "FAIL"
        reason = (
            f"No residual close-location feature passes gate. Best: {best_feat} IC="
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

    print("\nH134 CLOSE-LOCATION RESIDUAL RESULTS")
    print("=" * 72)
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
        REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h134_close_location_residual_details.json"
    )
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h134_close_location_residual",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"session": 44, "signal": "H134"},
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
