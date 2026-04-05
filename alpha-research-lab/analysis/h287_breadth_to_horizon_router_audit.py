"""
H287 — Breadth-to-Horizon Router Audit.

Question:
- Does lagged sector breadth / rotation state tell us when the fast reversal family
  (C13/C9/C12) should dominate versus when the slower continuation family
  (C6/C4/W reclaim) should dominate?

Design:
- build the canonical 1d target (`actual`) and a 5d relative excess-return target
- score two small feature families on their natural horizon:
  - fast reversal family on 1d: C13, C9, C12
  - slow continuation family on 5d: C6, C4, W reclaim family
- aggregate daily family ICs
- compare the family gap against lagged sector breadth / rotation state
- if breadth state changes the sign of the family gap between low and high quintiles,
  the next step is a routed WF; otherwise the branch stays parked

Usage:
    conda run -n stocks python analysis/h287_breadth_to_horizon_router_audit.py
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
from src.standalone_signal_utils import load_ohlcv_wide, load_vni_close, spearman_stat, to_long

MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
SECTOR_ROTATION_PATH = data_path("features/xs_sector_rotation_daily.parquet")

FAST_FEATURES = [
    "c13_compress_blowoff_2",
    "c9_reversal_1d",
    "c12_gap_absorb_3",
]

SLOW_FEATURES = [
    "c6_contrarian_intra_5d",
    "c4_oc_asym_5d",
    "xs_upward_w_base_12d",
    "xs_upward_w_moderate_12d",
    "xs_upward_w_reclaim_12d",
    "xs_upward_w_reclaim_15d",
]


def _future_excess_return(close: pd.DataFrame, benchmark_close: pd.Series, *, periods: int) -> pd.DataFrame:
    future_stock = close.shift(-int(periods)).div(close).sub(1.0)
    future_benchmark = benchmark_close.shift(-int(periods)).div(benchmark_close).sub(1.0)
    return future_stock.sub(future_benchmark, axis=0)


def _daily_ic_series(df: pd.DataFrame, feature_col: str, target_col: str) -> pd.DataFrame:
    rows = []
    for time, group in df.groupby("time", sort=True):
        gg = group[[feature_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(gg) < 3:
            continue
        rho, p = spearmanr(gg[feature_col], gg[target_col])
        rows.append({"time": pd.to_datetime(time), "ic": float(rho), "p_value": float(p), "n": int(len(gg))})
    return pd.DataFrame(rows)


def _family_daily_score(df: pd.DataFrame, feature_cols: list[str], target_col: str) -> pd.DataFrame:
    family_frames = []
    for feat in feature_cols:
        series = _daily_ic_series(df, feat, target_col)
        if series.empty:
            continue
        family_frames.append(series[["time", "ic"]].rename(columns={"ic": feat}))
    if not family_frames:
        return pd.DataFrame(columns=["time", "family_ic"])
    merged = family_frames[0]
    for frame in family_frames[1:]:
        merged = merged.merge(frame, on="time", how="inner")
    ic_cols = [c for c in merged.columns if c != "time"]
    merged["family_ic"] = merged[ic_cols].mean(axis=1)
    return merged[["time", "family_ic"]].sort_values("time")


def _daily_state_frame(sector: pd.DataFrame) -> pd.DataFrame:
    work = sector.copy()
    work["time"] = pd.to_datetime(work["time"], errors="coerce").dt.normalize()
    work = work.sort_values(["ticker", "time"])
    work["breadth_prev5"] = work.groupby("ticker")["xs_sector_breadth_5d"].shift(5)
    work["breadth_gap5"] = work["breadth_prev5"] - work["xs_sector_breadth_5d"]
    daily = (
        work.groupby("time", sort=True)
        .agg(
            breadth_level=("xs_sector_breadth_5d", "median"),
            breadth_gap5=("breadth_gap5", "median"),
            rotation_signal=("xs_sector_rotation_signal", "median"),
        )
        .reset_index()
        .sort_values("time")
        .reset_index(drop=True)
    )
    daily["breadth_level_lag1"] = daily["breadth_level"].shift(1)
    daily["breadth_gap5_lag1"] = daily["breadth_gap5"].shift(1)
    daily["rotation_lag1"] = daily["rotation_signal"].shift(1)
    return daily


def _quintile_table(frame: pd.DataFrame, state_col: str) -> pd.DataFrame:
    work = frame.dropna(subset=[state_col, "family_gap"]).copy()
    if work.empty or work[state_col].nunique() < 5:
        return pd.DataFrame()
    work["quintile"] = pd.qcut(work[state_col].rank(method="first"), 5, labels=False) + 1
    summary = (
        work.groupby("quintile", sort=True)
        .agg(
            n=("family_gap", "size"),
            state_mean=(state_col, "mean"),
            fast_mean=("fast_ic_1d", "mean"),
            slow_mean=("slow_ic_5d", "mean"),
            gap_mean=("family_gap", "mean"),
        )
        .reset_index()
    )
    summary["winner"] = np.where(summary["gap_mean"] > 0.0, "slow", "fast")
    return summary


def main() -> None:
    print("Building breadth-to-horizon router audit panel...")

    matrix = pd.read_parquet(MATRIX_PATH, columns=["time", "ticker", "actual", *FAST_FEATURES, "c4_oc_asym_5d", "c6_contrarian_intra_5d"]).copy()
    matrix["time"] = pd.to_datetime(matrix["time"])
    matrix = matrix[matrix["time"].dt.year <= 2025].copy()

    close = load_ohlcv_wide(min_rows=120)["close"].sort_index()
    close = close.loc[close.index.year <= 2025].copy()
    benchmark_close = load_vni_close().reindex(close.index)
    future5 = _future_excess_return(close, benchmark_close, periods=5)
    future5_df = to_long(future5, "future_rel_return_5d")
    future5_df["time"] = pd.to_datetime(future5_df["time"], errors="coerce")
    future5_df = future5_df[future5_df["time"].dt.year <= 2025].copy()

    w_shapes = build_upward_w_shape_features(close)
    w_frame = None
    for name in [c for c in SLOW_FEATURES if c.startswith("xs_upward_w_")]:
        part = to_long(w_shapes[name], name)
        w_frame = part if w_frame is None else w_frame.merge(part, on=["time", "ticker"], how="inner")
    if w_frame is None:
        raise ValueError("No upward-W shape features were built")
    w_frame["time"] = pd.to_datetime(w_frame["time"], errors="coerce")
    w_frame = w_frame[w_frame["time"].dt.year <= 2025].copy()

    feature_df = matrix.merge(w_frame, on=["time", "ticker"], how="inner")
    feature_df = feature_df.merge(future5_df, on=["time", "ticker"], how="inner")
    feature_df = feature_df.dropna(subset=["actual", "future_rel_return_5d"])

    sector = pd.read_parquet(SECTOR_ROTATION_PATH, columns=["time", "ticker", "xs_sector_breadth_5d", "xs_sector_rotation_signal"]).copy()
    sector["time"] = pd.to_datetime(sector["time"], errors="coerce")
    sector = sector[sector["time"].dt.year <= 2025].copy()
    daily_state = _daily_state_frame(sector)

    fast_1d = _family_daily_score(feature_df, FAST_FEATURES, "actual").rename(columns={"family_ic": "fast_ic_1d"})
    fast_5d = _family_daily_score(feature_df, FAST_FEATURES, "future_rel_return_5d").rename(columns={"family_ic": "fast_ic_5d"})
    slow_1d = _family_daily_score(feature_df, SLOW_FEATURES, "actual").rename(columns={"family_ic": "slow_ic_1d"})
    slow_5d = _family_daily_score(feature_df, SLOW_FEATURES, "future_rel_return_5d").rename(columns={"family_ic": "slow_ic_5d"})

    scores = fast_1d.merge(fast_5d, on="time", how="inner")
    scores = scores.merge(slow_1d, on="time", how="inner")
    scores = scores.merge(slow_5d, on="time", how="inner")
    scores["family_gap"] = scores["slow_ic_5d"] - scores["fast_ic_1d"]
    scores["same_target_gap_1d"] = scores["slow_ic_1d"] - scores["fast_ic_1d"]
    scores["same_target_gap_5d"] = scores["slow_ic_5d"] - scores["fast_ic_5d"]

    panel = daily_state.merge(scores, on="time", how="inner")
    panel = panel.dropna(subset=["breadth_level_lag1", "breadth_gap5_lag1", "rotation_lag1", "family_gap"])
    if panel.empty:
        raise ValueError("No matched daily state + family score rows")

    metrics = {}
    for state_col in ["breadth_level_lag1", "breadth_gap5_lag1", "rotation_lag1"]:
        rho, p = spearmanr(panel[state_col], panel["family_gap"])
        qtab = _quintile_table(panel, state_col)
        if qtab.empty:
            q1_gap = q5_gap = float("nan")
            sign_swap = False
        else:
            q1_gap = float(qtab.loc[qtab["quintile"] == 1, "gap_mean"].iloc[0])
            q5_gap = float(qtab.loc[qtab["quintile"] == 5, "gap_mean"].iloc[0])
            sign_swap = bool(q1_gap * q5_gap < 0.0)
        metrics[state_col] = {
            "rho": float(rho),
            "p_value": float(p),
            "q1_gap": q1_gap,
            "q5_gap": q5_gap,
            "sign_swap": sign_swap,
            "quintile_table": qtab.to_dict("records"),
        }

    best_state = max(metrics.items(), key=lambda item: abs(item[1]["rho"]))
    best_state_name, best_state_metrics = best_state
    best_abs_rho = abs(best_state_metrics["rho"])
    pass_condition = bool(best_abs_rho >= 0.10 and best_state_metrics["sign_swap"])
    mixed_condition = bool(best_abs_rho >= 0.05 or best_state_metrics["sign_swap"])
    verdict = "PASS" if pass_condition else "MIXED" if mixed_condition else "FAIL"

    print("\nH287 BREADTH-TO-HORIZON ROUTER RESULTS")
    print("=" * 140)
    print(f"{'state':<24} {'rho':>9} {'p-value':>10} {'q1_gap':>10} {'q5_gap':>10} {'swap':>8}")
    print("-" * 140)
    for name, item in metrics.items():
        print(
            f"{name:<24} {item['rho']:>+9.4f} {item['p_value']:>10.4g} "
            f"{item['q1_gap']:>+10.4f} {item['q5_gap']:>+10.4f} {str(item['sign_swap']):>8}"
        )

    print("\nFamily score means (daily IC averages):")
    print(
        f"  fast_1d mean  : {panel['fast_ic_1d'].mean():+.4f}\n"
        f"  fast_5d mean  : {panel['fast_ic_5d'].mean():+.4f}\n"
        f"  slow_1d mean  : {panel['slow_ic_1d'].mean():+.4f}\n"
        f"  slow_5d mean  : {panel['slow_ic_5d'].mean():+.4f}\n"
        f"  family_gap    : {panel['family_gap'].mean():+.4f}"
    )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    details_path = REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h287_breadth_to_horizon_router_audit_details.json"
    summary = {
        "verdict": verdict,
        "best_state": best_state_name,
        "best_abs_rho": float(best_abs_rho),
        "best_state_metrics": best_state_metrics,
        "metrics": metrics,
        "panel_rows": int(len(panel)),
        "panel_dates": int(panel["time"].nunique()),
        "fast_1d_mean": float(panel["fast_ic_1d"].mean()),
        "fast_5d_mean": float(panel["fast_ic_5d"].mean()),
        "slow_1d_mean": float(panel["slow_ic_1d"].mean()),
        "slow_5d_mean": float(panel["slow_ic_5d"].mean()),
        "family_gap_mean": float(panel["family_gap"].mean()),
        "pass_condition": pass_condition,
        "mixed_condition": mixed_condition,
    }
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h287_breadth_to_horizon_router_audit",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"signal": "H287"},
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
