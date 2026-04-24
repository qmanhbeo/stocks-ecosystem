from __future__ import annotations

from pathlib import Path

from data_tools.news_runtime.llm_extract.contracts import DayClassification


def classify_days(files: list[Path], *, cache_dir: Path, overwrite: bool, cache_has_successful_rows) -> DayClassification:
    skipped = 0
    retry_error_only = 0
    pending: list[Path] = []
    for path in files:
        out = cache_dir / f"{path.stem}.jsonl"
        if out.exists() and not overwrite:
            if cache_has_successful_rows(out):
                skipped += 1
            else:
                retry_error_only += 1
                pending.append(path)
        else:
            pending.append(path)
    retry_only_days = [path.stem for path in pending if (cache_dir / f"{path.stem}.jsonl").exists()]
    completed_days = [path.stem for path in files if path not in pending]
    return DayClassification(
        pending=pending,
        completed_days=completed_days,
        retry_only_days=retry_only_days,
        skipped_existing_days=skipped,
    )


def tracker_payload(
    *,
    pending_days: list[str],
    completed_days: list[str],
    retry_only_days: list[str],
    current_day: str | None,
    skipped_existing_days: int,
    aggregate_counts: dict[str, int],
    current_index: int | None = None,
    total_pending_days: int | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "pending_days": pending_days,
        "completed_days": completed_days,
        "retry_only_days": retry_only_days,
        "current_day": current_day,
        "skipped_existing_days": skipped_existing_days,
        "aggregate_counts": aggregate_counts,
    }
    if current_index is not None:
        payload["current_index"] = current_index
    if total_pending_days is not None:
        payload["total_pending_days"] = total_pending_days
    return payload

