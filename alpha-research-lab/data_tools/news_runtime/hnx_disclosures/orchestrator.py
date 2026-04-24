from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd


def run_local_rebuild(
    *,
    args,
    ocr_languages: tuple[str, ...],
    tracker,
    manifest_path: Path,
    news_parquet_path: Path,
    attachment_parquet_path: Path,
    transaction_extract_path: Path,
    per_ticker_extract_path,
    ensure_contract_shape,
    build_transaction_extracts,
    atomic_write_parquet,
    atomic_write_json,
    per_ticker_root: Path,
    news_columns: list[str],
    attachment_columns: list[str],
    transaction_attachment_extract_columns: list[str],
    source: str,
    utc_now_iso,
) -> None:
    print("HNX local transaction extract rebuild: loading cached news and attachment parquets", flush=True)
    news = ensure_contract_shape(pd.read_parquet(news_parquet_path) if news_parquet_path.exists() else pd.DataFrame(), news_columns)
    attachments = ensure_contract_shape(
        pd.read_parquet(attachment_parquet_path) if attachment_parquet_path.exists() else pd.DataFrame(),
        attachment_columns,
    )
    tracker.write(
        status="running",
        phase="local_rebuild_extracts",
        progress={
            "mode": "local_rebuild_transaction_extracts",
            "news_rows": int(len(news)),
            "attachment_rows": int(len(attachments)),
        },
    )
    transaction_extract_frames: list[pd.DataFrame] = []
    ticker_list = sorted(set(news["ticker"].dropna().astype(str).str.upper())) if not news.empty else []
    for index, ticker in enumerate(ticker_list, start=1):
        ticker_news = news[news["ticker"].astype(str).str.upper() == ticker].copy()
        ticker_attachments = attachments[attachments["ticker"].astype(str).str.upper() == ticker].copy()
        ticker_extracts = build_transaction_extracts(
            news=ticker_news,
            attachments=ticker_attachments,
            ocr_transaction_attachments=args.ocr_transaction_attachments,
            ocr_languages=ocr_languages,
            ocr_gpu=args.ocr_gpu,
            refresh_transaction_text_cache=args.refresh_transaction_text_cache,
            log_progress=True,
        )
        atomic_write_parquet(ticker_extracts, per_ticker_extract_path(ticker))
        transaction_extract_frames.append(ticker_extracts)
        print(f"HNX local extract rebuild {index}/{len(ticker_list)}: {ticker} extract_rows={len(ticker_extracts)}", flush=True)
        tracker.write(
            status="running",
            phase="local_rebuild_extracts",
            progress={
                "mode": "local_rebuild_transaction_extracts",
                "ticker_index": index,
                "ticker_total": len(ticker_list),
                "current_ticker": ticker,
                "completed_tickers": ticker_list[:index],
            },
        )

    transaction_extracts = ensure_contract_shape(
        pd.concat(transaction_extract_frames, ignore_index=True) if transaction_extract_frames else pd.DataFrame(),
        transaction_attachment_extract_columns,
    )
    atomic_write_parquet(transaction_extracts, transaction_extract_path)

    manifest: dict[str, object] = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            manifest = {}
    notes = list(manifest.get("notes") or [])
    local_note = "Transaction attachment extracts can be rebuilt locally from cached news/attachment parquets plus any saved OCR text files."
    if local_note not in notes:
        notes.append(local_note)
    manifest.update(
        {
            "fetched_at_utc": utc_now_iso(),
            "source": source,
            "notes": notes,
            "run_mode": "local_rebuild_transaction_extracts",
            "ocr_transaction_attachments": bool(args.ocr_transaction_attachments),
            "refresh_transaction_text_cache": bool(args.refresh_transaction_text_cache),
            "ocr_languages": list(ocr_languages),
            "outputs": {
                **(manifest.get("outputs") or {}),
                "issuer_transaction_attachment_extracts_parquet": str(transaction_extract_path)
                if transaction_extract_path.exists()
                else None,
            },
            "transaction_attachment_extract_rows": int(len(transaction_extracts)),
            "transaction_attachment_extract_status_counts": transaction_extracts["parser_status"].value_counts(dropna=False).to_dict()
            if not transaction_extracts.empty
            else {},
            "transaction_text_extraction_status_counts": transaction_extracts["text_extraction_status"].value_counts(dropna=False).to_dict()
            if not transaction_extracts.empty
            else {},
        }
    )
    atomic_write_json(manifest, manifest_path)
    tracker.write(
        status="complete",
        phase="complete",
        progress={
            "mode": "local_rebuild_transaction_extracts",
            "transaction_attachment_extract_rows": int(len(transaction_extracts)),
            "ticker_total": len(ticker_list),
        },
    )
    print("HNX local transaction extract rebuild complete")
    print(f"Transaction extracts: {len(transaction_extracts)}")


