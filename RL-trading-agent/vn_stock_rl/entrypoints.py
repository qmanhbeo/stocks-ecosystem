"""Lightweight console-script entrypoints.

These bootstrap runtime environment variables before importing the heavier
training/evaluation modules, which avoids Windows OpenMP initialization issues
when running installed console scripts.
"""

from __future__ import annotations

import os
from typing import Optional


def prepare_runtime() -> None:
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")


def train_main(argv: Optional[list[str]] = None) -> int:
    prepare_runtime()
    from vn_stock_rl.training.cli import main

    return main(argv)


def evaluate_main(argv: Optional[list[str]] = None) -> int:
    prepare_runtime()
    from vn_stock_rl.evaluation.cli import main

    return main(argv)


def count_params_main(argv: Optional[list[str]] = None) -> int:
    prepare_runtime()
    from vn_stock_rl.training.count_params_cli import main

    return main(argv)
