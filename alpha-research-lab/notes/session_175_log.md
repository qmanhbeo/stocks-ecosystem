# Session 175 Log - WSL CUDA Fail-Fast Guard For Heavy PhoBERT Jobs (2026-04-25)

## Objective

Stop wasting time on accidental CPU PhoBERT runs when this workstation's real
WSL runtime does have a GPU.

The immediate bug was not the trainer. It was runtime visibility:

- the restricted Codex sandbox hid `/dev/dxg`
- the same PhoBERT train command therefore fell back to CPU
- the real WSL runtime outside that sandbox still exposed the RTX 3050 and
  PyTorch CUDA correctly

This session did not change the live alpha branch.
It stayed long-only.

## What changed

### Runtime diagnosis

Confirmed the split between the restricted sandbox and the real WSL runtime:

- outside the restricted sandbox:
  - `/dev/dxg` exists
  - `/usr/lib/wsl/lib/nvidia-smi` reports the RTX 3050 Laptop GPU
  - PyTorch reports `cuda_available=True`
- inside the restricted sandbox:
  - `/dev/dxg` is hidden
  - the same PyTorch build reports `cuda_available=False`

### Local runtime hardening

Extended `research_pipelines/news_features/local_runtime.py` so the repo now:

- prepends `/usr/lib/wsl/lib` into `PATH` and `LD_LIBRARY_PATH` when present
- exposes compact CUDA diagnostics for the local PhoBERT lanes
- hard-fails heavy PhoBERT train/publish paths on this WSL workstation when
  the real WSL CUDA runtime exists but the current session hides `/dev/dxg`
- allows CPU only as an explicit override through `NEWS_FEATURES_ALLOW_CPU=1`

### Heavy PhoBERT surfaces now guarded

Applied that fail-fast CUDA guard to:

- PhoBERT sentiment publish
- PhoBERT forward-looking train
- PhoBERT forward-looking publish
- PhoBERT `article_scope` train
- PhoBERT `article_scope` publish
- PhoBERT `source_type` train
- PhoBERT `source_type` publish

### Operator docs

Updated the news-features README and live-state note so the runtime contract is
explicit:

- hidden-GPU WSL sessions are treated as runtime errors
- CPU fallback is opt-in, not silent default

## Verification

Completed during this pass:

- `python -m py_compile research_pipelines/news_features/local_runtime.py research_pipelines/news_features/core/phobert_forward_looking_train.py research_pipelines/news_features/core/phobert_binary_head_train.py research_pipelines/news_features/core/build_phobert_forward_looking_features.py research_pipelines/news_features/core/phobert_binary_head_publish.py research_pipelines/news_features/core/build_phobert_sentiment_features.py research_pipelines/news_features/tests/test_feature_builders.py`
- `python -m pytest research_pipelines/news_features/tests/test_feature_builders.py -q`
  - `38 passed`

System/runtime probes completed:

- `/usr/lib/wsl/lib/nvidia-smi`
  - reported the RTX 3050 Laptop GPU
- `python -c "import torch; ..."`
  - outside the restricted sandbox reported:
    - `cuda_available=True`
    - `device_count=1`
    - `device_name='NVIDIA GeForce RTX 3050 Laptop GPU'`

Live canary verification completed:

- relaunched `train_phobert_article_scope --candidate-name phobert_base`
  outside the restricted sandbox
- observed:
  - `runtime device=cuda dtype=float16 amp=True`
  - heartbeat around `23.3 rows/s`
  - `nvidia-smi` during the run showed roughly:
    - `2896MiB / 4096MiB` VRAM in use
    - `87%` GPU utilization
    - meaning the current micro-batch shape already uses most of the safe GPU
      headroom on this box

What was not executed:

- the full sequential four-job train/publish chain was not completed in this
  session log
- no final binary-head winner selection was recorded yet from this new GPU
  canary

## Results

- worked:
  - the repo now stops hidden-GPU WSL sessions before they burn time on CPU
  - the real WSL GPU path was verified and a fresh article-scope canary did
    start on CUDA
  - the runtime contract is now explicit in code and docs
- unresolved:
  - agent-run heavy PhoBERT jobs still need an unsandboxed session to reach the
    real WSL GPU
  - the remaining source-type train/publish and article-scope/source-type
    completion still need the sequential watchdog pass

## Durable Promotion Status

- promoted findings:
  - `F278`
- promoted dead ends:
  - none

## Pointers

- live state:
  - `notes/live_state.md`
- durable findings touched:
  - `notes/findings-271-300.md#f278`
