"""Sequential candidate training for the PhoBERT forward-looking distillation lane."""

from __future__ import annotations

from contextlib import nullcontext
import gc
import math
from pathlib import Path
import random
from time import perf_counter
from typing import Optional, Sequence

import numpy as np
import pandas as pd

from research_pipelines.news_features.config import NewsFeaturesConfig, get_default_config
from research_pipelines.news_features.local_runtime import (
    apply_local_transformers_runtime_defaults,
    ensure_expected_cuda_runtime,
)
from research_pipelines.news_features.core.phobert_forward_looking_common import (
    FORWARD_LOOKING_TRAINING_VERSION,
    ForwardLookingCandidateSpec,
    ForwardLookingTrainerFn,
    ForwardLookingTrainingError,
    json_digest,
    load_json_payload,
    path_signature,
    safe_metric_value,
    write_forward_looking_job_status,
    write_forward_looking_progress_line,
    write_json_atomic,
    write_stage_run_summary,
)
from research_pipelines.news_features.core.phobert_forward_looking_stage import (
    build_phobert_forward_looking_stage_dataset,
    ensure_phobert_input_cache,
    forward_looking_stage_source_signature,
)
from research_pipelines.news_features.core.phobert_forward_looking_teacher import (
    build_phobert_forward_looking_teacher_labels,
    forward_looking_teacher_source_signature,
)
from research_pipelines.news_features.io_utils import describe_path, update_manifest
from research_pipelines.supervised_label.models.baselines import compute_metrics, label_distribution


def candidate_specs(config: NewsFeaturesConfig) -> list[ForwardLookingCandidateSpec]:
    names = list(config.phobert_forward_looking_candidate_names)
    model_names = list(config.phobert_forward_looking_candidate_model_names)
    if len(names) != len(model_names):
        raise ForwardLookingTrainingError("Forward-looking candidate names and model names must have identical lengths.")
    return [ForwardLookingCandidateSpec(name, model_name) for name, model_name in zip(names, model_names)]


def forward_looking_training_signature(
    config: NewsFeaturesConfig,
    *,
    stage_manifest: dict[str, object],
    candidates: Sequence[ForwardLookingCandidateSpec],
) -> dict[str, object]:
    return {
        "training_version": FORWARD_LOOKING_TRAINING_VERSION,
        "stage_dataset": path_signature(config.phobert_forward_looking_stage_path()),
        "stage_source_signature": dict(stage_manifest.get("source_signature") or {}),
        "stage_rows": int(stage_manifest.get("stage_rows", 0)),
        "split_counts": dict(stage_manifest.get("split_counts") or {}),
        "label_distribution": dict(stage_manifest.get("label_distribution") or {}),
        "split_boundaries": dict(stage_manifest.get("split_boundaries") or {}),
        "candidate_names": [candidate.name for candidate in candidates],
        "candidate_model_names": [candidate.model_name for candidate in candidates],
        "max_length": int(config.phobert_forward_looking_max_length),
        "precision": str(config.phobert_forward_looking_precision),
        "train_micro_batch_size": int(config.phobert_forward_looking_train_micro_batch_size),
        "eval_micro_batch_size": int(config.phobert_forward_looking_eval_micro_batch_size),
        "gradient_accumulation_steps": int(config.phobert_forward_looking_gradient_accumulation_steps),
        "learning_rate": float(config.phobert_forward_looking_learning_rate),
        "weight_decay": float(config.phobert_forward_looking_weight_decay),
        "num_epochs": int(config.phobert_forward_looking_num_epochs),
        "stream_batch_rows": int(config.phobert_forward_looking_stream_batch_rows),
        "random_seed": int(config.phobert_forward_looking_random_seed),
        "prefer_local_files": bool(config.phobert_forward_looking_prefer_local_files),
        "enable_gradient_checkpointing": bool(config.phobert_forward_looking_enable_gradient_checkpointing),
    }


def stage_split_summary(stage_manifest: dict[str, object]) -> dict[str, object]:
    return {
        "stage_rows": int(stage_manifest.get("stage_rows", 0)),
        "split_counts": dict(stage_manifest.get("split_counts") or {}),
        "label_distribution": dict(stage_manifest.get("label_distribution") or {}),
        "split_boundaries": dict(stage_manifest.get("split_boundaries") or {}),
    }


def candidate_output_dir(config: NewsFeaturesConfig, run_id: str, candidate_name: str) -> Path:
    config.ensure_phobert_forward_looking_model_state()
    return config.phobert_forward_looking_model_artifacts_dir() / "runs" / str(run_id) / str(candidate_name)


def resolve_torch_dtype(config: NewsFeaturesConfig, torch, device: str):
    if str(config.phobert_forward_looking_precision) == "fp16":
        return torch.float16
    if str(config.phobert_forward_looking_precision) == "fp32":
        return torch.float32
    return torch.float16 if device == "cuda" else torch.float32


TRAIN_HEARTBEAT_SECONDS = 30.0


