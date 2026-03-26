import pandas as pd

from research_pipelines.news_features.core.tag_articles import tag_articles_dataframe


def test_tag_articles_supports_multiple_tickers_and_title_preference():
    normalized = pd.DataFrame(
        [
            {
                "article_id": "a1",
                "date": "2026-03-10",
                "url": "https://cafef.vn/a1.chn",
                "source": "cafef",
                "clean_title": "ACB but pha sau ket qua kinh doanh",
                "clean_summary": "",
                "clean_body_text": "HPG cung duoc nhac den trong bai viet",
            }
        ]
    )

    tagged = tag_articles_dataframe(normalized, ["ACB", "HPG", "VNM"])
    assert tagged["ticker"].tolist() == ["ACB", "HPG"]
    assert tagged.loc[tagged["ticker"] == "ACB", "match_source"].iloc[0] == "title"
    assert tagged.loc[tagged["ticker"] == "HPG", "match_source"].iloc[0] == "body"


def test_tag_articles_ignores_unknown_symbols():
    normalized = pd.DataFrame(
        [
            {
                "article_id": "a1",
                "date": "2026-03-10",
                "url": "https://cafef.vn/a1.chn",
                "source": "cafef",
                "clean_title": "XYZ tang manh",
                "clean_summary": "",
                "clean_body_text": "XYZ khong phai ticker co trong du lieu",
            }
        ]
    )

    tagged = tag_articles_dataframe(normalized, ["ACB", "HPG"])
    assert tagged.empty
