"""Sequential candidate training for PhoBERT binary local heads."""

from __future__ import annotations

from contextlib import nullcontext
import gc
import importlib.metadata
import math
from pathlib import Path
import random
import shutil
from time import perf_counter
from typing import Optional, Sequence

import numpy as np
import pandas as pd

from research_pipelines.news_features.config import NewsFeaturesConfig, get_default_config
from research_pipelines.news_features.local_runtime import (
    apply_local_transformers_runtime_defaults,
    ensure_expected_cuda_runtime,
)
from research_pipelines.news_features.core.phobert_binary_head_common import (
    BinaryHeadSpec,
    BinaryHeadTrainerFn,
    current_utc_timestamp,
    head_job_artifacts,
    head_latest_winner_path,
    head_model_artifacts_dir,
    head_stage_manifest_path,
    head_stage_path,
    head_teacher_manifest_path,
    head_training_manifest_path,
    json_digest,
    load_json_payload,
    path_signature,
    safe_metric_value,
    write_head_job_status,
    write_head_progress_line,
    write_json_atomic,
    write_stage_run_summary,
)
from research_pipelines.news_features.core.phobert_binary_head_teacher_stage import (
    binary_head_stage_source_signature,
    binary_head_teacher_source_signature,
    build_binary_head_stage_dataset,
    build_binary_head_teacher_labels,
    ensure_phobert_input_cache,
)
from research_pipelines.news_features.io_utils import describe_path, update_manifest
from research_pipelines.supervised_label.models.baselines import compute_metrics, label_distribution


class BinaryHeadTrainingError(RuntimeError):
    """Raised when a binary head training pipeline cannot proceed."""


class BinaryHeadCandidateSpec(tuple):
    __slots__ = ()

    def __new__(cls, name: str, model_name: str):
        return super().__new__(cls, (str(name), str(model_name)))

    @property
    def name(self) -> str:
        return str(self[0])

    @property
    def model_name(self) -> str:
        return str(self[1])


def candidate_specs(config: NewsFeaturesConfig) -> list[BinaryHeadCandidateSpec]:
    names = list(config.phobert_forward_looking_candidate_names)
    model_names = list(config.phobert_forward_looking_candidate_model_names)
    if len(names) != len(model_names):
        raise BinaryHeadTrainingError("PhoBERT candidate names and model names must have identical lengths.")
    return [BinaryHeadCandidateSpec(name, model_name) for name, model_name in zip(names, model_names)]


def training_signature(
    spec: BinaryHeadSpec,
    config: NewsFeaturesConfig,
    *,
    stage_manifest: dict[str, object],
    candidates: Sequence[BinaryHeadCandidateSpec],
) -> dict[str, object]:
    return {
        "training_version": 2,
        "head_name": spec.name,
        "stage_dataset": path_signature(head_stage_path(config, spec)),
        "stage_source_signature": dict(stage_manifest.get("source_signature") or {}),
        "stage_rows": int(stage_manifest.get("stage_rows", 0)),
        "split_counts": dict(stage_manifest.get("split_counts") or {}),
        "label_distribution": dict(stage_manifest.get("label_distribution") or {}),
        "split_strategy": str(stage_manifest.get("split_strategy") or config.phobert_binary_head_split_strategy(spec.name)),
        "split_label_distribution": dict(stage_manifest.get("split_label_distribution") or {}),
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
        "enable_class_weighting": bool(config.phobert_binary_head_enable_class_weighting(spec.name)),
        "default_positive_threshold": float(config.phobert_binary_head_default_positive_threshold(spec.name)),
        "threshold_search_min": float(config.phobert_binary_head_threshold_search_min),
        "threshold_search_max": float(config.phobert_binary_head_threshold_search_max),
        "threshold_search_step": float(config.phobert_binary_head_threshold_search_step),
        "training_checkpoint_steps": int(config.phobert_binary_head_training_checkpoint_steps),
    }


def stage_split_summary(stage_manifest: dict[str, object]) -> dict[str, object]:
    return {
        "stage_rows": int(stage_manifest.get("stage_rows", 0)),
        "split_counts": dict(stage_manifest.get("split_counts") or {}),
        "label_distribution": dict(stage_manifest.get("label_distribution") or {}),
        "split_strategy": str(stage_manifest.get("split_strategy") or ""),
        "split_label_distribution": dict(stage_manifest.get("split_label_distribution") or {}),
        "split_boundaries": dict(stage_manifest.get("split_boundaries") or {}),
    }


def candidate_output_dir(config: NewsFeaturesConfig, spec: BinaryHeadSpec, run_id: str, candidate_name: str) -> Path:
    return head_model_artifacts_dir(config, spec) / "runs" / str(run_id) / str(candidate_name)


def resolve_torch_dtype(config: NewsFeaturesConfig, torch, device: str):
    if str(config.phobert_forward_looking_precision) == "fp16":
        return torch.float16
    if str(config.phobert_forward_looking_precision) == "fp32":
        return torch.float32
    return torch.float16 if device == "cuda" else torch.float32


TRAIN_HEARTBEAT_SECONDS = 30.0
TRAINING_CHECKPOINT_VERSION = 1
TRAINING_CHECKPOINT_DIRNAME = "training_checkpoint"
TRAINING_CHECKPOINT_STATE_FILENAME = "trainer_state.json"
TRAINING_CHECKPOINT_OPTIMIZER_FILENAME = "optimizer.pt"
TRAINING_CHECKPOINT_SCALER_FILENAME = "scaler.pt"


def create_grad_scaler(torch, *, use_amp: bool):
    if hasattr(torch, "amp") and hasattr(torch.amp, "GradScaler"):
        return torch.amp.GradScaler("cuda", enabled=use_amp)
    return torch.cuda.amp.GradScaler(enabled=use_amp)


def candidate_training_checkpoint_dir(output_dir: Path) -> Path:
    return output_dir / TRAINING_CHECKPOINT_DIRNAME


def training_checkpoint_state_path(output_dir: Path) -> Path:
    return candidate_training_checkpoint_dir(output_dir) / TRAINING_CHECKPOINT_STATE_FILENAME


def load_training_checkpoint_state(output_dir: Path) -> dict[str, object]:
    state = load_json_payload(training_checkpoint_state_path(output_dir))
    if state.get("status") != "in_progress":
        return {}
    checkpoint_model_dir = candidate_training_checkpoint_dir(output_dir) / "model"
    if not checkpoint_model_dir.exists():
        return {}
    return state


