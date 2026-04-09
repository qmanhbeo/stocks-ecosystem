"""
H301: CafeF event-surface v2 pilot.

Question:
    Can alias-expanded CafeF company-news events support a richer company-specific
    event surface with enough novelty and timestamp integrity to justify a later
    predictive screen?
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from path_utils import data_path

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
OUT_DIR = ROOT / "artifacts" / "timing_data"

START_DATE = "2023-01-01"
END_DATE = "2025-12-31"
ALIAS_TRAIN_END_DATE = "2024-12-31"
ALIAS_HOLDOUT_START_DATE = "2025-01-01"
ALIAS_MIN_SUPPORT = 3
ALIAS_MIN_DOMINANCE = 0.9


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


def _build_v1_daily_flags(event_surface: pd.DataFrame) -> pd.DataFrame:
    v1 = event_surface.copy()
    proxy_cols = [
        "dividend_window_pre_20d",
        "dividend_window_post_5d",
        "issuance_window_pre_20d",
        "issuance_window_post_5d",
        "recent_insider_filing_5d",
        "recent_major_holder_filing_5d",
        "recent_any_filing_5d",
    ]
    for column in proxy_cols:
        v1[column] = pd.to_numeric(v1[column], errors="coerce").fillna(0.0)
    v1["has_company_proxy_v1"] = v1[proxy_cols].gt(0.0).any(axis=1).astype(int)
    return v1[["time", "ticker", "has_company_proxy_v1"]].copy()


def _build_pilot_surface(universe: pd.DataFrame, article_events: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    events = article_events.copy()
    events["time"] = pd.to_datetime(events["time"], errors="coerce").dt.normalize()
    events["published_at"] = pd.to_datetime(events["published_at"], errors="coerce")
    first_public = (
        events.groupby(["time", "ticker", "event_family"], as_index=False)
        .agg(
            first_published_at=("published_at", "min"),
            article_count_1d=("article_id", "nunique"),
        )
        .sort_values(["time", "ticker", "event_family"])
        .reset_index(drop=True)
    )
    count_wide = (
        first_public.pivot_table(
            index=["time", "ticker"],
            columns="event_family",
            values="article_count_1d",
            aggfunc="sum",
            fill_value=0,
        )
        .reset_index()
    )
    count_wide.columns.name = None
    count_columns = []
    for column in [c for c in count_wide.columns if c not in {"time", "ticker"}]:
        renamed = f"event_count__{column}"
        count_wide = count_wide.rename(columns={column: renamed})
        count_columns.append(renamed)
    count_wide["event_count__all"] = count_wide[count_columns].sum(axis=1) if count_columns else 0

    pilot = universe.merge(count_wide, on=["time", "ticker"], how="left")
    for column in count_columns + ["event_count__all"]:
        pilot[column] = pd.to_numeric(pilot[column], errors="coerce").fillna(0.0)
        binary_col = column.replace("event_count__", "event_flag__")
        pilot[binary_col] = pilot[column].gt(0.0).astype(int)
        recent_col = column.replace("event_count__", "event_recent5__")
        pilot[recent_col] = (
            pilot.sort_values(["ticker", "time"])
            .groupby("ticker")[column]
            .rolling(window=5, min_periods=1)
            .sum()
            .reset_index(level=0, drop=True)
            .astype(float)
        )
    pilot["has_company_event_article_v2"] = pilot["event_count__all"].gt(0.0).astype(int)
    pilot["recent_company_event_article_v2_5d"] = (
        pilot.sort_values(["ticker", "time"])
        .groupby("ticker")["has_company_event_article_v2"]
        .rolling(window=5, min_periods=1)
        .sum()
        .reset_index(level=0, drop=True)
        .astype(float)
    )
    return pilot, first_public


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
    seed_coverage = summarize_recent_event_window_coverage(
        panel=continuation.panel,
        daily_flags=seed_bundle.daily_flags,
        windows=(1, 5, 20),
    )
    pilot_coverage = summarize_recent_event_window_coverage(
        panel=continuation.panel,
        daily_flags=expanded_bundle.daily_flags,
        windows=(1, 5, 20),
    )

    event_surface_v1 = pd.read_parquet(Path(args.event_surface)).copy()
    event_surface_v1["time"] = pd.to_datetime(event_surface_v1["time"], errors="coerce").dt.normalize()
    event_surface_v1 = event_surface_v1.loc[
        (event_surface_v1["time"] >= pd.Timestamp(args.start_date))
        & (event_surface_v1["time"] <= pd.Timestamp(args.end_date))
    ].copy()
    v1_daily_flags = _build_v1_daily_flags(event_surface_v1)
    v1_coverage = summarize_recent_event_window_coverage(
        panel=continuation.panel,
        daily_flags=v1_daily_flags,
        windows=(1, 5, 20),
    )
    novelty_vs_v1 = summarize_company_event_novelty_vs_v1(
        daily_flags=expanded_bundle.daily_flags,
        event_surface_v1=event_surface_v1,
    )

    pilot_surface, first_public = _build_pilot_surface(matrix[["time", "ticker"]].drop_duplicates(), expanded_bundle.article_events)
    decision = "FAILED"
    pilot_coverage_5d = float(pilot_coverage.get("recent_has_company_event_article_5d", 0.0))
    seed_coverage_5d = float(seed_coverage.get("recent_has_company_event_article_5d", 0.0))
    alias_precision = alias_holdout_summary.get("assigned_precision")
    novel_share = novelty_vs_v1.get("novel_daily_share_vs_v1")
    if (
        alias_precision is not None
        and float(alias_precision) >= 0.95
        and pilot_coverage_5d >= 0.05
        and novel_share is not None
        and float(novel_share) >= 0.70
    ):
        decision = "PASSED"
    elif (
        alias_precision is not None
        and float(alias_precision) >= 0.90
        and pilot_coverage_5d > seed_coverage_5d
        and novel_share is not None
        and float(novel_share) >= 0.70
    ):
        decision = "MIXED"

    artifact_stem = f"{ts}_h301_cafef_event_surface_v2_pilot"
    pilot_surface_path = OUT_DIR / f"{artifact_stem}_pilot_surface.parquet"
    first_public_path = OUT_DIR / f"{artifact_stem}_first_public.parquet"
    article_events_path = OUT_DIR / f"{artifact_stem}_expanded_article_events.parquet"
    alias_map_path = OUT_DIR / f"{artifact_stem}_alias_map.parquet"
    alias_holdout_path = OUT_DIR / f"{artifact_stem}_alias_holdout.parquet"
    alias_assignments_path = OUT_DIR / f"{artifact_stem}_alias_assignments.parquet"

    pilot_surface.to_parquet(pilot_surface_path, index=False)
    first_public.to_parquet(first_public_path, index=False)
    expanded_bundle.article_events.to_parquet(article_events_path, index=False)
    alias_map.to_parquet(alias_map_path, index=False)
    alias_holdout_df.to_parquet(alias_holdout_path, index=False)
    alias_assignments.to_parquet(alias_assignments_path, index=False)

    summary = {
        "decision": decision,
        "analysis_window": {"start_date": str(args.start_date), "end_date": str(args.end_date)},
        "candidate_source": "cafef_company_news_archive_event_surface_v2_pilot",
        "seed_summary": seed_bundle.summary,
        "pilot_summary": expanded_bundle.summary,
        "alias_holdout_summary": alias_holdout_summary,
        "seed_held_window_coverage": seed_coverage,
        "pilot_held_window_coverage": pilot_coverage,
        "v1_held_window_coverage": v1_coverage,
        "novelty_vs_v1": novelty_vs_v1,
        "pilot_surface_rows": int(len(pilot_surface)),
        "pilot_surface_tickers": int(pilot_surface["ticker"].nunique()) if not pilot_surface.empty else 0,
        "first_public_rows": int(len(first_public)),
        "branch_decision": {
            "PASSED": "Pilot event-surface v2 has enough timestamp integrity and novelty to justify a later predictive screen.",
            "MIXED": "Pilot extraction is real and richer than the seed, but still too sparse to open a predictive branch yet.",
            "FAILED": "Close event-surface v2 on the current archive contract; coverage did not improve enough beyond the seed.",
        }[decision],
    }

    write_run_summary(
        ts=ts,
        mode="research_branch_cafef_event_surface_v2_pilot",
        name="h301_cafef_event_surface_v2_pilot",
        summary=summary,
        artifacts={
            "pilot_surface": str(pilot_surface_path),
            "first_public": str(first_public_path),
            "expanded_article_events": str(article_events_path),
            "alias_map": str(alias_map_path),
            "alias_holdout": str(alias_holdout_path),
            "alias_assignments": str(alias_assignments_path),
        },
        metadata={
            "session": 128,
            "branch_contract": "Data-first event pilot only; no predictive claim yet.",
        },
    )

    print("H301 CafeF event-surface v2 pilot")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
