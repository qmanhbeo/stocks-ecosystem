"""
H235: Sample-audit the passed CafeF news-source candidate and test whether a
strict extraction expansion materially improves operational value over the H234
seed without losing first-public timestamp integrity.
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
from src.news_event_source_research import (
    build_alias_expanded_news_event_bundle,
    build_candidate_news_event_bundle_from_scan,
    build_strict_title_alias_map,
    evaluate_title_alias_map_holdout,
    scan_news_event_archive,
    summarize_company_event_novelty_vs_v1,
    summarize_recent_event_window_coverage,
)
from src.run_summary import write_run_summary


RAW_NEWS_DIR = data_path("news/cafef/raw")
EVENT_SURFACE_V1_PATH = data_path("features/event_surface_daily.parquet")
RL_MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
STOCK_DIR = data_path("stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
OUT_DIR = ROOT / "artifacts/timing_data"

START_DATE = "2023-01-01"
END_DATE = "2025-12-31"
ALIAS_TRAIN_END_DATE = "2024-12-31"
ALIAS_HOLDOUT_START_DATE = "2025-01-01"
ALIAS_MIN_SUPPORT = 3
ALIAS_MIN_DOMINANCE = 0.9
PASS_ALIAS_PRECISION = 0.95
MIXED_ALIAS_PRECISION = 0.85
PASS_HELD_COVERAGE_5D = 0.40
MIXED_MIN_ADDED_ARTICLES = 50
MIXED_MIN_NOVEL_SHARE = 0.50


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-news-dir", type=str, default=str(RAW_NEWS_DIR))
    parser.add_argument("--event-surface", type=str, default=str(EVENT_SURFACE_V1_PATH))
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--start-date", type=str, default=START_DATE)
    parser.add_argument("--end-date", type=str, default=END_DATE)
    parser.add_argument("--alias-train-end-date", type=str, default=ALIAS_TRAIN_END_DATE)
    parser.add_argument("--alias-holdout-start-date", type=str, default=ALIAS_HOLDOUT_START_DATE)
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

    scan = scan_news_event_archive(
        raw_dir=Path(args.raw_news_dir),
        start_date=str(args.start_date),
        end_date=str(args.end_date),
        allowed_tickers=universe_tickers,
    )
    seed_bundle = build_candidate_news_event_bundle_from_scan(scan)
    alias_map = build_strict_title_alias_map(
        scan,
        train_start_date=str(args.start_date),
        train_end_date=str(args.alias_train_end_date),
        min_support=ALIAS_MIN_SUPPORT,
        min_dominance=ALIAS_MIN_DOMINANCE,
    )
    alias_holdout_df, alias_holdout_summary = evaluate_title_alias_map_holdout(
        scan,
        alias_map,
        holdout_start_date=str(args.alias_holdout_start_date),
        holdout_end_date=str(args.end_date),
    )
    expanded_bundle, alias_assignments = build_alias_expanded_news_event_bundle(scan, alias_map)

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
    seed_held_window_coverage = summarize_recent_event_window_coverage(
        panel=continuation.panel,
        daily_flags=seed_bundle.daily_flags,
        windows=(1, 5, 20),
    )
    expanded_held_window_coverage = summarize_recent_event_window_coverage(
        panel=continuation.panel,
        daily_flags=expanded_bundle.daily_flags,
        windows=(1, 5, 20),
    )

    event_surface_v1 = pd.read_parquet(Path(args.event_surface))
    event_surface_v1["time"] = pd.to_datetime(event_surface_v1["time"], errors="coerce").dt.normalize()
    event_surface_v1 = event_surface_v1.loc[
        (event_surface_v1["time"] >= pd.Timestamp(args.start_date))
        & (event_surface_v1["time"] <= pd.Timestamp(args.end_date))
    ].copy()
    seed_novelty_vs_v1 = summarize_company_event_novelty_vs_v1(
        daily_flags=seed_bundle.daily_flags,
        event_surface_v1=event_surface_v1,
    )
    expanded_novelty_vs_v1 = summarize_company_event_novelty_vs_v1(
        daily_flags=expanded_bundle.daily_flags,
        event_surface_v1=event_surface_v1,
    )

    seed_coverage_5d = float(seed_held_window_coverage.get("recent_has_company_event_article_5d", 0.0))
    expanded_coverage_5d = float(expanded_held_window_coverage.get("recent_has_company_event_article_5d", 0.0))
    coverage_delta_5d = expanded_coverage_5d - seed_coverage_5d
    alias_precision = alias_holdout_summary.get("assigned_precision")
    alias_unique_articles = int(expanded_bundle.summary.get("linkage_modes", {}).get("title_alias_unique_articles", 0))
    expanded_novel_share = expanded_novelty_vs_v1.get("novel_daily_share_vs_v1")

    decision = "FAILED"
    if (
        alias_precision is not None
        and float(alias_precision) >= PASS_ALIAS_PRECISION
        and expanded_bundle.summary.get("candidate_unique_tickers", 0) >= 100
        and expanded_coverage_5d >= PASS_HELD_COVERAGE_5D
    ):
        decision = "PASSED"
    elif (
        alias_precision is not None
        and float(alias_precision) >= MIXED_ALIAS_PRECISION
        and alias_unique_articles >= MIXED_MIN_ADDED_ARTICLES
        and expanded_novel_share is not None
        and float(expanded_novel_share) >= MIXED_MIN_NOVEL_SHARE
    ):
        decision = "MIXED"

    artifact_stem = f"{ts}_h235_event_source_sample_audit"
    expanded_article_events_path = OUT_DIR / f"{artifact_stem}_expanded_articles.parquet"
    expanded_daily_flags_path = OUT_DIR / f"{artifact_stem}_expanded_daily_flags.parquet"
    alias_map_path = OUT_DIR / f"{artifact_stem}_alias_map.parquet"
    alias_holdout_path = OUT_DIR / f"{artifact_stem}_alias_holdout.parquet"
    alias_assignments_path = OUT_DIR / f"{artifact_stem}_alias_assignments.parquet"

    expanded_bundle.article_events.to_parquet(expanded_article_events_path, index=False)
    expanded_bundle.daily_flags.to_parquet(expanded_daily_flags_path, index=False)
    alias_map.to_parquet(alias_map_path, index=False)
    alias_holdout_df.to_parquet(alias_holdout_path, index=False)
    alias_assignments.to_parquet(alias_assignments_path, index=False)

    coverage_delta_summary = {
        key: float(expanded_held_window_coverage.get(key, 0.0) - seed_held_window_coverage.get(key, 0.0))
        for key in expanded_held_window_coverage.keys()
    }
    next_action = {
        "PASSED": "Open H236 and publish an event surface v2 candidate before rerunning event-driven timing research.",
        "MIXED": "Do not open H236 yet; keep the richer source as acquisition evidence only and require a cleaner mapping contract before publication.",
        "FAILED": "Close the richer event-source subbranch on the current archive, keep H236 closed, and route effort back to provisional intraday/H232 or live monitoring.",
    }[decision]
    write_run_summary(
        ts=ts,
        mode="timing_event_source_sample_audit",
        name="h235_event_source_sample_audit",
        summary={
            "analysis_window": {"start_date": str(args.start_date), "end_date": str(args.end_date)},
            "candidate_source": "cafef_company_news_archive_strict_alias_sample_audit",
            "decision": decision,
            "pass": bool(decision == "PASSED"),
            "pass_contract": {
                "alias_train_window": {"start_date": str(args.start_date), "end_date": str(args.alias_train_end_date)},
                "alias_holdout_window": {"start_date": str(args.alias_holdout_start_date), "end_date": str(args.end_date)},
                "alias_min_support": ALIAS_MIN_SUPPORT,
                "alias_min_dominance": ALIAS_MIN_DOMINANCE,
                "pass_alias_precision": PASS_ALIAS_PRECISION,
                "mixed_alias_precision": MIXED_ALIAS_PRECISION,
                "pass_held_row_coverage_5d": PASS_HELD_COVERAGE_5D,
                "mixed_min_added_articles": MIXED_MIN_ADDED_ARTICLES,
                "mixed_min_novel_share": MIXED_MIN_NOVEL_SHARE,
            },
            "seed_summary": seed_bundle.summary,
            "expanded_summary": expanded_bundle.summary,
            "alias_map_summary": {
                "alias_rows": int(len(alias_map)),
                "alias_unique_tickers": int(alias_map["ticker"].nunique()) if not alias_map.empty else 0,
                "max_support": int(alias_map["support"].max()) if not alias_map.empty else 0,
            },
            "alias_holdout_summary": alias_holdout_summary,
            "seed_held_window_coverage": seed_held_window_coverage,
            "expanded_held_window_coverage": expanded_held_window_coverage,
            "coverage_delta": coverage_delta_summary,
            "seed_novelty_vs_v1": seed_novelty_vs_v1,
            "expanded_novelty_vs_v1": expanded_novelty_vs_v1,
            "next_action": next_action,
            "limitations": [
                "Alias expansion is evaluated only as a strict title-level audit; no body-text entity linking or external company-name map is introduced here.",
                "A high novelty share versus event surface v1 does not by itself imply operational coverage or predictive value.",
                "No 2026+ data is used.",
            ],
        },
        artifacts={
            "expanded_article_events": expanded_article_events_path,
            "expanded_daily_flags": expanded_daily_flags_path,
            "alias_map": alias_map_path,
            "alias_holdout": alias_holdout_path,
            "alias_assignments": alias_assignments_path,
        },
        metadata={
            "branch_contract": "H235 must prove operational improvement beyond event surface v1 without losing first-public timestamp integrity; only PASSED may open H236.",
            "decision_inputs": {
                "seed_coverage_5d": seed_coverage_5d,
                "expanded_coverage_5d": expanded_coverage_5d,
                "coverage_delta_5d": coverage_delta_5d,
                "alias_precision": alias_precision,
                "alias_unique_articles": alias_unique_articles,
                "expanded_novel_share": expanded_novel_share,
            },
        },
    )


if __name__ == "__main__":
    main()
