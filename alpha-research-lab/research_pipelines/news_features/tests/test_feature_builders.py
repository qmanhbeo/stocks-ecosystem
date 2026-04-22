import numpy as np
import pandas as pd
import tempfile
import json
from pathlib import Path

from research_pipelines.news_features.config import NewsFeaturesConfig
from research_pipelines.news_features.core.aggregate_daily_features import (
    aggregate_daily_feature_dataframe,
    aggregate_daily_feature_exports,
)
from research_pipelines.news_features.core.build_embedding_features import build_embedding_feature_dataframe
from research_pipelines.news_features.core.build_phobert_sentiment_features import (
    build_phobert_article_sentiment_dataframe,
    build_phobert_daily_sentiment_dataframe,
    build_phobert_sentiment_exports,
)
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


def _fake_phobert_scorer(texts: list[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for text in texts:
        lower = text.lower()
        if "ap luc" in lower or "rui ro" in lower:
            rows.append(
                {
                    "phobert_input_text_length": len(text),
                    "phobert_segmented_text_length": len(text) + 4,
                    "phobert_predicted_label": "NEG",
                    "phobert_confidence": 0.9,
                    "phobert_prob_neg": 0.9,
                    "phobert_prob_neu": 0.05,
                    "phobert_prob_pos": 0.05,
                }
            )
        elif "but pha" in lower or "tich cuc" in lower or "tang truong" in lower:
            rows.append(
                {
                    "phobert_input_text_length": len(text),
                    "phobert_segmented_text_length": len(text) + 4,
                    "phobert_predicted_label": "POS",
                    "phobert_confidence": 0.8,
                    "phobert_prob_neg": 0.05,
                    "phobert_prob_neu": 0.15,
                    "phobert_prob_pos": 0.8,
                }
            )
        else:
            rows.append(
                {
                    "phobert_input_text_length": len(text),
                    "phobert_segmented_text_length": len(text) + 4,
                    "phobert_predicted_label": "NEU",
                    "phobert_confidence": 0.6,
                    "phobert_prob_neg": 0.1,
                    "phobert_prob_neu": 0.6,
                    "phobert_prob_pos": 0.3,
                }
            )
    return rows


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


def test_build_phobert_features_create_article_rows_and_rolling_daily_states():
    config = _config()

    article_rows, metadata = build_phobert_article_sentiment_dataframe(
        _normalized_df(),
        _tagged_df(),
        config=config,
        scorer=_fake_phobert_scorer,
        scorer_metadata={"phobert_model_id": "fake-phobert"},
    )

    assert len(article_rows) == 4
    assert metadata["phobert_model_id"] == "fake-phobert"
    assert article_rows.loc[article_rows["article_id"] == "a1", "phobert_predicted_label"].iloc[0] == "POS"
    assert article_rows.loc[article_rows["article_id"] == "a2", "phobert_sentiment_score"].iloc[0] == -1.0

    daily = build_phobert_daily_sentiment_dataframe(article_rows, config=config)
    acb = daily.loc[daily["ticker"] == "ACB"].reset_index(drop=True)
    assert acb["date"].tolist() == ["2026-03-10", "2026-03-11", "2026-03-12"]
    assert acb["phobert_article_count_1d"].tolist() == [1.0, 0.0, 1.0]
    assert acb["phobert_article_count_5d"].tolist() == [1.0, 1.0, 2.0]
    assert acb["phobert_sentiment_score_sum"].tolist() == [1.0, 0.0, -1.0]


def test_aggregate_daily_features_merges_phobert_columns():
    config = _config()

    def fake_encoder(texts: list[str]) -> np.ndarray:
        return np.array([[len(text), len(text) / 2.0, index + 1.0, 1.0] for index, text in enumerate(texts)], dtype=float)

    embeddings, _, _, _ = build_embedding_feature_dataframe(
        normalized_df=_normalized_df(),
        tagged_df=_tagged_df(),
        config=config,
        encoder=fake_encoder,
    )
    tabular = build_tabular_feature_dataframe(_normalized_df(), _tagged_df(), config=config)
    article_rows, _ = build_phobert_article_sentiment_dataframe(
        _normalized_df(),
        _tagged_df(),
        config=config,
        scorer=_fake_phobert_scorer,
        scorer_metadata={"phobert_model_id": "fake-phobert"},
    )
    phobert_daily = build_phobert_daily_sentiment_dataframe(article_rows, config=config)

    combined = aggregate_daily_feature_dataframe(tabular, embeddings, phobert_df=phobert_daily, config=config)
    assert "phobert_sentiment_5d" in combined.columns
    acb_2026_03_10 = combined.loc[(combined["ticker"] == "ACB") & (combined["date"] == "2026-03-10")]
    assert acb_2026_03_10["phobert_article_count_1d"].iloc[0] == 1.0


def test_build_phobert_exports_writes_datasets_and_manifest_entries(tmp_path):
    root = tmp_path
    config = NewsFeaturesConfig(
        repo_root=root / "alpha-research-lab",
        package_root=root / "alpha-research-lab" / "research_pipelines" / "news_features",
        data_root=root / "data",
        feature_root=root / "data" / "features" / "news",
        raw_news_dir=root / "data" / "news",
        raw_stock_dir=root / "data" / "stock",
        artifacts_dir=root / "data" / "features" / "news",
        configs_dir=root / "alpha-research-lab" / "research_pipelines" / "news_features" / "configs",
        normalized_dir=root / "data" / "features" / "news" / "normalized",
        tagged_dir=root / "data" / "features" / "news" / "tagged",
        datasets_dir=root / "data" / "features" / "news" / "datasets",
        predictions_dir=root / "data" / "features" / "news" / "predictions",
        manifest_path=root / "data" / "features" / "news" / "manifest.json",
    )
    config.ensure_directories()

    _normalized_df().assign(published_at="2026-03-10T09:00:00+07:00").to_parquet(config.normalized_path(), index=False)
    _tagged_df().to_parquet(config.tagged_path(), index=False)

    daily = build_phobert_sentiment_exports(
        config=config,
        scorer=_fake_phobert_scorer,
        scorer_metadata={"phobert_model_id": "fake-phobert"},
    )

    assert len(daily) > 0
    assert config.phobert_article_sentiment_path().exists()
    assert config.phobert_ticker_day_sentiment_path().exists()
    manifest = json.loads(config.manifest_path.read_text(encoding="utf-8"))
    assert manifest["phobert_model_id"] == "fake-phobert"


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
