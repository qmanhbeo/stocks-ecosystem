"""
H285 — 5d Label Contract Audit.

Question:
- Do the current C4-C14 library signals and the upward-W family keep roughly
  the same ranking when the target is shifted from the current 1d contract to a
  5d forward excess-return contract?

Design:
- compare the canonical 1d label against a 5d excess-return target
- audit the current signal library columns C4-C14
- audit the explicit upward-W family from H278
- if the feature ordering materially changes, the next step is a 5d WF on the
  newly relevant horizon; otherwise keep the current label contract

Usage:
    conda run -n stocks python analysis/h285_5d_label_contract_audit.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from path_utils import data_path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.price_shape_research import build_upward_w_shape_features
from src.run_summary import write_run_summary
from src.standalone_signal_utils import (
    evaluate_features,
    load_ohlcv_wide,
    load_s1_frame,
    load_vni_close,
    spearman_stat,
    summarize_ic,
    to_long,
    yearly_ic,
)

S1_PATH = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
STOCK_DIR = data_path("stock")

LIBRARY_FEATURES = [
    "c4_oc_asym_5d",
    "c5_ins_relative_size_5d",
    "c6_contrarian_intra_5d",
    "c7_ceiling_count_5d",
    "c8_vol_zscore_5d",
    "c9_reversal_1d",
    "c10_illiq_level_rank",
    "c11_ret_60d_lag_rank",
    "c12_gap_absorb_3",
    "c13_compress_blowoff_2",
    "c14_clv_volconf_resid_rank",
]

W_FEATURES = [
    "xs_upward_w_base_12d",
    "xs_upward_w_moderate_12d",
    "xs_upward_w_reclaim_12d",
    "xs_upward_w_reclaim_15d",
]


def _future_excess_return(close: pd.DataFrame, benchmark_close: pd.Series, *, periods: int) -> pd.DataFrame:
    future_stock = close.shift(-int(periods)).div(close).sub(1.0)
    future_benchmark = benchmark_close.shift(-int(periods)).div(benchmark_close).sub(1.0)
    return future_stock.sub(future_benchmark, axis=0)


def _build_feature_frame() -> pd.DataFrame:
    matrix = pd.read_parquet(MATRIX_PATH, columns=["time", "ticker", *LIBRARY_FEATURES]).copy()
    matrix["time"] = pd.to_datetime(matrix["time"])
    matrix = matrix[matrix["time"].dt.year <= 2025].copy()

    close_full = load_ohlcv_wide(min_rows=120)["close"].sort_index()
    close_full = close_full.loc[close_full.index.year <= 2025].copy()
    w_shapes = build_upward_w_shape_features(close_full)
    w_frame = None
    for name in W_FEATURES:
        part = to_long(w_shapes[name], name)
        w_frame = part if w_frame is None else w_frame.merge(part, on=["time", "ticker"], how="inner")
    if w_frame is None:
        raise ValueError("No upward-W shape features were built")
    w_frame["time"] = pd.to_datetime(w_frame["time"], errors="coerce")
    w_frame = w_frame[w_frame["time"].dt.year <= 2025].copy()

    feature_df = matrix.merge(w_frame, on=["time", "ticker"], how="inner")
    feature_df = feature_df.dropna(subset=[LIBRARY_FEATURES[0]])
    return feature_df


def _build_targets(feature_df: pd.DataFrame) -> pd.DataFrame:
    s1 = load_s1_frame()[["time", "ticker", "actual", "xs_proba"]].copy()
    s1["time"] = pd.to_datetime(s1["time"])
    s1 = s1[s1["time"].dt.year <= 2025].copy()

    close_full = load_ohlcv_wide(min_rows=120)["close"].sort_index()
    close_full = close_full.loc[close_full.index.year <= 2025].copy()
    benchmark_close = load_vni_close().reindex(close_full.index)
    future5 = _future_excess_return(close_full, benchmark_close, periods=5)
    future5_df = to_long(future5, "future_rel_return_5d")
    future5_df["time"] = pd.to_datetime(future5_df["time"], errors="coerce")
    future5_df = future5_df[future5_df["time"].dt.year <= 2025].copy()

    merged = (
        feature_df.merge(s1, on=["time", "ticker"], how="inner")
        .merge(future5_df, on=["time", "ticker"], how="inner")
    )
    return merged


def _summarize_results(merged: pd.DataFrame, feature_cols: list[str], *, target_col: str, s1_col: str = "xs_proba") -> dict[str, dict]:
    raw_results = evaluate_features(merged, feature_cols, s1_col=s1_col, target_col=target_col)
    feat_df = merged[["time", "ticker", *feature_cols]].copy()

    matrix = pd.read_parquet(MATRIX_PATH).copy()
    matrix["time"] = pd.to_datetime(matrix["time"])
    candidate_cols = [col for col in matrix.columns if col.startswith("c") and col != "c5_signal_present"]

    for feature_col, result in raw_results.items():
        if not result.get("gate_pass"):
            result["candidate_corrs"] = {}
            result["max_abs_candidate_corr"] = None
            result["redundant_with"] = None
            result["final_pass"] = False
            continue
        query = feat_df[["time", "ticker", feature_col]].rename(columns={feature_col: "__query__"})
        merged_corr = matrix.merge(query, on=["time", "ticker"], how="inner")
        corrs = {
            col: spearman_stat(merged_corr["__query__"], merged_corr[col])
            for col in candidate_cols
            if col != feature_col
        }
        valid = {k: v for k, v in corrs.items() if pd.notna(v)}
        if valid:
            redundant_with, max_abs_corr = max(valid.items(), key=lambda item: abs(item[1]))
            max_abs_corr = float(abs(max_abs_corr))
            result["candidate_corrs"] = valid
            result["max_abs_candidate_corr"] = max_abs_corr
            result["redundant_with"] = redundant_with if max_abs_corr >= 0.75 else None
            result["final_pass"] = max_abs_corr < 0.75
        else:
            result["candidate_corrs"] = {}
            result["max_abs_candidate_corr"] = None
            result["redundant_with"] = None
            result["final_pass"] = True
    return raw_results


def _rank_table(results: dict[str, dict]) -> list[tuple[str, float]]:
    ranked = []
    for feat, res in results.items():
        ranked.append((feat, float(res.get("avg_ic") or float("nan"))))
    ranked.sort(key=lambda item: (-np.inf if pd.isna(item[1]) else -item[1], item[0]))
    return ranked


def main() -> None:
    print("Building 5d label contract audit panel...")
    feature_df = _build_feature_frame()
    merged = _build_targets(feature_df)
    print(
        f"Merged rows: {len(merged):,}  tickers: {merged['ticker'].nunique()}  "
        f"dates: {merged['time'].nunique()}"
    )

    all_features = LIBRARY_FEATURES + W_FEATURES
    one_day_results = _summarize_results(merged, all_features, target_col="actual")
    five_day_results = _summarize_results(merged, all_features, target_col="future_rel_return_5d")

    one_day_ranks = _rank_table(one_day_results)
    five_day_ranks = _rank_table(five_day_results)
    rank_map_1d = {feat: idx + 1 for idx, (feat, _) in enumerate(one_day_ranks)}
    rank_map_5d = {feat: idx + 1 for idx, (feat, _) in enumerate(five_day_ranks)}
    rank_df = pd.DataFrame(
        {
            "feature": all_features,
            "rank_1d": [rank_map_1d[f] for f in all_features],
            "rank_5d": [rank_map_5d[f] for f in all_features],
        }
    )
    rank_tau, rank_p = spearmanr(rank_df["rank_1d"], rank_df["rank_5d"])

    top3_1d = [feat for feat, _ in one_day_ranks[:3]]
    top3_5d = [feat for feat, _ in five_day_ranks[:3]]
    top1_1d = top3_1d[0]
    top1_5d = top3_5d[0]
    top3_overlap = len(set(top3_1d) & set(top3_5d))

    material_change = bool(top1_1d != top1_5d or top3_overlap < 2 or float(rank_tau) < 0.80)

    print("\nH285 5D LABEL CONTRACT RESULTS")
    print("=" * 140)
    print(
        f"{'feature':<30} {'1d_ic':>8} {'1d_pos':>7} {'1d_corr':>9} "
        f"{'5d_ic':>8} {'5d_pos':>7} {'5d_corr':>9} {'d_rank':>8}"
    )
    print("-" * 140)
    for feat in all_features:
        r1 = one_day_results[feat]
        r5 = five_day_results[feat]
        print(
            f"{feat:<30} "
            f"{(r1.get('avg_ic') or 0.0):>+7.4f} {r1.get('pos_years', 0):>7d}/{r1.get('years', 0):<2d} "
            f"{(r1.get('corr_with_s1') or 0.0):>+8.4f} "
            f"{(r5.get('avg_ic') or 0.0):>+7.4f} {r5.get('pos_years', 0):>7d}/{r5.get('years', 0):<2d} "
            f"{(r5.get('corr_with_s1') or 0.0):>+8.4f} "
            f"{rank_map_1d[feat] - rank_map_5d[feat]:>+8d}"
        )

    print("\nTop-3 ranking shift:")
    print(f"  1d: {top3_1d}")
    print(f"  5d: {top3_5d}")
    print(f"  overlap: {top3_overlap}/3")
    print(f"  rank spearman: {float(rank_tau):+.4f} (p={float(rank_p):.4g})")
    print(f"  material change: {material_change}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    details_path = REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h285_5d_label_contract_audit_details.json"
    summary = {
        "verdict": "MATERIAL_CHANGE" if material_change else "NO_MATERIAL_CHANGE",
        "top1_1d": top1_1d,
        "top1_5d": top1_5d,
        "top3_1d": top3_1d,
        "top3_5d": top3_5d,
        "top3_overlap": int(top3_overlap),
        "rank_spearman": float(rank_tau),
        "rank_p_value": float(rank_p),
        "material_change": bool(material_change),
        "one_day_results": one_day_results,
        "five_day_results": five_day_results,
    }
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h285_5d_label_contract_audit",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"signal": "H285"},
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