def create_grad_scaler(torch, *, use_amp: bool):
    if hasattr(torch, "amp") and hasattr(torch.amp, "GradScaler"):
        return torch.amp.GradScaler("cuda", enabled=use_amp)
    return torch.cuda.amp.GradScaler(enabled=use_amp)


def maybe_emit_train_heartbeat(
    *,
    config: NewsFeaturesConfig,
    state_path: Path,
    candidate: ForwardLookingCandidateSpec,
    stage_summary: dict[str, object],
    device: str,
    dtype,
    parameter_count: int,
    epoch_history: Sequence[dict[str, object]],
    epoch: int,
    total_epochs: int,
    epoch_started: float,
    last_heartbeat_at: float,
    last_heartbeat_rows: int,
    epoch_rows: int,
    optimizer_steps: int,
) -> tuple[float, int]:
    now = perf_counter()
    if now - last_heartbeat_at < TRAIN_HEARTBEAT_SECONDS:
        return last_heartbeat_at, last_heartbeat_rows

    epoch_elapsed = max(now - epoch_started, 1e-9)
    window_elapsed = max(now - last_heartbeat_at, 1e-9)
    window_rows = max(int(epoch_rows) - int(last_heartbeat_rows), 0)
    epoch_rows_per_second = float(epoch_rows / epoch_elapsed) if epoch_rows else 0.0
    window_rows_per_second = float(window_rows / window_elapsed) if window_rows else 0.0
    write_forward_looking_progress_line(
        "train",
        "candidate="
        f"{candidate.name} epoch={epoch}/{total_epochs} heartbeat "
        f"train_rows={epoch_rows} optimizer_steps={optimizer_steps} "
        f"rate={epoch_rows_per_second:.1f} rows/s window_rate={window_rows_per_second:.1f} rows/s",
    )
    write_forward_looking_job_status(
        config,
        status="running",
        phase="train",
        progress_updates={
            "current_candidate": candidate.name,
            "current_candidate_status": "in_progress",
            "current_epoch": int(epoch),
            "total_epochs": int(total_epochs),
            "epoch_train_rows": int(epoch_rows),
            "device": device,
            "current_candidate_model": candidate.model_name,
        },
        throughput_updates={
            "phase": "train",
            "unit": "rows_per_second",
            "current": epoch_rows_per_second,
            "window_rows": int(window_rows),
            "window_seconds": float(window_elapsed),
        },
    )
    write_json_atomic(
        state_path,
        {
            "status": "in_progress",
            "candidate_name": candidate.name,
            "model_name": candidate.model_name,
            "device": device,
            "dtype": str(dtype).replace("torch.", ""),
            "parameter_count": int(parameter_count),
            "stage_summary": stage_summary,
            "epoch_history": list(epoch_history),
            "current_epoch": int(epoch),
            "epoch_in_progress": {
                "epoch": int(epoch),
                "train_rows": int(epoch_rows),
                "optimizer_steps": int(optimizer_steps),
                "elapsed_seconds": float(epoch_elapsed),
                "rows_per_second": float(epoch_rows_per_second),
            },
            "last_completed_epoch": max(int(epoch) - 1, 0),
        },
    )
    return now, int(epoch_rows)


def ensure_forward_looking_stage_manifest(config: NewsFeaturesConfig) -> dict[str, object]:
    teacher_manifest_path = config.phobert_forward_looking_teacher_manifest_path()
    teacher_manifest = load_json_payload(teacher_manifest_path)
    teacher_ready = (
        config.phobert_forward_looking_teacher_labels_path().exists()
        and teacher_manifest.get("status") == "complete"
        and teacher_manifest.get("source_signature") == forward_looking_teacher_source_signature(config)
    )
    if not teacher_ready:
        build_phobert_forward_looking_teacher_labels(config=config, force_rebuild=False)

    ensure_phobert_input_cache(config)

    stage_manifest_path = config.phobert_forward_looking_stage_manifest_path()
    stage_manifest = load_json_payload(stage_manifest_path)
    stage_ready = (
        config.phobert_forward_looking_stage_path().exists()
        and stage_manifest.get("status") == "complete"
        and stage_manifest.get("source_signature") == forward_looking_stage_source_signature(config)
    )
    if not stage_ready:
        build_phobert_forward_looking_stage_dataset(config=config, force_rebuild=False)
        stage_manifest = load_json_payload(stage_manifest_path)
    return stage_manifest


def stream_stage_batches(
    stage_path: Path,
    *,
    split: str,
    columns: Sequence[str],
    batch_size: int,
):
    try:
        import pyarrow.dataset as ds
    except ImportError as exc:
        raise ImportError("Streaming forward-looking stage batches requires pyarrow.") from exc
    dataset = ds.dataset(stage_path, format="parquet")
    scanner = dataset.scanner(
        columns=list(columns),
        filter=ds.field("phobert_forward_looking_split") == str(split),
        batch_size=max(int(batch_size), 1),
    )
    yield from scanner.to_batches()


