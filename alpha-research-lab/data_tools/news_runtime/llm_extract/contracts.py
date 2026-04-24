from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CanonicalExtractOptions:
    date_from: str
    date_to: str
    batch_size: int
    provider: str
    model: str
    api_key: str
    timeout: int
    num_predict: int
    overwrite: bool
    workers: int
    max_summary_chars: int
    log_every_batches: int


@dataclass(frozen=True)
class DayClassification:
    pending: list[Path]
    completed_days: list[str]
    retry_only_days: list[str]
    skipped_existing_days: int

