# Session 166 Log - PhoBERT Forward-Looking Watchdog Canary (2026-04-24)

## Objective

Take the newly split PhoBERT forward-looking lane through the first real
watchdog-managed production canary, and repair any local runtime blockers that
prevent the first explicit candidate from training on the current workstation.

This session did not change the live alpha branch.
It stayed long-only.
It was an infrastructure / local-ML pass, not a research result.

---

## What changed

Updated the forward-looking lane itself:
- added the canonical watchdog heartbeat:
  - `alpha-research-lab/artifacts/job_status/phobert_forward_looking_train.json`
- added milestone progress logs for:
  - teacher
  - stage
  - candidate training
  - winner selection
- changed training preflight so resume runs reuse the stage manifest instead of
  loading the full stage parquet into RAM just to decide whether training can
  start
- updated `research_pipelines/news_features/README.md` with the canary-first
  launch rule, status path, and resume surfaces

Repaired two real runtime blockers found by the first production canary:
- `transformers 4.57.6` + `torch 2.5.1+cu121` now blocks legacy `.bin`
  checkpoint loads under `weights_only=True`, so the explicit trusted backbone
  list now retries with `weights_only=False` when needed
- the trainer was instantiating the model directly in FP16 before using AMP;
  that caused `ValueError: Attempting to unscale FP16 gradients`, so the model
  load now stays FP32 and AMP owns the precision change

---

## Real canary state

Real production teacher / stage artifacts were created cleanly:
- teacher labels:
  - `data/features/news/datasets/phobert_forward_looking_teacher_labels.parquet`
  - `79,284` rows
- teacher manifest:
  - `data/features/news/datasets/phobert_forward_looking_teacher_manifest.json`
- stage dataset:
  - `data/features/news/datasets/phobert_forward_looking_stage_articles.parquet`
  - `40,065` rows
- stage manifest:
  - `data/features/news/datasets/phobert_forward_looking_stage_manifest.json`
  - split counts:
    - `train 26,113`
    - `val 6,736`
    - `test 7,216`

Real production run summaries were also repaired for the completed phases:
- `artifacts/run_summaries/latest_news_forward_looking_teacher_labels.json`
- `artifacts/run_summaries/latest_news_forward_looking_stage_build.json`

Current canary command:
- `python -m research_pipelines.news_features.core.train_phobert_forward_looking --stages teacher,stage,train --candidate-name phobert_base --rerun-failed`

Current live state at writeback time:
- training process is still alive outside the sandbox
- watchdog heartbeat:
  - `status=running`
  - `phase=train`
  - `candidate=phobert_base`
  - `run_id=7abc8627d84b`
- external process check showed the canary was still consuming real CPU time on
  the target box after the runtime fixes

Important current limitation:
- the training heartbeat is still epoch-level, so the status file may remain
  unchanged during a long first epoch
- until that is tightened, a future watchdog pass should confirm the live
  process before calling the canary stalled

---

## Validation

Completed during this pass:
- `python3 -m py_compile research_pipelines/news_features/core/phobert_forward_looking_train.py`
- `python3 -m pytest research_pipelines/news_features/tests/test_feature_builders.py -k 'forward_looking'`
  - `4 passed`
- ran the real production canary multiple times and read:
  - the watchdog status file
  - the production teacher manifest
  - the production stage manifest
  - the production training manifest
  - the latest forward-looking run summaries

What was not completed yet:
- the single-candidate canary has started real training, but it had not reached
  the first epoch-summary heartbeat by the end of this pass
- the full candidate set has not been started yet

---

## Next step

Let the current `phobert_base` canary finish.
If it completes, inspect the candidate and winner summaries and then expand to
the full candidate set by dropping `--candidate-name`.
If it fails again, inspect the training manifest and patch only the local
training surface before relaunching.
