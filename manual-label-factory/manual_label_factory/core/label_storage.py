"""Persistent storage helpers for range-based labels."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Set, Union

from manual_label_factory.config import SupervisedLabelConfig, get_default_config
from manual_label_factory.schemas import ChunkSample, LabelRecord, SelectedRange, SessionRecord

from .validation import iter_label_records, validate_label_record


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_manifest(config: SupervisedLabelConfig) -> Dict[str, object]:
    if config.manifest_path.exists():
        return json.loads(config.manifest_path.read_text(encoding="utf-8-sig"))
    return {
        "latest_split_refresh": None,
        "latest_bar_labels_dataset": None,
        "latest_supervised_dataset": None,
        "latest_model_export": None,
        "latest_prediction_export": None,
        "session_count": 0,
    }


def update_manifest(config: Optional[SupervisedLabelConfig] = None, **updates: object) -> Dict[str, object]:
    config = config or get_default_config()
    manifest = _load_manifest(config)
    manifest.update(updates)
    config.manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _extract_numeric_suffix(value: str, prefix: str) -> int:
    token = str(value).replace(prefix, "", 1)
    return int(token) if token.isdigit() else 0


def generate_label_id(config: Optional[SupervisedLabelConfig] = None) -> str:
    config = config or get_default_config()
    max_id = 0
    for _, record in iter_label_records(config.labels_jsonl_path):
        label_id = str(record.get("label_id", ""))
        if label_id.startswith("lbl_"):
            max_id = max(max_id, _extract_numeric_suffix(label_id, "lbl_"))
    return f"lbl_{max_id + 1:06d}"


def generate_session_id(config: Optional[SupervisedLabelConfig] = None, now: Optional[datetime] = None) -> str:
    config = config or get_default_config()
    timestamp = now or datetime.now(timezone.utc)
    date_token = timestamp.strftime("%Y-%m-%d")
    prefix = f"session_{date_token}_"
    existing = sorted(config.sessions_dir.glob(f"{prefix}*.json"))
    sequence = 1
    for path in existing:
        stem = path.stem
        if stem.startswith(prefix):
            try:
                sequence = max(sequence, int(stem.replace(prefix, "")) + 1)
            except ValueError:
                continue
    return f"{prefix}{sequence:03d}"


def create_session_record(
    config: Optional[SupervisedLabelConfig] = None,
    session_id: Optional[str] = None,
) -> SessionRecord:
    config = config or get_default_config()
    config.ensure_directories()
    created_at = utc_now_iso()
    session_id = session_id or generate_session_id(config=config)
    session = SessionRecord(
        session_id=session_id,
        created_at=created_at,
        timeframe=config.timeframe,
        split_mode=config.split_mode,
        chunk_length_min=config.chunk_length_min,
        chunk_length_max=config.chunk_length_max,
        random_seed=config.random_seed,
    )
    session_path = config.sessions_dir / f"{session_id}.json"
    if session_path.exists():
        raise FileExistsError(f"Session already exists: {session_path}")
    session_path.write_text(json.dumps(session.to_dict(), indent=2), encoding="utf-8")
    manifest = update_manifest(config=config)
    update_manifest(config=config, session_count=int(manifest.get("session_count", 0)) + 1)
    return session


def normalize_selected_ranges(
    selected_ranges: Sequence[Union[Dict[str, object], SelectedRange]]
) -> List[SelectedRange]:
    normalized: List[SelectedRange] = []
    for item in selected_ranges:
        if isinstance(item, SelectedRange):
            normalized.append(item)
            continue
        normalized.append(
            SelectedRange(
                start_ts=str(item["start_ts"]),
                end_ts=str(item["end_ts"]),
                label=int(item.get("label", 1)),
            )
        )
    return normalized


def build_label_record(
    chunk_sample: ChunkSample,
    session_id: str,
    selected_ranges: Sequence[Union[Dict[str, object], SelectedRange]],
    confidence: str = "medium",
    notes: str = "",
    ticker_split: str = "unknown",
    config: Optional[SupervisedLabelConfig] = None,
) -> LabelRecord:
    config = config or get_default_config()
    return LabelRecord(
        label_id=generate_label_id(config=config),
        session_id=session_id,
        ticker=chunk_sample.ticker,
        timeframe=config.timeframe,
        chunk_id=chunk_sample.chunk_id,
        chunk_start=chunk_sample.chunk_start,
        chunk_end=chunk_sample.chunk_end,
        source_file=chunk_sample.source_file,
        ticker_split=str(ticker_split).lower().strip() or "unknown",
        selected_ranges=normalize_selected_ranges(selected_ranges),
        default_label=config.default_label,
        confidence=confidence,
        notes=notes,
        created_at=utc_now_iso(),
    )


def append_label_record(
    record: Union[LabelRecord, Dict[str, object]],
    config: Optional[SupervisedLabelConfig] = None,
) -> Dict[str, object]:
    config = config or get_default_config()
    config.ensure_directories()
    payload = record.to_dict() if isinstance(record, LabelRecord) else dict(record)
    validated = validate_label_record(payload, config=config, check_source=True)
    with config.labels_jsonl_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(validated, ensure_ascii=True) + "\n")
    return validated


def read_all_label_records(config: Optional[SupervisedLabelConfig] = None) -> List[Dict[str, object]]:
    config = config or get_default_config()
    records: List[Dict[str, object]] = []
    for _, record in iter_label_records(config.labels_jsonl_path):
        records.append(record)
    return records


def list_labeled_chunk_ids(config: Optional[SupervisedLabelConfig] = None) -> Set[str]:
    config = config or get_default_config()
    chunk_ids: Set[str] = set()
    for _, record in iter_label_records(config.labels_jsonl_path):
        if "chunk_id" in record:
            chunk_ids.add(str(record["chunk_id"]))
    return chunk_ids
