"""
H131 — Sector Breadth Shock (Session 43)

Tests whether the change in sector participation is more informative than the
static breadth level, especially when combined with intra-sector laggard status.

Signals tested:
1. xs_breadth_shock_laggard
2. xs_breadth_shock_leader
3. xs_breadth_impulse_laggard

Usage:
    conda run -n stocks python analysis/h131_sector_breadth_shock_standalone.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from path_utils import data_path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.run_summary import write_run_summary
from src.standalone_signal_utils import annotate_redundancy, evaluate_features, load_s1_frame

SECTOR_PATH = data_path("features/xs_sector_rotation_daily.parquet")


def build_features() -> pd.DataFrame:
    sector = pd.read_parquet(SECTOR_PATH)
    sector["time"] = pd.to_datetime(sector["time"])
    sector = sector.sort_values(["ticker", "time"]).copy()

    sector["breadth_delta_1"] = sector.groupby("ticker")["xs_sector_breadth_5d"].diff(1)
    sector["breadth_delta_3"] = sector.groupby("ticker")["xs_sector_breadth_5d"].diff(3)
    sector["breadth_impulse"] = sector["breadth_delta_3"] * sector["xs_sector_mom_5d_rank"]

    sector["raw_breadth_shock_laggard"] = sector["breadth_delta_3"] * (1.0 - sector["xs_intra_sector_rank"])
    sector["raw_breadth_shock_leader"] = sector["breadth_delta_3"] * sector["xs_intra_sector_rank"]
    sector["raw_breadth_impulse_laggard"] = sector["breadth_impulse"] * (1.0 - sector["xs_intra_sector_rank"])

    for raw_col, rank_col in [
        ("raw_breadth_shock_laggard", "xs_breadth_shock_laggard"),
        ("raw_breadth_shock_leader", "xs_breadth_shock_leader"),
        ("raw_breadth_impulse_laggard", "xs_breadth_impulse_laggard"),
    ]:
        sector[rank_col] = sector.groupby("time")[raw_col].rank(method="average", pct=True)

    return sector[
        [
            "time",
            "ticker",
            "xs_breadth_shock_laggard",
            "xs_breadth_shock_leader",
            "xs_breadth_impulse_laggard",
        ]
    ].dropna(subset=["xs_breadth_shock_laggard"])


def main():
    s1 = load_s1_frame()

    print("Loading sector breadth shock features...")
    feature_df = build_features()

    merged = s1.merge(feature_df, on=["time", "ticker"], how="inner")
    print(
        f"Merged rows: {len(merged):,}  tickers: {merged['ticker'].nunique()}  "
        f"dates: {merged['time'].nunique()}"
    )

    feature_cols = [
        "xs_breadth_shock_laggard",
        "xs_breadth_shock_leader",
        "xs_breadth_impulse_laggard",
    ]
    results = annotate_redundancy(feature_df, evaluate_features(merged, feature_cols))

    final_passers = [col for col, res in results.items() if res.get("final_pass")]
    standalone_passers = [col for col, res in results.items() if res.get("gate_pass")]
    best_feat = max(feature_cols, key=lambda col: results[col].get("avg_ic") or -99)
    c6_overlap = {
        col: results[col].get("candidate_corrs", {}).get("c6_contrarian_intra_5d")
        for col in standalone_passers
    }

    if final_passers:
        verdict = "PASS"
        reason = f"Sector breadth shock passes: {', '.join(final_passers)}"
    elif standalone_passers:
        verdict = "REJECTED_AS_REDUNDANT"
        reason = (
            "Sector breadth shock passes standalone but overlaps existing candidates: "
            + ", ".join(
                f"{col} vs {results[col]['redundant_with']}" for col in standalone_passers
            )
        )
    else:
        verdict = "FAIL"
        reason = (
            f"No breadth-shock feature passes gate. Best: {best_feat} IC="
            f"{(results[best_feat].get('avg_ic') or 0):+.4f}."
        )

    summary = {
        "verdict": verdict,
        "reason": reason,
        "primary_feature": best_feat,
        "standalone_passing_features": standalone_passers,
        "final_passing_features": final_passers,
        "c6_overlap": c6_overlap,
        "features": results,
    }

    print("\nH131 SECTOR BREADTH SHOCK RESULTS")
    print("=" * 72)
    print(f"Universe: {merged['ticker'].nunique()} tickers")
    print()
    print(
        f"  {'Feature':<28s}  {'IC':>7s}  {'Pos Yrs':>7s}  {'Corr S1':>8s}  "
        f"{'Corr C6':>8s}  Final"
    )
    for feat in feature_cols:
        res = results[feat]
        corr_c6 = res.get("candidate_corrs", {}).get("c6_contrarian_intra_5d")
        corr_c6_text = f"{corr_c6:+.3f}" if corr_c6 is not None and pd.notna(corr_c6) else "   n/a"
        final_state = "PASS" if res.get("final_pass") else ("dup" if res.get("gate_pass") else "fail")
        print(
            f"  {feat:<28s}  {(res.get('avg_ic') or 0):+.4f}  "
            f"{res['pos_years']:>2d}/{res['years']:<2d}   {res['corr_with_s1']:+.3f}   "
            f"{corr_c6_text:>8s}  {final_state}"
        )
    print(f"\nVerdict: {verdict}")
    print(f"Reason:  {reason}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    details_path = (
        REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h131_sector_breadth_shock_details.json"
    )
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h131_sector_breadth_shock",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"session": 43, "signal": "H131"},
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
