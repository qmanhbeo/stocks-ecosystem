import json

from research_pipelines.news_features.config import NewsFeaturesConfig
from research_pipelines.news_features.core.add_section_to_missing import add_section_to_missing


def test_add_section_to_missing_updates_only_rows_without_section(monkeypatch, tmp_path):
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

    raw_path = config.source_raw_dir("cafef") / "2026-03-11.jsonl"
    raw_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "article_id": "a1",
                        "source": "cafef",
                        "url": "https://cafef.vn/bai-viet-1.chn",
                        "title": "title",
                        "summary": "summary",
                        "body_text": "body",
                        "published_at": "2026-03-11T10:00:00Z",
                        "published_at_source": "html",
                        "fetched_at": "2026-03-11T10:00:05Z",
                        "author": None,
                        "section_name": None,
                        "tags": [],
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "article_id": "a2",
                        "source": "cafef",
                        "url": "https://cafef.vn/bai-viet-2.chn",
                        "title": "title",
                        "summary": "summary",
                        "body_text": "body",
                        "published_at": "2026-03-11T11:00:00Z",
                        "published_at_source": "html",
                        "fetched_at": "2026-03-11T11:00:05Z",
                        "author": None,
                        "section_name": "Doanh nghiệp",
                        "tags": [],
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "research_pipelines.news_features.core.add_section_to_missing.load_source_specs",
        lambda config=None: {
            "cafef": {
                "user_agent": "test-agent",
            }
        },
    )

    class FakeResponse:
        def __init__(self, text: str) -> None:
            self.text = text
            self.status_code = 200
            self.headers = {"Content-Type": "text/html"}

        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr(
        "research_pipelines.news_features.core.add_section_to_missing._get_with_retries",
        lambda **kwargs: FakeResponse(
            """
            <html><body>
              <p class="dateandcat">
                <span class="pdate">18-07-2022 - 17:50 PM</span>|
                <a data-role="cate-name" class="category-page__name cat" href="/thi-truong-chung-khoan.chn">Thị trường chứng khoán</a>
              </p>
            </body></html>
            """
        ),
    )

    summary = add_section_to_missing(source="cafef", config=config, workers=1)

    updated_rows = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()]
    assert summary["updated_rows"] == 1
    assert summary["files_updated"] == 1
    assert updated_rows[0]["section_name"] == "Thị trường chứng khoán"
    assert updated_rows[1]["section_name"] == "Doanh nghiệp"
