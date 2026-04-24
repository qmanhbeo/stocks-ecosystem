"""Publish RL-ready news exports from the existing PhoBERT daily dataset only."""

from __future__ import annotations

import argparse

from research_pipelines.news_features.config import get_default_config
from research_pipelines.news_features.core.aggregate_daily_features import aggregate_daily_feature_exports


def build_arg_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description=(
            "Publish RL-ready per-ticker news exports from the existing "
            "phobert_ticker_day_sentiment.parquet surface without rebuilding "
            "legacy tabular or embedding datasets."
        )
    )


def main() -> None:
    build_arg_parser().parse_args()
    config = get_default_config()
    aggregate_daily_feature_exports(config=config, sources=["phobert"])
    print(f"PhoBERT-only news export publish complete. Outputs written under: {config.predictions_dir}")


if __name__ == "__main__":
    main()
