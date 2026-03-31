"""
H221: Build the canonical corporate-event surface and audit held-position coverage.
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
from src.event_surface_research import build_event_surface, load_matrix_spine, merge_event_surface
from src.research_protocol import DEFAULT_PROTOCOL
from src.run_summary import write_run_summary


RL_MATRIX_PATH = Path("data/features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = Path("data/features/execution/tradability_daily.parquet")
STOCK_DIR = Path("data/stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
DIVIDEND_CACHE_DIR = Path("data/dividend_cache")
EARNINGS_CALENDAR_PATH = Path("data/features/xs_earnings_calendar_daily.parquet")
INSIDER_RAW_PATH = Path("data/features/xs_insider_deals_raw.parquet")
EVENT_SURFACE_PATH = Path("data/features/event_surface_daily.parquet")
OUT_DIR = ROOT / "artifacts/portfolio_baselines"
COVERAGE_GATE = 0.60


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--dividend-cache-dir", type=str, default=str(DIVIDEND_CACHE_DIR))
    parser.add_argument("--earnings-calendar", type=str, default=str(EARNINGS_CALENDAR_PATH))
    parser.add_argument("--insider-raw", type=str, default=str(INSIDER_RAW_PATH))
    parser.add_argument("--event-surface-out", type=str, default=str(EVENT_SURFACE_PATH))
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--portfolio-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    protocol = DEFAULT_PROTOCOL
    spine = load_matrix_spine(Path(args.matrix), start_year=int(args.start_year), end_year=int(args.end_year))
    bundle = build_event_surface(
        spine=spine,
        dividend_cache_dir=Path(args.dividend_cache_dir),
        earnings_calendar_path=Path(args.earnings_calendar),
        insider_raw_path=Path(args.insider_raw),
    )
    event_surface_path = Path(args.event_surface_out)
    event_surface_path.parent.mkdir(parents=True, exist_ok=True)
    bundle.surface.to_parquet(event_surface_path, index=False)

    continuation = build_continuation_dataset(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=min(int(args.end_year), 2025),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.portfolio_notional_vnd),
        round_trip_cost=float(args.round_trip_cost),
    )
    coverage = merge_event_surface(continuation.panel, bundle.surface)
    coverage_share = float(coverage.coverage_summary["coverage_share"])
    passed = coverage_share >= COVERAGE_GATE

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    coverage_path = OUT_DIR / f"{ts}_h221_event_surface_coverage_panel.parquet"
    coverage.merged_panel.to_parquet(coverage_path, index=False)
    write_run_summary(
        ts=ts,
        mode="portfolio_exit_event_surface_artifact",
        name="h221_event_surface_artifact",
        summary={
            "protocol": protocol.describe(),
            "coverage_gate": COVERAGE_GATE,
            "coverage_gate_passed": passed,
            "event_surface": bundle.coverage_summary,
            "held_panel_coverage": coverage.coverage_summary,
        },
        artifacts={
            "event_surface": str(event_surface_path),
            "coverage_panel": str(coverage_path),
        },
        metadata={"protocol": protocol.describe()},
    )


if __name__ == "__main__":
    main()
