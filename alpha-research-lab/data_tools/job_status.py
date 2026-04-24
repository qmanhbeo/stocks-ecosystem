from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

try:
    from cafef_history_common import atomic_write_json, utc_now_iso
except ModuleNotFoundError:
    from data_tools.cafef_history_common import atomic_write_json, utc_now_iso

from src.repo_paths import artifact_path, lab_relative_path


def _normalize_artifacts(artifacts: dict[str, object] | None) -> dict[str, object]:
    normalized: dict[str, object] = {}
    for key, value in (artifacts or {}).items():
        if value is None:
            normalized[key] = None
        elif isinstance(value, (list, tuple)):
            normalized[key] = [
                lab_relative_path(item) if hasattr(item, "__fspath__") else item
                for item in value
            ]
        elif hasattr(value, "__fspath__"):
            normalized[key] = lab_relative_path(value)
        else:
            normalized[key] = value
    return normalized


@dataclass
class JobStatusTracker:
    job: str
    started_at: str = field(default_factory=utc_now_iso)
    path: object | None = None
    artifacts: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.path is None:
            self.path = artifact_path("job_status", f"{self.job}.json")
        self.artifacts = {
            "status_file": self.path,
            **dict(self.artifacts or {}),
        }

    def write(
        self,
        *,
        status: str,
        phase: str,
        progress: dict[str, Any] | None = None,
        throughput: dict[str, Any] | None = None,
        artifacts: dict[str, object] | None = None,
        error: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "job": self.job,
            "status": status,
            "started_at": self.started_at,
            "updated_at": utc_now_iso(),
            "last_heartbeat": utc_now_iso(),
            "phase": phase,
            "progress": dict(progress or {}),
            "throughput": dict(throughput or {}),
            "artifacts": _normalize_artifacts({**self.artifacts, **dict(artifacts or {})}),
        }
        if error is not None:
            payload["error"] = error
        if extra:
            payload.update(extra)
        atomic_write_json(payload, self.path)
