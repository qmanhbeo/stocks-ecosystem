from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from time import sleep


def fetch_news(
    *,
    source: str,
    start_date: str | None,
    end_date: str | None,
    max_pages: int,
    delay: float,
    tickers: list[str] | None,
    workers: int,
    overwrite: bool,
    progress_callback,
    config,
    source_spec: dict[str, object],
    build_http_session,
    make_thread_session_getter,
    fetch_article_result,
    canonicalize_url,
    parse_sitemap_index,
    parse_input_bound,
    iter_existing_urls,
    iter_scanned_sitemaps,
    append_scanned_sitemap,
    collect_ticker_listing_urls,
    collect_listing_urls,
    current_utc_timestamp,
    select_sitemap_urls,
    should_rescan_sitemap,
    response_links,
    candidate_urls_from_sitemap_response,
    get_with_retries,
    save_fetched_news,
    interrupted_exception_cls,
) -> list[dict[str, object]]:
    config.source_raw_dir(source).mkdir(parents=True, exist_ok=True)
    config.source_dir(source).mkdir(parents=True, exist_ok=True)
    if overwrite:
        for path in config.source_raw_dir(source).glob("*.jsonl"):
            path.unlink()
        seen_urls_path = config.source_seen_urls_path(source)
        if seen_urls_path.exists():
            seen_urls_path.unlink()
        scanned_sitemaps_path = config.source_scanned_sitemaps_path(source)
        if scanned_sitemaps_path.exists():
            scanned_sitemaps_path.unlink()

    user_agent = str(source_spec.get("user_agent", "Mozilla/5.0"))
    session = build_http_session(user_agent)
    start_ts = parse_input_bound(start_date, is_end=False)
    end_ts = parse_input_bound(end_date, is_end=True)
    existing_urls = iter_existing_urls(source)
    scanned_sitemaps = iter_scanned_sitemaps(source)

    base_url = str(source_spec["base_url"])
    records: list[dict[str, object]] = []
    seen_urls: set[str] = set()
    processed_candidates = 0
    discovered_candidates = 0
    skipped_missing_articles = 0
    saved_records_count = 0
    pending_records: list[dict[str, object]] = []
    selected_sitemap_count = 0
    ticker_list = [ticker.upper() for ticker in (tickers or []) if str(ticker).strip()]
    used_ticker_mode = bool(ticker_list)
    now_ts = current_utc_timestamp()
    article_workers = max(int(workers), 1)
    thread_session_getter = make_thread_session_getter(user_agent)
    if article_workers > 1:
        print(f"Parallel article fetching enabled with {article_workers} workers", flush=True)

    def emit_progress(**payload: object) -> None:
        if progress_callback is not None:
            progress_callback(payload)

    def flush_pending(phase: str) -> None:
        nonlocal saved_records_count
        nonlocal pending_records
        if not pending_records:
            return
        saved_records_count += save_fetched_news(pending_records, source=source)
        pending_records = []
        emit_progress(
            phase=phase,
            processed_candidates=processed_candidates,
            discovered_candidates=discovered_candidates,
            saved_records_count=saved_records_count,
            kept_records=len(records),
            skipped_missing_articles=skipped_missing_articles,
        )

    def handle_result(result: dict[str, object], *, count_as_processed: bool = True) -> None:
        nonlocal processed_candidates
        nonlocal skipped_missing_articles
        nonlocal pending_records
        if count_as_processed:
            processed_candidates += 1
        status = str(result["status"])
        article_url = str(result["url"])
        if status == "failed":
            print(f"Skipping failed article URL after retries: {article_url}", flush=True)
        elif status == "missing":
            skipped_missing_articles += 1
            if skipped_missing_articles <= 3 or skipped_missing_articles % 25 == 0:
                print(f"Skipping missing article URL ({result['status_code']}): {article_url}", flush=True)
        elif status == "ok":
            record = dict(result["record"])
            records.append(record)
            pending_records.append(record)
            if len(pending_records) >= config.raw_save_batch_size:
                flush_pending("flush")
            sleep(delay)
        if processed_candidates == 1 or processed_candidates % 50 == 0:
            print(
                f"Processed {processed_candidates} discovered article URLs so far, kept {len(records)} records, "
                f"saved={saved_records_count}, skipped_missing={skipped_missing_articles}",
                flush=True,
            )
        emit_progress(
            phase="fetch",
            processed_candidates=processed_candidates,
            discovered_candidates=discovered_candidates,
            saved_records_count=saved_records_count,
            kept_records=len(records),
            skipped_missing_articles=skipped_missing_articles,
        )

    def process_candidate_urls(candidate_urls: list[str]) -> None:
        nonlocal processed_candidates
        nonlocal discovered_candidates
        urls_to_fetch: list[str] = []
        for article_url in candidate_urls:
            canonical_url = canonicalize_url(article_url)
            if canonical_url in seen_urls or canonical_url in existing_urls:
                processed_candidates += 1
                if processed_candidates == 1 or processed_candidates % 50 == 0:
                    print(
                        f"Processed {processed_candidates} discovered article URLs so far, kept {len(records)} records, "
                        f"saved={saved_records_count}, skipped_missing={skipped_missing_articles}",
                        flush=True,
                    )
                emit_progress(
                    phase="fetch",
                    processed_candidates=processed_candidates,
                    discovered_candidates=discovered_candidates,
                    saved_records_count=saved_records_count,
                    kept_records=len(records),
                    skipped_missing_articles=skipped_missing_articles,
                )
                continue
            seen_urls.add(canonical_url)
            urls_to_fetch.append(article_url)

        discovered_candidates += len(urls_to_fetch)

        if article_workers <= 1 or len(urls_to_fetch) <= 1:
            for article_url in urls_to_fetch:
                processed_candidates += 1
                handle_result(
                    fetch_article_result(
                        article_url=article_url,
                        start_ts=start_ts,
                        end_ts=end_ts,
                        timeout=config.source_timeout_seconds,
                        retry_attempts=config.request_retry_attempts,
                        retry_backoff_seconds=config.request_retry_backoff_seconds,
                        get_session=thread_session_getter,
                    ),
                    count_as_processed=False,
                )
            return

        with ThreadPoolExecutor(max_workers=article_workers, thread_name_prefix="news-fetch") as executor:
            for result in executor.map(
                lambda url: fetch_article_result(
                    article_url=url,
                    start_ts=start_ts,
                    end_ts=end_ts,
                    timeout=config.source_timeout_seconds,
                    retry_attempts=config.request_retry_attempts,
                    retry_backoff_seconds=config.request_retry_backoff_seconds,
                    get_session=thread_session_getter,
                ),
                urls_to_fetch,
            ):
                handle_result(result)

    sitemap_index_url = str(source_spec.get("sitemap_index_url", "")).strip()
    try:
        if ticker_list:
            ticker_listing_urls = collect_ticker_listing_urls(
                source_spec=source_spec,
                tickers=ticker_list,
                max_pages=max_pages,
                default_max_pages=config.max_listing_pages,
            )
            print(
                f"Ticker mode enabled for {', '.join(ticker_list)} across {len(ticker_listing_urls)} listing pages",
                flush=True,
            )
            emit_progress(phase="ticker_listings", listing_total=len(ticker_listing_urls))
            for listing_index, (ticker, listing_url) in enumerate(ticker_listing_urls, start=1):
                try:
                    response = get_with_retries(
                        session=session,
                        url=listing_url,
                        timeout=config.source_timeout_seconds,
                        retry_attempts=config.request_retry_attempts,
                        retry_backoff_seconds=config.request_retry_backoff_seconds,
                        request_label=f"Ticker listing {ticker}",
                    )
                except Exception:
                    print(f"Skipping failed ticker listing URL after retries: {listing_url}", flush=True)
                    continue
                if response.status_code == 404:
                    print(f"Skipping missing ticker listing URL: {listing_url}", flush=True)
                    continue
                response.raise_for_status()
                ticker_candidate_urls = response_links(response, base_url=base_url)
                print(
                    f"Ticker listing {listing_index}/{len(ticker_listing_urls)} for {ticker} yielded {len(ticker_candidate_urls)} candidate article URLs",
                    flush=True,
                )
                emit_progress(
                    phase="ticker_listing",
                    current_listing=f"{ticker}:{listing_index}",
                    listing_index=listing_index,
                    listing_total=len(ticker_listing_urls),
                    candidate_urls=len(ticker_candidate_urls),
                )
                process_candidate_urls(ticker_candidate_urls)
        elif sitemap_index_url:
            try:
                sitemap_index_response = get_with_retries(
                    session=session,
                    url=sitemap_index_url,
                    timeout=config.source_timeout_seconds,
                    retry_attempts=config.request_retry_attempts,
                    retry_backoff_seconds=config.request_retry_backoff_seconds,
                    request_label="Sitemap index",
                )
            except Exception:
                print(f"Failed to load sitemap index after retries: {sitemap_index_url}. Falling back to listing pages.", flush=True)
            else:
                index_rows = parse_sitemap_index(sitemap_index_response.text)
                sitemap_urls = select_sitemap_urls(index_rows, start_ts=start_ts, end_ts=end_ts, max_documents=max_pages)
                selected_sitemap_count = len(sitemap_urls)
                print(f"Selected {len(sitemap_urls)} sitemap documents from {sitemap_index_url}", flush=True)
                emit_progress(phase="sitemap_select", selected_sitemaps=selected_sitemap_count)
                if sitemap_urls:
                    print("Streaming sitemap scan and article fetch...", flush=True)
                progress_every = 1 if len(sitemap_urls) <= 10 else 10
                for sitemap_index, sitemap_url in enumerate(sitemap_urls, start=1):
                    should_recheck_recent = sitemap_url in scanned_sitemaps and should_rescan_sitemap(
                        sitemap_url,
                        now_ts=now_ts,
                        recent_days=config.rescan_recent_sitemap_days,
                    )
                    if sitemap_url in scanned_sitemaps and not should_recheck_recent:
                        if sitemap_index == 1 or sitemap_index % progress_every == 0 or sitemap_index == len(sitemap_urls):
                            print(f"Sitemap {sitemap_index}/{len(sitemap_urls)} already scanned, skipping", flush=True)
                        continue
                    if should_recheck_recent:
                        print(
                            f"Sitemap {sitemap_index}/{len(sitemap_urls)} was scanned before but is still recent, rechecking",
                            flush=True,
                        )
                    try:
                        response = get_with_retries(
                            session=session,
                            url=sitemap_url,
                            timeout=config.source_timeout_seconds,
                            retry_attempts=config.request_retry_attempts,
                            retry_backoff_seconds=config.request_retry_backoff_seconds,
                            request_label="Sitemap",
                        )
                    except Exception:
                        print(f"Skipping failed sitemap URL after retries: {sitemap_url}", flush=True)
                        continue
                    if response.status_code == 404:
                        print(f"Skipping missing sitemap URL: {sitemap_url}", flush=True)
                        continue
                    response.raise_for_status()
                    sitemap_candidate_urls = candidate_urls_from_sitemap_response(sitemap_url, response, start_ts, end_ts)
                    print(
                        f"Sitemap {sitemap_index}/{len(sitemap_urls)} yielded {len(sitemap_candidate_urls)} candidate article URLs; "
                        f"discovered={discovered_candidates + len(sitemap_candidate_urls)}",
                        flush=True,
                    )
                    emit_progress(
                        phase="sitemap_fetch",
                        current_sitemap=sitemap_url,
                        sitemap_index=sitemap_index,
                        sitemap_total=len(sitemap_urls),
                        candidate_urls=len(sitemap_candidate_urls),
                        processed_candidates=processed_candidates,
                        discovered_candidates=discovered_candidates + len(sitemap_candidate_urls),
                        saved_records_count=saved_records_count,
                    )
                    process_candidate_urls(sitemap_candidate_urls)
                    if sitemap_url not in scanned_sitemaps:
                        append_scanned_sitemap(source, sitemap_url)
                        scanned_sitemaps.add(sitemap_url)
                    if sitemap_index == 1 or sitemap_index % progress_every == 0 or sitemap_index == len(sitemap_urls):
                        print(
                            f"Completed sitemap {sitemap_index}/{len(sitemap_urls)}; processed={processed_candidates}, saved={saved_records_count}",
                            flush=True,
                        )
                        emit_progress(
                            phase="sitemap_complete",
                            current_sitemap=sitemap_url,
                            sitemap_index=sitemap_index,
                            sitemap_total=len(sitemap_urls),
                            processed_candidates=processed_candidates,
                            discovered_candidates=discovered_candidates,
                            saved_records_count=saved_records_count,
                        )

        if not used_ticker_mode and selected_sitemap_count == 0:
            listing_urls = collect_listing_urls(source_spec, max_pages=max_pages)
            for listing_index, listing_url in enumerate(listing_urls, start=1):
                try:
                    response = get_with_retries(
                        session=session,
                        url=listing_url,
                        timeout=config.source_timeout_seconds,
                        retry_attempts=config.request_retry_attempts,
                        retry_backoff_seconds=config.request_retry_backoff_seconds,
                        request_label="Listing",
                    )
                except Exception:
                    print(f"Skipping failed listing URL after retries: {listing_url}", flush=True)
                    continue
                if response.status_code == 404:
                    print(f"Skipping missing listing URL: {listing_url}")
                    continue
                response.raise_for_status()
                listing_candidate_urls = response_links(response, base_url=base_url)
                print(f"Listing {listing_index}/{len(listing_urls)} yielded {len(listing_candidate_urls)} candidate article URLs", flush=True)
                emit_progress(
                    phase="listing",
                    listing_index=listing_index,
                    listing_total=len(listing_urls),
                    candidate_urls=len(listing_candidate_urls),
                )
                process_candidate_urls(listing_candidate_urls)

        flush_pending("flush")
        return records
    except KeyboardInterrupt as exc:
        flush_pending("interrupt_flush")
        raise interrupted_exception_cls(
            records=records,
            output_dir=str(config.source_raw_dir(source)),
            processed_candidates=processed_candidates,
            total_candidates=discovered_candidates,
            saved_records_count=saved_records_count,
        ) from exc
