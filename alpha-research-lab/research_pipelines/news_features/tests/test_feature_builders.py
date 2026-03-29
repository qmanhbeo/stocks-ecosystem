import numpy as np
import pandas as pd
import tempfile
from pathlib import Path

from research_pipelines.news_features.config import NewsFeaturesConfig
from research_pipelines.news_features.core.aggregate_daily_features import (
    aggregate_daily_feature_dataframe,
    aggregate_daily_feature_exports,
)
from research_pipelines.news_features.core.build_embedding_features import build_embedding_feature_dataframe
from research_pipelines.news_features.core.build_tabular_features import build_tabular_feature_dataframe


def _config() -> NewsFeaturesConfig:
    return NewsFeaturesConfig()


def _normalized_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "article_id": "a1",
                "source": "cafef",
                "url": "https://cafef.vn/a1.chn",
                "clean_title": "ACB tang truong tich cuc",
                "clean_summary": "ket qua tot",
                "clean_body_text": "ACB but pha",
                "date": "2026-03-10",
            },
            {
                "article_id": "a2",
                "source": "cafef",
                "url": "https://cafef.vn/a2.chn",
                "clean_title": "HPG doi mat ap luc",
                "clean_summary": "",
                "clean_body_text": "rui ro ngan han",
                "date": "2026-03-11",
            },
            {
                "article_id": "a3",
                "source": "cafef",
                "url": "https://cafef.vn/a3.chn",
                "clean_title": "ACB va HPG cung duoc nhac den",
                "clean_summary": "",
                "clean_body_text": "but pha nhưng cung co ap luc",
                "date": "2026-03-12",
            },
        ]
    )


def _tagged_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "article_id": "a1",
                "ticker": "ACB",
                "date": "2026-03-10",
                "url": "https://cafef.vn/a1.chn",
                "source": "cafef",
                "match_source": "title",
                "title_hit": 1,
                "body_hit": 1,
            },
            {
                "article_id": "a2",
                "ticker": "HPG",
                "date": "2026-03-11",
                "url": "https://cafef.vn/a2.chn",
                "source": "cafef",
                "match_source": "title",
                "title_hit": 1,
                "body_hit": 1,
            },
            {
                "article_id": "a3",
                "ticker": "ACB",
                "date": "2026-03-12",
                "url": "https://cafef.vn/a3.chn",
                "source": "cafef",
                "match_source": "title",
                "title_hit": 1,
                "body_hit": 1,
            },
            {
                "article_id": "a3",
                "ticker": "HPG",
                "date": "2026-03-12",
                "url": "https://cafef.vn/a3.chn",
                "source": "cafef",
                "match_source": "body",
                "title_hit": 0,
                "body_hit": 1,
            },
        ]
    )


def test_build_tabular_features_creates_daily_counts_and_rolling_windows():
    config = _config()
    tabular = build_tabular_feature_dataframe(_normalized_df(), _tagged_df(), config=config)
    acb = tabular.loc[tabular["ticker"] == "ACB"].reset_index(drop=True)
    assert acb["date"].tolist() == ["2026-03-10", "2026-03-11", "2026-03-12"]
    assert acb["news_article_count_1d"].tolist() == [1.0, 0.0, 1.0]
    assert acb["news_article_count_3d"].tolist() == [1.0, 1.0, 2.0]


def test_build_embedding_features_and_aggregate_exports():
    config = _config()

    def fake_encoder(texts: list[str]) -> np.ndarray:
        return np.array([[len(text), len(text) / 2.0, index + 1.0, 1.0] for index, text in enumerate(texts)], dtype=float)

    embeddings, article_embeddings, metadata, _ = build_embedding_feature_dataframe(
        normalized_df=_normalized_df(),
        tagged_df=_tagged_df(),
        config=config,
        encoder=fake_encoder,
    )
    assert set(config.embedding_columns()) <= set(embeddings.columns)
    assert len(article_embeddings) == 4
    assert metadata["raw_embedding_dim"] == 4

    tabular = build_tabular_feature_dataframe(_normalized_df(), _tagged_df(), config=config)
    combined = aggregate_daily_feature_dataframe(tabular, embeddings, config=config)
    assert set(config.embedding_columns()) <= set(combined.columns)
    assert {"ticker", "date", "news_article_count_1d"} <= set(combined.columns)


def test_aggregate_daily_feature_exports_removes_stale_per_ticker_files():
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        config = NewsFeaturesConfig(
            repo_root=root,
            package_root=root / "pkg",
            data_root=root / "data",
            feature_root=root / "data" / "features" / "news",
            raw_news_dir=root / "data" / "news",
            raw_stock_dir=root / "data" / "stock",
            artifacts_dir=root / "data" / "features" / "news",
            configs_dir=root / "configs",
            normalized_dir=root / "data" / "features" / "news" / "normalized",
            tagged_dir=root / "data" / "features" / "news" / "tagged",
            datasets_dir=root / "data" / "features" / "news" / "datasets",
            predictions_dir=root / "data" / "features" / "news" / "predictions",
            manifest_path=root / "data" / "features" / "news" / "manifest.json",
        )
        config.ensure_directories()

        pd.DataFrame({"ticker": ["BBB"], "date": ["2024-01-01"], "x": [1.0]}).to_parquet(
            config.per_ticker_feature_path("BBB"),
            index=False,
        )
        pd.DataFrame({"ticker": ["AAA"], "date": ["2024-01-01"], "x": [2.0]}).to_parquet(
            config.tabular_dataset_path(),
            index=False,
        )

        combined = aggregate_daily_feature_exports(config=config)

        assert combined["ticker"].tolist() == ["AAA"]
        assert config.per_ticker_feature_path("AAA").exists()
        assert not config.per_ticker_feature_path("BBB").exists()
