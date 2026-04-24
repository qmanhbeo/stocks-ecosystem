from __future__ import annotations

import argparse
from dataclasses import dataclass


@dataclass(frozen=True)
class HnxDisclosureOptions:
    tickers: list[str]
    fetch_all_linked: bool
    max_tickers: int | None
    max_pages_per_ticker: int
    download_attachments: bool
    download_transaction_attachments: bool
    parse_transaction_attachments: bool
    rebuild_transaction_extracts_from_local: bool
    ocr_transaction_attachments: bool
    refresh_transaction_text_cache: bool
    ocr_languages: tuple[str, ...]
    ocr_gpu: bool
    sleep: float
    timeout: float
    dry_run: bool


def options_from_namespace(
    args: argparse.Namespace,
    *,
    parse_tickers,
    parse_language_list,
) -> HnxDisclosureOptions:
    return HnxDisclosureOptions(
        tickers=parse_tickers(args.tickers),
        fetch_all_linked=bool(args.fetch_all_linked),
        max_tickers=args.max_tickers,
        max_pages_per_ticker=int(args.max_pages_per_ticker),
        download_attachments=bool(args.download_attachments),
        download_transaction_attachments=bool(args.download_transaction_attachments),
        parse_transaction_attachments=bool(args.parse_transaction_attachments),
        rebuild_transaction_extracts_from_local=bool(args.rebuild_transaction_extracts_from_local),
        ocr_transaction_attachments=bool(args.ocr_transaction_attachments),
        refresh_transaction_text_cache=bool(args.refresh_transaction_text_cache),
        ocr_languages=parse_language_list(args.ocr_languages),
        ocr_gpu=bool(args.ocr_gpu),
        sleep=float(args.sleep),
        timeout=float(args.timeout),
        dry_run=bool(args.dry_run),
    )


def resolve_run_mode(options: HnxDisclosureOptions) -> str:
    if options.rebuild_transaction_extracts_from_local:
        return "local_rebuild_transaction_extracts"
    return "network_fetch"

