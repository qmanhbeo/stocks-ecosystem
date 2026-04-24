from __future__ import annotations

import re
from typing import Optional

import pandas as pd
import requests
from requests import Response


def collect_listing_urls(source_spec: dict[str, object], max_pages: int) -> list[str]:
    urls: list[str] = []
    category_url = str(source_spec.get("category_url", "")).strip()
    rss_url = str(source_spec.get("rss_url", "")).strip()
    if category_url:
        urls.append(category_url)
    if rss_url:
        urls.append(rss_url)

    template = str(source_spec.get("listing_url_template", "")).strip()
    if template:
        for page in range(2, max_pages + 1):
            urls.append(template.format(page=page))
    return list(dict.fromkeys(urls))


def parse_ticker_argument(value: Optional[str]) -> list[str]:
    if not value:
        return []
    parts = re.split(r"[\s,]+", str(value).strip())
    return [part.upper() for part in parts if part.strip()]


def collect_ticker_listing_urls(
    source_spec: dict[str, object],
    tickers: list[str],
    max_pages: int,
    default_max_pages: int,
) -> list[tuple[str, str]]:
    template = str(source_spec.get("ticker_listing_url_template", "")).strip()
    if not template:
        return []
    pages_per_ticker = max_pages if max_pages > 0 else max(int(default_max_pages), 1)
    urls: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for ticker in tickers:
        for page in range(1, pages_per_ticker + 1):
            item = (
                ticker,
                template.format(
                    ticker=ticker,
                    ticker_lower=ticker.lower(),
                    ticker_upper=ticker.upper(),
                    page=page,
                ),
            )
            if item in seen:
                continue
            seen.add(item)
            urls.append(item)
    return urls


def parse_timestamp(value: Optional[str]) -> pd.Timestamp | None:
    if not value:
        return None
    text = str(value).strip()
    is_iso_like = bool(re.match(r"^\d{4}-\d{1,2}-\d{1,2}", text))
    dayfirst = "T" not in text and not is_iso_like
    timestamp = pd.to_datetime(text, utc=True, errors="coerce", dayfirst=dayfirst)
    if pd.isna(timestamp):
        return None
    return timestamp


def parse_input_bound(value: Optional[str], is_end: bool) -> pd.Timestamp | None:
    timestamp = parse_timestamp(value)
    if timestamp is None:
        return None
    text = str(value).strip()
    if "T" not in text and " " not in text:
        if is_end:
            return timestamp + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        return timestamp
    return timestamp


def current_utc_timestamp() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC")


def sitemap_range(loc: str, sitemap_range_re: re.Pattern[str]) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    match = sitemap_range_re.search(loc)
    if not match:
        return None
    year = int(match.group("year"))
    month = int(match.group("month"))
    day_start = int(match.group("start"))
    day_end = int(match.group("end"))
    start = pd.Timestamp(year=year, month=month, day=day_start, tz="UTC")
    end = pd.Timestamp(year=year, month=month, day=day_end, tz="UTC") + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    return start, end


def ranges_overlap(
    left_start: pd.Timestamp | None,
    left_end: pd.Timestamp | None,
    right_start: pd.Timestamp,
    right_end: pd.Timestamp,
) -> bool:
    effective_left_start = left_start or pd.Timestamp("1970-01-01", tz="UTC")
    effective_left_end = left_end or pd.Timestamp("2100-01-01", tz="UTC")
    return effective_left_start <= right_end and effective_left_end >= right_start


def should_rescan_sitemap(
    sitemap_url: str,
    now_ts: pd.Timestamp,
    recent_days: int,
    sitemap_range_re: re.Pattern[str],
) -> bool:
    if recent_days <= 0:
        return False
    range_info = sitemap_range(sitemap_url, sitemap_range_re)
    if range_info is None:
        return True
    _, range_end = range_info
    cutoff = now_ts - pd.Timedelta(days=recent_days)
    return range_end >= cutoff


