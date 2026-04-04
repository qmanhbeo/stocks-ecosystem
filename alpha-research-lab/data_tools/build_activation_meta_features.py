"""
Build dense date-level activation meta features.

Output:
- data/features/activation_meta_daily.parquet

Purpose:
- turn activation alpha into a learnable selector-efficacy problem
- expose forward selector outcomes and recent selector-path diagnostics

Usage:
    conda run -n stocks python data_tools/build_activation_meta_features.py
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.activation_alpha import (
    ACTIVATION_STATE_PATH,
    BENCHMARK_PATH,
    RL_MATRIX_PATH,
    STOCK_DIR,
    TRADABILITY_PATH,
    latest_matrix_year,
)
from src.activation_meta import ACTIVATION_META_PATH, persist_activation_meta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--activation-state", type=str, default=str(ACTIVATION_STATE_PATH))
    parser.add_argument("--out", type=str, default=str(ACTIVATION_META_PATH))
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument(
        "--end-year",
        type=int,
        default=None,
        help="Defaults to the latest year present in the RL matrix.",
    )
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--initial-notional-vnd", type=float, default=100_000_000.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out = Path(args.out)
    matrix_path = Path(args.matrix)
    end_year = latest_matrix_year(matrix_path) if args.end_year is None else int(args.end_year)
    frame = persist_activation_meta(
        out_path=out,
        matrix_path=matrix_path,
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        activation_state_path=Path(args.activation_state),
        start_year=int(args.start_year),
        end_year=end_year,
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.initial_notional_vnd),
    )
    print(f"saved {len(frame):,} rows -> {out}")
    print(f"date range: {frame['time'].min().date()} -> {frame['time'].max().date()}")
    print(f"columns: {list(frame.columns)}")


if __name__ == "__main__":
    main()
