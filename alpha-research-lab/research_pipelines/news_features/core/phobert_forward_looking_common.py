"""Shared contract and helpers for the PhoBERT forward-looking distillation lane."""

from __future__ import annotations

import json
from hashlib import md5
from pathlib import Path
from typing import Callable, Optional, Sequence

import numpy as np
import pandas as pd

from research_pipelines.news_features.config import NewsFeaturesConfig
from research_pipelines.news_features.io_utils import describe_path
from src.run_summary import write_run_summary


FORWARD_LOOKING_TEACHER_VERSION = 1
FORWARD_LOOKING_STAGE_VERSION = 1
FORWARD_LOOKING_TRAINING_VERSION = 1
PHOBERT_FORWARD_LOOKING_JOB_NAME = "phobert_forward_looking_train"

TEACHER_COLUMNS = [
    "article_id",
    "source",
    "url",
    "published_at",
    "llm_cache_id",
    "phobert_forward_looking_label",
    "phobert_forward_looking_label_source",
]

STAGE_COLUMNS = [
    "article_id",
    "source",
    "url",
    "date",
    "published_at",
    "phobert_forward_looking_input_text",
    "phobert_forward_looking_input_text_length",
    "phobert_forward_looking_label",
    "phobert_forward_looking_label_source",
    "phobert_forward_looking_split",
]

FORWARD_LOOKING_LABEL_SOURCE = "llm_cache_is_forward_looking"


class ForwardLookingTrainingError(RuntimeError):
    """Raised when the forward-looking distillation pipeline cannot proceed."""


class ForwardLookingCandidateSpec(tuple):
    """Immutable name/model pair for sequential training."""

    __slots__ = ()

    def __new__(cls, name: str, model_name: str):
        return super().__new__(cls, (str(name), str(model_name)))

    @property
    def name(self) -> str:
        return str(self[0])

    @property
    def model_name(self) -> str:
        return str(self[1])


ForwardLookingTrainerFn = Callable[
    [ForwardLookingCandidateSpec, NewsFeaturesConfig, Path, Path, dict[str, object]],
    dict[str, object],
]


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
    return {
        "path": str(path),
        "exists": True,
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
    }


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


def phobert_forward_looking_job_artifacts(config: NewsFeaturesConfig) -> dict[str, str]:
    artifact_paths = {
        "status_file": config.phobert_forward_looking_job_status_path(),
        "teacher_labels": config.phobert_forward_looking_teacher_labels_path(),
        "teacher_manifest": config.phobert_forward_looking_teacher_manifest_path(),
        "stage_dataset": config.phobert_forward_looking_stage_path(),
        "stage_manifest": config.phobert_forward_looking_stage_manifest_path(),
        "training_manifest": config.phobert_forward_looking_training_manifest_path(),
        "latest_winner": config.phobert_forward_looking_latest_winner_path(),
        "run_summaries_dir": config.repo_root / "artifacts" / "run_summaries",
    }
    return {
        key: describe_path(path, config=config)
        for key, path in artifact_paths.items()
    }


def write_forward_looking_progress_line(phase: str, message: str) -> None:
    print(f"[{PHOBERT_FORWARD_LOOKING_JOB_NAME}][{str(phase)}] {message}", flush=True)


def write_forward_looking_job_status(
    config: NewsFeaturesConfig,
    *,
    status: str,
    phase: str,
    progress_updates: Optional[dict[str, object]] = None,
    throughput_updates: Optional[dict[str, object]] = None,
    artifact_updates: Optional[dict[str, object]] = None,
    error: Optional[str] = None,
    started_at: Optional[str] = None,
) -> dict[str, object]:
    status_path = config.phobert_forward_looking_job_status_path()
    existing = load_json_payload(status_path)
    now = current_utc_timestamp()

    progress = dict(existing.get("progress") or {})
    progress.update(progress_updates or {})

    throughput = dict(existing.get("throughput") or {})
    throughput.update(throughput_updates or {})

    artifacts = dict(existing.get("artifacts") or {})
    artifacts.update(phobert_forward_looking_job_artifacts(config))
    for key, value in (artifact_updates or {}).items():
        if value is None:
            artifacts[key] = None
        else:
            artifacts[str(key)] = describe_path(Path(str(value)), config=config)

    payload = {
        "job": PHOBERT_FORWARD_LOOKING_JOB_NAME,
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
    elif str(status).lower() in {"failed", "error"} and existing.get("error") is not None:
        payload["error"] = existing["error"]
    write_json_atomic(status_path, payload)
    return payload


def safe_metric_value(value: object) -> float:
    if value is None:
        return float("-inf")
    if isinstance(value, (int, float, np.floating)) and not pd.isna(value):
        return float(value)
    return float("-inf")


def empty_teacher_dataframe() -> pd.DataFrame:
    return pd.DataFrame(columns=TEACHER_COLUMNS)


def empty_stage_dataframe() -> pd.DataFrame:
    return pd.DataFrame(columns=STAGE_COLUMNS)
