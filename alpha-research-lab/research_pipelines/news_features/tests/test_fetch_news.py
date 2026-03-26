import pandas as pd
import pytest
import requests

from research_pipelines.news_features.config import NewsFeaturesConfig
from vn_stock_rl.data_tools.fetch_news import (
    NewsArticleParseError,
    NewsFetchInterrupted,
    _fetch_article_result,
    _candidate_urls_from_sitemaps,
    _parse_ticker_argument,
    extract_cafef_section_name,
    extract_article_links,
    extract_rss_article_links,
    fetch_news,
    infer_cafef_url_timestamp,
    parse_sitemap_index,
    parse_url_sitemap,
    parse_cafef_article,
    save_fetched_news,
)


def test_extract_article_links_deduplicates_and_filters_non_articles():
    html = """
    <html><body>
      <a href="/abc/ma-bai-viet-1.chn">Article 1</a>
      <a href="https://cafef.vn/abc/ma-bai-viet-1.chn?utm=1">Article 1 duplicate</a>
      <a href="https://cafef.vn/abc/ma-bai-viet-2.chn">Article 2</a>
      <a href="https://cafef.vn/bat-dong-san.chn">Category page</a>
      <a href="https://example.com/not-cafef.chn">External</a>
      <a href="/khong-phai-bai-viet">Non article</a>
    </body></html>
    """

    links = extract_article_links(html, base_url="https://cafef.vn")
    assert links == [
        "https://cafef.vn/abc/ma-bai-viet-1.chn",
        "https://cafef.vn/abc/ma-bai-viet-2.chn",
    ]


def test_parse_ticker_argument_accepts_commas_and_spaces():
    assert _parse_ticker_argument("ACB,VNM HPG") == ["ACB", "VNM", "HPG"]


def test_extract_rss_article_links_reads_item_links():
    xml = """<?xml version="1.0" encoding="utf-8"?>
    <rss>
      <channel>
        <item><link>https://cafef.vn/abc/bai-viet-1.chn</link></item>
        <item><link>/abc/bai-viet-2.chn?utm=1</link></item>
        <item><link>https://example.com/ignore.chn</link></item>
      </channel>
    </rss>
    """

    links = extract_rss_article_links(xml, base_url="https://cafef.vn")
    assert links == [
        "https://cafef.vn/abc/bai-viet-1.chn",
        "https://cafef.vn/abc/bai-viet-2.chn",
    ]


def test_parse_cafef_article_extracts_expected_fields():
    html = """
    <html><body>
      <h1>ACB va HPG tang truong manh</h1>
      <div class="sapo">Tom tat ngan</div>
      <div class="detail-content">Noi dung day du cua bai viet.</div>
      <p class="dateandcat"><span class="pdate">2026-03-10 09:15</span>|<a data-role="cate-name" class="category-page__name cat" href="/thi-truong-chung-khoan.chn">Thi truong chung khoan</a></p>
      <div class="pdate">2026-03-10 09:15</div>
      <div class="author">Cafef Reporter</div>
      <div class="tag-list"><a>ngan hang</a><a>chung khoan</a></div>
    </body></html>
    """

    record = parse_cafef_article(html, "https://cafef.vn/abc/bai-viet.chn")
    assert record is not None
    assert record["source"] == "cafef"
    assert record["url"] == "https://cafef.vn/abc/bai-viet.chn"
    assert record["title"] == "ACB va HPG tang truong manh"
    assert record["summary"] == "Tom tat ngan"
    assert "Noi dung day du" in record["body_text"]
    assert record["published_at"] == "2026-03-10T02:15:00Z"
    assert record["published_at_source"] == "html"
    assert record["author"] == "Cafef Reporter"
    assert record["section_name"] == "Thi truong chung khoan"
    assert record["tags"] == ["ngan hang", "chung khoan"]


def test_extract_cafef_section_name_reads_category_anchor():
    html = """
    <html><body>
      <div class="sharemxh topshare">
        <p class="dateandcat">
          <span class="pdate">18-07-2022 - 17:50 PM</span>|
          <a data-role="cate-name" class="category-page__name cat" href="/doanh-nghiep.chn" title="Doanh nghiệp">Doanh nghiệp</a>
        </p>
      </div>
    </body></html>
    """

    assert extract_cafef_section_name(html) == "Doanh nghiệp"


