"""Validation helpers for label artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd

from manual_label_factory.config import SupervisedLabelConfig, get_default_config
from manual_label_factory.io_utils import extract_ticker_from_filename, load_market_dataframe


class LabelValidationError(ValueError):
    """Raised when a label record is malformed."""


REQUIRED_LABEL_FIELDS = (
    "label_id",
    "session_id",
    "ticker",
    "timeframe",
    "chunk_id",
    "chunk_start",
    "chunk_end",
    "source_file",
    "selected_ranges",
    "default_label",
    "confidence",
    "notes",
    "created_at",
)


def resolve_source_path(source_file: str, config: Optional[SupervisedLabelConfig] = None) -> Path:
    config = config or get_default_config()
    path = Path(source_file)
    if path.is_absolute():
        return path
    return config.repo_root / path


def load_chunk_frame_for_record(record: Dict[str, object], config: Optional[SupervisedLabelConfig] = None) -> pd.DataFrame:
    config = config or get_default_config()
    source_path = resolve_source_path(str(record["source_file"]), config=config)
    frame = load_market_dataframe(source_path)
    chunk_start = pd.Timestamp(str(record["chunk_start"]))
    chunk_end = pd.Timestamp(str(record["chunk_end"]))
    chunk_df = frame.loc[(frame["time"] >= chunk_start) & (frame["time"] <= chunk_end)].copy().reset_index(drop=True)
    if chunk_df.empty:
        raise LabelValidationError(
            f"Chunk range {record['chunk_start']} -> {record['chunk_end']} produced no bars for {source_path}"
        )
    return chunk_df


def _normalize_range_payload(range_payload: Dict[str, object]) -> Dict[str, object]:
    start_ts = pd.Timestamp(str(range_payload["start_ts"]))
    end_ts = pd.Timestamp(str(range_payload["end_ts"]))
    if start_ts > end_ts:
        raise LabelValidationError(f"Selected range start {start_ts} is after end {end_ts}")
    label = int(range_payload.get("label", 1))
    return {
        "start_ts": start_ts.strftime("%Y-%m-%d"),
        "end_ts": end_ts.strftime("%Y-%m-%d"),
        "label": label,
    }


def validate_label_record(
    record: Dict[str, object],
    config: Optional[SupervisedLabelConfig] = None,
    check_source: bool = True,
) -> Dict[str, object]:
    config = config or get_default_config()
    missing = [field for field in REQUIRED_LABEL_FIELDS if field not in record]
    if missing:
        raise LabelValidationError(f"Label record missing fields: {missing}")

    ticker = str(record["ticker"]).upper()
    timeframe = str(record["timeframe"]).upper()
    chunk_start = pd.Timestamp(str(record["chunk_start"]))
    chunk_end = pd.Timestamp(str(record["chunk_end"]))
    if chunk_start > chunk_end:
        raise LabelValidationError("Chunk start must be before or equal to chunk end")
    if timeframe != config.timeframe.upper():
        raise LabelValidationError(f"timeframe must be {config.timeframe}")
    if int(record["default_label"]) != config.default_label:
        raise LabelValidationError(f"default_label must be {config.default_label}")

    selected_ranges = record.get("selected_ranges")
    if not isinstance(selected_ranges, list) or not selected_ranges:
        raise LabelValidationError("selected_ranges must contain at least one range")

    normalized_ranges: List[Dict[str, object]] = []
    for range_payload in selected_ranges:
        if not isinstance(range_payload, dict):
            raise LabelValidationError("Each selected range must be a dictionary")
        normalized = _normalize_range_payload(range_payload)
        if int(normalized["label"]) != config.selected_label:
            raise LabelValidationError(f"selected range label must be {config.selected_label}")
        normalized_start = pd.Timestamp(str(normalized["start_ts"]))
        normalized_end = pd.Timestamp(str(normalized["end_ts"]))
        if normalized_start < chunk_start or normalized_end > chunk_end:
            raise LabelValidationError("Selected range falls outside chunk bounds")
        normalized_ranges.append(normalized)

    confidence = str(record["confidence"]).lower().strip()
    if confidence not in config.label_confidence_weights:
        raise LabelValidationError(
            f"Unsupported confidence '{record['confidence']}'. Expected one of {sorted(config.label_confidence_weights)}"
        )

    normalized = dict(record)
    normalized["ticker"] = ticker
    normalized["timeframe"] = timeframe
    normalized["chunk_start"] = chunk_start.strftime("%Y-%m-%d")
    normalized["chunk_end"] = chunk_end.strftime("%Y-%m-%d")
    normalized["selected_ranges"] = normalized_ranges
    normalized["default_label"] = int(record["default_label"])
    normalized["confidence"] = confidence
    normalized["notes"] = str(record.get("notes", ""))
    normalized["created_at"] = pd.Timestamp(str(record["created_at"])).isoformat()

    if check_source:
        source_path = resolve_source_path(str(record["source_file"]), config=config)
        if not source_path.exists():
            raise LabelValidationError(f"Source file not found: {source_path}")
        source_ticker = extract_ticker_from_filename(source_path.name, timeframe=config.timeframe)
        if source_ticker != ticker:
            raise LabelValidationError(
                f"Ticker/source mismatch: record={ticker}, source_file={source_path.name} ({source_ticker})"
            )
        chunk_df = load_chunk_frame_for_record(normalized, config=config)
        actual_start = pd.Timestamp(chunk_df.iloc[0]["time"]).strftime("%Y-%m-%d")
        actual_end = pd.Timestamp(chunk_df.iloc[-1]["time"]).strftime("%Y-%m-%d")
        if actual_start != normalized["chunk_start"] or actual_end != normalized["chunk_end"]:
            raise LabelValidationError(
                f"Chunk bounds mismatch. Expected {normalized['chunk_start']} -> {normalized['chunk_end']}, "
                f"got {actual_start} -> {actual_end}"
            )

    return normalized


def iter_label_records(path: Path) -> Iterable[Tuple[int, Dict[str, object]]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            yield line_number, json.loads(line)


def scan_label_file(
    config: Optional[SupervisedLabelConfig] = None,
    jsonl_path: Optional[Path] = None,
    check_source: bool = True,
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    config = config or get_default_config()
    path = Path(jsonl_path or config.labels_jsonl_path)
    valid_records: List[Dict[str, object]] = []
    invalid_records: List[Dict[str, object]] = []
    for line_number, record in iter_label_records(path):
        try:
            valid_records.append(validate_label_record(record, config=config, check_source=check_source))
        except Exception as exc:
            invalid_records.append({"line_number": line_number, "error": str(exc), "record": record})
    return valid_records, invalid_records


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate supervised label JSONL records.")
    parser.add_argument("--jsonl-path", type=Path, default=None, help="Optional override path to range_labels.jsonl")
    parser.add_argument(
        "--skip-source-check",
        action="store_true",
        help="Skip source parquet verification and validate only record structure.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    valid_records, invalid_records = scan_label_file(
        jsonl_path=args.jsonl_path,
        check_source=not args.skip_source_check,
    )
    print(f"valid_records={len(valid_records)} invalid_records={len(invalid_records)}")
    for item in invalid_records:
        print(f"line={item['line_number']} error={item['error']}")
    if invalid_records:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
