from __future__ import annotations

import argparse
from dataclasses import dataclass


@dataclass(frozen=True)
class FetchNewsCliOptions:
    source: str
    tickers: list[str]
    start_date: str | None
    end_date: str | None
    max_pages: int
    delay: float
    workers: int
    overwrite: bool


def options_from_namespace(args: argparse.Namespace, *, parse_ticker_argument) -> FetchNewsCliOptions:
    return FetchNewsCliOptions(
        source=str(args.source),
        tickers=parse_ticker_argument(args.tickers),
        start_date=args.start_date,
        end_date=args.end_date,
        max_pages=int(args.max_pages),
        delay=float(args.delay),
        workers=int(args.workers),
        overwrite=bool(args.overwrite),
    )