def test_parse_cafef_article_falls_back_to_url_timestamp_when_selector_missing():
    html = """
    <html><body>
      <h1>ACB tang truong</h1>
      <div class="detail-content">Noi dung day du cua bai viet.</div>
    </body></html>
    """

    record = parse_cafef_article(html, "https://cafef.vn/abc/bai-viet-188260203154400176.chn")
    assert record is not None
    assert record["published_at"] == "2026-02-03T08:44:00Z"
    assert record["published_at_source"] == "url"


def test_parse_cafef_article_falls_back_to_four_digit_year_url_timestamp_when_selector_missing():
    html = """
    <html><body>
      <h1>ACB tang truong</h1>
      <div class="detail-content">Noi dung day du cua bai viet.</div>
    </body></html>
    """

    record = parse_cafef_article(html, "https://cafef.vn/abc/bai-viet-20230228164806428.chn")
    assert record is not None
    assert record["published_at"] == "2023-02-28T09:48:06Z"
    assert record["published_at_source"] == "url"


def test_parse_cafef_article_marks_unparsable_timestamp_without_dropping_article():
    html = """
    <html><body>
      <h1>ACB tang truong</h1>
      <div class="detail-content">Noi dung day du cua bai viet.</div>
    </body></html>
    """

    record = parse_cafef_article(html, "https://cafef.vn/abc/bai-viet-khong-co-ngay.chn")
    assert record is not None
    assert record["published_at"] is None
    assert record["published_at_source"] == "unparsable"


def test_fetch_article_result_raises_parse_error_with_article_url(monkeypatch):
    article_url = "https://cafef.vn/abc/bai-viet-loi-20231328164806428.chn"

    class FakeResponse:
        def __init__(self) -> None:
            self.text = "<html></html>"
            self.status_code = 200
            self.headers = {"Content-Type": "text/html"}

        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr(
        "vn_stock_rl.data_tools.fetch_news._get_with_retries",
        lambda **kwargs: FakeResponse(),
    )

    def _raise_parse_failure(html: str, url: str):
        raise ValueError("month must be in 1..12")

    monkeypatch.setattr(
        "vn_stock_rl.data_tools.fetch_news.parse_cafef_article",
        _raise_parse_failure,
    )

    with pytest.raises(NewsArticleParseError) as exc_info:
        _fetch_article_result(
            article_url=article_url,
            start_ts=None,
            end_ts=None,
            timeout=5.0,
            retry_attempts=1,
            retry_backoff_seconds=0.0,
            get_session=lambda: object(),
        )

    assert exc_info.value.article_url == article_url
    assert article_url in str(exc_info.value)
    assert "month must be in 1..12" in str(exc_info.value)


def test_infer_cafef_url_timestamp_returns_none_for_invalid_numeric_suffix():
    inferred = infer_cafef_url_timestamp("https://cafef.vn/abc/bai-viet-20231328164806428.chn")

    assert inferred is None


def test_parse_sitemap_index_and_url_sitemap():
    sitemap_index_xml = """<?xml version="1.0" encoding="utf-8"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap>
        <loc>https://cafef.vn/sitemaps/sitemaps-2026-3-6-10.xml</loc>
        <lastmod>2026-03-10T23:59:59+07:00</lastmod>
      </sitemap>
    </sitemapindex>
    """
    url_sitemap_xml = """<?xml version="1.0" encoding="utf-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url>
        <loc>https://cafef.vn/abc/bai-viet-1-188260310143703641.chn</loc>
        <lastmod>2026-03-10T15:50:10+07:00</lastmod>
      </url>
    </urlset>
    """

    index_rows = parse_sitemap_index(sitemap_index_xml)
    url_rows = parse_url_sitemap(url_sitemap_xml)
    assert index_rows == [
        {
            "loc": "https://cafef.vn/sitemaps/sitemaps-2026-3-6-10.xml",
            "lastmod": "2026-03-10T23:59:59+07:00",
        }
    ]
    assert url_rows == [
        {
            "loc": "https://cafef.vn/abc/bai-viet-1-188260310143703641.chn",
            "lastmod": "2026-03-10T15:50:10+07:00",
        }
    ]