def run_network_fetch(
    *,
    args,
    ocr_languages: tuple[str, ...],
    tracker,
    session,
    universe_json_path: Path,
    universe_parquet_path: Path,
    news_parquet_path: Path,
    attachment_parquet_path: Path,
    transaction_parquet_path: Path,
    transaction_extract_path: Path,
    manifest_path: Path,
    source: str,
    parse_tickers,
    fetch_universe,
    atomic_write_json,
    atomic_write_parquet,
    load_ticker_state,
    ticker_state_satisfies_run,
    fetch_ticker_history,
    prepare_news_output,
    prepare_attachment_output,
    write_ticker_state,
    per_ticker_news_path,
    per_ticker_attachment_path,
    per_ticker_extract_path,
    load_existing_ticker_frame,
    ensure_contract_shape,
    build_transaction_extracts,
    rebuild_aggregate_outputs,
    news_columns: list[str],
    attachment_columns: list[str],
    transaction_attachment_extract_columns: list[str],
    utc_now_iso,
) -> None:
    started_at_utc = utc_now_iso()
    tracker.write(
        status="running",
        phase="universe",
        progress={
            "target_tickers": [],
            "completed_tickers": [],
            "skipped_tickers": [],
            "failed_tickers": [],
            "current_ticker": None,
        },
    )
    print("Refreshing HNX official issuer universe...", flush=True)

    universe = fetch_universe(session, timeout=args.timeout)
    universe_payload = {
        "fetched_at_utc": started_at_utc,
        "source": source,
        "row_count": int(len(universe)),
        "market_counts": universe["market_code"].value_counts(dropna=False).to_dict(),
        "items": universe.to_dict(orient="records"),
    }

    if args.dry_run:
        target = universe.copy()
        if args.fetch_all_linked:
            target = target[target["detail_url"].notna()].copy()
        elif args.tickers:
            requested = parse_tickers(args.tickers)
            target = target[target["ticker"].isin(requested)].copy()
        else:
            target = target.iloc[0:0].copy()
        if args.max_tickers:
            target = target.head(args.max_tickers)
        print("HNX official disclosure fetch dry run")
        print(f"universe rows         : {len(universe)}")
        print(f"tickers to crawl      : {len(target)}")
        print(f"max pages per ticker  : {args.max_pages_per_ticker}")
        print(f"download attachments  : {args.download_attachments}")
        print(f"download tx pdfs      : {args.download_transaction_attachments}")
        print(f"parse tx attachments  : {args.parse_transaction_attachments}")
        print(f"ocr tx attachments    : {args.ocr_transaction_attachments}")
        print(f"refresh text cache    : {args.refresh_transaction_text_cache}")
        print(f"ocr languages         : {','.join(ocr_languages)}")
        return

    atomic_write_json(universe_payload, universe_json_path)
    atomic_write_parquet(universe, universe_parquet_path)

    requested_tickers = parse_tickers(args.tickers)
    if args.fetch_all_linked:
        target = universe[universe["detail_url"].notna()].copy()
    elif requested_tickers:
        target = universe[universe["ticker"].isin(requested_tickers)].copy()
    else:
        target = universe.iloc[0:0].copy()
    if args.max_tickers:
        target = target.head(args.max_tickers)
    target_tickers = target["ticker"].astype(str).tolist()

    print(
        f"HNX official disclosure fetch starting: target_tickers={len(target)}, "
        f"max_pages_per_ticker={args.max_pages_per_ticker}, "
        f"download_tx_pdfs={bool(args.download_transaction_attachments)}, "
        f"parse_tx_attachments={bool(args.parse_transaction_attachments)}",
        flush=True,
    )

    pages_fetched = 0
    failures: list[dict[str, object]] = []
    total_targets = len(target)
    ticker_start_time = time.perf_counter()
    completed_tickers: list[str] = []
    skipped_tickers: list[str] = []

    for ticker_index, row in enumerate(target.to_dict(orient="records"), start=1):
        ticker = str(row["ticker"])
        market_code = str(row["market_code"])
        tracker.write(
            status="running",
            phase="ticker_fetch",
            progress={
                "target_tickers": target_tickers,
                "completed_tickers": completed_tickers,
                "skipped_tickers": skipped_tickers,
                "failed_tickers": [item["ticker"] for item in failures],
                "current_ticker": ticker,
                "ticker_index": ticker_index,
                "ticker_total": total_targets,
                "pages_fetched": pages_fetched,
            },
        )
        print(f"HNX ticker {ticker_index}/{total_targets}: {ticker} ({market_code})", flush=True)
        ticker_started = time.perf_counter()
        ticker_state = load_ticker_state(ticker)
        if ticker_state_satisfies_run(ticker_state, args):
            skipped_tickers.append(ticker)
            print(f"HNX ticker {ticker_index}/{total_targets} reuse durable state: {ticker}", flush=True)
            tracker.write(
                status="running",
                phase="ticker_reuse",
                progress={
                    "target_tickers": target_tickers,
                    "completed_tickers": completed_tickers,
                    "skipped_tickers": skipped_tickers,
                    "failed_tickers": [item["ticker"] for item in failures],
                    "current_ticker": None,
                    "ticker_index": ticker_index,
                    "ticker_total": total_targets,
                    "pages_fetched": pages_fetched,
                },
            )
            continue
        try:
            ticker_news, ticker_attachments, ticker_pages = fetch_ticker_history(
                session,
                ticker=ticker,
                market_code=market_code,
                max_pages_per_ticker=args.max_pages_per_ticker,
                download_attachments=args.download_attachments,
                download_transaction_attachments=args.download_transaction_attachments,
                parse_transaction_attachments=args.parse_transaction_attachments,
                timeout=args.timeout,
                sleep=args.sleep,
                log_progress=True,
            )
            pages_fetched += ticker_pages
            ticker_news_frame = prepare_news_output(ticker_news)
            ticker_attachment_frame = prepare_attachment_output(ticker_attachments)
            atomic_write_parquet(ticker_news_frame, per_ticker_news_path(ticker))
            atomic_write_parquet(ticker_attachment_frame, per_ticker_attachment_path(ticker))
            write_ticker_state(
                ticker,
                {
                    "ticker": ticker,
                    "market_code": market_code,
                    "status": "complete",
                    "completed_at_utc": utc_now_iso(),
                    "max_pages_per_ticker": int(args.max_pages_per_ticker),
                    "download_attachments": bool(args.download_attachments),
                    "download_transaction_attachments": bool(args.download_transaction_attachments),
                    "parse_transaction_attachments": False,
                    "news_rows": int(len(ticker_news_frame)),
                    "attachment_rows": int(len(ticker_attachment_frame)),
                    "pages_fetched": int(ticker_pages),
                },
            )
            ticker_elapsed = time.perf_counter() - ticker_started
            ticker_transaction_rows = int(ticker_news_frame["has_transaction_keywords"].fillna(False).sum()) if not ticker_news_frame.empty else 0
            completed_tickers.append(ticker)
            print(
                f"HNX ticker {ticker_index}/{total_targets} complete: {ticker} "
                f"pages={ticker_pages}, news={len(ticker_news_frame)}, attachments={len(ticker_attachment_frame)}, "
                f"transaction_rows={ticker_transaction_rows}, elapsed={ticker_elapsed:.1f}s, "
                f"completed={len(completed_tickers)}, skipped={len(skipped_tickers)}",
                flush=True,
            )
        except Exception as exc:
            failures.append({"ticker": ticker, "market_code": market_code, "error": str(exc)})
            print(f"HNX ticker {ticker_index}/{total_targets} failed: {ticker} ({market_code}) error={exc}", flush=True)
            write_ticker_state(
                ticker,
                {
                    "ticker": ticker,
                    "market_code": market_code,
                    "status": "failed",
                    "updated_at_utc": utc_now_iso(),
                    "max_pages_per_ticker": int(args.max_pages_per_ticker),
                    "download_attachments": bool(args.download_attachments),
                    "download_transaction_attachments": bool(args.download_transaction_attachments),
                    "parse_transaction_attachments": bool(args.parse_transaction_attachments),
                    "error": str(exc),
                },
            )

    if args.parse_transaction_attachments:
        for ticker_index, ticker in enumerate(target_tickers, start=1):
            tracker.write(
                status="running",
                phase="transaction_extracts",
                progress={
                    "target_tickers": target_tickers,
                    "completed_tickers": completed_tickers,
                    "skipped_tickers": skipped_tickers,
                    "failed_tickers": [item["ticker"] for item in failures],
                    "current_ticker": ticker,
                    "ticker_index": ticker_index,
                    "ticker_total": len(target_tickers),
                    "pages_fetched": pages_fetched,
                },
            )
            ticker_news = load_existing_ticker_frame(per_ticker_news_path(ticker), news_columns)
            ticker_attachments = load_existing_ticker_frame(per_ticker_attachment_path(ticker), attachment_columns)
            ticker_state = load_ticker_state(ticker)
            if not args.refresh_transaction_text_cache and bool(ticker_state.get("parse_transaction_attachments")) and per_ticker_extract_path(ticker).exists():
                print(f"HNX transaction extract {ticker_index}/{len(target_tickers)} reuse durable state: {ticker}", flush=True)
                continue
            if ticker_news.empty or ticker_attachments.empty:
                atomic_write_parquet(ensure_contract_shape(pd.DataFrame(), transaction_attachment_extract_columns), per_ticker_extract_path(ticker))
                continue
            ticker_extracts = build_transaction_extracts(
                news=ticker_news,
                attachments=ticker_attachments,
                ocr_transaction_attachments=args.ocr_transaction_attachments,
                ocr_languages=ocr_languages,
                ocr_gpu=args.ocr_gpu,
                refresh_transaction_text_cache=args.refresh_transaction_text_cache,
                log_progress=True,
            )
            atomic_write_parquet(ticker_extracts, per_ticker_extract_path(ticker))
            ticker_state.update(
                {
                    "parse_transaction_attachments": True,
                    "transaction_extract_rows": int(len(ticker_extracts)),
                    "updated_at_utc": utc_now_iso(),
                }
            )
            write_ticker_state(ticker, ticker_state)
            print(f"HNX transaction extract {ticker_index}/{len(target_tickers)}: {ticker} extract_rows={len(ticker_extracts)}", flush=True)

    news, attachments, transactions, transaction_extracts = rebuild_aggregate_outputs(
        target_tickers=target_tickers,
        news_parquet_path=news_parquet_path,
        attachment_parquet_path=attachment_parquet_path,
        transaction_parquet_path=transaction_parquet_path,
        transaction_extract_path=transaction_extract_path,
        parse_transaction_attachments=bool(args.parse_transaction_attachments),
    )

    manifest = {
        "fetched_at_utc": utc_now_iso(),
        "started_at_utc": started_at_utc,
        "source": source,
        "run_mode": "network_fetch",
        "requested_tickers": requested_tickers,
        "resolved_target_tickers": target["ticker"].tolist(),
        "fetch_all_linked": bool(args.fetch_all_linked),
        "max_tickers": args.max_tickers,
        "max_pages_per_ticker": int(args.max_pages_per_ticker),
        "parse_transaction_attachments": bool(args.parse_transaction_attachments),
        "ocr_transaction_attachments": bool(args.ocr_transaction_attachments),
        "refresh_transaction_text_cache": bool(args.refresh_transaction_text_cache),
        "ocr_languages": list(ocr_languages),
        "notes": [
            "Universe refresh is full; per-ticker disclosure history is only fetched for the requested ticker set.",
            "The HNX mobile site requires TLS verification to be disabled in this environment.",
            "HSX official disclosures are not part of this fetcher because the current HSX SPA/API route is still unresolved.",
            "Latest-run parquet outputs are rewritten to match the current request scope; they are not append-only history stores.",
        ],
        "outputs": {
            "issuer_universe_json": str(universe_json_path),
            "issuer_universe_parquet": str(universe_parquet_path),
            "issuer_news_parquet": str(news_parquet_path),
            "issuer_news_attachments_parquet": str(attachment_parquet_path),
            "issuer_transaction_disclosures_parquet": str(transaction_parquet_path),
            "issuer_transaction_attachment_extracts_parquet": str(transaction_extract_path),
        },
        "universe_rows": int(len(universe)),
        "target_tickers": int(len(target)),
        "pages_fetched": int(pages_fetched),
        "news_rows": int(len(news)),
        "attachment_rows": int(len(attachments)),
        "transaction_rows": int(len(transactions)),
        "transaction_attachment_extract_rows": int(len(transaction_extracts)),
        "attachments_downloaded": int(attachments["attachment_storage_path"].notna().sum()) if not attachments.empty else 0,
        "transaction_attachment_extract_status_counts": transaction_extracts["parser_status"].value_counts(dropna=False).to_dict()
        if not transaction_extracts.empty
        else {},
        "transaction_text_extraction_status_counts": transaction_extracts["text_extraction_status"].value_counts(dropna=False).to_dict()
        if not transaction_extracts.empty
        else {},
        "failures": failures,
        "status": "success" if not failures else "partial",
    }
    atomic_write_json(manifest, manifest_path)

    total_elapsed = time.perf_counter() - ticker_start_time
    tracker.write(
        status="complete" if not failures else "partial",
        phase="complete",
        progress={
            "target_tickers": target_tickers,
            "completed_tickers": completed_tickers,
            "skipped_tickers": skipped_tickers,
            "failed_tickers": [item["ticker"] for item in failures],
            "current_ticker": None,
            "pages_fetched": pages_fetched,
            "news_rows": int(len(news)),
            "attachment_rows": int(len(attachments)),
            "transaction_rows": int(len(transactions)),
            "transaction_extract_rows": int(len(transaction_extracts)),
        },
        throughput={
            "tickers_per_second": (len(completed_tickers) / total_elapsed) if total_elapsed > 0 else 0.0,
            "pages_per_second": (pages_fetched / total_elapsed) if total_elapsed > 0 else 0.0,
        },
        error={"failures": failures} if failures else None,
    )
    print("HNX official disclosure fetch complete")
    print(f"Universe rows       : {len(universe)}")
    print(f"Target tickers      : {len(target)}")
    print(f"News rows           : {len(news)}")
    print(f"Attachment rows     : {len(attachments)}")
    print(f"Transaction rows    : {len(transactions)}")
    print(f"Transaction extracts: {len(transaction_extracts)}")
    print(f"Failures            : {len(failures)}")
    print(f"Elapsed seconds     : {total_elapsed:.1f}")
