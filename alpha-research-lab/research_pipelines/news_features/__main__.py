"""Run the full heavyweight news feature rebuild over already-fetched raw news."""

from __future__ import annotations

import argparse

from research_pipelines.news_features.config import get_default_config
from research_pipelines.news_features.core.aggregate_daily_features import aggregate_daily_feature_exports
from research_pipelines.news_features.core.build_embedding_features import build_embedding_feature_exports
from research_pipelines.news_features.core.build_phobert_sentiment_features import build_phobert_sentiment_exports
from research_pipelines.news_features.core.build_tabular_features import build_tabular_feature_exports
from research_pipelines.news_features.core.preprocess_news import preprocess_news_exports
from research_pipelines.news_features.core.tag_articles import tag_articles_exports


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the full heavyweight news rebuild over raw/normalized/tagged inputs. "
            "This is intentionally not the default path for narrow refreshes."
        )
    )
    parser.add_argument(
        "--full-rebuild",
        action="store_true",
        help=(
            "Required confirmation for the heavyweight end-to-end rebuild. "
            "Use narrower producer or publish commands for modular refreshes."
        ),
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    if not args.full_rebuild:
        raise SystemExit(
            "Refusing to run heavyweight news rebuild without --full-rebuild. "
            "Use narrower commands like "
            "'python -m research_pipelines.news_features.core.publish_phobert_exports' "
            "when you only need a modular export refresh."
        )
    config = get_default_config()
    preprocess_news_exports(config=config)
    tag_articles_exports(config=config)
    build_tabular_feature_exports(config=config, return_dataframe=False)
    build_phobert_sentiment_exports(config=config)
    build_embedding_feature_exports(config=config, return_dataframe=False)
    aggregate_daily_feature_exports(config=config)
    print(f"News feature pipeline complete. Outputs written under: {config.artifacts_dir}")


if __name__ == "__main__":
    main()
