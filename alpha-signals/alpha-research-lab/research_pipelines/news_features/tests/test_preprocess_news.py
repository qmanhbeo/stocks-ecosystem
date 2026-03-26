import pandas as pd

from research_pipelines.news_features.core.preprocess_news import preprocess_news_dataframe


def test_preprocess_news_drops_duplicates_and_empty_rows():
    raw_df = pd.DataFrame(
        [
            {
                "article_id": "a1",
                "source": "cafef",
                "url": "https://cafef.vn/a1.chn",
                "title": "  ACB  tang truong ",
                "summary": " Tom tat ",
                "body_text": " Noi   dung   day du ",
                "published_at": "2026-03-10T09:00:00Z",
                "section_name": "  Doanh nghiep  ",
            },
            {
                "article_id": "a1",
                "source": "cafef",
                "url": "https://cafef.vn/a1.chn",
                "title": "duplicate",
                "summary": "",
                "body_text": "duplicate",
                "published_at": "2026-03-10T10:00:00Z",
            },
            {
                "article_id": "a2",
                "source": "cafef",
                "url": "https://cafef.vn/a2.chn",
                "title": "",
                "summary": "",
                "body_text": "co body nhung khong co title",
                "published_at": "2026-03-10T11:00:00Z",
            },
        ]
    )

    normalized = preprocess_news_dataframe(raw_df)
    assert normalized["article_id"].tolist() == ["a1"]
    assert normalized.loc[0, "clean_title"] == "ACB tang truong"
    assert normalized.loc[0, "clean_body_text"] == "Noi dung day du"
    assert normalized.loc[0, "date"] == "2026-03-10"
    assert normalized.loc[0, "published_at"] == "2026-03-10T16:00:00+07:00"
    assert normalized.loc[0, "section_name"] == "Doanh nghiep"


def test_preprocess_news_uses_hanoi_local_date_for_rollover():
    raw_df = pd.DataFrame(
        [
            {
                "article_id": "late-night",
                "source": "cafef",
                "url": "https://cafef.vn/late-night.chn",
                "title": "Tin toi",
                "summary": "Tom tat",
                "body_text": "Noi dung ban dem",
                "published_at": "2026-03-10T20:30:00Z",
            },
        ]
    )

    normalized = preprocess_news_dataframe(raw_df)
    assert normalized.loc[0, "published_at"] == "2026-03-11T03:30:00+07:00"
    assert normalized.loc[0, "date"] == "2026-03-11"


def test_preprocess_news_drops_rows_without_parseable_timestamp():
    raw_df = pd.DataFrame(
        [
            {
                "article_id": "valid",
                "source": "cafef",
                "url": "https://cafef.vn/valid.chn",
                "title": "Tin hop le",
                "summary": "Tom tat",
                "body_text": "Noi dung",
                "published_at": "2026-03-10T20:30:00Z",
            },
            {
                "article_id": "unparsable",
                "source": "cafef",
                "url": "https://cafef.vn/unparsable.chn",
                "title": "Van giu bai viet",
                "summary": "Tom tat",
                "body_text": "Noi dung",
                "published_at": None,
                "published_at_source": "unparsable",
            },
        ]
    )

    normalized = preprocess_news_dataframe(raw_df)

    assert normalized["article_id"].tolist() == ["valid"]
