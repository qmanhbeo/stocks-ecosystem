"""Sequential orchestration for the PhoBERT forward-looking distillation lane."""

from __future__ import annotations

from time import perf_counter
from typing import Optional, Sequence

from research_pipelines.news_features.config import NewsFeaturesConfig, get_default_config
from research_pipelines.news_features.core.phobert_forward_looking_common import (
    ForwardLookingTrainerFn,
    current_utc_timestamp,
    write_forward_looking_job_status,
    write_forward_looking_progress_line,
)
from research_pipelines.news_features.core.phobert_forward_looking_stage import (
    build_phobert_forward_looking_stage_dataset,
)
from research_pipelines.news_features.core.phobert_forward_looking_teacher import (
    build_phobert_forward_looking_teacher_labels,
)
from research_pipelines.news_features.core.phobert_forward_looking_train import (
    train_phobert_forward_looking_candidates,
)


def run_phobert_forward_looking_pipeline(
    config: Optional[NewsFeaturesConfig] = None,
    *,
    stages: Optional[Sequence[str]] = None,
    trainer_fn: Optional[ForwardLookingTrainerFn] = None,
    candidate_names: Optional[Sequence[str]] = None,
    rerun_failed: bool = False,
) -> dict[str, object]:
    config = config or get_default_config()
    selected_stages = [str(stage).strip().lower() for stage in (stages or ["all"])]
    if "all" in selected_stages:
        selected_stages = ["teacher", "stage", "train"]
    started_at = current_utc_timestamp()
    progress_state: dict[str, object] = {
        "selected_stages": list(selected_stages),
        "completed_stages": [],
        "candidate_filter": list(candidate_names or []),
        "rerun_failed": bool(rerun_failed),
    }
    write_forward_looking_progress_line(
        "bootstrap",
        f"start stages={','.join(selected_stages)} candidate_filter={progress_state['candidate_filter'] or 'all'}",
    )
    write_forward_looking_job_status(
        config,
        status="running",
        phase="bootstrap",
        progress_updates=progress_state,
        throughput_updates={"unit": None, "current": None},
        started_at=started_at,
    )
    result: dict[str, object] = {}
    current_phase = "bootstrap"
    try:
        if "teacher" in selected_stages:
            current_phase = "teacher"
            write_forward_looking_progress_line("teacher", "building or reusing teacher labels")
            teacher_started = perf_counter()
            teacher_df = build_phobert_forward_looking_teacher_labels(config=config)
            teacher_elapsed = max(perf_counter() - teacher_started, 1e-9)
            teacher_rows = int(len(teacher_df))
            result["teacher_rows"] = teacher_rows
            progress_state["completed_stages"] = [*progress_state["completed_stages"], "teacher"]
            progress_state["teacher_rows"] = teacher_rows
            write_forward_looking_progress_line(
                "teacher",
                f"complete rows={teacher_rows} elapsed={teacher_elapsed:.1f}s rate={teacher_rows / teacher_elapsed:.1f} rows/s",
            )
            write_forward_looking_job_status(
                config,
                status="running",
                phase="teacher",
                progress_updates=progress_state,
                throughput_updates={
                    "phase": "teacher",
                    "unit": "rows_per_second",
                    "current": float(teacher_rows / teacher_elapsed) if teacher_rows else 0.0,
                    "window_rows": teacher_rows,
                    "window_seconds": float(teacher_elapsed),
                },
            )
        if "stage" in selected_stages:
            current_phase = "stage"
            write_forward_looking_progress_line("stage", "building or reusing tagged-only stage dataset")
            stage_started = perf_counter()
            stage_df = build_phobert_forward_looking_stage_dataset(config=config)
            stage_elapsed = max(perf_counter() - stage_started, 1e-9)
            stage_rows = int(len(stage_df))
            result["stage_rows"] = stage_rows
            progress_state["completed_stages"] = [*progress_state["completed_stages"], "stage"]
            progress_state["stage_rows"] = stage_rows
            write_forward_looking_progress_line(
                "stage",
                f"complete rows={stage_rows} elapsed={stage_elapsed:.1f}s rate={stage_rows / stage_elapsed:.1f} rows/s",
            )
            write_forward_looking_job_status(
                config,
                status="running",
                phase="stage",
                progress_updates=progress_state,
                throughput_updates={
                    "phase": "stage",
                    "unit": "rows_per_second",
                    "current": float(stage_rows / stage_elapsed) if stage_rows else 0.0,
                    "window_rows": stage_rows,
                    "window_seconds": float(stage_elapsed),
                },
            )
        if "train" in selected_stages:
            current_phase = "train"
            write_forward_looking_progress_line("train", "starting sequential candidate training")
            result["training"] = train_phobert_forward_looking_candidates(
                config=config,
                trainer_fn=trainer_fn,
                candidate_names=candidate_names,
                rerun_failed=rerun_failed,
            )
            progress_state["completed_stages"] = [*progress_state["completed_stages"], "train"]
            progress_state["training"] = dict(result["training"])
        final_status = str((result.get("training") or {}).get("status") or "complete")
        progress_state["result"] = dict(result)
        write_forward_looking_progress_line("complete", f"pipeline finished with status={final_status}")
        write_forward_looking_job_status(
            config,
            status=final_status,
            phase="complete",
            progress_updates=progress_state,
        )
        return result
    except Exception as exc:
        write_forward_looking_progress_line(current_phase, f"failed: {type(exc).__name__}: {exc}")
        write_forward_looking_job_status(
            config,
            status="failed",
            phase=current_phase,
            progress_updates=progress_state,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise
