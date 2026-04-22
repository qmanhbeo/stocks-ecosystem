"""Build transformer-based daily embedding features from tagged news articles."""

from __future__ import annotations

import argparse
import json
from typing import Callable, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

from research_pipelines.news_features.config import NewsFeaturesConfig, get_default_config
from research_pipelines.news_features.io_utils import describe_path, update_manifest


EncoderFn = Callable[[list[str]], np.ndarray]


def _compose_embedding_text(row: pd.Series, max_chars: int) -> str:
    parts = [row.get("clean_title", ""), row.get("clean_summary", ""), row.get("clean_body_text", "")]
    text = " ".join(str(part).strip() for part in parts if str(part).strip())
    return text[:max_chars]


def _load_sentence_encoder(config: NewsFeaturesConfig) -> EncoderFn:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise ImportError(
            "sentence-transformers is required for build_embedding_features. Install project dependencies first."
        ) from exc

    model = SentenceTransformer(config.embedding_model_name)

    def _encode(texts: list[str]) -> np.ndarray:
        return np.asarray(
            model.encode(
                texts,
                batch_size=config.embedding_batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
        )

    return _encode


def _fit_pca_vectors(vectors: np.ndarray, output_dim: int, random_seed: int) -> tuple[PCA, np.ndarray]:
    if vectors.ndim != 2:
        raise ValueError("Expected a 2D embedding array for PCA fitting")
    components = max(1, min(output_dim, vectors.shape[0], vectors.shape[1]))
    pca = PCA(n_components=components, random_state=random_seed)
    reduced = pca.fit_transform(vectors)
    return pca, reduced


def _pad_reduced_vectors(vectors: np.ndarray, output_dim: int) -> np.ndarray:
    if vectors.shape[1] >= output_dim:
        return vectors[:, :output_dim]
    padding = np.zeros((vectors.shape[0], output_dim - vectors.shape[1]), dtype=float)
    return np.hstack([vectors, padding])


def _load_pca_fit_tickers() -> list[str]:
    try:
        from research_pipelines.supervised_label.split_utils import load_split_files
    except Exception:
        return []
    try:
        split_map = load_split_files()
    except Exception:
        return []
    return list(split_map.get("train", []))


def build_embedding_feature_dataframe(
    normalized_df: pd.DataFrame,
    tagged_df: pd.DataFrame,
    config: Optional[NewsFeaturesConfig] = None,
    encoder: Optional[EncoderFn] = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object], PCA]:
    config = config or get_default_config()
    if normalized_df.empty or tagged_df.empty:
        empty_daily = pd.DataFrame(columns=["ticker", "date", *config.embedding_columns()])
        empty_articles = pd.DataFrame(columns=["article_id", "ticker", "date", "url", "source"])
        metadata = {
            "embedding_model_name": config.embedding_model_name,
            "raw_embedding_dim": 0,
            "pca_output_dim": config.embedding_output_dim,
            "pca_fit_scope": "empty",
        }
        dummy_pca = PCA(n_components=1)
        dummy_pca.components_ = np.zeros((1, 1))
        dummy_pca.mean_ = np.zeros(1)
        dummy_pca.n_features_in_ = 1
        return empty_daily, empty_articles, metadata, dummy_pca

    merged = tagged_df.merge(
        normalized_df[
            ["article_id", "url", "date", "source", "clean_title", "clean_summary", "clean_body_text"]
        ],
        on=["article_id", "url", "date", "source"],
        how="left",
        validate="many_to_one",
    )
    merged["embedding_text"] = merged.apply(
        lambda row: _compose_embedding_text(row, config.embedding_text_max_chars), axis=1
    )
    merged = merged[merged["embedding_text"].str.len() > 0].reset_index(drop=True)
    if merged.empty:
        raise ValueError("No non-empty tagged articles available for embedding generation")

    encode = encoder or _load_sentence_encoder(config)
    raw_embeddings = np.asarray(encode(merged["embedding_text"].tolist()), dtype=float)
    if raw_embeddings.ndim != 2 or raw_embeddings.shape[0] != len(merged):
        raise ValueError("Encoder must return a 2D numpy array with one embedding per input article")

    raw_columns = [f"embed_raw_{index:03d}" for index in range(raw_embeddings.shape[1])]
    article_embeddings = merged[["article_id", "ticker", "date", "url", "source"]].copy()
    article_embeddings[raw_columns] = raw_embeddings

    daily_raw = article_embeddings.groupby(["ticker", "date"], as_index=False)[raw_columns].mean()
    fit_tickers = _load_pca_fit_tickers()
    if fit_tickers:
        fit_vectors = daily_raw.loc[daily_raw["ticker"].isin(fit_tickers), raw_columns].to_numpy(dtype=float)
    else:
        fit_vectors = np.empty((0, len(raw_columns)))
    if fit_vectors.size == 0:
        fit_vectors = daily_raw[raw_columns].to_numpy(dtype=float)

    pca, _ = _fit_pca_vectors(fit_vectors, config.embedding_output_dim, config.pca_random_seed)
    reduced = pca.transform(daily_raw[raw_columns].to_numpy(dtype=float))
    reduced = _pad_reduced_vectors(reduced, config.embedding_output_dim)

    embedding_columns = config.embedding_columns()
    daily_reduced = daily_raw[["ticker", "date"]].copy()
    daily_reduced[embedding_columns] = reduced
    daily_reduced = daily_reduced.sort_values(["ticker", "date"]).reset_index(drop=True)

    metadata = {
        "embedding_model_name": config.embedding_model_name,
        "raw_embedding_dim": int(raw_embeddings.shape[1]),
        "pca_output_dim": config.embedding_output_dim,
        "pca_fitted_components": int(min(config.embedding_output_dim, pca.n_components_)),
        "pca_fit_scope": "supervised_label_train_tickers" if fit_tickers else "all_tagged_tickers",
        "fit_ticker_count": int(len(fit_tickers)),
        "article_count": int(len(merged)),
        "daily_row_count": int(len(daily_reduced)),
    }
    return daily_reduced, article_embeddings, metadata, pca


def build_embedding_feature_exports(
    config: Optional[NewsFeaturesConfig] = None,
    encoder: Optional[EncoderFn] = None,
) -> pd.DataFrame:
    config = config or get_default_config()
    normalized = pd.read_parquet(config.normalized_path()) if config.normalized_path().exists() else pd.DataFrame()
    tagged = pd.read_parquet(config.tagged_path()) if config.tagged_path().exists() else pd.DataFrame()
    daily_reduced, article_embeddings, metadata, pca = build_embedding_feature_dataframe(
        normalized_df=normalized,
        tagged_df=tagged,
        config=config,
        encoder=encoder,
    )
    article_embeddings.to_parquet(config.article_embeddings_path(), index=False)
    daily_reduced.to_parquet(config.embedding_dataset_path(), index=False)
    joblib.dump(pca, config.pca_model_path())
    config.embedding_metadata_path().write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    update_manifest(
        config=config,
        embedding_feature_rows=int(len(daily_reduced)),
        embedding_dataset_path=describe_path(config.embedding_dataset_path(), config=config),
    )
    print(f"Built {len(daily_reduced)} embedding feature rows -> {config.embedding_dataset_path()}")
    return daily_reduced


def build_arg_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(description="Build transformer-based news embedding features.")


def main() -> None:
    build_arg_parser().parse_args()
    build_embedding_feature_exports()


if __name__ == "__main__":
    main()