def test_candidate_urls_from_sitemaps_logs_progress(capsys):
    sitemap_xml = """<?xml version="1.0" encoding="utf-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url>
        <loc>https://cafef.vn/abc/bai-viet-1-188260310143703641.chn</loc>
        <lastmod>2026-03-10T15:50:10+07:00</lastmod>
      </url>
    </urlset>
    """

    class FakeResponse:
        def __init__(self, text: str) -> None:
            self.text = text
            self.status_code = 200
            self.headers = {"Content-Type": "application/xml"}

        def raise_for_status(self) -> None:
            return None

    class FakeSession:
        def get(self, url: str, timeout: float):
            return FakeResponse(sitemap_xml.replace("1-188260310143703641", url.rsplit("-", 1)[-1].replace(".xml", "")))

    urls = _candidate_urls_from_sitemaps(
        session=FakeSession(),
        sitemap_urls=[
            "https://cafef.vn/sitemaps/sitemaps-2026-3-1-5.xml",
            "https://cafef.vn/sitemaps/sitemaps-2026-3-6-10.xml",
            "https://cafef.vn/sitemaps/sitemaps-2026-3-11-15.xml",
        ],
        start_ts=None,
        end_ts=None,
        timeout=1.0,
    )

    captured = capsys.readouterr().out
    assert "Scanned 1/3 sitemap documents" in captured
    assert "Scanned 3/3 sitemap documents" in captured
    assert len(urls) == 3


def test_candidate_urls_from_sitemaps_skips_bad_gateway_after_retries(capsys):
    sitemap_xml = """<?xml version="1.0" encoding="utf-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url>
        <loc>https://cafef.vn/abc/bai-viet-1-188260310143703641.chn</loc>
        <lastmod>2026-03-10T15:50:10+07:00</lastmod>
      </url>
    </urlset>
    """

    class FakeResponse:
        def __init__(self, status_code: int = 200, text: str = sitemap_xml) -> None:
            self.text = text
            self.status_code = status_code
            self.headers = {"Content-Type": "application/xml"}

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise requests.HTTPError(f"{self.status_code} error", response=self)

    class FakeSession:
        def get(self, url: str, timeout: float):
            if url.endswith("broken.xml"):
                return FakeResponse(status_code=502)
            return FakeResponse()

    urls = _candidate_urls_from_sitemaps(
        session=FakeSession(),
        sitemap_urls=[
            "https://cafef.vn/sitemaps/broken.xml",
            "https://cafef.vn/sitemaps/sitemaps-2026-3-11-15.xml",
        ],
        start_ts=None,
        end_ts=None,
        timeout=1.0,
        retry_attempts=2,
        retry_backoff_seconds=0.0,
    )

    captured = capsys.readouterr().out
    assert "Sitemap request got HTTP 502 on attempt 1/2" in captured
    assert "Skipping failed sitemap URL after retries" in captured
    assert len(urls) == 1


