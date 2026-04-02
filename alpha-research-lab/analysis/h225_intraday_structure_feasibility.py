"""
H225: Intraday / auction structure feasibility and held-position coverage audit.
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
from src.research_protocol import DEFAULT_PROTOCOL
from src.run_summary import write_run_summary


RL_MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
STOCK_DIR = data_path("stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
FPT_INTRADAY_DAILY_PATH = data_path("features/fpt_intraday_daily.parquet")
OUT_DIR = ROOT / "artifacts/portfolio_baselines"
COVERAGE_GATE = 0.50


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--intraday-daily", type=str, default=str(FPT_INTRADAY_DAILY_PATH))
    parser.add_argument("--portfolio-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    protocol = DEFAULT_PROTOCOL
    continuation = build_continuation_dataset(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=2015,
        end_year=2025,
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.portfolio_notional_vnd),
        round_trip_cost=float(args.round_trip_cost),
    )
    intraday_path = Path(args.intraday_daily)
    if intraday_path.exists():
        intraday = pd.read_parquet(intraday_path).rename(columns={"date": "time"})
        intraday["time"] = pd.to_datetime(intraday["time"]).dt.normalize()
        intraday["ticker"] = "FPT"
    else:
        intraday = pd.DataFrame(columns=["time", "ticker"])
    merged = continuation.panel[["time", "ticker"]].merge(intraday[["time", "ticker"]].drop_duplicates(), on=["time", "ticker"], how="left", indicator=True)
    coverage_share = float((merged["_merge"] == "both").mean()) if len(merged) else 0.0
    passed = coverage_share >= COVERAGE_GATE
    available_1h_files = sorted(path.name for path in Path(args.stock_dir).glob("*_1H.parquet"))
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    coverage_path = OUT_DIR / f"{ts}_h225_intraday_structure_feasibility_coverage.parquet"
    merged.to_parquet(coverage_path, index=False)
    write_run_summary(
        ts=ts,
        mode="portfolio_exit_intraday_structure_feasibility",
        name="h225_intraday_structure_feasibility",
        summary={
            "protocol": protocol.describe(),
            "coverage_gate": COVERAGE_GATE,
            "coverage_gate_passed": passed,
            "coverage_share": coverage_share,
            "available_1h_files": available_1h_files,
            "available_intraday_tickers": sorted(intraday["ticker"].dropna().unique().tolist()),
        },
        artifacts={"coverage_panel": str(coverage_path)},
        metadata={"protocol": protocol.describe()},
    )


if __name__ == "__main__":
    main()
