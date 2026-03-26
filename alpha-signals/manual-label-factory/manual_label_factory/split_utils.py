"""Ticker-level split helpers for supervised labeling."""

from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .config import SupervisedLabelConfig, get_default_config
from .io_utils import get_ticker_to_path_map, make_relative_to_repo
from .core.label_storage import update_manifest


def split_tickers(
    tickers: Iterable[str],
    train_ratio: float,
    val_ratio: float,
    seed: int,
) -> Dict[str, List[str]]:
    tickers = sorted({str(ticker).upper() for ticker in tickers})
    if not tickers:
        raise ValueError("No tickers available for supervised splits")
    if train_ratio <= 0.0 or val_ratio < 0.0 or train_ratio + val_ratio >= 1.0:
        raise ValueError("Invalid split ratios. Expected train_ratio > 0, val_ratio >= 0, train + val < 1.")

    shuffled = tickers[:]
    random.Random(seed).shuffle(shuffled)

    count = len(shuffled)
    train_count = max(1, int(count * train_ratio))
    val_count = int(count * val_ratio)
    remaining = count - train_count - val_count
    if remaining <= 0 and count >= 3:
        val_count = max(1, min(val_count, count - train_count - 1))
        remaining = count - train_count - val_count
    if remaining < 0:
        raise ValueError("Split ratios left a negative test split")

    train = shuffled[:train_count]
    val = shuffled[train_count : train_count + val_count]
    test = shuffled[train_count + val_count :]
    return {"train": sorted(train), "val": sorted(val), "test": sorted(test)}


def save_split_files(split_map: Dict[str, List[str]], config: Optional[SupervisedLabelConfig] = None) -> Dict[str, Path]:
    config = config or get_default_config()
    config.ensure_directories()
    file_map = config.split_file_map()
    for split_name, path in file_map.items():
        values = split_map.get(split_name, [])
        path.write_text("\n".join(values) + ("\n" if values else ""), encoding="utf-8")
    update_manifest(config=config, latest_split_refresh=make_relative_to_repo(config.splits_dir, config=config))
    return file_map


def load_split_files(config: Optional[SupervisedLabelConfig] = None) -> Dict[str, List[str]]:
    config = config or get_default_config()
    file_map = config.split_file_map()
    split_map: Dict[str, List[str]] = {}
    for split_name, path in file_map.items():
        if not path.exists():
            split_map[split_name] = []
            continue
        lines = [line.strip().upper() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        split_map[split_name] = sorted(dict.fromkeys(lines))
    return split_map


def create_or_load_splits(
    config: Optional[SupervisedLabelConfig] = None,
    overwrite: bool = False,
) -> Dict[str, List[str]]:
    config = config or get_default_config()
    existing = load_split_files(config=config)
    if not overwrite and any(existing.values()):
        return existing
    tickers = list(get_ticker_to_path_map(config=config, timeframe=config.timeframe).keys())
    split_map = split_tickers(
        tickers=tickers,
        train_ratio=config.train_ratio,
        val_ratio=config.val_ratio,
        seed=config.random_seed,
    )
    save_split_files(split_map, config=config)
    return split_map


def get_split_tickers(split_name: str, config: Optional[SupervisedLabelConfig] = None) -> List[str]:
    split_map = load_split_files(config=config)
    if split_name not in split_map:
        raise KeyError(f"Unknown split name: {split_name}")
    return split_map[split_name]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create or refresh supervised_label ticker split files.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing split files.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    config = get_default_config()
    split_map = create_or_load_splits(config=config, overwrite=args.overwrite)
    for split_name, tickers in split_map.items():
        print(f"{split_name}: {len(tickers)} tickers")


if __name__ == "__main__":
    main()
