"""
Fetch CafeF intraday bars for the whole current stock universe in one command.

This is a thin wrapper around `fetch_cafef_intraday.py` that uses the existing
`*_1D.parquet` files under `data/stock/` as the ticker universe.

Default behavior:
    bare `python data_tools/fetch_cafef_intraday_all.py` means the full current
    universe from `2000-01-01` through `2099-12-31`.

Examples:
    conda run -n stocks python data_tools/fetch_cafef_intraday_all.py
    conda run -n stocks python data_tools/fetch_cafef_intraday_all.py --start 2000-01-01 --end 2026-12-31 --workers 16
    conda run -n stocks python data_tools/fetch_cafef_intraday_all.py --dry-run
"""

from __future__ import annotations

from fetch_cafef_intraday import build_parser, main as fetch_cafef_intraday_main

DEFAULT_UNIVERSE_START = "2000-01-01"
DEFAULT_UNIVERSE_END = "2099-12-31"


def main(argv: list[str] | None = None) -> None:
    parser = build_parser(
        include_tickers=False,
        description="Fetch open historical intraday data from CafeF MatchPrice for the full current universe",
    )
    parser.set_defaults(start=DEFAULT_UNIVERSE_START, end=DEFAULT_UNIVERSE_END)
    args = parser.parse_args(argv)
    forward_argv: list[str] = [
        "--start",
        args.start,
        "--end",
        args.end,
        "--interval-label",
        args.interval_label,
        "--delay",
        str(args.delay),
        "--timeout",
        str(args.timeout),
        "--workers",
        str(args.workers),
        "--retry-rounds",
        str(args.retry_rounds),
        "--retry-delay",
        str(args.retry_delay),
        "--parts-dir",
        args.parts_dir,
    ]
    if args.overwrite:
        forward_argv.append("--overwrite")
    if args.dry_run:
        forward_argv.append("--dry-run")
    fetch_cafef_intraday_main(forward_argv, include_tickers=False)


if __name__ == "__main__":
    main()
