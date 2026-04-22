#!/usr/bin/env python
"""Probe Vietnamese sentiment inference feasibility on the local WSL stack.

This script is intentionally small and self-contained so it can be rerun after
environment changes without depending on the research pipeline. It validates the
core constraints for PhoBERT-style sentiment inference:

1. required packages import cleanly
2. Vietnamese word segmentation is applied before tokenization
3. a sequence-classification checkpoint can load on the available device
4. the three reference strings can run as one batch with timing and RAM stats
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import resource
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any

import psutil
import torch
from pyvi import ViTokenizer
from transformers import AutoModelForSequenceClassification, AutoTokenizer


# Prefer a safetensors-backed finetune. Some community PhoBERT checkpoints still
# ship only legacy pytorch_model.bin weights, and current transformers versions
# will reject those on torch<2.6 because of the 2025 torch.load CVE guard.
DEFAULT_MODEL = "Angelectronic/phobert-base-vietnamese-sentiment"

SAMPLES = [
    {
        "name": "positive_growth",
        "raw_text": "Lợi nhuận quý 3 của Hòa Phát tăng trưởng vượt kỳ vọng.",
        "expected": "POS",
    },
    {
        "name": "negative_selloff",
        "raw_text": "Thị trường chứng khoán giảm điểm mạnh do áp lực bán tháo.",
        "expected": "NEG",
    },
    {
        "name": "neutral_board_meeting",
        "raw_text": "Hội đồng quản trị tổ chức họp thường niên vào thứ Hai.",
        "expected": "NEU",
    },
]

# Some community finetunes do not always persist a friendly id2label mapping.
MODEL_LABEL_OVERRIDES: dict[str, dict[int, str]] = {
    "wonrax/phobert-base-vietnamese-sentiment": {0: "NEG", 1: "POS", 2: "NEU"},
    "Angelectronic/phobert-base-vietnamese-sentiment": {0: "NEG", 1: "POS", 2: "NEU"},
}


@dataclass
class ProbeRow:
    name: str
    raw_text: str
    segmented_text: str
    expected: str
    predicted: str
    confidence: float
    match_expected: bool
    probabilities: dict[str, float]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL, help="HF model id to probe")
    parser.add_argument(
        "--max-length",
        type=int,
        default=256,
        help="Tokenizer truncation length",
    )
    parser.add_argument(
        "--precision",
        choices=["auto", "fp32", "fp16"],
        default="auto",
        help="Torch dtype policy. 'auto' uses fp16 on CUDA and fp32 otherwise.",
    )
    parser.add_argument(
        "--skip-nvidia-smi",
        action="store_true",
        help="Skip shelling out to nvidia-smi when collecting environment metadata.",
    )
    return parser.parse_args()


def _ru_maxrss_mb() -> float:
    # Linux reports ru_maxrss in KiB.
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def _process_rss_mb() -> float:
    return psutil.Process().memory_info().rss / (1024.0 * 1024.0)


def _choose_device() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"


def _choose_dtype(precision: str, device: str) -> torch.dtype:
    if precision == "fp32":
        return torch.float32
    if precision == "fp16":
        return torch.float16
    if device.startswith("cuda"):
        return torch.float16
    return torch.float32


def _canonical_label(raw_label: str) -> str:
    label = raw_label.strip().upper()
    if "NEG" in label or label in {"0", "LABEL_0", "NEGATIVE"}:
        return "NEG"
    if "POS" in label or label in {"1", "LABEL_1", "POSITIVE"}:
        return "POS"
    if "NEU" in label or "NEUTRAL" in label or label in {"2", "LABEL_2"}:
        return "NEU"
    return label


def _resolve_id2label(model_id: str, model: AutoModelForSequenceClassification) -> dict[int, str]:
    override = MODEL_LABEL_OVERRIDES.get(model_id)
    if override:
        return override

    config_map = getattr(model.config, "id2label", {}) or {}
    resolved: dict[int, str] = {}
    for key, value in config_map.items():
        try:
            idx = int(key)
        except (TypeError, ValueError):
            idx = key
        if isinstance(idx, int):
            resolved[idx] = _canonical_label(str(value))
    if resolved:
        return resolved

    return {idx: f"LABEL_{idx}" for idx in range(getattr(model.config, "num_labels", 0))}


def _collect_nvidia_smi(skip: bool) -> dict[str, Any] | None:
    if skip:
        return None
    try:
        command = [
            "nvidia-smi",
            "--query-gpu=name,driver_version,memory.total,memory.used",
            "--format=csv,noheader,nounits",
        ]
        output = subprocess.check_output(command, text=True, stderr=subprocess.STDOUT).strip()
        if not output:
            return None
        name, driver_version, memory_total_mb, memory_used_mb = [part.strip() for part in output.split(",")]
        return {
            "name": name,
            "driver_version": driver_version,
            "memory_total_mb": float(memory_total_mb),
            "memory_used_mb": float(memory_used_mb),
        }
    except Exception as exc:  # pragma: no cover - diagnostic only
        return {"error": repr(exc)}


def _load_model(model_id: str, device: str, dtype: torch.dtype) -> tuple[Any, Any, float, str]:
    load_start = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(model_id, use_fast=False)
    load_dtype = dtype
    try:
        model = AutoModelForSequenceClassification.from_pretrained(model_id, dtype=load_dtype)
    except Exception:
        if device.startswith("cuda") and load_dtype == torch.float16:
            load_dtype = torch.float32
            model = AutoModelForSequenceClassification.from_pretrained(model_id, dtype=load_dtype)
        else:
            raise
    model.to(device)
    model.eval()
    if device.startswith("cuda"):
        torch.cuda.synchronize()
    load_elapsed = time.perf_counter() - load_start
    return tokenizer, model, load_elapsed, str(load_dtype).replace("torch.", "")


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    device = _choose_device()
    dtype = _choose_dtype(args.precision, device)
    initial_rss_mb = _process_rss_mb()
    initial_peak_rss_mb = _ru_maxrss_mb()

    tokenizer, model, load_time_s, effective_dtype = _load_model(args.model, device, dtype)

    rows_input = []
    for sample in SAMPLES:
        segmented = ViTokenizer.tokenize(sample["raw_text"])
        rows_input.append(
            {
                "name": sample["name"],
                "raw_text": sample["raw_text"],
                "segmented_text": segmented,
                "expected": sample["expected"],
            }
        )

    preprocess_start = time.perf_counter()
    encoded = tokenizer(
        [row["segmented_text"] for row in rows_input],
        padding=True,
        truncation=True,
        max_length=args.max_length,
        return_tensors="pt",
    )
    preprocess_time_s = time.perf_counter() - preprocess_start
    encoded = {key: value.to(device) for key, value in encoded.items()}

    if device.startswith("cuda"):
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()

    inference_start = time.perf_counter()
    with torch.inference_mode():
        logits = model(**encoded).logits
        probabilities = torch.softmax(logits.float(), dim=-1)
    if device.startswith("cuda"):
        torch.cuda.synchronize()
    inference_time_s = time.perf_counter() - inference_start

    id2label = _resolve_id2label(args.model, model)
    rows: list[ProbeRow] = []
    predicted_ids = probabilities.argmax(dim=-1).tolist()
    probabilities_list = probabilities.cpu().tolist()
    for row_input, predicted_id, prob_vector in zip(rows_input, predicted_ids, probabilities_list):
        label_probabilities: dict[str, float] = {}
        for idx, prob in enumerate(prob_vector):
            label = id2label.get(idx, f"LABEL_{idx}")
            label_probabilities[label] = float(prob)
        predicted_label = id2label.get(predicted_id, f"LABEL_{predicted_id}")
        rows.append(
            ProbeRow(
                name=row_input["name"],
                raw_text=row_input["raw_text"],
                segmented_text=row_input["segmented_text"],
                expected=row_input["expected"],
                predicted=predicted_label,
                confidence=float(label_probabilities[predicted_label]),
                match_expected=predicted_label == row_input["expected"],
                probabilities=label_probabilities,
            )
        )

    peak_rss_mb = max(_ru_maxrss_mb(), initial_peak_rss_mb)
    current_rss_mb = _process_rss_mb()
    gpu_peak_memory_mb = None
    if device.startswith("cuda"):
        gpu_peak_memory_mb = torch.cuda.max_memory_allocated() / (1024.0 * 1024.0)

    return {
        "started_at_utc": started_at,
        "model": args.model,
        "device": device,
        "dtype": effective_dtype,
        "cuda_available": torch.cuda.is_available(),
        "environment": {
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "transformers": importlib.metadata.version("transformers"),
            "pyvi": importlib.metadata.version("pyvi"),
            "nvidia_smi": _collect_nvidia_smi(args.skip_nvidia_smi),
        },
        "metrics": {
            "load_time_s": load_time_s,
            "preprocess_time_s": preprocess_time_s,
            "inference_time_s": inference_time_s,
            "batch_size": len(SAMPLES),
            "initial_rss_mb": initial_rss_mb,
            "current_rss_mb": current_rss_mb,
            "peak_rss_mb": peak_rss_mb,
            "peak_rss_delta_mb": peak_rss_mb - initial_rss_mb,
            "gpu_peak_memory_mb": gpu_peak_memory_mb,
        },
        "rows": [asdict(row) for row in rows],
        "summary": {
            "matched_expected_count": sum(row.match_expected for row in rows),
            "total_count": len(rows),
        },
    }


def main() -> None:
    args = parse_args()
    result = run_probe(args)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