def evaluate_forward_looking_split(
    *,
    stage_path: Path,
    split: str,
    tokenizer,
    model,
    device: str,
    max_length: int,
    micro_batch_size: int,
    use_amp: bool,
    torch,
) -> dict[str, object]:
    y_true: list[int] = []
    y_pred: list[int] = []
    y_prob: list[float] = []
    loss_values: list[float] = []
    columns = [
        "phobert_forward_looking_input_text",
        "phobert_forward_looking_label",
        "phobert_forward_looking_split",
    ]
    for record_batch in stream_stage_batches(
        stage_path,
        split=split,
        columns=columns,
        batch_size=256,
    ):
        batch_df = record_batch.to_pandas()
        texts = batch_df["phobert_forward_looking_input_text"].astype(str).tolist()
        labels = batch_df["phobert_forward_looking_label"].astype(int).tolist()
        for offset in range(0, len(texts), max(int(micro_batch_size), 1)):
            micro_texts = texts[offset : offset + int(micro_batch_size)]
            micro_labels = labels[offset : offset + int(micro_batch_size)]
            encoded = tokenizer(
                micro_texts,
                padding=True,
                truncation=True,
                max_length=int(max_length),
                return_tensors="pt",
            )
            labels_tensor = torch.tensor(micro_labels, dtype=torch.long)
            encoded = {key: value.to(device) for key, value in encoded.items()}
            labels_tensor = labels_tensor.to(device)
            autocast_context = (
                torch.autocast(device_type="cuda", dtype=torch.float16, enabled=True)
                if use_amp
                else nullcontext()
            )
            with torch.no_grad():
                with autocast_context:
                    outputs = model(**encoded, labels=labels_tensor)
                logits = outputs.logits.detach().float().cpu()
                probabilities = torch.softmax(logits, dim=-1).numpy()
                loss_values.append(float(outputs.loss.detach().float().cpu().item()))
            micro_prob = probabilities[:, 1]
            micro_pred = (micro_prob >= 0.5).astype(int)
            y_true.extend(int(value) for value in micro_labels)
            y_prob.extend(float(value) for value in micro_prob.tolist())
            y_pred.extend(int(value) for value in micro_pred.tolist())
    if not y_true:
        return {
            "row_count": 0,
            "metrics": {
                "accuracy": None,
                "precision": None,
                "recall": None,
                "f1": None,
                "roc_auc": None,
            },
            "mean_loss": None,
            "label_distribution": {"count": 0, "positive": 0, "negative": 0},
        }
    metrics = compute_metrics(y_true=y_true, y_pred=y_pred, y_prob=y_prob)
    return {
        "row_count": int(len(y_true)),
        "metrics": metrics,
        "mean_loss": float(np.mean(loss_values)) if loss_values else None,
        "label_distribution": label_distribution(y_true),
    }


