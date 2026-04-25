"""Shared contract for PhoBERT binary local heads beyond sentiment."""

from __future__ import annotations

from dataclasses import dataclass
import json
from hashlib import md5
from pathlib import Path
from typing import Callable, Optional, Sequence

import numpy as np
import pandas as pd

from research_pipelines.news_features.config import NewsFeaturesConfig
from research_pipelines.news_features.io_utils import describe_path
from src.run_summary import write_run_summary


BinaryHeadTeacherLabelFn = Callable[[dict[str, object]], Optional[int]]
BinaryHeadTrainerFn = Callable[["BinaryHeadSpec", NewsFeaturesConfig, Path, Path, dict[str, object]], dict[str, object]]


@dataclass(frozen=True)
class BinaryHeadSpec:
    name: str
    dataset_prefix: str
    positive_label_name: str
    negative_label_name: str
    label_source_name: str
    summary_prefix: str
    teacher_label_fn: BinaryHeadTeacherLabelFn

    @property
    def job_name(self) -> str:
        return f"{self.dataset_prefix}_train"

    @property
    def publish_job_name(self) -> str:
        return f"{self.dataset_prefix}_publish"


def _article_scope_teacher_label(raw_record: dict[str, object]) -> Optional[int]:
    impact_scope = str(raw_record.get("impact_scope") or "").strip().lower()
    macro_theme = raw_record.get("macro_theme")
    tickers = raw_record.get("tickers") or []
    if impact_scope in {"stock", "sector"}:
        return 1
    if impact_scope in {"market"}:
        return 0
    if macro_theme not in (None, "") and macro_theme != [] and macro_theme != {}:
        return 0
    if isinstance(tickers, list):
        clean = [str(value).strip() for value in tickers if str(value).strip()]
        if len(clean) > 1:
            return 0
        if len(clean) == 1:
            return 1
    return None


def _source_type_teacher_label(raw_record: dict[str, object]) -> Optional[int]:
    authority = str(raw_record.get("source_authority") or "").strip().lower()
    if authority in {"official", "management"}:
        return 1
    if authority in {"media_report", "analyst", "rumor_source", "unclear"}:
        return 0
    return None


ARTICLE_SCOPE_SPEC = BinaryHeadSpec(
    name="article_scope",
    dataset_prefix="phobert_article_scope",
    positive_label_name="stock_news",
    negative_label_name="market_news",
    label_source_name="llm_cache_article_scope",
    summary_prefix="news_article_scope",
    teacher_label_fn=_article_scope_teacher_label,
)

SOURCE_TYPE_SPEC = BinaryHeadSpec(
    name="source_type",
    dataset_prefix="phobert_source_type",
    positive_label_name="official_or_regulatory",
    negative_label_name="media_or_commentary",
    label_source_name="llm_cache_source_type",
    summary_prefix="news_source_type",
    teacher_label_fn=_source_type_teacher_label,
)


def run_timestamp() -> str:
    return pd.Timestamp.utcnow().strftime("%Y%m%d_%H%M%S")


def current_utc_timestamp() -> str:
    return pd.Timestamp.utcnow().isoformat()


