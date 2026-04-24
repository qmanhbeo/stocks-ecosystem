import numpy as np
import pandas as pd
import tempfile
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from research_pipelines.news_features import __main__ as news_main
from research_pipelines.news_features.config import NewsFeaturesConfig
from research_pipelines.news_features.core.aggregate_daily_features import (
    aggregate_daily_feature_dataframe,
    aggregate_daily_feature_exports,
)
from research_pipelines.news_features.core.build_embedding_features import (
    build_embedding_feature_dataframe,
    build_embedding_feature_exports,
)
from research_pipelines.news_features.core.build_ollama_guarded_features import (
    build_ollama_guarded_article_feature_dataframe,
    build_ollama_guarded_daily_feature_dataframe,
    build_ollama_guarded_feature_exports,
)
from research_pipelines.news_features.core.build_phobert_forward_looking_features import (
    build_phobert_forward_looking_feature_exports,
)
from research_pipelines.news_features.core.build_phobert_sentiment_features import (
    build_phobert_article_sentiment_dataframe,
    build_phobert_daily_sentiment_dataframe,
    build_phobert_sentiment_exports,
)
from research_pipelines.news_features.core.train_phobert_forward_looking import (
    build_phobert_forward_looking_stage_dataset,
    build_phobert_forward_looking_teacher_labels,
    train_phobert_forward_looking_candidates,
)
from research_pipelines.news_features.core.build_tabular_features import (
    build_tabular_feature_dataframe,
    build_tabular_feature_exports,
)
from src import run_summary as run_summary_module


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


