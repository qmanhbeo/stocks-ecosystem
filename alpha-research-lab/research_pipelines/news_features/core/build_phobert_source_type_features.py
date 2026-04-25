"""Publish additive PhoBERT source-type datasets from the trained local winner."""

from __future__ import annotations

import json
from time import perf_counter

from research_pipelines.news_features.config import get_default_config
from research_pipelines.news_features.local_runtime import apply_local_transformers_runtime_defaults
from research_pipelines.news_features.core.phobert_binary_head_common import SOURCE_TYPE_SPEC
from research_pipelines.news_features.core.phobert_binary_head_publish import build_binary_head_feature_exports


def main() -> None:
    config = get_default_config()
    apply_local_transformers_runtime_defaults(config)
    started = perf_counter()
    daily = build_binary_head_feature_exports(SOURCE_TYPE_SPEC, config=config)
    elapsed = perf_counter() - started
    print(
        f"PhoBERT source-type publish complete in {elapsed:.1f}s: "
        f"{json.dumps({'daily_rows': int(len(daily))}, ensure_ascii=False)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