def default_train_forward_looking_candidate(
    candidate: ForwardLookingCandidateSpec,
    config: NewsFeaturesConfig,
    stage_path: Path,
    output_dir: Path,
    stage_summary: dict[str, object],
) -> dict[str, object]:
    apply_local_transformers_runtime_defaults(config)
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except ImportError as exc:
        raise ImportError(
            "Forward-looking PhoBERT training requires torch and transformers. Install project dependencies first."
        ) from exc
    ensure_expected_cuda_runtime(torch, context="PhoBERT forward-looking train")

    output_dir.mkdir(parents=True, exist_ok=True)
    state_path = output_dir / "candidate_state.json"
    metrics_path = output_dir / "metrics.json"
    model_dir = output_dir / "model"
    candidate_started = perf_counter()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = resolve_torch_dtype(config, torch, device)
    use_amp = device == "cuda" and dtype == torch.float16
    random.seed(int(config.phobert_forward_looking_random_seed))
    np.random.seed(int(config.phobert_forward_looking_random_seed))
    torch.manual_seed(int(config.phobert_forward_looking_random_seed))
    if device == "cuda":
        torch.cuda.manual_seed_all(int(config.phobert_forward_looking_random_seed))

    tokenizer_kwargs = {"use_fast": False}
    if config.phobert_forward_looking_prefer_local_files:
        tokenizer_kwargs["local_files_only"] = True
    tokenizer = AutoTokenizer.from_pretrained(candidate.model_name, **tokenizer_kwargs)

    model_kwargs: dict[str, object] = {
        "num_labels": 2,
        "ignore_mismatched_sizes": True,
    }
    if config.phobert_forward_looking_prefer_local_files:
        model_kwargs["local_files_only"] = True
    try:
        model = AutoModelForSequenceClassification.from_pretrained(candidate.model_name, **model_kwargs)
    except ValueError as exc:
        if "Due to a serious vulnerability issue in `torch.load`" not in str(exc):
            raise
        # The explicit backbone list for this lane is trusted operator input.
        # When a repo exposes only legacy `.bin` weights under torch<2.6,
        # retry once with `weights_only=False`, then immediately re-save the
        # trained checkpoint as safetensors for the local resume path.
        write_forward_looking_progress_line(
            "train",
            f"candidate={candidate.name} retrying model load with weights_only=False for trusted backbone {candidate.model_name}",
        )
        model = AutoModelForSequenceClassification.from_pretrained(
            candidate.model_name,
            weights_only=False,
            **model_kwargs,
        )
    model.config.id2label = {0: "NOT_FORWARD_LOOKING", 1: "FORWARD_LOOKING"}
    model.config.label2id = {"NOT_FORWARD_LOOKING": 0, "FORWARD_LOOKING": 1}
    if config.phobert_forward_looking_enable_gradient_checkpointing and hasattr(model, "gradient_checkpointing_enable"):
        model.gradient_checkpointing_enable()
        if hasattr(model.config, "use_cache"):
            model.config.use_cache = False
    model.to(device)

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(config.phobert_forward_looking_learning_rate),
        weight_decay=float(config.phobert_forward_looking_weight_decay),
    )
    scaler = create_grad_scaler(torch, use_amp=use_amp)
    parameter_count = int(sum(int(parameter.numel()) for parameter in model.parameters()))
    epoch_history: list[dict[str, object]] = []
    best_epoch = -1
    best_val_f1 = float("-inf")
    split_counts = dict(stage_summary.get("split_counts") or {})
    train_rows_target = int(split_counts.get("train", 0))
    val_rows_target = int(split_counts.get("val", 0))
    write_forward_looking_progress_line(
        "train",
        "candidate="
        f"{candidate.name} runtime device={device} dtype={str(dtype).replace('torch.', '')} "
        f"amp={use_amp} train_rows={train_rows_target} val_rows={val_rows_target}",
    )
    write_json_atomic(
        state_path,
        {
            "status": "in_progress",
            "candidate_name": candidate.name,
            "model_name": candidate.model_name,
            "device": device,
            "dtype": str(dtype).replace("torch.", ""),
            "parameter_count": int(parameter_count),
            "stage_summary": stage_summary,
            "epoch_history": [],
            "current_epoch": 0,
            "last_completed_epoch": 0,
        },
    )

    for epoch in range(1, int(config.phobert_forward_looking_num_epochs) + 1):
        epoch_started = perf_counter()
        last_heartbeat_at = epoch_started
        last_heartbeat_rows = 0
        write_forward_looking_progress_line(
            "train",
            "candidate="
            f"{candidate.name} epoch={epoch}/{int(config.phobert_forward_looking_num_epochs)} start "
            f"device={device} train_rows_target={train_rows_target}",
        )
        write_forward_looking_job_status(
            config,
            status="running",
            phase="train",
            progress_updates={
                "current_candidate": candidate.name,
                "current_candidate_status": "in_progress",
                "current_epoch": int(epoch),
                "total_epochs": int(config.phobert_forward_looking_num_epochs),
                "epoch_train_rows": 0,
                "device": device,
                "current_candidate_model": candidate.model_name,
            },
            throughput_updates={
                "phase": "train",
                "unit": "rows_per_second",
                "current": 0.0,
                "window_rows": 0,
                "window_seconds": 0.0,
            },
        )
        model.train()
        optimizer.zero_grad(set_to_none=True)
        epoch_loss = 0.0
        epoch_rows = 0
        optimizer_steps = 0
        accumulation_count = 0
        for record_batch in stream_stage_batches(
            stage_path,
            split="train",
            columns=[
                "phobert_forward_looking_input_text",
                "phobert_forward_looking_label",
                "phobert_forward_looking_split",
            ],
            batch_size=int(config.phobert_forward_looking_stream_batch_rows),
        ):
            batch_df = record_batch.to_pandas()
            if batch_df.empty:
                continue
            batch_df = batch_df.sample(frac=1.0, random_state=int(config.phobert_forward_looking_random_seed) + epoch).reset_index(drop=True)
            texts = batch_df["phobert_forward_looking_input_text"].astype(str).tolist()
            labels = batch_df["phobert_forward_looking_label"].astype(int).tolist()
            for offset in range(0, len(texts), int(config.phobert_forward_looking_train_micro_batch_size)):
                micro_texts = texts[offset : offset + int(config.phobert_forward_looking_train_micro_batch_size)]
                micro_labels = labels[offset : offset + int(config.phobert_forward_looking_train_micro_batch_size)]
                encoded = tokenizer(
                    micro_texts,
                    padding=True,
                    truncation=True,
                    max_length=int(config.phobert_forward_looking_max_length),
                    return_tensors="pt",
                )
                labels_tensor = torch.tensor(micro_labels, dtype=torch.long)
                encoded = {key: value.to(device) for key, value in encoded.items()}
                labels_tensor = labels_tensor.to(device)
                autocast_context = (
                    torch.autocast(device_type="cuda", dtype=torch.float16, enabled=True)
                    if use_amp
                    else nullcontext()
                )
                with autocast_context:
                    outputs = model(**encoded, labels=labels_tensor)
                    loss = outputs.loss / int(config.phobert_forward_looking_gradient_accumulation_steps)
                if use_amp:
                    scaler.scale(loss).backward()
                else:
                    loss.backward()
                epoch_loss += float(loss.detach().float().cpu().item()) * int(
                    config.phobert_forward_looking_gradient_accumulation_steps
                )
                epoch_rows += int(len(micro_labels))
                accumulation_count += 1
                should_step = accumulation_count >= int(config.phobert_forward_looking_gradient_accumulation_steps)
                if should_step:
                    if use_amp:
                        scaler.unscale_(optimizer)
                    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                    if use_amp:
                        scaler.step(optimizer)
                        scaler.update()
                    else:
                        optimizer.step()
                    optimizer.zero_grad(set_to_none=True)
                    optimizer_steps += 1
                    accumulation_count = 0
                last_heartbeat_at, last_heartbeat_rows = maybe_emit_train_heartbeat(
                    config=config,
                    state_path=state_path,
                    candidate=candidate,
                    stage_summary=stage_summary,
                    device=device,
                    dtype=dtype,
                    parameter_count=parameter_count,
                    epoch_history=epoch_history,
                    epoch=epoch,
                    total_epochs=int(config.phobert_forward_looking_num_epochs),
                    epoch_started=epoch_started,
                    last_heartbeat_at=last_heartbeat_at,
                    last_heartbeat_rows=last_heartbeat_rows,
                    epoch_rows=epoch_rows,
                    optimizer_steps=optimizer_steps,
                )
        if accumulation_count > 0:
            if use_amp:
                scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            if use_amp:
                scaler.step(optimizer)
                scaler.update()
            else:
                optimizer.step()
            optimizer.zero_grad(set_to_none=True)
            optimizer_steps += 1

        model.eval()
        val_summary = evaluate_forward_looking_split(
            stage_path=stage_path,
            split="val",
            tokenizer=tokenizer,
            model=model,
            device=device,
            max_length=int(config.phobert_forward_looking_max_length),
            micro_batch_size=int(config.phobert_forward_looking_eval_micro_batch_size),
            use_amp=use_amp,
            torch=torch,
        )
        epoch_summary = {
            "epoch": int(epoch),
            "train_rows": int(epoch_rows),
            "optimizer_steps": int(optimizer_steps),
            "mean_train_loss": float(epoch_loss / max(epoch_rows, 1)),
            "val_summary": val_summary,
        }
        epoch_history.append(epoch_summary)
        epoch_elapsed = max(perf_counter() - epoch_started, 1e-9)
        epoch_rows_per_second = float(epoch_rows / epoch_elapsed) if epoch_rows else 0.0
        val_metrics = dict(val_summary.get("metrics") or {})
        write_forward_looking_progress_line(
            "train",
            "candidate="
            f"{candidate.name} epoch={epoch}/{int(config.phobert_forward_looking_num_epochs)} "
            f"train_rows={epoch_rows} val_f1={val_metrics.get('f1')} "
            f"val_roc_auc={val_metrics.get('roc_auc')} rate={epoch_rows_per_second:.1f} rows/s",
        )
        write_forward_looking_job_status(
            config,
            status="running",
            phase="train",
            progress_updates={
                "current_candidate": candidate.name,
                "current_candidate_status": "in_progress",
                "current_epoch": int(epoch),
                "total_epochs": int(config.phobert_forward_looking_num_epochs),
                "epoch_train_rows": int(epoch_rows),
                "device": device,
                "current_candidate_model": candidate.model_name,
            },
            throughput_updates={
                "phase": "train",
                "unit": "rows_per_second",
                "current": epoch_rows_per_second,
                "window_rows": int(epoch_rows),
                "window_seconds": float(epoch_elapsed),
            },
        )
        write_json_atomic(
            state_path,
            {
                "status": "in_progress",
                "candidate_name": candidate.name,
                "model_name": candidate.model_name,
                "device": device,
                "dtype": str(dtype).replace("torch.", ""),
                "parameter_count": int(parameter_count),
                "stage_summary": stage_summary,
                "epoch_history": epoch_history,
                "last_completed_epoch": int(epoch),
            },
        )
        current_val_f1 = safe_metric_value(val_summary["metrics"].get("f1"))
        if best_epoch < 0 or current_val_f1 > best_val_f1:
            best_val_f1 = current_val_f1
            best_epoch = int(epoch)
            model.save_pretrained(model_dir, safe_serialization=True)
            tokenizer.save_pretrained(model_dir)

    del model
    gc.collect()
    if device == "cuda":
        torch.cuda.empty_cache()

    reloaded_tokenizer = AutoTokenizer.from_pretrained(model_dir, use_fast=False, local_files_only=True)
    reloaded_model = AutoModelForSequenceClassification.from_pretrained(model_dir, local_files_only=True)
    reloaded_model.to(device)
    reloaded_model.eval()
    train_summary = evaluate_forward_looking_split(
        stage_path=stage_path,
        split="train",
        tokenizer=reloaded_tokenizer,
        model=reloaded_model,
        device=device,
        max_length=int(config.phobert_forward_looking_max_length),
        micro_batch_size=int(config.phobert_forward_looking_eval_micro_batch_size),
        use_amp=use_amp,
        torch=torch,
    )
    val_summary = evaluate_forward_looking_split(
        stage_path=stage_path,
        split="val",
        tokenizer=reloaded_tokenizer,
        model=reloaded_model,
        device=device,
        max_length=int(config.phobert_forward_looking_max_length),
        micro_batch_size=int(config.phobert_forward_looking_eval_micro_batch_size),
        use_amp=use_amp,
        torch=torch,
    )
    test_summary = evaluate_forward_looking_split(
        stage_path=stage_path,
        split="test",
        tokenizer=reloaded_tokenizer,
        model=reloaded_model,
        device=device,
        max_length=int(config.phobert_forward_looking_max_length),
        micro_batch_size=int(config.phobert_forward_looking_eval_micro_batch_size),
        use_amp=use_amp,
        torch=torch,
    )
    result = {
        "candidate_name": candidate.name,
        "model_name": candidate.model_name,
        "model_dir": str(model_dir),
        "state_path": str(state_path),
        "metrics_path": str(metrics_path),
        "parameter_count": int(parameter_count),
        "device": device,
        "dtype": str(dtype).replace("torch.", ""),
        "best_epoch": int(best_epoch),
        "epoch_history": epoch_history,
        "train_summary": train_summary,
        "val_summary": val_summary,
        "test_summary": test_summary,
        "training_args": {
            "max_length": int(config.phobert_forward_looking_max_length),
            "train_micro_batch_size": int(config.phobert_forward_looking_train_micro_batch_size),
            "eval_micro_batch_size": int(config.phobert_forward_looking_eval_micro_batch_size),
            "gradient_accumulation_steps": int(config.phobert_forward_looking_gradient_accumulation_steps),
            "learning_rate": float(config.phobert_forward_looking_learning_rate),
            "weight_decay": float(config.phobert_forward_looking_weight_decay),
            "num_epochs": int(config.phobert_forward_looking_num_epochs),
            "stream_batch_rows": int(config.phobert_forward_looking_stream_batch_rows),
            "prefer_local_files": bool(config.phobert_forward_looking_prefer_local_files),
            "enable_gradient_checkpointing": bool(config.phobert_forward_looking_enable_gradient_checkpointing),
        },
    }
    candidate_elapsed = max(perf_counter() - candidate_started, 1e-9)
    write_forward_looking_progress_line(
        "train",
        "candidate="
        f"{candidate.name} complete best_epoch={best_epoch} "
        f"val_f1={(val_summary.get('metrics') or {}).get('f1')} "
        f"test_f1={(test_summary.get('metrics') or {}).get('f1')} "
        f"elapsed={candidate_elapsed:.1f}s",
    )
    write_json_atomic(metrics_path, result)
    write_json_atomic(
        state_path,
        {
            "status": "complete",
            **result,
        },
    )
    del reloaded_model
    del reloaded_tokenizer
    gc.collect()
    if device == "cuda":
        torch.cuda.empty_cache()
    return result


