"""
Build dense date-level activation state features.

Output:
- data/features/activation_state_daily.parquet

Purpose:
- separate selection alpha from activation alpha
- give activation experiments a compact date-level state surface built only from
  information known by the signal-date close

Usage:
    conda run -n stocks python data_tools/build_activation_state_features.py
"""

from __future__ import annotations

import argparse
from pathlib import Path
from path_utils import data_path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.activation_alpha import ACTIVATION_STATE_PATH, persist_activation_state


RL_MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
STOCK_DIR = data_path("stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--out", type=str, default=str(ACTIVATION_STATE_PATH))
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out = Path(args.out)
    frame = persist_activation_state(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        out_path=out,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )
    print(f"saved {len(frame):,} rows -> {out}")
    print(f"date range: {frame['time'].min().date()} -> {frame['time'].max().date()}")
    print(f"columns: {list(frame.columns)}")


if __name__ == "__main__":
    main()
