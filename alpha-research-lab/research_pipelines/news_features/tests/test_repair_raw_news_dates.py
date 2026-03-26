import json

from research_pipelines.news_features.config import NewsFeaturesConfig
from research_pipelines.news_features.core.repair_raw_news_dates import repair_raw_news_dates


def test_repair_raw_news_dates_rebuckets_rows(tmp_path):
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
                        "url": "https://cafef.vn/bai-viet-188260203154400176.chn",
                        "title": "title",
                        "summary": "summary",
                        "body_text": "body",
                        "published_at": "2026-03-11T13:29:00Z",
                        "fetched_at": "2026-03-11T13:29:00Z",
                        "author": None,
                        "tags": [],
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "article_id": "a2",
                        "source": "cafef",
                        "url": "https://cafef.vn/bai-viet-188260311202824689.chn",
                        "title": "title",
                        "summary": "summary",
                        "body_text": "body",
                        "published_at": "2026-03-11T13:29:00Z",
                        "fetched_at": "2026-03-11T13:29:00Z",
                        "author": None,
                        "tags": [],
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = repair_raw_news_dates(source="cafef", config=config)

    assert summary["article_count"] == 2
    assert summary["corrected_rows"] == 2
    assert (config.source_raw_dir("cafef") / "2026-02-03.jsonl").exists()
    assert (config.source_raw_dir("cafef") / "2026-03-11.jsonl").exists()

    repaired_old = (config.source_raw_dir("cafef") / "2026-02-03.jsonl").read_text(encoding="utf-8").splitlines()
    repaired_new = (config.source_raw_dir("cafef") / "2026-03-11.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(repaired_old) == 1
    assert len(repaired_new) == 1
    assert json.loads(repaired_old[0])["published_at"] == "2026-02-03T08:44:00Z"
    assert json.loads(repaired_new[0])["published_at"] == "2026-03-11T13:28:24Z"
    assert "raw_backup_rebucket_" in summary["backup_dir"]


def test_repair_raw_news_dates_keeps_unparsable_rows(tmp_path):
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
        json.dumps(
            {
                "article_id": "a1",
                "source": "cafef",
                "url": "https://cafef.vn/bai-viet-khong-co-ngay.chn",
                "title": "title",
                "summary": "summary",
                "body_text": "body",
                "published_at": None,
                "published_at_source": "unparsable",
                "fetched_at": "2026-03-11T13:29:00Z",
                "author": None,
                "tags": [],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    summary = repair_raw_news_dates(source="cafef", config=config)

    assert summary["article_count"] == 1
    unparsable_path = config.source_raw_dir("cafef") / "unparsable.jsonl"
    assert unparsable_path.exists()
    repaired = json.loads(unparsable_path.read_text(encoding="utf-8").splitlines()[0])
    assert repaired["published_at"] is None
    assert repaired["published_at_source"] == "unparsable"