def json_digest(payload: dict[str, object]) -> str:
    return md5(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def path_signature(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    stat = path.stat()
    return {"path": str(path), "exists": True, "size": int(stat.st_size), "mtime_ns": int(stat.st_mtime_ns)}


def directory_signature(paths: Sequence[Path], *, label: str) -> dict[str, object]:
    digest = md5()
    total_size = 0
    latest_mtime_ns = 0
    for path in sorted(paths):
        stat = path.stat()
        total_size += int(stat.st_size)
        latest_mtime_ns = max(latest_mtime_ns, int(stat.st_mtime_ns))
        digest.update(f"{path.name}|{stat.st_size}|{stat.st_mtime_ns}\n".encode("utf-8"))
    return {
        "label": label,
        "file_count": int(len(paths)),
        "total_size": int(total_size),
        "latest_mtime_ns": int(latest_mtime_ns),
        "signature": digest.hexdigest(),
    }


def write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(body, encoding="utf-8")
    temp_path.replace(path)


def load_json_payload(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def safe_metric_value(value: object) -> float:
    if value is None:
        return float("-inf")
    if isinstance(value, (int, float, np.floating)) and not pd.isna(value):
        return float(value)
    return float("-inf")


def write_stage_run_summary(
    *,
    mode: str,
    name: str,
    summary: dict[str, object],
    artifacts: dict[str, object],
    metadata: Optional[dict[str, object]] = None,
) -> None:
    write_run_summary(
        ts=run_timestamp(),
        mode=mode,
        name=name,
        summary=summary,
        artifacts=artifacts,
        metadata=metadata or {},
    )


def teacher_columns(spec: BinaryHeadSpec) -> list[str]:
    return [
        "article_id",
        "source",
        "url",
        "published_at",
        "llm_cache_id",
        f"{spec.dataset_prefix}_label",
        f"{spec.dataset_prefix}_label_source",
    ]


def stage_columns(spec: BinaryHeadSpec) -> list[str]:
    return [
        "article_id",
        "source",
        "url",
        "date",
        "published_at",
        f"{spec.dataset_prefix}_input_text",
        f"{spec.dataset_prefix}_input_text_length",
        f"{spec.dataset_prefix}_label",
        f"{spec.dataset_prefix}_label_source",
        f"{spec.dataset_prefix}_split",
    ]


def empty_teacher_dataframe(spec: BinaryHeadSpec) -> pd.DataFrame:
    return pd.DataFrame(columns=teacher_columns(spec))


def empty_stage_dataframe(spec: BinaryHeadSpec) -> pd.DataFrame:
    return pd.DataFrame(columns=stage_columns(spec))


def head_teacher_labels_path(config: NewsFeaturesConfig, spec: BinaryHeadSpec) -> Path:
    return getattr(config, f"{spec.dataset_prefix}_teacher_labels_path")()


def head_teacher_manifest_path(config: NewsFeaturesConfig, spec: BinaryHeadSpec) -> Path:
    return getattr(config, f"{spec.dataset_prefix}_teacher_manifest_path")()


def head_stage_path(config: NewsFeaturesConfig, spec: BinaryHeadSpec) -> Path:
    return getattr(config, f"{spec.dataset_prefix}_stage_path")()


def head_stage_manifest_path(config: NewsFeaturesConfig, spec: BinaryHeadSpec) -> Path:
    return getattr(config, f"{spec.dataset_prefix}_stage_manifest_path")()


def head_article_features_path(config: NewsFeaturesConfig, spec: BinaryHeadSpec) -> Path:
    return getattr(config, f"{spec.dataset_prefix}_article_features_path")()


def head_ticker_day_features_path(config: NewsFeaturesConfig, spec: BinaryHeadSpec) -> Path:
    return getattr(config, f"{spec.dataset_prefix}_ticker_day_features_path")()


def head_metadata_path(config: NewsFeaturesConfig, spec: BinaryHeadSpec) -> Path:
    return getattr(config, f"{spec.dataset_prefix}_metadata_path")()


def head_publish_checkpoint_dir(config: NewsFeaturesConfig, spec: BinaryHeadSpec) -> Path:
    return getattr(config, f"{spec.dataset_prefix}_publish_checkpoint_dir")()


def head_publish_checkpoint_manifest_path(config: NewsFeaturesConfig, spec: BinaryHeadSpec) -> Path:
    return getattr(config, f"{spec.dataset_prefix}_publish_checkpoint_manifest_path")()


def head_publish_checkpoint_shard_path(config: NewsFeaturesConfig, spec: BinaryHeadSpec, batch_index: int) -> Path:
    return getattr(config, f"{spec.dataset_prefix}_publish_checkpoint_shard_path")(batch_index)


def head_model_artifacts_dir(config: NewsFeaturesConfig, spec: BinaryHeadSpec) -> Path:
    return getattr(config, f"{spec.dataset_prefix}_model_artifacts_dir")()


def head_training_manifest_path(config: NewsFeaturesConfig, spec: BinaryHeadSpec) -> Path:
    return getattr(config, f"{spec.dataset_prefix}_training_manifest_path")()


def head_latest_winner_path(config: NewsFeaturesConfig, spec: BinaryHeadSpec) -> Path:
    return getattr(config, f"{spec.dataset_prefix}_latest_winner_path")()


def head_job_status_path(config: NewsFeaturesConfig, spec: BinaryHeadSpec) -> Path:
    return getattr(config, f"{spec.dataset_prefix}_job_status_path")()


def head_publish_job_status_path(config: NewsFeaturesConfig, spec: BinaryHeadSpec) -> Path:
    return getattr(config, f"{spec.dataset_prefix}_publish_job_status_path")()


def daily_columns_for_spec(config: NewsFeaturesConfig, spec: BinaryHeadSpec) -> list[str]:
    return getattr(config, f"{spec.dataset_prefix}_daily_columns")()


def article_feature_columns(spec: BinaryHeadSpec) -> list[str]:
    return [
        "article_id",
        "ticker",
        "date",
        "published_at",
        "url",
        "source",
        "match_source",
        "title_hit",
        "body_hit",
        f"{spec.dataset_prefix}_model_id",
        f"{spec.dataset_prefix}_input_text_length",
        f"{spec.dataset_prefix}_token_count",
        f"{spec.dataset_prefix}_predicted_label",
        f"{spec.dataset_prefix}_is_positive",
        f"{spec.dataset_prefix}_confidence",
        f"{spec.dataset_prefix}_prob_negative",
        f"{spec.dataset_prefix}_prob_positive",
    ]


def write_head_progress_line(spec: BinaryHeadSpec, phase: str, message: str) -> None:
    print(f"[{spec.job_name}][{str(phase)}] {message}", flush=True)


def head_job_artifacts(config: NewsFeaturesConfig, spec: BinaryHeadSpec) -> dict[str, str]:
    artifact_paths = {
        "status_file": head_job_status_path(config, spec),
        "teacher_labels": head_teacher_labels_path(config, spec),
        "teacher_manifest": head_teacher_manifest_path(config, spec),
        "stage_dataset": head_stage_path(config, spec),
        "stage_manifest": head_stage_manifest_path(config, spec),
        "training_manifest": head_training_manifest_path(config, spec),
        "latest_winner": head_latest_winner_path(config, spec),
        "run_summaries_dir": config.repo_root / "artifacts" / "run_summaries",
    }
    return {key: describe_path(path, config=config) for key, path in artifact_paths.items()}


def write_head_job_status(
    config: NewsFeaturesConfig,
    spec: BinaryHeadSpec,
    *,
    status: str,
    phase: str,
    progress_updates: Optional[dict[str, object]] = None,
    throughput_updates: Optional[dict[str, object]] = None,
    artifact_updates: Optional[dict[str, object]] = None,
    error: Optional[str] = None,
    started_at: Optional[str] = None,
) -> dict[str, object]:
    status_path = head_job_status_path(config, spec)
    existing = load_json_payload(status_path)
    now = current_utc_timestamp()
    progress = dict(existing.get("progress") or {})
    progress.update(progress_updates or {})
    throughput = dict(existing.get("throughput") or {})
    throughput.update(throughput_updates or {})
    artifacts = dict(existing.get("artifacts") or {})
    artifacts.update(head_job_artifacts(config, spec))
    for key, value in (artifact_updates or {}).items():
        artifacts[str(key)] = None if value is None else describe_path(Path(str(value)), config=config)
    payload = {
        "job": spec.job_name,
        "status": str(status),
        "started_at": str(started_at or existing.get("started_at") or now),
        "updated_at": now,
        "last_heartbeat": now,
        "phase": str(phase),
        "progress": progress,
        "throughput": throughput,
        "artifacts": artifacts,
    }
    if error is not None:
        payload["error"] = str(error)
    write_json_atomic(status_path, payload)
    return payload
