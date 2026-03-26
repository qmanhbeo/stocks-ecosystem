"""Fetch raw news articles into data/news/ for downstream feature generation."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import re
import threading
from time import sleep
from typing import Iterable, List, Optional
from urllib.parse import urljoin
from xml.etree import ElementTree

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests import Response

from research_pipelines.news_features.config import get_default_config
from research_pipelines.news_features.io_utils import (
    canonicalize_url,
    load_source_specs,
    make_article_id,
    read_jsonl,
    update_source_manifest,
    write_jsonl_records,
)


ARTICLE_URL_RE = re.compile(r"^https://cafef\.vn/.+-\d+\.chn$")
SITEMAP_RANGE_RE = re.compile(r"sitemaps-(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<start>\d{1,2})-(?P<end>\d{1,2})\.xml$")
CAFEF_URL_NUMERIC_SUFFIX_RE = re.compile(r"-(?P<digits>\d+)\.chn$")
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
UNPARSABLE_RAW_BUCKET = "unparsable"


class NewsFetchInterrupted(KeyboardInterrupt):
    """Raised when a long-running news fetch is interrupted after partial progress."""

    def __init__(
        self,
        records: List[dict[str, object]],
        output_dir: str,
        processed_candidates: int,
        total_candidates: int,
        saved_records_count: int,
    ) -> None:
        super().__init__("News fetch interrupted by user")
        self.records = list(records)
        self.output_dir = output_dir
        self.processed_candidates = int(processed_candidates)
        self.total_candidates = int(total_candidates)
        self.saved_records_count = int(saved_records_count)


class NewsArticleParseError(RuntimeError):
    """Raised when an article response cannot be parsed cleanly."""

    def __init__(self, article_url: str, exc: Exception) -> None:
        message = f"Failed to parse article URL: {article_url} ({exc.__class__.__name__}: {exc})"
        super().__init__(message)
        self.article_url = article_url
        self.original_exception = exc


def _build_http_session(user_agent: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})
    return session


def _should_skip_article_response(response: Response) -> bool:
    return response.status_code in {404, 410}


def _is_retryable_status_code(status_code: int) -> bool:
    return status_code in RETRYABLE_STATUS_CODES


def _get_with_retries(
    session: requests.Session,
    url: str,
    timeout: float,
    retry_attempts: int,
    retry_backoff_seconds: float,
    request_label: str,
) -> Response:
    attempts = max(int(retry_attempts), 1)
    backoff = max(float(retry_backoff_seconds), 0.0)

    for attempt in range(1, attempts + 1):
        try:
            response = session.get(url, timeout=timeout)
        except requests.RequestException as exc:
            if attempt >= attempts:
                raise
            print(
                f"{request_label} request failed on attempt {attempt}/{attempts}: {url} ({exc.__class__.__name__})",
                flush=True,
            )
            if backoff > 0:
                sleep(backoff * attempt)
            continue

        if _is_retryable_status_code(response.status_code):
            if attempt >= attempts:
                print(
                    f"{request_label} request failed after {attempts} attempts with HTTP {response.status_code}: {url}",
                    flush=True,
                )
                response.raise_for_status()
            else:
                print(
                    f"{request_label} request got HTTP {response.status_code} on attempt {attempt}/{attempts}: {url}",
                    flush=True,
                )
                if backoff > 0:
                    sleep(backoff * attempt)
                continue
        return response

    raise RuntimeError(f"Unreachable retry state for URL: {url}")


def extract_article_links(html: str, base_url: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: List[str] = []
    for anchor in soup.select("a[href]"):
        href = anchor.get("href")
        if not href:
            continue
        full_url = canonicalize_url(urljoin(base_url, href))
        if "cafef.vn" not in full_url:
            continue
        if not ARTICLE_URL_RE.match(full_url):
            continue
        links.append(full_url)
    return sorted(dict.fromkeys(links))


def extract_rss_article_links(xml_text: str, base_url: str) -> List[str]:
    links: List[str] = []
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return links
    for node in root.findall(".//item/link"):
        href = (node.text or "").strip()
        if not href:
            continue
        full_url = canonicalize_url(urljoin(base_url, href))
        if "cafef.vn" not in full_url:
            continue
        if not ARTICLE_URL_RE.match(full_url):
            continue
        links.append(full_url)
    return sorted(dict.fromkeys(links))


def parse_sitemap_index(xml_text: str) -> List[dict[str, str]]:
    rows: List[dict[str, str]] = []
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return rows
    for node in root.findall(".//{*}sitemap"):
        loc = (node.findtext("{*}loc") or "").strip()
        lastmod = (node.findtext("{*}lastmod") or "").strip()
        if not loc:
            continue
        rows.append({"loc": loc, "lastmod": lastmod})
    return rows


def parse_url_sitemap(xml_text: str) -> List[dict[str, str]]:
    rows: List[dict[str, str]] = []
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return rows
    for node in root.findall(".//{*}url"):
        loc = (node.findtext("{*}loc") or "").strip()
        lastmod = (node.findtext("{*}lastmod") or "").strip()
        if not loc:
            continue
        rows.append({"loc": loc, "lastmod": lastmod})
    return rows


def _extract_text_by_selectors(soup: BeautifulSoup, selectors: Iterable[str]) -> str:
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            return " ".join(node.stripped_strings)
    return ""


def _extract_cafef_section_name_from_soup(soup: BeautifulSoup) -> str | None:
    section_name = _extract_text_by_selectors(
        soup,
        [
            ".dateandcat a[data-role='cate-name']",
            "p.dateandcat a.category-page__name",
            "p.dateandcat a.cat",
            ".dateandcat a[href$='.chn']",
        ],
    )
    return section_name or None


def extract_cafef_section_name(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    return _extract_cafef_section_name_from_soup(soup)


def infer_cafef_url_timestamp(url: str) -> pd.Timestamp | None:
    match = CAFEF_URL_NUMERIC_SUFFIX_RE.search(url)
    if not match:
        return None

    digits = match.group("digits")
    config = get_default_config()
    market_timezone = config.market_timezone

    candidate_components: list[tuple[int, int, int, int, int, int]] = []
    if digits.startswith("188") and len(digits) >= 15:
        encoded = digits[3:15]
        candidate_components.append(
            (
                2000 + int(encoded[0:2]),
                int(encoded[2:4]),
                int(encoded[4:6]),
                int(encoded[6:8]),
                int(encoded[8:10]),
                int(encoded[10:12]),
            )
        )
    if len(digits) >= 14:
        encoded_year = int(digits[0:4])
        if 2000 <= encoded_year <= 2099:
            candidate_components.append(
                (
                    encoded_year,
                    int(digits[4:6]),
                    int(digits[6:8]),
                    int(digits[8:10]),
                    int(digits[10:12]),
                    int(digits[12:14]),
                )
            )

    for year, month, day, hour, minute, second in candidate_components:
        try:
            local_timestamp = pd.Timestamp(
                year=year,
                month=month,
                day=day,
                hour=hour,
                minute=minute,
                second=second,
            )
        except ValueError:
            continue
        return local_timestamp.tz_localize(market_timezone).tz_convert("UTC")

    return None


def _parse_cafef_published_timestamp(published_text: str, url: str) -> tuple[pd.Timestamp | None, str]:
    config = get_default_config()
    market_timezone = config.market_timezone

    text = str(published_text).strip()
    is_iso_like = bool(re.match(r"^\d{4}-\d{1,2}-\d{1,2}", text))
    parsed = pd.to_datetime(text, errors="coerce", dayfirst=not is_iso_like)
    if not pd.isna(parsed):
        timestamp = pd.Timestamp(parsed)
        if timestamp.tzinfo is None:
            return timestamp.tz_localize(market_timezone).tz_convert("UTC"), "html"
        return timestamp.tz_convert("UTC"), "html"

    inferred = infer_cafef_url_timestamp(url)
    if inferred is not None:
        return inferred, "url"

    return None, "unparsable"


def parse_cafef_article(html: str, url: str) -> Optional[dict[str, object]]:
    soup = BeautifulSoup(html, "html.parser")
    title = _extract_text_by_selectors(soup, ["h1", ".title", ".detail-title"])
    body = _extract_text_by_selectors(
        soup,
        [".detail-content", ".detail-content-afcbc-body", ".contentdetail", ".contentdetail div"],
    )
    summary = _extract_text_by_selectors(soup, [".sapo", ".detail-sapo", ".lead"])
    published = _extract_text_by_selectors(soup, [".pdate", ".time", ".detail-time"])
    author = _extract_text_by_selectors(soup, [".author", ".detail-author"])
    section_name = _extract_cafef_section_name_from_soup(soup)
    tags = [" ".join(node.stripped_strings) for node in soup.select(".tag-list a, .news-tag a")]

    if not title or not body:
        return None

    published_ts, published_at_source = _parse_cafef_published_timestamp(published, url)

    return {
        "article_id": make_article_id("cafef", url),
        "source": "cafef",
        "url": canonicalize_url(url),
        "title": title,
        "summary": summary,
        "body_text": body,
        "published_at": published_ts.strftime("%Y-%m-%dT%H:%M:%SZ") if published_ts is not None else None,
        "published_at_source": published_at_source,
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "author": author or None,
        "section_name": section_name,
        "tags": tags,
    }


def _iter_existing_urls(source: str) -> set[str]:
    config = get_default_config()
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


def _append_seen_urls(source: str, urls: List[str]) -> None:
    if not urls:
        return
    config = get_default_config()
    index_path = config.source_seen_urls_path(source)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("a", encoding="utf-8") as handle:
        for url in urls:
            handle.write(f"{canonicalize_url(url)}\n")


def _iter_scanned_sitemaps(source: str) -> set[str]:
    config = get_default_config()
    path = config.source_scanned_sitemaps_path(source)
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def _append_scanned_sitemap(source: str, sitemap_url: str) -> None:
    config = get_default_config()
    path = config.source_scanned_sitemaps_path(source)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{sitemap_url.strip()}\n")


def _make_thread_session_getter(user_agent: str):
    thread_state = threading.local()

    def get_session() -> requests.Session:
        session = getattr(thread_state, "session", None)
        if session is None:
            session = _build_http_session(user_agent)
            thread_state.session = session
        return session

    return get_session


def _fetch_article_result(
    article_url: str,
    start_ts: Optional[pd.Timestamp],
    end_ts: Optional[pd.Timestamp],
    timeout: float,
    retry_attempts: int,
    retry_backoff_seconds: float,
    get_session,
) -> dict[str, object]:
    try:
        article_response = _get_with_retries(
            session=get_session(),
            url=article_url,
            timeout=timeout,
            retry_attempts=retry_attempts,
            retry_backoff_seconds=retry_backoff_seconds,
            request_label="Article",
        )
    except requests.RequestException:
        return {"status": "failed", "url": article_url}

    if _should_skip_article_response(article_response):
        return {"status": "missing", "url": article_url, "status_code": article_response.status_code}

    article_response.raise_for_status()
    try:
        record = parse_cafef_article(article_response.text, article_url)
    except Exception as exc:
        raise NewsArticleParseError(article_url, exc) from exc
    if record is None:
        return {"status": "unparsed", "url": article_url}

    published_ts = pd.to_datetime(record.get("published_at"), utc=True, errors="coerce")
    if not pd.isna(published_ts):
        if start_ts is not None and published_ts < start_ts:
            return {"status": "out_of_range", "url": article_url}
        if end_ts is not None and published_ts > end_ts:
            return {"status": "out_of_range", "url": article_url}
    return {"status": "ok", "url": article_url, "record": record}


def _candidate_urls_from_sitemap_response(
    sitemap_url: str,
    response: Response,
    start_ts: Optional[pd.Timestamp],
    end_ts: Optional[pd.Timestamp],
) -> List[str]:
    urls: List[str] = []
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
        if not ARTICLE_URL_RE.match(loc):
            continue
        article_ts = _parse_timestamp(row.get("lastmod"))
        if start_ts is not None and article_ts is not None and article_ts < start_ts:
            continue
        if end_ts is not None and article_ts is not None and article_ts > end_ts:
            continue
        if loc in seen_urls:
            continue
        seen_urls.add(loc)
        urls.append(loc)
    return urls


def _collect_listing_urls(source_spec: dict[str, object], max_pages: int) -> List[str]:
    urls: List[str] = []
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


def _parse_ticker_argument(value: Optional[str]) -> List[str]:
    if not value:
        return []
    parts = re.split(r"[\s,]+", str(value).strip())
    return [part.upper() for part in parts if part.strip()]


def _collect_ticker_listing_urls(
    source_spec: dict[str, object],
    tickers: List[str],
    max_pages: int,
    default_max_pages: int,
) -> List[tuple[str, str]]:
    template = str(source_spec.get("ticker_listing_url_template", "")).strip()
    if not template:
        return []
    pages_per_ticker = max_pages if max_pages > 0 else max(int(default_max_pages), 1)
    urls: List[tuple[str, str]] = []
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


def _parse_timestamp(value: Optional[str]) -> pd.Timestamp | None:
    if not value:
        return None
    text = str(value).strip()
    is_iso_like = bool(re.match(r"^\d{4}-\d{1,2}-\d{1,2}", text))
    dayfirst = "T" not in text and not is_iso_like
    timestamp = pd.to_datetime(text, utc=True, errors="coerce", dayfirst=dayfirst)
    if pd.isna(timestamp):
        return None
    return timestamp


def _parse_input_bound(value: Optional[str], is_end: bool) -> pd.Timestamp | None:
    timestamp = _parse_timestamp(value)
    if timestamp is None:
        return None
    text = str(value).strip()
    if "T" not in text and " " not in text:
        if is_end:
            return timestamp + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        return timestamp
    return timestamp


def _current_utc_timestamp() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC")


def _sitemap_range(loc: str) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    match = SITEMAP_RANGE_RE.search(loc)
    if not match:
        return None
    year = int(match.group("year"))
    month = int(match.group("month"))
    day_start = int(match.group("start"))
    day_end = int(match.group("end"))
    start = pd.Timestamp(year=year, month=month, day=day_start, tz="UTC")
    end = pd.Timestamp(year=year, month=month, day=day_end, tz="UTC") + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    return start, end


def _ranges_overlap(
    left_start: Optional[pd.Timestamp],
    left_end: Optional[pd.Timestamp],
    right_start: pd.Timestamp,
    right_end: pd.Timestamp,
) -> bool:
    effective_left_start = left_start or pd.Timestamp("1970-01-01", tz="UTC")
    effective_left_end = left_end or pd.Timestamp("2100-01-01", tz="UTC")
    return effective_left_start <= right_end and effective_left_end >= right_start


def _should_rescan_sitemap(
    sitemap_url: str,
    now_ts: pd.Timestamp,
    recent_days: int,
) -> bool:
    if recent_days <= 0:
        return False
    range_info = _sitemap_range(sitemap_url)
    if range_info is None:
        return True
    _range_start, range_end = range_info
    cutoff = now_ts - pd.Timedelta(days=recent_days)
    return range_end >= cutoff


def _select_sitemap_urls(
    index_rows: List[dict[str, str]],
    start_ts: Optional[pd.Timestamp],
    end_ts: Optional[pd.Timestamp],
    max_documents: int,
) -> List[str]:
    selected: List[tuple[pd.Timestamp, str]] = []
    fallback_recent: List[tuple[pd.Timestamp, str]] = []
    for row in index_rows:
        loc = row["loc"]
        row_lastmod = _parse_timestamp(row.get("lastmod")) or pd.Timestamp("1970-01-01", tz="UTC")
        range_info = _sitemap_range(loc)
        if range_info is not None:
            range_start, range_end = range_info
            if _ranges_overlap(start_ts, end_ts, range_start, range_end):
                selected.append((range_end, loc))
            continue

        if any(token in loc for token in ("latest-news-sitemap.xml", "google-news-sitemap.xml", "category.rss")):
            fallback_recent.append((row_lastmod, loc))

    ordered = [loc for _ts, loc in sorted(dict.fromkeys(selected), reverse=True)]
    if not ordered:
        ordered = [loc for _ts, loc in sorted(dict.fromkeys(fallback_recent), reverse=True)]
    if max_documents > 0:
        ordered = ordered[:max_documents]
    return ordered


def _candidate_urls_from_sitemaps(
    session: requests.Session,
    sitemap_urls: List[str],
    start_ts: Optional[pd.Timestamp],
    end_ts: Optional[pd.Timestamp],
    timeout: float,
    retry_attempts: int = 3,
    retry_backoff_seconds: float = 1.0,
) -> List[str]:
    urls: List[str] = []
    seen_urls: set[str] = set()
    total_sitemaps = len(sitemap_urls)
    progress_every = 1 if total_sitemaps <= 10 else 10

    for index, sitemap_url in enumerate(sitemap_urls, start=1):
        try:
            response = _get_with_retries(
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
            print(f"Skipping missing sitemap URL: {sitemap_url}")
            continue
        response.raise_for_status()
        for loc in _candidate_urls_from_sitemap_response(sitemap_url, response, start_ts, end_ts):
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


def _response_links(response: Response, base_url: str) -> List[str]:
    content_type = response.headers.get("Content-Type", "").lower()
    if "xml" in content_type or response.text.lstrip().startswith("<?xml"):
        return extract_rss_article_links(response.text, base_url=base_url)
    return extract_article_links(response.text, base_url=base_url)


def fetch_news(
    source: str,
    start_date: Optional[str],
    end_date: Optional[str],
    max_pages: int,
    delay: float,
    tickers: Optional[List[str]] = None,
    workers: int = 1,
    overwrite: bool = False,
) -> List[dict[str, object]]:
    config = get_default_config()
    specs = load_source_specs(config=config)
    source_spec = specs.get(source)
    if source_spec is None:
        raise ValueError(f"Unsupported source: {source}")
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
    session = _build_http_session(user_agent)

    start_ts = _parse_input_bound(start_date, is_end=False)
    end_ts = _parse_input_bound(end_date, is_end=True)
    existing_urls = _iter_existing_urls(source)
    scanned_sitemaps = _iter_scanned_sitemaps(source)

    base_url = str(source_spec["base_url"])
    records: List[dict[str, object]] = []
    seen_urls: set[str] = set()
    processed_candidates = 0
    discovered_candidates = 0
    skipped_missing_articles = 0
    saved_records_count = 0
    pending_records: List[dict[str, object]] = []
    selected_sitemap_count = 0
    ticker_list = [ticker.upper() for ticker in (tickers or []) if str(ticker).strip()]
    used_ticker_mode = bool(ticker_list)
    now_ts = _current_utc_timestamp()
    article_workers = max(int(workers), 1)
    thread_session_getter = _make_thread_session_getter(user_agent)
    if article_workers > 1:
        print(f"Parallel article fetching enabled with {article_workers} workers", flush=True)
    try:
        def process_candidate_urls(candidate_urls: List[str]) -> None:
            nonlocal processed_candidates
            nonlocal skipped_missing_articles
            nonlocal saved_records_count
            nonlocal pending_records
            nonlocal discovered_candidates

            urls_to_fetch: List[str] = []
            for article_url in candidate_urls:
                canonical_url = canonicalize_url(article_url)
                if canonical_url in seen_urls or canonical_url in existing_urls:
                    processed_candidates += 1
                    if processed_candidates == 1 or processed_candidates % 50 == 0:
                        print(
                            f"Processed {processed_candidates} discovered article URLs so far, kept {len(records)} records, saved={saved_records_count}, skipped_missing={skipped_missing_articles}",
                            flush=True,
                        )
                    continue
                seen_urls.add(canonical_url)
                urls_to_fetch.append(article_url)

            discovered_candidates += len(urls_to_fetch)

            def handle_result(result: dict[str, object], count_as_processed: bool = True) -> None:
                nonlocal processed_candidates
                nonlocal skipped_missing_articles
                nonlocal saved_records_count
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
                        print(
                            f"Skipping missing article URL ({result['status_code']}): {article_url}",
                            flush=True,
                        )
                elif status == "ok":
                    record = dict(result["record"])
                    records.append(record)
                    pending_records.append(record)
                    if len(pending_records) >= config.raw_save_batch_size:
                        saved_records_count += save_fetched_news(pending_records, source=source)
                        pending_records = []
                    sleep(delay)
                if processed_candidates == 1 or processed_candidates % 50 == 0:
                    print(
                        f"Processed {processed_candidates} discovered article URLs so far, kept {len(records)} records, saved={saved_records_count}, skipped_missing={skipped_missing_articles}",
                        flush=True,
                    )

            if article_workers <= 1 or len(urls_to_fetch) <= 1:
                for article_url in urls_to_fetch:
                    processed_candidates += 1
                    handle_result(
                        _fetch_article_result(
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
                    lambda url: _fetch_article_result(
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
        if ticker_list:
            ticker_listing_urls = _collect_ticker_listing_urls(
                source_spec=source_spec,
                tickers=ticker_list,
                max_pages=max_pages,
                default_max_pages=config.max_listing_pages,
            )
            print(
                f"Ticker mode enabled for {', '.join(ticker_list)} across {len(ticker_listing_urls)} listing pages",
                flush=True,
            )
            for listing_index, (ticker, listing_url) in enumerate(ticker_listing_urls, start=1):
                try:
                    response = _get_with_retries(
                        session=session,
                        url=listing_url,
                        timeout=config.source_timeout_seconds,
                        retry_attempts=config.request_retry_attempts,
                        retry_backoff_seconds=config.request_retry_backoff_seconds,
                        request_label=f"Ticker listing {ticker}",
                    )
                except requests.RequestException:
                    print(f"Skipping failed ticker listing URL after retries: {listing_url}", flush=True)
                    continue
                if response.status_code == 404:
                    print(f"Skipping missing ticker listing URL: {listing_url}", flush=True)
                    continue
                response.raise_for_status()
                ticker_candidate_urls = _response_links(response, base_url=base_url)
                print(
                    f"Ticker listing {listing_index}/{len(ticker_listing_urls)} for {ticker} yielded {len(ticker_candidate_urls)} candidate article URLs",
                    flush=True,
                )
                process_candidate_urls(ticker_candidate_urls)
        elif sitemap_index_url:
            try:
                sitemap_index_response = _get_with_retries(
                    session=session,
                    url=sitemap_index_url,
                    timeout=config.source_timeout_seconds,
                    retry_attempts=config.request_retry_attempts,
                    retry_backoff_seconds=config.request_retry_backoff_seconds,
                    request_label="Sitemap index",
                )
            except requests.RequestException:
                print(
                    f"Failed to load sitemap index after retries: {sitemap_index_url}. Falling back to listing pages.",
                    flush=True,
                )
            else:
                index_rows = parse_sitemap_index(sitemap_index_response.text)
                sitemap_urls = _select_sitemap_urls(index_rows, start_ts=start_ts, end_ts=end_ts, max_documents=max_pages)
                selected_sitemap_count = len(sitemap_urls)
                print(f"Selected {len(sitemap_urls)} sitemap documents from {sitemap_index_url}", flush=True)
                if sitemap_urls:
                    print("Streaming sitemap scan and article fetch...", flush=True)
                progress_every = 1 if len(sitemap_urls) <= 10 else 10
                for sitemap_index, sitemap_url in enumerate(sitemap_urls, start=1):
                    should_recheck_recent = sitemap_url in scanned_sitemaps and _should_rescan_sitemap(
                        sitemap_url,
                        now_ts=now_ts,
                        recent_days=config.rescan_recent_sitemap_days,
                    )
                    if sitemap_url in scanned_sitemaps and not should_recheck_recent:
                        if (
                            sitemap_index == 1
                            or sitemap_index % progress_every == 0
                            or sitemap_index == len(sitemap_urls)
                        ):
                            print(
                                f"Sitemap {sitemap_index}/{len(sitemap_urls)} already scanned, skipping",
                                flush=True,
                            )
                        continue
                    if should_recheck_recent:
                        print(
                            f"Sitemap {sitemap_index}/{len(sitemap_urls)} was scanned before but is still recent, rechecking",
                            flush=True,
                        )
                    try:
                        response = _get_with_retries(
                            session=session,
                            url=sitemap_url,
                            timeout=config.source_timeout_seconds,
                            retry_attempts=config.request_retry_attempts,
                            retry_backoff_seconds=config.request_retry_backoff_seconds,
                            request_label="Sitemap",
                        )
                    except requests.RequestException:
                        print(f"Skipping failed sitemap URL after retries: {sitemap_url}", flush=True)
                        continue
                    if response.status_code == 404:
                        print(f"Skipping missing sitemap URL: {sitemap_url}", flush=True)
                        continue
                    response.raise_for_status()
                    sitemap_candidate_urls = _candidate_urls_from_sitemap_response(
                        sitemap_url,
                        response,
                        start_ts,
                        end_ts,
                    )
                    print(
                        f"Sitemap {sitemap_index}/{len(sitemap_urls)} yielded {len(sitemap_candidate_urls)} candidate article URLs; discovered={discovered_candidates + len(sitemap_candidate_urls)}",
                        flush=True,
                    )
                    process_candidate_urls(sitemap_candidate_urls)
                    if sitemap_url not in scanned_sitemaps:
                        _append_scanned_sitemap(source, sitemap_url)
                        scanned_sitemaps.add(sitemap_url)
                    if (
                        sitemap_index == 1
                        or sitemap_index % progress_every == 0
                        or sitemap_index == len(sitemap_urls)
                    ):
                        print(
                            f"Completed sitemap {sitemap_index}/{len(sitemap_urls)}; processed={processed_candidates}, saved={saved_records_count}",
                            flush=True,
                        )

        if not used_ticker_mode and selected_sitemap_count == 0:
            listing_urls = _collect_listing_urls(source_spec, max_pages=max_pages)
            for listing_index, listing_url in enumerate(listing_urls, start=1):
                try:
                    response = _get_with_retries(
                        session=session,
                        url=listing_url,
                        timeout=config.source_timeout_seconds,
                        retry_attempts=config.request_retry_attempts,
                        retry_backoff_seconds=config.request_retry_backoff_seconds,
                        request_label="Listing",
                    )
                except requests.RequestException:
                    print(f"Skipping failed listing URL after retries: {listing_url}", flush=True)
                    continue
                if response.status_code == 404:
                    print(f"Skipping missing listing URL: {listing_url}")
                    continue
                response.raise_for_status()
                listing_candidate_urls = _response_links(response, base_url=base_url)
                print(
                    f"Listing {listing_index}/{len(listing_urls)} yielded {len(listing_candidate_urls)} candidate article URLs",
                    flush=True,
                )
                process_candidate_urls(listing_candidate_urls)
        if pending_records:
            saved_records_count += save_fetched_news(pending_records, source=source)
        return records
    except KeyboardInterrupt as exc:
        if pending_records:
            saved_records_count += save_fetched_news(pending_records, source=source)
        raise NewsFetchInterrupted(
            records=records,
            output_dir=str(config.source_raw_dir(source)),
            processed_candidates=processed_candidates,
            total_candidates=discovered_candidates,
            saved_records_count=saved_records_count,
        ) from exc


def save_fetched_news(records: List[dict[str, object]], source: str) -> int:
    config = get_default_config()
    tracked_urls = _iter_existing_urls(source)
    unique_records: List[dict[str, object]] = []
    new_urls: List[str] = []
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
            date_key = UNPARSABLE_RAW_BUCKET
        else:
            date_key = pd.Timestamp(published_ts).strftime("%Y-%m-%d")
        grouped.setdefault(date_key, []).append(record)
    for date_key, rows in grouped.items():
        path = config.source_raw_dir(source) / f"{date_key}.jsonl"
        write_jsonl_records(path, rows, append=path.exists())
    _append_seen_urls(source, new_urls)
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


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch raw news articles for downstream feature generation.")
    parser.add_argument("--source", default="cafef", help="News source to fetch (default: cafef)")
    parser.add_argument(
        "--tickers",
        default=None,
        help="Optional comma-separated list of Cafef ticker pages to crawl (e.g., ACB,VNM,HPG)",
    )
    parser.add_argument("--start-date", default=None, help="Optional inclusive start date filter (YYYY-MM-DD)")
    parser.add_argument("--end-date", default=None, help="Optional inclusive end date filter (YYYY-MM-DD)")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=0,
        help="Maximum number of sitemap or listing documents to scan (default: 0 = all matching)",
    )
    parser.add_argument("--delay", type=float, default=0.0, help="Delay between article requests in seconds")
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Parallel article fetch workers (default: 1)",
    )
    parser.add_argument("--overwrite", action="store_true", help="Ignore existing raw files when fetching")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    try:
        records = fetch_news(
            source=args.source,
            start_date=args.start_date,
            end_date=args.end_date,
            max_pages=args.max_pages,
            delay=args.delay,
            tickers=_parse_ticker_argument(args.tickers),
            workers=args.workers,
            overwrite=args.overwrite,
        )
        print(f"Fetched {len(records)} raw articles into data/news/{args.source}/raw")
        return 0
    except NewsFetchInterrupted as exc:
        print("\nCancellation requested. Partial raw news records were already saved.", flush=True)
        print(
            f"Fetch cancelled after processing {exc.processed_candidates}/{exc.total_candidates} candidate article pages.",
            flush=True,
        )
        print(f"Saved {exc.saved_records_count} raw articles so far into {exc.output_dir}", flush=True)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
