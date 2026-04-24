"""Build transformer-based daily embedding features from tagged news articles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
from time import perf_counter
from typing import Callable, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

from research_pipelines.news_features.config import NewsFeaturesConfig, get_default_config
from research_pipelines.news_features.io_utils import describe_path, update_manifest, write_parquet_atomic


EncoderFn = Callable[[list[str]], np.ndarray]

EMBEDDING_INPUT_COLUMNS = ["article_id", "ticker", "date", "url", "source", "embedding_text"]
EMBEDDING_ARTICLE_COLUMNS = ["article_id", "ticker", "date", "url", "source"]
EMBEDDING_INPUT_CACHE_VERSION = 1
EMBEDDING_CHECKPOINT_VERSION = 1


def _empty_daily_dataframe(config: NewsFeaturesConfig) -> pd.DataFrame:
    return pd.DataFrame(columns=["ticker", "date", *config.embedding_columns()])


def _empty_article_embeddings_dataframe() -> pd.DataFrame:
    return pd.DataFrame(columns=EMBEDDING_ARTICLE_COLUMNS)


def _build_dummy_pca() -> PCA:
    dummy = PCA(n_components=1)
    dummy.components_ = np.zeros((1, 1))
    dummy.mean_ = np.zeros(1)
    dummy.n_features_in_ = 1
    dummy.n_components_ = 1
    dummy.explained_variance_ = np.zeros(1)
    dummy.explained_variance_ratio_ = np.zeros(1)
    dummy.singular_values_ = np.zeros(1)
    return dummy


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
        metadata = {
            "embedding_model_name": config.embedding_model_name,
            "raw_embedding_dim": 0,
            "pca_output_dim": config.embedding_output_dim,
            "pca_fit_scope": "empty",
        }
        return _empty_daily_dataframe(config), _empty_article_embeddings_dataframe(), metadata, _build_dummy_pca()

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
    article_embeddings = merged[EMBEDDING_ARTICLE_COLUMNS].copy()
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


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".json", delete=False) as handle:
        temp_path = Path(handle.name)
    try:
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


def _dump_joblib_atomic(value: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=path.suffix or ".joblib", delete=False) as handle:
        temp_path = Path(handle.name)
    try:
        joblib.dump(value, temp_path)
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


def _path_checkpoint_signature(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    stat = path.stat()
    return {
        "path": str(path),
        "exists": True,
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
    }


def _normalize_date_value(value: object) -> str:
    if pd.isna(value):
        return ""
    try:
        return pd.Timestamp(value).strftime("%Y-%m-%d")
    except Exception:
        return str(value)


def _embedding_join_key(article_id: object, url: object, date: object, source: object) -> str:
    return "\x1f".join(
        [
            "" if pd.isna(article_id) else str(article_id),
            "" if pd.isna(url) else str(url),
            _normalize_date_value(date),
            "" if pd.isna(source) else str(source),
        ]
    )


def _load_embedding_input_manifest(config: NewsFeaturesConfig) -> dict[str, object]:
    path = config.embedding_input_manifest_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_embedding_input_manifest(config: NewsFeaturesConfig, payload: dict[str, object]) -> None:
    _write_json_atomic(config.embedding_input_manifest_path(), payload)


def _load_embedding_checkpoint_manifest(config: NewsFeaturesConfig) -> dict[str, object]:
    path = config.embedding_checkpoint_manifest_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_embedding_checkpoint_manifest(config: NewsFeaturesConfig, payload: dict[str, object]) -> None:
    _write_json_atomic(config.embedding_checkpoint_manifest_path(), payload)


def _clear_embedding_checkpoint_shards(config: NewsFeaturesConfig) -> None:
    checkpoint_dir = config.embedding_checkpoint_dir()
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    for path in checkpoint_dir.glob("article_shard_*.parquet"):
        path.unlink(missing_ok=True)


def _embedding_input_source_signature(
    config: NewsFeaturesConfig,
    *,
    normalized_rows: int,
    tagged_rows: int,
) -> dict[str, object]:
    return {
        "input_cache_version": EMBEDDING_INPUT_CACHE_VERSION,
        "normalized_rows": int(normalized_rows),
        "tagged_rows": int(tagged_rows),
        "embedding_text_max_chars": int(config.embedding_text_max_chars),
        "normalized_input": _path_checkpoint_signature(config.normalized_path()),
        "tagged_input": _path_checkpoint_signature(config.tagged_path()),
    }


def _embedding_run_signature(
    config: NewsFeaturesConfig,
    *,
    input_rows: int,
    input_source_signature: dict[str, object],
) -> dict[str, object]:
    return {
        "checkpoint_version": EMBEDDING_CHECKPOINT_VERSION,
        "embedding_model_name": config.embedding_model_name,
        "embedding_batch_size": int(config.embedding_batch_size),
        "embedding_checkpoint_rows": int(config.embedding_checkpoint_rows),
        "embedding_text_max_chars": int(config.embedding_text_max_chars),
        "embedding_output_dim": int(config.embedding_output_dim),
        "pca_random_seed": int(config.pca_random_seed),
        "embedding_input_rows": int(input_rows),
        "embedding_input": _path_checkpoint_signature(config.embedding_input_articles_path()),
        "embedding_input_source_signature": input_source_signature,
    }


def _load_embedding_tagged_keys(config: NewsFeaturesConfig) -> tuple[set[str], int]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("Checkpointed embedding builds require pyarrow.") from exc

    if not config.tagged_path().exists():
        return set(), 0

    tagged_file = pq.ParquetFile(config.tagged_path())
    tagged_rows = int(tagged_file.metadata.num_rows)
    keys: set[str] = set()
    batch_size = 50000
    scanned_rows = 0
    progress_interval = 100000
    for batch in tagged_file.iter_batches(
        batch_size=batch_size,
        columns=["article_id", "url", "date", "source"],
    ):
        batch_df = batch.to_pandas()
        for row in batch_df.itertuples(index=False):
            keys.add(_embedding_join_key(row.article_id, row.url, row.date, row.source))
        scanned_rows += int(len(batch_df))
        if (
            scanned_rows == len(batch_df)
            or scanned_rows % progress_interval == 0
            or scanned_rows >= tagged_rows
        ):
            print(
                f"Embedding input cache scan: collected tagged_keys={len(keys)} from "
                f"tagged_rows={scanned_rows}/{tagged_rows}",
                flush=True,
            )
    return keys, tagged_rows


def _build_embedding_text_lookup(
    *,
    config: NewsFeaturesConfig,
    tagged_keys: set[str],
) -> tuple[dict[str, str], int]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("Checkpointed embedding builds require pyarrow.") from exc

    if not config.normalized_path().exists():
        return {}, 0

    normalized_file = pq.ParquetFile(config.normalized_path())
    normalized_rows = int(normalized_file.metadata.num_rows)
    requested_columns = [
        "article_id",
        "url",
        "date",
        "source",
        "clean_title",
        "clean_summary",
        "clean_body_text",
    ]
    available_columns = set(normalized_file.schema_arrow.names)
    columns = [column for column in requested_columns if column in available_columns]
    lookup: dict[str, str] = {}
    scanned_rows = 0
    batch_size = 50000
    progress_interval = 100000
    for batch in normalized_file.iter_batches(batch_size=batch_size, columns=columns):
        batch_df = batch.to_pandas()
        for column in requested_columns:
            if column not in batch_df.columns:
                batch_df[column] = ""
        for row in batch_df.itertuples(index=False):
            key = _embedding_join_key(row.article_id, row.url, row.date, row.source)
            if key not in tagged_keys:
                continue
            if key in lookup:
                raise ValueError("Embedding feature build expected normalized article keys to be unique")
            lookup[key] = _compose_embedding_text(pd.Series(row._asdict()), config.embedding_text_max_chars)
        scanned_rows += int(len(batch_df))
        if (
            scanned_rows == len(batch_df)
            or scanned_rows % progress_interval == 0
            or scanned_rows >= normalized_rows
        ):
            print(
                f"Embedding input cache: scanned normalized_rows={scanned_rows}/{normalized_rows}; "
                f"matched_articles={len(lookup)}",
                flush=True,
            )
    return lookup, normalized_rows


def _prepare_embedding_input_cache(config: NewsFeaturesConfig) -> dict[str, object]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("Checkpointed embedding builds require pyarrow.") from exc

    normalized_rows = 0
    tagged_rows = 0
    if config.normalized_path().exists():
        normalized_rows = int(pq.ParquetFile(config.normalized_path()).metadata.num_rows)
    if config.tagged_path().exists():
        tagged_rows = int(pq.ParquetFile(config.tagged_path()).metadata.num_rows)
    source_signature = _embedding_input_source_signature(
        config,
        normalized_rows=normalized_rows,
        tagged_rows=tagged_rows,
    )
    input_manifest = _load_embedding_input_manifest(config)
    input_path = config.embedding_input_articles_path()
    if (
        input_path.exists()
        and input_manifest.get("source_signature") == source_signature
        and input_manifest.get("status") == "complete"
    ):
        cached_rows = int(input_manifest.get("input_rows", 0))
        print(
            f"Embedding input cache reuse: input_rows={cached_rows}, "
            f"matched_articles={int(input_manifest.get('matched_article_count', 0))}",
            flush=True,
        )
        return input_manifest

    tagged_keys, tagged_rows = _load_embedding_tagged_keys(config)
    text_lookup, normalized_rows = _build_embedding_text_lookup(config=config, tagged_keys=tagged_keys)
    source_signature = _embedding_input_source_signature(
        config,
        normalized_rows=normalized_rows,
        tagged_rows=tagged_rows,
    )

    input_schema = pa.schema(
        [
            ("article_id", pa.string()),
            ("ticker", pa.string()),
            ("date", pa.string()),
            ("url", pa.string()),
            ("source", pa.string()),
            ("embedding_text", pa.string()),
        ]
    )
    input_writer = None
    temp_input_path: Optional[Path] = None
    input_rows = 0
    try:
        with tempfile.NamedTemporaryFile(dir=config.datasets_dir, suffix=".parquet", delete=False) as handle:
            temp_input_path = Path(handle.name)

        if config.tagged_path().exists():
            tagged_file = pq.ParquetFile(config.tagged_path())
            batch_size = 50000
            scanned_rows = 0
            progress_interval = 100000
            for batch in tagged_file.iter_batches(
                batch_size=batch_size,
                columns=["article_id", "ticker", "date", "url", "source"],
            ):
                batch_df = batch.to_pandas()
                input_batch_rows: list[dict[str, object]] = []
                for row in batch_df.itertuples(index=False):
                    key = _embedding_join_key(row.article_id, row.url, row.date, row.source)
                    embedding_text = text_lookup.get(key, "")
                    if not embedding_text:
                        continue
                    input_batch_rows.append(
                        {
                            "article_id": "" if pd.isna(row.article_id) else str(row.article_id),
                            "ticker": "" if pd.isna(row.ticker) else str(row.ticker),
                            "date": _normalize_date_value(row.date),
                            "url": "" if pd.isna(row.url) else str(row.url),
                            "source": "" if pd.isna(row.source) else str(row.source),
                            "embedding_text": embedding_text,
                        }
                    )
                if input_batch_rows:
                    input_batch_df = pd.DataFrame(input_batch_rows, columns=EMBEDDING_INPUT_COLUMNS)
                    table = pa.Table.from_pandas(input_batch_df, preserve_index=False, schema=input_schema)
                    if input_writer is None:
                        input_writer = pq.ParquetWriter(temp_input_path, schema=input_schema)
                    input_writer.write_table(table)
                    input_rows += int(len(input_batch_df))
                scanned_rows += int(len(batch_df))
                if (
                    scanned_rows == len(batch_df)
                    or scanned_rows % progress_interval == 0
                    or scanned_rows >= tagged_rows
                ):
                    print(
                        f"Embedding input cache write: input_rows={input_rows}, "
                        f"scanned_tagged_rows={scanned_rows}/{tagged_rows}",
                        flush=True,
                    )

        if input_writer is None:
            empty_input = pd.DataFrame(columns=EMBEDDING_INPUT_COLUMNS)
            write_parquet_atomic(empty_input, temp_input_path, index=False)
        else:
            input_writer.close()
            input_writer = None

        temp_input_path.replace(input_path)
    finally:
        if input_writer is not None:
            input_writer.close()
        if temp_input_path is not None and temp_input_path.exists():
            temp_input_path.unlink(missing_ok=True)

    input_manifest = {
        "status": "complete",
        "source_signature": source_signature,
        "input_rows": int(input_rows),
        "matched_article_count": int(len(text_lookup)),
        "input_path": describe_path(input_path, config=config),
        "completed_at_utc": pd.Timestamp.utcnow().isoformat(),
    }
    _write_embedding_input_manifest(config, input_manifest)
    return input_manifest


def _parquet_row_count(path: Path) -> int:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("Checkpointed embedding builds require pyarrow.") from exc
    if not path.exists():
        return 0
    return int(pq.ParquetFile(path).metadata.num_rows)


def _write_empty_embedding_outputs(config: NewsFeaturesConfig) -> dict[str, object]:
    metadata = {
        "embedding_model_name": config.embedding_model_name,
        "raw_embedding_dim": 0,
        "pca_output_dim": config.embedding_output_dim,
        "pca_fit_scope": "empty",
        "fit_ticker_count": 0,
        "article_count": 0,
        "daily_row_count": 0,
    }
    write_parquet_atomic(_empty_article_embeddings_dataframe(), config.article_embeddings_path(), index=False)
    write_parquet_atomic(_empty_daily_dataframe(config), config.embedding_dataset_path(), index=False)
    _dump_joblib_atomic(_build_dummy_pca(), config.pca_model_path())
    _write_json_atomic(config.embedding_metadata_path(), metadata)
    return metadata


def _encode_embedding_batch(
    batch_df: pd.DataFrame,
    *,
    encoder: EncoderFn,
) -> tuple[pd.DataFrame, int]:
    raw_embeddings = np.asarray(encoder(batch_df["embedding_text"].astype(str).tolist()), dtype=float)
    if raw_embeddings.ndim != 2 or raw_embeddings.shape[0] != len(batch_df):
        raise ValueError("Encoder must return a 2D numpy array with one embedding per input article")
    raw_columns = [f"embed_raw_{index:03d}" for index in range(raw_embeddings.shape[1])]
    shard_df = batch_df[EMBEDDING_ARTICLE_COLUMNS].copy()
    shard_df[raw_columns] = raw_embeddings
    return shard_df, int(raw_embeddings.shape[1])


def _finalize_article_embeddings_from_shards(
    *,
    config: NewsFeaturesConfig,
    raw_columns: list[str],
) -> None:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("Checkpointed embedding builds require pyarrow.") from exc

    schema = pa.schema(
        [
            ("article_id", pa.string()),
            ("ticker", pa.string()),
            ("date", pa.string()),
            ("url", pa.string()),
            ("source", pa.string()),
            *[(column, pa.float64()) for column in raw_columns],
        ]
    )
    writer = None
    temp_output_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(dir=config.datasets_dir, suffix=".parquet", delete=False) as handle:
            temp_output_path = Path(handle.name)
        for shard_path in sorted(config.embedding_checkpoint_dir().glob("article_shard_*.parquet")):
            shard_df = pd.read_parquet(shard_path)
            table = pa.Table.from_pandas(shard_df[EMBEDDING_ARTICLE_COLUMNS + raw_columns], preserve_index=False, schema=schema)
            if writer is None:
                writer = pq.ParquetWriter(temp_output_path, schema=schema)
            writer.write_table(table)
        if writer is None:
            write_parquet_atomic(_empty_article_embeddings_dataframe(), temp_output_path, index=False)
        else:
            writer.close()
            writer = None
        temp_output_path.replace(config.article_embeddings_path())
    finally:
        if writer is not None:
            writer.close()
        if temp_output_path is not None and temp_output_path.exists():
            temp_output_path.unlink(missing_ok=True)


def _aggregate_daily_raw_vectors(
    *,
    config: NewsFeaturesConfig,
    raw_columns: list[str],
) -> pd.DataFrame:
    daily_state: dict[tuple[str, str], dict[str, object]] = {}
    for shard_path in sorted(config.embedding_checkpoint_dir().glob("article_shard_*.parquet")):
        shard_df = pd.read_parquet(shard_path)
        if shard_df.empty:
            continue
        for (ticker, date), group in shard_df.groupby(["ticker", "date"], sort=False):
            key = ("" if pd.isna(ticker) else str(ticker), _normalize_date_value(date))
            state = daily_state.setdefault(
                key,
                {
                    "count": 0,
                    "sum": np.zeros(len(raw_columns), dtype=float),
                },
            )
            vectors = group[raw_columns].to_numpy(dtype=float)
            state["count"] += int(vectors.shape[0])
            state["sum"] += vectors.sum(axis=0)

    rows: list[dict[str, object]] = []
    for (ticker, date), state in sorted(daily_state.items()):
        count = max(int(state["count"]), 1)
        row = {"ticker": ticker, "date": date}
        row.update(
            {
                column: float(value)
                for column, value in zip(raw_columns, (state["sum"] / count).tolist())
            }
        )
        rows.append(row)
    return pd.DataFrame(rows, columns=["ticker", "date", *raw_columns])


def _finalize_embedding_outputs(
    *,
    config: NewsFeaturesConfig,
    checkpoint_manifest: dict[str, object],
    return_dataframe: bool,
) -> pd.DataFrame:
    raw_embedding_dim = int(checkpoint_manifest.get("raw_embedding_dim", 0))
    if raw_embedding_dim <= 0:
        _write_empty_embedding_outputs(config)
        return _empty_daily_dataframe(config) if return_dataframe else _empty_daily_dataframe(config)

    raw_columns = [f"embed_raw_{index:03d}" for index in range(raw_embedding_dim)]
    _finalize_article_embeddings_from_shards(config=config, raw_columns=raw_columns)
    daily_raw = _aggregate_daily_raw_vectors(config=config, raw_columns=raw_columns)
    if daily_raw.empty:
        metadata = _write_empty_embedding_outputs(config)
        checkpoint_manifest.update(
            {
                "status": "complete",
                "daily_feature_rows": 0,
                "completed_at_utc": pd.Timestamp.utcnow().isoformat(),
            }
        )
        _write_embedding_checkpoint_manifest(config, checkpoint_manifest)
        return _empty_daily_dataframe(config) if return_dataframe else _empty_daily_dataframe(config)

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

    daily_reduced = daily_raw[["ticker", "date"]].copy()
    daily_reduced[config.embedding_columns()] = reduced
    daily_reduced = daily_reduced.sort_values(["ticker", "date"]).reset_index(drop=True)

    metadata = {
        "embedding_model_name": config.embedding_model_name,
        "raw_embedding_dim": raw_embedding_dim,
        "pca_output_dim": config.embedding_output_dim,
        "pca_fitted_components": int(min(config.embedding_output_dim, pca.n_components_)),
        "pca_fit_scope": "supervised_label_train_tickers" if fit_tickers else "all_tagged_tickers",
        "fit_ticker_count": int(len(fit_tickers)),
        "article_count": _parquet_row_count(config.article_embeddings_path()),
        "daily_row_count": int(len(daily_reduced)),
    }

    write_parquet_atomic(daily_reduced, config.embedding_dataset_path(), index=False)
    _dump_joblib_atomic(pca, config.pca_model_path())
    _write_json_atomic(config.embedding_metadata_path(), metadata)
    _clear_embedding_checkpoint_shards(config)

    checkpoint_manifest.update(
        {
            "status": "complete",
            "daily_feature_rows": int(len(daily_reduced)),
            "completed_at_utc": pd.Timestamp.utcnow().isoformat(),
        }
    )
    _write_embedding_checkpoint_manifest(config, checkpoint_manifest)
    return daily_reduced if return_dataframe else _empty_daily_dataframe(config)


def build_embedding_feature_exports(
    config: Optional[NewsFeaturesConfig] = None,
    encoder: Optional[EncoderFn] = None,
    *,
    checkpoint_batch_limit: Optional[int] = None,
    return_dataframe: bool = True,
) -> pd.DataFrame:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("Checkpointed embedding builds require pyarrow.") from exc

    config = config or get_default_config()
    overall_start = perf_counter()

    input_start = perf_counter()
    input_manifest = _prepare_embedding_input_cache(config)
    input_elapsed = perf_counter() - input_start
    input_rows = int(input_manifest.get("input_rows", 0))
    print(f"Embedding input cache ready in {input_elapsed:.1f}s: input_rows={input_rows}", flush=True)

    input_source_signature = dict(input_manifest.get("source_signature") or {})
    run_signature = _embedding_run_signature(
        config,
        input_rows=input_rows,
        input_source_signature=input_source_signature,
    )

    if input_rows == 0:
        _clear_embedding_checkpoint_shards(config)
        _write_empty_embedding_outputs(config)
        checkpoint_manifest = {
            "status": "complete",
            "run_signature": run_signature,
            "input_rows": 0,
            "total_batches": 0,
            "completed_batch_count": 0,
            "raw_embedding_dim": 0,
            "daily_feature_rows": 0,
            "completed_at_utc": pd.Timestamp.utcnow().isoformat(),
        }
        _write_embedding_checkpoint_manifest(config, checkpoint_manifest)
        update_manifest(
            config=config,
            embedding_feature_rows=0,
            embedding_dataset_path=describe_path(config.embedding_dataset_path(), config=config),
        )
        return _empty_daily_dataframe(config) if return_dataframe else _empty_daily_dataframe(config)

    checkpoint_manifest = _load_embedding_checkpoint_manifest(config)
    if checkpoint_manifest and checkpoint_manifest.get("run_signature") != run_signature:
        _clear_embedding_checkpoint_shards(config)
        checkpoint_manifest = {}

    outputs_exist = (
        config.article_embeddings_path().exists()
        and config.embedding_dataset_path().exists()
        and config.embedding_metadata_path().exists()
        and config.pca_model_path().exists()
    )
    if (
        checkpoint_manifest.get("status") == "complete"
        and checkpoint_manifest.get("run_signature") == run_signature
        and outputs_exist
    ):
        print("Embedding checkpoint reuse: outputs already complete for current input/model signature", flush=True)
        update_manifest(
            config=config,
            embedding_feature_rows=_parquet_row_count(config.embedding_dataset_path()),
            embedding_dataset_path=describe_path(config.embedding_dataset_path(), config=config),
        )
        if return_dataframe:
            return pd.read_parquet(config.embedding_dataset_path())
        return _empty_daily_dataframe(config)

    encode = encoder or _load_sentence_encoder(config)
    input_file = pq.ParquetFile(config.embedding_input_articles_path())
    total_batches = max(
        (input_rows + max(int(config.embedding_checkpoint_rows), 1) - 1) // max(int(config.embedding_checkpoint_rows), 1),
        1,
    )
    if not checkpoint_manifest:
        checkpoint_manifest = {
            "status": "in_progress",
            "run_signature": run_signature,
            "input_rows": int(input_rows),
            "total_batches": int(total_batches),
            "completed_batch_count": 0,
            "completed_batches": {},
            "raw_embedding_dim": 0,
            "started_at_utc": pd.Timestamp.utcnow().isoformat(),
        }
        _write_embedding_checkpoint_manifest(config, checkpoint_manifest)

    completed_batches = {
        int(batch_index): str(shard_name)
        for batch_index, shard_name in dict(checkpoint_manifest.get("completed_batches") or {}).items()
        if config.embedding_checkpoint_shard_path(int(batch_index)).exists()
    }
    checkpoint_manifest["completed_batches"] = {str(key): value for key, value in sorted(completed_batches.items())}
    checkpoint_manifest["completed_batch_count"] = int(len(completed_batches))
    _write_embedding_checkpoint_manifest(config, checkpoint_manifest)

    processed_new_batches = 0
    batch_start = perf_counter()
    progress_interval = 1 if total_batches <= 10 else 25
    for batch_index, batch in enumerate(
        input_file.iter_batches(batch_size=max(int(config.embedding_checkpoint_rows), 1), columns=EMBEDDING_INPUT_COLUMNS),
        start=1,
    ):
        shard_path = config.embedding_checkpoint_shard_path(batch_index)
        if batch_index in completed_batches and shard_path.exists():
            if (
                batch_index == 1
                or batch_index % progress_interval == 0
                or batch_index == total_batches
            ):
                print(
                    f"Embedding checkpoint progress: reused batch {batch_index}/{total_batches}; "
                    f"completed={len(completed_batches)}/{total_batches}",
                    flush=True,
                )
            continue

        batch_df = batch.to_pandas()
        shard_df, raw_embedding_dim = _encode_embedding_batch(batch_df, encoder=encode)
        if checkpoint_manifest.get("raw_embedding_dim") and int(checkpoint_manifest["raw_embedding_dim"]) != raw_embedding_dim:
            raise ValueError("Embedding checkpoint shards disagree on raw embedding dimension")
        checkpoint_manifest["raw_embedding_dim"] = int(raw_embedding_dim)
        write_parquet_atomic(shard_df, shard_path, index=False)

        completed_batches[batch_index] = shard_path.name
        checkpoint_manifest["completed_batches"] = {str(key): value for key, value in sorted(completed_batches.items())}
        checkpoint_manifest["completed_batch_count"] = int(len(completed_batches))
        checkpoint_manifest["status"] = "in_progress"
        checkpoint_manifest["updated_at_utc"] = pd.Timestamp.utcnow().isoformat()
        _write_embedding_checkpoint_manifest(config, checkpoint_manifest)

        processed_new_batches += 1
        if (
            batch_index == 1
            or batch_index % progress_interval == 0
            or batch_index == total_batches
        ):
            print(
                f"Embedding checkpoint progress: processed batch {batch_index}/{total_batches}; "
                f"completed={len(completed_batches)}/{total_batches}",
                flush=True,
            )
        if checkpoint_batch_limit is not None and processed_new_batches >= int(checkpoint_batch_limit):
            break

    batch_elapsed = perf_counter() - batch_start
    if int(len(completed_batches)) != int(total_batches):
        checkpoint_manifest["status"] = "in_progress"
        checkpoint_manifest["updated_at_utc"] = pd.Timestamp.utcnow().isoformat()
        _write_embedding_checkpoint_manifest(config, checkpoint_manifest)
        print(
            f"Embedding checkpoint paused after {batch_elapsed:.1f}s: completed={len(completed_batches)}/{total_batches}",
            flush=True,
        )
        return _empty_daily_dataframe(config) if return_dataframe else _empty_daily_dataframe(config)

    finalize_start = perf_counter()
    daily_reduced = _finalize_embedding_outputs(
        config=config,
        checkpoint_manifest=checkpoint_manifest,
        return_dataframe=return_dataframe,
    )
    finalize_elapsed = perf_counter() - finalize_start
    update_manifest(
        config=config,
        embedding_feature_rows=int(len(daily_reduced)) if return_dataframe else _parquet_row_count(config.embedding_dataset_path()),
        embedding_dataset_path=describe_path(config.embedding_dataset_path(), config=config),
    )
    overall_elapsed = perf_counter() - overall_start
    print(
        f"Embedding timing summary: input={input_elapsed:.1f}s, checkpoint={batch_elapsed:.1f}s, "
        f"finalize={finalize_elapsed:.1f}s, total={overall_elapsed:.1f}s",
        flush=True,
    )
    print(f"Built embedding feature rows -> {config.embedding_dataset_path()}")
    return daily_reduced if return_dataframe else _empty_daily_dataframe(config)


def build_arg_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(description="Build transformer-based news embedding features.")


def main() -> None:
    build_arg_parser().parse_args()
    build_embedding_feature_exports(return_dataframe=False)


if __name__ == "__main__":
    main()
