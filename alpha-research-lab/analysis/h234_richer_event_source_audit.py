"""
H234: Audit whether the CafeF company-news archive is a richer timestamped event source than event surface v1.
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
from src.news_event_source_research import (
    build_candidate_news_event_bundle,
    summarize_recent_event_window_coverage,
)
from src.run_summary import write_run_summary


RAW_NEWS_DIR = Path("data/news/cafef/raw")
RL_MATRIX_PATH = Path("data/features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = Path("data/features/execution/tradability_daily.parquet")
STOCK_DIR = Path("data/stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
OUT_DIR = ROOT / "artifacts/timing_data"

START_DATE = "2023-01-01"
END_DATE = "2025-12-31"
MIN_TICKER_FLOOR = 50
PREFERRED_TICKER_COUNT = 100


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-news-dir", type=str, default=str(RAW_NEWS_DIR))
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--start-date", type=str, default=START_DATE)
    parser.add_argument("--end-date", type=str, default=END_DATE)
    parser.add_argument("--portfolio-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    matrix = pd.read_parquet(Path(args.matrix), columns=["time", "ticker"]).copy()
    matrix["time"] = pd.to_datetime(matrix["time"], errors="coerce").dt.normalize()
    matrix = matrix.loc[
        (matrix["time"] >= pd.Timestamp(args.start_date))
        & (matrix["time"] <= pd.Timestamp(args.end_date))
    ].copy()
    universe_tickers = set(matrix["ticker"].dropna().astype(str).unique().tolist())

    bundle = build_candidate_news_event_bundle(
        raw_dir=Path(args.raw_news_dir),
        start_date=str(args.start_date),
        end_date=str(args.end_date),
        allowed_tickers=universe_tickers,
    )
    continuation = build_continuation_dataset(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=pd.Timestamp(args.start_date).year,
        end_year=pd.Timestamp(args.end_date).year,
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.portfolio_notional_vnd),
        round_trip_cost=float(args.round_trip_cost),
    )
    held_window_coverage = summarize_recent_event_window_coverage(
        panel=continuation.panel,
        daily_flags=bundle.daily_flags,
        windows=(1, 5, 20),
    )

    family_floor = 0
    if not bundle.family_summary.empty:
        family_floor = int(pd.to_numeric(bundle.family_summary["unique_tickers"], errors="coerce").fillna(0).max())
    first_timestamp = None
    last_timestamp = None
    if not bundle.article_events.empty:
        first_timestamp = pd.to_datetime(bundle.article_events["published_at"], errors="coerce").min()
        last_timestamp = pd.to_datetime(bundle.article_events["published_at"], errors="coerce").max()

    passed = bool(
        bundle.summary["title_ticker_articles"] > 0
        and bundle.summary["timestamped_title_ticker_articles"] >= bundle.summary["title_ticker_articles"] * 0.99
        and bundle.summary["candidate_unique_tickers"] >= MIN_TICKER_FLOOR
        and family_floor >= MIN_TICKER_FLOOR
        and first_timestamp is not None
        and last_timestamp is not None
        and pd.Timestamp(first_timestamp) <= pd.Timestamp("2023-12-31")
        and pd.Timestamp(last_timestamp) >= pd.Timestamp("2025-01-01")
    )

    article_events_path = OUT_DIR / f"{ts}_h234_richer_event_source_audit_articles.parquet"
    daily_flags_path = OUT_DIR / f"{ts}_h234_richer_event_source_audit_daily_flags.parquet"
    family_summary_path = OUT_DIR / f"{ts}_h234_richer_event_source_audit_family_summary.parquet"
    bundle.article_events.to_parquet(article_events_path, index=False)
    bundle.daily_flags.to_parquet(daily_flags_path, index=False)
    bundle.family_summary.to_parquet(family_summary_path, index=False)

    family_summary_records = bundle.family_summary.to_dict(orient="records") if not bundle.family_summary.empty else []
    write_run_summary(
        ts=ts,
        mode="timing_richer_event_source_audit",
        name="h234_richer_event_source_audit",
        summary={
            "analysis_window": {
                "start_date": str(args.start_date),
                "end_date": str(args.end_date),
            },
            "candidate_source": "cafef_company_news_archive_title_ticker_seed",
            "pass": passed,
            "pass_contract": {
                "min_ticker_floor": MIN_TICKER_FLOOR,
                "preferred_ticker_count": PREFERRED_TICKER_COUNT,
                "requires_exact_published_timestamp": True,
                "requires_company_specific_event_families": True,
            },
            "archive_summary": bundle.summary,
            "family_summary": family_summary_records,
            "held_window_coverage": held_window_coverage,
            "limitations": [
                "This is a conservative title-ticker seed audit, not a final extraction pipeline.",
                "Sparse held-row window coverage does not fail H234 by itself; H235 must test whether richer extraction materially improves information content or coverage.",
                "No predictive claim is made here.",
            ],
        },
        artifacts={
            "article_events": str(article_events_path),
            "daily_flags": str(daily_flags_path),
            "family_summary": str(family_summary_path),
        },
        metadata={
            "branch_contract": "H234 source identification only; H235 must sample-audit operational coverage and leakage risk before promotion.",
        },
    )


if __name__ == "__main__":
    main()
