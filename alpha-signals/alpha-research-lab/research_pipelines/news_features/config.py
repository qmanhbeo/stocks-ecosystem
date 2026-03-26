"""Configuration for the news feature pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import os
from pathlib import Path
from typing import Dict, List


PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent.parent


def _shared_data_root() -> Path:
    configured = os.environ.get("STOCKS_DATA_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return REPO_ROOT.parent.parent / "data"


@dataclass(slots=True)
class NewsFeaturesConfig:
    """Centralized configuration for news ingestion and feature exports."""

    repo_root: Path = field(default_factory=lambda: REPO_ROOT)
    package_root: Path = field(default_factory=lambda: PACKAGE_ROOT)
    data_root: Path = field(default_factory=_shared_data_root)
    feature_root: Path = field(default_factory=lambda: _shared_data_root() / "features" / "news")
    raw_news_dir: Path = field(default_factory=lambda: _shared_data_root() / "news")
    raw_stock_dir: Path = field(default_factory=lambda: _shared_data_root() / "stock")
    artifacts_dir: Path = field(default_factory=lambda: _shared_data_root() / "features" / "news")
    configs_dir: Path = field(default_factory=lambda: PACKAGE_ROOT / "configs")
    normalized_dir: Path = field(default_factory=lambda: _shared_data_root() / "features" / "news" / "normalized")
    tagged_dir: Path = field(default_factory=lambda: _shared_data_root() / "features" / "news" / "tagged")
    datasets_dir: Path = field(default_factory=lambda: _shared_data_root() / "features" / "news" / "datasets")
    predictions_dir: Path = field(default_factory=lambda: _shared_data_root() / "features" / "news" / "predictions")
    manifest_path: Path = field(default_factory=lambda: _shared_data_root() / "features" / "news" / "manifest.json")
    source_manifest_filename: str = "manifest.json"
    default_source: str = "cafef"
    timeframe: str = "1D"
    market_timezone: str = "Asia/Ho_Chi_Minh"
    rolling_windows: List[int] = field(default_factory=lambda: [3, 5])
    keyword_score_column: str = "news_sentiment_keyword_score"
    embedding_model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"
    embedding_output_dim: int = 16
    embedding_batch_size: int = 16
    embedding_text_max_chars: int = 2000
    pca_random_seed: int = 1208
    feature_prefix: str = "news_"
    embedding_prefix: str = "news_embed_"
    missing_fill_value: float = 0.0
    max_listing_pages: int = 5
    request_delay_seconds: float = 1.0
    source_timeout_seconds: float = 15.0
    request_retry_attempts: int = 3
    request_retry_backoff_seconds: float = 1.0
    rescan_recent_sitemap_days: int = 7
    raw_save_batch_size: int = 100
    normalized_filename: str = "normalized_articles.parquet"
    tagged_filename: str = "tagged_articles.parquet"
    tabular_dataset_filename: str = "news_tabular_features.parquet"
    embedding_dataset_filename: str = "news_embedding_features.parquet"
    article_embeddings_filename: str = "article_embeddings.parquet"
    combined_dataset_filename: str = "news_daily_features.parquet"
    embedding_metadata_filename: str = "embedding_metadata.json"
    pca_model_filename: str = "news_embedding_pca.joblib"

    def ensure_directories(self) -> None:
        directories = (
            self.raw_news_dir,
            self.artifacts_dir,
            self.configs_dir,
            self.normalized_dir,
            self.tagged_dir,
            self.datasets_dir,
            self.predictions_dir,
        )
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
        self.source_raw_dir(self.default_source).mkdir(parents=True, exist_ok=True)

    def source_dir(self, source: str | None = None) -> Path:
        return self.raw_news_dir / str(source or self.default_source).lower()

    def source_raw_dir(self, source: str | None = None) -> Path:
        return self.source_dir(source) / "raw"

    def source_manifest_path(self, source: str | None = None) -> Path:
        return self.source_dir(source) / self.source_manifest_filename

    def source_seen_urls_path(self, source: str | None = None) -> Path:
        return self.source_dir(source) / "scraped_urls.txt"

    def source_scanned_sitemaps_path(self, source: str | None = None) -> Path:
        return self.source_dir(source) / "scanned_sitemaps.txt"

    def feature_spec_path(self) -> Path:
        return self.configs_dir / "feature_spec.yaml"

    def source_config_path(self) -> Path:
        return self.configs_dir / "sources.yaml"

    def normalized_path(self) -> Path:
        return self.normalized_dir / self.normalized_filename

    def tagged_path(self) -> Path:
        return self.tagged_dir / self.tagged_filename

    def tabular_dataset_path(self) -> Path:
        return self.datasets_dir / self.tabular_dataset_filename

    def embedding_dataset_path(self) -> Path:
        return self.datasets_dir / self.embedding_dataset_filename

    def article_embeddings_path(self) -> Path:
        return self.datasets_dir / self.article_embeddings_filename

    def combined_dataset_path(self) -> Path:
        return self.datasets_dir / self.combined_dataset_filename

    def embedding_metadata_path(self) -> Path:
        return self.predictions_dir / self.embedding_metadata_filename

    def pca_model_path(self) -> Path:
        return self.predictions_dir / self.pca_model_filename

    def per_ticker_feature_path(self, ticker: str) -> Path:
        return self.predictions_dir / f"{str(ticker).upper()}_news_features.parquet"

    def default_merge_columns(self) -> List[str]:
        columns = [
            "news_article_count_1d",
            "news_title_len_mean",
            "news_body_len_mean",
            "news_articles_with_title_hit",
            "news_articles_with_body_hit",
            "news_unique_urls_1d",
            "news_sentiment_keyword_score_sum",
            "news_sentiment_keyword_score_mean",
        ]
        columns.extend(f"news_article_count_{window}d" for window in self.rolling_windows)
        columns.extend(self.embedding_columns())
        return columns

    def embedding_columns(self) -> List[str]:
        return [f"{self.embedding_prefix}{index:02d}" for index in range(self.embedding_output_dim)]

    def to_dict(self) -> Dict[str, object]:
        raw = asdict(self)
        return {key: str(value) if isinstance(value, Path) else value for key, value in raw.items()}


def get_default_config() -> NewsFeaturesConfig:
    config = NewsFeaturesConfig()
    config.ensure_directories()
    return config
