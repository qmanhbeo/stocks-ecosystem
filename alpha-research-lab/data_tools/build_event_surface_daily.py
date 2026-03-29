"""
Build the canonical corporate-event surface used by the new-data exit ladder.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.event_surface_research import build_event_surface, load_matrix_spine


RL_MATRIX_PATH = Path("data/features/xs_rl_signal_matrix.parquet")
DIVIDEND_CACHE_DIR = Path("data/dividend_cache")
EARNINGS_CALENDAR_PATH = Path("data/features/xs_earnings_calendar_daily.parquet")
INSIDER_RAW_PATH = Path("data/features/xs_insider_deals_raw.parquet")
OUT_PATH = Path("data/features/event_surface_daily.parquet")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--dividend-cache-dir", type=str, default=str(DIVIDEND_CACHE_DIR))
    parser.add_argument("--earnings-calendar", type=str, default=str(EARNINGS_CALENDAR_PATH))
    parser.add_argument("--insider-raw", type=str, default=str(INSIDER_RAW_PATH))
    parser.add_argument("--out", type=str, default=str(OUT_PATH))
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2026)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    spine = load_matrix_spine(Path(args.matrix), start_year=int(args.start_year), end_year=int(args.end_year))
    bundle = build_event_surface(
        spine=spine,
        dividend_cache_dir=Path(args.dividend_cache_dir),
        earnings_calendar_path=Path(args.earnings_calendar),
        insider_raw_path=Path(args.insider_raw),
    )
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bundle.surface.to_parquet(out_path, index=False)
    print(f"Saved {len(bundle.surface):,} rows to {out_path}")
    print(bundle.coverage_summary)


if __name__ == "__main__":
    main()
