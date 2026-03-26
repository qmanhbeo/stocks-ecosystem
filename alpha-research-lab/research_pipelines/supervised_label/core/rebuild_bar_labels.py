"""Rebuild per-bar binary labels from saved range annotations."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from research_pipelines.supervised_label.config import SupervisedLabelConfig, get_default_config
from research_pipelines.supervised_label.io_utils import make_relative_to_repo
from research_pipelines.supervised_label.variants import (
    LABEL_VARIANT_CHOICES,
    iter_label_variants,
    resolve_label_variant_paths,
)

from .label_storage import update_manifest
from .validation import LabelValidationError, load_chunk_frame_for_record, scan_label_file, validate_label_record


def _range_mask(chunk_df: pd.DataFrame, start_ts: str, end_ts: str) -> pd.Series:
    start = pd.Timestamp(start_ts)
    end = pd.Timestamp(end_ts)
    return (chunk_df["time"] >= start) & (chunk_df["time"] <= end)


def map_ranges_to_bar_labels(
    chunk_df: pd.DataFrame,
    selected_ranges: List[Dict[str, object]],
    selected_label: int,
    default_label: int,
) -> pd.Series:
    labels = pd.Series(default_label, index=chunk_df.index, dtype="int64")
    for range_payload in selected_ranges:
        labels.loc[_range_mask(chunk_df, str(range_payload["start_ts"]), str(range_payload["end_ts"]))] = selected_label
    return labels


def rebuild_label_rows_for_record(
    record: Dict[str, object],
    config: Optional[SupervisedLabelConfig] = None,
) -> pd.DataFrame:
    config = config or get_default_config()
    validated = validate_label_record(record, config=config, check_source=True)
    chunk_df = load_chunk_frame_for_record(validated, config=config)
    labels = map_ranges_to_bar_labels(
        chunk_df=chunk_df,
        selected_ranges=list(validated["selected_ranges"]),
        selected_label=config.selected_label,
        default_label=config.default_label,
    )
    confidence = str(validated["confidence"])
    confidence_weight = float(config.label_confidence_weights[confidence])
    return pd.DataFrame(
        {
            "ticker": str(validated["ticker"]),
            "date": chunk_df["time"].dt.strftime("%Y-%m-%d"),
            "chunk_id": str(validated["chunk_id"]),
            "label": labels.astype(int).values,
            "confidence": confidence,
            "confidence_weight": confidence_weight,
            "session_id": str(validated["session_id"]),
        }
    )


def rebuild_bar_labels_dataframe(
    config: Optional[SupervisedLabelConfig] = None,
    labels_jsonl_path: Optional[Path] = None,
    skip_invalid: bool = False,
) -> Tuple[pd.DataFrame, List[Dict[str, object]]]:
    config = config or get_default_config()
    valid_records, invalid_records = scan_label_file(
        config=config,
        jsonl_path=labels_jsonl_path,
        check_source=True,
    )
    if invalid_records and not skip_invalid:
        first_error = invalid_records[0]
        raise LabelValidationError(f"Invalid label record at line {first_error['line_number']}: {first_error['error']}")

    rows: List[pd.DataFrame] = []
    for record in valid_records:
        rows.append(rebuild_label_rows_for_record(record, config=config))
    if not rows:
        raise ValueError("No valid label records were available for rebuild")
    rebuilt = pd.concat(rows, ignore_index=True)
    rebuilt = rebuilt.sort_values(["ticker", "date", "chunk_id"]).reset_index(drop=True)
    return rebuilt, invalid_records


def summarize_bar_labels(frame: pd.DataFrame) -> Dict[str, float]:
    labeled_one = int((frame["label"] == 1).sum())
    labeled_zero = int((frame["label"] == 0).sum())
    total = max(len(frame), 1)
    return {
        "total_labeled_chunks": int(frame["chunk_id"].nunique()),
        "total_bars": int(len(frame)),
        "total_bars_labeled_1": labeled_one,
        "total_bars_labeled_0": labeled_zero,
        "class_balance_positive": float(labeled_one / total),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild bar-level labels from saved range annotations.")
    parser.add_argument("--output", type=Path, default=None, help="Optional output parquet path.")
    parser.add_argument(
        "--labels-jsonl-path",
        type=Path,
        default=None,
        help="Optional override path to the labels JSONL file.",
    )
    parser.add_argument("--skip-invalid", action="store_true", help="Skip invalid label records instead of failing.")
    parser.add_argument(
        "--label-variant",
        choices=LABEL_VARIANT_CHOICES,
        default="both",
        help="Which label variant to rebuild. Defaults to both manual and auto.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    config = get_default_config()
    if args.label_variant == "both" and (args.output or args.labels_jsonl_path):
        parser.error("--output and --labels-jsonl-path can only be used with a single --label-variant")

    for variant in iter_label_variants(args.label_variant):
        variant_paths = resolve_label_variant_paths(config, variant)
        variant_paths.ensure_directories()
        output_path = Path(args.output) if args.output else variant_paths.bar_labels_path
        labels_jsonl_path = Path(args.labels_jsonl_path) if args.labels_jsonl_path else variant_paths.labels_jsonl_path
        if args.label_variant == "both" and not labels_jsonl_path.exists():
            print(f"[{variant}] skipped_missing_labels={labels_jsonl_path}")
            continue
        rebuilt, invalid_records = rebuild_bar_labels_dataframe(
            config=config,
            labels_jsonl_path=labels_jsonl_path,
            skip_invalid=args.skip_invalid,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        rebuilt.to_parquet(output_path, index=False)
        output_ref = make_relative_to_repo(output_path, config=config)
        update_manifest(
            config=config,
            latest_bar_labels_dataset=output_ref,
            **{f"latest_bar_labels_dataset_{variant}": output_ref},
        )
        summary = summarize_bar_labels(rebuilt)
        print(f"[{variant}] saved={output_path}")
        for key, value in summary.items():
            print(f"[{variant}] {key}={value}")
        if invalid_records:
            print(f"[{variant}] skipped_invalid_records={len(invalid_records)}")


if __name__ == "__main__":
    main()