def _replace_directory(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    source.rename(target)


def save_training_checkpoint(
    *,
    spec: BinaryHeadSpec,
    output_dir: Path,
    candidate: BinaryHeadCandidateSpec,
    model,
    tokenizer,
    optimizer,
    scaler,
    torch,
    use_amp: bool,
    epoch_history: Sequence[dict[str, object]],
    next_epoch: int,
    epoch_rows_to_skip: int,
    epoch_loss_sum: float,
    epoch_optimizer_steps: int,
    global_optimizer_steps: int,
    best_epoch: int,
    best_val_f1: float,
    checkpoint_reason: str,
) -> dict[str, object]:
    checkpoint_dir = candidate_training_checkpoint_dir(output_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    model_tmp_dir = checkpoint_dir / "model.tmp"
    model_dir = checkpoint_dir / "model"
    if model_tmp_dir.exists():
        shutil.rmtree(model_tmp_dir)
    model.save_pretrained(model_tmp_dir, safe_serialization=True)
    tokenizer.save_pretrained(model_tmp_dir)
    _replace_directory(model_tmp_dir, model_dir)

    optimizer_tmp_path = checkpoint_dir / f"{TRAINING_CHECKPOINT_OPTIMIZER_FILENAME}.tmp"
    optimizer_path = checkpoint_dir / TRAINING_CHECKPOINT_OPTIMIZER_FILENAME
    torch.save(optimizer.state_dict(), optimizer_tmp_path)
    optimizer_tmp_path.replace(optimizer_path)

    scaler_path = checkpoint_dir / TRAINING_CHECKPOINT_SCALER_FILENAME
    if use_amp and scaler is not None:
        scaler_tmp_path = checkpoint_dir / f"{TRAINING_CHECKPOINT_SCALER_FILENAME}.tmp"
        torch.save(scaler.state_dict(), scaler_tmp_path)
        scaler_tmp_path.replace(scaler_path)
    elif scaler_path.exists():
        scaler_path.unlink()

    state = {
        "status": "in_progress",
        "checkpoint_version": TRAINING_CHECKPOINT_VERSION,
        "head_name": spec.name,
        "candidate_name": candidate.name,
        "model_name": candidate.model_name,
        "checkpoint_reason": str(checkpoint_reason),
        "updated_at_utc": current_utc_timestamp(),
        "model_dir": str(model_dir),
        "optimizer_path": str(optimizer_path),
        "scaler_path": str(scaler_path) if scaler_path.exists() else None,
        "next_epoch": int(next_epoch),
        "epoch_rows_to_skip": int(epoch_rows_to_skip),
        "epoch_loss_sum": float(epoch_loss_sum),
        "epoch_optimizer_steps": int(epoch_optimizer_steps),
        "global_optimizer_steps": int(global_optimizer_steps),
        "best_epoch": int(best_epoch),
        "best_val_f1": float(best_val_f1) if math.isfinite(float(best_val_f1)) else None,
        "epoch_history": list(epoch_history),
    }
    write_json_atomic(training_checkpoint_state_path(output_dir), state)
    write_head_progress_line(
        spec,
        "train",
        "candidate="
        f"{candidate.name} checkpoint reason={checkpoint_reason} next_epoch={next_epoch} "
        f"epoch_rows_to_skip={epoch_rows_to_skip} global_optimizer_steps={global_optimizer_steps}",
    )
    return state


def mark_training_checkpoint_complete(output_dir: Path, *, result: dict[str, object]) -> None:
    checkpoint_dir = candidate_training_checkpoint_dir(output_dir)
    if not checkpoint_dir.exists():
        return
    payload = {
        "status": "complete",
        "checkpoint_version": TRAINING_CHECKPOINT_VERSION,
        "updated_at_utc": current_utc_timestamp(),
        "candidate_name": result.get("candidate_name"),
        "best_epoch": result.get("best_epoch"),
        "decision_threshold": result.get("decision_threshold"),
        "metrics_path": result.get("metrics_path"),
    }
    write_json_atomic(training_checkpoint_state_path(output_dir), payload)


def maybe_emit_train_heartbeat(
    *,
    spec: BinaryHeadSpec,
    config: NewsFeaturesConfig,
    state_path: Path,
    candidate: BinaryHeadCandidateSpec,
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
    checkpoint_state: Optional[dict[str, object]] = None,
) -> tuple[float, int]:
    now = perf_counter()
    if now - last_heartbeat_at < TRAIN_HEARTBEAT_SECONDS:
        return last_heartbeat_at, last_heartbeat_rows

    epoch_elapsed = max(now - epoch_started, 1e-9)
    window_elapsed = max(now - last_heartbeat_at, 1e-9)
    window_rows = max(int(epoch_rows) - int(last_heartbeat_rows), 0)
    epoch_rows_per_second = float(epoch_rows / epoch_elapsed) if epoch_rows else 0.0
    window_rows_per_second = float(window_rows / window_elapsed) if window_rows else 0.0
    write_head_progress_line(
        spec,
        "train",
        "candidate="
        f"{candidate.name} epoch={epoch}/{total_epochs} heartbeat "
        f"train_rows={epoch_rows} optimizer_steps={optimizer_steps} "
        f"rate={epoch_rows_per_second:.1f} rows/s window_rate={window_rows_per_second:.1f} rows/s",
    )
    write_head_job_status(
        config,
        spec,
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
            "training_checkpoint": dict(checkpoint_state or {}),
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


def ensure_stage_manifest(spec: BinaryHeadSpec, config: NewsFeaturesConfig) -> dict[str, object]:
    teacher_manifest_path = head_teacher_manifest_path(config, spec)
    teacher_manifest = load_json_payload(teacher_manifest_path)
    teacher_ready = (
        head_teacher_manifest_path(config, spec).exists()
        and head_teacher_manifest_path(config, spec).exists()
        and head_teacher_manifest_path(config, spec).parent.exists()
        and head_teacher_manifest_path(config, spec)
    )
    teacher_ready = (
        head_teacher_manifest_path(config, spec).exists()
        and head_teacher_manifest_path(config, spec).exists()
        and teacher_manifest.get("status") == "complete"
        and teacher_manifest.get("source_signature") == binary_head_teacher_source_signature(config)
    )
    if not teacher_ready:
        build_binary_head_teacher_labels(spec, config=config, force_rebuild=False)

    ensure_phobert_input_cache(config)

    stage_manifest_path = head_stage_manifest_path(config, spec)
    stage_manifest = load_json_payload(stage_manifest_path)
    stage_ready = (
        head_stage_path(config, spec).exists()
        and stage_manifest.get("status") == "complete"
        and stage_manifest.get("source_signature") == binary_head_stage_source_signature(config, spec)
    )
    if not stage_ready:
        build_binary_head_stage_dataset(spec, config=config, force_rebuild=False)
        stage_manifest = load_json_payload(stage_manifest_path)
    return stage_manifest


def stream_stage_batches(spec: BinaryHeadSpec, stage_path: Path, *, split: str, columns: Sequence[str], batch_size: int):
    try:
        import pyarrow.dataset as ds
    except ImportError as exc:
        raise ImportError("Streaming PhoBERT binary-head stage batches requires pyarrow.") from exc
    dataset = ds.dataset(stage_path, format="parquet")
    scanner = dataset.scanner(
        columns=list(columns),
        filter=ds.field(f"{spec.dataset_prefix}_split") == str(split),
        batch_size=max(int(batch_size), 1),
    )
    yield from scanner.to_batches()


def build_binary_head_loss_criterion(
    *,
    spec: BinaryHeadSpec,
    config: NewsFeaturesConfig,
    stage_path: Path,
    device: str,
    torch,
):
    label_counts = {0: 0, 1: 0}
    label_column = f"{spec.dataset_prefix}_label"
    for record_batch in stream_stage_batches(spec, stage_path, split="train", columns=[label_column], batch_size=4096):
        batch_df = record_batch.to_pandas()
        if batch_df.empty:
            continue
        counts = batch_df[label_column].astype(int).value_counts().to_dict()
        for label_value, count in counts.items():
            label_counts[int(label_value)] = label_counts.get(int(label_value), 0) + int(count)
    train_distribution = label_distribution(
        [0] * int(label_counts.get(0, 0)) + [1] * int(label_counts.get(1, 0))
    )
    positive_class_weight = None
    if (
        config.phobert_binary_head_enable_class_weighting(spec.name)
        and int(label_counts.get(0, 0)) > 0
        and int(label_counts.get(1, 0)) > 0
    ):
        positive_class_weight = float(label_counts[0] / label_counts[1])
    weight_tensor = None
    if positive_class_weight is not None:
        weight_tensor = torch.tensor([1.0, positive_class_weight], dtype=torch.float32, device=device)
    criterion = torch.nn.CrossEntropyLoss(weight=weight_tensor)
    return criterion, {
        "train_label_distribution": {key: int(value) for key, value in train_distribution.items()},
        "positive_class_weight": positive_class_weight,
        "class_weighting_enabled": bool(positive_class_weight is not None),
    }


def collect_split_predictions(
    spec: BinaryHeadSpec,
    *,
    stage_path: Path,
    split: str,
    tokenizer,
    model,
    device: str,
    max_length: int,
    micro_batch_size: int,
    use_amp: bool,
    criterion,
    torch,
) -> dict[str, object]:
    text_column = f"{spec.dataset_prefix}_input_text"
    label_column = f"{spec.dataset_prefix}_label"
    split_column = f"{spec.dataset_prefix}_split"
    y_true: list[int] = []
    y_prob: list[float] = []
    loss_values: list[float] = []
    columns = [text_column, label_column, split_column]
    was_training = bool(getattr(model, "training", False))
    had_gradient_checkpointing = bool(getattr(model, "is_gradient_checkpointing", False))
    if had_gradient_checkpointing and hasattr(model, "gradient_checkpointing_disable"):
        model.gradient_checkpointing_disable()
    model.eval()
    try:
        for record_batch in stream_stage_batches(spec, stage_path, split=split, columns=columns, batch_size=256):
            batch_df = record_batch.to_pandas()
            texts = batch_df[text_column].astype(str).tolist()
            labels = batch_df[label_column].astype(int).tolist()
            for offset in range(0, len(texts), max(int(micro_batch_size), 1)):
                micro_texts = texts[offset : offset + int(micro_batch_size)]
                micro_labels = labels[offset : offset + int(micro_batch_size)]
                encoded = tokenizer(micro_texts, padding=True, truncation=True, max_length=int(max_length), return_tensors="pt")
                labels_tensor = torch.tensor(micro_labels, dtype=torch.long)
                encoded = {key: value.to(device) for key, value in encoded.items()}
                labels_tensor = labels_tensor.to(device)
                autocast_context = (
                    torch.autocast(device_type="cuda", dtype=torch.float16, enabled=True) if use_amp else nullcontext()
                )
                with torch.no_grad():
                    with autocast_context:
                        outputs = model(**encoded)
                    logits = outputs.logits.detach().float().cpu()
                    probabilities = torch.softmax(logits, dim=-1).numpy()
                    batch_loss = criterion(outputs.logits.float(), labels_tensor)
                    loss_values.append(float(batch_loss.detach().float().cpu().item()))
                positive_prob = probabilities[:, 1]
                y_true.extend(int(value) for value in micro_labels)
                y_prob.extend(float(value) for value in positive_prob.tolist())
    finally:
        if had_gradient_checkpointing and hasattr(model, "gradient_checkpointing_enable"):
            model.gradient_checkpointing_enable()
        if was_training:
            model.train()
    if not y_true:
        return {
            "row_count": 0,
            "y_true": np.asarray([], dtype=int),
            "y_prob": np.asarray([], dtype=float),
            "mean_loss": None,
            "label_distribution": {"count": 0, "positive": 0, "negative": 0},
        }
    return {
        "row_count": int(len(y_true)),
        "y_true": np.asarray(y_true, dtype=int),
        "y_prob": np.asarray(y_prob, dtype=float),
        "mean_loss": float(np.mean(loss_values)) if loss_values else None,
        "label_distribution": label_distribution(y_true),
    }


def calibrate_positive_threshold(
    *,
    config: NewsFeaturesConfig,
    spec: BinaryHeadSpec,
    y_true: np.ndarray,
    y_prob: np.ndarray,
) -> dict[str, object]:
    default_threshold = float(config.phobert_binary_head_default_positive_threshold(spec.name))
    if y_true.size <= 0:
        return {
            "decision_threshold": default_threshold,
            "metrics": {"accuracy": None, "precision": None, "recall": None, "f1": None, "roc_auc": None},
            "predicted_positive_rate": None,
        }

    positive_rate = float(np.mean(y_true))
    threshold_values = np.arange(
        float(config.phobert_binary_head_threshold_search_min),
        float(config.phobert_binary_head_threshold_search_max) + float(config.phobert_binary_head_threshold_search_step) * 0.5,
        float(config.phobert_binary_head_threshold_search_step),
    )
    threshold_values = np.clip(threshold_values, 0.0, 1.0)
    best = None
    for threshold in threshold_values.tolist():
        predicted = (y_prob >= float(threshold)).astype(int)
        metrics = compute_metrics(y_true=y_true.tolist(), y_pred=predicted.tolist(), y_prob=y_prob.tolist())
        predicted_positive_rate = float(np.mean(predicted))
        score = (
            safe_metric_value(metrics.get("f1")),
            -abs(predicted_positive_rate - positive_rate),
            safe_metric_value(metrics.get("precision")),
            safe_metric_value(metrics.get("recall")),
            -abs(float(threshold) - default_threshold),
        )
        candidate = {
            "score": score,
            "decision_threshold": float(threshold),
            "metrics": metrics,
            "predicted_positive_rate": predicted_positive_rate,
        }
        if best is None or candidate["score"] > best["score"]:
            best = candidate
    assert best is not None
    return {
        "decision_threshold": float(best["decision_threshold"]),
        "metrics": dict(best["metrics"]),
        "predicted_positive_rate": float(best["predicted_positive_rate"]),
        "default_threshold": default_threshold,
        "search_min": float(config.phobert_binary_head_threshold_search_min),
        "search_max": float(config.phobert_binary_head_threshold_search_max),
        "search_step": float(config.phobert_binary_head_threshold_search_step),
    }


def summarize_split_predictions(
    *,
    y_true: np.ndarray,
    y_prob: np.ndarray,
    mean_loss: Optional[float],
    positive_threshold: float,
) -> dict[str, object]:
    if y_true.size <= 0:
        return {
            "row_count": 0,
            "metrics": {"accuracy": None, "precision": None, "recall": None, "f1": None, "roc_auc": None},
            "mean_loss": mean_loss,
            "label_distribution": {"count": 0, "positive": 0, "negative": 0},
            "decision_threshold": float(positive_threshold),
        }
    predicted = (y_prob >= float(positive_threshold)).astype(int)
    return {
        "row_count": int(y_true.size),
        "metrics": compute_metrics(y_true=y_true.tolist(), y_pred=predicted.tolist(), y_prob=y_prob.tolist()),
        "mean_loss": mean_loss,
        "label_distribution": label_distribution(y_true.tolist()),
        "decision_threshold": float(positive_threshold),
        "predicted_positive_rate": float(np.mean(predicted)),
    }


def evaluate_split(
    spec: BinaryHeadSpec,
    *,
    config: NewsFeaturesConfig,
    stage_path: Path,
    split: str,
    tokenizer,
    model,
    device: str,
    max_length: int,
    micro_batch_size: int,
    use_amp: bool,
    criterion,
    torch,
    positive_threshold: Optional[float] = None,
    calibrate_threshold: bool = False,
) -> dict[str, object]:
    raw_eval = collect_split_predictions(
        spec,
        stage_path=stage_path,
        split=split,
        tokenizer=tokenizer,
        model=model,
        device=device,
        max_length=max_length,
        micro_batch_size=micro_batch_size,
        use_amp=use_amp,
        criterion=criterion,
        torch=torch,
    )
    y_true = np.asarray(raw_eval.get("y_true", np.asarray([], dtype=int)), dtype=int)
    y_prob = np.asarray(raw_eval.get("y_prob", np.asarray([], dtype=float)), dtype=float)
    mean_loss = raw_eval.get("mean_loss")
    if calibrate_threshold:
        calibration = calibrate_positive_threshold(config=config, spec=spec, y_true=y_true, y_prob=y_prob)
        summary = summarize_split_predictions(
            y_true=y_true,
            y_prob=y_prob,
            mean_loss=mean_loss,
            positive_threshold=float(calibration["decision_threshold"]),
        )
        summary["threshold_calibration"] = calibration
        return summary
    decision_threshold = (
        float(positive_threshold)
        if positive_threshold is not None
        else float(config.phobert_binary_head_default_positive_threshold(spec.name))
    )
    return summarize_split_predictions(
        y_true=y_true,
        y_prob=y_prob,
        mean_loss=mean_loss,
        positive_threshold=decision_threshold,
    )


def default_train_binary_head_candidate(
    spec: BinaryHeadSpec,
    candidate: BinaryHeadCandidateSpec,
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
        raise ImportError("PhoBERT binary-head training requires torch and transformers.") from exc
    ensure_expected_cuda_runtime(torch, context=f"PhoBERT {spec.name} train")

    output_dir.mkdir(parents=True, exist_ok=True)
    state_path = output_dir / "candidate_state.json"
    metrics_path = output_dir / "metrics.json"
    model_dir = output_dir / "model"
    resume_checkpoint_state = load_training_checkpoint_state(output_dir)
    resume_checkpoint_dir = candidate_training_checkpoint_dir(output_dir)
    resume_model_dir = resume_checkpoint_dir / "model"
    candidate_started = perf_counter()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = resolve_torch_dtype(config, torch, device)
    use_amp = device == "cuda" and dtype == torch.float16
    random.seed(int(config.phobert_forward_looking_random_seed))
    np.random.seed(int(config.phobert_forward_looking_random_seed))
    torch.manual_seed(int(config.phobert_forward_looking_random_seed))
    if device == "cuda":
        torch.cuda.manual_seed_all(int(config.phobert_forward_looking_random_seed))

    load_source = str(resume_model_dir if resume_checkpoint_state else candidate.model_name)
    if resume_checkpoint_state:
        write_head_progress_line(
            spec,
            "train",
            "candidate="
            f"{candidate.name} resuming from checkpoint next_epoch={resume_checkpoint_state.get('next_epoch')} "
            f"epoch_rows_to_skip={resume_checkpoint_state.get('epoch_rows_to_skip')} "
            f"global_optimizer_steps={resume_checkpoint_state.get('global_optimizer_steps')}",
        )

    tokenizer_kwargs = {"use_fast": False}
    if config.phobert_forward_looking_prefer_local_files or resume_checkpoint_state:
        tokenizer_kwargs["local_files_only"] = True
    tokenizer = AutoTokenizer.from_pretrained(load_source, **tokenizer_kwargs)

    model_kwargs: dict[str, object] = {"num_labels": 2, "ignore_mismatched_sizes": True}
    if config.phobert_forward_looking_prefer_local_files or resume_checkpoint_state:
        model_kwargs["local_files_only"] = True
    try:
        model = AutoModelForSequenceClassification.from_pretrained(load_source, **model_kwargs)
    except ValueError as exc:
        if "Due to a serious vulnerability issue in `torch.load`" not in str(exc):
            raise
        write_head_progress_line(
            spec,
            "train",
            f"candidate={candidate.name} retrying model load with weights_only=False for trusted backbone {candidate.model_name}",
        )
        model = AutoModelForSequenceClassification.from_pretrained(load_source, weights_only=False, **model_kwargs)
    model.config.id2label = {0: spec.negative_label_name.upper(), 1: spec.positive_label_name.upper()}
    model.config.label2id = {spec.negative_label_name.upper(): 0, spec.positive_label_name.upper(): 1}
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
    if resume_checkpoint_state:
        optimizer_path = resume_checkpoint_dir / TRAINING_CHECKPOINT_OPTIMIZER_FILENAME
        if optimizer_path.exists():
            optimizer.load_state_dict(torch.load(optimizer_path, map_location=device))
        scaler_path = resume_checkpoint_dir / TRAINING_CHECKPOINT_SCALER_FILENAME
        if use_amp and scaler_path.exists():
            scaler.load_state_dict(torch.load(scaler_path, map_location=device))
    criterion, criterion_info = build_binary_head_loss_criterion(
        spec=spec,
        config=config,
        stage_path=stage_path,
        device=device,
        torch=torch,
    )
    parameter_count = int(sum(int(parameter.numel()) for parameter in model.parameters()))
    epoch_history: list[dict[str, object]] = [
        dict(item) for item in list(resume_checkpoint_state.get("epoch_history") or [])
    ]
    best_epoch = int(resume_checkpoint_state.get("best_epoch", -1) or -1)
    saved_best_val_f1 = resume_checkpoint_state.get("best_val_f1")
    best_val_f1 = float(saved_best_val_f1) if saved_best_val_f1 is not None else float("-inf")
    total_epochs = int(config.phobert_forward_looking_num_epochs)
    start_epoch = max(1, int(resume_checkpoint_state.get("next_epoch", 1) or 1))
    resume_epoch_rows_to_skip = max(0, int(resume_checkpoint_state.get("epoch_rows_to_skip", 0) or 0))
    resume_epoch_loss_sum = float(resume_checkpoint_state.get("epoch_loss_sum", 0.0) or 0.0)
    resume_epoch_optimizer_steps = int(resume_checkpoint_state.get("epoch_optimizer_steps", 0) or 0)
    global_optimizer_steps = int(resume_checkpoint_state.get("global_optimizer_steps", 0) or 0)
    checkpoint_steps = max(int(config.phobert_binary_head_training_checkpoint_steps), 0)
    last_checkpoint_state = dict(resume_checkpoint_state or {})
    text_column = f"{spec.dataset_prefix}_input_text"
    label_column = f"{spec.dataset_prefix}_label"
    split_column = f"{spec.dataset_prefix}_split"
    split_counts = dict(stage_summary.get("split_counts") or {})
    train_rows_target = int(split_counts.get("train", 0))
    val_rows_target = int(split_counts.get("val", 0))
    write_head_progress_line(
        spec,
        "train",
        "candidate="
        f"{candidate.name} runtime device={device} dtype={str(dtype).replace('torch.', '')} "
        f"amp={use_amp} train_rows={train_rows_target} val_rows={val_rows_target} "
        f"class_weighting={criterion_info['class_weighting_enabled']} "
        f"positive_class_weight={criterion_info['positive_class_weight']}",
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
            "criterion": criterion_info,
            "epoch_history": epoch_history,
            "current_epoch": int(start_epoch) if start_epoch <= total_epochs else int(total_epochs),
            "last_completed_epoch": max(int(start_epoch) - 1, 0),
            "training_checkpoint_steps": int(checkpoint_steps),
            "training_checkpoint": last_checkpoint_state,
        },
    )
    for epoch in range(start_epoch, total_epochs + 1):
        epoch_started = perf_counter()
        last_heartbeat_at = epoch_started
        last_heartbeat_rows = resume_epoch_rows_to_skip if epoch == start_epoch else 0
        rows_to_skip = resume_epoch_rows_to_skip if epoch == start_epoch else 0
        write_head_progress_line(
            spec,
            "train",
            "candidate="
            f"{candidate.name} epoch={epoch}/{total_epochs} start "
            f"device={device} train_rows_target={train_rows_target} resume_skip_rows={rows_to_skip}",
        )
        write_head_job_status(
            config,
            spec,
            status="running",
            phase="train",
            progress_updates={
                "current_candidate": candidate.name,
                "current_candidate_status": "in_progress",
                "current_epoch": int(epoch),
                "total_epochs": int(total_epochs),
                "epoch_train_rows": int(rows_to_skip),
                "device": device,
                "current_candidate_model": candidate.model_name,
                "training_checkpoint_steps": int(checkpoint_steps),
                "training_checkpoint": last_checkpoint_state,
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
        epoch_loss = resume_epoch_loss_sum if epoch == start_epoch else 0.0
        epoch_rows = resume_epoch_rows_to_skip if epoch == start_epoch else 0
        optimizer_steps = resume_epoch_optimizer_steps if epoch == start_epoch else 0
        accumulation_count = 0
        for record_batch in stream_stage_batches(
            spec,
            stage_path,
            split="train",
            columns=[text_column, label_column, split_column],
            batch_size=int(config.phobert_forward_looking_stream_batch_rows),
        ):
            batch_df = record_batch.to_pandas()
            if batch_df.empty:
                continue
            batch_df = batch_df.sample(frac=1.0, random_state=int(config.phobert_forward_looking_random_seed) + epoch).reset_index(drop=True)
            texts = batch_df[text_column].astype(str).tolist()
            labels = batch_df[label_column].astype(int).tolist()
            for offset in range(0, len(texts), int(config.phobert_forward_looking_train_micro_batch_size)):
                micro_texts = texts[offset : offset + int(config.phobert_forward_looking_train_micro_batch_size)]
                micro_labels = labels[offset : offset + int(config.phobert_forward_looking_train_micro_batch_size)]
                if rows_to_skip > 0:
                    if rows_to_skip >= len(micro_labels):
                        rows_to_skip -= int(len(micro_labels))
                        continue
                    micro_texts = micro_texts[rows_to_skip:]
                    micro_labels = micro_labels[rows_to_skip:]
                    rows_to_skip = 0
                encoded = tokenizer(micro_texts, padding=True, truncation=True, max_length=int(config.phobert_forward_looking_max_length), return_tensors="pt")
                labels_tensor = torch.tensor(micro_labels, dtype=torch.long)
                encoded = {key: value.to(device) for key, value in encoded.items()}
                labels_tensor = labels_tensor.to(device)
                autocast_context = (
                    torch.autocast(device_type="cuda", dtype=torch.float16, enabled=True) if use_amp else nullcontext()
                )
                with autocast_context:
                    outputs = model(**encoded)
                    loss = criterion(outputs.logits.float(), labels_tensor) / int(
                        config.phobert_forward_looking_gradient_accumulation_steps
                    )
                if use_amp:
                    scaler.scale(loss).backward()
                else:
                    loss.backward()
                epoch_loss += float(loss.detach().float().cpu().item()) * int(
                    config.phobert_forward_looking_gradient_accumulation_steps
                )
                epoch_rows += int(len(micro_labels))
                accumulation_count += 1
                if accumulation_count >= int(config.phobert_forward_looking_gradient_accumulation_steps):
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
                    global_optimizer_steps += 1
                    accumulation_count = 0
                    if checkpoint_steps > 0 and global_optimizer_steps % checkpoint_steps == 0:
                        last_checkpoint_state = save_training_checkpoint(
                            spec=spec,
                            output_dir=output_dir,
                            candidate=candidate,
                            model=model,
                            tokenizer=tokenizer,
                            optimizer=optimizer,
                            scaler=scaler,
                            torch=torch,
                            use_amp=use_amp,
                            epoch_history=epoch_history,
                            next_epoch=epoch,
                            epoch_rows_to_skip=epoch_rows,
                            epoch_loss_sum=epoch_loss,
                            epoch_optimizer_steps=optimizer_steps,
                            global_optimizer_steps=global_optimizer_steps,
                            best_epoch=best_epoch,
                            best_val_f1=best_val_f1,
                            checkpoint_reason="optimizer_step_interval",
                        )
                last_heartbeat_at, last_heartbeat_rows = maybe_emit_train_heartbeat(
                    spec=spec,
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
                    checkpoint_state=last_checkpoint_state,
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
            global_optimizer_steps += 1
            if checkpoint_steps > 0:
                last_checkpoint_state = save_training_checkpoint(
                    spec=spec,
                    output_dir=output_dir,
                    candidate=candidate,
                    model=model,
                    tokenizer=tokenizer,
                    optimizer=optimizer,
                    scaler=scaler,
                    torch=torch,
                    use_amp=use_amp,
                    epoch_history=epoch_history,
                    next_epoch=epoch,
                    epoch_rows_to_skip=epoch_rows,
                    epoch_loss_sum=epoch_loss,
                    epoch_optimizer_steps=optimizer_steps,
                    global_optimizer_steps=global_optimizer_steps,
                    best_epoch=best_epoch,
                    best_val_f1=best_val_f1,
                    checkpoint_reason="epoch_train_complete",
                )
        val_eval = evaluate_split(
            spec,
            config=config,
            stage_path=stage_path,
            split="val",
            tokenizer=tokenizer,
            model=model,
            device=device,
            max_length=int(config.phobert_forward_looking_max_length),
            micro_batch_size=int(config.phobert_forward_looking_eval_micro_batch_size),
            use_amp=use_amp,
            criterion=criterion,
            torch=torch,
            calibrate_threshold=True,
        )
        epoch_summary = {
            "epoch": int(epoch),
            "train_rows": int(epoch_rows),
            "optimizer_steps": int(optimizer_steps),
            "mean_train_loss": float(epoch_loss / max(epoch_rows, 1)),
            "val_summary": val_eval,
        }
        epoch_history.append(epoch_summary)
        epoch_elapsed = max(perf_counter() - epoch_started, 1e-9)
        epoch_rows_per_second = float(epoch_rows / epoch_elapsed) if epoch_rows else 0.0
        val_metrics = dict(val_eval.get("metrics") or {})
        write_head_progress_line(
            spec,
            "train",
            "candidate="
            f"{candidate.name} epoch={epoch}/{total_epochs} "
            f"train_rows={epoch_rows} val_f1={val_metrics.get('f1')} "
            f"val_roc_auc={val_metrics.get('roc_auc')} threshold={val_eval.get('decision_threshold')} "
            f"rate={epoch_rows_per_second:.1f} rows/s",
        )
        write_head_job_status(
            config,
            spec,
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
                "training_checkpoint": last_checkpoint_state,
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
                "criterion": criterion_info,
                "epoch_history": epoch_history,
                "training_checkpoint": last_checkpoint_state,
                "last_completed_epoch": int(epoch),
            },
        )
        val_f1 = safe_metric_value(val_eval["metrics"].get("f1"))
        if best_epoch < 0 or val_f1 > best_val_f1:
            best_val_f1 = val_f1
            best_epoch = int(epoch)
            model.save_pretrained(model_dir, safe_serialization=True)
            tokenizer.save_pretrained(model_dir)
        if checkpoint_steps > 0:
            last_checkpoint_state = save_training_checkpoint(
                spec=spec,
                output_dir=output_dir,
                candidate=candidate,
                model=model,
                tokenizer=tokenizer,
                optimizer=optimizer,
                scaler=scaler,
                torch=torch,
                use_amp=use_amp,
                epoch_history=epoch_history,
                next_epoch=epoch + 1,
                epoch_rows_to_skip=0,
                epoch_loss_sum=0.0,
                epoch_optimizer_steps=0,
                global_optimizer_steps=global_optimizer_steps,
                best_epoch=best_epoch,
                best_val_f1=best_val_f1,
                checkpoint_reason="epoch_complete",
            )
        resume_epoch_rows_to_skip = 0
        resume_epoch_loss_sum = 0.0
        resume_epoch_optimizer_steps = 0

    if not model_dir.exists():
        raise BinaryHeadTrainingError(f"No best checkpoint saved for {spec.name} candidate {candidate.name}")

    del model
    gc.collect()
    if device == "cuda":
        torch.cuda.empty_cache()

    reloaded_tokenizer = AutoTokenizer.from_pretrained(model_dir, use_fast=False, local_files_only=True)
    reloaded_model = AutoModelForSequenceClassification.from_pretrained(model_dir, local_files_only=True)
    reloaded_model.to(device)
    reloaded_model.eval()
    val_summary = evaluate_split(
        spec,
        config=config,
        stage_path=stage_path,
        split="val",
        tokenizer=reloaded_tokenizer,
        model=reloaded_model,
        device=device,
        max_length=int(config.phobert_forward_looking_max_length),
        micro_batch_size=int(config.phobert_forward_looking_eval_micro_batch_size),
        use_amp=use_amp,
        criterion=criterion,
        torch=torch,
        calibrate_threshold=True,
    )
    decision_threshold = float(val_summary.get("decision_threshold") or config.phobert_binary_head_default_positive_threshold(spec.name))
    train_summary = evaluate_split(
        spec,
        config=config,
        stage_path=stage_path,
        split="train",
        tokenizer=reloaded_tokenizer,
        model=reloaded_model,
        device=device,
        max_length=int(config.phobert_forward_looking_max_length),
        micro_batch_size=int(config.phobert_forward_looking_eval_micro_batch_size),
        use_amp=use_amp,
        criterion=criterion,
        torch=torch,
        positive_threshold=decision_threshold,
    )
    test_summary = evaluate_split(
        spec,
        config=config,
        stage_path=stage_path,
        split="test",
        tokenizer=reloaded_tokenizer,
        model=reloaded_model,
        device=device,
        max_length=int(config.phobert_forward_looking_max_length),
        micro_batch_size=int(config.phobert_forward_looking_eval_micro_batch_size),
        use_amp=use_amp,
        criterion=criterion,
        torch=torch,
        positive_threshold=decision_threshold,
    )
    result = {
        "candidate_name": candidate.name,
        "model_name": str(candidate.model_name),
        "model_dir": str(model_dir),
        "state_path": str(state_path),
        "metrics_path": str(metrics_path),
        "parameter_count": int(parameter_count),
        "device": device,
        "dtype": str(dtype).replace("torch.", ""),
        "best_epoch": int(best_epoch),
        "decision_threshold": float(decision_threshold),
        "epoch_history": epoch_history,
        "train_summary": train_summary,
        "val_summary": val_summary,
        "test_summary": test_summary,
        "torch_version": importlib.metadata.version("torch"),
        "transformers_version": importlib.metadata.version("transformers"),
        "stage_summary": dict(stage_summary),
        "criterion": criterion_info,
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
            "enable_class_weighting": bool(criterion_info["class_weighting_enabled"]),
            "positive_class_weight": criterion_info["positive_class_weight"],
            "split_strategy": str(stage_summary.get("split_strategy") or ""),
            "default_positive_threshold": float(config.phobert_binary_head_default_positive_threshold(spec.name)),
            "training_checkpoint_steps": int(checkpoint_steps),
        },
    }
    candidate_elapsed = max(perf_counter() - candidate_started, 1e-9)
    write_head_progress_line(
        spec,
        "train",
        "candidate="
        f"{candidate.name} complete best_epoch={best_epoch} "
        f"threshold={decision_threshold} "
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
    mark_training_checkpoint_complete(output_dir, result=result)
    del reloaded_model
    del reloaded_tokenizer
    gc.collect()
    if device == "cuda":
        torch.cuda.empty_cache()
    return result


def select_winner(
    *,
    candidates: Sequence[BinaryHeadCandidateSpec],
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
        "decision_threshold": float(winner.get("decision_threshold", 0.5)),
        "selection_metric": {
            "val_f1": safe_metric_value((winner.get("val_summary") or {}).get("metrics", {}).get("f1")),
            "val_roc_auc": safe_metric_value((winner.get("val_summary") or {}).get("metrics", {}).get("roc_auc")),
        },
        "test_metrics": dict((winner.get("test_summary") or {}).get("metrics") or {}),
    }


def train_binary_head_candidates(
    spec: BinaryHeadSpec,
    config: Optional[NewsFeaturesConfig] = None,
    *,
    trainer_fn: Optional[BinaryHeadTrainerFn] = None,
    candidate_names: Optional[Sequence[str]] = None,
    rerun_failed: bool = False,
) -> dict[str, object]:
    config = config or get_default_config()
    config.ensure_directories()
    head_model_artifacts_dir(config, spec).mkdir(parents=True, exist_ok=True)
    stage_manifest = ensure_stage_manifest(spec, config)
    stage_rows = int(stage_manifest.get("stage_rows", 0))
    if stage_rows <= 0:
        empty_summary = {
            "status": "no_stage_rows",
            "completed_candidates": 0,
            "failed_candidates": 0,
            "winner": None,
        }
        write_stage_run_summary(
            mode=f"{spec.summary_prefix}_winner_selection",
            name=f"{spec.dataset_prefix}_winner_selection",
            summary=empty_summary,
            artifacts={"training_manifest": head_training_manifest_path(config, spec)},
            metadata={"reason": "stage_dataset_empty"},
        )
        write_head_progress_line(spec, "train", "skipping candidate training because stage_rows=0")
        write_head_job_status(
            config,
            spec,
            status="no_stage_rows",
            phase="train",
            progress_updates={
                "stage_rows": 0,
                "completed_candidates": 0,
                "failed_candidates": 0,
                "candidate_filter": list(candidate_names or []),
                "rerun_failed": bool(rerun_failed),
            },
        )
        return empty_summary
    stage_path = head_stage_path(config, spec)
    if not stage_path.exists():
        raise BinaryHeadTrainingError(f"Stage dataset missing for {spec.name}: {stage_path}")
    all_candidates = candidate_specs(config)
    if candidate_names:
        allowed = {str(name) for name in candidate_names}
        all_candidates = [candidate for candidate in all_candidates if candidate.name in allowed]
    if not all_candidates:
        raise BinaryHeadTrainingError(f"No candidates selected for {spec.name}.")
    signature = training_signature(spec, config, stage_manifest=stage_manifest, candidates=all_candidates)
    training_manifest_path = head_training_manifest_path(config, spec)
    existing_manifest = load_json_payload(training_manifest_path)
    signature_digest = json_digest(signature)
    existing_candidates = dict(existing_manifest.get("candidates") or {})
    existing_status = str(existing_manifest.get("status") or "missing")
    if existing_manifest.get("signature_digest") != signature_digest or existing_status not in {"running", "complete"}:
        run_id = current_utc_timestamp().replace(":", "").replace("-", "").replace(".", "")
        manifest = {
            "status": "running",
            "head_name": spec.name,
            "run_id": run_id,
            "signature": signature,
            "signature_digest": signature_digest,
            "started_at": current_utc_timestamp(),
            "updated_at": current_utc_timestamp(),
            "candidates": {},
            "winner": None,
        }
    else:
        manifest = existing_manifest
        run_id = str(manifest.get("run_id"))
    write_json_atomic(training_manifest_path, manifest)
    stage_summary = stage_split_summary(stage_manifest)
    trainer = trainer_fn or (lambda candidate, cfg, stage, output, summary: default_train_binary_head_candidate(spec, candidate, cfg, stage, output, summary))
    started_at = current_utc_timestamp()
    write_head_progress_line(
        spec,
        "train",
        f"candidate plan={','.join(candidate.name for candidate in all_candidates)} stage_rows={stage_rows}",
    )
    write_head_job_status(
        config,
        spec,
        status="running",
        phase="train",
        progress_updates={
            "run_id": run_id,
            "candidate_names": [candidate.name for candidate in all_candidates],
            "stage_rows": stage_rows,
            "completed_candidates": 0,
            "failed_candidates": 0,
            "current_candidate": None,
            "current_candidate_status": None,
        },
        throughput_updates={"phase": "train", "unit": "rows_per_second", "current": None},
        started_at=started_at,
    )

    completed_count = 0
    failed_count = 0
    for candidate in all_candidates:
        current_state = dict((manifest.get("candidates") or {}).get(candidate.name) or {})
        current_status = str(current_state.get("status") or "")
        if current_status == "complete":
            completed_count += 1
            continue
        if current_status == "failed" and not rerun_failed:
            failed_count += 1
            continue
        output_dir = candidate_output_dir(config, spec, run_id, candidate.name)
        output_dir.mkdir(parents=True, exist_ok=True)
        write_head_progress_line(spec, "train", f"starting candidate={candidate.name} model={candidate.model_name}")
        write_head_job_status(
            config,
            spec,
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
        manifest.setdefault("candidates", {})[candidate.name] = entry
        write_json_atomic(training_manifest_path, manifest)
        try:
            result = trainer(candidate, config, stage_path, output_dir, stage_summary)
            entry.update(result)
            entry["status"] = "complete"
            entry["completed_at_utc"] = pd.Timestamp.utcnow().isoformat()
            manifest["candidates"][candidate.name] = entry
            completed_count += 1
            write_head_progress_line(
                spec,
                "train",
                "candidate="
                f"{candidate.name} complete val_f1={((entry.get('val_summary') or {}).get('metrics') or {}).get('f1')} "
                f"test_f1={((entry.get('test_summary') or {}).get('metrics') or {}).get('f1')}",
            )
            write_head_job_status(
                config,
                spec,
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
                mode=f"{spec.summary_prefix}_candidate_train",
                name=f"{spec.dataset_prefix}_candidate_{candidate.name}",
                summary={
                    "status": "complete",
                    "candidate_name": candidate.name,
                    "model_name": candidate.model_name,
                    "best_epoch": int(entry.get("best_epoch", 0)),
                    "decision_threshold": float(entry.get("decision_threshold", 0.5)),
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
            write_head_progress_line(spec, "train", f"candidate={candidate.name} failed: {entry['error']}")
            write_head_job_status(
                config,
                spec,
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
                mode=f"{spec.summary_prefix}_candidate_train",
                name=f"{spec.dataset_prefix}_candidate_{candidate.name}",
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
            manifest["updated_at"] = current_utc_timestamp()
            write_json_atomic(training_manifest_path, manifest)

    completed_entries = [
        dict(entry)
        for entry in (manifest.get("candidates") or {}).values()
        if str(entry.get("status", "")) == "complete"
    ]
    if completed_entries:
        winner = select_winner(candidates=all_candidates, completed_entries=completed_entries)
        manifest["winner"] = winner
        manifest["status"] = "complete"
        manifest["updated_at"] = current_utc_timestamp()
        write_json_atomic(head_latest_winner_path(config, spec), winner)
        update_manifest(
            config=config,
            **{
                f"{spec.dataset_prefix}_training_manifest": describe_path(training_manifest_path, config=config),
                f"{spec.dataset_prefix}_latest_winner": describe_path(head_latest_winner_path(config, spec), config=config),
            },
        )
        summary = {
            "status": "complete",
            "completed_candidates": int(len(completed_entries)),
            "failed_candidates": int(failed_count),
            "winner": winner,
        }
        write_stage_run_summary(
            mode=f"{spec.summary_prefix}_winner_selection",
            name=f"{spec.dataset_prefix}_winner_selection",
            summary=summary,
            artifacts={
                "latest_winner": head_latest_winner_path(config, spec),
                "training_manifest": training_manifest_path,
            },
            metadata={},
        )
        write_head_progress_line(
            spec,
            "winner_selection",
            f"winner={winner['candidate_name']} completed_candidates={len(completed_entries)} failed_candidates={failed_count}",
        )
    else:
        manifest["winner"] = None
        manifest["status"] = "no_winner"
        manifest["updated_at"] = current_utc_timestamp()
        summary = {
            "status": "no_winner",
            "completed_candidates": 0,
            "failed_candidates": int(failed_count),
            "winner": None,
        }
        write_stage_run_summary(
            mode=f"{spec.summary_prefix}_winner_selection",
            name=f"{spec.dataset_prefix}_winner_selection",
            summary=summary,
            artifacts={"training_manifest": training_manifest_path},
            metadata={},
        )
        write_head_progress_line(
            spec,
            "winner_selection",
            f"no winner completed_candidates=0 failed_candidates={failed_count}",
        )
    write_json_atomic(training_manifest_path, manifest)
    write_head_job_status(
        config,
        spec,
        status=str(manifest.get("status", "unknown")),
        phase="winner_selection",
        progress_updates={
            "current_candidate": None,
            "current_candidate_status": None,
            "completed_candidates": int(len(completed_entries)),
            "failed_candidates": int(failed_count),
            "stage_rows": stage_rows,
            "winner": manifest.get("winner"),
        },
    )
    return summary
