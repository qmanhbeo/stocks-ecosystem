"""Publish RL-ready news exports from the additive PhoBERT forward-looking lane.

Preferred operator alias: `publish_phobert_forward_looking_features.py`.
"""

from __future__ import annotations

import argparse

from research_pipelines.news_features.config import get_default_config
from research_pipelines.news_features.core.aggregate_daily_features import aggregate_daily_feature_exports
from research_pipelines.news_features.core.build_phobert_forward_looking_features import (
    build_phobert_forward_looking_feature_exports,
)


def build_arg_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description=(
            "Build additive PhoBERT forward-looking datasets from the latest winner and "
            "overlay the resulting phobert_forward_looking_* columns onto the existing "
            "RL-ready news exports."
        )
    )


def main() -> None:
    build_arg_parser().parse_args()
    config = get_default_config()
    build_phobert_forward_looking_feature_exports(config=config)
    aggregate_daily_feature_exports(config=config, sources=["phobert_forward_looking"])
    print(
        "PhoBERT forward-looking publish complete. Outputs written under: "
        f"{config.predictions_dir}",
        flush=True,
    )


if __name__ == "__main__":
    main()
