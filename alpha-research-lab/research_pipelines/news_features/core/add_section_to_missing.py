"""Backfill missing raw Cafef section names by refetching article pages."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import requests

from research_pipelines.news_features.config import NewsFeaturesConfig, get_default_config
from research_pipelines.news_features.io_utils import load_source_specs, read_jsonl, write_jsonl_records
from vn_stock_rl.data_tools.fetch_news import (
    _get_with_retries,
    _make_thread_session_getter,
    _should_skip_article_response,
    extract_cafef_section_name,
)


def _record_missing_section_name(record: dict[str, object]) -> bool:
    value = record.get("section_name")
    return value is None or str(value).strip() == ""


def _fetch_section_name_result(
    article_url: str,
    timeout: float,
    retry_attempts: int,
    retry_backoff_seconds: float,
    get_session,
) -> dict[str, object]:
    try:
        response = _get_with_retries(
            session=get_session(),
            url=article_url,
            timeout=timeout,
            retry_attempts=retry_attempts,
            retry_backoff_seconds=retry_backoff_seconds,
            request_label="Section backfill",
        )
    except requests.RequestException:
        return {"status": "failed", "url": article_url}

    if _should_skip_article_response(response):
        return {"status": "missing", "url": article_url, "status_code": response.status_code}

    response.raise_for_status()
    section_name = extract_cafef_section_name(response.text)
    if not section_name:
        return {"status": "unresolved", "url": article_url}
    return {"status": "ok", "url": article_url, "section_name": section_name}


def add_section_to_missing(
    source: str = "cafef",
    config: Optional[NewsFeaturesConfig] = None,
    workers: int = 1,
) -> dict[str, object]:
    config = config or get_default_config()
    if str(source).lower() != "cafef":
        raise ValueError(f"Section backfill currently supports only 'cafef', got: {source}")

    specs = load_source_specs(config=config)
    source_spec = specs.get(source)
    if source_spec is None:
        raise ValueError(f"Unsupported source: {source}")

    raw_dir = config.source_raw_dir(source)
    raw_files = sorted(raw_dir.glob("*.jsonl"))
    if not raw_files:
        raise FileNotFoundError(f"No raw JSONL files found under {raw_dir}")

    user_agent = str(source_spec.get("user_agent", "Mozilla/5.0"))
    thread_session_getter = _make_thread_session_getter(user_agent)
    max_workers = max(int(workers), 1)

    total_rows = 0
    missing_rows = 0
    updated_rows = 0
    unresolved_rows = 0
    failed_rows = 0
    files_updated = 0

    for file_index, path in enumerate(raw_files, start=1):
        rows = read_jsonl(path)
        total_rows += len(rows)
        missing_items = [
            (index, row)
            for index, row in enumerate(rows)
            if _record_missing_section_name(row) and str(row.get("url", "")).strip()
        ]
        missing_rows += len(missing_items)
        if not missing_items:
            continue

        print(
            f"Scanning {path.name} for missing section_name values: {len(missing_items)} rows",
            flush=True,
        )

        results: list[tuple[int, dict[str, object]]] = []
        if max_workers <= 1 or len(missing_items) <= 1:
            for index, row in missing_items:
                results.append(
                    (
                        index,
                        _fetch_section_name_result(
                            article_url=str(row["url"]),
                            timeout=config.source_timeout_seconds,
                            retry_attempts=config.request_retry_attempts,
                            retry_backoff_seconds=config.request_retry_backoff_seconds,
                            get_session=thread_session_getter,
                        ),
                    )
                )
        else:
            with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="news-section-backfill") as executor:
                for result in executor.map(
                    lambda item: (
                        item[0],
                        _fetch_section_name_result(
                            article_url=str(item[1]["url"]),
                            timeout=config.source_timeout_seconds,
                            retry_attempts=config.request_retry_attempts,
                            retry_backoff_seconds=config.request_retry_backoff_seconds,
                            get_session=thread_session_getter,
                        ),
                    ),
                    missing_items,
                ):
                    results.append(result)

        file_updated = False
        for result_index, (row_index, result) in enumerate(results, start=1):
            status = str(result["status"])
            article_url = str(result["url"])
            if status == "ok":
                rows[row_index]["section_name"] = str(result["section_name"])
                updated_rows += 1
                file_updated = True
            elif status == "unresolved":
                unresolved_rows += 1
                print(f"Section not found on article page: {article_url}", flush=True)
            elif status == "missing":
                failed_rows += 1
                print(f"Article missing during section backfill ({result['status_code']}): {article_url}", flush=True)
            else:
                failed_rows += 1
                print(f"Skipping failed section backfill URL after retries: {article_url}", flush=True)

            if result_index == 1 or result_index % 50 == 0 or result_index == len(results):
                print(
                    f"Processed {result_index}/{len(results)} missing-section URLs in {path.name}; "
                    f"updated={updated_rows}, unresolved={unresolved_rows}, failed={failed_rows}",
                    flush=True,
                )

        if file_updated:
            write_jsonl_records(path, rows, append=False)
            files_updated += 1
            print(f"Updated section_name values in {path.name}", flush=True)

        if file_index == 1 or file_index % 25 == 0 or file_index == len(raw_files):
            print(
                f"Completed {file_index}/{len(raw_files)} raw files; files_updated={files_updated}, "
                f"updated_rows={updated_rows}, unresolved_rows={unresolved_rows}, failed_rows={failed_rows}",
                flush=True,
            )

    summary = {
        "source": source,
        "raw_file_count": len(raw_files),
        "files_updated": files_updated,
        "article_count": total_rows,
        "missing_rows_seen": missing_rows,
        "updated_rows": updated_rows,
        "unresolved_rows": unresolved_rows,
        "failed_rows": failed_rows,
    }
    print(
        f"Section backfill complete. Updated {updated_rows} rows across {files_updated} files; "
        f"unresolved={unresolved_rows}, failed={failed_rows}",
        flush=True,
    )
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill missing raw Cafef section_name values.")
    parser.add_argument("--source", default="cafef", help="News source to backfill (default: cafef)")
    parser.add_argument("--workers", type=int, default=1, help="Parallel article fetch workers (default: 1)")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    add_section_to_missing(source=args.source, workers=args.workers)


if __name__ == "__main__":
    main()