def _normalized_with_untagged_df() -> pd.DataFrame:
    return pd.concat(
        [
            _normalized_df(),
            pd.DataFrame(
                [
                    {
                        "article_id": "a4",
                        "source": "cafef",
                        "url": "https://cafef.vn/a4.chn",
                        "clean_title": "Bai viet khong gan ticker",
                        "clean_summary": "",
                        "clean_body_text": "chi dung de kiem tra cache dau vao",
                        "date": "2026-03-13",
                    }
                ]
            ),
        ],
        ignore_index=True,
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


def _fake_forward_looking_scorer(texts: list[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for text in texts:
        lower = text.lower()
        is_forward = any(token in lower for token in ("du kien", "sap toi", "ke hoach", "tang truong", "but pha"))
        confidence = 0.84 if is_forward else 0.79
        forward_prob = 0.84 if is_forward else 0.18
        rows.append(
            {
                "phobert_forward_looking_input_text_length": len(text),
                "phobert_forward_looking_token_count": len(text.split()) + 2,
                "phobert_forward_looking_predicted_label": (
                    "FORWARD_LOOKING" if is_forward else "NOT_FORWARD_LOOKING"
                ),
                "phobert_forward_looking_is_forward_looking": is_forward,
                "phobert_forward_looking_confidence": confidence,
                "phobert_forward_looking_prob_not_forward": 1.0 - forward_prob,
                "phobert_forward_looking_prob_forward": forward_prob,
            }
        )
    return rows


def _deterministic_text_encoder(texts: list[str]) -> np.ndarray:
    rows = []
    for text in texts:
        checksum = float(sum(ord(char) for char in text))
        rows.append(
            [
                float(len(text)),
                float(len(text.split())),
                checksum % 997.0,
                (checksum % 17.0) / 17.0,
            ]
        )
    return np.asarray(rows, dtype=float)


def _temp_config(tmp_path: Path, **overrides: object) -> NewsFeaturesConfig:
    root = tmp_path
    kwargs = {
        "repo_root": root / "alpha-research-lab",
        "package_root": root / "alpha-research-lab" / "research_pipelines" / "news_features",
        "data_root": root / "data",
        "model_checkpoints_root": root / "data" / "model_checkpoints",
        "feature_root": root / "data" / "features" / "news",
        "raw_news_dir": root / "data" / "news",
        "raw_stock_dir": root / "data" / "stock",
        "artifacts_dir": root / "data" / "features" / "news",
        "configs_dir": root / "alpha-research-lab" / "research_pipelines" / "news_features" / "configs",
        "normalized_dir": root / "data" / "features" / "news" / "normalized",
        "tagged_dir": root / "data" / "features" / "news" / "tagged",
        "datasets_dir": root / "data" / "features" / "news" / "datasets",
        "predictions_dir": root / "data" / "features" / "news" / "predictions",
        "manifest_path": root / "data" / "features" / "news" / "manifest.json",
    }
    kwargs.update(overrides)
    config = NewsFeaturesConfig(**kwargs)
    config.ensure_directories()
    return config


@pytest.fixture(autouse=True)
def _redirect_run_summaries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_summary_dir = tmp_path / "alpha-research-lab" / "artifacts" / "run_summaries"
    monkeypatch.setattr(run_summary_module, "RUN_SUMMARY_DIR", run_summary_dir)


def _fake_guarded_raw_response(article: dict[str, object]) -> str:
    responses = {
        "a1": json.dumps(
            {
                "id": "a1",
                "tickers": ["ZZZ"],
                "confidence": 2,
                "is_forward_looking": True,
                "is_rumor": False,
            }
        ),
        "a2": json.dumps(
            {
                "id": "a2",
                "confidence": "medium",
                "is_forward_looking": "maybe",
                "is_rumor": "no",
            }
        ),
        "a3": "not valid json",
    }
    return responses[str(article["article_id"])]


def _write_forward_looking_teacher_fixture(config: NewsFeaturesConfig, *, include_untagged: bool = False) -> None:
    raw_dir = config.source_raw_dir(config.default_source)
    cache_dir = config.data_root / "llm_cache"
    raw_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    raw_by_day = {
        "2026-03-10": [
            {
                "article_id": "a1",
                "source": "cafef",
                "url": "https://cafef.vn/a1.chn",
                "title": "ACB du kien mo rong tang truong",
                "summary": "ke hoach sap toi",
                "body_text": "ACB dat muc tieu loi nhuan nam toi",
                "published_at": "2026-03-10T02:00:00Z",
            }
        ],
        "2026-03-11": [
            {
                "article_id": "a2",
                "source": "cafef",
                "url": "https://cafef.vn/a2.chn",
                "title": "HPG cong bo ket qua hien tai",
                "summary": "cap nhat doanh nghiep hien trang",
                "body_text": "Khong co du bao moi cho co phieu nhung la tin tai chinh",
                "published_at": "2026-03-11T02:00:00Z",
            }
        ],
        "2026-03-12": [
            {
                "article_id": "a3",
                "source": "cafef",
                "url": "https://cafef.vn/a3.chn",
                "title": "ACB va HPG nhac den ke hoach quy sau",
                "summary": "du kien sap toi",
                "body_text": "Doanh nghiep dat ke hoach tiep tuc mo rong",
                "published_at": "2026-03-12T02:00:00Z",
            }
        ],
    }
    cache_by_day = {
        "2026-03-10": [{"id": "2026-03-10_0001", "is_forward_looking": True}],
        "2026-03-11": [{"id": "2026-03-11_0001", "is_forward_looking": False}],
        "2026-03-12": [{"id": "2026-03-12_0001", "is_forward_looking": True}],
    }
    if include_untagged:
        raw_by_day["2026-03-13"] = [
            {
                "article_id": "a4",
                "source": "cafef",
                "url": "https://cafef.vn/a4.chn",
                "title": "Bai viet du bao nhung khong gan ticker",
                "summary": "du kien sap toi",
                "body_text": "Van la doanh nghiep va tai chinh nhung khong co ma",
                "published_at": "2026-03-13T02:00:00Z",
            }
        ]
        cache_by_day["2026-03-13"] = [{"id": "2026-03-13_0001", "is_forward_looking": True}]

    for day, rows in raw_by_day.items():
        path = raw_dir / f"{day}.jsonl"
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    for day, rows in cache_by_day.items():
        path = cache_dir / f"{day}.jsonl"
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _write_forward_looking_winner_fixture(config: NewsFeaturesConfig) -> None:
    model_dir = (
        config.phobert_forward_looking_model_artifacts_dir()
        / "runs"
        / "fixture_run"
        / "phobert_base"
        / "model"
    )
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "config.json").write_text(
        json.dumps(
            {
                "id2label": {"0": "NOT_FORWARD_LOOKING", "1": "FORWARD_LOOKING"},
                "label2id": {"NOT_FORWARD_LOOKING": 0, "FORWARD_LOOKING": 1},
            }
        ),
        encoding="utf-8",
    )
    latest_winner = {
        "candidate_name": "phobert_base",
        "model_name": "vinai/phobert-base",
        "model_dir": str(model_dir),
    }
    training_manifest = {
        "status": "complete",
        "run_id": "fixture_run",
        "winner": latest_winner,
    }
    config.phobert_forward_looking_latest_winner_path().write_text(
        json.dumps(latest_winner, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    config.phobert_forward_looking_training_manifest_path().write_text(
        json.dumps(training_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_forward_looking_legacy_winner_fixture(config: NewsFeaturesConfig) -> None:
    legacy_root = config.phobert_forward_looking_legacy_model_artifacts_dir()
    model_dir = legacy_root / "runs" / "legacy_run" / "phobert_base" / "model"
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "config.json").write_text(
        json.dumps(
            {
                "id2label": {"0": "NOT_FORWARD_LOOKING", "1": "FORWARD_LOOKING"},
                "label2id": {"NOT_FORWARD_LOOKING": 0, "FORWARD_LOOKING": 1},
            }
        ),
        encoding="utf-8",
    )
    state_path = model_dir.parent / "candidate_state.json"
    metrics_path = model_dir.parent / "metrics.json"
    latest_winner = {
        "candidate_name": "phobert_base",
        "model_name": "vinai/phobert-base",
        "model_dir": str(model_dir),
    }
    training_manifest = {
        "status": "complete",
        "run_id": "legacy_run",
        "winner": latest_winner,
        "candidates": {
            "phobert_base": {
                "candidate_name": "phobert_base",
                "model_name": "vinai/phobert-base",
                "output_dir": str(model_dir.parent),
                "model_dir": str(model_dir),
                "state_path": str(state_path),
                "metrics_path": str(metrics_path),
                "status": "complete",
            }
        },
    }
    candidate_state = {
        "candidate_name": "phobert_base",
        "model_dir": str(model_dir),
        "state_path": str(state_path),
        "metrics_path": str(metrics_path),
        "status": "complete",
    }
    state_path.write_text(json.dumps(candidate_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    metrics_path.write_text(json.dumps(candidate_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (legacy_root / "latest_winner.json").write_text(
        json.dumps(latest_winner, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (legacy_root / "training_manifest.json").write_text(
        json.dumps(training_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_build_tabular_features_creates_daily_counts_and_rolling_windows():
    config = _config()
    tabular = build_tabular_feature_dataframe(_normalized_df(), _tagged_df(), config=config)
    acb = tabular.loc[tabular["ticker"] == "ACB"].reset_index(drop=True)
    assert acb["date"].tolist() == ["2026-03-10", "2026-03-11", "2026-03-12"]
    assert acb["news_article_count_1d"].tolist() == [1.0, 0.0, 1.0]
    assert acb["news_article_count_3d"].tolist() == [1.0, 1.0, 2.0]


def test_build_tabular_feature_exports_matches_dataframe_builder_and_reuses_stage_cache(tmp_path):
    config = _temp_config(tmp_path)
    _normalized_df().to_parquet(config.normalized_path(), index=False)
    _tagged_df().to_parquet(config.tagged_path(), index=False)

    expected = build_tabular_feature_dataframe(_normalized_df(), _tagged_df(), config=config)
    first = build_tabular_feature_exports(config=config)
    stage_mtime_ns = config.tabular_stage_path().stat().st_mtime_ns
    second = build_tabular_feature_exports(config=config)
    stage_manifest = json.loads(config.tabular_stage_manifest_path().read_text(encoding="utf-8"))

    pd.testing.assert_frame_equal(first, expected, check_dtype=False)
    pd.testing.assert_frame_equal(second, expected, check_dtype=False)
    assert stage_manifest["status"] == "complete"
    assert stage_manifest["stage_rows"] == len(_tagged_df())
    assert config.tabular_stage_path().stat().st_mtime_ns == stage_mtime_ns


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


def test_build_embedding_feature_exports_matches_dataframe_builder_on_small_sample(tmp_path):
    config = _temp_config(tmp_path, embedding_checkpoint_rows=2)
    _normalized_df().to_parquet(config.normalized_path(), index=False)
    _tagged_df().to_parquet(config.tagged_path(), index=False)

    expected_daily, expected_articles, expected_metadata, _ = build_embedding_feature_dataframe(
        normalized_df=_normalized_df(),
        tagged_df=_tagged_df(),
        config=config,
        encoder=_deterministic_text_encoder,
    )
    actual_daily = build_embedding_feature_exports(
        config=config,
        encoder=_deterministic_text_encoder,
    )
    actual_articles = pd.read_parquet(config.article_embeddings_path())
    actual_metadata = json.loads(config.embedding_metadata_path().read_text(encoding="utf-8"))

    pd.testing.assert_frame_equal(
        actual_daily.sort_values(["ticker", "date"]).reset_index(drop=True),
        expected_daily.sort_values(["ticker", "date"]).reset_index(drop=True),
        check_dtype=False,
    )
    pd.testing.assert_frame_equal(
        actual_articles.sort_values(["article_id", "ticker", "date", "url", "source"]).reset_index(drop=True),
        expected_articles.sort_values(["article_id", "ticker", "date", "url", "source"]).reset_index(drop=True),
        check_dtype=False,
    )
    assert actual_metadata["raw_embedding_dim"] == expected_metadata["raw_embedding_dim"]
    assert actual_metadata["daily_row_count"] == expected_metadata["daily_row_count"]
    assert actual_metadata["article_count"] == expected_metadata["article_count"]
    assert json.loads(config.embedding_checkpoint_manifest_path().read_text(encoding="utf-8"))["status"] == "complete"
    assert list(config.embedding_checkpoint_dir().glob("article_shard_*.parquet")) == []


def test_build_embedding_feature_exports_resume_from_checkpoints(tmp_path):
    config = _temp_config(tmp_path, embedding_checkpoint_rows=2)
    _normalized_df().to_parquet(config.normalized_path(), index=False)
    _tagged_df().to_parquet(config.tagged_path(), index=False)

    partial = build_embedding_feature_exports(
        config=config,
        encoder=_deterministic_text_encoder,
        checkpoint_batch_limit=1,
    )
    checkpoint_manifest = json.loads(config.embedding_checkpoint_manifest_path().read_text(encoding="utf-8"))

    assert partial.empty
    assert checkpoint_manifest["status"] == "in_progress"
    assert checkpoint_manifest["completed_batch_count"] == 1
    assert len(list(config.embedding_checkpoint_dir().glob("article_shard_*.parquet"))) == 1
    assert not config.article_embeddings_path().exists()
    assert not config.embedding_dataset_path().exists()

    resumed = build_embedding_feature_exports(
        config=config,
        encoder=_deterministic_text_encoder,
    )
    checkpoint_manifest = json.loads(config.embedding_checkpoint_manifest_path().read_text(encoding="utf-8"))

    assert len(resumed) > 0
    assert checkpoint_manifest["status"] == "complete"
    assert config.article_embeddings_path().exists()
    assert config.embedding_dataset_path().exists()
    assert list(config.embedding_checkpoint_dir().glob("article_shard_*.parquet")) == []


def test_build_embedding_feature_exports_reuses_tagged_only_input_cache(tmp_path):
    config = _temp_config(tmp_path, embedding_checkpoint_rows=2)
    _normalized_with_untagged_df().to_parquet(config.normalized_path(), index=False)
    _tagged_df().to_parquet(config.tagged_path(), index=False)

    build_embedding_feature_exports(
        config=config,
        encoder=_deterministic_text_encoder,
        checkpoint_batch_limit=1,
    )
    input_cache = pd.read_parquet(config.embedding_input_articles_path())
    input_manifest = json.loads(config.embedding_input_manifest_path().read_text(encoding="utf-8"))
    input_mtime_ns = config.embedding_input_articles_path().stat().st_mtime_ns

    assert sorted(input_cache["article_id"].tolist()) == ["a1", "a2", "a3", "a3"]
    assert input_manifest["matched_article_count"] == 3
    assert input_manifest["input_rows"] == 4

    build_embedding_feature_exports(
        config=config,
        encoder=_deterministic_text_encoder,
    )

    assert config.embedding_input_articles_path().stat().st_mtime_ns == input_mtime_ns


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


def test_build_ollama_guarded_features_use_tagged_tickers_and_abstain_on_parse_fail():
    config = _config()

    article_rows, metadata = build_ollama_guarded_article_feature_dataframe(
        _normalized_df(),
        _tagged_df(),
        config=config,
        raw_response_fn=_fake_guarded_raw_response,
    )

    assert len(article_rows) == 4
    assert metadata["local_model_name"] == config.ollama_guarded_model_name
    assert set(article_rows.loc[article_rows["article_id"] == "a1", "ticker"]) == {"ACB"}
    assert article_rows.loc[article_rows["article_id"] == "a1", "ollama_guarded_confidence"].iloc[0] == 2.0
    assert article_rows.loc[article_rows["article_id"] == "a2", "ollama_guarded_confidence"].iloc[0] == 1.0
    assert pd.isna(
        article_rows.loc[article_rows["article_id"] == "a2", "ollama_guarded_is_forward_looking"].iloc[0]
    )
    assert article_rows.loc[article_rows["article_id"] == "a2", "ollama_guarded_is_rumor"].iloc[0] is False

    abstained = article_rows.loc[article_rows["article_id"] == "a3"].reset_index(drop=True)
    assert abstained["local_parse_ok"].tolist() == [False, False]
    assert abstained["local_abstained"].tolist() == [True, True]
    assert abstained["local_error"].tolist() == ["json_parse_fail", "json_parse_fail"]
    assert abstained["ollama_guarded_confidence"].isna().all()


def test_build_ollama_guarded_daily_features_create_rolling_counts_and_coverage_shares():
    config = _config()
    article_rows, _ = build_ollama_guarded_article_feature_dataframe(
        _normalized_df(),
        _tagged_df(),
        config=config,
        raw_response_fn=_fake_guarded_raw_response,
    )

    daily = build_ollama_guarded_daily_feature_dataframe(article_rows, config=config)
    acb = daily.loc[daily["ticker"] == "ACB"].reset_index(drop=True)
    hpg = daily.loc[daily["ticker"] == "HPG"].reset_index(drop=True)

    assert acb["date"].tolist() == ["2026-03-10", "2026-03-11", "2026-03-12"]
    assert acb["ollama_guarded_article_count_1d"].tolist() == [1.0, 0.0, 1.0]
    assert acb["ollama_guarded_article_count_5d"].tolist() == [1.0, 1.0, 2.0]
    assert acb["ollama_guarded_confidence_mean"].tolist() == [2.0, 0.0, 0.0]
    assert acb["ollama_guarded_forward_looking_share"].tolist() == [1.0, 0.0, 0.0]
    assert acb["ollama_guarded_abstain_share"].tolist() == [0.0, 0.0, 1.0]
    assert acb["ollama_guarded_parse_fail_share"].tolist() == [0.0, 0.0, 1.0]

    assert hpg["date"].tolist() == ["2026-03-11", "2026-03-12"]
    assert hpg["ollama_guarded_confidence_mean"].tolist() == [1.0, 0.0]
    assert hpg["ollama_guarded_rumor_share"].tolist() == [0.0, 0.0]


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


def test_aggregate_daily_features_phobert_only_keeps_full_schema():
    config = _config()
    article_rows, _ = build_phobert_article_sentiment_dataframe(
        _normalized_df(),
        _tagged_df(),
        config=config,
        scorer=_fake_phobert_scorer,
        scorer_metadata={"phobert_model_id": "fake-phobert"},
    )
    phobert_daily = build_phobert_daily_sentiment_dataframe(article_rows, config=config)

    combined = aggregate_daily_feature_dataframe(
        pd.DataFrame(),
        pd.DataFrame(),
        phobert_df=phobert_daily,
        config=config,
    )

    assert set(config.default_merge_columns()) <= set(combined.columns)
    acb_2026_03_10 = combined.loc[(combined["ticker"] == "ACB") & (combined["date"] == "2026-03-10")]
    assert acb_2026_03_10["phobert_article_count_1d"].iloc[0] == 1.0
    assert acb_2026_03_10["news_article_count_1d"].iloc[0] == 0.0
    assert acb_2026_03_10["news_embed_00"].iloc[0] == 0.0


def test_build_phobert_exports_writes_datasets_and_manifest_entries(tmp_path):
    config = _temp_config(tmp_path)

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


def test_build_phobert_exports_resume_from_checkpoints(tmp_path):
    config = _temp_config(tmp_path, phobert_checkpoint_rows=2)

    _normalized_df().assign(published_at="2026-03-10T09:00:00+07:00").to_parquet(config.normalized_path(), index=False)
    _tagged_df().to_parquet(config.tagged_path(), index=False)

    partial_daily = build_phobert_sentiment_exports(
        config=config,
        scorer=_fake_phobert_scorer,
        scorer_metadata={"phobert_model_id": "fake-phobert"},
        checkpoint_batch_limit=1,
    )
    checkpoint_manifest = json.loads(config.phobert_checkpoint_manifest_path().read_text(encoding="utf-8"))
    shard_paths = list(config.phobert_checkpoint_dir().glob("article_shard_*.parquet"))

    assert partial_daily.empty
    assert checkpoint_manifest["status"] == "in_progress"
    assert checkpoint_manifest["completed_batch_count"] == 1
    assert len(shard_paths) == 1
    assert not config.phobert_article_sentiment_path().exists()
    assert not config.phobert_ticker_day_sentiment_path().exists()

    resumed_daily = build_phobert_sentiment_exports(
        config=config,
        scorer=_fake_phobert_scorer,
        scorer_metadata={"phobert_model_id": "fake-phobert"},
    )
    checkpoint_manifest = json.loads(config.phobert_checkpoint_manifest_path().read_text(encoding="utf-8"))

    assert len(resumed_daily) > 0
    assert checkpoint_manifest["status"] == "complete"
    assert config.phobert_article_sentiment_path().exists()
    assert config.phobert_ticker_day_sentiment_path().exists()
    assert list(config.phobert_checkpoint_dir().glob("article_shard_*.parquet")) == []


def test_build_phobert_exports_materializes_tagged_only_input_cache(tmp_path):
    config = _temp_config(tmp_path, phobert_checkpoint_rows=2)

    _normalized_with_untagged_df().assign(published_at="2026-03-10T09:00:00+07:00").to_parquet(
        config.normalized_path(),
        index=False,
    )
    _tagged_df().to_parquet(config.tagged_path(), index=False)

    build_phobert_sentiment_exports(
        config=config,
        scorer=_fake_phobert_scorer,
        scorer_metadata={"phobert_model_id": "fake-phobert"},
        checkpoint_batch_limit=1,
    )

    input_cache = pd.read_parquet(config.phobert_input_articles_path())
    input_manifest = json.loads(config.phobert_input_manifest_path().read_text(encoding="utf-8"))
    checkpoint_manifest = json.loads(config.phobert_checkpoint_manifest_path().read_text(encoding="utf-8"))

    assert sorted(input_cache["article_id"].tolist()) == ["a1", "a2", "a3"]
    assert input_manifest["input_rows"] == 3
    assert checkpoint_manifest["total_batches"] == 2


def test_build_ollama_guarded_exports_materialize_tagged_only_input_cache_and_reuse_it(tmp_path):
    config = _temp_config(
        tmp_path,
        ollama_guarded_checkpoint_rows=2,
        ollama_guarded_model_name="fake-guarded",
    )
    _normalized_with_untagged_df().assign(published_at="2026-03-10T09:00:00+07:00").to_parquet(
        config.normalized_path(),
        index=False,
    )
    _tagged_df().to_parquet(config.tagged_path(), index=False)

    build_ollama_guarded_feature_exports(
        config=config,
        raw_response_fn=_fake_guarded_raw_response,
        checkpoint_batch_limit=1,
    )

    input_cache = pd.read_parquet(config.ollama_guarded_input_articles_path())
    input_manifest = json.loads(config.ollama_guarded_input_manifest_path().read_text(encoding="utf-8"))
    checkpoint_manifest = json.loads(config.ollama_guarded_checkpoint_manifest_path().read_text(encoding="utf-8"))
    input_mtime_ns = config.ollama_guarded_input_articles_path().stat().st_mtime_ns

    assert sorted(input_cache["article_id"].tolist()) == ["a1", "a2", "a3"]
    assert input_manifest["input_rows"] == 3
    assert checkpoint_manifest["total_batches"] == 2

    build_ollama_guarded_feature_exports(
        config=config,
        raw_response_fn=_fake_guarded_raw_response,
    )

    assert config.ollama_guarded_input_articles_path().stat().st_mtime_ns == input_mtime_ns


def test_build_ollama_guarded_exports_resume_from_checkpoints_and_match_direct_builder(tmp_path):
    config = _temp_config(
        tmp_path,
        ollama_guarded_checkpoint_rows=2,
        ollama_guarded_model_name="fake-guarded",
    )
    normalized = _normalized_df().assign(published_at="2026-03-10T09:00:00+07:00")
    tagged = _tagged_df()
    normalized.to_parquet(config.normalized_path(), index=False)
    tagged.to_parquet(config.tagged_path(), index=False)

    expected_articles, _ = build_ollama_guarded_article_feature_dataframe(
        normalized,
        tagged,
        config=config,
        raw_response_fn=_fake_guarded_raw_response,
    )
    expected_daily = build_ollama_guarded_daily_feature_dataframe(expected_articles, config=config)

    partial = build_ollama_guarded_feature_exports(
        config=config,
        raw_response_fn=_fake_guarded_raw_response,
        checkpoint_batch_limit=1,
    )
    checkpoint_manifest = json.loads(config.ollama_guarded_checkpoint_manifest_path().read_text(encoding="utf-8"))

    assert partial.empty
    assert checkpoint_manifest["status"] == "in_progress"
    assert checkpoint_manifest["completed_batch_count"] == 1
    assert len(list(config.ollama_guarded_checkpoint_dir().glob("article_shard_*.parquet"))) == 1
    assert not config.ollama_guarded_article_features_path().exists()
    assert not config.ollama_guarded_ticker_day_features_path().exists()

    resumed = build_ollama_guarded_feature_exports(
        config=config,
        raw_response_fn=_fake_guarded_raw_response,
    )
    checkpoint_manifest = json.loads(config.ollama_guarded_checkpoint_manifest_path().read_text(encoding="utf-8"))
    actual_articles = pd.read_parquet(config.ollama_guarded_article_features_path())

    pd.testing.assert_frame_equal(
        actual_articles.sort_values(["article_id", "ticker", "date"]).reset_index(drop=True),
        expected_articles.sort_values(["article_id", "ticker", "date"]).reset_index(drop=True),
        check_dtype=False,
    )
    pd.testing.assert_frame_equal(
        resumed.sort_values(["ticker", "date"]).reset_index(drop=True),
        expected_daily.sort_values(["ticker", "date"]).reset_index(drop=True),
        check_dtype=False,
    )
    assert checkpoint_manifest["status"] == "complete"
    assert list(config.ollama_guarded_checkpoint_dir().glob("article_shard_*.parquet")) == []
    assert not (tmp_path / "data" / "llm_cache").exists()


def test_build_phobert_forward_looking_teacher_labels_reconstructs_article_ids_from_cache_days(tmp_path):
    config = _temp_config(tmp_path)
    _write_forward_looking_teacher_fixture(config)

    teacher = build_phobert_forward_looking_teacher_labels(config=config)
    manifest = json.loads(config.phobert_forward_looking_teacher_manifest_path().read_text(encoding="utf-8"))

    assert teacher["article_id"].tolist() == ["a1", "a2", "a3"]
    assert teacher["phobert_forward_looking_label"].tolist() == [1, 0, 1]
    assert manifest["teacher_rows"] == 3
    assert manifest["cache_days_seen"] == 3
    assert manifest["missing_raw_article_count"] == 0


def test_build_phobert_forward_looking_stage_dataset_keeps_tagged_articles_and_assigns_date_splits(tmp_path):
    config = _temp_config(tmp_path, phobert_checkpoint_rows=2)
    _normalized_with_untagged_df().assign(published_at="2026-03-10T09:00:00+07:00").to_parquet(
        config.normalized_path(),
        index=False,
    )
    _tagged_df().to_parquet(config.tagged_path(), index=False)
    _write_forward_looking_teacher_fixture(config, include_untagged=True)

    stage = build_phobert_forward_looking_stage_dataset(config=config)
    manifest = json.loads(config.phobert_forward_looking_stage_manifest_path().read_text(encoding="utf-8"))

    assert stage["article_id"].tolist() == ["a1", "a2", "a3"]
    assert stage["phobert_forward_looking_label"].tolist() == [1, 0, 1]
    assert stage["phobert_forward_looking_split"].tolist() == ["train", "val", "test"]
    assert manifest["untagged_teacher_article_count"] == 1
    assert manifest["split_counts"] == {"train": 1, "val": 1, "test": 1}
    assert config.phobert_input_articles_path().exists()


def test_build_phobert_forward_looking_feature_exports_resume_from_checkpoints(tmp_path):
    config = _temp_config(
        tmp_path,
        phobert_forward_looking_publish_checkpoint_rows=2,
        repo_root=tmp_path,
        package_root=tmp_path / "pkg",
        configs_dir=tmp_path / "configs",
    )
    _normalized_df().assign(published_at="2026-03-10T09:00:00+07:00").to_parquet(config.normalized_path(), index=False)
    _tagged_df().to_parquet(config.tagged_path(), index=False)
    _write_forward_looking_winner_fixture(config)

    partial = build_phobert_forward_looking_feature_exports(
        config=config,
        scorer=_fake_forward_looking_scorer,
        scorer_metadata={"phobert_forward_looking_model_id": "fake-forward-looking"},
        checkpoint_batch_limit=1,
    )
    checkpoint_manifest = json.loads(
        config.phobert_forward_looking_publish_checkpoint_manifest_path().read_text(encoding="utf-8")
    )

    assert partial.empty
    assert checkpoint_manifest["status"] == "in_progress"
    assert checkpoint_manifest["completed_batch_count"] == 1
    assert len(list(config.phobert_forward_looking_publish_checkpoint_dir().glob("article_shard_*.parquet"))) == 1
    assert not config.phobert_forward_looking_article_features_path().exists()
    assert not config.phobert_forward_looking_ticker_day_features_path().exists()

    resumed = build_phobert_forward_looking_feature_exports(
        config=config,
        scorer=_fake_forward_looking_scorer,
        scorer_metadata={"phobert_forward_looking_model_id": "fake-forward-looking"},
    )
    checkpoint_manifest = json.loads(
        config.phobert_forward_looking_publish_checkpoint_manifest_path().read_text(encoding="utf-8")
    )
    actual_articles = pd.read_parquet(config.phobert_forward_looking_article_features_path())

    assert checkpoint_manifest["status"] == "complete"
    assert list(config.phobert_forward_looking_publish_checkpoint_dir().glob("article_shard_*.parquet")) == []
    assert len(resumed) > 0
    assert set(config.phobert_forward_looking_daily_columns()) <= set(resumed.columns)
    assert actual_articles["phobert_forward_looking_is_forward_looking"].sum() == 3
    acb = resumed.loc[resumed["ticker"] == "ACB"].reset_index(drop=True)
    assert acb["phobert_forward_looking_article_count_1d"].tolist() == [1.0, 0.0, 1.0]
    assert acb["phobert_forward_looking_prob_5d"].tolist() == [0.84, 0.84, 1.68]


def test_config_migrates_legacy_forward_looking_checkpoint_root_into_data_root(tmp_path):
    config = _temp_config(tmp_path)
    _write_forward_looking_legacy_winner_fixture(config)

    migrated_root = config.ensure_phobert_forward_looking_model_state()
    manifest = json.loads(config.phobert_forward_looking_training_manifest_path().read_text(encoding="utf-8"))
    winner = json.loads(config.phobert_forward_looking_latest_winner_path().read_text(encoding="utf-8"))
    candidate_state = json.loads(
        (migrated_root / "runs" / "legacy_run" / "phobert_base" / "candidate_state.json").read_text(encoding="utf-8")
    )

    assert migrated_root == config.phobert_forward_looking_model_artifacts_dir()
    assert str(config.model_checkpoints_root) in manifest["candidates"]["phobert_base"]["model_dir"]
    assert str(config.model_checkpoints_root) in winner["model_dir"]
    assert str(config.model_checkpoints_root) in candidate_state["model_dir"]
    assert config.phobert_forward_looking_legacy_model_artifacts_dir().exists()


def test_config_raises_when_new_and_legacy_forward_looking_roots_diverge(tmp_path):
    config = _temp_config(tmp_path)
    _write_forward_looking_legacy_winner_fixture(config)
    _write_forward_looking_winner_fixture(config)

    with pytest.raises(RuntimeError, match="Divergent PhoBERT forward-looking checkpoint roots"):
        config.ensure_phobert_forward_looking_model_state()


def test_train_phobert_forward_looking_candidates_run_sequentially_select_winner_and_resume(tmp_path):
    config = _temp_config(
        tmp_path,
        phobert_forward_looking_candidate_names=["base_a", "base_b"],
        phobert_forward_looking_candidate_model_names=["model/a", "model/b"],
    )
    _normalized_df().assign(published_at="2026-03-10T09:00:00+07:00").to_parquet(config.normalized_path(), index=False)
    _tagged_df().to_parquet(config.tagged_path(), index=False)
    _write_forward_looking_teacher_fixture(config)
    build_phobert_forward_looking_stage_dataset(config=config)

    calls: list[str] = []

    def _fake_trainer(candidate, _config, _stage_path, output_dir, _stage_summary):
        calls.append(candidate.name)
        model_dir = output_dir / "model"
        model_dir.mkdir(parents=True, exist_ok=True)
        (model_dir / "weights.bin").write_text("ok", encoding="utf-8")
        score = 0.55 if candidate.name == "base_a" else 0.80
        result = {
            "candidate_name": candidate.name,
            "model_name": candidate.model_name,
            "model_dir": str(model_dir),
            "state_path": str(output_dir / "candidate_state.json"),
            "metrics_path": str(output_dir / "metrics.json"),
            "parameter_count": 10 if candidate.name == "base_a" else 8,
            "device": "cpu",
            "dtype": "float32",
            "best_epoch": 1,
            "epoch_history": [{"epoch": 1}],
            "train_summary": {"metrics": {"f1": score - 0.05}},
            "val_summary": {"metrics": {"f1": score, "roc_auc": score}},
            "test_summary": {"metrics": {"f1": score - 0.02, "roc_auc": score - 0.01}},
            "training_args": {"num_epochs": 1},
        }
        Path(result["state_path"]).write_text(json.dumps(result), encoding="utf-8")
        Path(result["metrics_path"]).write_text(json.dumps(result), encoding="utf-8")
        return result

    summary = train_phobert_forward_looking_candidates(config=config, trainer_fn=_fake_trainer)
    manifest = json.loads(config.phobert_forward_looking_training_manifest_path().read_text(encoding="utf-8"))
    winner = json.loads(config.phobert_forward_looking_latest_winner_path().read_text(encoding="utf-8"))
    status = json.loads(config.phobert_forward_looking_job_status_path().read_text(encoding="utf-8"))

    assert calls == ["base_a", "base_b"]
    assert summary["status"] == "complete"
    assert manifest["status"] == "complete"
    assert winner["candidate_name"] == "base_b"
    assert status["job"] == "phobert_forward_looking_train"
    assert status["status"] == "complete"
    assert status["phase"] == "winner_selection"
    assert status["progress"]["completed_candidates"] == 2
    assert status["progress"]["failed_candidates"] == 0
    assert status["progress"]["winner"]["candidate_name"] == "base_b"
    assert status["artifacts"]["status_file"].endswith("artifacts/job_status/phobert_forward_looking_train.json")
    assert status["artifacts"]["training_manifest"].endswith("training_manifest.json")

    calls.clear()
    resumed = train_phobert_forward_looking_candidates(config=config, trainer_fn=_fake_trainer)

    assert resumed["status"] == "complete"
    assert calls == []


def test_train_phobert_forward_looking_candidates_reuses_current_stage_manifest_without_loading_stage_dataframe(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
):
    config = _temp_config(
        tmp_path,
        phobert_forward_looking_candidate_names=["base_a"],
        phobert_forward_looking_candidate_model_names=["model/a"],
    )
    _normalized_df().assign(published_at="2026-03-10T09:00:00+07:00").to_parquet(config.normalized_path(), index=False)
    _tagged_df().to_parquet(config.tagged_path(), index=False)
    _write_forward_looking_teacher_fixture(config)
    build_phobert_forward_looking_stage_dataset(config=config)

    original_read_parquet = pd.read_parquet
    stage_path = config.phobert_forward_looking_stage_path()

    def _guard_stage_read(path, *args, **kwargs):
        if Path(path) == stage_path:
            raise AssertionError("training preflight should not reload the full stage parquet")
        return original_read_parquet(path, *args, **kwargs)

    monkeypatch.setattr(pd, "read_parquet", _guard_stage_read)

    def _fake_trainer(candidate, _config, _stage_path, output_dir, _stage_summary):
        model_dir = output_dir / "model"
        model_dir.mkdir(parents=True, exist_ok=True)
        (model_dir / "weights.bin").write_text("ok", encoding="utf-8")
        result = {
            "candidate_name": candidate.name,
            "model_name": candidate.model_name,
            "model_dir": str(model_dir),
            "state_path": str(output_dir / "candidate_state.json"),
            "metrics_path": str(output_dir / "metrics.json"),
            "parameter_count": 10,
            "device": "cpu",
            "dtype": "float32",
            "best_epoch": 1,
            "epoch_history": [{"epoch": 1}],
            "train_summary": {"metrics": {"f1": 0.6}},
            "val_summary": {"metrics": {"f1": 0.65, "roc_auc": 0.66}},
            "test_summary": {"metrics": {"f1": 0.64, "roc_auc": 0.65}},
            "training_args": {"num_epochs": 1},
        }
        Path(result["state_path"]).write_text(json.dumps(result), encoding="utf-8")
        Path(result["metrics_path"]).write_text(json.dumps(result), encoding="utf-8")
        return result

    summary = train_phobert_forward_looking_candidates(config=config, trainer_fn=_fake_trainer)

    assert summary["status"] == "complete"


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


def test_aggregate_daily_feature_exports_supports_phobert_only_refresh(tmp_path):
    config = _temp_config(
        tmp_path,
        repo_root=tmp_path,
        package_root=tmp_path / "pkg",
        configs_dir=tmp_path / "configs",
    )

    article_rows, _ = build_phobert_article_sentiment_dataframe(
        _normalized_df(),
        _tagged_df(),
        config=config,
        scorer=_fake_phobert_scorer,
        scorer_metadata={"phobert_model_id": "fake-phobert"},
    )
    phobert_daily = build_phobert_daily_sentiment_dataframe(article_rows, config=config)
    phobert_daily.to_parquet(config.phobert_ticker_day_sentiment_path(), index=False)

    combined = aggregate_daily_feature_exports(config=config, sources=["phobert"])

    assert set(config.default_merge_columns()) <= set(combined.columns)
    assert config.combined_dataset_path().exists()
    assert config.per_ticker_feature_path("ACB").exists()
    exported = pd.read_parquet(config.per_ticker_feature_path("ACB"))
    assert "phobert_sentiment_score_sum" in exported.columns
    assert "news_article_count_1d" in exported.columns
    assert exported.loc[exported["date"] == "2026-03-10", "news_article_count_1d"].iloc[0] == 0.0


def test_aggregate_daily_feature_exports_partial_overlay_preserves_existing_columns(tmp_path):
    config = _temp_config(
        tmp_path,
        repo_root=tmp_path,
        package_root=tmp_path / "pkg",
        configs_dir=tmp_path / "configs",
    )
    existing = pd.DataFrame(
        [
            {
                "ticker": "ACB",
                "date": "2026-03-10",
                "news_article_count_1d": 7.0,
                "news_embed_00": 3.5,
            }
        ]
    )
    existing.to_parquet(config.combined_dataset_path(), index=False)
    forward_daily = pd.DataFrame(
        [
            {
                "ticker": "ACB",
                "date": "2026-03-10",
                "phobert_forward_looking_article_count_1d": 1.0,
                "phobert_forward_looking_true_count_1d": 1.0,
                "phobert_forward_looking_share": 1.0,
                "phobert_forward_looking_prob_mean": 0.9,
                "phobert_forward_looking_prob_sum": 0.9,
                "phobert_forward_looking_confidence_mean": 0.9,
                "phobert_forward_looking_article_count_5d": 1.0,
                "phobert_forward_looking_article_count_30d": 1.0,
                "phobert_forward_looking_prob_5d": 0.9,
                "phobert_forward_looking_prob_30d": 0.9,
            }
        ]
    )
    forward_daily.to_parquet(config.phobert_forward_looking_ticker_day_features_path(), index=False)

    combined = aggregate_daily_feature_exports(config=config, sources=["phobert_forward_looking"])

    row = combined.iloc[0]
    assert row["news_article_count_1d"] == 7.0
    assert row["news_embed_00"] == 3.5
    assert row["phobert_forward_looking_prob_sum"] == 0.9


def test_news_main_requires_full_rebuild(monkeypatch):
    monkeypatch.setattr("sys.argv", ["news_features"])
    with pytest.raises(SystemExit, match="--full-rebuild"):
        news_main.main()


def test_news_main_full_rebuild_calls_streamed_builders(monkeypatch):
    calls: list[tuple[str, dict[str, object]]] = []
    config = SimpleNamespace(artifacts_dir=Path("/tmp/news-artifacts"))

    def _record(name: str):
        def _inner(*args, **kwargs):
            calls.append((name, kwargs))
            return pd.DataFrame()

        return _inner

    monkeypatch.setattr("sys.argv", ["news_features", "--full-rebuild"])
    monkeypatch.setattr(news_main, "get_default_config", lambda: config)
    monkeypatch.setattr(news_main, "preprocess_news_exports", _record("preprocess"))
    monkeypatch.setattr(news_main, "tag_articles_exports", _record("tag"))
    monkeypatch.setattr(news_main, "build_tabular_feature_exports", _record("tabular"))
    monkeypatch.setattr(news_main, "build_phobert_sentiment_exports", _record("phobert"))
    monkeypatch.setattr(news_main, "build_embedding_feature_exports", _record("embedding"))
    monkeypatch.setattr(news_main, "aggregate_daily_feature_exports", _record("aggregate"))

    news_main.main()

    assert [name for name, _ in calls] == [
        "preprocess",
        "tag",
        "tabular",
        "phobert",
        "embedding",
        "aggregate",
    ]
    assert calls[2][1]["return_dataframe"] is False
    assert calls[4][1]["return_dataframe"] is False
