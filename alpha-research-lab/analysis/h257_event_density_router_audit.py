"""
H257: Event-density router audit. Gate the current deployed selector (`H201` sticky)
using alias-expanded event density to test whether the live/offline mismatch hides a regime switch.
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
    build_alias_expanded_news_event_bundle,
    build_strict_title_alias_map,
    compute_event_density_gate,
    scan_news_event_archive,
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
ALIAS_TRAIN_END_DATE = "2024-12-31"
EVENT_WINDOW = 5
EVENT_THRESHOLD = 2
PASS_COVERAGE = 0.4
MIXED_COVERAGE = 0.25


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-news-dir", type=str, default=str(RAW_NEWS_DIR))
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--start-date", type=str, default=START_DATE)
    parser.add_argument("--end-date", type=str, default=END_DATE)
    parser.add_argument("--alias-train-end-date", type=str, default=ALIAS_TRAIN_END_DATE)
    parser.add_argument("--event-window", type=int, default=EVENT_WINDOW)
    parser.add_argument("--event-threshold", type=int, default=EVENT_THRESHOLD)
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
    alias_map = build_strict_title_alias_map(
        scan,
        train_start_date=str(args.start_date),
        train_end_date=str(args.alias_train_end_date),
        min_support=3,
        min_dominance=0.9,
    )
    expanded_bundle, _ = build_alias_expanded_news_event_bundle(scan, alias_map)

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

    gate_summary = compute_event_density_gate(
        daily_flags=expanded_bundle.daily_flags,
        panel=continuation.panel,
        window=int(args.event_window),
        threshold=int(args.event_threshold),
    )

    coverage = float(gate_summary["coverage"])
    if coverage >= PASS_COVERAGE:
        decision = "PASSED"
        next_action = "Use the router to gate future additions; consider publishing event-density signals for live deployment."
    elif coverage >= MIXED_COVERAGE:
        decision = "MIXED"
        next_action = "Gate only in a litmus lane until coverage improves; keep exploring other states."
    else:
        decision = "FAILED"
        next_action = "Kill the router idea on this stack; route effort back to intraday acquisition."

    artifact_stem = f"{ts}_h257_event_density_router_audit"
    gate_path = OUT_DIR / f"{artifact_stem}_gate.parquet"
    alias_map_path = OUT_DIR / f"{artifact_stem}_alias_map.parquet"
    event_rows_path = OUT_DIR / f"{artifact_stem}_expanded_daily_flags.parquet"

    expanded_bundle.daily_flags.to_parquet(event_rows_path, index=False)
    alias_map.to_parquet(alias_map_path, index=False)
    pd.DataFrame([gate_summary]).to_parquet(gate_path, index=False)

    write_run_summary(
        ts=ts,
        mode="timing_event_density_router_audit",
        name="h257_event_density_router_audit",
        summary={
            "analysis_window": {"start_date": str(args.start_date), "end_date": str(args.end_date)},
            "candidate_source": "cafef_company_news_archive_alias_expanded",
            "window": int(args.event_window),
            "threshold": int(args.event_threshold),
            "coverage": coverage,
            "gating_share": gate_summary["gating_share"],
            "coverage_rows": gate_summary["gating_rows"],
            "total_rows": gate_summary["candidate_rows"],
            "decision": decision,
            "next_action": next_action,
            "limitations": [
                "This audit only covers alias-expanded event rows available through H235.",
                "No predictive screening or live gating was executed.",
                "2026+ data remains untouched.",
            ],
        },
        artifacts={
            "expanded_daily_flags": str(event_rows_path),
            "alias_map": str(alias_map_path),
            "gate_summary": str(gate_path),
        },
        metadata={
            "branch_contract": "Gate `H201` by alias-expanded event density; only PASSED enables a gated router.",
            "decision_inputs": gate_summary,
        },
    )


if __name__ == "__main__":
    main()