def test_fetch_news_interrupt_preserves_partial_records(monkeypatch, tmp_path):
    root = tmp_path
    package_root = root / "sub_pipelines" / "news_features"
    artifacts_dir = package_root / "artifacts"
    config = NewsFeaturesConfig(
        repo_root=root,
        package_root=package_root,
        raw_news_dir=root / "data" / "news",
        raw_stock_dir=root / "data" / "stock",
        artifacts_dir=artifacts_dir,
        configs_dir=artifacts_dir / "configs",
        normalized_dir=artifacts_dir / "normalized",
        tagged_dir=artifacts_dir / "tagged",
        datasets_dir=artifacts_dir / "datasets",
        predictions_dir=artifacts_dir / "predictions",
        manifest_path=artifacts_dir / "manifest.json",
    )
    config.ensure_directories()

    monkeypatch.setattr("vn_stock_rl.data_tools.fetch_news.get_default_config", lambda: config)
    monkeypatch.setattr(
        "vn_stock_rl.data_tools.fetch_news.load_source_specs",
        lambda config=None: {
            "cafef": {
                "base_url": "https://cafef.vn",
                "sitemap_index_url": "https://cafef.vn/sitemap.xml",
                "user_agent": "test-agent",
            }
        },
    )
    monkeypatch.setattr(
        "vn_stock_rl.data_tools.fetch_news.parse_sitemap_index",
        lambda xml_text: [{"loc": "https://cafef.vn/sitemaps/sitemaps-2026-3-11-15.xml", "lastmod": "2026-03-11T19:00:00+07:00"}],
    )
    monkeypatch.setattr(
        "vn_stock_rl.data_tools.fetch_news._select_sitemap_urls",
        lambda index_rows, start_ts, end_ts, max_documents: ["https://cafef.vn/sitemaps/sitemaps-2026-3-11-15.xml"],
    )
    monkeypatch.setattr(
        "vn_stock_rl.data_tools.fetch_news._candidate_urls_from_sitemap_response",
        lambda sitemap_url, response, start_ts, end_ts: [
            "https://cafef.vn/abc/bai-viet-1-188260310143703641.chn",
            "https://cafef.vn/abc/bai-viet-2-188260310143703642.chn",
        ],
    )

    class FakeResponse:
        def __init__(self, text: str = "") -> None:
            self.text = text
            self.status_code = 200
            self.headers = {"Content-Type": "text/html"}

        def raise_for_status(self) -> None:
            return None

    class FakeSession:
        def __init__(self) -> None:
            self.headers = {}
            self.calls = 0

        def get(self, url: str, timeout: float):
            self.calls += 1
            if url.endswith("642.chn"):
                raise KeyboardInterrupt
            return FakeResponse("<html></html>")

    monkeypatch.setattr("vn_stock_rl.data_tools.fetch_news.requests.Session", FakeSession)
    monkeypatch.setattr(
        "vn_stock_rl.data_tools.fetch_news.parse_cafef_article",
        lambda html, url: {
            "article_id": "a1",
            "source": "cafef",
            "url": url,
            "title": "title",
            "summary": "summary",
            "body_text": "body",
            "published_at": "2026-03-11T10:00:00Z",
            "fetched_at": "2026-03-11T10:00:05Z",
            "author": None,
            "tags": [],
        },
    )

    try:
        fetch_news(
            source="cafef",
            start_date="2026-03-11",
            end_date="2026-03-11",
            max_pages=1,
            delay=0.0,
            overwrite=False,
        )
    except NewsFetchInterrupted as exc:
        assert len(exc.records) == 1
        assert exc.processed_candidates == 2
        assert exc.total_candidates == 2
        assert exc.saved_records_count == 1
        assert exc.output_dir.endswith(str(root / "data" / "news" / "cafef" / "raw"))
    else:
        raise AssertionError("Expected fetch interruption to preserve partial records")


def test_fetch_news_skips_missing_article_urls(monkeypatch, tmp_path):
    root = tmp_path
    package_root = root / "sub_pipelines" / "news_features"
    artifacts_dir = package_root / "artifacts"
    config = NewsFeaturesConfig(
        repo_root=root,
        package_root=package_root,
        raw_news_dir=root / "data" / "news",
        raw_stock_dir=root / "data" / "stock",
        artifacts_dir=artifacts_dir,
        configs_dir=artifacts_dir / "configs",
        normalized_dir=artifacts_dir / "normalized",
        tagged_dir=artifacts_dir / "tagged",
        datasets_dir=artifacts_dir / "datasets",
        predictions_dir=artifacts_dir / "predictions",
        manifest_path=artifacts_dir / "manifest.json",
    )
    config.ensure_directories()

    monkeypatch.setattr("vn_stock_rl.data_tools.fetch_news.get_default_config", lambda: config)
    monkeypatch.setattr(
        "vn_stock_rl.data_tools.fetch_news.load_source_specs",
        lambda config=None: {
            "cafef": {
                "base_url": "https://cafef.vn",
                "sitemap_index_url": "https://cafef.vn/sitemap.xml",
                "user_agent": "test-agent",
            }
        },
    )
    monkeypatch.setattr(
        "vn_stock_rl.data_tools.fetch_news.parse_sitemap_index",
        lambda xml_text: [{"loc": "https://cafef.vn/sitemaps/sitemaps-2026-3-11-15.xml", "lastmod": "2026-03-11T19:00:00+07:00"}],
    )
    monkeypatch.setattr(
        "vn_stock_rl.data_tools.fetch_news._select_sitemap_urls",
        lambda index_rows, start_ts, end_ts, max_documents: ["https://cafef.vn/sitemaps/sitemaps-2026-3-11-15.xml"],
    )
    monkeypatch.setattr(
        "vn_stock_rl.data_tools.fetch_news._candidate_urls_from_sitemap_response",
        lambda sitemap_url, response, start_ts, end_ts: [
            "https://cafef.vn/abc/bai-viet-1-188260310143703641.chn",
            "https://cafef.vn/abc/bai-viet-missing-188260310143703642.chn",
            "https://cafef.vn/abc/bai-viet-2-188260310143703643.chn",
        ],
    )

    class FakeResponse:
        def __init__(self, status_code: int = 200, text: str = "") -> None:
            self.text = text
            self.status_code = status_code
            self.headers = {"Content-Type": "text/html"}

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise requests.HTTPError(f"{self.status_code} error", response=self)

    class FakeSession:
        def __init__(self) -> None:
            self.headers = {}

        def get(self, url: str, timeout: float):
            if url.endswith("642.chn"):
                return FakeResponse(status_code=404)
            return FakeResponse(text="<html></html>")

    monkeypatch.setattr("vn_stock_rl.data_tools.fetch_news.requests.Session", FakeSession)
    monkeypatch.setattr(
        "vn_stock_rl.data_tools.fetch_news.parse_cafef_article",
        lambda html, url: {
            "article_id": url.rsplit("/", 1)[-1],
            "source": "cafef",
            "url": url,
            "title": "title",
            "summary": "summary",
            "body_text": "body",
            "published_at": "2026-03-11T10:00:00Z",
            "fetched_at": "2026-03-11T10:00:05Z",
            "author": None,
            "tags": [],
        },
    )

    records = fetch_news(
        source="cafef",
        start_date="2026-03-11",
        end_date="2026-03-11",
        max_pages=1,
        delay=0.0,
        overwrite=False,
    )
    assert len(records) == 2
    assert all("missing" not in record["url"] for record in records)


