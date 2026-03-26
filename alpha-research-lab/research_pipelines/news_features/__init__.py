"""News feature pipeline for raw news ingestion, preprocessing, and RL-ready features."""

from research_pipelines.news_features.config import NewsFeaturesConfig, get_default_config

__all__ = ["NewsFeaturesConfig", "get_default_config"]
