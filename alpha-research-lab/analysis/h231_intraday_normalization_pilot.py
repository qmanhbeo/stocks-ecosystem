"""
H231: Partial intraday normalization pilot with an explicitly non-final H232 lower-bound estimate.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

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
    build_intraday_pilot_bundle,
    list_available_intraday_tickers,
    load_tradability_window,
    select_pilot_tickers,
    summarize_coverage_against_continuation,
)
from src.run_summary import write_run_summary


RL_MATRIX_PATH = Path("data/features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = Path("data/features/execution/tradability_daily.parquet")
SECTOR_PATH = Path("data/features/sector_classification.parquet")
STOCK_DIR = Path("data/stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
OUT_DIR = ROOT / "artifacts/timing_data"

START_DATE = "2023-01-01"
END_DATE = "2025-12-31"
PILOT_SAMPLE_SIZE = 20
PILOT_COMPLETE_DAY_GATE = 0.90
PILOT_FEATURE_SHARE_GATE = 0.95


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


def main() -> None:
    args = parse_args()
    stock_dir = Path(args.stock_dir)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    pilot_selection = select_pilot_tickers(
        stock_dir=stock_dir,
        sector_path=Path(args.sector),
        sample_size=int(args.sample_size),
    )
    pilot_feature_frames: list[pd.DataFrame] = []
    pilot_factor_frames: list[pd.DataFrame] = []
    pilot_summary_rows: list[dict[str, object]] = []
    for row in pilot_selection.itertuples(index=False):
        bundle = build_intraday_pilot_bundle(
            stock_dir=stock_dir,
            ticker=str(row.ticker),
            start_date=str(args.start_date),
            end_date=str(args.end_date),
        )
        summary_row = {**dict(row._asdict()), **bundle.summary_row}
        pilot_summary_rows.append(summary_row)
        if not bundle.features.empty:
            pilot_feature_frames.append(bundle.features)
        if not bundle.factors.empty:
            factor_frame = bundle.factors.copy()
            factor_frame["ticker"] = str(row.ticker)
            pilot_factor_frames.append(factor_frame)

    pilot_features = pd.concat(pilot_feature_frames, ignore_index=True) if pilot_feature_frames else pd.DataFrame()
    pilot_factors = pd.concat(pilot_factor_frames, ignore_index=True) if pilot_factor_frames else pd.DataFrame()
    pilot_ticker_summary = pd.DataFrame(pilot_summary_rows)

    available_tickers = list_available_intraday_tickers(stock_dir)
    tradability = load_tradability_window(
        tradability_path=Path(args.tradability),
        start_date=str(args.start_date),
        end_date=str(args.end_date),
        tickers=available_tickers,
    )
    coverage_frame, coverage_ticker_summary = build_intraday_coverage_taxonomy(
        stock_dir=stock_dir,
        tradability=tradability,
        start_date=str(args.start_date),
        end_date=str(args.end_date),
    )
    if not coverage_frame.empty:
        coverage_frame = coverage_frame.merge(
            pilot_selection[["ticker", "pilot_role"]],
            on="ticker",
            how="left",
        )
        coverage_frame["pilot_selected"] = coverage_frame["pilot_role"].notna()

    continuation = build_continuation_dataset(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=stock_dir,
        benchmark_path=Path(args.benchmark),
        start_year=pd.Timestamp(args.start_date).year,
        end_year=pd.Timestamp(args.end_date).year,
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.portfolio_notional_vnd),
        round_trip_cost=float(args.round_trip_cost),
    )
    coverage_summary = summarize_coverage_against_continuation(
        coverage_frame=coverage_frame,
        ticker_summary=coverage_ticker_summary,
        continuation_panel=continuation.panel,
    )

    pilot_success_tickers = int((pilot_ticker_summary["error"].isna()).sum()) if "error" in pilot_ticker_summary.columns else int(len(pilot_ticker_summary))
    pilot_complete_day_share = float(pilot_features["complete_day"].mean()) if not pilot_features.empty else 0.0
    pilot_first_hour_share = float(pilot_features["first_60m_return"].notna().mean()) if not pilot_features.empty else 0.0
    pilot_close_hour_share = float(pilot_features["close_hour_return"].notna().mean()) if not pilot_features.empty else 0.0
    pilot_midday_share = float(pilot_features["has_midday_window"].mean()) if not pilot_features.empty else 0.0

    h231_passed = bool(
        pilot_success_tickers >= int(args.sample_size)
        and pilot_complete_day_share >= PILOT_COMPLETE_DAY_GATE
        and pilot_first_hour_share >= PILOT_FEATURE_SHARE_GATE
        and pilot_close_hour_share >= PILOT_FEATURE_SHARE_GATE
    )

    pilot_features_path = OUT_DIR / f"{ts}_h231_intraday_normalization_pilot_features.parquet"
    pilot_factors_path = OUT_DIR / f"{ts}_h231_intraday_normalization_pilot_factors.parquet"
    pilot_ticker_summary_path = OUT_DIR / f"{ts}_h231_intraday_normalization_pilot_ticker_summary.parquet"
    coverage_path = OUT_DIR / f"{ts}_h231_intraday_normalization_pilot_coverage.parquet"
    coverage_summary_path = OUT_DIR / f"{ts}_h231_intraday_normalization_pilot_coverage_summary.parquet"

    pilot_features.to_parquet(pilot_features_path, index=False)
    pilot_factors.to_parquet(pilot_factors_path, index=False)
    pilot_ticker_summary.to_parquet(pilot_ticker_summary_path, index=False)
    coverage_frame.to_parquet(coverage_path, index=False)
    coverage_ticker_summary.to_parquet(coverage_summary_path, index=False)

    write_run_summary(
        ts=ts,
        mode="timing_intraday_normalization_pilot",
        name="h231_intraday_normalization_pilot",
        summary={
            "analysis_window": {
                "start_date": str(args.start_date),
                "end_date": str(args.end_date),
            },
            "no_alpha_claim": True,
            "h231_pilot": {
                "sample_size": int(args.sample_size),
                "selected_tickers": pilot_selection["ticker"].tolist(),
                "selected_roles": pilot_selection[["ticker", "pilot_role"]].to_dict(orient="records"),
                "selected_count": int(len(pilot_selection)),
                "successful_tickers": pilot_success_tickers,
                "passed": h231_passed,
                "complete_day_gate": PILOT_COMPLETE_DAY_GATE,
                "feature_share_gate": PILOT_FEATURE_SHARE_GATE,
                "complete_day_share": pilot_complete_day_share,
                "first_60m_feature_share": pilot_first_hour_share,
                "close_hour_feature_share": pilot_close_hour_share,
                "midday_window_share": pilot_midday_share,
                "pilot_day_rows": int(len(pilot_features)),
            },
            "early_h232_lower_bound": {
                "final_gate_deferred": True,
                **coverage_summary,
            },
        },
        artifacts={
            "pilot_features": str(pilot_features_path),
            "pilot_factors": str(pilot_factors_path),
            "pilot_ticker_summary": str(pilot_ticker_summary_path),
            "coverage_frame": str(coverage_path),
            "coverage_ticker_summary": str(coverage_summary_path),
        },
        metadata={
            "branch_contract": "H231 pilot only; H232 lower-bound estimate is provisional while fetch remains partial",
        },
    )


if __name__ == "__main__":
    main()