def test_save_fetched_news_creates_seen_url_index_and_dedupes(monkeypatch, tmp_path):
    root = tmp_path
    package_root = root / "sub_pipelines" / "news_features"
    artifacts_dir = package_root / "artifacts"
    config = NewsFeaturesConfig(
        repo_root=root,
        package_root=package_root,
        raw_news_dir=root / "data" / "news",
        raw_stock_dir=root / "data" / "stock",
        artifacts_dir=artifacts_dir,
        configs_dir=artifacts_dir / "configs",
        normalized_dir=artifacts_dir / "normalized",
        tagged_dir=artifacts_dir / "tagged",
        datasets_dir=artifacts_dir / "datasets",
        predictions_dir=artifacts_dir / "predictions",
        manifest_path=artifacts_dir / "manifest.json",
    )
    config.ensure_directories()
    monkeypatch.setattr("vn_stock_rl.data_tools.fetch_news.get_default_config", lambda: config)

    rows = [
        {
            "article_id": "a1",
            "source": "cafef",
            "url": "https://cafef.vn/abc/bai-viet-1.chn?utm=1",
            "title": "t1",
            "summary": "s1",
            "body_text": "b1",
            "published_at": "2026-03-11T10:00:00Z",
            "fetched_at": "2026-03-11T10:00:05Z",
            "author": None,
            "tags": [],
        },
        {
            "article_id": "a1-dup",
            "source": "cafef",
            "url": "https://cafef.vn/abc/bai-viet-1.chn",
            "title": "t1",
            "summary": "s1",
            "body_text": "b1",
            "published_at": "2026-03-11T10:00:00Z",
            "fetched_at": "2026-03-11T10:00:05Z",
            "author": None,
            "tags": [],
        },
    ]

    first_saved = save_fetched_news(rows, source="cafef")
    second_saved = save_fetched_news(rows, source="cafef")
    assert first_saved == 1
    assert second_saved == 0

    raw_file = config.source_raw_dir("cafef") / "2026-03-11.jsonl"
    assert raw_file.exists()
    lines = raw_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1

    seen_urls = config.source_seen_urls_path("cafef").read_text(encoding="utf-8").splitlines()
    assert seen_urls == ["https://cafef.vn/abc/bai-viet-1.chn"]


