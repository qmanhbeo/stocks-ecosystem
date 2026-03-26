"""Training package with lazy exports.

This stays intentionally lightweight so console-script entrypoints can set
runtime environment variables before importing heavier dependencies.
"""

from __future__ import annotations

__all__ = ["build_env_from_args", "build_training_env", "filter_help_tickers"]


def __getattr__(name: str):
    if name in __all__:
        from vn_stock_rl.training.env_builder import (
            build_env_from_args,
            build_training_env,
            filter_help_tickers,
        )

        mapping = {
            "build_env_from_args": build_env_from_args,
            "build_training_env": build_training_env,
            "filter_help_tickers": filter_help_tickers,
        }
        return mapping[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