def select_sitemap_urls(
    index_rows: list[dict[str, str]],
    start_ts: pd.Timestamp | None,
    end_ts: pd.Timestamp | None,
    max_documents: int,
    sitemap_range_re: re.Pattern[str],
) -> list[str]:
    selected: list[tuple[pd.Timestamp, str]] = []
    fallback_recent: list[tuple[pd.Timestamp, str]] = []
    for row in index_rows:
        loc = row["loc"]
        row_lastmod = parse_timestamp(row.get("lastmod")) or pd.Timestamp("1970-01-01", tz="UTC")
        range_info = sitemap_range(loc, sitemap_range_re)
        if range_info is not None:
            range_start, range_end = range_info
            if ranges_overlap(start_ts, end_ts, range_start, range_end):
                selected.append((range_end, loc))
            continue

        if any(token in loc for token in ("latest-news-sitemap.xml", "google-news-sitemap.xml", "category.rss")):
            fallback_recent.append((row_lastmod, loc))

    ordered = [loc for _, loc in sorted(dict.fromkeys(selected), reverse=True)]
    if not ordered:
        ordered = [loc for _, loc in sorted(dict.fromkeys(fallback_recent), reverse=True)]
    if max_documents > 0:
        ordered = ordered[:max_documents]
    return ordered


def candidate_urls_from_sitemap_response(
    sitemap_url: str,
    response: Response,
    start_ts: pd.Timestamp | None,
    end_ts: pd.Timestamp | None,
    *,
    parse_url_sitemap,
    extract_rss_article_links,
    canonicalize_url,
    article_url_re: re.Pattern[str],
) -> list[str]:
    urls: list[str] = []
    seen_urls: set[str] = set()

    if sitemap_url.endswith(".rss"):
        for loc in extract_rss_article_links(response.text, base_url="https://cafef.vn"):
            if loc in seen_urls:
                continue
            seen_urls.add(loc)
            urls.append(loc)
        return urls

    rows = parse_url_sitemap(response.text)
    for row in rows:
        loc = canonicalize_url(row["loc"])
        if not article_url_re.match(loc):
            continue
        article_ts = parse_timestamp(row.get("lastmod"))
        if start_ts is not None and article_ts is not None and article_ts < start_ts:
            continue
        if end_ts is not None and article_ts is not None and article_ts > end_ts:
            continue
        if loc in seen_urls:
            continue
        seen_urls.add(loc)
        urls.append(loc)
    return urls


def candidate_urls_from_sitemaps(
    session: requests.Session,
    sitemap_urls: list[str],
    start_ts: pd.Timestamp | None,
    end_ts: pd.Timestamp | None,
    timeout: float,
    *,
    get_with_retries,
    candidate_urls_from_sitemap_response_fn,
    retry_attempts: int = 3,
    retry_backoff_seconds: float = 1.0,
) -> list[str]:
    urls: list[str] = []
    seen_urls: set[str] = set()
    total_sitemaps = len(sitemap_urls)
    progress_every = 1 if total_sitemaps <= 10 else 10

    for index, sitemap_url in enumerate(sitemap_urls, start=1):
        try:
            response = get_with_retries(
                session=session,
                url=sitemap_url,
                timeout=timeout,
                retry_attempts=retry_attempts,
                retry_backoff_seconds=retry_backoff_seconds,
                request_label="Sitemap",
            )
        except requests.RequestException:
            print(f"Skipping failed sitemap URL after retries: {sitemap_url}", flush=True)
            continue
        if response.status_code == 404:
            print(f"Skipping missing sitemap URL: {sitemap_url}", flush=True)
            continue
        response.raise_for_status()
        for loc in candidate_urls_from_sitemap_response_fn(sitemap_url, response, start_ts, end_ts):
            if loc in seen_urls:
                continue
            seen_urls.add(loc)
            urls.append(loc)

        if index == 1 or index % progress_every == 0 or index == total_sitemaps:
            print(
                f"Scanned {index}/{total_sitemaps} sitemap documents, accumulated {len(urls)} candidate article URLs",
                flush=True,
            )
    return urls


def response_links(response: Response, base_url: str, *, extract_rss_article_links, extract_article_links) -> list[str]:
    content_type = response.headers.get("Content-Type", "").lower()
    if "xml" in content_type or response.text.lstrip().startswith("<?xml"):
        return extract_rss_article_links(response.text, base_url=base_url)
    return extract_article_links(response.text, base_url=base_url)

