"""Fetch raw news articles into data/news/ for downstream feature generation."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import re
import sys
import threading
from pathlib import Path
from time import sleep
from typing import Iterable, List, Optional
from urllib.parse import urljoin
from xml.etree import ElementTree

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests import Response

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_pipelines.news_features.config import DEFAULT_MARKET_TIMEZONE, get_default_config
from research_pipelines.news_features.io_utils import (
    canonicalize_url,
    load_source_specs,
    make_article_id,
    read_jsonl,
    update_source_manifest,
    write_jsonl_records,
)

try:
    from job_status import JobStatusTracker
except ModuleNotFoundError:
    from data_tools.job_status import JobStatusTracker

from data_tools.news_runtime.fetch_news.cli_contract import options_from_namespace
from data_tools.news_runtime.fetch_news.discovery import (
    candidate_urls_from_sitemap_response as _runtime_candidate_urls_from_sitemap_response,
    candidate_urls_from_sitemaps as _runtime_candidate_urls_from_sitemaps,
    collect_listing_urls as _runtime_collect_listing_urls,
    collect_ticker_listing_urls as _runtime_collect_ticker_listing_urls,
    current_utc_timestamp as _runtime_current_utc_timestamp,
    parse_input_bound as _runtime_parse_input_bound,
    parse_ticker_argument as _runtime_parse_ticker_argument,
    parse_timestamp as _runtime_parse_timestamp,
    response_links as _runtime_response_links,
    select_sitemap_urls as _runtime_select_sitemap_urls,
    should_rescan_sitemap as _runtime_should_rescan_sitemap,
)
from data_tools.news_runtime.fetch_news.orchestrator import fetch_news as _runtime_fetch_news
from data_tools.news_runtime.fetch_news.persistence import (
    append_scanned_sitemap as _runtime_append_scanned_sitemap,
    append_seen_urls as _runtime_append_seen_urls,
    iter_existing_urls as _runtime_iter_existing_urls,
    iter_scanned_sitemaps as _runtime_iter_scanned_sitemaps,
    save_fetched_news as _runtime_save_fetched_news,
)


ARTICLE_URL_RE = re.compile(r"^https://cafef\.vn/.+-\d+\.chn$")
SITEMAP_RANGE_RE = re.compile(r"sitemaps-(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<start>\d{1,2})-(?P<end>\d{1,2})\.xml$")
CAFEF_URL_NUMERIC_SUFFIX_RE = re.compile(r"-(?P<digits>\d+)\.chn$")
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
UNPARSABLE_RAW_BUCKET = "unparsable"
MARKET_TIMEZONE = DEFAULT_MARKET_TIMEZONE


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
        return local_timestamp.tz_localize(MARKET_TIMEZONE).tz_convert("UTC")

    return None


def _parse_cafef_published_timestamp(published_text: str, url: str) -> tuple[pd.Timestamp | None, str]:
    text = str(published_text).strip()
    is_iso_like = bool(re.match(r"^\d{4}-\d{1,2}-\d{1,2}", text))
    parsed = pd.to_datetime(text, errors="coerce", dayfirst=not is_iso_like)
    if not pd.isna(parsed):
        timestamp = pd.Timestamp(parsed)
        if timestamp.tzinfo is None:
            return timestamp.tz_localize(MARKET_TIMEZONE).tz_convert("UTC"), "html"
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
    return _runtime_iter_existing_urls(
        source,
        config=get_default_config(),
        canonicalize_url=canonicalize_url,
        get_default_config=get_default_config,
        read_jsonl=read_jsonl,
    )


def _append_seen_urls(source: str, urls: List[str]) -> None:
    _runtime_append_seen_urls(
        source,
        urls,
        config=get_default_config(),
        canonicalize_url=canonicalize_url,
    )


def _iter_scanned_sitemaps(source: str) -> set[str]:
    return _runtime_iter_scanned_sitemaps(source, config=get_default_config())


def _append_scanned_sitemap(source: str, sitemap_url: str) -> None:
    _runtime_append_scanned_sitemap(source, sitemap_url, config=get_default_config())


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
    return _runtime_collect_listing_urls(source_spec, max_pages)


def _parse_ticker_argument(value: Optional[str]) -> List[str]:
    return _runtime_parse_ticker_argument(value)


def _collect_ticker_listing_urls(
    source_spec: dict[str, object],
    tickers: List[str],
    max_pages: int,
    default_max_pages: int,
) -> List[tuple[str, str]]:
    return _runtime_collect_ticker_listing_urls(source_spec, tickers, max_pages, default_max_pages)


def _parse_timestamp(value: Optional[str]) -> pd.Timestamp | None:
    return _runtime_parse_timestamp(value)


def _parse_input_bound(value: Optional[str], is_end: bool) -> pd.Timestamp | None:
    return _runtime_parse_input_bound(value, is_end)


def _current_utc_timestamp() -> pd.Timestamp:
    return _runtime_current_utc_timestamp()


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
    return _runtime_should_rescan_sitemap(
        sitemap_url,
        now_ts,
        recent_days,
        sitemap_range_re=SITEMAP_RANGE_RE,
    )


def _select_sitemap_urls(
    index_rows: List[dict[str, str]],
    start_ts: Optional[pd.Timestamp],
    end_ts: Optional[pd.Timestamp],
    max_documents: int,
) -> List[str]:
    return _runtime_select_sitemap_urls(
        index_rows,
        start_ts,
        end_ts,
        max_documents,
        sitemap_range_re=SITEMAP_RANGE_RE,
    )


def _candidate_urls_from_sitemaps(
    session: requests.Session,
    sitemap_urls: List[str],
    start_ts: Optional[pd.Timestamp],
    end_ts: Optional[pd.Timestamp],
    timeout: float,
    retry_attempts: int = 3,
    retry_backoff_seconds: float = 1.0,
) -> List[str]:
    return _runtime_candidate_urls_from_sitemaps(
        session,
        sitemap_urls,
        start_ts,
        end_ts,
        timeout,
        get_with_retries=_get_with_retries,
        candidate_urls_from_sitemap_response_fn=_candidate_urls_from_sitemap_response,
        retry_attempts=retry_attempts,
        retry_backoff_seconds=retry_backoff_seconds,
    )


def _response_links(response: Response, base_url: str) -> List[str]:
    return _runtime_response_links(
        response,
        base_url,
        extract_rss_article_links=extract_rss_article_links,
        extract_article_links=extract_article_links,
    )


def fetch_news(
    source: str,
    start_date: Optional[str],
    end_date: Optional[str],
    max_pages: int,
    delay: float,
    tickers: Optional[List[str]] = None,
    workers: int = 1,
    overwrite: bool = False,
    progress_callback: Optional[callable] = None,
) -> List[dict[str, object]]:
    config = get_default_config()
    specs = load_source_specs(config=config)
    source_spec = specs.get(source)
    if source_spec is None:
        raise ValueError(f"Unsupported source: {source}")
    return _runtime_fetch_news(
        source=source,
        start_date=start_date,
        end_date=end_date,
        max_pages=max_pages,
        delay=delay,
        tickers=tickers,
        workers=workers,
        overwrite=overwrite,
        progress_callback=progress_callback,
        config=config,
        source_spec=source_spec,
        build_http_session=_build_http_session,
        make_thread_session_getter=_make_thread_session_getter,
        fetch_article_result=_fetch_article_result,
        canonicalize_url=canonicalize_url,
        parse_sitemap_index=parse_sitemap_index,
        parse_input_bound=_parse_input_bound,
        iter_existing_urls=_iter_existing_urls,
        iter_scanned_sitemaps=_iter_scanned_sitemaps,
        append_scanned_sitemap=_append_scanned_sitemap,
        collect_ticker_listing_urls=_collect_ticker_listing_urls,
        collect_listing_urls=_collect_listing_urls,
        current_utc_timestamp=_current_utc_timestamp,
        select_sitemap_urls=_select_sitemap_urls,
        should_rescan_sitemap=_should_rescan_sitemap,
        response_links=_response_links,
        candidate_urls_from_sitemap_response=_candidate_urls_from_sitemap_response,
        get_with_retries=_get_with_retries,
        save_fetched_news=save_fetched_news,
        interrupted_exception_cls=NewsFetchInterrupted,
    )


def save_fetched_news(records: List[dict[str, object]], source: str) -> int:
    return _runtime_save_fetched_news(
        records,
        source,
        config=get_default_config(),
        canonicalize_url=canonicalize_url,
        iter_existing_urls_fn=_iter_existing_urls,
        append_seen_urls_fn=_append_seen_urls,
        update_source_manifest=update_source_manifest,
        write_jsonl_records=write_jsonl_records,
        unparsable_raw_bucket=UNPARSABLE_RAW_BUCKET,
    )


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
    options = options_from_namespace(args, parse_ticker_argument=_parse_ticker_argument)
    tracker = JobStatusTracker(
        "fetch_news",
        artifacts={
            "raw_dir": get_default_config().source_raw_dir(args.source),
            "source_manifest": get_default_config().source_manifest_path(args.source),
        },
    )
    def progress_callback(payload: dict[str, object]) -> None:
        tracker.write(
            status="running",
            phase=str(payload.get("phase", "fetch")),
            progress={
                "source": args.source,
                "tickers": options.tickers,
                "start_date": options.start_date,
                "end_date": options.end_date,
                "max_pages": options.max_pages,
                "workers": options.workers,
                **payload,
            },
        )
    try:
        tracker.write(
            status="running",
            phase="start",
            progress={
                "source": args.source,
                "tickers": options.tickers,
                "start_date": options.start_date,
                "end_date": options.end_date,
                "max_pages": options.max_pages,
                "workers": options.workers,
                "overwrite": options.overwrite,
                "processed_candidates": 0,
                "saved_records_count": 0,
            },
        )
        records = fetch_news(
            source=options.source,
            start_date=options.start_date,
            end_date=options.end_date,
            max_pages=options.max_pages,
            delay=options.delay,
            tickers=options.tickers,
            workers=options.workers,
            overwrite=options.overwrite,
            progress_callback=progress_callback,
        )
        tracker.write(
            status="complete",
            phase="complete",
            progress={
                "source": args.source,
                "tickers": options.tickers,
                "start_date": options.start_date,
                "end_date": options.end_date,
                "max_pages": options.max_pages,
                "workers": options.workers,
                "saved_records_count": len(records),
            },
        )
        print(f"Fetched {len(records)} raw articles into data/news/{args.source}/raw")
        return 0
    except NewsFetchInterrupted as exc:
        tracker.write(
            status="interrupted",
            phase="interrupted",
            progress={
                "source": args.source,
                "tickers": options.tickers,
                "processed_candidates": exc.processed_candidates,
                "total_candidates": exc.total_candidates,
                "saved_records_count": exc.saved_records_count,
            },
        )
        print("\nCancellation requested. Partial raw news records were already saved.", flush=True)
        print(
            f"Fetch cancelled after processing {exc.processed_candidates}/{exc.total_candidates} candidate article pages.",
            flush=True,
        )
        print(f"Saved {exc.saved_records_count} raw articles so far into {exc.output_dir}", flush=True)
        return 130
    except Exception as exc:
        tracker.write(
            status="failed",
            phase="failed",
            progress={
                "source": args.source,
                "tickers": options.tickers,
            },
            error={"message": str(exc), "type": exc.__class__.__name__},
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
