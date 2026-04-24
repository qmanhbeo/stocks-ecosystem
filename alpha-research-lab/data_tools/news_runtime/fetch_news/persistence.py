from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd


def iter_existing_urls(source: str, *, config, canonicalize_url, get_default_config, read_jsonl) -> set[str]:
    config = get_default_config() if config is None else config
    index_path = config.source_seen_urls_path(source)
    if index_path.exists():
        return {
            canonicalize_url(line.strip())
            for line in index_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }

    seen: set[str] = set()
    for path in config.source_raw_dir(source).glob("*.jsonl"):
        for row in read_jsonl(path):
            url = row.get("url")
            if url:
                seen.add(canonicalize_url(str(url)))
    if seen:
        index_path.write_text("\n".join(sorted(seen)) + "\n", encoding="utf-8")
    return seen


def append_seen_urls(source: str, urls: list[str], *, config, canonicalize_url) -> None:
    if not urls:
        return
    index_path = config.source_seen_urls_path(source)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("a", encoding="utf-8") as handle:
        for url in urls:
            handle.write(f"{canonicalize_url(url)}\n")


def iter_scanned_sitemaps(source: str, *, config) -> set[str]:
    path = config.source_scanned_sitemaps_path(source)
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def append_scanned_sitemap(source: str, sitemap_url: str, *, config) -> None:
    path = config.source_scanned_sitemaps_path(source)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{sitemap_url.strip()}\n")


def save_fetched_news(
    records: list[dict[str, object]],
    source: str,
    *,
    config,
    canonicalize_url,
    iter_existing_urls_fn,
    append_seen_urls_fn,
    update_source_manifest,
    write_jsonl_records,
    unparsable_raw_bucket: str,
) -> int:
    tracked_urls = iter_existing_urls_fn(source)
    unique_records: list[dict[str, object]] = []
    new_urls: list[str] = []
    for record in records:
        canonical_url = canonicalize_url(str(record.get("url", "")))
        if not canonical_url or canonical_url in tracked_urls:
            continue
        tracked_urls.add(canonical_url)
        payload = dict(record)
        payload["url"] = canonical_url
        unique_records.append(payload)
        new_urls.append(canonical_url)

    grouped: dict[str, list[dict[str, object]]] = {}
    for record in unique_records:
        published_ts = pd.to_datetime(record.get("published_at"), utc=True, errors="coerce")
        if pd.isna(published_ts):
            date_key = unparsable_raw_bucket
        else:
            date_key = pd.Timestamp(published_ts).strftime("%Y-%m-%d")
        grouped.setdefault(date_key, []).append(record)
    for date_key, rows in grouped.items():
        path = config.source_raw_dir(source) / f"{date_key}.jsonl"
        write_jsonl_records(path, rows, append=path.exists())
    append_seen_urls_fn(source, new_urls)
    update_source_manifest(
        source=source,
        payload={
            "source": source,
            "raw_file_count": len(list(config.source_raw_dir(source).glob("*.jsonl"))),
            "article_count": len(tracked_urls),
            "last_saved_batch_count": len(unique_records),
            "last_fetch_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        config=config,
    )
    return len(unique_records)

