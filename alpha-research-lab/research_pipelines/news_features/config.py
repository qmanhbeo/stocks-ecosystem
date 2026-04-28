"""Configuration for the news feature pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import shutil
from typing import Dict, List


PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent.parent
DEFAULT_MARKET_TIMEZONE = "Asia/Ho_Chi_Minh"


def _shared_data_root() -> Path:
    configured = os.environ.get("STOCKS_DATA_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return REPO_ROOT.parent / "data"


@dataclass(slots=True)
class NewsFeaturesConfig:
    """Centralized configuration for news ingestion and feature exports."""

    repo_root: Path = field(default_factory=lambda: REPO_ROOT)
    package_root: Path = field(default_factory=lambda: PACKAGE_ROOT)
    data_root: Path = field(default_factory=_shared_data_root)
    feature_root: Path = field(default_factory=lambda: _shared_data_root() / "features" / "news")
    raw_news_dir: Path = field(default_factory=lambda: _shared_data_root() / "news")
    raw_stock_dir: Path = field(default_factory=lambda: _shared_data_root() / "stock")
    model_checkpoints_root: Path = field(default_factory=lambda: _shared_data_root() / "model_checkpoints")
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
    market_timezone: str = DEFAULT_MARKET_TIMEZONE
    rolling_windows: List[int] = field(default_factory=lambda: [3, 5])
    keyword_score_column: str = "news_sentiment_keyword_score"
    embedding_model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"
    embedding_output_dim: int = 16
    embedding_batch_size: int = 16
    embedding_checkpoint_rows: int = 2000
    embedding_text_max_chars: int = 2000
    pca_random_seed: int = 1208
    phobert_model_name: str = "Angelectronic/phobert-base-vietnamese-sentiment"
    phobert_batch_size: int = 64
    phobert_max_length: int = 256
    phobert_precision: str = "auto"
    phobert_checkpoint_rows: int = 2000
    phobert_prefer_local_files: bool = True
    phobert_forward_looking_candidate_names: List[str] = field(
        default_factory=lambda: ["phobert_base", "phobert_base_v2"]
    )
    phobert_forward_looking_candidate_model_names: List[str] = field(
        default_factory=lambda: ["vinai/phobert-base", "vinai/phobert-base-v2"]
    )
    phobert_forward_looking_max_length: int = 256
    phobert_forward_looking_precision: str = "auto"
    phobert_forward_looking_inference_batch_size: int = 32
    phobert_forward_looking_train_micro_batch_size: int = 2
    phobert_forward_looking_eval_micro_batch_size: int = 4
    phobert_forward_looking_gradient_accumulation_steps: int = 8
    phobert_forward_looking_learning_rate: float = 2e-5
    phobert_forward_looking_weight_decay: float = 0.01
    phobert_forward_looking_num_epochs: int = 2
    phobert_forward_looking_stream_batch_rows: int = 256
    phobert_forward_looking_random_seed: int = 1208
    phobert_forward_looking_train_fraction: float = 0.70
    phobert_forward_looking_val_fraction: float = 0.15
    phobert_forward_looking_enable_gradient_checkpointing: bool = True
    phobert_forward_looking_prefer_local_files: bool = True
    phobert_binary_head_training_checkpoint_steps: int = 250
    phobert_binary_head_default_positive_threshold_value: float = 0.5
    phobert_binary_head_threshold_search_min: float = 0.01
    phobert_binary_head_threshold_search_max: float = 0.99
    phobert_binary_head_threshold_search_step: float = 0.01
    phobert_article_scope_split_strategy_value: str = "stratified_random"
    phobert_source_type_split_strategy_value: str = "stratified_random"
    phobert_article_scope_enable_class_weighting: bool = True
    phobert_source_type_enable_class_weighting: bool = False
    ollama_guarded_model_name: str = "qwen2.5-coder:3b"
    ollama_guarded_timeout_seconds: int = 180
    ollama_guarded_num_predict: int = 64
    ollama_guarded_num_ctx: int = 512
    ollama_guarded_temperature: float = 0.0
    ollama_guarded_keep_alive: str = "5m"
    ollama_guarded_use_schema: bool = True
    ollama_guarded_prompt_variant: str = "lean_json_bottom_v1"
    ollama_guarded_field_set: str = "event_only"
    ollama_guarded_max_body_chars: int = 0
    ollama_guarded_max_body_words: int = 300
    ollama_guarded_stop_after_each_call: bool = False
    ollama_guarded_min_article_scope_prob: float = 0.28
    ollama_guarded_min_source_type_prob: float = 0.0
    ollama_guarded_checkpoint_rows: int = 20
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
    tabular_stage_filename: str = "news_tabular_article_stage.parquet"
    tabular_stage_manifest_filename: str = "news_tabular_article_stage_manifest.json"
    embedding_dataset_filename: str = "news_embedding_features.parquet"
    article_embeddings_filename: str = "article_embeddings.parquet"
    embedding_input_articles_filename: str = "embedding_input_articles.parquet"
    phobert_article_sentiment_filename: str = "phobert_article_sentiment.parquet"
    phobert_ticker_day_sentiment_filename: str = "phobert_ticker_day_sentiment.parquet"
    phobert_input_articles_filename: str = "phobert_input_articles.parquet"
    phobert_forward_looking_teacher_labels_filename: str = "phobert_forward_looking_teacher_labels.parquet"
    phobert_forward_looking_teacher_manifest_filename: str = "phobert_forward_looking_teacher_manifest.json"
    phobert_forward_looking_stage_filename: str = "phobert_forward_looking_stage_articles.parquet"
    phobert_forward_looking_stage_manifest_filename: str = "phobert_forward_looking_stage_manifest.json"
    phobert_forward_looking_article_features_filename: str = "phobert_forward_looking_article_features.parquet"
    phobert_forward_looking_ticker_day_features_filename: str = "phobert_forward_looking_ticker_day_features.parquet"
    phobert_forward_looking_metadata_filename: str = "phobert_forward_looking_metadata.json"
    phobert_article_scope_teacher_labels_filename: str = "phobert_article_scope_teacher_labels.parquet"
    phobert_article_scope_teacher_manifest_filename: str = "phobert_article_scope_teacher_manifest.json"
    phobert_article_scope_stage_filename: str = "phobert_article_scope_stage_articles.parquet"
    phobert_article_scope_stage_manifest_filename: str = "phobert_article_scope_stage_manifest.json"
    phobert_article_scope_article_features_filename: str = "phobert_article_scope_article_features.parquet"
    phobert_article_scope_ticker_day_features_filename: str = "phobert_article_scope_ticker_day_features.parquet"
    phobert_article_scope_metadata_filename: str = "phobert_article_scope_metadata.json"
    phobert_source_type_teacher_labels_filename: str = "phobert_source_type_teacher_labels.parquet"
    phobert_source_type_teacher_manifest_filename: str = "phobert_source_type_teacher_manifest.json"
    phobert_source_type_stage_filename: str = "phobert_source_type_stage_articles.parquet"
    phobert_source_type_stage_manifest_filename: str = "phobert_source_type_stage_manifest.json"
    phobert_source_type_article_features_filename: str = "phobert_source_type_article_features.parquet"
    phobert_source_type_ticker_day_features_filename: str = "phobert_source_type_ticker_day_features.parquet"
    phobert_source_type_metadata_filename: str = "phobert_source_type_metadata.json"
    ollama_guarded_article_features_filename: str = "ollama_guarded_article_features.parquet"
    ollama_guarded_ticker_day_features_filename: str = "ollama_guarded_ticker_day_features.parquet"
    ollama_guarded_input_articles_filename: str = "ollama_guarded_input_articles.parquet"
    combined_dataset_filename: str = "news_daily_features.parquet"
    embedding_metadata_filename: str = "embedding_metadata.json"
    pca_model_filename: str = "news_embedding_pca.joblib"
    embedding_checkpoint_dirname: str = "embedding_checkpoint"
    embedding_checkpoint_manifest_filename: str = "embedding_checkpoint_manifest.json"
    embedding_input_manifest_filename: str = "embedding_input_articles_manifest.json"
    phobert_checkpoint_dirname: str = "phobert_checkpoint"
    phobert_checkpoint_manifest_filename: str = "phobert_checkpoint_manifest.json"
    phobert_input_manifest_filename: str = "phobert_input_articles_manifest.json"
    phobert_forward_looking_publish_checkpoint_dirname: str = "phobert_forward_looking_checkpoint"
    phobert_forward_looking_publish_checkpoint_manifest_filename: str = "phobert_forward_looking_checkpoint_manifest.json"
    phobert_forward_looking_publish_checkpoint_rows: int = 2000
    phobert_forward_looking_model_dirname: str = "news/phobert_forward_looking"
    phobert_forward_looking_legacy_model_dirname: str = "news_models/phobert_forward_looking"
    phobert_forward_looking_training_manifest_filename: str = "training_manifest.json"
    phobert_forward_looking_latest_winner_filename: str = "latest_winner.json"
    phobert_article_scope_publish_checkpoint_dirname: str = "phobert_article_scope_checkpoint"
    phobert_article_scope_publish_checkpoint_manifest_filename: str = "phobert_article_scope_checkpoint_manifest.json"
    phobert_article_scope_model_dirname: str = "news/phobert_article_scope"
    phobert_source_type_publish_checkpoint_dirname: str = "phobert_source_type_checkpoint"
    phobert_source_type_publish_checkpoint_manifest_filename: str = "phobert_source_type_checkpoint_manifest.json"
    phobert_source_type_model_dirname: str = "news/phobert_source_type"
    job_status_dirname: str = "job_status"
    ollama_guarded_checkpoint_dirname: str = "ollama_guarded_checkpoint"
    ollama_guarded_checkpoint_manifest_filename: str = "ollama_guarded_checkpoint_manifest.json"
    ollama_guarded_input_manifest_filename: str = "ollama_guarded_input_manifest.json"
    ollama_guarded_score_cache_dirname: str = "ollama_guarded_score_cache"
    ollama_guarded_score_cache_manifest_filename: str = "ollama_guarded_score_cache_manifest.json"

    def ensure_directories(self) -> None:
        directories = (
            self.raw_news_dir,
            self.artifacts_dir,
            self.configs_dir,
            self.normalized_dir,
            self.tagged_dir,
            self.datasets_dir,
            self.predictions_dir,
            self.model_checkpoints_root,
            self.embedding_checkpoint_dir(),
            self.phobert_checkpoint_dir(),
            self.phobert_forward_looking_publish_checkpoint_dir(),
            self.ollama_guarded_checkpoint_dir(),
            self.ollama_guarded_score_cache_root_dir(),
            self.phobert_forward_looking_model_artifacts_dir(),
            self.job_status_dir(),
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

    def tabular_stage_path(self) -> Path:
        return self.datasets_dir / self.tabular_stage_filename

    def tabular_stage_manifest_path(self) -> Path:
        return self.datasets_dir / self.tabular_stage_manifest_filename

    def embedding_dataset_path(self) -> Path:
        return self.datasets_dir / self.embedding_dataset_filename

    def article_embeddings_path(self) -> Path:
        return self.datasets_dir / self.article_embeddings_filename

    def embedding_input_articles_path(self) -> Path:
        return self.datasets_dir / self.embedding_input_articles_filename

    def embedding_input_manifest_path(self) -> Path:
        return self.datasets_dir / self.embedding_input_manifest_filename

    def embedding_checkpoint_dir(self) -> Path:
        return self.datasets_dir / self.embedding_checkpoint_dirname

    def embedding_checkpoint_manifest_path(self) -> Path:
        return self.embedding_checkpoint_dir() / self.embedding_checkpoint_manifest_filename

    def embedding_checkpoint_shard_path(self, batch_index: int) -> Path:
        return self.embedding_checkpoint_dir() / f"article_shard_{int(batch_index):06d}.parquet"

    def phobert_article_sentiment_path(self) -> Path:
        return self.datasets_dir / self.phobert_article_sentiment_filename

    def phobert_ticker_day_sentiment_path(self) -> Path:
        return self.datasets_dir / self.phobert_ticker_day_sentiment_filename

    def phobert_input_articles_path(self) -> Path:
        return self.datasets_dir / self.phobert_input_articles_filename

    def phobert_input_manifest_path(self) -> Path:
        return self.datasets_dir / self.phobert_input_manifest_filename

    def phobert_checkpoint_dir(self) -> Path:
        return self.datasets_dir / self.phobert_checkpoint_dirname

    def phobert_checkpoint_manifest_path(self) -> Path:
        return self.phobert_checkpoint_dir() / self.phobert_checkpoint_manifest_filename

    def phobert_checkpoint_shard_path(self, batch_index: int) -> Path:
        return self.phobert_checkpoint_dir() / f"article_shard_{int(batch_index):06d}.parquet"

    def phobert_forward_looking_teacher_labels_path(self) -> Path:
        return self.datasets_dir / self.phobert_forward_looking_teacher_labels_filename

    def phobert_forward_looking_teacher_manifest_path(self) -> Path:
        return self.datasets_dir / self.phobert_forward_looking_teacher_manifest_filename

    def phobert_forward_looking_stage_path(self) -> Path:
        return self.datasets_dir / self.phobert_forward_looking_stage_filename

    def phobert_forward_looking_stage_manifest_path(self) -> Path:
        return self.datasets_dir / self.phobert_forward_looking_stage_manifest_filename

    def phobert_forward_looking_article_features_path(self) -> Path:
        return self.datasets_dir / self.phobert_forward_looking_article_features_filename

    def phobert_forward_looking_ticker_day_features_path(self) -> Path:
        return self.datasets_dir / self.phobert_forward_looking_ticker_day_features_filename

    def phobert_forward_looking_metadata_path(self) -> Path:
        return self.datasets_dir / self.phobert_forward_looking_metadata_filename

    def phobert_article_scope_teacher_labels_path(self) -> Path:
        return self.datasets_dir / self.phobert_article_scope_teacher_labels_filename

    def phobert_article_scope_teacher_manifest_path(self) -> Path:
        return self.datasets_dir / self.phobert_article_scope_teacher_manifest_filename

    def phobert_article_scope_stage_path(self) -> Path:
        return self.datasets_dir / self.phobert_article_scope_stage_filename

    def phobert_article_scope_stage_manifest_path(self) -> Path:
        return self.datasets_dir / self.phobert_article_scope_stage_manifest_filename

    def phobert_article_scope_article_features_path(self) -> Path:
        return self.datasets_dir / self.phobert_article_scope_article_features_filename

    def phobert_article_scope_ticker_day_features_path(self) -> Path:
        return self.datasets_dir / self.phobert_article_scope_ticker_day_features_filename

    def phobert_article_scope_metadata_path(self) -> Path:
        return self.datasets_dir / self.phobert_article_scope_metadata_filename

    def phobert_article_scope_publish_checkpoint_dir(self) -> Path:
        return self.datasets_dir / self.phobert_article_scope_publish_checkpoint_dirname

    def phobert_article_scope_publish_checkpoint_manifest_path(self) -> Path:
        return self.phobert_article_scope_publish_checkpoint_dir() / (
            self.phobert_article_scope_publish_checkpoint_manifest_filename
        )

    def phobert_article_scope_publish_checkpoint_shard_path(self, batch_index: int) -> Path:
        return self.phobert_article_scope_publish_checkpoint_dir() / f"article_shard_{int(batch_index):06d}.parquet"

    def phobert_article_scope_model_artifacts_dir(self) -> Path:
        return self.model_checkpoints_root / self.phobert_article_scope_model_dirname

    def phobert_article_scope_training_manifest_path(self) -> Path:
        return self.phobert_article_scope_model_artifacts_dir() / self.phobert_forward_looking_training_manifest_filename

    def phobert_article_scope_latest_winner_path(self) -> Path:
        return self.phobert_article_scope_model_artifacts_dir() / self.phobert_forward_looking_latest_winner_filename

    def phobert_source_type_teacher_labels_path(self) -> Path:
        return self.datasets_dir / self.phobert_source_type_teacher_labels_filename

    def phobert_source_type_teacher_manifest_path(self) -> Path:
        return self.datasets_dir / self.phobert_source_type_teacher_manifest_filename

    def phobert_source_type_stage_path(self) -> Path:
        return self.datasets_dir / self.phobert_source_type_stage_filename

    def phobert_source_type_stage_manifest_path(self) -> Path:
        return self.datasets_dir / self.phobert_source_type_stage_manifest_filename

    def phobert_source_type_article_features_path(self) -> Path:
        return self.datasets_dir / self.phobert_source_type_article_features_filename

    def phobert_source_type_ticker_day_features_path(self) -> Path:
        return self.datasets_dir / self.phobert_source_type_ticker_day_features_filename

    def phobert_source_type_metadata_path(self) -> Path:
        return self.datasets_dir / self.phobert_source_type_metadata_filename

    def phobert_source_type_publish_checkpoint_dir(self) -> Path:
        return self.datasets_dir / self.phobert_source_type_publish_checkpoint_dirname

    def phobert_source_type_publish_checkpoint_manifest_path(self) -> Path:
        return self.phobert_source_type_publish_checkpoint_dir() / (
            self.phobert_source_type_publish_checkpoint_manifest_filename
        )

    def phobert_source_type_publish_checkpoint_shard_path(self, batch_index: int) -> Path:
        return self.phobert_source_type_publish_checkpoint_dir() / f"article_shard_{int(batch_index):06d}.parquet"

    def phobert_source_type_model_artifacts_dir(self) -> Path:
        return self.model_checkpoints_root / self.phobert_source_type_model_dirname

    def phobert_source_type_training_manifest_path(self) -> Path:
        return self.phobert_source_type_model_artifacts_dir() / self.phobert_forward_looking_training_manifest_filename

    def phobert_source_type_latest_winner_path(self) -> Path:
        return self.phobert_source_type_model_artifacts_dir() / self.phobert_forward_looking_latest_winner_filename

    def phobert_forward_looking_publish_checkpoint_dir(self) -> Path:
        return self.datasets_dir / self.phobert_forward_looking_publish_checkpoint_dirname

    def phobert_forward_looking_publish_checkpoint_manifest_path(self) -> Path:
        return self.phobert_forward_looking_publish_checkpoint_dir() / (
            self.phobert_forward_looking_publish_checkpoint_manifest_filename
        )

    def phobert_forward_looking_publish_checkpoint_shard_path(self, batch_index: int) -> Path:
        return self.phobert_forward_looking_publish_checkpoint_dir() / f"article_shard_{int(batch_index):06d}.parquet"

    def phobert_forward_looking_model_artifacts_dir(self) -> Path:
        return self.model_checkpoints_root / self.phobert_forward_looking_model_dirname

    def phobert_forward_looking_legacy_model_artifacts_dir(self) -> Path:
        return self.repo_root / "artifacts" / self.phobert_forward_looking_legacy_model_dirname

    def phobert_forward_looking_training_manifest_path(self) -> Path:
        return self.phobert_forward_looking_model_artifacts_dir() / self.phobert_forward_looking_training_manifest_filename

    def phobert_forward_looking_latest_winner_path(self) -> Path:
        return self.phobert_forward_looking_model_artifacts_dir() / self.phobert_forward_looking_latest_winner_filename

    def job_status_dir(self) -> Path:
        return self.repo_root / "artifacts" / self.job_status_dirname

    def _normalize_checkpoint_payload(self, payload: object, source_root: Path, target_root: Path | str) -> object:
        source_root_str = str(source_root)
        source_rel = f"artifacts/{self.phobert_forward_looking_legacy_model_dirname}".replace("\\", "/")
        target_root_str = str(target_root)

        if isinstance(payload, dict):
            return {
                key: self._normalize_checkpoint_payload(value, source_root, target_root)
                for key, value in payload.items()
            }
        if isinstance(payload, list):
            return [self._normalize_checkpoint_payload(value, source_root, target_root) for value in payload]
        if isinstance(payload, str):
            value = payload.replace(source_root_str, target_root_str)
            value = value.replace(source_rel, target_root_str.replace("\\", "/"))
            return value
        return payload

    def _load_json_if_present(self, path: Path) -> object:
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _rewrite_checkpoint_json_tree(self, checkpoint_root: Path, source_root: Path) -> None:
        for path in sorted(checkpoint_root.rglob("*.json")):
            payload = self._load_json_if_present(path)
            normalized = self._normalize_checkpoint_payload(payload, source_root, checkpoint_root)
            path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _checkpoint_dir_has_content(self, root: Path) -> bool:
        return root.exists() and any(root.rglob("*"))

    def _checkpoint_payload_signature(self, root: Path) -> dict[str, object]:
        return {
            "training_manifest": self._normalize_checkpoint_payload(
                self._load_json_if_present(root / self.phobert_forward_looking_training_manifest_filename),
                root,
                "__MODEL_ROOT__",
            ),
            "latest_winner": self._normalize_checkpoint_payload(
                self._load_json_if_present(root / self.phobert_forward_looking_latest_winner_filename),
                root,
                "__MODEL_ROOT__",
            ),
        }

    def ensure_phobert_forward_looking_model_state(self) -> Path:
        checkpoint_root = self.phobert_forward_looking_model_artifacts_dir()
        legacy_root = self.phobert_forward_looking_legacy_model_artifacts_dir()
        checkpoint_root.mkdir(parents=True, exist_ok=True)

        checkpoint_has_content = self._checkpoint_dir_has_content(checkpoint_root)
        legacy_has_content = self._checkpoint_dir_has_content(legacy_root)
        if not legacy_has_content:
            return checkpoint_root
        if not checkpoint_has_content:
            shutil.copytree(legacy_root, checkpoint_root, dirs_exist_ok=True)
            self._rewrite_checkpoint_json_tree(checkpoint_root, legacy_root)
            return checkpoint_root

        checkpoint_signature = self._checkpoint_payload_signature(checkpoint_root)
        legacy_signature = self._checkpoint_payload_signature(legacy_root)
        if checkpoint_signature != legacy_signature:
            raise RuntimeError(
                "Divergent PhoBERT forward-looking checkpoint roots detected at "
                f"{checkpoint_root} and {legacy_root}. Resolve manually before continuing."
            )
        return checkpoint_root

    def phobert_forward_looking_job_status_path(self) -> Path:
        return self.job_status_dir() / "phobert_forward_looking_train.json"

    def phobert_forward_looking_publish_job_status_path(self) -> Path:
        return self.job_status_dir() / "phobert_forward_looking_publish.json"

    def phobert_article_scope_job_status_path(self) -> Path:
        return self.job_status_dir() / "phobert_article_scope_train.json"

    def phobert_article_scope_publish_job_status_path(self) -> Path:
        return self.job_status_dir() / "phobert_article_scope_publish.json"

    def phobert_source_type_job_status_path(self) -> Path:
        return self.job_status_dir() / "phobert_source_type_train.json"

    def phobert_source_type_publish_job_status_path(self) -> Path:
        return self.job_status_dir() / "phobert_source_type_publish.json"

    def ollama_guarded_job_status_path(self) -> Path:
        return self.job_status_dir() / "ollama_guarded_publish.json"

    def ollama_guarded_article_features_path(self) -> Path:
        return self.datasets_dir / self.ollama_guarded_article_features_filename

    def ollama_guarded_ticker_day_features_path(self) -> Path:
        return self.datasets_dir / self.ollama_guarded_ticker_day_features_filename

    def ollama_guarded_input_articles_path(self) -> Path:
        return self.datasets_dir / self.ollama_guarded_input_articles_filename

    def ollama_guarded_input_manifest_path(self) -> Path:
        return self.datasets_dir / self.ollama_guarded_input_manifest_filename

    def ollama_guarded_checkpoint_dir(self) -> Path:
        return self.datasets_dir / self.ollama_guarded_checkpoint_dirname

    def ollama_guarded_checkpoint_manifest_path(self) -> Path:
        return self.ollama_guarded_checkpoint_dir() / self.ollama_guarded_checkpoint_manifest_filename

    def ollama_guarded_checkpoint_shard_path(self, batch_index: int) -> Path:
        return self.ollama_guarded_checkpoint_dir() / f"article_shard_{int(batch_index):06d}.parquet"

    def ollama_guarded_score_cache_root_dir(self) -> Path:
        return self.datasets_dir / self.ollama_guarded_score_cache_dirname

    def ollama_guarded_score_cache_dir(self, score_signature_hash: str) -> Path:
        return self.ollama_guarded_score_cache_root_dir() / str(score_signature_hash)

    def ollama_guarded_score_cache_manifest_path(self, score_signature_hash: str) -> Path:
        return self.ollama_guarded_score_cache_dir(score_signature_hash) / (
            self.ollama_guarded_score_cache_manifest_filename
        )

    def ollama_guarded_score_cache_shard_path(self, score_signature_hash: str, shard_index: int) -> Path:
        return self.ollama_guarded_score_cache_dir(score_signature_hash) / (
            f"score_shard_{int(shard_index):06d}.parquet"
        )

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
        columns.extend(self.phobert_daily_columns())
        columns.extend(self.phobert_forward_looking_daily_columns())
        columns.extend(self.phobert_article_scope_daily_columns())
        columns.extend(self.phobert_source_type_daily_columns())
        columns.extend(self.ollama_guarded_daily_columns())
        columns.extend(self.embedding_columns())
        return columns

    def embedding_columns(self) -> List[str]:
        return [f"{self.embedding_prefix}{index:02d}" for index in range(self.embedding_output_dim)]

    def phobert_daily_columns(self) -> List[str]:
        return [
            "phobert_article_count_1d",
            "phobert_sentiment_score_mean",
            "phobert_sentiment_score_sum",
            "phobert_sentiment_conf_weighted_mean",
            "phobert_sentiment_conf_weighted_sum",
            "phobert_prob_pos_mean",
            "phobert_prob_neu_mean",
            "phobert_prob_neg_mean",
            "phobert_pos_share",
            "phobert_neu_share",
            "phobert_neg_share",
            "phobert_article_count_5d",
            "phobert_article_count_30d",
            "phobert_sentiment_5d",
            "phobert_sentiment_30d",
        ]

    def ollama_guarded_daily_columns(self) -> List[str]:
        return [
            "ollama_guarded_article_count_1d",
            "ollama_guarded_article_count_5d",
            "ollama_guarded_article_count_30d",
            "ollama_guarded_confidence_mean",
            "ollama_guarded_rumor_share",
            "ollama_guarded_event_family_unknown_share",
            "ollama_guarded_event_family_earnings_share",
            "ollama_guarded_event_family_dividend_share",
            "ollama_guarded_event_family_guidance_share",
            "ollama_guarded_event_family_capital_raise_or_debt_share",
            "ollama_guarded_event_family_mna_or_asset_share",
            "ollama_guarded_event_family_regulatory_or_legal_share",
            "ollama_guarded_event_family_other_company_event_share",
            "ollama_guarded_event_family_macro_or_sector_share",
            "ollama_guarded_impact_scope_unknown_share",
            "ollama_guarded_impact_scope_stock_share",
            "ollama_guarded_impact_scope_sector_share",
            "ollama_guarded_impact_scope_market_share",
            "ollama_guarded_impact_scope_macro_share",
            "ollama_guarded_source_authority_unknown_share",
            "ollama_guarded_source_authority_official_share",
            "ollama_guarded_source_authority_media_report_share",
            "ollama_guarded_source_authority_rumor_or_unsourced_share",
            "ollama_guarded_abstain_share",
            "ollama_guarded_parse_fail_share",
        ]

    def phobert_forward_looking_daily_columns(self) -> List[str]:
        return [
            "phobert_forward_looking_article_count_1d",
            "phobert_forward_looking_true_count_1d",
            "phobert_forward_looking_share",
            "phobert_forward_looking_prob_mean",
            "phobert_forward_looking_prob_sum",
            "phobert_forward_looking_confidence_mean",
            "phobert_forward_looking_article_count_5d",
            "phobert_forward_looking_article_count_30d",
            "phobert_forward_looking_prob_5d",
            "phobert_forward_looking_prob_30d",
        ]

    def phobert_article_scope_daily_columns(self) -> List[str]:
        return [
            "phobert_article_scope_article_count_1d",
            "phobert_article_scope_stock_news_count_1d",
            "phobert_article_scope_stock_news_share",
            "phobert_article_scope_stock_news_prob_mean",
            "phobert_article_scope_stock_news_prob_sum",
            "phobert_article_scope_confidence_mean",
            "phobert_article_scope_article_count_5d",
            "phobert_article_scope_article_count_30d",
            "phobert_article_scope_stock_news_prob_5d",
            "phobert_article_scope_stock_news_prob_30d",
        ]

    def phobert_source_type_daily_columns(self) -> List[str]:
        return [
            "phobert_source_type_article_count_1d",
            "phobert_source_type_official_or_regulatory_count_1d",
            "phobert_source_type_official_or_regulatory_share",
            "phobert_source_type_official_or_regulatory_prob_mean",
            "phobert_source_type_official_or_regulatory_prob_sum",
            "phobert_source_type_confidence_mean",
            "phobert_source_type_article_count_5d",
            "phobert_source_type_article_count_30d",
            "phobert_source_type_official_or_regulatory_prob_5d",
            "phobert_source_type_official_or_regulatory_prob_30d",
        ]

    def phobert_binary_head_split_strategy(self, head_name: str) -> str:
        value = getattr(self, f"phobert_{str(head_name)}_split_strategy_value", "time")
        normalized = str(value or "time").strip().lower()
        return normalized if normalized else "time"

    def phobert_binary_head_enable_class_weighting(self, head_name: str) -> bool:
        return bool(getattr(self, f"phobert_{str(head_name)}_enable_class_weighting", False))

    def phobert_binary_head_default_positive_threshold(self, head_name: str) -> float:
        _ = str(head_name)
        return float(self.phobert_binary_head_default_positive_threshold_value)

    def to_dict(self) -> Dict[str, object]:
        raw = asdict(self)
        return {key: str(value) if isinstance(value, Path) else value for key, value in raw.items()}


def get_default_config() -> NewsFeaturesConfig:
    config = NewsFeaturesConfig()
    config.ensure_directories()
    return config
