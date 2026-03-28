"""Inspect shared research exports required by the RL runtime."""

from __future__ import annotations

import argparse
from pathlib import Path

from vn_stock_rl.external_features import (
    default_help_assets_dir,
    default_lab_signal_matrix_path,
    default_lab_signal_prediction_dir,
    default_news_prediction_dir,
    default_signal_prediction_dir,
    default_stock_data_dir,
    shared_data_root,
)


def _count_parquet_files(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for item in path.glob("*.parquet") if item.is_file())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect shared research exports for RL consumption."
    )
    parser.add_argument(
        "--require-news",
        action="store_true",
        help="Fail if shared news predictions are missing.",
    )
    parser.add_argument(
        "--require-signal",
        action="store_true",
        help="Fail if shared signal predictions are missing.",
    )
    parser.add_argument(
        "--require-lab-matrix",
        action="store_true",
        help="Fail if the consolidated lab RL signal matrix is missing.",
    )
    parser.add_argument(
        "--require-lab-adapter",
        action="store_true",
        help="Fail if adapted per-ticker lab signal exports are missing.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    paths = {
        "shared_data_root": shared_data_root(),
        "stock_data_dir": default_stock_data_dir(),
        "help_assets_dir": default_help_assets_dir(),
        "news_prediction_dir": default_news_prediction_dir(),
        "signal_prediction_dir": default_signal_prediction_dir(),
        "lab_signal_matrix_path": default_lab_signal_matrix_path(),
        "lab_signal_prediction_dir": default_lab_signal_prediction_dir(),
    }
    counts = {
        "stock_parquet_files": _count_parquet_files(paths["stock_data_dir"]),
        "helper_asset_parquet_files": _count_parquet_files(paths["help_assets_dir"]),
        "news_prediction_files": _count_parquet_files(paths["news_prediction_dir"]),
        "signal_prediction_files": _count_parquet_files(paths["signal_prediction_dir"]),
        "lab_signal_matrix_exists": int(paths["lab_signal_matrix_path"].exists()),
        "lab_signal_prediction_files": _count_parquet_files(paths["lab_signal_prediction_dir"]),
    }

    for name, path in paths.items():
        print(f"{name}: {path}")
    for name, count in counts.items():
        print(f"{name}: {count}")

    if args.require_news and counts["news_prediction_files"] == 0:
        raise SystemExit("Missing shared news exports.")
    if args.require_signal and counts["signal_prediction_files"] == 0:
        raise SystemExit("Missing shared signal exports.")
    if args.require_lab_matrix and counts["lab_signal_matrix_exists"] == 0:
        raise SystemExit("Missing consolidated lab RL signal matrix.")
    if args.require_lab_adapter and counts["lab_signal_prediction_files"] == 0:
        raise SystemExit("Missing adapted lab signal exports.")


if __name__ == "__main__":
    main()