def select_winner(
    *,
    candidates: Sequence[ForwardLookingCandidateSpec],
    completed_entries: Sequence[dict[str, object]],
) -> dict[str, object]:
    candidate_order = {candidate.name: index for index, candidate in enumerate(candidates)}

    def score(entry: dict[str, object]) -> tuple[float, float, float, int]:
        val_summary = dict(entry.get("val_summary") or {})
        val_metrics = dict(val_summary.get("metrics") or {})
        return (
            safe_metric_value(val_metrics.get("f1")),
            safe_metric_value(val_metrics.get("roc_auc")),
            -float(entry.get("parameter_count", math.inf)),
            -int(candidate_order.get(str(entry.get("candidate_name", "")), 10_000)),
        )

    winner = max(completed_entries, key=score)
    return {
        "candidate_name": str(winner.get("candidate_name", "")),
        "model_name": str(winner.get("model_name", "")),
        "model_dir": str(winner.get("model_dir", "")),
        "parameter_count": int(winner.get("parameter_count", 0)),
        "selection_metric": {
            "val_f1": safe_metric_value((winner.get("val_summary") or {}).get("metrics", {}).get("f1")),
            "val_roc_auc": safe_metric_value((winner.get("val_summary") or {}).get("metrics", {}).get("roc_auc")),
        },
        "test_metrics": dict((winner.get("test_summary") or {}).get("metrics") or {}),
    }


