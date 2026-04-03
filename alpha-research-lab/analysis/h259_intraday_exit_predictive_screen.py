"""
H259: Reduced-shape intraday predictive screen against the continuation target.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from path_utils import data_path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.additive_selector_research import load_summary_payload, resolve_summary_artifact
from src.continuation_exit_research import (
    BASE_CONTINUATION_FEATURES,
    CONTINUATION_HORIZON_DAYS,
    ContinuationModelSpec,
    build_continuation_dataset,
    fit_continuation_model,
)
from src.intraday_exit_research import (
    INTRADAY_SHAPE_ATOM_COLUMNS,
    REDUCED_SHAPE_FEATURE_COLUMNS,
    add_intraday_shape_atoms,
    merge_reduced_shape_panel,
)
from src.research_protocol import ResearchProtocol, assign_research_phase
from src.run_summary import write_run_summary


RL_MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
STOCK_DIR = data_path("stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
H258_SUMMARY_PATH = ROOT / "artifacts/run_summaries/latest_timing_reduced_shape_intraday_contract_audit.json"
OUT_DIR = ROOT / "artifacts/portfolio_baselines"

INTRADAY_RESTART_PROTOCOL = ResearchProtocol(
    dev_start_year=2023,
    dev_end_year=2023,
    validation_start_year=2024,
    validation_end_year=2024,
    confirmation_year=2025,
    forward_start_year=2026,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--h258-summary", type=str, default=str(H258_SUMMARY_PATH))
    parser.add_argument("--start-year", type=int, default=2023)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--portfolio-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--horizon-days", type=int, default=CONTINUATION_HORIZON_DAYS)
    return parser.parse_args()


def _to_float(row: pd.Series, column: str) -> float | None:
    value = pd.to_numeric(row.get(column), errors="coerce")
    return None if pd.isna(value) else float(value)


def main() -> None:
    args = parse_args()
    h258_summary = load_summary_payload(Path(args.h258_summary))
    if not bool(h258_summary.get("summary", {}).get("advance_to_h259", False)):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        write_run_summary(
            ts=ts,
            mode="portfolio_exit_intraday_reduced_shape_predictive_screen",
            name="h259_intraday_exit_predictive_screen",
            summary={
                "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
                "skipped": True,
                "reason": "H258 did not clear the reduced-shape contract gate",
            },
            artifacts={},
            metadata={"protocol": INTRADAY_RESTART_PROTOCOL.describe()},
        )
        return

    reduced_shape_path = resolve_summary_artifact(Path(args.h258_summary), "reduced_shape_panel")
    coverage_path = resolve_summary_artifact(Path(args.h258_summary), "coverage_frame")
    reduced_shape_panel = pd.read_parquet(reduced_shape_path)
    coverage_frame = pd.read_parquet(coverage_path)

    continuation = build_continuation_dataset(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.portfolio_notional_vnd),
        round_trip_cost=float(args.round_trip_cost),
        horizon_days=int(args.horizon_days),
    )
    merged = merge_reduced_shape_panel(
        continuation.panel,
        feature_panel=reduced_shape_panel,
        coverage_frame=coverage_frame,
    )
    observed = merged.loc[merged["intraday_observed"].fillna(False).astype(bool)].copy()
    observed["time"] = pd.to_datetime(observed["time"], errors="coerce").dt.normalize()
    observed = assign_research_phase(observed, date_column="time", protocol=INTRADAY_RESTART_PROTOCOL)
    observed = add_intraday_shape_atoms(observed)

    specs = [
        ContinuationModelSpec(name="path_core_observed", feature_columns=tuple(BASE_CONTINUATION_FEATURES)),
        ContinuationModelSpec(name="intraday_shape_core", feature_columns=tuple(REDUCED_SHAPE_FEATURE_COLUMNS)),
        ContinuationModelSpec(name="intraday_shape_atoms", feature_columns=tuple(INTRADAY_SHAPE_ATOM_COLUMNS)),
        ContinuationModelSpec(
            name="intraday_shape_plus_path",
            feature_columns=tuple(list(BASE_CONTINUATION_FEATURES) + list(REDUCED_SHAPE_FEATURE_COLUMNS)),
        ),
    ]
    fits = [fit_continuation_model(observed, spec=spec) for spec in specs]
    results = pd.DataFrame([fit.summary_row for fit in fits]).sort_values(
        by=["promoted", "validation_auc", "validation_top_quintile_hold_advantage", "confirmation_auc", "model_name"],
        ascending=[False, False, False, False, True],
        ignore_index=True,
    )

    baseline_row = results.loc[results["model_name"] == "path_core_observed"].iloc[0]
    intraday_results = results.loc[results["model_name"] != "path_core_observed"].reset_index(drop=True)
    best_intraday_row = intraday_results.iloc[0]
    winner = fits[[fit.spec.name for fit in fits].index(str(results.iloc[0]["model_name"]))]

    validation_auc_delta = (_to_float(best_intraday_row, "validation_auc") or 0.0) - (_to_float(baseline_row, "validation_auc") or 0.0)
    validation_tq_delta = (
        (_to_float(best_intraday_row, "validation_top_quintile_hold_advantage") or 0.0)
        - (_to_float(baseline_row, "validation_top_quintile_hold_advantage") or 0.0)
    )
    confirmation_tq = _to_float(best_intraday_row, "confirmation_top_quintile_hold_advantage")
    passed = bool(best_intraday_row.get("promoted"))
    mixed = bool(
        not passed
        and validation_auc_delta >= 0.0
        and validation_tq_delta > 0.0
        and confirmation_tq is not None
        and confirmation_tq > -0.02
    )
    verdict = "PASSED" if passed else "MIXED" if mixed else "FAILED"

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h259_intraday_exit_predictive_screen_results.parquet"
    scored_path = OUT_DIR / f"{ts}_h259_intraday_exit_predictive_screen_scored_dataset.parquet"
    observed_path = OUT_DIR / f"{ts}_h259_intraday_exit_predictive_screen_observed_panel.parquet"
    baseline_daily_path = OUT_DIR / f"{ts}_h259_intraday_exit_predictive_screen_baseline_daily.parquet"

    results.to_parquet(results_path, index=False)
    winner.scored_dataset.to_parquet(scored_path, index=False)
    observed.to_parquet(observed_path, index=False)
    continuation.baseline_daily.to_parquet(baseline_daily_path, index=False)

    write_run_summary(
        ts=ts,
        mode="portfolio_exit_intraday_reduced_shape_predictive_screen",
        name="h259_intraday_exit_predictive_screen",
        summary={
            "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
            "decision": verdict,
            "observed_row_count": int(len(observed)),
            "candidate_row_count": int(len(merged)),
            "observed_row_share": float(len(observed) / len(merged)) if len(merged) else 0.0,
            "baseline_model": baseline_row.to_dict(),
            "best_intraday_model": best_intraday_row.to_dict(),
            "validation_auc_delta_vs_path_core": validation_auc_delta,
            "validation_top_quintile_delta_vs_path_core": validation_tq_delta,
            "winner": results.iloc[0].to_dict(),
        },
        artifacts={
            "results": str(results_path),
            "scored_dataset": str(scored_path),
            "observed_panel": str(observed_path),
            "baseline_daily": str(baseline_daily_path),
        },
        metadata={
            "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
            "branch_contract": "Reduced-shape predictive screen on the 2023-2025 observed intraday subset only",
        },
    )


if __name__ == "__main__":
    main()