def test_save_fetched_news_persists_unparsable_records(monkeypatch, tmp_path):
    root = tmp_path
    package_root = root / "sub_pipelines" / "news_features"
    artifacts_dir = package_root / "artifacts"
    config = NewsFeaturesConfig(
        repo_root=root,
        package_root=package_root,
        raw_news_dir=root / "data" / "news",
        raw_stock_dir=root / "data" / "stock",
        artifacts_dir=artifacts_dir,
        configs_dir=artifacts_dir / "configs",
        normalized_dir=artifacts_dir / "normalized",
        tagged_dir=artifacts_dir / "tagged",
        datasets_dir=artifacts_dir / "datasets",
        predictions_dir=artifacts_dir / "predictions",
        manifest_path=artifacts_dir / "manifest.json",
    )
    config.ensure_directories()
    monkeypatch.setattr("vn_stock_rl.data_tools.fetch_news.get_default_config", lambda: config)

    rows = [
        {
            "article_id": "a1",
            "source": "cafef",
            "url": "https://cafef.vn/abc/bai-viet-khong-co-ngay.chn",
            "title": "t1",
            "summary": "s1",
            "body_text": "b1",
            "published_at": None,
            "published_at_source": "unparsable",
            "fetched_at": "2026-03-11T10:00:05Z",
            "author": None,
            "tags": [],
        },
    ]

    saved = save_fetched_news(rows, source="cafef")

    assert saved == 1
    raw_file = config.source_raw_dir("cafef") / "unparsable.jsonl"
    assert raw_file.exists()
    lines = raw_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert "\"published_at\": null" in lines[0]
    assert "\"published_at_source\": \"unparsable\"" in lines[0]