def train_phobert_forward_looking_candidates(
    config: Optional[NewsFeaturesConfig] = None,
    *,
    trainer_fn: Optional[ForwardLookingTrainerFn] = None,
    candidate_names: Optional[Sequence[str]] = None,
    rerun_failed: bool = False,
) -> dict[str, object]:
    config = config or get_default_config()
    config.ensure_directories()
    config.ensure_phobert_forward_looking_model_state()
    stage_manifest = ensure_forward_looking_stage_manifest(config)
    stage_rows = int(stage_manifest.get("stage_rows", 0))
    if stage_rows <= 0:
        empty_summary = {
            "status": "no_stage_rows",
            "completed_candidates": 0,
            "failed_candidates": 0,
            "winner": None,
        }
        write_stage_run_summary(
            mode="news_forward_looking_winner_selection",
            name="phobert_forward_looking_winner_selection",
            summary=empty_summary,
            artifacts={"training_manifest": config.phobert_forward_looking_training_manifest_path()},
            metadata={"reason": "stage_dataset_empty"},
        )
        write_forward_looking_progress_line("train", "skipping candidate training because stage_rows=0")
        write_forward_looking_job_status(
            config,
            status="no_stage_rows",
            phase="train",
            progress_updates={
                "stage_rows": stage_rows,
                "completed_candidates": 0,
                "failed_candidates": 0,
                "winner": None,
            },
        )
        return empty_summary

    available_candidates = candidate_specs(config)
    if candidate_names:
        requested = {str(name) for name in candidate_names}
        available_candidates = [candidate for candidate in available_candidates if candidate.name in requested]
        if not available_candidates:
            raise ForwardLookingTrainingError("No matching forward-looking candidate names were requested.")

    trainer = trainer_fn or default_train_forward_looking_candidate
    training_manifest_path = config.phobert_forward_looking_training_manifest_path()
    existing_manifest = load_json_payload(training_manifest_path)
    run_signature = forward_looking_training_signature(
        config,
        stage_manifest=stage_manifest,
        candidates=available_candidates,
    )
    run_id = json_digest(run_signature)[:12]
    manifest = existing_manifest
    if existing_manifest.get("run_signature") != run_signature:
        manifest = {
            "training_version": FORWARD_LOOKING_TRAINING_VERSION,
            "status": "in_progress",
            "run_signature": run_signature,
            "run_id": run_id,
            "stage_summary": stage_split_summary(stage_manifest),
            "candidates": {},
            "winner": None,
            "created_at_utc": pd.Timestamp.utcnow().isoformat(),
        }
    else:
        manifest["status"] = "in_progress"
        manifest["run_id"] = run_id
        manifest.setdefault("candidates", {})
    write_json_atomic(training_manifest_path, manifest)
    write_forward_looking_progress_line(
        "train",
        f"candidate plan={','.join(candidate.name for candidate in available_candidates)} stage_rows={stage_rows}",
    )
    write_forward_looking_job_status(
        config,
        status="running",
        phase="train",
        progress_updates={
            "stage_rows": stage_rows,
            "run_id": run_id,
            "candidate_names": [candidate.name for candidate in available_candidates],
            "completed_candidates": 0,
            "failed_candidates": 0,
            "current_candidate": None,
            "current_candidate_status": None,
        },
        throughput_updates={"phase": "train", "unit": "rows_per_second", "current": None},
    )

    completed_count = 0
    failed_count = 0
    for candidate in available_candidates:
        entry = dict((manifest.get("candidates") or {}).get(candidate.name) or {})
        if entry.get("status") == "complete" and Path(str(entry.get("model_dir", ""))).exists():
            completed_count += 1
            continue
        if entry.get("status") == "failed" and not rerun_failed:
            failed_count += 1
            continue

        output_dir = candidate_output_dir(config, run_id, candidate.name)
        output_dir.mkdir(parents=True, exist_ok=True)
        write_forward_looking_progress_line("train", f"starting candidate={candidate.name} model={candidate.model_name}")
        write_forward_looking_job_status(
            config,
            status="running",
            phase="train",
            progress_updates={
                "current_candidate": candidate.name,
                "current_candidate_model": candidate.model_name,
                "current_candidate_status": "in_progress",
                "completed_candidates": int(completed_count),
                "failed_candidates": int(failed_count),
            },
        )
        entry = {
            "candidate_name": candidate.name,
            "model_name": candidate.model_name,
            "output_dir": str(output_dir),
            "status": "in_progress",
            "started_at_utc": pd.Timestamp.utcnow().isoformat(),
        }
        manifest["candidates"][candidate.name] = entry
        write_json_atomic(training_manifest_path, manifest)

        try:
            result = trainer(
                candidate,
                config,
                config.phobert_forward_looking_stage_path(),
                output_dir,
                stage_split_summary(stage_manifest),
            )
            entry.update(result)
            entry["status"] = "complete"
            entry["completed_at_utc"] = pd.Timestamp.utcnow().isoformat()
            manifest["candidates"][candidate.name] = entry
            completed_count += 1
            write_forward_looking_progress_line(
                "train",
                "candidate="
                f"{candidate.name} complete val_f1={((entry.get('val_summary') or {}).get('metrics') or {}).get('f1')} "
                f"test_f1={((entry.get('test_summary') or {}).get('metrics') or {}).get('f1')}",
            )
            write_forward_looking_job_status(
                config,
                status="running",
                phase="train",
                progress_updates={
                    "current_candidate": candidate.name,
                    "current_candidate_model": candidate.model_name,
                    "current_candidate_status": "complete",
                    "completed_candidates": int(completed_count),
                    "failed_candidates": int(failed_count),
                    "best_epoch": int(entry.get("best_epoch", 0)),
                },
            )
            write_stage_run_summary(
                mode="news_forward_looking_candidate_train",
                name=f"phobert_forward_looking_candidate_{candidate.name}",
                summary={
                    "status": "complete",
                    "candidate_name": candidate.name,
                    "model_name": candidate.model_name,
                    "best_epoch": int(entry.get("best_epoch", 0)),
                    "val_metrics": dict((entry.get("val_summary") or {}).get("metrics") or {}),
                    "test_metrics": dict((entry.get("test_summary") or {}).get("metrics") or {}),
                },
                artifacts={
                    "candidate_output_dir": output_dir,
                    "training_manifest": training_manifest_path,
                },
            )
        except Exception as exc:
            entry["status"] = "failed"
            entry["error"] = f"{type(exc).__name__}: {exc}"
            entry["completed_at_utc"] = pd.Timestamp.utcnow().isoformat()
            manifest["candidates"][candidate.name] = entry
            failed_count += 1
            write_forward_looking_progress_line("train", f"candidate={candidate.name} failed: {entry['error']}")
            write_forward_looking_job_status(
                config,
                status="running",
                phase="train",
                progress_updates={
                    "current_candidate": candidate.name,
                    "current_candidate_model": candidate.model_name,
                    "current_candidate_status": "failed",
                    "completed_candidates": int(completed_count),
                    "failed_candidates": int(failed_count),
                },
                error=entry["error"],
            )
            write_stage_run_summary(
                mode="news_forward_looking_candidate_train",
                name=f"phobert_forward_looking_candidate_{candidate.name}",
                summary={
                    "status": "failed",
                    "candidate_name": candidate.name,
                    "model_name": candidate.model_name,
                    "error": entry["error"],
                },
                artifacts={
                    "candidate_output_dir": output_dir,
                    "training_manifest": training_manifest_path,
                },
            )
        finally:
            write_json_atomic(training_manifest_path, manifest)

    completed_entries = [
        dict(entry)
        for entry in (manifest.get("candidates") or {}).values()
        if str(entry.get("status", "")) == "complete"
    ]
    if completed_entries:
        winner = select_winner(candidates=available_candidates, completed_entries=completed_entries)
        manifest["winner"] = winner
        manifest["status"] = "complete"
        manifest["completed_at_utc"] = pd.Timestamp.utcnow().isoformat()
        write_json_atomic(config.phobert_forward_looking_latest_winner_path(), winner)
        update_manifest(
            config=config,
            phobert_forward_looking_winner_candidate=str(winner["candidate_name"]),
            phobert_forward_looking_winner_model_dir=describe_path(Path(str(winner["model_dir"])), config=config),
        )
        write_stage_run_summary(
            mode="news_forward_looking_winner_selection",
            name="phobert_forward_looking_winner_selection",
            summary={
                "status": "complete",
                "completed_candidates": int(len(completed_entries)),
                "failed_candidates": int(failed_count),
                "winner": winner,
            },
            artifacts={
                "training_manifest": training_manifest_path,
                "latest_winner": config.phobert_forward_looking_latest_winner_path(),
            },
        )
        write_forward_looking_progress_line(
            "winner_selection",
            f"winner={winner['candidate_name']} completed_candidates={len(completed_entries)} failed_candidates={failed_count}",
        )
    else:
        manifest["winner"] = None
        manifest["status"] = "no_winner"
        manifest["completed_at_utc"] = pd.Timestamp.utcnow().isoformat()
        write_stage_run_summary(
            mode="news_forward_looking_winner_selection",
            name="phobert_forward_looking_winner_selection",
            summary={
                "status": "no_winner",
                "completed_candidates": 0,
                "failed_candidates": int(failed_count),
                "winner": None,
            },
            artifacts={"training_manifest": training_manifest_path},
        )
        write_forward_looking_progress_line(
            "winner_selection",
            f"no winner completed_candidates=0 failed_candidates={failed_count}",
        )
    write_json_atomic(training_manifest_path, manifest)
    write_forward_looking_job_status(
        config,
        status=str(manifest.get("status", "unknown")),
        phase="winner_selection",
        progress_updates={
            "current_candidate": None,
            "current_candidate_status": None,
            "completed_candidates": int(len(completed_entries)),
            "failed_candidates": int(failed_count),
            "winner": manifest.get("winner"),
        },
    )
    return {
        "status": str(manifest.get("status", "unknown")),
        "completed_candidates": int(len(completed_entries)),
        "failed_candidates": int(failed_count),
        "winner": manifest.get("winner"),
    }
