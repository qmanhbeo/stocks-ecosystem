"""Thin CLI wrapper for the PhoBERT source-type lane."""

from __future__ import annotations

import argparse
import json
from time import perf_counter

from research_pipelines.news_features.config import get_default_config
from research_pipelines.news_features.local_runtime import apply_local_transformers_runtime_defaults
from research_pipelines.news_features.core.phobert_binary_head_common import SOURCE_TYPE_SPEC
from research_pipelines.news_features.core.phobert_binary_head_pipeline import run_binary_head_pipeline


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build PhoBERT source-type teacher/stage tables and train candidates.")
    parser.add_argument("--stages", default="all", help="Comma-separated subset of teacher,stage,train. Defaults to all.")
    parser.add_argument("--candidate-name", action="append", default=[], help="Optional candidate name filter.")
    parser.add_argument("--rerun-failed", action="store_true", help="Rerun candidates currently marked failed.")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    config = get_default_config()
    apply_local_transformers_runtime_defaults(config)
    overall_start = perf_counter()
    result = run_binary_head_pipeline(
        SOURCE_TYPE_SPEC,
        config=config,
        stages=[stage.strip() for stage in str(args.stages).split(",") if stage.strip()],
        candidate_names=args.candidate_name or None,
        rerun_failed=bool(args.rerun_failed),
    )
    elapsed = perf_counter() - overall_start
    print(f"PhoBERT source-type pipeline complete in {elapsed:.1f}s: {json.dumps(result, ensure_ascii=False, default=str)}", flush=True)


if __name__ == "__main__":
    main()
