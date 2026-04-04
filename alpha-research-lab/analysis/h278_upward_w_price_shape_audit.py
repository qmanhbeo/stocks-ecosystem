"""
H278: explicit upward-W daily price-shape audit.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.price_shape_research import UPWARD_W_SIGNAL_FORMULAS, build_upward_w_shape_features
from src.run_summary import write_run_summary
from src.standalone_signal_utils import (
    PASS_CORR,
    PASS_IC,
    PASS_PCT_YEARS,
    annotate_redundancy,
    evaluate_features,
    gate_pass,
    load_ohlcv_wide,
    load_s1_frame,
    load_vni_close,
    pairwise_candidate_corrs,
    spearman_stat,
    summarize_ic,
    to_long,
    yearly_ic,
)


OUT_DIR = REPO_ROOT / "artifacts" / "portfolio_baselines"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H278: explicit upward-W daily price-shape audit")
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--future-horizon", type=int, default=5)
    return parser.parse_args()


def _safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _future_excess_return(close: pd.DataFrame, benchmark_close: pd.Series, *, periods: int) -> pd.DataFrame:
    future_stock = close.shift(-int(periods)).div(close).sub(1.0)
    future_benchmark = benchmark_close.shift(-int(periods)).div(benchmark_close).sub(1.0)
    return future_stock.sub(future_benchmark, axis=0)


def _overall_decision(row: dict[str, object]) -> str:
    if bool(row.get("canonical_final_pass")):
        return "PASSED"
    if bool(row.get("future5_final_pass")):
        return "MIXED"
    return "FAILED"


def _sort_results(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return results.copy()
    work = results.copy()
    work["_decision_rank"] = work["decision"].map({"FAILED": 0, "MIXED": 1, "PASSED": 2}).fillna(-1)
    for column in (
        "canonical_avg_ic",
        "future5_avg_ic",
        "canonical_corr_with_s1",
        "future5_corr_with_s1",
        "max_candidate_corr",
    ):
        work[column] = pd.to_numeric(work[column], errors="coerce")
    return work.sort_values(
        by=[
            "_decision_rank",
            "future5_avg_ic",
            "canonical_avg_ic",
            "max_candidate_corr",
            "signal_name",
        ],
        ascending=[False, False, False, True, True],
        ignore_index=True,
    ).drop(columns="_decision_rank")


def _print_table(results: pd.DataFrame) -> None:
    print("\n" + "=" * 176)
    print("H278: UPWARD-W DAILY PRICE SHAPE AUDIT")
    print("=" * 176)
    print(
        f"{'signal':<30} {'decision':<8} {'1d_ic':>8} {'1d_pos':>8} {'1d_corr':>9} "
        f"{'5d_ic':>8} {'5d_pos':>8} {'5d_corr':>9} {'max_corr':>9}"
    )
    print("-" * 176)
    for row in results.itertuples(index=False):
        print(
            f"{str(row.signal_name):<30} "
            f"{str(row.decision):<8} "
            f"{(_safe_float(row.canonical_avg_ic) or 0.0):>+7.4f} "
            f"{(_safe_float(row.canonical_pct_years_positive) or 0.0):>7.2f} "
            f"{(_safe_float(row.canonical_corr_with_s1) or 0.0):>+8.4f} "
            f"{(_safe_float(row.future5_avg_ic) or 0.0):>+7.4f} "
            f"{(_safe_float(row.future5_pct_years_positive) or 0.0):>7.2f} "
            f"{(_safe_float(row.future5_corr_with_s1) or 0.0):>+8.4f} "
            f"{(_safe_float(row.max_candidate_corr) or 0.0):>+8.4f}"
        )


def main() -> None:
    args = parse_args()

    print("Loading close-only data for upward-W audit...")
    panels = load_ohlcv_wide(min_rows=120)
    close_full = panels["close"].sort_index()
    close_full = close_full.loc[close_full.index.year <= int(args.end_year)].copy()
    benchmark_close = load_vni_close().reindex(close_full.index)

    signal_wides = build_upward_w_shape_features(close_full)
    feature_cols = list(signal_wides.keys())
    feature_df = None
    for feature_name in feature_cols:
        part = to_long(signal_wides[feature_name], feature_name)
        feature_df = part if feature_df is None else feature_df.merge(part, on=["time", "ticker"], how="inner")
    if feature_df is None:
        raise ValueError("No upward-W features were built")
    feature_df["time"] = pd.to_datetime(feature_df["time"], errors="coerce")
    feature_df = feature_df.loc[
        feature_df["time"].dt.year.between(int(args.start_year), int(args.end_year))
    ].copy()
    if feature_df.empty:
        raise ValueError("No feature rows remain in the requested year range")

    s1 = load_s1_frame()
    s1 = s1.loc[s1["time"].dt.year.between(int(args.start_year), int(args.end_year))].copy()
    merged_next_day = s1.merge(feature_df, on=["time", "ticker"], how="inner")
    if merged_next_day.empty:
        raise ValueError("No overlap between S1 frame and upward-W features")

    canonical_results = annotate_redundancy(feature_df, evaluate_features(merged_next_day, feature_cols))

    future5 = _future_excess_return(close_full, benchmark_close, periods=int(args.future_horizon))
    future5_df = to_long(future5, f"future_excess_return_{int(args.future_horizon)}d")
    future5_df["time"] = pd.to_datetime(future5_df["time"], errors="coerce")
    future5_df = future5_df.loc[
        future5_df["time"].dt.year.between(int(args.start_year), int(args.end_year))
    ].copy()

    future_target_col = f"future_excess_return_{int(args.future_horizon)}d"
    merged_future = (
        feature_df.merge(future5_df, on=["time", "ticker"], how="inner")
        .merge(s1[["time", "ticker", "xs_proba"]], on=["time", "ticker"], how="left")
    )

    rows: list[dict[str, object]] = []
    for feature_name in feature_cols:
        canonical = canonical_results[feature_name]
        future5_summary = summarize_ic(yearly_ic(merged_future, feature_name, future_target_col))
        future5_corr_with_s1 = spearman_stat(merged_future[feature_name], merged_future["xs_proba"])
        candidate_corrs = pairwise_candidate_corrs(feature_df[["time", "ticker", feature_name]], feature_name)
        valid_candidate_corrs = {
            key: float(abs(value))
            for key, value in candidate_corrs.items()
            if pd.notna(value)
        }
        max_candidate_corr = max(valid_candidate_corrs.values()) if valid_candidate_corrs else None
        max_candidate_corr_with = (
            max(valid_candidate_corrs.items(), key=lambda item: item[1])[0] if valid_candidate_corrs else None
        )
        future5_gate = gate_pass(
            future5_summary.get("avg_ic"),
            future5_corr_with_s1,
            future5_summary.get("pct_years_positive"),
        )
        future5_final_pass = bool(
            future5_gate
            and max_candidate_corr is not None
            and abs(float(max_candidate_corr)) < PASS_CORR
        )

        row: dict[str, object] = {
            "signal_name": feature_name,
            "formula": UPWARD_W_SIGNAL_FORMULAS.get(feature_name),
            "canonical_avg_ic": canonical.get("avg_ic"),
            "canonical_pos_years": canonical.get("pos_years"),
            "canonical_years": canonical.get("years"),
            "canonical_pct_years_positive": canonical.get("pct_years_positive"),
            "canonical_corr_with_s1": canonical.get("corr_with_s1"),
            "canonical_gate_pass": canonical.get("gate_pass"),
            "canonical_final_pass": canonical.get("final_pass"),
            "canonical_redundant_with": canonical.get("redundant_with"),
            "future5_avg_ic": future5_summary.get("avg_ic"),
            "future5_pos_years": future5_summary.get("pos_years"),
            "future5_years": future5_summary.get("years"),
            "future5_pct_years_positive": future5_summary.get("pct_years_positive"),
            "future5_corr_with_s1": future5_corr_with_s1,
            "future5_gate_pass": future5_gate,
            "future5_final_pass": future5_final_pass,
            "max_candidate_corr": max_candidate_corr,
            "max_candidate_corr_with": max_candidate_corr_with,
            "decision": "FAILED",
        }
        row["decision"] = _overall_decision(row)
        rows.append(row)

    results = _sort_results(pd.DataFrame(rows))
    _print_table(results)

    canonical_passers = results.loc[results["canonical_final_pass"].fillna(False).astype(bool), "signal_name"].tolist()
    future5_passers = results.loc[results["future5_final_pass"].fillna(False).astype(bool), "signal_name"].tolist()
    best_row = results.iloc[0].to_dict() if not results.empty else {}

    if canonical_passers:
        verdict = "PASS"
        reason = "At least one explicit upward-W feature passes the canonical next-day standalone gate."
    elif future5_passers:
        verdict = "MIXED"
        reason = (
            "No explicit upward-W feature passes the canonical next-day gate, "
            "but slower reclaim-style variants pass the 5-day excess-return diagnostic."
        )
    else:
        verdict = "FAIL"
        reason = "No explicit upward-W feature survives either the canonical next-day gate or the 5-day diagnostic."

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h278_upward_w_price_shape_audit_results.parquet"
    panel_path = OUT_DIR / f"{ts}_h278_upward_w_price_shape_audit_panel.parquet"
    details_path = REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h278_upward_w_price_shape_audit_details.json"

    results.to_parquet(results_path, index=False)
    merged_future[["time", "ticker", "xs_proba", future_target_col, *feature_cols]].to_parquet(panel_path, index=False)

    summary = {
        "verdict": verdict,
        "reason": reason,
        "start_year": int(args.start_year),
        "end_year": int(args.end_year),
        "future_horizon_days": int(args.future_horizon),
        "canonical_passing_features": canonical_passers,
        "future5_supporting_features": future5_passers,
        "best_feature": best_row,
        "close_daily_queue_reopen": bool(canonical_passers),
        "future5_only_signal_family": bool((not canonical_passers) and future5_passers),
        "signal_formulas": {key: UPWARD_W_SIGNAL_FORMULAS[key] for key in feature_cols},
        "pass_ic_threshold": PASS_IC,
        "pass_corr_threshold": PASS_CORR,
        "pass_pct_years_threshold": PASS_PCT_YEARS,
    }
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal_upward_w_price_shape",
        name="h278_upward_w_price_shape_audit",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "panel": str(panel_path),
            "details_json": str(details_path),
        },
        metadata={
            "session": 107,
            "signal_family": "upward_w_price_shape",
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "future_horizon_days": int(args.future_horizon),
        },
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
