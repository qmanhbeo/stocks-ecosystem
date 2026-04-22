"""Run the full news feature pipeline over already-fetched raw news."""

from __future__ import annotations

from research_pipelines.news_features.config import get_default_config
from research_pipelines.news_features.core.aggregate_daily_features import aggregate_daily_feature_exports
from research_pipelines.news_features.core.build_embedding_features import build_embedding_feature_exports
from research_pipelines.news_features.core.build_phobert_sentiment_features import build_phobert_sentiment_exports
from research_pipelines.news_features.core.build_tabular_features import build_tabular_feature_exports
from research_pipelines.news_features.core.preprocess_news import preprocess_news_exports
from research_pipelines.news_features.core.tag_articles import tag_articles_exports


def main() -> None:
    config = get_default_config()
    preprocess_news_exports(config=config)
    tag_articles_exports(config=config)
    build_tabular_feature_exports(config=config)
    build_phobert_sentiment_exports(config=config)
    build_embedding_feature_exports(config=config)
    aggregate_daily_feature_exports(config=config)
    print(f"News feature pipeline complete. Outputs written under: {config.artifacts_dir}")


if __name__ == "__main__":
    main()
