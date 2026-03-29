"""Export a supervised dataset aligned to rebuilt bar labels."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from research_pipelines.supervised_label.config import SupervisedLabelConfig, get_default_config
from research_pipelines.supervised_label.io_utils import load_ticker_dataframe, make_relative_to_repo
from research_pipelines.supervised_label.split_utils import create_or_load_splits
from research_pipelines.supervised_label.variants import (
    LABEL_VARIANT_CHOICES,
    iter_label_variants,
    resolve_label_variant_paths,
)

from .feature_builder import build_feature_frame, get_feature_columns
from .label_storage import update_manifest


def _chunk_hash_fraction(chunk_id: str, seed: int) -> float:
    digest = hashlib.md5(f"{seed}:{chunk_id}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / float(16 ** 8)


def assign_dataset_split(chunk_id: str, config: SupervisedLabelConfig) -> str:
    value = _chunk_hash_fraction(chunk_id, config.random_seed)
    if value < config.train_ratio:
        return "train"
    if value < config.train_ratio + config.val_ratio:
        return "val"
    return "test"


def build_ticker_split_lookup(config: SupervisedLabelConfig) -> Dict[str, str]:
    split_map = create_or_load_splits(config=config, overwrite=False)
    lookup: Dict[str, str] = {}
    for split_name, tickers in split_map.items():
        for ticker in tickers:
            lookup[str(ticker).upper()] = split_name
    return lookup


def _normalize_ticker_split_series(series: pd.Series) -> pd.Series:
    normalized = series.astype(str).str.lower().str.strip()
    normalized = normalized.replace({"": "unknown", "nan": "unknown", "none": "unknown"})
    return normalized


def export_supervised_dataset_dataframe(
    config: Optional[SupervisedLabelConfig] = None,
    bar_labels_path: Optional[Path] = None,
) -> pd.DataFrame:
    config = config or get_default_config()
    input_path = Path(bar_labels_path) if bar_labels_path else config.datasets_dir / config.bar_labels_filename
    if not input_path.exists():
        raise FileNotFoundError(f"Bar labels parquet not found: {input_path}")

    bar_labels = pd.read_parquet(input_path)
    if bar_labels.empty:
        raise ValueError("Bar labels dataset is empty")

    ticker_split_lookup = {} if "ticker_split" in bar_labels.columns else build_ticker_split_lookup(config)
    datasets: List[pd.DataFrame] = []
    for ticker in sorted(bar_labels["ticker"].astype(str).unique()):
        labels_for_ticker = bar_labels.loc[bar_labels["ticker"].astype(str) == ticker].copy()
        raw_df = load_ticker_dataframe(ticker=ticker, config=config, timeframe=config.timeframe)
        features = build_feature_frame(raw_df, lookback_window=config.lookback_window)
        merged = labels_for_ticker.merge(features, on="date", how="left", validate="many_to_one")
        if "ticker_split" in labels_for_ticker.columns:
            merged["ticker_split"] = _normalize_ticker_split_series(merged["ticker_split"])
        else:
            merged["ticker_split"] = ticker_split_lookup.get(str(ticker).upper(), "unknown")
        merged["dataset_split"] = merged["chunk_id"].astype(str).map(lambda value: assign_dataset_split(value, config))
        merged = merged.loc[merged["history_ready"] == 1].copy()
        feature_columns = get_feature_columns(merged)
        merged = merged.dropna(subset=feature_columns).reset_index(drop=True)
        datasets.append(merged)

    exported = pd.concat(datasets, ignore_index=True)
    if exported.empty:
        raise ValueError("No rows survived feature construction. Check lookback/chunk settings.")
    return exported


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export the supervised learning dataset.")
    parser.add_argument("--bar-labels-path", type=Path, default=None, help="Optional override input parquet path.")
    parser.add_argument("--output", type=Path, default=None, help="Optional output parquet path.")
    parser.add_argument(
        "--label-variant",
        choices=LABEL_VARIANT_CHOICES,
        default="both",
        help="Which label variant to export. Defaults to both manual and auto.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    config = get_default_config()
    if args.label_variant == "both" and (args.bar_labels_path or args.output):
        parser.error("--bar-labels-path and --output can only be used with a single --label-variant")

    for variant in iter_label_variants(args.label_variant):
        variant_paths = resolve_label_variant_paths(config, variant)
        variant_paths.ensure_directories()
        input_path = Path(args.bar_labels_path) if args.bar_labels_path else variant_paths.bar_labels_path
        if args.label_variant == "both" and not input_path.exists():
            print(f"[{variant}] skipped_missing_bar_labels={input_path}")
            continue
        exported = export_supervised_dataset_dataframe(config=config, bar_labels_path=input_path)
        output_path = Path(args.output) if args.output else variant_paths.supervised_dataset_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        exported.to_parquet(output_path, index=False)
        output_ref = make_relative_to_repo(output_path, config=config)
        update_manifest(
            config=config,
            latest_supervised_dataset=output_ref,
            **{f"latest_supervised_dataset_{variant}": output_ref},
        )
        print(f"[{variant}] saved={output_path}")
        print(f"[{variant}] rows={len(exported)} chunks={exported['chunk_id'].nunique()}")


if __name__ == "__main__":
    main()