def test_fetch_news_skips_previously_scanned_sitemaps(monkeypatch, tmp_path):
    root = tmp_path
    package_root = root / "sub_pipelines" / "news_features"
    artifacts_dir = package_root / "artifacts"
    config = NewsFeaturesConfig(
        repo_root=root,
        package_root=package_root,
        raw_news_dir=root / "data" / "news",
        raw_stock_dir=root / "data" / "stock",
        artifacts_dir=artifacts_dir,
        configs_dir=artifacts_dir / "configs",
        normalized_dir=artifacts_dir / "normalized",
        tagged_dir=artifacts_dir / "tagged",
        datasets_dir=artifacts_dir / "datasets",
        predictions_dir=artifacts_dir / "predictions",
        manifest_path=artifacts_dir / "manifest.json",
    )
    config.ensure_directories()
    config.source_scanned_sitemaps_path("cafef").write_text(
        "https://cafef.vn/sitemaps/sitemaps-2026-2-1-5.xml\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("vn_stock_rl.data_tools.fetch_news.get_default_config", lambda: config)
    monkeypatch.setattr(
        "vn_stock_rl.data_tools.fetch_news._current_utc_timestamp",
        lambda: pd.Timestamp("2026-03-11T00:00:00Z"),
    )
    monkeypatch.setattr(
        "vn_stock_rl.data_tools.fetch_news.load_source_specs",
        lambda config=None: {
            "cafef": {
                "base_url": "https://cafef.vn",
                "sitemap_index_url": "https://cafef.vn/sitemap.xml",
                "user_agent": "test-agent",
            }
        },
    )
    monkeypatch.setattr(
        "vn_stock_rl.data_tools.fetch_news.parse_sitemap_index",
        lambda xml_text: [
            {"loc": "https://cafef.vn/sitemaps/sitemaps-2026-2-1-5.xml", "lastmod": "2026-02-05T19:00:00+07:00"},
            {"loc": "https://cafef.vn/sitemaps/sitemaps-2026-3-6-10.xml", "lastmod": "2026-03-10T19:00:00+07:00"},
        ],
    )
    monkeypatch.setattr(
        "vn_stock_rl.data_tools.fetch_news._select_sitemap_urls",
        lambda index_rows, start_ts, end_ts, max_documents: [row["loc"] for row in index_rows],
    )
    monkeypatch.setattr(
        "vn_stock_rl.data_tools.fetch_news._candidate_urls_from_sitemap_response",
        lambda sitemap_url, response, start_ts, end_ts: ["https://cafef.vn/abc/bai-viet-1-188260310143703641.chn"],
    )
    monkeypatch.setattr(
        "vn_stock_rl.data_tools.fetch_news.parse_cafef_article",
        lambda html, url: {
            "article_id": "a1",
            "source": "cafef",
            "url": url,
            "title": "title",
            "summary": "summary",
            "body_text": "body",
            "published_at": "2026-03-11T10:00:00Z",
            "fetched_at": "2026-03-11T10:00:05Z",
            "author": None,
            "tags": [],
        },
    )

    requested_urls = []

    class FakeResponse:
        def __init__(self, text: str = "<xml/>") -> None:
            self.text = text
            self.status_code = 200
            self.headers = {"Content-Type": "application/xml"}

        def raise_for_status(self) -> None:
            return None

    class FakeSession:
        def __init__(self) -> None:
            self.headers = {}

        def get(self, url: str, timeout: float):
            requested_urls.append(url)
            if url.endswith(".chn"):
                return FakeResponse("<html></html>")
            return FakeResponse("<?xml version='1.0'?><xml/>")

    monkeypatch.setattr("vn_stock_rl.data_tools.fetch_news.requests.Session", FakeSession)

    records = fetch_news(
        source="cafef",
        start_date="2026-03-11",
        end_date="2026-03-11",
        max_pages=2,
        delay=0.0,
        overwrite=False,
    )

    assert len(records) == 1
    assert "https://cafef.vn/sitemaps/sitemaps-2026-2-1-5.xml" not in requested_urls
    scanned_sitemaps = config.source_scanned_sitemaps_path("cafef").read_text(encoding="utf-8").splitlines()
    assert scanned_sitemaps == [
        "https://cafef.vn/sitemaps/sitemaps-2026-2-1-5.xml",
        "https://cafef.vn/sitemaps/sitemaps-2026-3-6-10.xml",
    ]


def test_fetch_news_rechecks_recent_scanned_sitemaps(monkeypatch, tmp_path):
    root = tmp_path
    package_root = root / "sub_pipelines" / "news_features"
    artifacts_dir = package_root / "artifacts"
    config = NewsFeaturesConfig(
        repo_root=root,
        package_root=package_root,
        raw_news_dir=root / "data" / "news",
        raw_stock_dir=root / "data" / "stock",
        artifacts_dir=artifacts_dir,
        configs_dir=artifacts_dir / "configs",
        normalized_dir=artifacts_dir / "normalized",
        tagged_dir=artifacts_dir / "tagged",
        datasets_dir=artifacts_dir / "datasets",
        predictions_dir=artifacts_dir / "predictions",
        manifest_path=artifacts_dir / "manifest.json",
    )
    config.ensure_directories()
    config.source_scanned_sitemaps_path("cafef").write_text(
        "https://cafef.vn/sitemaps/sitemaps-2026-3-6-10.xml\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("vn_stock_rl.data_tools.fetch_news.get_default_config", lambda: config)
    monkeypatch.setattr(
        "vn_stock_rl.data_tools.fetch_news._current_utc_timestamp",
        lambda: pd.Timestamp("2026-03-11T00:00:00Z"),
    )
    monkeypatch.setattr(
        "vn_stock_rl.data_tools.fetch_news.load_source_specs",
        lambda config=None: {
            "cafef": {
                "base_url": "https://cafef.vn",
                "sitemap_index_url": "https://cafef.vn/sitemap.xml",
                "user_agent": "test-agent",
            }
        },
    )
    monkeypatch.setattr(
        "vn_stock_rl.data_tools.fetch_news.parse_sitemap_index",
        lambda xml_text: [
            {"loc": "https://cafef.vn/sitemaps/sitemaps-2026-3-6-10.xml", "lastmod": "2026-03-10T19:00:00+07:00"},
        ],
    )
    monkeypatch.setattr(
        "vn_stock_rl.data_tools.fetch_news._select_sitemap_urls",
        lambda index_rows, start_ts, end_ts, max_documents: [row["loc"] for row in index_rows],
    )
    monkeypatch.setattr(
        "vn_stock_rl.data_tools.fetch_news._candidate_urls_from_sitemap_response",
        lambda sitemap_url, response, start_ts, end_ts: ["https://cafef.vn/abc/bai-viet-1-188260310143703641.chn"],
    )
    monkeypatch.setattr(
        "vn_stock_rl.data_tools.fetch_news.parse_cafef_article",
        lambda html, url: {
            "article_id": "a1",
            "source": "cafef",
            "url": url,
            "title": "title",
            "summary": "summary",
            "body_text": "body",
            "published_at": "2026-03-11T10:00:00Z",
            "fetched_at": "2026-03-11T10:00:05Z",
            "author": None,
            "tags": [],
        },
    )

    requested_urls = []

    class FakeResponse:
        def __init__(self, text: str = "<xml/>") -> None:
            self.text = text
            self.status_code = 200
            self.headers = {"Content-Type": "application/xml"}

        def raise_for_status(self) -> None:
            return None

    class FakeSession:
        def __init__(self) -> None:
            self.headers = {}

        def get(self, url: str, timeout: float):
            requested_urls.append(url)
            if url.endswith(".chn"):
                return FakeResponse("<html></html>")
            return FakeResponse("<?xml version='1.0'?><xml/>")

    monkeypatch.setattr("vn_stock_rl.data_tools.fetch_news.requests.Session", FakeSession)

    records = fetch_news(
        source="cafef",
        start_date="2026-03-11",
        end_date="2026-03-11",
        max_pages=1,
        delay=0.0,
        overwrite=False,
    )

    assert len(records) == 1
    assert "https://cafef.vn/sitemaps/sitemaps-2026-3-6-10.xml" in requested_urls
    scanned_sitemaps = config.source_scanned_sitemaps_path("cafef").read_text(encoding="utf-8").splitlines()
    assert scanned_sitemaps == ["https://cafef.vn/sitemaps/sitemaps-2026-3-6-10.xml"]


def test_fetch_news_ticker_mode_uses_ticker_listing_pages(monkeypatch, tmp_path):
    root = tmp_path
    package_root = root / "sub_pipelines" / "news_features"
    artifacts_dir = package_root / "artifacts"
    config = NewsFeaturesConfig(
        repo_root=root,
        package_root=package_root,
        raw_news_dir=root / "data" / "news",
        raw_stock_dir=root / "data" / "stock",
        artifacts_dir=artifacts_dir,
        configs_dir=artifacts_dir / "configs",
        normalized_dir=artifacts_dir / "normalized",
        tagged_dir=artifacts_dir / "tagged",
        datasets_dir=artifacts_dir / "datasets",
        predictions_dir=artifacts_dir / "predictions",
        manifest_path=artifacts_dir / "manifest.json",
    )
    config.ensure_directories()

    monkeypatch.setattr("vn_stock_rl.data_tools.fetch_news.get_default_config", lambda: config)
    monkeypatch.setattr(
        "vn_stock_rl.data_tools.fetch_news.load_source_specs",
        lambda config=None: {
            "cafef": {
                "base_url": "https://cafef.vn",
                "ticker_listing_url_template": "https://cafef.vn/{ticker_lower}/trang-{page}.html",
                "user_agent": "test-agent",
            }
        },
    )
    monkeypatch.setattr(
        "vn_stock_rl.data_tools.fetch_news.parse_cafef_article",
        lambda html, url: {
            "article_id": url.rsplit("/", 1)[-1],
            "source": "cafef",
            "url": url,
            "title": "title",
            "summary": "summary",
            "body_text": "body",
            "published_at": "2026-03-11T10:00:00Z",
            "fetched_at": "2026-03-11T10:00:05Z",
            "author": None,
            "tags": [],
        },
    )

    requested_urls = []

    class FakeResponse:
        def __init__(self, text: str, content_type: str = "text/html", status_code: int = 200) -> None:
            self.text = text
            self.status_code = status_code
            self.headers = {"Content-Type": content_type}

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise requests.HTTPError(f"{self.status_code} error", response=self)

    class FakeSession:
        def __init__(self) -> None:
            self.headers = {}

        def get(self, url: str, timeout: float):
            requested_urls.append(url)
            if url.endswith(".chn"):
                return FakeResponse("<html></html>")
            ticker = "ACB" if "/acb/" in url else "HPG"
            html = f"""
            <html><body>
              <a href="https://cafef.vn/{ticker.lower()}/bai-viet-{ticker.lower()}-1-188260310143703641.chn">Article 1</a>
            </body></html>
            """
            return FakeResponse(html)

    monkeypatch.setattr("vn_stock_rl.data_tools.fetch_news.requests.Session", FakeSession)

    records = fetch_news(
        source="cafef",
        start_date="2026-03-11",
        end_date="2026-03-11",
        max_pages=2,
        delay=0.0,
        tickers=["ACB", "HPG"],
        workers=2,
        overwrite=False,
    )

    assert len(records) == 2
    assert "https://cafef.vn/acb/trang-1.html" in requested_urls
    assert "https://cafef.vn/acb/trang-2.html" in requested_urls
    assert "https://cafef.vn/hpg/trang-1.html" in requested_urls
    assert "https://cafef.vn/hpg/trang-2.html" in requested_urls
    assert not any(url.endswith("sitemap.xml") for url in requested_urls)
