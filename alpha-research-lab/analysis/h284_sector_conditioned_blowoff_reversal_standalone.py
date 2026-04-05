"""
H284 — Sector-Conditioned Blow-Off Reversal.

Tests whether the H133 compression blow-off reversal state gets stronger when
it occurs inside:
- hot sectors, or
- recent ceiling clusters

Design:
- start from the existing `c13_compress_blowoff_2` signal
- gate it with a fixed hot-sector threshold from the sector surface
- gate it with a fixed ceiling-cluster threshold from the library matrix
- no threshold sweep, no 2026 data

Usage:
    conda run -n stocks python analysis/h284_sector_conditioned_blowoff_reversal_standalone.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from path_utils import data_path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.run_summary import write_run_summary
from src.standalone_signal_utils import annotate_redundancy, evaluate_features, load_s1_frame

RL_MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
SECTOR_PATH = data_path("features/xs_sector_rotation_daily.parquet")

HOT_SECTOR_THRESHOLD = 0.80
CEILING_CLUSTER_THRESHOLD = 0.80


def build_features() -> pd.DataFrame:
    base = pd.read_parquet(RL_MATRIX_PATH, columns=["time", "ticker", "c13_compress_blowoff_2", "c7_ceiling_count_5d"])
    base["time"] = pd.to_datetime(base["time"])
    base = base[base["time"].dt.year <= 2025].copy()

    sector = pd.read_parquet(
        SECTOR_PATH,
        columns=["time", "ticker", "xs_sector_mom_5d_rank", "xs_sector_breadth_5d"],
    )
    sector["time"] = pd.to_datetime(sector["time"])
    sector = sector[sector["time"].dt.year <= 2025].copy()

    merged = base.merge(sector, on=["time", "ticker"], how="inner")
    merged["hot_sector"] = (pd.to_numeric(merged["xs_sector_mom_5d_rank"], errors="coerce") >= HOT_SECTOR_THRESHOLD).astype(float)
    merged["ceiling_cluster"] = (pd.to_numeric(merged["c7_ceiling_count_5d"], errors="coerce") >= CEILING_CLUSTER_THRESHOLD).astype(float)
    merged["hot_and_cluster"] = merged["hot_sector"] * merged["ceiling_cluster"]

    # Interaction terms: same reversal state, but only when the broader sector / ceiling context is hot.
    merged["h284_c13_compress_blowoff_2"] = merged["c13_compress_blowoff_2"]
    merged["h284_c13_hot_sector"] = merged["c13_compress_blowoff_2"] * merged["hot_sector"]
    merged["h284_c13_ceiling_cluster"] = merged["c13_compress_blowoff_2"] * merged["ceiling_cluster"]
    merged["h284_c13_hot_and_cluster"] = merged["c13_compress_blowoff_2"] * merged["hot_and_cluster"]

    return merged[[
        "time",
        "ticker",
        "h284_c13_compress_blowoff_2",
        "h284_c13_hot_sector",
        "h284_c13_ceiling_cluster",
        "h284_c13_hot_and_cluster",
        "hot_sector",
        "ceiling_cluster",
        "hot_and_cluster",
        "xs_sector_mom_5d_rank",
        "xs_sector_breadth_5d",
        "c7_ceiling_count_5d",
    ]].copy()


def main() -> None:
    s1 = load_s1_frame()

    print("Loading sector-conditioned blow-off inputs...")
    feature_df = build_features()
    feature_df["time"] = pd.to_datetime(feature_df["time"])

    merged = s1.merge(feature_df, on=["time", "ticker"], how="inner")
    print(
        f"Merged rows: {len(merged):,}  tickers: {merged['ticker'].nunique()}  "
        f"dates: {merged['time'].nunique()}"
    )

    feature_cols = [
        "h284_c13_compress_blowoff_2",
        "h284_c13_hot_sector",
        "h284_c13_ceiling_cluster",
        "h284_c13_hot_and_cluster",
    ]
    results = annotate_redundancy(feature_df, evaluate_features(merged, feature_cols))

    # Fixed condition diagnostics for the queue question.
    hot_mask = merged["hot_sector"] > 0.5
    ceil_mask = merged["ceiling_cluster"] > 0.5
    intersection_mask = hot_mask & ceil_mask
    subset_stats = {}
    for label, mask in {
        "all": pd.Series(True, index=merged.index),
        "hot_sector": hot_mask,
        "ceiling_cluster": ceil_mask,
        "hot_and_cluster": intersection_mask,
    }.items():
        sub = merged.loc[mask, ["time", "ticker"] + feature_cols].copy()
        sub_ic = evaluate_features(sub.assign(actual=merged.loc[mask, "actual"].values, xs_proba=merged.loc[mask, "xs_proba"].values), feature_cols)
        subset_stats[label] = {
            feat: {
                "avg_ic": sub_ic[feat].get("avg_ic"),
                "pos_years": sub_ic[feat].get("pos_years"),
                "years": sub_ic[feat].get("years"),
                "corr_with_s1": sub_ic[feat].get("corr_with_s1"),
            }
            for feat in feature_cols
        }

    final_passers = [col for col, res in results.items() if res.get("final_pass")]
    standalone_passers = [col for col, res in results.items() if res.get("gate_pass")]
    best_feat = max(feature_cols, key=lambda col: results[col].get("avg_ic") or -99)

    if final_passers:
        verdict = "PASS"
        reason = f"Sector-conditioned blow-off reversal passes: {', '.join(final_passers)}"
    elif standalone_passers:
        verdict = "REJECTED_AS_REDUNDANT"
        reason = (
            "Sector-conditioned blow-off reversal passes standalone but overlaps existing candidates: "
            + ", ".join(
                f"{col} vs {results[col]['redundant_with']}" for col in standalone_passers
            )
        )
    else:
        verdict = "FAIL"
        reason = (
            f"No sector-conditioned blow-off feature passes gate. Best: {best_feat} IC="
            f"{(results[best_feat].get('avg_ic') or 0):+.4f}."
        )

    summary = {
        "verdict": verdict,
        "reason": reason,
        "primary_feature": best_feat,
        "thresholds": {
            "hot_sector_rank": HOT_SECTOR_THRESHOLD,
            "ceiling_cluster_rank": CEILING_CLUSTER_THRESHOLD,
        },
        "standalone_passing_features": standalone_passers,
        "final_passing_features": final_passers,
        "subset_stats": subset_stats,
        "features": results,
    }

    print("\nH284 SECTOR-CONDITIONED BLOW-OFF REVERSAL RESULTS")
    print("=" * 92)
    print(f"Universe: {merged['ticker'].nunique()} tickers")
    print(f"Thresholds: hot_sector_rank >= {HOT_SECTOR_THRESHOLD:.2f}, ceiling_cluster_rank >= {CEILING_CLUSTER_THRESHOLD:.2f}")
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

    print("\nSubset diagnostics:")
    for subset_name, stats in subset_stats.items():
        feat = "h284_c13_compress_blowoff_2"
        val = stats[feat]
        print(
            f"  {subset_name:<16s}  c13 IC={val['avg_ic'] if val['avg_ic'] is not None else float('nan'):+.4f} "
            f"pos={val['pos_years']}/{val['years']} corrS1={val['corr_with_s1']:+.3f}"
        )

    print(f"\nVerdict: {verdict}")
    print(f"Reason:  {reason}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    details_path = (
        REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h284_sector_conditioned_blowoff_reversal_details.json"
    )
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h284_sector_conditioned_blowoff_reversal",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"signal": "H284", "hot_sector_threshold": HOT_SECTOR_THRESHOLD, "ceiling_cluster_threshold": CEILING_CLUSTER_THRESHOLD},
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
