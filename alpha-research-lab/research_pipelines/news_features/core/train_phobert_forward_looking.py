"""Thin CLI and compatibility wrapper for the PhoBERT forward-looking lane."""

from __future__ import annotations

import argparse
import json
from time import perf_counter

from research_pipelines.news_features.config import get_default_config
from research_pipelines.news_features.core.phobert_forward_looking_common import (
    ForwardLookingCandidateSpec,
    ForwardLookingTrainerFn,
    ForwardLookingTrainingError,
)
from research_pipelines.news_features.core.phobert_forward_looking_pipeline import (
    run_phobert_forward_looking_pipeline,
)
from research_pipelines.news_features.core.phobert_forward_looking_stage import (
    build_phobert_forward_looking_stage_dataset,
)
from research_pipelines.news_features.core.phobert_forward_looking_teacher import (
    build_phobert_forward_looking_teacher_labels,
)
from research_pipelines.news_features.core.phobert_forward_looking_train import (
    default_train_forward_looking_candidate,
    train_phobert_forward_looking_candidates,
)


__all__ = [
    "ForwardLookingCandidateSpec",
    "ForwardLookingTrainerFn",
    "ForwardLookingTrainingError",
    "build_phobert_forward_looking_teacher_labels",
    "build_phobert_forward_looking_stage_dataset",
    "default_train_forward_looking_candidate",
    "train_phobert_forward_looking_candidates",
    "run_phobert_forward_looking_pipeline",
    "build_arg_parser",
    "main",
]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Sequentially build hosted-LLM teacher labels, materialize a forward-looking "
            "PhoBERT training table, and train candidate heads one at a time."
        )
    )
    parser.add_argument(
        "--stages",
        default="all",
        help="Comma-separated subset of teacher,stage,train. Defaults to all.",
    )
    parser.add_argument(
        "--candidate-name",
        action="append",
        default=[],
        help="Optional candidate name filter. May be provided multiple times.",
    )
    parser.add_argument(
        "--rerun-failed",
        action="store_true",
        help="Rerun candidates currently marked failed in the training manifest.",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    config = get_default_config()
    overall_start = perf_counter()
    result = run_phobert_forward_looking_pipeline(
        config=config,
        stages=[stage.strip() for stage in str(args.stages).split(",") if stage.strip()],
        candidate_names=args.candidate_name or None,
        rerun_failed=bool(args.rerun_failed),
    )
    elapsed = perf_counter() - overall_start
    print(
        "PhoBERT forward-looking pipeline complete in "
        f"{elapsed:.1f}s: {json.dumps(result, ensure_ascii=False, default=str)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
