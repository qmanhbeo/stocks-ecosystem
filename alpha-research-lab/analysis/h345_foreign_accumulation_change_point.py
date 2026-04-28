"""
H345: CafeF foreign-flow accumulation change-point screen.

Question:
    After raw foreign-flow ranks, simple state conditioning, and room-residual
    thresholding failed, does the H95 signal live in slower foreign accumulation
    regime changes rather than one-day or five-day flow levels?

Design:
    - reuse the audited CafeF historical foreign-flow panel
    - build a small predeclared set of accumulation / ownership-change features
    - evaluate only 2015-2025 for predictive content; 2026 is excluded
    - keep the H327/H333 dev / validation / confirmation gate unchanged

This is not a live-system change and does not publish an RL feature.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.h327_cafef_foreign_flow_source_audit import (  # noqa: E402
    CONFIRMATION_END,
    CONFIRMATION_START,
    DEV_END,
    DEV_START,
    OUT_DIR,
    PASS_CORR,
    PASS_IC,
    PASS_PCT_YEARS,
    PREDICTIVE_END,
    PREDICTIVE_START,
    VALIDATION_END,
    VALIDATION_MIN_ABS_IC,
    VALIDATION_START,
    _json_safe,
    ic_for_frame,
    load_flow,
    load_stock_panel,
    phase_mask,
    rank_by_day,
    summarize_years,
    yearly_ic,
)
from src.run_summary import write_run_summary  # noqa: E402
from src.standalone_signal_utils import load_s1_frame, spearman_stat  # noqa: E402


DETAILS_DIR = ROOT / "artifacts" / "run_summaries"
ROLLING_WINDOWS = (20, 60)
FEATURE_COLS = [
    "xs_ff_net_accum_20d_rank",
    "xs_ff_net_accum_60d_rank",
    "xs_ff_net_accum_accel_20v20_rank",
    "xs_ff_ownership_delta_20d_rank",
    "xs_ff_ownership_delta_60d_rank",
    "xs_ff_room_scarcity_delta_20d_volnorm_rank",
]


def _rolling_sum(grouped: pd.core.groupby.DataFrameGroupBy, column: str, window: int) -> pd.Series:
    min_periods = max(5, window // 2)
    return grouped[column].rolling(window, min_periods=min_periods).sum().reset_index(level=0, drop=True)


def build_change_point_panel(flow: pd.DataFrame, stock: pd.DataFrame) -> pd.DataFrame:
    merged = stock.merge(flow, on=["time", "ticker"], how="inner", suffixes=("", "_flow"))
    merged = merged.sort_values(["ticker", "time"]).reset_index(drop=True)
    grouped = merged.groupby("ticker", group_keys=False)

    for window in ROLLING_WINDOWS:
        net_roll = _rolling_sum(grouped, "foreign_net_volume", window)
        volume_roll = _rolling_sum(grouped, "volume", window).replace(0, np.nan)
        merged[f"ff_net_accum_{window}d"] = net_roll / volume_roll
        merged[f"ff_ownership_delta_{window}d"] = grouped["foreign_ownership_pct"].diff(window)

    room_delta_20d = grouped["foreign_room_remaining"].diff(20)
    volume_60d = _rolling_sum(grouped, "volume", 60).replace(0, np.nan)
    merged["ff_room_scarcity_delta_20d_volnorm"] = -room_delta_20d / volume_60d

    merged["ff_net_accum_accel_20v20"] = (
        merged["ff_net_accum_20d"] - grouped["ff_net_accum_20d"].shift(20)
    )

    ranked = merged[["time", "ticker"]].copy()
    rank_specs = [
        ("ff_net_accum_20d", "xs_ff_net_accum_20d_rank"),
        ("ff_net_accum_60d", "xs_ff_net_accum_60d_rank"),
        ("ff_net_accum_accel_20v20", "xs_ff_net_accum_accel_20v20_rank"),
        ("ff_ownership_delta_20d", "xs_ff_ownership_delta_20d_rank"),
        ("ff_ownership_delta_60d", "xs_ff_ownership_delta_60d_rank"),
        ("ff_room_scarcity_delta_20d_volnorm", "xs_ff_room_scarcity_delta_20d_volnorm_rank"),
    ]
    for source_col, output_col in rank_specs:
        ranked = ranked.merge(rank_by_day(merged, source_col, output_col, ascending=True), on=["time", "ticker"])
    return ranked


def evaluate_change_point_features(merged: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    result_rows: list[dict[str, object]] = []
    yearly_rows: list[dict[str, object]] = []
    phase_specs = {
        "dev_2015_2022": (DEV_START, DEV_END),
        "validation_2023_2024": (VALIDATION_START, VALIDATION_END),
        "confirmation_2025": (CONFIRMATION_START, CONFIRMATION_END),
        "full_2015_2025": (PREDICTIVE_START, PREDICTIVE_END),
    }

    for feature_col in FEATURE_COLS:
        phase_stats: dict[str, dict[str, object]] = {}
        phase_years: dict[str, list[dict[str, object]]] = {}
        for phase, (start, end) in phase_specs.items():
            phase_frame = merged.loc[phase_mask(merged, start, end)].copy()
            stats = ic_for_frame(phase_frame, feature_col)
            years = yearly_ic(phase_frame, feature_col, phase)
            phase_stats[phase] = stats
            phase_years[phase] = years
            yearly_rows.extend(years)

        dev_ic = phase_stats["dev_2015_2022"].get("avg_ic")
        direction = 1 if (dev_ic or 0) >= 0 else -1
        dev_year_summary = summarize_years(phase_years["dev_2015_2022"], direction=direction)
        validation_ic = phase_stats["validation_2023_2024"].get("avg_ic")
        confirmation_ic = phase_stats["confirmation_2025"].get("avg_ic")
        corr_s1 = spearman_stat(merged[feature_col], merged["xs_proba"])
        dev_gate = (
            abs(dev_ic or 0) >= PASS_IC
            and (dev_year_summary.get("pct_directional_years") or 0) >= PASS_PCT_YEARS
        )
        validation_gate = validation_ic is not None and direction * validation_ic >= VALIDATION_MIN_ABS_IC
        confirmation_ok = confirmation_ic is not None and direction * confirmation_ic > 0
        corr_gate = abs(corr_s1) < PASS_CORR
        result_rows.append(
            {
                "feature": feature_col,
                "direction": "positive" if direction > 0 else "negative",
                "coverage": float(merged[feature_col].notna().mean()),
                "corr_with_s1": corr_s1,
                "dev_avg_ic": dev_ic,
                "dev_n": phase_stats["dev_2015_2022"].get("n"),
                "dev_years": dev_year_summary.get("years"),
                "dev_directional_years": dev_year_summary.get("directional_years"),
                "dev_pct_directional_years": dev_year_summary.get("pct_directional_years"),
                "validation_avg_ic": validation_ic,
                "validation_n": phase_stats["validation_2023_2024"].get("n"),
                "confirmation_avg_ic": confirmation_ic,
                "confirmation_n": phase_stats["confirmation_2025"].get("n"),
                "full_avg_ic": phase_stats["full_2015_2025"].get("avg_ic"),
                "full_n": phase_stats["full_2015_2025"].get("n"),
                "dev_gate": dev_gate,
                "validation_gate": validation_gate,
                "confirmation_ok": confirmation_ok,
                "corr_gate": corr_gate,
                "candidate_gate": bool(dev_gate and validation_gate and confirmation_ok and corr_gate),
                "near_gate_pre_confirmation": bool(dev_gate and validation_gate and corr_gate and not confirmation_ok),
            }
        )

    results = pd.DataFrame(result_rows)
    yearly = pd.DataFrame(yearly_rows)
    if not results.empty:
        results["abs_validation_ic"] = results["validation_avg_ic"].abs()
        results["abs_dev_ic"] = results["dev_avg_ic"].abs()
        results = results.sort_values(
            ["candidate_gate", "near_gate_pre_confirmation", "abs_validation_ic", "abs_dev_ic", "feature"],
            ascending=[False, False, False, False, True],
        ).reset_index(drop=True)

    passing = results.loc[results["candidate_gate"]].copy()
    near = results.loc[results["near_gate_pre_confirmation"]].copy()
    summary = {
        "merged_rows": int(len(merged)),
        "merged_tickers": int(merged["ticker"].nunique()) if not merged.empty else 0,
        "merged_dates": int(merged["time"].nunique()) if not merged.empty else 0,
        "feature_count": int(len(FEATURE_COLS)),
        "passing_features": passing["feature"].tolist() if not passing.empty else [],
        "near_features_pre_confirmation": near["feature"].tolist() if not near.empty else [],
        "best_feature": _json_safe(results.iloc[0].to_dict()) if not results.empty else {},
    }
    return results, yearly, summary


def main() -> int:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    flow = load_flow()
    stock = load_stock_panel()
    feature_panel = build_change_point_panel(flow, stock)
    s1 = load_s1_frame()
    merged = s1.merge(feature_panel, on=["time", "ticker"], how="inner")
    merged = merged.loc[phase_mask(merged, PREDICTIVE_START, PREDICTIVE_END)].copy()
    results, yearly, predictive_summary = evaluate_change_point_features(merged)

    results_path = OUT_DIR / f"{ts}_h345_foreign_accumulation_change_point_results.parquet"
    yearly_path = OUT_DIR / f"{ts}_h345_foreign_accumulation_change_point_yearly_ic.parquet"
    details_path = DETAILS_DIR / f"{ts}_h345_foreign_accumulation_change_point_details.json"
    results.to_parquet(results_path, index=False)
    yearly.to_parquet(yearly_path, index=False)

    passing_features = predictive_summary.get("passing_features") or []
    near_features = predictive_summary.get("near_features_pre_confirmation") or []
    if passing_features:
        verdict = "PASSED"
        branch_decision = (
            "Foreign accumulation change-points survived the first standalone gate. "
            "Next: run redundancy, liquidity, and transaction-cost audits before publishing anything."
        )
    elif near_features:
        verdict = "MIXED"
        branch_decision = (
            "Foreign accumulation change-points show pre-confirmation structure, but fail the 2025 "
            "confirmation gate. Keep only as offline evidence unless a distinct interaction changes the contract."
        )
    else:
        verdict = "FAILED"
        branch_decision = (
            "Foreign accumulation / ownership-change features do not clear the unchanged H327/H333 gate. "
            "Do not keep tuning this as a standalone H95 signal."
        )

    summary = {
        "verdict": verdict,
        "branch_decision": branch_decision,
        "predictive": predictive_summary,
    }
    details_path.write_text(
        json.dumps(
            {
                "summary": summary,
                "features": _json_safe(results.to_dict(orient="records")),
                "yearly_ic": _json_safe(yearly.to_dict(orient="records")),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    summary_path = write_run_summary(
        ts=ts,
        mode="research_branch_foreign_accumulation_change_point",
        name="h345_foreign_accumulation_change_point",
        summary=summary,
        artifacts={
            "feature_results": results_path,
            "yearly_ic": yearly_path,
            "details": details_path,
        },
        metadata={
            "hypothesis": (
                "CafeF foreign-flow alpha may live in accumulation / ownership regime changes "
                "rather than raw foreign buy/sell ranks or room-residual thresholds."
            ),
            "protocol": {
                "dev": f"{DEV_START}..{DEV_END}",
                "validation": f"{VALIDATION_START}..{VALIDATION_END}",
                "confirmation": f"{CONFIRMATION_START}..{CONFIRMATION_END}",
                "no_tuning_window": "2026+",
                "feature_count": len(FEATURE_COLS),
            },
        },
    )

    print("H345 foreign accumulation change-point")
    print("=" * 72)
    print(f"verdict: {verdict}")
    print(f"merged predictive rows: {predictive_summary['merged_rows']:,}")
    print("top feature rows:")
    display_cols = [
        "feature",
        "direction",
        "dev_avg_ic",
        "dev_directional_years",
        "dev_years",
        "validation_avg_ic",
        "confirmation_avg_ic",
        "corr_with_s1",
        "candidate_gate",
        "near_gate_pre_confirmation",
    ]
    print(results[display_cols].head(10).to_string(index=False))
    print(f"summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
