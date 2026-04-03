"""
H258: Reduced-shape intraday contract audit on the current CafeF 1H surface.
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

from src.continuation_exit_research import build_continuation_dataset
from src.intraday_acquisition_research import (
    build_intraday_coverage_taxonomy,
    list_available_intraday_tickers,
    load_tradability_window,
    select_pilot_tickers,
    summarize_coverage_against_continuation,
)
from src.intraday_exit_research import (
    build_reduced_shape_feature_panel,
    summarize_reduced_shape_feature_panel,
)
from src.run_summary import write_run_summary


RL_MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
SECTOR_PATH = data_path("features/sector_classification.parquet")
STOCK_DIR = data_path("stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
OUT_DIR = ROOT / "artifacts/timing_data"

START_DATE = "2023-01-01"
END_DATE = "2025-12-31"
PILOT_SAMPLE_SIZE = 20
HELD_ROW_COVERAGE_GATE = 0.90
MISSING_SESSION_GATE = 0.10
CORE_FEATURE_SHARE_GATE = 0.98
LIQUID_COMPLETE_DAY_GATE = 0.95


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--sector", type=str, default=str(SECTOR_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--start-date", type=str, default=START_DATE)
    parser.add_argument("--end-date", type=str, default=END_DATE)
    parser.add_argument("--sample-size", type=int, default=PILOT_SAMPLE_SIZE)
    parser.add_argument("--portfolio-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    return parser.parse_args()


def _liquid_role_summary(ticker_summary: pd.DataFrame, pilot_selection: pd.DataFrame) -> pd.DataFrame:
    if ticker_summary.empty or pilot_selection.empty:
        return pd.DataFrame()
    merged = ticker_summary.merge(
        pilot_selection[["ticker", "pilot_role"]],
        on="ticker",
        how="inner",
    )
    metrics = [
        "complete_day_share",
        "midday_window_share",
        "open_gap_feature_share",
        "first_60m_feature_share",
        "close_hour_feature_share",
        "median_bars_per_day",
    ]
    present_metrics = [column for column in metrics if column in merged.columns]
    if not present_metrics:
        return pd.DataFrame()
    return merged.groupby("pilot_role", dropna=False)[present_metrics].mean(numeric_only=True).reset_index()


def main() -> None:
    args = parse_args()
    stock_dir = Path(args.stock_dir)
    start_date = str(args.start_date)
    end_date = str(args.end_date)

    available_tickers = list_available_intraday_tickers(stock_dir)
    reduced_bundle = build_reduced_shape_feature_panel(
        stock_dir=stock_dir,
        start_date=start_date,
        end_date=end_date,
        tickers=available_tickers,
    )

    pilot_selection = select_pilot_tickers(
        stock_dir=stock_dir,
        sector_path=Path(args.sector),
        sample_size=int(args.sample_size),
    )
    pilot_role_summary = _liquid_role_summary(reduced_bundle.ticker_summary, pilot_selection)

    tradability = load_tradability_window(
        tradability_path=Path(args.tradability),
        start_date=start_date,
        end_date=end_date,
        tickers=available_tickers,
    )
    coverage_frame, coverage_ticker_summary = build_intraday_coverage_taxonomy(
        stock_dir=stock_dir,
        tradability=tradability,
        start_date=start_date,
        end_date=end_date,
    )

    continuation = build_continuation_dataset(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=stock_dir,
        benchmark_path=Path(args.benchmark),
        start_year=pd.Timestamp(start_date).year,
        end_year=pd.Timestamp(end_date).year,
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.portfolio_notional_vnd),
        round_trip_cost=float(args.round_trip_cost),
    )
    coverage_summary = summarize_coverage_against_continuation(
        coverage_frame=coverage_frame,
        ticker_summary=coverage_ticker_summary,
        continuation_panel=continuation.panel,
    )

    reduced_panel = reduced_bundle.feature_panel.copy()
    if not reduced_panel.empty:
        reduced_panel["session_date"] = pd.to_datetime(reduced_panel["session_date"], errors="coerce").dt.normalize()
        reduced_panel = reduced_panel.merge(
            coverage_frame[["session_date", "ticker", "coverage_bucket"]].drop_duplicates(),
            on=["session_date", "ticker"],
            how="left",
        )
        reduced_panel["intraday_observed"] = True

    feature_summary = summarize_reduced_shape_feature_panel(reduced_panel)

    coverage_ok = bool(
        float(coverage_summary.get("held_row_coverage_lower_bound", 0.0)) >= HELD_ROW_COVERAGE_GATE
        and float(coverage_summary.get("missing_session_rate_in_window", 1.0)) < MISSING_SESSION_GATE
    )
    shape_ok = bool(
        float(feature_summary.get("open_gap_feature_share") or 0.0) >= CORE_FEATURE_SHARE_GATE
        and float(feature_summary.get("first_60m_feature_share") or 0.0) >= CORE_FEATURE_SHARE_GATE
        and float(feature_summary.get("close_hour_feature_share") or 0.0) >= CORE_FEATURE_SHARE_GATE
    )
    liquid_roles = pilot_role_summary.loc[pilot_role_summary["pilot_role"].isin(["liquid_bank", "liquid_industrial", "liquid_fill"])].copy()
    liquid_roles_ok = bool(
        not liquid_roles.empty
        and (pd.to_numeric(liquid_roles["complete_day_share"], errors="coerce") >= LIQUID_COMPLETE_DAY_GATE).all()
        and (pd.to_numeric(liquid_roles["first_60m_feature_share"], errors="coerce") >= CORE_FEATURE_SHARE_GATE).all()
        and (pd.to_numeric(liquid_roles["close_hour_feature_share"], errors="coerce") >= CORE_FEATURE_SHARE_GATE).all()
    )

    if coverage_ok and shape_ok and liquid_roles_ok:
        verdict = "PASSED"
    elif coverage_ok and shape_ok:
        verdict = "MIXED"
    else:
        verdict = "FAILED"

    universal_full_session_ready = bool(float(coverage_summary.get("complete_day_share_present", 0.0)) >= 0.90)
    advance_to_h259 = verdict in {"PASSED", "MIXED"}
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    reduced_panel_path = OUT_DIR / f"{ts}_h258_reduced_shape_intraday_contract_panel.parquet"
    ticker_summary_path = OUT_DIR / f"{ts}_h258_reduced_shape_intraday_ticker_summary.parquet"
    coverage_path = OUT_DIR / f"{ts}_h258_reduced_shape_intraday_coverage.parquet"
    coverage_summary_path = OUT_DIR / f"{ts}_h258_reduced_shape_intraday_coverage_summary.parquet"
    pilot_role_summary_path = OUT_DIR / f"{ts}_h258_reduced_shape_intraday_pilot_role_summary.parquet"

    reduced_panel.to_parquet(reduced_panel_path, index=False)
    reduced_bundle.ticker_summary.to_parquet(ticker_summary_path, index=False)
    coverage_frame.to_parquet(coverage_path, index=False)
    coverage_ticker_summary.to_parquet(coverage_summary_path, index=False)
    pilot_role_summary.to_parquet(pilot_role_summary_path, index=False)

    write_run_summary(
        ts=ts,
        mode="timing_reduced_shape_intraday_contract_audit",
        name="h258_reduced_shape_intraday_contract_audit",
        summary={
            "analysis_window": {
                "start_date": start_date,
                "end_date": end_date,
            },
            "decision": verdict,
            "advance_to_h259": advance_to_h259,
            "universal_full_session_ready": universal_full_session_ready,
            "coverage_gate": {
                "held_row_coverage_min": HELD_ROW_COVERAGE_GATE,
                "missing_session_rate_max": MISSING_SESSION_GATE,
                "passed": coverage_ok,
            },
            "feature_gate": {
                "core_feature_share_min": CORE_FEATURE_SHARE_GATE,
                "liquid_complete_day_share_min": LIQUID_COMPLETE_DAY_GATE,
                "shape_passed": shape_ok,
                "liquid_roles_passed": liquid_roles_ok,
            },
            "coverage_summary": coverage_summary,
            "feature_summary": feature_summary,
            "pilot_role_summary": pilot_role_summary.to_dict(orient="records"),
        },
        artifacts={
            "reduced_shape_panel": str(reduced_panel_path),
            "ticker_summary": str(ticker_summary_path),
            "coverage_frame": str(coverage_path),
            "coverage_ticker_summary": str(coverage_summary_path),
            "pilot_role_summary": str(pilot_role_summary_path),
        },
        metadata={
            "branch_contract": "Reduced-shape intraday contract audit only; universal five-bar / auction publication remains unresolved",
        },
    )


if __name__ == "__main__":
    main()
