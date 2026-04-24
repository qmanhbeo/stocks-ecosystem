from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def per_ticker_news_path(ticker: str, *, per_ticker_root: Path) -> Path:
    return per_ticker_root / f"{ticker.upper()}_news.parquet"


def per_ticker_attachment_path(ticker: str, *, per_ticker_root: Path) -> Path:
    return per_ticker_root / f"{ticker.upper()}_attachments.parquet"


def per_ticker_extract_path(ticker: str, *, per_ticker_root: Path) -> Path:
    return per_ticker_root / f"{ticker.upper()}_transaction_extracts.parquet"


def per_ticker_state_path(ticker: str, *, per_ticker_root: Path) -> Path:
    return per_ticker_root / f"{ticker.upper()}_state.json"


def load_ticker_state(ticker: str, *, per_ticker_root: Path) -> dict[str, object]:
    path = per_ticker_state_path(ticker, per_ticker_root=per_ticker_root)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def write_ticker_state(
    ticker: str,
    payload: dict[str, object],
    *,
    per_ticker_root: Path,
    atomic_write_json,
) -> None:
    atomic_write_json(payload, per_ticker_state_path(ticker, per_ticker_root=per_ticker_root))


def ticker_state_satisfies_run(
    ticker_state: dict[str, object],
    args: argparse.Namespace,
    *,
    per_ticker_root: Path,
) -> bool:
    if not ticker_state:
        return False
    if str(ticker_state.get("status")) != "complete":
        return False
    if int(ticker_state.get("max_pages_per_ticker", 0) or 0) < int(args.max_pages_per_ticker):
        return False
    if bool(args.download_attachments) and not bool(ticker_state.get("download_attachments")):
        return False
    if bool(args.download_transaction_attachments) and not bool(ticker_state.get("download_transaction_attachments")):
        return False
    if bool(args.parse_transaction_attachments) and not bool(ticker_state.get("parse_transaction_attachments")):
        return False
    if bool(args.refresh_transaction_text_cache):
        return False
    ticker = str(ticker_state.get("ticker", ""))
    if not per_ticker_news_path(ticker, per_ticker_root=per_ticker_root).exists():
        return False
    if (args.download_attachments or args.download_transaction_attachments or args.parse_transaction_attachments) and not per_ticker_attachment_path(
        ticker,
        per_ticker_root=per_ticker_root,
    ).exists():
        return False
    if args.parse_transaction_attachments and not per_ticker_extract_path(ticker, per_ticker_root=per_ticker_root).exists():
        return False
    return True


def load_existing_ticker_frame(path: Path, columns: list[str], *, ensure_contract_shape) -> pd.DataFrame:
    if not path.exists():
        return ensure_contract_shape(pd.DataFrame(), columns)
    try:
        return ensure_contract_shape(pd.read_parquet(path), columns)
    except Exception:
        return ensure_contract_shape(pd.DataFrame(), columns)


def rebuild_aggregate_outputs(
    *,
    target_tickers: list[str],
    news_parquet_path: Path,
    attachment_parquet_path: Path,
    transaction_parquet_path: Path,
    transaction_extract_path: Path,
    parse_transaction_attachments: bool,
    per_ticker_root: Path,
    news_columns: list[str],
    attachment_columns: list[str],
    transaction_attachment_extract_columns: list[str],
    ensure_contract_shape,
    prepare_news_output,
    prepare_attachment_output,
    prepare_transaction_output,
    atomic_write_parquet,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    news_frames = [
        load_existing_ticker_frame(
            per_ticker_news_path(ticker, per_ticker_root=per_ticker_root),
            news_columns,
            ensure_contract_shape=ensure_contract_shape,
        )
        for ticker in target_tickers
    ]
    attachment_frames = [
        load_existing_ticker_frame(
            per_ticker_attachment_path(ticker, per_ticker_root=per_ticker_root),
            attachment_columns,
            ensure_contract_shape=ensure_contract_shape,
        )
        for ticker in target_tickers
    ]
    extract_frames = [
        load_existing_ticker_frame(
            per_ticker_extract_path(ticker, per_ticker_root=per_ticker_root),
            transaction_attachment_extract_columns,
            ensure_contract_shape=ensure_contract_shape,
        )
        for ticker in target_tickers
    ]
    news = prepare_news_output(
        pd.concat(news_frames, ignore_index=True).to_dict(orient="records")
        if any(not frame.empty for frame in news_frames)
        else []
    )
    attachments = prepare_attachment_output(
        pd.concat(attachment_frames, ignore_index=True).to_dict(orient="records")
        if any(not frame.empty for frame in attachment_frames)
        else []
    )
    transactions = prepare_transaction_output(news)
    if parse_transaction_attachments and any(not frame.empty for frame in extract_frames):
        transaction_extracts = ensure_contract_shape(
            pd.concat(extract_frames, ignore_index=True),
            transaction_attachment_extract_columns,
        )
    else:
        transaction_extracts = ensure_contract_shape(pd.DataFrame(), transaction_attachment_extract_columns)
    atomic_write_parquet(news, news_parquet_path)
    atomic_write_parquet(attachments, attachment_parquet_path)
    atomic_write_parquet(transactions, transaction_parquet_path)
    atomic_write_parquet(transaction_extracts, transaction_extract_path)
    return news, attachments, transactions, transaction_extracts

